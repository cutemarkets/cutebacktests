from __future__ import annotations

from bisect import bisect_left
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from functools import lru_cache
from math import ceil, floor, log1p, sqrt
import random
from statistics import pstdev
from time import perf_counter
from typing import Any, Callable, Dict, Iterator, List, Mapping, Optional, Sequence, Tuple
import uuid
from zoneinfo import ZoneInfo

from ..market_data_cache import MarketDataCacheBackend
from ..models import BacktestTrade
from .. import premarket_context as pmctx
from ..providers.alpaca import AlpacaDataProvider
from ..providers.cutemarkets import CuteMarketsProvider, _datetime_to_ns
from ..research.market_data_runtime import MarketDataRuntimeClient, PartitionHandle
from ..storage import DataStore
from ..research.options_tradability_sampler import (
    OptionTradabilitySample,
    sample_option_tradability,
    tradability_passes_thresholds,
)
from ..strategies.daily_forecasts import (
    COMBO_FAMILIES,
    DailyForecastConfig,
    DailyForecastSnapshot,
    OVERLAY_FAMILIES,
    _cap_value,
    build_combo_forecast_snapshot,
    build_daily_forecast_snapshot,
    bucket_members_for_ticker,
    daily_row_lookup,
    infer_asset_bucket,
)
from ..strategies.intraday import (
    IntradayStrategyConfig,
    _find_intraday_setup_with_audit,
    find_intraday_setup,
    resolve_dispersion_proxy_ticker,
    resolve_pairs_hedge_ticker,
    resolve_intraday_exit,
)
from ..strategies.regime import RegimeV2Config, classify_intraday_macro_regime
from ..strategies.surface_overlays import SurfaceOverlayDecision, apply_surface_overlay_to_forecast
from ..utils import parse_datetime, utcnow


_ET_ZONE = ZoneInfo("America/New_York")
_MISSING = object()
_MAX_CONTRACT_FETCH_PREFERENCE_CACHE_KEYS = 32
_MAX_CONTRACT_LIST_CACHE_KEYS = 64
_MAX_CONTRACT_UNIVERSE_CACHE_KEYS = 32
_MAX_CONTRACT_CANDIDATE_CACHE_KEYS = 64
_MAX_OPTION_CHAIN_SNAPSHOT_CACHE_KEYS = 16
_MAX_OPTION_CONTRACT_SNAPSHOT_CACHE_KEYS = 256
_MAX_OPTION_BAR_CACHE_KEYS = 16
_MAX_OPTION_QUOTE_CACHE_KEYS = 8
_MAX_OPTION_QUOTE_LOOKUP_CACHE_KEYS = 512
_MAX_OPTION_FIRST_HOUR_QUOTEABLE_CACHE_KEYS = 128
_MAX_CONTRACT_CANDIDATE_GROUP_CACHE_KEYS = 64
_OPTIONAL_AUXILIARY_TICKERS = frozenset({"I:VIX1D", "VIXY"})
_RUNTIME_IPC_ENABLED_BY_SOCKET: Dict[str, bool] = {}
_ET_WEEKDAY_CODES = {
    "MON": 0,
    "TUE": 1,
    "WED": 2,
    "THU": 3,
    "FRI": 4,
}
_OPTION_REJECTION_ALIAS_GROUPS = {
    "micro_entry_volume": ("microstructure_filter_rejected",),
    "micro_entry_range": ("microstructure_filter_rejected",),
    "micro_entry_price": ("microstructure_filter_rejected",),
    "micro_quote_spread": ("microstructure_filter_rejected",),
    "vertical_short_leg_missing": ("structure_filter_rejected",),
    "vertical_same_expiry_pair_missing": ("structure_filter_rejected",),
    "vertical_debit_to_width_ratio": ("structure_filter_rejected",),
    "vertical_combined_spread_to_debit_ratio": ("structure_filter_rejected",),
    "vertical_credit_long_leg_missing": ("structure_filter_rejected",),
    "vertical_credit_to_width_ratio": ("structure_filter_rejected",),
    "vertical_combined_spread_to_credit_ratio": ("structure_filter_rejected",),
    "vertical_credit_buffer_too_small": ("structure_filter_rejected",),
    "contract_open_interest_below_min": ("structure_filter_rejected",),
    "qty_below_1_after_caps": ("liquidity_cap_rejected", "sizing_rejected"),
    "entry_after_effective_exit": ("entry_fill_at_or_after_exit_rejected",),
    "entry_after_exit_fill": ("entry_fill_at_or_after_exit_rejected",),
}
_POST_SELECTION_RETRYABLE_MICRO_REJECTIONS = {
    "micro_entry_volume",
    "micro_entry_range",
    "micro_entry_bar_range",
    "micro_entry_price",
    "micro_quote_spread",
    "micro_entry_bar_missing",
}


def _mean_fast(values: Sequence[float]) -> float:
    count = len(values)
    if count <= 0:
        return 0.0
    return sum(float(value) for value in values) / float(count)

DEFAULT_USE_OPTION_QUOTES_FOR_FILLS = True
DEFAULT_OPTION_QUOTE_FILL_FALLBACK_TO_BAR_CLOSE = False


def _normalize_option_post_selection_conversion_mode(value: Any) -> str:
    mode = str(value or "disabled").strip().lower() or "disabled"
    if mode not in {
        "disabled",
        "retry_ranked_pool_v1",
        "retry_ranked_pool_quality_band_v1",
        "retry_same_expiry_quality_band_v1",
    }:
        raise ValueError(f"Unsupported option post-selection conversion mode: {mode}")
    return mode


def _clone_ranked_contract_pool(value: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return out
    for item in value:
        if isinstance(item, Mapping):
            out.append(dict(item))
    return out


def _selection_ranked_contract_pool(
    selection_meta: Optional[Mapping[str, Any]],
    selected_contract: Optional[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    pool = _clone_ranked_contract_pool((selection_meta or {}).get("ranked_pool"))
    if pool:
        return pool
    if isinstance(selected_contract, Mapping):
        selected = dict(selected_contract)
        if selected.get("_selection_rank") in (None, ""):
            selected["_selection_rank"] = 1
        return [selected]
    return []


def _selection_contract_rank(contract: Optional[Mapping[str, Any]], default_rank: int = 1) -> int:
    if not isinstance(contract, Mapping):
        return max(int(default_rank), 1)
    raw_rank = contract.get("_selection_rank")
    rank = int(raw_rank or 0) if raw_rank not in (None, "") else int(default_rank)
    return max(rank, 1)


def _selection_contract_strike_distance_steps(contract: Optional[Mapping[str, Any]]) -> Optional[int]:
    if not isinstance(contract, Mapping):
        return None
    raw_value = contract.get("_selection_strike_distance_steps")
    if raw_value in (None, ""):
        return None
    return int(raw_value or 0)


def _selection_contract_entry_bar_volume(contract: Optional[Mapping[str, Any]]) -> Optional[int]:
    if not isinstance(contract, Mapping):
        return None
    raw_value = contract.get("_selection_entry_bar_volume")
    if raw_value in (None, ""):
        return None
    return int(raw_value or 0)


def _selection_contract_quote_spread_pct(contract: Optional[Mapping[str, Any]]) -> Optional[float]:
    if not isinstance(contract, Mapping):
        return None
    return _safe_float(contract.get("_selection_quote_spread_pct"))


def _selection_contract_expiration_date_text(contract: Optional[Mapping[str, Any]]) -> str:
    if not isinstance(contract, Mapping):
        return ""
    parsed = parse_datetime(contract.get("expiration_date"))
    if isinstance(parsed, datetime):
        return parsed.date().isoformat()
    text = str(contract.get("expiration_date") or "").strip()
    return text[:10] if len(text) >= 10 else text


def _build_post_selection_contract_attempt_pool(
    *,
    ranked_contract_pool: Sequence[Mapping[str, Any]],
    selected_contract: Optional[Mapping[str, Any]],
    conversion_mode: str,
    max_alternates: int,
    max_final_rank: int,
    max_final_strike_distance_steps: int,
) -> List[Dict[str, Any]]:
    if conversion_mode == "disabled":
        return [dict(selected_contract)] if isinstance(selected_contract, Mapping) else []

    source_pool = _clone_ranked_contract_pool(ranked_contract_pool)
    if not source_pool and isinstance(selected_contract, Mapping):
        source_pool = [dict(selected_contract)]
    if not source_pool:
        return []

    initial_expiration_date = _selection_contract_expiration_date_text(selected_contract)
    filtered_pool: List[Dict[str, Any]] = []
    for idx, raw_contract in enumerate(source_pool):
        contract = dict(raw_contract)
        if idx > 0:
            contract_rank = _selection_contract_rank(contract, default_rank=idx + 1)
            if max_final_rank > 0 and contract_rank > max_final_rank:
                continue
            strike_distance_steps = _selection_contract_strike_distance_steps(contract)
            if (
                max_final_strike_distance_steps >= 0
                and strike_distance_steps is not None
                and strike_distance_steps > max_final_strike_distance_steps
            ):
                continue
            if conversion_mode == "retry_same_expiry_quality_band_v1":
                if not initial_expiration_date:
                    continue
                if _selection_contract_expiration_date_text(contract) != initial_expiration_date:
                    continue
        filtered_pool.append(contract)
        if len(filtered_pool) >= max_alternates + 1:
            break
    return filtered_pool


def _parse_allowed_weekdays_et(value: Any) -> Optional[set[int]]:
    text = str(value or "").strip()
    if not text:
        return None
    out: set[int] = set()
    for raw in text.split(","):
        code = str(raw or "").strip().upper()
        if not code:
            continue
        if code not in _ET_WEEKDAY_CODES:
            raise ValueError(f"Unsupported ET weekday code: {code}")
        out.add(_ET_WEEKDAY_CODES[code])
    return out or None


def _parse_allowed_trade_dates(value: Any) -> Optional[set[date]]:
    text = str(value or "").strip()
    if not text:
        return None
    out: set[date] = set()
    for raw in text.split(","):
        token = str(raw or "").strip()
        if not token:
            continue
        try:
            out.add(date.fromisoformat(token))
        except ValueError as exc:
            raise ValueError(f"Unsupported trade date token: {token}") from exc
    return out or None


def _normalize_option_chain_snapshot_enrichment_mode(value: Any) -> str:
    mode = str(value or "full").strip().lower() or "full"
    if mode not in {"off", "prior_oi_only", "full"}:
        raise ValueError(f"Unsupported option chain snapshot enrichment mode: {mode}")
    return mode


def _empty_option_funnel_counts() -> Dict[str, int]:
    return {
        "setups_found": 0,
        "setups_passed_signal_filters": 0,
        "setups_with_exit_plan": 0,
        "setups_after_trade_limits": 0,
        "historical_option_attempts": 0,
        "option_chain_available": 0,
        "contract_selected": 0,
        "entry_exit_bars_available": 0,
        "quote_fill_available": 0,
        "quote_fill_fallback_used": 0,
        "pricing_resolved": 0,
        "structure_filters_passed": 0,
        "microstructure_filters_passed": 0,
        "move_cost_filters_passed": 0,
        "sizing_passed": 0,
        "entry_constructed": 0,
        "trades_created": 0,
    }


def _empty_contract_lookup_cache_stats() -> Dict[str, int]:
    return {
        "fetch_preference_memory_hits": 0,
        "fetch_preference_persistent_hits": 0,
        "fetch_preference_persistent_writes": 0,
        "fetch_preference_persistent_write_skips": 0,
        "contract_list_memory_hits": 0,
        "contract_list_persistent_hits": 0,
        "contract_list_persistent_writes": 0,
        "contract_list_persistent_write_skips": 0,
        "contract_universe_memory_hits": 0,
        "contract_universe_persistent_hits": 0,
        "contract_universe_persistent_writes": 0,
        "contract_universe_persistent_write_skips": 0,
    }


def _empty_option_market_data_io_stats() -> Dict[str, Any]:
    return {
        "session_bars_total_seconds": 0.0,
        "option_chain_snapshot_total_seconds": 0.0,
        "option_quotes_total_seconds": 0.0,
        "option_bars_total_seconds": 0.0,
        "contract_list_total_seconds": 0.0,
        "duckdb_read_total_seconds": 0.0,
        "provider_fetch_total_seconds": 0.0,
        "session_bars_days_loaded": 0,
        "chain_snapshots_loaded": 0,
        "quote_days_loaded": 0,
        "bar_days_loaded": 0,
        "contract_list_days_loaded": 0,
        "duckdb_read_calls": 0,
        "provider_fetch_calls": 0,
    }


def _empty_daily_funnel_counts() -> Dict[str, int]:
    return {
        "daily_snapshot_missing": 0,
        "daily_signal_days": 0,
        "daily_nonzero_forecast_days": 0,
        "daily_zero_direction_days": 0,
        "daily_underlying_price_missing": 0,
        "daily_overlay_vetoes": 0,
        "daily_tradability_gate_failed": 0,
        "daily_tradability_gate_bypassed": 0,
        "daily_entry_attempts": 0,
        "daily_contract_pool_available": 0,
        "daily_contract_selection_failed": 0,
        "daily_contract_selected": 0,
        "daily_tradability_gate_passed": 0,
        "daily_quote_gate_passed": 0,
        "daily_entry_pricing_failed": 0,
        "daily_structure_gate_failed": 0,
        "daily_move_cost_gate_failed": 0,
        "daily_sizing_passed": 0,
        "daily_sizing_failed": 0,
        "daily_entry_created": 0,
        "daily_position_opened": 0,
        "daily_exit_created": 0,
        "daily_exit_pricing_failed": 0,
        "daily_trades_closed": 0,
    }


@dataclass
class _DailyHistoryAnalytics:
    rows: List[Dict[str, Any]]
    days: List[date]
    _atr_prefix_cache: Dict[int, List[Optional[float]]]

    @classmethod
    def from_rows(cls, rows: List[Dict[str, Any]]) -> "_DailyHistoryAnalytics":
        normalized: List[Dict[str, Any]] = []
        for row in rows:
            ts = row.get("ts")
            if not isinstance(ts, datetime):
                continue
            normalized_row = dict(row)
            normalized_row["ts"] = _as_utc_naive(ts)
            normalized.append(normalized_row)
        normalized.sort(key=lambda row: row["ts"])
        return cls(
            rows=normalized,
            days=[_as_et(row["ts"]).date() for row in normalized],
            _atr_prefix_cache={},
        )

    def _prefix_index(self, day: date) -> int:
        return bisect_left(self.days, day)

    def previous_close(self, day: date) -> Optional[float]:
        idx = self._prefix_index(day)
        if idx < 1:
            return None
        close = _safe_float(self.rows[idx - 1].get("close"))
        if close is None or close <= 0:
            return None
        return close

    def previous_bar(self, day: date, lookback: int = 1) -> Optional[Dict[str, Any]]:
        if lookback < 1:
            return None
        idx = self._prefix_index(day)
        if idx < lookback:
            return None
        return self.rows[idx - lookback]

    def atr(self, day: date, lookback_days: int) -> Optional[float]:
        if lookback_days < 2:
            return None
        prefix = self._atr_prefix(lookback_days)
        idx = self._prefix_index(day)
        if idx >= len(prefix):
            return prefix[-1] if prefix else None
        return prefix[idx]

    def avg_daily_volume(self, day: date, lookback_days: int = 20) -> Optional[float]:
        idx = self._prefix_index(day)
        if idx < 1:
            return None
        window = self.rows[max(0, idx - lookback_days):idx]
        vols = [float(r.get("volume") or 0.0) for r in window if (r.get("volume") or 0) > 0]
        return sum(vols) / len(vols) if vols else None

    def avg_daily_volume_ratio(
        self,
        day: date,
        *,
        fast_lookback_days: int = 5,
        slow_lookback_days: int = 20,
    ) -> Optional[float]:
        fast_avg = self.avg_daily_volume(day=day, lookback_days=fast_lookback_days)
        slow_avg = self.avg_daily_volume(day=day, lookback_days=slow_lookback_days)
        if fast_avg is None or slow_avg is None or slow_avg <= 0.0:
            return None
        return float(fast_avg) / float(slow_avg)

    def _atr_prefix(self, lookback_days: int) -> List[Optional[float]]:
        cached = self._atr_prefix_cache.get(lookback_days)
        if cached is not None:
            return cached

        max_daily_move_fraction = 0.50
        prefix: List[Optional[float]] = [None]
        true_ranges: List[float] = []
        prev_close: Optional[float] = None

        for idx, row in enumerate(self.rows, start=1):
            high = float(row.get("high") or 0.0)
            low = float(row.get("low") or 0.0)
            close = float(row.get("close") or 0.0)
            if high > 0 and low > 0 and close > 0 and high > low:
                base_price = close if prev_close is None else prev_close
                if base_price > 0:
                    max_move = max(high - low, abs(high - base_price), abs(low - base_price))
                    if (max_move / base_price) <= max_daily_move_fraction:
                        tr = (high - low) if prev_close is None else max(
                            high - low,
                            abs(high - prev_close),
                            abs(low - prev_close),
                        )
                        true_ranges.append(tr)
                    prev_close = close
            current_atr: Optional[float] = None
            if idx >= (lookback_days + 1) and len(true_ranges) >= lookback_days:
                current_atr = _mean_fast(true_ranges[-lookback_days:])
            prefix.append(current_atr)

        self._atr_prefix_cache[lookback_days] = prefix
        return prefix


@dataclass(frozen=True)
class _SessionAnalytics:
    opening_volume_by_day: Dict[date, float]
    opening_width_by_day: Dict[date, float]
    volume_days: List[date]
    volume_prefix: List[float]

    @classmethod
    def from_session_cache(
        cls,
        session_cache: Dict[date, List[Dict[str, Any]]],
        opening_range_minutes: int,
    ) -> "_SessionAnalytics":
        opening_volume_by_day: Dict[date, float] = {}
        opening_width_by_day: Dict[date, float] = {}
        for day, rows in sorted(session_cache.items()):
            opening_volume = IntradayOptionsBacktester._opening_range_volume(rows, opening_range_minutes)
            if opening_volume is not None:
                opening_volume_by_day[day] = float(opening_volume)
            opening_width = IntradayOptionsBacktester._opening_range_width_pct(rows, opening_range_minutes)
            if opening_width is not None:
                opening_width_by_day[day] = float(opening_width)

        volume_days = sorted(opening_volume_by_day)
        volume_prefix: List[float] = [0.0]
        running = 0.0
        for day in volume_days:
            running += float(opening_volume_by_day[day])
            volume_prefix.append(running)
        return cls(
            opening_volume_by_day=opening_volume_by_day,
            opening_width_by_day=opening_width_by_day,
            volume_days=volume_days,
            volume_prefix=volume_prefix,
        )

    def relative_opening_volume(self, day: date, lookback_days: int) -> Optional[float]:
        current_volume = self.opening_volume_by_day.get(day)
        effective_lookback = max(int(lookback_days), 1)
        if current_volume is None or current_volume <= 0.0:
            return None
        idx = bisect_left(self.volume_days, day)
        if idx >= len(self.volume_days) or self.volume_days[idx] != day:
            return None
        if idx < effective_lookback:
            return None
        history_sum = self.volume_prefix[idx] - self.volume_prefix[idx - effective_lookback]
        history_avg = history_sum / float(effective_lookback)
        if history_avg <= 0.0:
            return None
        return float(current_volume) / float(history_avg)

    def opening_width_pct(self, day: date) -> Optional[float]:
        return self.opening_width_by_day.get(day)


@dataclass(frozen=True)
class _ContractCandidate:
    strike: float
    expiration_day: date
    open_interest: int
    contract: Dict[str, Any]


@dataclass
class _OptionChainSnapshotIndex:
    by_symbol: Dict[str, Dict[str, Any]]
    by_triplet: Dict[Tuple[str, float, str], Dict[str, Any]]


@dataclass
class _OptionQuoteIndex:
    valid_quotes: List[Dict[str, Any]]
    valid_quote_timestamps_utc: List[datetime]
    fallback_last_quote: Optional[Dict[str, Any]]


@dataclass
class _GroupedContractCandidates:
    ascending_by_expiration: Dict[date, List[_ContractCandidate]]
    descending_by_expiration: Dict[date, List[_ContractCandidate]]


@dataclass
class _DailyOptionPosition:
    option_symbol: str
    side: str
    direction: int
    qty: int
    entry_day: date
    entry_ts: datetime
    entry_price: float
    entry_underlying: float
    entry_forecast: float
    forecast_family: str
    option_type: str
    expiration_day: date
    strike: float
    delta_abs: float
    premium_at_risk_pct_nav: float
    risk_budget_share: float
    overlay: Dict[str, Any]
    metadata: Dict[str, Any]


@dataclass
class IntradayOptionsBacktestConfig:
    start: datetime
    end: datetime
    ticker: str = "SPY"

    initial_equity: float = 100000.0
    risk_per_trade: float = 0.02
    max_trades_per_day: int = 1
    instrument_mode: str = "options"  # options | stocks

    option_mode: str = "auto"  # auto | historical | proxy
    option_contract_status: str = "inactive"
    option_min_dte: int = 0
    option_target_dte: int = 1
    option_max_dte: int = 7
    option_min_open_interest: int = 0
    require_option_microstructure_filter: bool = False
    option_min_entry_volume: int = 0
    option_max_entry_bar_range_pct: float = 1.0
    option_min_entry_price: float = 0.0
    option_structure_filter_enabled: bool = False
    option_structure_min_open_interest: int = 0
    option_structure_min_entry_volume: int = 0
    option_structure_max_entry_spread_pct: float = 1.0
    option_structure_max_entry_bar_range_pct: float = 1.0
    option_structure_min_entry_price: float = 0.0
    enforce_option_liquidity_caps: bool = False
    option_max_entry_volume_participation: float = 1.0
    option_max_open_interest_participation: float = 1.0
    option_range_adverse_fill_fraction: float = 0.0
    option_range_adverse_fill_max_bps: float = 0.0
    use_option_quotes_for_fills: bool = DEFAULT_USE_OPTION_QUOTES_FOR_FILLS
    option_quote_fill_fallback_to_bar_close: bool = DEFAULT_OPTION_QUOTE_FILL_FALLBACK_TO_BAR_CLOSE
    option_max_entry_spread_pct: float = 1.0
    option_take_profit_pct: float = 0.0
    option_max_loss_pct: float = 0.0
    option_use_contract_open_interest: bool = False
    option_selection_use_quote_spread: bool = False
    option_selection_quote_top_n: int = 8
    option_selection_spread_weight: float = 10.0
    option_selection_max_quote_spread_pct: float = 0.35
    option_selection_max_quote_spread_abs: float = 0.0
    option_selection_min_quote_ask: float = 0.0
    option_selection_spread_to_ask_weight: float = 0.0
    option_selection_max_spread_to_ask_ratio: float = 1.0
    option_selection_intrinsic_weight: float = 0.0
    option_selection_min_intrinsic_share: float = 0.0
    option_selection_delta_weight: float = 0.0
    option_selection_target_abs_delta: float = 0.0
    option_selection_min_abs_delta: float = 0.0
    option_selection_max_abs_delta: float = 1.0
    option_selection_delta_fallback_mode: str = "strict"
    option_selection_local_itm_steps: int = 0
    option_selection_local_otm_steps: int = 0
    option_selection_entry_bar_volume_weight: float = 0.0
    option_selection_quote_mode: str = "legacy"
    option_selection_quote_fallback_last: bool = True
    option_chain_snapshot_enrichment_mode: str = "full"
    option_min_expected_move_to_extrinsic_ratio: float = 0.0
    option_min_expected_move_to_spread_ratio: float = 0.0
    option_min_expected_move_to_debit_ratio: float = 0.0
    option_structure_mode: str = "single_leg"
    option_vertical_short_leg_steps: int = 1
    option_vertical_fallback_short_leg_steps: int = 2
    option_vertical_max_debit_to_width_ratio: float = 0.70
    option_vertical_min_short_bid: float = 0.10
    option_vertical_max_combined_spread_to_debit_ratio: float = 0.35
    option_vertical_credit_long_leg_steps: int = 1
    option_vertical_credit_fallback_long_leg_steps: int = 2
    option_vertical_min_credit_to_width_ratio: float = 0.0
    option_vertical_max_credit_to_width_ratio: float = 1.0
    option_vertical_max_combined_spread_to_credit_ratio: float = 1.0
    option_credit_min_short_bid: float = 0.0
    option_credit_min_short_strike_buffer_pct: float = 0.0
    option_credit_min_expected_move_buffer_ratio: float = 0.0
    option_credit_min_entry_credit: float = 0.0
    option_credit_take_profit_capture_pct: float = 0.0
    option_credit_stop_loss_multiple: float = 0.0
    proxy_option_leverage: float = 7.5
    option_sizing_include_commission: bool = True
    option_sizing_min_entry_price: float = 0.05
    option_risk_sizing_mode: str = "premium_at_risk"
    signal_cadence: str = "intraday"
    strategy_sleeve: str = "tactical_intraday"
    asset_bucket: str = ""
    forecast_group: str = ""
    forecast_family: str = ""
    lookback_fast: int = 16
    lookback_slow: int = 64
    lookback_breakout: int = 40
    lookback_relative: int = 63
    forecast_cap: float = 20.0
    vol_attenuation_enabled: bool = False
    vol_percentile_lookback: int = 252
    vol_attenuation_hi_pct: float = 80.0
    vol_attenuation_extreme_pct: float = 90.0
    forecast_weight: float = 1.0
    portfolio_target_vol_annualized: float = 0.10
    premium_at_risk_pct_nav_cap: float = 0.0035
    total_premium_at_risk_pct_nav_cap: float = 0.025
    risk_budget_share: float = 1.0
    max_calendar_hold_days: int = 30
    option_microstructure_gate_mode: str = "absolute"
    option_post_selection_conversion_mode: str = "disabled"
    option_post_selection_max_alternates: int = 0
    option_post_selection_max_final_rank: int = 0
    option_post_selection_max_final_strike_distance_steps: int = -1
    option_tradability_availability_mode: str = "strict_historical"
    option_min_quote_coverage_pct: float = 0.0
    option_min_chain_coverage_pct: float = 0.0
    option_liquidity_sampling_days: int = 90
    option_cost_speed_limit_ratio: float = 1.0
    option_tradeable_after_sample_days: int = 1
    audit_disable_daily_tradability_gate: bool = False
    audit_relax_daily_contract_selection: bool = False
    overlay_enabled: bool = False
    overlay_ivrv_scale_down_zscore: float = 1.0
    overlay_ivrv_scale_up_zscore: float = -0.5
    overlay_ivrv_scale_down_multiplier: float = 0.50
    overlay_ivrv_scale_up_multiplier: float = 1.15
    overlay_term_structure_veto_threshold: float = 0.04
    overlay_skew_veto_threshold: float = 0.12
    hybrid_core_weight: float = 0.70
    hybrid_overlay_weight: float = 0.20
    hybrid_tactical_weight: float = 0.10
    hybrid_tactical_profiles: str = ""

    # WARNING: 0.0 produces a frictionless option backtest. Set to a realistic
    # bid-ask spread estimate (e.g. 30–100 bps depending on liquidity) before
    # drawing real-money conclusions from option P&L.
    option_slippage_bps: float = 0.0
    option_commission_per_contract: float = 0.0
    execution_entry_delay_minutes: int = 0
    execution_exit_delay_minutes: int = 0
    execution_delay_randomization: bool = True
    execution_entry_delay_jitter_minutes: int = 2
    execution_exit_delay_jitter_minutes: int = 2
    execution_delay_random_seed: int = 42
    execution_timing_model: str = "bar_open"  # bar_open | live_poll
    execution_poll_seconds: int = 30
    execution_entry_signal_confirm_seconds: int = 0
    execution_exit_signal_confirm_seconds: int = 0
    execution_entry_fill_latency_seconds: int = 0
    execution_exit_fill_latency_seconds: int = 0
    runtime_mode: str = "legacy_local"
    runtime_socket: str = ""
    runtime_require_ipc: bool = False
    profiling_mode: str = "off"
    leakage_fail_severity: str = "off"
    persist_fetched_market_data: bool = True
    persist_option_contract_lookup_cache: bool = True
    persist_trades: bool = True
    return_trade_log: bool = False
    enable_underlying_shadow_mode: bool = False

    opening_range_minutes: int = 5
    entry_start_time: str = "09:35"
    entry_cutoff_time: str = "12:00"
    exit_time: str = "15:55"
    allowed_weekdays_et: str = ""
    allowed_trade_dates_csv: str = ""
    strategy_variant: str = (
        "orb_qc"  # orb_qc | orb_momentum_v1 | orb_trend_pullback_v1 | orb_event_drive_v1 | orb_transition_compression_v1 | orb_trend_short | orb_failure_fade | orb_fib_pullback | mr_vwap_revert_v1 | mr_vwap_zscore_v2 | mr_overnight_regime_v1
    )

    allow_long: bool = True
    allow_short: bool = True
    use_opening_bar_direction: bool = False
    require_breakout_open_inside_range: bool = True
    entry_trigger_mode: str = "close_breakout"  # close_breakout | stop_touch

    stop_mode: str = "range"  # range | breakout_candle | opening_bar_atr
    stop_loss_atr_distance: float = 1.0
    take_profit_rr: float = 0.0
    break_even_trigger_rr: float = 0.0
    exit_on_opposite_candle: bool = False
    opposite_candle_min_hold_minutes: int = 0
    early_fail_minutes: int = 0
    early_fail_min_rr: float = 0.0
    max_hold_minutes: int = 0
    fib_entry_level_low: float = 0.5
    fib_entry_level_high: float = 0.618
    fib_target_extension: float = 1.444
    fib_require_confirmation: bool = True
    mr_band_or_mult: float = 1.0
    mr_min_distance_from_vwap_pct: float = 0.0
    mr_reentry_buffer_or_mult: float = 0.1
    mr_stop_buffer_or_mult: float = 0.15
    mr_take_profit_mode: str = "vwap"  # vwap | rr | none | zscore
    mr_take_profit_rr: float = 1.0
    mr_require_reversal_candle: bool = True
    mr_zscore_window: int = 20
    mr_zscore_entry: float = 1.6
    mr_zscore_reentry: float = 0.8
    mr_zscore_stop: float = 2.4
    mr_zscore_target: float = 0.25
    mr_sigma_min_pct: float = 0.0
    mr_sigma_max_pct: float = 1.0
    mr_vwap_slope_lookback: int = 3
    mr_vwap_slope_max_pct: float = 1.0
    mr_overnight_abs_return_min: float = 0.004
    mr_overnight_close_to_range_extreme_pct: float = 0.2
    mr_overnight_efficiency_ratio_max: float = 0.45
    mr_overnight_min_session_range_pct: float = 0.003
    mr_adaptive_enabled: bool = False
    mr_adaptive_entry_min: float = 1.2
    mr_adaptive_entry_max: float = 2.4
    mr_adaptive_stop_min: float = 2.0
    mr_adaptive_stop_max: float = 3.2
    mr_adaptive_trend_weight: float = 0.65
    mr_adaptive_vol_weight: float = 0.35
    mr_session_extension_min_or_frac: float = 0.0
    mr_reversal_body_min_frac: float = 0.0
    mr_reversal_wick_min_frac: float = 0.0
    mr_trend_ema_spread_max_pct: float = 1.0
    mr_volume_climax_multiple_min: float = 0.0
    mr_trend_day_max_move_pct: float = 1.0
    mr_time_to_work_bars: int = 0
    mr_time_to_work_min_rr: float = 0.0
    mr_target_stretch_frac: float = 0.0
    pairs_hedge_ticker: str = "AUTO"
    pairs_beta_lookback: int = 24
    pairs_zscore_window: int = 48
    pairs_zscore_entry: float = 1.8
    pairs_zscore_reentry: float = 0.8
    pairs_zscore_exit: float = 0.25
    pairs_zscore_stop: float = 2.8
    pairs_min_correlation: float = 0.15
    pairs_excluded_tickers: str = "TQQQ,SQQQ"
    dispersion_proxy_ticker: str = "AUTO"
    dispersion_beta_lookback: int = 24
    dispersion_zscore_window: int = 36
    dispersion_zscore_entry: float = 1.8
    dispersion_zscore_reentry: float = 0.8
    dispersion_zscore_exit: float = 0.25
    dispersion_zscore_stop: float = 2.8
    dispersion_min_correlation: float = 0.10
    dispersion_rel_strength_entry_pct: float = 0.003
    dispersion_rel_strength_exit_pct: float = 0.001
    dispersion_rel_strength_stop_pct: float = 0.006
    dispersion_primary_min_abs_move_pct: float = 0.0025
    dispersion_proxy_max_abs_move_pct: float = 0.012
    dispersion_rel_strength_confirm_pct: float = 0.0
    dispersion_zscore_improvement_min: float = 0.0
    dispersion_reversal_body_min_frac: float = 0.0
    dispersion_reversal_wick_min_frac: float = 0.0
    dispersion_beta_shock_max_pct: float = 1.0
    dispersion_time_to_work_bars: int = 0
    dispersion_time_to_work_improvement_min: float = 0.0
    dispersion_breakout_rel_strength_floor_frac: float = 0.0
    trend_pullback_max_bars_after_breakout: int = 8
    trend_pullback_ema_buffer_pct: float = 0.0015
    trend_pullback_require_orb_reclaim: bool = True
    trend_pullback_min_breakout_or_frac: float = 0.05
    trend_pullback_min_volume_multiple: float = 1.2
    drive_min_abs_return_pct: float = 0.004
    drive_close_location_min: float = 0.65
    drive_pullback_min_retrace_frac: float = 0.15
    drive_pullback_max_retrace_frac: float = 0.65
    drive_touch_ma_buffer_pct: float = 0.0015
    drive_reclaim_close_location_min: float = 0.55
    drive_reclaim_min_volume_multiple: float = 0.9
    drive_pullback_require_hold_drive_open: bool = True
    drive_reclaim_requires_prev_extreme_break: bool = True
    drive_stop_buffer_range_frac: float = 0.05
    drive_max_pullback_bars: int = 8
    event_gap_abs_return: float = 0.0
    event_gap_direction: int = 0
    event_drive_min_gap_abs_return: float = 0.006
    event_drive_min_breakout_or_frac: float = 0.10
    event_drive_close_location_min: float = 0.60
    event_drive_min_volume_multiple: float = 1.3
    compression_lookback_bars: int = 5
    compression_max_range_pct: float = 0.0025
    compression_breakout_buffer_or_frac: float = 0.03
    compression_min_volume_multiple: float = 1.2
    momentum_breakout_min_or_frac: float = 0.05
    momentum_breakout_max_or_frac: float = 10.0
    momentum_close_location_min: float = 0.55
    momentum_min_ema_spread_pct: float = 0.0
    momentum_pullback_to_ema_max_pct: float = 0.02
    momentum_confirmation_bars: int = 1
    momentum_volume_multiple_min: float = 1.0
    momentum_min_body_or_frac: float = 0.0
    momentum_max_opposite_wick_body_ratio: float = 100.0
    momentum_atr_range_min: float = 0.0
    momentum_trend_bars_min: int = 1
    momentum_adx_period: int = 14
    momentum_adx_min: float = 0.0
    max_positions: int = 20
    stop_loss_risk_size: float = 0.01
    stock_slippage_bps: float = 0.0
    stock_commission_per_share: float = 0.0

    require_relative_volume: bool = True
    relative_volume_min: float = 1.0
    relative_volume_max: float = 0.0
    relative_volume_lookback_days: int = 14
    require_premarket_context: bool = False
    premarket_bars_min: int = 0
    premarket_volume_pct_adv_min: float = 0.0
    premarket_gap_abs_return_min: float = 0.0
    premarket_range_min_pct: float = 0.0
    premarket_range_max_pct: float = 1000.0
    recent_daily_volume_ratio_min: float = 0.0
    require_atr_filter: bool = False
    atr_lookback_days: int = 14
    atr_min: float = 0.0

    volume_ma_window: int = 20
    volume_spike_multiple: float = 1.2
    trend_ema_fast: int = 20
    trend_ema_slow: int = 50
    require_fvg: bool = False
    require_volume_spike: bool = False
    require_trend_alignment: bool = False
    require_or_width_filter: bool = False
    opening_range_min_width_pct: float = 0.0
    opening_range_max_width_pct: float = 1.0
    require_macro_release_filter: bool = False
    macro_release_times_et: str = "10:00"
    macro_post_release_block_minutes: int = 15

    require_prior_day_inside_bar: bool = False
    require_prior_day_range_filter: bool = False
    prior_day_range_max_pct: float = 1.0

    require_vol_regime_filter: bool = False
    vol_regime_ticker: str = "I:VIX1D"
    vol_regime_proxy_ticker: str = "VIXY"
    vol_regime_min: float = 0.0
    vol_regime_max: float = 1000.0

    regime_gate_enabled: bool = False
    regime_gate_model: str = "threshold"
    regime_gate_allowed_labels: str = "trending,neutral"
    regime_day_map: Optional[Dict[date, str]] = None

    regime_v2_enabled: bool = False
    regime_v2_router_enabled: bool = False
    regime_v2_router_mode: str = "core"
    regime_v2_min_confidence: float = 0.35
    regime_v2_router_trend_up_min_confidence: float = 0.0
    regime_v2_router_trend_down_min_confidence: float = 0.0
    regime_v2_router_range_low_vol_min_confidence: float = 0.0
    regime_v2_router_high_rv_min: float = 1.15
    regime_v2_router_trend_up_rv_max: float = 1.30
    regime_v2_router_trend_down_rv_max: float = 1.35
    regime_v2_router_trend_up_entry_bar_range_min_pct: float = 0.04
    regime_v2_router_trend_down_entry_bar_range_min_pct: float = 0.04
    regime_v2_router_low_confidence_mr_rv_max: float = 1.15
    regime_v2_router_low_confidence_mr_entry_bar_range_max_pct: float = 0.03
    regime_v2_router_low_confidence_skip_rv_min: float = 1.60
    regime_v2_router_low_confidence_skip_entry_bar_range_min_pct: float = 0.06
    regime_v2_router_trend_up_overlay_compression_max_range_pct: float = 0.0030
    regime_v2_router_trend_up_overlay_option_max_entry_bar_range_pct: float = 0.06
    regime_v2_router_event_gap_tight_entry_bar_range_max_pct: float = 0.01
    regime_v2_router_event_gap_mid_rv_min: float = 1.0
    regime_v2_router_event_gap_mid_rv_max: float = 2.0
    regime_v2_router_event_gap_mid_entry_bar_range_max_pct: float = 0.025
    regime_v2_router_event_gap_overlay_compression_max_range_pct: float = 0.0030
    regime_v2_router_event_gap_overlay_option_max_entry_bar_range_pct: float = 0.06
    regime_v2_router_range_low_vol_tight_rv_max: float = 0.95
    regime_v2_router_range_low_vol_tight_entry_bar_range_max_pct: float = 0.005
    regime_v2_router_transition_high_rv_min: float = 2.0
    regime_v2_router_transition_wide_entry_bar_range_min_pct: float = 0.05
    regime_v2_intraday_er_trend_min: float = 0.45
    regime_v2_intraday_er_sideways_max: float = 0.20
    regime_v2_intraday_direction_abs_return_min: float = 0.001
    regime_v2_range_low_vol_max_pct: float = 0.012
    regime_v2_range_high_vol_min_pct: float = 0.020
    regime_v2_event_gap_abs_return_min: float = 0.006
    regime_v2_event_gap_min_range_pct: float = 0.004


class IntradayOptionsBacktester:
    def __init__(
        self,
        store: DataStore,
        cutemarkets_provider: Optional[CuteMarketsProvider] = None,
        alpaca_data_provider: Optional[AlpacaDataProvider] = None,
        market_data_cache_backend: Optional[MarketDataCacheBackend] = None,
    ):
        self.store = store
        self.cutemarkets_provider = cutemarkets_provider
        self.alpaca_data_provider = alpaca_data_provider
        self.market_data_cache_backend = market_data_cache_backend
        self._contract_cache: Dict[Tuple[Any, ...], Optional[Dict[str, Any]]] = {}
        self._contract_selection_meta_cache: Dict[Tuple[Any, ...], Dict[str, Any]] = {}
        self._contract_list_cache: Dict[Tuple[Any, ...], List[Dict[str, Any]]] = {}
        self._contract_universe_cache: Dict[Tuple[Any, ...], List[Dict[str, Any]]] = {}
        self._contract_candidate_cache: Dict[Tuple[Any, ...], List[_ContractCandidate]] = {}
        self._contract_candidate_group_cache: Dict[Tuple[Any, ...], _GroupedContractCandidates] = {}
        self._contract_fetch_preference_cache: Dict[Tuple[Any, ...], Tuple[str, str]] = {}
        self._option_chain_snapshot_cache: Dict[Tuple[str, date], List[Dict[str, Any]]] = {}
        self._option_chain_snapshot_index_cache: Dict[Tuple[str, date], _OptionChainSnapshotIndex] = {}
        self._option_contract_snapshot_cache: Dict[Tuple[str, str, date], Optional[Dict[str, Any]]] = {}
        self._option_bar_cache: Dict[Tuple[str, date], List[Dict[str, Any]]] = {}
        self._option_quote_cache: Dict[Tuple[str, date], List[Dict[str, Any]]] = {}
        self._option_quote_probe_cache: Dict[Tuple[str, date, datetime, bool], Optional[Dict[str, Any]]] = {}
        self._option_quote_index_cache: Dict[Tuple[str, date], _OptionQuoteIndex] = {}
        self._option_quote_lookup_cache: Dict[Tuple[str, date, str, bool], Optional[Dict[str, Any]]] = {}
        self._option_first_hour_quoteable_cache: Dict[Tuple[str, date], bool] = {}
        self._session_bar_cache: Dict[Tuple[str, date], List[Dict[str, Any]]] = {}
        self._daily_bar_range_cache: Dict[Tuple[str, date, date], List[Dict[str, Any]]] = {}
        self._selection_quote_prefetch_cache: set[Tuple[date, Tuple[str, ...]]] = set()
        self._historical_option_quotes_supported: Optional[bool] = None
        self._option_rejection_counts: Dict[str, int] = {}
        self._option_funnel_counts: Dict[str, int] = _empty_option_funnel_counts()
        self._option_attempt_log: List[Dict[str, Any]] = []
        self._daily_funnel_counts: Dict[str, int] = _empty_daily_funnel_counts()
        self._contract_lookup_cache_stats: Dict[str, int] = _empty_contract_lookup_cache_stats()
        self._option_market_data_io_stats: Dict[str, Any] = _empty_option_market_data_io_stats()
        self._last_option_rejection_reason: str = ""
        self._last_contract_selection_reason: str = ""
        self._last_contract_selection_meta: Dict[str, Any] = {}
        self._premarket_bar_cache: Dict[Tuple[str, date], List[Dict[str, Any]]] = {}
        self._premarket_source_cache: Dict[Tuple[str, date], str] = {}
        self._lfcm_ticker_details_cache: Dict[str, Dict[str, Any]] = {}
        self._lfcm_news_cache: Dict[Tuple[str, date], List[str]] = {}
        self._optional_aux_provider_denials: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
        store_is_read_only = bool(getattr(store, "read_only", False))
        self._persist_fetched_market_data: bool = not store_is_read_only
        self._persist_option_contract_lookup_cache: bool = not store_is_read_only
        self._runtime_mode: str = "legacy_local"
        self._runtime_socket: str = ""
        self._runtime_client: Optional[MarketDataRuntimeClient] = None
        self._runtime_handle_cache: Dict[str, PartitionHandle] = {}
        self._runtime_require_ipc: bool = False
        self._profiling_mode: str = "off"
        self._profiling_trace: Dict[str, Any] = {
            "stage_seconds": {},
            "stage_counts": {},
        }

    @staticmethod
    def _set_bounded_cache_entry(
        cache: Dict[Tuple[Any, ...], Any],
        key: Tuple[Any, ...],
        value: Any,
        *,
        max_entries: int,
    ) -> None:
        if key in cache:
            cache.pop(key, None)
        cache[key] = value
        limit = max(int(max_entries), 0)
        while limit > 0 and len(cache) > limit:
            cache.pop(next(iter(cache)))

    def _reset_option_rejection_counts(self) -> None:
        self._option_rejection_counts = {}

    def _reset_option_funnel_counts(self) -> None:
        self._option_funnel_counts = _empty_option_funnel_counts()

    def _reset_option_attempt_log(self) -> None:
        self._option_attempt_log = []

    def _reset_daily_funnel_counts(self) -> None:
        self._daily_funnel_counts = _empty_daily_funnel_counts()

    def _reset_contract_lookup_cache_stats(self) -> None:
        self._contract_lookup_cache_stats = _empty_contract_lookup_cache_stats()

    def _reset_option_market_data_io_stats(self) -> None:
        self._option_market_data_io_stats = _empty_option_market_data_io_stats()

    def _bump_contract_lookup_cache_stat(self, key: str, amount: int = 1) -> None:
        normalized = str(key or "").strip()
        if not normalized:
            return
        self._contract_lookup_cache_stats[normalized] = (
            int(self._contract_lookup_cache_stats.get(normalized, 0)) + int(amount)
        )

    def _bump_option_market_data_io_stat(self, key: str, amount: Any) -> None:
        normalized = str(key or "").strip()
        if not normalized:
            return
        current = self._option_market_data_io_stats.get(normalized, 0)
        if isinstance(current, float) or isinstance(amount, float):
            self._option_market_data_io_stats[normalized] = float(current or 0.0) + float(amount or 0.0)
            return
        self._option_market_data_io_stats[normalized] = int(current or 0) + int(amount or 0)

    def _record_option_market_data_io(
        self,
        *,
        dataset: str,
        total_seconds: float = 0.0,
        duckdb_seconds: float = 0.0,
        provider_seconds: float = 0.0,
        loaded_count: int = 0,
        duckdb_calls: int = 0,
        provider_calls: int = 0,
    ) -> None:
        dataset_key = str(dataset or "").strip().lower()
        if dataset_key:
            self._bump_option_market_data_io_stat(f"{dataset_key}_total_seconds", float(total_seconds or 0.0))
            if loaded_count:
                count_key = {
                    "session_bars": "session_bars_days_loaded",
                    "option_chain_snapshot": "chain_snapshots_loaded",
                    "option_quotes": "quote_days_loaded",
                    "option_bars": "bar_days_loaded",
                    "contract_list": "contract_list_days_loaded",
                }.get(dataset_key)
                if count_key:
                    self._bump_option_market_data_io_stat(count_key, int(loaded_count))
        if duckdb_seconds:
            self._bump_option_market_data_io_stat("duckdb_read_total_seconds", float(duckdb_seconds))
        if provider_seconds:
            self._bump_option_market_data_io_stat("provider_fetch_total_seconds", float(provider_seconds))
        if duckdb_calls:
            self._bump_option_market_data_io_stat("duckdb_read_calls", int(duckdb_calls))
        if provider_calls:
            self._bump_option_market_data_io_stat("provider_fetch_calls", int(provider_calls))

    def _bump_option_rejection(self, reason: str, amount: int = 1) -> None:
        key = str(reason or "unknown")
        self._last_option_rejection_reason = key
        self._option_rejection_counts[key] = int(self._option_rejection_counts.get(key, 0)) + int(amount)
        for alias in _OPTION_REJECTION_ALIAS_GROUPS.get(key, ()):
            self._option_rejection_counts[str(alias)] = int(
                self._option_rejection_counts.get(str(alias), 0)
            ) + int(amount)

    def _bump_option_funnel(self, stage: str, amount: int = 1) -> None:
        key = str(stage or "unknown")
        self._option_funnel_counts[key] = int(self._option_funnel_counts.get(key, 0)) + int(amount)

    def _bump_daily_funnel(self, stage: str, amount: int = 1) -> None:
        key = str(stage or "unknown")
        self._daily_funnel_counts[key] = int(self._daily_funnel_counts.get(key, 0)) + int(amount)

    @staticmethod
    def _normalize_option_attempt_value(value: Any) -> Any:
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, date):
            return value.isoformat()
        return value

    def _append_option_attempt_log_row(self, row: Mapping[str, Any]) -> None:
        normalized: Dict[str, Any] = {}
        for key, value in dict(row or {}).items():
            normalized[str(key)] = self._normalize_option_attempt_value(value)
        self._option_attempt_log.append(normalized)

    def _build_option_attempt_row_from_trade(
        self,
        *,
        trade: BacktestTrade,
        session_date: date,
        trade_limit_state: str = "passed",
    ) -> Dict[str, Any]:
        metadata = dict(trade.metadata or {})
        return {
            "symbol": str(trade.ticker or "").strip().upper(),
            "session_date": session_date,
            "strategy_variant": str(metadata.get("strategy_variant") or ""),
            "direction": int(metadata.get("direction") or 0),
            "delayed_entry_signal_ts": metadata.get("delayed_entry_signal_ts"),
            "effective_exit_signal_ts": metadata.get("effective_exit_signal_ts"),
            "trade_limit_state": str(trade_limit_state or "passed"),
            "trade_created": True,
            "rejection_reason": "",
            "option_structure_mode": str(metadata.get("option_structure_mode") or ""),
            "long_leg_symbol": metadata.get("long_leg_symbol"),
            "short_leg_symbol": metadata.get("short_leg_symbol"),
            "contract_selection_dte": metadata.get("contract_selection_dte"),
            "contract_strike": metadata.get("contract_strike"),
            "selected_abs_delta": metadata.get("selected_abs_delta"),
            "selected_strike_distance_steps": metadata.get("selected_strike_distance_steps"),
            "selected_entry_bar_volume": metadata.get("selected_entry_bar_volume"),
            "selected_quote_spread_pct": metadata.get("selected_quote_spread_pct"),
            "initial_selected_option_symbol": metadata.get("initial_selected_option_symbol"),
            "final_selected_option_symbol": metadata.get("final_selected_option_symbol"),
            "initial_selected_expiration_date": metadata.get("initial_selected_expiration_date"),
            "final_selected_expiration_date": metadata.get("final_selected_expiration_date"),
            "conversion_changed_expiry": metadata.get("conversion_changed_expiry"),
            "initial_contract_rank": metadata.get("initial_contract_rank"),
            "final_contract_rank": metadata.get("final_contract_rank"),
            "initial_selected_strike_distance_steps": metadata.get("initial_selected_strike_distance_steps"),
            "final_selected_strike_distance_steps": metadata.get("final_selected_strike_distance_steps"),
            "initial_selected_entry_bar_volume": metadata.get("initial_selected_entry_bar_volume"),
            "final_selected_entry_bar_volume": metadata.get("final_selected_entry_bar_volume"),
            "initial_selected_quote_spread_pct": metadata.get("initial_selected_quote_spread_pct"),
            "final_selected_quote_spread_pct": metadata.get("final_selected_quote_spread_pct"),
            "conversion_applied": metadata.get("conversion_applied"),
            "conversion_attempt_count": metadata.get("conversion_attempt_count"),
            "conversion_terminal_rejection_reason": metadata.get("conversion_terminal_rejection_reason"),
            "entry_volume": metadata.get("entry_volume"),
            "contract_open_interest": metadata.get("contract_open_interest"),
            "open_interest_data_available": metadata.get("open_interest_data_available"),
            "entry_quote_ts": metadata.get("entry_quote_ts"),
            "exit_quote_ts": metadata.get("exit_quote_ts"),
            "entry_quote_spread_abs": metadata.get("entry_quote_spread_abs"),
            "entry_quote_spread_pct": metadata.get("entry_quote_spread_pct"),
            "expected_move_to_extrinsic_ratio": metadata.get("expected_move_to_extrinsic_ratio"),
            "expected_move_to_debit_ratio": metadata.get("expected_move_to_debit_ratio"),
            "expected_move_to_spread_ratio": metadata.get("expected_move_to_spread_ratio"),
            "entry_debit": metadata.get("entry_debit"),
            "entry_credit": metadata.get("entry_credit"),
            "entry_price_effective": metadata.get("entry_price_effective", trade.entry_price),
            "exit_price_effective": metadata.get("exit_price_effective", trade.exit_price),
            "option_quote_fallback_used": metadata.get("option_quote_fallback_used"),
        }

    def _record_last_contract_selection_rejections(self) -> None:
        selection_meta = dict(self._last_contract_selection_meta or {})
        selection_rejections = dict(selection_meta.get("rejection_counts") or {})
        for reason, amount in selection_rejections.items():
            self._bump_option_rejection(str(reason), int(amount or 0))
        final_reason = str(self._last_contract_selection_reason or "contract_not_found")
        if final_reason and final_reason not in selection_rejections:
            self._bump_option_rejection(final_reason)

    def _clear_ephemeral_option_market_caches(self) -> None:
        self._contract_cache.clear()
        self._contract_selection_meta_cache.clear()

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

    def _contract_lookup_cache_stats_snapshot(self) -> Dict[str, int]:
        return dict(self._contract_lookup_cache_stats)

    def _option_market_data_io_stats_snapshot(self) -> Dict[str, Any]:
        return dict(self._option_market_data_io_stats)

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

    def _configure_runtime(self, config: IntradayOptionsBacktestConfig) -> None:
        mode = str(getattr(config, "runtime_mode", "legacy_local") or "legacy_local").strip().lower()
        if mode not in {"legacy_local", "host_runtime"}:
            mode = "legacy_local"
        socket_path = str(getattr(config, "runtime_socket", "") or "").strip()
        self._runtime_require_ipc = bool(getattr(config, "runtime_require_ipc", False))
        profiling_mode = str(getattr(config, "profiling_mode", "off") or "off").strip().lower()
        if profiling_mode not in {"off", "trace", "cprofile"}:
            profiling_mode = "off"
        self._profiling_mode = profiling_mode
        self._runtime_mode = mode
        self._runtime_socket = socket_path
        self._release_runtime_handles()
        self._runtime_handle_cache.clear()
        if mode == "host_runtime" and socket_path:
            self._runtime_client = MarketDataRuntimeClient(socket_path)
            if self._runtime_require_ipc:
                ipc_enabled = _RUNTIME_IPC_ENABLED_BY_SOCKET.get(socket_path)
                if ipc_enabled is None:
                    runtime_stats = dict(self._runtime_client.stats(force=True, max_age_seconds=0.0) or {})
                    ipc_enabled = bool(runtime_stats.get("ipc_enabled"))
                    _RUNTIME_IPC_ENABLED_BY_SOCKET[socket_path] = ipc_enabled
                if not bool(ipc_enabled):
                    raise RuntimeError("host runtime IPC support is required but unavailable")
        else:
            self._runtime_client = None

    def clear_runtime_caches(self) -> None:
        self._release_runtime_handles()
        self._runtime_handle_cache.clear()
        self._clear_contract_lookup_caches()
        self._option_bar_cache.clear()
        self._option_quote_cache.clear()
        self._option_quote_probe_cache.clear()
        self._selection_quote_prefetch_cache.clear()
        self._session_bar_cache.clear()
        self._daily_bar_range_cache.clear()
        self._premarket_bar_cache.clear()
        self._premarket_source_cache.clear()
        self._optional_aux_provider_denials.clear()

    def _release_runtime_handles(self) -> None:
        if self._runtime_client is None or not self._runtime_handle_cache:
            return
        try:
            self._runtime_client.release(list(self._runtime_handle_cache))
        except Exception:
            pass

    def _profile_stage(self, stage: str, started_at: float) -> None:
        if self._profiling_mode == "off":
            return
        elapsed = max(perf_counter() - float(started_at), 0.0)
        stage_key = str(stage or "unknown")
        stage_seconds = self._profiling_trace.setdefault("stage_seconds", {})
        stage_counts = self._profiling_trace.setdefault("stage_counts", {})
        stage_seconds[stage_key] = float(stage_seconds.get(stage_key) or 0.0) + elapsed
        stage_counts[stage_key] = int(stage_counts.get(stage_key) or 0) + 1

    def _runtime_rows(self, key: str) -> Optional[List[Dict[str, Any]]]:
        if self._runtime_mode != "host_runtime" or self._runtime_client is None:
            return None
        handle = self._runtime_handle_cache.get(key)
        if handle is None:
            try:
                handle = self._runtime_client.resolve(key, lease=True)
            except Exception as exc:
                if self._runtime_require_ipc:
                    raise RuntimeError(f"host runtime resolve failed for key={key}") from exc
                return None
            if self._runtime_require_ipc and str(handle.fmt or "").strip().lower() != "ipc":
                raise RuntimeError(f"host runtime returned non-IPC handle for key={key}")
            self._runtime_handle_cache[key] = handle
        try:
            return self._runtime_client.load_rows(handle)
        except Exception as exc:
            if self._runtime_require_ipc:
                raise RuntimeError(f"host runtime load failed for key={key}") from exc
            return None

    def _use_runtime_for_option_chain_snapshot(self) -> bool:
        return self._runtime_mode == "host_runtime" and self._runtime_client is not None

    def _use_runtime_for_option_quote_probe(self) -> bool:
        return self._runtime_mode == "host_runtime" and self._runtime_client is not None

    def _use_runtime_for_option_quotes(self) -> bool:
        return self._runtime_mode == "host_runtime" and self._runtime_client is not None

    def _use_runtime_for_option_bars(self) -> bool:
        return self._runtime_mode == "host_runtime" and self._runtime_client is not None

    @staticmethod
    def _normalize_selection_quote_mode(value: Any) -> str:
        mode = str(value or "legacy").strip().lower()
        if mode not in {"legacy", "probe", "prefetch"}:
            return "legacy"
        return mode

    @staticmethod
    def _causal_quote_near_ts(
        quotes: Sequence[Dict[str, Any]],
        ts: datetime,
        *,
        fallback_last: bool,
    ) -> Optional[Dict[str, Any]]:
        last_before: Optional[Dict[str, Any]] = None
        for quote in quotes:
            quote_ts = quote.get("ts")
            if not isinstance(quote_ts, datetime):
                continue
            if quote_ts >= ts:
                return quote
            if fallback_last and quote_ts <= ts:
                last_before = quote
        return last_before

    def _load_option_quote_probe(
        self,
        *,
        symbol: str,
        day: date,
        selection_ts: datetime,
        fallback_last: bool,
    ) -> Optional[Dict[str, Any]]:
        cache_key = (symbol, day, selection_ts, bool(fallback_last))
        if cache_key in self._option_quote_probe_cache:
            return self._option_quote_probe_cache[cache_key]

        rows: Optional[List[Dict[str, Any]]] = None
        if self._use_runtime_for_option_quote_probe():
            fallback_mode = "last" if fallback_last else "strict"
            key = f"option_quote_probe:{symbol}:{day.isoformat()}:{int(_datetime_to_ns(selection_ts))}:{fallback_mode}"
            rows = self._runtime_rows(key)
        if rows is None:
            if self.cutemarkets_provider is not None and hasattr(self.cutemarkets_provider, "fetch_option_quote_probe"):
                try:
                    quote = self.cutemarkets_provider.fetch_option_quote_probe(
                        option_symbol=symbol,
                        ts=selection_ts,
                        day=day,
                        fallback_last=fallback_last,
                    )
                except Exception:
                    quote = None
                rows = [dict(quote)] if isinstance(quote, dict) else []
            else:
                rows = []
        quote = rows[0] if rows else None
        self._option_quote_probe_cache[cache_key] = quote
        return quote

    def _prefetch_selection_quotes(
        self,
        *,
        symbols: Sequence[str],
        day: date,
    ) -> None:
        unique_symbols = [str(symbol).strip() for symbol in dict.fromkeys(symbols) if str(symbol).strip()]
        if not unique_symbols:
            return
        cache_key = (day, tuple(unique_symbols))
        if cache_key in self._selection_quote_prefetch_cache:
            return
        if self._use_runtime_for_option_quotes() and self._runtime_client is not None:
            try:
                self._runtime_client.warm([f"option_quotes:{symbol}:{day.isoformat()}" for symbol in unique_symbols])
            except Exception:
                pass
        for symbol in unique_symbols:
            self._load_option_quotes(symbol=symbol, day=day)
        self._selection_quote_prefetch_cache.add(cache_key)

    def _selection_quote_for_symbol(
        self,
        *,
        symbol: str,
        day: date,
        selection_ts: datetime,
        fallback_last: bool,
        selection_quote_mode: str,
    ) -> Tuple[Optional[Dict[str, Any]], str]:
        mode = self._normalize_selection_quote_mode(selection_quote_mode)
        if mode == "probe":
            quote = self._load_option_quote_probe(
                symbol=symbol,
                day=day,
                selection_ts=selection_ts,
                fallback_last=fallback_last,
            )
            return quote, "quote_probe"
        quotes = self._load_option_quotes(symbol=symbol, day=day)
        quote = self._causal_quote_near_ts(quotes, selection_ts, fallback_last=fallback_last)
        source = "quote_prefetch" if mode == "prefetch" else "quote_legacy"
        return quote, source

    @staticmethod
    def _contract_request_family_key(
        *,
        ticker: str,
        option_type: str,
        requested_status: str,
        option_min_dte: int,
        option_max_dte: int,
    ) -> Tuple[Any, ...]:
        return (
            ticker,
            option_type,
            requested_status,
            int(option_min_dte),
            int(option_max_dte),
        )

    @staticmethod
    def _contract_universe_key(
        *,
        ticker: str,
        option_type: str,
        status: str,
        option_min_dte: int,
        option_max_dte: int,
    ) -> Tuple[Any, ...]:
        return (
            ticker,
            option_type,
            status,
            int(option_min_dte),
            int(option_max_dte),
        )

    def _get_contract_fetch_preference(
        self,
        *,
        ticker: str,
        option_type: str,
        requested_status: str,
        option_min_dte: int,
        option_max_dte: int,
        allow_persistent_read: bool = True,
    ) -> Optional[Tuple[str, str]]:
        family_key = self._contract_request_family_key(
            ticker=ticker,
            option_type=option_type,
            requested_status=requested_status,
            option_min_dte=option_min_dte,
            option_max_dte=option_max_dte,
        )
        cached = self._contract_fetch_preference_cache.get(family_key)
        if cached is not None:
            self._bump_contract_lookup_cache_stat("fetch_preference_memory_hits")
            return cached
        if not allow_persistent_read:
            return None
        getter = getattr(self.store, "get_option_contract_fetch_preference", None)
        persistent = (
            getter(
                underlying=ticker,
                option_type=option_type,
                requested_status=requested_status,
                option_min_dte=int(option_min_dte),
                option_max_dte=int(option_max_dte),
            )
            if callable(getter)
            else None
        )
        if not isinstance(persistent, dict):
            return None
        preferred_status = str(persistent.get("preferred_status") or "").strip().lower()
        preferred_mode = str(persistent.get("preferred_as_of_mode") or "").strip().lower()
        if not preferred_status or preferred_mode not in {"day", "none"}:
            return None
        preferred = (preferred_status, preferred_mode)
        self._bump_contract_lookup_cache_stat("fetch_preference_persistent_hits")
        self._set_bounded_cache_entry(
            self._contract_fetch_preference_cache,
            family_key,
            preferred,
            max_entries=_MAX_CONTRACT_FETCH_PREFERENCE_CACHE_KEYS,
        )
        return preferred

    def _set_contract_fetch_preference(
        self,
        *,
        ticker: str,
        option_type: str,
        requested_status: str,
        option_min_dte: int,
        option_max_dte: int,
        preferred_status: str,
        preferred_as_of_mode: str,
    ) -> None:
        family_key = self._contract_request_family_key(
            ticker=ticker,
            option_type=option_type,
            requested_status=requested_status,
            option_min_dte=option_min_dte,
            option_max_dte=option_max_dte,
        )
        normalized = (str(preferred_status).strip().lower(), str(preferred_as_of_mode).strip().lower())
        if not normalized[0] or normalized[1] not in {"day", "none"}:
            return
        self._set_bounded_cache_entry(
            self._contract_fetch_preference_cache,
            family_key,
            normalized,
            max_entries=_MAX_CONTRACT_FETCH_PREFERENCE_CACHE_KEYS,
        )
        if not self._persist_option_contract_lookup_cache:
            self._bump_contract_lookup_cache_stat("fetch_preference_persistent_write_skips")
            return
        setter = getattr(self.store, "set_option_contract_fetch_preference", None)
        if callable(setter):
            setter(
                underlying=ticker,
                option_type=option_type,
                requested_status=requested_status,
                option_min_dte=int(option_min_dte),
                option_max_dte=int(option_max_dte),
                preferred_status=normalized[0],
                preferred_as_of_mode=normalized[1],
            )
            self._bump_contract_lookup_cache_stat("fetch_preference_persistent_writes")

    @staticmethod
    def _contract_fetch_attempts(
        *,
        requested_status: str,
        preferred: Optional[Tuple[str, str]],
    ) -> List[Tuple[str, str]]:
        attempts: List[Tuple[str, str]] = []
        if preferred is not None:
            attempts.append(preferred)
        attempts.extend(
            [
                (requested_status, "day"),
                (requested_status, "none"),
            ]
        )
        if requested_status != "all":
            attempts.extend(
                [
                    ("all", "day"),
                    ("all", "none"),
                ]
            )
        if requested_status != "inactive":
            attempts.extend(
                [
                    ("inactive", "day"),
                    ("inactive", "none"),
                ]
            )
        deduped: List[Tuple[str, str]] = []
        seen = set()
        for status, as_of_mode in attempts:
            key = (str(status).strip().lower(), str(as_of_mode).strip().lower())
            if not key[0] or key[1] not in {"day", "none"} or key in seen:
                continue
            seen.add(key)
            deduped.append(key)
        return deduped

    def _get_cached_contract_list_for_day(
        self,
        *,
        raw_cache_key: Tuple[Any, ...],
        ticker: str,
        day: date,
        option_type: str,
        requested_status: str,
        option_min_dte: int,
        option_max_dte: int,
        allow_persistent_read: bool = True,
    ) -> Tuple[List[Dict[str, Any]], bool]:
        cached = self._contract_list_cache.get(raw_cache_key, _MISSING)
        if cached is not _MISSING:
            self._bump_contract_lookup_cache_stat("contract_list_memory_hits")
            return list(cached), True
        if not allow_persistent_read:
            return [], False
        getter = getattr(self.store, "get_option_contract_list_cache", None)
        started_at = perf_counter()
        persistent = (
            getter(
                underlying=ticker,
                trading_day=day,
                option_type=option_type,
                status=requested_status,
                option_min_dte=int(option_min_dte),
                option_max_dte=int(option_max_dte),
            )
            if callable(getter)
            else None
        )
        duckdb_seconds = perf_counter() - started_at if callable(getter) else 0.0
        self._record_option_market_data_io(
            dataset="contract_list",
            total_seconds=duckdb_seconds,
            duckdb_seconds=duckdb_seconds,
            loaded_count=1 if callable(getter) else 0,
            duckdb_calls=1 if callable(getter) else 0,
        )
        if persistent is None:
            return [], False
        contracts = list(persistent.get("contracts") or [])
        self._bump_contract_lookup_cache_stat("contract_list_persistent_hits")
        self._set_bounded_cache_entry(
            self._contract_list_cache,
            raw_cache_key,
            contracts,
            max_entries=_MAX_CONTRACT_LIST_CACHE_KEYS,
        )
        return list(contracts), True

    def _set_cached_contract_list_for_day(
        self,
        *,
        raw_cache_key: Tuple[Any, ...],
        ticker: str,
        day: date,
        option_type: str,
        requested_status: str,
        option_min_dte: int,
        option_max_dte: int,
        contracts: Sequence[Dict[str, Any]],
    ) -> None:
        normalized = [dict(item) for item in contracts if isinstance(item, dict)]
        self._set_bounded_cache_entry(
            self._contract_list_cache,
            raw_cache_key,
            normalized,
            max_entries=_MAX_CONTRACT_LIST_CACHE_KEYS,
        )
        if not self._persist_option_contract_lookup_cache:
            self._bump_contract_lookup_cache_stat("contract_list_persistent_write_skips")
            return
        setter = getattr(self.store, "set_option_contract_list_cache", None)
        if callable(setter):
            setter(
                underlying=ticker,
                trading_day=day,
                option_type=option_type,
                status=requested_status,
                option_min_dte=int(option_min_dte),
                option_max_dte=int(option_max_dte),
                found=bool(normalized),
                contracts=normalized,
            )
            self._bump_contract_lookup_cache_stat("contract_list_persistent_writes")

    def _get_cached_contract_universe(
        self,
        *,
        universe_key: Tuple[Any, ...],
        ticker: str,
        option_type: str,
        status: str,
        option_min_dte: int,
        option_max_dte: int,
        allow_persistent_read: bool = True,
    ) -> Tuple[List[Dict[str, Any]], bool]:
        cached = self._contract_universe_cache.get(universe_key, _MISSING)
        if cached is not _MISSING:
            self._bump_contract_lookup_cache_stat("contract_universe_memory_hits")
            return list(cached), True
        if not allow_persistent_read:
            return [], False
        getter = getattr(self.store, "get_option_contract_universe_cache", None)
        persistent = (
            getter(
                underlying=ticker,
                option_type=option_type,
                status=status,
                option_min_dte=int(option_min_dte),
                option_max_dte=int(option_max_dte),
            )
            if callable(getter)
            else None
        )
        if persistent is None:
            return [], False
        contracts = list(persistent.get("contracts") or [])
        self._bump_contract_lookup_cache_stat("contract_universe_persistent_hits")
        self._set_bounded_cache_entry(
            self._contract_universe_cache,
            universe_key,
            contracts,
            max_entries=_MAX_CONTRACT_UNIVERSE_CACHE_KEYS,
        )
        return list(contracts), True

    def _set_cached_contract_universe(
        self,
        *,
        universe_key: Tuple[Any, ...],
        ticker: str,
        option_type: str,
        status: str,
        option_min_dte: int,
        option_max_dte: int,
        contracts: Sequence[Dict[str, Any]],
    ) -> None:
        normalized = [dict(item) for item in contracts if isinstance(item, dict)]
        self._set_bounded_cache_entry(
            self._contract_universe_cache,
            universe_key,
            normalized,
            max_entries=_MAX_CONTRACT_UNIVERSE_CACHE_KEYS,
        )
        if not self._persist_option_contract_lookup_cache:
            self._bump_contract_lookup_cache_stat("contract_universe_persistent_write_skips")
            return
        setter = getattr(self.store, "set_option_contract_universe_cache", None)
        if callable(setter):
            setter(
                underlying=ticker,
                option_type=option_type,
                status=status,
                option_min_dte=int(option_min_dte),
                option_max_dte=int(option_max_dte),
                found=bool(normalized),
                contracts=normalized,
            )
            self._bump_contract_lookup_cache_stat("contract_universe_persistent_writes")

    def _contract_candidates_for_cache_key(
        self,
        *,
        cache_key: Tuple[Any, ...],
        contracts: Sequence[Dict[str, Any]],
    ) -> List[_ContractCandidate]:
        cached = self._contract_candidate_cache.get(cache_key)
        if cached is not None:
            return cached
        candidates: List[_ContractCandidate] = []
        for contract in contracts:
            if not isinstance(contract, dict):
                continue
            strike = _safe_float(contract.get("strike_price"))
            expiry = parse_datetime(contract.get("expiration_date"))
            if strike is None or strike <= 0 or expiry is None:
                continue
            candidates.append(
                _ContractCandidate(
                    strike=float(strike),
                    expiration_day=expiry.date(),
                    open_interest=int(contract.get("open_interest") or 0),
                    contract=contract,
                )
            )
        self._set_bounded_cache_entry(
            self._contract_candidate_cache,
            cache_key,
            candidates,
            max_entries=_MAX_CONTRACT_CANDIDATE_CACHE_KEYS,
        )
        return candidates

    def _group_contract_candidates_for_cache_key(
        self,
        *,
        cache_key: Tuple[Any, ...],
        contracts: Sequence[Dict[str, Any]],
    ) -> _GroupedContractCandidates:
        cached = self._contract_candidate_group_cache.get(cache_key)
        if cached is not None:
            return cached
        by_expiration: Dict[date, List[_ContractCandidate]] = {}
        for candidate in self._contract_candidates_for_cache_key(cache_key=cache_key, contracts=contracts):
            by_expiration.setdefault(candidate.expiration_day, []).append(candidate)
        ascending_by_expiration: Dict[date, List[_ContractCandidate]] = {}
        descending_by_expiration: Dict[date, List[_ContractCandidate]] = {}
        for expiration_day, rows in by_expiration.items():
            ascending_by_expiration[expiration_day] = sorted(rows, key=lambda item: float(item.strike))
            descending_by_expiration[expiration_day] = sorted(rows, key=lambda item: -float(item.strike))
        grouped = _GroupedContractCandidates(
            ascending_by_expiration=ascending_by_expiration,
            descending_by_expiration=descending_by_expiration,
        )
        self._set_bounded_cache_entry(
            self._contract_candidate_group_cache,
            cache_key,
            grouped,
            max_entries=_MAX_CONTRACT_CANDIDATE_GROUP_CACHE_KEYS,
        )
        return grouped

    def _restrict_candidates_to_local_strike_band(
        self,
        *,
        grouped_candidates: _GroupedContractCandidates,
        direction: int,
        entry_underlying: float,
        itm_steps: int,
        otm_steps: int,
    ) -> List[_ContractCandidate]:
        itm_steps = max(int(itm_steps), 0)
        otm_steps = max(int(otm_steps), 0)
        if itm_steps <= 0 and otm_steps <= 0:
            return []
        restricted: List[_ContractCandidate] = []
        seen_symbols: set[str] = set()
        for expiration_day, ascending_rows in grouped_candidates.ascending_by_expiration.items():
            if not ascending_rows:
                continue
            lower = [candidate for candidate in ascending_rows if float(candidate.strike) < float(entry_underlying)]
            upper = [candidate for candidate in ascending_rows if float(candidate.strike) > float(entry_underlying)]
            nearest = min(
                ascending_rows,
                key=lambda candidate: (
                    abs(float(candidate.strike) - float(entry_underlying)),
                    0 if float(candidate.strike) >= float(entry_underlying) else 1,
                    abs((candidate.expiration_day - expiration_day).days),
                ),
            )
            local_band: List[_ContractCandidate] = [nearest]
            if int(direction) > 0:
                local_band.extend(reversed(lower[-itm_steps:]))
                local_band.extend(upper[:otm_steps])
            else:
                local_band.extend(upper[:itm_steps])
                local_band.extend(reversed(lower[-otm_steps:]))
            for candidate in local_band:
                symbol = str(candidate.contract.get("symbol") or "").strip()
                if not symbol or symbol in seen_symbols:
                    continue
                seen_symbols.add(symbol)
                restricted.append(candidate)
        return restricted

    def _clear_contract_lookup_caches(self) -> None:
        self._contract_cache.clear()
        self._contract_list_cache.clear()
        self._contract_universe_cache.clear()
        self._contract_candidate_cache.clear()
        self._contract_candidate_group_cache.clear()
        self._contract_fetch_preference_cache.clear()
        self._option_chain_snapshot_cache.clear()
        self._option_chain_snapshot_index_cache.clear()
        self._option_contract_snapshot_cache.clear()
        self._option_quote_index_cache.clear()
        self._option_quote_lookup_cache.clear()
        self._option_first_hour_quoteable_cache.clear()

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

    def _load_option_chain_snapshot(self, ticker: str, day: date) -> List[Dict[str, Any]]:
        key = (str(ticker).strip().upper(), day)
        cached = self._option_chain_snapshot_cache.get(key)
        if cached is not None:
            return cached
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

    def _load_option_chain_snapshot_uncached(self, *, ticker: str, day: date) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        duckdb_seconds = 0.0
        started_at = perf_counter()
        get_chain_snapshot = getattr(self.store, "get_option_chain_snapshot", None)
        if callable(get_chain_snapshot):
            rows = list(
                get_chain_snapshot(
                    str(ticker).strip().upper(),
                    as_of=datetime.combine(day, time(23, 59, 59)),
                )
            )
        duckdb_seconds = perf_counter() - started_at
        if rows:
            self._record_option_market_data_io(
                dataset="option_chain_snapshot",
                total_seconds=duckdb_seconds,
                duckdb_seconds=duckdb_seconds,
                loaded_count=1,
                duckdb_calls=1,
            )
            return rows
        provider_seconds = 0.0
        if self.cutemarkets_provider is not None:
            started_at = perf_counter()
            try:
                rows = list(self.cutemarkets_provider.fetch_option_chain_snapshot(str(ticker).strip().upper(), as_of=day) or [])
            except Exception:
                rows = []
            provider_seconds = perf_counter() - started_at
        self._record_option_market_data_io(
            dataset="option_chain_snapshot",
            total_seconds=duckdb_seconds + provider_seconds,
            duckdb_seconds=duckdb_seconds,
            provider_seconds=provider_seconds,
            loaded_count=1,
            duckdb_calls=1,
            provider_calls=1 if self.cutemarkets_provider is not None else 0,
        )
        return rows

    def _build_option_chain_snapshot_index(
        self,
        snapshot_rows: Sequence[Mapping[str, Any]],
    ) -> _OptionChainSnapshotIndex:
        by_symbol: Dict[str, Dict[str, Any]] = {}
        by_triplet: Dict[Tuple[str, float, str], Dict[str, Any]] = {}
        for row in snapshot_rows:
            if isinstance(row, dict):
                normalized = row
            elif isinstance(row, Mapping):
                normalized = dict(row)
            else:
                continue
            row_type = str(normalized.get("option_type") or "").strip().lower()
            symbol = str(normalized.get("option_symbol") or normalized.get("symbol") or "").strip()
            if symbol:
                by_symbol[symbol] = normalized
            expiration_raw = normalized.get("expiration")
            expiration = expiration_raw if isinstance(expiration_raw, datetime) else parse_datetime(expiration_raw)
            strike_raw = normalized.get("strike")
            strike = strike_raw if isinstance(strike_raw, float) else _safe_float(strike_raw)
            if expiration is None or strike is None or strike <= 0.0 or not row_type:
                continue
            by_triplet[(expiration.date().isoformat(), round(float(strike), 6), row_type)] = normalized
        return _OptionChainSnapshotIndex(by_symbol=by_symbol, by_triplet=by_triplet)

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

    def _load_option_contract_snapshot(
        self,
        *,
        ticker: str,
        option_symbol: str,
        day: date,
    ) -> Optional[Dict[str, Any]]:
        symbol = str(option_symbol or "").strip()
        if not symbol:
            return None
        key = (str(ticker).strip().upper(), symbol, day)
        cached = self._option_contract_snapshot_cache.get(key, _MISSING)
        if cached is not _MISSING:
            return dict(cached) if isinstance(cached, dict) else None
        row: Optional[Dict[str, Any]] = None
        if self.cutemarkets_provider is not None and hasattr(self.cutemarkets_provider, "fetch_option_contract_snapshot"):
            try:
                fetched = self.cutemarkets_provider.fetch_option_contract_snapshot(
                    key[0],
                    symbol,
                    as_of=day,
                )
            except Exception:
                fetched = None
            if isinstance(fetched, dict) and fetched:
                row = dict(fetched)
        self._set_bounded_cache_entry(
            self._option_contract_snapshot_cache,
            key,
            dict(row) if isinstance(row, dict) else None,
            max_entries=_MAX_OPTION_CONTRACT_SNAPSHOT_CACHE_KEYS,
        )
        return dict(row) if isinstance(row, dict) else None

    def _invalidate_option_quote_derived_caches(self, *, symbol: str, day: date) -> None:
        cache_key = (str(symbol or "").strip(), day)
        self._option_quote_index_cache.pop(cache_key, None)
        self._option_first_hour_quoteable_cache.pop(cache_key, None)
        stale_probe_keys = [
            key
            for key in self._option_quote_probe_cache
            if len(key) >= 2 and key[0] == cache_key[0] and key[1] == cache_key[1]
        ]
        for key in stale_probe_keys:
            self._option_quote_probe_cache.pop(key, None)
        stale_lookup_keys = [
            key
            for key in self._option_quote_lookup_cache
            if len(key) >= 2 and key[0] == cache_key[0] and key[1] == cache_key[1]
        ]
        for key in stale_lookup_keys:
            self._option_quote_lookup_cache.pop(key, None)

    def _build_option_quote_index(
        self,
        quotes: Sequence[Mapping[str, Any]],
    ) -> _OptionQuoteIndex:
        valid_quotes: List[Dict[str, Any]] = []
        valid_quote_timestamps_utc: List[datetime] = []
        fallback_last_quote: Optional[Dict[str, Any]] = None
        for row in quotes:
            if not isinstance(row, dict):
                if isinstance(row, Mapping):
                    normalized = dict(row)
                else:
                    continue
            else:
                normalized = row
            fallback_last_quote = normalized
            quote_ts = normalized.get("ts")
            if not isinstance(quote_ts, datetime):
                continue
            valid_quotes.append(normalized)
            valid_quote_timestamps_utc.append(_as_utc_aware(quote_ts))
        return _OptionQuoteIndex(
            valid_quotes=valid_quotes,
            valid_quote_timestamps_utc=valid_quote_timestamps_utc,
            fallback_last_quote=fallback_last_quote,
        )

    def _load_option_quote_index(self, *, symbol: str, day: date) -> _OptionQuoteIndex:
        cache_key = (str(symbol or "").strip(), day)
        cached = self._option_quote_index_cache.get(cache_key)
        if cached is not None:
            return cached
        index = self._build_option_quote_index(self._load_option_quotes(symbol=symbol, day=day))
        self._set_bounded_cache_entry(
            self._option_quote_index_cache,
            cache_key,
            index,
            max_entries=_MAX_OPTION_QUOTE_CACHE_KEYS,
        )
        return index

    def _lookup_option_quote_on_or_after(
        self,
        *,
        symbol: str,
        day: date,
        ts: datetime,
        fallback_last: bool = False,
    ) -> Optional[Dict[str, Any]]:
        normalized_symbol = str(symbol or "").strip()
        lookup_key = (
            normalized_symbol,
            day,
            _as_utc_aware(ts).isoformat(),
            bool(fallback_last),
        )
        if lookup_key in self._option_quote_lookup_cache:
            return self._option_quote_lookup_cache[lookup_key]
        index = self._load_option_quote_index(symbol=normalized_symbol, day=day)
        target_ts = _as_utc_aware(ts)
        idx = bisect_left(index.valid_quote_timestamps_utc, target_ts)
        if idx < len(index.valid_quotes):
            quote = index.valid_quotes[idx]
        elif fallback_last:
            quote = index.fallback_last_quote
        else:
            quote = None
        self._set_bounded_cache_entry(
            self._option_quote_lookup_cache,
            lookup_key,
            quote,
            max_entries=_MAX_OPTION_QUOTE_LOOKUP_CACHE_KEYS,
        )
        return quote

    def _has_first_hour_quoteable_quotes(self, *, symbol: str, day: date) -> bool:
        cache_key = (str(symbol or "").strip(), day)
        cached = self._option_first_hour_quoteable_cache.get(cache_key)
        if cached is not None:
            return bool(cached)
        index = self._load_option_quote_index(symbol=cache_key[0], day=day)
        start_utc = datetime.combine(day, time(9, 30), tzinfo=_ET_ZONE).astimezone(timezone.utc)
        end_utc = datetime.combine(day, time(10, 30), tzinfo=_ET_ZONE).astimezone(timezone.utc)
        start_idx = bisect_left(index.valid_quote_timestamps_utc, start_utc)
        quoteable = False
        for idx in range(start_idx, len(index.valid_quotes)):
            if index.valid_quote_timestamps_utc[idx] > end_utc:
                break
            quote = index.valid_quotes[idx]
            bid = _safe_float(quote.get("bid"))
            ask = _safe_float(quote.get("ask"))
            if bid is not None and bid > 0.0 and ask is not None and ask > 0.0:
                quoteable = True
                break
        self._set_bounded_cache_entry(
            self._option_first_hour_quoteable_cache,
            cache_key,
            bool(quoteable),
            max_entries=_MAX_OPTION_FIRST_HOUR_QUOTEABLE_CACHE_KEYS,
        )
        return bool(quoteable)

    def _maybe_fill_contract_open_interest(
        self,
        *,
        ticker: str,
        day: date,
        contract: Optional[Dict[str, Any]],
        enrichment_mode: str,
    ) -> Optional[Dict[str, Any]]:
        if not isinstance(contract, dict):
            return contract
        mode = _normalize_option_chain_snapshot_enrichment_mode(enrichment_mode)
        if mode not in {"prior_oi_only", "full"}:
            return contract
        if int(contract.get("open_interest") or 0) > 0:
            return contract
        snapshot = self._load_option_contract_snapshot(
            ticker=ticker,
            option_symbol=str(contract.get("symbol") or ""),
            day=day,
        )
        if not isinstance(snapshot, dict):
            return contract
        if snapshot.get("open_interest") is not None and int(contract.get("open_interest") or 0) <= 0:
            contract["open_interest"] = int(snapshot.get("open_interest") or 0)
        if mode == "full":
            if contract.get("delta") in {None, ""} and snapshot.get("delta") is not None:
                contract["delta"] = snapshot.get("delta")
            if int(contract.get("volume") or 0) <= 0 and snapshot.get("volume") is not None:
                contract["volume"] = int(snapshot.get("volume") or 0)
        return contract

    @staticmethod
    def _map_cutemarkets_snapshot_contract_row(row: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
        symbol = str(row.get("option_symbol") or row.get("symbol") or row.get("ticker") or "").strip()
        expiration = parse_datetime(row.get("expiration") or row.get("expiration_date"))
        strike = _safe_float(row.get("strike") or row.get("strike_price"))
        option_type = str(
            row.get("option_type") or row.get("type") or row.get("contract_type") or ""
        ).strip().lower()
        if not symbol or expiration is None or strike is None or strike <= 0.0:
            return None
        if option_type not in {"call", "put"}:
            return None
        return {
            "symbol": symbol,
            "expiration_date": expiration.date().isoformat(),
            "strike_price": float(strike),
            "type": option_type,
            "option_type": option_type,
            "status": "snapshot",
        }

    def _contract_list_from_chain_snapshot(
        self,
        *,
        ticker: str,
        day: date,
        option_type: str,
        option_min_dte: int,
        option_max_dte: int,
        requested_status: str = "",
    ) -> List[Dict[str, Any]]:
        snapshot_rows = self._load_option_chain_snapshot(ticker=ticker, day=day)
        if not snapshot_rows:
            return []
        min_expiration_day = day + timedelta(days=max(int(option_min_dte), 0))
        max_expiration_day = day + timedelta(days=max(int(option_max_dte), int(option_min_dte)))
        option_type_norm = str(option_type or "").strip().lower()
        status_norm = str(requested_status or "").strip().lower()
        deduped: Dict[str, Dict[str, Any]] = {}
        for row in snapshot_rows:
            if not isinstance(row, Mapping):
                continue
            mapped = self._map_cutemarkets_snapshot_contract_row(row)
            if mapped is None:
                continue
            mapped_type = str(mapped.get("option_type") or "").strip().lower()
            if option_type_norm and mapped_type != option_type_norm:
                continue
            expiration = parse_datetime(mapped.get("expiration_date"))
            if expiration is None:
                continue
            expiration_day = expiration.date()
            if expiration_day < min_expiration_day or expiration_day > max_expiration_day:
                continue
            if status_norm and status_norm != "all":
                mapped["status"] = status_norm
            deduped[str(mapped.get("symbol") or "").strip()] = mapped
        return [deduped[key] for key in sorted(deduped)]

    def _fetch_cutemarkets_contract_list(
        self,
        *,
        ticker: str,
        day: date,
        option_type: str,
        option_min_dte: int,
        option_max_dte: int,
    ) -> List[Dict[str, Any]]:
        if self.cutemarkets_provider is None:
            return []
        expiration_date_gte = (day + timedelta(days=max(int(option_min_dte), 0))).isoformat()
        expiration_date_lte = (
            day + timedelta(days=max(int(option_max_dte), int(option_min_dte)))
        ).isoformat()
        expired_contracts_only = False
        try:
            expired_contracts_only = date.fromisoformat(expiration_date_lte) < date.today()
        except Exception:
            expired_contracts_only = False
        fetch_kwargs: Dict[str, Any] = {
            "underlying": str(ticker).strip().upper(),
            "limit": 1000,
            "contract_type": str(option_type or "").strip().lower() or None,
            "paginate": True,
            "expired": expired_contracts_only,
        }
        if expiration_date_gte == expiration_date_lte:
            fetch_kwargs["expiration_date"] = expiration_date_gte
        else:
            fetch_kwargs["expiration_date_gte"] = expiration_date_gte
            fetch_kwargs["expiration_date_lte"] = expiration_date_lte
        started_at = perf_counter()
        if hasattr(self.cutemarkets_provider, "fetch_option_contracts"):
            rows = self.cutemarkets_provider.fetch_option_contracts(**fetch_kwargs) or []
        else:
            rows = self.cutemarkets_provider.fetch_option_chain_snapshot(**fetch_kwargs) or []
        total_seconds = perf_counter() - started_at
        self._record_option_market_data_io(
            dataset="contract_list",
            total_seconds=total_seconds,
            provider_seconds=total_seconds,
            loaded_count=1,
            provider_calls=1,
        )
        deduped: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            mapped = self._map_cutemarkets_snapshot_contract_row(row)
            if mapped is None:
                continue
            deduped[str(mapped.get("symbol") or "").strip()] = mapped
        return [deduped[key] for key in sorted(deduped)]

    def _enrich_contracts_with_chain_snapshot(
        self,
        *,
        ticker: str,
        day: date,
        option_type: str,
        contracts: Sequence[Dict[str, Any]],
        enrichment_mode: str = "full",
    ) -> List[Dict[str, Any]]:
        normalized = [dict(contract) for contract in contracts if isinstance(contract, dict)]
        if not normalized:
            return normalized
        mode = _normalize_option_chain_snapshot_enrichment_mode(enrichment_mode)
        if mode == "off":
            return normalized
        snapshot_index = self._load_option_chain_snapshot_index(ticker=ticker, day=day)
        if not snapshot_index.by_symbol and not snapshot_index.by_triplet:
            return normalized

        option_type_norm = str(option_type or "").strip().lower()

        enriched: List[Dict[str, Any]] = []
        for contract in normalized:
            row = None
            symbol = str(contract.get("symbol") or "").strip()
            if symbol:
                matched = snapshot_index.by_symbol.get(symbol)
                matched_type = str((matched or {}).get("option_type") or "").strip().lower()
                if matched is not None and (not option_type_norm or matched_type == option_type_norm):
                    row = matched
            if row is None:
                expiry = parse_datetime(contract.get("expiration_date"))
                strike = _safe_float(contract.get("strike_price"))
                if expiry is not None and strike is not None and strike > 0.0:
                    row = snapshot_index.by_triplet.get(
                        (expiry.date().isoformat(), round(float(strike), 6), option_type_norm)
                    )
            if row is not None:
                if mode == "full" and contract.get("delta") in {None, ""}:
                    contract["delta"] = row.get("delta")
                if int(contract.get("open_interest") or 0) <= 0 and row.get("open_interest") is not None:
                    contract["open_interest"] = int(row.get("open_interest") or 0)
                if mode == "full" and int(contract.get("volume") or 0) <= 0 and row.get("volume") is not None:
                    contract["volume"] = int(row.get("volume") or 0)
            enriched.append(contract)
        return enriched

    def run(self, config: IntradayOptionsBacktestConfig) -> Dict[str, Any]:
        self._reset_option_rejection_counts()
        self._reset_option_funnel_counts()
        self._reset_option_attempt_log()
        self._reset_daily_funnel_counts()
        self._reset_contract_lookup_cache_stats()
        self._reset_option_market_data_io_stats()
        self._last_option_rejection_reason = ""
        store_is_read_only = bool(getattr(self.store, "read_only", False))
        self._persist_fetched_market_data = bool(config.persist_fetched_market_data) and not store_is_read_only
        self._persist_option_contract_lookup_cache = (
            bool(config.persist_option_contract_lookup_cache) and not store_is_read_only
        )
        self._configure_runtime(config)
        if self._runtime_mode == "host_runtime":
            self.clear_runtime_caches()
        if str(config.signal_cadence or "intraday").strip().lower() == "daily_eod":
            return self._run_daily_forecast(config)
        equity = float(config.initial_equity)
        trades: List[BacktestTrade] = []
        returns: List[float] = []
        session_cache: Dict[date, List[Dict[str, Any]]] = {}
        session_prefetch_lookback = max(int(config.relative_volume_lookback_days), 1) * 8 if config.require_relative_volume else 0
        session_prefetch_start = config.start.date() - timedelta(days=session_prefetch_lookback)
        session_prefetch_end = config.end.date() + timedelta(days=1)
        if type(self)._load_session_bars is IntradayOptionsBacktester._load_session_bars:
            session_cache.update(
                self._load_session_bars_range(
                    ticker=config.ticker,
                    start_day=session_prefetch_start,
                    end_day=session_prefetch_end,
                )
            )
        else:
            for preload_day in _iter_dates(session_prefetch_start, session_prefetch_end):
                session_cache[preload_day] = self._load_session_bars(config.ticker, preload_day)
        session_analytics = _SessionAnalytics.from_session_cache(
            session_cache=session_cache,
            opening_range_minutes=config.opening_range_minutes,
        )
        daily_history = self._load_daily_bars_range(
            ticker=config.ticker,
            start_day=config.start.date() - timedelta(days=max(config.atr_lookback_days, 1) * 8),
            end_day=config.end.date(),
        )
        daily_analytics = _DailyHistoryAnalytics.from_rows(daily_history)

        vol_regime_history: List[Dict[str, Any]] = []
        vol_regime_ticker_used = config.vol_regime_ticker
        if config.require_vol_regime_filter:
            vol_regime_history = self._load_daily_bars_range(
                ticker=config.vol_regime_ticker,
                start_day=config.start.date() - timedelta(days=max(config.atr_lookback_days, 1) * 8),
                end_day=config.end.date(),
            )
            if not vol_regime_history and str(config.vol_regime_proxy_ticker or "").strip():
                proxy_ticker = str(config.vol_regime_proxy_ticker).strip()
                if proxy_ticker and proxy_ticker != config.vol_regime_ticker:
                    fallback = self._load_daily_bars_range(
                        ticker=proxy_ticker,
                        start_day=config.start.date() - timedelta(days=max(config.atr_lookback_days, 1) * 8),
                        end_day=config.end.date(),
                    )
                    if fallback:
                        vol_regime_history = fallback
                        vol_regime_ticker_used = proxy_ticker
        vol_regime_analytics = _DailyHistoryAnalytics.from_rows(vol_regime_history)
        strategy_variant_normalized = str(config.strategy_variant or "orb_qc").strip().lower()
        needs_premarket_context = bool(config.require_premarket_context) or strategy_variant_normalized == "lfcm_v1"
        if needs_premarket_context:
            self._prime_premarket_context_range(
                ticker=config.ticker,
                start_day=config.start.date(),
                end_day=config.end.date(),
            )

        total_days = 0
        days_with_session_data = 0
        setup_days = 0
        skipped_no_option_data = 0
        proxy_fills = 0
        historical_fills = 0
        no_setup_days = 0
        option_trade_attempts = 0
        option_trade_executed = 0
        days_filtered_by_vol_regime = 0
        days_filtered_by_or_width = 0
        days_filtered_by_prior_day_inside_bar = 0
        days_filtered_by_prior_day_range = 0
        setups_filtered_by_regime_gate = 0
        session_days: List[str] = []
        setup_days_list: List[str] = []
        setup_regime_label_counts = _empty_regime_label_counts()
        trade_regime_label_counts = _empty_regime_label_counts()
        setup_audit_days = 0
        setup_opportunities_before_filters_total = 0
        setup_opportunities_after_filters_total = 0
        setup_rejection_counts_total: Dict[str, int] = {}
        underlying_shadow_equity = float(config.initial_equity)
        underlying_shadow_trades: List[BacktestTrade] = []
        underlying_shadow_returns: List[float] = []
        regime_gate_enabled = bool(config.regime_gate_enabled)
        regime_gate_allowed_labels = _parse_regime_label_allowlist(config.regime_gate_allowed_labels)
        regime_day_map: Dict[date, str] = {}
        if isinstance(config.regime_day_map, dict):
            for raw_day, raw_label in config.regime_day_map.items():
                day_key = raw_day if isinstance(raw_day, date) else None
                if day_key is None:
                    try:
                        day_key = datetime.fromisoformat(str(raw_day)).date()
                    except Exception:
                        day_key = None
                if day_key is None:
                    continue
                regime_day_map[day_key] = _normalize_regime_label(raw_label)
        regime_v2_cfg = RegimeV2Config(
            enabled=bool(config.regime_v2_enabled),
            min_intraday_bars=max(int(config.opening_range_minutes), 2),
            intraday_er_trend_min=float(config.regime_v2_intraday_er_trend_min),
            intraday_er_sideways_max=float(config.regime_v2_intraday_er_sideways_max),
            intraday_direction_abs_return_min=float(config.regime_v2_intraday_direction_abs_return_min),
            range_low_vol_max_pct=float(config.regime_v2_range_low_vol_max_pct),
            range_high_vol_min_pct=float(config.regime_v2_range_high_vol_min_pct),
            event_gap_abs_return_min=float(config.regime_v2_event_gap_abs_return_min),
            event_gap_min_range_pct=float(config.regime_v2_event_gap_min_range_pct),
            min_confidence=float(config.regime_v2_min_confidence),
        )
        regime_v2_router_requested = bool(config.regime_v2_router_enabled)
        regime_v2_router_enabled = bool(regime_v2_router_requested and config.regime_v2_enabled)
        regime_v2_router_config_warning = ""
        if regime_v2_router_requested and not bool(config.regime_v2_enabled):
            regime_v2_router_config_warning = "router_requires_regime_v2_enabled"
        route_fn_argnames = _route_strategy_for_regime_v2.__code__.co_varnames[
            : _route_strategy_for_regime_v2.__code__.co_argcount
            + _route_strategy_for_regime_v2.__code__.co_kwonlyargcount
        ]
        route_supports_relative_opening_volume = "relative_opening_volume" in route_fn_argnames
        route_supports_entry_bar_range_pct = "entry_bar_range_pct" in route_fn_argnames
        route_supports_gap_return = "gap_return" in route_fn_argnames
        route_supports_trend_up_min_confidence = "trend_up_min_confidence" in route_fn_argnames
        route_supports_trend_down_min_confidence = "trend_down_min_confidence" in route_fn_argnames
        route_supports_range_low_vol_min_confidence = "range_low_vol_min_confidence" in route_fn_argnames
        route_supports_high_rv_min = "high_rv_min" in route_fn_argnames
        route_supports_trend_up_rv_max = "trend_up_rv_max" in route_fn_argnames
        route_supports_trend_down_rv_max = "trend_down_rv_max" in route_fn_argnames
        route_supports_trend_up_entry_bar_range_min_pct = (
            "trend_up_entry_bar_range_min_pct" in route_fn_argnames
        )
        route_supports_trend_down_entry_bar_range_min_pct = (
            "trend_down_entry_bar_range_min_pct" in route_fn_argnames
        )
        route_supports_low_confidence_mr_rv_max = "low_confidence_mr_rv_max" in route_fn_argnames
        route_supports_low_confidence_mr_entry_bar_range_max_pct = (
            "low_confidence_mr_entry_bar_range_max_pct" in route_fn_argnames
        )
        route_supports_low_confidence_skip_rv_min = "low_confidence_skip_rv_min" in route_fn_argnames
        route_supports_low_confidence_skip_entry_bar_range_min_pct = (
            "low_confidence_skip_entry_bar_range_min_pct" in route_fn_argnames
        )
        route_supports_trend_up_overlay_compression_max_range_pct = (
            "trend_up_overlay_compression_max_range_pct" in route_fn_argnames
        )
        route_supports_trend_up_overlay_option_max_entry_bar_range_pct = (
            "trend_up_overlay_option_max_entry_bar_range_pct" in route_fn_argnames
        )
        route_supports_event_gap_tight_entry_bar_range_max_pct = (
            "event_gap_tight_entry_bar_range_max_pct" in route_fn_argnames
        )
        route_supports_event_gap_mid_rv_min = "event_gap_mid_rv_min" in route_fn_argnames
        route_supports_event_gap_mid_rv_max = "event_gap_mid_rv_max" in route_fn_argnames
        route_supports_event_gap_mid_entry_bar_range_max_pct = (
            "event_gap_mid_entry_bar_range_max_pct" in route_fn_argnames
        )
        route_supports_event_gap_overlay_compression_max_range_pct = (
            "event_gap_overlay_compression_max_range_pct" in route_fn_argnames
        )
        route_supports_event_gap_overlay_option_max_entry_bar_range_pct = (
            "event_gap_overlay_option_max_entry_bar_range_pct" in route_fn_argnames
        )
        route_supports_range_low_vol_tight_rv_max = "range_low_vol_tight_rv_max" in route_fn_argnames
        route_supports_range_low_vol_tight_entry_bar_range_max_pct = (
            "range_low_vol_tight_entry_bar_range_max_pct" in route_fn_argnames
        )
        route_supports_transition_high_rv_min = "transition_high_rv_min" in route_fn_argnames
        route_supports_transition_wide_entry_bar_range_min_pct = (
            "transition_wide_entry_bar_range_min_pct" in route_fn_argnames
        )
        regime_v2_decision_time = _parse_hhmm(config.entry_start_time, _default_entry_start(config.opening_range_minutes))
        allowed_weekdays = _parse_allowed_weekdays_et(config.allowed_weekdays_et)
        allowed_trade_dates = _parse_allowed_trade_dates(config.allowed_trade_dates_csv)
        regime_v2_state_counts = _empty_regime_v2_state_counts()
        regime_v2_route_counts = _empty_regime_v2_route_counts()
        regime_v2_selected_variant_counts: Counter[str] = Counter()
        regime_v2_skip_reason_counts: Counter[str] = Counter()
        router_audit_rows: List[Dict[str, Any]] = []
        days_filtered_by_regime_v2_router = 0
        days_filtered_by_allowed_weekdays = 0
        days_filtered_by_allowed_trade_dates = 0

        for day in _iter_dates(config.start.date(), config.end.date()):
            total_days += 1
            if allowed_trade_dates is not None and day not in allowed_trade_dates:
                days_filtered_by_allowed_trade_dates += 1
                continue
            if allowed_weekdays is not None and day.weekday() not in allowed_weekdays:
                days_filtered_by_allowed_weekdays += 1
                continue
            session_bars = session_cache.get(day)
            if session_bars is None:
                session_bars = self._load_session_bars(config.ticker, day)
                session_cache[day] = session_bars
            if not session_bars:
                continue
            days_with_session_data += 1
            session_days.append(day.isoformat())

            vol_regime_prev_close = vol_regime_analytics.previous_close(day)
            if config.require_vol_regime_filter:
                if vol_regime_prev_close is None:
                    days_filtered_by_vol_regime += 1
                    continue
                if (
                    vol_regime_prev_close < float(config.vol_regime_min)
                    or vol_regime_prev_close > float(config.vol_regime_max)
                ):
                    days_filtered_by_vol_regime += 1
                    continue

            opening_range_width = session_analytics.opening_width_pct(day)
            if config.require_or_width_filter:
                min_width = max(float(config.opening_range_min_width_pct), 0.0)
                max_width = max(float(config.opening_range_max_width_pct), min_width)
                if opening_range_width is None or opening_range_width < min_width or opening_range_width > max_width:
                    days_filtered_by_or_width += 1
                    continue

            prior_day_bar = daily_analytics.previous_bar(day=day, lookback=1)
            if config.require_prior_day_inside_bar:
                prior2_day_bar = daily_analytics.previous_bar(day=day, lookback=2)
                if not self._is_inside_bar(inner_bar=prior_day_bar, outer_bar=prior2_day_bar):
                    days_filtered_by_prior_day_inside_bar += 1
                    continue

            if config.require_prior_day_range_filter:
                prior_day_range_pct = self._daily_bar_range_pct(prior_day_bar)
                max_range_pct = max(float(config.prior_day_range_max_pct), 0.0)
                if prior_day_range_pct is None or prior_day_range_pct > max_range_pct:
                    days_filtered_by_prior_day_range += 1
                    continue

            market_regime_label = _normalize_regime_label(regime_day_map.get(day))
            prev_close = daily_analytics.previous_close(day)
            session_open = _safe_float(session_bars[0].get("open")) if session_bars else None
            gap_return = 0.0
            gap_direction = 0
            if (
                session_open is not None
                and session_open > 0.0
                and prev_close is not None
                and prev_close > 0.0
            ):
                gap_return = (float(session_open) / float(prev_close)) - 1.0
                if gap_return > 0:
                    gap_direction = 1
                elif gap_return < 0:
                    gap_direction = -1
            regime_session_bars = _bars_through_et_time(session_bars, regime_v2_decision_time)
            regime_v2 = classify_intraday_macro_regime(
                session_rows=regime_session_bars,
                previous_close=prev_close,
                macro_label=market_regime_label,
                config=regime_v2_cfg,
            )
            regime_v2_state = str(regime_v2.get("state") or "unknown")
            regime_v2_state_counts[regime_v2_state] = int(regime_v2_state_counts.get(regime_v2_state, 0)) + 1
            rel_opening_vol = session_analytics.relative_opening_volume(day, config.relative_volume_lookback_days)
            entry_bar_range_pct = opening_range_width
            route_kwargs: Dict[str, Any] = {
                "base_variant": str(config.strategy_variant or "orb_qc"),
                "base_allow_long": bool(config.allow_long),
                "base_allow_short": bool(config.allow_short),
                "regime_v2_state": regime_v2_state,
                "confidence": float(regime_v2.get("confidence") or 0.0),
                "router_enabled": regime_v2_router_enabled,
                "router_mode": str(config.regime_v2_router_mode or "core"),
                "min_confidence": float(config.regime_v2_min_confidence),
            }
            if route_supports_relative_opening_volume:
                route_kwargs["relative_opening_volume"] = rel_opening_vol
            if route_supports_entry_bar_range_pct:
                route_kwargs["entry_bar_range_pct"] = entry_bar_range_pct
            if route_supports_gap_return:
                route_kwargs["gap_return"] = gap_return
            if route_supports_trend_up_min_confidence:
                route_kwargs["trend_up_min_confidence"] = float(
                    config.regime_v2_router_trend_up_min_confidence
                )
            if route_supports_trend_down_min_confidence:
                route_kwargs["trend_down_min_confidence"] = float(
                    config.regime_v2_router_trend_down_min_confidence
                )
            if route_supports_range_low_vol_min_confidence:
                route_kwargs["range_low_vol_min_confidence"] = float(
                    config.regime_v2_router_range_low_vol_min_confidence
                )
            if route_supports_high_rv_min:
                route_kwargs["high_rv_min"] = float(config.regime_v2_router_high_rv_min)
            if route_supports_trend_up_rv_max:
                route_kwargs["trend_up_rv_max"] = float(config.regime_v2_router_trend_up_rv_max)
            if route_supports_trend_down_rv_max:
                route_kwargs["trend_down_rv_max"] = float(config.regime_v2_router_trend_down_rv_max)
            if route_supports_trend_up_entry_bar_range_min_pct:
                route_kwargs["trend_up_entry_bar_range_min_pct"] = float(
                    config.regime_v2_router_trend_up_entry_bar_range_min_pct
                )
            if route_supports_trend_down_entry_bar_range_min_pct:
                route_kwargs["trend_down_entry_bar_range_min_pct"] = float(
                    config.regime_v2_router_trend_down_entry_bar_range_min_pct
                )
            if route_supports_low_confidence_mr_rv_max:
                route_kwargs["low_confidence_mr_rv_max"] = float(
                    config.regime_v2_router_low_confidence_mr_rv_max
                )
            if route_supports_low_confidence_mr_entry_bar_range_max_pct:
                route_kwargs["low_confidence_mr_entry_bar_range_max_pct"] = float(
                    config.regime_v2_router_low_confidence_mr_entry_bar_range_max_pct
                )
            if route_supports_low_confidence_skip_rv_min:
                route_kwargs["low_confidence_skip_rv_min"] = float(
                    config.regime_v2_router_low_confidence_skip_rv_min
                )
            if route_supports_low_confidence_skip_entry_bar_range_min_pct:
                route_kwargs["low_confidence_skip_entry_bar_range_min_pct"] = float(
                    config.regime_v2_router_low_confidence_skip_entry_bar_range_min_pct
                )
            if route_supports_trend_up_overlay_compression_max_range_pct:
                route_kwargs["trend_up_overlay_compression_max_range_pct"] = float(
                    config.regime_v2_router_trend_up_overlay_compression_max_range_pct
                )
            if route_supports_trend_up_overlay_option_max_entry_bar_range_pct:
                route_kwargs["trend_up_overlay_option_max_entry_bar_range_pct"] = float(
                    config.regime_v2_router_trend_up_overlay_option_max_entry_bar_range_pct
                )
            if route_supports_event_gap_tight_entry_bar_range_max_pct:
                route_kwargs["event_gap_tight_entry_bar_range_max_pct"] = float(
                    config.regime_v2_router_event_gap_tight_entry_bar_range_max_pct
                )
            if route_supports_event_gap_mid_rv_min:
                route_kwargs["event_gap_mid_rv_min"] = float(config.regime_v2_router_event_gap_mid_rv_min)
            if route_supports_event_gap_mid_rv_max:
                route_kwargs["event_gap_mid_rv_max"] = float(config.regime_v2_router_event_gap_mid_rv_max)
            if route_supports_event_gap_mid_entry_bar_range_max_pct:
                route_kwargs["event_gap_mid_entry_bar_range_max_pct"] = float(
                    config.regime_v2_router_event_gap_mid_entry_bar_range_max_pct
                )
            if route_supports_event_gap_overlay_compression_max_range_pct:
                route_kwargs["event_gap_overlay_compression_max_range_pct"] = float(
                    config.regime_v2_router_event_gap_overlay_compression_max_range_pct
                )
            if route_supports_event_gap_overlay_option_max_entry_bar_range_pct:
                route_kwargs["event_gap_overlay_option_max_entry_bar_range_pct"] = float(
                    config.regime_v2_router_event_gap_overlay_option_max_entry_bar_range_pct
                )
            if route_supports_range_low_vol_tight_rv_max:
                route_kwargs["range_low_vol_tight_rv_max"] = float(
                    config.regime_v2_router_range_low_vol_tight_rv_max
                )
            if route_supports_range_low_vol_tight_entry_bar_range_max_pct:
                route_kwargs["range_low_vol_tight_entry_bar_range_max_pct"] = float(
                    config.regime_v2_router_range_low_vol_tight_entry_bar_range_max_pct
                )
            if route_supports_transition_high_rv_min:
                route_kwargs["transition_high_rv_min"] = float(config.regime_v2_router_transition_high_rv_min)
            if route_supports_transition_wide_entry_bar_range_min_pct:
                route_kwargs["transition_wide_entry_bar_range_min_pct"] = float(
                    config.regime_v2_router_transition_wide_entry_bar_range_min_pct
                )
            route = _route_strategy_for_regime_v2(
                **route_kwargs,
            )
            route_state = str(route.get("route_state") or regime_v2_state)
            route_overrides = dict(route.get("setup_overrides") or {})
            route_overlay_name = str(route.get("route_overlay_name") or "")
            regime_v2_route_counts[route_state] = int(regime_v2_route_counts.get(route_state, 0)) + 1
            if regime_v2_router_enabled:
                router_audit_rows.append(
                    {
                        "day": day.isoformat(),
                        "regime_v2_state": regime_v2_state,
                        "regime_v2_route_state": route_state,
                        "regime_v2_route_action": str(route.get("route_action") or ""),
                        "regime_v2_confidence": float(regime_v2.get("confidence") or 0.0),
                        "regime_v2_selected_variant": str(route.get("selected_variant") or config.strategy_variant or ""),
                        "regime_v2_skip_reason": str(route.get("skip_reason") or ""),
                        "regime_v2_route_overlay_name": route_overlay_name,
                        "gap_return": (_safe_float(gap_return) if _safe_float(gap_return) is not None else 0.0),
                        "relative_opening_volume": _safe_float(rel_opening_vol),
                        "entry_bar_range_pct": _safe_float(entry_bar_range_pct),
                    }
                )
            if bool(route.get("skip_day")):
                skip_reason = str(route.get("skip_reason") or route_state or "unknown_state_skip")
                regime_v2_skip_reason_counts[skip_reason] += 1
                days_filtered_by_regime_v2_router += 1
                continue
            selected_variant = str(route.get("selected_variant") or config.strategy_variant or "").strip()
            if selected_variant:
                regime_v2_selected_variant_counts[selected_variant] += 1
            atr_value = daily_analytics.atr(day=day, lookback_days=config.atr_lookback_days)

            strategy_cfg = IntradayStrategyConfig(
                opening_range_minutes=config.opening_range_minutes,
                entry_start_time=config.entry_start_time,
                entry_cutoff_time=config.entry_cutoff_time,
                exit_time=config.exit_time,
                strategy_variant=str(route.get("selected_variant") or config.strategy_variant),
                allow_long=bool(route.get("allow_long")) if "allow_long" in route else bool(config.allow_long),
                allow_short=bool(route.get("allow_short")) if "allow_short" in route else bool(config.allow_short),
                use_opening_bar_direction=config.use_opening_bar_direction,
                require_breakout_open_inside_range=config.require_breakout_open_inside_range,
                entry_trigger_mode=config.entry_trigger_mode,
                stop_mode=config.stop_mode,
                stop_loss_atr_distance=config.stop_loss_atr_distance,
                take_profit_rr=config.take_profit_rr,
                break_even_trigger_rr=config.break_even_trigger_rr,
                exit_on_opposite_candle=config.exit_on_opposite_candle,
                opposite_candle_min_hold_minutes=config.opposite_candle_min_hold_minutes,
                early_fail_minutes=config.early_fail_minutes,
                early_fail_min_rr=config.early_fail_min_rr,
                max_hold_minutes=config.max_hold_minutes,
                fib_entry_level_low=config.fib_entry_level_low,
                fib_entry_level_high=config.fib_entry_level_high,
                fib_target_extension=config.fib_target_extension,
                fib_require_confirmation=config.fib_require_confirmation,
                mr_band_or_mult=config.mr_band_or_mult,
                mr_min_distance_from_vwap_pct=config.mr_min_distance_from_vwap_pct,
                mr_reentry_buffer_or_mult=config.mr_reentry_buffer_or_mult,
                mr_stop_buffer_or_mult=config.mr_stop_buffer_or_mult,
                mr_take_profit_mode=config.mr_take_profit_mode,
                mr_take_profit_rr=config.mr_take_profit_rr,
                mr_require_reversal_candle=config.mr_require_reversal_candle,
                mr_zscore_window=config.mr_zscore_window,
                mr_zscore_entry=config.mr_zscore_entry,
                mr_zscore_reentry=config.mr_zscore_reentry,
                mr_zscore_stop=config.mr_zscore_stop,
                mr_zscore_target=config.mr_zscore_target,
                mr_sigma_min_pct=config.mr_sigma_min_pct,
                mr_sigma_max_pct=config.mr_sigma_max_pct,
                mr_vwap_slope_lookback=config.mr_vwap_slope_lookback,
                mr_vwap_slope_max_pct=config.mr_vwap_slope_max_pct,
                mr_overnight_abs_return_min=config.mr_overnight_abs_return_min,
                mr_overnight_close_to_range_extreme_pct=config.mr_overnight_close_to_range_extreme_pct,
                mr_overnight_efficiency_ratio_max=config.mr_overnight_efficiency_ratio_max,
                mr_overnight_min_session_range_pct=config.mr_overnight_min_session_range_pct,
                mr_adaptive_enabled=config.mr_adaptive_enabled,
                mr_adaptive_entry_min=config.mr_adaptive_entry_min,
                mr_adaptive_entry_max=config.mr_adaptive_entry_max,
                mr_adaptive_stop_min=config.mr_adaptive_stop_min,
                mr_adaptive_stop_max=config.mr_adaptive_stop_max,
                mr_adaptive_trend_weight=config.mr_adaptive_trend_weight,
                mr_adaptive_vol_weight=config.mr_adaptive_vol_weight,
                mr_session_extension_min_or_frac=config.mr_session_extension_min_or_frac,
                mr_reversal_body_min_frac=config.mr_reversal_body_min_frac,
                mr_reversal_wick_min_frac=config.mr_reversal_wick_min_frac,
                mr_trend_ema_spread_max_pct=config.mr_trend_ema_spread_max_pct,
                mr_volume_climax_multiple_min=config.mr_volume_climax_multiple_min,
                mr_trend_day_max_move_pct=config.mr_trend_day_max_move_pct,
                mr_time_to_work_bars=config.mr_time_to_work_bars,
                mr_time_to_work_min_rr=config.mr_time_to_work_min_rr,
                mr_target_stretch_frac=config.mr_target_stretch_frac,
                pairs_hedge_ticker=config.pairs_hedge_ticker,
                pairs_beta_lookback=config.pairs_beta_lookback,
                pairs_zscore_window=config.pairs_zscore_window,
                pairs_zscore_entry=config.pairs_zscore_entry,
                pairs_zscore_reentry=config.pairs_zscore_reentry,
                pairs_zscore_exit=config.pairs_zscore_exit,
                pairs_zscore_stop=config.pairs_zscore_stop,
                pairs_min_correlation=config.pairs_min_correlation,
                pairs_excluded_tickers=config.pairs_excluded_tickers,
                dispersion_proxy_ticker=config.dispersion_proxy_ticker,
                dispersion_beta_lookback=config.dispersion_beta_lookback,
                dispersion_zscore_window=config.dispersion_zscore_window,
                dispersion_zscore_entry=config.dispersion_zscore_entry,
                dispersion_zscore_reentry=config.dispersion_zscore_reentry,
                dispersion_zscore_exit=config.dispersion_zscore_exit,
                dispersion_zscore_stop=config.dispersion_zscore_stop,
                dispersion_min_correlation=config.dispersion_min_correlation,
                dispersion_rel_strength_entry_pct=config.dispersion_rel_strength_entry_pct,
                dispersion_rel_strength_exit_pct=config.dispersion_rel_strength_exit_pct,
                dispersion_rel_strength_stop_pct=config.dispersion_rel_strength_stop_pct,
                dispersion_primary_min_abs_move_pct=config.dispersion_primary_min_abs_move_pct,
                dispersion_proxy_max_abs_move_pct=config.dispersion_proxy_max_abs_move_pct,
                dispersion_rel_strength_confirm_pct=config.dispersion_rel_strength_confirm_pct,
                dispersion_zscore_improvement_min=config.dispersion_zscore_improvement_min,
                dispersion_reversal_body_min_frac=config.dispersion_reversal_body_min_frac,
                dispersion_reversal_wick_min_frac=config.dispersion_reversal_wick_min_frac,
                dispersion_beta_shock_max_pct=config.dispersion_beta_shock_max_pct,
                dispersion_time_to_work_bars=config.dispersion_time_to_work_bars,
                dispersion_time_to_work_improvement_min=config.dispersion_time_to_work_improvement_min,
                dispersion_breakout_rel_strength_floor_frac=config.dispersion_breakout_rel_strength_floor_frac,
                trend_pullback_max_bars_after_breakout=config.trend_pullback_max_bars_after_breakout,
                trend_pullback_ema_buffer_pct=config.trend_pullback_ema_buffer_pct,
                trend_pullback_require_orb_reclaim=config.trend_pullback_require_orb_reclaim,
                trend_pullback_min_breakout_or_frac=config.trend_pullback_min_breakout_or_frac,
                trend_pullback_min_volume_multiple=config.trend_pullback_min_volume_multiple,
                drive_min_abs_return_pct=config.drive_min_abs_return_pct,
                drive_close_location_min=config.drive_close_location_min,
                drive_pullback_min_retrace_frac=config.drive_pullback_min_retrace_frac,
                drive_pullback_max_retrace_frac=config.drive_pullback_max_retrace_frac,
                drive_touch_ma_buffer_pct=config.drive_touch_ma_buffer_pct,
                drive_reclaim_close_location_min=config.drive_reclaim_close_location_min,
                drive_reclaim_min_volume_multiple=config.drive_reclaim_min_volume_multiple,
                drive_pullback_require_hold_drive_open=config.drive_pullback_require_hold_drive_open,
                drive_reclaim_requires_prev_extreme_break=config.drive_reclaim_requires_prev_extreme_break,
                drive_stop_buffer_range_frac=config.drive_stop_buffer_range_frac,
                drive_max_pullback_bars=config.drive_max_pullback_bars,
                event_gap_abs_return=abs(float(regime_v2.get("gap_return") or gap_return)),
                event_gap_direction=(
                    int(gap_direction) if gap_direction in (-1, 1) else int(config.event_gap_direction)
                ),
                event_drive_min_gap_abs_return=config.event_drive_min_gap_abs_return,
                event_drive_min_breakout_or_frac=config.event_drive_min_breakout_or_frac,
                event_drive_close_location_min=config.event_drive_close_location_min,
                event_drive_min_volume_multiple=config.event_drive_min_volume_multiple,
                compression_lookback_bars=config.compression_lookback_bars,
                compression_max_range_pct=float(
                    route_overrides.get("compression_max_range_pct")
                    if "compression_max_range_pct" in route_overrides
                    else config.compression_max_range_pct
                ),
                compression_breakout_buffer_or_frac=config.compression_breakout_buffer_or_frac,
                compression_min_volume_multiple=config.compression_min_volume_multiple,
                momentum_breakout_min_or_frac=config.momentum_breakout_min_or_frac,
                momentum_breakout_max_or_frac=config.momentum_breakout_max_or_frac,
                momentum_close_location_min=config.momentum_close_location_min,
                momentum_min_ema_spread_pct=config.momentum_min_ema_spread_pct,
                momentum_pullback_to_ema_max_pct=config.momentum_pullback_to_ema_max_pct,
                momentum_confirmation_bars=config.momentum_confirmation_bars,
                momentum_volume_multiple_min=config.momentum_volume_multiple_min,
                momentum_min_body_or_frac=config.momentum_min_body_or_frac,
                momentum_max_opposite_wick_body_ratio=config.momentum_max_opposite_wick_body_ratio,
                momentum_atr_range_min=config.momentum_atr_range_min,
                momentum_trend_bars_min=config.momentum_trend_bars_min,
                momentum_adx_period=config.momentum_adx_period,
                momentum_adx_min=config.momentum_adx_min,
                require_relative_volume=config.require_relative_volume,
                relative_volume_min=config.relative_volume_min,
                relative_volume_max=config.relative_volume_max,
                relative_volume_lookback_days=config.relative_volume_lookback_days,
                require_premarket_context=config.require_premarket_context,
                premarket_bars_min=config.premarket_bars_min,
                premarket_volume_pct_adv_min=config.premarket_volume_pct_adv_min,
                premarket_gap_abs_return_min=config.premarket_gap_abs_return_min,
                premarket_range_min_pct=config.premarket_range_min_pct,
                premarket_range_max_pct=config.premarket_range_max_pct,
                recent_daily_volume_ratio_min=config.recent_daily_volume_ratio_min,
                require_atr_filter=config.require_atr_filter,
                atr_min=config.atr_min,
                volume_ma_window=config.volume_ma_window,
                volume_spike_multiple=config.volume_spike_multiple,
                trend_ema_fast=config.trend_ema_fast,
                trend_ema_slow=config.trend_ema_slow,
                require_fvg=config.require_fvg,
                require_volume_spike=config.require_volume_spike,
                require_trend_alignment=config.require_trend_alignment,
                require_or_width_filter=config.require_or_width_filter,
                opening_range_min_width_pct=config.opening_range_min_width_pct,
                opening_range_max_width_pct=config.opening_range_max_width_pct,
                require_macro_release_filter=config.require_macro_release_filter,
                macro_release_times_et=config.macro_release_times_et,
                macro_post_release_block_minutes=config.macro_post_release_block_minutes,
                option_min_open_interest=config.option_min_open_interest,
                require_option_microstructure_filter=config.require_option_microstructure_filter,
                option_min_entry_volume=config.option_min_entry_volume,
                option_max_entry_bar_range_pct=float(
                    route_overrides.get("option_max_entry_bar_range_pct")
                    if "option_max_entry_bar_range_pct" in route_overrides
                    else config.option_max_entry_bar_range_pct
                ),
                option_min_entry_price=config.option_min_entry_price,
            )
            pair_session_bars: Optional[List[Dict[str, Any]]] = None
            strategy_variant = str(strategy_cfg.strategy_variant or "").strip().lower()
            if strategy_variant in {
                "pairs_spread_v1",
                "dispersion_relative_breakout_v1",
                "dispersion_relative_revert_v1",
                "relative_strength_continuation_v1",
                "proxy_vwap_reclaim_v1",
            }:
                if strategy_variant == "pairs_spread_v1":
                    hedge_ticker = resolve_pairs_hedge_ticker(config.ticker, strategy_cfg.pairs_hedge_ticker)
                else:
                    hedge_ticker = resolve_dispersion_proxy_ticker(config.ticker, strategy_cfg.dispersion_proxy_ticker)
                if hedge_ticker:
                    if hedge_ticker == str(config.ticker or "").strip().upper():
                        pair_session_bars = session_bars
                    else:
                        pair_session_bars = self._load_session_bars(hedge_ticker, day)

            lfcm_context: Optional[Dict[str, Any]] = None
            if strategy_variant == "lfcm_v1":
                lfcm_context = self._get_lfcm_context(
                    ticker=config.ticker,
                    day=day,
                    prev_close=prev_close,
                    avg_daily_volume=daily_analytics.avg_daily_volume(day, lookback_days=20),
                )
            preopen_context: Optional[Dict[str, Any]] = None
            if needs_premarket_context:
                preopen_context = self._get_preopen_context(
                    ticker=config.ticker,
                    day=day,
                    prev_close=prev_close,
                    daily_analytics=daily_analytics,
                    vol_regime_prev_close=vol_regime_prev_close,
                    vol_regime_analytics=vol_regime_analytics,
                )

            setup, setup_audit = _find_intraday_setup_with_audit(
                session_bars=session_bars,
                cfg=strategy_cfg,
                relative_opening_volume=rel_opening_vol,
                atr_value=atr_value,
                pair_session_bars=pair_session_bars,
                lfcm_context=lfcm_context,
                preopen_context=preopen_context,
            )
            setup_audit_days += 1
            setup_opportunities_before_filters_total += int(setup_audit.get("opportunities_before_filters") or 0)
            setup_opportunities_after_filters_total += int(setup_audit.get("opportunities_after_filters") or 0)
            for label, amount in dict(setup_audit.get("rejections") or {}).items():
                label_text = str(label or "").strip() or "unknown"
                setup_rejection_counts_total[label_text] = (
                    int(setup_rejection_counts_total.get(label_text) or 0) + int(amount or 0)
                )
            if setup is None:
                no_setup_days += 1
                continue
            self._bump_option_funnel("setups_found")
            setup["market_regime_label"] = market_regime_label
            setup["regime_v2_state"] = regime_v2_state
            setup["regime_v2_route_state"] = route_state
            setup["regime_v2_route_action"] = str(route.get("route_action") or "")
            setup["regime_v2_confidence"] = float(regime_v2.get("confidence") or 0.0)
            setup["regime_v2_selected_variant"] = str(route.get("selected_variant") or config.strategy_variant)
            setup["regime_v2_skip_reason"] = str(route.get("skip_reason") or "")
            setup["regime_v2_route_overlay_name"] = route_overlay_name
            setup["regime_v2_setup_overrides"] = dict(route_overrides)
            setup["gap_return"] = (_safe_float(gap_return) if _safe_float(gap_return) is not None else 0.0)
            setup_regime_label_counts[market_regime_label] = (
                int(setup_regime_label_counts.get(market_regime_label, 0)) + 1
            )
            if regime_gate_enabled and market_regime_label not in regime_gate_allowed_labels:
                setups_filtered_by_regime_gate += 1
                continue
            setup["vol_regime_prev_close"] = vol_regime_prev_close
            setup_days += 1
            self._bump_option_funnel("setups_passed_signal_filters")
            setup_days_list.append(day.isoformat())

            strategy_variant = str(setup.get("strategy_variant") or strategy_cfg.strategy_variant or "").strip().lower()
            if strategy_variant == "mr_overnight_regime_v1":
                exit_plan = self._resolve_overnight_exit_plan(
                    ticker=config.ticker,
                    entry_day=day,
                    setup=setup,
                    session_cache=session_cache,
                )
            else:
                exit_plan = resolve_intraday_exit(
                    session_bars=session_bars,
                    setup=setup,
                    cfg=strategy_cfg,
                    pair_session_bars=pair_session_bars,
                )
            if exit_plan is None:
                continue
            self._bump_option_funnel("setups_with_exit_plan")

            if self._daily_trade_count(trades, day, config.ticker) >= max(config.max_trades_per_day, 1):
                continue
            self._bump_option_funnel("setups_after_trade_limits")

            if bool(config.enable_underlying_shadow_mode):
                if self._daily_trade_count(underlying_shadow_trades, day, config.ticker) < max(config.max_trades_per_day, 1):
                    shadow_trade = self._simulate_stock_trade(
                        ticker=config.ticker,
                        setup=setup,
                        exit_plan=exit_plan,
                        current_equity=underlying_shadow_equity,
                        config=config,
                    )
                    if shadow_trade is not None:
                        underlying_shadow_trades.append(shadow_trade)
                        underlying_shadow_equity += float(shadow_trade.pnl)
                        underlying_shadow_returns.append(float(shadow_trade.return_pct))

            trade: Optional[BacktestTrade] = None
            if config.instrument_mode == "stocks":
                trade = self._simulate_stock_trade(
                    ticker=config.ticker,
                    setup=setup,
                    exit_plan=exit_plan,
                    current_equity=equity,
                    config=config,
                )
            else:
                option_trade_attempts += 1
                if config.option_mode in {"auto", "historical"}:
                    trade = self._simulate_historical_option_trade(
                        ticker=config.ticker,
                        day=day,
                        setup=setup,
                        exit_plan=exit_plan,
                        current_equity=equity,
                        config=config,
                    )
                    if trade is not None:
                        historical_fills += 1

                if trade is None and config.option_mode == "historical":
                    skipped_no_option_data += 1
                    continue

                if trade is None:
                    trade = self._simulate_proxy_option_trade(
                        ticker=config.ticker,
                        setup=setup,
                        exit_plan=exit_plan,
                        current_equity=equity,
                        config=config,
                    )
                    proxy_fills += 1

            if trade is None:
                continue

            trades.append(trade)
            equity += float(trade.pnl)
            returns.append(float(trade.return_pct))
            if config.instrument_mode != "stocks":
                option_trade_executed += 1
            trade_regime_label_counts[market_regime_label] = (
                int(trade_regime_label_counts.get(market_regime_label, 0)) + 1
            )

        if config.persist_trades and trades:
            self.store.insert_backtest_trades(trades)

        summary = _summarize_trades(
            trades=trades,
            returns=returns,
            initial_equity=config.initial_equity,
            final_equity=equity,
            start=config.start,
            end=config.end,
        )
        underlying_shadow_summary = _summarize_trades(
            trades=underlying_shadow_trades,
            returns=underlying_shadow_returns,
            initial_equity=config.initial_equity,
            final_equity=underlying_shadow_equity,
            start=config.start,
            end=config.end,
        )
        summary.update(
            {
                "strategy": "intraday_opening_range_stocks_in_play_options",
                "ticker": config.ticker,
                "instrument_mode": config.instrument_mode,
                "option_mode": config.option_mode,
                "option_min_open_interest": config.option_min_open_interest,
                "require_option_microstructure_filter": config.require_option_microstructure_filter,
                "option_min_entry_volume": config.option_min_entry_volume,
                "option_max_entry_bar_range_pct": config.option_max_entry_bar_range_pct,
                "option_min_entry_price": config.option_min_entry_price,
                "option_selection_intrinsic_weight": float(config.option_selection_intrinsic_weight),
                "option_selection_min_intrinsic_share": float(config.option_selection_min_intrinsic_share),
                "option_min_expected_move_to_extrinsic_ratio": float(config.option_min_expected_move_to_extrinsic_ratio),
                "option_min_expected_move_to_spread_ratio": float(config.option_min_expected_move_to_spread_ratio),
                "option_min_expected_move_to_debit_ratio": float(config.option_min_expected_move_to_debit_ratio),
                "option_structure_filter_enabled": bool(config.option_structure_filter_enabled),
                "option_structure_min_open_interest": int(config.option_structure_min_open_interest),
                "option_structure_min_entry_volume": int(config.option_structure_min_entry_volume),
                "option_structure_max_entry_spread_pct": float(config.option_structure_max_entry_spread_pct),
                "option_structure_max_entry_bar_range_pct": float(config.option_structure_max_entry_bar_range_pct),
                "option_structure_min_entry_price": float(config.option_structure_min_entry_price),
                "signal_cadence": str(config.signal_cadence or "intraday"),
                "strategy_sleeve": str(config.strategy_sleeve or "tactical_intraday"),
                "sleeve": str(config.strategy_sleeve or "tactical_intraday"),
                "asset_bucket": str(config.asset_bucket or infer_asset_bucket(config.ticker)),
                "forecast_group": str(config.forecast_group or ""),
                "forecast_family": str(config.forecast_family or ""),
                "forecast_weight": float(config.forecast_weight),
                "combined_forecast": 0.0,
                "forecast_turnover": 0.0,
                "portfolio_target_vol_annualized": float(config.portfolio_target_vol_annualized),
                "premium_at_risk_pct_nav": 0.0,
                "risk_budget_share": float(config.risk_budget_share),
                "option_microstructure_gate_mode": str(config.option_microstructure_gate_mode or "absolute"),
                "option_tradability_availability_mode": str(
                    config.option_tradability_availability_mode or "strict_historical"
                ),
                "quote_coverage_pct": 0.0,
                "chain_coverage_pct": 0.0,
                "cost_speed_limit_ratio": 0.0,
                "overlay_enabled": bool(config.overlay_enabled),
                "overlay_veto_count": 0,
                "overlay_scale_up_count": 0,
                "overlay_scale_down_count": 0,
                "lookback_fast": int(config.lookback_fast),
                "lookback_slow": int(config.lookback_slow),
                "lookback_breakout": int(config.lookback_breakout),
                "lookback_relative": int(config.lookback_relative),
                "forecast_cap": float(config.forecast_cap),
                "vol_attenuation_enabled": bool(config.vol_attenuation_enabled),
                "vol_percentile_lookback": int(config.vol_percentile_lookback),
                "vol_attenuation_hi_pct": float(config.vol_attenuation_hi_pct),
                "vol_attenuation_extreme_pct": float(config.vol_attenuation_extreme_pct),
                "enforce_option_liquidity_caps": config.enforce_option_liquidity_caps,
                "option_max_entry_volume_participation": config.option_max_entry_volume_participation,
                "option_max_open_interest_participation": config.option_max_open_interest_participation,
                "option_open_interest_liquidity_cap_enabled": bool(
                    config.enforce_option_liquidity_caps
                    and float(config.option_max_open_interest_participation) > 0.0
                ),
                "option_range_adverse_fill_fraction": config.option_range_adverse_fill_fraction,
                "option_range_adverse_fill_max_bps": config.option_range_adverse_fill_max_bps,
                "use_option_quotes_for_fills": config.use_option_quotes_for_fills,
                "option_quote_fill_fallback_to_bar_close": config.option_quote_fill_fallback_to_bar_close,
                "option_max_entry_spread_pct": config.option_max_entry_spread_pct,
                "option_take_profit_pct": config.option_take_profit_pct,
                "option_max_loss_pct": config.option_max_loss_pct,
                "option_use_contract_open_interest": config.option_use_contract_open_interest,
                "opening_range_minutes": config.opening_range_minutes,
                "entry_cutoff_time": config.entry_cutoff_time,
                "allowed_weekdays_et": str(config.allowed_weekdays_et or ""),
                "strategy_variant": config.strategy_variant,
                "entry_trigger_mode": config.entry_trigger_mode,
                "stop_mode": config.stop_mode,
                "take_profit_rr": config.take_profit_rr,
                "break_even_trigger_rr": config.break_even_trigger_rr,
                "opposite_candle_min_hold_minutes": config.opposite_candle_min_hold_minutes,
                "early_fail_minutes": config.early_fail_minutes,
                "early_fail_min_rr": config.early_fail_min_rr,
                "max_hold_minutes": config.max_hold_minutes,
                "execution_entry_delay_minutes": config.execution_entry_delay_minutes,
                "execution_exit_delay_minutes": config.execution_exit_delay_minutes,
                "execution_delay_randomization": config.execution_delay_randomization,
                "execution_entry_delay_jitter_minutes": config.execution_entry_delay_jitter_minutes,
                "execution_exit_delay_jitter_minutes": config.execution_exit_delay_jitter_minutes,
                "execution_delay_random_seed": config.execution_delay_random_seed,
                "fib_entry_level_low": config.fib_entry_level_low,
                "fib_entry_level_high": config.fib_entry_level_high,
                "fib_target_extension": config.fib_target_extension,
                "fib_require_confirmation": config.fib_require_confirmation,
                "mr_band_or_mult": config.mr_band_or_mult,
                "mr_min_distance_from_vwap_pct": config.mr_min_distance_from_vwap_pct,
                "mr_reentry_buffer_or_mult": config.mr_reentry_buffer_or_mult,
                "mr_stop_buffer_or_mult": config.mr_stop_buffer_or_mult,
                "mr_take_profit_mode": config.mr_take_profit_mode,
                "mr_take_profit_rr": config.mr_take_profit_rr,
                "mr_require_reversal_candle": config.mr_require_reversal_candle,
                "mr_zscore_window": config.mr_zscore_window,
                "mr_zscore_entry": config.mr_zscore_entry,
                "mr_zscore_reentry": config.mr_zscore_reentry,
                "mr_zscore_stop": config.mr_zscore_stop,
                "mr_zscore_target": config.mr_zscore_target,
                "mr_sigma_min_pct": config.mr_sigma_min_pct,
                "mr_sigma_max_pct": config.mr_sigma_max_pct,
                "mr_vwap_slope_lookback": config.mr_vwap_slope_lookback,
                "mr_vwap_slope_max_pct": config.mr_vwap_slope_max_pct,
                "mr_adaptive_enabled": bool(config.mr_adaptive_enabled),
                "mr_adaptive_entry_min": float(config.mr_adaptive_entry_min),
                "mr_adaptive_entry_max": float(config.mr_adaptive_entry_max),
                "mr_adaptive_stop_min": float(config.mr_adaptive_stop_min),
                "mr_adaptive_stop_max": float(config.mr_adaptive_stop_max),
                "mr_adaptive_trend_weight": float(config.mr_adaptive_trend_weight),
                "mr_adaptive_vol_weight": float(config.mr_adaptive_vol_weight),
                "mr_session_extension_min_or_frac": float(config.mr_session_extension_min_or_frac),
                "mr_reversal_body_min_frac": float(config.mr_reversal_body_min_frac),
                "mr_reversal_wick_min_frac": float(config.mr_reversal_wick_min_frac),
                "mr_trend_ema_spread_max_pct": float(config.mr_trend_ema_spread_max_pct),
                "mr_volume_climax_multiple_min": float(config.mr_volume_climax_multiple_min),
                "mr_trend_day_max_move_pct": float(config.mr_trend_day_max_move_pct),
                "mr_time_to_work_bars": int(config.mr_time_to_work_bars),
                "mr_time_to_work_min_rr": float(config.mr_time_to_work_min_rr),
                "mr_target_stretch_frac": float(config.mr_target_stretch_frac),
                "pairs_hedge_ticker": str(config.pairs_hedge_ticker),
                "pairs_beta_lookback": int(config.pairs_beta_lookback),
                "pairs_zscore_window": int(config.pairs_zscore_window),
                "pairs_zscore_entry": float(config.pairs_zscore_entry),
                "pairs_zscore_reentry": float(config.pairs_zscore_reentry),
                "pairs_zscore_exit": float(config.pairs_zscore_exit),
                "pairs_zscore_stop": float(config.pairs_zscore_stop),
                "pairs_min_correlation": float(config.pairs_min_correlation),
                "dispersion_proxy_ticker": str(config.dispersion_proxy_ticker),
                "dispersion_beta_lookback": int(config.dispersion_beta_lookback),
                "dispersion_zscore_window": int(config.dispersion_zscore_window),
                "dispersion_zscore_entry": float(config.dispersion_zscore_entry),
                "dispersion_zscore_reentry": float(config.dispersion_zscore_reentry),
                "dispersion_zscore_exit": float(config.dispersion_zscore_exit),
                "dispersion_zscore_stop": float(config.dispersion_zscore_stop),
                "dispersion_min_correlation": float(config.dispersion_min_correlation),
                "dispersion_rel_strength_entry_pct": float(config.dispersion_rel_strength_entry_pct),
                "dispersion_rel_strength_exit_pct": float(config.dispersion_rel_strength_exit_pct),
                "dispersion_rel_strength_stop_pct": float(config.dispersion_rel_strength_stop_pct),
                "dispersion_primary_min_abs_move_pct": float(config.dispersion_primary_min_abs_move_pct),
                "dispersion_proxy_max_abs_move_pct": float(config.dispersion_proxy_max_abs_move_pct),
                "dispersion_rel_strength_confirm_pct": float(config.dispersion_rel_strength_confirm_pct),
                "dispersion_zscore_improvement_min": float(config.dispersion_zscore_improvement_min),
                "dispersion_reversal_body_min_frac": float(config.dispersion_reversal_body_min_frac),
                "dispersion_reversal_wick_min_frac": float(config.dispersion_reversal_wick_min_frac),
                "dispersion_beta_shock_max_pct": float(config.dispersion_beta_shock_max_pct),
                "dispersion_time_to_work_bars": int(config.dispersion_time_to_work_bars),
                "dispersion_time_to_work_improvement_min": float(config.dispersion_time_to_work_improvement_min),
                "dispersion_breakout_rel_strength_floor_frac": float(config.dispersion_breakout_rel_strength_floor_frac),
                "trend_pullback_max_bars_after_breakout": int(config.trend_pullback_max_bars_after_breakout),
                "trend_pullback_ema_buffer_pct": float(config.trend_pullback_ema_buffer_pct),
                "trend_pullback_require_orb_reclaim": bool(config.trend_pullback_require_orb_reclaim),
                "trend_pullback_min_breakout_or_frac": float(config.trend_pullback_min_breakout_or_frac),
                "trend_pullback_min_volume_multiple": float(config.trend_pullback_min_volume_multiple),
                "drive_min_abs_return_pct": float(config.drive_min_abs_return_pct),
                "drive_close_location_min": float(config.drive_close_location_min),
                "drive_pullback_min_retrace_frac": float(config.drive_pullback_min_retrace_frac),
                "drive_pullback_max_retrace_frac": float(config.drive_pullback_max_retrace_frac),
                "drive_touch_ma_buffer_pct": float(config.drive_touch_ma_buffer_pct),
                "drive_reclaim_close_location_min": float(config.drive_reclaim_close_location_min),
                "drive_reclaim_min_volume_multiple": float(config.drive_reclaim_min_volume_multiple),
                "drive_pullback_require_hold_drive_open": bool(config.drive_pullback_require_hold_drive_open),
                "drive_reclaim_requires_prev_extreme_break": bool(config.drive_reclaim_requires_prev_extreme_break),
                "drive_stop_buffer_range_frac": float(config.drive_stop_buffer_range_frac),
                "drive_max_pullback_bars": int(config.drive_max_pullback_bars),
                "event_drive_min_gap_abs_return": float(config.event_drive_min_gap_abs_return),
                "event_drive_min_breakout_or_frac": float(config.event_drive_min_breakout_or_frac),
                "event_drive_close_location_min": float(config.event_drive_close_location_min),
                "event_drive_min_volume_multiple": float(config.event_drive_min_volume_multiple),
                "compression_lookback_bars": int(config.compression_lookback_bars),
                "compression_max_range_pct": float(config.compression_max_range_pct),
                "compression_breakout_buffer_or_frac": float(config.compression_breakout_buffer_or_frac),
                "compression_min_volume_multiple": float(config.compression_min_volume_multiple),
                "require_vol_regime_filter": config.require_vol_regime_filter,
                "vol_regime_ticker_requested": config.vol_regime_ticker,
                "vol_regime_ticker_used": vol_regime_ticker_used,
                "vol_regime_min": config.vol_regime_min,
                "vol_regime_max": config.vol_regime_max,
                "regime_gate_enabled": regime_gate_enabled,
                "regime_gate_model": str(config.regime_gate_model or "threshold"),
                "regime_gate_allowed_labels": sorted(regime_gate_allowed_labels),
                "setups_filtered_by_regime_gate": setups_filtered_by_regime_gate,
                "regime_v2_enabled": bool(config.regime_v2_enabled),
                "regime_v2_router_enabled": bool(regime_v2_router_enabled),
                "regime_v2_router_requested": bool(regime_v2_router_requested),
                "regime_v2_router_config_warning": regime_v2_router_config_warning,
                "regime_v2_router_mode": str(config.regime_v2_router_mode or "core"),
                "regime_v2_min_confidence": float(config.regime_v2_min_confidence),
                "regime_v2_router_high_rv_min": float(config.regime_v2_router_high_rv_min),
                "regime_v2_router_trend_up_rv_max": float(config.regime_v2_router_trend_up_rv_max),
                "regime_v2_router_trend_down_rv_max": float(config.regime_v2_router_trend_down_rv_max),
                "regime_v2_router_trend_up_entry_bar_range_min_pct": float(
                    config.regime_v2_router_trend_up_entry_bar_range_min_pct
                ),
                "regime_v2_router_trend_down_entry_bar_range_min_pct": float(
                    config.regime_v2_router_trend_down_entry_bar_range_min_pct
                ),
                "regime_v2_router_low_confidence_mr_rv_max": float(
                    config.regime_v2_router_low_confidence_mr_rv_max
                ),
                "regime_v2_router_low_confidence_mr_entry_bar_range_max_pct": float(
                    config.regime_v2_router_low_confidence_mr_entry_bar_range_max_pct
                ),
                "regime_v2_router_low_confidence_skip_rv_min": float(
                    config.regime_v2_router_low_confidence_skip_rv_min
                ),
                "regime_v2_router_low_confidence_skip_entry_bar_range_min_pct": float(
                    config.regime_v2_router_low_confidence_skip_entry_bar_range_min_pct
                ),
                "regime_v2_router_trend_up_overlay_compression_max_range_pct": float(
                    config.regime_v2_router_trend_up_overlay_compression_max_range_pct
                ),
                "regime_v2_router_trend_up_overlay_option_max_entry_bar_range_pct": float(
                    config.regime_v2_router_trend_up_overlay_option_max_entry_bar_range_pct
                ),
                "regime_v2_router_event_gap_tight_entry_bar_range_max_pct": float(
                    config.regime_v2_router_event_gap_tight_entry_bar_range_max_pct
                ),
                "regime_v2_router_event_gap_mid_rv_min": float(config.regime_v2_router_event_gap_mid_rv_min),
                "regime_v2_router_event_gap_mid_rv_max": float(config.regime_v2_router_event_gap_mid_rv_max),
                "regime_v2_router_event_gap_mid_entry_bar_range_max_pct": float(
                    config.regime_v2_router_event_gap_mid_entry_bar_range_max_pct
                ),
                "regime_v2_router_event_gap_overlay_compression_max_range_pct": float(
                    config.regime_v2_router_event_gap_overlay_compression_max_range_pct
                ),
                "regime_v2_router_event_gap_overlay_option_max_entry_bar_range_pct": float(
                    config.regime_v2_router_event_gap_overlay_option_max_entry_bar_range_pct
                ),
                "regime_v2_router_range_low_vol_tight_rv_max": float(
                    config.regime_v2_router_range_low_vol_tight_rv_max
                ),
                "regime_v2_router_range_low_vol_tight_entry_bar_range_max_pct": float(
                    config.regime_v2_router_range_low_vol_tight_entry_bar_range_max_pct
                ),
                "regime_v2_router_transition_high_rv_min": float(config.regime_v2_router_transition_high_rv_min),
                "regime_v2_router_transition_wide_entry_bar_range_min_pct": float(
                    config.regime_v2_router_transition_wide_entry_bar_range_min_pct
                ),
                "regime_v2_decision_time_et": regime_v2_decision_time.strftime("%H:%M"),
                "regime_v2_intraday_er_trend_min": float(config.regime_v2_intraday_er_trend_min),
                "regime_v2_intraday_er_sideways_max": float(config.regime_v2_intraday_er_sideways_max),
                "regime_v2_intraday_direction_abs_return_min": float(config.regime_v2_intraday_direction_abs_return_min),
                "regime_v2_range_low_vol_max_pct": float(config.regime_v2_range_low_vol_max_pct),
                "regime_v2_range_high_vol_min_pct": float(config.regime_v2_range_high_vol_min_pct),
                "regime_v2_event_gap_abs_return_min": float(config.regime_v2_event_gap_abs_return_min),
                "regime_v2_event_gap_min_range_pct": float(config.regime_v2_event_gap_min_range_pct),
                "regime_v2_state_counts": dict(regime_v2_state_counts),
                "regime_v2_route_counts": dict(regime_v2_route_counts),
                "regime_v2_selected_variant_counts": dict(regime_v2_selected_variant_counts),
                "regime_v2_skip_reason_counts": dict(regime_v2_skip_reason_counts),
                "regime_v2_router_audit_rows": list(router_audit_rows),
                "days_filtered_by_regime_v2_router": int(days_filtered_by_regime_v2_router),
                "setup_regime_label_counts": dict(setup_regime_label_counts),
                "trade_regime_label_counts": dict(trade_regime_label_counts),
                "require_or_width_filter": config.require_or_width_filter,
                "opening_range_min_width_pct": config.opening_range_min_width_pct,
                "opening_range_max_width_pct": config.opening_range_max_width_pct,
                "require_macro_release_filter": config.require_macro_release_filter,
                "macro_release_times_et": config.macro_release_times_et,
                "macro_post_release_block_minutes": config.macro_post_release_block_minutes,
                "require_prior_day_inside_bar": config.require_prior_day_inside_bar,
                "require_prior_day_range_filter": config.require_prior_day_range_filter,
                "prior_day_range_max_pct": config.prior_day_range_max_pct,
                "max_positions": config.max_positions,
                "stop_loss_risk_size": config.stop_loss_risk_size,
                "require_relative_volume": config.require_relative_volume,
                "relative_volume_min": config.relative_volume_min,
                "relative_volume_max": config.relative_volume_max,
                "require_premarket_context": config.require_premarket_context,
                "premarket_bars_min": config.premarket_bars_min,
                "premarket_volume_pct_adv_min": config.premarket_volume_pct_adv_min,
                "premarket_gap_abs_return_min": config.premarket_gap_abs_return_min,
                "premarket_range_min_pct": config.premarket_range_min_pct,
                "premarket_range_max_pct": config.premarket_range_max_pct,
                "recent_daily_volume_ratio_min": config.recent_daily_volume_ratio_min,
                "require_atr_filter": config.require_atr_filter,
                "atr_min": config.atr_min,
                "momentum_adx_period": config.momentum_adx_period,
                "momentum_adx_min": config.momentum_adx_min,
                "total_days": total_days,
                "days_filtered_by_allowed_weekdays": days_filtered_by_allowed_weekdays,
                "days_filtered_by_allowed_trade_dates": days_filtered_by_allowed_trade_dates,
                "days_with_session_data": days_with_session_data,
                "days_filtered_by_vol_regime": days_filtered_by_vol_regime,
                "days_filtered_by_or_width": days_filtered_by_or_width,
                "days_filtered_by_prior_day_inside_bar": days_filtered_by_prior_day_inside_bar,
                "days_filtered_by_prior_day_range": days_filtered_by_prior_day_range,
                "days_with_setup": setup_days,
                "days_without_setup": no_setup_days,
                "session_days": session_days,
                "setup_days": setup_days_list,
                "setup_audit_days": int(setup_audit_days),
                "setup_opportunities_before_filters_total": int(setup_opportunities_before_filters_total),
                "setup_opportunities_after_filters_total": int(setup_opportunities_after_filters_total),
                "setup_rejection_counts_total": dict(setup_rejection_counts_total),
                "historical_option_fills": historical_fills,
                "proxy_fills": proxy_fills,
                "skipped_no_option_data": skipped_no_option_data,
                "option_trade_attempts": int(option_trade_attempts),
                "option_trade_executed": int(option_trade_executed),
                "option_trade_fill_rate": (
                    float(option_trade_executed) / float(option_trade_attempts)
                    if option_trade_attempts > 0
                    else 0.0
                ),
                "setup_to_executed_trade_rate": (
                    float(option_trade_executed) / float(setup_days)
                    if setup_days > 0
                    else 0.0
                ),
                "option_funnel_counts": dict(self._option_funnel_counts),
                "option_rejection_counts": dict(self._option_rejection_counts),
                "contract_lookup_cache_stats": self._contract_lookup_cache_stats_snapshot(),
                "option_market_data_io": self._option_market_data_io_stats_snapshot(),
                "market_data_cache": self._market_data_cache_stats(),
                "underlying_shadow_enabled": bool(config.enable_underlying_shadow_mode),
                "underlying_shadow_summary": underlying_shadow_summary,
                "underlying_shadow_trade_count": int(underlying_shadow_summary.get("trades") or 0),
                "underlying_shadow_days_with_trade": len(
                    {
                        trade.entry_ts.date()
                        for trade in underlying_shadow_trades
                        if isinstance(trade.entry_ts, datetime)
                    }
                ),
                "generated_at": utcnow().isoformat(),
            }
        )
        if config.return_trade_log:
            summary["trade_log"] = [_serialize_backtest_trade(trade) for trade in trades]
            summary["option_attempt_log"] = list(self._option_attempt_log)
        return summary

    def _run_daily_forecast(self, config: IntradayOptionsBacktestConfig) -> Dict[str, Any]:
        equity = float(config.initial_equity)
        trades: List[BacktestTrade] = []
        returns: List[float] = []
        ticker = str(config.ticker or "").strip().upper()
        history_buffer = max(
            int(config.lookback_slow) * 3,
            int(config.lookback_breakout) * 3,
            int(config.lookback_relative) * 3,
            int(config.vol_percentile_lookback),
            252,
        )
        all_daily_rows = self._load_daily_bars_range(
            ticker=ticker,
            start_day=config.start.date() - timedelta(days=history_buffer),
            end_day=config.end.date(),
        )
        ordered_daily_rows = daily_row_lookup(all_daily_rows)
        if not ordered_daily_rows:
            summary = _summarize_trades(
                trades=[],
                returns=[],
                initial_equity=config.initial_equity,
                final_equity=equity,
                start=config.start,
                end=config.end,
            )
            summary.update(
                {
                    "strategy": "carver_daily_options",
                    "ticker": ticker,
                    "instrument_mode": config.instrument_mode,
                    "option_mode": config.option_mode,
                    "signal_cadence": str(config.signal_cadence or "daily_eod"),
                    "strategy_sleeve": str(config.strategy_sleeve or "core_daily"),
                    "asset_bucket": str(config.asset_bucket or infer_asset_bucket(ticker)),
                    "forecast_group": str(config.forecast_group or ""),
                    "forecast_family": str(config.forecast_family or ""),
                    "audit_disable_daily_tradability_gate": bool(config.audit_disable_daily_tradability_gate),
                    "audit_relax_daily_contract_selection": bool(config.audit_relax_daily_contract_selection),
                    "option_funnel_counts": dict(self._option_funnel_counts),
                    "daily_funnel_counts": dict(self._daily_funnel_counts),
                    "option_rejection_counts": dict(self._option_rejection_counts),
                    "generated_at": utcnow().isoformat(),
                }
            )
            return summary

        peer_daily_rows = self._load_peer_daily_histories(
            ticker=ticker,
            start_day=config.start.date() - timedelta(days=history_buffer),
            end_day=config.end.date(),
            asset_bucket=str(config.asset_bucket or infer_asset_bucket(ticker)),
        )
        tradability_sample: Optional[OptionTradabilitySample] = None
        tradability_allowed = True
        if (
            config.instrument_mode == "options"
            and str(config.option_microstructure_gate_mode or "absolute").strip().lower() == "coverage_speed_limit"
        ):
            tradability_sample = sample_option_tradability(
                ticker=ticker,
                store=self.store,
                cutemarkets_provider=self.cutemarkets_provider,
                end_day=config.end.date(),
                lookback_days=max(int(config.option_liquidity_sampling_days), 1),
                dte_min=max(int(config.option_min_dte), 0),
                dte_max=max(int(config.option_max_dte), max(int(config.option_min_dte), 0)),
                delta_min=max(float(config.option_selection_min_abs_delta), 0.0),
                delta_max=min(max(float(config.option_selection_max_abs_delta), 0.0), 1.0),
                target_dte=max(int(config.option_target_dte), max(int(config.option_min_dte), 0)),
                target_abs_delta=max(float(config.option_selection_target_abs_delta), 0.0),
                max_target_contracts_per_day=5,
            )
            tradability_allowed = tradability_passes_thresholds(
                sample=tradability_sample,
                min_quote_coverage_pct=max(float(config.option_min_quote_coverage_pct), 0.0),
                min_chain_coverage_pct=max(float(config.option_min_chain_coverage_pct), 0.0),
                min_open_interest=max(int(config.option_min_open_interest), 0),
                max_spread_to_ask=max(float(config.option_selection_max_spread_to_ask_ratio), 0.0),
                max_cost_to_expected_edge_ratio=max(float(config.option_cost_speed_limit_ratio), 0.0),
                availability_mode=str(config.option_tradability_availability_mode or "strict_historical"),
            )
            if tradability_allowed:
                self._bump_option_funnel("move_cost_filters_passed")
            else:
                if tradability_sample is not None and float(tradability_sample.quote_coverage_pct) < max(
                    float(config.option_min_quote_coverage_pct),
                    0.0,
                ):
                    self._bump_option_rejection("quote_coverage_below_min")
                self._bump_option_rejection("daily_tradability_gate")

        total_days = 0
        setup_days = 0
        no_setup_days = 0
        option_trade_attempts = 0
        option_trade_executed = 0
        overlay_veto_count = 0
        overlay_scale_up_count = 0
        overlay_scale_down_count = 0
        combined_forecasts: List[float] = []
        forecast_turnovers: List[float] = []
        premium_at_risk_values: List[float] = []
        allowed_weekdays = _parse_allowed_weekdays_et(config.allowed_weekdays_et)
        allowed_trade_dates = _parse_allowed_trade_dates(config.allowed_trade_dates_csv)
        days_filtered_by_allowed_weekdays = 0
        days_filtered_by_allowed_trade_dates = 0
        daily_rows_in_window = [row for row in ordered_daily_rows if config.start.date() <= row["day"] <= config.end.date()]
        position: Optional[_DailyOptionPosition] = None
        previous_snapshot: Optional[DailyForecastSnapshot] = None
        previous_combined_forecast: Optional[float] = None

        for row_index, row in enumerate(daily_rows_in_window):
            total_days += 1
            trade_day = row["day"]
            if allowed_trade_dates is not None and trade_day not in allowed_trade_dates:
                days_filtered_by_allowed_trade_dates += 1
                continue
            if allowed_weekdays is not None and trade_day.weekday() not in allowed_weekdays:
                days_filtered_by_allowed_weekdays += 1
                continue
            full_index = next((idx for idx, candidate in enumerate(ordered_daily_rows) if candidate["day"] == trade_day), None)
            if full_index is None or full_index < 1:
                continue
            signal_row = ordered_daily_rows[full_index - 1]
            signal_day = signal_row["day"]
            snapshot = self._build_daily_signal_snapshot(
                ticker=ticker,
                signal_day=signal_day,
                ordered_daily_rows=ordered_daily_rows,
                config=config,
                peer_daily_rows=peer_daily_rows,
                previous_snapshot=previous_snapshot,
                previous_combined_forecast=previous_combined_forecast,
            )
            if snapshot is None:
                self._bump_daily_funnel("daily_snapshot_missing")
                no_setup_days += 1
                continue
            self._bump_daily_funnel("daily_signal_days")
            previous_snapshot = snapshot
            previous_combined_forecast = snapshot.combined_forecast
            overlay_decision = SurfaceOverlayDecision()
            combined_forecast = float(snapshot.combined_forecast)
            if bool(config.overlay_enabled) and config.instrument_mode == "options":
                option_type = "call" if combined_forecast >= 0.0 else "put"
                overlay_decision = apply_surface_overlay_to_forecast(
                    base_forecast=combined_forecast,
                    chain_snapshot=self._load_option_chain_snapshot(ticker=ticker, day=trade_day),
                    realized_vol_annualized=snapshot.realized_vol_annualized,
                    option_type=option_type,
                    forecast_cap=float(config.forecast_cap),
                    ivrv_scale_down_zscore=float(config.overlay_ivrv_scale_down_zscore),
                    ivrv_scale_up_zscore=float(config.overlay_ivrv_scale_up_zscore),
                    ivrv_scale_down_multiplier=float(config.overlay_ivrv_scale_down_multiplier),
                    ivrv_scale_up_multiplier=float(config.overlay_ivrv_scale_up_multiplier),
                    term_structure_veto_threshold=float(config.overlay_term_structure_veto_threshold),
                    skew_veto_threshold=float(config.overlay_skew_veto_threshold),
                )
                combined_forecast = _cap_value(
                    combined_forecast * float(overlay_decision.forecast_scale_multiplier),
                    float(config.forecast_cap),
                )
                if overlay_decision.veto_new_trade:
                    overlay_veto_count += 1
                if overlay_decision.scale_up:
                    overlay_scale_up_count += 1
                if overlay_decision.scale_down:
                    overlay_scale_down_count += 1
            combined_forecasts.append(float(combined_forecast))
            forecast_turnovers.append(float(snapshot.forecast_turnover))
            direction = 1 if combined_forecast > 0.0 else (-1 if combined_forecast < 0.0 else 0)
            if direction > 0 and not bool(config.allow_long):
                direction = 0
            if direction < 0 and not bool(config.allow_short):
                direction = 0
            if str(config.forecast_family or "") in OVERLAY_FAMILIES:
                direction = 0
            if direction != 0:
                self._bump_option_funnel("setups_found")
                self._bump_option_funnel("setups_passed_signal_filters")
                self._bump_daily_funnel("daily_nonzero_forecast_days")
                setup_days += 1
            else:
                self._bump_daily_funnel("daily_zero_direction_days")
                no_setup_days += 1

            trade_ts = self._trade_ts_for_day(trade_day, "09:35")
            trade_underlying = max(float(row.get("open") or 0.0), float(row.get("close") or 0.0))
            if trade_underlying <= 0.0:
                self._bump_daily_funnel("daily_underlying_price_missing")
                continue

            if position is not None:
                should_exit = False
                exit_reason = ""
                held_days = max((trade_day - position.entry_day).days, 0)
                current_dte = (position.expiration_day - trade_day).days if position.option_type != "stock" else 999
                if direction == 0:
                    should_exit = True
                    exit_reason = "forecast_zero_cross"
                elif direction != position.direction:
                    should_exit = True
                    exit_reason = "forecast_sign_flip"
                elif current_dte < max(int(config.option_min_dte), 0):
                    should_exit = True
                    exit_reason = "dte_roll"
                elif held_days >= max(int(config.max_calendar_hold_days), 1):
                    should_exit = True
                    exit_reason = "max_calendar_hold"
                if should_exit:
                    trade = self._close_daily_position(
                        position=position,
                        trade_day=trade_day,
                        trade_ts=trade_ts,
                        underlying_price=trade_underlying,
                        current_equity=equity,
                        config=config,
                        exit_reason=exit_reason,
                    )
                    if trade is not None:
                        self._bump_daily_funnel("daily_trades_closed")
                        trades.append(trade)
                        equity += float(trade.pnl)
                        returns.append(float(trade.return_pct))
                        option_trade_executed += 1 if config.instrument_mode == "options" else 0
                    position = None

            if direction == 0 or position is not None:
                continue
            if bool(config.overlay_enabled) and overlay_decision.veto_new_trade:
                self._bump_daily_funnel("daily_overlay_vetoes")
                continue
            bypass_daily_tradability_gate = bool(
                config.instrument_mode == "options"
                and str(config.signal_cadence or "intraday").strip().lower() == "daily_eod"
                and bool(config.audit_disable_daily_tradability_gate)
            )
            if config.instrument_mode == "options" and not tradability_allowed:
                self._bump_daily_funnel("daily_tradability_gate_failed")
                if bypass_daily_tradability_gate:
                    self._bump_daily_funnel("daily_tradability_gate_bypassed")
                else:
                    continue
            self._bump_daily_funnel("daily_entry_attempts")
            if config.instrument_mode == "options":
                if tradability_allowed:
                    self._bump_daily_funnel("daily_tradability_gate_passed")

            self._bump_option_funnel("setups_with_exit_plan")
            self._bump_option_funnel("setups_after_trade_limits")
            if config.instrument_mode == "stocks":
                stock_position = self._open_daily_stock_position(
                    ticker=ticker,
                    trade_day=trade_day,
                    trade_ts=trade_ts,
                    underlying_price=trade_underlying,
                    direction=direction,
                    combined_forecast=combined_forecast,
                    snapshot=snapshot,
                    current_equity=equity,
                    config=config,
                    overlay_decision=overlay_decision,
                )
                if stock_position is not None:
                    position = stock_position
                continue

            option_trade_attempts += 1
            self._bump_option_funnel("historical_option_attempts")
            selected_contract = self._select_contract(
                ticker=ticker,
                day=trade_day,
                direction=direction,
                entry_underlying=trade_underlying,
                config=config,
                selection_ts=trade_ts,
            )
            selection_meta = dict(self._last_contract_selection_meta or {})
            if int(selection_meta.get("pool_contract_count") or 0) > 0 or selected_contract is not None:
                self._bump_option_funnel("option_chain_available")
                self._bump_daily_funnel("daily_contract_pool_available")
            if selected_contract is None:
                self._bump_daily_funnel("daily_contract_selection_failed")
                self._record_last_contract_selection_rejections()
                continue
            self._bump_option_funnel("contract_selected")
            self._bump_daily_funnel("daily_contract_selected")
            position = self._open_daily_option_position(
                ticker=ticker,
                trade_day=trade_day,
                trade_ts=trade_ts,
                underlying_price=trade_underlying,
                direction=direction,
                combined_forecast=combined_forecast,
                snapshot=snapshot,
                selected_contract=selected_contract,
                current_equity=equity,
                config=config,
                overlay_decision=overlay_decision,
                tradability_sample=tradability_sample,
            )
            if position is not None:
                self._bump_daily_funnel("daily_position_opened")
                premium_at_risk_values.append(float(position.premium_at_risk_pct_nav))

        if position is not None:
            final_row = daily_rows_in_window[-1]
            trade_day = final_row["day"]
            trade_ts = self._trade_ts_for_day(trade_day, "15:30")
            underlying_price = max(float(final_row.get("close") or 0.0), float(final_row.get("open") or 0.0))
            trade = self._close_daily_position(
                position=position,
                trade_day=trade_day,
                trade_ts=trade_ts,
                underlying_price=underlying_price,
                current_equity=equity,
                config=config,
                exit_reason="window_end",
            )
            if trade is not None:
                self._bump_daily_funnel("daily_trades_closed")
                trades.append(trade)
                equity += float(trade.pnl)
                returns.append(float(trade.return_pct))
                option_trade_executed += 1 if config.instrument_mode == "options" else 0

        if config.persist_trades and trades:
            self.store.insert_backtest_trades(trades)

        summary = _summarize_trades(
            trades=trades,
            returns=returns,
            initial_equity=config.initial_equity,
            final_equity=equity,
            start=config.start,
            end=config.end,
        )
        summary.update(
            {
                "strategy": "carver_daily_options",
                "ticker": ticker,
                "instrument_mode": config.instrument_mode,
                "option_mode": config.option_mode,
                "signal_cadence": str(config.signal_cadence or "daily_eod"),
                "strategy_sleeve": str(config.strategy_sleeve or "core_daily"),
                "sleeve": str(config.strategy_sleeve or "core_daily"),
                "asset_bucket": str(config.asset_bucket or infer_asset_bucket(ticker)),
                "forecast_group": str(config.forecast_group or ""),
                "forecast_family": str(config.forecast_family or ""),
                "forecast_weight": float(config.forecast_weight),
                "allowed_weekdays_et": str(config.allowed_weekdays_et or ""),
                "allowed_trade_dates_csv": str(config.allowed_trade_dates_csv or ""),
                "combined_forecast": _mean_fast(combined_forecasts) if combined_forecasts else 0.0,
                "forecast_turnover": _mean_fast(forecast_turnovers) if forecast_turnovers else 0.0,
                "portfolio_target_vol_annualized": float(config.portfolio_target_vol_annualized),
                "premium_at_risk_pct_nav": _mean_fast(premium_at_risk_values) if premium_at_risk_values else 0.0,
                "risk_budget_share": float(config.risk_budget_share),
                "audit_disable_daily_tradability_gate": bool(config.audit_disable_daily_tradability_gate),
                "audit_relax_daily_contract_selection": bool(config.audit_relax_daily_contract_selection),
                "overlay_enabled": bool(config.overlay_enabled),
                "overlay_veto_count": int(overlay_veto_count),
                "overlay_scale_up_count": int(overlay_scale_up_count),
                "overlay_scale_down_count": int(overlay_scale_down_count),
                "option_microstructure_gate_mode": str(config.option_microstructure_gate_mode or "absolute"),
                "option_tradability_availability_mode": str(
                    config.option_tradability_availability_mode or "strict_historical"
                ),
                "quote_coverage_pct": float(tradability_sample.quote_coverage_pct) if tradability_sample else 0.0,
                "chain_coverage_pct": float(tradability_sample.chain_coverage_pct) if tradability_sample else 0.0,
                "cost_speed_limit_ratio": (
                    float(tradability_sample.estimated_cost_to_expected_edge_ratio)
                    if tradability_sample is not None
                    else 0.0
                ),
                "daily_tradability_sample": tradability_sample.to_dict() if tradability_sample else None,
                "total_days": int(total_days),
                "days_filtered_by_allowed_weekdays": int(days_filtered_by_allowed_weekdays),
                "days_filtered_by_allowed_trade_dates": int(days_filtered_by_allowed_trade_dates),
                "days_with_session_data": int(total_days),
                "days_with_setup": int(setup_days),
                "days_without_setup": int(no_setup_days),
                "historical_option_fills": int(option_trade_executed),
                "proxy_fills": 0,
                "skipped_no_option_data": max(int(option_trade_attempts - option_trade_executed), 0),
                "option_trade_attempts": int(option_trade_attempts),
                "option_trade_executed": int(option_trade_executed),
                "option_trade_fill_rate": (
                    float(option_trade_executed) / float(option_trade_attempts)
                    if option_trade_attempts > 0
                    else 0.0
                ),
                "setup_to_executed_trade_rate": (
                    float(option_trade_executed) / float(setup_days)
                    if setup_days > 0
                    else 0.0
                ),
                "option_funnel_counts": dict(self._option_funnel_counts),
                "daily_funnel_counts": dict(self._daily_funnel_counts),
                "option_rejection_counts": dict(self._option_rejection_counts),
                "generated_at": utcnow().isoformat(),
            }
        )
        if config.return_trade_log:
            summary["trade_log"] = [_serialize_backtest_trade(trade) for trade in trades]
            summary["option_attempt_log"] = list(self._option_attempt_log)
        return summary

    def _load_peer_daily_histories(
        self,
        *,
        ticker: str,
        start_day: date,
        end_day: date,
        asset_bucket: str,
    ) -> Dict[str, List[Dict[str, Any]]]:
        members = bucket_members_for_ticker(ticker) if not asset_bucket else bucket_members_for_ticker(ticker)
        histories: Dict[str, List[Dict[str, Any]]] = {}
        for member in members:
            histories[member] = self._load_daily_bars_range(
                ticker=member,
                start_day=start_day,
                end_day=end_day,
            )
        return histories

    def _build_daily_signal_snapshot(
        self,
        *,
        ticker: str,
        signal_day: date,
        ordered_daily_rows: Sequence[Mapping[str, Any]],
        config: IntradayOptionsBacktestConfig,
        peer_daily_rows: Mapping[str, Sequence[Mapping[str, Any]]],
        previous_snapshot: Optional[DailyForecastSnapshot],
        previous_combined_forecast: Optional[float],
    ) -> Optional[DailyForecastSnapshot]:
        forecast_cfg = DailyForecastConfig(
            signal_cadence=str(config.signal_cadence or "daily_eod"),
            forecast_family=str(config.forecast_family or ""),
            lookback_fast=int(config.lookback_fast),
            lookback_slow=int(config.lookback_slow),
            lookback_breakout=int(config.lookback_breakout),
            lookback_relative=int(config.lookback_relative),
            forecast_cap=float(config.forecast_cap),
            vol_attenuation_enabled=bool(config.vol_attenuation_enabled),
            vol_percentile_lookback=int(config.vol_percentile_lookback),
            vol_attenuation_hi_pct=float(config.vol_attenuation_hi_pct),
            vol_attenuation_extreme_pct=float(config.vol_attenuation_extreme_pct),
        )
        if str(config.forecast_family or "") in COMBO_FAMILIES:
            return build_combo_forecast_snapshot(
                ticker=ticker,
                day=signal_day,
                daily_rows=ordered_daily_rows,
                config=forecast_cfg,
                strategy_sleeve=str(config.strategy_sleeve or "core_daily"),
                peer_daily_rows=peer_daily_rows,
                previous_combined_forecast=previous_combined_forecast,
            )
        if str(config.forecast_family or "") in OVERLAY_FAMILIES:
            base_snapshot = build_combo_forecast_snapshot(
                ticker=ticker,
                day=signal_day,
                daily_rows=ordered_daily_rows,
                config=DailyForecastConfig(
                    signal_cadence=str(config.signal_cadence or "daily_eod"),
                    forecast_family="c50_carver_core_combo_v1",
                    lookback_fast=int(config.lookback_fast),
                    lookback_slow=int(config.lookback_slow),
                    lookback_breakout=int(config.lookback_breakout),
                    lookback_relative=int(config.lookback_relative),
                    forecast_cap=float(config.forecast_cap),
                    vol_attenuation_enabled=bool(config.vol_attenuation_enabled),
                    vol_percentile_lookback=int(config.vol_percentile_lookback),
                    vol_attenuation_hi_pct=float(config.vol_attenuation_hi_pct),
                    vol_attenuation_extreme_pct=float(config.vol_attenuation_extreme_pct),
                ),
                strategy_sleeve=str(config.strategy_sleeve or "surface_overlay"),
                peer_daily_rows=peer_daily_rows,
                previous_combined_forecast=previous_combined_forecast,
            )
            if base_snapshot is None:
                return None
            return DailyForecastSnapshot(
                day=signal_day,
                ticker=str(base_snapshot.ticker),
                strategy_sleeve=str(config.strategy_sleeve or "surface_overlay"),
                asset_bucket=str(base_snapshot.asset_bucket),
                forecast_group="surface_overlay",
                forecast_family=str(config.forecast_family or ""),
                forecast_raw=float(base_snapshot.forecast_raw),
                forecast_scaled=float(base_snapshot.forecast_scaled),
                forecast_capped=float(base_snapshot.forecast_capped),
                forecast_weight=1.0,
                combined_forecast=float(base_snapshot.combined_forecast),
                forecast_turnover=float(base_snapshot.forecast_turnover),
                realized_vol_annualized=base_snapshot.realized_vol_annualized,
                vol_percentile=base_snapshot.vol_percentile,
                attenuation_multiplier=float(base_snapshot.attenuation_multiplier),
                coverage_count=int(base_snapshot.coverage_count),
            )
        return build_daily_forecast_snapshot(
            ticker=ticker,
            day=signal_day,
            daily_rows=ordered_daily_rows,
            config=forecast_cfg,
            strategy_sleeve=str(config.strategy_sleeve or "core_daily"),
            peer_daily_rows=peer_daily_rows,
            previous_snapshot=previous_snapshot,
        )

    def _trade_ts_for_day(self, day: date, hhmm: str) -> datetime:
        trade_time = _parse_hhmm(hhmm, "09:35")
        return datetime.combine(day, trade_time, tzinfo=_ET_ZONE).astimezone(timezone.utc)

    def _resolve_daily_option_price(
        self,
        *,
        symbol: str,
        day: date,
        ts: datetime,
        side: str,
        config: IntradayOptionsBacktestConfig,
    ) -> Tuple[Optional[float], str, Dict[str, Any]]:
        price_source = ""
        meta: Dict[str, Any] = {}
        normalized_side = str(side or "buy").strip().lower()
        if bool(config.use_option_quotes_for_fills):
            quote = self._lookup_option_quote_on_or_after(
                symbol=symbol,
                day=day,
                ts=ts,
                fallback_last=False,
            )
            if quote is not None:
                bid = _safe_float(quote.get("bid"))
                ask = _safe_float(quote.get("ask"))
                if bid is not None and ask is not None and ask > 0.0 and ask >= bid >= 0.0:
                    self._bump_option_funnel("quote_fill_available")
                    meta.update(
                        {
                            "quote_ts": quote["ts"].isoformat() if isinstance(quote.get("ts"), datetime) else None,
                            "quote_bid": float(bid),
                            "quote_ask": float(ask),
                            "quote_mid": (float(bid) + float(ask)) / 2.0,
                            "quote_spread_abs": max(float(ask) - float(bid), 0.0),
                        }
                    )
                    if normalized_side == "buy":
                        return float(ask), "quotes", meta
                    return float(bid), "quotes", meta
        if bool(config.option_quote_fill_fallback_to_bar_close):
            bars = self._load_option_bars(symbol=symbol, day=day)
            bar = _first_bar_on_or_after(bars, ts, fallback_last=False)
            if bar is not None:
                self._bump_option_funnel("quote_fill_fallback_used")
                price_source = "bar_close"
                meta.update(
                    {
                        "bar_ts": bar["ts"].isoformat() if isinstance(bar.get("ts"), datetime) else None,
                        "bar_open": float(bar.get("open") or 0.0),
                        "bar_close": float(bar.get("close") or 0.0),
                        "bar_high": float(bar.get("high") or 0.0),
                        "bar_low": float(bar.get("low") or 0.0),
                        "bar_volume": int(bar.get("volume") or 0),
                    }
                )
                return float(bar.get("close") or 0.0), price_source, meta
        return None, price_source, meta

    def _open_daily_stock_position(
        self,
        *,
        ticker: str,
        trade_day: date,
        trade_ts: datetime,
        underlying_price: float,
        direction: int,
        combined_forecast: float,
        snapshot: DailyForecastSnapshot,
        current_equity: float,
        config: IntradayOptionsBacktestConfig,
        overlay_decision: SurfaceOverlayDecision,
    ) -> Optional[_DailyOptionPosition]:
        target_notional = current_equity * max(float(config.risk_budget_share), 0.0) * (
            abs(float(combined_forecast)) / max(float(config.forecast_cap), 1.0)
        )
        qty = int(target_notional / max(float(underlying_price), 1.0))
        if qty <= 0:
            return None
        return _DailyOptionPosition(
            option_symbol=ticker,
            side="buy",
            direction=int(direction),
            qty=int(qty),
            entry_day=trade_day,
            entry_ts=trade_ts,
            entry_price=float(underlying_price),
            entry_underlying=float(underlying_price),
            entry_forecast=float(combined_forecast),
            forecast_family=str(snapshot.forecast_family),
            option_type="stock",
            expiration_day=trade_day + timedelta(days=max(int(config.max_calendar_hold_days), 1)),
            strike=0.0,
            delta_abs=1.0,
            premium_at_risk_pct_nav=0.0,
            risk_budget_share=float(config.risk_budget_share),
            overlay=overlay_decision.to_dict(),
            metadata=snapshot.to_dict(),
        )

    def _open_daily_option_position(
        self,
        *,
        ticker: str,
        trade_day: date,
        trade_ts: datetime,
        underlying_price: float,
        direction: int,
        combined_forecast: float,
        snapshot: DailyForecastSnapshot,
        selected_contract: Dict[str, Any],
        current_equity: float,
        config: IntradayOptionsBacktestConfig,
        overlay_decision: SurfaceOverlayDecision,
        tradability_sample: Optional[OptionTradabilitySample],
    ) -> Optional[_DailyOptionPosition]:
        ranked_contract_pool = _selection_ranked_contract_pool(
            self._last_contract_selection_meta,
            selected_contract,
        )
        conversion_mode = _normalize_option_post_selection_conversion_mode(
            getattr(config, "option_post_selection_conversion_mode", "disabled")
        )
        max_alternates = max(int(getattr(config, "option_post_selection_max_alternates", 0) or 0), 0)
        max_final_rank = max(int(getattr(config, "option_post_selection_max_final_rank", 0) or 0), 0)
        raw_max_final_strike_distance_steps = getattr(
            config,
            "option_post_selection_max_final_strike_distance_steps",
            -1,
        )
        max_final_strike_distance_steps = int(
            raw_max_final_strike_distance_steps
            if raw_max_final_strike_distance_steps not in (None, "")
            else -1
        )
        contract_attempt_pool = _build_post_selection_contract_attempt_pool(
            ranked_contract_pool=ranked_contract_pool,
            selected_contract=selected_contract,
            conversion_mode=conversion_mode,
            max_alternates=max_alternates,
            max_final_rank=max_final_rank,
            max_final_strike_distance_steps=max_final_strike_distance_steps,
        )
        if not contract_attempt_pool:
            contract_attempt_pool = [dict(selected_contract)]
        initial_selected_symbol = str(selected_contract.get("symbol") or "").strip() or None
        initial_selected_expiration_date = _selection_contract_expiration_date_text(selected_contract) or None
        initial_contract_rank = _selection_contract_rank(selected_contract, default_rank=1)
        initial_selected_strike_distance_steps = _selection_contract_strike_distance_steps(selected_contract)
        initial_selected_entry_bar_volume = _selection_contract_entry_bar_volume(selected_contract)
        initial_selected_quote_spread_pct = _selection_contract_quote_spread_pct(selected_contract)
        chosen_contract: Optional[Dict[str, Any]] = None
        chosen_symbol = ""
        chosen_expiration: Optional[datetime] = None
        chosen_strike: Optional[float] = None
        chosen_entry_price: Optional[float] = None
        chosen_price_source = ""
        chosen_price_meta: Mapping[str, Any] = {}
        chosen_attempt_idx = 0
        for idx, candidate_contract in enumerate(contract_attempt_pool):
            candidate_contract = dict(candidate_contract)
            symbol = str(candidate_contract.get("symbol") or "").strip()
            expiration = parse_datetime(candidate_contract.get("expiration_date"))
            strike = _safe_float(candidate_contract.get("strike_price"))
            if not symbol or expiration is None or strike is None or strike <= 0.0:
                self._bump_option_rejection("daily_contract_invalid")
                self._bump_daily_funnel("daily_contract_selection_failed")
                return None
            self._bump_option_funnel("entry_exit_bars_available")
            entry_price, price_source, price_meta = self._resolve_daily_option_price(
                symbol=symbol,
                day=trade_day,
                ts=trade_ts,
                side="buy",
                config=config,
            )
            if entry_price is None or entry_price <= 0.0:
                self._bump_option_rejection("daily_entry_pricing_unavailable")
                self._bump_daily_funnel("daily_entry_pricing_failed")
                return None
            self._bump_option_funnel("pricing_resolved")
            self._bump_daily_funnel("daily_quote_gate_passed")
            rejection_reason = self._daily_option_structure_and_microstructure_rejection_reason(
                symbol=symbol,
                day=trade_day,
                ts=trade_ts,
                entry_price=float(entry_price),
                selected_contract=candidate_contract,
                underlying_price=underlying_price,
                current_equity=current_equity,
                combined_forecast=combined_forecast,
                config=config,
                tradability_sample=tradability_sample,
            )
            if rejection_reason:
                if (
                    conversion_mode != "disabled"
                    and idx < len(contract_attempt_pool) - 1
                    and rejection_reason in _POST_SELECTION_RETRYABLE_MICRO_REJECTIONS
                ):
                    continue
                self._bump_option_rejection(rejection_reason)
                self._bump_daily_funnel("daily_structure_gate_failed")
                return None
            self._bump_option_funnel("microstructure_filters_passed")
            chosen_contract = candidate_contract
            chosen_symbol = symbol
            chosen_expiration = expiration
            chosen_strike = strike
            chosen_entry_price = float(entry_price)
            chosen_price_source = str(price_source or "")
            chosen_price_meta = dict(price_meta or {})
            chosen_attempt_idx = int(idx)
            break
        if chosen_contract is None or chosen_entry_price is None or chosen_expiration is None or chosen_strike is None:
            self._bump_daily_funnel("daily_structure_gate_failed")
            return None
        expected_move = self._daily_expected_move(
            underlying_price=underlying_price,
            snapshot=snapshot,
            hold_days=max(int(config.max_calendar_hold_days), 1),
        )
        if not self._daily_move_cost_filters_pass(
            expected_move=expected_move,
            entry_price=float(chosen_entry_price),
            selected_contract=chosen_contract,
            config=config,
            price_meta=chosen_price_meta,
            underlying_price=underlying_price,
            direction=direction,
        ):
            self._bump_daily_funnel("daily_move_cost_gate_failed")
            return None
        qty, premium_at_risk_pct_nav = self._size_daily_option_position(
            current_equity=current_equity,
            combined_forecast=combined_forecast,
            underlying_price=underlying_price,
            entry_price=float(chosen_entry_price),
            selected_contract=chosen_contract,
            config=config,
        )
        if qty <= 0:
            self._bump_option_rejection("daily_sizing_failed")
            self._bump_daily_funnel("daily_sizing_failed")
            return None
        self._bump_option_funnel("sizing_passed")
        self._bump_option_funnel("entry_constructed")
        self._bump_daily_funnel("daily_sizing_passed")
        self._bump_daily_funnel("daily_entry_created")
        option_type = "call" if direction > 0 else "put"
        abs_delta = abs(float(chosen_contract.get("_selection_abs_delta") or 0.0))
        return _DailyOptionPosition(
            option_symbol=chosen_symbol,
            side="buy",
            direction=int(direction),
            qty=int(qty),
            entry_day=trade_day,
            entry_ts=trade_ts,
            entry_price=float(chosen_entry_price),
            entry_underlying=float(underlying_price),
            entry_forecast=float(combined_forecast),
            forecast_family=str(snapshot.forecast_family),
            option_type=option_type,
            expiration_day=chosen_expiration.date(),
            strike=float(chosen_strike),
            delta_abs=abs_delta if abs_delta > 0.0 else max(float(config.option_selection_target_abs_delta), 0.5),
            premium_at_risk_pct_nav=float(premium_at_risk_pct_nav),
            risk_budget_share=float(config.risk_budget_share),
            overlay=overlay_decision.to_dict(),
            metadata={
                **snapshot.to_dict(),
                **chosen_price_meta,
                "fill_pricing_source": chosen_price_source,
                "contract_open_interest": int(chosen_contract.get("open_interest") or 0),
                "initial_selected_option_symbol": initial_selected_symbol,
                "final_selected_option_symbol": chosen_symbol,
                "initial_selected_expiration_date": initial_selected_expiration_date,
                "final_selected_expiration_date": chosen_expiration.date().isoformat(),
                "conversion_changed_expiry": bool(
                    initial_selected_expiration_date
                    and initial_selected_expiration_date != chosen_expiration.date().isoformat()
                ),
                "initial_contract_rank": int(initial_contract_rank),
                "final_contract_rank": int(
                    _selection_contract_rank(chosen_contract, default_rank=chosen_attempt_idx + 1)
                ),
                "initial_selected_strike_distance_steps": initial_selected_strike_distance_steps,
                "final_selected_strike_distance_steps": _selection_contract_strike_distance_steps(chosen_contract),
                "initial_selected_entry_bar_volume": initial_selected_entry_bar_volume,
                "final_selected_entry_bar_volume": _selection_contract_entry_bar_volume(chosen_contract),
                "initial_selected_quote_spread_pct": initial_selected_quote_spread_pct,
                "final_selected_quote_spread_pct": _selection_contract_quote_spread_pct(chosen_contract),
                "conversion_applied": bool(initial_selected_symbol and initial_selected_symbol != chosen_symbol),
                "conversion_attempt_count": int(chosen_attempt_idx),
                "conversion_terminal_rejection_reason": "",
            },
        )

    def _daily_option_structure_and_microstructure_rejection_reason(
        self,
        *,
        symbol: str,
        day: date,
        ts: datetime,
        entry_price: float,
        selected_contract: Dict[str, Any],
        underlying_price: float,
        current_equity: Optional[float] = None,
        combined_forecast: Optional[float] = None,
        config: IntradayOptionsBacktestConfig,
        tradability_sample: Optional[OptionTradabilitySample],
        setup: Optional[Mapping[str, Any]] = None,
    ) -> str:
        gate_mode = str(config.option_microstructure_gate_mode or "absolute").strip().lower()
        if gate_mode == "coverage_speed_limit":
            if tradability_sample is None:
                return "daily_tradability_sample_missing"
            return ""
        if entry_price < max(float(config.option_min_entry_price), 0.0):
            return "micro_entry_price"
        bars = self._load_option_bars(symbol=symbol, day=day)
        bar = _first_bar_on_or_after(bars, ts, fallback_last=False)
        if bar is None:
            return "micro_entry_bar_missing"
        entry_volume = int(bar.get("volume") or 0)
        bar_high = float(bar.get("high") or 0.0)
        bar_low = float(bar.get("low") or 0.0)
        min_entry_volume = max(int(config.option_min_entry_volume), 0)
        if gate_mode == "size_aware_absolute" and current_equity is not None and combined_forecast is not None:
            provisional_qty, _ = self._size_daily_option_position(
                current_equity=float(current_equity),
                combined_forecast=float(combined_forecast),
                underlying_price=float(underlying_price),
                entry_price=float(entry_price),
                selected_contract=selected_contract,
                config=config,
            )
            min_entry_volume = _required_option_entry_volume(
                gate_mode=gate_mode,
                base_min_entry_volume=min_entry_volume,
                provisional_qty=int(provisional_qty),
                max_entry_volume_participation=float(config.option_max_entry_volume_participation),
            )
        if entry_volume < min_entry_volume:
            return "micro_entry_volume"
        if entry_price > 0.0 and bar_high > 0.0 and bar_low > 0.0 and bar_high >= bar_low:
            bar_range_pct = (bar_high - bar_low) / max(entry_price, 1e-6)
            max_entry_bar_range_pct = max(
                _setup_override_float(setup, "option_max_entry_bar_range_pct", config.option_max_entry_bar_range_pct),
                0.0,
            )
            if bar_range_pct > max_entry_bar_range_pct:
                return "micro_entry_bar_range"
        return ""

    def _daily_option_structure_and_microstructure_pass(
        self,
        *,
        symbol: str,
        day: date,
        ts: datetime,
        entry_price: float,
        selected_contract: Dict[str, Any],
        underlying_price: float,
        current_equity: Optional[float] = None,
        combined_forecast: Optional[float] = None,
        config: IntradayOptionsBacktestConfig,
        tradability_sample: Optional[OptionTradabilitySample],
        setup: Optional[Mapping[str, Any]] = None,
    ) -> bool:
        self._bump_option_funnel("structure_filters_passed")
        rejection_reason = self._daily_option_structure_and_microstructure_rejection_reason(
            symbol=symbol,
            day=day,
            ts=ts,
            entry_price=entry_price,
            selected_contract=selected_contract,
            underlying_price=underlying_price,
            current_equity=current_equity,
            combined_forecast=combined_forecast,
            config=config,
            tradability_sample=tradability_sample,
            setup=setup,
        )
        if rejection_reason:
            self._bump_option_rejection(rejection_reason)
            return False
        self._bump_option_funnel("microstructure_filters_passed")
        return True

    def _daily_move_cost_filters_pass(
        self,
        *,
        expected_move: Optional[float],
        entry_price: float,
        selected_contract: Dict[str, Any],
        config: IntradayOptionsBacktestConfig,
        price_meta: Mapping[str, Any],
        underlying_price: float,
        direction: int,
    ) -> bool:
        if expected_move is None or expected_move <= 0.0:
            self._bump_option_funnel("move_cost_filters_passed")
            return True
        intrinsic_value = _option_intrinsic_value(
            option_type="call" if int(direction) > 0 else "put",
            underlying_price=underlying_price,
            strike=float(selected_contract.get("strike_price") or 0.0),
        )
        extrinsic_value = max(float(entry_price) - float(intrinsic_value), 0.0)
        spread_abs = _safe_float(price_meta.get("quote_spread_abs"))
        min_move_to_extrinsic = max(float(config.option_min_expected_move_to_extrinsic_ratio), 0.0)
        min_move_to_spread = max(float(config.option_min_expected_move_to_spread_ratio), 0.0)
        min_move_to_debit = max(float(config.option_min_expected_move_to_debit_ratio), 0.0)
        if min_move_to_extrinsic > 0.0 and extrinsic_value > 0.0:
            if (float(expected_move) / float(extrinsic_value)) < min_move_to_extrinsic:
                self._bump_option_rejection("move_to_cost_extrinsic_ratio")
                return False
        if min_move_to_spread > 0.0 and spread_abs is not None and spread_abs > 0.0:
            if (float(expected_move) / float(spread_abs)) < min_move_to_spread:
                self._bump_option_rejection("move_to_cost_spread_ratio")
                return False
        if min_move_to_debit > 0.0 and entry_price > 0.0:
            if (float(expected_move) / float(entry_price)) < min_move_to_debit:
                self._bump_option_rejection("move_to_cost_debit_ratio")
                return False
        self._bump_option_funnel("move_cost_filters_passed")
        return True

    def _daily_expected_move(
        self,
        *,
        underlying_price: float,
        snapshot: DailyForecastSnapshot,
        hold_days: int,
    ) -> Optional[float]:
        realized_vol = snapshot.realized_vol_annualized
        if realized_vol is None or realized_vol <= 0.0 or underlying_price <= 0.0:
            return None
        horizon = max(min(int(hold_days), 30), 1)
        return float(underlying_price) * float(realized_vol) * sqrt(float(horizon) / 252.0)

    def _size_daily_option_position(
        self,
        *,
        current_equity: float,
        combined_forecast: float,
        underlying_price: float,
        entry_price: float,
        selected_contract: Dict[str, Any],
        config: IntradayOptionsBacktestConfig,
    ) -> Tuple[int, float]:
        abs_delta = abs(float(selected_contract.get("_selection_abs_delta") or 0.0))
        if abs_delta <= 0.0:
            abs_delta = max(float(config.option_selection_target_abs_delta), 0.5)
        target_notional = (
            current_equity
            * max(float(config.risk_budget_share), 0.0)
            * max(float(config.portfolio_target_vol_annualized), 0.0)
            * (abs(float(combined_forecast)) / max(float(config.forecast_cap), 1.0))
        )
        contract_risk_notional = max(float(underlying_price) * abs_delta * 100.0, 1.0)
        qty_by_delta = int(target_notional / contract_risk_notional)
        qty_by_premium = int(
            (current_equity * max(float(config.premium_at_risk_pct_nav_cap), 0.0))
            / max(float(entry_price) * 100.0, 1.0)
        )
        qty_by_total_premium = int(
            (current_equity * max(float(config.total_premium_at_risk_pct_nav_cap), 0.0))
            / max(float(entry_price) * 100.0, 1.0)
        )
        candidates = [qty for qty in (qty_by_delta, qty_by_premium, qty_by_total_premium) if qty > 0]
        if not candidates:
            return 0, 0.0
        qty = min(candidates)
        premium_at_risk_pct_nav = (float(entry_price) * float(qty) * 100.0) / max(float(current_equity), 1.0)
        return int(qty), float(premium_at_risk_pct_nav)

    def _close_daily_position(
        self,
        *,
        position: _DailyOptionPosition,
        trade_day: date,
        trade_ts: datetime,
        underlying_price: float,
        current_equity: float,
        config: IntradayOptionsBacktestConfig,
        exit_reason: str,
    ) -> Optional[BacktestTrade]:
        if position.option_type == "stock":
            exit_price = float(underlying_price)
            side_multiplier = 1.0 if int(position.direction) > 0 else -1.0
            pnl = (float(exit_price) - float(position.entry_price)) * float(position.qty) * side_multiplier
            capital = max(float(position.entry_price) * float(position.qty), 1.0)
            self._bump_daily_funnel("daily_exit_created")
            return BacktestTrade(
                trade_id=str(uuid.uuid4()),
                signal_id=f"{position.forecast_family}:{position.entry_day.isoformat()}",
                ticker=str(config.ticker or "").strip().upper(),
                option_symbol=str(config.ticker or "").strip().upper(),
                entry_ts=position.entry_ts,
                exit_ts=trade_ts,
                side="buy" if int(position.direction) > 0 else "sell",
                qty=int(position.qty),
                entry_price=float(position.entry_price),
                exit_price=float(exit_price),
                pnl=float(pnl),
                return_pct=float(pnl) / capital,
                status="closed",
                metadata={
                    **dict(position.metadata),
                    "strategy_sleeve": str(config.strategy_sleeve or "core_daily"),
                    "signal_cadence": str(config.signal_cadence or "daily_eod"),
                    "forecast_family": position.forecast_family,
                    "combined_forecast": float(position.entry_forecast),
                    "risk_budget_share": float(position.risk_budget_share),
                    "premium_at_risk_pct_nav": float(position.premium_at_risk_pct_nav),
                    "overlay": dict(position.overlay),
                    "exit_reason": str(exit_reason or "window_end"),
                    "fill_pricing_source": "stock_open",
                },
            )
        exit_price, price_source, price_meta = self._resolve_daily_option_price(
            symbol=position.option_symbol,
            day=trade_day,
            ts=trade_ts,
            side="sell",
            config=config,
        )
        if exit_price is None or exit_price <= 0.0:
            self._bump_option_rejection("daily_exit_pricing_unavailable")
            self._bump_daily_funnel("daily_exit_pricing_failed")
            return None
        pnl = (float(exit_price) - float(position.entry_price)) * float(position.qty) * 100.0
        commission = float(config.option_commission_per_contract) * float(position.qty) * 2.0
        pnl -= commission
        capital = max(float(position.entry_price) * float(position.qty) * 100.0, 1.0)
        self._bump_option_funnel("trades_created")
        self._bump_daily_funnel("daily_exit_created")
        contract_open_interest = position.metadata.get("contract_open_interest")
        return BacktestTrade(
            trade_id=str(uuid.uuid4()),
            signal_id=f"{position.forecast_family}:{position.entry_day.isoformat()}",
            ticker=str(config.ticker or "").strip().upper(),
            option_symbol=str(position.option_symbol),
            entry_ts=position.entry_ts,
            exit_ts=trade_ts,
            side="buy",
            qty=int(position.qty),
            entry_price=float(position.entry_price),
            exit_price=float(exit_price),
            pnl=float(pnl),
            return_pct=float(pnl) / capital,
            status="closed",
            metadata={
                **dict(position.metadata),
                **price_meta,
                "strategy_sleeve": str(config.strategy_sleeve or "core_daily"),
                "signal_cadence": str(config.signal_cadence or "daily_eod"),
                "forecast_family": position.forecast_family,
                "combined_forecast": float(position.entry_forecast),
                "asset_bucket": str(config.asset_bucket or infer_asset_bucket(config.ticker)),
                "risk_budget_share": float(position.risk_budget_share),
                "premium_at_risk_pct_nav": float(position.premium_at_risk_pct_nav),
                "overlay": dict(position.overlay),
                "exit_reason": str(exit_reason or "window_end"),
                "fill_pricing_source": str(price_source or "quotes"),
                "contract_open_interest": (
                    int(contract_open_interest or 0) if contract_open_interest is not None else None
                ),
            },
        )

    @staticmethod
    def _daily_trade_count(trades: List[BacktestTrade], day: date, ticker: str) -> int:
        count = 0
        for trade in trades:
            if trade.ticker != ticker:
                continue
            if trade.entry_ts.date() == day:
                count += 1
        return count

    @staticmethod
    def _first_session_bar_on_or_after_time(
        session_bars: List[Dict[str, Any]],
        target_time: time,
    ) -> Optional[Dict[str, Any]]:
        if not session_bars:
            return None
        for row in session_bars:
            ts = row.get("ts")
            if not isinstance(ts, datetime):
                continue
            if _as_et(ts).time() >= target_time:
                return row
        return None

    def _resolve_overnight_exit_plan(
        self,
        *,
        ticker: str,
        entry_day: date,
        setup: Dict[str, Any],
        session_cache: Dict[date, List[Dict[str, Any]]],
    ) -> Optional[Dict[str, Any]]:
        day_offset = max(int(setup.get("overnight_exit_day_offset") or 1), 1)
        exit_day = entry_day + timedelta(days=day_offset)
        next_session = session_cache.get(exit_day)
        if next_session is None:
            next_session = self._load_session_bars(ticker=ticker, day=exit_day)
            session_cache[exit_day] = next_session
        if not next_session:
            return None

        exit_time_text = str(setup.get("overnight_exit_time") or "09:31")
        try:
            hh, mm = exit_time_text.split(":", 1)
            target_time = time(hour=max(0, min(23, int(hh))), minute=max(0, min(59, int(mm))))
        except (TypeError, ValueError):
            target_time = time(9, 31)

        exit_bar = self._first_session_bar_on_or_after_time(next_session, target_time)
        if exit_bar is None:
            return None
        exit_underlying = float(exit_bar.get("open") or 0.0)
        if exit_underlying <= 0:
            exit_underlying = float(exit_bar.get("close") or 0.0)
        if exit_underlying <= 0:
            return None
        return {
            "exit_idx": 0,
            "exit_ts": exit_bar["ts"],
            "exit_underlying": exit_underlying,
            "exit_reason": "overnight_next_open",
            "exit_day": exit_day,
        }

    @staticmethod
    def _opening_range_volume(session_bars: List[Dict[str, Any]], opening_range_minutes: int) -> Optional[float]:
        count = max(int(opening_range_minutes), 1)
        if len(session_bars) < count:
            return None
        volume = sum(float(row.get("volume") or 0.0) for row in session_bars[:count])
        if volume <= 0:
            return None
        return volume

    @staticmethod
    def _opening_range_width_pct(session_bars: List[Dict[str, Any]], opening_range_minutes: int) -> Optional[float]:
        count = max(int(opening_range_minutes), 1)
        if len(session_bars) < count:
            return None
        opening_range = session_bars[:count]
        high = max(float(row.get("high") or 0.0) for row in opening_range)
        low = min(float(row.get("low") or 0.0) for row in opening_range)
        open_price = float(opening_range[0].get("open") or 0.0)
        if high <= 0 or low <= 0 or open_price <= 0 or high <= low:
            return None
        return (high - low) / open_price

    def _relative_opening_volume(
        self,
        ticker: str,
        day: date,
        opening_range_minutes: int,
        lookback_days: int,
        session_cache: Dict[date, List[Dict[str, Any]]],
    ) -> Optional[float]:
        current_bars = session_cache.get(day)
        if current_bars is None:
            current_bars = self._load_session_bars(ticker=ticker, day=day)
            session_cache[day] = current_bars
        current_volume = self._opening_range_volume(current_bars, opening_range_minutes)
        if current_volume is None:
            return None

        history: List[float] = []
        cursor = day - timedelta(days=1)
        attempts = 0
        max_attempts = max(int(lookback_days), 1) * 6
        while len(history) < max(int(lookback_days), 1) and attempts < max_attempts:
            bars = session_cache.get(cursor)
            if bars is None:
                bars = self._load_session_bars(ticker=ticker, day=cursor)
                session_cache[cursor] = bars
            vol = self._opening_range_volume(bars, opening_range_minutes)
            if vol is not None:
                history.append(vol)
            cursor -= timedelta(days=1)
            attempts += 1

        if not history:
            return None
        avg_history = _mean_fast(history)
        if avg_history <= 0:
            return None
        return current_volume / avg_history

    def _load_daily_bars_range(
        self,
        ticker: str,
        start_day: date,
        end_day: date,
    ) -> List[Dict[str, Any]]:
        if end_day < start_day:
            return []
        cache_key = (str(ticker).upper(), start_day, end_day)
        cached = self._daily_bar_range_cache.get(cache_key)
        if cached is not None:
            return cached

        cached_rows = self.store.get_stock_daily_bars(ticker=ticker, start_day=start_day, end_day=end_day)
        cached_days = sorted(
            row["day"]
            for row in cached_rows
            if isinstance(row.get("day"), date)
        )

        missing_ranges: List[Tuple[date, date]] = []
        if not cached_days:
            missing_ranges.append((start_day, end_day))
        else:
            first_cached_day = cached_days[0]
            last_cached_day = cached_days[-1]
            if start_day < first_cached_day:
                front_end = min(end_day, first_cached_day - timedelta(days=1))
                if start_day <= front_end:
                    missing_ranges.append((start_day, front_end))
            if end_day > last_cached_day:
                back_start = max(start_day, last_cached_day + timedelta(days=1))
                if back_start <= end_day:
                    missing_ranges.append((back_start, end_day))

        all_rows = list(cached_rows)
        for missing_start, missing_end in missing_ranges:
            fetched = self._fetch_daily_bars_from_providers(
                ticker=ticker,
                start_day=missing_start,
                end_day=missing_end,
            )
            if not fetched:
                fetched = self._derive_daily_bars_from_intraday_store(
                    ticker=ticker,
                    start_day=missing_start,
                    end_day=missing_end,
                )
            if not fetched:
                continue
            to_store: List[Dict[str, Any]] = []
            for row in fetched:
                ts = row.get("ts")
                day_value = row.get("day")
                day = day_value if isinstance(day_value, date) else None
                if day is None and isinstance(ts, datetime):
                    day = _as_et(ts).date()
                if day is None:
                    continue
                to_store.append(
                    {
                        **row,
                        "day": day,
                    }
                )
            if to_store:
                if self._persist_fetched_market_data:
                    self.store.insert_stock_daily_bars(to_store)
                all_rows.extend(to_store)

        rows = all_rows if all_rows else self.store.get_stock_daily_bars(ticker=ticker, start_day=start_day, end_day=end_day)
        dedup: Dict[date, Dict[str, Any]] = {}
        for row in rows:
            day = row.get("day")
            ts = row.get("ts")
            if not isinstance(day, date):
                if not isinstance(ts, datetime):
                    continue
                day = _as_et(ts).date()
            dedup[day] = {
                "ticker": row.get("ticker"),
                "ts": ts,
                "open": row.get("open"),
                "high": row.get("high"),
                "low": row.get("low"),
                "close": row.get("close"),
                "volume": row.get("volume"),
            }
        out = [dedup[key] for key in sorted(dedup)]
        self._daily_bar_range_cache[cache_key] = out
        return out

    def _derive_daily_bars_from_intraday_store(
        self,
        *,
        ticker: str,
        start_day: date,
        end_day: date,
    ) -> List[Dict[str, Any]]:
        start_dt = datetime.combine(start_day, time(0, 0))
        end_dt = datetime.combine(end_day + timedelta(days=1), time(0, 0))
        try:
            minute_rows = self.store.get_stock_bars(
                ticker=str(ticker).upper(),
                start=start_dt,
                end=end_dt,
            )
        except Exception:
            return []
        if not minute_rows:
            return []

        aggregated: Dict[date, Dict[str, Any]] = {}
        for row in minute_rows:
            ts = row.get("ts")
            if not isinstance(ts, datetime):
                continue
            day = _as_et(ts).date()
            if day < start_day or day > end_day:
                continue
            open_price = _safe_float(row.get("open"))
            high_price = _safe_float(row.get("high"))
            low_price = _safe_float(row.get("low"))
            close_price = _safe_float(row.get("close"))
            volume = int(row.get("volume") or 0)
            if (
                open_price is None
                or high_price is None
                or low_price is None
                or close_price is None
            ):
                continue
            current = aggregated.get(day)
            if current is None:
                aggregated[day] = {
                    "ticker": str(ticker).upper(),
                    "day": day,
                    "ts": datetime.combine(day, time(0, 0), tzinfo=timezone.utc),
                    "open": float(open_price),
                    "high": float(high_price),
                    "low": float(low_price),
                    "close": float(close_price),
                    "volume": int(volume),
                }
                continue
            current["high"] = max(float(current.get("high") or high_price), float(high_price))
            current["low"] = min(float(current.get("low") or low_price), float(low_price))
            current["close"] = float(close_price)
            current["volume"] = int(current.get("volume") or 0) + int(volume)
        return [aggregated[key] for key in sorted(aggregated)]

    def _fetch_daily_bars_from_providers(
        self,
        ticker: str,
        start_day: date,
        end_day: date,
    ) -> List[Dict[str, Any]]:
        bars: List[Dict[str, Any]] = []
        ticker_key = str(ticker).upper()
        if self.cutemarkets_provider is not None and not self._optional_aux_provider_denied(
            provider_name="cutemarkets",
            dataset="stock_daily_bars",
            ticker=ticker_key,
        ):
            try:
                bars = self.cutemarkets_provider.fetch_stock_bars(
                    ticker=ticker_key,
                    start=start_day,
                    end=end_day,
                    multiplier=1,
                    timespan="day",
                )
            except Exception as exc:
                if self._is_optional_auxiliary_ticker(ticker_key) and self._provider_error_is_denial(exc):
                    self._cache_optional_aux_provider_denial(
                        provider_name="cutemarkets",
                        dataset="stock_daily_bars",
                        ticker=ticker_key,
                        reason="not_authorized",
                    )
                bars = []
            if not bars and self._is_optional_auxiliary_ticker(ticker_key):
                self._cache_optional_aux_provider_denial(
                    provider_name="cutemarkets",
                    dataset="stock_daily_bars",
                    ticker=ticker_key,
                    reason="empty",
                )

        if not bars and self.alpaca_data_provider is not None and not self._optional_aux_provider_denied(
            provider_name="alpaca",
            dataset="stock_daily_bars",
            ticker=ticker_key,
        ):
            start_iso = datetime.combine(start_day, time(0, 0), tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
            end_iso = (
                datetime.combine(end_day + timedelta(days=1), time(0, 0), tzinfo=timezone.utc)
                .isoformat()
                .replace("+00:00", "Z")
            )
            try:
                fetched = self.alpaca_data_provider.fetch_stock_bars(
                    symbol=ticker_key,
                    start=start_iso,
                    end=end_iso,
                    timeframe="1Day",
                )
            except Exception:
                if self._is_optional_auxiliary_ticker(ticker_key):
                    self._cache_optional_aux_provider_denial(
                        provider_name="alpaca",
                        dataset="stock_daily_bars",
                        ticker=ticker_key,
                        reason="error",
                    )
                fetched = []
            bars = [_map_alpaca_stock_bar(ticker=ticker_key, row=row) for row in fetched]
            bars = [row for row in bars if row is not None]
            if not bars and self._is_optional_auxiliary_ticker(ticker_key):
                self._cache_optional_aux_provider_denial(
                    provider_name="alpaca",
                    dataset="stock_daily_bars",
                    ticker=ticker_key,
                    reason="empty",
                )

        dedup: Dict[date, Dict[str, Any]] = {}
        for row in bars:
            ts = row.get("ts")
            if not isinstance(ts, datetime):
                continue
            day = _as_et(ts).date()
            dedup[day] = row
        return [dedup[key] for key in sorted(dedup)]

    @staticmethod
    def _atr_from_daily_history(
        daily_history: List[Dict[str, Any]],
        day: date,
        lookback_days: int,
    ) -> Optional[float]:
        if lookback_days < 2:
            return None

        past = [row for row in daily_history if isinstance(row.get("ts"), datetime) and _as_et(row["ts"]).date() < day]
        if len(past) < (lookback_days + 1):
            return None

        true_ranges: List[float] = []
        prev_close: Optional[float] = None
        # Skip extreme daily-bar moves that are usually bad prints in vendor data.
        # These outliers can explode ATR and invalidate stop placement.
        max_daily_move_fraction = 0.50
        for row in past:
            high = float(row.get("high") or 0.0)
            low = float(row.get("low") or 0.0)
            close = float(row.get("close") or 0.0)
            if high <= 0 or low <= 0 or close <= 0:
                continue
            if high <= low:
                continue

            if prev_close is None:
                base_price = close
            else:
                base_price = prev_close
            if base_price > 0:
                max_move = max(high - low, abs(high - base_price), abs(low - base_price))
                if (max_move / base_price) > max_daily_move_fraction:
                    prev_close = close
                    continue

            if prev_close is None:
                tr = high - low
            else:
                tr = max(
                    high - low,
                    abs(high - prev_close),
                    abs(low - prev_close),
                )
            true_ranges.append(tr)
            prev_close = close

        if len(true_ranges) < lookback_days:
            return None
        return _mean_fast(true_ranges[-lookback_days:])

    @staticmethod
    def _previous_close_from_daily_history(
        daily_history: List[Dict[str, Any]],
        day: date,
    ) -> Optional[float]:
        if not daily_history:
            return None
        past = [
            row
            for row in daily_history
            if isinstance(row.get("ts"), datetime) and _as_et(row["ts"]).date() < day
        ]
        if not past:
            return None
        past.sort(key=lambda row: row["ts"])
        close = _safe_float(past[-1].get("close"))
        if close is None or close <= 0:
            return None
        return close

    @staticmethod
    def _previous_daily_bar(
        daily_history: List[Dict[str, Any]],
        day: date,
        lookback: int = 1,
    ) -> Optional[Dict[str, Any]]:
        if lookback < 1 or not daily_history:
            return None
        past = [
            row
            for row in daily_history
            if isinstance(row.get("ts"), datetime) and _as_et(row["ts"]).date() < day
        ]
        if not past or len(past) < lookback:
            return None
        past.sort(key=lambda row: row["ts"])
        return past[-lookback]

    @staticmethod
    def _daily_bar_range_pct(bar: Optional[Dict[str, Any]]) -> Optional[float]:
        if not isinstance(bar, dict):
            return None
        high = _safe_float(bar.get("high"))
        low = _safe_float(bar.get("low"))
        close = _safe_float(bar.get("close"))
        if high is None or low is None or close is None:
            return None
        if high <= low or close <= 0:
            return None
        return (high - low) / close

    @staticmethod
    def _is_inside_bar(
        inner_bar: Optional[Dict[str, Any]],
        outer_bar: Optional[Dict[str, Any]],
    ) -> bool:
        if not isinstance(inner_bar, dict) or not isinstance(outer_bar, dict):
            return False
        inner_high = _safe_float(inner_bar.get("high"))
        inner_low = _safe_float(inner_bar.get("low"))
        outer_high = _safe_float(outer_bar.get("high"))
        outer_low = _safe_float(outer_bar.get("low"))
        if None in {inner_high, inner_low, outer_high, outer_low}:
            return False
        if outer_high <= outer_low or inner_high <= inner_low:
            return False
        return bool(inner_high <= outer_high and inner_low >= outer_low)

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

    def _load_session_bars_range_local(
        self,
        *,
        ticker: str,
        start_day: date,
        end_day: date,
    ) -> Dict[date, List[Dict[str, Any]]]:
        if end_day < start_day:
            return {}

        ticker_key = str(ticker).upper()
        requested_days = _iter_dates(start_day, end_day)
        missing_days = [day for day in requested_days if (ticker_key, day) not in self._session_bar_cache]
        if missing_days:
            self._prime_session_bar_cache(
                ticker=ticker_key,
                start_day=min(missing_days),
                end_day=max(missing_days),
            )
            self._record_option_market_data_io(
                dataset="session_bars",
                loaded_count=len(missing_days),
            )
        return {
            day: list(self._session_bar_cache.get((ticker_key, day), []))
            for day in requested_days
        }

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

    def _fetch_stock_bar_range_from_providers(
        self,
        *,
        ticker: str,
        start_day: date,
        end_day: date,
    ) -> Tuple[List[Dict[str, Any]], bool]:
        coverage_complete = False
        ticker_key = str(ticker).upper()

        if self.cutemarkets_provider is not None and not self._optional_aux_provider_denied(
            provider_name="cutemarkets",
            dataset="session_bars",
            ticker=ticker_key,
        ):
            try:
                fetched = self.cutemarkets_provider.fetch_stock_bars(
                    ticker=ticker_key,
                    start=start_day,
                    end=end_day,
                    multiplier=1,
                    timespan="minute",
                )
            except Exception as exc:
                if self._is_optional_auxiliary_ticker(ticker_key) and self._provider_error_is_denial(exc):
                    self._cache_optional_aux_provider_denial(
                        provider_name="cutemarkets",
                        dataset="session_bars",
                        ticker=ticker_key,
                        reason="not_authorized",
                    )
                fetched = []
            else:
                coverage_complete = True
            if not fetched and self._is_optional_auxiliary_ticker(ticker_key):
                self._cache_optional_aux_provider_denial(
                    provider_name="cutemarkets",
                    dataset="session_bars",
                    ticker=ticker_key,
                    reason="empty",
                )
            if fetched:
                return fetched, True

        if self.alpaca_data_provider is not None and not self._optional_aux_provider_denied(
            provider_name="alpaca",
            dataset="session_bars",
            ticker=ticker_key,
        ):
            start_iso = datetime.combine(start_day, time(0, 0), tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
            end_iso = datetime.combine(end_day + timedelta(days=1), time(0, 0), tzinfo=timezone.utc).isoformat().replace(
                "+00:00",
                "Z",
            )
            try:
                fetched = self.alpaca_data_provider.fetch_stock_bars(
                    symbol=ticker_key,
                    start=start_iso,
                    end=end_iso,
                    timeframe="1Min",
                )
            except Exception:
                if self._is_optional_auxiliary_ticker(ticker_key):
                    self._cache_optional_aux_provider_denial(
                        provider_name="alpaca",
                        dataset="session_bars",
                        ticker=ticker_key,
                        reason="error",
                    )
                fetched = []
            else:
                coverage_complete = True
            mapped = [_map_alpaca_stock_bar(ticker=ticker_key, row=row) for row in fetched]
            mapped = [row for row in mapped if row is not None]
            if not mapped and self._is_optional_auxiliary_ticker(ticker_key):
                self._cache_optional_aux_provider_denial(
                    provider_name="alpaca",
                    dataset="session_bars",
                    ticker=ticker_key,
                    reason="empty",
                )
            if mapped:
                return mapped, True

        return [], coverage_complete

    @staticmethod
    def _session_rows_by_day(
        *,
        rows: List[Dict[str, Any]],
        start_day: date,
        end_day: date,
    ) -> Dict[date, List[Dict[str, Any]]]:
        out: Dict[date, List[Dict[str, Any]]] = {}
        for row in rows:
            ts = row.get("ts")
            if not isinstance(ts, datetime):
                continue
            et_dt = _as_et(ts)
            session_day = et_dt.date()
            if session_day < start_day or session_day > end_day:
                continue
            if et_dt.time() < time(9, 30) or et_dt.time() > time(16, 0):
                continue
            out.setdefault(session_day, []).append(row)
        for day_rows in out.values():
            day_rows.sort(key=lambda item: item["ts"])
        return out

    @staticmethod
    def _premarket_rows_by_day(
        *,
        rows: List[Dict[str, Any]],
        start_day: date,
        end_day: date,
    ) -> Dict[date, List[Dict[str, Any]]]:
        ticker = ""
        for row in rows:
            ticker = str(row.get("ticker") or row.get("symbol") or "").strip().upper()
            if ticker:
                break
        grouped, _ = pmctx.group_premarket_rows_by_day(
            ticker=ticker,
            rows=rows,
            start_day=start_day,
            end_day=end_day,
        )
        return grouped

    def _prime_premarket_context_range(
        self,
        *,
        ticker: str,
        start_day: date,
        end_day: date,
    ) -> None:
        ticker_key = str(ticker).upper()
        source_maps = pmctx.load_premarket_source_maps(
            store=self.store,
            cutemarkets=self.cutemarkets_provider,
            alpaca=self.alpaca_data_provider,
            ticker=ticker_key,
            start_day=start_day,
            end_day=end_day,
        )
        resolved, source_used, _ = pmctx.resolve_premarket_days_with_fallback(
            source_maps={
                "store": dict(source_maps.get("store") or {}),
                "cutemarkets": dict(source_maps.get("cutemarkets") or {}),
                "alpaca": dict(source_maps.get("alpaca") or {}),
            },
            start_day=start_day,
            end_day=end_day,
        )
        for day, bars in resolved.items():
            self._premarket_bar_cache[(ticker_key, day)] = [dict(row) for row in bars]
            self._premarket_source_cache[(ticker_key, day)] = str(source_used.get(day) or "none")

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

    def _load_premarket_bars_uncached(self, *, ticker: str, day: date) -> List[Dict[str, Any]]:
        ticker_key = str(ticker).upper()
        cache_key = (ticker_key, day)
        if cache_key in self._premarket_bar_cache:
            return list(self._premarket_bar_cache[cache_key])
        self._prime_premarket_context_range(ticker=ticker_key, start_day=day, end_day=day)
        if cache_key not in self._premarket_bar_cache:
            self._premarket_bar_cache[cache_key] = []
            self._premarket_source_cache[cache_key] = "none"
        return list(self._premarket_bar_cache[cache_key])

    def _get_preopen_context(
        self,
        *,
        ticker: str,
        day: date,
        prev_close: Optional[float],
        daily_analytics: _DailyHistoryAnalytics,
        vol_regime_prev_close: Optional[float] = None,
        vol_regime_analytics: Optional[_DailyHistoryAnalytics] = None,
    ) -> Dict[str, Any]:
        ticker_key = str(ticker).upper()
        bars = self._load_premarket_bars(ticker_key, day)
        source_used = str(self._premarket_source_cache.get((ticker_key, day)) or "none")
        vix_5d_change_pct: Optional[float] = None
        if vol_regime_analytics is not None:
            prior5 = vol_regime_analytics.previous_bar(day=day, lookback=5)
            prior5_close = _safe_float((prior5 or {}).get("close"))
            if (
                vol_regime_prev_close is not None
                and vol_regime_prev_close > 0.0
                and prior5_close is not None
                and prior5_close > 0.0
            ):
                vix_5d_change_pct = (float(vol_regime_prev_close) / float(prior5_close)) - 1.0
        return pmctx.build_preopen_context_row(
            ticker=ticker_key,
            day=day,
            source_used=source_used,
            premarket_bars=bars,
            prev_close=prev_close,
            adv_20=daily_analytics.avg_daily_volume(day=day, lookback_days=20),
            recent_daily_volume_ratio_5d_20d=daily_analytics.avg_daily_volume_ratio(day=day),
            vix_prev_close=vol_regime_prev_close,
            vix_5d_change_pct=vix_5d_change_pct,
        )

    def _get_lfcm_context(
        self,
        ticker: str,
        day: date,
        prev_close: Optional[float],
        avg_daily_volume: Optional[float],
    ) -> Dict[str, Any]:
        ticker_key = str(ticker).upper()
        if ticker_key not in self._lfcm_ticker_details_cache:
            if self.cutemarkets_provider is not None:
                try:
                    self._lfcm_ticker_details_cache[ticker_key] = self.cutemarkets_provider.fetch_ticker_details(ticker_key)
                except Exception:
                    self._lfcm_ticker_details_cache[ticker_key] = {}
            else:
                self._lfcm_ticker_details_cache[ticker_key] = {}
        details = self._lfcm_ticker_details_cache[ticker_key]
        current_float = details.get("float_shares") or details.get("shares_outstanding")

        today = date.today()
        years_ago = max((today - day).days / 365.25, 0.0)

        news_key = (ticker_key, day)
        if news_key not in self._lfcm_news_cache:
            merged_headlines = pmctx.merge_headlines_by_scan_date(
                pmctx.fetch_cutemarkets_headlines_by_scan_date(
                    self.cutemarkets_provider,
                    ticker=ticker_key,
                    start_day=day,
                    end_day=day,
                ),
                pmctx.fetch_alpaca_headlines_by_scan_date(
                    self.alpaca_data_provider,
                    ticker=ticker_key,
                    start_day=day,
                    end_day=day,
                ),
            )
            self._lfcm_news_cache[news_key] = list(merged_headlines.get(day, []))

        return {
            "premarket_bars": self._load_premarket_bars(ticker_key, day),
            "prev_close": prev_close,
            "avg_daily_volume": avg_daily_volume,
            "current_float": current_float,
            "years_ago": years_ago,
            "catalyst_headlines": self._lfcm_news_cache[news_key],
        }

    def _simulate_historical_option_trade(
        self,
        ticker: str,
        day: date,
        setup: Dict[str, Any],
        exit_plan: Dict[str, Any],
        current_equity: float,
        config: IntradayOptionsBacktestConfig,
    ) -> Optional[BacktestTrade]:
        self._bump_option_funnel("historical_option_attempts")
        direction = int(setup["direction"])
        structure_mode = str(config.option_structure_mode or "single_leg").strip().lower()
        attempt_snapshot: Dict[str, Any] = {
            "symbol": str(ticker or "").strip().upper(),
            "session_date": day,
            "strategy_variant": str(setup.get("strategy_variant") or config.strategy_variant or ""),
            "direction": int(direction),
            "delayed_entry_signal_ts": (
                setup.get("entry_ts") if isinstance(setup.get("entry_ts"), datetime) else None
            ),
            "effective_exit_signal_ts": (
                exit_plan.get("exit_ts") if isinstance(exit_plan.get("exit_ts"), datetime) else None
            ),
            "trade_limit_state": "passed",
            "trade_created": False,
            "rejection_reason": "",
            "option_structure_mode": structure_mode,
            "long_leg_symbol": None,
            "short_leg_symbol": None,
            "contract_selection_dte": None,
            "contract_strike": None,
            "selected_abs_delta": None,
            "selected_strike_distance_steps": None,
            "selected_entry_bar_volume": None,
            "selected_quote_spread_pct": None,
            "initial_selected_option_symbol": None,
            "final_selected_option_symbol": None,
            "initial_selected_expiration_date": None,
            "final_selected_expiration_date": None,
            "conversion_changed_expiry": False,
            "initial_contract_rank": None,
            "final_contract_rank": None,
            "initial_selected_strike_distance_steps": None,
            "final_selected_strike_distance_steps": None,
            "initial_selected_entry_bar_volume": None,
            "final_selected_entry_bar_volume": None,
            "initial_selected_quote_spread_pct": None,
            "final_selected_quote_spread_pct": None,
            "conversion_applied": False,
            "conversion_attempt_count": 0,
            "conversion_terminal_rejection_reason": "",
            "entry_volume": None,
            "contract_open_interest": None,
            "open_interest_data_available": None,
            "entry_quote_ts": None,
            "exit_quote_ts": None,
            "entry_quote_spread_abs": None,
            "entry_quote_spread_pct": None,
            "expected_move_to_extrinsic_ratio": None,
            "expected_move_to_debit_ratio": None,
            "expected_move_to_spread_ratio": None,
            "entry_debit": None,
            "entry_credit": None,
            "entry_price_effective": None,
            "exit_price_effective": None,
            "option_quote_fallback_used": False,
        }
        self._last_option_rejection_reason = ""

        def _finalize_attempt(trade: Optional[BacktestTrade]) -> Optional[BacktestTrade]:
            if trade is not None:
                self._append_option_attempt_log_row(
                    self._build_option_attempt_row_from_trade(
                        trade=trade,
                        session_date=day,
                        trade_limit_state=str(attempt_snapshot.get("trade_limit_state") or "passed"),
                    )
                )
                return trade
            failure_row = dict(attempt_snapshot)
            failure_row["trade_created"] = False
            failure_row["rejection_reason"] = (
                str(self._last_option_rejection_reason or self._last_contract_selection_reason or "attempt_failed")
                .strip()
                or "attempt_failed"
            )
            self._append_option_attempt_log_row(failure_row)
            return None

        if self.cutemarkets_provider is None and self.alpaca_data_provider is None:
            self._bump_option_rejection("no_option_market_data_provider")
            return _finalize_attempt(None)

        is_vertical_debit = structure_mode == "vertical_debit"
        is_vertical_credit = structure_mode == "vertical_credit"
        is_vertical_pair = is_vertical_debit or is_vertical_credit
        enrichment_mode = _normalize_option_chain_snapshot_enrichment_mode(
            getattr(config, "option_chain_snapshot_enrichment_mode", "full")
        )

        selected_contract = self._select_contract(
            ticker=ticker,
            day=day,
            direction=direction,
            entry_underlying=float(setup["entry_underlying"]),
            config=config,
            selection_ts=setup.get("entry_ts") if isinstance(setup.get("entry_ts"), datetime) else None,
        )
        selection_meta = dict(self._last_contract_selection_meta or {})
        if int(selection_meta.get("pool_contract_count") or 0) > 0 or selected_contract is not None:
            self._bump_option_funnel("option_chain_available")
        if selected_contract is None:
            selection_rejections = dict(selection_meta.get("rejection_counts") or {})
            for reason, amount in selection_rejections.items():
                self._bump_option_rejection(str(reason), int(amount or 0))
            final_reason = str(self._last_contract_selection_reason or "contract_not_found")
            if final_reason not in selection_rejections:
                self._bump_option_rejection(final_reason)
            return _finalize_attempt(None)
        self._bump_option_funnel("contract_selected")
        attempt_snapshot.update(
            {
                "contract_selection_dte": (
                    int(selected_contract.get("_selection_dte") or 0)
                    if selected_contract.get("_selection_dte") not in (None, "")
                    else None
                ),
                "contract_strike": _safe_float(selected_contract.get("strike_price")),
                "selected_abs_delta": _safe_float(selected_contract.get("_selection_abs_delta")),
                "selected_strike_distance_steps": (
                    int(selected_contract.get("_selection_strike_distance_steps") or 0)
                    if selected_contract.get("_selection_strike_distance_steps") not in (None, "")
                    else None
                ),
                "selected_entry_bar_volume": (
                    int(selected_contract.get("_selection_entry_bar_volume") or 0)
                    if selected_contract.get("_selection_entry_bar_volume") not in (None, "")
                    else None
                ),
                "selected_quote_spread_pct": _safe_float(selected_contract.get("_selection_quote_spread_pct")),
                "contract_open_interest": (
                    int(selected_contract.get("open_interest") or 0)
                    if selected_contract.get("open_interest") not in (None, "")
                    else None
                ),
            }
        )
        if attempt_snapshot.get("contract_open_interest") is not None:
            attempt_snapshot["open_interest_data_available"] = bool(
                int(attempt_snapshot["contract_open_interest"] or 0) > 0
            )
        ranked_contract_pool = _selection_ranked_contract_pool(selection_meta, selected_contract)
        initial_selected_option_symbol = str(selected_contract.get("symbol") or "").strip()
        initial_selected_expiration_date = _selection_contract_expiration_date_text(selected_contract) or None
        initial_contract_rank = _selection_contract_rank(selected_contract, default_rank=1)
        initial_selected_strike_distance_steps = _selection_contract_strike_distance_steps(selected_contract)
        initial_selected_entry_bar_volume = _selection_contract_entry_bar_volume(selected_contract)
        initial_selected_quote_spread_pct = _selection_contract_quote_spread_pct(selected_contract)
        attempt_snapshot.update(
            {
                "initial_selected_option_symbol": initial_selected_option_symbol or None,
                "final_selected_option_symbol": initial_selected_option_symbol or None,
                "initial_selected_expiration_date": initial_selected_expiration_date,
                "final_selected_expiration_date": initial_selected_expiration_date,
                "conversion_changed_expiry": False,
                "initial_contract_rank": int(initial_contract_rank),
                "final_contract_rank": int(initial_contract_rank),
                "initial_selected_strike_distance_steps": initial_selected_strike_distance_steps,
                "final_selected_strike_distance_steps": initial_selected_strike_distance_steps,
                "initial_selected_entry_bar_volume": initial_selected_entry_bar_volume,
                "final_selected_entry_bar_volume": initial_selected_entry_bar_volume,
                "initial_selected_quote_spread_pct": initial_selected_quote_spread_pct,
                "final_selected_quote_spread_pct": initial_selected_quote_spread_pct,
                "conversion_applied": False,
                "conversion_attempt_count": 0,
                "conversion_terminal_rejection_reason": "",
            }
        )
        conversion_mode = _normalize_option_post_selection_conversion_mode(
            getattr(config, "option_post_selection_conversion_mode", "disabled")
        )
        max_conversion_alternates = max(int(getattr(config, "option_post_selection_max_alternates", 0) or 0), 0)
        max_conversion_final_rank = max(int(getattr(config, "option_post_selection_max_final_rank", 0) or 0), 0)
        raw_max_conversion_final_strike_distance_steps = getattr(
            config,
            "option_post_selection_max_final_strike_distance_steps",
            -1,
        )
        max_conversion_final_strike_distance_steps = int(
            raw_max_conversion_final_strike_distance_steps
            if raw_max_conversion_final_strike_distance_steps not in (None, "")
            else -1
        )

        def _simulate_single_leg_candidate_with_optional_conversion(
            candidate_contract: Dict[str, Any],
            *,
            conversion_attempt_count: int,
            suppress_retryable_micro_failure: bool,
        ) -> Optional[BacktestTrade]:
            long_contract_local = self._maybe_fill_contract_open_interest(
                ticker=ticker,
                day=day,
                contract=dict(candidate_contract),
                enrichment_mode=enrichment_mode,
            )
            long_option_symbol_local = str(long_contract_local.get("symbol") or "").strip()
            final_selected_expiration_date = (
                _selection_contract_expiration_date_text(long_contract_local) or initial_selected_expiration_date
            )
            final_contract_rank = _selection_contract_rank(
                long_contract_local,
                default_rank=conversion_attempt_count + 1,
            )
            attempt_snapshot.update(
                {
                    "long_leg_symbol": long_option_symbol_local or None,
                    "short_leg_symbol": None,
                    "contract_selection_dte": (
                        int(long_contract_local.get("_selection_dte") or 0)
                        if long_contract_local.get("_selection_dte") not in (None, "")
                        else None
                    ),
                    "contract_strike": _safe_float(long_contract_local.get("strike_price")),
                    "selected_abs_delta": _safe_float(long_contract_local.get("_selection_abs_delta")),
                    "selected_strike_distance_steps": (
                        int(long_contract_local.get("_selection_strike_distance_steps") or 0)
                        if long_contract_local.get("_selection_strike_distance_steps") not in (None, "")
                        else None
                    ),
                    "selected_entry_bar_volume": (
                        int(long_contract_local.get("_selection_entry_bar_volume") or 0)
                        if long_contract_local.get("_selection_entry_bar_volume") not in (None, "")
                        else None
                    ),
                    "selected_quote_spread_pct": _safe_float(
                        long_contract_local.get("_selection_quote_spread_pct")
                    ),
                    "contract_open_interest": (
                        int(long_contract_local.get("open_interest") or 0)
                        if long_contract_local.get("open_interest") not in (None, "")
                        else None
                    ),
                    "open_interest_data_available": (
                        bool(int(long_contract_local.get("open_interest") or 0) > 0)
                        if long_contract_local.get("open_interest") not in (None, "")
                        else None
                    ),
                    "final_selected_option_symbol": long_option_symbol_local or None,
                    "final_selected_expiration_date": final_selected_expiration_date or None,
                    "conversion_changed_expiry": bool(
                        initial_selected_expiration_date
                        and final_selected_expiration_date
                        and initial_selected_expiration_date != final_selected_expiration_date
                    ),
                    "final_contract_rank": int(final_contract_rank),
                    "final_selected_strike_distance_steps": _selection_contract_strike_distance_steps(
                        long_contract_local
                    ),
                    "final_selected_entry_bar_volume": _selection_contract_entry_bar_volume(long_contract_local),
                    "final_selected_quote_spread_pct": _selection_contract_quote_spread_pct(long_contract_local),
                    "conversion_applied": bool(conversion_attempt_count > 0),
                    "conversion_attempt_count": int(conversion_attempt_count),
                    "conversion_terminal_rejection_reason": "",
                }
            )
            self._last_option_rejection_reason = ""
            if not long_option_symbol_local:
                self._bump_option_rejection("contract_symbol_missing")
                return None

            trade_option_symbol_local = long_option_symbol_local
            long_strike_local = _safe_float(long_contract_local.get("strike_price")) or 0.0
            exit_day_raw_local = exit_plan.get("exit_day")
            exit_day_local = exit_day_raw_local if isinstance(exit_day_raw_local, date) else day
            entry_bars_local = self._load_option_bars(symbol=long_option_symbol_local, day=day)
            if not entry_bars_local:
                self._bump_option_rejection("option_bars_missing")
                return None
            if exit_day_local == day:
                exit_bars_local = entry_bars_local
            else:
                exit_bars_local = self._load_option_bars(symbol=long_option_symbol_local, day=exit_day_local)
                if not exit_bars_local:
                    self._bump_option_rejection("option_bars_missing")
                    return None

            entry_delay_base_local = max(int(config.execution_entry_delay_minutes), 0)
            exit_delay_base_local = max(int(config.execution_exit_delay_minutes), 0)
            randomization_enabled_local = bool(config.execution_delay_randomization)
            entry_delay_local = _jittered_delay_minutes(
                base_delay_minutes=entry_delay_base_local,
                jitter_minutes=max(int(config.execution_entry_delay_jitter_minutes), 0),
                randomization_enabled=randomization_enabled_local,
                random_seed=int(config.execution_delay_random_seed),
                seed_key=(
                    f"{ticker}|{day.isoformat()}|{trade_option_symbol_local}|entry|"
                    f"{setup['entry_ts'].isoformat() if isinstance(setup.get('entry_ts'), datetime) else setup.get('entry_ts')}"
                ),
            )
            exit_delay_local = _jittered_delay_minutes(
                base_delay_minutes=exit_delay_base_local,
                jitter_minutes=max(int(config.execution_exit_delay_jitter_minutes), 0),
                randomization_enabled=randomization_enabled_local,
                random_seed=int(config.execution_delay_random_seed),
                seed_key=(
                    f"{ticker}|{day.isoformat()}|{trade_option_symbol_local}|exit|"
                    f"{exit_plan['exit_ts'].isoformat() if isinstance(exit_plan.get('exit_ts'), datetime) else exit_plan.get('exit_ts')}"
                ),
            )
            delayed_entry_ts_local = _apply_execution_timing_model(
                setup["entry_ts"] + timedelta(minutes=entry_delay_local),
                model=str(config.execution_timing_model or "bar_open"),
                poll_seconds=int(config.execution_poll_seconds),
                signal_confirm_seconds=int(config.execution_entry_signal_confirm_seconds),
                fill_latency_seconds=int(config.execution_entry_fill_latency_seconds),
            )
            delayed_exit_ts_local = _apply_execution_timing_model(
                exit_plan["exit_ts"] + timedelta(minutes=exit_delay_local),
                model=str(config.execution_timing_model or "bar_open"),
                poll_seconds=int(config.execution_poll_seconds),
                signal_confirm_seconds=int(config.execution_exit_signal_confirm_seconds),
                fill_latency_seconds=int(config.execution_exit_fill_latency_seconds),
            )
            attempt_snapshot["delayed_entry_signal_ts"] = delayed_entry_ts_local
            attempt_snapshot["effective_exit_signal_ts"] = delayed_exit_ts_local

            entry_bar_local = _first_bar_on_or_after(entry_bars_local, delayed_entry_ts_local)
            exit_bar_local = _first_bar_on_or_after(exit_bars_local, delayed_exit_ts_local)
            if entry_bar_local is None:
                self._last_option_rejection_reason = "micro_entry_bar_missing"
                if suppress_retryable_micro_failure:
                    return None
                self._bump_option_rejection("micro_entry_bar_missing")
                attempt_snapshot["conversion_terminal_rejection_reason"] = "micro_entry_bar_missing"
                return None
            if exit_bar_local is None:
                self._bump_option_rejection("entry_or_exit_bar_missing")
                return None

            entry_exit_bars_available = True
            entry_bar_close_local = float(entry_bar_local.get("close") or 0.0)
            entry_fill_ts_local = entry_bar_local["ts"]
            entry_raw_local = _causal_bar_fill_price(entry_bar_local)
            exit_fill_ts_local = exit_bar_local["ts"]
            exit_raw_local = _causal_bar_fill_price(exit_bar_local)
            effective_exit_reason_local = str(exit_plan.get("exit_reason") or "")
            effective_exit_ts_local = delayed_exit_ts_local
            option_premium_stop_triggered_local = False
            option_premium_stop_price_raw_local: Optional[float] = None
            entry_volume_local = int(entry_bar_local.get("volume") or 0)
            entry_high_local = float(entry_bar_local.get("high") or 0.0)
            entry_low_local = float(entry_bar_local.get("low") or 0.0)
            entry_bar_range_pct_local = (
                ((entry_high_local - entry_low_local) / entry_bar_close_local)
                if entry_bar_close_local > 0
                else 0.0
            )
            attempt_snapshot["entry_volume"] = int(entry_volume_local)

            quote_pricing_enabled_local = bool(config.use_option_quotes_for_fills)
            quote_fallback_enabled_local = bool(config.option_quote_fill_fallback_to_bar_close)
            fill_pricing_source_local = "bar_open"
            used_quote_fallback_local = False
            can_use_quote_fill_local = False
            pricing_resolved = False
            structure_passed = False

            entry_quote_local: Optional[Dict[str, Any]] = None
            exit_quote_local: Optional[Dict[str, Any]] = None
            entry_quote_bid_local: Optional[float] = None
            entry_quote_ask_local: Optional[float] = None
            entry_quote_mid_local: Optional[float] = None
            entry_quote_spread_abs_local: Optional[float] = None
            entry_quote_spread_pct_local: Optional[float] = None
            exit_quote_bid_local: Optional[float] = None
            exit_quote_ask_local: Optional[float] = None
            expected_move_to_extrinsic_ratio_local: Optional[float] = None
            expected_move_to_spread_ratio_local: Optional[float] = None
            expected_move_to_debit_ratio_local: Optional[float] = None
            premium_take_profit_triggered_local = False
            premium_stop_triggered_local = False
            option_take_profit_pct_local = max(float(config.option_take_profit_pct), 0.0)
            option_max_loss_pct_local = max(float(config.option_max_loss_pct), 0.0)
            entry_quote_ready_local = False
            exit_quote_ready_local = False

            if quote_pricing_enabled_local:
                entry_quotes_local = self._load_option_quotes(symbol=long_option_symbol_local, day=day)
                entry_quote_local = self._lookup_option_quote_on_or_after(
                    symbol=long_option_symbol_local,
                    day=day,
                    ts=delayed_entry_ts_local,
                )
                if entry_quote_local is not None:
                    entry_quote_bid_local = _safe_float(entry_quote_local.get("bid"))
                    entry_quote_ask_local = _safe_float(entry_quote_local.get("ask"))
                    if (
                        entry_quote_bid_local is not None
                        and entry_quote_bid_local > 0
                        and entry_quote_ask_local is not None
                        and entry_quote_ask_local > 0
                    ):
                        entry_quote_mid_local = (entry_quote_bid_local + entry_quote_ask_local) / 2.0
                        entry_quote_spread_abs_local = max(
                            entry_quote_ask_local - entry_quote_bid_local,
                            0.0,
                        )
                        if entry_quote_mid_local > 0:
                            entry_quote_spread_pct_local = entry_quote_spread_abs_local / entry_quote_mid_local
                entry_quote_ready_local = bool(entry_quote_ask_local is not None and entry_quote_ask_local > 0.0)
                if isinstance(entry_quote_local, dict) and isinstance(entry_quote_local.get("ts"), datetime):
                    attempt_snapshot["entry_quote_ts"] = entry_quote_local["ts"]
                attempt_snapshot["entry_quote_spread_abs"] = entry_quote_spread_abs_local
                attempt_snapshot["entry_quote_spread_pct"] = entry_quote_spread_pct_local

            fallback_stop_local = _apply_option_premium_stop(
                entry_price_raw=entry_raw_local,
                option_take_profit_pct=option_take_profit_pct_local,
                option_max_loss_pct=option_max_loss_pct_local,
                entry_bar=entry_bar_local,
                exit_bar=exit_bar_local,
                entry_bars=entry_bars_local,
                exit_bars=exit_bars_local,
                day=day,
                exit_day=exit_day_local,
                default_exit_reason=str(exit_plan.get("exit_reason") or ""),
                default_exit_ts=delayed_exit_ts_local,
            )
            if quote_pricing_enabled_local and entry_quote_ask_local is not None and entry_quote_ask_local > 0:
                default_exit_quotes_local = (
                    entry_quotes_local
                    if exit_day_local == day
                    else self._load_option_quotes(symbol=long_option_symbol_local, day=exit_day_local)
                )
                quote_stop_local = _apply_option_premium_stop_from_quotes(
                    entry_price_raw=float(entry_quote_ask_local),
                    option_take_profit_pct=option_take_profit_pct_local,
                    option_max_loss_pct=option_max_loss_pct_local,
                    entry_fill_ts=entry_quote_local["ts"]
                    if isinstance(entry_quote_local, dict) and isinstance(entry_quote_local.get("ts"), datetime)
                    else delayed_entry_ts_local,
                    default_exit_bar=exit_bar_local,
                    default_exit_reason=str(exit_plan.get("exit_reason") or ""),
                    default_exit_ts=delayed_exit_ts_local,
                    same_day_quotes=entry_quotes_local,
                    exit_day_quotes=default_exit_quotes_local,
                    day=day,
                    exit_day=exit_day_local,
                )
                quote_exit_day_local = _as_et(quote_stop_local["effective_exit_ts"]).date()
                exit_quotes_local = (
                    entry_quotes_local
                    if quote_exit_day_local == day
                    else self._load_option_quotes(symbol=long_option_symbol_local, day=quote_exit_day_local)
                )
                exit_quote_local = self._lookup_option_quote_on_or_after(
                    symbol=long_option_symbol_local,
                    day=quote_exit_day_local,
                    ts=quote_stop_local["effective_exit_ts"],
                    fallback_last=False,
                )
                if exit_quote_local is not None:
                    exit_quote_bid_local = _safe_float(exit_quote_local.get("bid"))
                    exit_quote_ask_local = _safe_float(exit_quote_local.get("ask"))
                exit_quote_ready_local = bool(exit_quote_bid_local is not None and exit_quote_bid_local > 0.0)
                if isinstance(exit_quote_local, dict) and isinstance(exit_quote_local.get("ts"), datetime):
                    attempt_snapshot["exit_quote_ts"] = exit_quote_local["ts"]
                can_use_quote_fill_local = bool(exit_quote_bid_local is not None and exit_quote_bid_local > 0)
                if can_use_quote_fill_local:
                    self._bump_option_funnel("quote_fill_available")
                    entry_raw_local = float(entry_quote_ask_local)
                    exit_bar_local = quote_stop_local["exit_bar"]
                    effective_exit_reason_local = str(quote_stop_local["effective_exit_reason"] or "")
                    effective_exit_ts_local = quote_stop_local["effective_exit_ts"]
                    option_premium_stop_triggered_local = bool(
                        quote_stop_local.get("option_premium_stop_triggered")
                    )
                    option_premium_stop_price_raw_local = quote_stop_local.get("option_premium_stop_price_raw")
                    premium_take_profit_triggered_local = bool(
                        quote_stop_local.get("premium_take_profit_triggered")
                    )
                    premium_stop_triggered_local = bool(quote_stop_local.get("premium_stop_triggered"))
                    exit_raw_local = float(exit_quote_bid_local)
                    if isinstance(entry_quote_local, dict) and isinstance(entry_quote_local.get("ts"), datetime):
                        entry_fill_ts_local = entry_quote_local["ts"]
                    if isinstance(exit_quote_local, dict) and isinstance(exit_quote_local.get("ts"), datetime):
                        exit_fill_ts_local = exit_quote_local["ts"]
                    fill_pricing_source_local = "quotes"
                    if premium_take_profit_triggered_local:
                        fill_pricing_source_local = "quotes_premium_take_profit"
                    if option_premium_stop_triggered_local and option_premium_stop_price_raw_local is not None:
                        fill_pricing_source_local = "quotes_option_premium_stop"
                        exit_raw_local = min(exit_raw_local, float(option_premium_stop_price_raw_local))

            if not can_use_quote_fill_local:
                exit_bar_local = fallback_stop_local["exit_bar"]
                effective_exit_reason_local = str(fallback_stop_local["effective_exit_reason"] or "")
                effective_exit_ts_local = fallback_stop_local["effective_exit_ts"]
                option_premium_stop_triggered_local = bool(
                    fallback_stop_local.get("option_premium_stop_triggered")
                )
                option_premium_stop_price_raw_local = fallback_stop_local.get("option_premium_stop_price_raw")
                premium_take_profit_triggered_local = bool(
                    fallback_stop_local.get("premium_take_profit_triggered")
                )
                premium_stop_triggered_local = bool(fallback_stop_local.get("premium_stop_triggered"))
                entry_raw_local = _causal_bar_fill_price(entry_bar_local)
                exit_raw_local = float(fallback_stop_local["exit_raw"])
                entry_fill_ts_local = entry_bar_local["ts"]
                exit_fill_ts_local = exit_bar_local["ts"]
                if quote_pricing_enabled_local:
                    if quote_fallback_enabled_local:
                        used_quote_fallback_local = True
                        self._bump_option_funnel("quote_fill_fallback_used")
                        fill_pricing_source_local = "bar_open_quote_fallback"
                    else:
                        if not entry_quote_ready_local:
                            self._bump_option_rejection("quote_missing_after_entry_ts")
                        elif not exit_quote_ready_local:
                            self._bump_option_rejection("quote_missing_after_exit_ts")
                        self._bump_option_rejection("quotes_unavailable_without_fallback")
                        return None

            if entry_raw_local <= 0:
                self._bump_option_rejection("entry_price_nonpositive")
                return None
            if (
                isinstance(entry_fill_ts_local, datetime)
                and isinstance(effective_exit_ts_local, datetime)
                and _as_utc_aware(entry_fill_ts_local) >= _as_utc_aware(effective_exit_ts_local)
            ):
                self._bump_option_rejection("entry_after_effective_exit")
                return None
            if (
                isinstance(entry_fill_ts_local, datetime)
                and isinstance(exit_fill_ts_local, datetime)
                and _as_utc_aware(entry_fill_ts_local) >= _as_utc_aware(exit_fill_ts_local)
            ):
                self._bump_option_rejection("entry_after_exit_fill")
                return None
            pricing_resolved = True
            attempt_snapshot.update(
                {
                    "entry_volume": int(entry_volume_local),
                    "option_quote_fallback_used": bool(used_quote_fallback_local),
                }
            )

            structure_passed = True
            gate_mode_local = str(config.option_microstructure_gate_mode or "absolute").strip().lower()
            static_slippage_bps_local = max(float(config.option_slippage_bps), 0.0)
            range_slippage_bps_local = (
                max(float(config.option_range_adverse_fill_fraction), 0.0)
                * max(entry_bar_range_pct_local, 0.0)
                * 10000.0
            )
            max_range_slippage_bps_local = max(float(config.option_range_adverse_fill_max_bps), 0.0)
            if max_range_slippage_bps_local > 0:
                range_slippage_bps_local = min(range_slippage_bps_local, max_range_slippage_bps_local)
            total_slippage_bps_local = static_slippage_bps_local + range_slippage_bps_local
            pre_capacity_slippage_local = total_slippage_bps_local / 10000.0
            entry_price_before_capacity_local = entry_raw_local * (1.0 + pre_capacity_slippage_local)
            risk_notional_local = max(float(current_equity), 0.0) * max(float(config.risk_per_trade), 0.0)
            sizing_mode_local = str(config.option_risk_sizing_mode or "premium_at_risk").strip().lower()
            sizing_loss_fraction_local = (
                max(float(config.option_max_loss_pct), 0.0)
                if sizing_mode_local == "premium_stop" and 0.0 < float(config.option_max_loss_pct) <= 1.0
                else 1.0
            )
            commission_risk_local = (
                max(float(config.option_commission_per_contract), 0.0) * 2.0
                if bool(config.option_sizing_include_commission)
                else 0.0
            )
            per_contract_risk_capital_local = (
                entry_price_before_capacity_local * 100.0 * sizing_loss_fraction_local
            ) + commission_risk_local
            provisional_qty_local = _option_qty_for_risk(
                risk_notional=risk_notional_local,
                entry_price=entry_price_before_capacity_local,
                commission_per_contract=float(config.option_commission_per_contract),
                include_commission=bool(config.option_sizing_include_commission),
                min_entry_price=float(config.option_sizing_min_entry_price),
                sizing_mode=sizing_mode_local,
                option_max_loss_pct=float(config.option_max_loss_pct),
                option_leg_count=1,
            )

            micro_filter_active_local = bool(config.require_option_microstructure_filter) or bool(
                config.option_structure_filter_enabled
            )
            if micro_filter_active_local:
                min_entry_volume_local = 0
                if bool(config.require_option_microstructure_filter):
                    min_entry_volume_local = max(
                        min_entry_volume_local,
                        max(int(config.option_min_entry_volume), 0),
                    )
                if bool(config.option_structure_filter_enabled):
                    min_entry_volume_local = max(
                        min_entry_volume_local,
                        max(int(config.option_structure_min_entry_volume), 0),
                    )
                min_entry_volume_local = _required_option_entry_volume(
                    gate_mode=gate_mode_local,
                    base_min_entry_volume=min_entry_volume_local,
                    provisional_qty=int(provisional_qty_local),
                    max_entry_volume_participation=float(config.option_max_entry_volume_participation),
                )
                if entry_volume_local < min_entry_volume_local:
                    self._last_option_rejection_reason = "micro_entry_volume"
                    if suppress_retryable_micro_failure:
                        return None
                    self._bump_option_funnel("entry_exit_bars_available")
                    self._bump_option_funnel("pricing_resolved")
                    self._bump_option_funnel("structure_filters_passed")
                    self._bump_option_rejection("micro_entry_volume")
                    attempt_snapshot["conversion_terminal_rejection_reason"] = "micro_entry_volume"
                    return None

                max_range_pct_local = 0.0
                if bool(config.require_option_microstructure_filter):
                    max_range_pct_local = max(
                        _setup_override_float(
                            setup,
                            "option_max_entry_bar_range_pct",
                            config.option_max_entry_bar_range_pct,
                        ),
                        0.0,
                    )
                if bool(config.option_structure_filter_enabled):
                    structure_cap_local = max(float(config.option_structure_max_entry_bar_range_pct), 0.0)
                    max_range_pct_local = (
                        structure_cap_local
                        if max_range_pct_local <= 0
                        else min(max_range_pct_local, structure_cap_local)
                    )
                if max_range_pct_local > 0 and entry_bar_range_pct_local > max_range_pct_local:
                    self._last_option_rejection_reason = "micro_entry_range"
                    if suppress_retryable_micro_failure:
                        return None
                    self._bump_option_funnel("entry_exit_bars_available")
                    self._bump_option_funnel("pricing_resolved")
                    self._bump_option_funnel("structure_filters_passed")
                    self._bump_option_rejection("micro_entry_range")
                    attempt_snapshot["conversion_terminal_rejection_reason"] = "micro_entry_range"
                    return None

                min_entry_price_local = 0.0
                if bool(config.require_option_microstructure_filter):
                    min_entry_price_local = max(
                        min_entry_price_local,
                        max(float(config.option_min_entry_price), 0.0),
                    )
                if bool(config.option_structure_filter_enabled):
                    min_entry_price_local = max(
                        min_entry_price_local,
                        max(float(config.option_structure_min_entry_price), 0.0),
                    )
                if entry_raw_local < min_entry_price_local:
                    self._last_option_rejection_reason = "micro_entry_price"
                    if suppress_retryable_micro_failure:
                        return None
                    self._bump_option_funnel("entry_exit_bars_available")
                    self._bump_option_funnel("pricing_resolved")
                    self._bump_option_funnel("structure_filters_passed")
                    self._bump_option_rejection("micro_entry_price")
                    attempt_snapshot["conversion_terminal_rejection_reason"] = "micro_entry_price"
                    return None

                max_spread_pct_local = 0.0
                if bool(config.require_option_microstructure_filter):
                    max_spread_pct_local = max(float(config.option_max_entry_spread_pct), 0.0)
                if bool(config.option_structure_filter_enabled):
                    structure_spread_cap_local = max(
                        float(config.option_structure_max_entry_spread_pct),
                        0.0,
                    )
                    max_spread_pct_local = (
                        structure_spread_cap_local
                        if max_spread_pct_local <= 0
                        else min(max_spread_pct_local, structure_spread_cap_local)
                    )
                if max_spread_pct_local > 0 and can_use_quote_fill_local:
                    if (
                        entry_quote_spread_pct_local is None
                        or entry_quote_spread_pct_local > max_spread_pct_local
                    ):
                        self._last_option_rejection_reason = "micro_quote_spread"
                        if suppress_retryable_micro_failure:
                            return None
                        self._bump_option_funnel("entry_exit_bars_available")
                        self._bump_option_funnel("pricing_resolved")
                        self._bump_option_funnel("structure_filters_passed")
                        self._bump_option_rejection("micro_quote_spread")
                        attempt_snapshot["conversion_terminal_rejection_reason"] = "micro_quote_spread"
                        return None
            self._bump_option_funnel("entry_exit_bars_available")
            self._bump_option_funnel("pricing_resolved")
            self._bump_option_funnel("structure_filters_passed")
            self._bump_option_funnel("microstructure_filters_passed")

            expected_move_local = _expected_underlying_target_move(
                setup=setup,
                take_profit_rr=float(config.take_profit_rr),
            )
            if expected_move_local is not None:
                if can_use_quote_fill_local and entry_quote_ask_local is not None and entry_quote_ask_local > 0:
                    option_type_local = "call" if int(setup.get("direction") or 0) > 0 else "put"
                    intrinsic_value_local = _option_intrinsic_value(
                        option_type=option_type_local,
                        underlying_price=float(setup.get("entry_underlying") or 0.0),
                        strike=float(long_contract_local.get("strike_price") or 0.0),
                    )
                    extrinsic_value_local = max(float(entry_quote_ask_local) - intrinsic_value_local, 0.0)
                    min_move_to_extrinsic_local = max(
                        float(config.option_min_expected_move_to_extrinsic_ratio),
                        0.0,
                    )
                    min_move_to_spread_local = max(float(config.option_min_expected_move_to_spread_ratio), 0.0)
                    if min_move_to_extrinsic_local > 0.0:
                        if extrinsic_value_local <= 0.0:
                            move_to_extrinsic_ratio_local = float("inf")
                        else:
                            move_to_extrinsic_ratio_local = float(expected_move_local) / float(
                                extrinsic_value_local
                            )
                        expected_move_to_extrinsic_ratio_local = move_to_extrinsic_ratio_local
                        if move_to_extrinsic_ratio_local < min_move_to_extrinsic_local:
                            self._bump_option_rejection("move_to_cost_extrinsic_ratio")
                            return None
                    if min_move_to_spread_local > 0.0:
                        if entry_quote_spread_abs_local is None or entry_quote_spread_abs_local <= 0.0:
                            self._bump_option_rejection("move_to_cost_spread_ratio")
                            return None
                        move_to_spread_ratio_local = float(expected_move_local) / float(
                            entry_quote_spread_abs_local
                        )
                        expected_move_to_spread_ratio_local = move_to_spread_ratio_local
                        if move_to_spread_ratio_local < min_move_to_spread_local:
                            self._bump_option_rejection("move_to_cost_spread_ratio")
                            return None
                min_move_to_debit_local = max(float(config.option_min_expected_move_to_debit_ratio), 0.0)
                if min_move_to_debit_local > 0.0:
                    if entry_raw_local <= 0.0:
                        self._bump_option_rejection("move_to_cost_debit_ratio")
                        return None
                    expected_move_to_debit_ratio_local = float(expected_move_local) / float(entry_raw_local)
                    if expected_move_to_debit_ratio_local < min_move_to_debit_local:
                        self._bump_option_rejection("move_to_cost_debit_ratio")
                        return None
            self._bump_option_funnel("move_cost_filters_passed")

            entry_price_local = entry_raw_local * (1.0 + pre_capacity_slippage_local)
            exit_price_local = max(0.0, exit_raw_local * (1.0 - pre_capacity_slippage_local))
            contract_open_interest_local = int(long_contract_local.get("open_interest") or 0)
            qty_before_liquidity_caps_local = _option_qty_for_risk(
                risk_notional=risk_notional_local,
                entry_price=entry_price_local,
                commission_per_contract=float(config.option_commission_per_contract),
                include_commission=bool(config.option_sizing_include_commission),
                min_entry_price=float(config.option_sizing_min_entry_price),
                sizing_mode=sizing_mode_local,
                option_max_loss_pct=float(config.option_max_loss_pct),
                option_leg_count=1,
            )
            qty_local = qty_before_liquidity_caps_local
            volume_cap_qty_local = qty_local
            oi_cap_qty_local = qty_local
            if bool(config.enforce_option_liquidity_caps):
                if entry_volume_local > 0 and float(config.option_max_entry_volume_participation) > 0.0:
                    volume_cap_qty_local = int(
                        floor(float(entry_volume_local) * float(config.option_max_entry_volume_participation))
                    )
                    qty_local = min(qty_local, volume_cap_qty_local)
                if contract_open_interest_local > 0 and float(config.option_max_open_interest_participation) > 0.0:
                    oi_cap_qty_local = int(
                        floor(
                            float(contract_open_interest_local)
                            * float(config.option_max_open_interest_participation)
                        )
                    )
                    qty_local = min(qty_local, oi_cap_qty_local)
            if qty_local < 1:
                self._bump_option_rejection("qty_below_1_after_caps")
                return None
            self._bump_option_funnel("sizing_passed")
            volume_participation_local = (
                float(qty_local) / float(entry_volume_local) if entry_volume_local > 0 else 0.0
            )
            oi_participation_local = (
                float(qty_local) / float(contract_open_interest_local)
                if contract_open_interest_local > 0
                else 0.0
            )
            gross_pnl_local = qty_local * (exit_price_local - entry_price_local) * 100.0
            commission_local = qty_local * max(float(config.option_commission_per_contract), 0.0) * 2.0
            pnl_local = gross_pnl_local - commission_local
            invested_local = qty_local * entry_price_local * 100.0
            trade_return_local = (pnl_local / invested_local) if invested_local > 0 else 0.0
            self._bump_option_funnel("entry_constructed")
            self._bump_option_funnel("trades_created")

            return BacktestTrade(
                trade_id=str(uuid.uuid4()),
                signal_id=str(uuid.uuid4()),
                ticker=ticker,
                option_symbol=trade_option_symbol_local,
                entry_ts=entry_fill_ts_local,
                exit_ts=exit_fill_ts_local,
                side="long_call" if direction > 0 else "long_put",
                qty=qty_local,
                entry_price=entry_price_local,
                exit_price=exit_price_local,
                pnl=pnl_local,
                return_pct=trade_return_local,
                status="closed",
                metadata={
                    "strategy": "intraday_opening_range_stocks_in_play_options",
                    "strategy_variant": str(setup.get("strategy_variant") or config.strategy_variant),
                    "execution_mode": "historical_options",
                    "direction": direction,
                    "entry_underlying": float(setup["entry_underlying"]),
                    "exit_underlying": float(exit_plan["exit_underlying"]),
                    "stop_underlying": float(setup["stop_underlying"]),
                    "exit_reason": effective_exit_reason_local,
                    "exit_reason_base": str(exit_plan["exit_reason"]),
                    "orb_high": float(setup["orb_high"]),
                    "orb_low": float(setup["orb_low"]),
                    "opening_range_minutes": int(setup.get("opening_range_minutes") or 0),
                    "opening_bar_direction": int(setup.get("opening_bar_direction") or 0),
                    "trend_ema_fast": float(setup["trend_ema_fast"]),
                    "trend_ema_slow": float(setup["trend_ema_slow"]),
                    "volume_ratio": float(setup["volume_ratio"]),
                    "relative_opening_volume": _safe_float(setup.get("relative_opening_volume")),
                    "gap_return": _safe_float(setup.get("gap_return")),
                    "atr_value": _safe_float(setup.get("atr_value")),
                    "vol_regime_prev_close": _safe_float(setup.get("vol_regime_prev_close")),
                    "market_regime_label": _normalize_regime_label(setup.get("market_regime_label")),
                    "regime_v2_state": str(setup.get("regime_v2_state") or "unknown"),
                    "regime_v2_route_state": str(setup.get("regime_v2_route_state") or "unknown"),
                    "regime_v2_route_action": str(setup.get("regime_v2_route_action") or ""),
                    "regime_v2_confidence": _safe_float(setup.get("regime_v2_confidence")),
                    "regime_v2_selected_variant": str(setup.get("regime_v2_selected_variant") or ""),
                    "regime_v2_skip_reason": str(setup.get("regime_v2_skip_reason") or ""),
                    "regime_v2_route_overlay_name": str(setup.get("regime_v2_route_overlay_name") or ""),
                    "fvg_gap": float(setup["fvg_gap"]),
                    "fib_anchor": _safe_float(setup.get("fib_anchor")),
                    "fib_impulse_extreme": _safe_float(setup.get("fib_impulse_extreme")),
                    "fib_entry_zone_low": _safe_float(setup.get("fib_entry_zone_low")),
                    "fib_entry_zone_high": _safe_float(setup.get("fib_entry_zone_high")),
                    "fill_pricing_source": fill_pricing_source_local,
                    "option_structure_mode": structure_mode,
                    "option_leg_count": 1,
                    "long_leg_symbol": long_option_symbol_local,
                    "short_leg_symbol": None,
                    "long_leg_strike": float(long_strike_local),
                    "short_leg_strike": None,
                    "spread_width": None,
                    "entry_debit": None,
                    "exit_credit": None,
                    "entry_credit": None,
                    "exit_debit": None,
                    "entry_combined_spread_abs": None,
                    "entry_combined_spread_to_debit_ratio": None,
                    "entry_combined_spread_to_credit_ratio": None,
                    "credit_to_width_ratio": None,
                    "short_strike_buffer_pct": None,
                    "expected_move_to_debit_ratio": expected_move_to_debit_ratio_local,
                    "short_leg_bid_at_entry": None,
                    "short_leg_ask_at_exit": None,
                    "long_leg_ask_at_entry": None,
                    "long_leg_bid_at_exit": None,
                    "option_quote_pricing_enabled": bool(config.use_option_quotes_for_fills),
                    "option_quote_fill_fallback_enabled": quote_fallback_enabled_local,
                    "option_quote_fallback_used": used_quote_fallback_local,
                    "entry_quote_ts": (
                        entry_quote_local["ts"].isoformat()
                        if isinstance(entry_quote_local, dict) and isinstance(entry_quote_local.get("ts"), datetime)
                        else None
                    ),
                    "entry_quote_bid": entry_quote_bid_local,
                    "entry_quote_ask": entry_quote_ask_local,
                    "entry_quote_mid": entry_quote_mid_local,
                    "entry_quote_spread_abs": entry_quote_spread_abs_local,
                    "entry_quote_spread_pct": entry_quote_spread_pct_local,
                    "exit_quote_ts": (
                        exit_quote_local["ts"].isoformat()
                        if isinstance(exit_quote_local, dict) and isinstance(exit_quote_local.get("ts"), datetime)
                        else None
                    ),
                    "exit_quote_bid": exit_quote_bid_local,
                    "exit_quote_ask": exit_quote_ask_local,
                    "short_entry_quote_ts": None,
                    "short_exit_quote_ts": None,
                    "short_entry_quote_bid": None,
                    "short_entry_quote_ask": None,
                    "short_exit_quote_bid": None,
                    "short_exit_quote_ask": None,
                    "entry_price_raw": entry_raw_local,
                    "entry_volume": entry_volume_local,
                    "entry_volume_long_leg": int(entry_bar_local.get("volume") or 0),
                    "entry_volume_short_leg": 0,
                    "entry_bar_range_pct": entry_bar_range_pct_local,
                    "exit_price_raw": exit_raw_local,
                    "entry_price_effective": entry_price_local,
                    "exit_price_effective": exit_price_local,
                    "option_take_profit_pct": option_take_profit_pct_local,
                    "option_max_loss_pct": option_max_loss_pct_local,
                    "option_premium_stop_triggered": option_premium_stop_triggered_local,
                    "option_premium_stop_price_raw": option_premium_stop_price_raw_local,
                    "premium_take_profit_triggered": premium_take_profit_triggered_local,
                    "premium_stop_triggered": premium_stop_triggered_local,
                    "option_slippage_bps": total_slippage_bps_local,
                    "option_slippage_static_bps": static_slippage_bps_local,
                    "option_slippage_range_bps": range_slippage_bps_local,
                    "option_commission_total": commission_local,
                    "execution_entry_delay_base_minutes": entry_delay_base_local,
                    "execution_exit_delay_base_minutes": exit_delay_base_local,
                    "execution_entry_delay_minutes": entry_delay_local,
                    "execution_exit_delay_minutes": exit_delay_local,
                    "execution_delay_randomization": randomization_enabled_local,
                    "execution_entry_delay_jitter_minutes": int(config.execution_entry_delay_jitter_minutes),
                    "execution_exit_delay_jitter_minutes": int(config.execution_exit_delay_jitter_minutes),
                    "execution_delay_random_seed": int(config.execution_delay_random_seed),
                    "execution_timing_model": str(config.execution_timing_model or "bar_open"),
                    "execution_poll_seconds": int(config.execution_poll_seconds),
                    "execution_entry_signal_confirm_seconds": int(config.execution_entry_signal_confirm_seconds),
                    "execution_exit_signal_confirm_seconds": int(config.execution_exit_signal_confirm_seconds),
                    "execution_entry_fill_latency_seconds": int(config.execution_entry_fill_latency_seconds),
                    "execution_exit_fill_latency_seconds": int(config.execution_exit_fill_latency_seconds),
                    "delayed_entry_signal_ts": delayed_entry_ts_local.isoformat(),
                    "delayed_exit_signal_ts": delayed_exit_ts_local.isoformat(),
                    "entry_fill_ts": entry_fill_ts_local.isoformat()
                    if isinstance(entry_fill_ts_local, datetime)
                    else str(entry_fill_ts_local),
                    "exit_fill_ts": exit_fill_ts_local.isoformat()
                    if isinstance(exit_fill_ts_local, datetime)
                    else str(exit_fill_ts_local),
                    "effective_exit_signal_ts": effective_exit_ts_local.isoformat()
                    if isinstance(effective_exit_ts_local, datetime)
                    else str(effective_exit_ts_local),
                    "gross_pnl": gross_pnl_local,
                    "contract_expiration": long_contract_local.get("expiration_date"),
                    "contract_strike": float(long_contract_local.get("strike_price") or 0.0),
                    "contract_status": long_contract_local.get("status"),
                    "contract_open_interest": contract_open_interest_local,
                    "contract_open_interest_long_leg": contract_open_interest_local,
                    "contract_open_interest_short_leg": None,
                    "contract_volume_snapshot": int(long_contract_local.get("volume") or 0),
                    "contract_volume_snapshot_short_leg": None,
                    "option_structure_filter_enabled": bool(config.option_structure_filter_enabled),
                    "option_structure_min_open_interest": int(config.option_structure_min_open_interest),
                    "option_structure_min_entry_volume": int(config.option_structure_min_entry_volume),
                    "option_structure_max_entry_spread_pct": float(config.option_structure_max_entry_spread_pct),
                    "option_structure_max_entry_bar_range_pct": float(
                        config.option_structure_max_entry_bar_range_pct
                    ),
                    "option_structure_min_entry_price": float(config.option_structure_min_entry_price),
                    "option_vertical_short_leg_steps": int(config.option_vertical_short_leg_steps),
                    "option_vertical_fallback_short_leg_steps": int(
                        config.option_vertical_fallback_short_leg_steps
                    ),
                    "option_vertical_max_debit_to_width_ratio": float(
                        config.option_vertical_max_debit_to_width_ratio
                    ),
                    "option_vertical_min_short_bid": float(config.option_vertical_min_short_bid),
                    "option_vertical_max_combined_spread_to_debit_ratio": float(
                        config.option_vertical_max_combined_spread_to_debit_ratio
                    ),
                    "option_vertical_credit_long_leg_steps": int(
                        config.option_vertical_credit_long_leg_steps
                    ),
                    "option_vertical_credit_fallback_long_leg_steps": int(
                        config.option_vertical_credit_fallback_long_leg_steps
                    ),
                    "option_vertical_min_credit_to_width_ratio": float(
                        config.option_vertical_min_credit_to_width_ratio
                    ),
                    "option_vertical_max_credit_to_width_ratio": float(
                        config.option_vertical_max_credit_to_width_ratio
                    ),
                    "option_vertical_max_combined_spread_to_credit_ratio": float(
                        config.option_vertical_max_combined_spread_to_credit_ratio
                    ),
                    "option_credit_min_short_bid": float(config.option_credit_min_short_bid),
                    "option_credit_min_short_strike_buffer_pct": float(
                        config.option_credit_min_short_strike_buffer_pct
                    ),
                    "option_credit_min_expected_move_buffer_ratio": float(
                        config.option_credit_min_expected_move_buffer_ratio
                    ),
                    "option_credit_min_entry_credit": float(config.option_credit_min_entry_credit),
                    "option_credit_take_profit_capture_pct": float(
                        config.option_credit_take_profit_capture_pct
                    ),
                    "option_credit_stop_loss_multiple": float(config.option_credit_stop_loss_multiple),
                    "option_min_expected_move_to_debit_ratio": float(
                        config.option_min_expected_move_to_debit_ratio
                    ),
                    "liquidity_caps_enabled": bool(config.enforce_option_liquidity_caps),
                    "option_sizing_include_commission": bool(config.option_sizing_include_commission),
                    "option_sizing_min_entry_price": float(config.option_sizing_min_entry_price),
                    "option_risk_sizing_mode": sizing_mode_local,
                    "option_risk_sizing_loss_fraction": float(sizing_loss_fraction_local),
                    "per_contract_risk_capital": float(per_contract_risk_capital_local),
                    "option_max_entry_volume_participation": float(
                        config.option_max_entry_volume_participation
                    ),
                    "option_max_open_interest_participation": float(
                        config.option_max_open_interest_participation
                    ),
                    "option_use_contract_open_interest": bool(config.option_use_contract_open_interest),
                    "open_interest_liquidity_cap_enabled": bool(
                        config.enforce_option_liquidity_caps
                        and float(config.option_max_open_interest_participation) > 0.0
                    ),
                    "open_interest_data_available": bool(contract_open_interest_local > 0),
                    "open_interest_cap_applied": bool(
                        config.enforce_option_liquidity_caps
                        and float(config.option_max_open_interest_participation) > 0.0
                        and contract_open_interest_local > 0
                    ),
                    "qty_before_liquidity_caps": int(qty_before_liquidity_caps_local),
                    "qty_after_liquidity_caps": int(qty_local),
                    "entry_volume_participation": volume_participation_local,
                    "open_interest_participation": oi_participation_local,
                    "volume_cap_qty": int(volume_cap_qty_local),
                    "open_interest_cap_qty": int(oi_cap_qty_local),
                    "contract_selection_dte": int(long_contract_local.get("_selection_dte") or 0),
                    "contract_selection_moneyness": _safe_float(long_contract_local.get("_selection_moneyness")),
                    "contract_selection_oi_bonus": _safe_float(long_contract_local.get("_selection_oi_bonus")),
                    "contract_selection_score": _safe_float(long_contract_local.get("_selection_score")),
                    "contract_selection_requested_status": str(
                        long_contract_local.get("_selection_requested_status") or ""
                    ),
                    "selected_abs_delta": _safe_float(long_contract_local.get("_selection_abs_delta")),
                    "selected_strike_distance_steps": (
                        int(long_contract_local.get("_selection_strike_distance_steps") or 0)
                        if long_contract_local.get("_selection_strike_distance_steps") not in (None, "")
                        else None
                    ),
                    "selected_entry_bar_volume": (
                        int(long_contract_local.get("_selection_entry_bar_volume") or 0)
                        if long_contract_local.get("_selection_entry_bar_volume") not in (None, "")
                        else None
                    ),
                    "selected_quote_spread_pct": _safe_float(
                        long_contract_local.get("_selection_quote_spread_pct")
                    ),
                    "contract_selection_intrinsic_value": _safe_float(
                        long_contract_local.get("_selection_intrinsic_value")
                    ),
                    "contract_selection_intrinsic_share": _safe_float(
                        long_contract_local.get("_selection_intrinsic_share")
                    ),
                    "contract_selection_extrinsic_value": _safe_float(
                        long_contract_local.get("_selection_extrinsic_value")
                    ),
                    "expected_move_to_extrinsic_ratio": expected_move_to_extrinsic_ratio_local,
                    "expected_move_to_spread_ratio": expected_move_to_spread_ratio_local,
                    "initial_selected_option_symbol": initial_selected_option_symbol or None,
                    "final_selected_option_symbol": long_option_symbol_local,
                    "initial_selected_expiration_date": initial_selected_expiration_date,
                    "final_selected_expiration_date": (
                        _selection_contract_expiration_date_text(long_contract_local)
                        or initial_selected_expiration_date
                    ),
                    "conversion_changed_expiry": bool(
                        initial_selected_expiration_date
                        and _selection_contract_expiration_date_text(long_contract_local)
                        and initial_selected_expiration_date
                        != _selection_contract_expiration_date_text(long_contract_local)
                    ),
                    "initial_contract_rank": int(initial_contract_rank),
                    "final_contract_rank": int(final_contract_rank),
                    "initial_selected_strike_distance_steps": initial_selected_strike_distance_steps,
                    "final_selected_strike_distance_steps": _selection_contract_strike_distance_steps(
                        long_contract_local
                    ),
                    "initial_selected_entry_bar_volume": initial_selected_entry_bar_volume,
                    "final_selected_entry_bar_volume": _selection_contract_entry_bar_volume(long_contract_local),
                    "initial_selected_quote_spread_pct": initial_selected_quote_spread_pct,
                    "final_selected_quote_spread_pct": _selection_contract_quote_spread_pct(long_contract_local),
                    "conversion_applied": bool(conversion_attempt_count > 0),
                    "conversion_attempt_count": int(conversion_attempt_count),
                    "conversion_terminal_rejection_reason": "",
                },
            )

        if not is_vertical_pair and conversion_mode != "disabled":
            retry_pool = _build_post_selection_contract_attempt_pool(
                ranked_contract_pool=ranked_contract_pool,
                selected_contract=selected_contract,
                conversion_mode=conversion_mode,
                max_alternates=max_conversion_alternates,
                max_final_rank=max_conversion_final_rank,
                max_final_strike_distance_steps=max_conversion_final_strike_distance_steps,
            )
            if not retry_pool:
                retry_pool = [dict(selected_contract)]
            for attempt_idx, retry_contract in enumerate(retry_pool):
                trade = _simulate_single_leg_candidate_with_optional_conversion(
                    dict(retry_contract),
                    conversion_attempt_count=int(attempt_idx),
                    suppress_retryable_micro_failure=bool(attempt_idx < len(retry_pool) - 1),
                )
                if trade is not None:
                    return _finalize_attempt(trade)
                current_reason = str(self._last_option_rejection_reason or "")
                if current_reason in _POST_SELECTION_RETRYABLE_MICRO_REJECTIONS and attempt_idx < len(retry_pool) - 1:
                    continue
                return _finalize_attempt(None)

        long_contract: Optional[Dict[str, Any]] = None
        short_contract: Optional[Dict[str, Any]] = None
        short_option_symbol = ""
        long_option_symbol = ""
        short_strike = 0.0
        long_strike = 0.0
        spread_width: Optional[float] = None
        option_leg_count = 1
        if is_vertical_credit:
            short_contract = dict(selected_contract)
            short_contract = self._maybe_fill_contract_open_interest(
                ticker=ticker,
                day=day,
                contract=short_contract,
                enrichment_mode=enrichment_mode,
            )
            short_option_symbol = str(short_contract.get("symbol") or "").strip()
            if not short_option_symbol:
                self._bump_option_rejection("contract_symbol_missing")
                return _finalize_attempt(None)
            attempt_snapshot["short_leg_symbol"] = short_option_symbol
            short_strike = _safe_float(short_contract.get("strike_price")) or 0.0
            long_contract = self._select_vertical_credit_long_leg(
                ticker=ticker,
                day=day,
                direction=direction,
                short_contract=short_contract,
                config=config,
                selection_ts=setup.get("entry_ts") if isinstance(setup.get("entry_ts"), datetime) else None,
            )
            if long_contract is None:
                return _finalize_attempt(None)
            long_contract = self._maybe_fill_contract_open_interest(
                ticker=ticker,
                day=day,
                contract=dict(long_contract),
                enrichment_mode=enrichment_mode,
            )
            long_option_symbol = str(long_contract.get("symbol") or "").strip()
            if not long_option_symbol:
                self._bump_option_rejection("vertical_credit_long_leg_missing")
                return _finalize_attempt(None)
            attempt_snapshot["long_leg_symbol"] = long_option_symbol
            long_strike = _safe_float(long_contract.get("strike_price")) or 0.0
            spread_width = abs(float(short_strike) - float(long_strike))
            if spread_width <= 0.0:
                self._bump_option_rejection("vertical_credit_long_leg_missing")
                return _finalize_attempt(None)
            option_leg_count = 2
        else:
            long_contract = dict(selected_contract)
            long_contract = self._maybe_fill_contract_open_interest(
                ticker=ticker,
                day=day,
                contract=long_contract,
                enrichment_mode=enrichment_mode,
            )
            long_option_symbol = str(long_contract.get("symbol") or "").strip()
            if not long_option_symbol:
                self._bump_option_rejection("contract_symbol_missing")
                return _finalize_attempt(None)
            attempt_snapshot["long_leg_symbol"] = long_option_symbol
            long_strike = _safe_float(long_contract.get("strike_price")) or 0.0
        if is_vertical_debit:
            short_contract = self._select_vertical_short_leg(
                ticker=ticker,
                day=day,
                direction=direction,
                long_contract=long_contract or {},
                config=config,
                selection_ts=setup.get("entry_ts") if isinstance(setup.get("entry_ts"), datetime) else None,
            )
            if short_contract is None:
                return _finalize_attempt(None)
            short_contract = self._maybe_fill_contract_open_interest(
                ticker=ticker,
                day=day,
                contract=dict(short_contract),
                enrichment_mode=enrichment_mode,
            )
            short_option_symbol = str(short_contract.get("symbol") or "").strip()
            if not short_option_symbol:
                self._bump_option_rejection("vertical_short_leg_missing")
                return _finalize_attempt(None)
            attempt_snapshot["short_leg_symbol"] = short_option_symbol
            short_strike = _safe_float(short_contract.get("strike_price")) or 0.0
            spread_width = abs(float(short_strike) - float(long_strike))
            if spread_width <= 0.0:
                self._bump_option_rejection("vertical_short_leg_missing")
                return _finalize_attempt(None)
            option_leg_count = 2
        trade_option_symbol = (
            long_option_symbol
            if not is_vertical_pair
            else f"VERTICAL:{long_option_symbol}|{short_option_symbol}"
        )
        if isinstance(long_contract, dict):
            attempt_snapshot.update(
                {
                    "contract_selection_dte": (
                        int(long_contract.get("_selection_dte") or 0)
                        if long_contract.get("_selection_dte") not in (None, "")
                        else attempt_snapshot.get("contract_selection_dte")
                    ),
                    "contract_strike": (
                        _safe_float(long_contract.get("strike_price"))
                        if _safe_float(long_contract.get("strike_price")) is not None
                        else attempt_snapshot.get("contract_strike")
                    ),
                    "contract_open_interest": (
                        int(long_contract.get("open_interest") or 0)
                        if long_contract.get("open_interest") not in (None, "")
                        else attempt_snapshot.get("contract_open_interest")
                    ),
                }
            )
            if attempt_snapshot.get("contract_open_interest") is not None:
                attempt_snapshot["open_interest_data_available"] = bool(
                    int(attempt_snapshot["contract_open_interest"] or 0) > 0
                )

        exit_day_raw = exit_plan.get("exit_day")
        exit_day = exit_day_raw if isinstance(exit_day_raw, date) else day
        primary_option_symbol = short_option_symbol if is_vertical_credit else long_option_symbol
        entry_bars = self._load_option_bars(symbol=primary_option_symbol, day=day)
        if not entry_bars:
            self._bump_option_rejection("option_bars_missing")
            return _finalize_attempt(None)
        if exit_day == day:
            exit_bars = entry_bars
        else:
            exit_bars = self._load_option_bars(symbol=primary_option_symbol, day=exit_day)
            if not exit_bars:
                self._bump_option_rejection("option_bars_missing")
                return _finalize_attempt(None)
        secondary_entry_bars: Optional[List[Dict[str, Any]]] = None
        secondary_exit_bars: Optional[List[Dict[str, Any]]] = None
        if is_vertical_pair:
            secondary_symbol = short_option_symbol if is_vertical_debit else long_option_symbol
            secondary_entry_bars = self._load_option_bars(symbol=secondary_symbol, day=day)
            if exit_day == day:
                secondary_exit_bars = secondary_entry_bars
            elif secondary_entry_bars:
                secondary_exit_bars = self._load_option_bars(symbol=secondary_symbol, day=exit_day)

        entry_delay_base = max(int(config.execution_entry_delay_minutes), 0)
        exit_delay_base = max(int(config.execution_exit_delay_minutes), 0)
        randomization_enabled = bool(config.execution_delay_randomization)
        entry_delay = _jittered_delay_minutes(
            base_delay_minutes=entry_delay_base,
            jitter_minutes=max(int(config.execution_entry_delay_jitter_minutes), 0),
            randomization_enabled=randomization_enabled,
            random_seed=int(config.execution_delay_random_seed),
            seed_key=(
                f"{ticker}|{day.isoformat()}|{trade_option_symbol}|entry|"
                f"{setup['entry_ts'].isoformat() if isinstance(setup.get('entry_ts'), datetime) else setup.get('entry_ts')}"
            ),
        )
        exit_delay = _jittered_delay_minutes(
            base_delay_minutes=exit_delay_base,
            jitter_minutes=max(int(config.execution_exit_delay_jitter_minutes), 0),
            randomization_enabled=randomization_enabled,
            random_seed=int(config.execution_delay_random_seed),
            seed_key=(
                f"{ticker}|{day.isoformat()}|{trade_option_symbol}|exit|"
                f"{exit_plan['exit_ts'].isoformat() if isinstance(exit_plan.get('exit_ts'), datetime) else exit_plan.get('exit_ts')}"
            ),
        )
        delayed_entry_ts = setup["entry_ts"] + timedelta(minutes=entry_delay)
        delayed_exit_ts = exit_plan["exit_ts"] + timedelta(minutes=exit_delay)
        delayed_entry_ts = _apply_execution_timing_model(
            delayed_entry_ts,
            model=str(config.execution_timing_model or "bar_open"),
            poll_seconds=int(config.execution_poll_seconds),
            signal_confirm_seconds=int(config.execution_entry_signal_confirm_seconds),
            fill_latency_seconds=int(config.execution_entry_fill_latency_seconds),
        )
        delayed_exit_ts = _apply_execution_timing_model(
            delayed_exit_ts,
            model=str(config.execution_timing_model or "bar_open"),
            poll_seconds=int(config.execution_poll_seconds),
            signal_confirm_seconds=int(config.execution_exit_signal_confirm_seconds),
            fill_latency_seconds=int(config.execution_exit_fill_latency_seconds),
        )
        attempt_snapshot["delayed_entry_signal_ts"] = delayed_entry_ts
        attempt_snapshot["effective_exit_signal_ts"] = delayed_exit_ts

        entry_bar = _first_bar_on_or_after(entry_bars, delayed_entry_ts)
        exit_bar = _first_bar_on_or_after(exit_bars, delayed_exit_ts)
        if entry_bar is None or exit_bar is None:
            self._bump_option_rejection("entry_or_exit_bar_missing")
            return _finalize_attempt(None)

        entry_bar_close = float(entry_bar.get("close") or 0.0)
        entry_fill_ts = entry_bar["ts"]
        entry_raw = _causal_bar_fill_price(entry_bar)
        exit_fill_ts = exit_bar["ts"]
        exit_raw = _causal_bar_fill_price(exit_bar)
        effective_exit_reason = str(exit_plan.get("exit_reason") or "")
        effective_exit_ts = delayed_exit_ts
        option_premium_stop_triggered = False
        option_premium_stop_price_raw: Optional[float] = None
        entry_volume = int(entry_bar.get("volume") or 0)
        entry_high = float(entry_bar.get("high") or 0.0)
        entry_low = float(entry_bar.get("low") or 0.0)
        entry_bar_range_pct = ((entry_high - entry_low) / entry_bar_close) if entry_bar_close > 0 else 0.0
        short_entry_volume = 0
        short_entry_bar_range_pct = 0.0

        quote_pricing_enabled = bool(config.use_option_quotes_for_fills)
        quote_fallback_enabled = bool(config.option_quote_fill_fallback_to_bar_close)
        fill_pricing_source = "bar_open"
        used_quote_fallback = False
        can_use_quote_fill = False

        entry_quote: Optional[Dict[str, Any]] = None
        exit_quote: Optional[Dict[str, Any]] = None
        entry_quote_bid: Optional[float] = None
        entry_quote_ask: Optional[float] = None
        entry_quote_mid: Optional[float] = None
        entry_quote_spread_abs: Optional[float] = None
        entry_quote_spread_pct: Optional[float] = None
        exit_quote_bid: Optional[float] = None
        exit_quote_ask: Optional[float] = None
        short_entry_quote: Optional[Dict[str, Any]] = None
        short_exit_quote: Optional[Dict[str, Any]] = None
        short_entry_quote_bid: Optional[float] = None
        short_entry_quote_ask: Optional[float] = None
        short_exit_quote_bid: Optional[float] = None
        short_exit_quote_ask: Optional[float] = None
        entry_combined_spread_abs: Optional[float] = None
        entry_combined_spread_to_debit_ratio: Optional[float] = None
        entry_combined_spread_to_credit_ratio: Optional[float] = None
        expected_move_to_extrinsic_ratio: Optional[float] = None
        expected_move_to_spread_ratio: Optional[float] = None
        expected_move_to_debit_ratio: Optional[float] = None
        short_strike_buffer_pct: Optional[float] = None
        credit_to_width_ratio: Optional[float] = None
        premium_take_profit_triggered = False
        premium_stop_triggered = False
        option_take_profit_pct = max(float(config.option_take_profit_pct), 0.0)
        option_max_loss_pct = max(float(config.option_max_loss_pct), 0.0)
        short_contract_open_interest = int(short_contract.get("open_interest") or 0) if isinstance(short_contract, dict) else 0
        secondary_entry_bar: Optional[Dict[str, Any]] = None
        secondary_exit_bar: Optional[Dict[str, Any]] = None
        if is_vertical_pair and secondary_entry_bars and secondary_exit_bars:
            secondary_entry_bar = _first_bar_on_or_after(secondary_entry_bars, delayed_entry_ts)
            secondary_exit_bar = _first_bar_on_or_after(secondary_exit_bars, delayed_exit_ts)
            if secondary_entry_bar is None or secondary_exit_bar is None:
                self._bump_option_rejection("entry_or_exit_bar_missing")
                return _finalize_attempt(None)
            short_entry_volume = int(secondary_entry_bar.get("volume") or 0)
            short_entry_high = float(secondary_entry_bar.get("high") or 0.0)
            short_entry_low = float(secondary_entry_bar.get("low") or 0.0)
            short_entry_close = float(secondary_entry_bar.get("close") or 0.0)
            short_entry_bar_range_pct = (
                (short_entry_high - short_entry_low) / short_entry_close
                if short_entry_close > 0.0
                else 0.0
            )
        self._bump_option_funnel("entry_exit_bars_available")
        attempt_snapshot["entry_volume"] = int(entry_volume)
        entry_quote_ready = False
        exit_quote_ready = False

        if quote_pricing_enabled:
            entry_quotes = self._load_option_quotes(symbol=primary_option_symbol, day=day)
            entry_quote = self._lookup_option_quote_on_or_after(
                symbol=primary_option_symbol,
                day=day,
                ts=delayed_entry_ts,
            )
            if entry_quote is not None:
                entry_quote_bid = _safe_float(entry_quote.get("bid"))
                entry_quote_ask = _safe_float(entry_quote.get("ask"))
                if entry_quote_bid is not None and entry_quote_bid > 0 and entry_quote_ask is not None and entry_quote_ask > 0:
                    entry_quote_mid = (entry_quote_bid + entry_quote_ask) / 2.0
                    entry_quote_spread_abs = max(entry_quote_ask - entry_quote_bid, 0.0)
                    if entry_quote_mid > 0:
                        entry_quote_spread_pct = entry_quote_spread_abs / entry_quote_mid
            if is_vertical_pair:
                secondary_symbol = short_option_symbol if is_vertical_debit else long_option_symbol
                short_entry_quotes = self._load_option_quotes(symbol=secondary_symbol, day=day)
                short_entry_quote = self._lookup_option_quote_on_or_after(
                    symbol=secondary_symbol,
                    day=day,
                    ts=delayed_entry_ts,
                )
                if short_entry_quote is not None:
                    short_entry_quote_bid = _safe_float(short_entry_quote.get("bid"))
                    short_entry_quote_ask = _safe_float(short_entry_quote.get("ask"))
            if is_vertical_debit:
                entry_quote_ready = bool(
                    entry_quote_ask is not None
                    and entry_quote_ask > 0.0
                    and short_entry_quote_bid is not None
                    and short_entry_quote_bid > 0.0
                )
            elif is_vertical_credit:
                entry_quote_ready = bool(
                    entry_quote_bid is not None
                    and entry_quote_bid > 0.0
                    and short_entry_quote_ask is not None
                    and short_entry_quote_ask > 0.0
                )
            else:
                entry_quote_ready = bool(entry_quote_ask is not None and entry_quote_ask > 0.0)
            if isinstance(entry_quote, dict) and isinstance(entry_quote.get("ts"), datetime):
                attempt_snapshot["entry_quote_ts"] = entry_quote["ts"]
            attempt_snapshot["entry_quote_spread_abs"] = entry_quote_spread_abs
            attempt_snapshot["entry_quote_spread_pct"] = entry_quote_spread_pct

        if is_vertical_credit:
            if not secondary_entry_bars or not secondary_exit_bars:
                self._bump_option_rejection("option_bars_missing")
                return _finalize_attempt(None)
            fallback_stop = _apply_vertical_credit_premium_exits(
                entry_credit_raw=max(float(entry_raw), 0.0),
                take_profit_capture_pct=float(config.option_credit_take_profit_capture_pct),
                stop_loss_multiple=float(config.option_credit_stop_loss_multiple),
                short_entry_bar=entry_bar,
                short_exit_bar=exit_bar,
                short_entry_bars=entry_bars,
                short_exit_bars=exit_bars,
                long_entry_bars=secondary_entry_bars or [],
                long_exit_bars=secondary_exit_bars or [],
                day=day,
                exit_day=exit_day,
                default_exit_reason=str(exit_plan.get("exit_reason") or ""),
                default_exit_ts=delayed_exit_ts,
            )
        elif is_vertical_debit:
            if secondary_entry_bar is None or secondary_exit_bar is None or not secondary_entry_bars or not secondary_exit_bars:
                self._bump_option_rejection("option_bars_missing")
                return _finalize_attempt(None)
            fallback_stop = _apply_vertical_debit_premium_exits(
                entry_debit_raw=max(
                    _causal_bar_fill_price(entry_bar) - _causal_bar_fill_price(secondary_entry_bar),
                    0.0,
                ),
                option_take_profit_pct=option_take_profit_pct,
                option_max_loss_pct=option_max_loss_pct,
                long_entry_bar=entry_bar,
                long_exit_bar=exit_bar,
                long_entry_bars=entry_bars,
                long_exit_bars=exit_bars,
                short_entry_bar=secondary_entry_bar,
                short_exit_bar=secondary_exit_bar,
                short_entry_bars=secondary_entry_bars,
                short_exit_bars=secondary_exit_bars,
                day=day,
                exit_day=exit_day,
                default_exit_reason=str(exit_plan.get("exit_reason") or ""),
                default_exit_ts=delayed_exit_ts,
            )
        else:
            fallback_stop = _apply_option_premium_stop(
                entry_price_raw=entry_raw,
                option_take_profit_pct=option_take_profit_pct,
                option_max_loss_pct=option_max_loss_pct,
                entry_bar=entry_bar,
                exit_bar=exit_bar,
                entry_bars=entry_bars,
                exit_bars=exit_bars,
                day=day,
                exit_day=exit_day,
                default_exit_reason=str(exit_plan.get("exit_reason") or ""),
                default_exit_ts=delayed_exit_ts,
            )

        if quote_pricing_enabled and (
            (is_vertical_credit and entry_quote_bid is not None and entry_quote_bid > 0.0)
            or (entry_quote_ask is not None and entry_quote_ask > 0.0)
        ):
            if is_vertical_credit:
                quote_stop = dict(fallback_stop)
            elif is_vertical_debit:
                if short_entry_quote_bid is not None and short_entry_quote_bid > 0.0:
                    if secondary_entry_bar is None or secondary_exit_bar is None or not secondary_entry_bars or not secondary_exit_bars:
                        self._bump_option_rejection("option_bars_missing")
                        return _finalize_attempt(None)
                    long_default_exit_quotes = (
                        entry_quotes
                        if exit_day == day
                        else self._load_option_quotes(symbol=primary_option_symbol, day=exit_day)
                    )
                    short_default_exit_quotes = (
                        short_entry_quotes
                        if exit_day == day
                        else self._load_option_quotes(symbol=secondary_symbol, day=exit_day)
                    )
                    entry_quote_ts = (
                        max(
                            [entry_quote["ts"], short_entry_quote["ts"]],
                            key=_as_utc_aware,
                        )
                        if isinstance(entry_quote.get("ts"), datetime)
                        and isinstance(short_entry_quote.get("ts"), datetime)
                        else delayed_entry_ts
                    )
                    quote_stop = _apply_vertical_debit_premium_exits_from_quotes(
                        entry_debit_raw=max(float(entry_quote_ask) - float(short_entry_quote_bid), 0.0),
                        option_take_profit_pct=option_take_profit_pct,
                        option_max_loss_pct=option_max_loss_pct,
                        entry_fill_ts=entry_quote_ts,
                        default_exit_bar=exit_bar,
                        default_exit_reason=str(exit_plan.get("exit_reason") or ""),
                        default_exit_ts=delayed_exit_ts,
                        long_same_day_quotes=entry_quotes,
                        long_exit_day_quotes=long_default_exit_quotes,
                        short_same_day_quotes=short_entry_quotes,
                        short_exit_day_quotes=short_default_exit_quotes,
                        day=day,
                        exit_day=exit_day,
                    )
                else:
                    quote_stop = dict(fallback_stop)
            else:
                default_exit_quotes = (
                    entry_quotes
                    if exit_day == day
                    else self._load_option_quotes(symbol=primary_option_symbol, day=exit_day)
                )
                quote_stop = _apply_option_premium_stop_from_quotes(
                    entry_price_raw=float(entry_quote_ask),
                    option_take_profit_pct=option_take_profit_pct,
                    option_max_loss_pct=option_max_loss_pct,
                    entry_fill_ts=entry_quote["ts"] if isinstance(entry_quote.get("ts"), datetime) else delayed_entry_ts,
                    default_exit_bar=exit_bar,
                    default_exit_reason=str(exit_plan.get("exit_reason") or ""),
                    default_exit_ts=delayed_exit_ts,
                    same_day_quotes=entry_quotes,
                    exit_day_quotes=default_exit_quotes,
                    day=day,
                    exit_day=exit_day,
                )
            quote_exit_day = _as_et(quote_stop["effective_exit_ts"]).date()
            if quote_exit_day == day:
                exit_quotes = entry_quotes
            else:
                exit_quotes = self._load_option_quotes(symbol=primary_option_symbol, day=quote_exit_day)
            exit_quote = self._lookup_option_quote_on_or_after(
                symbol=primary_option_symbol,
                day=quote_exit_day,
                ts=quote_stop["effective_exit_ts"],
                fallback_last=False,
            )
            if exit_quote is not None:
                exit_quote_bid = _safe_float(exit_quote.get("bid"))
                exit_quote_ask = _safe_float(exit_quote.get("ask"))
            if is_vertical_pair:
                secondary_symbol = short_option_symbol if is_vertical_debit else long_option_symbol
                if quote_exit_day == day:
                    short_exit_quotes = self._load_option_quotes(symbol=secondary_symbol, day=day)
                else:
                    short_exit_quotes = self._load_option_quotes(symbol=secondary_symbol, day=quote_exit_day)
                short_exit_quote = self._lookup_option_quote_on_or_after(
                    symbol=secondary_symbol,
                    day=quote_exit_day,
                    ts=quote_stop["effective_exit_ts"],
                    fallback_last=False,
                )
                if short_exit_quote is not None:
                    short_exit_quote_bid = _safe_float(short_exit_quote.get("bid"))
                    short_exit_quote_ask = _safe_float(short_exit_quote.get("ask"))
                if is_vertical_debit:
                    can_use_quote_fill = bool(
                        short_entry_quote_bid is not None
                        and short_entry_quote_bid > 0.0
                        and exit_quote_bid is not None
                        and exit_quote_bid > 0.0
                        and short_exit_quote_ask is not None
                        and short_exit_quote_ask > 0.0
                    )
                else:
                    can_use_quote_fill = bool(
                        entry_quote_bid is not None
                        and entry_quote_bid > 0.0
                        and short_entry_quote_ask is not None
                        and short_entry_quote_ask > 0.0
                        and exit_quote_ask is not None
                        and exit_quote_ask > 0.0
                        and short_exit_quote_bid is not None
                        and short_exit_quote_bid >= 0.0
                    )
            else:
                can_use_quote_fill = bool(exit_quote_bid is not None and exit_quote_bid > 0)
            if is_vertical_debit:
                exit_quote_ready = bool(
                    exit_quote_bid is not None
                    and exit_quote_bid > 0.0
                    and short_exit_quote_ask is not None
                    and short_exit_quote_ask > 0.0
                )
            elif is_vertical_credit:
                exit_quote_ready = bool(
                    exit_quote_ask is not None
                    and exit_quote_ask > 0.0
                    and short_exit_quote_bid is not None
                    and short_exit_quote_bid >= 0.0
                )
            else:
                exit_quote_ready = bool(exit_quote_bid is not None and exit_quote_bid > 0.0)
            if isinstance(exit_quote, dict) and isinstance(exit_quote.get("ts"), datetime):
                attempt_snapshot["exit_quote_ts"] = exit_quote["ts"]
            if can_use_quote_fill:
                self._bump_option_funnel("quote_fill_available")
                if is_vertical_debit:
                    entry_raw = float(entry_quote_ask) - float(short_entry_quote_bid)
                elif is_vertical_credit:
                    entry_raw = float(entry_quote_bid) - float(short_entry_quote_ask)
                else:
                    entry_raw = float(entry_quote_ask)
                if is_vertical_pair:
                    pair_entry_ts_candidates = [
                        quote.get("ts")
                        for quote in (entry_quote, short_entry_quote)
                        if isinstance(quote, dict) and isinstance(quote.get("ts"), datetime)
                    ]
                    if pair_entry_ts_candidates:
                        entry_fill_ts = max(pair_entry_ts_candidates, key=_as_utc_aware)
                elif isinstance(entry_quote.get("ts"), datetime):
                    entry_fill_ts = entry_quote["ts"]
                exit_bar = quote_stop["exit_bar"]
                effective_exit_reason = str(quote_stop["effective_exit_reason"] or "")
                effective_exit_ts = quote_stop["effective_exit_ts"]
                option_premium_stop_triggered = bool(quote_stop.get("option_premium_stop_triggered"))
                option_premium_stop_price_raw = quote_stop.get("option_premium_stop_price_raw")
                premium_take_profit_triggered = bool(quote_stop.get("premium_take_profit_triggered"))
                premium_stop_triggered = bool(quote_stop.get("premium_stop_triggered"))
                if is_vertical_debit:
                    exit_raw = max(float(exit_quote_bid) - float(short_exit_quote_ask), 0.0)
                    fill_pricing_source = "quotes_vertical_debit"
                    pair_exit_ts_candidates = [
                        quote.get("ts")
                        for quote in (exit_quote, short_exit_quote)
                        if isinstance(quote, dict) and isinstance(quote.get("ts"), datetime)
                    ]
                    if pair_exit_ts_candidates:
                        exit_fill_ts = max(pair_exit_ts_candidates, key=_as_utc_aware)
                elif is_vertical_credit:
                    exit_raw = max(float(exit_quote_ask) - float(short_exit_quote_bid), 0.0)
                    fill_pricing_source = "quotes_vertical_credit"
                    pair_exit_ts_candidates = [
                        quote.get("ts")
                        for quote in (exit_quote, short_exit_quote)
                        if isinstance(quote, dict) and isinstance(quote.get("ts"), datetime)
                    ]
                    if pair_exit_ts_candidates:
                        exit_fill_ts = max(pair_exit_ts_candidates, key=_as_utc_aware)
                else:
                    exit_raw = float(exit_quote_bid)
                    if isinstance(exit_quote.get("ts"), datetime):
                        exit_fill_ts = exit_quote["ts"]
                    fill_pricing_source = "quotes"
                    if premium_take_profit_triggered:
                        fill_pricing_source = "quotes_premium_take_profit"
                    if option_premium_stop_triggered and option_premium_stop_price_raw is not None:
                        fill_pricing_source = "quotes_option_premium_stop"
                        exit_raw = min(exit_raw, float(option_premium_stop_price_raw))

        if not can_use_quote_fill:
            exit_bar = fallback_stop["exit_bar"]
            effective_exit_reason = str(fallback_stop["effective_exit_reason"] or "")
            effective_exit_ts = fallback_stop["effective_exit_ts"]
            option_premium_stop_triggered = bool(fallback_stop.get("option_premium_stop_triggered"))
            option_premium_stop_price_raw = fallback_stop.get("option_premium_stop_price_raw")
            premium_take_profit_triggered = bool(fallback_stop.get("premium_take_profit_triggered"))
            premium_stop_triggered = bool(fallback_stop.get("premium_stop_triggered"))
            if is_vertical_pair:
                if secondary_entry_bar is None or secondary_exit_bar is None:
                    self._bump_option_rejection("option_bars_missing")
                    return _finalize_attempt(None)
                if is_vertical_debit:
                    entry_raw = _causal_bar_fill_price(entry_bar) - _causal_bar_fill_price(secondary_entry_bar or {})
                    exit_raw = max(float(fallback_stop["exit_raw"]) - _causal_bar_fill_price(secondary_exit_bar or {}), 0.0)
                    fill_pricing_source = "bar_open_vertical_debit"
                else:
                    entry_raw = _causal_bar_fill_price(entry_bar) - _causal_bar_fill_price(secondary_entry_bar or {})
                    exit_raw = float(fallback_stop["exit_raw"])
                    fill_pricing_source = "bar_open_vertical_credit"
            else:
                entry_raw = _causal_bar_fill_price(entry_bar)
                exit_raw = float(fallback_stop["exit_raw"])
            entry_fill_ts = entry_bar["ts"]
            exit_fill_ts = exit_bar["ts"]
            if quote_pricing_enabled:
                if quote_fallback_enabled:
                    used_quote_fallback = True
                    self._bump_option_funnel("quote_fill_fallback_used")
                    fill_pricing_source = (
                        "bar_open_quote_fallback_vertical_debit"
                        if is_vertical_debit
                        else ("bar_open_quote_fallback_vertical_credit" if is_vertical_credit else "bar_open_quote_fallback")
                    )
                else:
                    if not entry_quote_ready:
                        self._bump_option_rejection("quote_missing_after_entry_ts")
                    elif not exit_quote_ready:
                        self._bump_option_rejection("quote_missing_after_exit_ts")
                    self._bump_option_rejection("quotes_unavailable_without_fallback")
                    return _finalize_attempt(None)

        if entry_raw <= 0:
            self._bump_option_rejection("entry_price_nonpositive")
            return _finalize_attempt(None)
        if (
            isinstance(entry_fill_ts, datetime)
            and isinstance(effective_exit_ts, datetime)
            and _as_utc_aware(entry_fill_ts) >= _as_utc_aware(effective_exit_ts)
        ):
            self._bump_option_rejection("entry_after_effective_exit")
            return _finalize_attempt(None)
        if (
            isinstance(entry_fill_ts, datetime)
            and isinstance(exit_fill_ts, datetime)
            and _as_utc_aware(entry_fill_ts) >= _as_utc_aware(exit_fill_ts)
        ):
            self._bump_option_rejection("entry_after_exit_fill")
            return _finalize_attempt(None)
        self._bump_option_funnel("pricing_resolved")
        attempt_snapshot.update(
            {
                "entry_volume": int(entry_volume),
                "option_quote_fallback_used": bool(used_quote_fallback),
            }
        )
        if is_vertical_pair:
            if short_entry_quote is not None:
                short_entry_volume = max(
                    int(short_entry_quote.get("bid_size") or 0),
                    int(short_entry_quote.get("ask_size") or 0),
                    short_entry_volume,
                )
            if short_entry_volume > 0:
                entry_volume = min(entry_volume, short_entry_volume) if entry_volume > 0 else short_entry_volume
            if short_entry_bar_range_pct > 0.0:
                entry_bar_range_pct = max(entry_bar_range_pct, short_entry_bar_range_pct)
            if spread_width is None or spread_width <= 0.0:
                self._bump_option_rejection("vertical_short_leg_missing" if is_vertical_debit else "vertical_credit_long_leg_missing")
                return _finalize_attempt(None)
            if is_vertical_debit:
                debit_to_width_ratio = float(entry_raw) / float(spread_width)
                if debit_to_width_ratio > max(float(config.option_vertical_max_debit_to_width_ratio), 0.0):
                    self._bump_option_rejection("vertical_debit_to_width_ratio")
                    return _finalize_attempt(None)
                if (
                    entry_quote_bid is not None
                    and entry_quote_ask is not None
                    and short_entry_quote_bid is not None
                    and short_entry_quote_ask is not None
                ):
                    entry_combined_spread_abs = max(float(entry_quote_ask) - float(entry_quote_bid), 0.0) + max(
                        float(short_entry_quote_ask) - float(short_entry_quote_bid),
                        0.0,
                    )
                    if entry_raw > 0.0:
                        entry_combined_spread_to_debit_ratio = entry_combined_spread_abs / float(entry_raw)
                        if (
                            entry_combined_spread_to_debit_ratio
                            > max(float(config.option_vertical_max_combined_spread_to_debit_ratio), 0.0)
                        ):
                            self._bump_option_rejection("vertical_combined_spread_to_debit_ratio")
                            return _finalize_attempt(None)
            else:
                credit_to_width_ratio = float(entry_raw) / float(spread_width)
                if credit_to_width_ratio < max(float(config.option_vertical_min_credit_to_width_ratio), 0.0):
                    self._bump_option_rejection("vertical_credit_to_width_ratio")
                    return _finalize_attempt(None)
                max_credit_to_width = max(float(config.option_vertical_max_credit_to_width_ratio), 0.0)
                if max_credit_to_width > 0.0 and credit_to_width_ratio > max_credit_to_width:
                    self._bump_option_rejection("vertical_credit_to_width_ratio")
                    return _finalize_attempt(None)
                if entry_raw < max(float(config.option_credit_min_entry_credit), 0.0):
                    self._bump_option_rejection("vertical_credit_to_width_ratio")
                    return _finalize_attempt(None)
                short_strike_buffer_pct = (
                    abs(float(setup.get("entry_underlying") or 0.0) - float(short_strike))
                    / max(float(setup.get("entry_underlying") or 0.0), 1.0)
                )
                if short_strike_buffer_pct < max(float(config.option_credit_min_short_strike_buffer_pct), 0.0):
                    self._bump_option_rejection("vertical_credit_buffer_too_small")
                    return _finalize_attempt(None)
                if (
                    entry_quote_bid is not None
                    and entry_quote_ask is not None
                    and short_entry_quote_bid is not None
                    and short_entry_quote_ask is not None
                ):
                    entry_combined_spread_abs = max(float(entry_quote_ask) - float(entry_quote_bid), 0.0) + max(
                        float(short_entry_quote_ask) - float(short_entry_quote_bid),
                        0.0,
                    )
                    if entry_raw > 0.0:
                        entry_combined_spread_to_credit_ratio = entry_combined_spread_abs / float(entry_raw)
                        if (
                            entry_combined_spread_to_credit_ratio
                            > max(float(config.option_vertical_max_combined_spread_to_credit_ratio), 0.0)
                        ):
                            self._bump_option_rejection("vertical_combined_spread_to_credit_ratio")
                            return _finalize_attempt(None)
        self._bump_option_funnel("structure_filters_passed")

        gate_mode = str(config.option_microstructure_gate_mode or "absolute").strip().lower()
        static_slippage_bps = max(float(config.option_slippage_bps), 0.0)
        range_slippage_bps = max(float(config.option_range_adverse_fill_fraction), 0.0) * max(
            entry_bar_range_pct,
            0.0,
        ) * 10000.0
        max_range_slippage_bps = max(float(config.option_range_adverse_fill_max_bps), 0.0)
        if max_range_slippage_bps > 0:
            range_slippage_bps = min(range_slippage_bps, max_range_slippage_bps)
        total_slippage_bps = static_slippage_bps + range_slippage_bps
        pre_capacity_slippage = total_slippage_bps / 10000.0
        entry_price_before_capacity = (
            max(0.0, entry_raw * (1.0 - pre_capacity_slippage))
            if is_vertical_credit
            else entry_raw * (1.0 + pre_capacity_slippage)
        )
        risk_notional = max(float(current_equity), 0.0) * max(float(config.risk_per_trade), 0.0)
        sizing_mode = str(config.option_risk_sizing_mode or "premium_at_risk").strip().lower()
        sizing_loss_fraction = (
            max(float(config.option_max_loss_pct), 0.0)
            if sizing_mode == "premium_stop" and 0.0 < float(config.option_max_loss_pct) <= 1.0
            else 1.0
        )
        commission_risk = (
            max(float(config.option_commission_per_contract), 0.0) * 2.0 * max(int(option_leg_count), 1)
            if bool(config.option_sizing_include_commission)
            else 0.0
        )
        if is_vertical_credit:
            max_loss_per_contract = max(float(spread_width or 0.0) - float(entry_price_before_capacity), 0.0) * 100.0
            per_contract_risk_capital = max_loss_per_contract + commission_risk
            provisional_qty = int(risk_notional / per_contract_risk_capital) if per_contract_risk_capital > 0 else 0
        else:
            per_contract_risk_capital = (
                entry_price_before_capacity * 100.0 * sizing_loss_fraction
            ) + commission_risk
            provisional_qty = _option_qty_for_risk(
                risk_notional=risk_notional,
                entry_price=entry_price_before_capacity,
                commission_per_contract=float(config.option_commission_per_contract),
                include_commission=bool(config.option_sizing_include_commission),
                min_entry_price=float(config.option_sizing_min_entry_price),
                sizing_mode=sizing_mode,
                option_max_loss_pct=float(config.option_max_loss_pct),
                option_leg_count=int(option_leg_count),
            )

        micro_filter_active = bool(config.require_option_microstructure_filter) or bool(
            config.option_structure_filter_enabled
        )
        if micro_filter_active:
            min_entry_volume = 0
            if bool(config.require_option_microstructure_filter):
                min_entry_volume = max(min_entry_volume, max(int(config.option_min_entry_volume), 0))
            if bool(config.option_structure_filter_enabled):
                min_entry_volume = max(min_entry_volume, max(int(config.option_structure_min_entry_volume), 0))
            min_entry_volume = _required_option_entry_volume(
                gate_mode=gate_mode,
                base_min_entry_volume=min_entry_volume,
                provisional_qty=int(provisional_qty),
                max_entry_volume_participation=float(config.option_max_entry_volume_participation),
            )
            if entry_volume < min_entry_volume:
                self._bump_option_rejection("micro_entry_volume")
                return _finalize_attempt(None)

            max_range_pct = 0.0
            if bool(config.require_option_microstructure_filter):
                max_range_pct = max(
                    _setup_override_float(
                        setup,
                        "option_max_entry_bar_range_pct",
                        config.option_max_entry_bar_range_pct,
                    ),
                    0.0,
                )
            if bool(config.option_structure_filter_enabled):
                structure_cap = max(float(config.option_structure_max_entry_bar_range_pct), 0.0)
                max_range_pct = structure_cap if max_range_pct <= 0 else min(max_range_pct, structure_cap)
            if max_range_pct > 0 and entry_bar_range_pct > max_range_pct:
                self._bump_option_rejection("micro_entry_range")
                return _finalize_attempt(None)

            min_entry_price = 0.0
            if bool(config.require_option_microstructure_filter):
                min_entry_price = max(min_entry_price, max(float(config.option_min_entry_price), 0.0))
            if bool(config.option_structure_filter_enabled):
                min_entry_price = max(min_entry_price, max(float(config.option_structure_min_entry_price), 0.0))
            if entry_raw < min_entry_price:
                self._bump_option_rejection("micro_entry_price")
                return _finalize_attempt(None)

            max_spread_pct = 0.0
            if bool(config.require_option_microstructure_filter):
                max_spread_pct = max(float(config.option_max_entry_spread_pct), 0.0)
            if bool(config.option_structure_filter_enabled):
                structure_spread_cap = max(float(config.option_structure_max_entry_spread_pct), 0.0)
                max_spread_pct = structure_spread_cap if max_spread_pct <= 0 else min(
                    max_spread_pct,
                    structure_spread_cap,
                )
            if max_spread_pct > 0 and can_use_quote_fill:
                if entry_quote_spread_pct is None or entry_quote_spread_pct > max_spread_pct:
                    self._bump_option_rejection("micro_quote_spread")
                    return _finalize_attempt(None)
        self._bump_option_funnel("microstructure_filters_passed")

        expected_move = _expected_underlying_target_move(
            setup=setup,
            take_profit_rr=float(config.take_profit_rr),
        )
        if expected_move is not None:
            if (not is_vertical_pair) and can_use_quote_fill and entry_quote_ask is not None and entry_quote_ask > 0:
                option_type = "call" if int(setup.get("direction") or 0) > 0 else "put"
                intrinsic_value = _option_intrinsic_value(
                    option_type=option_type,
                    underlying_price=float(setup.get("entry_underlying") or 0.0),
                    strike=float(long_contract.get("strike_price") or 0.0),
                )
                extrinsic_value = max(float(entry_quote_ask) - intrinsic_value, 0.0)
                min_move_to_extrinsic = max(float(config.option_min_expected_move_to_extrinsic_ratio), 0.0)
                min_move_to_spread = max(float(config.option_min_expected_move_to_spread_ratio), 0.0)
                if min_move_to_extrinsic > 0.0:
                    if extrinsic_value <= 0.0:
                        move_to_extrinsic_ratio = float("inf")
                    else:
                        move_to_extrinsic_ratio = float(expected_move) / float(extrinsic_value)
                    expected_move_to_extrinsic_ratio = move_to_extrinsic_ratio
                    if move_to_extrinsic_ratio < min_move_to_extrinsic:
                        self._bump_option_rejection("move_to_cost_extrinsic_ratio")
                        return _finalize_attempt(None)
                if min_move_to_spread > 0.0:
                    if entry_quote_spread_abs is None or entry_quote_spread_abs <= 0.0:
                        self._bump_option_rejection("move_to_cost_spread_ratio")
                        return _finalize_attempt(None)
                    move_to_spread_ratio = float(expected_move) / float(entry_quote_spread_abs)
                    expected_move_to_spread_ratio = move_to_spread_ratio
                    if move_to_spread_ratio < min_move_to_spread:
                        self._bump_option_rejection("move_to_cost_spread_ratio")
                        return _finalize_attempt(None)
            if is_vertical_debit:
                min_move_to_debit = max(float(config.option_min_expected_move_to_debit_ratio), 0.0)
                if min_move_to_debit > 0.0:
                    if entry_raw <= 0.0:
                        self._bump_option_rejection("move_to_cost_debit_ratio")
                        return _finalize_attempt(None)
                    expected_move_to_debit_ratio = float(expected_move) / float(entry_raw)
                    if expected_move_to_debit_ratio < min_move_to_debit:
                        self._bump_option_rejection("move_to_cost_debit_ratio")
                        return _finalize_attempt(None)
            if is_vertical_credit:
                min_buffer_ratio = max(float(config.option_credit_min_expected_move_buffer_ratio), 0.0)
                if min_buffer_ratio > 0.0:
                    short_strike_buffer = abs(float(setup.get("entry_underlying") or 0.0) - float(short_strike))
                    if expected_move <= 0.0:
                        buffer_ratio = float("inf")
                    else:
                        buffer_ratio = short_strike_buffer / float(expected_move)
                    expected_move_to_debit_ratio = buffer_ratio
                    if buffer_ratio < min_buffer_ratio:
                        self._bump_option_rejection("vertical_credit_buffer_too_small")
                        return _finalize_attempt(None)
        self._bump_option_funnel("move_cost_filters_passed")
        attempt_snapshot.update(
            {
                "expected_move_to_extrinsic_ratio": expected_move_to_extrinsic_ratio,
                "expected_move_to_debit_ratio": expected_move_to_debit_ratio,
                "expected_move_to_spread_ratio": expected_move_to_spread_ratio,
            }
        )

        slippage = pre_capacity_slippage
        if is_vertical_credit:
            entry_price = max(0.0, entry_raw * (1.0 - slippage))
            exit_price = max(0.0, exit_raw * (1.0 + slippage))
        else:
            entry_price = entry_raw * (1.0 + slippage)
            exit_price = max(0.0, exit_raw * (1.0 - slippage))
        attempt_snapshot.update(
            {
                "entry_debit": float(entry_raw) if is_vertical_debit else None,
                "entry_credit": float(entry_raw) if is_vertical_credit else None,
                "entry_price_effective": float(entry_price),
                "exit_price_effective": float(exit_price),
                "option_quote_fallback_used": bool(used_quote_fallback),
            }
        )

        if is_vertical_credit:
            qty = int(provisional_qty)
        else:
            qty = int(provisional_qty)
        qty_before_liquidity_caps = qty
        long_contract_open_interest = int(long_contract.get("open_interest") or 0)
        contract_open_interest = (
            min(long_contract_open_interest, short_contract_open_interest)
            if is_vertical_pair and short_contract_open_interest > 0
            else long_contract_open_interest
        )
        attempt_snapshot["contract_open_interest"] = int(contract_open_interest)
        attempt_snapshot["open_interest_data_available"] = bool(contract_open_interest > 0)
        volume_cap_qty = qty
        oi_cap_qty = qty
        if config.enforce_option_liquidity_caps:
            max_volume_participation = max(float(config.option_max_entry_volume_participation), 0.0)
            if max_volume_participation <= 0:
                qty = 0
            else:
                volume_cap_qty = int(max(float(entry_volume), 0.0) * max_volume_participation)
                qty = min(qty, volume_cap_qty)

            max_oi_participation = max(float(config.option_max_open_interest_participation), 0.0)
            if max_oi_participation <= 0:
                qty = 0
            elif contract_open_interest > 0:
                oi_cap_qty = int(float(contract_open_interest) * max_oi_participation)
                qty = min(qty, oi_cap_qty)

        if qty < 1:
            self._bump_option_rejection("qty_below_1_after_caps")
            return _finalize_attempt(None)
        self._bump_option_funnel("sizing_passed")
        volume_participation = (float(qty) / float(entry_volume)) if entry_volume > 0 else 0.0
        oi_participation = (float(qty) / float(contract_open_interest)) if contract_open_interest > 0 else 0.0

        if is_vertical_credit:
            gross_pnl = qty * (entry_price - exit_price) * 100.0
        else:
            gross_pnl = qty * (exit_price - entry_price) * 100.0
        commission = qty * max(float(config.option_commission_per_contract), 0.0) * 2.0 * max(
            int(option_leg_count),
            1,
        )
        pnl = gross_pnl - commission
        invested = qty * per_contract_risk_capital if is_vertical_credit else qty * entry_price * 100.0
        trade_return = (pnl / invested) if invested > 0 else 0.0
        self._bump_option_funnel("entry_constructed")
        self._bump_option_funnel("trades_created")

        return _finalize_attempt(BacktestTrade(
            trade_id=str(uuid.uuid4()),
            signal_id=str(uuid.uuid4()),
            ticker=ticker,
            option_symbol=trade_option_symbol,
            entry_ts=entry_fill_ts,
            exit_ts=exit_fill_ts,
            side=(
                "bull_put_credit"
                if is_vertical_credit and direction > 0
                else (
                    "bear_call_credit"
                    if is_vertical_credit
                    else ("long_call" if direction > 0 else "long_put")
                )
            ),
            qty=qty,
            entry_price=entry_price,
            exit_price=exit_price,
            pnl=pnl,
            return_pct=trade_return,
            status="closed",
            metadata={
                "strategy": "intraday_opening_range_stocks_in_play_options",
                "strategy_variant": str(setup.get("strategy_variant") or config.strategy_variant),
                "execution_mode": "historical_options",
                "direction": direction,
                "entry_underlying": float(setup["entry_underlying"]),
                "exit_underlying": float(exit_plan["exit_underlying"]),
                "stop_underlying": float(setup["stop_underlying"]),
                "exit_reason": effective_exit_reason,
                "exit_reason_base": str(exit_plan["exit_reason"]),
                "orb_high": float(setup["orb_high"]),
                "orb_low": float(setup["orb_low"]),
                "opening_range_minutes": int(setup.get("opening_range_minutes") or 0),
                "opening_bar_direction": int(setup.get("opening_bar_direction") or 0),
                "trend_ema_fast": float(setup["trend_ema_fast"]),
                "trend_ema_slow": float(setup["trend_ema_slow"]),
                "volume_ratio": float(setup["volume_ratio"]),
                "relative_opening_volume": _safe_float(setup.get("relative_opening_volume")),
                "gap_return": _safe_float(setup.get("gap_return")),
                "atr_value": _safe_float(setup.get("atr_value")),
                "vol_regime_prev_close": _safe_float(setup.get("vol_regime_prev_close")),
                "market_regime_label": _normalize_regime_label(setup.get("market_regime_label")),
                "regime_v2_state": str(setup.get("regime_v2_state") or "unknown"),
                "regime_v2_route_state": str(setup.get("regime_v2_route_state") or "unknown"),
                "regime_v2_route_action": str(setup.get("regime_v2_route_action") or ""),
                "regime_v2_confidence": _safe_float(setup.get("regime_v2_confidence")),
                "regime_v2_selected_variant": str(setup.get("regime_v2_selected_variant") or ""),
                "regime_v2_skip_reason": str(setup.get("regime_v2_skip_reason") or ""),
                "regime_v2_route_overlay_name": str(setup.get("regime_v2_route_overlay_name") or ""),
                "fvg_gap": float(setup["fvg_gap"]),
                "fib_anchor": _safe_float(setup.get("fib_anchor")),
                "fib_impulse_extreme": _safe_float(setup.get("fib_impulse_extreme")),
                "fib_entry_zone_low": _safe_float(setup.get("fib_entry_zone_low")),
                "fib_entry_zone_high": _safe_float(setup.get("fib_entry_zone_high")),
                "fill_pricing_source": fill_pricing_source,
                "option_structure_mode": structure_mode,
                "option_leg_count": int(option_leg_count),
                "long_leg_symbol": long_option_symbol,
                "short_leg_symbol": short_option_symbol or None,
                "long_leg_strike": float(long_strike),
                "short_leg_strike": float(short_strike) if short_option_symbol else None,
                "spread_width": float(spread_width) if spread_width is not None else None,
                "entry_debit": float(entry_raw) if is_vertical_debit else None,
                "exit_credit": float(exit_raw) if is_vertical_debit else None,
                "entry_credit": float(entry_raw) if is_vertical_credit else None,
                "exit_debit": float(exit_raw) if is_vertical_credit else None,
                "entry_combined_spread_abs": (
                    float(entry_combined_spread_abs) if entry_combined_spread_abs is not None else None
                ),
                "entry_combined_spread_to_debit_ratio": (
                    float(entry_combined_spread_to_debit_ratio)
                    if entry_combined_spread_to_debit_ratio is not None
                    else None
                ),
                "entry_combined_spread_to_credit_ratio": (
                    float(entry_combined_spread_to_credit_ratio)
                    if entry_combined_spread_to_credit_ratio is not None
                    else None
                ),
                "credit_to_width_ratio": float(credit_to_width_ratio) if credit_to_width_ratio is not None else None,
                "short_strike_buffer_pct": (
                    float(short_strike_buffer_pct) if short_strike_buffer_pct is not None else None
                ),
                "expected_move_to_debit_ratio": (
                    float(expected_move_to_debit_ratio) if expected_move_to_debit_ratio is not None else None
                ),
                "short_leg_bid_at_entry": (
                    float(entry_quote_bid) if is_vertical_credit and entry_quote_bid is not None else (
                        float(short_entry_quote_bid) if short_entry_quote_bid is not None else None
                    )
                ),
                "short_leg_ask_at_exit": (
                    float(exit_quote_ask) if is_vertical_credit and exit_quote_ask is not None else (
                        float(short_exit_quote_ask) if short_exit_quote_ask is not None else None
                    )
                ),
                "long_leg_ask_at_entry": (
                    float(short_entry_quote_ask) if is_vertical_credit and short_entry_quote_ask is not None else (
                        float(entry_quote_ask) if is_vertical_debit and entry_quote_ask is not None else None
                    )
                ),
                "long_leg_bid_at_exit": (
                    float(short_exit_quote_bid) if is_vertical_credit and short_exit_quote_bid is not None else (
                        float(exit_quote_bid) if is_vertical_debit and exit_quote_bid is not None else None
                    )
                ),
                "option_quote_pricing_enabled": bool(config.use_option_quotes_for_fills),
                "option_quote_fill_fallback_enabled": quote_fallback_enabled,
                "option_quote_fallback_used": used_quote_fallback,
                "entry_quote_ts": (
                    entry_quote["ts"].isoformat()
                    if isinstance(entry_quote, dict) and isinstance(entry_quote.get("ts"), datetime)
                    else None
                ),
                "entry_quote_bid": entry_quote_bid,
                "entry_quote_ask": entry_quote_ask,
                "entry_quote_mid": entry_quote_mid,
                "entry_quote_spread_abs": entry_quote_spread_abs,
                "entry_quote_spread_pct": entry_quote_spread_pct,
                "exit_quote_ts": (
                    exit_quote["ts"].isoformat()
                    if isinstance(exit_quote, dict) and isinstance(exit_quote.get("ts"), datetime)
                    else None
                ),
                "exit_quote_bid": exit_quote_bid,
                "exit_quote_ask": exit_quote_ask,
                "short_entry_quote_ts": (
                    short_entry_quote["ts"].isoformat()
                    if isinstance(short_entry_quote, dict) and isinstance(short_entry_quote.get("ts"), datetime)
                    else None
                ),
                "short_exit_quote_ts": (
                    short_exit_quote["ts"].isoformat()
                    if isinstance(short_exit_quote, dict) and isinstance(short_exit_quote.get("ts"), datetime)
                    else None
                ),
                "short_entry_quote_bid": short_entry_quote_bid,
                "short_entry_quote_ask": short_entry_quote_ask,
                "short_exit_quote_bid": short_exit_quote_bid,
                "short_exit_quote_ask": short_exit_quote_ask,
                "entry_price_raw": entry_raw,
                "entry_volume": entry_volume,
                "entry_volume_long_leg": int(entry_bar.get("volume") or 0),
                "entry_volume_short_leg": int(short_entry_volume),
                "entry_bar_range_pct": entry_bar_range_pct,
                "exit_price_raw": exit_raw,
                "entry_price_effective": entry_price,
                "exit_price_effective": exit_price,
                "option_take_profit_pct": option_take_profit_pct,
                "option_max_loss_pct": option_max_loss_pct,
                "option_premium_stop_triggered": option_premium_stop_triggered,
                "option_premium_stop_price_raw": option_premium_stop_price_raw,
                "premium_take_profit_triggered": premium_take_profit_triggered,
                "premium_stop_triggered": premium_stop_triggered,
                "option_slippage_bps": total_slippage_bps,
                "option_slippage_static_bps": static_slippage_bps,
                "option_slippage_range_bps": range_slippage_bps,
                "option_commission_total": commission,
                "execution_entry_delay_base_minutes": entry_delay_base,
                "execution_exit_delay_base_minutes": exit_delay_base,
                "execution_entry_delay_minutes": entry_delay,
                "execution_exit_delay_minutes": exit_delay,
                "execution_delay_randomization": randomization_enabled,
                "execution_entry_delay_jitter_minutes": int(config.execution_entry_delay_jitter_minutes),
                "execution_exit_delay_jitter_minutes": int(config.execution_exit_delay_jitter_minutes),
                "execution_delay_random_seed": int(config.execution_delay_random_seed),
                "execution_timing_model": str(config.execution_timing_model or "bar_open"),
                "execution_poll_seconds": int(config.execution_poll_seconds),
                "execution_entry_signal_confirm_seconds": int(config.execution_entry_signal_confirm_seconds),
                "execution_exit_signal_confirm_seconds": int(config.execution_exit_signal_confirm_seconds),
                "execution_entry_fill_latency_seconds": int(config.execution_entry_fill_latency_seconds),
                "execution_exit_fill_latency_seconds": int(config.execution_exit_fill_latency_seconds),
                "delayed_entry_signal_ts": delayed_entry_ts.isoformat(),
                "delayed_exit_signal_ts": delayed_exit_ts.isoformat(),
                "entry_fill_ts": (
                    entry_fill_ts.isoformat()
                    if isinstance(entry_fill_ts, datetime)
                    else str(entry_fill_ts)
                ),
                "exit_fill_ts": (
                    exit_fill_ts.isoformat()
                    if isinstance(exit_fill_ts, datetime)
                    else str(exit_fill_ts)
                ),
                "effective_exit_signal_ts": (
                    effective_exit_ts.isoformat()
                    if isinstance(effective_exit_ts, datetime)
                    else str(effective_exit_ts)
                ),
                "gross_pnl": gross_pnl,
                "contract_expiration": long_contract.get("expiration_date"),
                "contract_strike": float(long_contract.get("strike_price") or 0.0),
                "contract_status": long_contract.get("status"),
                "contract_open_interest": contract_open_interest,
                "contract_open_interest_long_leg": long_contract_open_interest,
                "contract_open_interest_short_leg": short_contract_open_interest if short_option_symbol else None,
                "contract_volume_snapshot": int(long_contract.get("volume") or 0),
                "contract_volume_snapshot_short_leg": (
                    int(short_contract.get("volume") or 0) if isinstance(short_contract, dict) else None
                ),
                "option_structure_filter_enabled": bool(config.option_structure_filter_enabled),
                "option_structure_min_open_interest": int(config.option_structure_min_open_interest),
                "option_structure_min_entry_volume": int(config.option_structure_min_entry_volume),
                "option_structure_max_entry_spread_pct": float(config.option_structure_max_entry_spread_pct),
                "option_structure_max_entry_bar_range_pct": float(config.option_structure_max_entry_bar_range_pct),
                "option_structure_min_entry_price": float(config.option_structure_min_entry_price),
                "option_vertical_short_leg_steps": int(config.option_vertical_short_leg_steps),
                "option_vertical_fallback_short_leg_steps": int(config.option_vertical_fallback_short_leg_steps),
                "option_vertical_max_debit_to_width_ratio": float(config.option_vertical_max_debit_to_width_ratio),
                "option_vertical_min_short_bid": float(config.option_vertical_min_short_bid),
                "option_vertical_max_combined_spread_to_debit_ratio": float(
                    config.option_vertical_max_combined_spread_to_debit_ratio
                ),
                "option_vertical_credit_long_leg_steps": int(config.option_vertical_credit_long_leg_steps),
                "option_vertical_credit_fallback_long_leg_steps": int(
                    config.option_vertical_credit_fallback_long_leg_steps
                ),
                "option_vertical_min_credit_to_width_ratio": float(config.option_vertical_min_credit_to_width_ratio),
                "option_vertical_max_credit_to_width_ratio": float(config.option_vertical_max_credit_to_width_ratio),
                "option_vertical_max_combined_spread_to_credit_ratio": float(
                    config.option_vertical_max_combined_spread_to_credit_ratio
                ),
                "option_credit_min_short_bid": float(config.option_credit_min_short_bid),
                "option_credit_min_short_strike_buffer_pct": float(
                    config.option_credit_min_short_strike_buffer_pct
                ),
                "option_credit_min_expected_move_buffer_ratio": float(
                    config.option_credit_min_expected_move_buffer_ratio
                ),
                "option_credit_min_entry_credit": float(config.option_credit_min_entry_credit),
                "option_credit_take_profit_capture_pct": float(config.option_credit_take_profit_capture_pct),
                "option_credit_stop_loss_multiple": float(config.option_credit_stop_loss_multiple),
                "option_min_expected_move_to_debit_ratio": float(config.option_min_expected_move_to_debit_ratio),
                "liquidity_caps_enabled": bool(config.enforce_option_liquidity_caps),
                "option_sizing_include_commission": bool(config.option_sizing_include_commission),
                "option_sizing_min_entry_price": float(config.option_sizing_min_entry_price),
                "option_risk_sizing_mode": sizing_mode,
                "option_risk_sizing_loss_fraction": float(sizing_loss_fraction),
                "per_contract_risk_capital": float(per_contract_risk_capital),
                "option_max_entry_volume_participation": float(config.option_max_entry_volume_participation),
                "option_max_open_interest_participation": float(config.option_max_open_interest_participation),
                "option_use_contract_open_interest": bool(config.option_use_contract_open_interest),
                "open_interest_liquidity_cap_enabled": bool(
                    config.enforce_option_liquidity_caps
                    and float(config.option_max_open_interest_participation) > 0.0
                ),
                "open_interest_data_available": bool(contract_open_interest > 0),
                "open_interest_cap_applied": bool(
                    config.enforce_option_liquidity_caps
                    and float(config.option_max_open_interest_participation) > 0.0
                    and contract_open_interest > 0
                ),
                "qty_before_liquidity_caps": int(qty_before_liquidity_caps),
                "qty_after_liquidity_caps": int(qty),
                "entry_volume_participation": volume_participation,
                "open_interest_participation": oi_participation,
                "volume_cap_qty": int(volume_cap_qty),
                "open_interest_cap_qty": int(oi_cap_qty),
                "contract_selection_dte": int(long_contract.get("_selection_dte") or 0),
                "contract_selection_moneyness": _safe_float(long_contract.get("_selection_moneyness")),
                "contract_selection_oi_bonus": _safe_float(long_contract.get("_selection_oi_bonus")),
                "contract_selection_score": _safe_float(long_contract.get("_selection_score")),
                "contract_selection_requested_status": str(long_contract.get("_selection_requested_status") or ""),
                "selected_abs_delta": _safe_float(long_contract.get("_selection_abs_delta")),
                "selected_strike_distance_steps": (
                    int(long_contract.get("_selection_strike_distance_steps") or 0)
                    if long_contract.get("_selection_strike_distance_steps") not in (None, "")
                    else None
                ),
                "selected_entry_bar_volume": (
                    int(long_contract.get("_selection_entry_bar_volume") or 0)
                    if long_contract.get("_selection_entry_bar_volume") not in (None, "")
                    else None
                ),
                "selected_quote_spread_pct": _safe_float(long_contract.get("_selection_quote_spread_pct")),
                "contract_selection_intrinsic_value": _safe_float(long_contract.get("_selection_intrinsic_value")),
                "contract_selection_intrinsic_share": _safe_float(long_contract.get("_selection_intrinsic_share")),
                "contract_selection_extrinsic_value": _safe_float(long_contract.get("_selection_extrinsic_value")),
                "expected_move_to_extrinsic_ratio": expected_move_to_extrinsic_ratio,
                "expected_move_to_spread_ratio": expected_move_to_spread_ratio,
            },
        ))

    def _simulate_proxy_option_trade(
        self,
        ticker: str,
        setup: Dict[str, Any],
        exit_plan: Dict[str, Any],
        current_equity: float,
        config: IntradayOptionsBacktestConfig,
    ) -> BacktestTrade:
        direction = int(setup["direction"])
        structure_mode = str(config.option_structure_mode or "single_leg").strip().lower()
        option_leg_count = 2 if structure_mode in {"vertical_debit", "vertical_credit"} else 1
        entry_underlying = float(setup["entry_underlying"])
        exit_underlying = float(exit_plan["exit_underlying"])

        underlying_return = (exit_underlying / entry_underlying) - 1.0
        directional_return = underlying_return if direction > 0 else -underlying_return
        option_return_raw = max(-1.0, directional_return * max(float(config.proxy_option_leverage), 0.0))

        slippage = max(float(config.option_slippage_bps), 0.0) / 10000.0
        entry_price_raw = 1.0
        exit_price_raw = max(0.0, entry_price_raw * (1.0 + option_return_raw))
        entry_price = entry_price_raw * (1.0 + slippage)
        exit_price = max(0.0, exit_price_raw * (1.0 - slippage))

        risk_notional = max(float(current_equity), 0.0) * max(float(config.risk_per_trade), 0.0)
        sizing_mode = str(config.option_risk_sizing_mode or "premium_at_risk").strip().lower()
        sizing_loss_fraction = (
            max(float(config.option_max_loss_pct), 0.0)
            if sizing_mode == "premium_stop" and 0.0 < float(config.option_max_loss_pct) <= 1.0
            else 1.0
        )
        per_contract_risk_capital = (entry_price * 100.0 * sizing_loss_fraction) + (
            max(float(config.option_commission_per_contract), 0.0) * 2.0 * max(int(option_leg_count), 1)
            if bool(config.option_sizing_include_commission)
            else 0.0
        )
        qty = _option_qty_for_risk(
            risk_notional=risk_notional,
            entry_price=entry_price,
            commission_per_contract=float(config.option_commission_per_contract),
            include_commission=bool(config.option_sizing_include_commission),
            min_entry_price=float(config.option_sizing_min_entry_price),
            sizing_mode=sizing_mode,
            option_max_loss_pct=float(config.option_max_loss_pct),
            option_leg_count=int(option_leg_count),
        )
        if qty < 1:
            qty = 1
        gross_pnl = (
            qty * (entry_price - exit_price) * 100.0
            if structure_mode == "vertical_credit"
            else qty * (exit_price - entry_price) * 100.0
        )
        commission = qty * max(float(config.option_commission_per_contract), 0.0) * 2.0 * max(
            int(option_leg_count),
            1,
        )
        pnl = gross_pnl - commission
        invested = qty * entry_price * 100.0
        trade_return = (pnl / invested) if invested > 0 else 0.0

        return BacktestTrade(
            trade_id=str(uuid.uuid4()),
            signal_id=str(uuid.uuid4()),
            ticker=ticker,
            option_symbol=f"PROXY:{ticker}",
            entry_ts=setup["entry_ts"],
            exit_ts=exit_plan["exit_ts"],
            side=(
                "bull_put_credit"
                if structure_mode == "vertical_credit" and direction > 0
                else (
                    "bear_call_credit"
                    if structure_mode == "vertical_credit"
                    else ("long_call" if direction > 0 else "long_put")
                )
            ),
            qty=qty,
            entry_price=entry_price,
            exit_price=exit_price,
            pnl=pnl,
            return_pct=trade_return,
            status="closed",
            metadata={
                "strategy": "intraday_opening_range_stocks_in_play_options",
                "strategy_variant": str(setup.get("strategy_variant") or config.strategy_variant),
                "execution_mode": "proxy",
                "option_structure_mode": structure_mode,
                "option_leg_count": int(option_leg_count),
                "direction": direction,
                "entry_underlying": entry_underlying,
                "exit_underlying": exit_underlying,
                "underlying_return": underlying_return,
                "proxy_option_return_raw": option_return_raw,
                "proxy_option_leverage": float(config.proxy_option_leverage),
                "option_sizing_include_commission": bool(config.option_sizing_include_commission),
                "option_sizing_min_entry_price": float(config.option_sizing_min_entry_price),
                "option_risk_sizing_mode": sizing_mode,
                "option_risk_sizing_loss_fraction": float(sizing_loss_fraction),
                "per_contract_risk_capital": float(per_contract_risk_capital),
                "stop_underlying": float(setup["stop_underlying"]),
                "exit_reason": str(exit_plan["exit_reason"]),
                "orb_high": float(setup["orb_high"]),
                "orb_low": float(setup["orb_low"]),
                "opening_range_minutes": int(setup.get("opening_range_minutes") or 0),
                "opening_bar_direction": int(setup.get("opening_bar_direction") or 0),
                "trend_ema_fast": float(setup["trend_ema_fast"]),
                "trend_ema_slow": float(setup["trend_ema_slow"]),
                "volume_ratio": float(setup["volume_ratio"]),
                "relative_opening_volume": _safe_float(setup.get("relative_opening_volume")),
                "atr_value": _safe_float(setup.get("atr_value")),
                "vol_regime_prev_close": _safe_float(setup.get("vol_regime_prev_close")),
                "market_regime_label": _normalize_regime_label(setup.get("market_regime_label")),
                "regime_v2_state": str(setup.get("regime_v2_state") or "unknown"),
                "regime_v2_route_state": str(setup.get("regime_v2_route_state") or "unknown"),
                "regime_v2_route_action": str(setup.get("regime_v2_route_action") or ""),
                "regime_v2_confidence": _safe_float(setup.get("regime_v2_confidence")),
                "regime_v2_selected_variant": str(setup.get("regime_v2_selected_variant") or ""),
                "regime_v2_skip_reason": str(setup.get("regime_v2_skip_reason") or ""),
                "regime_v2_route_overlay_name": str(setup.get("regime_v2_route_overlay_name") or ""),
                "fvg_gap": float(setup["fvg_gap"]),
                "fib_anchor": _safe_float(setup.get("fib_anchor")),
                "fib_impulse_extreme": _safe_float(setup.get("fib_impulse_extreme")),
                "fib_entry_zone_low": _safe_float(setup.get("fib_entry_zone_low")),
                "fib_entry_zone_high": _safe_float(setup.get("fib_entry_zone_high")),
                "entry_price_raw": entry_price_raw,
                "exit_price_raw": exit_price_raw,
                "entry_price_effective": entry_price,
                "exit_price_effective": exit_price,
                "option_slippage_bps": float(config.option_slippage_bps),
                "option_commission_total": commission,
                "gross_pnl": gross_pnl,
            },
        )

    def _simulate_stock_trade(
        self,
        ticker: str,
        setup: Dict[str, Any],
        exit_plan: Dict[str, Any],
        current_equity: float,
        config: IntradayOptionsBacktestConfig,
    ) -> Optional[BacktestTrade]:
        direction = int(setup["direction"])
        entry_raw = float(setup["entry_underlying"])
        exit_raw = float(exit_plan["exit_underlying"])
        stop_underlying = float(setup["stop_underlying"])
        if entry_raw <= 0 or exit_raw <= 0:
            return None

        stop_distance = abs(entry_raw - stop_underlying)
        if stop_distance <= 0:
            return None

        max_positions = max(int(config.max_positions), 1)
        stop_risk_size = max(float(config.stop_loss_risk_size), 0.0)
        risk_budget = (float(current_equity) * stop_risk_size) / float(max_positions)
        qty_risk = int(risk_budget / stop_distance)
        qty_cap = int((float(current_equity) / float(max_positions)) / entry_raw)
        qty = min(qty_risk, qty_cap)
        if qty < 1:
            return None

        slippage = max(float(config.stock_slippage_bps), 0.0) / 10000.0
        if direction > 0:
            entry_price = entry_raw * (1.0 + slippage)
            exit_price = max(0.0, exit_raw * (1.0 - slippage))
            gross_pnl = qty * (exit_price - entry_price)
        else:
            entry_price = entry_raw * (1.0 - slippage)
            exit_price = exit_raw * (1.0 + slippage)
            gross_pnl = qty * (entry_price - exit_price)

        commission = qty * max(float(config.stock_commission_per_share), 0.0) * 2.0
        pnl = gross_pnl - commission
        invested = qty * entry_price
        trade_return = (pnl / invested) if invested > 0 else 0.0

        return BacktestTrade(
            trade_id=str(uuid.uuid4()),
            signal_id=str(uuid.uuid4()),
            ticker=ticker,
            option_symbol=f"STOCK:{ticker}",
            entry_ts=setup["entry_ts"],
            exit_ts=exit_plan["exit_ts"],
            side="long_stock" if direction > 0 else "short_stock",
            qty=qty,
            entry_price=entry_price,
            exit_price=exit_price,
            pnl=pnl,
            return_pct=trade_return,
            status="closed",
            metadata={
                "strategy": "intraday_opening_range_stocks_in_play_options",
                "strategy_variant": str(setup.get("strategy_variant") or config.strategy_variant),
                "execution_mode": "stocks",
                "direction": direction,
                "entry_underlying": entry_raw,
                "exit_underlying": exit_raw,
                "stop_underlying": stop_underlying,
                "exit_reason": str(exit_plan["exit_reason"]),
                "orb_high": float(setup["orb_high"]),
                "orb_low": float(setup["orb_low"]),
                "opening_range_minutes": int(setup.get("opening_range_minutes") or 0),
                "opening_bar_direction": int(setup.get("opening_bar_direction") or 0),
                "relative_opening_volume": _safe_float(setup.get("relative_opening_volume")),
                "atr_value": _safe_float(setup.get("atr_value")),
                "vol_regime_prev_close": _safe_float(setup.get("vol_regime_prev_close")),
                "market_regime_label": _normalize_regime_label(setup.get("market_regime_label")),
                "regime_v2_state": str(setup.get("regime_v2_state") or "unknown"),
                "regime_v2_route_state": str(setup.get("regime_v2_route_state") or "unknown"),
                "regime_v2_route_action": str(setup.get("regime_v2_route_action") or ""),
                "regime_v2_confidence": _safe_float(setup.get("regime_v2_confidence")),
                "regime_v2_selected_variant": str(setup.get("regime_v2_selected_variant") or ""),
                "regime_v2_skip_reason": str(setup.get("regime_v2_skip_reason") or ""),
                "regime_v2_route_overlay_name": str(setup.get("regime_v2_route_overlay_name") or ""),
                "fib_anchor": _safe_float(setup.get("fib_anchor")),
                "fib_impulse_extreme": _safe_float(setup.get("fib_impulse_extreme")),
                "fib_entry_zone_low": _safe_float(setup.get("fib_entry_zone_low")),
                "fib_entry_zone_high": _safe_float(setup.get("fib_entry_zone_high")),
                "max_positions": max_positions,
                "stop_loss_risk_size": stop_risk_size,
                "stop_distance": stop_distance,
                "qty_risk": qty_risk,
                "qty_cap": qty_cap,
                "stock_slippage_bps": float(config.stock_slippage_bps),
                "stock_commission_total": commission,
                "gross_pnl": gross_pnl,
            },
        )

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
            )
            and isinstance(selection_ts, datetime)
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
        ) -> Tuple[Optional[Dict[str, Any]], bool]:
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
                return None, had_filtered_candidates
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
            use_nearest_strike_delta_fallback = delta_fallback_mode == "nearest_strike"
            entry_bar_volume_weight = max(
                float(getattr(config, "option_selection_entry_bar_volume_weight", 0.0) or 0.0),
                0.0,
            )
            multi_candidate_mode = bool(spread_mode or use_local_strike_band or entry_bar_volume_weight > 0.0)
            if use_local_strike_band:
                top_n = max(top_n, 1 + local_itm_steps + local_otm_steps)
            shortlisted = ranked[:top_n] if multi_candidate_mode else ranked[:1]
            selected_score: Optional[float] = None
            selected_candidate: Optional[_ContractCandidate] = None
            selected_dte = 0
            selected_moneyness = 0.0
            selected_oi_bonus = 0.0
            selected_quote_spread_pct: Optional[float] = None
            selected_quote_spread_abs: Optional[float] = None
            selected_quote_spread_to_ask_ratio: Optional[float] = None
            selected_intrinsic_value: Optional[float] = None
            selected_intrinsic_share: Optional[float] = None
            selected_extrinsic_value: Optional[float] = None
            selected_abs_delta: Optional[float] = None
            selected_strike_distance_steps: Optional[int] = None
            selected_delta_fallback_used = False
            selected_quote_used = False
            selected_entry_bar_volume: Optional[int] = None
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
                    quote = self._lookup_option_quote_on_or_after(
                        symbol=symbol,
                        day=day,
                        ts=selection_ts_effective,
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
                if selected_score is None or score < selected_score:
                    selected_score = score
                    selected_candidate = candidate
                    selected_dte = int(dte)
                    selected_moneyness = float(moneyness)
                    selected_oi_bonus = float(oi_bonus)
                    selected_quote_spread_pct = quote_spread_pct
                    selected_quote_spread_abs = quote_spread_abs
                    selected_quote_spread_to_ask_ratio = quote_spread_to_ask_ratio
                    selected_intrinsic_value = intrinsic_value
                    selected_intrinsic_share = intrinsic_share
                    selected_extrinsic_value = extrinsic_value
                    selected_abs_delta = abs_delta
                    selected_delta_fallback_used = bool(delta_fallback_used)
                    selected_quote_used = quote_used
                    selected_entry_bar_volume = entry_bar_volume
            if selected_candidate is None:
                return None, had_filtered_candidates
            expiry_candidates = list(grouped_candidates.ascending_by_expiration.get(selected_candidate.expiration_day) or [])
            if expiry_candidates:
                nearest_candidate = min(
                    expiry_candidates,
                    key=lambda candidate: (
                        abs(float(candidate.strike) - float(entry_underlying)),
                        0 if float(candidate.strike) >= float(entry_underlying) else 1,
                        abs((candidate.expiration_day - selected_candidate.expiration_day).days),
                    ),
                )
                nearest_symbol = str(nearest_candidate.contract.get("symbol") or "").strip()
                selected_symbol = str(selected_candidate.contract.get("symbol") or "").strip()
                nearest_idx = next(
                    (
                        idx
                        for idx, candidate in enumerate(expiry_candidates)
                        if str(candidate.contract.get("symbol") or "").strip() == nearest_symbol
                    ),
                    0,
                )
                selected_idx = next(
                    (
                        idx
                        for idx, candidate in enumerate(expiry_candidates)
                        if str(candidate.contract.get("symbol") or "").strip() == selected_symbol
                    ),
                    nearest_idx,
                )
                selected_strike_distance_steps = abs(int(selected_idx) - int(nearest_idx))
            selected = dict(selected_candidate.contract)
            selected["_selection_dte"] = int(selected_dte)
            selected["_selection_moneyness"] = float(selected_moneyness)
            selected["_selection_oi_bonus"] = float(selected_oi_bonus)
            selected["_selection_score"] = float(selected_score or 0.0)
            selected["_selection_requested_status"] = str(contract_status)
            selected["_selection_quote_spread_pct"] = (
                float(selected_quote_spread_pct) if selected_quote_spread_pct is not None else None
            )
            selected["_selection_quote_spread_abs"] = (
                float(selected_quote_spread_abs) if selected_quote_spread_abs is not None else None
            )
            selected["_selection_quote_spread_to_ask_ratio"] = (
                float(selected_quote_spread_to_ask_ratio)
                if selected_quote_spread_to_ask_ratio is not None
                else None
            )
            selected["_selection_intrinsic_value"] = (
                float(selected_intrinsic_value) if selected_intrinsic_value is not None else None
            )
            selected["_selection_intrinsic_share"] = (
                float(selected_intrinsic_share) if selected_intrinsic_share is not None else None
            )
            selected["_selection_extrinsic_value"] = (
                float(selected_extrinsic_value) if selected_extrinsic_value is not None else None
            )
            selected["_selection_abs_delta"] = float(selected_abs_delta) if selected_abs_delta is not None else None
            selected["_selection_strike_distance_steps"] = (
                int(selected_strike_distance_steps) if selected_strike_distance_steps is not None else None
            )
            selected["_selection_delta_fallback_mode"] = str(delta_fallback_mode)
            selected["_selection_delta_fallback_used"] = bool(selected_delta_fallback_used)
            selected["_selection_quote_used"] = bool(selected_quote_used)
            selected["_selection_local_itm_steps"] = int(local_itm_steps)
            selected["_selection_local_otm_steps"] = int(local_otm_steps)
            selected["_selection_local_strike_band_size"] = int(local_strike_band_size)
            selected["_selection_entry_bar_volume"] = (
                int(selected_entry_bar_volume) if selected_entry_bar_volume is not None else None
            )
            selected["_selection_entry_bar_volume_weight"] = float(entry_bar_volume_weight)
            selected["_selection_quote_max_spread_abs_filter"] = (
                float(max_quote_spread_abs) if max_quote_spread_abs > 0.0 else None
            )
            selected["_selection_quote_max_spread_to_ask_filter"] = (
                float(max_spread_to_ask_ratio) if max_spread_to_ask_ratio > 0.0 else None
            )
            selected["_selection_quote_min_ask_filter"] = (
                float(min_quote_ask) if min_quote_ask > 0.0 else None
            )
            return selected, had_filtered_candidates

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
        selected, had_filtered_candidates = _rank_contracts(
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
            selected, had_filtered_candidates = _rank_contracts(
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
        long_quote = self._lookup_option_quote_on_or_after(
            symbol=long_symbol,
            day=day,
            ts=selection_ts_effective,
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
            quote = self._lookup_option_quote_on_or_after(
                symbol=short_symbol,
                day=day,
                ts=selection_ts_effective,
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
        short_quote = self._lookup_option_quote_on_or_after(
            symbol=short_symbol,
            day=day,
            ts=selection_ts_effective,
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
            quote = self._lookup_option_quote_on_or_after(
                symbol=long_symbol,
                day=day,
                ts=selection_ts_effective,
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

    def _load_option_bars(self, symbol: str, day: date) -> List[Dict[str, Any]]:
        cache_key = (symbol, day)
        if cache_key in self._option_bar_cache:
            return self._option_bar_cache[cache_key]
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

    def _load_option_bars_uncached(self, *, symbol: str, day: date) -> List[Dict[str, Any]]:
        start_dt = datetime.combine(day, time(0, 0))
        end_dt = datetime.combine(day, time(23, 59, 59))
        started_at = perf_counter()
        existing = self.store.get_option_bars(symbol=symbol, start=start_dt, end=end_dt)
        duckdb_seconds = perf_counter() - started_at
        if existing:
            self._record_option_market_data_io(
                dataset="option_bars",
                total_seconds=duckdb_seconds,
                duckdb_seconds=duckdb_seconds,
                loaded_count=1,
                duckdb_calls=1,
            )
            return existing

        mapped: List[Dict[str, Any]] = []
        provider_seconds = 0.0
        provider_calls = 0
        if self.cutemarkets_provider is not None:
            provider_started_at = perf_counter()
            try:
                mapped = list(
                    self.cutemarkets_provider.fetch_option_bars(
                        option_symbol=symbol,
                        start=day,
                        end=day + timedelta(days=1),
                        multiplier=1,
                        timespan="minute",
                    )
                    or []
                )
            except Exception:
                mapped = []
            provider_seconds += perf_counter() - provider_started_at
            provider_calls += 1

        if not mapped and self.alpaca_data_provider is not None:
            provider_started_at = perf_counter()
            try:
                fetched = self.alpaca_data_provider.fetch_option_bars(
                    symbol=symbol,
                    start=day.isoformat(),
                    end=(day + timedelta(days=1)).isoformat(),
                    timeframe="1Min",
                    limit=10000,
                )
            except Exception:
                fetched = []
            provider_seconds += perf_counter() - provider_started_at
            provider_calls += 1
            mapped = [_map_alpaca_option_bar(symbol=symbol, row=row) for row in fetched]
            mapped = [row for row in mapped if row is not None]

        if mapped:
            if self._persist_fetched_market_data:
                self.store.insert_option_bars(mapped)
            rows = self._merge_rows_by_ts(existing, mapped)
        else:
            rows = existing
        self._record_option_market_data_io(
            dataset="option_bars",
            total_seconds=duckdb_seconds + provider_seconds,
            duckdb_seconds=duckdb_seconds,
            provider_seconds=provider_seconds,
            loaded_count=1,
            duckdb_calls=1,
            provider_calls=provider_calls,
        )
        return rows

    @staticmethod
    def _merge_rows_by_ts(*row_groups: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
        dedup: Dict[datetime, Dict[str, Any]] = {}
        for rows in row_groups:
            for row in rows:
                ts = row.get("ts")
                if not isinstance(ts, datetime):
                    continue
                normalized_row = dict(row)
                normalized_row["ts"] = _as_utc_naive(ts)
                dedup[normalized_row["ts"]] = normalized_row
        return [dedup[key] for key in sorted(dedup)]

    def _load_option_quotes(self, symbol: str, day: date) -> List[Dict[str, Any]]:
        if self._historical_option_quotes_supported is False and self.cutemarkets_provider is None:
            return []
        cache_key = (symbol, day)
        if cache_key in self._option_quote_cache:
            return self._option_quote_cache[cache_key]
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

    def _load_option_quotes_uncached(self, *, symbol: str, day: date) -> List[Dict[str, Any]]:
        start_iso = datetime.combine(day, time(0, 0), tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
        end_iso = datetime.combine(day + timedelta(days=1), time(0, 0), tzinfo=timezone.utc).isoformat().replace(
            "+00:00",
            "Z",
        )

        rows: List[Dict[str, Any]] = []
        duckdb_seconds = 0.0
        provider_seconds = 0.0
        provider_calls = 0

        started_at = perf_counter()
        get_option_quotes = getattr(self.store, "get_option_quotes", None)
        if callable(get_option_quotes):
            try:
                rows = list(
                    get_option_quotes(
                        symbol=symbol,
                        start=datetime.combine(day, time(0, 0)),
                        end=datetime.combine(day + timedelta(days=1), time(0, 0)),
                    )
                )
            except Exception:
                rows = []
        duckdb_seconds = perf_counter() - started_at
        if rows:
            rows.sort(key=lambda item: item["ts"])
            self._record_option_market_data_io(
                dataset="option_quotes",
                total_seconds=duckdb_seconds + provider_seconds,
                duckdb_seconds=duckdb_seconds,
                provider_seconds=provider_seconds,
                loaded_count=1,
                duckdb_calls=1,
                provider_calls=provider_calls,
            )
            return rows

        if self.cutemarkets_provider is not None:
            provider_started_at = perf_counter()
            try:
                cutemarkets_rows = self.cutemarkets_provider.fetch_option_quotes(
                    option_symbol=symbol,
                    start=datetime.combine(day, time(0, 0), tzinfo=timezone.utc),
                    end=datetime.combine(day + timedelta(days=1), time(0, 0), tzinfo=timezone.utc),
                    limit=0,
                )
            except Exception:
                cutemarkets_rows = []
            provider_seconds += perf_counter() - provider_started_at
            provider_calls += 1
            for row in cutemarkets_rows:
                ts = row.get("ts")
                if not isinstance(ts, datetime):
                    continue
                if _as_et(ts).date() != day:
                    continue
                rows.append(row)
        if rows:
            rows.sort(key=lambda item: item["ts"])
            self._record_option_market_data_io(
                dataset="option_quotes",
                total_seconds=duckdb_seconds + provider_seconds,
                duckdb_seconds=duckdb_seconds,
                provider_seconds=provider_seconds,
                loaded_count=1,
                duckdb_calls=1 if callable(get_option_quotes) else 0,
                provider_calls=provider_calls,
            )
            return rows

        if self.alpaca_data_provider is not None and self._historical_option_quotes_supported is not False:
            provider_started_at = perf_counter()
            try:
                fetched = self.alpaca_data_provider.fetch_option_quotes(
                    symbol=symbol,
                    start=start_iso,
                    end=end_iso,
                    limit=10000,
                )
            except Exception:
                fetched = []
            provider_seconds += perf_counter() - provider_started_at
            provider_calls += 1
            if fetched:
                self._historical_option_quotes_supported = True
                mapped = [_map_alpaca_option_quote(symbol=symbol, row=row) for row in fetched]
                for row in mapped:
                    ts = row.get("ts")
                    if row is None or not isinstance(ts, datetime):
                        continue
                    if _as_et(ts).date() != day:
                        continue
                    rows.append(row)
            else:
                provider_support = getattr(self.alpaca_data_provider, "_historical_option_quotes_supported", None)
                if isinstance(provider_support, bool) and not provider_support:
                    self._historical_option_quotes_supported = False

        rows.sort(key=lambda item: item["ts"])
        self._record_option_market_data_io(
            dataset="option_quotes",
            total_seconds=duckdb_seconds + provider_seconds,
            duckdb_seconds=duckdb_seconds,
            provider_seconds=provider_seconds,
            loaded_count=1,
            duckdb_calls=1,
            provider_calls=provider_calls,
        )
        return rows


def _map_alpaca_option_bar(symbol: str, row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    ts = parse_datetime(row.get("t"))
    if ts is None:
        return None
    return {
        "symbol": symbol,
        "ts": _as_utc_naive(ts),
        "open": float(row.get("o") or 0.0),
        "high": float(row.get("h") or 0.0),
        "low": float(row.get("l") or 0.0),
        "close": float(row.get("c") or 0.0),
        "volume": int(row.get("v") or 0),
    }


def _map_alpaca_option_quote(symbol: str, row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    ts = parse_datetime(row.get("t"))
    if ts is None:
        return None
    bid = _safe_float(row.get("bp", row.get("bid_price")))
    ask = _safe_float(row.get("ap", row.get("ask_price")))
    if bid is not None and bid < 0:
        bid = None
    if ask is not None and ask < 0:
        ask = None
    if bid is None and ask is None:
        return None
    return {
        "symbol": symbol,
        "ts": _as_utc_naive(ts),
        "bid": bid,
        "ask": ask,
        "bid_size": int(row.get("bs", row.get("bid_size")) or 0),
        "ask_size": int(row.get("as", row.get("ask_size")) or 0),
    }


def _map_alpaca_stock_bar(ticker: str, row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    ts = parse_datetime(row.get("t"))
    if ts is None:
        return None
    return {
        "ticker": ticker,
        "ts": _as_utc_naive(ts),
        "open": float(row.get("o") or 0.0),
        "high": float(row.get("h") or 0.0),
        "low": float(row.get("l") or 0.0),
        "close": float(row.get("c") or 0.0),
        "volume": int(row.get("v") or 0),
    }


@lru_cache(maxsize=262144)
def _as_utc_aware(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


@lru_cache(maxsize=262144)
def _as_utc_naive(ts: datetime) -> datetime:
    return _as_utc_aware(ts).replace(tzinfo=None)


@lru_cache(maxsize=262144)
def _as_et(ts: datetime) -> datetime:
    return _as_utc_aware(ts).astimezone(_ET_ZONE)


def _parse_hhmm(value: str, default_value: str) -> time:
    text = (value or "").strip() or default_value
    try:
        hour_text, minute_text = text.split(":", 1)
        hour = max(0, min(23, int(hour_text)))
        minute = max(0, min(59, int(minute_text)))
        return time(hour=hour, minute=minute)
    except (TypeError, ValueError):
        hour_text, minute_text = default_value.split(":", 1)
        return time(hour=int(hour_text), minute=int(minute_text))


def _default_entry_start(opening_range_minutes: int) -> str:
    effective = max(int(opening_range_minutes), 1)
    minute_total = (9 * 60) + 30 + effective
    hour = minute_total // 60
    minute = minute_total % 60
    return f"{hour:02d}:{minute:02d}"


def _bars_through_et_time(bars: Sequence[Dict[str, Any]], cutoff_time: time) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for bar in bars:
        ts = bar.get("ts")
        if not isinstance(ts, datetime):
            continue
        bar_time = _as_et(ts).time()
        if bar_time <= cutoff_time:
            out.append(bar)
            continue
        # Session bars arrive in chronological order, so nothing later can re-enter.
        break
    return out


def _iter_dates(start_day: date, end_day: date) -> List[date]:
    days: List[date] = []
    cur = start_day
    while cur <= end_day:
        days.append(cur)
        cur += timedelta(days=1)
    return days


def _first_bar_on_or_after(
    bars: List[Dict[str, Any]],
    ts: datetime,
    fallback_last: bool = False,
) -> Optional[Dict[str, Any]]:
    target_ts = _as_utc_aware(ts)
    for bar in bars:
        bar_ts = bar.get("ts")
        if not isinstance(bar_ts, datetime):
            continue
        if _as_utc_aware(bar_ts) >= target_ts:
            return bar
    if fallback_last and bars:
        return bars[-1]
    return None


def _bar_index_by_ts(bars: List[Dict[str, Any]], ts: datetime) -> Optional[int]:
    for idx, bar in enumerate(bars):
        if bar.get("ts") == ts:
            return idx
    return None


def _next_observable_exit_target(
    *,
    scan_bars: Sequence[Dict[str, Any]],
    trigger_index: int,
    default_exit_bar: Dict[str, Any],
    default_exit_ts: datetime,
) -> Tuple[Dict[str, Any], datetime]:
    next_index = int(trigger_index) + 1
    if 0 <= next_index < len(scan_bars):
        next_bar = scan_bars[next_index]
        next_ts = next_bar.get("ts")
        if isinstance(next_ts, datetime):
            return next_bar, next_ts
        return next_bar, default_exit_ts
    trigger_bar = scan_bars[trigger_index] if 0 <= int(trigger_index) < len(scan_bars) else {}
    trigger_ts = trigger_bar.get("ts")
    if isinstance(trigger_ts, datetime):
        return default_exit_bar, _as_utc_aware(trigger_ts) + timedelta(minutes=1)
    return default_exit_bar, default_exit_ts


def _quotes_in_window(
    *,
    same_day_quotes: Sequence[Dict[str, Any]],
    exit_day_quotes: Sequence[Dict[str, Any]],
    day: date,
    exit_day: date,
    start_ts: datetime,
    end_ts: datetime,
) -> List[Dict[str, Any]]:
    start_utc = _as_utc_aware(start_ts)
    end_utc = _as_utc_aware(end_ts)
    rows: List[Dict[str, Any]] = []

    def _extend(quotes: Sequence[Dict[str, Any]]) -> None:
        for quote in quotes:
            quote_ts = quote.get("ts")
            if not isinstance(quote_ts, datetime):
                continue
            quote_utc = _as_utc_aware(quote_ts)
            if start_utc <= quote_utc <= end_utc:
                rows.append(quote)

    _extend(same_day_quotes)
    if exit_day != day:
        _extend(exit_day_quotes)
    rows.sort(key=lambda row: _as_utc_aware(row["ts"]))
    return rows


def _iter_quote_pairs_in_window(
    *,
    primary_same_day_quotes: Sequence[Dict[str, Any]],
    primary_exit_day_quotes: Sequence[Dict[str, Any]],
    secondary_same_day_quotes: Sequence[Dict[str, Any]],
    secondary_exit_day_quotes: Sequence[Dict[str, Any]],
    day: date,
    exit_day: date,
    start_ts: datetime,
    end_ts: datetime,
) -> Iterator[Tuple[datetime, Dict[str, Any], Dict[str, Any]]]:
    primary_quotes = _quotes_in_window(
        same_day_quotes=primary_same_day_quotes,
        exit_day_quotes=primary_exit_day_quotes,
        day=day,
        exit_day=exit_day,
        start_ts=start_ts,
        end_ts=end_ts,
    )
    secondary_quotes = _quotes_in_window(
        same_day_quotes=secondary_same_day_quotes,
        exit_day_quotes=secondary_exit_day_quotes,
        day=day,
        exit_day=exit_day,
        start_ts=start_ts,
        end_ts=end_ts,
    )
    if not primary_quotes or not secondary_quotes:
        return

    timeline = sorted(
        {
            _as_utc_aware(quote["ts"])
            for quote in list(primary_quotes) + list(secondary_quotes)
            if isinstance(quote.get("ts"), datetime)
        }
    )
    primary_index = 0
    secondary_index = 0
    latest_primary: Optional[Dict[str, Any]] = None
    latest_secondary: Optional[Dict[str, Any]] = None
    for ts in timeline:
        while primary_index < len(primary_quotes):
            current = primary_quotes[primary_index]
            current_ts = current.get("ts")
            if not isinstance(current_ts, datetime) or _as_utc_aware(current_ts) > ts:
                break
            latest_primary = current
            primary_index += 1
        while secondary_index < len(secondary_quotes):
            current = secondary_quotes[secondary_index]
            current_ts = current.get("ts")
            if not isinstance(current_ts, datetime) or _as_utc_aware(current_ts) > ts:
                break
            latest_secondary = current
            secondary_index += 1
        if latest_primary is None or latest_secondary is None:
            continue
        yield ts, latest_primary, latest_secondary


def _apply_option_premium_stop_from_quotes(
    *,
    entry_price_raw: float,
    option_take_profit_pct: float,
    option_max_loss_pct: float,
    entry_fill_ts: datetime,
    default_exit_bar: Dict[str, Any],
    default_exit_reason: str,
    default_exit_ts: datetime,
    same_day_quotes: Sequence[Dict[str, Any]],
    exit_day_quotes: Sequence[Dict[str, Any]],
    day: date,
    exit_day: date,
) -> Dict[str, Any]:
    selected_exit_bar = default_exit_bar
    exit_raw = 0.0
    effective_exit_reason = str(default_exit_reason or "")
    effective_exit_ts = default_exit_ts
    premium_take_profit_triggered = False
    premium_take_profit_price_raw: Optional[float] = None
    option_premium_stop_triggered = False
    option_premium_stop_price_raw: Optional[float] = None

    take_profit_price_raw = (
        entry_price_raw * (1.0 + option_take_profit_pct)
        if option_take_profit_pct > 0 and entry_price_raw > 0
        else None
    )
    stop_price_raw = (
        entry_price_raw * (1.0 - option_max_loss_pct)
        if option_max_loss_pct > 0 and entry_price_raw > 0
        else None
    )
    scan_quotes = _quotes_in_window(
        same_day_quotes=same_day_quotes,
        exit_day_quotes=exit_day_quotes,
        day=day,
        exit_day=exit_day,
        start_ts=entry_fill_ts,
        end_ts=default_exit_ts,
    )
    for quote in scan_quotes:
        quote_ts = quote.get("ts")
        if not isinstance(quote_ts, datetime):
            continue
        exit_mark = _safe_float(quote.get("bid"))
        if exit_mark is None or exit_mark <= 0.0:
            continue
        if stop_price_raw is not None and exit_mark <= stop_price_raw:
            option_premium_stop_triggered = True
            option_premium_stop_price_raw = max(stop_price_raw, 0.0)
            effective_exit_reason = "option_premium_stop"
            effective_exit_ts = quote_ts
            exit_raw = exit_mark
            break
        if take_profit_price_raw is not None and exit_mark >= take_profit_price_raw:
            premium_take_profit_triggered = True
            premium_take_profit_price_raw = max(take_profit_price_raw, 0.0)
            effective_exit_reason = "premium_take_profit"
            effective_exit_ts = quote_ts
            exit_raw = exit_mark
            break

    return {
        "exit_bar": selected_exit_bar,
        "exit_raw": exit_raw,
        "effective_exit_reason": effective_exit_reason,
        "effective_exit_ts": effective_exit_ts,
        "premium_take_profit_triggered": premium_take_profit_triggered,
        "premium_take_profit_price_raw": premium_take_profit_price_raw,
        "option_premium_stop_triggered": option_premium_stop_triggered,
        "option_premium_stop_price_raw": option_premium_stop_price_raw,
    }


def _apply_vertical_debit_premium_exits_from_quotes(
    *,
    entry_debit_raw: float,
    option_take_profit_pct: float,
    option_max_loss_pct: float,
    entry_fill_ts: datetime,
    default_exit_bar: Dict[str, Any],
    default_exit_reason: str,
    default_exit_ts: datetime,
    long_same_day_quotes: Sequence[Dict[str, Any]],
    long_exit_day_quotes: Sequence[Dict[str, Any]],
    short_same_day_quotes: Sequence[Dict[str, Any]],
    short_exit_day_quotes: Sequence[Dict[str, Any]],
    day: date,
    exit_day: date,
) -> Dict[str, Any]:
    selected_exit_bar = default_exit_bar
    effective_exit_reason = str(default_exit_reason or "")
    effective_exit_ts = default_exit_ts
    premium_take_profit_triggered = False
    option_premium_stop_triggered = False
    premium_stop_triggered = False
    option_premium_stop_price_raw: Optional[float] = None
    exit_raw = 0.0

    take_profit_mark = (
        entry_debit_raw * (1.0 + option_take_profit_pct)
        if entry_debit_raw > 0.0 and option_take_profit_pct > 0.0
        else None
    )
    stop_mark = (
        entry_debit_raw * (1.0 - option_max_loss_pct)
        if entry_debit_raw > 0.0 and option_max_loss_pct > 0.0
        else None
    )
    for ts, long_quote, short_quote in _iter_quote_pairs_in_window(
        primary_same_day_quotes=long_same_day_quotes,
        primary_exit_day_quotes=long_exit_day_quotes,
        secondary_same_day_quotes=short_same_day_quotes,
        secondary_exit_day_quotes=short_exit_day_quotes,
        day=day,
        exit_day=exit_day,
        start_ts=entry_fill_ts,
        end_ts=default_exit_ts,
    ):
        long_bid = _safe_float(long_quote.get("bid"))
        short_ask = _safe_float(short_quote.get("ask"))
        if long_bid is None or long_bid <= 0.0 or short_ask is None or short_ask <= 0.0:
            continue
        spread_mark = max(float(long_bid) - float(short_ask), 0.0)
        if stop_mark is not None and spread_mark <= stop_mark:
            effective_exit_reason = "option_premium_stop"
            effective_exit_ts = ts
            option_premium_stop_triggered = True
            premium_stop_triggered = True
            option_premium_stop_price_raw = max(stop_mark, 0.0)
            exit_raw = spread_mark
            break
        if take_profit_mark is not None and spread_mark >= take_profit_mark:
            effective_exit_reason = "premium_take_profit"
            effective_exit_ts = ts
            premium_take_profit_triggered = True
            exit_raw = spread_mark
            break

    return {
        "exit_bar": selected_exit_bar,
        "exit_raw": exit_raw,
        "effective_exit_reason": effective_exit_reason,
        "effective_exit_ts": effective_exit_ts,
        "premium_take_profit_triggered": premium_take_profit_triggered,
        "premium_stop_triggered": premium_stop_triggered,
        "option_premium_stop_triggered": option_premium_stop_triggered,
        "option_premium_stop_price_raw": option_premium_stop_price_raw,
    }


def _apply_option_premium_stop(
    *,
    entry_price_raw: float,
    option_take_profit_pct: float,
    option_max_loss_pct: float,
    entry_bar: Dict[str, Any],
    exit_bar: Dict[str, Any],
    entry_bars: List[Dict[str, Any]],
    exit_bars: List[Dict[str, Any]],
    day: date,
    exit_day: date,
    default_exit_reason: str,
    default_exit_ts: datetime,
) -> Dict[str, Any]:
    selected_exit_bar = exit_bar
    exit_raw = _causal_bar_fill_price(selected_exit_bar)
    effective_exit_reason = str(default_exit_reason or "")
    effective_exit_ts = default_exit_ts
    premium_take_profit_triggered = False
    premium_take_profit_price_raw: Optional[float] = None
    option_premium_stop_triggered = False
    option_premium_stop_price_raw: Optional[float] = None

    take_profit_price_raw = (
        entry_price_raw * (1.0 + option_take_profit_pct)
        if option_take_profit_pct > 0 and entry_price_raw > 0
        else None
    )
    stop_price_raw = (
        entry_price_raw * (1.0 - option_max_loss_pct)
        if option_max_loss_pct > 0 and entry_price_raw > 0
        else None
    )

    if take_profit_price_raw is not None or stop_price_raw is not None:
        scan_bars: List[Dict[str, Any]] = []
        if exit_day == day:
            scan_bars = list(entry_bars)
        else:
            scan_bars.extend(
                row for row in entry_bars if isinstance(row.get("ts"), datetime) and row["ts"] >= entry_bar["ts"]
            )
            scan_bars.extend(
                row
                for row in exit_bars
                if isinstance(row.get("ts"), datetime) and row["ts"] <= exit_bar["ts"]
            )
            scan_bars.sort(key=lambda row: row["ts"])
        entry_bar_idx = _bar_index_by_ts(scan_bars, entry_bar["ts"])
        exit_bar_idx = _bar_index_by_ts(scan_bars, exit_bar["ts"])
        if entry_bar_idx is not None and exit_bar_idx is not None and exit_bar_idx >= entry_bar_idx:
            for scan_idx in range(entry_bar_idx, exit_bar_idx + 1):
                scan_bar = scan_bars[scan_idx]
                scan_high = float(scan_bar.get("high") or 0.0)
                scan_low = float(scan_bar.get("low") or 0.0)
                take_profit_hit = bool(
                    take_profit_price_raw is not None and scan_high > 0 and scan_high >= take_profit_price_raw
                )
                stop_hit = bool(stop_price_raw is not None and scan_low > 0 and scan_low <= stop_price_raw)
                if stop_hit:
                    selected_exit_bar, effective_exit_ts = _next_observable_exit_target(
                        scan_bars=scan_bars,
                        trigger_index=scan_idx,
                        default_exit_bar=exit_bar,
                        default_exit_ts=default_exit_ts,
                    )
                    option_premium_stop_triggered = True
                    option_premium_stop_price_raw = max(stop_price_raw, 0.0)
                    effective_exit_reason = "option_premium_stop"
                    exit_raw = option_premium_stop_price_raw
                    break
                if take_profit_hit:
                    selected_exit_bar, effective_exit_ts = _next_observable_exit_target(
                        scan_bars=scan_bars,
                        trigger_index=scan_idx,
                        default_exit_bar=exit_bar,
                        default_exit_ts=default_exit_ts,
                    )
                    premium_take_profit_triggered = True
                    premium_take_profit_price_raw = max(take_profit_price_raw, 0.0)
                    effective_exit_reason = "premium_take_profit"
                    exit_raw = premium_take_profit_price_raw
                    break

    return {
        "exit_bar": selected_exit_bar,
        "exit_raw": exit_raw,
        "effective_exit_reason": effective_exit_reason,
        "effective_exit_ts": effective_exit_ts,
        "premium_take_profit_triggered": premium_take_profit_triggered,
        "premium_take_profit_price_raw": premium_take_profit_price_raw,
        "option_premium_stop_triggered": option_premium_stop_triggered,
        "option_premium_stop_price_raw": option_premium_stop_price_raw,
    }


def _apply_vertical_credit_premium_exits(
    *,
    entry_credit_raw: float,
    take_profit_capture_pct: float,
    stop_loss_multiple: float,
    short_entry_bar: Dict[str, Any],
    short_exit_bar: Dict[str, Any],
    short_entry_bars: List[Dict[str, Any]],
    short_exit_bars: List[Dict[str, Any]],
    long_entry_bars: List[Dict[str, Any]],
    long_exit_bars: List[Dict[str, Any]],
    day: date,
    exit_day: date,
    default_exit_reason: str,
    default_exit_ts: datetime,
) -> Dict[str, Any]:
    selected_exit_bar = short_exit_bar
    effective_exit_reason = str(default_exit_reason or "")
    effective_exit_ts = default_exit_ts
    premium_take_profit_triggered = False
    premium_stop_triggered = False
    exit_raw = max(
        _causal_bar_fill_price(short_exit_bar) - _causal_bar_fill_price(long_exit_bars[_bar_index_by_ts(long_exit_bars, short_exit_bar["ts"])]),
        0.0,
    ) if _bar_index_by_ts(long_exit_bars, short_exit_bar["ts"]) is not None else max(_causal_bar_fill_price(short_exit_bar), 0.0)

    take_profit_mark = (
        entry_credit_raw * (1.0 - max(min(float(take_profit_capture_pct), 1.0), 0.0))
        if entry_credit_raw > 0.0 and take_profit_capture_pct > 0.0
        else None
    )
    stop_mark = (
        entry_credit_raw * max(float(stop_loss_multiple), 0.0)
        if entry_credit_raw > 0.0 and stop_loss_multiple > 0.0
        else None
    )
    if take_profit_mark is None and stop_mark is None:
        return {
            "exit_bar": selected_exit_bar,
            "exit_raw": exit_raw,
            "effective_exit_reason": effective_exit_reason,
            "effective_exit_ts": effective_exit_ts,
            "premium_take_profit_triggered": premium_take_profit_triggered,
            "premium_stop_triggered": premium_stop_triggered,
        }

    def _bars_in_window(
        bars_same_day: List[Dict[str, Any]],
        bars_exit_day: List[Dict[str, Any]],
        *,
        start_ts: datetime,
        end_ts: datetime,
    ) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        if exit_day == day:
            rows = list(bars_same_day)
        else:
            rows.extend(
                row
                for row in bars_same_day
                if isinstance(row.get("ts"), datetime) and row["ts"] >= start_ts
            )
            rows.extend(
                row
                for row in bars_exit_day
                if isinstance(row.get("ts"), datetime) and row["ts"] <= end_ts
            )
            rows.sort(key=lambda row: row["ts"])
        return rows

    short_scan_bars = _bars_in_window(
        short_entry_bars,
        short_exit_bars,
        start_ts=short_entry_bar["ts"],
        end_ts=short_exit_bar["ts"],
    )
    long_scan_bars = _bars_in_window(
        long_entry_bars,
        long_exit_bars,
        start_ts=short_entry_bar["ts"],
        end_ts=short_exit_bar["ts"],
    )
    long_by_ts = {
        row["ts"]: row
        for row in long_scan_bars
        if isinstance(row.get("ts"), datetime)
    }
    entry_bar_idx = _bar_index_by_ts(short_scan_bars, short_entry_bar["ts"])
    exit_bar_idx = _bar_index_by_ts(short_scan_bars, short_exit_bar["ts"])
    if entry_bar_idx is None or exit_bar_idx is None or exit_bar_idx < entry_bar_idx:
        return {
            "exit_bar": selected_exit_bar,
            "exit_raw": exit_raw,
            "effective_exit_reason": effective_exit_reason,
            "effective_exit_ts": effective_exit_ts,
            "premium_take_profit_triggered": premium_take_profit_triggered,
            "premium_stop_triggered": premium_stop_triggered,
        }

    for scan_idx in range(entry_bar_idx, exit_bar_idx + 1):
        short_bar = short_scan_bars[scan_idx]
        ts = short_bar.get("ts")
        if not isinstance(ts, datetime):
            continue
        long_bar = long_by_ts.get(ts)
        if long_bar is None:
            continue
        spread_mark = max(_causal_bar_fill_price(short_bar) - _causal_bar_fill_price(long_bar), 0.0)
        if stop_mark is not None and spread_mark >= stop_mark:
            selected_exit_bar = short_bar
            effective_exit_reason = "premium_stop"
            effective_exit_ts = ts
            premium_stop_triggered = True
            exit_raw = spread_mark
            break
        if take_profit_mark is not None and spread_mark <= take_profit_mark:
            selected_exit_bar = short_bar
            effective_exit_reason = "premium_take_profit"
            effective_exit_ts = ts
            premium_take_profit_triggered = True
            exit_raw = spread_mark
            break

    return {
        "exit_bar": selected_exit_bar,
        "exit_raw": exit_raw,
        "effective_exit_reason": effective_exit_reason,
        "effective_exit_ts": effective_exit_ts,
        "premium_take_profit_triggered": premium_take_profit_triggered,
        "premium_stop_triggered": premium_stop_triggered,
    }


def _apply_vertical_debit_premium_exits(
    *,
    entry_debit_raw: float,
    option_take_profit_pct: float,
    option_max_loss_pct: float,
    long_entry_bar: Dict[str, Any],
    long_exit_bar: Dict[str, Any],
    long_entry_bars: List[Dict[str, Any]],
    long_exit_bars: List[Dict[str, Any]],
    short_entry_bar: Dict[str, Any],
    short_exit_bar: Dict[str, Any],
    short_entry_bars: List[Dict[str, Any]],
    short_exit_bars: List[Dict[str, Any]],
    day: date,
    exit_day: date,
    default_exit_reason: str,
    default_exit_ts: datetime,
) -> Dict[str, Any]:
    selected_exit_bar = long_exit_bar
    effective_exit_reason = str(default_exit_reason or "")
    effective_exit_ts = default_exit_ts
    premium_take_profit_triggered = False
    option_premium_stop_triggered = False
    premium_stop_triggered = False
    option_premium_stop_price_raw: Optional[float] = None
    exit_raw = max(
        _causal_bar_fill_price(long_exit_bar)
        - _causal_bar_fill_price(short_exit_bars[_bar_index_by_ts(short_exit_bars, long_exit_bar["ts"])]),
        0.0,
    ) if _bar_index_by_ts(short_exit_bars, long_exit_bar["ts"]) is not None else max(_causal_bar_fill_price(long_exit_bar), 0.0)

    take_profit_mark = (
        entry_debit_raw * (1.0 + option_take_profit_pct)
        if entry_debit_raw > 0.0 and option_take_profit_pct > 0.0
        else None
    )
    stop_mark = (
        entry_debit_raw * (1.0 - option_max_loss_pct)
        if entry_debit_raw > 0.0 and option_max_loss_pct > 0.0
        else None
    )
    if take_profit_mark is None and stop_mark is None:
        return {
            "exit_bar": selected_exit_bar,
            "exit_raw": exit_raw,
            "effective_exit_reason": effective_exit_reason,
            "effective_exit_ts": effective_exit_ts,
            "premium_take_profit_triggered": premium_take_profit_triggered,
            "premium_stop_triggered": premium_stop_triggered,
            "option_premium_stop_triggered": option_premium_stop_triggered,
            "option_premium_stop_price_raw": option_premium_stop_price_raw,
        }

    def _bars_in_window(
        bars_same_day: List[Dict[str, Any]],
        bars_exit_day: List[Dict[str, Any]],
        *,
        start_ts: datetime,
        end_ts: datetime,
    ) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        if exit_day == day:
            rows = list(bars_same_day)
        else:
            rows.extend(
                row
                for row in bars_same_day
                if isinstance(row.get("ts"), datetime) and row["ts"] >= start_ts
            )
            rows.extend(
                row
                for row in bars_exit_day
                if isinstance(row.get("ts"), datetime) and row["ts"] <= end_ts
            )
            rows.sort(key=lambda row: row["ts"])
        return rows

    long_scan_bars = _bars_in_window(
        long_entry_bars,
        long_exit_bars,
        start_ts=long_entry_bar["ts"],
        end_ts=long_exit_bar["ts"],
    )
    short_scan_bars = _bars_in_window(
        short_entry_bars,
        short_exit_bars,
        start_ts=short_entry_bar["ts"],
        end_ts=short_exit_bar["ts"],
    )
    short_by_ts = {
        row["ts"]: row
        for row in short_scan_bars
        if isinstance(row.get("ts"), datetime)
    }
    entry_bar_idx = _bar_index_by_ts(long_scan_bars, long_entry_bar["ts"])
    exit_bar_idx = _bar_index_by_ts(long_scan_bars, long_exit_bar["ts"])
    if entry_bar_idx is None or exit_bar_idx is None or exit_bar_idx < entry_bar_idx:
        return {
            "exit_bar": selected_exit_bar,
            "exit_raw": exit_raw,
            "effective_exit_reason": effective_exit_reason,
            "effective_exit_ts": effective_exit_ts,
            "premium_take_profit_triggered": premium_take_profit_triggered,
            "premium_stop_triggered": premium_stop_triggered,
            "option_premium_stop_triggered": option_premium_stop_triggered,
            "option_premium_stop_price_raw": option_premium_stop_price_raw,
        }

    for scan_idx in range(entry_bar_idx, exit_bar_idx + 1):
        long_bar = long_scan_bars[scan_idx]
        ts = long_bar.get("ts")
        if not isinstance(ts, datetime):
            continue
        short_bar = short_by_ts.get(ts)
        if short_bar is None:
            continue
        spread_mark = max(_causal_bar_fill_price(long_bar) - _causal_bar_fill_price(short_bar), 0.0)
        if stop_mark is not None and spread_mark <= stop_mark:
            selected_exit_bar, effective_exit_ts = _next_observable_exit_target(
                scan_bars=long_scan_bars,
                trigger_index=scan_idx,
                default_exit_bar=long_exit_bar,
                default_exit_ts=default_exit_ts,
            )
            effective_exit_reason = "option_premium_stop"
            option_premium_stop_triggered = True
            premium_stop_triggered = True
            option_premium_stop_price_raw = max(stop_mark, 0.0)
            exit_raw = spread_mark
            break
        if take_profit_mark is not None and spread_mark >= take_profit_mark:
            selected_exit_bar, effective_exit_ts = _next_observable_exit_target(
                scan_bars=long_scan_bars,
                trigger_index=scan_idx,
                default_exit_bar=long_exit_bar,
                default_exit_ts=default_exit_ts,
            )
            effective_exit_reason = "premium_take_profit"
            premium_take_profit_triggered = True
            exit_raw = spread_mark
            break

    return {
        "exit_bar": selected_exit_bar,
        "exit_raw": exit_raw,
        "effective_exit_reason": effective_exit_reason,
        "effective_exit_ts": effective_exit_ts,
        "premium_take_profit_triggered": premium_take_profit_triggered,
        "premium_stop_triggered": premium_stop_triggered,
        "option_premium_stop_triggered": option_premium_stop_triggered,
        "option_premium_stop_price_raw": option_premium_stop_price_raw,
    }


def _first_quote_on_or_after(
    quotes: List[Dict[str, Any]],
    ts: datetime,
    fallback_last: bool = False,
) -> Optional[Dict[str, Any]]:
    target_ts = _as_utc_aware(ts)
    for quote in quotes:
        quote_ts = quote.get("ts")
        if not isinstance(quote_ts, datetime):
            continue
        if _as_utc_aware(quote_ts) >= target_ts:
            return quote
    if fallback_last and quotes:
        return quotes[-1]
    return None


def _jittered_delay_minutes(
    *,
    base_delay_minutes: int,
    jitter_minutes: int,
    randomization_enabled: bool,
    random_seed: int,
    seed_key: str,
) -> int:
    base = max(int(base_delay_minutes), 0)
    jitter = max(int(jitter_minutes), 0)
    if not randomization_enabled or jitter <= 0:
        return base
    rng = random.Random(f"{int(random_seed)}|{seed_key}")
    return max(0, base + rng.randint(-jitter, jitter))


def _snap_to_poll_boundary(ts: datetime, poll_seconds: int) -> datetime:
    poll = max(int(poll_seconds), 1)
    seconds = (
        ts.hour * 3600
        + ts.minute * 60
        + ts.second
        + (ts.microsecond / 1_000_000.0)
    )
    remainder = seconds % float(poll)
    if remainder <= 0:
        return ts
    return ts + timedelta(seconds=float(poll) - remainder)


def _apply_execution_timing_model(
    ts: datetime,
    *,
    model: str,
    poll_seconds: int,
    signal_confirm_seconds: int,
    fill_latency_seconds: int,
) -> datetime:
    normalized_model = str(model or "bar_open").strip().lower()
    effective = ts + timedelta(seconds=max(int(signal_confirm_seconds), 0))
    if normalized_model == "live_poll":
        effective = _snap_to_poll_boundary(effective, max(int(poll_seconds), 1))
    effective = effective + timedelta(seconds=max(int(fill_latency_seconds), 0))
    return effective


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _causal_bar_fill_price(row: Dict[str, Any]) -> float:
    open_price = float(row.get("open") or 0.0)
    if open_price > 0:
        return open_price
    return float(row.get("close") or 0.0)


def _option_qty_for_risk(
    *,
    risk_notional: float,
    entry_price: float,
    commission_per_contract: float,
    include_commission: bool,
    min_entry_price: float,
    sizing_mode: str = "premium_at_risk",
    option_max_loss_pct: float = 0.0,
    option_leg_count: int = 1,
) -> int:
    risk_capital = max(float(risk_notional), 0.0)
    effective_entry_price = max(float(entry_price), max(float(min_entry_price), 0.0))
    if risk_capital <= 0.0 or effective_entry_price <= 0.0:
        return 0
    normalized_mode = str(sizing_mode or "premium_at_risk").strip().lower()
    loss_fraction = 1.0
    if normalized_mode == "premium_stop":
        candidate = max(float(option_max_loss_pct), 0.0)
        if 0.0 < candidate <= 1.0:
            loss_fraction = candidate
    per_contract_cost = effective_entry_price * 100.0 * loss_fraction
    if include_commission:
        per_contract_cost += max(float(commission_per_contract), 0.0) * 2.0 * max(int(option_leg_count), 1)
    if per_contract_cost <= 0.0:
        return 0
    return int(risk_capital / per_contract_cost)


def _required_option_entry_volume(
    *,
    gate_mode: str,
    base_min_entry_volume: int,
    provisional_qty: int,
    max_entry_volume_participation: float,
) -> int:
    required = max(int(base_min_entry_volume), 0)
    normalized_mode = str(gate_mode or "absolute").strip().lower()
    if normalized_mode != "size_aware_absolute":
        return required
    if provisional_qty <= 0:
        return required
    participation = max(float(max_entry_volume_participation), 0.0)
    if participation <= 0.0:
        return required
    return max(required, int(ceil(float(provisional_qty) / participation)))


def _option_intrinsic_value(option_type: str, underlying_price: float, strike: float) -> float:
    normalized = str(option_type or "").strip().lower()
    underlying = max(float(underlying_price), 0.0)
    strike_px = max(float(strike), 0.0)
    if normalized == "put":
        return max(strike_px - underlying, 0.0)
    return max(underlying - strike_px, 0.0)


def _setup_override_float(
    setup: Optional[Mapping[str, Any]],
    key: str,
    default_value: float,
) -> float:
    if isinstance(setup, Mapping):
        overrides = setup.get("regime_v2_setup_overrides")
        if isinstance(overrides, Mapping) and key in overrides:
            value = _safe_float(overrides.get(key))
            if value is not None:
                return float(value)
    return float(default_value)


def _expected_underlying_target_move(
    *,
    setup: Dict[str, Any],
    take_profit_rr: float,
) -> Optional[float]:
    entry_underlying = _safe_float(setup.get("entry_underlying"))
    stop_underlying = _safe_float(setup.get("stop_underlying"))
    if entry_underlying is None or entry_underlying <= 0:
        return None
    target_underlying = _safe_float(setup.get("mr_target_underlying"))
    if target_underlying is None and stop_underlying is not None and stop_underlying > 0 and take_profit_rr > 0:
        risk_per_share = abs(entry_underlying - stop_underlying)
        if risk_per_share > 0:
            direction = 1 if int(setup.get("direction") or 0) >= 0 else -1
            target_underlying = entry_underlying + (direction * risk_per_share * float(take_profit_rr))
    if target_underlying is None or target_underlying <= 0:
        return None
    move = abs(float(target_underlying) - float(entry_underlying))
    return move if move > 0 else None


def _normalize_regime_label(value: Any) -> str:
    label = str(value or "").strip().lower()
    if label in {"trending", "trend", "trending_up", "trending_down", "momentum", "breakout"}:
        return "trending"
    if label in {"sideways", "sideway", "choppy", "range", "mean_reversion"}:
        return "sideways"
    if label in {"neutral", "transition", "mixed"}:
        return "neutral"
    return "unknown"


def _empty_regime_label_counts() -> Dict[str, int]:
    return {
        "trending": 0,
        "sideways": 0,
        "neutral": 0,
        "unknown": 0,
    }


def _empty_regime_v2_state_counts() -> Dict[str, int]:
    return {
        "trend_up": 0,
        "trend_down": 0,
        "range_low_vol": 0,
        "range_high_vol": 0,
        "event_gap": 0,
        "transition": 0,
        "defensive": 0,
        "unknown": 0,
    }


def _empty_regime_v2_route_counts() -> Dict[str, int]:
    return {
        "trend_up": 0,
        "trend_down": 0,
        "range_low_vol": 0,
        "range_high_vol": 0,
        "event_gap": 0,
        "transition": 0,
        "low_confidence": 0,
        "low_confidence_skip": 0,
        "bull_high_rv_skip": 0,
        "range_high_vol_skip": 0,
        "event_gap_skip": 0,
        "positive_event_gap_skip": 0,
        "transition_skip": 0,
        "unknown_state_skip": 0,
        "non_trend_skip": 0,
        "defensive": 0,
        "unknown": 0,
    }


def _parse_regime_label_allowlist(value: Any) -> set[str]:
    raw = str(value or "").strip()
    if not raw:
        return {"trending", "sideways", "neutral", "unknown"}
    out: set[str] = set()
    for item in raw.split(","):
        label = _normalize_regime_label(item)
        out.add(label)
    if not out:
        out.add("unknown")
    return out


def _route_strategy_for_regime_v2(
    *,
    base_variant: str,
    base_allow_long: bool,
    base_allow_short: bool,
    regime_v2_state: str,
    confidence: float,
    router_enabled: bool,
    router_mode: str,
    min_confidence: float,
    trend_up_min_confidence: Optional[float] = None,
    trend_down_min_confidence: Optional[float] = None,
    range_low_vol_min_confidence: Optional[float] = None,
    relative_opening_volume: Optional[float] = None,
    entry_bar_range_pct: Optional[float] = None,
    gap_return: Optional[float] = None,
    high_rv_min: float = 1.15,
    trend_up_rv_max: float = 1.30,
    trend_down_rv_max: float = 1.35,
    trend_up_entry_bar_range_min_pct: float = 0.04,
    trend_down_entry_bar_range_min_pct: float = 0.04,
    low_confidence_mr_rv_max: float = 1.15,
    low_confidence_mr_entry_bar_range_max_pct: float = 0.03,
    low_confidence_skip_rv_min: float = 1.60,
    low_confidence_skip_entry_bar_range_min_pct: float = 0.06,
    trend_up_overlay_compression_max_range_pct: float = 0.0030,
    trend_up_overlay_option_max_entry_bar_range_pct: float = 0.06,
    event_gap_tight_entry_bar_range_max_pct: float = 0.01,
    event_gap_mid_rv_min: float = 1.0,
    event_gap_mid_rv_max: float = 2.0,
    event_gap_mid_entry_bar_range_max_pct: float = 0.025,
    event_gap_overlay_compression_max_range_pct: float = 0.0030,
    event_gap_overlay_option_max_entry_bar_range_pct: float = 0.06,
    range_low_vol_tight_rv_max: float = 0.95,
    range_low_vol_tight_entry_bar_range_max_pct: float = 0.005,
    transition_high_rv_min: float = 2.0,
    transition_wide_entry_bar_range_min_pct: float = 0.05,
) -> Dict[str, Any]:
    base_variant_text = str(base_variant or "orb_qc")
    base = {
        "route_state": str(regime_v2_state or "unknown"),
        "selected_variant": base_variant_text,
        "allow_long": bool(base_allow_long),
        "allow_short": bool(base_allow_short),
        "skip_day": False,
        "skip_reason": "",
        "route_action": "fallback_base",
        "route_overlay_name": "",
        "setup_overrides": {},
    }
    if not bool(router_enabled):
        return base

    safe_conf = float(confidence or 0.0)
    min_conf = max(float(min_confidence), 0.0)
    state = str(regime_v2_state or "unknown").strip().lower() or "unknown"
    mode = str(router_mode or "core").strip().lower() or "core"
    def _normalize_state_min_confidence(value: Optional[float]) -> float:
        if value in (None, ""):
            return min_conf
        try:
            normalized = float(value)
        except (TypeError, ValueError):
            return min_conf
        if normalized <= 0.0:
            return min_conf
        return max(normalized, 0.0)

    trend_up_min_conf = _normalize_state_min_confidence(trend_up_min_confidence)
    trend_down_min_conf = _normalize_state_min_confidence(trend_down_min_confidence)
    range_low_vol_min_conf = _normalize_state_min_confidence(range_low_vol_min_confidence)
    rel_opening_vol = _safe_float(relative_opening_volume)
    normalized_entry_bar_range_pct = _safe_float(entry_bar_range_pct)
    normalized_gap_return = _safe_float(gap_return)
    is_high_rv = rel_opening_vol is not None and rel_opening_vol >= max(float(high_rv_min), 0.0)
    trend_up_rv_cap = max(float(trend_up_rv_max), 0.0)
    trend_down_rv_cap = max(float(trend_down_rv_max), 0.0)
    trend_up_entry_range_min = max(float(trend_up_entry_bar_range_min_pct), 0.0)
    trend_down_entry_range_min = max(float(trend_down_entry_bar_range_min_pct), 0.0)
    low_confidence_mr_rv_cap = max(float(low_confidence_mr_rv_max), 0.0)
    low_confidence_mr_entry_range_cap = max(float(low_confidence_mr_entry_bar_range_max_pct), 0.0)
    low_confidence_skip_rv_floor = max(float(low_confidence_skip_rv_min), 0.0)
    low_confidence_skip_entry_range_floor = max(
        float(low_confidence_skip_entry_bar_range_min_pct),
        0.0,
    )
    trend_up_overlay_compression_cap = max(float(trend_up_overlay_compression_max_range_pct), 0.0)
    trend_up_overlay_option_range_cap = max(
        float(trend_up_overlay_option_max_entry_bar_range_pct),
        0.0,
    )
    event_gap_tight_entry_range_cap = max(float(event_gap_tight_entry_bar_range_max_pct), 0.0)
    event_gap_mid_rv_floor = max(float(event_gap_mid_rv_min), 0.0)
    event_gap_mid_rv_cap = max(float(event_gap_mid_rv_max), event_gap_mid_rv_floor)
    event_gap_mid_entry_range_cap = max(float(event_gap_mid_entry_bar_range_max_pct), 0.0)
    event_gap_overlay_compression_cap = max(float(event_gap_overlay_compression_max_range_pct), 0.0)
    event_gap_overlay_option_range_cap = max(float(event_gap_overlay_option_max_entry_bar_range_pct), 0.0)
    range_low_vol_tight_rv_cap = max(float(range_low_vol_tight_rv_max), 0.0)
    range_low_vol_tight_entry_range_cap = max(float(range_low_vol_tight_entry_bar_range_max_pct), 0.0)
    transition_high_rv_floor = max(float(transition_high_rv_min), 0.0)
    transition_wide_entry_range_floor = max(float(transition_wide_entry_bar_range_min_pct), 0.0)

    def _finish() -> Dict[str, Any]:
        if bool(base.get("skip_day")):
            base["route_action"] = "skip_day"
        else:
            selected_variant = str(base.get("selected_variant") or base_variant_text)
            allow_long = bool(base.get("allow_long"))
            allow_short = bool(base.get("allow_short"))
            if (
                str(base.get("route_action") or "") == "override_variant"
                or selected_variant != base_variant_text
                or allow_long != bool(base_allow_long)
                or allow_short != bool(base_allow_short)
            ):
                base["route_action"] = "override_variant"
            else:
                base["route_action"] = "fallback_base"
        return base

    def _fallback(route_state: Optional[str] = None) -> Dict[str, Any]:
        if route_state is not None:
            base["route_state"] = str(route_state)
        base["selected_variant"] = base_variant_text
        base["allow_long"] = bool(base_allow_long)
        base["allow_short"] = bool(base_allow_short)
        base["skip_day"] = False
        base["skip_reason"] = ""
        base["route_action"] = "fallback_base"
        base["route_overlay_name"] = ""
        base["setup_overrides"] = {}
        return _finish()

    def _override(
        *,
        selected_variant: str,
        allow_long: bool,
        allow_short: bool,
        route_state: Optional[str] = None,
        route_overlay_name: str = "",
        setup_overrides: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        if route_state is not None:
            base["route_state"] = str(route_state)
        base["selected_variant"] = str(selected_variant)
        base["allow_long"] = bool(allow_long)
        base["allow_short"] = bool(allow_short)
        base["skip_day"] = False
        base["skip_reason"] = ""
        base["route_action"] = "override_variant"
        base["route_overlay_name"] = str(route_overlay_name or "")
        base["setup_overrides"] = dict(setup_overrides or {})
        return _finish()

    def _fallback_with_overlay(
        *,
        route_state: Optional[str] = None,
        route_overlay_name: str,
        setup_overrides: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        if route_state is not None:
            base["route_state"] = str(route_state)
        base["selected_variant"] = base_variant_text
        base["allow_long"] = bool(base_allow_long)
        base["allow_short"] = bool(base_allow_short)
        base["skip_day"] = False
        base["skip_reason"] = ""
        base["route_action"] = "fallback_base"
        base["route_overlay_name"] = str(route_overlay_name or "")
        base["setup_overrides"] = dict(setup_overrides or {})
        return _finish()

    def _skip(skip_reason: str, *, route_state: Optional[str] = None) -> Dict[str, Any]:
        base["route_state"] = str(route_state or skip_reason)
        base["skip_day"] = True
        base["skip_reason"] = str(skip_reason)
        base["route_action"] = "skip_day"
        base["route_overlay_name"] = ""
        base["setup_overrides"] = {}
        return _finish()

    def _effective_min_confidence() -> float:
        if state == "trend_up":
            return trend_up_min_conf
        if state == "trend_down":
            return trend_down_min_conf
        if state == "range_low_vol":
            return range_low_vol_min_conf
        return min_conf

    def _low_confidence_guard(*, route_state: str = "low_confidence") -> Dict[str, Any]:
        if (
            rel_opening_vol is not None
            and rel_opening_vol <= low_confidence_mr_rv_cap
            and normalized_entry_bar_range_pct is not None
            and normalized_entry_bar_range_pct <= low_confidence_mr_entry_range_cap
        ):
            return _override(
                selected_variant="mr_vwap_zscore_v2",
                allow_long=True,
                allow_short=True,
                route_state=route_state,
            )
        if (
            (rel_opening_vol is not None and rel_opening_vol >= low_confidence_skip_rv_floor)
            or (
                normalized_entry_bar_range_pct is not None
                and normalized_entry_bar_range_pct >= low_confidence_skip_entry_range_floor
            )
        ):
            return _skip(
                "low_confidence_high_risk_skip",
                route_state="low_confidence_high_risk_skip",
            )
        return _fallback(route_state)

    def _trend_down_guarded_fallback() -> Dict[str, Any]:
        if (
            normalized_entry_bar_range_pct is not None
            and normalized_entry_bar_range_pct >= trend_down_entry_range_min
            and rel_opening_vol is not None
            and rel_opening_vol < trend_down_rv_cap
        ):
            return _override(
                selected_variant="orb_momentum_v1",
                allow_long=False,
                allow_short=True,
                route_state="trend_down",
            )
        return _fallback("trend_down")

    def _trend_up_trendcap_override() -> Dict[str, Any]:
        return _override(
            selected_variant="mr_vwap_zscore_v2",
            allow_long=True,
            allow_short=True,
            route_state="trend_up",
            route_overlay_name="trend_up_rangecap_overlay",
            setup_overrides={
                "compression_max_range_pct": trend_up_overlay_compression_cap,
                "option_max_entry_bar_range_pct": trend_up_overlay_option_range_cap,
            },
        )

    def _event_gap_guard() -> Dict[str, Any]:
        if (
            normalized_entry_bar_range_pct is not None
            and normalized_entry_bar_range_pct < event_gap_tight_entry_range_cap
            and rel_opening_vol is not None
            and rel_opening_vol >= event_gap_mid_rv_floor
        ):
            return _skip("event_gap_tight_skip", route_state="event_gap_tight_skip")
        if (
            rel_opening_vol is not None
            and event_gap_mid_rv_floor <= rel_opening_vol < event_gap_mid_rv_cap
            and normalized_entry_bar_range_pct is not None
            and normalized_entry_bar_range_pct < event_gap_mid_entry_range_cap
        ):
            return _skip(
                "event_gap_midrv_narrow_skip",
                route_state="event_gap_midrv_narrow_skip",
            )
        return _fallback("event_gap")

    def _event_gap_softcap_fallback() -> Dict[str, Any]:
        if (
            normalized_entry_bar_range_pct is not None
            and normalized_entry_bar_range_pct < event_gap_tight_entry_range_cap
            and rel_opening_vol is not None
            and rel_opening_vol >= event_gap_mid_rv_floor
        ):
            return _skip("event_gap_tight_skip", route_state="event_gap_tight_skip")
        return _fallback_with_overlay(
            route_state="event_gap",
            route_overlay_name="event_gap_softcap_overlay",
            setup_overrides={
                "compression_max_range_pct": event_gap_overlay_compression_cap,
                "option_max_entry_bar_range_pct": event_gap_overlay_option_range_cap,
            },
        )

    def _range_low_vol_tight_guard() -> Dict[str, Any]:
        if (
            normalized_entry_bar_range_pct is not None
            and normalized_entry_bar_range_pct <= range_low_vol_tight_entry_range_cap
            and rel_opening_vol is not None
            and rel_opening_vol <= range_low_vol_tight_rv_cap
        ):
            return _skip("range_low_vol_tight_skip", route_state="range_low_vol_tight_skip")
        return _fallback("range_low_vol")

    def _transition_high_rv_wide_guard() -> Dict[str, Any]:
        if (
            normalized_entry_bar_range_pct is not None
            and normalized_entry_bar_range_pct >= transition_wide_entry_range_floor
            and rel_opening_vol is not None
            and rel_opening_vol >= transition_high_rv_floor
        ):
            return _skip("transition_high_rv_wide_skip", route_state="transition_high_rv_wide_skip")
        return _fallback("transition")

    if safe_conf < _effective_min_confidence():
        if mode in {
            "meta_trend_pullback_fallback_v1",
            "meta_trend_mr_fallback_v1",
            "meta_trendmr_fulltrend_fallback_v1",
        }:
            return _fallback("low_confidence")
        if mode == "meta_trendmr_lowconf_guard_v1":
            return _low_confidence_guard()
        if mode in {
            "meta_trendmr_lowconf_guard_trendcap_v1",
            "meta_trendmr_lowconf_guard_eventgap_v1",
            "meta_trendmr_lowconf_guard_trendcap_eventgap_v1",
            "meta_trendmr_lowconf_guard_trendcap_eventgap_soft_v1",
            "meta_trendmr_lowconf_guard_trendcap_eventgap_soft_rangelow_v1",
            "meta_trendmr_lowconf_guard_trendcap_eventgap_soft_rangelow_transition_v1",
        }:
            return _low_confidence_guard()
        return _skip("low_confidence_skip")

    if mode == "meta_v1":
        if state == "trend_up":
            return _override(
                selected_variant="orb_trend_pullback_v1",
                allow_long=True,
                allow_short=False,
            )
        if state == "trend_down":
            return _override(
                selected_variant="orb_momentum_v1",
                allow_long=False,
                allow_short=True,
            )
        if state == "range_low_vol":
            return _override(
                selected_variant="mr_vwap_zscore_v2",
                allow_long=True,
                allow_short=True,
            )
        if state == "range_high_vol":
            return _override(
                selected_variant="orb_transition_compression_v1",
                allow_long=True,
                allow_short=True,
            )
        if state == "event_gap":
            return _override(
                selected_variant="orb_event_drive_v1",
                allow_long=True,
                allow_short=True,
            )
        if state == "transition":
            return _override(
                selected_variant="orb_transition_compression_v1",
                allow_long=True,
                allow_short=True,
            )
        return _skip("unknown_state_skip")

    if mode == "core_eventskip_v1":
        if state == "trend_up":
            return _override(selected_variant="orb_momentum_v1", allow_long=True, allow_short=False)
        if state == "trend_down":
            return _override(selected_variant="orb_momentum_v1", allow_long=False, allow_short=True)
        if state == "range_low_vol":
            return _override(selected_variant="mr_vwap_zscore_v2", allow_long=True, allow_short=True)
        if state == "range_high_vol":
            return _skip("range_high_vol_skip")
        if state == "event_gap":
            return _skip("event_gap_skip")
        if state == "transition":
            return _skip("transition_skip")
        return _skip("unknown_state_skip")

    if mode == "core_eventdrive_v1":
        if state == "trend_up":
            return _override(selected_variant="orb_momentum_v1", allow_long=True, allow_short=False)
        if state == "trend_down":
            return _override(selected_variant="orb_momentum_v1", allow_long=False, allow_short=True)
        if state == "range_low_vol":
            return _override(selected_variant="mr_vwap_zscore_v2", allow_long=True, allow_short=True)
        if state == "range_high_vol":
            return _skip("range_high_vol_skip")
        if state == "event_gap":
            return _override(selected_variant="orb_event_drive_v1", allow_long=True, allow_short=True)
        if state == "transition":
            return _skip("transition_skip")
        return _skip("unknown_state_skip")

    if mode == "core_trendonly_v1":
        if state == "trend_up":
            return _override(selected_variant="orb_momentum_v1", allow_long=True, allow_short=False)
        if state == "trend_down":
            return _override(selected_variant="orb_momentum_v1", allow_long=False, allow_short=True)
        if state == "range_low_vol":
            return _skip("non_trend_skip")
        if state == "range_high_vol":
            return _skip("range_high_vol_skip")
        if state == "event_gap":
            return _skip("event_gap_skip")
        if state == "transition":
            return _skip("transition_skip")
        return _skip("unknown_state_skip")

    if mode == "meta_defensive_v2":
        if state == "trend_up":
            return _override(selected_variant="orb_trend_pullback_v1", allow_long=True, allow_short=False)
        if state == "trend_down":
            return _override(selected_variant="orb_momentum_v1", allow_long=False, allow_short=True)
        if state == "range_low_vol":
            return _override(selected_variant="mr_vwap_zscore_v2", allow_long=True, allow_short=True)
        if state == "range_high_vol":
            return _skip("range_high_vol_skip")
        if state == "event_gap":
            return _override(selected_variant="orb_event_drive_v1", allow_long=True, allow_short=True)
        if state == "transition":
            return _skip("transition_skip")
        return _skip("unknown_state_skip")

    if mode == "core_trendup_pullback_v1":
        if state == "trend_up":
            return _override(selected_variant="orb_trend_pullback_v1", allow_long=True, allow_short=False)
        if state == "trend_down":
            return _override(selected_variant="orb_momentum_v1", allow_long=False, allow_short=True)
        if state == "range_low_vol":
            return _override(selected_variant="mr_vwap_zscore_v2", allow_long=True, allow_short=True)
        if state == "range_high_vol":
            return _skip("range_high_vol_skip")
        if state == "event_gap":
            return _skip("event_gap_skip")
        if state == "transition":
            return _skip("transition_skip")
        return _skip("unknown_state_skip")

    if mode == "core_bullhighrv_skip_v1":
        if is_high_rv and state in {"trend_up", "event_gap"}:
            return _skip("bull_high_rv_skip")
        if state == "trend_up":
            return _override(selected_variant="orb_momentum_v1", allow_long=True, allow_short=False)
        if state == "trend_down":
            return _override(selected_variant="orb_momentum_v1", allow_long=False, allow_short=True)
        if state == "range_low_vol":
            return _override(selected_variant="mr_vwap_zscore_v2", allow_long=True, allow_short=True)
        if state == "range_high_vol":
            return _skip("range_high_vol_skip")
        if state == "event_gap":
            return _skip("event_gap_skip")
        if state == "transition":
            return _skip("transition_skip")
        return _skip("unknown_state_skip")

    if mode == "core_gapdown_eventdrive_v1":
        if state == "trend_up":
            return _override(selected_variant="orb_trend_pullback_v1", allow_long=True, allow_short=False)
        if state == "trend_down":
            return _override(selected_variant="orb_momentum_v1", allow_long=False, allow_short=True)
        if state == "range_low_vol":
            return _override(selected_variant="mr_vwap_zscore_v2", allow_long=True, allow_short=True)
        if state == "range_high_vol":
            return _skip("range_high_vol_skip")
        if state == "event_gap":
            if float(normalized_gap_return or 0.0) < 0.0:
                return _override(selected_variant="orb_event_drive_v1", allow_long=True, allow_short=True)
            return _skip("positive_event_gap_skip")
        if state == "transition":
            return _skip("transition_skip")
        return _skip("unknown_state_skip")

    if mode == "meta_rv_defensive_v1":
        if state == "trend_up":
            if is_high_rv:
                return _skip("bull_high_rv_skip")
            return _override(selected_variant="orb_trend_pullback_v1", allow_long=True, allow_short=False)
        if state == "trend_down":
            return _override(selected_variant="orb_momentum_v1", allow_long=False, allow_short=True)
        if state == "range_low_vol":
            return _override(selected_variant="mr_vwap_zscore_v2", allow_long=True, allow_short=True)
        if state == "range_high_vol":
            return _skip("range_high_vol_skip")
        if state == "event_gap":
            if float(normalized_gap_return or 0.0) < 0.0:
                return _override(selected_variant="orb_event_drive_v1", allow_long=True, allow_short=True)
            return _skip("positive_event_gap_skip")
        if state == "transition":
            return _skip("transition_skip")
        return _skip("unknown_state_skip")

    if mode == "core_downrange_conf20_v1":
        if state == "trend_down":
            return _override(selected_variant="orb_momentum_v1", allow_long=False, allow_short=True)
        if state == "range_low_vol":
            return _override(selected_variant="mr_vwap_zscore_v2", allow_long=True, allow_short=True)
        if state == "trend_up":
            return _skip("non_trend_skip")
        if state == "range_high_vol":
            return _skip("range_high_vol_skip")
        if state == "event_gap":
            return _skip("event_gap_skip")
        if state == "transition":
            return _skip("transition_skip")
        return _skip("unknown_state_skip")

    if mode in {
        "core_conf20_v1",
        "core_conf15_v1",
        "core_asym_conf_v1",
    }:
        pass

    if mode == "core_bullhighrv_conf20_v1":
        if is_high_rv and state in {"trend_up", "event_gap"}:
            return _skip("bull_high_rv_skip")
        if state == "trend_up":
            return _override(selected_variant="orb_momentum_v1", allow_long=True, allow_short=False)
        if state == "trend_down":
            return _override(selected_variant="orb_momentum_v1", allow_long=False, allow_short=True)
        if state == "range_low_vol":
            return _override(selected_variant="mr_vwap_zscore_v2", allow_long=True, allow_short=True)
        if state == "range_high_vol":
            return _skip("range_high_vol_skip")
        if state == "event_gap":
            return _skip("event_gap_skip")
        if state == "transition":
            return _skip("transition_skip")
        return _skip("unknown_state_skip")

    if mode == "meta_trend_filter_balanced_v1":
        if state == "trend_up":
            if (
                normalized_entry_bar_range_pct is not None
                and normalized_entry_bar_range_pct < trend_up_entry_range_min
            ):
                return _skip("trend_up_tight_skip")
            if rel_opening_vol is not None and rel_opening_vol >= trend_up_rv_cap:
                return _skip("trend_up_high_rv_skip")
            return _override(selected_variant="mr_vwap_zscore_v2", allow_long=True, allow_short=True)
        if state == "trend_down":
            if (
                normalized_entry_bar_range_pct is not None
                and normalized_entry_bar_range_pct < trend_down_entry_range_min
            ):
                return _skip("trend_down_tight_skip")
            if rel_opening_vol is not None and rel_opening_vol >= trend_down_rv_cap:
                return _skip("trend_down_high_rv_skip")
            return _override(selected_variant="orb_momentum_v1", allow_long=False, allow_short=True)
        if state == "range_low_vol":
            return _override(selected_variant="mr_vwap_zscore_v2", allow_long=True, allow_short=True)
        if state == "range_high_vol":
            return _skip("range_high_vol_skip")
        if state == "event_gap":
            if float(normalized_gap_return or 0.0) < 0.0:
                return _override(selected_variant="orb_event_drive_v1", allow_long=True, allow_short=True)
            return _skip("positive_event_gap_skip")
        if state == "transition":
            return _skip("transition_skip")
        return _skip("unknown_state_skip")

    if mode == "meta_trend_filter_strict_v1":
        if state == "trend_up":
            return _skip("trend_up_skip")
        if state == "trend_down":
            if (
                normalized_entry_bar_range_pct is not None
                and normalized_entry_bar_range_pct < trend_down_entry_range_min
            ):
                return _skip("trend_down_tight_skip")
            if rel_opening_vol is not None and rel_opening_vol >= trend_down_rv_cap:
                return _skip("trend_down_high_rv_skip")
            return _override(selected_variant="orb_momentum_v1", allow_long=False, allow_short=True)
        if state == "range_low_vol":
            return _override(selected_variant="mr_vwap_zscore_v2", allow_long=True, allow_short=True)
        if state == "range_high_vol":
            return _skip("range_high_vol_skip")
        if state == "event_gap":
            if float(normalized_gap_return or 0.0) < 0.0:
                return _override(selected_variant="orb_event_drive_v1", allow_long=True, allow_short=True)
            return _skip("positive_event_gap_skip")
        if state == "transition":
            return _skip("transition_skip")
        return _skip("unknown_state_skip")

    if mode == "meta_trend_pullback_fallback_v1":
        if state == "trend_up":
            if (
                normalized_entry_bar_range_pct is not None
                and normalized_entry_bar_range_pct < trend_up_entry_range_min
            ) or (rel_opening_vol is not None and rel_opening_vol >= trend_up_rv_cap):
                return _override(
                    selected_variant="orb_trend_pullback_v1",
                    allow_long=True,
                    allow_short=False,
                    route_state="trend_up",
                )
            return _fallback("trend_up")
        if state == "trend_down":
            if (
                normalized_entry_bar_range_pct is not None
                and normalized_entry_bar_range_pct >= trend_down_entry_range_min
                and rel_opening_vol is not None
                and rel_opening_vol < trend_down_rv_cap
            ):
                return _override(
                    selected_variant="orb_momentum_v1",
                    allow_long=False,
                    allow_short=True,
                    route_state="trend_down",
                )
            return _fallback("trend_down")
        if state in {"range_low_vol", "range_high_vol", "event_gap", "transition", "unknown"}:
            return _fallback(state)
        return _fallback("unknown")

    if mode == "meta_trend_mr_fallback_v1":
        if state == "trend_up":
            if (
                normalized_entry_bar_range_pct is not None
                and normalized_entry_bar_range_pct < trend_up_entry_range_min
            ) or (rel_opening_vol is not None and rel_opening_vol >= trend_up_rv_cap):
                return _override(
                    selected_variant="mr_vwap_zscore_v2",
                    allow_long=True,
                    allow_short=True,
                    route_state="trend_up",
                )
            return _fallback("trend_up")
        if state == "trend_down":
            if (
                normalized_entry_bar_range_pct is not None
                and normalized_entry_bar_range_pct >= trend_down_entry_range_min
                and rel_opening_vol is not None
                and rel_opening_vol < trend_down_rv_cap
            ):
                return _override(
                    selected_variant="orb_momentum_v1",
                    allow_long=False,
                    allow_short=True,
                    route_state="trend_down",
                )
            return _fallback("trend_down")
        if state in {"range_low_vol", "range_high_vol", "event_gap", "transition", "unknown"}:
            return _fallback(state)
        return _fallback("unknown")

    if mode == "meta_trendmr_fulltrend_fallback_v1":
        if state == "trend_up":
            return _override(
                selected_variant="mr_vwap_zscore_v2",
                allow_long=True,
                allow_short=True,
                route_state="trend_up",
            )
        if state == "trend_down":
            return _trend_down_guarded_fallback()
        if state in {"low_confidence", "range_low_vol", "range_high_vol", "event_gap", "transition", "unknown"}:
            return _fallback(state)
        return _fallback("unknown")

    if mode == "meta_trendmr_lowconf_guard_v1":
        if state == "low_confidence":
            return _low_confidence_guard()
        if state == "trend_up":
            return _override(
                selected_variant="mr_vwap_zscore_v2",
                allow_long=True,
                allow_short=True,
                route_state="trend_up",
            )
        if state == "trend_down":
            return _trend_down_guarded_fallback()
        if state in {"range_low_vol", "range_high_vol", "event_gap", "transition", "unknown"}:
            return _fallback(state)
        return _fallback("unknown")

    if mode == "meta_trendmr_lowconf_guard_trendcap_v1":
        if state == "low_confidence":
            return _low_confidence_guard()
        if state == "trend_up":
            return _trend_up_trendcap_override()
        if state == "trend_down":
            return _trend_down_guarded_fallback()
        if state in {"range_low_vol", "range_high_vol", "event_gap", "transition", "unknown"}:
            return _fallback(state)
        return _fallback("unknown")

    if mode == "meta_trendmr_lowconf_guard_eventgap_v1":
        if state == "low_confidence":
            return _low_confidence_guard()
        if state == "trend_up":
            return _override(
                selected_variant="mr_vwap_zscore_v2",
                allow_long=True,
                allow_short=True,
                route_state="trend_up",
            )
        if state == "trend_down":
            return _trend_down_guarded_fallback()
        if state == "event_gap":
            return _event_gap_guard()
        if state in {"range_low_vol", "range_high_vol", "transition", "unknown"}:
            return _fallback(state)
        return _fallback("unknown")

    if mode == "meta_trendmr_lowconf_guard_trendcap_eventgap_v1":
        if state == "low_confidence":
            return _low_confidence_guard()
        if state == "trend_up":
            return _trend_up_trendcap_override()
        if state == "trend_down":
            return _trend_down_guarded_fallback()
        if state == "event_gap":
            return _event_gap_guard()
        if state in {"range_low_vol", "range_high_vol", "transition", "unknown"}:
            return _fallback(state)
        return _fallback("unknown")

    if mode == "meta_trendmr_lowconf_guard_trendcap_eventgap_soft_v1":
        if state == "low_confidence":
            return _low_confidence_guard()
        if state == "trend_up":
            return _trend_up_trendcap_override()
        if state == "trend_down":
            return _trend_down_guarded_fallback()
        if state == "event_gap":
            return _event_gap_softcap_fallback()
        if state in {"range_low_vol", "range_high_vol", "transition", "unknown"}:
            return _fallback(state)
        return _fallback("unknown")

    if mode == "meta_trendmr_lowconf_guard_trendcap_eventgap_soft_rangelow_v1":
        if state == "low_confidence":
            return _low_confidence_guard()
        if state == "trend_up":
            return _trend_up_trendcap_override()
        if state == "trend_down":
            return _trend_down_guarded_fallback()
        if state == "event_gap":
            return _event_gap_softcap_fallback()
        if state == "range_low_vol":
            return _range_low_vol_tight_guard()
        if state in {"range_high_vol", "transition", "unknown"}:
            return _fallback(state)
        return _fallback("unknown")

    if mode == "meta_trendmr_lowconf_guard_trendcap_eventgap_soft_rangelow_transition_v1":
        if state == "low_confidence":
            return _low_confidence_guard()
        if state == "trend_up":
            return _trend_up_trendcap_override()
        if state == "trend_down":
            return _trend_down_guarded_fallback()
        if state == "event_gap":
            return _event_gap_softcap_fallback()
        if state == "range_low_vol":
            return _range_low_vol_tight_guard()
        if state == "transition":
            return _transition_high_rv_wide_guard()
        if state in {"range_high_vol", "unknown"}:
            return _fallback(state)
        return _fallback("unknown")

    if state == "trend_up":
        return _override(selected_variant="orb_momentum_v1", allow_long=True, allow_short=False)
    if state == "trend_down":
        return _override(selected_variant="orb_momentum_v1", allow_long=False, allow_short=True)
    if state == "range_low_vol":
        return _override(selected_variant="mr_vwap_zscore_v2", allow_long=True, allow_short=True)
    if state in {"range_high_vol", "event_gap"}:
        return _override(selected_variant="orb_failure_fade", allow_long=True, allow_short=True)
    if state == "transition":
        return _skip("transition_skip")
    if state == "unknown":
        return _skip("unknown_state_skip")
    return _finish()


def _serialize_backtest_trade(trade: BacktestTrade) -> Dict[str, Any]:
    return {
        "trade_id": trade.trade_id,
        "signal_id": trade.signal_id,
        "ticker": trade.ticker,
        "option_symbol": trade.option_symbol,
        "entry_ts": trade.entry_ts.isoformat() if isinstance(trade.entry_ts, datetime) else str(trade.entry_ts),
        "exit_ts": trade.exit_ts.isoformat() if isinstance(trade.exit_ts, datetime) else str(trade.exit_ts),
        "side": trade.side,
        "qty": int(trade.qty),
        "entry_price": float(trade.entry_price),
        "exit_price": float(trade.exit_price),
        "pnl": float(trade.pnl),
        "return_pct": float(trade.return_pct),
        "status": trade.status,
        "metadata": dict(trade.metadata or {}),
    }


def _summarize_trades(
    trades: List[BacktestTrade],
    returns: List[float],
    initial_equity: float,
    final_equity: float,
    start: datetime,
    end: datetime,
) -> Dict[str, Any]:
    total_return = (final_equity / initial_equity) - 1.0 if initial_equity > 0 else 0.0
    years = max((end - start).days / 365.25, 1.0 / 365.25)
    cagr = ((final_equity / initial_equity) ** (1.0 / years) - 1.0) if initial_equity > 0 else 0.0

    win_rate = 0.0
    if trades:
        win_rate = sum(1 for trade in trades if trade.pnl > 0) / len(trades)

    avg_return = _mean_fast(returns) if returns else 0.0
    sharpe = 0.0
    if len(returns) > 1:
        volatility = pstdev(returns)
        if volatility > 0:
            sharpe = (avg_return / volatility) * sqrt(252.0)

    sortino = 0.0
    if returns:
        downside_squares = [min(value, 0.0) ** 2 for value in returns]
        downside_deviation = sqrt(sum(downside_squares) / len(downside_squares))
        if downside_deviation > 0:
            sortino = (avg_return / downside_deviation) * sqrt(252.0)

    max_drawdown = _max_drawdown(initial_equity=initial_equity, trades=trades)

    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "trades": len(trades),
        "initial_equity": round(initial_equity, 2),
        "final_equity": round(final_equity, 2),
        "total_return": round(total_return, 6),
        "cagr": round(cagr, 6),
        "win_rate": round(win_rate, 6),
        "avg_trade_return": round(avg_return, 6),
        "sharpe": round(sharpe, 6),
        "sortino": round(sortino, 6),
        "max_drawdown": round(max_drawdown, 6),
    }


def _max_drawdown(initial_equity: float, trades: List[BacktestTrade]) -> float:
    high_water = initial_equity
    equity = initial_equity
    max_dd = 0.0
    for trade in trades:
        equity += trade.pnl
        if equity > high_water:
            high_water = equity
        drawdown = (equity / high_water) - 1.0 if high_water > 0 else 0.0
        if drawdown < max_dd:
            max_dd = drawdown
    return max_dd


_simulate_historical_option_trade_impl = IntradayOptionsBacktester._simulate_historical_option_trade


from . import intraday_contracts as _intraday_contracts
from . import intraday_market as _intraday_market
from . import intraday_pricing as _intraday_pricing

for _name in (
    "_clear_reused_runtime_state",
    "_market_data_cache_stats",
    "_load_rows_with_market_backend",
    "_load_option_chain_snapshot",
    "_load_option_chain_snapshot_index",
    "_load_session_bars",
    "_load_session_bars_range",
    "_prime_session_bar_cache",
    "_load_premarket_bars",
    "_load_option_bars",
    "_load_option_quotes",
):
    setattr(
        IntradayOptionsBacktester,
        _name,
        getattr(_intraday_market, _name),
    )
for _name in (
    "_select_contract",
    "_load_contract_pool_for_day",
    "_select_vertical_short_leg",
    "_select_vertical_credit_long_leg",
):
    setattr(
        IntradayOptionsBacktester,
        _name,
        getattr(_intraday_contracts, _name),
    )
for _name in ("_simulate_historical_option_trade",):
    setattr(
        IntradayOptionsBacktester,
        _name,
        getattr(_intraday_pricing, _name),
    )
for _name in (
    "_map_alpaca_option_bar",
    "_map_alpaca_option_quote",
    "_map_alpaca_stock_bar",
    "_as_utc_aware",
    "_as_et",
    "_parse_hhmm",
    "_default_entry_start",
    "_bars_through_et_time",
    "_iter_dates",
    "_first_bar_on_or_after",
    "_bar_index_by_ts",
    "_next_observable_exit_target",
    "_quotes_in_window",
    "_iter_quote_pairs_in_window",
    "_apply_option_premium_stop_from_quotes",
    "_apply_vertical_debit_premium_exits_from_quotes",
    "_apply_option_premium_stop",
    "_apply_vertical_credit_premium_exits",
    "_apply_vertical_debit_premium_exits",
    "_first_quote_on_or_after",
    "_jittered_delay_minutes",
    "_snap_to_poll_boundary",
    "_apply_execution_timing_model",
    "_safe_float",
    "_causal_bar_fill_price",
    "_option_qty_for_risk",
    "_option_intrinsic_value",
    "_expected_underlying_target_move",
    "_normalize_regime_label",
    "_empty_regime_label_counts",
    "_empty_regime_v2_state_counts",
    "_parse_regime_label_allowlist",
    "_route_strategy_for_regime_v2",
    "_serialize_backtest_trade",
    "_summarize_trades",
    "_max_drawdown",
):
    globals()[_name] = getattr(_intraday_pricing, _name)
