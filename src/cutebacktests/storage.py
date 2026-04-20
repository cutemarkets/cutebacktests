from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime
import json
import os
from pathlib import Path
import threading
import time
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

import duckdb

from .models import BacktestTrade, DisclosureEvent, PaperOrder, Signal

_DUCKDB_CONNECT_LOCK = threading.Lock()
_DUCKDB_SCHEMA_LOCK = threading.Lock()
_DUCKDB_WRITE_LOCK = threading.Lock()


def _is_unique_file_handle_conflict(exc: Exception) -> bool:
    message = str(exc or "").lower()
    return "unique file handle conflict" in message and "already attached" in message


def _is_catalog_write_conflict(exc: Exception) -> bool:
    message = str(exc or "").lower()
    return "catalog write-write conflict" in message


def _is_duplicate_key_conflict(exc: Exception) -> bool:
    message = str(exc or "").lower()
    return "duplicate key" in message


def _is_internal_unaligned_fetch_error(exc: Exception) -> bool:
    message = str(exc or "").lower()
    return "unaligned fetch in validity and main column data for update" in message


def _is_transient_write_error(exc: Exception) -> bool:
    return (
        _is_catalog_write_conflict(exc)
        or _is_duplicate_key_conflict(exc)
        or _is_internal_unaligned_fetch_error(exc)
    )


def _sql_text_literal(value: Any) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _sql_value_literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, datetime):
        return _sql_text_literal(value.isoformat())
    if isinstance(value, date):
        return _sql_text_literal(value.isoformat())
    if isinstance(value, (int, float)):
        return str(value)
    return _sql_text_literal(value)


def _resolve_stock_bar_insert_mode() -> str:
    mode = str(os.getenv("CUTEBACKTESTS_STOCK_BAR_INSERT_MODE", "literal") or "").strip().lower()
    if mode in {"literal", "stage", "auto"}:
        return mode
    return "literal"


def _resolve_db_read_only(default: bool = False) -> bool:
    raw = str(os.getenv("CUTEBACKTESTS_DB_READ_ONLY", "") or "").strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    return bool(default)


class DataStore:
    def __init__(self, db_path: Path, *, read_only: bool = False):
        self.db_path = Path(db_path)
        self.read_only = _resolve_db_read_only(default=bool(read_only))
        if not self.read_only:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.con = self._connect_with_retry()
        self._stock_bar_insert_mode = _resolve_stock_bar_insert_mode()
        self._stock_bar_stage_ready = False
        self._stock_bar_fast_upsert_supported = self._stock_bar_insert_mode != "literal"
        if not self.read_only:
            self._init_schema_with_retry()

    def _connect_with_retry(self) -> duckdb.DuckDBPyConnection:
        max_attempts = 5
        for attempt in range(1, max_attempts + 1):
            try:
                with _DUCKDB_CONNECT_LOCK:
                    return duckdb.connect(str(self.db_path), read_only=self.read_only)
            except duckdb.BinderException as exc:
                if attempt >= max_attempts or not _is_unique_file_handle_conflict(exc):
                    raise
                time.sleep(0.05 * attempt)
        raise RuntimeError("DuckDB connect retry loop exhausted unexpectedly")

    def close(self) -> None:
        self.con.close()

    def _init_schema_with_retry(self) -> None:
        max_attempts = 10
        for attempt in range(1, max_attempts + 1):
            try:
                with _DUCKDB_SCHEMA_LOCK:
                    self.init_schema()
                return
            except Exception as exc:
                if attempt >= max_attempts or not _is_catalog_write_conflict(exc):
                    raise
                time.sleep(0.05 * attempt)
        raise RuntimeError("DuckDB schema init retry loop exhausted unexpectedly")

    def init_schema(self) -> None:
        self.con.execute(
            """
            CREATE TABLE IF NOT EXISTS disclosures (
                id TEXT PRIMARY KEY,
                person TEXT,
                ticker TEXT,
                transaction_type TEXT,
                amount_bucket TEXT,
                owner TEXT,
                traded_at TIMESTAMP,
                disclosed_at TIMESTAMP,
                source TEXT,
                raw TEXT
            )
            """
        )
        self.con.execute(
            """
            CREATE TABLE IF NOT EXISTS stock_bars (
                ticker TEXT,
                ts TIMESTAMP,
                open DOUBLE,
                high DOUBLE,
                low DOUBLE,
                close DOUBLE,
                volume BIGINT,
                PRIMARY KEY(ticker, ts)
            )
            """
        )
        self.con.execute(
            """
            CREATE TABLE IF NOT EXISTS stock_bar_coverage (
                ticker TEXT,
                timeframe TEXT,
                start_ts TIMESTAMP,
                end_ts TIMESTAMP,
                updated_at TIMESTAMP,
                PRIMARY KEY(ticker, timeframe, start_ts, end_ts)
            )
            """
        )
        self.con.execute(
            """
            CREATE TABLE IF NOT EXISTS option_chain (
                option_symbol TEXT,
                underlying TEXT,
                ts TIMESTAMP,
                expiration DATE,
                strike DOUBLE,
                option_type TEXT,
                bid DOUBLE,
                ask DOUBLE,
                delta DOUBLE,
                iv DOUBLE,
                open_interest BIGINT,
                volume BIGINT,
                PRIMARY KEY(option_symbol, ts)
            )
            """
        )
        self.con.execute(
            """
            CREATE TABLE IF NOT EXISTS option_bars (
                symbol TEXT,
                ts TIMESTAMP,
                open DOUBLE,
                high DOUBLE,
                low DOUBLE,
                close DOUBLE,
                volume BIGINT,
                PRIMARY KEY(symbol, ts)
            )
            """
        )
        self.con.execute(
            """
            CREATE TABLE IF NOT EXISTS option_quotes (
                symbol TEXT,
                ts TIMESTAMP,
                bid DOUBLE,
                ask DOUBLE,
                bid_size BIGINT,
                ask_size BIGINT,
                PRIMARY KEY(symbol, ts)
            )
            """
        )
        self.con.execute(
            """
            CREATE TABLE IF NOT EXISTS stock_daily_bars (
                ticker TEXT,
                day DATE,
                ts TIMESTAMP,
                open DOUBLE,
                high DOUBLE,
                low DOUBLE,
                close DOUBLE,
                volume BIGINT,
                PRIMARY KEY(ticker, day)
            )
            """
        )
        self.con.execute(
            """
            CREATE TABLE IF NOT EXISTS option_contract_cache (
                underlying TEXT,
                trading_day DATE,
                option_type TEXT,
                status TEXT,
                option_min_dte INTEGER,
                option_target_dte INTEGER,
                option_max_dte INTEGER,
                option_min_open_interest BIGINT,
                found BOOLEAN,
                payload TEXT,
                updated_at TIMESTAMP,
                PRIMARY KEY(
                    underlying,
                    trading_day,
                    option_type,
                    status,
                    option_min_dte,
                    option_target_dte,
                    option_max_dte,
                    option_min_open_interest
                )
            )
            """
        )
        self.con.execute(
            """
            CREATE TABLE IF NOT EXISTS option_contract_list_cache (
                underlying TEXT,
                trading_day DATE,
                option_type TEXT,
                status TEXT,
                option_min_dte INTEGER,
                option_max_dte INTEGER,
                found BOOLEAN,
                payload TEXT,
                updated_at TIMESTAMP,
                PRIMARY KEY(
                    underlying,
                    trading_day,
                    option_type,
                    status,
                    option_min_dte,
                    option_max_dte
                )
            )
            """
        )
        self.con.execute(
            """
            CREATE TABLE IF NOT EXISTS option_contract_universe_cache (
                underlying TEXT,
                option_type TEXT,
                status TEXT,
                option_min_dte INTEGER,
                option_max_dte INTEGER,
                found BOOLEAN,
                payload TEXT,
                updated_at TIMESTAMP,
                PRIMARY KEY(
                    underlying,
                    option_type,
                    status,
                    option_min_dte,
                    option_max_dte
                )
            )
            """
        )
        self.con.execute(
            """
            CREATE TABLE IF NOT EXISTS option_contract_fetch_preference (
                underlying TEXT,
                option_type TEXT,
                requested_status TEXT,
                option_min_dte INTEGER,
                option_max_dte INTEGER,
                preferred_status TEXT,
                preferred_as_of_mode TEXT,
                updated_at TIMESTAMP,
                PRIMARY KEY(
                    underlying,
                    option_type,
                    requested_status,
                    option_min_dte,
                    option_max_dte
                )
            )
            """
        )
        self.con.execute(
            """
            CREATE TABLE IF NOT EXISTS signals (
                signal_id TEXT PRIMARY KEY,
                disclosure_id TEXT,
                ticker TEXT,
                direction INTEGER,
                conviction DOUBLE,
                generated_at TIMESTAMP,
                model_tag TEXT,
                metadata TEXT
            )
            """
        )
        self.con.execute(
            """
            CREATE TABLE IF NOT EXISTS backtest_trades (
                trade_id TEXT PRIMARY KEY,
                signal_id TEXT,
                ticker TEXT,
                option_symbol TEXT,
                entry_ts TIMESTAMP,
                exit_ts TIMESTAMP,
                side TEXT,
                qty INTEGER,
                entry_price DOUBLE,
                exit_price DOUBLE,
                pnl DOUBLE,
                return_pct DOUBLE,
                status TEXT,
                metadata TEXT
            )
            """
        )
        self.con.execute(
            """
            CREATE TABLE IF NOT EXISTS paper_orders (
                local_id TEXT PRIMARY KEY,
                signal_id TEXT,
                ticker TEXT,
                option_symbol TEXT,
                side TEXT,
                qty INTEGER,
                limit_price DOUBLE,
                status TEXT,
                submitted_at TIMESTAMP,
                broker_order_id TEXT,
                raw TEXT
            )
            """
        )

    def insert_disclosures(self, rows: Iterable[DisclosureEvent]) -> int:
        count = 0
        for row in rows:
            self.con.execute(
                """
                INSERT OR REPLACE INTO disclosures
                (id, person, ticker, transaction_type, amount_bucket, owner, traded_at, disclosed_at, source, raw)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    row.id,
                    row.person,
                    row.ticker,
                    row.transaction_type,
                    row.amount_bucket,
                    row.owner,
                    row.traded_at,
                    row.disclosed_at,
                    row.source,
                    json.dumps(row.raw),
                ],
            )
            count += 1
        return count

    def get_disclosures(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        person_contains: Optional[str] = None,
        ticker: Optional[str] = None,
    ) -> List[DisclosureEvent]:
        where = []
        params: List[Any] = []
        if start is not None:
            where.append("disclosed_at >= ?")
            params.append(start)
        if end is not None:
            where.append("disclosed_at <= ?")
            params.append(end)
        if person_contains:
            where.append("LOWER(person) LIKE ?")
            params.append("%" + person_contains.lower() + "%")
        if ticker:
            where.append("ticker = ?")
            params.append(ticker)

        query = "SELECT * FROM disclosures"
        if where:
            query += " WHERE " + " AND ".join(where)
        query += " ORDER BY disclosed_at ASC"

        out: List[DisclosureEvent] = []
        for row in self.con.execute(query, params).fetchall():
            out.append(
                DisclosureEvent(
                    id=row[0],
                    person=row[1],
                    ticker=row[2],
                    transaction_type=row[3],
                    amount_bucket=row[4],
                    owner=row[5],
                    traded_at=row[6],
                    disclosed_at=row[7],
                    source=row[8],
                    raw=json.loads(row[9] or "{}"),
                )
            )
        return out

    def latest_disclosure_timestamp(self) -> Optional[datetime]:
        row = self.con.execute("SELECT max(disclosed_at) FROM disclosures").fetchone()
        if not row:
            return None
        return row[0]

    def get_disclosure_ids(self, source: Optional[str] = None) -> Set[str]:
        where = []
        params: List[Any] = []
        if source:
            where.append("source = ?")
            params.append(source)

        query = "SELECT id FROM disclosures"
        if where:
            query += " WHERE " + " AND ".join(where)

        rows = self.con.execute(query, params).fetchall()
        return {str(row[0]) for row in rows if row and row[0]}

    def insert_stock_bars(self, rows: Iterable[Dict[str, Any]]) -> int:
        payload = [
            [
                row.get("ticker"),
                row.get("ts"),
                row.get("open"),
                row.get("high"),
                row.get("low"),
                row.get("close"),
                int(row.get("volume") or 0),
            ]
            for row in rows
        ]
        if not payload:
            return 0
        with _DUCKDB_WRITE_LOCK:
            if self._stock_bar_insert_mode != "literal" and self._stock_bar_fast_upsert_supported:
                max_attempts = 5
                for attempt in range(1, max_attempts + 1):
                    try:
                        self._insert_stock_bars_via_stage(payload)
                        return len(payload)
                    except Exception as exc:
                        if attempt >= max_attempts or not _is_transient_write_error(exc):
                            self._stock_bar_fast_upsert_supported = False
                            break
                        time.sleep(0.02 * attempt)
            self._insert_stock_bars_literal(payload)
        return len(payload)

    def _ensure_stock_bar_stage_table(self) -> None:
        if self._stock_bar_stage_ready:
            return
        self.con.execute(
            """
            CREATE TEMP TABLE IF NOT EXISTS cutebacktests_stage_stock_bars (
                ticker TEXT,
                ts TIMESTAMP,
                open DOUBLE,
                high DOUBLE,
                low DOUBLE,
                close DOUBLE,
                volume BIGINT
            )
            """
        )
        self._stock_bar_stage_ready = True

    def _insert_stock_bars_via_stage(self, payload: Sequence[Sequence[Any]]) -> None:
        self._ensure_stock_bar_stage_table()
        self.con.execute("DELETE FROM cutebacktests_stage_stock_bars")
        try:
            self.con.executemany(
                """
                INSERT INTO cutebacktests_stage_stock_bars
                (ticker, ts, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                payload,
            )
            self.con.execute(
                """
                MERGE INTO stock_bars AS target
                USING cutebacktests_stage_stock_bars AS src
                ON target.ticker = src.ticker AND target.ts = src.ts
                WHEN MATCHED THEN UPDATE SET
                    open = src.open,
                    high = src.high,
                    low = src.low,
                    close = src.close,
                    volume = src.volume
                WHEN NOT MATCHED THEN INSERT
                    (ticker, ts, open, high, low, close, volume)
                VALUES
                    (src.ticker, src.ts, src.open, src.high, src.low, src.close, src.volume)
                """
            )
        finally:
            self.con.execute("DELETE FROM cutebacktests_stage_stock_bars")

    def _insert_stock_bars_literal(self, payload: Sequence[Sequence[Any]]) -> None:
        chunk_size = 500
        max_attempts = 5
        for attempt in range(1, max_attempts + 1):
            try:
                for offset in range(0, len(payload), chunk_size):
                    batch = payload[offset : offset + chunk_size]
                    values_sql = ", ".join(
                        "("
                        + ", ".join(_sql_value_literal(value) for value in item)
                        + ")"
                        for item in batch
                    )
                    self.con.execute(
                        f"""
                        INSERT INTO stock_bars
                        (ticker, ts, open, high, low, close, volume)
                        VALUES {values_sql}
                        ON CONFLICT (ticker, ts) DO UPDATE SET
                            open = EXCLUDED.open,
                            high = EXCLUDED.high,
                            low = EXCLUDED.low,
                            close = EXCLUDED.close,
                            volume = EXCLUDED.volume
                        """
                    )
                return
            except Exception as exc:
                if _is_duplicate_key_conflict(exc) or _is_internal_unaligned_fetch_error(exc):
                    try:
                        for item in payload:
                            values_sql = "(" + ", ".join(_sql_value_literal(value) for value in item) + ")"
                            self.con.execute(
                                f"""
                                INSERT INTO stock_bars
                                (ticker, ts, open, high, low, close, volume)
                                VALUES {values_sql}
                                ON CONFLICT (ticker, ts) DO UPDATE SET
                                    open = EXCLUDED.open,
                                    high = EXCLUDED.high,
                                    low = EXCLUDED.low,
                                    close = EXCLUDED.close,
                                    volume = EXCLUDED.volume
                                """
                            )
                        return
                    except Exception as row_exc:
                        if attempt >= max_attempts or not _is_transient_write_error(row_exc):
                            raise
                        time.sleep(0.02 * attempt)
                        continue
                if attempt >= max_attempts or not _is_transient_write_error(exc):
                    raise
                time.sleep(0.02 * attempt)

    def get_stock_bars(
        self,
        ticker: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        where = [f"ticker = {_sql_value_literal(ticker)}"]
        if start is not None:
            where.append(f"ts >= {_sql_value_literal(start)}")
        if end is not None:
            where.append(f"ts <= {_sql_value_literal(end)}")

        query = """
            SELECT ticker, ts, open, high, low, close, volume
            FROM stock_bars
            WHERE {where}
            ORDER BY ts ASC
        """.format(where=" AND ".join(where))

        return [
            {
                "ticker": row[0],
                "ts": row[1],
                "open": row[2],
                "high": row[3],
                "low": row[4],
                "close": row[5],
                "volume": row[6],
            }
            for row in self.con.execute(query).fetchall()
        ]

    def get_stock_bars_range(
        self,
        ticker: str,
        start: datetime,
        end: datetime,
    ) -> List[Dict[str, Any]]:
        return self.get_stock_bars(ticker=ticker, start=start, end=end)

    def set_stock_bar_coverage(
        self,
        *,
        ticker: str,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> None:
        ticker_sql = _sql_text_literal(ticker)
        timeframe_sql = _sql_text_literal(timeframe)
        start_sql = _sql_text_literal(start.isoformat())
        end_sql = _sql_text_literal(end.isoformat())
        with _DUCKDB_WRITE_LOCK:
            max_attempts = 5
            for attempt in range(1, max_attempts + 1):
                updated_at_sql = _sql_text_literal(datetime.utcnow().isoformat())
                try:
                    self.con.execute(
                        f"""
                        INSERT INTO stock_bar_coverage
                        (ticker, timeframe, start_ts, end_ts, updated_at)
                        VALUES ({ticker_sql}, {timeframe_sql}, {start_sql}, {end_sql}, {updated_at_sql})
                        ON CONFLICT (ticker, timeframe, start_ts, end_ts) DO UPDATE SET
                            updated_at = EXCLUDED.updated_at
                        """
                    )
                    break
                except Exception as exc:
                    if attempt >= max_attempts or not _is_transient_write_error(exc):
                        raise
                    time.sleep(0.02 * attempt)

    def has_stock_bar_coverage(
        self,
        *,
        ticker: str,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> bool:
        row = self.con.execute(
            f"""
            SELECT 1
            FROM stock_bar_coverage
            WHERE ticker = {_sql_text_literal(ticker)}
              AND timeframe = {_sql_text_literal(timeframe)}
              AND start_ts <= {_sql_text_literal(start.isoformat())}
              AND end_ts >= {_sql_text_literal(end.isoformat())}
            LIMIT 1
            """
        ).fetchone()
        return bool(row)

    def insert_option_chain(self, rows: Iterable[Dict[str, Any]]) -> int:
        payload = [
            [
                row.get("option_symbol"),
                row.get("underlying"),
                row.get("ts"),
                row.get("expiration"),
                row.get("strike"),
                row.get("option_type"),
                row.get("bid"),
                row.get("ask"),
                row.get("delta"),
                row.get("iv"),
                int(row.get("open_interest") or 0),
                int(row.get("volume") or 0),
            ]
            for row in rows
        ]
        if not payload:
            return 0
        query = """
            INSERT INTO option_chain
            (option_symbol, underlying, ts, expiration, strike, option_type, bid, ask, delta, iv, open_interest, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (option_symbol, ts) DO UPDATE SET
                underlying = EXCLUDED.underlying,
                expiration = EXCLUDED.expiration,
                strike = EXCLUDED.strike,
                option_type = EXCLUDED.option_type,
                bid = EXCLUDED.bid,
                ask = EXCLUDED.ask,
                delta = EXCLUDED.delta,
                iv = EXCLUDED.iv,
                open_interest = EXCLUDED.open_interest,
                volume = EXCLUDED.volume
        """
        with _DUCKDB_WRITE_LOCK:
            max_attempts = 5
            for attempt in range(1, max_attempts + 1):
                try:
                    self.con.executemany(query, payload)
                    break
                except Exception as exc:
                    if _is_duplicate_key_conflict(exc) or _is_internal_unaligned_fetch_error(exc):
                        try:
                            for item in payload:
                                self.con.execute(query, item)
                            break
                        except Exception as row_exc:
                            if attempt >= max_attempts or not _is_transient_write_error(row_exc):
                                raise
                            time.sleep(0.02 * attempt)
                            continue
                    if attempt >= max_attempts or not _is_transient_write_error(exc):
                        raise
                    time.sleep(0.02 * attempt)
        return len(payload)

    def get_option_chain_snapshot(
        self,
        underlying: str,
        as_of: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        if as_of is None:
            snapshot_row = self.con.execute(
                "SELECT max(ts) FROM option_chain WHERE underlying = ?",
                [underlying],
            ).fetchone()
            if not snapshot_row or snapshot_row[0] is None:
                return []
            snapshot_ts = snapshot_row[0]
        else:
            snapshot_row = self.con.execute(
                "SELECT max(ts) FROM option_chain WHERE underlying = ? AND ts <= ?",
                [underlying, as_of],
            ).fetchone()
            if not snapshot_row or snapshot_row[0] is None:
                return []
            snapshot_ts = snapshot_row[0]

        query = """
            SELECT option_symbol, underlying, ts, expiration, strike, option_type, bid, ask, delta, iv, open_interest, volume
            FROM option_chain
            WHERE underlying = ? AND ts = ?
            ORDER BY expiration ASC, strike ASC
        """
        rows = self.con.execute(query, [underlying, snapshot_ts]).fetchall()
        return [
            {
                "option_symbol": row[0],
                "underlying": row[1],
                "ts": row[2],
                "expiration": row[3],
                "strike": row[4],
                "option_type": row[5],
                "bid": row[6],
                "ask": row[7],
                "delta": row[8],
                "iv": row[9],
                "open_interest": row[10],
                "volume": row[11],
            }
            for row in rows
        ]

    def insert_option_bars(self, rows: Iterable[Dict[str, Any]]) -> int:
        payload = [
            [
                row.get("symbol"),
                row.get("ts"),
                row.get("open"),
                row.get("high"),
                row.get("low"),
                row.get("close"),
                int(row.get("volume") or 0),
            ]
            for row in rows
        ]
        if not payload:
            return 0
        query = """
            INSERT INTO option_bars
            (symbol, ts, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (symbol, ts) DO UPDATE SET
                open = EXCLUDED.open,
                high = EXCLUDED.high,
                low = EXCLUDED.low,
                close = EXCLUDED.close,
                volume = EXCLUDED.volume
        """
        with _DUCKDB_WRITE_LOCK:
            max_attempts = 5
            for attempt in range(1, max_attempts + 1):
                try:
                    self.con.executemany(query, payload)
                    break
                except Exception as exc:
                    if _is_duplicate_key_conflict(exc) or _is_internal_unaligned_fetch_error(exc):
                        try:
                            for item in payload:
                                self.con.execute(query, item)
                            break
                        except Exception as row_exc:
                            if attempt >= max_attempts or not _is_transient_write_error(row_exc):
                                raise
                            time.sleep(0.02 * attempt)
                            continue
                    if attempt >= max_attempts or not _is_transient_write_error(exc):
                        raise
                    time.sleep(0.02 * attempt)
        return len(payload)

    def get_option_bars(
        self,
        symbol: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        where = ["symbol = ?"]
        params: List[Any] = [symbol]
        if start is not None:
            where.append("ts >= ?")
            params.append(start)
        if end is not None:
            where.append("ts <= ?")
            params.append(end)

        query = """
            SELECT symbol, ts, open, high, low, close, volume
            FROM option_bars
            WHERE {where}
            ORDER BY ts ASC
        """.format(where=" AND ".join(where))

        return [
            {
                "symbol": row[0],
                "ts": row[1],
                "open": row[2],
                "high": row[3],
                "low": row[4],
                "close": row[5],
                "volume": row[6],
            }
            for row in self.con.execute(query, params).fetchall()
        ]

    def insert_option_quotes(self, rows: Iterable[Dict[str, Any]]) -> int:
        payload = [
            [
                row.get("symbol"),
                row.get("ts"),
                row.get("bid"),
                row.get("ask"),
                int(row.get("bid_size") or 0),
                int(row.get("ask_size") or 0),
            ]
            for row in rows
        ]
        if not payload:
            return 0
        query = """
            INSERT INTO option_quotes
            (symbol, ts, bid, ask, bid_size, ask_size)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT (symbol, ts) DO UPDATE SET
                bid = EXCLUDED.bid,
                ask = EXCLUDED.ask,
                bid_size = EXCLUDED.bid_size,
                ask_size = EXCLUDED.ask_size
        """
        with _DUCKDB_WRITE_LOCK:
            max_attempts = 5
            for attempt in range(1, max_attempts + 1):
                try:
                    self.con.executemany(query, payload)
                    break
                except Exception as exc:
                    if _is_duplicate_key_conflict(exc) or _is_internal_unaligned_fetch_error(exc):
                        try:
                            for item in payload:
                                self.con.execute(query, item)
                            break
                        except Exception as row_exc:
                            if attempt >= max_attempts or not _is_transient_write_error(row_exc):
                                raise
                            time.sleep(0.02 * attempt)
                            continue
                    if attempt >= max_attempts or not _is_transient_write_error(exc):
                        raise
                    time.sleep(0.02 * attempt)
        return len(payload)

    def get_option_quotes(
        self,
        symbol: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        where = ["symbol = ?"]
        params: List[Any] = [symbol]
        if start is not None:
            where.append("ts >= ?")
            params.append(start)
        if end is not None:
            where.append("ts <= ?")
            params.append(end)

        query = """
            SELECT symbol, ts, bid, ask, bid_size, ask_size
            FROM option_quotes
            WHERE {where}
            ORDER BY ts ASC
        """.format(where=" AND ".join(where))

        return [
            {
                "symbol": row[0],
                "ts": row[1],
                "bid": row[2],
                "ask": row[3],
                "bid_size": row[4],
                "ask_size": row[5],
            }
            for row in self.con.execute(query, params).fetchall()
        ]

    def insert_stock_daily_bars(self, rows: Iterable[Dict[str, Any]]) -> int:
        dedup_payload: Dict[tuple, List[Any]] = {}
        for row in rows:
            ts = row.get("ts")
            day_value = row.get("day")
            if isinstance(day_value, datetime):
                day_value = day_value.date()
            if day_value is None and isinstance(ts, datetime):
                day_value = ts.date()
            if not isinstance(day_value, date):
                continue
            ticker_value = row.get("ticker")
            key = (ticker_value, day_value)
            dedup_payload[key] = [
                ticker_value,
                day_value,
                ts,
                row.get("open"),
                row.get("high"),
                row.get("low"),
                row.get("close"),
                int(row.get("volume") or 0),
            ]
        payload: List[List[Any]] = list(dedup_payload.values())
        if not payload:
            return 0
        query = """
            INSERT INTO stock_daily_bars
            (ticker, day, ts, open, high, low, close, volume)
            VALUES ({ticker}, {day}, {ts}, {open}, {high}, {low}, {close}, {volume})
        """
        # Serialize shared daily-bar writes across worker threads to avoid duplicate-key races.
        with _DUCKDB_WRITE_LOCK:
            max_attempts = 5
            for attempt in range(1, max_attempts + 1):
                try:
                    for item in payload:
                        delete_sql = f"""
                            DELETE FROM stock_daily_bars
                            WHERE ticker = {_sql_value_literal(item[0])}
                              AND day = {_sql_value_literal(item[1])}
                        """
                        insert_sql = query.format(
                            ticker=_sql_value_literal(item[0]),
                            day=_sql_value_literal(item[1]),
                            ts=_sql_value_literal(item[2]),
                            open=_sql_value_literal(item[3]),
                            high=_sql_value_literal(item[4]),
                            low=_sql_value_literal(item[5]),
                            close=_sql_value_literal(item[6]),
                            volume=_sql_value_literal(item[7]),
                        )
                        self.con.execute(delete_sql)
                        self.con.execute(insert_sql)
                    break
                except Exception as exc:
                    if _is_duplicate_key_conflict(exc):
                        retriable = True
                        if attempt >= max_attempts or not retriable:
                            raise
                        time.sleep(0.02 * attempt)
                        continue
                    retriable = _is_catalog_write_conflict(exc)
                    if attempt >= max_attempts or not retriable:
                        raise
                    time.sleep(0.02 * attempt)
        return len(payload)

    def get_stock_daily_bars(
        self,
        ticker: str,
        start_day: Optional[date] = None,
        end_day: Optional[date] = None,
    ) -> List[Dict[str, Any]]:
        where = [f"ticker = {_sql_value_literal(ticker)}"]
        if start_day is not None:
            where.append(f"day >= {_sql_value_literal(start_day)}")
        if end_day is not None:
            where.append(f"day <= {_sql_value_literal(end_day)}")

        query = """
            SELECT ticker, day, ts, open, high, low, close, volume
            FROM stock_daily_bars
            WHERE {where}
            ORDER BY day ASC
        """.format(where=" AND ".join(where))
        return [
            {
                "ticker": row[0],
                "day": row[1],
                "ts": row[2],
                "open": row[3],
                "high": row[4],
                "low": row[5],
                "close": row[6],
                "volume": row[7],
            }
            for row in self.con.execute(query).fetchall()
        ]

    def set_option_contract_cache(
        self,
        *,
        underlying: str,
        trading_day: date,
        option_type: str,
        status: str,
        option_min_dte: int,
        option_target_dte: int,
        option_max_dte: int,
        option_min_open_interest: int,
        found: bool,
        contract: Optional[Dict[str, Any]],
    ) -> None:
        payload = contract if isinstance(contract, dict) else {}
        trading_day_sql = _sql_text_literal(trading_day.isoformat())
        underlying_sql = _sql_text_literal(underlying)
        option_type_sql = _sql_text_literal(option_type)
        status_sql = _sql_text_literal(status)
        payload_sql = _sql_text_literal(json.dumps(payload, separators=(",", ":")))
        updated_at_sql = _sql_text_literal(datetime.utcnow().isoformat())
        found_sql = "TRUE" if bool(found) else "FALSE"
        with _DUCKDB_WRITE_LOCK:
            self.con.execute(
                f"""
                INSERT INTO option_contract_cache
                (
                    underlying,
                    trading_day,
                    option_type,
                    status,
                    option_min_dte,
                    option_target_dte,
                    option_max_dte,
                    option_min_open_interest,
                    found,
                    payload,
                    updated_at
                )
                VALUES (
                    {underlying_sql},
                    {trading_day_sql},
                    {option_type_sql},
                    {status_sql},
                    {int(option_min_dte)},
                    {int(option_target_dte)},
                    {int(option_max_dte)},
                    {int(option_min_open_interest)},
                    {found_sql},
                    {payload_sql},
                    {updated_at_sql}
                )
                ON CONFLICT (
                    underlying,
                    trading_day,
                    option_type,
                    status,
                    option_min_dte,
                    option_target_dte,
                    option_max_dte,
                    option_min_open_interest
                ) DO UPDATE SET
                    found = EXCLUDED.found,
                    payload = EXCLUDED.payload,
                    updated_at = EXCLUDED.updated_at
                """
            )

    def set_option_contract_list_cache(
        self,
        *,
        underlying: str,
        trading_day: date,
        option_type: str,
        status: str,
        option_min_dte: int,
        option_max_dte: int,
        found: bool,
        contracts: Sequence[Dict[str, Any]],
    ) -> None:
        payload = [dict(item) for item in contracts if isinstance(item, dict)]
        trading_day_sql = _sql_text_literal(trading_day.isoformat())
        underlying_sql = _sql_text_literal(underlying)
        option_type_sql = _sql_text_literal(option_type)
        status_sql = _sql_text_literal(status)
        payload_sql = _sql_text_literal(json.dumps(payload, separators=(",", ":")))
        updated_at_sql = _sql_text_literal(datetime.utcnow().isoformat())
        found_sql = "TRUE" if bool(found) else "FALSE"
        with _DUCKDB_WRITE_LOCK:
            self.con.execute(
                f"""
                INSERT INTO option_contract_list_cache
                (
                    underlying,
                    trading_day,
                    option_type,
                    status,
                    option_min_dte,
                    option_max_dte,
                    found,
                    payload,
                    updated_at
                )
                VALUES (
                    {underlying_sql},
                    {trading_day_sql},
                    {option_type_sql},
                    {status_sql},
                    {int(option_min_dte)},
                    {int(option_max_dte)},
                    {found_sql},
                    {payload_sql},
                    {updated_at_sql}
                )
                ON CONFLICT (
                    underlying,
                    trading_day,
                    option_type,
                    status,
                    option_min_dte,
                    option_max_dte
                ) DO UPDATE SET
                    found = EXCLUDED.found,
                    payload = EXCLUDED.payload,
                    updated_at = EXCLUDED.updated_at
                """
            )

    def set_option_contract_universe_cache(
        self,
        *,
        underlying: str,
        option_type: str,
        status: str,
        option_min_dte: int,
        option_max_dte: int,
        found: bool,
        contracts: Sequence[Dict[str, Any]],
    ) -> None:
        payload = [dict(item) for item in contracts if isinstance(item, dict)]
        underlying_sql = _sql_text_literal(underlying)
        option_type_sql = _sql_text_literal(option_type)
        status_sql = _sql_text_literal(status)
        payload_sql = _sql_text_literal(json.dumps(payload, separators=(",", ":")))
        updated_at_sql = _sql_text_literal(datetime.utcnow().isoformat())
        found_sql = "TRUE" if bool(found) else "FALSE"
        with _DUCKDB_WRITE_LOCK:
            self.con.execute(
                f"""
                INSERT INTO option_contract_universe_cache
                (
                    underlying,
                    option_type,
                    status,
                    option_min_dte,
                    option_max_dte,
                    found,
                    payload,
                    updated_at
                )
                VALUES (
                    {underlying_sql},
                    {option_type_sql},
                    {status_sql},
                    {int(option_min_dte)},
                    {int(option_max_dte)},
                    {found_sql},
                    {payload_sql},
                    {updated_at_sql}
                )
                ON CONFLICT (
                    underlying,
                    option_type,
                    status,
                    option_min_dte,
                    option_max_dte
                ) DO UPDATE SET
                    found = EXCLUDED.found,
                    payload = EXCLUDED.payload,
                    updated_at = EXCLUDED.updated_at
                """
            )

    def get_option_contract_universe_cache(
        self,
        *,
        underlying: str,
        option_type: str,
        status: str,
        option_min_dte: int,
        option_max_dte: int,
    ) -> Optional[Dict[str, Any]]:
        row = self.con.execute(
            f"""
            SELECT found, payload
            FROM option_contract_universe_cache
            WHERE underlying = {_sql_text_literal(underlying)}
              AND option_type = {_sql_text_literal(option_type)}
              AND status = {_sql_text_literal(status)}
              AND option_min_dte = {int(option_min_dte)}
              AND option_max_dte = {int(option_max_dte)}
            """
        ).fetchone()
        if not row:
            return None
        payload = json.loads(row[1] or "[]")
        contracts = payload if isinstance(payload, list) else []
        return {
            "found": bool(row[0]),
            "contracts": [item for item in contracts if isinstance(item, dict)],
        }

    def set_option_contract_fetch_preference(
        self,
        *,
        underlying: str,
        option_type: str,
        requested_status: str,
        option_min_dte: int,
        option_max_dte: int,
        preferred_status: str,
        preferred_as_of_mode: str,
    ) -> None:
        underlying_sql = _sql_text_literal(underlying)
        option_type_sql = _sql_text_literal(option_type)
        requested_status_sql = _sql_text_literal(requested_status)
        preferred_status_sql = _sql_text_literal(preferred_status)
        preferred_as_of_mode_sql = _sql_text_literal(preferred_as_of_mode)
        with _DUCKDB_WRITE_LOCK:
            max_attempts = 5
            for attempt in range(1, max_attempts + 1):
                updated_at_sql = _sql_text_literal(datetime.utcnow().isoformat())
                try:
                    self.con.execute(
                        f"""
                        INSERT INTO option_contract_fetch_preference
                        (
                            underlying,
                            option_type,
                            requested_status,
                            option_min_dte,
                            option_max_dte,
                            preferred_status,
                            preferred_as_of_mode,
                            updated_at
                        )
                        VALUES (
                            {underlying_sql},
                            {option_type_sql},
                            {requested_status_sql},
                            {int(option_min_dte)},
                            {int(option_max_dte)},
                            {preferred_status_sql},
                            {preferred_as_of_mode_sql},
                            {updated_at_sql}
                        )
                        ON CONFLICT (
                            underlying,
                            option_type,
                            requested_status,
                            option_min_dte,
                            option_max_dte
                        ) DO UPDATE SET
                            preferred_status = EXCLUDED.preferred_status,
                            preferred_as_of_mode = EXCLUDED.preferred_as_of_mode,
                            updated_at = EXCLUDED.updated_at
                        """
                    )
                    break
                except Exception as exc:
                    if _is_duplicate_key_conflict(exc):
                        try:
                            self.con.execute(
                                f"""
                                UPDATE option_contract_fetch_preference
                                SET preferred_status = {preferred_status_sql},
                                    preferred_as_of_mode = {preferred_as_of_mode_sql},
                                    updated_at = {updated_at_sql}
                                WHERE underlying = {underlying_sql}
                                  AND option_type = {option_type_sql}
                                  AND requested_status = {requested_status_sql}
                                  AND option_min_dte = {int(option_min_dte)}
                                  AND option_max_dte = {int(option_max_dte)}
                                """
                            )
                            break
                        except Exception as update_exc:
                            if attempt >= max_attempts or not _is_transient_write_error(update_exc):
                                raise
                            time.sleep(0.02 * attempt)
                            continue
                    if attempt >= max_attempts or not _is_transient_write_error(exc):
                        raise
                    time.sleep(0.02 * attempt)

    def get_option_contract_fetch_preference(
        self,
        *,
        underlying: str,
        option_type: str,
        requested_status: str,
        option_min_dte: int,
        option_max_dte: int,
    ) -> Optional[Dict[str, str]]:
        row = self.con.execute(
            f"""
            SELECT preferred_status, preferred_as_of_mode
            FROM option_contract_fetch_preference
            WHERE underlying = {_sql_text_literal(underlying)}
              AND option_type = {_sql_text_literal(option_type)}
              AND requested_status = {_sql_text_literal(requested_status)}
              AND option_min_dte = {int(option_min_dte)}
              AND option_max_dte = {int(option_max_dte)}
            """
        ).fetchone()
        if not row:
            return None
        return {
            "preferred_status": str(row[0] or ""),
            "preferred_as_of_mode": str(row[1] or ""),
        }

    def get_option_contract_list_cache(
        self,
        *,
        underlying: str,
        trading_day: date,
        option_type: str,
        status: str,
        option_min_dte: int,
        option_max_dte: int,
    ) -> Optional[Dict[str, Any]]:
        row = self.con.execute(
            f"""
            SELECT found, payload
            FROM option_contract_list_cache
            WHERE underlying = {_sql_text_literal(underlying)}
              AND trading_day = {_sql_text_literal(trading_day.isoformat())}
              AND option_type = {_sql_text_literal(option_type)}
              AND status = {_sql_text_literal(status)}
              AND option_min_dte = {int(option_min_dte)}
              AND option_max_dte = {int(option_max_dte)}
            """
        ).fetchone()
        if not row:
            return None
        payload = json.loads(row[1] or "[]")
        contracts = payload if isinstance(payload, list) else []
        return {
            "found": bool(row[0]),
            "contracts": [item for item in contracts if isinstance(item, dict)],
        }

    def get_option_contract_cache(
        self,
        *,
        underlying: str,
        trading_day: date,
        option_type: str,
        status: str,
        option_min_dte: int,
        option_target_dte: int,
        option_max_dte: int,
        option_min_open_interest: int,
    ) -> Optional[Dict[str, Any]]:
        row = self.con.execute(
            f"""
            SELECT found, payload
            FROM option_contract_cache
            WHERE underlying = {_sql_text_literal(underlying)}
              AND trading_day = {_sql_text_literal(trading_day.isoformat())}
              AND option_type = {_sql_text_literal(option_type)}
              AND status = {_sql_text_literal(status)}
              AND option_min_dte = {int(option_min_dte)}
              AND option_target_dte = {int(option_target_dte)}
              AND option_max_dte = {int(option_max_dte)}
              AND option_min_open_interest = {int(option_min_open_interest)}
            """
        ).fetchone()
        if not row:
            return None
        payload = json.loads(row[1] or "{}")
        contract = payload if isinstance(payload, dict) else {}
        return {
            "found": bool(row[0]),
            "contract": contract,
        }

    def insert_signals(self, signals: Iterable[Signal]) -> int:
        count = 0
        for signal in signals:
            self.con.execute(
                """
                INSERT OR REPLACE INTO signals
                (signal_id, disclosure_id, ticker, direction, conviction, generated_at, model_tag, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    signal.id,
                    signal.disclosure_id,
                    signal.ticker,
                    signal.direction,
                    signal.conviction,
                    signal.generated_at,
                    signal.model_tag,
                    json.dumps(signal.metadata),
                ],
            )
            count += 1
        return count

    def insert_backtest_trades(self, trades: Iterable[BacktestTrade]) -> int:
        count = 0
        for trade in trades:
            self.con.execute(
                f"""
                DELETE FROM backtest_trades
                WHERE trade_id = {_sql_value_literal(trade.trade_id)}
                """
            )
            self.con.execute(
                f"""
                INSERT INTO backtest_trades
                (
                    trade_id,
                    signal_id,
                    ticker,
                    option_symbol,
                    entry_ts,
                    exit_ts,
                    side,
                    qty,
                    entry_price,
                    exit_price,
                    pnl,
                    return_pct,
                    status,
                    metadata
                )
                VALUES (
                    {_sql_value_literal(trade.trade_id)},
                    {_sql_value_literal(trade.signal_id)},
                    {_sql_value_literal(trade.ticker)},
                    {_sql_value_literal(trade.option_symbol)},
                    {_sql_value_literal(trade.entry_ts)},
                    {_sql_value_literal(trade.exit_ts)},
                    {_sql_value_literal(trade.side)},
                    {_sql_value_literal(trade.qty)},
                    {_sql_value_literal(trade.entry_price)},
                    {_sql_value_literal(trade.exit_price)},
                    {_sql_value_literal(trade.pnl)},
                    {_sql_value_literal(trade.return_pct)},
                    {_sql_value_literal(trade.status)},
                    {_sql_value_literal(json.dumps(trade.metadata))}
                )
                """
            )
            count += 1
        return count

    def insert_paper_orders(self, orders: Iterable[PaperOrder]) -> int:
        count = 0
        for order in orders:
            self.con.execute(
                """
                INSERT OR REPLACE INTO paper_orders
                (local_id, signal_id, ticker, option_symbol, side, qty, limit_price, status, submitted_at, broker_order_id, raw)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    order.local_id,
                    order.signal_id,
                    order.ticker,
                    order.option_symbol,
                    order.side,
                    order.qty,
                    order.limit_price,
                    order.status,
                    order.submitted_at,
                    order.broker_order_id,
                    json.dumps(order.raw),
                ],
            )
            count += 1
        return count

    def get_ordered_signal_ids(self) -> Set[str]:
        rows = self.con.execute("SELECT DISTINCT signal_id FROM paper_orders").fetchall()
        return {row[0] for row in rows if row[0]}

    def get_open_paper_entries(self) -> List[Dict[str, Any]]:
        rows = self.con.execute(
            """
            SELECT
                p.local_id,
                p.signal_id,
                p.ticker,
                p.option_symbol,
                p.qty,
                p.limit_price,
                p.submitted_at,
                p.status
            FROM paper_orders p
            WHERE p.side = 'buy'
              AND p.signal_id IS NOT NULL
              AND NOT EXISTS (
                SELECT 1
                FROM paper_orders s
                WHERE s.signal_id = p.signal_id
                  AND s.side = 'sell'
              )
            ORDER BY p.submitted_at ASC
            """
        ).fetchall()
        return [
            {
                "local_id": row[0],
                "signal_id": row[1],
                "ticker": row[2],
                "option_symbol": row[3],
                "qty": int(row[4] or 0),
                "limit_price": float(row[5] or 0.0),
                "submitted_at": row[6],
                "status": row[7],
            }
            for row in rows
        ]
