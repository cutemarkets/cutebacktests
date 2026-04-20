from __future__ import annotations

import argparse
from collections import Counter
import json
import os
import socket
import socketserver
import threading
import time
from dataclasses import dataclass
from datetime import date, datetime, time as dtime, timedelta, timezone
from hashlib import sha1
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo

try:
    import polars as pl  # type: ignore
except Exception:  # pragma: no cover - optional runtime dependency
    pl = None

from ..providers.cutemarkets import CuteMarketsProvider
from ..settings import Settings
from ..storage import DataStore


_ET_TZ = ZoneInfo("America/New_York")
_OPTIONAL_AUXILIARY_TICKERS = frozenset({"I:VIX1D", "VIXY"})


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return {"__cutebacktests_type__": "datetime", "value": value.isoformat()}
    if isinstance(value, date):
        return {"__cutebacktests_type__": "date", "value": value.isoformat()}
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Unsupported JSON value: {type(value)!r}")


def _json_object_hook(payload: Dict[str, Any]) -> Any:
    marker = payload.get("__cutebacktests_type__")
    if marker == "datetime":
        try:
            return datetime.fromisoformat(str(payload.get("value") or ""))
        except Exception:
            return payload
    if marker == "date":
        try:
            return date.fromisoformat(str(payload.get("value") or ""))
        except Exception:
            return payload
    return payload


def _as_et(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc).astimezone(_ET_TZ)
    return value.astimezone(_ET_TZ)


def _iter_dates(start_day: date, end_day: date) -> List[date]:
    days: List[date] = []
    cursor = start_day
    while cursor <= end_day:
        days.append(cursor)
        cursor += timedelta(days=1)
    return days


def _stable_schema(rows: Sequence[Mapping[str, Any]]) -> List[str]:
    keys: List[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row.keys():
            key_str = str(key)
            if key_str in seen:
                continue
            seen.add(key_str)
            keys.append(key_str)
    return keys


def _parse_partition_key(key: str) -> Tuple[str, List[str]]:
    raw_key = str(key or "").strip()
    if not raw_key or ":" not in raw_key:
        raise ValueError(f"unsupported partition key: {key}")
    kind, remainder = raw_key.split(":", 1)
    if kind == "stock_daily":
        return kind, [remainder]
    if kind in {"session_bars", "option_chain_snapshot", "option_bars", "option_quotes"}:
        if ":" not in remainder:
            raise ValueError(f"unsupported partition key: {key}")
        symbol, day_text = remainder.rsplit(":", 1)
        return kind, [symbol, day_text]
    if kind == "option_quote_probe":
        parts = remainder.rsplit(":", 3)
        if len(parts) != 4:
            raise ValueError(f"unsupported partition key: {key}")
        symbol, day_text, ts_ns, fallback_mode = parts
        return kind, [symbol, day_text, ts_ns, fallback_mode]
    if kind == "contract_universe":
        parts = [part for part in remainder.split(":") if part]
        if len(parts) < 5:
            raise ValueError(f"unsupported partition key: {key}")
        if len(parts) == 5:
            return kind, [":".join(parts[:-4]), parts[-4], parts[-3], parts[-2], parts[-1], "inactive"]
        return kind, [":".join(parts[:-5]), parts[-5], parts[-4], parts[-3], parts[-2], parts[-1]]
    raise ValueError(f"unsupported partition key: {key}")


@dataclass(frozen=True)
class PartitionHandle:
    key: str
    path: str
    fmt: str
    row_count: int
    byte_size: int
    schema: List[str]
    last_access_epoch: float


@dataclass
class PartitionMeta:
    key: str
    path: str
    fmt: str
    row_count: int
    byte_size: int
    schema: List[str]
    created_at_epoch: float
    last_access_epoch: float
    lease_count: int = 0

    def handle(self) -> PartitionHandle:
        return PartitionHandle(
            key=self.key,
            path=self.path,
            fmt=self.fmt,
            row_count=int(self.row_count),
            byte_size=int(self.byte_size),
            schema=list(self.schema),
            last_access_epoch=float(self.last_access_epoch),
        )


def _partition_handle_payload(handle: PartitionHandle) -> Dict[str, Any]:
    return {
        "key": str(handle.key),
        "path": str(handle.path),
        "fmt": str(handle.fmt),
        "row_count": int(handle.row_count),
        "byte_size": int(handle.byte_size),
        "schema": list(handle.schema),
        "last_access_epoch": float(handle.last_access_epoch),
    }


def _partition_meta_payload(meta: PartitionMeta) -> Dict[str, Any]:
    return {
        "key": str(meta.key),
        "path": str(meta.path),
        "fmt": str(meta.fmt),
        "row_count": int(meta.row_count),
        "byte_size": int(meta.byte_size),
        "schema": list(meta.schema),
        "created_at_epoch": float(meta.created_at_epoch),
        "last_access_epoch": float(meta.last_access_epoch),
        "lease_count": int(meta.lease_count),
    }


def _encode_rows_json(rows: Sequence[Mapping[str, Any]]) -> str:
    return json.dumps({"rows": list(rows)}, default=_json_default, separators=(",", ":"))


def _decode_rows_json(raw: str) -> List[Dict[str, Any]]:
    payload = json.loads(raw, object_hook=_json_object_hook)
    rows = payload.get("rows") if isinstance(payload, dict) else []
    return [dict(row) for row in rows] if isinstance(rows, list) else []


def _read_rows_from_handle(handle: PartitionHandle) -> List[Dict[str, Any]]:
    path = Path(handle.path)
    if not path.exists():
        return []
    if handle.fmt == "ipc" and pl is not None:
        frame = pl.read_ipc(path, memory_map=True)
        return [dict(row) for row in frame.to_dicts()]
    return _decode_rows_json(path.read_text(encoding="utf-8"))


def _probe_quote_rows(
    *,
    rows: Sequence[Mapping[str, Any]],
    selection_ts: datetime,
    fallback_last: bool,
) -> Optional[Dict[str, Any]]:
    if selection_ts.tzinfo is not None:
        selection_ts_cmp = selection_ts.astimezone(timezone.utc).replace(tzinfo=None)
    else:
        selection_ts_cmp = selection_ts
    best_before: Optional[Dict[str, Any]] = None
    for row in rows:
        ts = row.get("ts")
        if not isinstance(ts, datetime):
            continue
        if ts.tzinfo is not None:
            ts_cmp = ts.astimezone(timezone.utc).replace(tzinfo=None)
        else:
            ts_cmp = ts
        if ts_cmp >= selection_ts_cmp:
            return dict(row)
        if fallback_last and ts_cmp <= selection_ts_cmp:
            best_before = dict(row)
    return best_before


class MarketDataRuntime:
    def __init__(
        self,
        *,
        root: Path,
        db_path: Path,
        env_path: str = ".env",
        settings: Optional[Settings] = None,
        store: Optional[DataStore] = None,
        cutemarkets_provider: Optional[CuteMarketsProvider] = None,
    ) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.partitions_dir = self.root / "partitions"
        self.partitions_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.root / "manifest.json"
        self._lock = threading.Lock()
        self._manifest: Dict[str, PartitionMeta] = {}
        self._store: Optional[DataStore] = store
        self._cutemarkets_provider: Optional[CuteMarketsProvider] = cutemarkets_provider
        self._hit_count: int = 0
        self._miss_count: int = 0
        self._eviction_count: int = 0
        self._hit_counts_by_kind: Counter[str] = Counter()
        self._miss_counts_by_kind: Counter[str] = Counter()
        self._eviction_counts_by_kind: Counter[str] = Counter()
        self._manifest_dirty: bool = False
        self._last_manifest_save_epoch: float = 0.0
        self._optional_aux_provider_denials: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
        if settings is None:
            settings = Settings.from_env(env_path)
            settings.db_path = Path(db_path)
            settings.data_dir = Path(db_path).parent
        self.settings = settings
        self.db_path = Path(db_path)
        self._load_manifest()

    def _load_manifest(self) -> None:
        if not self.manifest_path.exists():
            self._manifest = {}
            return
        try:
            raw = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except Exception:
            self._manifest = {}
            return
        manifest: Dict[str, PartitionMeta] = {}
        for key, payload in dict(raw or {}).items():
            if not isinstance(payload, dict):
                continue
            try:
                manifest[str(key)] = PartitionMeta(
                    key=str(key),
                    path=str(payload.get("path") or ""),
                    fmt=str(payload.get("fmt") or "json"),
                    row_count=int(payload.get("row_count") or 0),
                    byte_size=int(payload.get("byte_size") or 0),
                    schema=[str(item) for item in (payload.get("schema") or [])],
                    created_at_epoch=float(payload.get("created_at_epoch") or 0.0),
                    last_access_epoch=float(payload.get("last_access_epoch") or 0.0),
                    lease_count=int(payload.get("lease_count") or 0),
                )
            except Exception:
                continue
        self._manifest = manifest
        self._manifest_dirty = False
        self._last_manifest_save_epoch = time.time()

    def _save_manifest(self) -> None:
        payload = {
            key: _partition_meta_payload(value)
            for key, value in sorted(self._manifest.items())
        }
        self.manifest_path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
        self._manifest_dirty = False
        self._last_manifest_save_epoch = time.time()

    def _mark_manifest_dirty(self) -> None:
        self._manifest_dirty = True

    def _maybe_save_manifest(self, *, force: bool = False, min_interval_seconds: float = 10.0) -> None:
        if not self._manifest_dirty:
            return
        now = time.time()
        if not force and (now - float(self._last_manifest_save_epoch)) < float(min_interval_seconds):
            return
        self._save_manifest()

    def _store_handle(self) -> DataStore:
        if self._store is None:
            self._store = DataStore(self.db_path, read_only=True)
        return self._store

    def _cutemarkets_handle(self) -> Optional[CuteMarketsProvider]:
        if self._cutemarkets_provider is None and bool(self.settings.cutemarkets_api_key):
            self._cutemarkets_provider = CuteMarketsProvider(self.settings)
        return self._cutemarkets_provider

    @staticmethod
    def _is_optional_auxiliary_ticker(ticker: str) -> bool:
        return str(ticker or "").strip().upper() in _OPTIONAL_AUXILIARY_TICKERS

    @staticmethod
    def _provider_error_is_denial(exc: Exception) -> bool:
        message = str(exc or "").strip().lower()
        return (
            "not_authorized" in message
            or "not authorized" in message
            or "status=403" in message
            or " 403 " in message
        )

    def _optional_aux_denial_key(self, *, provider_name: str, dataset: str, ticker: str) -> Tuple[str, str, str]:
        return (
            str(provider_name or "").strip().lower(),
            str(dataset or "").strip().lower(),
            str(ticker or "").strip().upper(),
        )

    def _optional_aux_provider_denied(self, *, provider_name: str, dataset: str, ticker: str) -> bool:
        if not self._is_optional_auxiliary_ticker(ticker):
            return False
        return self._optional_aux_denial_key(
            provider_name=provider_name,
            dataset=dataset,
            ticker=ticker,
        ) in self._optional_aux_provider_denials

    def _cache_optional_aux_provider_denial(
        self,
        *,
        provider_name: str,
        dataset: str,
        ticker: str,
        reason: str,
    ) -> None:
        if not self._is_optional_auxiliary_ticker(ticker):
            return
        self._optional_aux_provider_denials[
            self._optional_aux_denial_key(provider_name=provider_name, dataset=dataset, ticker=ticker)
        ] = {
            "provider_name": str(provider_name or "").strip().lower(),
            "dataset": str(dataset or "").strip().lower(),
            "ticker": str(ticker or "").strip().upper(),
            "reason": str(reason or "").strip().lower(),
            "as_of": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        }

    def close(self) -> None:
        with self._lock:
            self._maybe_save_manifest(force=True)
        if self._store is not None:
            self._store.close()
            self._store = None

    def _partition_path(self, key: str, fmt: str) -> Path:
        ext = "ipc" if fmt == "ipc" else "json"
        return self.partitions_dir / f"{sha1(key.encode('utf-8')).hexdigest()}.{ext}"

    def warm(self, keys: Sequence[str]) -> List[PartitionHandle]:
        return [self.resolve(key, lease=False) for key in keys]

    def resolve(self, key: str, *, lease: bool = True) -> PartitionHandle:
        key = str(key or "").strip()
        if not key:
            raise ValueError("partition key is required")
        kind, _ = _parse_partition_key(key)
        with self._lock:
            meta = self._manifest.get(key)
            if meta is not None and Path(meta.path).exists():
                meta.last_access_epoch = time.time()
                if lease:
                    meta.lease_count = max(int(meta.lease_count), 0) + 1
                self._manifest[key] = meta
                self._hit_count += 1
                self._hit_counts_by_kind[kind] += 1
                self._mark_manifest_dirty()
                self._maybe_save_manifest()
                return meta.handle()

        rows = self._materialize_rows_for_key(key)
        schema = _stable_schema(rows)
        fmt = "ipc" if pl is not None else "json"
        path = self._partition_path(key, fmt)
        if fmt == "ipc" and pl is not None:
            pl.DataFrame(rows).write_ipc(path)
        else:
            path.write_text(_encode_rows_json(rows), encoding="utf-8")
        stat = path.stat()
        now = time.time()
        meta = PartitionMeta(
            key=key,
            path=str(path),
            fmt=fmt,
            row_count=len(rows),
            byte_size=int(stat.st_size),
            schema=schema,
            created_at_epoch=now,
            last_access_epoch=now,
            lease_count=1 if lease else 0,
        )
        with self._lock:
            self._manifest[key] = meta
            self._miss_count += 1
            self._miss_counts_by_kind[kind] += 1
            self._mark_manifest_dirty()
            self._maybe_save_manifest()
        return meta.handle()

    def release(self, keys: Sequence[str]) -> Dict[str, Any]:
        released: List[str] = []
        with self._lock:
            for raw_key in keys:
                key = str(raw_key or "").strip()
                if not key:
                    continue
                meta = self._manifest.get(key)
                if meta is None:
                    continue
                if int(meta.lease_count) > 0:
                    meta.lease_count = max(int(meta.lease_count) - 1, 0)
                self._manifest[key] = meta
                released.append(key)
            if released:
                self._mark_manifest_dirty()
                self._maybe_save_manifest()
        return {"released": released, "released_count": len(released)}

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            handles = [meta.handle() for meta in self._manifest.values() if Path(meta.path).exists()]
            hit_count = int(self._hit_count)
            miss_count = int(self._miss_count)
            eviction_count = int(self._eviction_count)
            leased_partition_count = sum(1 for meta in self._manifest.values() if int(meta.lease_count) > 0)
            format_counts = Counter(str(meta.fmt or "json") for meta in self._manifest.values())
            kind_stats: Dict[str, Dict[str, Any]] = {}
            for meta in self._manifest.values():
                path = Path(meta.path)
                if not path.exists():
                    continue
                kind, _ = _parse_partition_key(meta.key)
                bucket = kind_stats.setdefault(
                    kind,
                    {
                        "partition_count": 0,
                        "total_bytes": 0,
                        "warm_partition_bytes": 0,
                        "leased_partition_count": 0,
                        "hit_count": int(self._hit_counts_by_kind.get(kind, 0)),
                        "miss_count": int(self._miss_counts_by_kind.get(kind, 0)),
                        "eviction_count": int(self._eviction_counts_by_kind.get(kind, 0)),
                    },
                )
                bucket["partition_count"] = int(bucket.get("partition_count") or 0) + 1
                bucket["total_bytes"] = int(bucket.get("total_bytes") or 0) + int(meta.byte_size or 0)
                bucket["warm_partition_bytes"] = int(bucket.get("warm_partition_bytes") or 0) + int(meta.byte_size or 0)
                if int(meta.lease_count) > 0:
                    bucket["leased_partition_count"] = int(bucket.get("leased_partition_count") or 0) + 1
        total_bytes = sum(int(item.byte_size) for item in handles)
        total_resolves = hit_count + miss_count
        for bucket in kind_stats.values():
            total_kind_resolves = int(bucket.get("hit_count") or 0) + int(bucket.get("miss_count") or 0)
            bucket["hit_rate"] = (
                float(bucket.get("hit_count") or 0) / float(total_kind_resolves)
                if total_kind_resolves > 0
                else 0.0
            )
        return {
            "partition_count": len(handles),
            "total_bytes": total_bytes,
            "warm_partition_bytes": total_bytes,
            "leased_partition_count": leased_partition_count,
            "hit_count": hit_count,
            "miss_count": miss_count,
            "hit_rate": (float(hit_count) / float(total_resolves)) if total_resolves > 0 else 0.0,
            "eviction_count": eviction_count,
            "ipc_enabled": bool(pl is not None),
            "format_counts": dict(format_counts),
            "partition_kind_stats": kind_stats,
            "keys": [item.key for item in sorted(handles, key=lambda item: item.key)],
        }

    def evict(self, *, cold_only: bool = True, older_than_seconds: float = 300.0) -> Dict[str, Any]:
        now = time.time()
        removed: List[str] = []
        removed_bytes = 0
        with self._lock:
            keys = list(self._manifest)
            for key in keys:
                meta = self._manifest.get(key)
                if meta is None:
                    continue
                if int(meta.lease_count) > 0:
                    continue
                if cold_only and (now - float(meta.last_access_epoch)) < float(older_than_seconds):
                    continue
                path = Path(meta.path)
                if path.exists():
                    try:
                        removed_bytes += int(path.stat().st_size)
                        path.unlink()
                    except Exception:
                        continue
                try:
                    kind, _ = _parse_partition_key(key)
                    self._eviction_counts_by_kind[kind] += 1
                except Exception:
                    pass
                self._manifest.pop(key, None)
                removed.append(key)
            self._eviction_count += len(removed)
            self._mark_manifest_dirty()
            self._maybe_save_manifest(force=True)
        return {"removed": removed, "removed_count": len(removed), "removed_bytes": int(removed_bytes)}

    def _materialize_rows_for_key(self, key: str) -> List[Dict[str, Any]]:
        kind, parts = _parse_partition_key(key)
        if kind == "stock_daily":
            return self._load_stock_daily(parts[0])
        if kind == "session_bars":
            return self._load_session_bars(parts[0], date.fromisoformat(parts[1]))
        if kind == "option_chain_snapshot":
            return self._load_option_chain_snapshot(parts[0], date.fromisoformat(parts[1]))
        if kind == "option_bars":
            return self._load_option_bars(parts[0], date.fromisoformat(parts[1]))
        if kind == "option_quotes":
            return self._load_option_quotes(parts[0], date.fromisoformat(parts[1]))
        if kind == "option_quote_probe":
            return self._load_option_quote_probe(
                parts[0],
                date.fromisoformat(parts[1]),
                int(parts[2]),
                str(parts[3] or "strict"),
            )
        if kind == "contract_universe":
            return self._load_contract_universe(
                parts[0],
                date.fromisoformat(parts[1]),
                int(parts[2]),
                int(parts[3]),
                parts[4],
                parts[5],
            )
        raise ValueError(f"unsupported partition key: {key}")

    def _load_stock_daily(self, ticker: str) -> List[Dict[str, Any]]:
        return list(self._store_handle().get_stock_daily_bars(str(ticker).upper()))

    def _load_session_bars(self, ticker: str, day: date) -> List[Dict[str, Any]]:
        store = self._store_handle()
        start_dt = datetime.combine(day, dtime(0, 0))
        end_dt = datetime.combine(day + timedelta(days=1), dtime(0, 0))
        ticker_key = str(ticker).upper()
        rows = list(store.get_stock_bars(ticker=ticker_key, start=start_dt, end=end_dt))
        if not rows:
            provider = self._cutemarkets_handle()
            if provider is not None and not self._optional_aux_provider_denied(
                provider_name="cutemarkets",
                dataset="session_bars",
                ticker=ticker_key,
            ):
                try:
                    rows = list(provider.fetch_stock_bars(ticker_key, start=day, end=day, multiplier=1, timespan="minute"))
                except Exception as exc:
                    if self._is_optional_auxiliary_ticker(ticker_key) and self._provider_error_is_denial(exc):
                        self._cache_optional_aux_provider_denial(
                            provider_name="cutemarkets",
                            dataset="session_bars",
                            ticker=ticker_key,
                            reason="not_authorized",
                        )
                    rows = []
                if not rows and self._is_optional_auxiliary_ticker(ticker_key):
                    self._cache_optional_aux_provider_denial(
                        provider_name="cutemarkets",
                        dataset="session_bars",
                        ticker=ticker_key,
                        reason="empty",
                    )
        out: List[Dict[str, Any]] = []
        for row in rows:
            ts = row.get("ts")
            if not isinstance(ts, datetime):
                continue
            et_ts = _as_et(ts)
            if et_ts.date() != day:
                continue
            if et_ts.time() < dtime(9, 30) or et_ts.time() > dtime(16, 0):
                continue
            out.append(dict(row))
        out.sort(key=lambda item: item.get("ts") or datetime.min)
        return out

    def _load_option_chain_snapshot(self, ticker: str, day: date) -> List[Dict[str, Any]]:
        store = self._store_handle()
        as_of = datetime.combine(day, dtime.max)
        rows = list(store.get_option_chain_snapshot(str(ticker).upper(), as_of))
        if rows:
            return rows
        provider = self._cutemarkets_handle()
        if provider is None:
            return []
        try:
            return list(provider.fetch_option_chain_snapshot(str(ticker).upper(), as_of=day) or [])
        except Exception:
            return []

    def _load_option_bars(self, option_symbol: str, day: date) -> List[Dict[str, Any]]:
        store = self._store_handle()
        start_dt = datetime.combine(day, dtime(0, 0))
        end_dt = datetime.combine(day, dtime(23, 59, 59))
        rows = list(store.get_option_bars(symbol=option_symbol, start=start_dt, end=end_dt))
        if rows:
            return rows
        provider = self._cutemarkets_handle()
        if provider is None:
            return []
        try:
            return list(
                provider.fetch_option_bars(
                    option_symbol=option_symbol,
                    start=day,
                    end=day,
                    multiplier=1,
                    timespan="minute",
                )
            )
        except Exception:
            return []

    def _load_option_quotes(self, option_symbol: str, day: date) -> List[Dict[str, Any]]:
        start_dt = datetime.combine(day, dtime(0, 0), tzinfo=timezone.utc)
        end_dt = datetime.combine(day + timedelta(days=1), dtime(0, 0), tzinfo=timezone.utc)
        store = self._store_handle()
        get_option_quotes = getattr(store, "get_option_quotes", None)
        if callable(get_option_quotes):
            try:
                rows = list(
                    get_option_quotes(
                        symbol=option_symbol,
                        start=start_dt.replace(tzinfo=None),
                        end=end_dt.replace(tzinfo=None),
                    )
                )
            except Exception:
                rows = []
            if rows:
                return rows
        provider = self._cutemarkets_handle()
        if provider is not None:
            try:
                rows = list(
                    provider.fetch_option_quotes(
                        option_symbol=option_symbol,
                        start=start_dt,
                        end=end_dt,
                        limit=0,
                    )
                )
            except Exception:
                rows = []
            if rows:
                return rows
        if provider is None:
            return []
        return []

    def _load_option_quote_probe(
        self,
        option_symbol: str,
        day: date,
        ts_ns: int,
        fallback_mode: str,
    ) -> List[Dict[str, Any]]:
        selection_ts = datetime.fromtimestamp(float(ts_ns) / 1_000_000_000.0, tz=timezone.utc)
        fallback_last = str(fallback_mode or "strict").strip().lower() in {"last", "fallback_last", "true", "1"}
        option_quote_key = f"option_quotes:{option_symbol}:{day.isoformat()}"
        with self._lock:
            existing_meta = self._manifest.get(option_quote_key)
        if existing_meta is not None and Path(existing_meta.path).exists():
            try:
                rows = _read_rows_from_handle(existing_meta.handle())
            except Exception:
                rows = []
            quote = _probe_quote_rows(rows=rows, selection_ts=selection_ts, fallback_last=fallback_last)
            return [quote] if quote is not None else []

        provider = self._cutemarkets_handle()
        if provider is None:
            return []
        try:
            quote = provider.fetch_option_quote_probe(
                option_symbol=option_symbol,
                ts=selection_ts,
                day=day,
                fallback_last=fallback_last,
            )
        except Exception:
            return []
        return [dict(quote)] if isinstance(quote, dict) else []

    def _load_contract_universe(
        self,
        ticker: str,
        day: date,
        option_min_dte: int,
        option_max_dte: int,
        option_type: str,
        status: str,
    ) -> List[Dict[str, Any]]:
        rows = self._load_option_chain_snapshot(ticker=ticker, day=day)
        option_type_norm = str(option_type or "").strip().lower()
        status_norm = str(status or "inactive").strip().lower() or "inactive"
        if not rows:
            provider = self._cutemarkets_handle()
            if provider is None:
                return []
            min_expiry = day + timedelta(days=max(option_min_dte, 0))
            max_expiry = day + timedelta(days=max(option_max_dte, option_min_dte))
            try:
                return list(
                    provider.fetch_option_contracts(
                        underlying_symbol=str(ticker).upper(),
                        expiration_date_gte=min_expiry.isoformat(),
                        expiration_date_lte=max_expiry.isoformat(),
                        option_type=option_type_norm,
                        status=status_norm,
                        as_of=day.isoformat(),
                        limit=1000,
                    )
                    or []
                )
            except Exception:
                return []
        min_expiry = day + timedelta(days=max(option_min_dte, 0))
        max_expiry = day + timedelta(days=max(option_max_dte, option_min_dte))
        out: List[Dict[str, Any]] = []
        for row in rows:
            row_type = str(row.get("option_type") or row.get("type") or "").strip().lower()
            if option_type_norm and row_type and row_type != option_type_norm:
                continue
            row_status = str(row.get("status") or "").strip().lower()
            if status_norm and row_status and row_status != status_norm and status_norm != "all":
                continue
            expiry_raw = row.get("expiration") or row.get("expiration_date")
            expiry_day: Optional[date]
            if isinstance(expiry_raw, datetime):
                expiry_day = expiry_raw.date()
            elif isinstance(expiry_raw, date):
                expiry_day = expiry_raw
            else:
                try:
                    expiry_day = date.fromisoformat(str(expiry_raw))
                except Exception:
                    expiry_day = None
            if expiry_day is None or expiry_day < min_expiry or expiry_day > max_expiry:
                continue
            out.append(dict(row))
        return out


class _RuntimeServer(socketserver.UnixStreamServer):
    allow_reuse_address = True

    def __init__(self, socket_path: str, runtime: MarketDataRuntime):
        self.runtime = runtime
        super().__init__(socket_path, _RuntimeRequestHandler)


class _RuntimeRequestHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        raw = self.rfile.readline()
        if not raw:
            return
        try:
            request = json.loads(raw.decode("utf-8"))
            command = str(request.get("command") or "").strip().lower()
            payload = request.get("payload") or {}
            if command == "resolve":
                handle = self.server.runtime.resolve(  # type: ignore[attr-defined]
                    str(payload.get("key") or ""),
                    lease=bool(payload.get("lease", True)),
                )
                response = {"ok": True, "handle": _partition_handle_payload(handle)}
            elif command == "warm":
                keys = [str(item) for item in (payload.get("keys") or []) if str(item or "").strip()]
                handles = self.server.runtime.warm(keys)  # type: ignore[attr-defined]
                response = {"ok": True, "handles": [_partition_handle_payload(handle) for handle in handles]}
            elif command == "stats":
                response = {"ok": True, "stats": self.server.runtime.stats()}  # type: ignore[attr-defined]
            elif command == "release":
                response = {"ok": True, "released": self.server.runtime.release(payload.get("keys") or [])}  # type: ignore[attr-defined]
            elif command == "evict":
                response = {
                    "ok": True,
                    "evicted": self.server.runtime.evict(  # type: ignore[attr-defined]
                        cold_only=bool(payload.get("cold_only", True)),
                        older_than_seconds=float(payload.get("older_than_seconds", 300.0) or 300.0),
                    ),
                }
            else:
                response = {"ok": False, "error": f"unsupported command: {command}"}
        except Exception as exc:
            response = {"ok": False, "error": str(exc)}
        self.wfile.write((json.dumps(response, separators=(",", ":")) + "\n").encode("utf-8"))


class MarketDataRuntimeClient:
    def __init__(self, socket_path: str):
        self.socket_path = str(socket_path or "").strip()
        if not self.socket_path:
            raise ValueError("runtime socket path is required")
        self._stats_cache_payload: Optional[Dict[str, Any]] = None
        self._stats_cache_epoch: float = 0.0

    def _request(self, command: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.connect(self.socket_path)
            message = json.dumps(
                {"command": command, "payload": payload or {}},
                separators=(",", ":"),
            ).encode("utf-8") + b"\n"
            sock.sendall(message)
            chunks: List[bytes] = []
            while True:
                block = sock.recv(65536)
                if not block:
                    break
                chunks.append(block)
                if b"\n" in block:
                    break
        raw = b"".join(chunks).strip()
        response = json.loads(raw.decode("utf-8")) if raw else {}
        if not bool(response.get("ok")):
            raise RuntimeError(str(response.get("error") or f"{command} failed"))
        return dict(response)

    def resolve(self, key: str, *, lease: bool = True) -> PartitionHandle:
        payload = self._request("resolve", {"key": key, "lease": bool(lease)})
        return PartitionHandle(**dict(payload.get("handle") or {}))

    def warm(self, keys: Sequence[str]) -> List[PartitionHandle]:
        payload = self._request("warm", {"keys": list(keys)})
        return [PartitionHandle(**dict(item)) for item in (payload.get("handles") or [])]

    def stats(self, *, force: bool = False, max_age_seconds: float = 1.0) -> Dict[str, Any]:
        if (
            not force
            and self._stats_cache_payload is not None
            and max_age_seconds >= 0.0
            and (time.time() - float(self._stats_cache_epoch)) <= float(max_age_seconds)
        ):
            return dict(self._stats_cache_payload)
        payload = self._request("stats", {})
        stats_payload = dict(payload.get("stats") or {})
        self._stats_cache_payload = dict(stats_payload)
        self._stats_cache_epoch = time.time()
        return stats_payload

    def release(self, keys: Sequence[str]) -> Dict[str, Any]:
        payload = self._request("release", {"keys": list(keys)})
        return dict(payload.get("released") or {})

    def evict(self, *, cold_only: bool = True, older_than_seconds: float = 300.0) -> Dict[str, Any]:
        payload = self._request(
            "evict",
            {"cold_only": bool(cold_only), "older_than_seconds": float(older_than_seconds)},
        )
        return dict(payload.get("evicted") or {})

    def load_rows(self, handle: PartitionHandle) -> List[Dict[str, Any]]:
        return _read_rows_from_handle(handle)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Single-host market data runtime")
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve")
    serve.add_argument("--root", required=True)
    serve.add_argument("--db-path", required=True)
    serve.add_argument("--socket", required=True)
    serve.add_argument("--env", default=".env")

    warm = sub.add_parser("warm")
    warm.add_argument("--socket", required=True)
    warm.add_argument("--manifest", required=True, help="JSON file containing {'keys': [...]} or a raw list")

    stats = sub.add_parser("stats")
    stats.add_argument("--socket", required=True)

    evict = sub.add_parser("evict")
    evict.add_argument("--socket", required=True)
    evict.add_argument("--older-than-seconds", type=float, default=300.0)
    evict.add_argument("--all", dest="cold_only", action="store_false")
    evict.set_defaults(cold_only=True)
    return parser


def _load_warm_manifest(path: Path) -> List[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [str(item) for item in payload if str(item or "").strip()]
    if isinstance(payload, dict):
        return [str(item) for item in (payload.get("keys") or []) if str(item or "").strip()]
    return []


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "serve":
        socket_path = Path(args.socket)
        socket_path.parent.mkdir(parents=True, exist_ok=True)
        if socket_path.exists():
            socket_path.unlink()
        runtime = MarketDataRuntime(
            root=Path(args.root),
            db_path=Path(args.db_path),
            env_path=str(args.env),
        )
        try:
            with _RuntimeServer(str(socket_path), runtime) as server:
                server.serve_forever(poll_interval=0.25)
        finally:
            runtime.close()
            if socket_path.exists():
                socket_path.unlink()
        return 0
    client = MarketDataRuntimeClient(str(args.socket))
    if args.command == "warm":
        keys = _load_warm_manifest(Path(args.manifest))
        print(
            json.dumps(
                {"handles": [_partition_handle_payload(handle) for handle in client.warm(keys)]},
                indent=2,
            )
        )
        return 0
    if args.command == "stats":
        print(json.dumps(client.stats(), indent=2))
        return 0
    if args.command == "evict":
        print(json.dumps(client.evict(cold_only=bool(args.cold_only), older_than_seconds=float(args.older_than_seconds)), indent=2))
        return 0
    raise ValueError(f"unsupported command: {args.command}")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
