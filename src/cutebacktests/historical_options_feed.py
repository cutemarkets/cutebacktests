from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time as dtime, timedelta, timezone
from math import erf, exp, log, sqrt
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo

from .providers.alpaca import AlpacaDataProvider
from .providers.cutemarkets import CuteMarketsProvider
from .storage import DataStore


_ET_ZONE = ZoneInfo("America/New_York")
_UTC = timezone.utc
_ATM_WINDOW_STRIKES_PER_SIDE = 8
_TAIL_SAMPLE_STRIKES_PER_SIDE = 4


@dataclass(frozen=True)
class HistoricalOptionsFeedConfig:
    start_day: date
    end_day: date
    tickers: Tuple[str, ...]
    option_min_dte: int = 0
    option_max_dte: int = 30
    option_type: str = "all"
    contract_limit: int = 1000
    quote_mode: str = "close"  # close | full_day


class HistoricalOptionsFeed:
    def __init__(
        self,
        *,
        cutemarkets_provider: CuteMarketsProvider,
        alpaca_data_provider: Optional[AlpacaDataProvider] = None,
        store: Optional[DataStore] = None,
    ) -> None:
        self.cutemarkets_provider = cutemarkets_provider
        self.alpaca_data_provider = alpaca_data_provider
        self.store = store
        self._stock_daily_cache: Dict[Tuple[str, date, date], List[Dict[str, Any]]] = {}
        self._chain_cache: Dict[Tuple[str, date, Tuple[Tuple[str, Any], ...]], List[Dict[str, Any]]] = {}
        self._quote_rows_cache: Dict[Tuple[str, date, str], List[Dict[str, Any]]] = {}
        self._close_quote_cache: Dict[Tuple[str, date, str], Optional[Dict[str, Any]]] = {}
        self._daily_bar_close_cache: Dict[Tuple[str, date], Optional[Dict[str, Any]]] = {}
        self._stats: Dict[str, int] = {
            "stock_daily_rows_upserted": 0,
            "option_chain_rows_upserted": 0,
            "option_quote_rows_upserted": 0,
            "contract_rows_considered": 0,
        }

    def stats(self) -> Dict[str, int]:
        return {str(key): int(value) for key, value in self._stats.items()}

    def load_stock_daily_bars(
        self,
        *,
        ticker: str,
        start_day: date,
        end_day: date,
    ) -> List[Dict[str, Any]]:
        key = (str(ticker).strip().upper(), start_day, end_day)
        cached = self._stock_daily_cache.get(key)
        if cached is not None:
            return [dict(row) for row in cached]

        rows: List[Dict[str, Any]] = []
        if self.store is not None:
            rows = list(self.store.get_stock_daily_bars(key[0], start_day=start_day, end_day=end_day))
        fetched_rows: List[Dict[str, Any]] = []
        if self.alpaca_data_provider is not None:
            try:
                fetched = list(
                    self.alpaca_data_provider.fetch_stock_bars(
                        symbol=key[0],
                        start=start_day.isoformat(),
                        end=end_day.isoformat(),
                        timeframe="1Day",
                        limit=10000,
                    )
                    or []
                )
            except Exception:
                fetched = []
            fetched_rows = [_normalize_stock_daily_bar(key[0], row) for row in fetched]
            fetched_rows = [row for row in fetched_rows if row is not None]
        if not fetched_rows:
            try:
                fetched = list(
                    self.cutemarkets_provider.fetch_stock_bars(
                        ticker=key[0],
                        start=start_day,
                        end=end_day,
                        multiplier=1,
                        timespan="day",
                    )
                    or []
                )
            except Exception:
                fetched = []
            fetched_rows = [_normalize_stock_daily_bar(key[0], row) for row in fetched]
            fetched_rows = [row for row in fetched_rows if row is not None]

        rows.extend(fetched_rows)
        if rows:
            dedup: Dict[date, Dict[str, Any]] = {}
            for row in rows:
                day_value = row.get("day")
                if isinstance(day_value, date):
                    dedup[day_value] = dict(row)
            rows = [dedup[day] for day in sorted(dedup)]
            if self.store is not None:
                inserted = self.store.insert_stock_daily_bars(rows)
                self._stats["stock_daily_rows_upserted"] += int(inserted)

        self._stock_daily_cache[key] = [dict(row) for row in rows]
        return [dict(row) for row in rows]

    def load_option_chain_snapshot(
        self,
        *,
        ticker: str,
        day: date,
        expiration_date_gte: Optional[str] = None,
        expiration_date_lte: Optional[str] = None,
        contract_type: Optional[str] = None,
        strike_price: Optional[float] = None,
        limit: int = 1000,
        quote_mode: str = "close",
    ) -> List[Dict[str, Any]]:
        normalized_filters = tuple(
            sorted(
                (str(key), value)
                for key, value in {
                    "expiration_date_gte": expiration_date_gte,
                    "expiration_date_lte": expiration_date_lte,
                    "contract_type": contract_type,
                    "strike_price": strike_price,
                    "limit": int(limit),
                    "quote_mode": str(quote_mode or "close"),
                }.items()
                if value not in (None, "")
            )
        )
        key = (str(ticker).strip().upper(), day, normalized_filters)
        cached = self._chain_cache.get(key)
        if cached is not None:
            return [dict(row) for row in cached]

        rows: List[Dict[str, Any]] = []
        if self.store is not None:
            rows = _filter_chain_rows(
                self.store.get_option_chain_snapshot(key[0], as_of=_chain_snapshot_ts(day)),
                expiration_date_gte=expiration_date_gte,
                expiration_date_lte=expiration_date_lte,
                contract_type=contract_type,
                strike_price=strike_price,
            )

        built_rows = self._build_option_chain_snapshot_from_contracts(
            ticker=key[0],
            day=day,
            expiration_date_gte=expiration_date_gte,
            expiration_date_lte=expiration_date_lte,
            contract_type=contract_type,
            limit=limit,
            quote_mode=quote_mode,
        )
        if built_rows:
            rows.extend(built_rows)

        if not rows and not hasattr(self.cutemarkets_provider, "fetch_option_contracts"):
            rows = _normalize_chain_rows(
                getattr(self.cutemarkets_provider, "fetch_option_chain_snapshot")(
                    key[0],
                    as_of=day,
                    expiration_date_gte=expiration_date_gte,
                    expiration_date_lte=expiration_date_lte,
                    contract_type=contract_type,
                    strike_price=strike_price,
                    limit=limit,
                )
                or [],
                ticker=key[0],
                day=day,
            )

        rows = _filter_chain_rows(
            rows,
            expiration_date_gte=expiration_date_gte,
            expiration_date_lte=expiration_date_lte,
            contract_type=contract_type,
            strike_price=strike_price,
        )
        self._chain_cache[key] = [dict(row) for row in rows]
        return [dict(row) for row in rows]

    def load_option_close_snapshot(
        self,
        *,
        ticker: str,
        option_symbol: str,
        day: date,
        quote_mode: str = "close",
    ) -> Optional[Dict[str, Any]]:
        normalized_mode = _normalize_quote_mode(quote_mode)
        cache_key = (str(option_symbol).strip(), day, normalized_mode)
        if cache_key in self._close_quote_cache:
            cached = self._close_quote_cache[cache_key]
            return dict(cached) if isinstance(cached, dict) else None

        rows = self._load_option_quote_rows(
            option_symbol=str(option_symbol).strip(),
            day=day,
            quote_mode=normalized_mode,
        )
        snapshot = _select_close_quote(rows, day=day)
        if snapshot is None:
            fallback_bar = self._load_daily_option_bar_close(option_symbol=str(option_symbol).strip(), day=day)
            snapshot = _bar_close_snapshot(option_symbol=str(option_symbol).strip(), bar=fallback_bar)
        if snapshot is None and not hasattr(self.cutemarkets_provider, "fetch_option_quotes"):
            raw = getattr(self.cutemarkets_provider, "fetch_option_contract_snapshot")(
                underlying=str(ticker).strip().upper(),
                option_symbol=str(option_symbol).strip(),
                as_of=day,
            )
            snapshot = dict(raw) if isinstance(raw, Mapping) else None
        self._close_quote_cache[cache_key] = dict(snapshot) if isinstance(snapshot, dict) else None
        return dict(snapshot) if isinstance(snapshot, dict) else None

    def ingest_range(self, *, config: HistoricalOptionsFeedConfig) -> Dict[str, Any]:
        trading_days_with_stock = 0
        days_with_chain = 0
        chain_rows_available = 0
        skipped_days = 0
        option_type = str(config.option_type or "all").strip().lower()
        contract_type = None if option_type in {"", "all"} else option_type
        for ticker in config.tickers:
            daily_rows = self.load_stock_daily_bars(
                ticker=ticker,
                start_day=config.start_day,
                end_day=config.end_day,
            )
            trading_lookup = {row["day"]: dict(row) for row in daily_rows if isinstance(row.get("day"), date)}
            cursor = config.start_day
            while cursor <= config.end_day:
                if cursor not in trading_lookup:
                    skipped_days += 1
                    cursor += timedelta(days=1)
                    continue
                trading_days_with_stock += 1
                rows = self.load_option_chain_snapshot(
                    ticker=ticker,
                    day=cursor,
                    expiration_date_gte=(cursor + timedelta(days=max(int(config.option_min_dte), 0))).isoformat(),
                    expiration_date_lte=(
                        cursor + timedelta(days=max(int(config.option_max_dte), int(config.option_min_dte)))
                    ).isoformat(),
                    contract_type=contract_type,
                    limit=int(config.contract_limit),
                    quote_mode=config.quote_mode,
                )
                if rows:
                    days_with_chain += 1
                    chain_rows_available += len(rows)
                cursor += timedelta(days=1)

        summary = self.stats()
        summary.update(
            {
                "tickers": list(config.tickers),
                "start_day": config.start_day.isoformat(),
                "end_day": config.end_day.isoformat(),
                "option_min_dte": int(config.option_min_dte),
                "option_max_dte": int(config.option_max_dte),
                "option_type": option_type or "all",
                "quote_mode": _normalize_quote_mode(config.quote_mode),
                "trading_days_with_stock": int(trading_days_with_stock),
                "days_with_chain": int(days_with_chain),
                "chain_rows_available": int(chain_rows_available),
                "skipped_days_without_stock": int(skipped_days),
            }
        )
        return summary

    def _build_option_chain_snapshot_from_contracts(
        self,
        *,
        ticker: str,
        day: date,
        expiration_date_gte: Optional[str],
        expiration_date_lte: Optional[str],
        contract_type: Optional[str],
        limit: int,
        quote_mode: str,
    ) -> List[Dict[str, Any]]:
        if not hasattr(self.cutemarkets_provider, "fetch_option_contracts"):
            return []

        stock_rows = self.load_stock_daily_bars(ticker=ticker, start_day=day, end_day=day)
        stock_row = stock_rows[0] if stock_rows else None
        spot = _safe_float((stock_row or {}).get("close"))
        if spot is None or spot <= 0.0:
            return []

        try:
            contracts = list(
                self.cutemarkets_provider.fetch_option_contracts(
                    underlying_symbol=ticker,
                    expiration_date_gte=expiration_date_gte,
                    expiration_date_lte=expiration_date_lte,
                    option_type=contract_type,
                    status="active",
                    as_of=day.isoformat(),
                    limit=int(limit),
                )
                or []
            )
        except Exception:
            return []

        if not contracts:
            return []
        self._stats["contract_rows_considered"] += int(len(contracts))
        contracts = _prioritize_contracts_for_pricing(contracts, spot=float(spot))
        rows: List[Dict[str, Any]] = []
        snapshot_ts = _chain_snapshot_ts(day)
        for contract in contracts:
            expiration_day = _expiration_day(contract)
            strike = _safe_float(contract.get("strike") or contract.get("strike_price"))
            option_kind = str(contract.get("option_type") or contract.get("type") or "").strip().lower()
            option_symbol = str(contract.get("option_symbol") or contract.get("symbol") or "").strip()
            if expiration_day is None or strike is None or strike <= 0.0 or not option_kind or not option_symbol:
                continue

            close_quote = self.load_option_close_snapshot(
                ticker=ticker,
                option_symbol=option_symbol,
                day=day,
                quote_mode=quote_mode,
            )
            bid = _safe_float((close_quote or {}).get("bid"))
            ask = _safe_float((close_quote or {}).get("ask"))
            fallback_bar = None if close_quote is not None else self._load_daily_option_bar_close(option_symbol=option_symbol, day=day)
            fallback_close = _safe_float((fallback_bar or {}).get("close"))
            if bid is None and fallback_close is not None:
                bid = fallback_close
            if ask is None and fallback_close is not None:
                ask = fallback_close
            if bid is None or ask is None:
                continue
            midpoint = _quote_mid({"bid": bid, "ask": ask})
            if midpoint <= 0.0:
                continue
            implied_vol, estimated_delta = _estimate_option_greeks(
                option_price=midpoint,
                underlying_price=float(spot),
                strike=float(strike),
                valuation_day=day,
                expiration_day=expiration_day,
                option_type=option_kind,
            )
            volume = max(
                int(contract.get("volume") or 0),
                int((fallback_bar or {}).get("volume") or 0),
                int((close_quote or {}).get("bid_size") or 0) + int((close_quote or {}).get("ask_size") or 0),
            )
            row = {
                "option_symbol": option_symbol,
                "underlying": ticker,
                "ts": snapshot_ts,
                "expiration": expiration_day,
                "strike": float(strike),
                "option_type": option_kind,
                "bid": float(bid),
                "ask": float(ask),
                "midpoint": float(midpoint),
                "delta": _safe_float(contract.get("delta")) or estimated_delta,
                "iv": _safe_float(contract.get("iv")) or implied_vol,
                "open_interest": int(contract.get("open_interest") or 0),
                "volume": int(volume),
            }
            rows.append(row)

        if rows and self.store is not None:
            inserted = self.store.insert_option_chain(rows)
            self._stats["option_chain_rows_upserted"] += int(inserted)
        rows.sort(key=lambda item: (_expiration_day(item) or date.max, float(item.get("strike") or 0.0)))
        return rows

    def _load_option_quote_rows(
        self,
        *,
        option_symbol: str,
        day: date,
        quote_mode: str,
    ) -> List[Dict[str, Any]]:
        normalized_mode = _normalize_quote_mode(quote_mode)
        key = (str(option_symbol).strip(), day, normalized_mode)
        cached = self._quote_rows_cache.get(key)
        if cached is not None:
            return [dict(row) for row in cached]

        rows: List[Dict[str, Any]] = []
        if self.store is not None:
            rows = list(
                self.store.get_option_quotes(
                    symbol=option_symbol,
                    start=datetime.combine(day, dtime(0, 0)),
                    end=datetime.combine(day + timedelta(days=1), dtime(0, 0)),
                )
            )
        if not rows and hasattr(self.cutemarkets_provider, "fetch_option_quotes"):
            start_dt, end_dt = _quote_fetch_window(day=day, quote_mode=normalized_mode)
            try:
                rows = list(
                    self.cutemarkets_provider.fetch_option_quotes(
                        option_symbol=option_symbol,
                        start=start_dt,
                        end=end_dt,
                        limit=0 if normalized_mode == "full_day" else 5000,
                    )
                    or []
                )
            except Exception:
                rows = []
            if rows and normalized_mode == "full_day" and self.store is not None:
                inserted = self.store.insert_option_quotes(rows)
                self._stats["option_quote_rows_upserted"] += int(inserted)
        rows.sort(key=lambda item: item.get("ts") or datetime.min)
        self._quote_rows_cache[key] = [dict(row) for row in rows]
        return [dict(row) for row in rows]

    def _load_daily_option_bar_close(self, *, option_symbol: str, day: date) -> Optional[Dict[str, Any]]:
        key = (str(option_symbol).strip(), day)
        if key in self._daily_bar_close_cache:
            cached = self._daily_bar_close_cache[key]
            return dict(cached) if isinstance(cached, dict) else None
        try:
            rows = list(
                self.cutemarkets_provider.fetch_option_bars(
                    option_symbol=option_symbol,
                    start=day,
                    end=day,
                    multiplier=1,
                    timespan="day",
                )
                or []
            )
        except Exception:
            rows = []
        payload = dict(rows[-1]) if rows else None
        self._daily_bar_close_cache[key] = dict(payload) if isinstance(payload, dict) else None
        return dict(payload) if isinstance(payload, dict) else None


def backfill_historical_options_feed(
    *,
    config: HistoricalOptionsFeedConfig,
    cutemarkets_provider: CuteMarketsProvider,
    alpaca_data_provider: Optional[AlpacaDataProvider] = None,
    store: Optional[DataStore] = None,
) -> Dict[str, Any]:
    feed = HistoricalOptionsFeed(
        cutemarkets_provider=cutemarkets_provider,
        alpaca_data_provider=alpaca_data_provider,
        store=store,
    )
    return feed.ingest_range(config=config)


def _normalize_quote_mode(value: Any) -> str:
    normalized = str(value or "close").strip().lower()
    if normalized in {"full_day", "full-day", "full"}:
        return "full_day"
    return "close"


def _quote_fetch_window(*, day: date, quote_mode: str) -> Tuple[datetime, datetime]:
    normalized_mode = _normalize_quote_mode(quote_mode)
    if normalized_mode == "full_day":
        return (
            datetime.combine(day, dtime(0, 0), tzinfo=_UTC),
            datetime.combine(day + timedelta(days=1), dtime(0, 0), tzinfo=_UTC),
        )
    close_dt = datetime.combine(day, dtime(16, 0), tzinfo=_ET_ZONE)
    return (close_dt - timedelta(minutes=15)).astimezone(_UTC), (close_dt + timedelta(minutes=15)).astimezone(_UTC)


def _chain_snapshot_ts(day: date) -> datetime:
    return datetime.combine(day, dtime(23, 59, 59))


def _normalize_chain_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    ticker: str,
    day: date,
) -> List[Dict[str, Any]]:
    snapshot_ts = _chain_snapshot_ts(day)
    out: List[Dict[str, Any]] = []
    for row in rows:
        normalized = dict(row)
        if not str(normalized.get("option_symbol") or normalized.get("symbol") or "").strip():
            continue
        normalized["option_symbol"] = str(normalized.get("option_symbol") or normalized.get("symbol") or "").strip()
        normalized["underlying"] = str(normalized.get("underlying") or normalized.get("underlying_symbol") or ticker).strip().upper()
        normalized["ts"] = snapshot_ts
        expiration_day = _expiration_day(normalized)
        if expiration_day is not None:
            normalized["expiration"] = expiration_day
        strike = _safe_float(normalized.get("strike") or normalized.get("strike_price"))
        if strike is not None:
            normalized["strike"] = float(strike)
        option_type = str(normalized.get("option_type") or normalized.get("type") or "").strip().lower()
        if option_type:
            normalized["option_type"] = option_type
        out.append(normalized)
    return out


def _filter_chain_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    expiration_date_gte: Optional[str] = None,
    expiration_date_lte: Optional[str] = None,
    contract_type: Optional[str] = None,
    strike_price: Optional[float] = None,
) -> List[Dict[str, Any]]:
    min_expiry = _parse_day(expiration_date_gte)
    max_expiry = _parse_day(expiration_date_lte)
    expected_type = str(contract_type or "").strip().lower()
    expected_strike = _safe_float(strike_price)
    filtered: List[Dict[str, Any]] = []
    dedup: Dict[Tuple[str, date, float, str], Dict[str, Any]] = {}
    for raw in rows:
        row = dict(raw)
        expiration_day = _expiration_day(row)
        if min_expiry is not None and (expiration_day is None or expiration_day < min_expiry):
            continue
        if max_expiry is not None and (expiration_day is None or expiration_day > max_expiry):
            continue
        row_type = str(row.get("option_type") or row.get("type") or "").strip().lower()
        if expected_type and row_type != expected_type:
            continue
        strike = _safe_float(row.get("strike") or row.get("strike_price"))
        if expected_strike is not None and strike is not None and abs(float(strike) - expected_strike) > 1e-9:
            continue
        dedup[
            (
                str(row.get("option_symbol") or row.get("symbol") or "").strip(),
                expiration_day or date.min,
                float(strike or 0.0),
                row_type,
            )
        ] = row
    filtered = list(dedup.values())
    filtered.sort(key=lambda item: (_expiration_day(item) or date.max, float(item.get("strike") or 0.0)))
    return filtered


def _normalize_stock_daily_bar(ticker: str, row: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    ts = row.get("ts")
    if not isinstance(ts, datetime):
        raw_ts = row.get("t")
        if isinstance(raw_ts, str):
            normalized = raw_ts.strip()
            if normalized.endswith("Z"):
                normalized = normalized[:-1] + "+00:00"
            try:
                ts = datetime.fromisoformat(normalized)
            except ValueError:
                ts = None
            if isinstance(ts, datetime) and ts.tzinfo is not None:
                ts = ts.astimezone(_UTC).replace(tzinfo=None)
    if not isinstance(ts, datetime):
        return None
    return {
        "ticker": str(ticker).strip().upper(),
        "day": ts.date(),
        "ts": ts,
        "open": _safe_float(row.get("open", row.get("o"))) or 0.0,
        "high": _safe_float(row.get("high", row.get("h"))) or 0.0,
        "low": _safe_float(row.get("low", row.get("l"))) or 0.0,
        "close": _safe_float(row.get("close", row.get("c"))) or 0.0,
        "volume": int(row.get("volume", row.get("v")) or 0),
    }


def _select_close_quote(rows: Sequence[Mapping[str, Any]], *, day: date) -> Optional[Dict[str, Any]]:
    if not rows:
        return None
    window_start, window_end = _quote_fetch_window(day=day, quote_mode="close")
    start_cmp = window_start.astimezone(_UTC).replace(tzinfo=None)
    end_cmp = window_end.astimezone(_UTC).replace(tzinfo=None)
    in_window: List[Dict[str, Any]] = []
    for raw in rows:
        row = dict(raw)
        ts = row.get("ts")
        if not isinstance(ts, datetime):
            continue
        if start_cmp <= ts <= end_cmp:
            in_window.append(row)
    target = in_window[-1] if in_window else dict(rows[-1])
    return dict(target)


def _bar_close_snapshot(*, option_symbol: str, bar: Optional[Mapping[str, Any]]) -> Optional[Dict[str, Any]]:
    if not isinstance(bar, Mapping):
        return None
    close_value = _safe_float(bar.get("close"))
    ts = bar.get("ts")
    if close_value is None or close_value <= 0.0 or not isinstance(ts, datetime):
        return None
    volume = int(bar.get("volume") or 0)
    return {
        "symbol": str(option_symbol).strip(),
        "ts": ts,
        "bid": float(close_value),
        "ask": float(close_value),
        "bid_size": int(volume),
        "ask_size": int(volume),
    }


def _prioritize_contracts_for_pricing(
    contracts: Sequence[Mapping[str, Any]],
    *,
    spot: float,
) -> List[Dict[str, Any]]:
    grouped: Dict[Tuple[date, str], List[Dict[str, Any]]] = {}
    for raw in contracts:
        expiration_day = _expiration_day(raw)
        option_type = str(raw.get("option_type") or raw.get("type") or "").strip().lower()
        strike = _safe_float(raw.get("strike") or raw.get("strike_price"))
        if expiration_day is None or strike is None or strike <= 0.0 or not option_type:
            continue
        grouped.setdefault((expiration_day, option_type), []).append(dict(raw))
    prioritized: List[Dict[str, Any]] = []
    for key in sorted(grouped):
        rows = list(grouped[key])
        rows.sort(key=lambda row: float(row.get("strike") or row.get("strike_price") or 0.0))
        if not rows:
            continue
        atm_index = min(
            range(len(rows)),
            key=lambda idx: abs(float(rows[idx].get("strike") or rows[idx].get("strike_price") or 0.0) - float(spot)),
        )
        selected_indices = set(
            range(
                max(0, atm_index - _ATM_WINDOW_STRIKES_PER_SIDE),
                min(len(rows), atm_index + _ATM_WINDOW_STRIKES_PER_SIDE + 1),
            )
        )
        selected_indices.update(
            _sample_index_range(
                start=0,
                end=max(atm_index - _ATM_WINDOW_STRIKES_PER_SIDE - 1, -1),
                sample_count=_TAIL_SAMPLE_STRIKES_PER_SIDE,
            )
        )
        selected_indices.update(
            _sample_index_range(
                start=min(atm_index + _ATM_WINDOW_STRIKES_PER_SIDE + 1, len(rows)),
                end=len(rows) - 1,
                sample_count=_TAIL_SAMPLE_STRIKES_PER_SIDE,
            )
        )
        prioritized.extend(rows[idx] for idx in sorted(selected_indices) if 0 <= idx < len(rows))
    return prioritized


def _sample_index_range(*, start: int, end: int, sample_count: int) -> List[int]:
    if sample_count <= 0 or end < start:
        return []
    span = end - start + 1
    if span <= sample_count:
        return list(range(start, end + 1))
    if sample_count == 1:
        return [start]
    out: List[int] = []
    for idx in range(sample_count):
        ratio = float(idx) / float(sample_count - 1)
        chosen = start + int(round(ratio * float(end - start)))
        if not out or out[-1] != chosen:
            out.append(chosen)
    if out[-1] != end:
        out[-1] = end
    return out


def _estimate_option_greeks(
    *,
    option_price: float,
    underlying_price: float,
    strike: float,
    valuation_day: date,
    expiration_day: date,
    option_type: str,
) -> Tuple[Optional[float], Optional[float]]:
    if option_price <= 0.0 or underlying_price <= 0.0 or strike <= 0.0:
        return None, None
    years = max((expiration_day - valuation_day).days, 1) / 365.0
    intrinsic = _intrinsic_value(option_type=option_type, strike=strike, underlying_price=underlying_price)
    if option_price <= intrinsic + 1e-6:
        if option_type == "put":
            return 0.0001, -1.0 if strike > underlying_price else 0.0
        return 0.0001, 1.0 if underlying_price > strike else 0.0
    low = 0.0001
    high = 5.0
    for _ in range(60):
        mid = (low + high) / 2.0
        model_price = _black_scholes_price(
            underlying_price=underlying_price,
            strike=strike,
            years_to_expiry=years,
            volatility=mid,
            option_type=option_type,
        )
        if model_price < option_price:
            low = mid
        else:
            high = mid
    implied_vol = (low + high) / 2.0
    delta = _black_scholes_delta(
        underlying_price=underlying_price,
        strike=strike,
        years_to_expiry=years,
        volatility=implied_vol,
        option_type=option_type,
    )
    return implied_vol, delta


def _black_scholes_price(
    *,
    underlying_price: float,
    strike: float,
    years_to_expiry: float,
    volatility: float,
    option_type: str,
) -> float:
    intrinsic = _intrinsic_value(option_type=option_type, strike=strike, underlying_price=underlying_price)
    if years_to_expiry <= 0.0 or volatility <= 0.0:
        return intrinsic
    d1, d2 = _black_scholes_d1_d2(
        underlying_price=underlying_price,
        strike=strike,
        years_to_expiry=years_to_expiry,
        volatility=volatility,
    )
    if option_type == "put":
        return strike * _norm_cdf(-d2) - underlying_price * _norm_cdf(-d1)
    return underlying_price * _norm_cdf(d1) - strike * _norm_cdf(d2)


def _black_scholes_delta(
    *,
    underlying_price: float,
    strike: float,
    years_to_expiry: float,
    volatility: float,
    option_type: str,
) -> float:
    if years_to_expiry <= 0.0 or volatility <= 0.0:
        if option_type == "put":
            return -1.0 if strike > underlying_price else 0.0
        return 1.0 if underlying_price > strike else 0.0
    d1, _ = _black_scholes_d1_d2(
        underlying_price=underlying_price,
        strike=strike,
        years_to_expiry=years_to_expiry,
        volatility=volatility,
    )
    if option_type == "put":
        return _norm_cdf(d1) - 1.0
    return _norm_cdf(d1)


def _black_scholes_d1_d2(
    *,
    underlying_price: float,
    strike: float,
    years_to_expiry: float,
    volatility: float,
) -> Tuple[float, float]:
    denom = volatility * sqrt(years_to_expiry)
    d1 = (log(underlying_price / strike) + 0.5 * volatility * volatility * years_to_expiry) / denom
    d2 = d1 - denom
    return d1, d2


def _norm_cdf(value: float) -> float:
    return 0.5 * (1.0 + erf(value / sqrt(2.0)))


def _quote_mid(row: Mapping[str, Any]) -> float:
    bid = _safe_float(row.get("bid"))
    ask = _safe_float(row.get("ask"))
    if bid is not None and ask is not None and bid > 0.0 and ask > 0.0:
        return (bid + ask) / 2.0
    if ask is not None and ask > 0.0:
        return ask
    if bid is not None and bid > 0.0:
        return bid
    return 0.0


def _intrinsic_value(*, option_type: str, strike: float, underlying_price: float) -> float:
    if str(option_type or "").strip().lower() == "put":
        return max(float(strike) - float(underlying_price), 0.0)
    return max(float(underlying_price) - float(strike), 0.0)


def _expiration_day(row: Mapping[str, Any]) -> Optional[date]:
    raw = row.get("expiration") or row.get("expiration_date")
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    if isinstance(raw, str):
        try:
            return date.fromisoformat(raw)
        except ValueError:
            return None
    return None


def _parse_day(value: Any) -> Optional[date]:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return date.fromisoformat(value.strip())
        except ValueError:
            return None
    return None


def _safe_float(value: Any) -> Optional[float]:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if out != out or out in {float("inf"), float("-inf")}:
        return None
    return out
