from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List


DEFAULT_OR_WIDTH_MIN = 0.002


@dataclass(frozen=True)
class OrbProfile:
    name: str
    description: str

    opening_range_minutes: int = 5
    entry_start_time: str = "09:35"
    entry_cutoff_time: str = "12:00"
    exit_time: str = "15:55"
    allowed_weekdays_et: str = ""
    strategy_variant: str = "orb_qc"

    allow_long: bool = True
    allow_short: bool = True
    use_opening_bar_direction: bool = False
    require_breakout_open_inside_range: bool = True
    entry_trigger_mode: str = "close_breakout"

    stop_mode: str = "opening_bar_atr"
    stop_loss_atr_distance: float = 1.0
    take_profit_rr: float = 1.0
    break_even_trigger_rr: float = 0.0
    exit_on_opposite_candle: bool = True
    opposite_candle_min_hold_minutes: int = 15
    early_fail_minutes: int = 0
    early_fail_min_rr: float = 0.0
    max_hold_minutes: int = 0
    mr_band_or_mult: float = 1.0
    mr_min_distance_from_vwap_pct: float = 0.0
    mr_reentry_buffer_or_mult: float = 0.1
    mr_stop_buffer_or_mult: float = 0.15
    mr_take_profit_mode: str = "vwap"
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
    fib_entry_level_low: float = 0.5
    fib_entry_level_high: float = 0.618
    fib_target_extension: float = 1.272
    fib_require_confirmation: bool = True
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
    macro_release_times_et: str = "10:00,14:00"
    macro_post_release_block_minutes: int = 20

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

    def to_intraday_strategy_kwargs(self) -> Dict[str, Any]:
        return {
            "opening_range_minutes": int(self.opening_range_minutes),
            "entry_start_time": str(self.entry_start_time),
            "entry_cutoff_time": str(self.entry_cutoff_time),
            "exit_time": str(self.exit_time),
            "allowed_weekdays_et": str(self.allowed_weekdays_et),
            "strategy_variant": str(self.strategy_variant),
            "allow_long": bool(self.allow_long),
            "allow_short": bool(self.allow_short),
            "use_opening_bar_direction": bool(self.use_opening_bar_direction),
            "require_breakout_open_inside_range": bool(self.require_breakout_open_inside_range),
            "entry_trigger_mode": str(self.entry_trigger_mode),
            "stop_mode": str(self.stop_mode),
            "stop_loss_atr_distance": float(self.stop_loss_atr_distance),
            "take_profit_rr": float(self.take_profit_rr),
            "break_even_trigger_rr": float(self.break_even_trigger_rr),
            "exit_on_opposite_candle": bool(self.exit_on_opposite_candle),
            "opposite_candle_min_hold_minutes": int(self.opposite_candle_min_hold_minutes),
            "early_fail_minutes": int(self.early_fail_minutes),
            "early_fail_min_rr": float(self.early_fail_min_rr),
            "max_hold_minutes": int(self.max_hold_minutes),
            "mr_band_or_mult": float(self.mr_band_or_mult),
            "mr_min_distance_from_vwap_pct": float(self.mr_min_distance_from_vwap_pct),
            "mr_reentry_buffer_or_mult": float(self.mr_reentry_buffer_or_mult),
            "mr_stop_buffer_or_mult": float(self.mr_stop_buffer_or_mult),
            "mr_take_profit_mode": str(self.mr_take_profit_mode),
            "mr_take_profit_rr": float(self.mr_take_profit_rr),
            "mr_require_reversal_candle": bool(self.mr_require_reversal_candle),
            "mr_zscore_window": int(self.mr_zscore_window),
            "mr_zscore_entry": float(self.mr_zscore_entry),
            "mr_zscore_reentry": float(self.mr_zscore_reentry),
            "mr_zscore_stop": float(self.mr_zscore_stop),
            "mr_zscore_target": float(self.mr_zscore_target),
            "mr_sigma_min_pct": float(self.mr_sigma_min_pct),
            "mr_sigma_max_pct": float(self.mr_sigma_max_pct),
            "mr_vwap_slope_lookback": int(self.mr_vwap_slope_lookback),
            "mr_vwap_slope_max_pct": float(self.mr_vwap_slope_max_pct),
            "mr_overnight_abs_return_min": float(self.mr_overnight_abs_return_min),
            "mr_overnight_close_to_range_extreme_pct": float(self.mr_overnight_close_to_range_extreme_pct),
            "mr_overnight_efficiency_ratio_max": float(self.mr_overnight_efficiency_ratio_max),
            "mr_overnight_min_session_range_pct": float(self.mr_overnight_min_session_range_pct),
            "mr_adaptive_enabled": bool(self.mr_adaptive_enabled),
            "mr_adaptive_entry_min": float(self.mr_adaptive_entry_min),
            "mr_adaptive_entry_max": float(self.mr_adaptive_entry_max),
            "mr_adaptive_stop_min": float(self.mr_adaptive_stop_min),
            "mr_adaptive_stop_max": float(self.mr_adaptive_stop_max),
            "mr_adaptive_trend_weight": float(self.mr_adaptive_trend_weight),
            "mr_adaptive_vol_weight": float(self.mr_adaptive_vol_weight),
            "mr_session_extension_min_or_frac": float(self.mr_session_extension_min_or_frac),
            "mr_reversal_body_min_frac": float(self.mr_reversal_body_min_frac),
            "mr_reversal_wick_min_frac": float(self.mr_reversal_wick_min_frac),
            "mr_trend_ema_spread_max_pct": float(self.mr_trend_ema_spread_max_pct),
            "mr_volume_climax_multiple_min": float(self.mr_volume_climax_multiple_min),
            "mr_trend_day_max_move_pct": float(self.mr_trend_day_max_move_pct),
            "mr_time_to_work_bars": int(self.mr_time_to_work_bars),
            "mr_time_to_work_min_rr": float(self.mr_time_to_work_min_rr),
            "mr_target_stretch_frac": float(self.mr_target_stretch_frac),
            "pairs_hedge_ticker": str(self.pairs_hedge_ticker),
            "pairs_beta_lookback": int(self.pairs_beta_lookback),
            "pairs_zscore_window": int(self.pairs_zscore_window),
            "pairs_zscore_entry": float(self.pairs_zscore_entry),
            "pairs_zscore_reentry": float(self.pairs_zscore_reentry),
            "pairs_zscore_exit": float(self.pairs_zscore_exit),
            "pairs_zscore_stop": float(self.pairs_zscore_stop),
            "pairs_min_correlation": float(self.pairs_min_correlation),
            "pairs_excluded_tickers": str(self.pairs_excluded_tickers),
            "dispersion_proxy_ticker": str(self.dispersion_proxy_ticker),
            "dispersion_beta_lookback": int(self.dispersion_beta_lookback),
            "dispersion_zscore_window": int(self.dispersion_zscore_window),
            "dispersion_zscore_entry": float(self.dispersion_zscore_entry),
            "dispersion_zscore_reentry": float(self.dispersion_zscore_reentry),
            "dispersion_zscore_exit": float(self.dispersion_zscore_exit),
            "dispersion_zscore_stop": float(self.dispersion_zscore_stop),
            "dispersion_min_correlation": float(self.dispersion_min_correlation),
            "dispersion_rel_strength_entry_pct": float(self.dispersion_rel_strength_entry_pct),
            "dispersion_rel_strength_exit_pct": float(self.dispersion_rel_strength_exit_pct),
            "dispersion_rel_strength_stop_pct": float(self.dispersion_rel_strength_stop_pct),
            "dispersion_primary_min_abs_move_pct": float(self.dispersion_primary_min_abs_move_pct),
            "dispersion_proxy_max_abs_move_pct": float(self.dispersion_proxy_max_abs_move_pct),
            "dispersion_rel_strength_confirm_pct": float(self.dispersion_rel_strength_confirm_pct),
            "dispersion_zscore_improvement_min": float(self.dispersion_zscore_improvement_min),
            "dispersion_reversal_body_min_frac": float(self.dispersion_reversal_body_min_frac),
            "dispersion_reversal_wick_min_frac": float(self.dispersion_reversal_wick_min_frac),
            "dispersion_beta_shock_max_pct": float(self.dispersion_beta_shock_max_pct),
            "dispersion_time_to_work_bars": int(self.dispersion_time_to_work_bars),
            "dispersion_time_to_work_improvement_min": float(self.dispersion_time_to_work_improvement_min),
            "dispersion_breakout_rel_strength_floor_frac": float(self.dispersion_breakout_rel_strength_floor_frac),
            "trend_pullback_max_bars_after_breakout": int(self.trend_pullback_max_bars_after_breakout),
            "trend_pullback_ema_buffer_pct": float(self.trend_pullback_ema_buffer_pct),
            "trend_pullback_require_orb_reclaim": bool(self.trend_pullback_require_orb_reclaim),
            "trend_pullback_min_breakout_or_frac": float(self.trend_pullback_min_breakout_or_frac),
            "trend_pullback_min_volume_multiple": float(self.trend_pullback_min_volume_multiple),
            "drive_min_abs_return_pct": float(self.drive_min_abs_return_pct),
            "drive_close_location_min": float(self.drive_close_location_min),
            "drive_pullback_min_retrace_frac": float(self.drive_pullback_min_retrace_frac),
            "drive_pullback_max_retrace_frac": float(self.drive_pullback_max_retrace_frac),
            "drive_touch_ma_buffer_pct": float(self.drive_touch_ma_buffer_pct),
            "drive_reclaim_close_location_min": float(self.drive_reclaim_close_location_min),
            "drive_reclaim_min_volume_multiple": float(self.drive_reclaim_min_volume_multiple),
            "drive_pullback_require_hold_drive_open": bool(self.drive_pullback_require_hold_drive_open),
            "drive_reclaim_requires_prev_extreme_break": bool(self.drive_reclaim_requires_prev_extreme_break),
            "drive_stop_buffer_range_frac": float(self.drive_stop_buffer_range_frac),
            "drive_max_pullback_bars": int(self.drive_max_pullback_bars),
            "fib_entry_level_low": float(self.fib_entry_level_low),
            "fib_entry_level_high": float(self.fib_entry_level_high),
            "fib_target_extension": float(self.fib_target_extension),
            "fib_require_confirmation": bool(self.fib_require_confirmation),
            "event_gap_abs_return": float(self.event_gap_abs_return),
            "event_gap_direction": int(self.event_gap_direction),
            "event_drive_min_gap_abs_return": float(self.event_drive_min_gap_abs_return),
            "event_drive_min_breakout_or_frac": float(self.event_drive_min_breakout_or_frac),
            "event_drive_close_location_min": float(self.event_drive_close_location_min),
            "event_drive_min_volume_multiple": float(self.event_drive_min_volume_multiple),
            "compression_lookback_bars": int(self.compression_lookback_bars),
            "compression_max_range_pct": float(self.compression_max_range_pct),
            "compression_breakout_buffer_or_frac": float(self.compression_breakout_buffer_or_frac),
            "compression_min_volume_multiple": float(self.compression_min_volume_multiple),
            "momentum_breakout_min_or_frac": float(self.momentum_breakout_min_or_frac),
            "momentum_breakout_max_or_frac": float(self.momentum_breakout_max_or_frac),
            "momentum_close_location_min": float(self.momentum_close_location_min),
            "momentum_min_ema_spread_pct": float(self.momentum_min_ema_spread_pct),
            "momentum_pullback_to_ema_max_pct": float(self.momentum_pullback_to_ema_max_pct),
            "momentum_confirmation_bars": int(self.momentum_confirmation_bars),
            "momentum_volume_multiple_min": float(self.momentum_volume_multiple_min),
            "momentum_min_body_or_frac": float(self.momentum_min_body_or_frac),
            "momentum_max_opposite_wick_body_ratio": float(self.momentum_max_opposite_wick_body_ratio),
            "momentum_atr_range_min": float(self.momentum_atr_range_min),
            "momentum_trend_bars_min": int(self.momentum_trend_bars_min),
            "momentum_adx_period": int(self.momentum_adx_period),
            "momentum_adx_min": float(self.momentum_adx_min),
            "require_relative_volume": bool(self.require_relative_volume),
            "relative_volume_min": float(self.relative_volume_min),
            "relative_volume_max": float(self.relative_volume_max),
            "relative_volume_lookback_days": int(self.relative_volume_lookback_days),
            "require_premarket_context": bool(self.require_premarket_context),
            "premarket_bars_min": int(self.premarket_bars_min),
            "premarket_volume_pct_adv_min": float(self.premarket_volume_pct_adv_min),
            "premarket_gap_abs_return_min": float(self.premarket_gap_abs_return_min),
            "premarket_range_min_pct": float(self.premarket_range_min_pct),
            "premarket_range_max_pct": float(self.premarket_range_max_pct),
            "recent_daily_volume_ratio_min": float(self.recent_daily_volume_ratio_min),
            "require_atr_filter": bool(self.require_atr_filter),
            "atr_lookback_days": int(self.atr_lookback_days),
            "atr_min": float(self.atr_min),
            "volume_ma_window": int(self.volume_ma_window),
            "volume_spike_multiple": float(self.volume_spike_multiple),
            "trend_ema_fast": int(self.trend_ema_fast),
            "trend_ema_slow": int(self.trend_ema_slow),
            "require_fvg": bool(self.require_fvg),
            "require_volume_spike": bool(self.require_volume_spike),
            "require_trend_alignment": bool(self.require_trend_alignment),
            "require_or_width_filter": bool(self.require_or_width_filter),
            "opening_range_min_width_pct": float(self.opening_range_min_width_pct),
            "opening_range_max_width_pct": float(self.opening_range_max_width_pct),
            "require_macro_release_filter": bool(self.require_macro_release_filter),
            "macro_release_times_et": str(self.macro_release_times_et),
            "macro_post_release_block_minutes": int(self.macro_post_release_block_minutes),
            "option_min_open_interest": int(self.option_min_open_interest),
            "require_option_microstructure_filter": bool(self.require_option_microstructure_filter),
            "option_min_entry_volume": int(self.option_min_entry_volume),
            "option_max_entry_bar_range_pct": float(self.option_max_entry_bar_range_pct),
            "option_min_entry_price": float(self.option_min_entry_price),
            "option_selection_use_quote_spread": bool(self.option_selection_use_quote_spread),
            "option_selection_quote_top_n": int(self.option_selection_quote_top_n),
            "option_selection_spread_weight": float(self.option_selection_spread_weight),
            "option_selection_max_quote_spread_pct": float(self.option_selection_max_quote_spread_pct),
            "option_selection_max_quote_spread_abs": float(self.option_selection_max_quote_spread_abs),
            "option_selection_min_quote_ask": float(self.option_selection_min_quote_ask),
            "option_selection_spread_to_ask_weight": float(self.option_selection_spread_to_ask_weight),
            "option_selection_max_spread_to_ask_ratio": float(self.option_selection_max_spread_to_ask_ratio),
            "option_selection_intrinsic_weight": float(self.option_selection_intrinsic_weight),
            "option_selection_min_intrinsic_share": float(self.option_selection_min_intrinsic_share),
            "option_selection_delta_weight": float(self.option_selection_delta_weight),
            "option_selection_target_abs_delta": float(self.option_selection_target_abs_delta),
            "option_selection_min_abs_delta": float(self.option_selection_min_abs_delta),
            "option_selection_max_abs_delta": float(self.option_selection_max_abs_delta),
            "option_selection_delta_fallback_mode": str(self.option_selection_delta_fallback_mode),
            "option_selection_local_itm_steps": int(self.option_selection_local_itm_steps),
            "option_selection_local_otm_steps": int(self.option_selection_local_otm_steps),
            "option_selection_entry_bar_volume_weight": float(self.option_selection_entry_bar_volume_weight),
            "option_selection_quote_mode": str(self.option_selection_quote_mode),
            "option_selection_quote_fallback_last": bool(self.option_selection_quote_fallback_last),
            "option_chain_snapshot_enrichment_mode": str(self.option_chain_snapshot_enrichment_mode),
            "option_risk_sizing_mode": str(self.option_risk_sizing_mode),
            "option_take_profit_pct": float(self.option_take_profit_pct),
            "option_max_loss_pct": float(self.option_max_loss_pct),
            "option_min_expected_move_to_extrinsic_ratio": float(self.option_min_expected_move_to_extrinsic_ratio),
            "option_min_expected_move_to_spread_ratio": float(self.option_min_expected_move_to_spread_ratio),
            "option_min_expected_move_to_debit_ratio": float(self.option_min_expected_move_to_debit_ratio),
            "option_structure_mode": str(self.option_structure_mode),
            "option_vertical_short_leg_steps": int(self.option_vertical_short_leg_steps),
            "option_vertical_fallback_short_leg_steps": int(self.option_vertical_fallback_short_leg_steps),
            "option_vertical_max_debit_to_width_ratio": float(self.option_vertical_max_debit_to_width_ratio),
            "option_vertical_min_short_bid": float(self.option_vertical_min_short_bid),
            "option_vertical_max_combined_spread_to_debit_ratio": float(
                self.option_vertical_max_combined_spread_to_debit_ratio
            ),
            "option_vertical_credit_long_leg_steps": int(self.option_vertical_credit_long_leg_steps),
            "option_vertical_credit_fallback_long_leg_steps": int(
                self.option_vertical_credit_fallback_long_leg_steps
            ),
            "option_vertical_min_credit_to_width_ratio": float(self.option_vertical_min_credit_to_width_ratio),
            "option_vertical_max_credit_to_width_ratio": float(self.option_vertical_max_credit_to_width_ratio),
            "option_vertical_max_combined_spread_to_credit_ratio": float(
                self.option_vertical_max_combined_spread_to_credit_ratio
            ),
            "option_credit_min_short_bid": float(self.option_credit_min_short_bid),
            "option_credit_min_short_strike_buffer_pct": float(self.option_credit_min_short_strike_buffer_pct),
            "option_credit_min_expected_move_buffer_ratio": float(
                self.option_credit_min_expected_move_buffer_ratio
            ),
            "option_credit_min_entry_credit": float(self.option_credit_min_entry_credit),
            "option_credit_take_profit_capture_pct": float(self.option_credit_take_profit_capture_pct),
            "option_credit_stop_loss_multiple": float(self.option_credit_stop_loss_multiple),
            "option_structure_filter_enabled": bool(self.option_structure_filter_enabled),
            "option_structure_min_open_interest": int(self.option_structure_min_open_interest),
            "option_structure_min_entry_volume": int(self.option_structure_min_entry_volume),
            "option_structure_max_entry_spread_pct": float(self.option_structure_max_entry_spread_pct),
            "option_structure_max_entry_bar_range_pct": float(self.option_structure_max_entry_bar_range_pct),
            "option_structure_min_entry_price": float(self.option_structure_min_entry_price),
            "option_sizing_include_commission": bool(self.option_sizing_include_commission),
            "option_sizing_min_entry_price": float(self.option_sizing_min_entry_price),
            "signal_cadence": str(self.signal_cadence),
            "strategy_sleeve": str(self.strategy_sleeve),
            "asset_bucket": str(self.asset_bucket),
            "forecast_group": str(self.forecast_group),
            "forecast_family": str(self.forecast_family),
            "lookback_fast": int(self.lookback_fast),
            "lookback_slow": int(self.lookback_slow),
            "lookback_breakout": int(self.lookback_breakout),
            "lookback_relative": int(self.lookback_relative),
            "forecast_cap": float(self.forecast_cap),
            "vol_attenuation_enabled": bool(self.vol_attenuation_enabled),
            "vol_percentile_lookback": int(self.vol_percentile_lookback),
            "vol_attenuation_hi_pct": float(self.vol_attenuation_hi_pct),
            "vol_attenuation_extreme_pct": float(self.vol_attenuation_extreme_pct),
            "forecast_weight": float(self.forecast_weight),
            "portfolio_target_vol_annualized": float(self.portfolio_target_vol_annualized),
            "premium_at_risk_pct_nav_cap": float(self.premium_at_risk_pct_nav_cap),
            "total_premium_at_risk_pct_nav_cap": float(self.total_premium_at_risk_pct_nav_cap),
            "risk_budget_share": float(self.risk_budget_share),
            "max_calendar_hold_days": int(self.max_calendar_hold_days),
            "option_microstructure_gate_mode": str(self.option_microstructure_gate_mode),
            "option_post_selection_conversion_mode": str(self.option_post_selection_conversion_mode),
            "option_post_selection_max_alternates": int(self.option_post_selection_max_alternates),
            "option_post_selection_max_final_rank": int(self.option_post_selection_max_final_rank),
            "option_post_selection_max_final_strike_distance_steps": int(
                self.option_post_selection_max_final_strike_distance_steps
            ),
            "option_tradability_availability_mode": str(self.option_tradability_availability_mode),
            "option_min_quote_coverage_pct": float(self.option_min_quote_coverage_pct),
            "option_min_chain_coverage_pct": float(self.option_min_chain_coverage_pct),
            "option_liquidity_sampling_days": int(self.option_liquidity_sampling_days),
            "option_cost_speed_limit_ratio": float(self.option_cost_speed_limit_ratio),
            "option_tradeable_after_sample_days": int(self.option_tradeable_after_sample_days),
            "overlay_enabled": bool(self.overlay_enabled),
            "overlay_ivrv_scale_down_zscore": float(self.overlay_ivrv_scale_down_zscore),
            "overlay_ivrv_scale_up_zscore": float(self.overlay_ivrv_scale_up_zscore),
            "overlay_ivrv_scale_down_multiplier": float(self.overlay_ivrv_scale_down_multiplier),
            "overlay_ivrv_scale_up_multiplier": float(self.overlay_ivrv_scale_up_multiplier),
            "overlay_term_structure_veto_threshold": float(self.overlay_term_structure_veto_threshold),
            "overlay_skew_veto_threshold": float(self.overlay_skew_veto_threshold),
            "hybrid_core_weight": float(self.hybrid_core_weight),
            "hybrid_overlay_weight": float(self.hybrid_overlay_weight),
            "hybrid_tactical_weight": float(self.hybrid_tactical_weight),
            "hybrid_tactical_profiles": str(self.hybrid_tactical_profiles),
            "require_vol_regime_filter": bool(self.require_vol_regime_filter),
            "vol_regime_min": float(self.vol_regime_min),
            "vol_regime_max": float(self.vol_regime_max),
            "require_prior_day_inside_bar": bool(self.require_prior_day_inside_bar),
            "require_prior_day_range_filter": bool(self.require_prior_day_range_filter),
            "prior_day_range_max_pct": float(self.prior_day_range_max_pct),
            "regime_v2_enabled": bool(self.regime_v2_enabled),
            "regime_v2_router_enabled": bool(self.regime_v2_router_enabled),
            "regime_v2_router_mode": str(self.regime_v2_router_mode),
            "regime_v2_min_confidence": float(self.regime_v2_min_confidence),
            "regime_v2_router_high_rv_min": float(self.regime_v2_router_high_rv_min),
            "regime_v2_router_trend_up_rv_max": float(self.regime_v2_router_trend_up_rv_max),
            "regime_v2_router_trend_down_rv_max": float(self.regime_v2_router_trend_down_rv_max),
            "regime_v2_router_trend_up_entry_bar_range_min_pct": float(
                self.regime_v2_router_trend_up_entry_bar_range_min_pct
            ),
            "regime_v2_router_trend_down_entry_bar_range_min_pct": float(
                self.regime_v2_router_trend_down_entry_bar_range_min_pct
            ),
            "regime_v2_router_low_confidence_mr_rv_max": float(
                self.regime_v2_router_low_confidence_mr_rv_max
            ),
            "regime_v2_router_low_confidence_mr_entry_bar_range_max_pct": float(
                self.regime_v2_router_low_confidence_mr_entry_bar_range_max_pct
            ),
            "regime_v2_router_low_confidence_skip_rv_min": float(
                self.regime_v2_router_low_confidence_skip_rv_min
            ),
            "regime_v2_router_low_confidence_skip_entry_bar_range_min_pct": float(
                self.regime_v2_router_low_confidence_skip_entry_bar_range_min_pct
            ),
            "regime_v2_router_trend_up_overlay_compression_max_range_pct": float(
                self.regime_v2_router_trend_up_overlay_compression_max_range_pct
            ),
            "regime_v2_router_trend_up_overlay_option_max_entry_bar_range_pct": float(
                self.regime_v2_router_trend_up_overlay_option_max_entry_bar_range_pct
            ),
            "regime_v2_router_event_gap_tight_entry_bar_range_max_pct": float(
                self.regime_v2_router_event_gap_tight_entry_bar_range_max_pct
            ),
            "regime_v2_router_event_gap_mid_rv_min": float(self.regime_v2_router_event_gap_mid_rv_min),
            "regime_v2_router_event_gap_mid_rv_max": float(self.regime_v2_router_event_gap_mid_rv_max),
            "regime_v2_router_event_gap_mid_entry_bar_range_max_pct": float(
                self.regime_v2_router_event_gap_mid_entry_bar_range_max_pct
            ),
            "regime_v2_router_event_gap_overlay_compression_max_range_pct": float(
                self.regime_v2_router_event_gap_overlay_compression_max_range_pct
            ),
            "regime_v2_router_event_gap_overlay_option_max_entry_bar_range_pct": float(
                self.regime_v2_router_event_gap_overlay_option_max_entry_bar_range_pct
            ),
            "regime_v2_router_range_low_vol_tight_rv_max": float(
                self.regime_v2_router_range_low_vol_tight_rv_max
            ),
            "regime_v2_router_range_low_vol_tight_entry_bar_range_max_pct": float(
                self.regime_v2_router_range_low_vol_tight_entry_bar_range_max_pct
            ),
            "regime_v2_router_transition_high_rv_min": float(self.regime_v2_router_transition_high_rv_min),
            "regime_v2_router_transition_wide_entry_bar_range_min_pct": float(
                self.regime_v2_router_transition_wide_entry_bar_range_min_pct
            ),
            "regime_v2_intraday_er_trend_min": float(self.regime_v2_intraday_er_trend_min),
            "regime_v2_intraday_er_sideways_max": float(self.regime_v2_intraday_er_sideways_max),
            "regime_v2_intraday_direction_abs_return_min": float(self.regime_v2_intraday_direction_abs_return_min),
            "regime_v2_range_low_vol_max_pct": float(self.regime_v2_range_low_vol_max_pct),
            "regime_v2_range_high_vol_min_pct": float(self.regime_v2_range_high_vol_min_pct),
            "regime_v2_event_gap_abs_return_min": float(self.regime_v2_event_gap_abs_return_min),
            "regime_v2_event_gap_min_range_pct": float(self.regime_v2_event_gap_min_range_pct),
        }

    def to_confluence_profile_dict(self) -> Dict[str, Any]:
        # Field shape aligned with research.orb_confluence.ConfluenceProfile.
        return {
            "name": str(self.name),
            "require_relative_volume": bool(self.require_relative_volume),
            "relative_volume_min": float(self.relative_volume_min),
            "relative_volume_max": float(self.relative_volume_max),
            "relative_volume_lookback_days": int(self.relative_volume_lookback_days),
            "require_premarket_context": bool(self.require_premarket_context),
            "premarket_bars_min": int(self.premarket_bars_min),
            "premarket_volume_pct_adv_min": float(self.premarket_volume_pct_adv_min),
            "premarket_gap_abs_return_min": float(self.premarket_gap_abs_return_min),
            "premarket_range_min_pct": float(self.premarket_range_min_pct),
            "premarket_range_max_pct": float(self.premarket_range_max_pct),
            "recent_daily_volume_ratio_min": float(self.recent_daily_volume_ratio_min),
            "require_atr_filter": bool(self.require_atr_filter),
            "atr_lookback_days": int(self.atr_lookback_days),
            "atr_min": float(self.atr_min),
            "require_or_width_filter": bool(self.require_or_width_filter),
            "opening_range_min_width_pct": float(self.opening_range_min_width_pct),
            "opening_range_max_width_pct": float(self.opening_range_max_width_pct),
            "require_macro_release_filter": bool(self.require_macro_release_filter),
            "macro_release_times_et": str(self.macro_release_times_et),
            "macro_post_release_block_minutes": int(self.macro_post_release_block_minutes),
            "option_min_open_interest": int(self.option_min_open_interest),
            "require_option_microstructure_filter": bool(self.require_option_microstructure_filter),
            "option_min_dte": int(self.option_min_dte),
            "option_target_dte": int(self.option_target_dte),
            "option_max_dte": int(self.option_max_dte),
            "option_min_entry_volume": int(self.option_min_entry_volume),
            "option_max_entry_bar_range_pct": float(self.option_max_entry_bar_range_pct),
            "option_min_entry_price": float(self.option_min_entry_price),
            "option_selection_use_quote_spread": bool(self.option_selection_use_quote_spread),
            "option_selection_quote_top_n": int(self.option_selection_quote_top_n),
            "option_selection_spread_weight": float(self.option_selection_spread_weight),
            "option_selection_max_quote_spread_pct": float(self.option_selection_max_quote_spread_pct),
            "option_selection_max_quote_spread_abs": float(self.option_selection_max_quote_spread_abs),
            "option_selection_min_quote_ask": float(self.option_selection_min_quote_ask),
            "option_selection_spread_to_ask_weight": float(self.option_selection_spread_to_ask_weight),
            "option_selection_max_spread_to_ask_ratio": float(self.option_selection_max_spread_to_ask_ratio),
            "option_selection_intrinsic_weight": float(self.option_selection_intrinsic_weight),
            "option_selection_min_intrinsic_share": float(self.option_selection_min_intrinsic_share),
            "option_selection_delta_weight": float(self.option_selection_delta_weight),
            "option_selection_target_abs_delta": float(self.option_selection_target_abs_delta),
            "option_selection_min_abs_delta": float(self.option_selection_min_abs_delta),
            "option_selection_max_abs_delta": float(self.option_selection_max_abs_delta),
            "option_selection_delta_fallback_mode": str(self.option_selection_delta_fallback_mode),
            "option_selection_local_itm_steps": int(self.option_selection_local_itm_steps),
            "option_selection_local_otm_steps": int(self.option_selection_local_otm_steps),
            "option_selection_entry_bar_volume_weight": float(self.option_selection_entry_bar_volume_weight),
            "option_selection_quote_mode": str(self.option_selection_quote_mode),
            "option_selection_quote_fallback_last": bool(self.option_selection_quote_fallback_last),
            "option_chain_snapshot_enrichment_mode": str(self.option_chain_snapshot_enrichment_mode),
            "option_risk_sizing_mode": str(self.option_risk_sizing_mode),
            "option_take_profit_pct": float(self.option_take_profit_pct),
            "option_max_loss_pct": float(self.option_max_loss_pct),
            "option_min_expected_move_to_extrinsic_ratio": float(self.option_min_expected_move_to_extrinsic_ratio),
            "option_min_expected_move_to_spread_ratio": float(self.option_min_expected_move_to_spread_ratio),
            "option_min_expected_move_to_debit_ratio": float(self.option_min_expected_move_to_debit_ratio),
            "option_structure_mode": str(self.option_structure_mode),
            "option_vertical_short_leg_steps": int(self.option_vertical_short_leg_steps),
            "option_vertical_fallback_short_leg_steps": int(self.option_vertical_fallback_short_leg_steps),
            "option_vertical_max_debit_to_width_ratio": float(self.option_vertical_max_debit_to_width_ratio),
            "option_vertical_min_short_bid": float(self.option_vertical_min_short_bid),
            "option_vertical_max_combined_spread_to_debit_ratio": float(
                self.option_vertical_max_combined_spread_to_debit_ratio
            ),
            "option_vertical_credit_long_leg_steps": int(self.option_vertical_credit_long_leg_steps),
            "option_vertical_credit_fallback_long_leg_steps": int(
                self.option_vertical_credit_fallback_long_leg_steps
            ),
            "option_vertical_min_credit_to_width_ratio": float(self.option_vertical_min_credit_to_width_ratio),
            "option_vertical_max_credit_to_width_ratio": float(self.option_vertical_max_credit_to_width_ratio),
            "option_vertical_max_combined_spread_to_credit_ratio": float(
                self.option_vertical_max_combined_spread_to_credit_ratio
            ),
            "option_credit_min_short_bid": float(self.option_credit_min_short_bid),
            "option_credit_min_short_strike_buffer_pct": float(self.option_credit_min_short_strike_buffer_pct),
            "option_credit_min_expected_move_buffer_ratio": float(
                self.option_credit_min_expected_move_buffer_ratio
            ),
            "option_credit_min_entry_credit": float(self.option_credit_min_entry_credit),
            "option_credit_take_profit_capture_pct": float(self.option_credit_take_profit_capture_pct),
            "option_credit_stop_loss_multiple": float(self.option_credit_stop_loss_multiple),
            "option_structure_filter_enabled": bool(self.option_structure_filter_enabled),
            "option_structure_min_open_interest": int(self.option_structure_min_open_interest),
            "option_structure_min_entry_volume": int(self.option_structure_min_entry_volume),
            "option_structure_max_entry_spread_pct": float(self.option_structure_max_entry_spread_pct),
            "option_structure_max_entry_bar_range_pct": float(self.option_structure_max_entry_bar_range_pct),
            "option_structure_min_entry_price": float(self.option_structure_min_entry_price),
            "option_sizing_include_commission": bool(self.option_sizing_include_commission),
            "option_sizing_min_entry_price": float(self.option_sizing_min_entry_price),
            "signal_cadence": str(self.signal_cadence),
            "strategy_sleeve": str(self.strategy_sleeve),
            "asset_bucket": str(self.asset_bucket),
            "forecast_group": str(self.forecast_group),
            "forecast_family": str(self.forecast_family),
            "lookback_fast": int(self.lookback_fast),
            "lookback_slow": int(self.lookback_slow),
            "lookback_breakout": int(self.lookback_breakout),
            "lookback_relative": int(self.lookback_relative),
            "forecast_cap": float(self.forecast_cap),
            "vol_attenuation_enabled": bool(self.vol_attenuation_enabled),
            "vol_percentile_lookback": int(self.vol_percentile_lookback),
            "vol_attenuation_hi_pct": float(self.vol_attenuation_hi_pct),
            "vol_attenuation_extreme_pct": float(self.vol_attenuation_extreme_pct),
            "forecast_weight": float(self.forecast_weight),
            "portfolio_target_vol_annualized": float(self.portfolio_target_vol_annualized),
            "premium_at_risk_pct_nav_cap": float(self.premium_at_risk_pct_nav_cap),
            "total_premium_at_risk_pct_nav_cap": float(self.total_premium_at_risk_pct_nav_cap),
            "risk_budget_share": float(self.risk_budget_share),
            "max_calendar_hold_days": int(self.max_calendar_hold_days),
            "option_microstructure_gate_mode": str(self.option_microstructure_gate_mode),
            "option_post_selection_conversion_mode": str(self.option_post_selection_conversion_mode),
            "option_post_selection_max_alternates": int(self.option_post_selection_max_alternates),
            "option_post_selection_max_final_rank": int(self.option_post_selection_max_final_rank),
            "option_post_selection_max_final_strike_distance_steps": int(
                self.option_post_selection_max_final_strike_distance_steps
            ),
            "option_tradability_availability_mode": str(self.option_tradability_availability_mode),
            "option_min_quote_coverage_pct": float(self.option_min_quote_coverage_pct),
            "option_min_chain_coverage_pct": float(self.option_min_chain_coverage_pct),
            "option_liquidity_sampling_days": int(self.option_liquidity_sampling_days),
            "option_cost_speed_limit_ratio": float(self.option_cost_speed_limit_ratio),
            "option_tradeable_after_sample_days": int(self.option_tradeable_after_sample_days),
            "overlay_enabled": bool(self.overlay_enabled),
            "overlay_ivrv_scale_down_zscore": float(self.overlay_ivrv_scale_down_zscore),
            "overlay_ivrv_scale_up_zscore": float(self.overlay_ivrv_scale_up_zscore),
            "overlay_ivrv_scale_down_multiplier": float(self.overlay_ivrv_scale_down_multiplier),
            "overlay_ivrv_scale_up_multiplier": float(self.overlay_ivrv_scale_up_multiplier),
            "overlay_term_structure_veto_threshold": float(self.overlay_term_structure_veto_threshold),
            "overlay_skew_veto_threshold": float(self.overlay_skew_veto_threshold),
            "hybrid_core_weight": float(self.hybrid_core_weight),
            "hybrid_overlay_weight": float(self.hybrid_overlay_weight),
            "hybrid_tactical_weight": float(self.hybrid_tactical_weight),
            "hybrid_tactical_profiles": str(self.hybrid_tactical_profiles),
            "opening_range_minutes": int(self.opening_range_minutes),
            "entry_start_time": str(self.entry_start_time),
            "entry_cutoff_time": str(self.entry_cutoff_time),
            "exit_time": str(self.exit_time),
            "allowed_weekdays_et": str(self.allowed_weekdays_et),
            "strategy_variant": str(self.strategy_variant),
            "allow_long": bool(self.allow_long),
            "allow_short": bool(self.allow_short),
            "use_opening_bar_direction": bool(self.use_opening_bar_direction),
            "require_breakout_open_inside_range": bool(self.require_breakout_open_inside_range),
            "entry_trigger_mode": str(self.entry_trigger_mode),
            "stop_mode": str(self.stop_mode),
            "stop_loss_atr_distance": float(self.stop_loss_atr_distance),
            "take_profit_rr": float(self.take_profit_rr),
            "break_even_trigger_rr": float(self.break_even_trigger_rr),
            "exit_on_opposite_candle": bool(self.exit_on_opposite_candle),
            "opposite_candle_min_hold_minutes": int(self.opposite_candle_min_hold_minutes),
            "early_fail_minutes": int(self.early_fail_minutes),
            "early_fail_min_rr": float(self.early_fail_min_rr),
            "max_hold_minutes": int(self.max_hold_minutes),
            "mr_band_or_mult": float(self.mr_band_or_mult),
            "mr_min_distance_from_vwap_pct": float(self.mr_min_distance_from_vwap_pct),
            "mr_reentry_buffer_or_mult": float(self.mr_reentry_buffer_or_mult),
            "mr_stop_buffer_or_mult": float(self.mr_stop_buffer_or_mult),
            "mr_take_profit_mode": str(self.mr_take_profit_mode),
            "mr_take_profit_rr": float(self.mr_take_profit_rr),
            "mr_require_reversal_candle": bool(self.mr_require_reversal_candle),
            "mr_zscore_window": int(self.mr_zscore_window),
            "mr_zscore_entry": float(self.mr_zscore_entry),
            "mr_zscore_reentry": float(self.mr_zscore_reentry),
            "mr_zscore_stop": float(self.mr_zscore_stop),
            "mr_zscore_target": float(self.mr_zscore_target),
            "mr_sigma_min_pct": float(self.mr_sigma_min_pct),
            "mr_sigma_max_pct": float(self.mr_sigma_max_pct),
            "mr_vwap_slope_lookback": int(self.mr_vwap_slope_lookback),
            "mr_vwap_slope_max_pct": float(self.mr_vwap_slope_max_pct),
            "mr_overnight_abs_return_min": float(self.mr_overnight_abs_return_min),
            "mr_overnight_close_to_range_extreme_pct": float(self.mr_overnight_close_to_range_extreme_pct),
            "mr_overnight_efficiency_ratio_max": float(self.mr_overnight_efficiency_ratio_max),
            "mr_overnight_min_session_range_pct": float(self.mr_overnight_min_session_range_pct),
            "mr_adaptive_enabled": bool(self.mr_adaptive_enabled),
            "mr_adaptive_entry_min": float(self.mr_adaptive_entry_min),
            "mr_adaptive_entry_max": float(self.mr_adaptive_entry_max),
            "mr_adaptive_stop_min": float(self.mr_adaptive_stop_min),
            "mr_adaptive_stop_max": float(self.mr_adaptive_stop_max),
            "mr_adaptive_trend_weight": float(self.mr_adaptive_trend_weight),
            "mr_adaptive_vol_weight": float(self.mr_adaptive_vol_weight),
            "mr_session_extension_min_or_frac": float(self.mr_session_extension_min_or_frac),
            "mr_reversal_body_min_frac": float(self.mr_reversal_body_min_frac),
            "mr_reversal_wick_min_frac": float(self.mr_reversal_wick_min_frac),
            "mr_trend_ema_spread_max_pct": float(self.mr_trend_ema_spread_max_pct),
            "mr_volume_climax_multiple_min": float(self.mr_volume_climax_multiple_min),
            "mr_trend_day_max_move_pct": float(self.mr_trend_day_max_move_pct),
            "mr_time_to_work_bars": int(self.mr_time_to_work_bars),
            "mr_time_to_work_min_rr": float(self.mr_time_to_work_min_rr),
            "mr_target_stretch_frac": float(self.mr_target_stretch_frac),
            "pairs_hedge_ticker": str(self.pairs_hedge_ticker),
            "pairs_beta_lookback": int(self.pairs_beta_lookback),
            "pairs_zscore_window": int(self.pairs_zscore_window),
            "pairs_zscore_entry": float(self.pairs_zscore_entry),
            "pairs_zscore_reentry": float(self.pairs_zscore_reentry),
            "pairs_zscore_exit": float(self.pairs_zscore_exit),
            "pairs_zscore_stop": float(self.pairs_zscore_stop),
            "pairs_min_correlation": float(self.pairs_min_correlation),
            "pairs_excluded_tickers": str(self.pairs_excluded_tickers),
            "dispersion_proxy_ticker": str(self.dispersion_proxy_ticker),
            "dispersion_beta_lookback": int(self.dispersion_beta_lookback),
            "dispersion_zscore_window": int(self.dispersion_zscore_window),
            "dispersion_zscore_entry": float(self.dispersion_zscore_entry),
            "dispersion_zscore_reentry": float(self.dispersion_zscore_reentry),
            "dispersion_zscore_exit": float(self.dispersion_zscore_exit),
            "dispersion_zscore_stop": float(self.dispersion_zscore_stop),
            "dispersion_min_correlation": float(self.dispersion_min_correlation),
            "dispersion_rel_strength_entry_pct": float(self.dispersion_rel_strength_entry_pct),
            "dispersion_rel_strength_exit_pct": float(self.dispersion_rel_strength_exit_pct),
            "dispersion_rel_strength_stop_pct": float(self.dispersion_rel_strength_stop_pct),
            "dispersion_primary_min_abs_move_pct": float(self.dispersion_primary_min_abs_move_pct),
            "dispersion_proxy_max_abs_move_pct": float(self.dispersion_proxy_max_abs_move_pct),
            "dispersion_rel_strength_confirm_pct": float(self.dispersion_rel_strength_confirm_pct),
            "dispersion_zscore_improvement_min": float(self.dispersion_zscore_improvement_min),
            "dispersion_reversal_body_min_frac": float(self.dispersion_reversal_body_min_frac),
            "dispersion_reversal_wick_min_frac": float(self.dispersion_reversal_wick_min_frac),
            "dispersion_beta_shock_max_pct": float(self.dispersion_beta_shock_max_pct),
            "dispersion_time_to_work_bars": int(self.dispersion_time_to_work_bars),
            "dispersion_time_to_work_improvement_min": float(self.dispersion_time_to_work_improvement_min),
            "dispersion_breakout_rel_strength_floor_frac": float(self.dispersion_breakout_rel_strength_floor_frac),
            "trend_pullback_max_bars_after_breakout": int(self.trend_pullback_max_bars_after_breakout),
            "trend_pullback_ema_buffer_pct": float(self.trend_pullback_ema_buffer_pct),
            "trend_pullback_require_orb_reclaim": bool(self.trend_pullback_require_orb_reclaim),
            "trend_pullback_min_breakout_or_frac": float(self.trend_pullback_min_breakout_or_frac),
            "trend_pullback_min_volume_multiple": float(self.trend_pullback_min_volume_multiple),
            "drive_min_abs_return_pct": float(self.drive_min_abs_return_pct),
            "drive_close_location_min": float(self.drive_close_location_min),
            "drive_pullback_min_retrace_frac": float(self.drive_pullback_min_retrace_frac),
            "drive_pullback_max_retrace_frac": float(self.drive_pullback_max_retrace_frac),
            "drive_touch_ma_buffer_pct": float(self.drive_touch_ma_buffer_pct),
            "drive_reclaim_close_location_min": float(self.drive_reclaim_close_location_min),
            "drive_reclaim_min_volume_multiple": float(self.drive_reclaim_min_volume_multiple),
            "drive_pullback_require_hold_drive_open": bool(self.drive_pullback_require_hold_drive_open),
            "drive_reclaim_requires_prev_extreme_break": bool(self.drive_reclaim_requires_prev_extreme_break),
            "drive_stop_buffer_range_frac": float(self.drive_stop_buffer_range_frac),
            "drive_max_pullback_bars": int(self.drive_max_pullback_bars),
            "fib_entry_level_low": float(self.fib_entry_level_low),
            "fib_entry_level_high": float(self.fib_entry_level_high),
            "fib_target_extension": float(self.fib_target_extension),
            "fib_require_confirmation": bool(self.fib_require_confirmation),
            "event_gap_abs_return": float(self.event_gap_abs_return),
            "event_gap_direction": int(self.event_gap_direction),
            "event_drive_min_gap_abs_return": float(self.event_drive_min_gap_abs_return),
            "event_drive_min_breakout_or_frac": float(self.event_drive_min_breakout_or_frac),
            "event_drive_close_location_min": float(self.event_drive_close_location_min),
            "event_drive_min_volume_multiple": float(self.event_drive_min_volume_multiple),
            "compression_lookback_bars": int(self.compression_lookback_bars),
            "compression_max_range_pct": float(self.compression_max_range_pct),
            "compression_breakout_buffer_or_frac": float(self.compression_breakout_buffer_or_frac),
            "compression_min_volume_multiple": float(self.compression_min_volume_multiple),
            "momentum_breakout_min_or_frac": float(self.momentum_breakout_min_or_frac),
            "momentum_breakout_max_or_frac": float(self.momentum_breakout_max_or_frac),
            "momentum_close_location_min": float(self.momentum_close_location_min),
            "momentum_min_ema_spread_pct": float(self.momentum_min_ema_spread_pct),
            "momentum_pullback_to_ema_max_pct": float(self.momentum_pullback_to_ema_max_pct),
            "momentum_confirmation_bars": int(self.momentum_confirmation_bars),
            "momentum_volume_multiple_min": float(self.momentum_volume_multiple_min),
            "momentum_min_body_or_frac": float(self.momentum_min_body_or_frac),
            "momentum_max_opposite_wick_body_ratio": float(self.momentum_max_opposite_wick_body_ratio),
            "momentum_atr_range_min": float(self.momentum_atr_range_min),
            "momentum_trend_bars_min": int(self.momentum_trend_bars_min),
            "momentum_adx_period": int(self.momentum_adx_period),
            "momentum_adx_min": float(self.momentum_adx_min),
            "require_vol_regime_filter": bool(self.require_vol_regime_filter),
            "vol_regime_min": float(self.vol_regime_min),
            "vol_regime_max": float(self.vol_regime_max),
            "volume_ma_window": int(self.volume_ma_window),
            "volume_spike_multiple": float(self.volume_spike_multiple),
            "trend_ema_fast": int(self.trend_ema_fast),
            "trend_ema_slow": int(self.trend_ema_slow),
            "require_fvg": bool(self.require_fvg),
            "require_volume_spike": bool(self.require_volume_spike),
            "require_trend_alignment": bool(self.require_trend_alignment),
            "require_prior_day_inside_bar": bool(self.require_prior_day_inside_bar),
            "require_prior_day_range_filter": bool(self.require_prior_day_range_filter),
            "prior_day_range_max_pct": float(self.prior_day_range_max_pct),
            "regime_v2_enabled": bool(self.regime_v2_enabled),
            "regime_v2_router_enabled": bool(self.regime_v2_router_enabled),
            "regime_v2_router_mode": str(self.regime_v2_router_mode),
            "regime_v2_min_confidence": float(self.regime_v2_min_confidence),
            "regime_v2_router_high_rv_min": float(self.regime_v2_router_high_rv_min),
            "regime_v2_router_trend_up_rv_max": float(self.regime_v2_router_trend_up_rv_max),
            "regime_v2_router_trend_down_rv_max": float(self.regime_v2_router_trend_down_rv_max),
            "regime_v2_router_trend_up_entry_bar_range_min_pct": float(
                self.regime_v2_router_trend_up_entry_bar_range_min_pct
            ),
            "regime_v2_router_trend_down_entry_bar_range_min_pct": float(
                self.regime_v2_router_trend_down_entry_bar_range_min_pct
            ),
            "regime_v2_router_low_confidence_mr_rv_max": float(
                self.regime_v2_router_low_confidence_mr_rv_max
            ),
            "regime_v2_router_low_confidence_mr_entry_bar_range_max_pct": float(
                self.regime_v2_router_low_confidence_mr_entry_bar_range_max_pct
            ),
            "regime_v2_router_low_confidence_skip_rv_min": float(
                self.regime_v2_router_low_confidence_skip_rv_min
            ),
            "regime_v2_router_low_confidence_skip_entry_bar_range_min_pct": float(
                self.regime_v2_router_low_confidence_skip_entry_bar_range_min_pct
            ),
            "regime_v2_router_trend_up_overlay_compression_max_range_pct": float(
                self.regime_v2_router_trend_up_overlay_compression_max_range_pct
            ),
            "regime_v2_router_trend_up_overlay_option_max_entry_bar_range_pct": float(
                self.regime_v2_router_trend_up_overlay_option_max_entry_bar_range_pct
            ),
            "regime_v2_router_event_gap_tight_entry_bar_range_max_pct": float(
                self.regime_v2_router_event_gap_tight_entry_bar_range_max_pct
            ),
            "regime_v2_router_event_gap_mid_rv_min": float(self.regime_v2_router_event_gap_mid_rv_min),
            "regime_v2_router_event_gap_mid_rv_max": float(self.regime_v2_router_event_gap_mid_rv_max),
            "regime_v2_router_event_gap_mid_entry_bar_range_max_pct": float(
                self.regime_v2_router_event_gap_mid_entry_bar_range_max_pct
            ),
            "regime_v2_router_event_gap_overlay_compression_max_range_pct": float(
                self.regime_v2_router_event_gap_overlay_compression_max_range_pct
            ),
            "regime_v2_router_event_gap_overlay_option_max_entry_bar_range_pct": float(
                self.regime_v2_router_event_gap_overlay_option_max_entry_bar_range_pct
            ),
            "regime_v2_router_range_low_vol_tight_rv_max": float(
                self.regime_v2_router_range_low_vol_tight_rv_max
            ),
            "regime_v2_router_range_low_vol_tight_entry_bar_range_max_pct": float(
                self.regime_v2_router_range_low_vol_tight_entry_bar_range_max_pct
            ),
            "regime_v2_router_transition_high_rv_min": float(self.regime_v2_router_transition_high_rv_min),
            "regime_v2_router_transition_wide_entry_bar_range_min_pct": float(
                self.regime_v2_router_transition_wide_entry_bar_range_min_pct
            ),
            "regime_v2_intraday_er_trend_min": float(self.regime_v2_intraday_er_trend_min),
            "regime_v2_intraday_er_sideways_max": float(self.regime_v2_intraday_er_sideways_max),
            "regime_v2_intraday_direction_abs_return_min": float(self.regime_v2_intraday_direction_abs_return_min),
            "regime_v2_range_low_vol_max_pct": float(self.regime_v2_range_low_vol_max_pct),
            "regime_v2_range_high_vol_min_pct": float(self.regime_v2_range_high_vol_min_pct),
            "regime_v2_event_gap_abs_return_min": float(self.regime_v2_event_gap_abs_return_min),
            "regime_v2_event_gap_min_range_pct": float(self.regime_v2_event_gap_min_range_pct),
        }

    def to_export_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["intraday_strategy_kwargs"] = self.to_intraday_strategy_kwargs()
        payload["confluence_profile"] = self.to_confluence_profile_dict()
        return payload


OpeningRangeProfile = OrbProfile
