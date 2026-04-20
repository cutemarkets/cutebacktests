from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, time, timedelta, timezone
from functools import lru_cache
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo

from .lfcm import (
    LFCMConfig as _LFCMConfig,
    find_lfcm_setup as _find_lfcm_setup,
    resolve_lfcm_exit as _resolve_lfcm_exit,
)
from .mean_reversion_intraday import (
    find_mr_vwap_exhaustion_setup_with_audit,
    find_mr_vwap_setup_with_audit,
    find_mr_vwap_zscore_setup_with_audit,
    resolve_mr_vwap_exit,
)


_ET_ZONE = ZoneInfo("America/New_York")


def _mean_fast(values: Iterable[float]) -> float:
    total = 0.0
    count = 0
    for value in values:
        total += float(value)
        count += 1
    return (total / float(count)) if count > 0 else 0.0


@dataclass
class IntradayStrategyConfig:
    opening_range_minutes: int = 5
    entry_start_time: str = "09:35"
    entry_cutoff_time: str = "12:00"
    exit_time: str = "15:55"
    allowed_weekdays_et: str = ""
    strategy_variant: str = (
        "orb_qc"  # orb_qc | orb_momentum_v1 | orb_vwap_reclaim_v1 | orb_trend_pullback_v1 | orb_event_drive_v1 | orb_transition_compression_v1 | orb_trend_short | orb_failure_fade | failed_break_reclaim_v1 | pause_go_continuation_v1 | vwap_rollover_short_v1 | orb_fib_pullback | mr_vwap_revert_v1 | mr_vwap_zscore_v2 | mr_overnight_regime_v1 | opening_drive_pullback_v1 | opening_exhaustion_reversal_v1 | relative_strength_continuation_v1 | proxy_vwap_reclaim_v1
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
    mr_take_profit_mode: str = "vwap"  # vwap | rr | none
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

    option_min_open_interest: int = 0
    require_option_microstructure_filter: bool = False
    option_min_dte: int = 0
    option_target_dte: int = 1
    option_max_dte: int = 7
    option_min_entry_volume: int = 0
    option_max_entry_bar_range_pct: float = 1.0
    option_min_entry_price: float = 0.0
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
    option_risk_sizing_mode: str = "premium_at_risk"
    option_take_profit_pct: float = 0.0
    option_max_loss_pct: float = 0.0
    option_min_expected_move_to_extrinsic_ratio: float = 0.0
    option_min_expected_move_to_spread_ratio: float = 0.0
    option_min_expected_move_to_debit_ratio: float = 0.0
    option_post_selection_conversion_mode: str = "legacy"
    option_post_selection_max_alternates: int = 0
    option_post_selection_max_final_rank: int = 0
    option_post_selection_max_final_strike_distance_steps: int = 0
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
    option_structure_filter_enabled: bool = False
    option_structure_min_open_interest: int = 0
    option_structure_min_entry_volume: int = 0
    option_structure_max_entry_spread_pct: float = 1.0
    option_structure_max_entry_bar_range_pct: float = 1.0
    option_structure_min_entry_price: float = 0.0
    option_sizing_include_commission: bool = True
    option_sizing_min_entry_price: float = 0.05
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
    option_tradability_availability_mode: str = "strict_historical"
    option_min_quote_coverage_pct: float = 0.0
    option_min_chain_coverage_pct: float = 0.0
    option_liquidity_sampling_days: int = 90
    option_cost_speed_limit_ratio: float = 1.0
    option_tradeable_after_sample_days: int = 1
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
    require_vol_regime_filter: bool = False
    vol_regime_min: float = 0.0
    vol_regime_max: float = 1000.0
    require_prior_day_inside_bar: bool = False
    require_prior_day_range_filter: bool = False
    prior_day_range_max_pct: float = 1.0
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


def _parse_hhmm_list(value: str, default_value: str) -> List[time]:
    text = (value or "").strip() or default_value
    parts = [part.strip() for part in text.replace(";", ",").split(",") if part.strip()]
    if not parts:
        parts = [default_value]
    return [_parse_hhmm(part, default_value) for part in parts]


def _is_in_macro_release_block(bar_time: time, release_times: List[time], block_minutes: int) -> bool:
    effective_block = max(int(block_minutes), 0)
    if effective_block <= 0 or not release_times:
        return False
    bar_minute = (bar_time.hour * 60) + bar_time.minute
    for release_time in release_times:
        release_minute = (release_time.hour * 60) + release_time.minute
        if release_minute <= bar_minute < (release_minute + effective_block):
            return True
    return False


def _default_entry_start(opening_range_minutes: int) -> str:
    effective = max(int(opening_range_minutes), 1)
    minute_total = (9 * 60) + 30 + effective
    hour = minute_total // 60
    minute = minute_total % 60
    return f"{hour:02d}:{minute:02d}"


@lru_cache(maxsize=262144)
def _to_et_time(ts: datetime) -> time:
    if ts.tzinfo is None:
        aware = ts.replace(tzinfo=timezone.utc)
    else:
        aware = ts.astimezone(timezone.utc)
    return aware.astimezone(_ET_ZONE).time()


def _ema_series(values: List[float], period: int) -> List[float]:
    if not values:
        return []
    effective_period = max(int(period), 1)
    alpha = 2.0 / (effective_period + 1.0)
    out: List[float] = []
    ema = values[0]
    for value in values:
        ema = (alpha * value) + ((1.0 - alpha) * ema)
        out.append(ema)
    return out


def _running_vwap_series(session_bars: List[Dict[str, Any]]) -> List[float]:
    out: List[float] = []
    cumulative_notional = 0.0
    cumulative_volume = 0.0
    for bar in session_bars:
        high_price = float(bar.get("high") or 0.0)
        low_price = float(bar.get("low") or 0.0)
        close_price = float(bar.get("close") or 0.0)
        volume = max(float(bar.get("volume") or 0.0), 0.0)
        typical_price = (high_price + low_price + close_price) / 3.0 if close_price > 0 else 0.0
        cumulative_notional += typical_price * volume
        cumulative_volume += volume
        if cumulative_volume > 0:
            out.append(cumulative_notional / cumulative_volume)
        else:
            out.append(0.0)
    return out


def _adx_series(highs: List[float], lows: List[float], closes: List[float], period: int) -> List[float]:
    size = min(len(highs), len(lows), len(closes))
    if size == 0:
        return []
    effective_period = max(int(period), 1)
    highs = highs[:size]
    lows = lows[:size]
    closes = closes[:size]

    true_ranges: List[float] = [max(highs[0] - lows[0], 0.0)]
    plus_dm: List[float] = [0.0]
    minus_dm: List[float] = [0.0]
    for idx in range(1, size):
        up_move = highs[idx] - highs[idx - 1]
        down_move = lows[idx - 1] - lows[idx]
        plus_dm.append(up_move if up_move > down_move and up_move > 0 else 0.0)
        minus_dm.append(down_move if down_move > up_move and down_move > 0 else 0.0)
        true_ranges.append(
            max(
                highs[idx] - lows[idx],
                abs(highs[idx] - closes[idx - 1]),
                abs(lows[idx] - closes[idx - 1]),
            )
        )

    adx_values: List[float] = [0.0] * size
    if size <= effective_period:
        return adx_values

    smooth_tr = sum(true_ranges[1 : effective_period + 1])
    smooth_plus = sum(plus_dm[1 : effective_period + 1])
    smooth_minus = sum(minus_dm[1 : effective_period + 1])
    dx_values: List[float] = [0.0] * size

    for idx in range(effective_period, size):
        if idx > effective_period:
            smooth_tr = smooth_tr - (smooth_tr / effective_period) + true_ranges[idx]
            smooth_plus = smooth_plus - (smooth_plus / effective_period) + plus_dm[idx]
            smooth_minus = smooth_minus - (smooth_minus / effective_period) + minus_dm[idx]
        if smooth_tr <= 0:
            dx_values[idx] = 0.0
            continue
        plus_di = 100.0 * smooth_plus / smooth_tr
        minus_di = 100.0 * smooth_minus / smooth_tr
        denom = plus_di + minus_di
        dx_values[idx] = 0.0 if denom <= 0 else 100.0 * abs(plus_di - minus_di) / denom

    adx_start = (effective_period * 2) - 1
    if adx_start >= size:
        return adx_values

    seed = dx_values[effective_period : adx_start + 1]
    adx_values[adx_start] = _mean_fast(seed) if seed else 0.0
    for idx in range(adx_start + 1, size):
        adx_values[idx] = ((adx_values[idx - 1] * (effective_period - 1)) + dx_values[idx]) / effective_period
    return adx_values


def _compute_stop_price(
    cfg: IntradayStrategyConfig,
    direction: int,
    orb_high: float,
    orb_low: float,
    breakout_high: float,
    breakout_low: float,
    entry_price: float,
    atr_value: Optional[float],
) -> Optional[float]:
    mode = str(cfg.stop_mode or "range").strip().lower()
    if mode == "breakout_candle":
        stop_price = breakout_low if direction > 0 else breakout_high
    elif mode == "opening_bar_atr":
        if atr_value is None or atr_value <= 0:
            return None
        distance = max(float(cfg.stop_loss_atr_distance), 0.0) * atr_value
        stop_price = (orb_high - distance) if direction > 0 else (orb_low + distance)
    else:
        stop_price = orb_low if direction > 0 else orb_high

    if direction > 0 and stop_price >= entry_price:
        return None
    if direction < 0 and stop_price <= entry_price:
        return None
    return stop_price


def _next_bar_open_entry(
    session_bars: Sequence[Dict[str, Any]],
    *,
    signal_idx: int,
) -> Tuple[Optional[int], Optional[Dict[str, Any]], float]:
    entry_idx = int(signal_idx) + 1
    if entry_idx < 0 or entry_idx >= len(session_bars):
        return None, None, 0.0
    entry_bar = session_bars[entry_idx]
    return entry_idx, entry_bar, float(entry_bar.get("open") or 0.0)


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _inc_reason(counter: Dict[str, int], reason: str, amount: int = 1) -> None:
    key = str(reason or "unknown").strip() or "unknown"
    counter[key] = int(counter.get(key) or 0) + max(int(amount), 1)


def _relative_volume_rejection_reason(
    cfg: IntradayStrategyConfig,
    relative_opening_volume: Optional[float],
) -> Optional[str]:
    if not bool(getattr(cfg, "require_relative_volume", False)):
        return None
    rel_opening_vol = _safe_float(relative_opening_volume)
    if rel_opening_vol is None or rel_opening_vol < float(getattr(cfg, "relative_volume_min", 0.0) or 0.0):
        return "relative_volume_filter"
    relative_volume_max = _safe_float(getattr(cfg, "relative_volume_max", 0.0))
    if relative_volume_max is not None and relative_volume_max > 0.0 and rel_opening_vol > relative_volume_max:
        return "relative_volume_max_filter"
    return None


def _premarket_gate_enabled(cfg: IntradayStrategyConfig) -> bool:
    if bool(getattr(cfg, "require_premarket_context", False)):
        return True
    return any(
        float(getattr(cfg, field_name, 0.0) or 0.0) > 0.0
        for field_name in (
            "premarket_bars_min",
            "premarket_volume_pct_adv_min",
            "premarket_gap_abs_return_min",
            "premarket_range_min_pct",
            "recent_daily_volume_ratio_min",
        )
    )


def _passes_premarket_gate_with_audit(
    *,
    cfg: IntradayStrategyConfig,
    preopen_context: Optional[Dict[str, Any]],
    audit: Dict[str, Any],
) -> bool:
    if not _premarket_gate_enabled(cfg):
        return True
    ctx = dict(preopen_context or {})
    if not ctx:
        _inc_reason(audit["rejections"], "missing_premarket_context")
        return False

    premarket_bar_count = int(ctx.get("premarket_bar_count") or 0)
    if premarket_bar_count < max(int(getattr(cfg, "premarket_bars_min", 0) or 0), 0):
        _inc_reason(audit["rejections"], "premarket_bars_min")
        return False

    min_volume_pct_adv = max(float(getattr(cfg, "premarket_volume_pct_adv_min", 0.0) or 0.0), 0.0)
    if min_volume_pct_adv > 0.0:
        volume_pct_adv = _safe_float(ctx.get("premarket_volume_pct_of_adv"))
        if volume_pct_adv is None or volume_pct_adv < min_volume_pct_adv:
            _inc_reason(audit["rejections"], "premarket_volume_pct_adv_min")
            return False

    min_gap_abs_return = max(float(getattr(cfg, "premarket_gap_abs_return_min", 0.0) or 0.0), 0.0)
    if min_gap_abs_return > 0.0:
        premarket_gap_abs_return = abs(_safe_float(ctx.get("premarket_last_gap_pct")) or 0.0)
        if premarket_gap_abs_return < min_gap_abs_return:
            _inc_reason(audit["rejections"], "premarket_gap_abs_return_min")
            return False

    premarket_range_pct = _safe_float(ctx.get("premarket_range_pct"))
    min_range_pct = max(float(getattr(cfg, "premarket_range_min_pct", 0.0) or 0.0), 0.0)
    if min_range_pct > 0.0 and (premarket_range_pct is None or premarket_range_pct < min_range_pct):
        _inc_reason(audit["rejections"], "premarket_range_min_pct")
        return False

    max_range_pct = max(float(getattr(cfg, "premarket_range_max_pct", 0.0) or 0.0), min_range_pct)
    if premarket_range_pct is not None and premarket_range_pct > max_range_pct:
        _inc_reason(audit["rejections"], "premarket_range_max_pct")
        return False

    recent_daily_volume_ratio = _safe_float(ctx.get("recent_daily_volume_ratio_5d_20d"))
    min_recent_volume_ratio = max(float(getattr(cfg, "recent_daily_volume_ratio_min", 0.0) or 0.0), 0.0)
    if min_recent_volume_ratio > 0.0 and (
        recent_daily_volume_ratio is None or recent_daily_volume_ratio < min_recent_volume_ratio
    ):
        _inc_reason(audit["rejections"], "recent_daily_volume_ratio_min")
        return False
    return True


def _parse_csv_tickers(value: Any) -> List[str]:
    text = str(value or "").strip()
    if not text:
        return []
    out: List[str] = []
    seen: set[str] = set()
    for raw in text.split(","):
        ticker = str(raw or "").strip().upper()
        if not ticker or ticker in seen:
            continue
        seen.add(ticker)
        out.append(ticker)
    return out


_PAIRS_HEDGE_DEFAULTS: Dict[str, str] = {
    "SPY": "QQQ",
    "QQQ": "SPY",
    "IWM": "SPY",
    "DIA": "SPY",
    "TQQQ": "QQQ",
    "SQQQ": "QQQ",
}

_DISPERSION_PROXY_DEFAULTS: Dict[str, str] = {
    "SPY": "QQQ",
    "QQQ": "SPY",
    "IWM": "SPY",
    "DIA": "SPY",
    "TQQQ": "QQQ",
    "SQQQ": "QQQ",
    "SMH": "QQQ",
    "XLK": "QQQ",
    "XLF": "SPY",
    "XLE": "SPY",
    "XLI": "SPY",
    "XLV": "SPY",
    "XLP": "SPY",
    "GLD": "SPY",
    "TLT": "SPY",
}


def _default_dispersion_proxy_ticker(primary: str) -> str:
    if primary in _DISPERSION_PROXY_DEFAULTS:
        return _DISPERSION_PROXY_DEFAULTS[primary]
    if primary == "SPY":
        return "QQQ"
    return "SPY"


def resolve_pairs_hedge_ticker(primary_ticker: str, configured_value: str) -> str:
    primary = str(primary_ticker or "").strip().upper()
    configured = str(configured_value or "").strip().upper()
    if configured and configured not in {"AUTO", "DEFAULT", "NONE"}:
        return configured
    return _PAIRS_HEDGE_DEFAULTS.get(primary, "")


def resolve_dispersion_proxy_ticker(primary_ticker: str, configured_value: str) -> str:
    primary = str(primary_ticker or "").strip().upper()
    configured = str(configured_value or "").strip().upper()
    if configured == "AUTO_SPY_DIA":
        if primary == "SPY":
            return "DIA"
        return _default_dispersion_proxy_ticker(primary)
    if configured and configured not in {"AUTO", "DEFAULT", "NONE"}:
        return configured
    return _default_dispersion_proxy_ticker(primary)


def _bar_by_ts(bars: List[Dict[str, Any]]) -> Dict[datetime, Dict[str, Any]]:
    out: Dict[datetime, Dict[str, Any]] = {}
    for bar in bars:
        ts = bar.get("ts")
        if isinstance(ts, datetime):
            out[ts] = bar
    return out


def _pair_close_at(
    by_ts: Dict[datetime, Dict[str, Any]],
    ts: Any,
) -> Optional[float]:
    if not isinstance(ts, datetime):
        return None
    bar = by_ts.get(ts)
    if not isinstance(bar, dict):
        return None
    close_price = _safe_float(bar.get("close"))
    if close_price is None or close_price <= 0:
        return None
    return close_price


def _aligned_proxy_series(
    session_bars: List[Dict[str, Any]],
    proxy_session_bars: Optional[List[Dict[str, Any]]],
) -> Tuple[Dict[datetime, Dict[str, Any]], List[int], List[float], List[float], Dict[int, int]]:
    pair_by_ts = _bar_by_ts(proxy_session_bars or [])
    aligned_indices: List[int] = []
    primary_closes: List[float] = []
    proxy_closes: List[float] = []
    for idx, bar in enumerate(session_bars):
        close_price = _safe_float(bar.get("close"))
        proxy_close = _pair_close_at(pair_by_ts, bar.get("ts"))
        if close_price is None or close_price <= 0 or proxy_close is None:
            continue
        aligned_indices.append(idx)
        primary_closes.append(float(close_price))
        proxy_closes.append(float(proxy_close))
    aligned_pos_by_idx = {idx: pos for pos, idx in enumerate(aligned_indices)}
    return pair_by_ts, aligned_indices, primary_closes, proxy_closes, aligned_pos_by_idx


def _beta_corr_over_lookback(
    primary_closes: List[float],
    proxy_closes: List[float],
    aligned_pos: int,
    lookback: int,
) -> Tuple[Optional[float], Optional[float]]:
    start = aligned_pos - lookback
    count = 0
    sum_x = 0.0
    sum_y = 0.0
    sum_xx = 0.0
    sum_yy = 0.0
    sum_xy = 0.0
    for pos in range(start + 1, aligned_pos + 1):
        x_prev = primary_closes[pos - 1]
        x_now = primary_closes[pos]
        y_prev = proxy_closes[pos - 1]
        y_now = proxy_closes[pos]
        if x_prev <= 0 or y_prev <= 0:
            continue
        x_ret = (x_now / x_prev) - 1.0
        y_ret = (y_now / y_prev) - 1.0
        count += 1
        sum_x += x_ret
        sum_y += y_ret
        sum_xx += x_ret * x_ret
        sum_yy += y_ret * y_ret
        sum_xy += x_ret * y_ret
    if count < 2:
        return None, None

    count_f = float(count)
    mean_x = sum_x / count_f
    mean_y = sum_y / count_f
    cov = sum_xy - (count_f * mean_x * mean_y)
    var_y = sum_yy - (count_f * mean_y * mean_y)
    if var_y <= 0.0:
        return None, None

    beta = cov / var_y
    if count < 3:
        return beta, None

    var_x = sum_xx - (count_f * mean_x * mean_x)
    den = (var_x * var_y) ** 0.5
    corr = (cov / den) if den > 0.0 else None
    return beta, corr


def _spread_window_stats(
    primary_closes: Sequence[float],
    proxy_closes: Sequence[float],
    beta: float,
    start_pos: int,
    end_pos: int,
) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
    count = 0
    sum_spread = 0.0
    sum_spread_sq = 0.0
    current_spread: Optional[float] = None
    previous_spread: Optional[float] = None
    for pos in range(start_pos, end_pos + 1):
        spread = float(primary_closes[pos]) - (float(beta) * float(proxy_closes[pos]))
        previous_spread = current_spread
        current_spread = spread
        count += 1
        sum_spread += spread
        sum_spread_sq += spread * spread
    if count <= 0 or current_spread is None:
        return None, None, None, None
    spread_mean = sum_spread / float(count)
    spread_var = max((sum_spread_sq / float(count)) - (spread_mean * spread_mean), 0.0)
    spread_std = spread_var ** 0.5
    if previous_spread is None:
        previous_spread = current_spread
    return spread_mean, spread_std, current_spread, previous_spread


def _find_pairs_spread_setup_with_audit(
    session_bars: List[Dict[str, Any]],
    pair_session_bars: Optional[List[Dict[str, Any]]],
    cfg: IntradayStrategyConfig,
    relative_opening_volume: Optional[float],
    atr_value: Optional[float],
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    audit: Dict[str, Any] = {
        "strategy_variant": "pairs_spread_v1",
        "opportunities_before_filters": 0,
        "opportunities_after_filters": 0,
        "rejections": {},
    }
    if not session_bars or not pair_session_bars:
        _inc_reason(audit["rejections"], "pairs_missing_session_bars")
        return None, audit
    opening_range_count = max(int(cfg.opening_range_minutes), 1)
    warmup_needed = max(
        max(int(cfg.pairs_beta_lookback), 2),
        max(int(cfg.pairs_zscore_window), 5),
    )
    if len(session_bars) < (opening_range_count + warmup_needed + 2):
        _inc_reason(audit["rejections"], "insufficient_bars")
        return None, audit

    pair_by_ts = _bar_by_ts(pair_session_bars)
    if not pair_by_ts:
        _inc_reason(audit["rejections"], "pairs_missing_session_bars")
        return None, audit

    opening_range = session_bars[:opening_range_count]
    orb_high = max(float(bar.get("high") or 0.0) for bar in opening_range)
    orb_low = min(float(bar.get("low") or 0.0) for bar in opening_range)
    orb_open = float(opening_range[0].get("open") or 0.0)
    orb_close = float(opening_range[-1].get("close") or 0.0)
    if orb_high <= 0 or orb_low <= 0 or orb_high <= orb_low:
        _inc_reason(audit["rejections"], "invalid_opening_range")
        return None, audit
    orb_width = orb_high - orb_low
    orb_width_pct = orb_width / max(orb_open, 1.0)
    if cfg.require_or_width_filter:
        min_width = max(float(cfg.opening_range_min_width_pct), 0.0)
        max_width = max(float(cfg.opening_range_max_width_pct), min_width)
        if orb_width_pct < min_width or orb_width_pct > max_width:
            _inc_reason(audit["rejections"], "orb_width_filter")
            return None, audit

    opening_bar_direction = 0
    if orb_close > orb_open:
        opening_bar_direction = 1
    elif orb_close < orb_open:
        opening_bar_direction = -1

    entry_start = _parse_hhmm(cfg.entry_start_time, _default_entry_start(opening_range_count))
    entry_cutoff = _parse_hhmm(cfg.entry_cutoff_time, "12:00")

    beta_lookback = max(int(cfg.pairs_beta_lookback), 4)
    z_window = max(int(cfg.pairs_zscore_window), 10)
    z_entry = max(float(cfg.pairs_zscore_entry), 0.2)
    z_reentry = min(max(float(cfg.pairs_zscore_reentry), 0.0), z_entry)
    z_stop = max(float(cfg.pairs_zscore_stop), z_entry)
    min_corr = max(float(cfg.pairs_min_correlation), 0.0)
    stop_buffer_or_mult = max(float(cfg.mr_stop_buffer_or_mult), 0.0)

    primary_ticker = str(session_bars[0].get("ticker") or "").strip().upper()
    excluded_tickers = set(_parse_csv_tickers(getattr(cfg, "pairs_excluded_tickers", "")))
    if primary_ticker in excluded_tickers:
        _inc_reason(audit["rejections"], "pairs_primary_excluded")
        return None, audit

    hedge_ticker = resolve_pairs_hedge_ticker(primary_ticker, cfg.pairs_hedge_ticker)
    if not hedge_ticker:
        _inc_reason(audit["rejections"], "pairs_missing_hedge_ticker")
        return None, audit
    if hedge_ticker == primary_ticker:
        _inc_reason(audit["rejections"], "pairs_invalid_hedge_ticker")
        return None, audit
    if hedge_ticker in excluded_tickers:
        _inc_reason(audit["rejections"], "pairs_hedge_excluded")
        return None, audit

    aligned_indices: List[int] = []
    primary_closes: List[float] = []
    hedge_closes: List[float] = []
    for idx, bar in enumerate(session_bars):
        close_price = _safe_float(bar.get("close"))
        hedge_close = _pair_close_at(pair_by_ts, bar.get("ts"))
        if close_price is None or close_price <= 0 or hedge_close is None:
            continue
        aligned_indices.append(idx)
        primary_closes.append(float(close_price))
        hedge_closes.append(float(hedge_close))

    if len(aligned_indices) < (opening_range_count + warmup_needed + 2):
        _inc_reason(audit["rejections"], "pairs_insufficient_aligned_bars")
        return None, audit

    aligned_pos_by_idx = {idx: pos for pos, idx in enumerate(aligned_indices)}

    for idx in range(opening_range_count, len(session_bars) - 1):
        bar = session_bars[idx]
        bar_time = _to_et_time(bar["ts"])
        if bar_time < entry_start or bar_time > entry_cutoff:
            continue
        aligned_pos = aligned_pos_by_idx.get(idx)
        if aligned_pos is None:
            continue
        if aligned_pos < max(beta_lookback, z_window):
            continue

        relative_volume_rejection = _relative_volume_rejection_reason(cfg, relative_opening_volume)
        if relative_volume_rejection is not None:
            _inc_reason(audit["rejections"], relative_volume_rejection)
            continue
        if cfg.require_atr_filter:
            if atr_value is None or atr_value < cfg.atr_min:
                _inc_reason(audit["rejections"], "atr_filter")
                continue

        beta, corr = _beta_corr_over_lookback(primary_closes, hedge_closes, aligned_pos, beta_lookback)
        if beta is None:
            _inc_reason(audit["rejections"], "pairs_beta_invalid")
            continue
        if corr is None or abs(corr) < min_corr:
            _inc_reason(audit["rejections"], "pairs_correlation_filter")
            continue

        spread_start = aligned_pos - z_window + 1
        spread_mean, spread_std, spread_now, spread_prev = _spread_window_stats(
            primary_closes,
            hedge_closes,
            beta,
            spread_start,
            aligned_pos,
        )
        if spread_mean is None or spread_std is None or spread_now is None or spread_prev is None or spread_std <= 0:
            _inc_reason(audit["rejections"], "pairs_sigma_invalid")
            continue

        z_now = (spread_now - spread_mean) / spread_std
        z_prev = (spread_prev - spread_mean) / spread_std
        long_signal = z_prev <= -z_entry and z_now >= -z_reentry
        short_signal = z_prev >= z_entry and z_now <= z_reentry
        raw_directions: List[int] = []
        if long_signal:
            raw_directions.append(1)
        if short_signal:
            raw_directions.append(-1)
        if not raw_directions:
            continue
        audit["opportunities_before_filters"] = int(audit.get("opportunities_before_filters") or 0) + len(raw_directions)

        candidate_directions: List[int] = []
        for direction in raw_directions:
            if direction > 0 and cfg.allow_long:
                candidate_directions.append(direction)
            elif direction < 0 and cfg.allow_short:
                candidate_directions.append(direction)
            else:
                _inc_reason(audit["rejections"], "direction_not_allowed")
        if not candidate_directions:
            continue

        if cfg.use_opening_bar_direction:
            filtered = [direction for direction in candidate_directions if direction == opening_bar_direction]
            dropped = len(candidate_directions) - len(filtered)
            if dropped > 0:
                _inc_reason(audit["rejections"], "opening_bar_direction_mismatch", dropped)
            candidate_directions = filtered
            if not candidate_directions:
                continue

        direction = candidate_directions[0]
        if len(candidate_directions) > 1:
            _inc_reason(audit["rejections"], "secondary_direction_dropped", len(candidate_directions) - 1)

        entry_idx = idx + 1
        if entry_idx >= len(session_bars):
            _inc_reason(audit["rejections"], "insufficient_bars")
            continue
        entry_bar = session_bars[entry_idx]
        entry_price = float(entry_bar.get("open") or 0.0)
        if entry_price <= 0:
            _inc_reason(audit["rejections"], "invalid_entry_price")
            continue

        prev_low = float(session_bars[idx - 1].get("low") or 0.0) if idx > 0 else float(bar.get("low") or 0.0)
        prev_high = float(session_bars[idx - 1].get("high") or 0.0) if idx > 0 else float(bar.get("high") or 0.0)
        if direction > 0:
            stop_core = min(float(bar.get("low") or 0.0), prev_low, orb_low)
            stop_price = stop_core - (orb_width * stop_buffer_or_mult)
        else:
            stop_core = max(float(bar.get("high") or 0.0), prev_high, orb_high)
            stop_price = stop_core + (orb_width * stop_buffer_or_mult)
        if direction > 0 and stop_price >= entry_price:
            _inc_reason(audit["rejections"], "invalid_stop")
            continue
        if direction < 0 and stop_price <= entry_price:
            _inc_reason(audit["rejections"], "invalid_stop")
            continue

        risk_per_share = abs(entry_price - stop_price)
        if risk_per_share <= 0:
            _inc_reason(audit["rejections"], "invalid_stop")
            continue
        target_underlying: Optional[float] = None
        if cfg.take_profit_rr > 0:
            target_underlying = (
                entry_price + (risk_per_share * cfg.take_profit_rr)
                if direction > 0
                else entry_price - (risk_per_share * cfg.take_profit_rr)
            )

        audit["opportunities_after_filters"] = int(audit.get("opportunities_after_filters") or 0) + 1
        return {
            "direction": direction,
            "signal_idx": idx,
            "signal_ts": bar["ts"],
            "entry_idx": entry_idx,
            "entry_ts": entry_bar["ts"],
            "entry_underlying": entry_price,
            "stop_underlying": stop_price,
            "mr_target_underlying": target_underlying,
            "orb_high": orb_high,
            "orb_low": orb_low,
            "opening_bar_open": orb_open,
            "opening_bar_close": orb_close,
            "opening_bar_direction": opening_bar_direction,
            "trend_ema_fast": 0.0,
            "trend_ema_slow": 0.0,
            "volume_ratio": 1.0,
            "relative_opening_volume": relative_opening_volume,
            "atr_value": atr_value,
            "fvg_gap": 0.0,
            "opening_range_minutes": opening_range_count,
            "orb_width_pct": orb_width_pct,
            "strategy_variant": "pairs_spread_v1",
            "pairs_hedge_ticker": hedge_ticker,
            "pairs_beta": float(beta),
            "pairs_corr": float(corr),
            "pairs_spread_mean": float(spread_mean),
            "pairs_spread_sigma": float(spread_std),
            "pairs_zscore_at_signal": float(z_now),
            "pairs_zscore_exit": float(max(float(cfg.pairs_zscore_exit), 0.0)),
            "pairs_zscore_stop": float(z_stop),
        }, audit

    if int(audit.get("opportunities_before_filters") or 0) == 0:
        _inc_reason(audit["rejections"], "pairs_no_signal")
    return None, audit


def _find_dispersion_relative_breakout_setup_with_audit(
    session_bars: List[Dict[str, Any]],
    pair_session_bars: Optional[List[Dict[str, Any]]],
    cfg: IntradayStrategyConfig,
    relative_opening_volume: Optional[float],
    atr_value: Optional[float],
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    audit: Dict[str, Any] = {
        "strategy_variant": "dispersion_relative_breakout_v1",
        "opportunities_before_filters": 0,
        "opportunities_after_filters": 0,
        "rejections": {},
    }
    if not session_bars or not pair_session_bars:
        _inc_reason(audit["rejections"], "dispersion_missing_session_bars")
        return None, audit

    opening_range_count = max(int(cfg.opening_range_minutes), 1)
    beta_lookback = max(int(cfg.dispersion_beta_lookback), 4)
    warmup_needed = max(opening_range_count + 1, beta_lookback + 1)
    if len(session_bars) < (warmup_needed + 2):
        _inc_reason(audit["rejections"], "insufficient_bars")
        return None, audit

    pair_by_ts, aligned_indices, primary_closes, proxy_closes, aligned_pos_by_idx = _aligned_proxy_series(
        session_bars=session_bars,
        proxy_session_bars=pair_session_bars,
    )
    if not pair_by_ts:
        _inc_reason(audit["rejections"], "dispersion_missing_session_bars")
        return None, audit
    if len(aligned_indices) < (warmup_needed + 2):
        _inc_reason(audit["rejections"], "dispersion_insufficient_aligned_bars")
        return None, audit

    opening_ref_pos: Optional[int] = None
    for pos, idx in enumerate(aligned_indices):
        if idx >= (opening_range_count - 1):
            opening_ref_pos = pos
            break
    if opening_ref_pos is None:
        _inc_reason(audit["rejections"], "dispersion_missing_opening_reference")
        return None, audit

    opening_range = session_bars[:opening_range_count]
    orb_high = max(float(bar.get("high") or 0.0) for bar in opening_range)
    orb_low = min(float(bar.get("low") or 0.0) for bar in opening_range)
    orb_open = float(opening_range[0].get("open") or 0.0)
    orb_close = float(opening_range[-1].get("close") or 0.0)
    if orb_high <= 0 or orb_low <= 0 or orb_high <= orb_low:
        _inc_reason(audit["rejections"], "invalid_opening_range")
        return None, audit
    orb_width = orb_high - orb_low
    orb_width_pct = orb_width / max(orb_open, 1.0)
    if cfg.require_or_width_filter:
        min_width = max(float(cfg.opening_range_min_width_pct), 0.0)
        max_width = max(float(cfg.opening_range_max_width_pct), min_width)
        if orb_width_pct < min_width or orb_width_pct > max_width:
            _inc_reason(audit["rejections"], "orb_width_filter")
            return None, audit

    opening_bar_direction = 0
    if orb_close > orb_open:
        opening_bar_direction = 1
    elif orb_close < orb_open:
        opening_bar_direction = -1

    entry_start = _parse_hhmm(cfg.entry_start_time, _default_entry_start(opening_range_count))
    entry_cutoff = _parse_hhmm(cfg.entry_cutoff_time, "12:00")
    min_corr = max(float(cfg.dispersion_min_correlation), 0.0)
    rel_edge_entry = max(float(cfg.dispersion_rel_strength_entry_pct), 0.0)
    primary_move_min = max(float(cfg.dispersion_primary_min_abs_move_pct), 0.0)
    proxy_move_max = max(float(cfg.dispersion_proxy_max_abs_move_pct), 0.0)
    beta_shock_max = max(float(getattr(cfg, "dispersion_beta_shock_max_pct", 1.0)), 0.0)
    rel_strength_confirm = max(float(getattr(cfg, "dispersion_rel_strength_confirm_pct", 0.0)), 0.0)
    time_to_work_bars = max(int(getattr(cfg, "dispersion_time_to_work_bars", 0)), 0)
    rel_strength_floor_frac = max(float(getattr(cfg, "dispersion_breakout_rel_strength_floor_frac", 0.0)), 0.0)
    stop_buffer_or_mult = max(float(cfg.mr_stop_buffer_or_mult), 0.0)
    breakout_buffer = orb_width * max(float(cfg.compression_breakout_buffer_or_frac), 0.0)
    primary_ref = primary_closes[opening_ref_pos]
    proxy_ref = proxy_closes[opening_ref_pos]
    primary_ticker = str(session_bars[0].get("ticker") or "").strip().upper()
    proxy_ticker = resolve_dispersion_proxy_ticker(primary_ticker, cfg.dispersion_proxy_ticker)

    for idx in range(opening_range_count, len(session_bars) - 1):
        bar = session_bars[idx]
        bar_time = _to_et_time(bar["ts"])
        if bar_time < entry_start or bar_time > entry_cutoff:
            continue
        aligned_pos = aligned_pos_by_idx.get(idx)
        if aligned_pos is None or aligned_pos <= opening_ref_pos or aligned_pos < beta_lookback:
            continue

        relative_volume_rejection = _relative_volume_rejection_reason(cfg, relative_opening_volume)
        if relative_volume_rejection is not None:
            _inc_reason(audit["rejections"], relative_volume_rejection)
            continue
        if cfg.require_atr_filter:
            if atr_value is None or atr_value < cfg.atr_min:
                _inc_reason(audit["rejections"], "atr_filter")
                continue

        beta, corr = _beta_corr_over_lookback(primary_closes, proxy_closes, aligned_pos, beta_lookback)
        if beta is None:
            _inc_reason(audit["rejections"], "dispersion_beta_invalid")
            continue
        if corr is None or abs(corr) < min_corr:
            _inc_reason(audit["rejections"], "dispersion_correlation_filter")
            continue

        close_price = _safe_float(bar.get("close"))
        if close_price is None or close_price <= 0 or primary_ref <= 0 or proxy_ref <= 0:
            continue
        proxy_close = proxy_closes[aligned_pos]
        primary_move = (float(close_price) / primary_ref) - 1.0
        proxy_move = (proxy_close / proxy_ref) - 1.0
        rel_edge = primary_move - (beta * proxy_move)
        beta_shock = abs(beta * proxy_move)
        proxy_abs_move = abs(proxy_move)
        primary_abs_move = abs(primary_move)
        if beta_shock_max > 0 and beta_shock > beta_shock_max:
            _inc_reason(audit["rejections"], "dispersion_beta_shock_filter")
            continue

        raw_directions: List[int] = []
        if (
            float(close_price) >= (orb_high + breakout_buffer)
            and rel_edge >= rel_edge_entry
            and abs(rel_edge) >= rel_strength_confirm
            and primary_abs_move >= primary_move_min
            and (proxy_abs_move <= proxy_move_max or rel_edge >= (rel_edge_entry * 1.5))
        ):
            raw_directions.append(1)
        if (
            float(close_price) <= (orb_low - breakout_buffer)
            and rel_edge <= -rel_edge_entry
            and abs(rel_edge) >= rel_strength_confirm
            and primary_abs_move >= primary_move_min
            and (proxy_abs_move <= proxy_move_max or rel_edge <= -(rel_edge_entry * 1.5))
        ):
            raw_directions.append(-1)
        if not raw_directions:
            continue
        audit["opportunities_before_filters"] = int(audit.get("opportunities_before_filters") or 0) + len(raw_directions)

        candidate_directions: List[int] = []
        for direction in raw_directions:
            if direction > 0 and cfg.allow_long:
                candidate_directions.append(direction)
            elif direction < 0 and cfg.allow_short:
                candidate_directions.append(direction)
            else:
                _inc_reason(audit["rejections"], "direction_not_allowed")
        if not candidate_directions:
            continue

        if cfg.use_opening_bar_direction:
            filtered = [direction for direction in candidate_directions if direction == opening_bar_direction]
            dropped = len(candidate_directions) - len(filtered)
            if dropped > 0:
                _inc_reason(audit["rejections"], "opening_bar_direction_mismatch", dropped)
            candidate_directions = filtered
            if not candidate_directions:
                continue

        direction = candidate_directions[0]
        if len(candidate_directions) > 1:
            _inc_reason(audit["rejections"], "secondary_direction_dropped", len(candidate_directions) - 1)

        entry_idx = idx + 1
        if entry_idx >= len(session_bars):
            _inc_reason(audit["rejections"], "insufficient_bars")
            continue
        entry_bar = session_bars[entry_idx]
        entry_price = float(entry_bar.get("open") or 0.0)
        if entry_price <= 0:
            _inc_reason(audit["rejections"], "invalid_entry_price")
            continue

        prev_low = float(session_bars[idx - 1].get("low") or 0.0) if idx > 0 else float(bar.get("low") or 0.0)
        prev_high = float(session_bars[idx - 1].get("high") or 0.0) if idx > 0 else float(bar.get("high") or 0.0)
        if direction > 0:
            stop_core = min(float(bar.get("low") or 0.0), prev_low, orb_low)
            stop_price = stop_core - (orb_width * stop_buffer_or_mult)
        else:
            stop_core = max(float(bar.get("high") or 0.0), prev_high, orb_high)
            stop_price = stop_core + (orb_width * stop_buffer_or_mult)
        if direction > 0 and stop_price >= entry_price:
            _inc_reason(audit["rejections"], "invalid_stop")
            continue
        if direction < 0 and stop_price <= entry_price:
            _inc_reason(audit["rejections"], "invalid_stop")
            continue

        risk_per_share = abs(entry_price - stop_price)
        if risk_per_share <= 0:
            _inc_reason(audit["rejections"], "invalid_stop")
            continue
        target_underlying: Optional[float] = None
        if cfg.take_profit_rr > 0:
            target_underlying = (
                entry_price + (risk_per_share * cfg.take_profit_rr)
                if direction > 0
                else entry_price - (risk_per_share * cfg.take_profit_rr)
            )

        audit["opportunities_after_filters"] = int(audit.get("opportunities_after_filters") or 0) + 1
        return {
            "direction": direction,
            "signal_idx": idx,
            "signal_ts": bar["ts"],
            "entry_idx": entry_idx,
            "entry_ts": entry_bar["ts"],
            "entry_underlying": entry_price,
            "stop_underlying": stop_price,
            "mr_target_underlying": target_underlying,
            "orb_high": orb_high,
            "orb_low": orb_low,
            "opening_bar_open": orb_open,
            "opening_bar_close": orb_close,
            "opening_bar_direction": opening_bar_direction,
            "trend_ema_fast": 0.0,
            "trend_ema_slow": 0.0,
            "volume_ratio": 1.0,
            "relative_opening_volume": relative_opening_volume,
            "atr_value": atr_value,
            "fvg_gap": 0.0,
            "opening_range_minutes": opening_range_count,
            "orb_width_pct": orb_width_pct,
            "strategy_variant": "dispersion_relative_breakout_v1",
            "dispersion_proxy_ticker": proxy_ticker,
            "dispersion_beta": float(beta),
            "dispersion_corr": float(corr),
            "dispersion_primary_ref": float(primary_ref),
            "dispersion_proxy_ref": float(proxy_ref),
            "dispersion_rel_strength_at_signal": float(rel_edge),
            "dispersion_rel_strength_exit_pct": float(max(float(cfg.dispersion_rel_strength_exit_pct), 0.0)),
            "dispersion_rel_strength_stop_pct": float(max(float(cfg.dispersion_rel_strength_stop_pct), 0.0)),
            "dispersion_beta_shock_max_pct": float(beta_shock_max),
            "dispersion_time_to_work_bars": int(time_to_work_bars),
            "dispersion_breakout_rel_strength_floor_frac": float(rel_strength_floor_frac),
        }, audit

    if int(audit.get("opportunities_before_filters") or 0) == 0:
        _inc_reason(audit["rejections"], "dispersion_no_signal")
    return None, audit


def _find_dispersion_relative_revert_setup_with_audit(
    session_bars: List[Dict[str, Any]],
    pair_session_bars: Optional[List[Dict[str, Any]]],
    cfg: IntradayStrategyConfig,
    relative_opening_volume: Optional[float],
    atr_value: Optional[float],
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    audit: Dict[str, Any] = {
        "strategy_variant": "dispersion_relative_revert_v1",
        "opportunities_before_filters": 0,
        "opportunities_after_filters": 0,
        "rejections": {},
    }
    if not session_bars or not pair_session_bars:
        _inc_reason(audit["rejections"], "dispersion_missing_session_bars")
        return None, audit

    opening_range_count = max(int(cfg.opening_range_minutes), 1)
    beta_lookback = max(int(cfg.dispersion_beta_lookback), 4)
    z_window = max(int(cfg.dispersion_zscore_window), 10)
    warmup_needed = max(beta_lookback, z_window)
    if len(session_bars) < (opening_range_count + warmup_needed + 2):
        _inc_reason(audit["rejections"], "insufficient_bars")
        return None, audit

    pair_by_ts, aligned_indices, primary_closes, proxy_closes, aligned_pos_by_idx = _aligned_proxy_series(
        session_bars=session_bars,
        proxy_session_bars=pair_session_bars,
    )
    if not pair_by_ts:
        _inc_reason(audit["rejections"], "dispersion_missing_session_bars")
        return None, audit
    if len(aligned_indices) < (opening_range_count + warmup_needed + 2):
        _inc_reason(audit["rejections"], "dispersion_insufficient_aligned_bars")
        return None, audit

    opening_ref_pos: Optional[int] = None
    for pos, idx in enumerate(aligned_indices):
        if idx >= (opening_range_count - 1):
            opening_ref_pos = pos
            break
    if opening_ref_pos is None:
        _inc_reason(audit["rejections"], "dispersion_missing_opening_reference")
        return None, audit

    opening_range = session_bars[:opening_range_count]
    orb_high = max(float(bar.get("high") or 0.0) for bar in opening_range)
    orb_low = min(float(bar.get("low") or 0.0) for bar in opening_range)
    orb_open = float(opening_range[0].get("open") or 0.0)
    orb_close = float(opening_range[-1].get("close") or 0.0)
    if orb_high <= 0 or orb_low <= 0 or orb_high <= orb_low:
        _inc_reason(audit["rejections"], "invalid_opening_range")
        return None, audit
    orb_width = orb_high - orb_low
    orb_width_pct = orb_width / max(orb_open, 1.0)
    if cfg.require_or_width_filter:
        min_width = max(float(cfg.opening_range_min_width_pct), 0.0)
        max_width = max(float(cfg.opening_range_max_width_pct), min_width)
        if orb_width_pct < min_width or orb_width_pct > max_width:
            _inc_reason(audit["rejections"], "orb_width_filter")
            return None, audit

    opening_bar_direction = 0
    if orb_close > orb_open:
        opening_bar_direction = 1
    elif orb_close < orb_open:
        opening_bar_direction = -1

    entry_start = _parse_hhmm(cfg.entry_start_time, _default_entry_start(opening_range_count))
    entry_cutoff = _parse_hhmm(cfg.entry_cutoff_time, "12:00")
    z_entry = max(float(cfg.dispersion_zscore_entry), 0.2)
    z_reentry = min(max(float(cfg.dispersion_zscore_reentry), 0.0), z_entry)
    z_stop = max(float(cfg.dispersion_zscore_stop), z_entry)
    min_corr = max(float(cfg.dispersion_min_correlation), 0.0)
    proxy_move_max = max(float(cfg.dispersion_proxy_max_abs_move_pct), 0.0)
    rel_strength_confirm = max(float(getattr(cfg, "dispersion_rel_strength_confirm_pct", 0.0)), 0.0)
    zscore_improvement_min = max(float(getattr(cfg, "dispersion_zscore_improvement_min", 0.0)), 0.0)
    reversal_body_min_frac = max(float(getattr(cfg, "dispersion_reversal_body_min_frac", 0.0)), 0.0)
    reversal_wick_min_frac = max(float(getattr(cfg, "dispersion_reversal_wick_min_frac", 0.0)), 0.0)
    beta_shock_max = max(float(getattr(cfg, "dispersion_beta_shock_max_pct", 1.0)), 0.0)
    time_to_work_bars = max(int(getattr(cfg, "dispersion_time_to_work_bars", 0)), 0)
    time_to_work_improvement_min = max(float(getattr(cfg, "dispersion_time_to_work_improvement_min", 0.0)), 0.0)
    stop_buffer_or_mult = max(float(cfg.mr_stop_buffer_or_mult), 0.0)
    primary_ref = primary_closes[opening_ref_pos]
    proxy_ref = proxy_closes[opening_ref_pos]
    primary_ticker = str(session_bars[0].get("ticker") or "").strip().upper()
    proxy_ticker = resolve_dispersion_proxy_ticker(primary_ticker, cfg.dispersion_proxy_ticker)

    for idx in range(opening_range_count, len(session_bars) - 1):
        bar = session_bars[idx]
        bar_time = _to_et_time(bar["ts"])
        if bar_time < entry_start or bar_time > entry_cutoff:
            continue
        aligned_pos = aligned_pos_by_idx.get(idx)
        if aligned_pos is None or aligned_pos <= opening_ref_pos or aligned_pos < max(beta_lookback, z_window):
            continue

        relative_volume_rejection = _relative_volume_rejection_reason(cfg, relative_opening_volume)
        if relative_volume_rejection is not None:
            _inc_reason(audit["rejections"], relative_volume_rejection)
            continue
        if cfg.require_atr_filter:
            if atr_value is None or atr_value < cfg.atr_min:
                _inc_reason(audit["rejections"], "atr_filter")
                continue

        beta, corr = _beta_corr_over_lookback(primary_closes, proxy_closes, aligned_pos, beta_lookback)
        if beta is None:
            _inc_reason(audit["rejections"], "dispersion_beta_invalid")
            continue
        if corr is None or abs(corr) < min_corr:
            _inc_reason(audit["rejections"], "dispersion_correlation_filter")
            continue

        proxy_close = proxy_closes[aligned_pos]
        primary_close = primary_closes[aligned_pos]
        if proxy_ref <= 0 or primary_ref <= 0:
            continue
        primary_move = (primary_close / primary_ref) - 1.0
        proxy_move = (proxy_close / proxy_ref) - 1.0
        rel_edge = primary_move - (beta * proxy_move)
        beta_shock = abs(beta * proxy_move)
        if beta_shock_max > 0 and beta_shock > beta_shock_max:
            _inc_reason(audit["rejections"], "dispersion_beta_shock_filter")
            continue
        if proxy_move_max > 0 and abs(proxy_move) > proxy_move_max:
            _inc_reason(audit["rejections"], "dispersion_proxy_move_filter")
            continue

        spread_start = aligned_pos - z_window + 1
        spread_mean, spread_std, spread_now, spread_prev = _spread_window_stats(
            primary_closes,
            proxy_closes,
            beta,
            spread_start,
            aligned_pos,
        )
        if spread_mean is None or spread_std is None or spread_now is None or spread_prev is None or spread_std <= 0:
            _inc_reason(audit["rejections"], "dispersion_sigma_invalid")
            continue

        z_now = (spread_now - spread_mean) / spread_std
        z_prev = (spread_prev - spread_mean) / spread_std
        zscore_improvement = abs(z_prev) - abs(z_now)
        if zscore_improvement < zscore_improvement_min:
            _inc_reason(audit["rejections"], "dispersion_zscore_improvement_filter")
            continue
        if rel_strength_confirm > 0 and abs(rel_edge) < rel_strength_confirm:
            _inc_reason(audit["rejections"], "dispersion_rel_strength_filter")
            continue

        open_price = float(bar.get("open") or 0.0)
        high_price = float(bar.get("high") or 0.0)
        low_price = float(bar.get("low") or 0.0)
        close_price = float(bar.get("close") or 0.0)
        bar_range = high_price - low_price
        body_frac = 0.0
        lower_wick_frac = 0.0
        upper_wick_frac = 0.0
        if bar_range > 0:
            body_frac = abs(close_price - open_price) / bar_range
            lower_wick_frac = max(min(open_price, close_price) - low_price, 0.0) / bar_range
            upper_wick_frac = max(high_price - max(open_price, close_price), 0.0) / bar_range

        raw_directions: List[int] = []
        long_reversal_ok = (
            reversal_body_min_frac <= 0.0 and reversal_wick_min_frac <= 0.0
        ) or (
            (close_price > open_price and body_frac >= reversal_body_min_frac)
            or (reversal_wick_min_frac > 0.0 and lower_wick_frac >= reversal_wick_min_frac and close_price >= open_price)
        )
        short_reversal_ok = (
            reversal_body_min_frac <= 0.0 and reversal_wick_min_frac <= 0.0
        ) or (
            (close_price < open_price and body_frac >= reversal_body_min_frac)
            or (reversal_wick_min_frac > 0.0 and upper_wick_frac >= reversal_wick_min_frac and close_price <= open_price)
        )
        if z_prev <= -z_entry and z_now >= -z_reentry and long_reversal_ok:
            raw_directions.append(1)
        if z_prev >= z_entry and z_now <= z_reentry and short_reversal_ok:
            raw_directions.append(-1)
        if not raw_directions:
            continue
        audit["opportunities_before_filters"] = int(audit.get("opportunities_before_filters") or 0) + len(raw_directions)

        candidate_directions: List[int] = []
        for direction in raw_directions:
            if direction > 0 and cfg.allow_long:
                candidate_directions.append(direction)
            elif direction < 0 and cfg.allow_short:
                candidate_directions.append(direction)
            else:
                _inc_reason(audit["rejections"], "direction_not_allowed")
        if not candidate_directions:
            continue

        if cfg.use_opening_bar_direction:
            filtered = [direction for direction in candidate_directions if direction == opening_bar_direction]
            dropped = len(candidate_directions) - len(filtered)
            if dropped > 0:
                _inc_reason(audit["rejections"], "opening_bar_direction_mismatch", dropped)
            candidate_directions = filtered
            if not candidate_directions:
                continue

        direction = candidate_directions[0]
        if len(candidate_directions) > 1:
            _inc_reason(audit["rejections"], "secondary_direction_dropped", len(candidate_directions) - 1)

        entry_idx = idx + 1
        if entry_idx >= len(session_bars):
            _inc_reason(audit["rejections"], "insufficient_bars")
            continue
        entry_bar = session_bars[entry_idx]
        entry_price = float(entry_bar.get("open") or 0.0)
        if entry_price <= 0:
            _inc_reason(audit["rejections"], "invalid_entry_price")
            continue

        prev_low = float(session_bars[idx - 1].get("low") or 0.0) if idx > 0 else float(bar.get("low") or 0.0)
        prev_high = float(session_bars[idx - 1].get("high") or 0.0) if idx > 0 else float(bar.get("high") or 0.0)
        if direction > 0:
            stop_core = min(float(bar.get("low") or 0.0), prev_low, orb_low)
            stop_price = stop_core - (orb_width * stop_buffer_or_mult)
        else:
            stop_core = max(float(bar.get("high") or 0.0), prev_high, orb_high)
            stop_price = stop_core + (orb_width * stop_buffer_or_mult)
        if direction > 0 and stop_price >= entry_price:
            _inc_reason(audit["rejections"], "invalid_stop")
            continue
        if direction < 0 and stop_price <= entry_price:
            _inc_reason(audit["rejections"], "invalid_stop")
            continue

        risk_per_share = abs(entry_price - stop_price)
        if risk_per_share <= 0:
            _inc_reason(audit["rejections"], "invalid_stop")
            continue
        target_underlying: Optional[float] = None
        if cfg.take_profit_rr > 0:
            target_underlying = (
                entry_price + (risk_per_share * cfg.take_profit_rr)
                if direction > 0
                else entry_price - (risk_per_share * cfg.take_profit_rr)
            )

        audit["opportunities_after_filters"] = int(audit.get("opportunities_after_filters") or 0) + 1
        return {
            "direction": direction,
            "signal_idx": idx,
            "signal_ts": bar["ts"],
            "entry_idx": entry_idx,
            "entry_ts": entry_bar["ts"],
            "entry_underlying": entry_price,
            "stop_underlying": stop_price,
            "mr_target_underlying": target_underlying,
            "orb_high": orb_high,
            "orb_low": orb_low,
            "opening_bar_open": orb_open,
            "opening_bar_close": orb_close,
            "opening_bar_direction": opening_bar_direction,
            "trend_ema_fast": 0.0,
            "trend_ema_slow": 0.0,
            "volume_ratio": 1.0,
            "relative_opening_volume": relative_opening_volume,
            "atr_value": atr_value,
            "fvg_gap": 0.0,
            "opening_range_minutes": opening_range_count,
            "orb_width_pct": orb_width_pct,
            "strategy_variant": "dispersion_relative_revert_v1",
            "dispersion_proxy_ticker": proxy_ticker,
            "dispersion_beta": float(beta),
            "dispersion_corr": float(corr),
            "dispersion_primary_ref": float(primary_ref),
            "dispersion_proxy_ref": float(proxy_ref),
            "dispersion_spread_mean": float(spread_mean),
            "dispersion_spread_sigma": float(spread_std),
            "dispersion_zscore_at_signal": float(z_now),
            "dispersion_zscore_exit": float(max(float(cfg.dispersion_zscore_exit), 0.0)),
            "dispersion_zscore_stop": float(z_stop),
            "dispersion_rel_strength_at_signal": float(rel_edge),
            "dispersion_zscore_improvement_at_signal": float(zscore_improvement),
            "dispersion_beta_shock_max_pct": float(beta_shock_max),
            "dispersion_time_to_work_bars": int(time_to_work_bars),
            "dispersion_time_to_work_improvement_min": float(time_to_work_improvement_min),
        }, audit

    if int(audit.get("opportunities_before_filters") or 0) == 0:
        _inc_reason(audit["rejections"], "dispersion_no_signal")
    return None, audit


def _find_relative_strength_continuation_setup_with_audit(
    session_bars: List[Dict[str, Any]],
    pair_session_bars: Optional[List[Dict[str, Any]]],
    cfg: IntradayStrategyConfig,
    relative_opening_volume: Optional[float],
    atr_value: Optional[float],
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    audit: Dict[str, Any] = {
        "strategy_variant": "relative_strength_continuation_v1",
        "opportunities_before_filters": 0,
        "opportunities_after_filters": 0,
        "rejections": {},
    }
    if not session_bars or not pair_session_bars:
        _inc_reason(audit["rejections"], "relative_strength_missing_session_bars")
        return None, audit

    opening_count = max(int(cfg.opening_range_minutes), 1)
    beta_lookback = max(int(cfg.dispersion_beta_lookback), 4)
    warmup_needed = max(opening_count + 1, beta_lookback + 1)
    if len(session_bars) < (warmup_needed + 2):
        _inc_reason(audit["rejections"], "insufficient_bars")
        return None, audit

    pair_by_ts, aligned_indices, primary_closes, proxy_closes, aligned_pos_by_idx = _aligned_proxy_series(
        session_bars=session_bars,
        proxy_session_bars=pair_session_bars,
    )
    if not pair_by_ts:
        _inc_reason(audit["rejections"], "relative_strength_missing_session_bars")
        return None, audit
    if len(aligned_indices) < (warmup_needed + 2):
        _inc_reason(audit["rejections"], "relative_strength_insufficient_aligned_bars")
        return None, audit

    opening_ref_pos: Optional[int] = None
    for pos, idx in enumerate(aligned_indices):
        if idx >= (opening_count - 1):
            opening_ref_pos = pos
            break
    if opening_ref_pos is None:
        _inc_reason(audit["rejections"], "relative_strength_missing_open_reference")
        return None, audit

    opening_window = session_bars[:opening_count]
    opening_open = float(opening_window[0].get("open") or 0.0)
    opening_close = float(opening_window[-1].get("close") or 0.0)
    opening_high = max(float(bar.get("high") or 0.0) for bar in opening_window)
    opening_low = min(float(bar.get("low") or 0.0) for bar in opening_window)
    if opening_open <= 0 or opening_close <= 0 or opening_high <= 0 or opening_low <= 0 or opening_high <= opening_low:
        _inc_reason(audit["rejections"], "invalid_opening_reference")
        return None, audit
    opening_range = opening_high - opening_low
    opening_range_pct = opening_range / max(opening_open, 1.0)
    if cfg.require_or_width_filter:
        min_width = max(float(cfg.opening_range_min_width_pct), 0.0)
        max_width = max(float(cfg.opening_range_max_width_pct), min_width)
        if opening_range_pct < min_width or opening_range_pct > max_width:
            _inc_reason(audit["rejections"], "opening_width_filter")
            return None, audit

    closes = [float(bar.get("close") or 0.0) for bar in session_bars]
    ema_fast = _ema_series(closes, cfg.trend_ema_fast)
    ema_slow = _ema_series(closes, cfg.trend_ema_slow)
    vwap_series = _running_vwap_series(session_bars)

    entry_start = _parse_hhmm(cfg.entry_start_time, _default_entry_start(opening_count))
    entry_cutoff = _parse_hhmm(cfg.entry_cutoff_time, "12:00")
    min_corr = max(float(cfg.dispersion_min_correlation), 0.0)
    rel_edge_entry = max(float(cfg.dispersion_rel_strength_entry_pct), 0.0)
    rel_edge_confirm = max(float(cfg.dispersion_rel_strength_confirm_pct), 0.0)
    primary_move_min = max(
        float(getattr(cfg, "drive_min_abs_return_pct", 0.0)),
        float(cfg.dispersion_primary_min_abs_move_pct),
        0.0,
    )
    proxy_move_max = max(float(cfg.dispersion_proxy_max_abs_move_pct), 0.0)
    beta_shock_max = max(float(getattr(cfg, "dispersion_beta_shock_max_pct", 1.0)), 0.0)
    min_retrace_frac = max(float(getattr(cfg, "drive_pullback_min_retrace_frac", 0.0)), 0.0)
    max_retrace_frac = max(float(getattr(cfg, "drive_pullback_max_retrace_frac", 0.0)), min_retrace_frac)
    touch_buffer_pct = max(float(getattr(cfg, "drive_touch_ma_buffer_pct", 0.0)), 0.0)
    reclaim_close_location_min = max(
        0.0,
        min(1.0, float(getattr(cfg, "drive_reclaim_close_location_min", 0.0))),
    )
    reclaim_min_volume_multiple = max(float(getattr(cfg, "drive_reclaim_min_volume_multiple", 0.0)), 0.0)
    max_pullback_bars = max(int(getattr(cfg, "drive_max_pullback_bars", 1)), 1)
    stop_buffer_range_frac = max(float(getattr(cfg, "drive_stop_buffer_range_frac", 0.0)), 0.0)
    require_hold_reference = bool(getattr(cfg, "drive_pullback_require_hold_drive_open", True))
    primary_ref = primary_closes[opening_ref_pos]
    proxy_ref = proxy_closes[opening_ref_pos]
    primary_ticker = str(session_bars[0].get("ticker") or "").strip().upper()
    proxy_ticker = resolve_dispersion_proxy_ticker(primary_ticker, cfg.dispersion_proxy_ticker)
    if primary_ref <= 0 or proxy_ref <= 0:
        _inc_reason(audit["rejections"], "relative_strength_invalid_reference")
        return None, audit

    for idx in range(opening_count + 1, len(session_bars) - 1):
        bar = session_bars[idx]
        bar_time = _to_et_time(bar["ts"])
        if bar_time < entry_start or bar_time > entry_cutoff:
            continue
        aligned_pos = aligned_pos_by_idx.get(idx)
        if aligned_pos is None or aligned_pos <= opening_ref_pos or aligned_pos < beta_lookback:
            continue

        relative_volume_rejection = _relative_volume_rejection_reason(cfg, relative_opening_volume)
        if relative_volume_rejection is not None:
            _inc_reason(audit["rejections"], relative_volume_rejection)
            continue
        if cfg.require_atr_filter:
            if atr_value is None or atr_value < cfg.atr_min:
                _inc_reason(audit["rejections"], "atr_filter")
                continue

        beta, corr = _beta_corr_over_lookback(primary_closes, proxy_closes, aligned_pos, beta_lookback)
        if beta is None:
            _inc_reason(audit["rejections"], "relative_strength_beta_invalid")
            continue
        if corr is None or abs(corr) < min_corr:
            _inc_reason(audit["rejections"], "relative_strength_correlation_filter")
            continue

        open_price = _safe_float(bar.get("open"))
        high_price = _safe_float(bar.get("high"))
        low_price = _safe_float(bar.get("low"))
        close_price = _safe_float(bar.get("close"))
        if open_price is None or high_price is None or low_price is None or close_price is None:
            continue
        ema_now = float(ema_fast[idx]) if idx < len(ema_fast) else 0.0
        ema_slow_now = float(ema_slow[idx]) if idx < len(ema_slow) else 0.0
        vwap_now = float(vwap_series[idx]) if idx < len(vwap_series) else 0.0
        if ema_now <= 0 or ema_slow_now <= 0 or vwap_now <= 0:
            _inc_reason(audit["rejections"], "relative_strength_ma_unavailable")
            continue
        if not (close_price > max(vwap_now, ema_now) and ema_now > ema_slow_now):
            _inc_reason(audit["rejections"], "relative_strength_trend_alignment")
            continue

        proxy_close = proxy_closes[aligned_pos]
        prev_primary_close = primary_closes[aligned_pos - 1]
        prev_proxy_close = proxy_closes[aligned_pos - 1]
        primary_move = (close_price / primary_ref) - 1.0
        proxy_move = (proxy_close / proxy_ref) - 1.0
        rel_edge = primary_move - (beta * proxy_move)
        prev_primary_move = (prev_primary_close / primary_ref) - 1.0
        prev_proxy_move = (prev_proxy_close / proxy_ref) - 1.0
        rel_edge_prev = prev_primary_move - (beta * prev_proxy_move)
        beta_shock = abs(beta * proxy_move)
        if beta_shock_max > 0 and beta_shock > beta_shock_max:
            _inc_reason(audit["rejections"], "relative_strength_beta_shock_filter")
            continue
        if proxy_move_max > 0 and abs(proxy_move) > proxy_move_max:
            _inc_reason(audit["rejections"], "relative_strength_proxy_move_filter")
            continue
        if primary_move < primary_move_min:
            _inc_reason(audit["rejections"], "relative_strength_primary_move_filter")
            continue
        if rel_edge < rel_edge_entry:
            _inc_reason(audit["rejections"], "relative_strength_edge_filter")
            continue
        if rel_edge < max(rel_edge_confirm, rel_edge_prev):
            _inc_reason(audit["rejections"], "relative_strength_edge_confirm")
            continue

        recent_start = max(opening_count, idx - max_pullback_bars)
        recent_window = session_bars[recent_start : idx + 1]
        if not recent_window:
            continue
        recent_high = max(float(row.get("high") or 0.0) for row in recent_window)
        recent_low = min(float(row.get("low") or 0.0) for row in recent_window)
        impulse_move = max(recent_high - primary_ref, 0.0)
        if impulse_move <= 0:
            _inc_reason(audit["rejections"], "relative_strength_no_impulse")
            continue
        retrace_frac = max(recent_high - low_price, 0.0) / max(impulse_move, 1e-9)
        if retrace_frac < min_retrace_frac:
            _inc_reason(audit["rejections"], "relative_strength_pullback_too_shallow")
            continue
        if retrace_frac > max_retrace_frac:
            _inc_reason(audit["rejections"], "relative_strength_pullback_too_deep")
            continue

        touched_value = low_price <= (max(vwap_now, ema_now) * (1.0 + touch_buffer_pct))
        if not touched_value:
            _inc_reason(audit["rejections"], "relative_strength_value_touch")
            continue
        if require_hold_reference and low_price <= primary_ref:
            _inc_reason(audit["rejections"], "relative_strength_reference_hold")
            continue

        volume_ratio = 1.0
        lookback = session_bars[max(opening_count, idx - 3) : idx]
        if lookback:
            avg_volume = _mean_fast(float(row.get("volume") or 0.0) for row in lookback)
            if avg_volume > 0:
                volume_ratio = float(bar.get("volume") or 0.0) / avg_volume
        if volume_ratio < reclaim_min_volume_multiple:
            _inc_reason(audit["rejections"], "relative_strength_volume")
            continue

        reclaim_location = _close_location_fraction(
            direction=1,
            high_price=high_price,
            low_price=low_price,
            close_price=close_price,
        )
        if reclaim_location < reclaim_close_location_min:
            _inc_reason(audit["rejections"], "relative_strength_close_location")
            continue

        prev_high = float(session_bars[idx - 1].get("high") or 0.0)
        reclaim_threshold = max(vwap_now, ema_now, prev_high)
        if close_price <= reclaim_threshold:
            _inc_reason(audit["rejections"], "relative_strength_reclaim_confirmation")
            continue

        audit["opportunities_before_filters"] = int(audit.get("opportunities_before_filters") or 0) + 1
        entry_idx, entry_bar, entry_underlying = _next_bar_open_entry(session_bars, signal_idx=idx)
        if entry_idx is None or entry_bar is None or entry_underlying <= 0:
            _inc_reason(audit["rejections"], "invalid_entry_price")
            continue
        stop_underlying = recent_low - (impulse_move * stop_buffer_range_frac)
        if stop_underlying >= entry_underlying:
            _inc_reason(audit["rejections"], "invalid_stop")
            continue
        risk_per_share = entry_underlying - stop_underlying
        if risk_per_share <= 0:
            _inc_reason(audit["rejections"], "invalid_stop")
            continue

        target_underlying: Optional[float] = None
        if cfg.take_profit_rr > 0:
            target_underlying = entry_underlying + (risk_per_share * cfg.take_profit_rr)

        audit["opportunities_after_filters"] = int(audit.get("opportunities_after_filters") or 0) + 1
        return {
            "direction": 1,
            "signal_idx": idx,
            "signal_ts": bar["ts"],
            "entry_idx": entry_idx,
            "entry_ts": entry_bar["ts"],
            "entry_underlying": entry_underlying,
            "stop_underlying": stop_underlying,
            "mr_target_underlying": target_underlying,
            "orb_high": recent_high,
            "orb_low": recent_low,
            "opening_bar_open": opening_open,
            "opening_bar_close": opening_close,
            "opening_bar_direction": 1 if opening_close > opening_open else (-1 if opening_close < opening_open else 0),
            "trend_ema_fast": ema_now,
            "trend_ema_slow": ema_slow_now,
            "volume_ratio": volume_ratio,
            "relative_opening_volume": relative_opening_volume,
            "atr_value": atr_value,
            "fvg_gap": 0.0,
            "opening_range_minutes": opening_count,
            "orb_width_pct": opening_range_pct,
            "strategy_variant": "relative_strength_continuation_v1",
            "dispersion_proxy_ticker": proxy_ticker,
            "dispersion_beta": float(beta),
            "dispersion_corr": float(corr),
            "dispersion_primary_ref": float(primary_ref),
            "dispersion_proxy_ref": float(proxy_ref),
            "dispersion_rel_strength_at_signal": float(rel_edge),
            "dispersion_rel_strength_exit_pct": float(max(float(cfg.dispersion_rel_strength_exit_pct), 0.0)),
            "dispersion_rel_strength_stop_pct": float(max(float(cfg.dispersion_rel_strength_stop_pct), 0.0)),
            "dispersion_beta_shock_max_pct": float(beta_shock_max),
            "dispersion_time_to_work_bars": int(max(int(getattr(cfg, "dispersion_time_to_work_bars", 0)), 0)),
            "dispersion_breakout_rel_strength_floor_frac": float(
                max(float(getattr(cfg, "dispersion_breakout_rel_strength_floor_frac", 0.0)), 0.0)
            ),
            "relative_strength_primary_move": float(primary_move),
            "relative_strength_proxy_move": float(proxy_move),
            "relative_strength_retrace_frac": float(retrace_frac),
            "relative_strength_close_location": float(reclaim_location),
        }, audit

    if int(audit.get("opportunities_before_filters") or 0) == 0:
        _inc_reason(audit["rejections"], "relative_strength_no_signal")
    return None, audit


def _find_proxy_vwap_reclaim_setup_with_audit(
    session_bars: List[Dict[str, Any]],
    pair_session_bars: Optional[List[Dict[str, Any]]],
    cfg: IntradayStrategyConfig,
    relative_opening_volume: Optional[float],
    atr_value: Optional[float],
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    audit: Dict[str, Any] = {
        "strategy_variant": "proxy_vwap_reclaim_v1",
        "opportunities_before_filters": 0,
        "opportunities_after_filters": 0,
        "rejections": {},
    }
    if not session_bars or not pair_session_bars:
        _inc_reason(audit["rejections"], "proxy_reclaim_missing_session_bars")
        return None, audit

    opening_count = max(int(cfg.opening_range_minutes), 1)
    beta_lookback = max(int(cfg.dispersion_beta_lookback), 4)
    warmup_needed = max(opening_count + 2, beta_lookback + 1)
    if len(session_bars) < (warmup_needed + 2):
        _inc_reason(audit["rejections"], "insufficient_bars")
        return None, audit

    pair_by_ts, aligned_indices, primary_closes, proxy_closes, aligned_pos_by_idx = _aligned_proxy_series(
        session_bars=session_bars,
        proxy_session_bars=pair_session_bars,
    )
    if not pair_by_ts:
        _inc_reason(audit["rejections"], "proxy_reclaim_missing_session_bars")
        return None, audit
    if len(aligned_indices) < (warmup_needed + 2):
        _inc_reason(audit["rejections"], "proxy_reclaim_insufficient_aligned_bars")
        return None, audit

    opening_ref_pos: Optional[int] = None
    for pos, idx in enumerate(aligned_indices):
        if idx >= (opening_count - 1):
            opening_ref_pos = pos
            break
    if opening_ref_pos is None:
        _inc_reason(audit["rejections"], "proxy_reclaim_missing_open_reference")
        return None, audit

    opening_window = session_bars[:opening_count]
    opening_open = float(opening_window[0].get("open") or 0.0)
    opening_close = float(opening_window[-1].get("close") or 0.0)
    opening_high = max(float(bar.get("high") or 0.0) for bar in opening_window)
    opening_low = min(float(bar.get("low") or 0.0) for bar in opening_window)
    if opening_open <= 0 or opening_close <= 0 or opening_high <= 0 or opening_low <= 0 or opening_high <= opening_low:
        _inc_reason(audit["rejections"], "invalid_opening_reference")
        return None, audit

    opening_range = opening_high - opening_low
    opening_range_pct = opening_range / max(opening_open, 1.0)
    if cfg.require_or_width_filter:
        min_width = max(float(cfg.opening_range_min_width_pct), 0.0)
        max_width = max(float(cfg.opening_range_max_width_pct), min_width)
        if opening_range_pct < min_width or opening_range_pct > max_width:
            _inc_reason(audit["rejections"], "opening_width_filter")
            return None, audit

    primary_vwap = _running_vwap_series(session_bars)
    proxy_vwap = _running_vwap_series(pair_session_bars)
    primary_ema_fast = _ema_series(primary_closes, cfg.trend_ema_fast)
    primary_ema_slow = _ema_series(primary_closes, cfg.trend_ema_slow)
    proxy_ema_fast = _ema_series(proxy_closes, cfg.trend_ema_fast)
    proxy_ema_slow = _ema_series(proxy_closes, cfg.trend_ema_slow)

    entry_start = _parse_hhmm(cfg.entry_start_time, _default_entry_start(opening_count))
    entry_cutoff = _parse_hhmm(cfg.entry_cutoff_time, "12:00")
    min_corr = max(float(cfg.dispersion_min_correlation), 0.0)
    min_proxy_move = max(float(cfg.dispersion_primary_min_abs_move_pct), 0.0)
    max_primary_move = max(float(cfg.dispersion_proxy_max_abs_move_pct), 0.0)
    min_lag_gap = max(float(cfg.dispersion_rel_strength_entry_pct), 0.0)
    min_gap_improvement = max(float(cfg.dispersion_rel_strength_confirm_pct), 0.0)
    improve_frac = max(float(getattr(cfg, "dispersion_breakout_rel_strength_floor_frac", 0.0)), 0.0)
    beta_shock_max = max(float(getattr(cfg, "dispersion_beta_shock_max_pct", 1.0)), 0.0)
    time_to_work_bars = max(int(getattr(cfg, "dispersion_time_to_work_bars", 0)), 0)
    time_to_work_price_move = max(float(getattr(cfg, "dispersion_time_to_work_improvement_min", 0.0)), 0.0)
    min_retrace_frac = max(float(getattr(cfg, "drive_pullback_min_retrace_frac", 0.0)), 0.0)
    max_retrace_frac = max(float(getattr(cfg, "drive_pullback_max_retrace_frac", 0.0)), min_retrace_frac)
    touch_buffer_pct = max(float(getattr(cfg, "drive_touch_ma_buffer_pct", 0.0)), 0.0)
    reclaim_close_location_min = max(0.0, min(1.0, float(getattr(cfg, "drive_reclaim_close_location_min", 0.0))))
    reclaim_min_volume_multiple = max(float(getattr(cfg, "drive_reclaim_min_volume_multiple", 0.0)), 0.0)
    max_pullback_bars = max(int(getattr(cfg, "drive_max_pullback_bars", 1)), 1)
    require_hold_reference = bool(getattr(cfg, "drive_pullback_require_hold_drive_open", True))
    require_prev_high_break = bool(getattr(cfg, "drive_reclaim_requires_prev_extreme_break", True))
    stop_buffer_range_frac = max(float(getattr(cfg, "drive_stop_buffer_range_frac", 0.0)), 0.0)
    primary_ref = primary_closes[opening_ref_pos]
    proxy_ref = proxy_closes[opening_ref_pos]
    primary_ticker = str(session_bars[0].get("ticker") or "").strip().upper()
    proxy_ticker = resolve_dispersion_proxy_ticker(primary_ticker, cfg.dispersion_proxy_ticker)
    if primary_ref <= 0 or proxy_ref <= 0:
        _inc_reason(audit["rejections"], "proxy_reclaim_invalid_reference")
        return None, audit

    state: Optional[Dict[str, Any]] = None
    for idx in range(opening_count + 1, len(session_bars) - 1):
        bar = session_bars[idx]
        bar_time = _to_et_time(bar["ts"])
        if bar_time < entry_start or bar_time > entry_cutoff:
            continue
        aligned_pos = aligned_pos_by_idx.get(idx)
        if aligned_pos is None or aligned_pos <= opening_ref_pos or aligned_pos < beta_lookback:
            continue

        relative_volume_rejection = _relative_volume_rejection_reason(cfg, relative_opening_volume)
        if relative_volume_rejection is not None:
            _inc_reason(audit["rejections"], relative_volume_rejection)
            continue
        if cfg.require_atr_filter:
            if atr_value is None or atr_value < cfg.atr_min:
                _inc_reason(audit["rejections"], "atr_filter")
                continue

        beta, corr = _beta_corr_over_lookback(primary_closes, proxy_closes, aligned_pos, beta_lookback)
        if beta is None:
            _inc_reason(audit["rejections"], "proxy_reclaim_beta_invalid")
            continue
        if corr is None or abs(corr) < min_corr:
            _inc_reason(audit["rejections"], "proxy_reclaim_correlation_filter")
            continue

        open_price = _safe_float(bar.get("open"))
        high_price = _safe_float(bar.get("high"))
        low_price = _safe_float(bar.get("low"))
        close_price = _safe_float(bar.get("close"))
        if open_price is None or high_price is None or low_price is None or close_price is None:
            continue
        primary_vwap_now = float(primary_vwap[idx]) if idx < len(primary_vwap) else 0.0
        primary_ema_fast_now = float(primary_ema_fast[aligned_pos]) if aligned_pos < len(primary_ema_fast) else 0.0
        primary_ema_slow_now = float(primary_ema_slow[aligned_pos]) if aligned_pos < len(primary_ema_slow) else 0.0
        proxy_close = proxy_closes[aligned_pos]
        proxy_vwap_now = float(proxy_vwap[aligned_pos]) if aligned_pos < len(proxy_vwap) else 0.0
        proxy_ema_fast_now = float(proxy_ema_fast[aligned_pos]) if aligned_pos < len(proxy_ema_fast) else 0.0
        proxy_ema_slow_now = float(proxy_ema_slow[aligned_pos]) if aligned_pos < len(proxy_ema_slow) else 0.0
        if (
            primary_vwap_now <= 0
            or primary_ema_fast_now <= 0
            or primary_ema_slow_now <= 0
            or proxy_vwap_now <= 0
            or proxy_ema_fast_now <= 0
            or proxy_ema_slow_now <= 0
        ):
            _inc_reason(audit["rejections"], "proxy_reclaim_ma_unavailable")
            continue

        proxy_move = (proxy_close / proxy_ref) - 1.0
        primary_move = (close_price / primary_ref) - 1.0
        rel_edge = primary_move - (beta * proxy_move)
        lag_gap = max(0.0, -rel_edge)
        beta_shock = abs(beta * proxy_move)
        if beta_shock_max > 0 and beta_shock > beta_shock_max:
            _inc_reason(audit["rejections"], "proxy_reclaim_beta_shock_filter")
            state = None
            continue
        proxy_strong = (
            proxy_move >= min_proxy_move
            and proxy_close > max(proxy_vwap_now, proxy_ema_fast_now)
            and proxy_ema_fast_now > proxy_ema_slow_now
        )
        if not proxy_strong:
            _inc_reason(audit["rejections"], "proxy_reclaim_proxy_not_strong")
            state = None
            continue

        if state is None:
            if lag_gap < min_lag_gap:
                _inc_reason(audit["rejections"], "proxy_reclaim_gap_too_small")
                continue
            if primary_move > max_primary_move:
                _inc_reason(audit["rejections"], "proxy_reclaim_primary_too_extended")
                continue
            touched_value = low_price <= (max(primary_vwap_now, primary_ema_fast_now) * (1.0 + touch_buffer_pct))
            if not touched_value:
                _inc_reason(audit["rejections"], "proxy_reclaim_value_touch")
                continue
            state = {
                "idx": idx,
                "initial_gap": lag_gap,
                "recent_high": max(high_price, close_price),
                "recent_low": min(low_price, close_price),
                "had_touch": touched_value,
            }
            audit["opportunities_before_filters"] = int(audit.get("opportunities_before_filters") or 0) + 1
            continue

        bars_since_state = idx - int(state["idx"])
        if bars_since_state > max_pullback_bars:
            _inc_reason(audit["rejections"], "proxy_reclaim_timeout")
            state = None
            continue

        state["recent_high"] = max(float(state["recent_high"]), high_price, close_price)
        state["recent_low"] = min(float(state["recent_low"]), low_price, close_price)
        state["had_touch"] = bool(state["had_touch"]) or (
            low_price <= (max(primary_vwap_now, primary_ema_fast_now) * (1.0 + touch_buffer_pct))
        )
        if require_hold_reference and low_price <= primary_ref:
            _inc_reason(audit["rejections"], "proxy_reclaim_reference_hold")
            state = None
            continue
        if not bool(state["had_touch"]):
            _inc_reason(audit["rejections"], "proxy_reclaim_no_value_touch")
            continue

        impulse_move = max(float(state["recent_high"]) - primary_ref, 0.0)
        if impulse_move <= 0:
            _inc_reason(audit["rejections"], "proxy_reclaim_no_impulse")
            continue
        retrace_frac = max(float(state["recent_high"]) - low_price, 0.0) / max(impulse_move, 1e-9)
        if retrace_frac < min_retrace_frac:
            _inc_reason(audit["rejections"], "proxy_reclaim_pullback_too_shallow")
            continue
        if retrace_frac > max_retrace_frac:
            _inc_reason(audit["rejections"], "proxy_reclaim_pullback_too_deep")
            state = None
            continue

        lookback = session_bars[max(opening_count, idx - 3) : idx]
        volume_ratio = 1.0
        if lookback:
            avg_volume = _mean_fast(float(row.get("volume") or 0.0) for row in lookback)
            if avg_volume > 0:
                volume_ratio = float(bar.get("volume") or 0.0) / avg_volume
        if volume_ratio < reclaim_min_volume_multiple:
            _inc_reason(audit["rejections"], "proxy_reclaim_volume")
            continue

        reclaim_location = _close_location_fraction(
            direction=1,
            high_price=high_price,
            low_price=low_price,
            close_price=close_price,
        )
        if reclaim_location < reclaim_close_location_min:
            _inc_reason(audit["rejections"], "proxy_reclaim_close_location")
            continue

        prev_high = float(session_bars[idx - 1].get("high") or 0.0)
        reclaim_threshold = max(primary_vwap_now, primary_ema_fast_now)
        if require_prev_high_break:
            reclaim_threshold = max(reclaim_threshold, prev_high)
        if close_price <= reclaim_threshold:
            _inc_reason(audit["rejections"], "proxy_reclaim_confirmation")
            continue

        initial_gap = max(float(state["initial_gap"]), 0.0)
        gap_improvement = initial_gap - lag_gap
        required_gap_improvement = max(min_gap_improvement, initial_gap * improve_frac)
        if gap_improvement < required_gap_improvement:
            _inc_reason(audit["rejections"], "proxy_reclaim_gap_improvement")
            continue

        entry_idx, entry_bar, entry_underlying = _next_bar_open_entry(session_bars, signal_idx=idx)
        if entry_idx is None or entry_bar is None or entry_underlying <= 0:
            _inc_reason(audit["rejections"], "invalid_entry_price")
            state = None
            continue
        local_range = max(float(state["recent_high"]) - float(state["recent_low"]), 0.0)
        stop_underlying = float(state["recent_low"]) - (local_range * stop_buffer_range_frac)
        if stop_underlying >= entry_underlying:
            _inc_reason(audit["rejections"], "invalid_stop")
            state = None
            continue
        risk_per_share = entry_underlying - stop_underlying
        if risk_per_share <= 0:
            _inc_reason(audit["rejections"], "invalid_stop")
            state = None
            continue
        target_underlying: Optional[float] = None
        if cfg.take_profit_rr > 0:
            target_underlying = entry_underlying + (risk_per_share * cfg.take_profit_rr)

        audit["opportunities_after_filters"] = int(audit.get("opportunities_after_filters") or 0) + 1
        return {
            "direction": 1,
            "signal_idx": idx,
            "signal_ts": bar["ts"],
            "entry_idx": entry_idx,
            "entry_ts": entry_bar["ts"],
            "entry_underlying": entry_underlying,
            "stop_underlying": stop_underlying,
            "mr_target_underlying": target_underlying,
            "orb_high": float(state["recent_high"]),
            "orb_low": float(state["recent_low"]),
            "opening_bar_open": opening_open,
            "opening_bar_close": opening_close,
            "opening_bar_direction": 1 if opening_close > opening_open else (-1 if opening_close < opening_open else 0),
            "trend_ema_fast": primary_ema_fast_now,
            "trend_ema_slow": primary_ema_slow_now,
            "volume_ratio": volume_ratio,
            "relative_opening_volume": relative_opening_volume,
            "atr_value": atr_value,
            "fvg_gap": 0.0,
            "opening_range_minutes": opening_count,
            "orb_width_pct": opening_range_pct,
            "strategy_variant": "proxy_vwap_reclaim_v1",
            "proxy_reclaim_proxy_ticker": proxy_ticker,
            "proxy_reclaim_primary_ref": float(primary_ref),
            "proxy_reclaim_proxy_ref": float(proxy_ref),
            "proxy_reclaim_beta": float(beta),
            "proxy_reclaim_initial_gap": float(initial_gap),
            "proxy_reclaim_gap_at_signal": float(lag_gap),
            "proxy_reclaim_gap_improvement": float(gap_improvement),
            "proxy_reclaim_proxy_move": float(proxy_move),
            "proxy_reclaim_primary_move": float(primary_move),
            "proxy_reclaim_retrace_frac": float(retrace_frac),
            "proxy_reclaim_close_location": float(reclaim_location),
            "proxy_reclaim_time_to_work_bars": int(time_to_work_bars),
            "proxy_reclaim_time_to_work_price_move": float(time_to_work_price_move),
        }, audit

    if int(audit.get("opportunities_before_filters") or 0) == 0:
        _inc_reason(audit["rejections"], "proxy_reclaim_no_signal")
    return None, audit


def _close_location_fraction(*, direction: int, high_price: float, low_price: float, close_price: float) -> float:
    bar_range = high_price - low_price
    if bar_range <= 0:
        return 0.0
    if direction > 0:
        return max(0.0, min(1.0, (close_price - low_price) / bar_range))
    return max(0.0, min(1.0, (high_price - close_price) / bar_range))


def _find_orb_momentum_setup_with_audit(
    session_bars: List[Dict[str, Any]],
    cfg: IntradayStrategyConfig,
    relative_opening_volume: Optional[float],
    atr_value: Optional[float],
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    audit: Dict[str, Any] = {
        "strategy_variant": "orb_momentum_v1",
        "opportunities_before_filters": 0,
        "opportunities_after_filters": 0,
        "rejections": {},
    }
    opening_range_count = max(int(cfg.opening_range_minutes), 1)
    if len(session_bars) < (opening_range_count + 3):
        _inc_reason(audit["rejections"], "insufficient_bars")
        return None, audit

    opening_range = session_bars[:opening_range_count]
    orb_high = max(float(bar.get("high") or 0.0) for bar in opening_range)
    orb_low = min(float(bar.get("low") or 0.0) for bar in opening_range)
    orb_open = float(opening_range[0].get("open") or 0.0)
    orb_close = float(opening_range[-1].get("close") or 0.0)
    if orb_high <= 0 or orb_low <= 0 or orb_high <= orb_low:
        _inc_reason(audit["rejections"], "invalid_opening_range")
        return None, audit

    orb_width = orb_high - orb_low
    orb_width_pct = orb_width / max(orb_open, 1.0)
    if cfg.require_or_width_filter:
        min_width = max(float(cfg.opening_range_min_width_pct), 0.0)
        max_width = max(float(cfg.opening_range_max_width_pct), min_width)
        if orb_width_pct < min_width or orb_width_pct > max_width:
            _inc_reason(audit["rejections"], "orb_width_filter")
            return None, audit

    opening_bar_direction = 0
    if orb_close > orb_open:
        opening_bar_direction = 1
    elif orb_close < orb_open:
        opening_bar_direction = -1

    highs = [float(bar.get("high") or 0.0) for bar in session_bars]
    lows = [float(bar.get("low") or 0.0) for bar in session_bars]
    closes = [float(bar.get("close") or 0.0) for bar in session_bars]
    ema_fast = _ema_series(closes, cfg.trend_ema_fast)
    ema_slow = _ema_series(closes, cfg.trend_ema_slow)
    adx_period = max(int(getattr(cfg, "momentum_adx_period", 14)), 1)
    min_adx = max(float(getattr(cfg, "momentum_adx_min", 0.0)), 0.0)
    adx_values = _adx_series(highs, lows, closes, adx_period) if min_adx > 0 else [0.0] * len(session_bars)

    entry_start = _parse_hhmm(cfg.entry_start_time, _default_entry_start(opening_range_count))
    entry_cutoff = _parse_hhmm(cfg.entry_cutoff_time, "12:00")
    macro_release_times = (
        _parse_hhmm_list(cfg.macro_release_times_et, "10:00")
        if cfg.require_macro_release_filter
        else []
    )
    macro_block_minutes = max(int(cfg.macro_post_release_block_minutes), 0)
    trigger_mode = str(cfg.entry_trigger_mode or "close_breakout").strip().lower()

    min_breakout_or_frac = max(float(getattr(cfg, "momentum_breakout_min_or_frac", 0.0)), 0.0)
    max_breakout_or_frac = max(
        float(getattr(cfg, "momentum_breakout_max_or_frac", 10.0)),
        min_breakout_or_frac,
    )
    min_close_location = max(0.0, min(1.0, float(getattr(cfg, "momentum_close_location_min", 0.0))))
    min_ema_spread_pct = max(float(getattr(cfg, "momentum_min_ema_spread_pct", 0.0)), 0.0)
    max_pullback_to_ema_pct = max(float(getattr(cfg, "momentum_pullback_to_ema_max_pct", 0.0)), 0.0)
    confirm_bars = max(int(getattr(cfg, "momentum_confirmation_bars", 1)), 1)
    min_volume_multiple = max(float(getattr(cfg, "momentum_volume_multiple_min", 1.0)), 0.0)
    min_body_or_frac = max(float(getattr(cfg, "momentum_min_body_or_frac", 0.0)), 0.0)
    max_opposite_wick_body_ratio = max(
        float(getattr(cfg, "momentum_max_opposite_wick_body_ratio", 100.0)),
        0.0,
    )
    atr_range_min = max(float(getattr(cfg, "momentum_atr_range_min", 0.0)), 0.0)
    trend_bars_min = max(int(getattr(cfg, "momentum_trend_bars_min", 1)), 1)

    setup: Optional[Dict[str, Any]] = None
    for idx in range(opening_range_count, len(session_bars) - 1):
        bar = session_bars[idx]
        bar_time = _to_et_time(bar["ts"])
        if bar_time < entry_start or bar_time > entry_cutoff:
            continue

        current_open = float(bar.get("open") or 0.0)
        current_high = float(bar.get("high") or 0.0)
        current_low = float(bar.get("low") or 0.0)
        current_close = float(bar.get("close") or 0.0)
        if current_open <= 0 or current_high <= 0 or current_low <= 0 or current_close <= 0:
            continue

        if trigger_mode == "stop_touch":
            long_breakout = current_high >= orb_high
            short_breakout = current_low <= orb_low
        else:
            long_breakout = current_close > orb_high
            short_breakout = current_close < orb_low
        raw_directions: List[int] = []
        if long_breakout:
            raw_directions.append(1)
        if short_breakout:
            raw_directions.append(-1)
        if not raw_directions:
            continue
        audit["opportunities_before_filters"] = int(audit.get("opportunities_before_filters") or 0) + len(
            raw_directions
        )

        if cfg.require_macro_release_filter and _is_in_macro_release_block(
            bar_time,
            macro_release_times,
            macro_block_minutes,
        ):
            _inc_reason(audit["rejections"], "macro_release_block", len(raw_directions))
            continue

        if cfg.require_breakout_open_inside_range and not (orb_low <= current_open <= orb_high):
            _inc_reason(audit["rejections"], "breakout_open_outside_range", len(raw_directions))
            continue

        candidate_directions: List[int] = []
        for direction in raw_directions:
            if direction > 0 and cfg.allow_long:
                candidate_directions.append(direction)
            elif direction < 0 and cfg.allow_short:
                candidate_directions.append(direction)
            else:
                _inc_reason(audit["rejections"], "direction_not_allowed")
        if not candidate_directions:
            continue

        if cfg.use_opening_bar_direction:
            filtered = [direction for direction in candidate_directions if direction == opening_bar_direction]
            skipped = len(candidate_directions) - len(filtered)
            if skipped > 0:
                _inc_reason(audit["rejections"], "opening_bar_direction_mismatch", skipped)
            candidate_directions = filtered
            if not candidate_directions:
                continue

        relative_volume_rejection = _relative_volume_rejection_reason(cfg, relative_opening_volume)
        if relative_volume_rejection is not None:
            _inc_reason(audit["rejections"], relative_volume_rejection, len(candidate_directions))
            continue

        if cfg.require_atr_filter:
            if atr_value is None or atr_value < cfg.atr_min:
                _inc_reason(audit["rejections"], "atr_filter", len(candidate_directions))
                continue

        require_volume_filter = bool(cfg.require_volume_spike) or min_volume_multiple > 1.0
        volume_ratio = 1.0
        if require_volume_filter:
            if idx < cfg.volume_ma_window:
                _inc_reason(audit["rejections"], "volume_ma_warmup", len(candidate_directions))
                continue
            lookback = session_bars[idx - cfg.volume_ma_window : idx]
            avg_volume = _mean_fast(float(row.get("volume") or 0.0) for row in lookback)
            if avg_volume <= 0:
                _inc_reason(audit["rejections"], "volume_ma_invalid", len(candidate_directions))
                continue
            volume_ratio = float(bar.get("volume") or 0.0) / avg_volume
            required_volume_ratio = 0.0
            if bool(cfg.require_volume_spike):
                required_volume_ratio = max(required_volume_ratio, float(cfg.volume_spike_multiple))
            if min_volume_multiple > 1.0:
                required_volume_ratio = max(required_volume_ratio, min_volume_multiple)
            if volume_ratio < required_volume_ratio:
                _inc_reason(audit["rejections"], "momentum_volume_filter", len(candidate_directions))
                continue

        selected_direction: Optional[int] = None
        selected_breakout_or_frac = 0.0
        selected_close_location = 0.0
        selected_ema_spread_pct = 0.0
        selected_pullback_pct = 0.0
        selected_body_or_frac = 0.0
        selected_opposite_wick_body_ratio = 0.0
        selected_atr_range = 0.0
        selected_adx = 0.0
        for direction in candidate_directions:
            if direction > 0:
                if bool(cfg.require_trend_alignment) and not (ema_fast[idx] > ema_slow[idx]):
                    _inc_reason(audit["rejections"], "trend_alignment_filter")
                    continue
                breakout_distance = (
                    current_high - orb_high if trigger_mode == "stop_touch" else current_close - orb_high
                )
            else:
                if bool(cfg.require_trend_alignment) and not (ema_fast[idx] < ema_slow[idx]):
                    _inc_reason(audit["rejections"], "trend_alignment_filter")
                    continue
                breakout_distance = (
                    orb_low - current_low if trigger_mode == "stop_touch" else orb_low - current_close
                )

            if breakout_distance <= 0:
                _inc_reason(audit["rejections"], "momentum_breakout_distance")
                continue
            breakout_or_frac = breakout_distance / max(orb_width, 1e-9)
            if breakout_or_frac < min_breakout_or_frac:
                _inc_reason(audit["rejections"], "momentum_breakout_strength")
                continue
            if breakout_or_frac > max_breakout_or_frac:
                _inc_reason(audit["rejections"], "momentum_breakout_overextension")
                continue

            close_location = _close_location_fraction(
                direction=direction,
                high_price=current_high,
                low_price=current_low,
                close_price=current_close,
            )
            if close_location < min_close_location:
                _inc_reason(audit["rejections"], "momentum_close_location")
                continue

            ema_spread_pct = abs(ema_fast[idx] - ema_slow[idx]) / max(current_close, 1.0)
            if ema_spread_pct < min_ema_spread_pct:
                _inc_reason(audit["rejections"], "momentum_ema_spread")
                continue

            pullback_to_ema_pct = abs(current_close - ema_fast[idx]) / max(current_close, 1.0)
            if pullback_to_ema_pct > max_pullback_to_ema_pct:
                _inc_reason(audit["rejections"], "momentum_ema_extension")
                continue

            body_abs = abs(current_close - current_open)
            body_or_frac = body_abs / max(orb_width, 1e-9)
            if body_or_frac < min_body_or_frac:
                _inc_reason(audit["rejections"], "momentum_body_strength")
                continue

            if direction > 0:
                opposite_wick = min(current_open, current_close) - current_low
            else:
                opposite_wick = current_high - max(current_open, current_close)
            opposite_wick_body_ratio = max(opposite_wick, 0.0) / max(body_abs, 1e-9)
            if opposite_wick_body_ratio > max_opposite_wick_body_ratio:
                _inc_reason(audit["rejections"], "momentum_opposite_wick")
                continue

            atr_range = 0.0
            if atr_range_min > 0:
                if atr_value is None or atr_value <= 0:
                    _inc_reason(audit["rejections"], "momentum_atr_unavailable")
                    continue
                atr_range = (current_high - current_low) / max(atr_value, 1e-9)
                if atr_range < atr_range_min:
                    _inc_reason(audit["rejections"], "momentum_atr_expansion")
                    continue

            if bool(cfg.require_trend_alignment):
                trend_start = idx - trend_bars_min + 1
                if trend_start < opening_range_count:
                    _inc_reason(audit["rejections"], "momentum_trend_window")
                    continue
                trend_persistent = True
                for trend_idx in range(trend_start, idx + 1):
                    if direction > 0 and not (ema_fast[trend_idx] > ema_slow[trend_idx]):
                        trend_persistent = False
                        break
                    if direction < 0 and not (ema_fast[trend_idx] < ema_slow[trend_idx]):
                        trend_persistent = False
                        break
                if not trend_persistent:
                    _inc_reason(audit["rejections"], "momentum_trend_persistence")
                    continue

            if min_adx > 0:
                adx_ready_idx = max((adx_period * 2) - 1, opening_range_count)
                if idx < adx_ready_idx:
                    _inc_reason(audit["rejections"], "momentum_adx_warmup")
                    continue
                adx_value = float(adx_values[idx])
                if adx_value < min_adx:
                    _inc_reason(audit["rejections"], "momentum_adx_filter")
                    continue
            else:
                adx_value = 0.0

            confirm_start = idx - confirm_bars + 1
            if confirm_start < opening_range_count:
                _inc_reason(audit["rejections"], "momentum_confirmation_window")
                continue
            confirmed = True
            for confirm_idx in range(confirm_start, idx + 1):
                confirm_close = float(session_bars[confirm_idx].get("close") or 0.0)
                if direction > 0 and confirm_close <= orb_high:
                    confirmed = False
                    break
                if direction < 0 and confirm_close >= orb_low:
                    confirmed = False
                    break
            if not confirmed:
                _inc_reason(audit["rejections"], "momentum_confirmation")
                continue

            selected_direction = direction
            selected_breakout_or_frac = breakout_or_frac
            selected_close_location = close_location
            selected_ema_spread_pct = ema_spread_pct
            selected_pullback_pct = pullback_to_ema_pct
            selected_body_or_frac = body_or_frac
            selected_opposite_wick_body_ratio = opposite_wick_body_ratio
            selected_atr_range = atr_range
            selected_adx = adx_value
            break

        if selected_direction is None:
            continue

        entry_idx, entry_bar, entry_price = _next_bar_open_entry(session_bars, signal_idx=idx)
        if entry_idx is None or entry_bar is None or entry_price <= 0:
            _inc_reason(audit["rejections"], "invalid_entry_price")
            continue

        stop_price = _compute_stop_price(
            cfg=cfg,
            direction=selected_direction,
            orb_high=orb_high,
            orb_low=orb_low,
            breakout_high=current_high,
            breakout_low=current_low,
            entry_price=entry_price,
            atr_value=atr_value,
        )
        if stop_price is None:
            _inc_reason(audit["rejections"], "invalid_stop")
            continue

        audit["opportunities_after_filters"] = int(audit.get("opportunities_after_filters") or 0) + 1
        if setup is not None:
            continue

        setup = {
            "direction": selected_direction,
            "signal_idx": idx,
            "signal_ts": bar["ts"],
            "entry_idx": entry_idx,
            "entry_ts": entry_bar["ts"],
            "entry_underlying": entry_price,
            "stop_underlying": stop_price,
            "orb_high": orb_high,
            "orb_low": orb_low,
            "opening_bar_open": orb_open,
            "opening_bar_close": orb_close,
            "opening_bar_direction": opening_bar_direction,
            "trend_ema_fast": ema_fast[idx],
            "trend_ema_slow": ema_slow[idx],
            "volume_ratio": volume_ratio,
            "relative_opening_volume": relative_opening_volume,
            "atr_value": atr_value,
            "fvg_gap": 0.0,
            "opening_range_minutes": opening_range_count,
            "orb_width_pct": orb_width_pct,
            "strategy_variant": "orb_momentum_v1",
            "momentum_breakout_or_frac": selected_breakout_or_frac,
            "momentum_close_location": selected_close_location,
            "momentum_ema_spread_pct": selected_ema_spread_pct,
            "momentum_pullback_to_ema_pct": selected_pullback_pct,
            "momentum_confirmation_bars": confirm_bars,
            "momentum_body_or_frac": selected_body_or_frac,
            "momentum_opposite_wick_body_ratio": selected_opposite_wick_body_ratio,
            "momentum_atr_range": selected_atr_range,
            "momentum_breakout_max_or_frac": max_breakout_or_frac,
            "momentum_trend_bars_min": trend_bars_min,
            "momentum_adx": selected_adx,
        }

    return setup, audit


def _bar_volume_ratio(session_bars: List[Dict[str, Any]], idx: int, volume_ma_window: int) -> Optional[float]:
    if idx < int(volume_ma_window):
        return None
    lookback = session_bars[idx - int(volume_ma_window) : idx]
    avg_volume = _mean_fast(float(row.get("volume") or 0.0) for row in lookback)
    if avg_volume <= 0:
        return None
    return float(session_bars[idx].get("volume") or 0.0) / avg_volume


def _find_orb_vwap_reclaim_setup_with_audit(
    session_bars: List[Dict[str, Any]],
    cfg: IntradayStrategyConfig,
    relative_opening_volume: Optional[float],
    atr_value: Optional[float],
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    audit: Dict[str, Any] = {
        "strategy_variant": "orb_vwap_reclaim_v1",
        "opportunities_before_filters": 0,
        "opportunities_after_filters": 0,
        "rejections": {},
    }
    opening_range_count = max(int(cfg.opening_range_minutes), 1)
    if len(session_bars) < (opening_range_count + 5):
        _inc_reason(audit["rejections"], "insufficient_bars")
        return None, audit

    opening_range = session_bars[:opening_range_count]
    orb_high = max(float(bar.get("high") or 0.0) for bar in opening_range)
    orb_low = min(float(bar.get("low") or 0.0) for bar in opening_range)
    orb_open = float(opening_range[0].get("open") or 0.0)
    orb_close = float(opening_range[-1].get("close") or 0.0)
    if orb_high <= 0 or orb_low <= 0 or orb_high <= orb_low:
        _inc_reason(audit["rejections"], "invalid_opening_range")
        return None, audit

    orb_width = orb_high - orb_low
    orb_width_pct = orb_width / max(orb_open, 1.0)
    if cfg.require_or_width_filter:
        min_width = max(float(cfg.opening_range_min_width_pct), 0.0)
        max_width = max(float(cfg.opening_range_max_width_pct), min_width)
        if orb_width_pct < min_width or orb_width_pct > max_width:
            _inc_reason(audit["rejections"], "orb_width_filter")
            return None, audit

    closes = [float(bar.get("close") or 0.0) for bar in session_bars]
    ema_fast = _ema_series(closes, cfg.trend_ema_fast)
    ema_slow = _ema_series(closes, cfg.trend_ema_slow)
    vwap_series = _running_vwap_series(session_bars)
    opening_bar_direction = 1 if orb_close > orb_open else (-1 if orb_close < orb_open else 0)

    entry_start = _parse_hhmm(cfg.entry_start_time, _default_entry_start(opening_range_count))
    entry_cutoff = _parse_hhmm(cfg.entry_cutoff_time, "12:00")
    trigger_mode = str(cfg.entry_trigger_mode or "close_breakout").strip().lower()
    min_breakout_or_frac = max(float(getattr(cfg, "trend_pullback_min_breakout_or_frac", 0.0)), 0.0)
    min_volume_multiple = max(float(getattr(cfg, "trend_pullback_min_volume_multiple", 0.0)), 0.0)
    vwap_buffer_pct = max(float(getattr(cfg, "trend_pullback_ema_buffer_pct", 0.0)), 0.0)
    max_pullback_bars = max(int(getattr(cfg, "trend_pullback_max_bars_after_breakout", 0)), 1)
    require_orb_reclaim = bool(getattr(cfg, "trend_pullback_require_orb_reclaim", True))

    breakout_state: Optional[Dict[str, Any]] = None
    setup: Optional[Dict[str, Any]] = None
    for idx in range(opening_range_count, len(session_bars) - 1):
        bar = session_bars[idx]
        bar_time = _to_et_time(bar["ts"])
        if bar_time < entry_start or bar_time > entry_cutoff:
            continue

        open_price = float(bar.get("open") or 0.0)
        high_price = float(bar.get("high") or 0.0)
        low_price = float(bar.get("low") or 0.0)
        close_price = float(bar.get("close") or 0.0)
        vwap_now = float(vwap_series[idx]) if idx < len(vwap_series) else 0.0
        if open_price <= 0 or high_price <= 0 or low_price <= 0 or close_price <= 0 or vwap_now <= 0:
            continue

        if breakout_state is None:
            if trigger_mode == "stop_touch":
                long_breakout = high_price >= orb_high
                short_breakout = low_price <= orb_low
            else:
                long_breakout = close_price > orb_high
                short_breakout = close_price < orb_low
            raw_directions: List[int] = []
            if long_breakout:
                raw_directions.append(1)
            if short_breakout:
                raw_directions.append(-1)
            if not raw_directions:
                continue
            audit["opportunities_before_filters"] = int(audit.get("opportunities_before_filters") or 0) + len(
                raw_directions
            )

            for candidate in raw_directions:
                if candidate > 0 and not cfg.allow_long:
                    _inc_reason(audit["rejections"], "direction_not_allowed")
                    continue
                if candidate < 0 and not cfg.allow_short:
                    _inc_reason(audit["rejections"], "direction_not_allowed")
                    continue
                if cfg.use_opening_bar_direction and candidate != opening_bar_direction:
                    _inc_reason(audit["rejections"], "opening_bar_direction_mismatch")
                    continue
                relative_volume_rejection = _relative_volume_rejection_reason(cfg, relative_opening_volume)
                if relative_volume_rejection is not None:
                    _inc_reason(audit["rejections"], relative_volume_rejection)
                    continue
                if cfg.require_atr_filter:
                    if atr_value is None or atr_value < cfg.atr_min:
                        _inc_reason(audit["rejections"], "atr_filter")
                        continue
                if candidate > 0 and not (ema_fast[idx] > ema_slow[idx]):
                    _inc_reason(audit["rejections"], "trend_alignment_filter")
                    continue
                if candidate < 0 and not (ema_fast[idx] < ema_slow[idx]):
                    _inc_reason(audit["rejections"], "trend_alignment_filter")
                    continue
                breakout_distance = (
                    (high_price - orb_high)
                    if candidate > 0 and trigger_mode == "stop_touch"
                    else (close_price - orb_high)
                    if candidate > 0
                    else (orb_low - low_price)
                    if trigger_mode == "stop_touch"
                    else (orb_low - close_price)
                )
                if breakout_distance <= 0:
                    _inc_reason(audit["rejections"], "trend_pullback_breakout_distance")
                    continue
                breakout_or_frac = breakout_distance / max(orb_width, 1e-9)
                if breakout_or_frac < min_breakout_or_frac:
                    _inc_reason(audit["rejections"], "trend_pullback_breakout_strength")
                    continue
                volume_ratio = _bar_volume_ratio(session_bars, idx, cfg.volume_ma_window)
                if volume_ratio is None:
                    _inc_reason(audit["rejections"], "volume_ma_warmup")
                    continue
                if volume_ratio < min_volume_multiple:
                    _inc_reason(audit["rejections"], "trend_pullback_volume_filter")
                    continue
                breakout_state = {
                    "direction": candidate,
                    "idx": idx,
                    "high": high_price,
                    "low": low_price,
                    "volume_ratio": volume_ratio,
                    "breakout_or_frac": breakout_or_frac,
                }
                break
            continue

        assert breakout_state is not None
        bars_since_breakout = idx - int(breakout_state["idx"])
        if bars_since_breakout > max_pullback_bars:
            _inc_reason(audit["rejections"], "trend_pullback_timeout")
            breakout_state = None
            continue

        direction = int(breakout_state["direction"])
        if direction > 0:
            touched = low_price <= (vwap_now * (1.0 + vwap_buffer_pct))
            confirmed = close_price >= vwap_now
            if require_orb_reclaim:
                confirmed = confirmed and close_price > orb_high
        else:
            touched = high_price >= (vwap_now * (1.0 - vwap_buffer_pct))
            confirmed = close_price <= vwap_now
            if require_orb_reclaim:
                confirmed = confirmed and close_price < orb_low
        if not touched or not confirmed:
            continue

        entry_idx = idx + 1
        entry_bar = session_bars[entry_idx]
        entry_price = float(entry_bar.get("open") or 0.0)
        if entry_price <= 0:
            _inc_reason(audit["rejections"], "invalid_entry_price")
            breakout_state = None
            continue

        stop_price = _compute_stop_price(
            cfg=cfg,
            direction=direction,
            orb_high=orb_high,
            orb_low=orb_low,
            breakout_high=float(breakout_state["high"]),
            breakout_low=float(breakout_state["low"]),
            entry_price=entry_price,
            atr_value=atr_value,
        )
        if stop_price is None:
            _inc_reason(audit["rejections"], "invalid_stop")
            breakout_state = None
            continue

        audit["opportunities_after_filters"] = int(audit.get("opportunities_after_filters") or 0) + 1
        setup = {
            "direction": direction,
            "signal_idx": idx,
            "signal_ts": bar["ts"],
            "entry_idx": entry_idx,
            "entry_ts": entry_bar["ts"],
            "entry_underlying": entry_price,
            "stop_underlying": stop_price,
            "orb_high": orb_high,
            "orb_low": orb_low,
            "opening_bar_open": orb_open,
            "opening_bar_close": orb_close,
            "opening_bar_direction": opening_bar_direction,
            "trend_ema_fast": ema_fast[idx],
            "trend_ema_slow": ema_slow[idx],
            "volume_ratio": float(breakout_state.get("volume_ratio") or 0.0),
            "relative_opening_volume": relative_opening_volume,
            "atr_value": atr_value,
            "fvg_gap": 0.0,
            "opening_range_minutes": opening_range_count,
            "orb_width_pct": orb_width_pct,
            "strategy_variant": "orb_vwap_reclaim_v1",
            "trend_pullback_breakout_or_frac": float(breakout_state.get("breakout_or_frac") or 0.0),
            "trend_pullback_bars_since_breakout": int(bars_since_breakout),
            "momentum_vwap_at_signal": vwap_now,
        }
        break

    if setup is None and int(audit.get("opportunities_before_filters") or 0) == 0:
        _inc_reason(audit["rejections"], "no_breakout_detected")
    return setup, audit


def _find_orb_trend_pullback_setup_with_audit(
    session_bars: List[Dict[str, Any]],
    cfg: IntradayStrategyConfig,
    relative_opening_volume: Optional[float],
    atr_value: Optional[float],
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    audit: Dict[str, Any] = {
        "strategy_variant": "orb_trend_pullback_v1",
        "opportunities_before_filters": 0,
        "opportunities_after_filters": 0,
        "rejections": {},
    }
    opening_range_count = max(int(cfg.opening_range_minutes), 1)
    if len(session_bars) < (opening_range_count + 5):
        _inc_reason(audit["rejections"], "insufficient_bars")
        return None, audit

    opening_range = session_bars[:opening_range_count]
    orb_high = max(float(bar.get("high") or 0.0) for bar in opening_range)
    orb_low = min(float(bar.get("low") or 0.0) for bar in opening_range)
    orb_open = float(opening_range[0].get("open") or 0.0)
    orb_close = float(opening_range[-1].get("close") or 0.0)
    if orb_high <= 0 or orb_low <= 0 or orb_high <= orb_low:
        _inc_reason(audit["rejections"], "invalid_opening_range")
        return None, audit

    orb_width = orb_high - orb_low
    orb_width_pct = orb_width / max(orb_open, 1.0)
    if cfg.require_or_width_filter:
        min_width = max(float(cfg.opening_range_min_width_pct), 0.0)
        max_width = max(float(cfg.opening_range_max_width_pct), min_width)
        if orb_width_pct < min_width or orb_width_pct > max_width:
            _inc_reason(audit["rejections"], "orb_width_filter")
            return None, audit

    closes = [float(bar.get("close") or 0.0) for bar in session_bars]
    ema_fast = _ema_series(closes, cfg.trend_ema_fast)
    ema_slow = _ema_series(closes, cfg.trend_ema_slow)
    opening_bar_direction = 1 if orb_close > orb_open else (-1 if orb_close < orb_open else 0)

    entry_start = _parse_hhmm(cfg.entry_start_time, _default_entry_start(opening_range_count))
    entry_cutoff = _parse_hhmm(cfg.entry_cutoff_time, "12:00")
    trigger_mode = str(cfg.entry_trigger_mode or "close_breakout").strip().lower()
    min_breakout_or_frac = max(float(getattr(cfg, "trend_pullback_min_breakout_or_frac", 0.0)), 0.0)
    min_volume_multiple = max(float(getattr(cfg, "trend_pullback_min_volume_multiple", 0.0)), 0.0)
    ema_buffer_pct = max(float(getattr(cfg, "trend_pullback_ema_buffer_pct", 0.0)), 0.0)
    max_pullback_bars = max(int(getattr(cfg, "trend_pullback_max_bars_after_breakout", 0)), 1)
    require_orb_reclaim = bool(getattr(cfg, "trend_pullback_require_orb_reclaim", True))

    breakout_state: Optional[Dict[str, Any]] = None
    setup: Optional[Dict[str, Any]] = None
    for idx in range(opening_range_count, len(session_bars) - 1):
        bar = session_bars[idx]
        bar_time = _to_et_time(bar["ts"])
        if bar_time < entry_start or bar_time > entry_cutoff:
            continue

        open_price = float(bar.get("open") or 0.0)
        high_price = float(bar.get("high") or 0.0)
        low_price = float(bar.get("low") or 0.0)
        close_price = float(bar.get("close") or 0.0)
        if open_price <= 0 or high_price <= 0 or low_price <= 0 or close_price <= 0:
            continue

        if breakout_state is None:
            if trigger_mode == "stop_touch":
                long_breakout = high_price >= orb_high
                short_breakout = low_price <= orb_low
            else:
                long_breakout = close_price > orb_high
                short_breakout = close_price < orb_low
            raw_directions: List[int] = []
            if long_breakout:
                raw_directions.append(1)
            if short_breakout:
                raw_directions.append(-1)
            if not raw_directions:
                continue
            audit["opportunities_before_filters"] = int(audit.get("opportunities_before_filters") or 0) + len(
                raw_directions
            )

            direction = 0
            for candidate in raw_directions:
                if candidate > 0 and not cfg.allow_long:
                    _inc_reason(audit["rejections"], "direction_not_allowed")
                    continue
                if candidate < 0 and not cfg.allow_short:
                    _inc_reason(audit["rejections"], "direction_not_allowed")
                    continue
                if cfg.use_opening_bar_direction and candidate != opening_bar_direction:
                    _inc_reason(audit["rejections"], "opening_bar_direction_mismatch")
                    continue
                relative_volume_rejection = _relative_volume_rejection_reason(cfg, relative_opening_volume)
                if relative_volume_rejection is not None:
                    _inc_reason(audit["rejections"], relative_volume_rejection)
                    continue
                if cfg.require_atr_filter:
                    if atr_value is None or atr_value < cfg.atr_min:
                        _inc_reason(audit["rejections"], "atr_filter")
                        continue
                if candidate > 0 and not (ema_fast[idx] > ema_slow[idx]):
                    _inc_reason(audit["rejections"], "trend_alignment_filter")
                    continue
                if candidate < 0 and not (ema_fast[idx] < ema_slow[idx]):
                    _inc_reason(audit["rejections"], "trend_alignment_filter")
                    continue
                breakout_distance = (
                    (high_price - orb_high)
                    if candidate > 0 and trigger_mode == "stop_touch"
                    else (close_price - orb_high)
                    if candidate > 0
                    else (orb_low - low_price)
                    if trigger_mode == "stop_touch"
                    else (orb_low - close_price)
                )
                if breakout_distance <= 0:
                    _inc_reason(audit["rejections"], "trend_pullback_breakout_distance")
                    continue
                breakout_or_frac = breakout_distance / max(orb_width, 1e-9)
                if breakout_or_frac < min_breakout_or_frac:
                    _inc_reason(audit["rejections"], "trend_pullback_breakout_strength")
                    continue
                volume_ratio = _bar_volume_ratio(session_bars, idx, cfg.volume_ma_window)
                if volume_ratio is None:
                    _inc_reason(audit["rejections"], "volume_ma_warmup")
                    continue
                if volume_ratio < min_volume_multiple:
                    _inc_reason(audit["rejections"], "trend_pullback_volume_filter")
                    continue
                direction = candidate
                breakout_state = {
                    "direction": direction,
                    "idx": idx,
                    "high": high_price,
                    "low": low_price,
                    "volume_ratio": volume_ratio,
                    "breakout_or_frac": breakout_or_frac,
                }
                break
            continue

        assert breakout_state is not None
        bars_since_breakout = idx - int(breakout_state["idx"])
        if bars_since_breakout > max_pullback_bars:
            _inc_reason(audit["rejections"], "trend_pullback_timeout")
            breakout_state = None
            continue

        direction = int(breakout_state["direction"])
        ema_now = float(ema_fast[idx])
        if direction > 0:
            touched = low_price <= (ema_now * (1.0 + ema_buffer_pct))
            confirmed = close_price >= ema_now
            if require_orb_reclaim:
                confirmed = confirmed and close_price > orb_high
        else:
            touched = high_price >= (ema_now * (1.0 - ema_buffer_pct))
            confirmed = close_price <= ema_now
            if require_orb_reclaim:
                confirmed = confirmed and close_price < orb_low
        if not touched or not confirmed:
            continue

        entry_idx = idx + 1
        entry_bar = session_bars[entry_idx]
        entry_price = float(entry_bar.get("open") or 0.0)
        if entry_price <= 0:
            _inc_reason(audit["rejections"], "invalid_entry_price")
            breakout_state = None
            continue

        stop_price = _compute_stop_price(
            cfg=cfg,
            direction=direction,
            orb_high=orb_high,
            orb_low=orb_low,
            breakout_high=float(breakout_state["high"]),
            breakout_low=float(breakout_state["low"]),
            entry_price=entry_price,
            atr_value=atr_value,
        )
        if stop_price is None:
            _inc_reason(audit["rejections"], "invalid_stop")
            breakout_state = None
            continue

        audit["opportunities_after_filters"] = int(audit.get("opportunities_after_filters") or 0) + 1
        setup = {
            "direction": direction,
            "signal_idx": idx,
            "signal_ts": bar["ts"],
            "entry_idx": entry_idx,
            "entry_ts": entry_bar["ts"],
            "entry_underlying": entry_price,
            "stop_underlying": stop_price,
            "orb_high": orb_high,
            "orb_low": orb_low,
            "opening_bar_open": orb_open,
            "opening_bar_close": orb_close,
            "opening_bar_direction": opening_bar_direction,
            "trend_ema_fast": ema_fast[idx],
            "trend_ema_slow": ema_slow[idx],
            "volume_ratio": float(breakout_state.get("volume_ratio") or 0.0),
            "relative_opening_volume": relative_opening_volume,
            "atr_value": atr_value,
            "fvg_gap": 0.0,
            "opening_range_minutes": opening_range_count,
            "orb_width_pct": orb_width_pct,
            "strategy_variant": "orb_trend_pullback_v1",
            "trend_pullback_breakout_or_frac": float(breakout_state.get("breakout_or_frac") or 0.0),
            "trend_pullback_bars_since_breakout": int(bars_since_breakout),
        }
        break

    if setup is None and int(audit.get("opportunities_before_filters") or 0) == 0:
        _inc_reason(audit["rejections"], "no_breakout_detected")
    return setup, audit


def _find_opening_drive_pullback_setup_with_audit(
    session_bars: List[Dict[str, Any]],
    cfg: IntradayStrategyConfig,
    relative_opening_volume: Optional[float],
    atr_value: Optional[float],
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    audit: Dict[str, Any] = {
        "strategy_variant": "opening_drive_pullback_v1",
        "opportunities_before_filters": 0,
        "opportunities_after_filters": 0,
        "rejections": {},
    }
    drive_count = max(int(cfg.opening_range_minutes), 1)
    if len(session_bars) < (drive_count + 3):
        _inc_reason(audit["rejections"], "insufficient_bars")
        return None, audit

    drive_window = session_bars[:drive_count]
    drive_high = max(float(bar.get("high") or 0.0) for bar in drive_window)
    drive_low = min(float(bar.get("low") or 0.0) for bar in drive_window)
    drive_open = float(drive_window[0].get("open") or 0.0)
    drive_close = float(drive_window[-1].get("close") or 0.0)
    if drive_high <= 0 or drive_low <= 0 or drive_high <= drive_low or drive_open <= 0 or drive_close <= 0:
        _inc_reason(audit["rejections"], "invalid_opening_drive")
        return None, audit

    drive_range = drive_high - drive_low
    drive_range_pct = drive_range / max(drive_open, 1.0)
    if cfg.require_or_width_filter:
        min_width = max(float(cfg.opening_range_min_width_pct), 0.0)
        max_width = max(float(cfg.opening_range_max_width_pct), min_width)
        if drive_range_pct < min_width or drive_range_pct > max_width:
            _inc_reason(audit["rejections"], "drive_width_filter")
            return None, audit

    drive_direction = 1 if drive_close > drive_open else (-1 if drive_close < drive_open else 0)
    if drive_direction == 0:
        _inc_reason(audit["rejections"], "flat_opening_drive")
        return None, audit
    if drive_direction > 0 and not cfg.allow_long:
        _inc_reason(audit["rejections"], "direction_not_allowed")
        return None, audit
    if drive_direction < 0 and not cfg.allow_short:
        _inc_reason(audit["rejections"], "direction_not_allowed")
        return None, audit

    drive_abs_return_pct = abs(drive_close - drive_open) / max(drive_open, 1.0)
    if drive_abs_return_pct < max(float(getattr(cfg, "drive_min_abs_return_pct", 0.0)), 0.0):
        _inc_reason(audit["rejections"], "drive_abs_return_filter")
        return None, audit

    drive_close_location = _close_location_fraction(
        direction=drive_direction,
        high_price=drive_high,
        low_price=drive_low,
        close_price=drive_close,
    )
    if drive_close_location < max(0.0, min(1.0, float(getattr(cfg, "drive_close_location_min", 0.0)))):
        _inc_reason(audit["rejections"], "drive_close_location_filter")
        return None, audit

    relative_volume_rejection = _relative_volume_rejection_reason(cfg, relative_opening_volume)
    if relative_volume_rejection is not None:
        _inc_reason(audit["rejections"], relative_volume_rejection)
        return None, audit
    if cfg.require_atr_filter:
        if atr_value is None or atr_value < cfg.atr_min:
            _inc_reason(audit["rejections"], "atr_filter")
            return None, audit

    closes = [float(bar.get("close") or 0.0) for bar in session_bars]
    ema_fast = _ema_series(closes, cfg.trend_ema_fast)
    ema_slow = _ema_series(closes, cfg.trend_ema_slow)
    vwap_series = _running_vwap_series(session_bars)
    drive_end_idx = drive_count - 1
    drive_vwap = float(vwap_series[drive_end_idx]) if drive_end_idx < len(vwap_series) else 0.0
    if drive_vwap <= 0:
        _inc_reason(audit["rejections"], "drive_vwap_unavailable")
        return None, audit
    if drive_direction > 0:
        if not (drive_close > drive_vwap and ema_fast[drive_end_idx] > ema_slow[drive_end_idx]):
            _inc_reason(audit["rejections"], "drive_trend_alignment")
            return None, audit
    else:
        if not (drive_close < drive_vwap and ema_fast[drive_end_idx] < ema_slow[drive_end_idx]):
            _inc_reason(audit["rejections"], "drive_trend_alignment")
            return None, audit

    drive_move = abs(drive_close - drive_open)
    drive_mid = (drive_open + drive_close) / 2.0
    touch_buffer_pct = max(float(getattr(cfg, "drive_touch_ma_buffer_pct", 0.0)), 0.0)
    min_retrace_frac = max(float(getattr(cfg, "drive_pullback_min_retrace_frac", 0.0)), 0.0)
    max_retrace_frac = max(float(getattr(cfg, "drive_pullback_max_retrace_frac", 0.0)), min_retrace_frac)
    reclaim_close_location_min = max(
        0.0,
        min(1.0, float(getattr(cfg, "drive_reclaim_close_location_min", 0.0))),
    )
    reclaim_min_volume_multiple = max(float(getattr(cfg, "drive_reclaim_min_volume_multiple", 0.0)), 0.0)
    require_hold_drive_open = bool(getattr(cfg, "drive_pullback_require_hold_drive_open", True))
    require_prev_extreme_break = bool(getattr(cfg, "drive_reclaim_requires_prev_extreme_break", True))
    max_pullback_bars = max(int(getattr(cfg, "drive_max_pullback_bars", 1)), 1)
    stop_buffer_range_frac = max(float(getattr(cfg, "drive_stop_buffer_range_frac", 0.0)), 0.0)

    entry_start = _parse_hhmm(cfg.entry_start_time, _default_entry_start(drive_count))
    entry_cutoff = _parse_hhmm(cfg.entry_cutoff_time, "12:00")
    setup: Optional[Dict[str, Any]] = None
    for idx in range(drive_count, len(session_bars) - 1):
        bar = session_bars[idx]
        bar_time = _to_et_time(bar["ts"])
        if bar_time < entry_start or bar_time > entry_cutoff:
            continue
        if (idx - drive_end_idx) > max_pullback_bars:
            _inc_reason(audit["rejections"], "drive_pullback_timeout")
            break

        open_price = float(bar.get("open") or 0.0)
        high_price = float(bar.get("high") or 0.0)
        low_price = float(bar.get("low") or 0.0)
        close_price = float(bar.get("close") or 0.0)
        if open_price <= 0 or high_price <= 0 or low_price <= 0 or close_price <= 0:
            continue
        vwap_now = float(vwap_series[idx]) if idx < len(vwap_series) else 0.0
        ema_now = float(ema_fast[idx]) if idx < len(ema_fast) else 0.0
        if vwap_now <= 0 or ema_now <= 0:
            _inc_reason(audit["rejections"], "drive_pullback_ma_unavailable")
            continue

        prev_bar = session_bars[idx - 1] if idx > 0 else None
        prev_high = float((prev_bar or {}).get("high") or 0.0)
        prev_low = float((prev_bar or {}).get("low") or 0.0)
        volume_ratio = 1.0
        lookback = session_bars[max(drive_count, idx - 3) : idx]
        if lookback:
            avg_volume = _mean_fast(float(row.get("volume") or 0.0) for row in lookback)
            if avg_volume > 0:
                volume_ratio = float(bar.get("volume") or 0.0) / avg_volume

        audit["opportunities_before_filters"] = int(audit.get("opportunities_before_filters") or 0) + 1
        if volume_ratio < reclaim_min_volume_multiple:
            _inc_reason(audit["rejections"], "drive_reclaim_volume")
            continue

        if drive_direction > 0:
            retrace_frac = max(drive_close - low_price, 0.0) / max(drive_move, 1e-9)
            touched = low_price <= (max(vwap_now, ema_now) * (1.0 + touch_buffer_pct))
            structure_ok = close_price > drive_mid and (not require_hold_drive_open or low_price > drive_open)
            reclaim_threshold = max(ema_now, vwap_now)
            if require_prev_extreme_break and prev_high > 0:
                reclaim_threshold = max(reclaim_threshold, prev_high)
            reclaim = close_price > reclaim_threshold
            reclaim_location = _close_location_fraction(
                direction=1,
                high_price=high_price,
                low_price=low_price,
                close_price=close_price,
            )
            stop_price = low_price - (drive_range * stop_buffer_range_frac)
        else:
            retrace_frac = max(high_price - drive_close, 0.0) / max(drive_move, 1e-9)
            touched = high_price >= (min(vwap_now, ema_now) * (1.0 - touch_buffer_pct))
            structure_ok = close_price < drive_mid and (not require_hold_drive_open or high_price < drive_open)
            reclaim_threshold = min(ema_now, vwap_now)
            if require_prev_extreme_break and prev_low > 0:
                reclaim_threshold = min(reclaim_threshold, prev_low)
            reclaim = close_price < reclaim_threshold
            reclaim_location = _close_location_fraction(
                direction=-1,
                high_price=high_price,
                low_price=low_price,
                close_price=close_price,
            )
            stop_price = high_price + (drive_range * stop_buffer_range_frac)

        if retrace_frac < min_retrace_frac:
            _inc_reason(audit["rejections"], "drive_pullback_too_shallow")
            continue
        if retrace_frac > max_retrace_frac:
            _inc_reason(audit["rejections"], "drive_pullback_too_deep")
            continue
        if not touched:
            _inc_reason(audit["rejections"], "drive_pullback_ma_touch")
            continue
        if not structure_ok:
            _inc_reason(audit["rejections"], "drive_pullback_structure")
            continue
        if reclaim_location < reclaim_close_location_min:
            _inc_reason(audit["rejections"], "drive_reclaim_close_location")
            continue
        if not reclaim:
            _inc_reason(audit["rejections"], "drive_reclaim_confirmation")
            continue

        entry_idx, entry_bar, entry_price = _next_bar_open_entry(session_bars, signal_idx=idx)
        if entry_idx is None or entry_bar is None or entry_price <= 0:
            _inc_reason(audit["rejections"], "invalid_entry_price")
            continue
        if drive_direction > 0 and stop_price >= entry_price:
            _inc_reason(audit["rejections"], "invalid_stop")
            continue
        if drive_direction < 0 and stop_price <= entry_price:
            _inc_reason(audit["rejections"], "invalid_stop")
            continue

        audit["opportunities_after_filters"] = int(audit.get("opportunities_after_filters") or 0) + 1
        setup = {
            "direction": drive_direction,
            "signal_idx": idx,
            "signal_ts": bar["ts"],
            "entry_idx": entry_idx,
            "entry_ts": entry_bar["ts"],
            "entry_underlying": entry_price,
            "stop_underlying": stop_price,
            "orb_high": drive_high,
            "orb_low": drive_low,
            "opening_bar_open": drive_open,
            "opening_bar_close": drive_close,
            "opening_bar_direction": drive_direction,
            "trend_ema_fast": ema_now,
            "trend_ema_slow": ema_slow[idx],
            "volume_ratio": volume_ratio,
            "relative_opening_volume": relative_opening_volume,
            "atr_value": atr_value,
            "fvg_gap": 0.0,
            "opening_range_minutes": drive_count,
            "orb_width_pct": drive_range_pct,
            "strategy_variant": "opening_drive_pullback_v1",
            "drive_abs_return_pct": drive_abs_return_pct,
            "drive_close_location": drive_close_location,
            "drive_pullback_retrace_frac": retrace_frac,
            "drive_reclaim_close_location": reclaim_location,
            "drive_pullback_require_hold_drive_open": require_hold_drive_open,
            "drive_reclaim_requires_prev_extreme_break": require_prev_extreme_break,
            "drive_vwap_at_signal": vwap_now,
            "drive_ema_fast_at_signal": ema_now,
        }
        break

    if setup is None and int(audit.get("opportunities_before_filters") or 0) == 0:
        _inc_reason(audit["rejections"], "no_drive_pullback_candidate")
    return setup, audit


def _find_opening_exhaustion_reversal_setup_with_audit(
    session_bars: List[Dict[str, Any]],
    cfg: IntradayStrategyConfig,
    relative_opening_volume: Optional[float],
    atr_value: Optional[float],
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    audit: Dict[str, Any] = {
        "strategy_variant": "opening_exhaustion_reversal_v1",
        "opportunities_before_filters": 0,
        "opportunities_after_filters": 0,
        "rejections": {},
    }
    drive_count = max(int(cfg.opening_range_minutes), 1)
    if len(session_bars) < (drive_count + 3):
        _inc_reason(audit["rejections"], "insufficient_bars")
        return None, audit

    drive_window = session_bars[:drive_count]
    drive_high = max(float(bar.get("high") or 0.0) for bar in drive_window)
    drive_low = min(float(bar.get("low") or 0.0) for bar in drive_window)
    drive_open = float(drive_window[0].get("open") or 0.0)
    drive_close = float(drive_window[-1].get("close") or 0.0)
    if drive_high <= 0 or drive_low <= 0 or drive_high <= drive_low or drive_open <= 0 or drive_close <= 0:
        _inc_reason(audit["rejections"], "invalid_opening_drive")
        return None, audit

    drive_range = drive_high - drive_low
    drive_range_pct = drive_range / max(drive_open, 1.0)
    if cfg.require_or_width_filter:
        min_width = max(float(cfg.opening_range_min_width_pct), 0.0)
        max_width = max(float(cfg.opening_range_max_width_pct), min_width)
        if drive_range_pct < min_width or drive_range_pct > max_width:
            _inc_reason(audit["rejections"], "drive_width_filter")
            return None, audit

    drive_direction = 1 if drive_close > drive_open else (-1 if drive_close < drive_open else 0)
    if drive_direction == 0:
        _inc_reason(audit["rejections"], "flat_opening_drive")
        return None, audit
    gap_abs_return = abs(float(getattr(cfg, "event_gap_abs_return", 0.0)))
    min_gap_abs_return = max(float(getattr(cfg, "event_drive_min_gap_abs_return", 0.0)), 0.0)
    if gap_abs_return < min_gap_abs_return:
        _inc_reason(audit["rejections"], "event_gap_too_small")
        return None, audit
    gap_direction = int(getattr(cfg, "event_gap_direction", 0))
    if min_gap_abs_return > 0.0:
        if gap_direction not in (-1, 1):
            _inc_reason(audit["rejections"], "event_gap_direction_unknown")
            return None, audit
        if drive_direction != gap_direction:
            _inc_reason(audit["rejections"], "gap_drive_direction_mismatch")
            return None, audit
    reversal_direction = -drive_direction
    if reversal_direction > 0 and not cfg.allow_long:
        _inc_reason(audit["rejections"], "direction_not_allowed")
        return None, audit
    if reversal_direction < 0 and not cfg.allow_short:
        _inc_reason(audit["rejections"], "direction_not_allowed")
        return None, audit

    drive_abs_return_pct = abs(drive_close - drive_open) / max(drive_open, 1.0)
    if drive_abs_return_pct < max(float(getattr(cfg, "drive_min_abs_return_pct", 0.0)), 0.0):
        _inc_reason(audit["rejections"], "drive_abs_return_filter")
        return None, audit

    drive_close_location = _close_location_fraction(
        direction=drive_direction,
        high_price=drive_high,
        low_price=drive_low,
        close_price=drive_close,
    )
    if drive_close_location < max(0.0, min(1.0, float(getattr(cfg, "drive_close_location_min", 0.0)))):
        _inc_reason(audit["rejections"], "drive_close_location_filter")
        return None, audit

    relative_volume_rejection = _relative_volume_rejection_reason(cfg, relative_opening_volume)
    if relative_volume_rejection is not None:
        _inc_reason(audit["rejections"], relative_volume_rejection)
        return None, audit
    if cfg.require_atr_filter:
        if atr_value is None or atr_value < cfg.atr_min:
            _inc_reason(audit["rejections"], "atr_filter")
            return None, audit

    closes = [float(bar.get("close") or 0.0) for bar in session_bars]
    ema_fast = _ema_series(closes, cfg.trend_ema_fast)
    ema_slow = _ema_series(closes, cfg.trend_ema_slow)
    vwap_series = _running_vwap_series(session_bars)
    drive_end_idx = drive_count - 1
    drive_vwap = float(vwap_series[drive_end_idx]) if drive_end_idx < len(vwap_series) else 0.0
    drive_ema = float(ema_fast[drive_end_idx]) if drive_end_idx < len(ema_fast) else 0.0
    if drive_vwap <= 0 or drive_ema <= 0:
        _inc_reason(audit["rejections"], "drive_ma_unavailable")
        return None, audit

    drive_value_ref = max(drive_vwap, drive_ema) if drive_direction > 0 else min(drive_vwap, drive_ema)
    drive_extension_pct = abs(drive_close - drive_value_ref) / max(drive_open, 1.0)
    extension_min_pct = max(float(getattr(cfg, "drive_touch_ma_buffer_pct", 0.0)), 0.0)
    if drive_extension_pct < extension_min_pct:
        _inc_reason(audit["rejections"], "drive_extension_filter")
        return None, audit

    drive_move = abs(drive_close - drive_open)
    drive_mid = (drive_open + drive_close) / 2.0
    min_retrace_frac = max(float(getattr(cfg, "drive_pullback_min_retrace_frac", 0.0)), 0.0)
    max_retrace_frac = max(float(getattr(cfg, "drive_pullback_max_retrace_frac", 0.0)), min_retrace_frac)
    reversal_close_location_min = max(
        0.0,
        min(1.0, float(getattr(cfg, "drive_reclaim_close_location_min", 0.0))),
    )
    max_reversal_bars = max(int(getattr(cfg, "drive_max_pullback_bars", 1)), 1)
    stop_buffer_range_frac = max(float(getattr(cfg, "drive_stop_buffer_range_frac", 0.0)), 0.0)
    entry_start = _parse_hhmm(cfg.entry_start_time, _default_entry_start(drive_count))
    entry_cutoff = _parse_hhmm(cfg.entry_cutoff_time, "11:30")

    setup: Optional[Dict[str, Any]] = None
    for idx in range(drive_count, len(session_bars) - 1):
        bar = session_bars[idx]
        bar_time = _to_et_time(bar["ts"])
        if bar_time < entry_start or bar_time > entry_cutoff:
            continue
        if (idx - drive_end_idx) > max_reversal_bars:
            _inc_reason(audit["rejections"], "reversal_timeout")
            break

        open_price = float(bar.get("open") or 0.0)
        high_price = float(bar.get("high") or 0.0)
        low_price = float(bar.get("low") or 0.0)
        close_price = float(bar.get("close") or 0.0)
        if open_price <= 0 or high_price <= 0 or low_price <= 0 or close_price <= 0:
            continue
        vwap_now = float(vwap_series[idx]) if idx < len(vwap_series) else 0.0
        ema_now = float(ema_fast[idx]) if idx < len(ema_fast) else 0.0
        if vwap_now <= 0 or ema_now <= 0:
            _inc_reason(audit["rejections"], "reversal_ma_unavailable")
            continue

        audit["opportunities_before_filters"] = int(audit.get("opportunities_before_filters") or 0) + 1
        if drive_direction > 0:
            retrace_frac = max(drive_close - close_price, 0.0) / max(drive_move, 1e-9)
            value_cross = close_price < min(vwap_now, ema_now, drive_mid)
            reversal_close_location = _close_location_fraction(
                direction=-1,
                high_price=high_price,
                low_price=low_price,
                close_price=close_price,
            )
            stop_price = max(drive_high, high_price) + (drive_range * stop_buffer_range_frac)
        else:
            retrace_frac = max(close_price - drive_close, 0.0) / max(drive_move, 1e-9)
            value_cross = close_price > max(vwap_now, ema_now, drive_mid)
            reversal_close_location = _close_location_fraction(
                direction=1,
                high_price=high_price,
                low_price=low_price,
                close_price=close_price,
            )
            stop_price = min(drive_low, low_price) - (drive_range * stop_buffer_range_frac)

        if retrace_frac < min_retrace_frac:
            _inc_reason(audit["rejections"], "reversal_too_shallow")
            continue
        if retrace_frac > max_retrace_frac:
            _inc_reason(audit["rejections"], "reversal_too_deep")
            continue
        if reversal_close_location < reversal_close_location_min:
            _inc_reason(audit["rejections"], "reversal_close_location")
            continue
        if not value_cross:
            _inc_reason(audit["rejections"], "reversal_value_cross")
            continue

        entry_idx, entry_bar, entry_price = _next_bar_open_entry(session_bars, signal_idx=idx)
        if entry_idx is None or entry_bar is None or entry_price <= 0:
            _inc_reason(audit["rejections"], "invalid_entry_price")
            continue
        if reversal_direction > 0 and stop_price >= entry_price:
            _inc_reason(audit["rejections"], "invalid_stop")
            continue
        if reversal_direction < 0 and stop_price <= entry_price:
            _inc_reason(audit["rejections"], "invalid_stop")
            continue

        audit["opportunities_after_filters"] = int(audit.get("opportunities_after_filters") or 0) + 1
        setup = {
            "direction": reversal_direction,
            "signal_idx": idx,
            "signal_ts": bar["ts"],
            "entry_idx": entry_idx,
            "entry_ts": entry_bar["ts"],
            "entry_underlying": entry_price,
            "stop_underlying": stop_price,
            "orb_high": drive_high,
            "orb_low": drive_low,
            "opening_bar_open": drive_open,
            "opening_bar_close": drive_close,
            "opening_bar_direction": drive_direction,
            "trend_ema_fast": ema_now,
            "trend_ema_slow": ema_slow[idx],
            "volume_ratio": 1.0,
            "relative_opening_volume": relative_opening_volume,
            "atr_value": atr_value,
            "fvg_gap": 0.0,
            "opening_range_minutes": drive_count,
            "orb_width_pct": drive_range_pct,
            "strategy_variant": "opening_exhaustion_reversal_v1",
            "drive_abs_return_pct": drive_abs_return_pct,
            "drive_close_location": drive_close_location,
            "drive_extension_pct": drive_extension_pct,
            "reversal_retrace_frac": retrace_frac,
            "reversal_close_location": reversal_close_location,
            "drive_vwap_at_signal": vwap_now,
            "drive_ema_fast_at_signal": ema_now,
            "event_gap_abs_return": gap_abs_return,
            "event_gap_direction": gap_direction if gap_direction in (-1, 1) else drive_direction,
        }
        break

    if setup is None and int(audit.get("opportunities_before_filters") or 0) == 0:
        _inc_reason(audit["rejections"], "no_exhaustion_reversal_candidate")
    return setup, audit


def _find_orb_event_drive_setup_with_audit(
    session_bars: List[Dict[str, Any]],
    cfg: IntradayStrategyConfig,
    relative_opening_volume: Optional[float],
    atr_value: Optional[float],
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    audit: Dict[str, Any] = {
        "strategy_variant": "orb_event_drive_v1",
        "opportunities_before_filters": 0,
        "opportunities_after_filters": 0,
        "rejections": {},
    }
    opening_range_count = max(int(cfg.opening_range_minutes), 1)
    if len(session_bars) < (opening_range_count + 3):
        _inc_reason(audit["rejections"], "insufficient_bars")
        return None, audit

    opening_range = session_bars[:opening_range_count]
    orb_high = max(float(bar.get("high") or 0.0) for bar in opening_range)
    orb_low = min(float(bar.get("low") or 0.0) for bar in opening_range)
    orb_open = float(opening_range[0].get("open") or 0.0)
    orb_close = float(opening_range[-1].get("close") or 0.0)
    if orb_high <= 0 or orb_low <= 0 or orb_high <= orb_low:
        _inc_reason(audit["rejections"], "invalid_opening_range")
        return None, audit
    orb_width = orb_high - orb_low
    orb_width_pct = orb_width / max(orb_open, 1.0)

    gap_abs_return = abs(float(getattr(cfg, "event_gap_abs_return", 0.0)))
    if gap_abs_return < max(float(getattr(cfg, "event_drive_min_gap_abs_return", 0.0)), 0.0):
        _inc_reason(audit["rejections"], "event_gap_too_small")
        return None, audit

    closes = [float(bar.get("close") or 0.0) for bar in session_bars]
    ema_fast = _ema_series(closes, cfg.trend_ema_fast)
    ema_slow = _ema_series(closes, cfg.trend_ema_slow)
    opening_bar_direction = 1 if orb_close > orb_open else (-1 if orb_close < orb_open else 0)

    preferred_direction = int(getattr(cfg, "event_gap_direction", 0))
    if preferred_direction not in (-1, 1):
        preferred_direction = opening_bar_direction
    if preferred_direction not in (-1, 1):
        _inc_reason(audit["rejections"], "event_direction_unknown")
        return None, audit
    if preferred_direction > 0 and not cfg.allow_long:
        _inc_reason(audit["rejections"], "direction_not_allowed")
        return None, audit
    if preferred_direction < 0 and not cfg.allow_short:
        _inc_reason(audit["rejections"], "direction_not_allowed")
        return None, audit

    entry_start = _parse_hhmm(cfg.entry_start_time, _default_entry_start(opening_range_count))
    entry_cutoff = _parse_hhmm(cfg.entry_cutoff_time, "12:00")
    trigger_mode = str(cfg.entry_trigger_mode or "close_breakout").strip().lower()
    min_breakout_or_frac = max(float(getattr(cfg, "event_drive_min_breakout_or_frac", 0.0)), 0.0)
    min_close_location = max(0.0, min(1.0, float(getattr(cfg, "event_drive_close_location_min", 0.0))))
    min_volume_multiple = max(float(getattr(cfg, "event_drive_min_volume_multiple", 0.0)), 0.0)

    setup: Optional[Dict[str, Any]] = None
    for idx in range(opening_range_count, len(session_bars) - 1):
        bar = session_bars[idx]
        bar_time = _to_et_time(bar["ts"])
        if bar_time < entry_start or bar_time > entry_cutoff:
            continue
        open_price = float(bar.get("open") or 0.0)
        high_price = float(bar.get("high") or 0.0)
        low_price = float(bar.get("low") or 0.0)
        close_price = float(bar.get("close") or 0.0)
        if open_price <= 0 or high_price <= 0 or low_price <= 0 or close_price <= 0:
            continue

        if trigger_mode == "stop_touch":
            breakout = high_price >= orb_high if preferred_direction > 0 else low_price <= orb_low
            breakout_distance = (high_price - orb_high) if preferred_direction > 0 else (orb_low - low_price)
        else:
            breakout = close_price > orb_high if preferred_direction > 0 else close_price < orb_low
            breakout_distance = (close_price - orb_high) if preferred_direction > 0 else (orb_low - close_price)
        if not breakout:
            continue
        audit["opportunities_before_filters"] = int(audit.get("opportunities_before_filters") or 0) + 1

        relative_volume_rejection = _relative_volume_rejection_reason(cfg, relative_opening_volume)
        if relative_volume_rejection is not None:
            _inc_reason(audit["rejections"], relative_volume_rejection)
            continue
        if cfg.require_atr_filter:
            if atr_value is None or atr_value < cfg.atr_min:
                _inc_reason(audit["rejections"], "atr_filter")
                continue
        if preferred_direction > 0 and not (ema_fast[idx] > ema_slow[idx]):
            _inc_reason(audit["rejections"], "trend_alignment_filter")
            continue
        if preferred_direction < 0 and not (ema_fast[idx] < ema_slow[idx]):
            _inc_reason(audit["rejections"], "trend_alignment_filter")
            continue
        if breakout_distance <= 0:
            _inc_reason(audit["rejections"], "event_drive_breakout_distance")
            continue
        breakout_or_frac = breakout_distance / max(orb_width, 1e-9)
        if breakout_or_frac < min_breakout_or_frac:
            _inc_reason(audit["rejections"], "event_drive_breakout_strength")
            continue
        close_location = _close_location_fraction(
            direction=preferred_direction,
            high_price=high_price,
            low_price=low_price,
            close_price=close_price,
        )
        if close_location < min_close_location:
            _inc_reason(audit["rejections"], "event_drive_close_location")
            continue
        volume_ratio = _bar_volume_ratio(session_bars, idx, cfg.volume_ma_window)
        if volume_ratio is None:
            _inc_reason(audit["rejections"], "volume_ma_warmup")
            continue
        if volume_ratio < min_volume_multiple:
            _inc_reason(audit["rejections"], "event_drive_volume_filter")
            continue

        entry_idx, entry_bar, entry_price = _next_bar_open_entry(session_bars, signal_idx=idx)
        if entry_idx is None or entry_bar is None or entry_price <= 0:
            _inc_reason(audit["rejections"], "invalid_entry_price")
            continue

        stop_price = _compute_stop_price(
            cfg=cfg,
            direction=preferred_direction,
            orb_high=orb_high,
            orb_low=orb_low,
            breakout_high=high_price,
            breakout_low=low_price,
            entry_price=entry_price,
            atr_value=atr_value,
        )
        if stop_price is None:
            _inc_reason(audit["rejections"], "invalid_stop")
            continue

        audit["opportunities_after_filters"] = int(audit.get("opportunities_after_filters") or 0) + 1
        setup = {
            "direction": preferred_direction,
            "signal_idx": idx,
            "signal_ts": bar["ts"],
            "entry_idx": entry_idx,
            "entry_ts": entry_bar["ts"],
            "entry_underlying": entry_price,
            "stop_underlying": stop_price,
            "orb_high": orb_high,
            "orb_low": orb_low,
            "opening_bar_open": orb_open,
            "opening_bar_close": orb_close,
            "opening_bar_direction": opening_bar_direction,
            "trend_ema_fast": ema_fast[idx],
            "trend_ema_slow": ema_slow[idx],
            "volume_ratio": volume_ratio,
            "relative_opening_volume": relative_opening_volume,
            "atr_value": atr_value,
            "fvg_gap": 0.0,
            "opening_range_minutes": opening_range_count,
            "orb_width_pct": orb_width_pct,
            "strategy_variant": "orb_event_drive_v1",
            "event_gap_abs_return": gap_abs_return,
            "event_gap_direction": preferred_direction,
            "event_drive_breakout_or_frac": breakout_or_frac,
        }
        break

    if setup is None and int(audit.get("opportunities_before_filters") or 0) == 0:
        _inc_reason(audit["rejections"], "no_breakout_detected")
    return setup, audit


def _find_orb_transition_compression_setup_with_audit(
    session_bars: List[Dict[str, Any]],
    cfg: IntradayStrategyConfig,
    relative_opening_volume: Optional[float],
    atr_value: Optional[float],
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    audit: Dict[str, Any] = {
        "strategy_variant": "orb_transition_compression_v1",
        "opportunities_before_filters": 0,
        "opportunities_after_filters": 0,
        "rejections": {},
    }
    opening_range_count = max(int(cfg.opening_range_minutes), 1)
    lookback_bars = max(int(getattr(cfg, "compression_lookback_bars", 2)), 2)
    if len(session_bars) < (opening_range_count + lookback_bars + 2):
        _inc_reason(audit["rejections"], "insufficient_bars")
        return None, audit

    opening_range = session_bars[:opening_range_count]
    orb_high = max(float(bar.get("high") or 0.0) for bar in opening_range)
    orb_low = min(float(bar.get("low") or 0.0) for bar in opening_range)
    orb_open = float(opening_range[0].get("open") or 0.0)
    orb_close = float(opening_range[-1].get("close") or 0.0)
    if orb_high <= 0 or orb_low <= 0 or orb_high <= orb_low:
        _inc_reason(audit["rejections"], "invalid_opening_range")
        return None, audit
    orb_width = orb_high - orb_low
    orb_width_pct = orb_width / max(orb_open, 1.0)

    closes = [float(bar.get("close") or 0.0) for bar in session_bars]
    ema_fast = _ema_series(closes, cfg.trend_ema_fast)
    ema_slow = _ema_series(closes, cfg.trend_ema_slow)
    opening_bar_direction = 1 if orb_close > orb_open else (-1 if orb_close < orb_open else 0)

    entry_start = _parse_hhmm(cfg.entry_start_time, _default_entry_start(opening_range_count))
    entry_cutoff = _parse_hhmm(cfg.entry_cutoff_time, "12:00")
    max_range_pct = max(float(getattr(cfg, "compression_max_range_pct", 0.0)), 0.0)
    breakout_buffer_frac = max(float(getattr(cfg, "compression_breakout_buffer_or_frac", 0.0)), 0.0)
    min_volume_multiple = max(float(getattr(cfg, "compression_min_volume_multiple", 0.0)), 0.0)

    setup: Optional[Dict[str, Any]] = None
    for idx in range(opening_range_count + lookback_bars, len(session_bars) - 1):
        bar = session_bars[idx]
        bar_time = _to_et_time(bar["ts"])
        if bar_time < entry_start or bar_time > entry_cutoff:
            continue

        prev_window = session_bars[idx - lookback_bars : idx]
        win_high = max(float(row.get("high") or 0.0) for row in prev_window)
        win_low = min(float(row.get("low") or 0.0) for row in prev_window)
        close_price = float(bar.get("close") or 0.0)
        open_price = float(bar.get("open") or 0.0)
        high_price = float(bar.get("high") or 0.0)
        low_price = float(bar.get("low") or 0.0)
        if close_price <= 0 or open_price <= 0 or high_price <= 0 or low_price <= 0:
            continue

        window_range_pct = (win_high - win_low) / max(close_price, 1.0)
        if window_range_pct > max_range_pct:
            _inc_reason(audit["rejections"], "compression_range_too_wide")
            continue

        long_breakout = close_price > (win_high + (orb_width * breakout_buffer_frac))
        short_breakout = close_price < (win_low - (orb_width * breakout_buffer_frac))
        raw_directions: List[int] = []
        if long_breakout:
            raw_directions.append(1)
        if short_breakout:
            raw_directions.append(-1)
        if not raw_directions:
            continue
        audit["opportunities_before_filters"] = int(audit.get("opportunities_before_filters") or 0) + len(
            raw_directions
        )

        direction = 0
        for candidate in raw_directions:
            if candidate > 0 and not cfg.allow_long:
                _inc_reason(audit["rejections"], "direction_not_allowed")
                continue
            if candidate < 0 and not cfg.allow_short:
                _inc_reason(audit["rejections"], "direction_not_allowed")
                continue
            if cfg.use_opening_bar_direction and candidate != opening_bar_direction:
                _inc_reason(audit["rejections"], "opening_bar_direction_mismatch")
                continue
            relative_volume_rejection = _relative_volume_rejection_reason(cfg, relative_opening_volume)
            if relative_volume_rejection is not None:
                _inc_reason(audit["rejections"], relative_volume_rejection)
                continue
            if cfg.require_atr_filter:
                if atr_value is None or atr_value < cfg.atr_min:
                    _inc_reason(audit["rejections"], "atr_filter")
                    continue
            volume_ratio = _bar_volume_ratio(session_bars, idx, cfg.volume_ma_window)
            if volume_ratio is None:
                _inc_reason(audit["rejections"], "volume_ma_warmup")
                continue
            if volume_ratio < min_volume_multiple:
                _inc_reason(audit["rejections"], "compression_volume_filter")
                continue
            direction = candidate
            break
        if direction == 0:
            continue

        entry_idx = idx + 1
        entry_bar = session_bars[entry_idx]
        entry_price = float(entry_bar.get("open") or 0.0)
        if entry_price <= 0:
            _inc_reason(audit["rejections"], "invalid_entry_price")
            continue
        stop_price = _compute_stop_price(
            cfg=cfg,
            direction=direction,
            orb_high=orb_high,
            orb_low=orb_low,
            breakout_high=high_price,
            breakout_low=low_price,
            entry_price=entry_price,
            atr_value=atr_value,
        )
        if stop_price is None:
            _inc_reason(audit["rejections"], "invalid_stop")
            continue

        audit["opportunities_after_filters"] = int(audit.get("opportunities_after_filters") or 0) + 1
        setup = {
            "direction": direction,
            "signal_idx": idx,
            "signal_ts": bar["ts"],
            "entry_idx": entry_idx,
            "entry_ts": entry_bar["ts"],
            "entry_underlying": entry_price,
            "stop_underlying": stop_price,
            "orb_high": orb_high,
            "orb_low": orb_low,
            "opening_bar_open": orb_open,
            "opening_bar_close": orb_close,
            "opening_bar_direction": opening_bar_direction,
            "trend_ema_fast": ema_fast[idx],
            "trend_ema_slow": ema_slow[idx],
            "volume_ratio": _bar_volume_ratio(session_bars, idx, cfg.volume_ma_window) or 0.0,
            "relative_opening_volume": relative_opening_volume,
            "atr_value": atr_value,
            "fvg_gap": 0.0,
            "opening_range_minutes": opening_range_count,
            "orb_width_pct": orb_width_pct,
            "strategy_variant": "orb_transition_compression_v1",
            "compression_window_range_pct": window_range_pct,
            "compression_lookback_bars": lookback_bars,
        }
        break

    if setup is None and int(audit.get("opportunities_before_filters") or 0) == 0:
        _inc_reason(audit["rejections"], "no_compression_breakout")
    return setup, audit


def _find_mr_overnight_regime_setup_with_audit(
    session_bars: List[Dict[str, Any]],
    cfg: IntradayStrategyConfig,
    relative_opening_volume: Optional[float],
    atr_value: Optional[float],
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    audit: Dict[str, Any] = {
        "strategy_variant": "mr_overnight_regime_v1",
        "opportunities_before_filters": 0,
        "opportunities_after_filters": 0,
        "rejections": {},
    }
    if len(session_bars) < 20:
        _inc_reason(audit["rejections"], "insufficient_bars")
        return None, audit

    entry_start = _parse_hhmm(cfg.entry_start_time, "15:50")
    entry_cutoff = _parse_hhmm(cfg.entry_cutoff_time, "15:59")
    if entry_cutoff < entry_start:
        entry_cutoff = entry_start

    entry_idx: Optional[int] = None
    for idx, bar in enumerate(session_bars):
        bar_time = _to_et_time(bar["ts"])
        if bar_time < entry_start:
            continue
        if bar_time > entry_cutoff:
            break
        open_price = float(bar.get("open") or 0.0)
        high_price = float(bar.get("high") or 0.0)
        low_price = float(bar.get("low") or 0.0)
        close_price = float(bar.get("close") or 0.0)
        if open_price <= 0 or high_price <= 0 or low_price <= 0 or close_price <= 0:
            continue
        entry_idx = idx
        break
    if entry_idx is None:
        _inc_reason(audit["rejections"], "overnight_entry_window_miss")
        return None, audit

    bars_until_entry = session_bars[:entry_idx]
    if not bars_until_entry:
        _inc_reason(audit["rejections"], "overnight_signal_window_empty")
        return None, audit
    session_open = float(bars_until_entry[0].get("open") or 0.0)
    if session_open <= 0:
        _inc_reason(audit["rejections"], "invalid_session_open")
        return None, audit

    highs = [float(row.get("high") or 0.0) for row in bars_until_entry]
    lows = [float(row.get("low") or 0.0) for row in bars_until_entry]
    closes = [float(row.get("close") or 0.0) for row in bars_until_entry]
    if not highs or not lows or not closes:
        _inc_reason(audit["rejections"], "invalid_session_state")
        return None, audit
    session_high = max(highs)
    session_low = min(lows)
    if session_high <= session_low:
        _inc_reason(audit["rejections"], "invalid_session_range")
        return None, audit

    session_range = session_high - session_low
    session_range_pct = session_range / max(session_open, 1.0)
    min_range_pct = max(float(getattr(cfg, "mr_overnight_min_session_range_pct", 0.0)), 0.0)
    if session_range_pct < min_range_pct:
        _inc_reason(audit["rejections"], "overnight_range_too_small")
        return None, audit

    session_close = closes[-1]
    if session_close <= 0:
        _inc_reason(audit["rejections"], "invalid_session_close")
        return None, audit

    path_move = sum(abs(closes[idx] - closes[idx - 1]) for idx in range(1, len(closes)))
    efficiency_ratio = (abs(session_close - session_open) / path_move) if path_move > 0 else 1.0
    max_efficiency_ratio = max(float(getattr(cfg, "mr_overnight_efficiency_ratio_max", 1.0)), 0.0)
    if efficiency_ratio > max_efficiency_ratio:
        _inc_reason(audit["rejections"], "overnight_trending_filter")
        return None, audit

    day_return = (session_close / session_open) - 1.0
    close_location = (session_close - session_low) / max(session_range, 1e-9)
    return_threshold = max(float(getattr(cfg, "mr_overnight_abs_return_min", 0.0)), 0.0)
    range_extreme_pct = min(max(float(getattr(cfg, "mr_overnight_close_to_range_extreme_pct", 0.2)), 0.01), 0.49)

    long_score = max(
        (-day_return) - return_threshold,
        ((range_extreme_pct - close_location) / range_extreme_pct) if close_location <= range_extreme_pct else 0.0,
    )
    short_score = max(
        day_return - return_threshold,
        (
            (close_location - (1.0 - range_extreme_pct)) / range_extreme_pct
            if close_location >= (1.0 - range_extreme_pct)
            else 0.0
        ),
    )
    raw_directions: List[int] = []
    if long_score > 0:
        raw_directions.append(1)
    if short_score > 0:
        raw_directions.append(-1)
    if not raw_directions:
        _inc_reason(audit["rejections"], "overnight_no_signal")
        return None, audit

    audit["opportunities_before_filters"] = int(audit.get("opportunities_before_filters") or 0) + len(raw_directions)

    candidate_directions: List[int] = []
    for direction in raw_directions:
        if direction > 0 and bool(cfg.allow_long):
            candidate_directions.append(direction)
        elif direction < 0 and bool(cfg.allow_short):
            candidate_directions.append(direction)
        else:
            _inc_reason(audit["rejections"], "direction_not_allowed")
    if not candidate_directions:
        return None, audit

    if len(candidate_directions) > 1:
        direction = 1 if long_score >= short_score else -1
        _inc_reason(audit["rejections"], "secondary_direction_dropped")
    else:
        direction = candidate_directions[0]

    signal_idx = entry_idx - 1
    signal_bar = bars_until_entry[-1]
    entry_bar = session_bars[entry_idx]
    entry_price = float(entry_bar.get("open") or 0.0)
    if entry_price <= 0:
        _inc_reason(audit["rejections"], "invalid_entry_price")
        return None, audit

    base_stop_buffer = max(session_range * max(float(cfg.mr_stop_buffer_or_mult), 0.0), entry_price * 0.0025)
    atr_buffer = max(float(atr_value or 0.0) * 0.25, 0.0)
    stop_buffer = max(base_stop_buffer, atr_buffer)
    if direction > 0:
        stop_price = min(session_low, entry_price - stop_buffer)
        if stop_price >= entry_price:
            _inc_reason(audit["rejections"], "invalid_stop")
            return None, audit
    else:
        stop_price = max(session_high, entry_price + stop_buffer)
        if stop_price <= entry_price:
            _inc_reason(audit["rejections"], "invalid_stop")
            return None, audit

    audit["opportunities_after_filters"] = int(audit.get("opportunities_after_filters") or 0) + 1
    return (
        {
            "direction": direction,
            "signal_idx": signal_idx,
            "signal_ts": signal_bar["ts"],
            "entry_idx": entry_idx,
            "entry_ts": entry_bar["ts"],
            "entry_underlying": entry_price,
            "stop_underlying": stop_price,
            "orb_high": session_high,
            "orb_low": session_low,
            "opening_bar_open": session_open,
            "opening_bar_close": closes[min(len(closes) - 1, max(int(cfg.opening_range_minutes) - 1, 0))],
            "opening_bar_direction": 0,
            "trend_ema_fast": session_close,
            "trend_ema_slow": session_open,
            "volume_ratio": 1.0,
            "relative_opening_volume": relative_opening_volume,
            "atr_value": atr_value,
            "fvg_gap": 0.0,
            "opening_range_minutes": int(cfg.opening_range_minutes),
            "orb_width_pct": session_range_pct,
            "strategy_variant": "mr_overnight_regime_v1",
            "overnight_exit_day_offset": 1,
            "overnight_exit_time": str(cfg.exit_time or "09:31"),
            "mr_overnight_day_return": day_return,
            "mr_overnight_close_location": close_location,
            "mr_overnight_efficiency_ratio": efficiency_ratio,
        },
        audit,
    )


def _find_orb_fib_pullback_setup(
    session_bars: List[Dict[str, Any]],
    cfg: IntradayStrategyConfig,
    opening_range_count: int,
    orb_high: float,
    orb_low: float,
    orb_open: float,
    orb_close: float,
    orb_width_pct: float,
    opening_bar_direction: int,
    ema_fast: List[float],
    ema_slow: List[float],
    relative_opening_volume: Optional[float],
    atr_value: Optional[float],
) -> Optional[Dict[str, Any]]:
    entry_start = _parse_hhmm(cfg.entry_start_time, _default_entry_start(opening_range_count))
    entry_cutoff = _parse_hhmm(cfg.entry_cutoff_time, "12:00")
    trigger_mode = str(cfg.entry_trigger_mode or "close_breakout").strip().lower()
    macro_release_times = (
        _parse_hhmm_list(cfg.macro_release_times_et, "10:00")
        if cfg.require_macro_release_filter
        else []
    )
    macro_block_minutes = max(int(cfg.macro_post_release_block_minutes), 0)

    fib_low_ratio = max(min(float(cfg.fib_entry_level_low), 0.99), 0.01)
    fib_high_ratio = max(min(float(cfg.fib_entry_level_high), 0.99), 0.01)
    if fib_low_ratio > fib_high_ratio:
        fib_low_ratio, fib_high_ratio = fib_high_ratio, fib_low_ratio

    breakout_direction = 0
    breakout_volume_ratio = 1.0
    impulse_extreme: Optional[float] = None
    pullback_extreme: Optional[float] = None

    for idx in range(opening_range_count, len(session_bars) - 1):
        bar = session_bars[idx]
        bar_time = _to_et_time(bar["ts"])
        if bar_time < entry_start or bar_time > entry_cutoff:
            continue
        if cfg.require_macro_release_filter and _is_in_macro_release_block(
            bar_time,
            macro_release_times,
            macro_block_minutes,
        ):
            continue

        current_open = float(bar.get("open") or 0.0)
        current_high = float(bar.get("high") or 0.0)
        current_low = float(bar.get("low") or 0.0)
        current_close = float(bar.get("close") or 0.0)
        if current_open <= 0 or current_high <= 0 or current_low <= 0 or current_close <= 0:
            continue

        if breakout_direction == 0:
            if trigger_mode == "stop_touch":
                long_breakout = current_high >= orb_high
                short_breakout = current_low <= orb_low
            else:
                long_breakout = current_close > orb_high
                short_breakout = current_close < orb_low

            if cfg.require_breakout_open_inside_range and not (orb_low <= current_open <= orb_high):
                long_breakout = False
                short_breakout = False

            candidate_directions: List[int] = []
            if long_breakout and cfg.allow_long:
                candidate_directions.append(1)
            if short_breakout and cfg.allow_short:
                candidate_directions.append(-1)
            if not candidate_directions:
                continue

            if cfg.use_opening_bar_direction:
                candidate_directions = [d for d in candidate_directions if d == opening_bar_direction]
                if not candidate_directions:
                    continue

            relative_volume_rejection = _relative_volume_rejection_reason(cfg, relative_opening_volume)
            if relative_volume_rejection is not None:
                _inc_reason(audit["rejections"], relative_volume_rejection)
                continue

            if cfg.require_atr_filter:
                if atr_value is None or atr_value < cfg.atr_min:
                    continue

            if cfg.require_volume_spike:
                if idx < cfg.volume_ma_window:
                    continue
                lookback = session_bars[idx - cfg.volume_ma_window : idx]
                avg_volume = _mean_fast(float(row.get("volume") or 0.0) for row in lookback)
                if avg_volume <= 0:
                    continue
                volume_ratio = float(bar.get("volume") or 0.0) / avg_volume
                if volume_ratio < cfg.volume_spike_multiple:
                    continue
            else:
                volume_ratio = 1.0

            direction = candidate_directions[0]
            if cfg.require_trend_alignment:
                if direction > 0 and not (ema_fast[idx] > ema_slow[idx]):
                    continue
                if direction < 0 and not (ema_fast[idx] < ema_slow[idx]):
                    continue

            prev2 = session_bars[idx - 2]
            prev2_high = float(prev2.get("high") or 0.0)
            prev2_low = float(prev2.get("low") or 0.0)
            if cfg.require_fvg:
                if direction > 0 and not (prev2_high < current_low):
                    continue
                if direction < 0 and not (prev2_low > current_high):
                    continue

            breakout_direction = direction
            breakout_volume_ratio = volume_ratio
            if direction > 0:
                impulse_extreme = current_high
                pullback_extreme = current_low
            else:
                impulse_extreme = current_low
                pullback_extreme = current_high
            continue

        direction = breakout_direction
        if direction > 0:
            assert impulse_extreme is not None and pullback_extreme is not None
            impulse_extreme = max(impulse_extreme, current_high)
            pullback_extreme = min(pullback_extreme, current_low)
            impulse = impulse_extreme - orb_low
            if impulse <= 0:
                continue
            zone_low = orb_low + (impulse * fib_low_ratio)
            zone_high = orb_low + (impulse * fib_high_ratio)
            if not (current_low <= zone_high and current_high >= zone_low):
                continue
            if cfg.fib_require_confirmation:
                if not (current_close > current_open and current_close >= zone_high):
                    continue
            elif current_close < zone_low:
                continue
            entry_idx = idx + 1
            entry_bar = session_bars[entry_idx]
            entry_price = float(entry_bar.get("open") or 0.0)
            if entry_price <= 0:
                continue
            stop_price = pullback_extreme
            if stop_price >= entry_price:
                continue
            prev2 = session_bars[idx - 2]
            prev2_high = float(prev2.get("high") or 0.0)
            prev2_low = float(prev2.get("low") or 0.0)
            return {
                "direction": direction,
                "signal_idx": idx,
                "signal_ts": bar["ts"],
                "entry_idx": entry_idx,
                "entry_ts": entry_bar["ts"],
                "entry_underlying": entry_price,
                "stop_underlying": stop_price,
                "orb_high": orb_high,
                "orb_low": orb_low,
                "opening_bar_open": orb_open,
                "opening_bar_close": orb_close,
                "opening_bar_direction": opening_bar_direction,
                "trend_ema_fast": ema_fast[idx],
                "trend_ema_slow": ema_slow[idx],
                "volume_ratio": breakout_volume_ratio,
                "relative_opening_volume": relative_opening_volume,
                "atr_value": atr_value,
                "fvg_gap": (current_low - prev2_high) if direction > 0 else (prev2_low - current_high),
                "opening_range_minutes": opening_range_count,
                "orb_width_pct": orb_width_pct,
                "strategy_variant": "orb_fib_pullback",
                "fib_anchor": orb_low,
                "fib_impulse_extreme": impulse_extreme,
                "fib_entry_zone_low": zone_low,
                "fib_entry_zone_high": zone_high,
                "fib_pullback_extreme": pullback_extreme,
            }

        assert impulse_extreme is not None and pullback_extreme is not None
        impulse_extreme = min(impulse_extreme, current_low)
        pullback_extreme = max(pullback_extreme, current_high)
        impulse = orb_high - impulse_extreme
        if impulse <= 0:
            continue
        zone_high = orb_high - (impulse * fib_low_ratio)
        zone_low = orb_high - (impulse * fib_high_ratio)
        if not (current_high >= zone_low and current_low <= zone_high):
            continue
        if cfg.fib_require_confirmation:
            if not (current_close < current_open and current_close <= zone_low):
                continue
        elif current_close > zone_high:
            continue
        entry_idx = idx + 1
        entry_bar = session_bars[entry_idx]
        entry_price = float(entry_bar.get("open") or 0.0)
        if entry_price <= 0:
            continue
        stop_price = pullback_extreme
        if stop_price <= entry_price:
            continue
        prev2 = session_bars[idx - 2]
        prev2_high = float(prev2.get("high") or 0.0)
        prev2_low = float(prev2.get("low") or 0.0)
        return {
            "direction": direction,
            "signal_idx": idx,
            "signal_ts": bar["ts"],
            "entry_idx": entry_idx,
            "entry_ts": entry_bar["ts"],
            "entry_underlying": entry_price,
            "stop_underlying": stop_price,
            "orb_high": orb_high,
            "orb_low": orb_low,
            "opening_bar_open": orb_open,
            "opening_bar_close": orb_close,
            "opening_bar_direction": opening_bar_direction,
            "trend_ema_fast": ema_fast[idx],
            "trend_ema_slow": ema_slow[idx],
            "volume_ratio": breakout_volume_ratio,
            "relative_opening_volume": relative_opening_volume,
            "atr_value": atr_value,
            "fvg_gap": (current_low - prev2_high) if direction > 0 else (prev2_low - current_high),
            "opening_range_minutes": opening_range_count,
            "orb_width_pct": orb_width_pct,
            "strategy_variant": "orb_fib_pullback",
            "fib_anchor": orb_high,
            "fib_impulse_extreme": impulse_extreme,
            "fib_entry_zone_low": zone_low,
            "fib_entry_zone_high": zone_high,
            "fib_pullback_extreme": pullback_extreme,
        }

    return None


def _find_intraday_setup_qc_with_audit(
    session_bars: List[Dict[str, Any]],
    cfg: IntradayStrategyConfig,
    relative_opening_volume: Optional[float],
    atr_value: Optional[float],
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    audit: Dict[str, Any] = {
        "strategy_variant": "orb_qc",
        "opportunities_before_filters": 0,
        "opportunities_after_filters": 0,
        "rejections": {},
    }
    opening_range_count = max(int(cfg.opening_range_minutes), 1)
    if len(session_bars) < (opening_range_count + 3):
        _inc_reason(audit["rejections"], "insufficient_bars")
        return None, audit

    opening_range = session_bars[:opening_range_count]
    orb_high = max(float(bar.get("high") or 0.0) for bar in opening_range)
    orb_low = min(float(bar.get("low") or 0.0) for bar in opening_range)
    orb_open = float(opening_range[0].get("open") or 0.0)
    orb_close = float(opening_range[-1].get("close") or 0.0)
    if orb_high <= 0 or orb_low <= 0 or orb_high <= orb_low:
        _inc_reason(audit["rejections"], "invalid_opening_range")
        return None, audit

    orb_width_pct = (orb_high - orb_low) / max(orb_open, 1.0)
    if cfg.require_or_width_filter:
        min_width = max(float(cfg.opening_range_min_width_pct), 0.0)
        max_width = max(float(cfg.opening_range_max_width_pct), min_width)
        if orb_width_pct < min_width or orb_width_pct > max_width:
            _inc_reason(audit["rejections"], "orb_width_filter")
            return None, audit

    opening_bar_direction = 0
    if orb_close > orb_open:
        opening_bar_direction = 1
    elif orb_close < orb_open:
        opening_bar_direction = -1

    closes = [float(bar.get("close") or 0.0) for bar in session_bars]
    ema_fast = _ema_series(closes, cfg.trend_ema_fast)
    ema_slow = _ema_series(closes, cfg.trend_ema_slow)

    setup: Optional[Dict[str, Any]] = None
    entry_start = _parse_hhmm(cfg.entry_start_time, _default_entry_start(opening_range_count))
    entry_cutoff = _parse_hhmm(cfg.entry_cutoff_time, "12:00")
    macro_release_times = (
        _parse_hhmm_list(cfg.macro_release_times_et, "10:00")
        if cfg.require_macro_release_filter
        else []
    )
    macro_block_minutes = max(int(cfg.macro_post_release_block_minutes), 0)
    trigger_mode = str(cfg.entry_trigger_mode or "close_breakout").strip().lower()

    for idx in range(opening_range_count, len(session_bars) - 1):
        bar = session_bars[idx]
        bar_time = _to_et_time(bar["ts"])
        if bar_time < entry_start or bar_time > entry_cutoff:
            continue

        current_open = float(bar.get("open") or 0.0)
        current_high = float(bar.get("high") or 0.0)
        current_low = float(bar.get("low") or 0.0)
        current_close = float(bar.get("close") or 0.0)
        if current_open <= 0 or current_high <= 0 or current_low <= 0 or current_close <= 0:
            continue

        if trigger_mode == "stop_touch":
            long_breakout = current_high >= orb_high
            short_breakout = current_low <= orb_low
        else:
            long_breakout = current_close > orb_high
            short_breakout = current_close < orb_low
        raw_directions: List[int] = []
        if long_breakout:
            raw_directions.append(1)
        if short_breakout:
            raw_directions.append(-1)
        if not raw_directions:
            continue
        audit["opportunities_before_filters"] = int(audit.get("opportunities_before_filters") or 0) + len(
            raw_directions
        )

        if cfg.require_macro_release_filter and _is_in_macro_release_block(
            bar_time,
            macro_release_times,
            macro_block_minutes,
        ):
            _inc_reason(audit["rejections"], "macro_release_block", len(raw_directions))
            continue

        if cfg.require_breakout_open_inside_range and not (orb_low <= current_open <= orb_high):
            _inc_reason(audit["rejections"], "breakout_open_outside_range", len(raw_directions))
            continue

        candidate_directions: List[int] = []
        for direction in raw_directions:
            if direction > 0 and cfg.allow_long:
                candidate_directions.append(direction)
            elif direction < 0 and cfg.allow_short:
                candidate_directions.append(direction)
            else:
                _inc_reason(audit["rejections"], "direction_not_allowed")
        if not candidate_directions:
            continue

        if cfg.use_opening_bar_direction:
            filtered = [direction for direction in candidate_directions if direction == opening_bar_direction]
            skipped = len(candidate_directions) - len(filtered)
            if skipped > 0:
                _inc_reason(audit["rejections"], "opening_bar_direction_mismatch", skipped)
            candidate_directions = filtered
            if not candidate_directions:
                continue

        relative_volume_rejection = _relative_volume_rejection_reason(cfg, relative_opening_volume)
        if relative_volume_rejection is not None:
            _inc_reason(audit["rejections"], relative_volume_rejection, len(candidate_directions))
            continue

        if cfg.require_atr_filter:
            if atr_value is None or atr_value < cfg.atr_min:
                _inc_reason(audit["rejections"], "atr_filter", len(candidate_directions))
                continue

        if cfg.require_volume_spike:
            if idx < cfg.volume_ma_window:
                _inc_reason(audit["rejections"], "volume_ma_warmup", len(candidate_directions))
                continue
            lookback = session_bars[idx - cfg.volume_ma_window : idx]
            avg_volume = _mean_fast(float(row.get("volume") or 0.0) for row in lookback)
            if avg_volume <= 0:
                _inc_reason(audit["rejections"], "volume_ma_invalid", len(candidate_directions))
                continue
            volume_ratio = float(bar.get("volume") or 0.0) / avg_volume
            if volume_ratio < cfg.volume_spike_multiple:
                _inc_reason(audit["rejections"], "volume_spike_filter", len(candidate_directions))
                continue
        else:
            volume_ratio = 1.0

        direction = candidate_directions[0]
        if len(candidate_directions) > 1:
            _inc_reason(audit["rejections"], "secondary_direction_dropped", len(candidate_directions) - 1)

        if cfg.require_trend_alignment:
            if direction > 0 and not (ema_fast[idx] > ema_slow[idx]):
                _inc_reason(audit["rejections"], "trend_alignment_filter")
                continue
            if direction < 0 and not (ema_fast[idx] < ema_slow[idx]):
                _inc_reason(audit["rejections"], "trend_alignment_filter")
                continue

        prev2 = session_bars[idx - 2]
        prev2_high = float(prev2.get("high") or 0.0)
        prev2_low = float(prev2.get("low") or 0.0)
        if cfg.require_fvg:
            if direction > 0 and not (prev2_high < current_low):
                _inc_reason(audit["rejections"], "fvg_filter")
                continue
            if direction < 0 and not (prev2_low > current_high):
                _inc_reason(audit["rejections"], "fvg_filter")
                continue

        entry_idx, entry_bar, entry_price = _next_bar_open_entry(session_bars, signal_idx=idx)
        if entry_idx is None or entry_bar is None or entry_price <= 0:
            _inc_reason(audit["rejections"], "invalid_entry_price")
            continue

        stop_price = _compute_stop_price(
            cfg=cfg,
            direction=direction,
            orb_high=orb_high,
            orb_low=orb_low,
            breakout_high=current_high,
            breakout_low=current_low,
            entry_price=entry_price,
            atr_value=atr_value,
        )
        if stop_price is None:
            _inc_reason(audit["rejections"], "invalid_stop")
            continue

        audit["opportunities_after_filters"] = int(audit.get("opportunities_after_filters") or 0) + 1
        if setup is not None:
            continue

        setup = {
            "direction": direction,
            "signal_idx": idx,
            "signal_ts": bar["ts"],
            "entry_idx": entry_idx,
            "entry_ts": entry_bar["ts"],
            "entry_underlying": entry_price,
            "stop_underlying": stop_price,
            "orb_high": orb_high,
            "orb_low": orb_low,
            "opening_bar_open": orb_open,
            "opening_bar_close": orb_close,
            "opening_bar_direction": opening_bar_direction,
            "trend_ema_fast": ema_fast[idx],
            "trend_ema_slow": ema_slow[idx],
            "volume_ratio": volume_ratio,
            "relative_opening_volume": relative_opening_volume,
            "atr_value": atr_value,
            "fvg_gap": (current_low - prev2_high) if direction > 0 else (prev2_low - current_high),
            "opening_range_minutes": opening_range_count,
            "orb_width_pct": orb_width_pct,
            "strategy_variant": "orb_qc",
        }

    return setup, audit


def _find_orb_trend_short_setup_with_audit(
    session_bars: List[Dict[str, Any]],
    cfg: IntradayStrategyConfig,
    relative_opening_volume: Optional[float],
    atr_value: Optional[float],
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    short_cfg = replace(
        cfg,
        strategy_variant="orb_qc",
        allow_long=False,
        allow_short=True,
    )
    setup, audit = _find_intraday_setup_qc_with_audit(
        session_bars=session_bars,
        cfg=short_cfg,
        relative_opening_volume=relative_opening_volume,
        atr_value=atr_value,
    )
    out = dict(audit)
    out["strategy_variant"] = "orb_trend_short"
    if setup is None:
        return None, out
    setup["strategy_variant"] = "orb_trend_short"
    return setup, out


def _find_orb_failure_fade_setup_with_audit(
    session_bars: List[Dict[str, Any]],
    cfg: IntradayStrategyConfig,
    relative_opening_volume: Optional[float],
    atr_value: Optional[float],
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    audit: Dict[str, Any] = {
        "strategy_variant": "orb_failure_fade",
        "opportunities_before_filters": 0,
        "opportunities_after_filters": 0,
        "rejections": {},
    }
    opening_range_count = max(int(cfg.opening_range_minutes), 1)
    if len(session_bars) < (opening_range_count + 4):
        _inc_reason(audit["rejections"], "insufficient_bars")
        return None, audit

    opening_range = session_bars[:opening_range_count]
    orb_high = max(float(bar.get("high") or 0.0) for bar in opening_range)
    orb_low = min(float(bar.get("low") or 0.0) for bar in opening_range)
    orb_open = float(opening_range[0].get("open") or 0.0)
    orb_close = float(opening_range[-1].get("close") or 0.0)
    if orb_high <= 0 or orb_low <= 0 or orb_high <= orb_low:
        _inc_reason(audit["rejections"], "invalid_opening_range")
        return None, audit

    orb_width_pct = (orb_high - orb_low) / max(orb_open, 1.0)
    if cfg.require_or_width_filter:
        min_width = max(float(cfg.opening_range_min_width_pct), 0.0)
        max_width = max(float(cfg.opening_range_max_width_pct), min_width)
        if orb_width_pct < min_width or orb_width_pct > max_width:
            _inc_reason(audit["rejections"], "orb_width_filter")
            return None, audit

    entry_start = _parse_hhmm(cfg.entry_start_time, _default_entry_start(opening_range_count))
    entry_cutoff = _parse_hhmm(cfg.entry_cutoff_time, "12:00")
    trigger_mode = str(cfg.entry_trigger_mode or "close_breakout").strip().lower()
    macro_release_times = (
        _parse_hhmm_list(cfg.macro_release_times_et, "10:00")
        if cfg.require_macro_release_filter
        else []
    )
    macro_block_minutes = max(int(cfg.macro_post_release_block_minutes), 0)

    opening_bar_direction = 0
    if orb_close > orb_open:
        opening_bar_direction = 1
    elif orb_close < orb_open:
        opening_bar_direction = -1
    closes = [float(bar.get("close") or 0.0) for bar in session_bars]
    ema_fast = _ema_series(closes, cfg.trend_ema_fast)
    ema_slow = _ema_series(closes, cfg.trend_ema_slow)

    breakout_direction = 0
    breakout_extreme = 0.0
    breakout_idx = -1

    for idx in range(opening_range_count, len(session_bars) - 1):
        bar = session_bars[idx]
        bar_time = _to_et_time(bar["ts"])
        if bar_time < entry_start or bar_time > entry_cutoff:
            continue
        if cfg.require_macro_release_filter and _is_in_macro_release_block(
            bar_time,
            macro_release_times,
            macro_block_minutes,
        ):
            _inc_reason(audit["rejections"], "macro_release_block")
            continue

        current_open = float(bar.get("open") or 0.0)
        current_high = float(bar.get("high") or 0.0)
        current_low = float(bar.get("low") or 0.0)
        current_close = float(bar.get("close") or 0.0)
        if current_open <= 0 or current_high <= 0 or current_low <= 0 or current_close <= 0:
            continue

        if breakout_direction == 0:
            if trigger_mode == "stop_touch":
                up_break = current_high >= orb_high
                down_break = current_low <= orb_low
            else:
                up_break = current_close > orb_high
                down_break = current_close < orb_low
            if not up_break and not down_break:
                continue

            if cfg.require_breakout_open_inside_range and not (orb_low <= current_open <= orb_high):
                _inc_reason(audit["rejections"], "breakout_open_outside_range")
                continue

            audit["opportunities_before_filters"] = int(audit.get("opportunities_before_filters") or 0) + 1
            if up_break and down_break:
                distance_up = abs(current_close - orb_high)
                distance_down = abs(current_close - orb_low)
                breakout_direction = 1 if distance_up >= distance_down else -1
            else:
                breakout_direction = 1 if up_break else -1
            breakout_extreme = current_high if breakout_direction > 0 else current_low
            breakout_idx = idx
            continue

        if breakout_direction > 0:
            breakout_extreme = max(breakout_extreme, current_high)
            failure_confirmed = current_close < orb_high
            if not failure_confirmed:
                continue
            direction = -1
            if not cfg.allow_short:
                _inc_reason(audit["rejections"], "direction_not_allowed")
                return None, audit
            stop_price = max(breakout_extreme, current_high)
            if atr_value is not None and atr_value > 0:
                stop_price = max(stop_price, current_close + (0.15 * atr_value))
        else:
            breakout_extreme = min(breakout_extreme, current_low)
            failure_confirmed = current_close > orb_low
            if not failure_confirmed:
                continue
            direction = 1
            if not cfg.allow_long:
                _inc_reason(audit["rejections"], "direction_not_allowed")
                return None, audit
            stop_price = min(breakout_extreme, current_low)
            if atr_value is not None and atr_value > 0:
                stop_price = min(stop_price, current_close - (0.15 * atr_value))

        relative_volume_rejection = _relative_volume_rejection_reason(cfg, relative_opening_volume)
        if relative_volume_rejection is not None:
            _inc_reason(audit["rejections"], relative_volume_rejection)
            return None, audit
        if cfg.require_atr_filter:
            if atr_value is None or atr_value < cfg.atr_min:
                _inc_reason(audit["rejections"], "atr_filter")
                return None, audit

        entry_idx = idx + 1
        if entry_idx >= len(session_bars):
            _inc_reason(audit["rejections"], "insufficient_bars")
            return None, audit
        entry_bar = session_bars[entry_idx]
        entry_price = float(entry_bar.get("open") or 0.0)
        if entry_price <= 0:
            _inc_reason(audit["rejections"], "invalid_entry_price")
            return None, audit
        if direction > 0 and stop_price >= entry_price:
            _inc_reason(audit["rejections"], "invalid_stop")
            return None, audit
        if direction < 0 and stop_price <= entry_price:
            _inc_reason(audit["rejections"], "invalid_stop")
            return None, audit

        audit["opportunities_after_filters"] = int(audit.get("opportunities_after_filters") or 0) + 1
        return (
            {
                "direction": direction,
                "signal_idx": idx,
                "signal_ts": bar["ts"],
                "entry_idx": entry_idx,
                "entry_ts": entry_bar["ts"],
                "entry_underlying": entry_price,
                "stop_underlying": stop_price,
                "orb_high": orb_high,
                "orb_low": orb_low,
                "opening_bar_open": orb_open,
                "opening_bar_close": orb_close,
                "opening_bar_direction": opening_bar_direction,
                "trend_ema_fast": ema_fast[idx],
                "trend_ema_slow": ema_slow[idx],
                "volume_ratio": 1.0,
                "relative_opening_volume": relative_opening_volume,
                "atr_value": atr_value,
                "fvg_gap": 0.0,
                "opening_range_minutes": opening_range_count,
                "orb_width_pct": orb_width_pct,
                "strategy_variant": "orb_failure_fade",
                "failure_breakout_direction": breakout_direction,
                "failure_breakout_idx": breakout_idx,
                "failure_breakout_extreme": breakout_extreme,
            },
            audit,
        )

    if breakout_direction == 0:
        _inc_reason(audit["rejections"], "no_breakout_detected")
    else:
        _inc_reason(audit["rejections"], "no_failure_confirmation")
    return None, audit


def _find_failed_break_reclaim_setup_with_audit(
    session_bars: List[Dict[str, Any]],
    cfg: IntradayStrategyConfig,
    relative_opening_volume: Optional[float],
    atr_value: Optional[float],
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    audit: Dict[str, Any] = {
        "strategy_variant": "failed_break_reclaim_v1",
        "opportunities_before_filters": 0,
        "opportunities_after_filters": 0,
        "rejections": {},
    }
    opening_range_count = max(int(cfg.opening_range_minutes), 1)
    if len(session_bars) < (opening_range_count + 5):
        _inc_reason(audit["rejections"], "insufficient_bars")
        return None, audit

    opening_range = session_bars[:opening_range_count]
    orb_high = max(float(bar.get("high") or 0.0) for bar in opening_range)
    orb_low = min(float(bar.get("low") or 0.0) for bar in opening_range)
    orb_open = float(opening_range[0].get("open") or 0.0)
    orb_close = float(opening_range[-1].get("close") or 0.0)
    if orb_high <= 0 or orb_low <= 0 or orb_high <= orb_low:
        _inc_reason(audit["rejections"], "invalid_opening_range")
        return None, audit

    orb_width = orb_high - orb_low
    orb_width_pct = orb_width / max(orb_open, 1.0)
    if cfg.require_or_width_filter:
        min_width = max(float(cfg.opening_range_min_width_pct), 0.0)
        max_width = max(float(cfg.opening_range_max_width_pct), min_width)
        if orb_width_pct < min_width or orb_width_pct > max_width:
            _inc_reason(audit["rejections"], "orb_width_filter")
            return None, audit

    if not cfg.allow_long:
        _inc_reason(audit["rejections"], "direction_not_allowed")
        return None, audit

    entry_start = _parse_hhmm(cfg.entry_start_time, _default_entry_start(opening_range_count))
    entry_cutoff = _parse_hhmm(cfg.entry_cutoff_time, "12:00")
    macro_release_times = (
        _parse_hhmm_list(cfg.macro_release_times_et, "10:00")
        if cfg.require_macro_release_filter
        else []
    )
    macro_block_minutes = max(int(cfg.macro_post_release_block_minutes), 0)
    closes = [float(bar.get("close") or 0.0) for bar in session_bars]
    ema_fast = _ema_series(closes, cfg.trend_ema_fast)
    ema_slow = _ema_series(closes, cfg.trend_ema_slow)
    vwap_series = _running_vwap_series(session_bars)
    opening_bar_direction = 1 if orb_close > orb_open else (-1 if orb_close < orb_open else 0)
    orb_mid = (orb_high + orb_low) / 2.0
    min_sweep_distance = max(float(getattr(cfg, "trend_pullback_min_breakout_or_frac", 0.0)) * orb_width, orb_open * 0.0005)
    max_reclaim_bars = max(int(getattr(cfg, "trend_pullback_max_bars_after_breakout", 30)), 1)
    reclaim_close_location_min = max(
        0.0,
        min(1.0, float(getattr(cfg, "drive_reclaim_close_location_min", 0.55))),
    )

    sweep_state: Optional[Dict[str, Any]] = None
    for idx in range(opening_range_count, len(session_bars) - 1):
        bar = session_bars[idx]
        bar_time = _to_et_time(bar["ts"])
        if bar_time < entry_start or bar_time > entry_cutoff:
            continue
        if cfg.require_macro_release_filter and _is_in_macro_release_block(
            bar_time,
            macro_release_times,
            macro_block_minutes,
        ):
            _inc_reason(audit["rejections"], "macro_release_block")
            continue

        open_price = float(bar.get("open") or 0.0)
        high_price = float(bar.get("high") or 0.0)
        low_price = float(bar.get("low") or 0.0)
        close_price = float(bar.get("close") or 0.0)
        if open_price <= 0 or high_price <= 0 or low_price <= 0 or close_price <= 0:
            continue

        if sweep_state is None:
            sweep_distance = max(orb_low - low_price, 0.0)
            if sweep_distance < min_sweep_distance:
                continue
            audit["opportunities_before_filters"] = int(audit.get("opportunities_before_filters") or 0) + 1
            sweep_state = {
                "idx": idx,
                "low": low_price,
                "distance": sweep_distance,
            }
            continue

        if low_price < float(sweep_state.get("low") or low_price):
            sweep_state["idx"] = idx
            sweep_state["low"] = low_price
            sweep_state["distance"] = max(orb_low - low_price, 0.0)

        bars_since_sweep = idx - int(sweep_state.get("idx") or idx)
        if bars_since_sweep > max_reclaim_bars:
            _inc_reason(audit["rejections"], "reclaim_timeout")
            sweep_state = None
            continue

        relative_volume_rejection = _relative_volume_rejection_reason(cfg, relative_opening_volume)
        if relative_volume_rejection is not None:
            _inc_reason(audit["rejections"], relative_volume_rejection)
            continue
        if cfg.require_atr_filter and (atr_value is None or atr_value < cfg.atr_min):
            _inc_reason(audit["rejections"], "atr_filter")
            continue
        if cfg.require_trend_alignment and not (ema_fast[idx] > ema_slow[idx]):
            _inc_reason(audit["rejections"], "trend_alignment_filter")
            continue

        vwap_now = float(vwap_series[idx]) if idx < len(vwap_series) else 0.0
        if vwap_now <= 0 or close_price <= vwap_now:
            _inc_reason(audit["rejections"], "reclaim_below_vwap")
            continue
        if close_price <= orb_mid:
            _inc_reason(audit["rejections"], "reclaim_below_or_mid")
            continue
        if not (orb_low < close_price < orb_high):
            _inc_reason(audit["rejections"], "reclaim_not_inside_range")
            continue
        reclaim_close_location = _close_location_fraction(
            direction=1,
            high_price=high_price,
            low_price=low_price,
            close_price=close_price,
        )
        if reclaim_close_location < reclaim_close_location_min:
            _inc_reason(audit["rejections"], "reclaim_close_location")
            continue

        entry_idx, entry_bar, entry_price = _next_bar_open_entry(session_bars, signal_idx=idx)
        if entry_idx is None or entry_bar is None or entry_price <= 0:
            _inc_reason(audit["rejections"], "invalid_entry_price")
            continue
        stop_price = float(sweep_state.get("low") or 0.0)
        if stop_price <= 0 or stop_price >= entry_price:
            _inc_reason(audit["rejections"], "invalid_stop")
            continue

        audit["opportunities_after_filters"] = int(audit.get("opportunities_after_filters") or 0) + 1
        return (
            {
                "direction": 1,
                "signal_idx": idx,
                "signal_ts": bar["ts"],
                "entry_idx": entry_idx,
                "entry_ts": entry_bar["ts"],
                "entry_underlying": entry_price,
                "stop_underlying": stop_price,
                "orb_high": orb_high,
                "orb_low": orb_low,
                "opening_bar_open": orb_open,
                "opening_bar_close": orb_close,
                "opening_bar_direction": opening_bar_direction,
                "trend_ema_fast": ema_fast[idx],
                "trend_ema_slow": ema_slow[idx],
                "volume_ratio": _bar_volume_ratio(session_bars, idx, cfg.volume_ma_window) or 1.0,
                "relative_opening_volume": relative_opening_volume,
                "atr_value": atr_value,
                "fvg_gap": 0.0,
                "opening_range_minutes": opening_range_count,
                "orb_width_pct": orb_width_pct,
                "strategy_variant": "failed_break_reclaim_v1",
                "failure_sweep_low": float(sweep_state.get("low") or 0.0),
                "failure_sweep_distance": float(sweep_state.get("distance") or 0.0),
                "failure_reclaim_close_location": reclaim_close_location,
            },
            audit,
        )

    if sweep_state is None:
        _inc_reason(audit["rejections"], "no_downside_sweep")
    else:
        _inc_reason(audit["rejections"], "no_reclaim_confirmation")
    return None, audit


def _find_pause_go_continuation_setup_with_audit(
    session_bars: List[Dict[str, Any]],
    cfg: IntradayStrategyConfig,
    relative_opening_volume: Optional[float],
    atr_value: Optional[float],
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    audit: Dict[str, Any] = {
        "strategy_variant": "pause_go_continuation_v1",
        "opportunities_before_filters": 0,
        "opportunities_after_filters": 0,
        "rejections": {},
    }
    opening_range_count = max(int(cfg.opening_range_minutes), 1)
    if len(session_bars) < (opening_range_count + 6):
        _inc_reason(audit["rejections"], "insufficient_bars")
        return None, audit

    opening_range = session_bars[:opening_range_count]
    orb_high = max(float(bar.get("high") or 0.0) for bar in opening_range)
    orb_low = min(float(bar.get("low") or 0.0) for bar in opening_range)
    orb_open = float(opening_range[0].get("open") or 0.0)
    orb_close = float(opening_range[-1].get("close") or 0.0)
    if orb_high <= 0 or orb_low <= 0 or orb_high <= orb_low:
        _inc_reason(audit["rejections"], "invalid_opening_range")
        return None, audit

    if not cfg.allow_long:
        _inc_reason(audit["rejections"], "direction_not_allowed")
        return None, audit

    orb_width = orb_high - orb_low
    orb_width_pct = orb_width / max(orb_open, 1.0)
    if cfg.require_or_width_filter:
        min_width = max(float(cfg.opening_range_min_width_pct), 0.0)
        max_width = max(float(cfg.opening_range_max_width_pct), min_width)
        if orb_width_pct < min_width or orb_width_pct > max_width:
            _inc_reason(audit["rejections"], "orb_width_filter")
            return None, audit

    entry_start = _parse_hhmm(cfg.entry_start_time, _default_entry_start(opening_range_count))
    entry_cutoff = _parse_hhmm(cfg.entry_cutoff_time, "12:00")
    breakout_deadline = _parse_hhmm("10:15", "10:15")
    trigger_mode = str(cfg.entry_trigger_mode or "close_breakout").strip().lower()
    closes = [float(bar.get("close") or 0.0) for bar in session_bars]
    ema_fast = _ema_series(closes, cfg.trend_ema_fast)
    ema_slow = _ema_series(closes, cfg.trend_ema_slow)
    vwap_series = _running_vwap_series(session_bars)
    opening_bar_direction = 1 if orb_close > orb_open else (-1 if orb_close < orb_open else 0)
    pause_lookback = max(int(getattr(cfg, "compression_lookback_bars", 4)), 2)
    compression_max_range_pct = max(float(getattr(cfg, "compression_max_range_pct", 0.0)), 0.0)
    breakout_buffer_or_frac = max(float(getattr(cfg, "compression_breakout_buffer_or_frac", 0.0)), 0.0)
    min_volume_multiple = max(float(getattr(cfg, "compression_min_volume_multiple", 0.0)), 0.0)

    breakout_state: Optional[Dict[str, Any]] = None
    for idx in range(opening_range_count, len(session_bars) - 1):
        bar = session_bars[idx]
        bar_time = _to_et_time(bar["ts"])
        if bar_time < entry_start or bar_time > entry_cutoff:
            continue

        open_price = float(bar.get("open") or 0.0)
        high_price = float(bar.get("high") or 0.0)
        low_price = float(bar.get("low") or 0.0)
        close_price = float(bar.get("close") or 0.0)
        if open_price <= 0 or high_price <= 0 or low_price <= 0 or close_price <= 0:
            continue
        vwap_now = float(vwap_series[idx]) if idx < len(vwap_series) else 0.0
        if vwap_now <= 0:
            continue

        if breakout_state is None:
            if bar_time > breakout_deadline:
                _inc_reason(audit["rejections"], "breakout_deadline_miss")
                break
            relative_volume_rejection = _relative_volume_rejection_reason(cfg, relative_opening_volume)
            if relative_volume_rejection is not None:
                _inc_reason(audit["rejections"], relative_volume_rejection)
                continue
            if cfg.require_atr_filter and (atr_value is None or atr_value < cfg.atr_min):
                _inc_reason(audit["rejections"], "atr_filter")
                continue
            if cfg.require_trend_alignment and not (ema_fast[idx] > ema_slow[idx]):
                _inc_reason(audit["rejections"], "trend_alignment_filter")
                continue
            breakout_distance = (
                high_price - orb_high
                if trigger_mode == "stop_touch"
                else close_price - orb_high
            )
            if breakout_distance <= 0:
                continue
            audit["opportunities_before_filters"] = int(audit.get("opportunities_before_filters") or 0) + 1
            breakout_or_frac = breakout_distance / max(orb_width, 1e-9)
            if breakout_or_frac < breakout_buffer_or_frac:
                _inc_reason(audit["rejections"], "pause_go_breakout_strength")
                continue
            volume_ratio = _bar_volume_ratio(session_bars, idx, cfg.volume_ma_window)
            if volume_ratio is None:
                _inc_reason(audit["rejections"], "volume_ma_warmup")
                continue
            if volume_ratio < min_volume_multiple:
                _inc_reason(audit["rejections"], "compression_volume_filter")
                continue
            if close_price <= vwap_now:
                _inc_reason(audit["rejections"], "breakout_below_vwap")
                continue
            breakout_state = {
                "idx": idx,
                "high": high_price,
                "low": low_price,
                "range": high_price - low_price,
                "volume_ratio": volume_ratio,
                "breakout_or_frac": breakout_or_frac,
            }
            continue

        pause_start = max(int(breakout_state["idx"]) + 1, idx - pause_lookback)
        pause_window = session_bars[pause_start:idx]
        if len(pause_window) < 2:
            continue
        pause_high = max(float(row.get("high") or 0.0) for row in pause_window)
        pause_low = min(float(row.get("low") or 0.0) for row in pause_window)
        if any(float(row.get("low") or 0.0) <= orb_high for row in pause_window):
            _inc_reason(audit["rejections"], "pause_not_above_or")
            continue
        if any(float(row.get("close") or 0.0) <= float(vwap_series[pause_start + offset]) for offset, row in enumerate(pause_window)):
            _inc_reason(audit["rejections"], "pause_not_above_vwap")
            continue
        pause_range_pct = (pause_high - pause_low) / max(pause_low, 1.0)
        if pause_range_pct > compression_max_range_pct:
            _inc_reason(audit["rejections"], "compression_range_too_wide")
            continue
        if (pause_high - pause_low) >= max(float(breakout_state.get("range") or 0.0), 1e-9):
            _inc_reason(audit["rejections"], "pause_not_contracting")
            continue
        release_trigger = (
            high_price >= (pause_high + (orb_width * breakout_buffer_or_frac))
            if trigger_mode == "stop_touch"
            else close_price > (pause_high + (orb_width * breakout_buffer_or_frac))
        )
        if not release_trigger or close_price <= max(orb_high, vwap_now):
            _inc_reason(audit["rejections"], "release_confirmation")
            continue
        release_close_location = _close_location_fraction(
            direction=1,
            high_price=high_price,
            low_price=low_price,
            close_price=close_price,
        )
        if release_close_location < 0.55:
            _inc_reason(audit["rejections"], "release_close_location")
            continue

        entry_idx, entry_bar, entry_price = _next_bar_open_entry(session_bars, signal_idx=idx)
        if entry_idx is None or entry_bar is None or entry_price <= 0:
            _inc_reason(audit["rejections"], "invalid_entry_price")
            continue
        stop_price = pause_low
        if stop_price <= 0 or stop_price >= entry_price:
            _inc_reason(audit["rejections"], "invalid_stop")
            continue

        audit["opportunities_after_filters"] = int(audit.get("opportunities_after_filters") or 0) + 1
        return (
            {
                "direction": 1,
                "signal_idx": idx,
                "signal_ts": bar["ts"],
                "entry_idx": entry_idx,
                "entry_ts": entry_bar["ts"],
                "entry_underlying": entry_price,
                "stop_underlying": stop_price,
                "orb_high": orb_high,
                "orb_low": orb_low,
                "opening_bar_open": orb_open,
                "opening_bar_close": orb_close,
                "opening_bar_direction": opening_bar_direction,
                "trend_ema_fast": ema_fast[idx],
                "trend_ema_slow": ema_slow[idx],
                "volume_ratio": _bar_volume_ratio(session_bars, idx, cfg.volume_ma_window) or float(breakout_state.get("volume_ratio") or 1.0),
                "relative_opening_volume": relative_opening_volume,
                "atr_value": atr_value,
                "fvg_gap": 0.0,
                "opening_range_minutes": opening_range_count,
                "orb_width_pct": orb_width_pct,
                "strategy_variant": "pause_go_continuation_v1",
                "pause_go_breakout_or_frac": float(breakout_state.get("breakout_or_frac") or 0.0),
                "pause_go_pause_range_pct": pause_range_pct,
                "pause_go_pause_bars": len(pause_window),
            },
            audit,
        )

    if breakout_state is None:
        _inc_reason(audit["rejections"], "no_breakout_detected")
    else:
        _inc_reason(audit["rejections"], "no_pause_go_release")
    return None, audit


def _find_vwap_rollover_short_setup_with_audit(
    session_bars: List[Dict[str, Any]],
    cfg: IntradayStrategyConfig,
    relative_opening_volume: Optional[float],
    atr_value: Optional[float],
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    audit: Dict[str, Any] = {
        "strategy_variant": "vwap_rollover_short_v1",
        "opportunities_before_filters": 0,
        "opportunities_after_filters": 0,
        "rejections": {},
    }
    opening_range_count = max(int(cfg.opening_range_minutes), 1)
    if len(session_bars) < (opening_range_count + 5):
        _inc_reason(audit["rejections"], "insufficient_bars")
        return None, audit

    opening_range = session_bars[:opening_range_count]
    orb_high = max(float(bar.get("high") or 0.0) for bar in opening_range)
    orb_low = min(float(bar.get("low") or 0.0) for bar in opening_range)
    orb_open = float(opening_range[0].get("open") or 0.0)
    orb_close = float(opening_range[-1].get("close") or 0.0)
    if orb_high <= 0 or orb_low <= 0 or orb_high <= orb_low:
        _inc_reason(audit["rejections"], "invalid_opening_range")
        return None, audit

    if not cfg.allow_short:
        _inc_reason(audit["rejections"], "direction_not_allowed")
        return None, audit

    orb_width = orb_high - orb_low
    orb_width_pct = orb_width / max(orb_open, 1.0)
    if cfg.require_or_width_filter:
        min_width = max(float(cfg.opening_range_min_width_pct), 0.0)
        max_width = max(float(cfg.opening_range_max_width_pct), min_width)
        if orb_width_pct < min_width or orb_width_pct > max_width:
            _inc_reason(audit["rejections"], "orb_width_filter")
            return None, audit

    entry_start = _parse_hhmm(cfg.entry_start_time, _default_entry_start(opening_range_count))
    entry_cutoff = _parse_hhmm(cfg.entry_cutoff_time, "12:00")
    vwap_buffer_pct = max(float(getattr(cfg, "trend_pullback_ema_buffer_pct", 0.0)), 0.0)
    max_rollover_bars = max(int(getattr(cfg, "trend_pullback_max_bars_after_breakout", 8)), 1)
    closes = [float(bar.get("close") or 0.0) for bar in session_bars]
    ema_fast = _ema_series(closes, cfg.trend_ema_fast)
    ema_slow = _ema_series(closes, cfg.trend_ema_slow)
    vwap_series = _running_vwap_series(session_bars)
    opening_bar_direction = 1 if orb_close > orb_open else (-1 if orb_close < orb_open else 0)
    orb_mid = (orb_high + orb_low) / 2.0
    rejection_close_location_min = max(
        0.0,
        min(1.0, float(getattr(cfg, "drive_reclaim_close_location_min", 0.55))),
    )

    bounce_state: Optional[Dict[str, Any]] = None
    for idx in range(opening_range_count, len(session_bars) - 1):
        bar = session_bars[idx]
        bar_time = _to_et_time(bar["ts"])
        if bar_time < entry_start or bar_time > entry_cutoff:
            continue

        open_price = float(bar.get("open") or 0.0)
        high_price = float(bar.get("high") or 0.0)
        low_price = float(bar.get("low") or 0.0)
        close_price = float(bar.get("close") or 0.0)
        if open_price <= 0 or high_price <= 0 or low_price <= 0 or close_price <= 0:
            continue
        vwap_now = float(vwap_series[idx]) if idx < len(vwap_series) else 0.0
        if vwap_now <= 0:
            continue

        relative_volume_rejection = _relative_volume_rejection_reason(cfg, relative_opening_volume)
        if relative_volume_rejection is not None:
            _inc_reason(audit["rejections"], relative_volume_rejection)
            continue
        if cfg.require_atr_filter and (atr_value is None or atr_value < cfg.atr_min):
            _inc_reason(audit["rejections"], "atr_filter")
            continue
        if cfg.require_trend_alignment and not (ema_fast[idx] < ema_slow[idx]):
            _inc_reason(audit["rejections"], "trend_alignment_filter")
            continue

        if bounce_state is None:
            touched_vwap = high_price >= (vwap_now * (1.0 - vwap_buffer_pct))
            rejected = close_price < min(vwap_now, orb_mid)
            if not touched_vwap or not rejected:
                continue
            audit["opportunities_before_filters"] = int(audit.get("opportunities_before_filters") or 0) + 1
            bounce_state = {
                "idx": idx,
                "high": high_price,
                "low": low_price,
            }
            continue

        if idx - int(bounce_state.get("idx") or idx) > max_rollover_bars:
            _inc_reason(audit["rejections"], "rollover_timeout")
            bounce_state = None
            continue

        if high_price >= float(bounce_state.get("high") or high_price) and close_price < vwap_now:
            bounce_state["idx"] = idx
            bounce_state["high"] = high_price
            bounce_state["low"] = low_price
            continue

        lower_high_ok = high_price < float(bounce_state.get("high") or high_price) and high_price <= max(vwap_now, orb_mid)
        if not lower_high_ok:
            _inc_reason(audit["rejections"], "rollover_not_lower_high")
            continue
        close_location = _close_location_fraction(
            direction=-1,
            high_price=high_price,
            low_price=low_price,
            close_price=close_price,
        )
        if close_location < rejection_close_location_min:
            _inc_reason(audit["rejections"], "rollover_close_location")
            continue
        prev_low = float(session_bars[idx - 1].get("low") or 0.0) if idx > 0 else low_price
        if close_price >= min(prev_low, vwap_now, orb_mid):
            _inc_reason(audit["rejections"], "rollover_confirmation")
            continue

        entry_idx, entry_bar, entry_price = _next_bar_open_entry(session_bars, signal_idx=idx)
        if entry_idx is None or entry_bar is None or entry_price <= 0:
            _inc_reason(audit["rejections"], "invalid_entry_price")
            continue
        stop_price = max(float(bounce_state.get("high") or 0.0), high_price)
        if stop_price <= 0 or stop_price <= entry_price:
            _inc_reason(audit["rejections"], "invalid_stop")
            continue

        audit["opportunities_after_filters"] = int(audit.get("opportunities_after_filters") or 0) + 1
        return (
            {
                "direction": -1,
                "signal_idx": idx,
                "signal_ts": bar["ts"],
                "entry_idx": entry_idx,
                "entry_ts": entry_bar["ts"],
                "entry_underlying": entry_price,
                "stop_underlying": stop_price,
                "orb_high": orb_high,
                "orb_low": orb_low,
                "opening_bar_open": orb_open,
                "opening_bar_close": orb_close,
                "opening_bar_direction": opening_bar_direction,
                "trend_ema_fast": ema_fast[idx],
                "trend_ema_slow": ema_slow[idx],
                "volume_ratio": _bar_volume_ratio(session_bars, idx, cfg.volume_ma_window) or 1.0,
                "relative_opening_volume": relative_opening_volume,
                "atr_value": atr_value,
                "fvg_gap": 0.0,
                "opening_range_minutes": opening_range_count,
                "orb_width_pct": orb_width_pct,
                "strategy_variant": "vwap_rollover_short_v1",
                "rollover_bounce_high": float(bounce_state.get("high") or 0.0),
                "rollover_close_location": close_location,
            },
            audit,
        )

    if bounce_state is None:
        _inc_reason(audit["rejections"], "no_vwap_rejection")
    else:
        _inc_reason(audit["rejections"], "no_rollover_confirmation")
    return None, audit


def _find_intraday_setup_with_audit(
    session_bars: List[Dict[str, Any]],
    cfg: IntradayStrategyConfig,
    relative_opening_volume: Optional[float],
    atr_value: Optional[float],
    pair_session_bars: Optional[List[Dict[str, Any]]] = None,
    lfcm_context: Optional[Dict[str, Any]] = None,
    preopen_context: Optional[Dict[str, Any]] = None,
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    variant = str(cfg.strategy_variant or "orb_qc").strip().lower()
    audit: Dict[str, Any] = {
        "strategy_variant": variant,
        "opportunities_before_filters": 0,
        "opportunities_after_filters": 0,
        "rejections": {},
    }
    if not _passes_premarket_gate_with_audit(cfg=cfg, preopen_context=preopen_context, audit=audit):
        return None, audit
    if variant == "lfcm_v1":
        ctx = lfcm_context or {}
        lfcm_cfg = _LFCMConfig()
        return _find_lfcm_setup(
            session_bars=session_bars,
            premarket_bars=ctx.get("premarket_bars") or [],
            prev_close=float(ctx.get("prev_close") or 0.0),
            avg_daily_volume=ctx.get("avg_daily_volume"),
            current_float=ctx.get("current_float"),
            years_ago=float(ctx.get("years_ago") or 0.0),
            catalyst_headlines=ctx.get("catalyst_headlines"),
            cfg=lfcm_cfg,
        )
    if variant == "pairs_spread_v1":
        return _find_pairs_spread_setup_with_audit(
            session_bars=session_bars,
            pair_session_bars=pair_session_bars,
            cfg=cfg,
            relative_opening_volume=relative_opening_volume,
            atr_value=atr_value,
        )
    if variant == "dispersion_relative_breakout_v1":
        return _find_dispersion_relative_breakout_setup_with_audit(
            session_bars=session_bars,
            pair_session_bars=pair_session_bars,
            cfg=cfg,
            relative_opening_volume=relative_opening_volume,
            atr_value=atr_value,
        )
    if variant == "dispersion_relative_revert_v1":
        return _find_dispersion_relative_revert_setup_with_audit(
            session_bars=session_bars,
            pair_session_bars=pair_session_bars,
            cfg=cfg,
            relative_opening_volume=relative_opening_volume,
            atr_value=atr_value,
        )
    if variant == "relative_strength_continuation_v1":
        return _find_relative_strength_continuation_setup_with_audit(
            session_bars=session_bars,
            pair_session_bars=pair_session_bars,
            cfg=cfg,
            relative_opening_volume=relative_opening_volume,
            atr_value=atr_value,
        )
    if variant == "proxy_vwap_reclaim_v1":
        return _find_proxy_vwap_reclaim_setup_with_audit(
            session_bars=session_bars,
            pair_session_bars=pair_session_bars,
            cfg=cfg,
            relative_opening_volume=relative_opening_volume,
            atr_value=atr_value,
        )
    if variant == "mr_vwap_revert_v1":
        return find_mr_vwap_setup_with_audit(
            session_bars=session_bars,
            cfg=cfg,
            relative_opening_volume=relative_opening_volume,
            atr_value=atr_value,
        )
    if variant == "mr_vwap_exhaustion_v1":
        return find_mr_vwap_exhaustion_setup_with_audit(
            session_bars=session_bars,
            cfg=cfg,
            relative_opening_volume=relative_opening_volume,
            atr_value=atr_value,
        )
    if variant == "mr_vwap_zscore_v2":
        return find_mr_vwap_zscore_setup_with_audit(
            session_bars=session_bars,
            cfg=cfg,
            relative_opening_volume=relative_opening_volume,
            atr_value=atr_value,
        )
    if variant == "mr_overnight_regime_v1":
        return _find_mr_overnight_regime_setup_with_audit(
            session_bars=session_bars,
            cfg=cfg,
            relative_opening_volume=relative_opening_volume,
            atr_value=atr_value,
        )
    if variant == "orb_momentum_v1":
        return _find_orb_momentum_setup_with_audit(
            session_bars=session_bars,
            cfg=cfg,
            relative_opening_volume=relative_opening_volume,
            atr_value=atr_value,
        )
    if variant == "orb_vwap_reclaim_v1":
        return _find_orb_vwap_reclaim_setup_with_audit(
            session_bars=session_bars,
            cfg=cfg,
            relative_opening_volume=relative_opening_volume,
            atr_value=atr_value,
        )
    if variant == "opening_exhaustion_reversal_v1":
        return _find_opening_exhaustion_reversal_setup_with_audit(
            session_bars=session_bars,
            cfg=cfg,
            relative_opening_volume=relative_opening_volume,
            atr_value=atr_value,
        )
    if variant == "opening_drive_pullback_v1":
        return _find_opening_drive_pullback_setup_with_audit(
            session_bars=session_bars,
            cfg=cfg,
            relative_opening_volume=relative_opening_volume,
            atr_value=atr_value,
        )
    if variant == "orb_trend_pullback_v1":
        return _find_orb_trend_pullback_setup_with_audit(
            session_bars=session_bars,
            cfg=cfg,
            relative_opening_volume=relative_opening_volume,
            atr_value=atr_value,
        )
    if variant == "orb_event_drive_v1":
        return _find_orb_event_drive_setup_with_audit(
            session_bars=session_bars,
            cfg=cfg,
            relative_opening_volume=relative_opening_volume,
            atr_value=atr_value,
        )
    if variant == "orb_transition_compression_v1":
        return _find_orb_transition_compression_setup_with_audit(
            session_bars=session_bars,
            cfg=cfg,
            relative_opening_volume=relative_opening_volume,
            atr_value=atr_value,
        )
    if variant == "orb_trend_short":
        return _find_orb_trend_short_setup_with_audit(
            session_bars=session_bars,
            cfg=cfg,
            relative_opening_volume=relative_opening_volume,
            atr_value=atr_value,
        )
    if variant == "orb_failure_fade":
        return _find_orb_failure_fade_setup_with_audit(
            session_bars=session_bars,
            cfg=cfg,
            relative_opening_volume=relative_opening_volume,
            atr_value=atr_value,
        )
    if variant == "failed_break_reclaim_v1":
        return _find_failed_break_reclaim_setup_with_audit(
            session_bars=session_bars,
            cfg=cfg,
            relative_opening_volume=relative_opening_volume,
            atr_value=atr_value,
        )
    if variant == "pause_go_continuation_v1":
        return _find_pause_go_continuation_setup_with_audit(
            session_bars=session_bars,
            cfg=cfg,
            relative_opening_volume=relative_opening_volume,
            atr_value=atr_value,
        )
    if variant == "vwap_rollover_short_v1":
        return _find_vwap_rollover_short_setup_with_audit(
            session_bars=session_bars,
            cfg=cfg,
            relative_opening_volume=relative_opening_volume,
            atr_value=atr_value,
        )
    if variant != "orb_fib_pullback":
        return _find_intraday_setup_qc_with_audit(
            session_bars=session_bars,
            cfg=cfg,
            relative_opening_volume=relative_opening_volume,
            atr_value=atr_value,
        )

    audit = {
        "strategy_variant": "orb_fib_pullback",
        "opportunities_before_filters": 0,
        "opportunities_after_filters": 0,
        "rejections": {},
    }
    opening_range_count = max(int(cfg.opening_range_minutes), 1)
    if len(session_bars) < (opening_range_count + 3):
        _inc_reason(audit["rejections"], "insufficient_bars")
        return None, audit

    opening_range = session_bars[:opening_range_count]
    orb_high = max(float(bar.get("high") or 0.0) for bar in opening_range)
    orb_low = min(float(bar.get("low") or 0.0) for bar in opening_range)
    orb_open = float(opening_range[0].get("open") or 0.0)
    orb_close = float(opening_range[-1].get("close") or 0.0)
    if orb_high <= 0 or orb_low <= 0 or orb_high <= orb_low:
        _inc_reason(audit["rejections"], "invalid_opening_range")
        return None, audit
    orb_width_pct = (orb_high - orb_low) / max(orb_open, 1.0)
    if cfg.require_or_width_filter:
        min_width = max(float(cfg.opening_range_min_width_pct), 0.0)
        max_width = max(float(cfg.opening_range_max_width_pct), min_width)
        if orb_width_pct < min_width or orb_width_pct > max_width:
            _inc_reason(audit["rejections"], "orb_width_filter")
            return None, audit

    opening_bar_direction = 0
    if orb_close > orb_open:
        opening_bar_direction = 1
    elif orb_close < orb_open:
        opening_bar_direction = -1

    closes = [float(bar.get("close") or 0.0) for bar in session_bars]
    ema_fast = _ema_series(closes, cfg.trend_ema_fast)
    ema_slow = _ema_series(closes, cfg.trend_ema_slow)
    setup = _find_orb_fib_pullback_setup(
        session_bars=session_bars,
        cfg=cfg,
        opening_range_count=opening_range_count,
        orb_high=orb_high,
        orb_low=orb_low,
        orb_open=orb_open,
        orb_close=orb_close,
        orb_width_pct=orb_width_pct,
        opening_bar_direction=opening_bar_direction,
        ema_fast=ema_fast,
        ema_slow=ema_slow,
        relative_opening_volume=relative_opening_volume,
        atr_value=atr_value,
    )
    if setup is None:
        _inc_reason(audit["rejections"], "fib_no_setup")
        return None, audit
    audit["opportunities_before_filters"] = 1
    audit["opportunities_after_filters"] = 1
    return setup, audit


def find_intraday_setup(
    session_bars: List[Dict[str, Any]],
    cfg: IntradayStrategyConfig,
    relative_opening_volume: Optional[float] = None,
    atr_value: Optional[float] = None,
    pair_session_bars: Optional[List[Dict[str, Any]]] = None,
    lfcm_context: Optional[Dict[str, Any]] = None,
    preopen_context: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    setup, _ = _find_intraday_setup_with_audit(
        session_bars=session_bars,
        cfg=cfg,
        relative_opening_volume=relative_opening_volume,
        atr_value=atr_value,
        pair_session_bars=pair_session_bars,
        lfcm_context=lfcm_context,
        preopen_context=preopen_context,
    )
    return setup


def audit_intraday_funnel(
    session_bars: List[Dict[str, Any]],
    cfg: IntradayStrategyConfig,
    relative_opening_volume: Optional[float] = None,
    atr_value: Optional[float] = None,
    pair_session_bars: Optional[List[Dict[str, Any]]] = None,
    lfcm_context: Optional[Dict[str, Any]] = None,
    preopen_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    setup, audit = _find_intraday_setup_with_audit(
        session_bars=session_bars,
        cfg=cfg,
        relative_opening_volume=relative_opening_volume,
        atr_value=atr_value,
        pair_session_bars=pair_session_bars,
        lfcm_context=lfcm_context,
        preopen_context=preopen_context,
    )
    out = dict(audit)
    out["setup_found"] = bool(setup is not None)
    if setup is not None:
        out["setup_entry_ts"] = setup.get("entry_ts")
        out["setup_signal_ts"] = setup.get("signal_ts")
        out["setup_direction"] = int(setup.get("direction") or 0)
    return out


def resolve_intraday_exit(
    session_bars: List[Dict[str, Any]],
    setup: Dict[str, Any],
    cfg: IntradayStrategyConfig,
    pair_session_bars: Optional[List[Dict[str, Any]]] = None,
) -> Optional[Dict[str, Any]]:
    if not session_bars:
        return None

    strategy_variant = str(setup.get("strategy_variant") or cfg.strategy_variant or "orb_qc").strip().lower()
    if strategy_variant == "lfcm_v1":
        return _resolve_lfcm_exit(session_bars=session_bars, setup=setup, cfg=_LFCMConfig())
    if strategy_variant in {"mr_vwap_revert_v1", "mr_vwap_zscore_v2", "mr_vwap_exhaustion_v1"}:
        return resolve_mr_vwap_exit(session_bars=session_bars, setup=setup, cfg=cfg)
    if strategy_variant == "pairs_spread_v1":
        pair_by_ts = _bar_by_ts(pair_session_bars or [])
        if not pair_by_ts:
            return None
        direction = int(setup.get("direction") or 0)
        entry_idx = int(setup.get("entry_idx") or 0)
        if direction == 0 or entry_idx < 0 or entry_idx >= len(session_bars):
            return None

        entry_underlying = float(setup.get("entry_underlying") or 0.0)
        stop_underlying = float(setup.get("stop_underlying") or 0.0)
        if entry_underlying <= 0 or stop_underlying <= 0:
            return None

        spread_mean = _safe_float(setup.get("pairs_spread_mean"))
        spread_sigma = _safe_float(setup.get("pairs_spread_sigma"))
        beta = _safe_float(setup.get("pairs_beta"))
        z_exit = max(_safe_float(setup.get("pairs_zscore_exit")) or float(cfg.pairs_zscore_exit), 0.0)
        z_stop = max(_safe_float(setup.get("pairs_zscore_stop")) or float(cfg.pairs_zscore_stop), z_exit)
        target_underlying = _safe_float(setup.get("mr_target_underlying"))

        exit_cutoff = _parse_hhmm(cfg.exit_time, "15:55")
        for idx in range(entry_idx, len(session_bars)):
            bar = session_bars[idx]
            bar_time = _to_et_time(bar["ts"])
            open_price = float(bar.get("open") or 0.0)
            high_price = float(bar.get("high") or 0.0)
            low_price = float(bar.get("low") or 0.0)
            close_price = float(bar.get("close") or 0.0)
            if open_price <= 0 or high_price <= 0 or low_price <= 0 or close_price <= 0:
                continue

            if direction > 0 and low_price <= stop_underlying:
                fill = min(stop_underlying, open_price) if open_price > 0 else stop_underlying
                return {
                    "exit_idx": idx,
                    "exit_ts": bar["ts"],
                    "exit_underlying": fill,
                    "exit_reason": "stop_loss",
                }
            if direction < 0 and high_price >= stop_underlying:
                fill = max(stop_underlying, open_price) if open_price > 0 else stop_underlying
                return {
                    "exit_idx": idx,
                    "exit_ts": bar["ts"],
                    "exit_underlying": fill,
                    "exit_reason": "stop_loss",
                }

            if target_underlying is not None:
                if direction > 0 and high_price >= target_underlying:
                    return {
                        "exit_idx": idx,
                        "exit_ts": bar["ts"],
                        "exit_underlying": target_underlying,
                        "exit_reason": "take_profit",
                    }
                if direction < 0 and low_price <= target_underlying:
                    return {
                        "exit_idx": idx,
                        "exit_ts": bar["ts"],
                        "exit_underlying": target_underlying,
                        "exit_reason": "take_profit",
                    }

            if (
                spread_mean is not None
                and spread_sigma is not None
                and spread_sigma > 0
                and beta is not None
            ):
                hedge_close = _pair_close_at(pair_by_ts, bar.get("ts"))
                if hedge_close is not None:
                    spread_now = close_price - (beta * hedge_close)
                    z_now = (spread_now - spread_mean) / spread_sigma
                    if direction > 0 and z_now >= -z_exit:
                        return {
                            "exit_idx": idx,
                            "exit_ts": bar["ts"],
                            "exit_underlying": close_price,
                            "exit_reason": "pairs_mean_revert",
                        }
                    if direction < 0 and z_now <= z_exit:
                        return {
                            "exit_idx": idx,
                            "exit_ts": bar["ts"],
                            "exit_underlying": close_price,
                            "exit_reason": "pairs_mean_revert",
                        }
                    if abs(z_now) >= z_stop:
                        return {
                            "exit_idx": idx,
                            "exit_ts": bar["ts"],
                            "exit_underlying": close_price,
                            "exit_reason": "pairs_zstop",
                        }

            if bar_time >= exit_cutoff:
                return {
                    "exit_idx": idx,
                    "exit_ts": bar["ts"],
                    "exit_underlying": close_price,
                    "exit_reason": "time_exit",
                }
        return None
    if strategy_variant in {"dispersion_relative_breakout_v1", "relative_strength_continuation_v1"}:
        pair_by_ts = _bar_by_ts(pair_session_bars or [])
        if not pair_by_ts:
            return None
        direction = int(setup.get("direction") or 0)
        entry_idx = int(setup.get("entry_idx") or 0)
        if direction == 0 or entry_idx < 0 or entry_idx >= len(session_bars):
            return None

        entry_underlying = float(setup.get("entry_underlying") or 0.0)
        stop_underlying = float(setup.get("stop_underlying") or 0.0)
        primary_ref = _safe_float(setup.get("dispersion_primary_ref"))
        proxy_ref = _safe_float(setup.get("dispersion_proxy_ref"))
        beta = _safe_float(setup.get("dispersion_beta"))
        if entry_underlying <= 0 or stop_underlying <= 0 or primary_ref is None or proxy_ref is None or beta is None:
            return None

        target_underlying = _safe_float(setup.get("mr_target_underlying"))
        edge_exit = max(
            _safe_float(setup.get("dispersion_rel_strength_exit_pct")) or float(cfg.dispersion_rel_strength_exit_pct),
            0.0,
        )
        edge_stop = max(
            _safe_float(setup.get("dispersion_rel_strength_stop_pct")) or float(cfg.dispersion_rel_strength_stop_pct),
            edge_exit,
        )
        beta_shock_max = max(
            _safe_float(setup.get("dispersion_beta_shock_max_pct")) or float(cfg.dispersion_beta_shock_max_pct),
            0.0,
        )
        time_to_work_bars = max(
            int(_safe_float(setup.get("dispersion_time_to_work_bars")) or float(cfg.dispersion_time_to_work_bars)),
            0,
        )
        rel_strength_floor_frac = max(
            _safe_float(setup.get("dispersion_breakout_rel_strength_floor_frac"))
            or float(cfg.dispersion_breakout_rel_strength_floor_frac),
            0.0,
        )
        signal_edge_abs = abs(_safe_float(setup.get("dispersion_rel_strength_at_signal")) or 0.0)
        exit_cutoff = _parse_hhmm(cfg.exit_time, "15:55")
        for idx in range(entry_idx, len(session_bars)):
            bar = session_bars[idx]
            bar_time = _to_et_time(bar["ts"])
            open_price = float(bar.get("open") or 0.0)
            high_price = float(bar.get("high") or 0.0)
            low_price = float(bar.get("low") or 0.0)
            close_price = float(bar.get("close") or 0.0)
            if open_price <= 0 or high_price <= 0 or low_price <= 0 or close_price <= 0:
                continue

            if direction > 0 and low_price <= stop_underlying:
                return {"exit_idx": idx, "exit_ts": bar["ts"], "exit_underlying": stop_underlying, "exit_reason": "stop_loss"}
            if direction < 0 and high_price >= stop_underlying:
                return {"exit_idx": idx, "exit_ts": bar["ts"], "exit_underlying": stop_underlying, "exit_reason": "stop_loss"}

            if target_underlying is not None:
                if direction > 0 and high_price >= target_underlying:
                    return {"exit_idx": idx, "exit_ts": bar["ts"], "exit_underlying": target_underlying, "exit_reason": "take_profit"}
                if direction < 0 and low_price <= target_underlying:
                    return {"exit_idx": idx, "exit_ts": bar["ts"], "exit_underlying": target_underlying, "exit_reason": "take_profit"}

            proxy_close = _pair_close_at(pair_by_ts, bar.get("ts"))
            if proxy_close is not None and primary_ref > 0 and proxy_ref > 0:
                rel_edge = (close_price / primary_ref) - 1.0
                proxy_move = (proxy_close / proxy_ref) - 1.0
                rel_edge -= beta * proxy_move
                if beta_shock_max > 0 and abs(beta * proxy_move) > beta_shock_max:
                    return {
                        "exit_idx": idx,
                        "exit_ts": bar["ts"],
                        "exit_underlying": close_price,
                        "exit_reason": "relative_strength_beta_shock"
                        if strategy_variant == "relative_strength_continuation_v1"
                        else "dispersion_beta_shock",
                    }
                if direction > 0 and rel_edge <= -edge_stop:
                    return {
                        "exit_idx": idx,
                        "exit_ts": bar["ts"],
                        "exit_underlying": close_price,
                        "exit_reason": "relative_strength_stop"
                        if strategy_variant == "relative_strength_continuation_v1"
                        else "dispersion_relative_stop",
                    }
                if direction < 0 and rel_edge >= edge_stop:
                    return {
                        "exit_idx": idx,
                        "exit_ts": bar["ts"],
                        "exit_underlying": close_price,
                        "exit_reason": "relative_strength_stop"
                        if strategy_variant == "relative_strength_continuation_v1"
                        else "dispersion_relative_stop",
                    }
                if direction > 0 and rel_edge <= edge_exit:
                    return {
                        "exit_idx": idx,
                        "exit_ts": bar["ts"],
                        "exit_underlying": close_price,
                        "exit_reason": "relative_strength_fade"
                        if strategy_variant == "relative_strength_continuation_v1"
                        else "dispersion_relative_fade",
                    }
                if direction < 0 and rel_edge >= -edge_exit:
                    return {
                        "exit_idx": idx,
                        "exit_ts": bar["ts"],
                        "exit_underlying": close_price,
                        "exit_reason": "relative_strength_fade"
                        if strategy_variant == "relative_strength_continuation_v1"
                        else "dispersion_relative_fade",
                    }
                if (
                    time_to_work_bars > 0
                    and rel_strength_floor_frac > 0.0
                    and (idx - entry_idx) >= time_to_work_bars
                    and signal_edge_abs > 0.0
                    and abs(rel_edge) < (signal_edge_abs * rel_strength_floor_frac)
                ):
                    return {
                        "exit_idx": idx,
                        "exit_ts": bar["ts"],
                        "exit_underlying": close_price,
                        "exit_reason": "relative_strength_decay"
                        if strategy_variant == "relative_strength_continuation_v1"
                        else "dispersion_relative_decay",
                    }

            if bar_time >= exit_cutoff:
                return {"exit_idx": idx, "exit_ts": bar["ts"], "exit_underlying": close_price, "exit_reason": "time_exit"}
        return None
    if strategy_variant == "proxy_vwap_reclaim_v1":
        pair_by_ts = _bar_by_ts(pair_session_bars or [])
        if not pair_by_ts:
            return None
        pair_idx_by_ts = {
            row.get("ts"): idx for idx, row in enumerate(pair_session_bars or []) if row.get("ts") is not None
        }
        entry_idx = int(setup.get("entry_idx") or 0)
        if entry_idx < 0 or entry_idx >= len(session_bars):
            return None
        entry_underlying = float(setup.get("entry_underlying") or 0.0)
        stop_underlying = float(setup.get("stop_underlying") or 0.0)
        primary_ref = _safe_float(setup.get("proxy_reclaim_primary_ref"))
        proxy_ref = _safe_float(setup.get("proxy_reclaim_proxy_ref"))
        beta = _safe_float(setup.get("proxy_reclaim_beta"))
        if entry_underlying <= 0 or stop_underlying <= 0 or primary_ref is None or proxy_ref is None or beta is None:
            return None
        target_underlying = _safe_float(setup.get("mr_target_underlying"))
        proxy_vwap_series = _running_vwap_series(pair_session_bars or [])
        proxy_closes = [float(row.get("close") or 0.0) for row in (pair_session_bars or [])]
        proxy_ema_fast = _ema_series(proxy_closes, cfg.trend_ema_fast)
        proxy_ema_slow = _ema_series(proxy_closes, cfg.trend_ema_slow)
        primary_vwap_series = _running_vwap_series(session_bars)
        primary_closes = [float(row.get("close") or 0.0) for row in session_bars]
        primary_ema_fast = _ema_series(primary_closes, cfg.trend_ema_fast)
        time_to_work_bars = max(int(_safe_float(setup.get("proxy_reclaim_time_to_work_bars")) or 0), 0)
        time_to_work_price_move = max(float(_safe_float(setup.get("proxy_reclaim_time_to_work_price_move")) or 0.0), 0.0)
        exit_cutoff = _parse_hhmm(cfg.exit_time, "15:55")
        for idx in range(entry_idx, len(session_bars)):
            bar = session_bars[idx]
            bar_time = _to_et_time(bar["ts"])
            open_price = float(bar.get("open") or 0.0)
            high_price = float(bar.get("high") or 0.0)
            low_price = float(bar.get("low") or 0.0)
            close_price = float(bar.get("close") or 0.0)
            if open_price <= 0 or high_price <= 0 or low_price <= 0 or close_price <= 0:
                continue
            if low_price <= stop_underlying:
                return {"exit_idx": idx, "exit_ts": bar["ts"], "exit_underlying": stop_underlying, "exit_reason": "stop_loss"}
            if target_underlying is not None and high_price >= target_underlying:
                return {"exit_idx": idx, "exit_ts": bar["ts"], "exit_underlying": target_underlying, "exit_reason": "take_profit"}

            proxy_close = _pair_close_at(pair_by_ts, bar.get("ts"))
            aligned_proxy_idx = pair_idx_by_ts.get(bar.get("ts"))
            if proxy_close is not None and aligned_proxy_idx is not None:
                proxy_vwap_now = float(proxy_vwap_series[aligned_proxy_idx]) if aligned_proxy_idx < len(proxy_vwap_series) else 0.0
                proxy_ema_fast_now = float(proxy_ema_fast[aligned_proxy_idx]) if aligned_proxy_idx < len(proxy_ema_fast) else 0.0
                proxy_ema_slow_now = float(proxy_ema_slow[aligned_proxy_idx]) if aligned_proxy_idx < len(proxy_ema_slow) else 0.0
                if proxy_vwap_now > 0 and proxy_ema_fast_now > 0 and proxy_ema_slow_now > 0:
                    if proxy_close < max(proxy_vwap_now, proxy_ema_fast_now) or proxy_ema_fast_now < proxy_ema_slow_now:
                        return {
                            "exit_idx": idx,
                            "exit_ts": bar["ts"],
                            "exit_underlying": close_price,
                            "exit_reason": "proxy_strength_lost",
                        }

            primary_vwap_now = float(primary_vwap_series[idx]) if idx < len(primary_vwap_series) else 0.0
            primary_ema_fast_now = float(primary_ema_fast[idx]) if idx < len(primary_ema_fast) else 0.0
            if primary_vwap_now > 0 and primary_ema_fast_now > 0:
                if close_price < min(primary_vwap_now, primary_ema_fast_now):
                    return {
                        "exit_idx": idx,
                        "exit_ts": bar["ts"],
                        "exit_underlying": close_price,
                        "exit_reason": "proxy_reclaim_fail",
                    }

            if time_to_work_bars > 0 and (idx - entry_idx) >= time_to_work_bars and time_to_work_price_move > 0:
                move_pct = (close_price / entry_underlying) - 1.0
                if move_pct < time_to_work_price_move:
                    return {
                        "exit_idx": idx,
                        "exit_ts": bar["ts"],
                        "exit_underlying": close_price,
                        "exit_reason": "proxy_reclaim_decay",
                    }

            if bar_time >= exit_cutoff:
                return {"exit_idx": idx, "exit_ts": bar["ts"], "exit_underlying": close_price, "exit_reason": "time_exit"}
        return None
    if strategy_variant == "dispersion_relative_revert_v1":
        pair_by_ts = _bar_by_ts(pair_session_bars or [])
        if not pair_by_ts:
            return None
        direction = int(setup.get("direction") or 0)
        entry_idx = int(setup.get("entry_idx") or 0)
        if direction == 0 or entry_idx < 0 or entry_idx >= len(session_bars):
            return None

        entry_underlying = float(setup.get("entry_underlying") or 0.0)
        stop_underlying = float(setup.get("stop_underlying") or 0.0)
        if entry_underlying <= 0 or stop_underlying <= 0:
            return None

        spread_mean = _safe_float(setup.get("dispersion_spread_mean"))
        spread_sigma = _safe_float(setup.get("dispersion_spread_sigma"))
        beta = _safe_float(setup.get("dispersion_beta"))
        z_exit = max(_safe_float(setup.get("dispersion_zscore_exit")) or float(cfg.dispersion_zscore_exit), 0.0)
        z_stop = max(_safe_float(setup.get("dispersion_zscore_stop")) or float(cfg.dispersion_zscore_stop), z_exit)
        target_underlying = _safe_float(setup.get("mr_target_underlying"))
        beta_shock_max = max(
            _safe_float(setup.get("dispersion_beta_shock_max_pct")) or float(cfg.dispersion_beta_shock_max_pct),
            0.0,
        )
        time_to_work_bars = max(
            int(_safe_float(setup.get("dispersion_time_to_work_bars")) or float(cfg.dispersion_time_to_work_bars)),
            0,
        )
        time_to_work_improvement_min = max(
            _safe_float(setup.get("dispersion_time_to_work_improvement_min"))
            or float(cfg.dispersion_time_to_work_improvement_min),
            0.0,
        )
        signal_z_abs = abs(_safe_float(setup.get("dispersion_zscore_at_signal")) or 0.0)

        exit_cutoff = _parse_hhmm(cfg.exit_time, "15:55")
        for idx in range(entry_idx, len(session_bars)):
            bar = session_bars[idx]
            bar_time = _to_et_time(bar["ts"])
            open_price = float(bar.get("open") or 0.0)
            high_price = float(bar.get("high") or 0.0)
            low_price = float(bar.get("low") or 0.0)
            close_price = float(bar.get("close") or 0.0)
            if open_price <= 0 or high_price <= 0 or low_price <= 0 or close_price <= 0:
                continue

            if direction > 0 and low_price <= stop_underlying:
                return {"exit_idx": idx, "exit_ts": bar["ts"], "exit_underlying": stop_underlying, "exit_reason": "stop_loss"}
            if direction < 0 and high_price >= stop_underlying:
                return {"exit_idx": idx, "exit_ts": bar["ts"], "exit_underlying": stop_underlying, "exit_reason": "stop_loss"}

            if target_underlying is not None:
                if direction > 0 and high_price >= target_underlying:
                    return {"exit_idx": idx, "exit_ts": bar["ts"], "exit_underlying": target_underlying, "exit_reason": "take_profit"}
                if direction < 0 and low_price <= target_underlying:
                    return {"exit_idx": idx, "exit_ts": bar["ts"], "exit_underlying": target_underlying, "exit_reason": "take_profit"}

            if spread_mean is not None and spread_sigma is not None and spread_sigma > 0 and beta is not None:
                proxy_close = _pair_close_at(pair_by_ts, bar.get("ts"))
                if proxy_close is not None:
                    proxy_ref = _safe_float(setup.get("dispersion_proxy_ref")) or 0.0
                    if proxy_ref > 0 and beta_shock_max > 0:
                        proxy_move = (proxy_close / proxy_ref) - 1.0
                        if abs(beta * proxy_move) > beta_shock_max:
                            return {
                                "exit_idx": idx,
                                "exit_ts": bar["ts"],
                                "exit_underlying": close_price,
                                "exit_reason": "dispersion_beta_shock",
                            }
                    spread_now = close_price - (beta * proxy_close)
                    z_now = (spread_now - spread_mean) / spread_sigma
                    if direction > 0 and z_now >= -z_exit:
                        return {
                            "exit_idx": idx,
                            "exit_ts": bar["ts"],
                            "exit_underlying": close_price,
                            "exit_reason": "dispersion_mean_revert",
                        }
                    if direction < 0 and z_now <= z_exit:
                        return {
                            "exit_idx": idx,
                            "exit_ts": bar["ts"],
                            "exit_underlying": close_price,
                            "exit_reason": "dispersion_mean_revert",
                        }
                    if abs(z_now) >= z_stop:
                        return {
                            "exit_idx": idx,
                            "exit_ts": bar["ts"],
                            "exit_underlying": close_price,
                            "exit_reason": "dispersion_zstop",
                        }
                    if (
                        time_to_work_bars > 0
                        and time_to_work_improvement_min > 0.0
                        and (idx - entry_idx) >= time_to_work_bars
                        and signal_z_abs > 0.0
                        and (signal_z_abs - abs(z_now)) < time_to_work_improvement_min
                    ):
                        return {
                            "exit_idx": idx,
                            "exit_ts": bar["ts"],
                            "exit_underlying": close_price,
                            "exit_reason": "dispersion_revert_stall",
                        }

            if bar_time >= exit_cutoff:
                return {"exit_idx": idx, "exit_ts": bar["ts"], "exit_underlying": close_price, "exit_reason": "time_exit"}
        return None
    if strategy_variant == "mr_overnight_regime_v1":
        entry_underlying = float(setup.get("entry_underlying") or 0.0)
        entry_ts = setup.get("entry_ts")
        overnight_exit_ts = session_bars[-1]["ts"]
        if isinstance(entry_ts, datetime):
            preserve_naive = entry_ts.tzinfo is None
            effective_entry_ts = entry_ts if entry_ts.tzinfo is not None else entry_ts.replace(tzinfo=timezone.utc)
            entry_day_et = effective_entry_ts.astimezone(_ET_ZONE).date()
            overnight_exit_time = _parse_hhmm(str(setup.get("overnight_exit_time") or cfg.exit_time or "09:31"), "09:31")
            overnight_exit_ts = datetime.combine(
                entry_day_et + timedelta(days=max(int(setup.get("overnight_exit_day_offset") or 1), 1)),
                overnight_exit_time,
                tzinfo=_ET_ZONE,
            ).astimezone(timezone.utc)
            if preserve_naive:
                overnight_exit_ts = overnight_exit_ts.replace(tzinfo=None)
        return {
            "exit_idx": int(setup.get("entry_idx") or 0),
            "exit_ts": overnight_exit_ts,
            "exit_underlying": entry_underlying,
            "exit_reason": "overnight_next_open",
            "overnight_exit_day_offset": max(int(setup.get("overnight_exit_day_offset") or 1), 1),
            "overnight_exit_time": str(setup.get("overnight_exit_time") or cfg.exit_time or "09:31"),
        }

    exit_cutoff = _parse_hhmm(cfg.exit_time, "15:55")
    direction = int(setup["direction"])
    entry_idx = int(setup["entry_idx"])
    entry_underlying = float(setup["entry_underlying"])
    stop_underlying = float(setup["stop_underlying"])
    entry_ts = setup.get("entry_ts")

    opposite_min_hold_ts: Optional[datetime] = None
    if isinstance(entry_ts, datetime):
        min_hold = max(int(cfg.opposite_candle_min_hold_minutes), 0)
        opposite_min_hold_ts = entry_ts + timedelta(minutes=min_hold)

    risk_per_share = abs(entry_underlying - stop_underlying)
    break_even_trigger_rr = max(float(cfg.break_even_trigger_rr), 0.0)
    early_fail_minutes = max(int(cfg.early_fail_minutes), 0)
    early_fail_min_rr = float(cfg.early_fail_min_rr)
    max_hold_minutes = max(int(cfg.max_hold_minutes), 0)
    dynamic_stop_underlying = stop_underlying
    break_even_armed = False
    take_profit: Optional[float] = None
    if strategy_variant == "orb_fib_pullback" and cfg.fib_target_extension > 0:
        fib_anchor = _safe_float(setup.get("fib_anchor"))
        fib_impulse_extreme = _safe_float(setup.get("fib_impulse_extreme"))
        if fib_anchor is not None and fib_impulse_extreme is not None:
            if direction > 0 and fib_impulse_extreme > fib_anchor:
                fib_impulse = fib_impulse_extreme - fib_anchor
                take_profit = fib_anchor + (fib_impulse * float(cfg.fib_target_extension))
            if direction < 0 and fib_impulse_extreme < fib_anchor:
                fib_impulse = fib_anchor - fib_impulse_extreme
                take_profit = fib_anchor - (fib_impulse * float(cfg.fib_target_extension))

    if take_profit is None and cfg.take_profit_rr > 0 and risk_per_share > 0:
        take_profit = (
            entry_underlying + (risk_per_share * cfg.take_profit_rr)
            if direction > 0
            else entry_underlying - (risk_per_share * cfg.take_profit_rr)
        )
    trigger_mode = str(cfg.entry_trigger_mode or "close_breakout").strip().lower()
    if trigger_mode == "stop_touch" and 0 <= entry_idx < len(session_bars):
        entry_bar = session_bars[entry_idx]
        entry_open = float(entry_bar.get("open") or 0.0)
        entry_high = float(entry_bar.get("high") or 0.0)
        entry_low = float(entry_bar.get("low") or 0.0)
        entry_close = float(entry_bar.get("close") or 0.0)
        if entry_open > 0 and entry_high > 0 and entry_low > 0 and entry_close > 0:
            if direction > 0 and entry_low <= stop_underlying:
                fill = min(stop_underlying, entry_open) if entry_open > 0 else stop_underlying
                return {
                    "exit_idx": entry_idx,
                    "exit_ts": entry_bar["ts"],
                    "exit_underlying": fill,
                    "exit_reason": "stop_loss",
                }
            if direction < 0 and entry_high >= stop_underlying:
                fill = max(stop_underlying, entry_open) if entry_open > 0 else stop_underlying
                return {
                    "exit_idx": entry_idx,
                    "exit_ts": entry_bar["ts"],
                    "exit_underlying": fill,
                    "exit_reason": "stop_loss",
                }

            if take_profit is not None:
                if direction > 0 and entry_high >= take_profit:
                    return {
                        "exit_idx": entry_idx,
                        "exit_ts": entry_bar["ts"],
                        "exit_underlying": take_profit,
                        "exit_reason": "take_profit",
                    }
                if direction < 0 and entry_low <= take_profit:
                    return {
                        "exit_idx": entry_idx,
                        "exit_ts": entry_bar["ts"],
                        "exit_underlying": take_profit,
                        "exit_reason": "take_profit",
                    }

    for idx in range(entry_idx + 1, len(session_bars)):
        bar = session_bars[idx]
        bar_time = _to_et_time(bar["ts"])
        open_price = float(bar.get("open") or 0.0)
        high_price = float(bar.get("high") or 0.0)
        low_price = float(bar.get("low") or 0.0)
        close_price = float(bar.get("close") or 0.0)
        if open_price <= 0 or high_price <= 0 or low_price <= 0 or close_price <= 0:
            continue

        elapsed_minutes: Optional[float] = None
        if isinstance(entry_ts, datetime) and isinstance(bar.get("ts"), datetime):
            elapsed_minutes = (bar["ts"] - entry_ts).total_seconds() / 60.0

        if direction > 0 and low_price <= dynamic_stop_underlying:
            fill = min(dynamic_stop_underlying, open_price) if open_price > 0 else dynamic_stop_underlying
            return {
                "exit_idx": idx,
                "exit_ts": bar["ts"],
                "exit_underlying": fill,
                "exit_reason": "stop_loss",
            }
        if direction < 0 and high_price >= dynamic_stop_underlying:
            fill = max(dynamic_stop_underlying, open_price) if open_price > 0 else dynamic_stop_underlying
            return {
                "exit_idx": idx,
                "exit_ts": bar["ts"],
                "exit_underlying": fill,
                "exit_reason": "stop_loss",
            }

        if take_profit is not None:
            if direction > 0 and high_price >= take_profit:
                return {
                    "exit_idx": idx,
                    "exit_ts": bar["ts"],
                    "exit_underlying": take_profit,
                    "exit_reason": "take_profit",
                }
            if direction < 0 and low_price <= take_profit:
                return {
                    "exit_idx": idx,
                    "exit_ts": bar["ts"],
                    "exit_underlying": take_profit,
                    "exit_reason": "take_profit",
                }

        if cfg.exit_on_opposite_candle:
            if opposite_min_hold_ts is not None and bar["ts"] < opposite_min_hold_ts:
                pass
            elif direction > 0 and close_price < open_price:
                return {
                    "exit_idx": idx,
                    "exit_ts": bar["ts"],
                    "exit_underlying": close_price,
                    "exit_reason": "opposite_color_candle",
                }
            elif direction < 0 and close_price > open_price:
                return {
                    "exit_idx": idx,
                    "exit_ts": bar["ts"],
                    "exit_underlying": close_price,
                    "exit_reason": "opposite_color_candle",
                }

        if (
            early_fail_minutes > 0
            and elapsed_minutes is not None
            and elapsed_minutes >= float(early_fail_minutes)
            and risk_per_share > 0
        ):
            rr_now = (
                (close_price - entry_underlying) / risk_per_share
                if direction > 0
                else (entry_underlying - close_price) / risk_per_share
            )
            if rr_now < early_fail_min_rr:
                return {
                    "exit_idx": idx,
                    "exit_ts": bar["ts"],
                    "exit_underlying": close_price,
                    "exit_reason": "early_fail_r",
                }

        if (
            max_hold_minutes > 0
            and elapsed_minutes is not None
            and elapsed_minutes >= float(max_hold_minutes)
        ):
            return {
                "exit_idx": idx,
                "exit_ts": bar["ts"],
                "exit_underlying": close_price,
                "exit_reason": "max_hold_time",
            }

        if (
            (not break_even_armed)
            and break_even_trigger_rr > 0
            and risk_per_share > 0
        ):
            trigger_underlying = (
                entry_underlying + (risk_per_share * break_even_trigger_rr)
                if direction > 0
                else entry_underlying - (risk_per_share * break_even_trigger_rr)
            )
            trigger_hit = (
                (direction > 0 and high_price >= trigger_underlying)
                or (direction < 0 and low_price <= trigger_underlying)
            )
            if trigger_hit:
                break_even_armed = True
                if direction > 0:
                    dynamic_stop_underlying = max(dynamic_stop_underlying, entry_underlying)
                else:
                    dynamic_stop_underlying = min(dynamic_stop_underlying, entry_underlying)

        if bar_time >= exit_cutoff:
            return {
                "exit_idx": idx,
                "exit_ts": bar["ts"],
                "exit_underlying": close_price,
                "exit_reason": "time_exit",
            }

    last_bar = session_bars[-1]
    last_close = float(last_bar.get("close") or 0.0)
    if last_close <= 0:
        return None
    return {
        "exit_idx": len(session_bars) - 1,
        "exit_ts": last_bar["ts"],
        "exit_underlying": last_close,
        "exit_reason": "session_close",
    }
