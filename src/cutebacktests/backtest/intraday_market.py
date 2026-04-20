from __future__ import annotations

import sys
from time import perf_counter

_fit = sys.modules.get("cutebacktests.backtest.intraday_options") or sys.modules.get("__main__")
if _fit is not None:
    for _name, _value in vars(_fit).items():
        if _name.startswith("__"):
            continue
        globals().setdefault(_name, _value)


def _clear_reused_runtime_state(self) -> None:
    self._contract_cache.clear()
    self._contract_selection_meta_cache.clear()
    self._contract_list_cache.clear()
    self._contract_universe_cache.clear()
    self._contract_candidate_cache.clear()
    self._contract_candidate_group_cache.clear()
    self._contract_fetch_preference_cache.clear()
    self._last_contract_selection_reason = ""
    self._last_contract_selection_meta = {}


def _market_data_cache_stats(self) -> Dict[str, Any]:
    backend = self.market_data_cache_backend
    if backend is None:
        return {
            "mode": "local",
            "dataset_hits": {},
            "dataset_misses": {},
            "coalesced_load_count": 0,
            "resident_bytes": 0,
            "resident_bytes_peak": 0,
        }
    try:
        return dict(backend.stats_snapshot())
    except Exception:
        return {"mode": str(getattr(backend, "mode", "local") or "local"), "error": "stats_unavailable"}


def _load_rows_with_market_backend(
    self,
    *,
    dataset: str,
    key: Tuple[Any, ...],
    loader: Callable[[], List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    backend = self.market_data_cache_backend
    if backend is None or str(getattr(backend, "mode", "local") or "local") == "local":
        return list(loader() or [])
    return list(backend.get_or_load_rows(dataset=dataset, key=tuple(key), loader=loader) or [])


def _load_option_chain_snapshot(self, ticker: str, day: date) -> List[Dict[str, Any]]:
    key = (str(ticker).strip().upper(), day)
    cached = self._option_chain_snapshot_cache.get(key)
    if cached is not None:
        return cached
    if self._use_runtime_for_option_chain_snapshot():
        runtime_rows = self._runtime_rows(f"option_chain_snapshot:{key[0]}:{day.isoformat()}")
        if runtime_rows is not None:
            self._set_bounded_cache_entry(
                self._option_chain_snapshot_cache,
                key,
                runtime_rows,
                max_entries=_MAX_OPTION_CHAIN_SNAPSHOT_CACHE_KEYS,
            )
            return runtime_rows
    rows = self._load_rows_with_market_backend(
        dataset="option_chain_snapshot",
        key=key,
        loader=lambda: self._load_option_chain_snapshot_uncached(ticker=key[0], day=day),
    )
    self._set_bounded_cache_entry(
        self._option_chain_snapshot_cache,
        key,
        rows,
        max_entries=_MAX_OPTION_CHAIN_SNAPSHOT_CACHE_KEYS,
    )
    return rows


def _load_option_chain_snapshot_index(
    self,
    *,
    ticker: str,
    day: date,
) -> _OptionChainSnapshotIndex:
    key = (str(ticker).strip().upper(), day)
    cached = self._option_chain_snapshot_index_cache.get(key)
    if cached is not None:
        return cached
    index = self._build_option_chain_snapshot_index(self._load_option_chain_snapshot(ticker=ticker, day=day))
    self._set_bounded_cache_entry(
        self._option_chain_snapshot_index_cache,
        key,
        index,
        max_entries=_MAX_OPTION_CHAIN_SNAPSHOT_CACHE_KEYS,
    )
    return index


def _load_session_bars(self, ticker: str, day: date) -> List[Dict[str, Any]]:
    ticker_key = str(ticker).upper()
    cache_key = (ticker_key, day)
    if cache_key in self._session_bar_cache:
        return list(self._session_bar_cache.get(cache_key, []))
    rows = self._load_rows_with_market_backend(
        dataset="session_bars",
        key=cache_key,
        loader=lambda: list(self._load_session_bars_range_local(ticker=ticker_key, start_day=day, end_day=day).get(day, [])),
    )
    if cache_key in self._session_bar_cache:
        return list(self._session_bar_cache.get(cache_key, []))
    if rows:
        self._session_bar_cache[cache_key] = rows
    return list(rows)


def _load_session_bars_range(
    self,
    *,
    ticker: str,
    start_day: date,
    end_day: date,
) -> Dict[date, List[Dict[str, Any]]]:
    backend = self.market_data_cache_backend
    if backend is not None and str(getattr(backend, "mode", "local") or "local") != "local":
        return {day: list(self._load_session_bars(ticker=ticker, day=day)) for day in _iter_dates(start_day, end_day)}
    return self._load_session_bars_range_local(ticker=ticker, start_day=start_day, end_day=end_day)


def _prime_session_bar_cache(
    self,
    *,
    ticker: str,
    start_day: date,
    end_day: date,
) -> None:
    if end_day < start_day:
        return

    start_dt = datetime.combine(start_day, time(0, 0))
    end_dt = datetime.combine(end_day + timedelta(days=1), time(0, 0))
    coverage_getter = getattr(self.store, "has_stock_bar_coverage", None)
    coverage_setter = getattr(self.store, "set_stock_bar_coverage", None)
    duckdb_seconds = 0.0
    duckdb_calls = 0
    if callable(coverage_getter):
        started_at = perf_counter()
        has_coverage = bool(
            coverage_getter(
                ticker=ticker,
                timeframe="1Min",
                start=start_dt,
                end=end_dt,
            )
        )
        duckdb_seconds += perf_counter() - started_at
        duckdb_calls += 1
    else:
        has_coverage = False

    range_getter = getattr(self.store, "get_stock_bars_range", None)
    if callable(range_getter):
        started_at = perf_counter()
        rows = range_getter(
            ticker=ticker,
            start=start_dt,
            end=end_dt,
        )
        duckdb_seconds += perf_counter() - started_at
        duckdb_calls += 1
    else:
        started_at = perf_counter()
        rows = self.store.get_stock_bars(ticker=ticker, start=start_dt, end=end_dt)
        duckdb_seconds += perf_counter() - started_at
        duckdb_calls += 1

    grouped_existing = self._session_rows_by_day(rows=rows, start_day=start_day, end_day=end_day)
    confirmed_empty_days: set[date] = set()
    full_range_coverage_confirmed = bool(has_coverage)
    if not has_coverage:
        missing_days = [
            day
            for day in _iter_dates(start_day, end_day)
            if day.weekday() < 5 and day not in grouped_existing
        ]
        fetched_rows: List[Dict[str, Any]] = []
        coverage_complete = False
        if missing_days or not rows:
            provider_started_at = perf_counter()
            fetched_rows, coverage_complete = self._fetch_stock_bar_range_from_providers(
                ticker=ticker,
                start_day=min(missing_days) if missing_days else start_day,
                end_day=max(missing_days) if missing_days else end_day,
            )
            provider_seconds = perf_counter() - provider_started_at
            if provider_seconds > 0.0:
                self._record_option_market_data_io(
                    dataset="session_bars",
                    total_seconds=provider_seconds,
                    provider_seconds=provider_seconds,
                    provider_calls=1,
                )
            if fetched_rows:
                if self._persist_fetched_market_data:
                    self.store.insert_stock_bars(fetched_rows)
                rows = self._merge_rows_by_ts(rows, fetched_rows)
        grouped_existing = self._session_rows_by_day(rows=rows, start_day=start_day, end_day=end_day)
        unresolved_weekdays = [
            day
            for day in _iter_dates(start_day, end_day)
            if day.weekday() < 5 and day not in grouped_existing
        ]
        if unresolved_weekdays:
            retry_rows: List[Dict[str, Any]] = []
            for missing_day in unresolved_weekdays:
                day_rows, day_complete = self._fetch_stock_bar_range_from_providers(
                    ticker=ticker,
                    start_day=missing_day,
                    end_day=missing_day,
                )
                if day_rows:
                    retry_rows.extend(day_rows)
                elif day_complete:
                    confirmed_empty_days.add(missing_day)
                if self._persist_fetched_market_data and callable(coverage_setter) and day_complete:
                    coverage_setter(
                        ticker=ticker,
                        timeframe="1Min",
                        start=datetime.combine(missing_day, time(0, 0)),
                        end=datetime.combine(missing_day + timedelta(days=1), time(0, 0)),
                    )
            if retry_rows:
                if self._persist_fetched_market_data:
                    self.store.insert_stock_bars(retry_rows)
                rows = self._merge_rows_by_ts(rows, retry_rows)
                grouped_existing = self._session_rows_by_day(rows=rows, start_day=start_day, end_day=end_day)
                unresolved_weekdays = [
                    day
                    for day in _iter_dates(start_day, end_day)
                    if day.weekday() < 5 and day not in grouped_existing
                ]
        if self._persist_fetched_market_data and callable(coverage_setter):
            if coverage_complete and not unresolved_weekdays:
                coverage_setter(
                    ticker=ticker,
                    timeframe="1Min",
                    start=start_dt,
                    end=end_dt,
                )
                full_range_coverage_confirmed = True
            else:
                for resolved_day in sorted(grouped_existing):
                    coverage_setter(
                        ticker=ticker,
                        timeframe="1Min",
                        start=datetime.combine(resolved_day, time(0, 0)),
                        end=datetime.combine(resolved_day + timedelta(days=1), time(0, 0)),
                    )
    if duckdb_seconds > 0.0:
        self._record_option_market_data_io(
            dataset="session_bars",
            total_seconds=duckdb_seconds,
            duckdb_seconds=duckdb_seconds,
            duckdb_calls=duckdb_calls,
        )

    grouped = self._session_rows_by_day(rows=rows, start_day=start_day, end_day=end_day)
    for day in _iter_dates(start_day, end_day):
        day_rows = grouped.get(day, [])
        if day_rows:
            self._session_bar_cache[(ticker, day)] = day_rows
            continue
        if day.weekday() >= 5 or full_range_coverage_confirmed or day in confirmed_empty_days:
            self._session_bar_cache[(ticker, day)] = []
            continue
        self._session_bar_cache.pop((ticker, day), None)


def _load_premarket_bars(self, ticker: str, day: date) -> List[Dict[str, Any]]:
    ticker_key = str(ticker).upper()
    cache_key = (ticker_key, day)
    if cache_key in self._premarket_bar_cache:
        return list(self._premarket_bar_cache[cache_key])
    rows = self._load_rows_with_market_backend(
        dataset="premarket_bars",
        key=cache_key,
        loader=lambda: self._load_premarket_bars_uncached(ticker=ticker_key, day=day),
    )
    self._premarket_bar_cache[cache_key] = rows
    return list(rows)


def _load_option_bars(self, symbol: str, day: date) -> List[Dict[str, Any]]:
    cache_key = (symbol, day)
    if cache_key in self._option_bar_cache:
        return self._option_bar_cache[cache_key]
    if self._use_runtime_for_option_bars():
        runtime_rows = self._runtime_rows(f"option_bars:{symbol}:{day.isoformat()}")
        if runtime_rows is not None:
            self._set_bounded_cache_entry(
                self._option_bar_cache,
                cache_key,
                runtime_rows,
                max_entries=_MAX_OPTION_BAR_CACHE_KEYS,
            )
            return runtime_rows
    rows = self._load_rows_with_market_backend(
        dataset="option_bars",
        key=cache_key,
        loader=lambda: self._load_option_bars_uncached(symbol=symbol, day=day),
    )
    self._set_bounded_cache_entry(
        self._option_bar_cache,
        cache_key,
        rows,
        max_entries=_MAX_OPTION_BAR_CACHE_KEYS,
    )
    return rows


def _load_option_quotes(self, symbol: str, day: date) -> List[Dict[str, Any]]:
    if self._historical_option_quotes_supported is False and self.cutemarkets_provider is None:
        return []
    cache_key = (symbol, day)
    if cache_key in self._option_quote_cache:
        return self._option_quote_cache[cache_key]
    if self._use_runtime_for_option_quotes():
        runtime_rows = self._runtime_rows(f"option_quotes:{symbol}:{day.isoformat()}")
        if runtime_rows is not None:
            self._invalidate_option_quote_derived_caches(symbol=symbol, day=day)
            self._set_bounded_cache_entry(
                self._option_quote_cache,
                cache_key,
                runtime_rows,
                max_entries=_MAX_OPTION_QUOTE_CACHE_KEYS,
            )
            return runtime_rows
    rows = self._load_rows_with_market_backend(
        dataset="option_quotes",
        key=cache_key,
        loader=lambda: self._load_option_quotes_uncached(symbol=symbol, day=day),
    )
    self._invalidate_option_quote_derived_caches(symbol=symbol, day=day)
    self._set_bounded_cache_entry(
        self._option_quote_cache,
        cache_key,
        rows,
        max_entries=_MAX_OPTION_QUOTE_CACHE_KEYS,
    )
    return rows
