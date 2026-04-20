from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from statistics import median
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from ..providers.cutemarkets import CuteMarketsProvider
from ..storage import DataStore


@dataclass(frozen=True)
class OptionTradabilitySample:
    ticker: str
    start_day: date
    end_day: date
    dte_min: int
    dte_max: int
    delta_min: float
    delta_max: float
    quote_coverage_pct: float
    chain_coverage_pct: float
    median_open_interest: float
    median_entry_volume: float
    median_spread_to_mid: float
    median_spread_to_ask: float
    median_premium_price: float
    sample_count: int
    estimated_round_trip_cost_pct: float
    estimated_cost_to_expected_edge_ratio: float
    days_evaluated: int = 0
    days_with_chain: int = 0
    days_with_quotes: int = 0
    page_limit: int = 0
    paginated: bool = False
    raw_chain_days: int = 0
    raw_quote_days: int = 0
    raw_contract_count: int = 0
    filtered_contract_count: int = 0
    raw_rows_with_bid: int = 0
    raw_rows_with_ask: int = 0
    raw_rows_with_midpoint: int = 0
    raw_rows_with_valid_quote: int = 0
    fetch_error_count: int = 0
    fetch_error_examples: tuple[str, ...] = ()
    sampling_mode: str = "historical_window"
    sampling_reference_day: Optional[date] = None
    historical_quote_coverage_pct: float = 0.0
    historical_chain_coverage_pct: float = 0.0
    historical_sample_count: int = 0
    current_quote_coverage_pct: float = 0.0
    current_chain_coverage_pct: float = 0.0
    current_median_open_interest: float = 0.0
    current_median_entry_volume: float = 0.0
    current_median_spread_to_mid: float = 0.0
    current_median_spread_to_ask: float = 0.0
    current_median_premium_price: float = 0.0
    current_quote_sample_count: int = 0
    current_raw_contract_count: int = 0
    current_filtered_contract_count: int = 0
    current_raw_rows_with_bid: int = 0
    current_raw_rows_with_ask: int = 0
    current_raw_rows_with_midpoint: int = 0
    current_raw_rows_with_valid_quote: int = 0
    current_estimated_round_trip_cost_pct: float = 0.0
    current_estimated_cost_to_expected_edge_ratio: float = 0.0
    current_sampling_mode: str = "none"
    current_sampling_reference_day: Optional[date] = None
    current_note: str = ""
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "start_day": self.start_day.isoformat(),
            "end_day": self.end_day.isoformat(),
            "dte_min": int(self.dte_min),
            "dte_max": int(self.dte_max),
            "delta_min": float(self.delta_min),
            "delta_max": float(self.delta_max),
            "quote_coverage_pct": float(self.quote_coverage_pct),
            "chain_coverage_pct": float(self.chain_coverage_pct),
            "median_open_interest": float(self.median_open_interest),
            "median_entry_volume": float(self.median_entry_volume),
            "median_spread_to_mid": float(self.median_spread_to_mid),
            "median_spread_to_ask": float(self.median_spread_to_ask),
            "median_premium_price": float(self.median_premium_price),
            "sample_count": int(self.sample_count),
            "estimated_round_trip_cost_pct": float(self.estimated_round_trip_cost_pct),
            "estimated_cost_to_expected_edge_ratio": float(self.estimated_cost_to_expected_edge_ratio),
            "days_evaluated": int(self.days_evaluated),
            "days_with_chain": int(self.days_with_chain),
            "days_with_quotes": int(self.days_with_quotes),
            "page_limit": int(self.page_limit),
            "paginated": bool(self.paginated),
            "raw_chain_days": int(self.raw_chain_days),
            "raw_quote_days": int(self.raw_quote_days),
            "raw_contract_count": int(self.raw_contract_count),
            "filtered_contract_count": int(self.filtered_contract_count),
            "raw_rows_with_bid": int(self.raw_rows_with_bid),
            "raw_rows_with_ask": int(self.raw_rows_with_ask),
            "raw_rows_with_midpoint": int(self.raw_rows_with_midpoint),
            "raw_rows_with_valid_quote": int(self.raw_rows_with_valid_quote),
            "fetch_error_count": int(self.fetch_error_count),
            "fetch_error_examples": list(self.fetch_error_examples),
            "sampling_mode": str(self.sampling_mode),
            "sampling_reference_day": self.sampling_reference_day.isoformat() if self.sampling_reference_day else None,
            "historical_quote_coverage_pct": float(self.historical_quote_coverage_pct),
            "historical_chain_coverage_pct": float(self.historical_chain_coverage_pct),
            "historical_sample_count": int(self.historical_sample_count),
            "current_quote_coverage_pct": float(self.current_quote_coverage_pct),
            "current_chain_coverage_pct": float(self.current_chain_coverage_pct),
            "current_median_open_interest": float(self.current_median_open_interest),
            "current_median_entry_volume": float(self.current_median_entry_volume),
            "current_median_spread_to_mid": float(self.current_median_spread_to_mid),
            "current_median_spread_to_ask": float(self.current_median_spread_to_ask),
            "current_median_premium_price": float(self.current_median_premium_price),
            "current_quote_sample_count": int(self.current_quote_sample_count),
            "current_raw_contract_count": int(self.current_raw_contract_count),
            "current_filtered_contract_count": int(self.current_filtered_contract_count),
            "current_raw_rows_with_bid": int(self.current_raw_rows_with_bid),
            "current_raw_rows_with_ask": int(self.current_raw_rows_with_ask),
            "current_raw_rows_with_midpoint": int(self.current_raw_rows_with_midpoint),
            "current_raw_rows_with_valid_quote": int(self.current_raw_rows_with_valid_quote),
            "current_estimated_round_trip_cost_pct": float(self.current_estimated_round_trip_cost_pct),
            "current_estimated_cost_to_expected_edge_ratio": float(self.current_estimated_cost_to_expected_edge_ratio),
            "current_sampling_mode": str(self.current_sampling_mode),
            "current_sampling_reference_day": self.current_sampling_reference_day.isoformat()
            if self.current_sampling_reference_day
            else None,
            "current_note": str(self.current_note or ""),
            "note": str(self.note or ""),
        }


def sample_option_tradability(
    *,
    ticker: str,
    store: Optional[DataStore],
    cutemarkets_provider: Optional[CuteMarketsProvider],
    end_day: date,
    lookback_days: int,
    dte_min: int,
    dte_max: int,
    delta_min: float,
    delta_max: float,
    target_dte: Optional[int] = None,
    target_abs_delta: Optional[float] = None,
    max_target_contracts_per_day: int = 5,
    expected_edge_pct: float = 0.08,
) -> OptionTradabilitySample:
    historical_page_limit = 250
    historical_max_pages = 2
    target_dte_value = (
        int(target_dte)
        if target_dte is not None
        else max(int(round((int(dte_min) + int(dte_max)) / 2.0)), int(dte_min))
    )
    target_abs_delta_value = (
        float(target_abs_delta)
        if target_abs_delta is not None and float(target_abs_delta) > 0.0
        else max((float(delta_min) + float(delta_max)) / 2.0, 0.0)
    )
    target_abs_delta_value = min(max(target_abs_delta_value, 0.0), 1.0)
    target_contracts_per_day = max(int(max_target_contracts_per_day or 1), 1)
    start_day = end_day - timedelta(days=max(int(lookback_days), 1) - 1)
    total_days = 0
    days_with_chain = 0
    days_with_quotes = 0
    raw_chain_days = 0
    raw_quote_days = 0
    raw_contract_count = 0
    filtered_contract_count = 0
    raw_rows_with_bid = 0
    raw_rows_with_ask = 0
    raw_rows_with_midpoint = 0
    raw_rows_with_valid_quote = 0
    fetch_error_count = 0
    fetch_error_examples: List[str] = []
    repeated_snapshot_signatures: List[str] = []
    fallback_reason = ""
    open_interest_values: List[float] = []
    volume_values: List[float] = []
    spread_to_mid_values: List[float] = []
    spread_to_ask_values: List[float] = []
    premium_values: List[float] = []
    current_proxy: Optional[OptionTradabilitySample] = None

    current = start_day
    while current <= end_day:
        if current.weekday() >= 5:
            current += timedelta(days=1)
            continue
        total_days += 1
        rows, fetch_error = _load_chain_snapshot(
            ticker=str(ticker or "").strip().upper(),
            day=current,
            store=store,
            cutemarkets_provider=cutemarkets_provider,
            dte_min=int(dte_min),
            dte_max=int(dte_max),
            page_limit=historical_page_limit,
            max_pages=historical_max_pages,
        )
        if fetch_error:
            fetch_error_count += 1
            if fetch_error not in fetch_error_examples and len(fetch_error_examples) < 5:
                fetch_error_examples.append(fetch_error)
        if rows:
            raw_chain_days += 1
            raw_contract_count += len(rows)
            raw_rows_with_bid += sum(1 for row in rows if _has_bid(row))
            raw_rows_with_ask += sum(1 for row in rows if _has_ask(row))
            raw_rows_with_midpoint += sum(1 for row in rows if _has_midpoint(row))
            day_valid_quotes = sum(1 for row in rows if _quoted(row))
            raw_rows_with_valid_quote += day_valid_quotes
            if day_valid_quotes > 0:
                raw_quote_days += 1
            signature = _snapshot_signature(rows)
            if signature:
                repeated_snapshot_signatures.append(signature)
        filtered = _filter_chain_rows(
            rows,
            day=current,
            dte_min=int(dte_min),
            dte_max=int(dte_max),
            delta_min=float(delta_min),
            delta_max=float(delta_max),
        )
        filtered_contract_count += len(filtered)
        targeted = _select_targeted_rows(
            filtered,
            target_dte=target_dte_value,
            target_abs_delta=target_abs_delta_value,
            max_rows=target_contracts_per_day,
        )
        if targeted:
            days_with_chain += 1
            quoted = [row for row in targeted if _quoted(row)]
            if quoted:
                days_with_quotes += 1
            for row in quoted or targeted:
                oi = _safe_float(row.get("open_interest"))
                vol = _safe_float(row.get("volume"))
                bid = _safe_float(row.get("bid"))
                ask = _safe_float(row.get("ask"))
                if oi is not None:
                    open_interest_values.append(float(oi))
                if vol is not None:
                    volume_values.append(float(vol))
                if bid is not None and ask is not None and ask > 0.0 and ask >= bid >= 0.0:
                    mid = (bid + ask) / 2.0 if (bid + ask) > 0.0 else 0.0
                    if mid > 0.0:
                        spread_to_mid_values.append(max(ask - bid, 0.0) / mid)
                    spread_to_ask_values.append(max(ask - bid, 0.0) / ask)
                    premium_values.append(ask)
        if days_with_chain == 0:
            if raw_chain_days >= 3 and len(repeated_snapshot_signatures) >= 3:
                if len(set(repeated_snapshot_signatures[-3:])) == 1:
                    fallback_reason = "historical_snapshot_repeated_signature"
                    break
            if raw_chain_days == 0 and fetch_error_count >= 3:
                fallback_reason = "historical_snapshot_fetch_errors"
                break
        current += timedelta(days=1)

    if cutemarkets_provider is not None:
        current_proxy = _sample_current_snapshot_proxy(
            ticker=str(ticker or "").strip().upper(),
            cutemarkets_provider=cutemarkets_provider,
            expected_edge_pct=float(expected_edge_pct),
            dte_min=int(dte_min),
            dte_max=int(dte_max),
            delta_min=float(delta_min),
            delta_max=float(delta_max),
            target_dte=target_dte_value,
            target_abs_delta=target_abs_delta_value,
            max_target_contracts_per_day=target_contracts_per_day,
            end_day=end_day,
        )
    if days_with_chain == 0 and current_proxy is not None:
        fallback = current_proxy
        return OptionTradabilitySample(
            ticker=fallback.ticker,
            start_day=start_day,
            end_day=end_day,
            dte_min=int(dte_min),
            dte_max=int(dte_max),
            delta_min=float(delta_min),
            delta_max=float(delta_max),
            quote_coverage_pct=fallback.quote_coverage_pct,
            chain_coverage_pct=fallback.chain_coverage_pct,
            median_open_interest=fallback.median_open_interest,
            median_entry_volume=fallback.median_entry_volume,
            median_spread_to_mid=fallback.median_spread_to_mid,
            median_spread_to_ask=fallback.median_spread_to_ask,
            median_premium_price=fallback.median_premium_price,
            sample_count=fallback.sample_count,
            estimated_round_trip_cost_pct=fallback.estimated_round_trip_cost_pct,
            estimated_cost_to_expected_edge_ratio=fallback.estimated_cost_to_expected_edge_ratio,
            days_evaluated=int(total_days),
            days_with_chain=int(days_with_chain),
            days_with_quotes=int(days_with_quotes),
            page_limit=int(historical_page_limit),
            paginated=bool(historical_max_pages > 1),
            raw_chain_days=int(raw_chain_days) if raw_chain_days > 0 else int(fallback.raw_chain_days),
            raw_quote_days=int(raw_quote_days) if raw_quote_days > 0 else int(fallback.raw_quote_days),
            raw_contract_count=int(raw_contract_count) if raw_contract_count > 0 else int(fallback.raw_contract_count),
            filtered_contract_count=int(filtered_contract_count) if filtered_contract_count > 0 else int(fallback.filtered_contract_count),
            raw_rows_with_bid=int(raw_rows_with_bid) if raw_rows_with_bid > 0 else int(fallback.raw_rows_with_bid),
            raw_rows_with_ask=int(raw_rows_with_ask) if raw_rows_with_ask > 0 else int(fallback.raw_rows_with_ask),
            raw_rows_with_midpoint=(
                int(raw_rows_with_midpoint) if raw_rows_with_midpoint > 0 else int(fallback.raw_rows_with_midpoint)
            ),
            raw_rows_with_valid_quote=(
                int(raw_rows_with_valid_quote)
                if raw_rows_with_valid_quote > 0
                else int(fallback.raw_rows_with_valid_quote)
            ),
            fetch_error_count=int(fetch_error_count) + int(fallback.fetch_error_count),
            fetch_error_examples=tuple(fetch_error_examples or list(fallback.fetch_error_examples)),
            sampling_mode=str(fallback.sampling_mode),
            sampling_reference_day=fallback.sampling_reference_day,
            historical_quote_coverage_pct=0.0,
            historical_chain_coverage_pct=0.0,
            historical_sample_count=0,
            current_quote_coverage_pct=fallback.current_quote_coverage_pct or fallback.quote_coverage_pct,
            current_chain_coverage_pct=fallback.current_chain_coverage_pct or fallback.chain_coverage_pct,
            current_median_open_interest=fallback.current_median_open_interest or fallback.median_open_interest,
            current_median_entry_volume=fallback.current_median_entry_volume or fallback.median_entry_volume,
            current_median_spread_to_mid=fallback.current_median_spread_to_mid or fallback.median_spread_to_mid,
            current_median_spread_to_ask=fallback.current_median_spread_to_ask or fallback.median_spread_to_ask,
            current_median_premium_price=fallback.current_median_premium_price or fallback.median_premium_price,
            current_quote_sample_count=fallback.current_quote_sample_count or fallback.sample_count,
            current_raw_contract_count=fallback.current_raw_contract_count or fallback.raw_contract_count,
            current_filtered_contract_count=fallback.current_filtered_contract_count or fallback.filtered_contract_count,
            current_raw_rows_with_bid=fallback.current_raw_rows_with_bid or fallback.raw_rows_with_bid,
            current_raw_rows_with_ask=fallback.current_raw_rows_with_ask or fallback.raw_rows_with_ask,
            current_raw_rows_with_midpoint=fallback.current_raw_rows_with_midpoint or fallback.raw_rows_with_midpoint,
            current_raw_rows_with_valid_quote=(
                fallback.current_raw_rows_with_valid_quote or fallback.raw_rows_with_valid_quote
            ),
            current_estimated_round_trip_cost_pct=fallback.current_estimated_round_trip_cost_pct
            or fallback.estimated_round_trip_cost_pct,
            current_estimated_cost_to_expected_edge_ratio=fallback.current_estimated_cost_to_expected_edge_ratio
            or fallback.estimated_cost_to_expected_edge_ratio,
            current_sampling_mode=fallback.current_sampling_mode or fallback.sampling_mode,
            current_sampling_reference_day=fallback.current_sampling_reference_day or fallback.sampling_reference_day,
            current_note=fallback.current_note or fallback.note,
            note=str(
                (
                    f"{fallback_reason}: historical_chain_sampling_unavailable_using_current_snapshot_proxy"
                    if fallback_reason
                    else "historical_chain_sampling_unavailable_using_current_snapshot_proxy"
                )
                if not fetch_error_examples
                else (
                    (
                        f"{fallback_reason}: historical_chain_sampling_unavailable_using_current_snapshot_proxy: "
                        if fallback_reason
                        else "historical_chain_sampling_unavailable_using_current_snapshot_proxy: "
                    )
                    + "; ".join(fetch_error_examples)
                )
            ),
        )

    quote_coverage_pct = (float(days_with_quotes) / float(total_days)) if total_days > 0 else 0.0
    chain_coverage_pct = (float(days_with_chain) / float(total_days)) if total_days > 0 else 0.0
    median_open_interest = _median_or_zero(open_interest_values)
    median_entry_volume = _median_or_zero(volume_values)
    median_spread_to_mid = _median_or_zero(spread_to_mid_values)
    median_spread_to_ask = _median_or_zero(spread_to_ask_values)
    median_premium_price = _median_or_zero(premium_values)
    estimated_round_trip_cost_pct = min(max(median_spread_to_mid, median_spread_to_ask) * 2.0, 5.0)
    estimated_cost_to_expected_edge_ratio = estimated_round_trip_cost_pct / max(float(expected_edge_pct), 1e-6)
    sample_count = len(premium_values) if premium_values else len(open_interest_values)
    current_quote_coverage_pct = float(current_proxy.quote_coverage_pct) if current_proxy is not None else 0.0
    current_chain_coverage_pct = float(current_proxy.chain_coverage_pct) if current_proxy is not None else 0.0
    current_median_open_interest = float(current_proxy.median_open_interest) if current_proxy is not None else 0.0
    current_median_entry_volume = float(current_proxy.median_entry_volume) if current_proxy is not None else 0.0
    current_median_spread_to_mid = float(current_proxy.median_spread_to_mid) if current_proxy is not None else 0.0
    current_median_spread_to_ask = float(current_proxy.median_spread_to_ask) if current_proxy is not None else 0.0
    current_median_premium_price = float(current_proxy.median_premium_price) if current_proxy is not None else 0.0
    current_quote_sample_count = int(current_proxy.sample_count) if current_proxy is not None else 0
    current_raw_contract_count = int(current_proxy.raw_contract_count) if current_proxy is not None else 0
    current_filtered_contract_count = int(current_proxy.filtered_contract_count) if current_proxy is not None else 0
    current_estimated_round_trip_cost_pct = (
        float(current_proxy.estimated_round_trip_cost_pct) if current_proxy is not None else 0.0
    )
    current_estimated_cost_to_expected_edge_ratio = (
        float(current_proxy.estimated_cost_to_expected_edge_ratio) if current_proxy is not None else 0.0
    )
    return OptionTradabilitySample(
        ticker=str(ticker or "").strip().upper(),
        start_day=start_day,
        end_day=end_day,
        dte_min=int(dte_min),
        dte_max=int(dte_max),
        delta_min=float(delta_min),
        delta_max=float(delta_max),
        quote_coverage_pct=quote_coverage_pct,
        chain_coverage_pct=chain_coverage_pct,
        median_open_interest=median_open_interest,
        median_entry_volume=median_entry_volume,
        median_spread_to_mid=median_spread_to_mid,
        median_spread_to_ask=median_spread_to_ask,
        median_premium_price=median_premium_price,
        sample_count=sample_count,
        estimated_round_trip_cost_pct=estimated_round_trip_cost_pct,
        estimated_cost_to_expected_edge_ratio=estimated_cost_to_expected_edge_ratio,
        days_evaluated=total_days,
        days_with_chain=days_with_chain,
        days_with_quotes=days_with_quotes,
        page_limit=historical_page_limit,
        paginated=bool(historical_max_pages > 1),
        raw_chain_days=raw_chain_days,
        raw_quote_days=raw_quote_days,
        raw_contract_count=raw_contract_count,
        filtered_contract_count=filtered_contract_count,
        raw_rows_with_bid=raw_rows_with_bid,
        raw_rows_with_ask=raw_rows_with_ask,
        raw_rows_with_midpoint=raw_rows_with_midpoint,
        raw_rows_with_valid_quote=raw_rows_with_valid_quote,
        fetch_error_count=fetch_error_count,
        fetch_error_examples=tuple(fetch_error_examples),
        sampling_mode="historical_window",
        sampling_reference_day=end_day,
        historical_quote_coverage_pct=quote_coverage_pct,
        historical_chain_coverage_pct=chain_coverage_pct,
        historical_sample_count=sample_count,
        current_quote_coverage_pct=current_quote_coverage_pct,
        current_chain_coverage_pct=current_chain_coverage_pct,
        current_median_open_interest=current_median_open_interest,
        current_median_entry_volume=current_median_entry_volume,
        current_median_spread_to_mid=current_median_spread_to_mid,
        current_median_spread_to_ask=current_median_spread_to_ask,
        current_median_premium_price=current_median_premium_price,
        current_quote_sample_count=current_quote_sample_count,
        current_raw_contract_count=current_raw_contract_count,
        current_filtered_contract_count=current_filtered_contract_count,
        current_raw_rows_with_bid=int(current_proxy.raw_rows_with_bid) if current_proxy is not None else 0,
        current_raw_rows_with_ask=int(current_proxy.raw_rows_with_ask) if current_proxy is not None else 0,
        current_raw_rows_with_midpoint=int(current_proxy.raw_rows_with_midpoint) if current_proxy is not None else 0,
        current_raw_rows_with_valid_quote=(
            int(current_proxy.raw_rows_with_valid_quote) if current_proxy is not None else 0
        ),
        current_estimated_round_trip_cost_pct=current_estimated_round_trip_cost_pct,
        current_estimated_cost_to_expected_edge_ratio=current_estimated_cost_to_expected_edge_ratio,
        current_sampling_mode=str(current_proxy.sampling_mode) if current_proxy is not None else "none",
        current_sampling_reference_day=current_proxy.sampling_reference_day if current_proxy is not None else None,
        current_note=(
            "using_current_quote_quality_proxy"
            if current_proxy is not None and current_quote_sample_count > 0
            else (str(current_proxy.note or "") if current_proxy is not None else "")
        ),
    )


def evaluate_tradability_thresholds(
    *,
    sample: OptionTradabilitySample,
    min_quote_coverage_pct: float,
    min_chain_coverage_pct: float,
    min_open_interest: int,
    max_spread_to_ask: float,
    max_cost_to_expected_edge_ratio: float,
    availability_mode: str = "strict_historical",
) -> Dict[str, Any]:
    availability_mode_value = str(availability_mode or "strict_historical").strip().lower()
    current_quote_proxy_available = int(sample.current_quote_sample_count or 0) > 0
    gate_quote_coverage_pct = (
        float(sample.current_quote_coverage_pct)
        if current_quote_proxy_available
        else float(sample.quote_coverage_pct)
    )
    gate_spread_to_ask = (
        float(sample.current_median_spread_to_ask)
        if current_quote_proxy_available
        else float(sample.median_spread_to_ask)
    )
    gate_cost_to_expected_edge_ratio = (
        float(sample.current_estimated_cost_to_expected_edge_ratio)
        if current_quote_proxy_available
        else float(sample.estimated_cost_to_expected_edge_ratio)
    )
    quote_quality_passed = bool(
        gate_quote_coverage_pct >= float(min_quote_coverage_pct)
        and gate_spread_to_ask <= float(max_spread_to_ask)
        and gate_cost_to_expected_edge_ratio <= float(max_cost_to_expected_edge_ratio)
    )
    historical_chain_passed = float(sample.chain_coverage_pct) >= float(min_chain_coverage_pct)
    historical_open_interest_passed = float(sample.median_open_interest) >= float(min_open_interest)
    failed_checks: List[str] = []
    diagnostic_checks: List[str] = []
    if availability_mode_value == "vendor_limited_current_proxy":
        availability_passed = bool(historical_open_interest_passed and current_quote_proxy_available)
        if not historical_open_interest_passed:
            failed_checks.append("historical_open_interest")
        if not current_quote_proxy_available:
            failed_checks.append("current_quote_proxy_missing")
        if not historical_chain_passed:
            diagnostic_checks.append("historical_chain_coverage")
    else:
        availability_passed = bool(historical_chain_passed and historical_open_interest_passed)
        if not historical_chain_passed:
            failed_checks.append("historical_chain_coverage")
        if not historical_open_interest_passed:
            failed_checks.append("historical_open_interest")
    if gate_quote_coverage_pct < float(min_quote_coverage_pct):
        failed_checks.append("quote_coverage")
    if gate_spread_to_ask > float(max_spread_to_ask):
        failed_checks.append("quote_spread_to_ask")
    if gate_cost_to_expected_edge_ratio > float(max_cost_to_expected_edge_ratio):
        failed_checks.append("cost_to_expected_edge_ratio")
    return {
        "passed": bool(availability_passed and quote_quality_passed),
        "availability_passed": availability_passed,
        "quote_quality_passed": quote_quality_passed,
        "failed_checks": failed_checks,
        "diagnostic_checks": diagnostic_checks,
        "availability_mode": availability_mode_value,
        "historical_chain_hard_required": bool(availability_mode_value != "vendor_limited_current_proxy"),
        "current_quote_proxy_available": current_quote_proxy_available,
        "gate_quote_coverage_pct": gate_quote_coverage_pct,
        "gate_spread_to_ask": gate_spread_to_ask,
        "gate_cost_to_expected_edge_ratio": gate_cost_to_expected_edge_ratio,
        "quote_quality_mode": "current_snapshot_proxy" if current_quote_proxy_available else "historical_window",
    }


def tradability_passes_thresholds(
    *,
    sample: OptionTradabilitySample,
    min_quote_coverage_pct: float,
    min_chain_coverage_pct: float,
    min_open_interest: int,
    max_spread_to_ask: float,
    max_cost_to_expected_edge_ratio: float,
    availability_mode: str = "strict_historical",
) -> bool:
    return bool(
        evaluate_tradability_thresholds(
            sample=sample,
            min_quote_coverage_pct=min_quote_coverage_pct,
            min_chain_coverage_pct=min_chain_coverage_pct,
            min_open_interest=min_open_interest,
            max_spread_to_ask=max_spread_to_ask,
            max_cost_to_expected_edge_ratio=max_cost_to_expected_edge_ratio,
            availability_mode=availability_mode,
        )["passed"]
    )


def _load_chain_snapshot(
    *,
    ticker: str,
    day: date,
    store: Optional[DataStore],
    cutemarkets_provider: Optional[CuteMarketsProvider],
    dte_min: int,
    dte_max: int,
    page_limit: int = 100,
    max_pages: int = 1,
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    as_of = datetime.combine(day, time(23, 59, 59))
    expiration_date_gte = (day + timedelta(days=max(int(dte_min), 0))).isoformat()
    expiration_date_lte = (day + timedelta(days=max(int(dte_max), 0))).isoformat()
    if store is not None:
        rows = list(store.get_option_chain_snapshot(ticker, as_of=as_of) or [])
        if rows:
            return rows, None
    if cutemarkets_provider is None:
        return [], None
    try:
        rows = list(
            cutemarkets_provider.fetch_option_chain_snapshot(
                ticker,
                as_of=day,
                limit=page_limit,
                paginate=bool(max_pages > 1),
                max_pages=max(int(max_pages), 1),
                expiration_date_gte=expiration_date_gte,
                expiration_date_lte=expiration_date_lte,
            )
            or []
        )
    except Exception as exc:
        return [], f"{type(exc).__name__}: {str(exc)[:200]}"
    if rows and store is not None:
        try:
            store.insert_option_chain(rows)
        except Exception:
            pass
    return rows, None


def _sample_current_snapshot_proxy(
    *,
    ticker: str,
    cutemarkets_provider: CuteMarketsProvider,
    expected_edge_pct: float,
    dte_min: int,
    dte_max: int,
    delta_min: float,
    delta_max: float,
    target_dte: int,
    target_abs_delta: float,
    max_target_contracts_per_day: int,
    end_day: date,
) -> OptionTradabilitySample:
    _ = end_day
    current_page_limit = 100
    reference_day = date.today()
    try:
        rows = list(
            cutemarkets_provider.fetch_option_chain_snapshot(
                ticker,
                as_of=None,
                limit=current_page_limit,
                paginate=False,
                expiration_date_gte=(reference_day + timedelta(days=max(int(dte_min), 0))).isoformat(),
                expiration_date_lte=(reference_day + timedelta(days=max(int(dte_max), 0))).isoformat(),
            )
            or []
        )
        fetch_error: Optional[str] = None
    except Exception as exc:
        rows = []
        fetch_error = f"{type(exc).__name__}: {str(exc)[:200]}"
    filtered = _filter_chain_rows(
        rows,
        day=reference_day,
        dte_min=dte_min,
        dte_max=dte_max,
        delta_min=delta_min,
        delta_max=delta_max,
    )
    targeted = _select_targeted_rows(
        filtered,
        target_dte=target_dte,
        target_abs_delta=target_abs_delta,
        max_rows=max(int(max_target_contracts_per_day or 1), 1),
    )
    quoted = [row for row in targeted if _quoted(row)]
    raw_rows_with_bid = sum(1 for row in rows if _has_bid(row))
    raw_rows_with_ask = sum(1 for row in rows if _has_ask(row))
    raw_rows_with_midpoint = sum(1 for row in rows if _has_midpoint(row))
    raw_rows_with_valid_quote = sum(1 for row in rows if _quoted(row))
    open_interest_values = [float(_safe_float(row.get("open_interest")) or 0.0) for row in targeted]
    volume_values = [float(_safe_float(row.get("volume")) or 0.0) for row in targeted]
    spread_to_mid_values: List[float] = []
    spread_to_ask_values: List[float] = []
    premium_values: List[float] = []
    for row in quoted:
        bid = _safe_float(row.get("bid"))
        ask = _safe_float(row.get("ask"))
        if bid is None or ask is None or ask <= 0.0 or ask < bid:
            continue
        mid = (bid + ask) / 2.0 if (bid + ask) > 0.0 else 0.0
        if mid > 0.0:
            spread_to_mid_values.append(max(ask - bid, 0.0) / mid)
        spread_to_ask_values.append(max(ask - bid, 0.0) / ask)
        premium_values.append(ask)
    median_spread_to_mid = _median_or_zero(spread_to_mid_values)
    median_spread_to_ask = _median_or_zero(spread_to_ask_values)
    estimated_round_trip_cost_pct = min(max(median_spread_to_mid, median_spread_to_ask) * 2.0, 5.0)
    estimated_cost_to_expected_edge_ratio = estimated_round_trip_cost_pct / max(float(expected_edge_pct), 1e-6)
    return OptionTradabilitySample(
        ticker=ticker,
        start_day=reference_day,
        end_day=reference_day,
        dte_min=int(dte_min),
        dte_max=int(dte_max),
        delta_min=float(delta_min),
        delta_max=float(delta_max),
        quote_coverage_pct=1.0 if quoted else 0.0,
        chain_coverage_pct=1.0 if targeted else 0.0,
        median_open_interest=_median_or_zero(open_interest_values),
        median_entry_volume=_median_or_zero(volume_values),
        median_spread_to_mid=median_spread_to_mid,
        median_spread_to_ask=median_spread_to_ask,
        median_premium_price=_median_or_zero(premium_values),
        sample_count=len(quoted) if quoted else len(targeted),
        estimated_round_trip_cost_pct=estimated_round_trip_cost_pct,
        estimated_cost_to_expected_edge_ratio=estimated_cost_to_expected_edge_ratio,
        days_evaluated=1 if rows or targeted else 0,
        days_with_chain=1 if targeted else 0,
        days_with_quotes=1 if quoted else 0,
        page_limit=current_page_limit,
        paginated=False,
        raw_chain_days=1 if rows else 0,
        raw_quote_days=1 if raw_rows_with_valid_quote > 0 else 0,
        raw_contract_count=len(rows),
        filtered_contract_count=len(filtered),
        raw_rows_with_bid=raw_rows_with_bid,
        raw_rows_with_ask=raw_rows_with_ask,
        raw_rows_with_midpoint=raw_rows_with_midpoint,
        raw_rows_with_valid_quote=raw_rows_with_valid_quote,
        fetch_error_count=1 if fetch_error else 0,
        fetch_error_examples=(fetch_error,) if fetch_error else (),
        sampling_mode="current_snapshot_proxy",
        sampling_reference_day=reference_day,
        current_quote_coverage_pct=1.0 if quoted else 0.0,
        current_chain_coverage_pct=1.0 if targeted else 0.0,
        current_median_open_interest=_median_or_zero(open_interest_values),
        current_median_entry_volume=_median_or_zero(volume_values),
        current_median_spread_to_mid=median_spread_to_mid,
        current_median_spread_to_ask=median_spread_to_ask,
        current_median_premium_price=_median_or_zero(premium_values),
        current_quote_sample_count=len(quoted) if quoted else len(targeted),
        current_raw_contract_count=len(rows),
        current_filtered_contract_count=len(filtered),
        current_raw_rows_with_bid=raw_rows_with_bid,
        current_raw_rows_with_ask=raw_rows_with_ask,
        current_raw_rows_with_midpoint=raw_rows_with_midpoint,
        current_raw_rows_with_valid_quote=raw_rows_with_valid_quote,
        current_estimated_round_trip_cost_pct=estimated_round_trip_cost_pct,
        current_estimated_cost_to_expected_edge_ratio=estimated_cost_to_expected_edge_ratio,
        current_sampling_mode="current_snapshot_proxy",
        current_sampling_reference_day=reference_day,
        current_note="current_quote_quality_proxy",
        note="historical_chain_sampling_unavailable_using_current_snapshot_proxy",
    )


def _filter_chain_rows(
    rows: Sequence[Dict[str, Any]],
    *,
    day: date,
    dte_min: int,
    dte_max: int,
    delta_min: float,
    delta_max: float,
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in rows:
        expiration_day = _coerce_day(row.get("expiration"))
        if expiration_day is None:
            continue
        dte = int((expiration_day - day).days)
        if dte < int(dte_min) or dte > int(dte_max):
            continue
        abs_delta = abs(float(row.get("delta") or 0.0)) if row.get("delta") is not None else None
        if abs_delta is not None and abs_delta > 0.0:
            if abs_delta < float(delta_min) or abs_delta > float(delta_max):
                continue
        out.append({**row, "dte": dte, "day": day})
    return out


def _select_targeted_rows(
    rows: Sequence[Dict[str, Any]],
    *,
    target_dte: int,
    target_abs_delta: float,
    max_rows: int,
) -> List[Dict[str, Any]]:
    if not rows:
        return []

    def _score(row: Dict[str, Any]) -> Tuple[float, float, float, float]:
        dte = int(row.get("dte") or 0)
        abs_delta = abs(float(row.get("delta") or 0.0)) if row.get("delta") is not None else target_abs_delta
        oi = float(_safe_float(row.get("open_interest")) or 0.0)
        volume = float(_safe_float(row.get("volume")) or 0.0)
        return (
            abs(dte - int(target_dte)),
            abs(abs_delta - float(target_abs_delta)),
            -oi,
            -volume,
        )

    ranked = sorted(rows, key=_score)
    return ranked[: max(int(max_rows or 1), 1)]


def _quoted(row: Dict[str, Any]) -> bool:
    bid = _safe_float(row.get("bid"))
    ask = _safe_float(row.get("ask"))
    return bool(bid is not None and ask is not None and ask > 0.0 and ask >= bid >= 0.0)


def _has_bid(row: Dict[str, Any]) -> bool:
    bid = _safe_float(row.get("bid"))
    return bool(bid is not None and bid > 0.0)


def _has_ask(row: Dict[str, Any]) -> bool:
    ask = _safe_float(row.get("ask"))
    return bool(ask is not None and ask > 0.0)


def _has_midpoint(row: Dict[str, Any]) -> bool:
    midpoint = _safe_float(row.get("midpoint"))
    return bool(midpoint is not None and midpoint > 0.0)


def _safe_float(value: Any) -> Optional[float]:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if out != out:
        return None
    return out


def _median_or_zero(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    return float(median(float(value) for value in values))


def _snapshot_signature(rows: Sequence[Dict[str, Any]]) -> str:
    if not rows:
        return ""
    first = rows[0]
    expiration_day = _coerce_day(first.get("expiration"))
    option_symbol = str(first.get("option_symbol") or "")
    return f"{option_symbol}|{expiration_day.isoformat() if expiration_day else ''}|{len(rows)}"


def _coerce_day(value: Any) -> Optional[date]:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
        except ValueError:
            return None
    return None
