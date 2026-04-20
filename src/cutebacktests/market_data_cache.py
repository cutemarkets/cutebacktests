from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timezone
from multiprocessing.managers import BaseProxy, SyncManager
from multiprocessing.shared_memory import SharedMemory
from threading import Condition, Lock, RLock, Semaphore
from time import monotonic_ns
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Protocol, Sequence, Tuple

import numpy as np

from .providers.cutemarkets import CuteMarketsProvider
from .settings import Settings
from .storage import DataStore

MARKET_DATA_CACHE_MODES = ("local", "process_shared", "host_shared")
_CACHE_DATASETS = {
    "session_bars",
    "premarket_bars",
    "option_chain_snapshot",
    "option_bars",
    "option_quotes",
}
_EMPTY_BYTES = 1
_BAR_DTYPE = np.dtype(
    [
        ("ts_ns", "<i8"),
        ("open", "<f8"),
        ("high", "<f8"),
        ("low", "<f8"),
        ("close", "<f8"),
        ("volume", "<i8"),
    ]
)
_QUOTE_DTYPE = np.dtype(
    [
        ("ts_ns", "<i8"),
        ("bid", "<f8"),
        ("ask", "<f8"),
        ("bid_size", "<i8"),
        ("ask_size", "<i8"),
    ]
)
_SNAPSHOT_DTYPE = np.dtype(
    [
        ("option_symbol", "U48"),
        ("underlying", "U16"),
        ("expiration_ns", "<i8"),
        ("strike", "<f8"),
        ("option_type", "U16"),
        ("bid", "<f8"),
        ("ask", "<f8"),
        ("midpoint", "<f8"),
        ("delta", "<f8"),
        ("iv", "<f8"),
        ("open_interest", "<i8"),
        ("volume", "<i8"),
    ]
)


def normalize_market_data_cache_mode(value: Any) -> str:
    normalized = str(value or "local").strip().lower() or "local"
    if normalized not in MARKET_DATA_CACHE_MODES:
        raise ValueError(
            f"Unsupported market data cache mode: {value!r}. "
            f"Expected one of {', '.join(MARKET_DATA_CACHE_MODES)}."
        )
    return normalized


class MarketDataCacheBackend(Protocol):
    mode: str

    def get_or_load_rows(
        self,
        *,
        dataset: str,
        key: Tuple[Any, ...],
        loader: Callable[[], List[Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        ...

    def stats_snapshot(self) -> Dict[str, Any]:
        ...

    def close(self) -> None:
        ...


def _as_utc_naive_timestamp_ns(ts: Any) -> int:
    if not isinstance(ts, datetime):
        return 0
    if ts.tzinfo is None:
        aware = ts.replace(tzinfo=timezone.utc)
    else:
        aware = ts.astimezone(timezone.utc)
    return int(round(aware.timestamp() * 1_000_000_000))


def _utc_datetime_from_ns(value: int) -> datetime:
    return datetime.fromtimestamp(float(int(value)) / 1_000_000_000.0, tz=timezone.utc).replace(tzinfo=None)


def _safe_float(value: Any) -> float:
    if value in {None, ""}:
        return float("nan")
    try:
        return float(value)
    except Exception:
        return float("nan")


def _safe_int(value: Any, *, default: int = 0) -> int:
    if value in {None, ""}:
        return int(default)
    try:
        return int(value)
    except Exception:
        return int(default)


def _rows_to_array(dataset: str, rows: Sequence[Mapping[str, Any]]) -> np.ndarray:
    normalized_rows = [row for row in rows if isinstance(row, Mapping)]
    if dataset in {"session_bars", "premarket_bars", "option_bars"}:
        array = np.empty(len(normalized_rows), dtype=_BAR_DTYPE)
        for index, row in enumerate(normalized_rows):
            array[index]["ts_ns"] = _as_utc_naive_timestamp_ns(row.get("ts"))
            array[index]["open"] = _safe_float(row.get("open"))
            array[index]["high"] = _safe_float(row.get("high"))
            array[index]["low"] = _safe_float(row.get("low"))
            array[index]["close"] = _safe_float(row.get("close"))
            array[index]["volume"] = _safe_int(row.get("volume"))
        return array
    if dataset == "option_quotes":
        array = np.empty(len(normalized_rows), dtype=_QUOTE_DTYPE)
        for index, row in enumerate(normalized_rows):
            array[index]["ts_ns"] = _as_utc_naive_timestamp_ns(row.get("ts"))
            array[index]["bid"] = _safe_float(row.get("bid"))
            array[index]["ask"] = _safe_float(row.get("ask"))
            array[index]["bid_size"] = _safe_int(row.get("bid_size"))
            array[index]["ask_size"] = _safe_int(row.get("ask_size"))
        return array
    if dataset == "option_chain_snapshot":
        array = np.empty(len(normalized_rows), dtype=_SNAPSHOT_DTYPE)
        for index, row in enumerate(normalized_rows):
            array[index]["option_symbol"] = str(row.get("option_symbol") or row.get("symbol") or "")
            array[index]["underlying"] = str(row.get("underlying") or "")
            array[index]["expiration_ns"] = _as_utc_naive_timestamp_ns(row.get("expiration"))
            array[index]["strike"] = _safe_float(row.get("strike"))
            array[index]["option_type"] = str(row.get("option_type") or "")
            array[index]["bid"] = _safe_float(row.get("bid"))
            array[index]["ask"] = _safe_float(row.get("ask"))
            array[index]["midpoint"] = _safe_float(row.get("midpoint"))
            array[index]["delta"] = _safe_float(row.get("delta"))
            array[index]["iv"] = _safe_float(row.get("iv"))
            array[index]["open_interest"] = _safe_int(row.get("open_interest"), default=-1)
            array[index]["volume"] = _safe_int(row.get("volume"), default=-1)
        return array
    raise ValueError(f"Unsupported cache dataset: {dataset}")


def _decode_array(dataset: str, array: np.ndarray) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if dataset in {"session_bars", "premarket_bars", "option_bars"}:
        for row in array:
            rows.append(
                {
                    "ts": _utc_datetime_from_ns(int(row["ts_ns"])),
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": int(row["volume"]),
                }
            )
        return rows
    if dataset == "option_quotes":
        for row in array:
            bid = float(row["bid"])
            ask = float(row["ask"])
            rows.append(
                {
                    "ts": _utc_datetime_from_ns(int(row["ts_ns"])),
                    "bid": None if np.isnan(bid) else bid,
                    "ask": None if np.isnan(ask) else ask,
                    "bid_size": int(row["bid_size"]),
                    "ask_size": int(row["ask_size"]),
                }
            )
        return rows
    if dataset == "option_chain_snapshot":
        for row in array:
            expiration_ns = int(row["expiration_ns"])
            bid = float(row["bid"])
            ask = float(row["ask"])
            midpoint = float(row["midpoint"])
            delta = float(row["delta"])
            iv = float(row["iv"])
            open_interest = int(row["open_interest"])
            volume = int(row["volume"])
            rows.append(
                {
                    "option_symbol": str(row["option_symbol"]),
                    "symbol": str(row["option_symbol"]),
                    "underlying": str(row["underlying"]),
                    "expiration": _utc_datetime_from_ns(expiration_ns) if expiration_ns > 0 else None,
                    "strike": float(row["strike"]),
                    "option_type": str(row["option_type"]),
                    "bid": None if np.isnan(bid) else bid,
                    "ask": None if np.isnan(ask) else ask,
                    "midpoint": None if np.isnan(midpoint) else midpoint,
                    "delta": None if np.isnan(delta) else delta,
                    "iv": None if np.isnan(iv) else iv,
                    "open_interest": None if open_interest < 0 else open_interest,
                    "volume": None if volume < 0 else volume,
                }
            )
        return rows
    raise ValueError(f"Unsupported cache dataset: {dataset}")


def _dtype_for_dataset(dataset: str) -> np.dtype:
    if dataset in {"session_bars", "premarket_bars", "option_bars"}:
        return _BAR_DTYPE
    if dataset == "option_quotes":
        return _QUOTE_DTYPE
    if dataset == "option_chain_snapshot":
        return _SNAPSHOT_DTYPE
    raise ValueError(f"Unsupported cache dataset: {dataset}")


def _approx_rows_nbytes(dataset: str, rows: Sequence[Mapping[str, Any]]) -> int:
    if not rows:
        return _EMPTY_BYTES
    return max(int(_rows_to_array(dataset, rows).nbytes), _EMPTY_BYTES)


@dataclass
class _ProcessSharedEntry:
    rows: List[Dict[str, Any]]
    nbytes: int
    last_access_ns: int


class ProcessSharedMarketDataCache:
    mode = "process_shared"

    def __init__(self, *, max_bytes: int = 0):
        self._lock = RLock()
        self._conditions: Dict[Tuple[str, Tuple[Any, ...]], Condition] = {}
        self._entries: Dict[Tuple[str, Tuple[Any, ...]], _ProcessSharedEntry] = {}
        self._max_bytes = max(int(max_bytes), 0)
        self._current_bytes = 0
        self._peak_bytes = 0
        self._dataset_hits: Counter[str] = Counter()
        self._dataset_misses: Counter[str] = Counter()
        self._coalesced_load_count = 0

    def _evict_if_needed_locked(self) -> None:
        if self._max_bytes <= 0 or self._current_bytes <= self._max_bytes:
            return
        target = int(self._max_bytes * 0.85)
        ordered = sorted(self._entries.items(), key=lambda item: item[1].last_access_ns)
        for entry_key, entry in ordered:
            if self._current_bytes <= target:
                break
            self._current_bytes = max(self._current_bytes - int(entry.nbytes), 0)
            self._entries.pop(entry_key, None)

    def get_or_load_rows(
        self,
        *,
        dataset: str,
        key: Tuple[Any, ...],
        loader: Callable[[], List[Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        normalized_dataset = str(dataset or "").strip().lower()
        if normalized_dataset not in _CACHE_DATASETS:
            return list(loader() or [])
        entry_key = (normalized_dataset, tuple(key))
        with self._lock:
            cached = self._entries.get(entry_key)
            if cached is not None:
                cached.last_access_ns = monotonic_ns()
                self._dataset_hits[normalized_dataset] += 1
                return cached.rows
            while entry_key in self._conditions:
                self._coalesced_load_count += 1
                self._conditions[entry_key].wait()
                cached = self._entries.get(entry_key)
                if cached is not None:
                    cached.last_access_ns = monotonic_ns()
                    self._dataset_hits[normalized_dataset] += 1
                    return cached.rows
            self._conditions[entry_key] = Condition(self._lock)
            self._dataset_misses[normalized_dataset] += 1
        try:
            rows = list(loader() or [])
            nbytes = _approx_rows_nbytes(normalized_dataset, rows)
            with self._lock:
                self._entries[entry_key] = _ProcessSharedEntry(
                    rows=rows,
                    nbytes=nbytes,
                    last_access_ns=monotonic_ns(),
                )
                self._current_bytes += int(nbytes)
                self._peak_bytes = max(self._peak_bytes, self._current_bytes)
                self._evict_if_needed_locked()
                condition = self._conditions.pop(entry_key, None)
                if condition is not None:
                    condition.notify_all()
            return rows
        except Exception:
            with self._lock:
                condition = self._conditions.pop(entry_key, None)
                if condition is not None:
                    condition.notify_all()
            raise

    def stats_snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "mode": self.mode,
                "dataset_hits": dict(self._dataset_hits),
                "dataset_misses": dict(self._dataset_misses),
                "coalesced_load_count": int(self._coalesced_load_count),
                "resident_bytes": int(self._current_bytes),
                "resident_bytes_peak": int(self._peak_bytes),
                "entry_count": len(self._entries),
            }

    def close(self) -> None:
        with self._lock:
            self._entries.clear()
            self._conditions.clear()
            self._current_bytes = 0


@dataclass
class _SharedMemoryEntry:
    dataset: str
    key: Tuple[Any, ...]
    shm_name: str
    row_count: int
    nbytes: int
    last_access_ns: int
    pin_count: int = 0


class _SharedMarketDataCacheService:
    def __init__(
        self,
        settings: Settings,
        *,
        read_only_store: bool,
        persist_fetched_market_data: bool,
        max_bytes: int,
        loader_workers: int,
    ) -> None:
        self._settings = settings
        self._read_only_store = bool(read_only_store)
        self._persist_fetched_market_data = bool(persist_fetched_market_data) and not self._read_only_store
        self._lock = Lock()
        self._entries: Dict[Tuple[str, Tuple[Any, ...]], _SharedMemoryEntry] = {}
        self._conditions: Dict[Tuple[str, Tuple[Any, ...]], Condition] = {}
        self._current_bytes = 0
        self._peak_bytes = 0
        self._max_bytes = max(int(max_bytes), 0)
        self._dataset_hits: Counter[str] = Counter()
        self._dataset_misses: Counter[str] = Counter()
        self._coalesced_load_count = 0
        self._loader_gate = Semaphore(max(int(loader_workers), 1))

    def _evict_if_needed_locked(self) -> None:
        if self._max_bytes <= 0 or self._current_bytes <= self._max_bytes:
            return
        target = int(self._max_bytes * 0.85)
        ordered = sorted(self._entries.items(), key=lambda item: item[1].last_access_ns)
        for entry_key, entry in ordered:
            if self._current_bytes <= target:
                break
            if int(entry.pin_count) > 0:
                continue
            self._entries.pop(entry_key, None)
            self._current_bytes = max(self._current_bytes - int(entry.nbytes), 0)
            if entry.shm_name:
                try:
                    shm = SharedMemory(name=entry.shm_name)
                except FileNotFoundError:
                    continue
                try:
                    shm.close()
                    shm.unlink()
                except FileNotFoundError:
                    pass

    def _load_rows(self, dataset: str, key: Tuple[Any, ...]) -> List[Dict[str, Any]]:
        store = DataStore(self._settings.db_path, read_only=self._read_only_store)
        from .backtest.intraday_options import IntradayOptionsBacktester

        backtester = IntradayOptionsBacktester(
            store=store,
            cutemarkets_provider=CuteMarketsProvider(self._settings),
            alpaca_data_provider=None,
        )
        backtester._persist_fetched_market_data = self._persist_fetched_market_data
        normalized_dataset = str(dataset or "").strip().lower()
        try:
            if normalized_dataset == "session_bars":
                ticker, day = key
                return list(backtester._load_session_bars(str(ticker), day))
            if normalized_dataset == "premarket_bars":
                ticker, day = key
                return list(backtester._load_premarket_bars(str(ticker), day))
            if normalized_dataset == "option_chain_snapshot":
                ticker, day = key
                return list(backtester._load_option_chain_snapshot(str(ticker), day))
            if normalized_dataset == "option_bars":
                symbol, day = key
                return list(backtester._load_option_bars(str(symbol), day))
            if normalized_dataset == "option_quotes":
                symbol, day = key
                return list(backtester._load_option_quotes(str(symbol), day))
            raise ValueError(f"Unsupported cache dataset: {dataset}")
        finally:
            store.close()

    def _store_rows_locked(self, dataset: str, key: Tuple[Any, ...], rows: Sequence[Mapping[str, Any]]) -> _SharedMemoryEntry:
        array = _rows_to_array(dataset, rows)
        nbytes = max(int(array.nbytes), _EMPTY_BYTES)
        shm = SharedMemory(create=True, size=nbytes)
        if array.nbytes > 0:
            shm.buf[: array.nbytes] = array.view(np.uint8)
        entry = _SharedMemoryEntry(
            dataset=str(dataset),
            key=tuple(key),
            shm_name=shm.name,
            row_count=len(array),
            nbytes=nbytes,
            last_access_ns=monotonic_ns(),
            pin_count=1,
        )
        shm.close()
        self._entries[(str(dataset), tuple(key))] = entry
        self._current_bytes += int(nbytes)
        self._peak_bytes = max(self._peak_bytes, self._current_bytes)
        self._evict_if_needed_locked()
        return entry

    def acquire_rows(self, dataset: str, key: Tuple[Any, ...]) -> Dict[str, Any]:
        normalized_dataset = str(dataset or "").strip().lower()
        if normalized_dataset not in _CACHE_DATASETS:
            raise ValueError(f"Unsupported cache dataset: {dataset}")
        entry_key = (normalized_dataset, tuple(key))
        with self._lock:
            cached = self._entries.get(entry_key)
            if cached is not None:
                cached.pin_count += 1
                cached.last_access_ns = monotonic_ns()
                self._dataset_hits[normalized_dataset] += 1
                return {
                    "dataset": normalized_dataset,
                    "key": tuple(key),
                    "shm_name": cached.shm_name,
                    "row_count": int(cached.row_count),
                }
            while entry_key in self._conditions:
                self._coalesced_load_count += 1
                self._conditions[entry_key].wait()
                cached = self._entries.get(entry_key)
                if cached is not None:
                    cached.pin_count += 1
                    cached.last_access_ns = monotonic_ns()
                    self._dataset_hits[normalized_dataset] += 1
                    return {
                        "dataset": normalized_dataset,
                        "key": tuple(key),
                        "shm_name": cached.shm_name,
                        "row_count": int(cached.row_count),
                    }
            self._conditions[entry_key] = Condition(self._lock)
            self._dataset_misses[normalized_dataset] += 1
        try:
            with self._loader_gate:
                rows = self._load_rows(normalized_dataset, tuple(key))
            with self._lock:
                entry = self._store_rows_locked(normalized_dataset, tuple(key), rows)
                condition = self._conditions.pop(entry_key, None)
                if condition is not None:
                    condition.notify_all()
                return {
                    "dataset": normalized_dataset,
                    "key": tuple(key),
                    "shm_name": entry.shm_name,
                    "row_count": int(entry.row_count),
                }
        except Exception:
            with self._lock:
                condition = self._conditions.pop(entry_key, None)
                if condition is not None:
                    condition.notify_all()
            raise

    def release_rows(self, dataset: str, key: Tuple[Any, ...]) -> None:
        entry_key = (str(dataset or "").strip().lower(), tuple(key))
        with self._lock:
            entry = self._entries.get(entry_key)
            if entry is not None and entry.pin_count > 0:
                entry.pin_count -= 1

    def stats_snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "mode": "host_shared",
                "dataset_hits": dict(self._dataset_hits),
                "dataset_misses": dict(self._dataset_misses),
                "coalesced_load_count": int(self._coalesced_load_count),
                "resident_bytes": int(self._current_bytes),
                "resident_bytes_peak": int(self._peak_bytes),
                "entry_count": len(self._entries),
            }

    def close(self) -> None:
        with self._lock:
            entries = list(self._entries.values())
            self._entries.clear()
            self._conditions.clear()
            self._current_bytes = 0
        for entry in entries:
            if entry.shm_name:
                try:
                    shm = SharedMemory(name=entry.shm_name)
                except FileNotFoundError:
                    continue
                try:
                    shm.close()
                    shm.unlink()
                except FileNotFoundError:
                    pass


class _SharedMarketDataProxyManager(SyncManager):
    pass


_SharedMarketDataProxyManager.register("SharedMarketDataCacheService", _SharedMarketDataCacheService)


@dataclass
class SharedMarketDataClient:
    proxy: BaseProxy
    mode: str = "host_shared"

    def get_or_load_rows(
        self,
        *,
        dataset: str,
        key: Tuple[Any, ...],
        loader: Callable[[], List[Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        del loader
        meta = self.proxy.acquire_rows(str(dataset), tuple(key))
        shm_name = str(meta.get("shm_name") or "")
        row_count = int(meta.get("row_count") or 0)
        try:
            if not shm_name or row_count <= 0:
                return []
            shm = SharedMemory(name=shm_name)
            try:
                dtype = _dtype_for_dataset(str(dataset))
                array = np.ndarray((row_count,), dtype=dtype, buffer=shm.buf)
                copied = array.copy()
            finally:
                shm.close()
            return _decode_array(str(dataset), copied)
        finally:
            self.proxy.release_rows(str(dataset), tuple(key))

    def stats_snapshot(self) -> Dict[str, Any]:
        return dict(self.proxy.stats_snapshot())

    def close(self) -> None:
        return None


@dataclass
class SharedMarketDataCacheManager:
    manager: _SharedMarketDataProxyManager
    proxy: BaseProxy

    @classmethod
    def start(
        cls,
        *,
        settings: Settings,
        read_only_store: bool,
        persist_fetched_market_data: bool,
        max_bytes: int,
        loader_workers: int,
    ) -> "SharedMarketDataCacheManager":
        manager = _SharedMarketDataProxyManager()
        manager.start()
        proxy = manager.SharedMarketDataCacheService(
            settings,
            read_only_store=bool(read_only_store),
            persist_fetched_market_data=bool(persist_fetched_market_data),
            max_bytes=max(int(max_bytes), 0),
            loader_workers=max(int(loader_workers), 1),
        )
        return cls(manager=manager, proxy=proxy)

    def build_client(self) -> SharedMarketDataClient:
        return SharedMarketDataClient(proxy=self.proxy)

    def close(self) -> None:
        try:
            self.proxy.close()
        except Exception:
            pass
        self.manager.shutdown()
