from __future__ import annotations

import sys

_fit = sys.modules.get("cutebacktests.backtest.intraday_options") or sys.modules.get("__main__")
if _fit is not None:
    for _name, _value in vars(_fit).items():
        if _name.startswith("__"):
            continue
        globals().setdefault(_name, _value)


def _select_contract(
    self,
    ticker: str,
    day: date,
    direction: int,
    entry_underlying: float,
    config: IntradayOptionsBacktestConfig,
    selection_ts: Optional[datetime] = None,
) -> Optional[Dict[str, Any]]:
    self._last_contract_selection_reason = ""
    self._last_contract_selection_meta = {}
    selection_rejection_counts: Counter[str] = Counter()
    open_interest_data_unavailable = False

    def _record_selection_rejection(reason: str, amount: int = 1) -> None:
        key = str(reason or "unknown")
        selection_rejection_counts[key] += int(amount)

    def _attempt_reason(prefix: str, status: str, as_of_mode: str, *, cached: bool = False) -> str:
        status_key = str(status or "unknown").strip().lower().replace("-", "_")
        mode_key = str(as_of_mode or "unknown").strip().lower().replace("-", "_")
        suffix = "_cached" if cached else ""
        return f"{prefix}_status_{status_key}_mode_{mode_key}{suffix}"

    structure_mode = str(config.option_structure_mode or "single_leg").strip().lower()
    if structure_mode == "vertical_credit":
        option_type = "put" if direction > 0 else "call"
    else:
        option_type = "call" if direction > 0 else "put"
    contract_status = str(config.option_contract_status or "inactive").strip().lower()
    use_open_interest = bool(config.option_use_contract_open_interest)
    min_open_interest = int(config.option_min_open_interest) if use_open_interest else 0
    if bool(config.option_structure_filter_enabled):
        min_open_interest = max(min_open_interest, int(config.option_structure_min_open_interest))
    audit_relax_daily_contract_selection = bool(
        str(config.signal_cadence or "intraday").strip().lower() == "daily_eod"
        and bool(config.audit_relax_daily_contract_selection)
    )
    entry_underlying_cents = int(round(max(float(entry_underlying), 0.0) * 100.0))
    raw_cache_key = (
        ticker,
        day.isoformat(),
        option_type,
        contract_status,
        config.option_min_dte,
        config.option_max_dte,
    )
    cache_key = (
        ticker,
        day.isoformat(),
        direction,
        contract_status,
        config.option_min_dte,
        config.option_target_dte,
        config.option_max_dte,
        min_open_interest,
        use_open_interest,
        entry_underlying_cents,
        bool(config.option_selection_use_quote_spread),
        int(config.option_selection_quote_top_n),
        round(float(config.option_selection_spread_weight), 6),
        round(float(config.option_selection_max_quote_spread_pct), 6),
        round(float(config.option_selection_max_quote_spread_abs), 6),
        round(float(config.option_selection_min_quote_ask), 6),
        round(float(config.option_selection_spread_to_ask_weight), 6),
        round(float(config.option_selection_max_spread_to_ask_ratio), 6),
        round(float(config.option_selection_intrinsic_weight), 6),
        round(float(config.option_selection_min_intrinsic_share), 6),
        round(float(config.option_selection_delta_weight), 6),
        round(float(config.option_selection_target_abs_delta), 6),
        round(float(config.option_selection_min_abs_delta), 6),
        round(float(config.option_selection_max_abs_delta), 6),
        str(getattr(config, "option_selection_delta_fallback_mode", "strict") or "strict").strip().lower(),
        int(getattr(config, "option_selection_local_itm_steps", 0) or 0),
        int(getattr(config, "option_selection_local_otm_steps", 0) or 0),
        round(float(getattr(config, "option_selection_entry_bar_volume_weight", 0.0) or 0.0), 6),
        self._normalize_selection_quote_mode(getattr(config, "option_selection_quote_mode", "legacy")),
        bool(getattr(config, "option_selection_quote_fallback_last", True)),
        _normalize_option_chain_snapshot_enrichment_mode(
            getattr(config, "option_chain_snapshot_enrichment_mode", "full")
        ),
        round(float(config.option_min_expected_move_to_extrinsic_ratio), 6),
        round(float(config.option_min_expected_move_to_spread_ratio), 6),
        round(float(config.option_min_expected_move_to_debit_ratio), 6),
        structure_mode,
        int(config.option_vertical_short_leg_steps),
        int(config.option_vertical_fallback_short_leg_steps),
        round(float(config.option_vertical_max_debit_to_width_ratio), 6),
        round(float(config.option_vertical_min_short_bid), 6),
        round(float(config.option_vertical_max_combined_spread_to_debit_ratio), 6),
        int(config.option_vertical_credit_long_leg_steps),
        int(config.option_vertical_credit_fallback_long_leg_steps),
        round(float(config.option_vertical_min_credit_to_width_ratio), 6),
        round(float(config.option_vertical_max_credit_to_width_ratio), 6),
        round(float(config.option_vertical_max_combined_spread_to_credit_ratio), 6),
        round(float(config.option_credit_min_short_bid), 6),
        round(float(config.option_credit_min_short_strike_buffer_pct), 6),
        round(float(config.option_credit_min_expected_move_buffer_ratio), 6),
        round(float(config.option_credit_min_entry_credit), 6),
        round(float(config.option_credit_take_profit_capture_pct), 6),
        round(float(config.option_credit_stop_loss_multiple), 6),
        bool(audit_relax_daily_contract_selection),
        selection_ts.isoformat()
        if (
            bool(config.option_selection_use_quote_spread)
            or float(getattr(config, "option_selection_entry_bar_volume_weight", 0.0) or 0.0) > 0.0
        ) and isinstance(selection_ts, datetime)
        else "",
    )
    if cache_key in self._contract_cache:
        cached_meta = dict(self._contract_selection_meta_cache.get(cache_key) or {})
        self._last_contract_selection_meta = cached_meta
        if self._contract_cache[cache_key] is None:
            self._last_contract_selection_reason = str(
                cached_meta.get("final_reason") or "contract_not_found_cached"
            )
        return self._contract_cache[cache_key]

    min_expiration_day = day + timedelta(days=max(int(config.option_min_dte), 0))
    max_expiration_day = day + timedelta(days=max(int(config.option_max_dte), int(config.option_min_dte)))

    def _restrict_contracts_to_requested_dte_window(
        contract_rows: Sequence[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        eligible: List[Dict[str, Any]] = []
        for contract in contract_rows:
            if not isinstance(contract, dict):
                continue
            expiry = parse_datetime(contract.get("expiration_date"))
            if expiry is None:
                continue
            expiry_day = expiry.date()
            if expiry_day < min_expiration_day or expiry_day > max_expiration_day:
                continue
            eligible.append(dict(contract))
        return eligible

    if self.cutemarkets_provider is None and self.alpaca_data_provider is None:
        self._contract_cache[cache_key] = None
        self._contract_selection_meta_cache[cache_key] = {
            "selected": False,
            "pool_contract_count": 0,
            "had_filtered_candidates": False,
            "had_fetch_error": False,
            "had_successful_attempt": False,
            "raw_list_cached": False,
            "used_cached_contract_source": False,
            "rejection_counts": {"no_option_contract_provider": 1},
            "final_reason": "no_option_contract_provider",
        }
        self._last_contract_selection_reason = "no_option_contract_provider"
        self._last_contract_selection_meta = dict(self._contract_selection_meta_cache.get(cache_key) or {})
        return None

    persistent_lookup_cache_allowed = (
        bool(getattr(config, "persist_option_contract_lookup_cache", True))
        and not bool(getattr(self.store, "read_only", False))
    )
    self._persist_option_contract_lookup_cache = persistent_lookup_cache_allowed

    def _load_contract_pool(allow_persistent_cache: bool) -> Tuple[
        List[Dict[str, Any]],
        bool,
        bool,
        bool,
        Tuple[Any, ...],
        bool,
    ]:
        had_fetch_error = False
        had_successful_attempt = False
        used_cached_contract_source = False
        enrichment_mode = _normalize_option_chain_snapshot_enrichment_mode(
            getattr(config, "option_chain_snapshot_enrichment_mode", "full")
        )
        contracts, raw_list_cached = self._get_cached_contract_list_for_day(
            raw_cache_key=raw_cache_key,
            ticker=ticker,
            day=day,
            option_type=option_type,
            requested_status=contract_status,
            option_min_dte=int(config.option_min_dte),
            option_max_dte=int(config.option_max_dte),
            allow_persistent_read=bool(allow_persistent_cache and persistent_lookup_cache_allowed),
        )
        if contracts:
            contracts = _restrict_contracts_to_requested_dte_window(contracts)
        if raw_list_cached and not contracts:
            # Old persisted day caches may contain only out-of-window expiries.
            # Force a refetch so 0DTE selectors can continue to later variants.
            raw_list_cached = False
        if raw_list_cached and not contracts and int(config.option_max_dte) <= 0:
            # Empty same-day caches are too risky to trust because transient
            # provider empties can poison later 0DTE selections.
            raw_list_cached = False
        candidate_cache_key: Tuple[Any, ...] = ("day", enrichment_mode) + raw_cache_key
        used_cached_contract_source = bool(raw_list_cached)
        if not raw_list_cached:
            contracts = self._contract_list_from_chain_snapshot(
                ticker=ticker,
                day=day,
                option_type=option_type,
                option_min_dte=int(config.option_min_dte),
                option_max_dte=int(config.option_max_dte),
                requested_status=contract_status,
            )
            if contracts:
                candidate_cache_key = ("snapshot_day", enrichment_mode) + raw_cache_key
                used_cached_contract_source = True
            if self.cutemarkets_provider is not None:
                if not contracts:
                    try:
                        raw_contracts = self._fetch_cutemarkets_contract_list(
                            ticker=ticker,
                            day=day,
                            option_type=option_type,
                            option_min_dte=int(config.option_min_dte),
                            option_max_dte=int(config.option_max_dte),
                        )
                    except Exception:
                        had_fetch_error = True
                        _record_selection_rejection("contract_fetch_error_cutemarkets_snapshot")
                        raw_contracts = []
                    else:
                        had_successful_attempt = True
                    raw_fetch_empty = not raw_contracts
                    if raw_fetch_empty:
                        _record_selection_rejection("contract_fetch_empty_cutemarkets_snapshot")
                    candidate_cache_key = ("cutemarkets_day", enrichment_mode) + raw_cache_key
                    contracts = self._enrich_contracts_with_chain_snapshot(
                        ticker=ticker,
                        day=day,
                        option_type=option_type,
                        contracts=raw_contracts,
                        enrichment_mode=enrichment_mode,
                    )
                    contracts = _restrict_contracts_to_requested_dte_window(contracts)
                    if not contracts and not raw_fetch_empty:
                        _record_selection_rejection("contract_fetch_empty_cutemarkets_snapshot")
            else:
                preferred_attempt = self._get_contract_fetch_preference(
                    ticker=ticker,
                    option_type=option_type,
                    requested_status=contract_status,
                    option_min_dte=int(config.option_min_dte),
                    option_max_dte=int(config.option_max_dte),
                    allow_persistent_read=bool(allow_persistent_cache and persistent_lookup_cache_allowed),
                )
                expiration_date_gte = (day + timedelta(days=max(config.option_min_dte, 0))).isoformat()
                expiration_date_lte = (
                    day + timedelta(days=max(config.option_max_dte, config.option_min_dte))
                ).isoformat()

                for attempt_status, attempt_as_of_mode in self._contract_fetch_attempts(
                    requested_status=contract_status,
                    preferred=preferred_attempt,
                ):
                    if attempt_as_of_mode == "none":
                        universe_key = self._contract_universe_key(
                            ticker=ticker,
                            option_type=option_type,
                            status=attempt_status,
                            option_min_dte=int(config.option_min_dte),
                            option_max_dte=int(config.option_max_dte),
                        )
                        universe_contracts, universe_cached = self._get_cached_contract_universe(
                            universe_key=universe_key,
                            ticker=ticker,
                            option_type=option_type,
                            status=attempt_status,
                            option_min_dte=int(config.option_min_dte),
                            option_max_dte=int(config.option_max_dte),
                            allow_persistent_read=bool(allow_persistent_cache and persistent_lookup_cache_allowed),
                        )
                        if universe_cached:
                            filtered_universe_contracts = (
                                _restrict_contracts_to_requested_dte_window(universe_contracts)
                                if universe_contracts
                                else []
                            )
                            if not filtered_universe_contracts and int(config.option_max_dte) <= 0:
                                universe_cached = False
                            else:
                                used_cached_contract_source = True
                                contracts = list(filtered_universe_contracts)
                                candidate_cache_key = ("universe_day", enrichment_mode, day.isoformat()) + universe_key
                                if contracts:
                                    self._set_contract_fetch_preference(
                                        ticker=ticker,
                                        option_type=option_type,
                                        requested_status=contract_status,
                                        option_min_dte=int(config.option_min_dte),
                                        option_max_dte=int(config.option_max_dte),
                                        preferred_status=attempt_status,
                                        preferred_as_of_mode=attempt_as_of_mode,
                                    )
                                    break
                                _record_selection_rejection(
                                    _attempt_reason(
                                        "contract_fetch_empty",
                                        attempt_status,
                                        attempt_as_of_mode,
                                        cached=True,
                                    )
                                )
                                continue
                    attempt_as_of = day.isoformat() if attempt_as_of_mode == "day" else None
                    try:
                        fetched_contracts = self.alpaca_data_provider.fetch_option_contracts(
                            underlying_symbol=ticker,
                            expiration_date_gte=expiration_date_gte,
                            expiration_date_lte=expiration_date_lte,
                            option_type=option_type,
                            status=attempt_status,
                            as_of=attempt_as_of,
                            limit=1000,
                        )
                    except Exception:
                        had_fetch_error = True
                        _record_selection_rejection(
                            _attempt_reason("contract_fetch_error", attempt_status, attempt_as_of_mode)
                        )
                        continue
                    had_successful_attempt = True
                    raw_contracts = list(fetched_contracts or [])
                    raw_fetch_empty = not raw_contracts
                    if raw_fetch_empty:
                        _record_selection_rejection(
                            _attempt_reason("contract_fetch_empty", attempt_status, attempt_as_of_mode)
                        )
                    if attempt_as_of_mode == "none":
                        universe_key = self._contract_universe_key(
                            ticker=ticker,
                            option_type=option_type,
                            status=attempt_status,
                            option_min_dte=int(config.option_min_dte),
                            option_max_dte=int(config.option_max_dte),
                        )
                        if raw_contracts or int(config.option_max_dte) > 0:
                            self._set_cached_contract_universe(
                                universe_key=universe_key,
                                ticker=ticker,
                                option_type=option_type,
                                status=attempt_status,
                                option_min_dte=int(config.option_min_dte),
                                option_max_dte=int(config.option_max_dte),
                                contracts=raw_contracts,
                            )
                        candidate_cache_key = ("universe_day", enrichment_mode, day.isoformat()) + universe_key
                    else:
                        candidate_cache_key = ("day", enrichment_mode) + raw_cache_key
                    contracts = self._enrich_contracts_with_chain_snapshot(
                        ticker=ticker,
                        day=day,
                        option_type=option_type,
                        contracts=raw_contracts,
                        enrichment_mode=enrichment_mode,
                    )
                    contracts = _restrict_contracts_to_requested_dte_window(contracts)
                    if not contracts and not raw_fetch_empty:
                        _record_selection_rejection(
                            _attempt_reason("contract_fetch_empty", attempt_status, attempt_as_of_mode)
                        )
                    if contracts:
                        self._set_contract_fetch_preference(
                            ticker=ticker,
                            option_type=option_type,
                            requested_status=contract_status,
                            option_min_dte=int(config.option_min_dte),
                            option_max_dte=int(config.option_max_dte),
                            preferred_status=attempt_status,
                            preferred_as_of_mode=attempt_as_of_mode,
                        )
                        break

            if contracts or had_successful_attempt:
                if contracts or (not had_fetch_error and int(config.option_max_dte) > 0):
                    self._set_cached_contract_list_for_day(
                        raw_cache_key=raw_cache_key,
                        ticker=ticker,
                        day=day,
                        option_type=option_type,
                        requested_status=contract_status,
                        option_min_dte=int(config.option_min_dte),
                        option_max_dte=int(config.option_max_dte),
                        contracts=contracts,
                    )
        else:
            contracts = self._enrich_contracts_with_chain_snapshot(
                ticker=ticker,
                day=day,
                option_type=option_type,
                contracts=contracts,
                enrichment_mode=enrichment_mode,
            )
        return (
            contracts,
            raw_list_cached,
            had_fetch_error,
            had_successful_attempt,
            candidate_cache_key,
            used_cached_contract_source,
        )

    def _rank_contracts(
        contracts: Sequence[Dict[str, Any]],
        candidate_cache_key: Tuple[Any, ...],
    ) -> Tuple[Optional[Dict[str, Any]], bool, List[Dict[str, Any]]]:
        nonlocal open_interest_data_unavailable
        ranked: List[Tuple[float, int, float, float, _ContractCandidate]] = []
        had_filtered_candidates = False
        grouped_candidates = self._group_contract_candidates_for_cache_key(
            cache_key=candidate_cache_key,
            contracts=contracts,
        )
        candidates = list(
            self._contract_candidates_for_cache_key(
                cache_key=candidate_cache_key,
                contracts=contracts,
            )
        )
        local_itm_steps = max(int(getattr(config, "option_selection_local_itm_steps", 0) or 0), 0)
        local_otm_steps = max(int(getattr(config, "option_selection_local_otm_steps", 0) or 0), 0)
        use_local_strike_band = bool(local_itm_steps > 0 or local_otm_steps > 0)
        if use_local_strike_band:
            restricted_candidates = self._restrict_candidates_to_local_strike_band(
                grouped_candidates=grouped_candidates,
                direction=direction,
                entry_underlying=entry_underlying,
                itm_steps=local_itm_steps,
                otm_steps=local_otm_steps,
            )
            if restricted_candidates:
                candidates = restricted_candidates
        local_strike_band_size = len(candidates)
        min_open_interest_floor = max(min_open_interest, 0)
        open_interest_data_unavailable = bool(
            min_open_interest_floor > 0
            and str(config.option_mode or "").strip().lower() == "historical"
            and str(config.option_contract_status or "").strip().lower() == "inactive"
            and candidates
            and not any(int(candidate.open_interest or 0) > 0 for candidate in candidates)
        )
        if open_interest_data_unavailable:
            _record_selection_rejection("contract_open_interest_data_unavailable")
        for candidate in candidates:
            dte = (candidate.expiration_day - day).days
            if dte < config.option_min_dte or dte > config.option_max_dte:
                had_filtered_candidates = True
                _record_selection_rejection("contract_dte_mismatch")
                continue

            moneyness = abs(candidate.strike - entry_underlying) / max(entry_underlying, 1.0)
            dte_gap = abs(dte - config.option_target_dte)
            open_interest = candidate.open_interest
            if open_interest < min_open_interest_floor:
                _record_selection_rejection("contract_open_interest_below_min")
                if audit_relax_daily_contract_selection or open_interest_data_unavailable:
                    _record_selection_rejection("contract_open_interest_below_min_bypassed")
                else:
                    had_filtered_candidates = True
                    continue
            oi_bonus = (
                min(open_interest / 5000.0, 1.0) * 0.05
                if use_open_interest and open_interest > 0
                else 0.0
            )
            score = float(dte_gap) + (moneyness * 20.0) - oi_bonus
            ranked.append((score, dte, moneyness, oi_bonus, candidate))
        ranked.sort(key=lambda item: item[0])
        if not ranked:
            return None, had_filtered_candidates, []
        spread_mode = bool(config.option_selection_use_quote_spread)
        top_n = max(int(config.option_selection_quote_top_n), 1)
        spread_weight = max(float(config.option_selection_spread_weight), 0.0)
        max_quote_spread_pct = max(float(config.option_selection_max_quote_spread_pct), 0.0)
        max_quote_spread_abs = max(float(config.option_selection_max_quote_spread_abs), 0.0)
        min_quote_ask = max(float(config.option_selection_min_quote_ask), 0.0)
        spread_to_ask_weight = max(float(config.option_selection_spread_to_ask_weight), 0.0)
        max_spread_to_ask_ratio = max(float(config.option_selection_max_spread_to_ask_ratio), 0.0)
        intrinsic_weight = max(float(config.option_selection_intrinsic_weight), 0.0)
        min_intrinsic_share = max(float(config.option_selection_min_intrinsic_share), 0.0)
        delta_weight = max(float(config.option_selection_delta_weight), 0.0)
        target_abs_delta = max(float(config.option_selection_target_abs_delta), 0.0)
        min_abs_delta = max(float(config.option_selection_min_abs_delta), 0.0)
        max_abs_delta = min(max(float(config.option_selection_max_abs_delta), 0.0), 1.0)
        delta_fallback_mode = str(getattr(config, "option_selection_delta_fallback_mode", "strict") or "strict")
        delta_fallback_mode = delta_fallback_mode.strip().lower() or "strict"
        selection_quote_mode = self._normalize_selection_quote_mode(
            getattr(config, "option_selection_quote_mode", "legacy")
        )
        quote_fallback_last = bool(getattr(config, "option_selection_quote_fallback_last", True))
        use_nearest_strike_delta_fallback = delta_fallback_mode == "nearest_strike"
        entry_bar_volume_weight = max(
            float(getattr(config, "option_selection_entry_bar_volume_weight", 0.0) or 0.0),
            0.0,
        )
        multi_candidate_mode = bool(spread_mode or use_local_strike_band or entry_bar_volume_weight > 0.0)
        if use_local_strike_band:
            top_n = max(top_n, 1 + local_itm_steps + local_otm_steps)
        shortlisted = ranked[:top_n] if multi_candidate_mode else ranked[:1]
        scored_candidates: List[Dict[str, Any]] = []
        selection_ts_effective = (
            selection_ts
            if isinstance(selection_ts, datetime)
            else datetime.combine(day, time(9, 35))
        )
        for base_score, dte, moneyness, oi_bonus, candidate in shortlisted:
            score = float(base_score)
            quote_spread_pct: Optional[float] = None
            quote_spread_abs: Optional[float] = None
            quote_spread_to_ask_ratio: Optional[float] = None
            intrinsic_value: Optional[float] = None
            intrinsic_share: Optional[float] = None
            extrinsic_value: Optional[float] = None
            abs_delta: Optional[float] = None
            delta_missing_relaxed = False
            delta_fallback_used = False
            quote_used = False
            entry_bar_volume: Optional[int] = None
            delta_value = _safe_float(candidate.contract.get("delta"))
            if delta_value is not None:
                abs_delta = abs(float(delta_value))
            if abs_delta is None and (
                (
                    audit_relax_daily_contract_selection
                    and (min_abs_delta > 0.0 or (max_abs_delta > 0.0 and max_abs_delta < 1.0))
                )
                or use_nearest_strike_delta_fallback
            ):
                _record_selection_rejection("contract_delta_missing")
                if use_nearest_strike_delta_fallback:
                    _record_selection_rejection("contract_delta_missing_nearest_strike_fallback")
                    delta_fallback_used = True
                    if target_abs_delta > 0.0:
                        # For 0DTE ATM proxy selection, missing Greeks should not
                        # keep the candidate in an indeterminate delta state once
                        # we have already decided to use nearest-strike fallback.
                        abs_delta = float(target_abs_delta)
                else:
                    _record_selection_rejection("contract_delta_missing_bypassed")
                delta_missing_relaxed = True
            if structure_mode == "vertical_credit":
                strike_px = float(candidate.strike)
                is_otm_short = strike_px < entry_underlying if direction > 0 else strike_px > entry_underlying
                if not is_otm_short:
                    had_filtered_candidates = True
                    _record_selection_rejection("vertical_credit_short_not_otm")
                    continue
            if min_abs_delta > 0.0:
                if abs_delta is None:
                    if not delta_missing_relaxed:
                        had_filtered_candidates = True
                        _record_selection_rejection("contract_delta_missing")
                        continue
                elif abs_delta < min_abs_delta:
                    had_filtered_candidates = True
                    _record_selection_rejection("contract_delta_out_of_range")
                    continue
            if max_abs_delta > 0.0 and max_abs_delta < 1.0:
                if abs_delta is None:
                    if not delta_missing_relaxed:
                        had_filtered_candidates = True
                        _record_selection_rejection("contract_delta_missing")
                        continue
                elif abs_delta > max_abs_delta:
                    had_filtered_candidates = True
                    _record_selection_rejection("contract_delta_out_of_range")
                    continue
            needs_quote_data = spread_mode or structure_mode == "vertical_credit"
            if needs_quote_data:
                symbol = str(candidate.contract.get("symbol") or "").strip()
                if not symbol:
                    had_filtered_candidates = True
                    _record_selection_rejection("contract_symbol_missing")
                    continue
                quote, _quote_source = self._selection_quote_for_symbol(
                    symbol=symbol,
                    day=day,
                    selection_ts=selection_ts_effective,
                    fallback_last=quote_fallback_last,
                    selection_quote_mode=selection_quote_mode,
                )
                if quote is None:
                    had_filtered_candidates = True
                    _record_selection_rejection("contract_quote_missing")
                    continue
                bid = _safe_float(quote.get("bid"))
                ask = _safe_float(quote.get("ask"))
                if bid is None or ask is None or bid <= 0 or ask <= bid:
                    had_filtered_candidates = True
                    _record_selection_rejection("contract_quote_invalid")
                    continue
                if ask < min_quote_ask:
                    had_filtered_candidates = True
                    _record_selection_rejection("contract_quote_ask_below_min")
                    continue
                quote_used = True
                quote_spread_abs = max(ask - bid, 0.0)
                if max_quote_spread_abs > 0.0 and quote_spread_abs > max_quote_spread_abs:
                    had_filtered_candidates = True
                    _record_selection_rejection("contract_quote_spread_abs")
                    continue
                quote_spread_to_ask_ratio = quote_spread_abs / ask
                if max_spread_to_ask_ratio > 0.0 and quote_spread_to_ask_ratio > max_spread_to_ask_ratio:
                    had_filtered_candidates = True
                    _record_selection_rejection("contract_quote_spread_to_ask_ratio")
                    continue
                mid = (ask + bid) / 2.0
                if mid <= 0:
                    had_filtered_candidates = True
                    _record_selection_rejection("contract_quote_invalid")
                    continue
                quote_spread_pct = quote_spread_abs / mid
                if quote_spread_pct > max_quote_spread_pct:
                    had_filtered_candidates = True
                    _record_selection_rejection("contract_quote_spread_pct")
                    continue
                intrinsic_value = _option_intrinsic_value(
                    option_type=option_type,
                    underlying_price=entry_underlying,
                    strike=float(candidate.strike),
                )
                intrinsic_share = min(max(intrinsic_value / ask, 0.0), 1.0)
                extrinsic_value = max(ask - intrinsic_value, 0.0)
                if min_intrinsic_share > 0.0 and intrinsic_share < min_intrinsic_share:
                    had_filtered_candidates = True
                    _record_selection_rejection("contract_intrinsic_share")
                    continue
                if structure_mode == "vertical_credit":
                    if bid < max(float(config.option_credit_min_short_bid), 0.0):
                        self._bump_option_rejection("vertical_credit_short_leg_bid_too_low")
                        had_filtered_candidates = True
                        continue
                    short_buffer_pct = abs(entry_underlying - float(candidate.strike)) / max(entry_underlying, 1.0)
                    if short_buffer_pct < max(float(config.option_credit_min_short_strike_buffer_pct), 0.0):
                        self._bump_option_rejection("vertical_credit_buffer_too_small")
                        had_filtered_candidates = True
                        continue
                score += quote_spread_pct * spread_weight
                score += quote_spread_to_ask_ratio * spread_to_ask_weight
                score += (1.0 - intrinsic_share) * intrinsic_weight
            if entry_bar_volume_weight > 0.0:
                symbol = str(candidate.contract.get("symbol") or "").strip()
                if not symbol:
                    had_filtered_candidates = True
                    _record_selection_rejection("contract_symbol_missing")
                    continue
                entry_bars = self._load_option_bars(symbol=symbol, day=day)
                entry_bar = _first_bar_on_or_after(entry_bars, selection_ts_effective, fallback_last=False)
                required_entry_volume = max(int(config.option_min_entry_volume), 0)
                if entry_bar is None:
                    entry_bar_volume = 0
                    score += entry_bar_volume_weight * 8.0
                else:
                    entry_bar_volume = int(entry_bar.get("volume") or 0)
                    if required_entry_volume > 0:
                        shortfall = max(required_entry_volume - entry_bar_volume, 0) / max(
                            float(required_entry_volume),
                            1.0,
                        )
                        if shortfall > 0.0:
                            score += shortfall * (entry_bar_volume_weight * 8.0)
                        else:
                            extra_volume = max(entry_bar_volume - required_entry_volume, 0)
                            volume_bonus = min(
                                float(extra_volume) / max(float(required_entry_volume), 1.0),
                                1.5,
                            )
                            score -= volume_bonus * entry_bar_volume_weight
                    else:
                        volume_bonus = min(log1p(float(entry_bar_volume) + 1.0) / log1p(11.0), 1.0)
                        score -= volume_bonus * (entry_bar_volume_weight * 0.5)
            if delta_weight > 0.0 and target_abs_delta > 0.0:
                if abs_delta is None:
                    if delta_fallback_used:
                        score += (moneyness * 20.0) * delta_weight
                    else:
                        score += target_abs_delta * delta_weight
                else:
                    score += abs(abs_delta - target_abs_delta) * delta_weight
            scored_candidates.append(
                {
                    "score": float(score),
                    "candidate": candidate,
                    "dte": int(dte),
                    "moneyness": float(moneyness),
                    "oi_bonus": float(oi_bonus),
                    "quote_spread_pct": quote_spread_pct,
                    "quote_spread_abs": quote_spread_abs,
                    "quote_spread_to_ask_ratio": quote_spread_to_ask_ratio,
                    "intrinsic_value": intrinsic_value,
                    "intrinsic_share": intrinsic_share,
                    "extrinsic_value": extrinsic_value,
                    "abs_delta": abs_delta,
                    "delta_fallback_used": bool(delta_fallback_used),
                    "quote_used": bool(quote_used),
                    "entry_bar_volume": entry_bar_volume,
                }
            )
        if not scored_candidates:
            return None, had_filtered_candidates, []

        def _strike_distance_steps_for_candidate(target_candidate: _ContractCandidate) -> Optional[int]:
            expiry_candidates = list(grouped_candidates.ascending_by_expiration.get(target_candidate.expiration_day) or [])
            if not expiry_candidates:
                return None
            nearest_candidate = min(
                expiry_candidates,
                key=lambda candidate: (
                    abs(float(candidate.strike) - float(entry_underlying)),
                    0 if float(candidate.strike) >= float(entry_underlying) else 1,
                    abs((candidate.expiration_day - target_candidate.expiration_day).days),
                ),
            )
            nearest_symbol = str(nearest_candidate.contract.get("symbol") or "").strip()
            target_symbol = str(target_candidate.contract.get("symbol") or "").strip()
            nearest_idx = next(
                (
                    idx
                    for idx, candidate in enumerate(expiry_candidates)
                    if str(candidate.contract.get("symbol") or "").strip() == nearest_symbol
                ),
                0,
            )
            target_idx = next(
                (
                    idx
                    for idx, candidate in enumerate(expiry_candidates)
                    if str(candidate.contract.get("symbol") or "").strip() == target_symbol
                ),
                nearest_idx,
            )
            return abs(int(target_idx) - int(nearest_idx))

        scored_candidates.sort(key=lambda item: float(item.get("score") or 0.0))
        ranked_pool: List[Dict[str, Any]] = []
        for rank, item in enumerate(scored_candidates, start=1):
            candidate = item["candidate"]
            strike_distance_steps = _strike_distance_steps_for_candidate(candidate)
            contract_row = dict(candidate.contract)
            contract_row["_selection_dte"] = int(item["dte"])
            contract_row["_selection_moneyness"] = float(item["moneyness"])
            contract_row["_selection_oi_bonus"] = float(item["oi_bonus"])
            contract_row["_selection_score"] = float(item["score"])
            contract_row["_selection_requested_status"] = str(contract_status)
            contract_row["_selection_quote_spread_pct"] = (
                float(item["quote_spread_pct"]) if item["quote_spread_pct"] is not None else None
            )
            contract_row["_selection_quote_spread_abs"] = (
                float(item["quote_spread_abs"]) if item["quote_spread_abs"] is not None else None
            )
            contract_row["_selection_quote_spread_to_ask_ratio"] = (
                float(item["quote_spread_to_ask_ratio"])
                if item["quote_spread_to_ask_ratio"] is not None
                else None
            )
            contract_row["_selection_intrinsic_value"] = (
                float(item["intrinsic_value"]) if item["intrinsic_value"] is not None else None
            )
            contract_row["_selection_intrinsic_share"] = (
                float(item["intrinsic_share"]) if item["intrinsic_share"] is not None else None
            )
            contract_row["_selection_extrinsic_value"] = (
                float(item["extrinsic_value"]) if item["extrinsic_value"] is not None else None
            )
            contract_row["_selection_abs_delta"] = (
                float(item["abs_delta"]) if item["abs_delta"] is not None else None
            )
            contract_row["_selection_strike_distance_steps"] = (
                int(strike_distance_steps) if strike_distance_steps is not None else None
            )
            contract_row["_selection_delta_fallback_mode"] = str(delta_fallback_mode)
            contract_row["_selection_delta_fallback_used"] = bool(item["delta_fallback_used"])
            contract_row["_selection_quote_used"] = bool(item["quote_used"])
            contract_row["_selection_local_itm_steps"] = int(local_itm_steps)
            contract_row["_selection_local_otm_steps"] = int(local_otm_steps)
            contract_row["_selection_local_strike_band_size"] = int(local_strike_band_size)
            contract_row["_selection_entry_bar_volume"] = (
                int(item["entry_bar_volume"]) if item["entry_bar_volume"] is not None else None
            )
            contract_row["_selection_entry_bar_volume_weight"] = float(entry_bar_volume_weight)
            contract_row["_selection_quote_max_spread_abs_filter"] = (
                float(max_quote_spread_abs) if max_quote_spread_abs > 0.0 else None
            )
            contract_row["_selection_quote_max_spread_to_ask_filter"] = (
                float(max_spread_to_ask_ratio) if max_spread_to_ask_ratio > 0.0 else None
            )
            contract_row["_selection_quote_min_ask_filter"] = (
                float(min_quote_ask) if min_quote_ask > 0.0 else None
            )
            contract_row["_selection_rank"] = int(rank)
            ranked_pool.append(contract_row)
        return dict(ranked_pool[0]), had_filtered_candidates, ranked_pool

    (
        contracts,
        raw_list_cached,
        had_fetch_error,
        had_successful_attempt,
        candidate_cache_key,
        used_cached_contract_source,
    ) = _load_contract_pool(True)
    if not contracts:
        _record_selection_rejection("contract_pool_empty")
    if had_fetch_error and not had_successful_attempt:
        _record_selection_rejection("contract_fetch_error")
    selected, had_filtered_candidates, ranked_pool = _rank_contracts(
        contracts=contracts,
        candidate_cache_key=candidate_cache_key,
    )
    if selected is None and used_cached_contract_source:
        self._clear_contract_lookup_caches()
        (
            contracts,
            raw_list_cached,
            had_fetch_error,
            had_successful_attempt,
            candidate_cache_key,
            _,
        ) = _load_contract_pool(False)
        if not contracts:
            _record_selection_rejection("contract_pool_empty")
        if had_fetch_error and not had_successful_attempt:
            _record_selection_rejection("contract_fetch_error")
        selected, had_filtered_candidates, ranked_pool = _rank_contracts(
            contracts=contracts,
            candidate_cache_key=candidate_cache_key,
        )

    if selected is None:
        if had_fetch_error and not had_successful_attempt:
            self._last_contract_selection_reason = "contract_fetch_error"
        elif not contracts:
            self._last_contract_selection_reason = "contract_pool_empty"
        elif had_filtered_candidates:
            self._last_contract_selection_reason = "contract_filtered_out"
        elif raw_list_cached:
            self._last_contract_selection_reason = "contract_not_found_cached"
        else:
            self._last_contract_selection_reason = "contract_not_found"
    else:
        self._last_contract_selection_reason = ""
    selection_meta = {
        "selected": bool(selected is not None),
        "pool_contract_count": int(len(contracts)),
        "ranked_pool": [dict(item) for item in ranked_pool],
        "had_filtered_candidates": bool(had_filtered_candidates),
        "had_fetch_error": bool(had_fetch_error),
        "had_successful_attempt": bool(had_successful_attempt),
        "raw_list_cached": bool(raw_list_cached),
        "used_cached_contract_source": bool(used_cached_contract_source),
        "open_interest_data_unavailable": bool(open_interest_data_unavailable),
        "rejection_counts": dict(selection_rejection_counts),
        "final_reason": str(self._last_contract_selection_reason or ""),
    }
    self._contract_selection_meta_cache[cache_key] = dict(selection_meta)
    self._last_contract_selection_meta = dict(selection_meta)
    self._contract_cache[cache_key] = selected
    return selected


def _load_contract_pool_for_day(
    self,
    *,
    ticker: str,
    day: date,
    option_type: str,
    config: IntradayOptionsBacktestConfig,
) -> List[Dict[str, Any]]:
    raw_cache_key = (
        ticker,
        day.isoformat(),
        option_type,
        str(config.option_contract_status or "inactive").strip().lower(),
        int(config.option_min_dte),
        int(config.option_max_dte),
    )
    contracts, _ = self._get_cached_contract_list_for_day(
        raw_cache_key=raw_cache_key,
        ticker=ticker,
        day=day,
        option_type=option_type,
        requested_status=str(config.option_contract_status or "inactive").strip().lower(),
        option_min_dte=int(config.option_min_dte),
        option_max_dte=int(config.option_max_dte),
        allow_persistent_read=True,
    )
    if not contracts:
        contracts = self._contract_list_from_chain_snapshot(
            ticker=ticker,
            day=day,
            option_type=option_type,
            option_min_dte=int(config.option_min_dte),
            option_max_dte=int(config.option_max_dte),
            requested_status=str(config.option_contract_status or "inactive").strip().lower(),
        )
        if contracts:
            self._set_cached_contract_list_for_day(
                raw_cache_key=raw_cache_key,
                ticker=ticker,
                day=day,
                option_type=option_type,
                requested_status=str(config.option_contract_status or "inactive").strip().lower(),
                option_min_dte=int(config.option_min_dte),
                option_max_dte=int(config.option_max_dte),
                contracts=contracts,
            )
    if not contracts and self.cutemarkets_provider is not None:
        try:
            contracts = self._fetch_cutemarkets_contract_list(
                ticker=ticker,
                day=day,
                option_type=option_type,
                option_min_dte=int(config.option_min_dte),
                option_max_dte=int(config.option_max_dte),
            )
        except Exception:
            contracts = []
        if contracts:
            self._set_cached_contract_list_for_day(
                raw_cache_key=raw_cache_key,
                ticker=ticker,
                day=day,
                option_type=option_type,
                requested_status=str(config.option_contract_status or "inactive").strip().lower(),
                option_min_dte=int(config.option_min_dte),
                option_max_dte=int(config.option_max_dte),
                contracts=contracts,
            )
    return self._enrich_contracts_with_chain_snapshot(
        ticker=ticker,
        day=day,
        option_type=option_type,
        contracts=contracts or [],
        enrichment_mode=getattr(config, "option_chain_snapshot_enrichment_mode", "full"),
    )


def _select_vertical_short_leg(
    self,
    *,
    ticker: str,
    day: date,
    direction: int,
    long_contract: Dict[str, Any],
    config: IntradayOptionsBacktestConfig,
    selection_ts: Optional[datetime],
) -> Optional[Dict[str, Any]]:
    option_type = "call" if int(direction) > 0 else "put"
    long_symbol = str(long_contract.get("symbol") or "").strip()
    long_strike = _safe_float(long_contract.get("strike_price"))
    long_expiry = parse_datetime(long_contract.get("expiration_date"))
    if not long_symbol or long_strike is None or long_strike <= 0.0 or long_expiry is None:
        self._bump_option_rejection("vertical_short_leg_missing")
        return None

    contracts = self._load_contract_pool_for_day(
        ticker=ticker,
        day=day,
        option_type=option_type,
        config=config,
    )
    if not contracts:
        self._bump_option_rejection("vertical_short_leg_missing")
        return None

    candidate_cache_key = (
        "vertical_pair",
        ticker,
        day.isoformat(),
        option_type,
        str(config.option_contract_status or "inactive").strip().lower(),
        int(config.option_min_dte),
        int(config.option_max_dte),
    )
    grouped_candidates = self._group_contract_candidates_for_cache_key(
        cache_key=candidate_cache_key,
        contracts=contracts,
    )
    same_expiry_rows = list(grouped_candidates.ascending_by_expiration.get(long_expiry.date(), []))
    same_expiry = [
        candidate
        for candidate in same_expiry_rows
        if str(candidate.contract.get("symbol") or "").strip() not in {"", long_symbol}
    ]
    if not same_expiry:
        self._bump_option_rejection("vertical_same_expiry_pair_missing")
        return None

    if int(direction) > 0:
        otm_candidates = [candidate for candidate in same_expiry if float(candidate.strike) > float(long_strike)]
    else:
        same_expiry_desc = [
            candidate
            for candidate in grouped_candidates.descending_by_expiration.get(long_expiry.date(), [])
            if str(candidate.contract.get("symbol") or "").strip() not in {"", long_symbol}
        ]
        otm_candidates = [candidate for candidate in same_expiry_desc if float(candidate.strike) < float(long_strike)]
    if not otm_candidates:
        self._bump_option_rejection("vertical_short_leg_missing")
        return None

    effective_steps: List[int] = []
    for raw_step in (
        int(config.option_vertical_short_leg_steps),
        int(config.option_vertical_fallback_short_leg_steps),
    ):
        step = max(int(raw_step), 1)
        if step not in effective_steps:
            effective_steps.append(step)

    selection_ts_effective = selection_ts if isinstance(selection_ts, datetime) else datetime.combine(day, time(9, 35))
    selection_quote_mode = self._normalize_selection_quote_mode(getattr(config, "option_selection_quote_mode", "legacy"))
    quote_fallback_last = bool(getattr(config, "option_selection_quote_fallback_last", True))
    long_quote, _long_quote_source = self._selection_quote_for_symbol(
        symbol=long_symbol,
        day=day,
        selection_ts=selection_ts_effective,
        fallback_last=quote_fallback_last,
        selection_quote_mode=selection_quote_mode,
    )
    long_bid = _safe_float(long_quote.get("bid")) if isinstance(long_quote, dict) else None
    long_ask = _safe_float(long_quote.get("ask")) if isinstance(long_quote, dict) else None
    ranked_candidates: List[Tuple[Tuple[float, float, float], Dict[str, Any]]] = []
    for step in effective_steps:
        idx = step - 1
        if idx >= len(otm_candidates):
            continue
        selected = dict(otm_candidates[idx].contract)
        short_symbol = str(selected.get("symbol") or "").strip()
        if not short_symbol:
            continue
        quote, _quote_source = self._selection_quote_for_symbol(
            symbol=short_symbol,
            day=day,
            selection_ts=selection_ts_effective,
            fallback_last=quote_fallback_last,
            selection_quote_mode=selection_quote_mode,
        )
        if quote is None:
            self._bump_option_rejection("vertical_short_leg_quote_missing")
            continue
        bid = _safe_float(quote.get("bid"))
        ask = _safe_float(quote.get("ask"))
        if bid is None or bid <= 0.0 or ask is None or ask < bid:
            self._bump_option_rejection("vertical_short_leg_quote_missing")
            continue
        if bid < max(float(config.option_vertical_min_short_bid), 0.0):
            self._bump_option_rejection("vertical_short_leg_bid_too_low")
            continue
        width = abs(float(selected.get("strike_price") or 0.0) - float(long_strike))
        if width <= 0.0:
            continue
        entry_debit = (float(long_ask) - float(bid)) if long_ask is not None and long_ask > 0.0 else None
        combined_spread_abs = (
            max(float(long_ask) - float(long_bid), 0.0) + max(float(ask) - float(bid), 0.0)
            if long_ask is not None and long_bid is not None
            else None
        )
        debit_to_width_ratio = (float(entry_debit) / float(width)) if entry_debit is not None and entry_debit > 0.0 else None
        combined_spread_to_debit_ratio = (
            float(combined_spread_abs) / float(entry_debit)
            if combined_spread_abs is not None and entry_debit is not None and entry_debit > 0.0
            else None
        )
        selected["_vertical_pair_step"] = int(step)
        selected["_vertical_entry_quote_bid"] = float(bid)
        selected["_vertical_entry_quote_ask"] = float(ask)
        selected["_vertical_entry_quote_ts"] = (
            quote["ts"].isoformat() if isinstance(quote.get("ts"), datetime) else None
        )
        selected["_vertical_entry_debit_candidate"] = entry_debit
        selected["_vertical_combined_spread_abs_candidate"] = combined_spread_abs
        selected["_vertical_combined_spread_to_debit_ratio_candidate"] = combined_spread_to_debit_ratio
        selected["_vertical_debit_to_width_ratio_candidate"] = debit_to_width_ratio
        ranked_candidates.append(
            (
                (
                    float(combined_spread_to_debit_ratio)
                    if combined_spread_to_debit_ratio is not None
                    else float("inf"),
                    float(debit_to_width_ratio) if debit_to_width_ratio is not None else float("inf"),
                    -float(bid),
                ),
                selected,
            )
        )

    if ranked_candidates:
        ranked_candidates.sort(key=lambda item: item[0])
        return ranked_candidates[0][1]

    return None


def _select_vertical_credit_long_leg(
    self,
    *,
    ticker: str,
    day: date,
    direction: int,
    short_contract: Dict[str, Any],
    config: IntradayOptionsBacktestConfig,
    selection_ts: Optional[datetime],
) -> Optional[Dict[str, Any]]:
    option_type = "put" if int(direction) > 0 else "call"
    short_symbol = str(short_contract.get("symbol") or "").strip()
    short_strike = _safe_float(short_contract.get("strike_price"))
    short_expiry = parse_datetime(short_contract.get("expiration_date"))
    if not short_symbol or short_strike is None or short_strike <= 0.0 or short_expiry is None:
        self._bump_option_rejection("vertical_credit_long_leg_missing")
        return None

    contracts = self._load_contract_pool_for_day(
        ticker=ticker,
        day=day,
        option_type=option_type,
        config=config,
    )
    if not contracts:
        self._bump_option_rejection("vertical_credit_long_leg_missing")
        return None

    candidate_cache_key = (
        "vertical_credit_pair",
        ticker,
        day.isoformat(),
        option_type,
        str(config.option_contract_status or "inactive").strip().lower(),
        int(config.option_min_dte),
        int(config.option_max_dte),
    )
    grouped_candidates = self._group_contract_candidates_for_cache_key(
        cache_key=candidate_cache_key,
        contracts=contracts,
    )
    same_expiry_rows = list(grouped_candidates.ascending_by_expiration.get(short_expiry.date(), []))
    same_expiry = [
        candidate
        for candidate in same_expiry_rows
        if str(candidate.contract.get("symbol") or "").strip() not in {"", short_symbol}
    ]
    if not same_expiry:
        self._bump_option_rejection("vertical_credit_same_expiry_pair_missing")
        return None

    if int(direction) > 0:
        same_expiry_desc = [
            candidate
            for candidate in grouped_candidates.descending_by_expiration.get(short_expiry.date(), [])
            if str(candidate.contract.get("symbol") or "").strip() not in {"", short_symbol}
        ]
        otm_candidates = [candidate for candidate in same_expiry_desc if float(candidate.strike) < float(short_strike)]
    else:
        otm_candidates = [candidate for candidate in same_expiry if float(candidate.strike) > float(short_strike)]
    if not otm_candidates:
        self._bump_option_rejection("vertical_credit_long_leg_missing")
        return None

    effective_steps: List[int] = []
    for raw_step in (
        int(config.option_vertical_credit_long_leg_steps),
        int(config.option_vertical_credit_fallback_long_leg_steps),
    ):
        step = max(int(raw_step), 1)
        if step not in effective_steps:
            effective_steps.append(step)

    selection_ts_effective = selection_ts if isinstance(selection_ts, datetime) else datetime.combine(day, time(9, 35))
    selection_quote_mode = self._normalize_selection_quote_mode(getattr(config, "option_selection_quote_mode", "legacy"))
    quote_fallback_last = bool(getattr(config, "option_selection_quote_fallback_last", True))
    short_quote, _short_quote_source = self._selection_quote_for_symbol(
        symbol=short_symbol,
        day=day,
        selection_ts=selection_ts_effective,
        fallback_last=quote_fallback_last,
        selection_quote_mode=selection_quote_mode,
    )
    short_bid = _safe_float(short_quote.get("bid")) if isinstance(short_quote, dict) else None
    short_ask = _safe_float(short_quote.get("ask")) if isinstance(short_quote, dict) else None
    ranked_candidates: List[Tuple[Tuple[float, float, float], Dict[str, Any]]] = []
    for step in effective_steps:
        idx = step - 1
        if idx >= len(otm_candidates):
            continue
        selected = dict(otm_candidates[idx].contract)
        long_symbol = str(selected.get("symbol") or "").strip()
        if not long_symbol:
            continue
        quote, _quote_source = self._selection_quote_for_symbol(
            symbol=long_symbol,
            day=day,
            selection_ts=selection_ts_effective,
            fallback_last=quote_fallback_last,
            selection_quote_mode=selection_quote_mode,
        )
        if quote is None:
            self._bump_option_rejection("vertical_credit_long_leg_quote_missing")
            continue
        bid = _safe_float(quote.get("bid"))
        ask = _safe_float(quote.get("ask"))
        if ask is None or ask <= 0.0 or bid is None or bid > ask:
            self._bump_option_rejection("vertical_credit_long_leg_quote_missing")
            continue
        width = abs(float(selected.get("strike_price") or 0.0) - float(short_strike))
        if width <= 0.0:
            continue
        entry_credit = (float(short_bid) - float(ask)) if short_bid is not None and short_bid > 0.0 else None
        combined_spread_abs = (
            max(float(short_ask) - float(short_bid), 0.0) + max(float(ask) - float(bid), 0.0)
            if short_ask is not None and short_bid is not None
            else None
        )
        credit_to_width_ratio = (
            float(entry_credit) / float(width) if entry_credit is not None and entry_credit > 0.0 else None
        )
        combined_spread_to_credit_ratio = (
            float(combined_spread_abs) / float(entry_credit)
            if combined_spread_abs is not None and entry_credit is not None and entry_credit > 0.0
            else None
        )
        selected["_vertical_credit_pair_step"] = int(step)
        selected["_vertical_credit_entry_quote_bid"] = float(bid) if bid is not None else None
        selected["_vertical_credit_entry_quote_ask"] = float(ask)
        selected["_vertical_credit_entry_quote_ts"] = (
            quote["ts"].isoformat() if isinstance(quote.get("ts"), datetime) else None
        )
        selected["_vertical_entry_credit_candidate"] = entry_credit
        selected["_vertical_combined_spread_abs_candidate"] = combined_spread_abs
        selected["_vertical_combined_spread_to_credit_ratio_candidate"] = combined_spread_to_credit_ratio
        selected["_vertical_credit_to_width_ratio_candidate"] = credit_to_width_ratio
        ranked_candidates.append(
            (
                (
                    float(combined_spread_to_credit_ratio)
                    if combined_spread_to_credit_ratio is not None
                    else float("inf"),
                    float(credit_to_width_ratio) if credit_to_width_ratio is not None else float("inf"),
                    float(width),
                ),
                selected,
            )
        )

    if ranked_candidates:
        ranked_candidates.sort(key=lambda item: item[0])
        return ranked_candidates[0][1]

    return None
