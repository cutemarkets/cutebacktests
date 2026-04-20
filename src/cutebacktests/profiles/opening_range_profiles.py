from __future__ import annotations

from dataclasses import replace
from typing import Any, List

from .opening_range_profiles_core import DEFAULT_OR_WIDTH_MIN, OrbProfile
from .opening_range_profiles_family_carver import (
    _carver_daily_profile,
    apply_carver_daily_wrapper_v1,
    c40_carver_daily_candidates_v1,
    c40_daily_ewmac_fast_v1,
    c41_daily_ewmac_slow_v1,
    c42_daily_breakout_medium_v1,
    c43_daily_breakout_slow_v1,
    c52_daily_trend_pullback_v1,
    c44_daily_relmom_bucket_v1,
    c45_daily_assettrend_bucket_v1,
    c46_surface_ivrv_overlay_v1,
    c47_surface_term_structure_overlay_v1,
    c48_surface_skew_overlay_v1,
    c50_carver_core_combo_v1,
    c51_carver_hybrid_portfolio_v1,
)
from .opening_range_profiles_family_option_structure import (
    c17_option_structure_strength_balance_v1,
    c17_option_structure_strength_candidates,
    c17_option_structure_strength_opportunity_v1,
    c17_option_structure_strength_quality_v1,
    c17_option_structure_strength_regime_v1,
)


def c40_carver_complement_candidates_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> List[OrbProfile]:
    return [
        c44_daily_relmom_bucket_v1(or_width_min=or_width_min),
        c45_daily_assettrend_bucket_v1(or_width_min=or_width_min),
        c50_carver_core_combo_v1(or_width_min=or_width_min),
        c51_carver_hybrid_portfolio_v1(or_width_min=or_width_min),
    ]


def c4_long_only_rr15(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    return OrbProfile(
        name="c4_long_only_rr15",
        description=(
            "Primary ORB profile: long-only 5-minute opening range breakout, "
            "OR-width guard, 1.5R target, opposite-color exit."
        ),
        require_or_width_filter=True,
        opening_range_min_width_pct=max(float(or_width_min), 0.0),
        opening_range_max_width_pct=0.02,
        allow_short=False,
        entry_trigger_mode="close_breakout",
        take_profit_rr=1.5,
    )


def c4_rr15_r1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_long_only_rr15(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_rr15_r1",
        description=(
            "RR15 r1 variant: slightly looser ORB gate and RVOL with 1.4R profit target."
        ),
        opening_range_min_width_pct=max(float(or_width_min), 0.0015),
        require_relative_volume=True,
        relative_volume_min=0.95,
        take_profit_rr=1.4,
    )


def c4_long_only_rr15_defensive_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_long_only_rr15(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_long_only_rr15_defensive_v1",
        description=(
            "Defensive C4 long-only profile: stricter ORB quality filters plus break-even and "
            "time-based defensive exits for better live robustness."
        ),
        require_or_width_filter=True,
        opening_range_min_width_pct=max(float(or_width_min), 0.003),
        opening_range_max_width_pct=0.02,
        require_relative_volume=True,
        relative_volume_min=1.2,
        require_trend_alignment=True,
        require_volume_spike=True,
        volume_spike_multiple=1.3,
        require_option_microstructure_filter=True,
        option_min_open_interest=1000,
        option_min_entry_volume=75,
        option_max_entry_bar_range_pct=0.25,
        option_min_entry_price=0.8,
        break_even_trigger_rr=0.8,
        early_fail_minutes=45,
        early_fail_min_rr=0.15,
        max_hold_minutes=120,
        opposite_candle_min_hold_minutes=10,
        take_profit_rr=1.5,
    )


def c4_long_only_rr15_recovery_v2(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_long_only_rr15(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_long_only_rr15_recovery_v2",
        description=(
            "Post-leakage breakout recovery profile: keep the long-only ORB structure, but relax the "
            "open-inside gate and slightly widen the hold horizon so causal next-bar entries still produce enough trades."
        ),
        require_breakout_open_inside_range=False,
        opening_range_min_width_pct=max(float(or_width_min) * 0.85, 0.0016),
        require_relative_volume=True,
        relative_volume_min=0.90,
        take_profit_rr=1.35,
        early_fail_minutes=35,
        early_fail_min_rr=0.08,
        max_hold_minutes=75,
    )


def c4_long_only_rr15_openany_tight_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_long_only_rr15(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_long_only_rr15_openany_tight_v1",
        description=(
            "C4 long-only variant with breakout-open-inside-range gate disabled to reduce over-filtering, "
            "plus modest OR-width and RVOL tightening to keep entry quality."
        ),
        require_breakout_open_inside_range=False,
        opening_range_min_width_pct=max(float(or_width_min), 0.0025),
        require_relative_volume=True,
        relative_volume_min=1.1,
    )


def c4_long_only_rr15_pocket_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_long_only_rr15_recovery_v2(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_long_only_rr15_pocket_v1",
        description=(
            "Phase88 breakout pocket v1: causal long-only ORB around the validated discovery cluster "
            "(OR width 0.24%, RVOL 0.90, 1.4R target, 80 minute hold)."
        ),
        opening_range_min_width_pct=max(float(or_width_min), 0.0024),
        require_relative_volume=True,
        relative_volume_min=0.90,
        take_profit_rr=1.40,
        max_hold_minutes=80,
    )


def c4_long_only_rr15_pocket_v2(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_long_only_rr15_recovery_v2(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_long_only_rr15_pocket_v2",
        description=(
            "Phase88 breakout pocket v2: slightly wider/stronger breakout cluster "
            "(OR width 0.25%, RVOL 0.95, 1.45R target, 85 minute hold)."
        ),
        opening_range_min_width_pct=max(float(or_width_min), 0.0025),
        require_relative_volume=True,
        relative_volume_min=0.95,
        take_profit_rr=1.45,
        max_hold_minutes=85,
    )


def c4_long_only_rr15_openany_pocket_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_long_only_rr15_openany_tight_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_long_only_rr15_openany_pocket_v1",
        description=(
            "Phase88 open-any pocket: breakout-open-inside disabled, but aligned to the validated "
            "higher-width/higher-RVOL cluster for faster post-fix discovery."
        ),
        opening_range_min_width_pct=max(float(or_width_min), 0.0024),
        require_relative_volume=True,
        relative_volume_min=0.90,
        take_profit_rr=1.40,
        max_hold_minutes=80,
    )


def c4_long_slip10_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_long_only_rr15(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_long_slip10_v1",
        description=(
            "Cost-aware C4 variant: disable opposite-candle exits, keep long-only OR-width guard, "
            "and target 2.0R so average trade edge can absorb slippage."
        ),
        take_profit_rr=2.0,
        exit_on_opposite_candle=False,
    )


def c4_long_slip10_strict_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_long_slip10_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_long_slip10_strict_v1",
        description=(
            "Cost-aware strict C4 variant: no opposite-candle exit, 2.0R target, "
            "wider minimum opening range (0.30%) and stronger RVOL floor (1.2)."
        ),
        require_or_width_filter=True,
        opening_range_min_width_pct=max(float(or_width_min), 0.003),
        opening_range_max_width_pct=0.02,
        require_relative_volume=True,
        relative_volume_min=1.2,
    )


def c4_orw30_rvol12_noopp_rr20(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    strict = c4_long_slip10_strict_v1(or_width_min=or_width_min)
    return replace(
        strict,
        name="c4_orw30_rvol12_noopp_rr20",
        description=(
            "Research profile alias: long-only RR2.0 with no opposite-candle exit, "
            "minimum OR width 0.30% and RVOL floor 1.2."
        ),
        max_hold_minutes=30,
    )


def c4_orw25_rvol12_noopp_rr20(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    strict = c4_long_slip10_strict_v1(or_width_min=or_width_min)
    return replace(
        strict,
        name="c4_orw25_rvol12_noopp_rr20",
        description=(
            "Frequency-tuned research profile: long-only RR2.0 with no opposite-candle exit, "
            "minimum OR width 0.25% and RVOL floor 1.2."
        ),
        opening_range_min_width_pct=max(float(or_width_min), 0.0025),
        max_hold_minutes=30,
    )


def c4_orw30_rvol12_noopp_rr20_openany(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    strict = c4_orw30_rvol12_noopp_rr20(or_width_min=or_width_min)
    return replace(
        strict,
        name="c4_orw30_rvol12_noopp_rr20_openany",
        description=(
            "Live-debug variant of c4_orw30_rvol12_noopp_rr20 with breakout-open-inside-range "
            "gate disabled to increase entry frequency."
        ),
        require_breakout_open_inside_range=False,
    )


def c4_orw25_rvol12_noopp_rr20_openany(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    strict = c4_orw25_rvol12_noopp_rr20(or_width_min=or_width_min)
    return replace(
        strict,
        name="c4_orw25_rvol12_noopp_rr20_openany",
        description=(
            "Frequency-tuned c4_orw25_rvol12_noopp_rr20 with breakout-open-inside-range gate disabled."
        ),
        require_breakout_open_inside_range=False,
    )


def c4_orw25_rvol12_noopp_rr20_stop_touch_openany(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_orw25_rvol12_noopp_rr20_openany(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_orw25_rvol12_noopp_rr20_stop_touch_openany",
        description=(
            "Open-any long-only variant with stop-touch trigger to reduce missed momentum entries."
        ),
        entry_trigger_mode="stop_touch",
    )


def c4_orw25_rvol12_noopp_rr20_stop_touch_realism(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_orw25_rvol12_noopp_rr20(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_orw25_rvol12_noopp_rr20_stop_touch_realism",
        description=(
            "Production realism variant: stop-touch trigger plus option microstructure guards "
            "(OI/entry-volume/entry-range/entry-price)."
        ),
        entry_trigger_mode="stop_touch",
        option_min_open_interest=500,
        require_option_microstructure_filter=True,
        option_min_entry_volume=25,
        option_max_entry_bar_range_pct=0.35,
        option_min_entry_price=0.5,
    )


def c4_orw25_rvol12_noopp_rr20_ls_openany(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_orw25_rvol12_noopp_rr20_openany(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_orw25_rvol12_noopp_rr20_ls_openany",
        description=(
            "Open-any long+short variant (calls and puts) for higher trade frequency."
        ),
        allow_short=True,
    )


def c4_freq_v1() -> OrbProfile:
    return OrbProfile(
        name="c4_freq_v1",
        description=(
            "Higher-frequency C4 profile: long-only close-breakout, "
            "relaxed OR-width floor (0.10%) and relaxed RVOL floor (0.8)."
        ),
        require_or_width_filter=True,
        opening_range_min_width_pct=0.001,
        opening_range_max_width_pct=0.02,
        allow_short=False,
        entry_trigger_mode="close_breakout",
        take_profit_rr=1.5,
        require_relative_volume=True,
        relative_volume_min=0.8,
    )


def c4_freq_v1_f4() -> OrbProfile:
    base = c4_freq_v1()
    return replace(
        base,
        name="c4_freq_v1_f4",
        description=(
            "Frequency f4 variant: late entry cutoff, longer hold cap, and 1.8R take-profit."
        ),
        entry_cutoff_time="12:30",
        max_hold_minutes=60,
        take_profit_rr=1.8,
    )


def c4_freq_breakout_hybrid_v1() -> OrbProfile:
    base = c4_freq_v1_f4()
    return replace(
        base,
        name="c4_freq_breakout_hybrid_v1",
        description=(
            "Phase88 freq/breakout hybrid v1: keeps the later frequency profile timing, but uses "
            "the validated breakout pocket width/RVOL/target settings."
        ),
        opening_range_min_width_pct=0.0024,
        require_relative_volume=True,
        relative_volume_min=0.90,
        take_profit_rr=1.40,
        max_hold_minutes=80,
    )


def c4_freq_breakout_hybrid_v2() -> OrbProfile:
    base = c4_freq_v1_f4()
    return replace(
        base,
        name="c4_freq_breakout_hybrid_v2",
        description=(
            "Phase88 freq/breakout hybrid v2: slightly wider, higher-RVOL breakout pocket with the "
            "frequency-friendly cutoff and hold structure."
        ),
        opening_range_min_width_pct=0.0025,
        require_relative_volume=True,
        relative_volume_min=0.95,
        take_profit_rr=1.45,
        max_hold_minutes=85,
    )


def c4_long_only_rr15_quote_guard_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_long_only_rr15_openany_tight_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_long_only_rr15_quote_guard_v1",
        description=(
            "Quote-aware breakout control with tighter option microstructure constraints and slightly "
            "faster monetization to survive realistic bid/ask execution."
        ),
        take_profit_rr=1.20,
        max_hold_minutes=45,
        require_option_microstructure_filter=True,
        option_min_open_interest=750,
        option_min_entry_volume=75,
        option_max_entry_bar_range_pct=0.25,
        option_min_entry_price=0.60,
    )


def c4_freq_breakout_quote_guard_v1() -> OrbProfile:
    base = c4_freq_breakout_hybrid_v1()
    return replace(
        base,
        name="c4_freq_breakout_quote_guard_v1",
        description=(
            "Quote-aware higher-frequency breakout control with tighter option microstructure filters "
            "and faster monetization for spread-sensitive execution."
        ),
        take_profit_rr=1.10,
        max_hold_minutes=40,
        require_option_microstructure_filter=True,
        option_min_open_interest=750,
        option_min_entry_volume=75,
        option_max_entry_bar_range_pct=0.25,
        option_min_entry_price=0.60,
    )


def c4_freq_ls_v1() -> OrbProfile:
    base = c4_freq_v1()
    return replace(
        base,
        name="c4_freq_ls_v1",
        description=(
            "Higher-frequency C4 profile with both directions enabled "
            "(long calls and long puts)."
        ),
        allow_short=True,
    )


def c4_freq_ls_trend_v1() -> OrbProfile:
    base = c4_freq_ls_v1()
    return replace(
        base,
        name="c4_freq_ls_trend_v1",
        description=(
            "Higher-frequency long+short profile with trend-alignment and "
            "moderate volatility-regime guards."
        ),
        require_trend_alignment=True,
        require_vol_regime_filter=True,
        vol_regime_min=12.0,
        vol_regime_max=35.0,
    )


def c4_orb_trend_short_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_orw25_rvol12_noopp_rr20(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_orb_trend_short_v1",
        description=(
            "Trend-following short-only ORB profile for downside momentum days "
            "(long puts only)."
        ),
        strategy_variant="orb_trend_short",
        allow_long=False,
        allow_short=True,
        take_profit_rr=1.5,
        require_breakout_open_inside_range=False,
        max_hold_minutes=45,
    )


def c4_orb_failure_fade_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    _ = or_width_min
    return OrbProfile(
        name="c4_orb_failure_fade_v1",
        description=(
            "Fade failed ORB breakouts back into range (both directions), aimed at choppy sessions."
        ),
        strategy_variant="orb_failure_fade",
        require_or_width_filter=True,
        opening_range_min_width_pct=0.001,
        opening_range_max_width_pct=0.03,
        allow_long=True,
        allow_short=True,
        require_breakout_open_inside_range=False,
        entry_trigger_mode="close_breakout",
        stop_mode="breakout_candle",
        take_profit_rr=1.0,
        exit_on_opposite_candle=True,
        opposite_candle_min_hold_minutes=5,
        require_relative_volume=True,
        relative_volume_min=0.9,
    )


def c4_orb_momentum_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    return OrbProfile(
        name="c4_orb_momentum_v1",
        description=(
            "Momentum-continuation ORB profile for trend sessions: breakout-strength, "
            "volume-spike, and EMA-trend confirmation before entry (long calls + long puts)."
        ),
        strategy_variant="orb_momentum_v1",
        require_or_width_filter=True,
        opening_range_min_width_pct=max(float(or_width_min), 0.002),
        opening_range_max_width_pct=0.03,
        allow_short=True,
        require_breakout_open_inside_range=False,
        entry_trigger_mode="close_breakout",
        stop_mode="opening_bar_atr",
        stop_loss_atr_distance=1.0,
        take_profit_rr=2.0,
        exit_on_opposite_candle=True,
        opposite_candle_min_hold_minutes=8,
        max_hold_minutes=75,
        require_relative_volume=True,
        relative_volume_min=1.1,
        require_volume_spike=True,
        volume_ma_window=20,
        volume_spike_multiple=1.4,
        require_trend_alignment=True,
        trend_ema_fast=8,
        trend_ema_slow=21,
        require_vol_regime_filter=True,
        vol_regime_min=12.0,
        vol_regime_max=45.0,
        momentum_breakout_min_or_frac=0.10,
        momentum_breakout_max_or_frac=1.0,
        momentum_close_location_min=0.65,
        momentum_min_ema_spread_pct=0.0008,
        momentum_pullback_to_ema_max_pct=0.006,
        momentum_confirmation_bars=1,
        momentum_volume_multiple_min=1.4,
        momentum_min_body_or_frac=0.05,
        momentum_max_opposite_wick_body_ratio=1.8,
        momentum_atr_range_min=0.35,
        momentum_trend_bars_min=2,
    )


def c4_orb_trend_pullback_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_orb_momentum_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_orb_trend_pullback_v1",
        description=(
            "Trend pullback continuation: require initial ORB breakout, pullback into fast EMA, "
            "then reclaim in breakout direction."
        ),
        strategy_variant="orb_trend_pullback_v1",
        take_profit_rr=1.8,
        max_hold_minutes=90,
        trend_pullback_max_bars_after_breakout=8,
        trend_pullback_ema_buffer_pct=0.0015,
        trend_pullback_require_orb_reclaim=True,
        trend_pullback_min_breakout_or_frac=0.06,
        trend_pullback_min_volume_multiple=1.3,
    )


def c5_opening_drive_pullback_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    return OrbProfile(
        name="c5_opening_drive_pullback_v1",
        description=(
            "Opening-drive pullback continuation: require a strong opening drive, then enter the first controlled "
            "retest of VWAP/fast EMA that reclaims in the original direction."
        ),
        opening_range_minutes=10,
        entry_start_time="09:40",
        entry_cutoff_time="11:30",
        exit_time="15:55",
        strategy_variant="opening_drive_pullback_v1",
        allow_long=True,
        allow_short=True,
        require_breakout_open_inside_range=False,
        entry_trigger_mode="close_breakout",
        stop_mode="range",
        take_profit_rr=1.5,
        break_even_trigger_rr=0.75,
        exit_on_opposite_candle=True,
        opposite_candle_min_hold_minutes=10,
        early_fail_minutes=25,
        early_fail_min_rr=0.10,
        max_hold_minutes=90,
        require_relative_volume=True,
        relative_volume_min=1.0,
        trend_ema_fast=21,
        trend_ema_slow=55,
        require_or_width_filter=False,
        drive_min_abs_return_pct=0.004,
        drive_close_location_min=0.68,
        drive_pullback_min_retrace_frac=0.18,
        drive_pullback_max_retrace_frac=0.60,
        drive_touch_ma_buffer_pct=0.0015,
        drive_reclaim_close_location_min=0.55,
        drive_reclaim_min_volume_multiple=0.90,
        drive_stop_buffer_range_frac=0.05,
        drive_max_pullback_bars=8,
    )


def c5_opening_drive_pullback_guard_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c5_opening_drive_pullback_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c5_opening_drive_pullback_guard_v1",
        description=(
            "Stricter opening-drive pullback: stronger opening impulse, shallower retrace, and stronger reclaim "
            "volume before entry."
        ),
        relative_volume_min=1.15,
        take_profit_rr=1.75,
        max_hold_minutes=70,
        drive_min_abs_return_pct=0.0055,
        drive_close_location_min=0.75,
        drive_pullback_min_retrace_frac=0.20,
        drive_pullback_max_retrace_frac=0.45,
        drive_reclaim_close_location_min=0.62,
        drive_reclaim_min_volume_multiple=1.10,
        drive_stop_buffer_range_frac=0.04,
        drive_max_pullback_bars=6,
    )


def c5_opening_drive_pullback_relaxed_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c5_opening_drive_pullback_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c5_opening_drive_pullback_relaxed_v1",
        description=(
            "Higher-frequency opening-drive pullback: slightly shorter drive window and looser retrace limits to "
            "capture secondary continuation attempts."
        ),
        opening_range_minutes=8,
        entry_start_time="09:38",
        relative_volume_min=0.90,
        take_profit_rr=1.25,
        max_hold_minutes=100,
        drive_min_abs_return_pct=0.0030,
        drive_close_location_min=0.60,
        drive_pullback_min_retrace_frac=0.12,
        drive_pullback_max_retrace_frac=0.75,
        drive_touch_ma_buffer_pct=0.0020,
        drive_reclaim_close_location_min=0.50,
        drive_reclaim_min_volume_multiple=0.75,
        drive_stop_buffer_range_frac=0.06,
        drive_max_pullback_bars=12,
    )


def c5_opening_drive_pullback_long_only_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c5_opening_drive_pullback_guard_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c5_opening_drive_pullback_long_only_v1",
        description="Long-only opening-drive pullback profile for index ETFs.",
        allow_short=False,
    )


def c5_opening_drive_pullback_reclaim_v2(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c5_opening_drive_pullback_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c5_opening_drive_pullback_reclaim_v2",
        description=(
            "Opening-drive pullback v2: keep the drive and pullback structure, but allow deeper retraces below "
            "the drive open and require reclaim above VWAP/EMA without forcing a previous-bar extreme break."
        ),
        entry_start_time="09:38",
        relative_volume_min=0.95,
        take_profit_rr=1.35,
        max_hold_minutes=80,
        drive_pullback_max_retrace_frac=0.75,
        drive_touch_ma_buffer_pct=0.0020,
        drive_reclaim_close_location_min=0.50,
        drive_reclaim_min_volume_multiple=0.80,
        drive_pullback_require_hold_drive_open=False,
        drive_reclaim_requires_prev_extreme_break=False,
        drive_stop_buffer_range_frac=0.06,
        drive_max_pullback_bars=10,
    )


def c5_opening_drive_pullback_quality_v2(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c5_opening_drive_pullback_reclaim_v2(or_width_min=or_width_min)
    return replace(
        base,
        name="c5_opening_drive_pullback_quality_v2",
        description=(
            "Opening-drive pullback v2 quality filter: same relaxed reclaim geometry, but require a stronger "
            "opening impulse and cleaner reclaim close location."
        ),
        relative_volume_min=1.05,
        take_profit_rr=1.5,
        drive_min_abs_return_pct=0.0045,
        drive_close_location_min=0.72,
        drive_pullback_min_retrace_frac=0.15,
        drive_pullback_max_retrace_frac=0.60,
        drive_reclaim_close_location_min=0.58,
        drive_reclaim_min_volume_multiple=0.95,
        drive_max_pullback_bars=8,
    )


def c5_opening_drive_pullback_long_only_v2(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c5_opening_drive_pullback_quality_v2(or_width_min=or_width_min)
    return replace(
        base,
        name="c5_opening_drive_pullback_long_only_v2",
        description="Long-only opening-drive pullback v2 for index ETFs.",
        allow_short=False,
    )


def c5_opening_drive_pullback_prev_break_v3(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c5_opening_drive_pullback_quality_v2(or_width_min=or_width_min)
    return replace(
        base,
        name="c5_opening_drive_pullback_prev_break_v3",
        description=(
            "Opening-drive pullback v3: allow deeper pullbacks below the drive open, but require the reclaim bar "
            "to break the previous bar extreme before entry."
        ),
        drive_pullback_require_hold_drive_open=False,
        drive_reclaim_requires_prev_extreme_break=True,
    )


def c5_opening_drive_pullback_hold_open_v3(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c5_opening_drive_pullback_quality_v2(or_width_min=or_width_min)
    return replace(
        base,
        name="c5_opening_drive_pullback_hold_open_v3",
        description=(
            "Opening-drive pullback v3: keep the pullback above the drive open, but drop the previous-bar extreme "
            "break requirement so reclaim can trigger earlier."
        ),
        drive_pullback_require_hold_drive_open=True,
        drive_reclaim_requires_prev_extreme_break=False,
    )


def c5_opening_drive_pullback_long_only_balance_v4(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c5_opening_drive_pullback_long_only_v2(or_width_min=or_width_min)
    return replace(
        base,
        name="c5_opening_drive_pullback_long_only_balance_v4",
        description=(
            "Opening-drive pullback v4 balance: long-only, no previous-bar break requirement, and slightly looser "
            "drive/pullback filters to lift trade count without reopening the weak short path."
        ),
        entry_start_time="09:38",
        relative_volume_min=0.95,
        take_profit_rr=1.35,
        drive_min_abs_return_pct=0.0040,
        drive_close_location_min=0.68,
        drive_pullback_min_retrace_frac=0.12,
        drive_pullback_max_retrace_frac=0.68,
        drive_reclaim_close_location_min=0.50,
        drive_reclaim_min_volume_multiple=0.85,
        drive_max_pullback_bars=10,
    )


def c5_opening_drive_pullback_long_only_fast_v4(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c5_opening_drive_pullback_long_only_balance_v4(or_width_min=or_width_min)
    return replace(
        base,
        name="c5_opening_drive_pullback_long_only_fast_v4",
        description=(
            "Opening-drive pullback v4 fast: same long-only reclaim geometry with a shorter drive window and "
            "earlier start time to test whether the family is simply too slow."
        ),
        opening_range_minutes=8,
        entry_start_time="09:38",
        max_hold_minutes=70,
        drive_min_abs_return_pct=0.0035,
        drive_close_location_min=0.64,
        drive_pullback_max_retrace_frac=0.72,
        drive_max_pullback_bars=12,
    )


def c5_opening_drive_pullback_long_only_regime_v5(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c5_opening_drive_pullback_long_only_balance_v4(or_width_min=or_width_min)
    return replace(
        base,
        name="c5_opening_drive_pullback_long_only_regime_v5",
        description=(
            "Opening-drive pullback v5: long-only balance profile, but only on calmer prior-range / short-vol-regime "
            "days to avoid the leveraged high-vol path that is dragging the family."
        ),
        require_relative_volume=True,
        relative_volume_min=1.0,
        require_prior_day_range_filter=True,
        prior_day_range_max_pct=0.02,
        require_vol_regime_filter=True,
        vol_regime_min=10.0,
        vol_regime_max=35.0,
    )


def c6_opening_exhaustion_reversal_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    return OrbProfile(
        name="c6_opening_exhaustion_reversal_v1",
        description=(
            "Opening-exhaustion reversal: require a strong opening drive away from VWAP, then trade the first "
            "reversal candle that closes back through value."
        ),
        opening_range_minutes=10,
        entry_start_time="09:40",
        entry_cutoff_time="11:00",
        exit_time="15:55",
        strategy_variant="opening_exhaustion_reversal_v1",
        allow_long=True,
        allow_short=True,
        require_breakout_open_inside_range=False,
        entry_trigger_mode="close_breakout",
        stop_mode="range",
        take_profit_rr=1.25,
        break_even_trigger_rr=0.75,
        exit_on_opposite_candle=True,
        opposite_candle_min_hold_minutes=8,
        early_fail_minutes=20,
        early_fail_min_rr=0.08,
        max_hold_minutes=75,
        require_relative_volume=True,
        relative_volume_min=1.0,
        trend_ema_fast=13,
        trend_ema_slow=34,
        require_or_width_filter=False,
        drive_min_abs_return_pct=0.0045,
        drive_close_location_min=0.72,
        drive_pullback_min_retrace_frac=0.35,
        drive_pullback_max_retrace_frac=1.10,
        drive_touch_ma_buffer_pct=0.0015,
        drive_reclaim_close_location_min=0.60,
        drive_stop_buffer_range_frac=0.05,
        drive_max_pullback_bars=6,
    )


def c6_opening_exhaustion_reversal_quality_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c6_opening_exhaustion_reversal_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c6_opening_exhaustion_reversal_quality_v1",
        description=(
            "Stricter opening-exhaustion reversal: stronger opening drive, stronger reversal candle, and tighter "
            "entry horizon."
        ),
        relative_volume_min=1.1,
        take_profit_rr=1.5,
        max_hold_minutes=60,
        drive_min_abs_return_pct=0.0055,
        drive_close_location_min=0.78,
        drive_pullback_min_retrace_frac=0.40,
        drive_pullback_max_retrace_frac=0.95,
        drive_touch_ma_buffer_pct=0.0020,
        drive_reclaim_close_location_min=0.68,
        drive_stop_buffer_range_frac=0.04,
        drive_max_pullback_bars=5,
    )


def c6_opening_exhaustion_reversal_regime_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c6_opening_exhaustion_reversal_quality_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c6_opening_exhaustion_reversal_regime_v1",
        description=(
            "Opening-exhaustion reversal on calmer sessions only, avoiding the highest-volatility regime where "
            "failed opening moves tend to trend instead of mean-revert."
        ),
        require_vol_regime_filter=True,
        vol_regime_min=10.0,
        vol_regime_max=32.0,
        require_prior_day_range_filter=True,
        prior_day_range_max_pct=0.022,
    )


def c6_opening_exhaustion_reversal_long_only_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c6_opening_exhaustion_reversal_regime_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c6_opening_exhaustion_reversal_long_only_v1",
        description="Long-only opening-exhaustion reversal for downside opening drives.",
        allow_short=False,
    )


def c6_opening_exhaustion_reversal_short_only_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c6_opening_exhaustion_reversal_regime_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c6_opening_exhaustion_reversal_short_only_v1",
        description="Short-only opening-exhaustion reversal for upside opening drives.",
        allow_long=False,
    )


def c6_opening_exhaustion_reversal_balance_v2(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c6_opening_exhaustion_reversal_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c6_opening_exhaustion_reversal_balance_v2",
        description=(
            "Opening-exhaustion reversal v2 balance: shorter drive window and materially looser drive/retrace "
            "requirements after the v1 audit showed the family was rejecting almost every day before reversal "
            "evaluation."
        ),
        opening_range_minutes=6,
        entry_start_time="09:36",
        relative_volume_min=0.9,
        take_profit_rr=1.10,
        max_hold_minutes=60,
        drive_min_abs_return_pct=0.0030,
        drive_close_location_min=0.62,
        drive_pullback_min_retrace_frac=0.20,
        drive_pullback_max_retrace_frac=0.95,
        drive_touch_ma_buffer_pct=0.0010,
        drive_reclaim_close_location_min=0.52,
        drive_stop_buffer_range_frac=0.04,
        drive_max_pullback_bars=8,
    )


def c6_opening_exhaustion_reversal_regime_v2(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c6_opening_exhaustion_reversal_balance_v2(or_width_min=or_width_min)
    return replace(
        base,
        name="c6_opening_exhaustion_reversal_regime_v2",
        description=(
            "Opening-exhaustion reversal v2 with calmer-day filters only, keeping the looser balance geometry "
            "while excluding the highest-volatility sessions."
        ),
        require_vol_regime_filter=True,
        vol_regime_min=10.0,
        vol_regime_max=35.0,
        require_prior_day_range_filter=True,
        prior_day_range_max_pct=0.024,
    )


def c6_opening_exhaustion_reversal_long_only_v2(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c6_opening_exhaustion_reversal_regime_v2(or_width_min=or_width_min)
    return replace(
        base,
        name="c6_opening_exhaustion_reversal_long_only_v2",
        description="Long-only opening-exhaustion reversal v2 for downside opening drives.",
        allow_short=False,
    )


def c6_opening_exhaustion_reversal_short_only_v2(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c6_opening_exhaustion_reversal_regime_v2(or_width_min=or_width_min)
    return replace(
        base,
        name="c6_opening_exhaustion_reversal_short_only_v2",
        description="Short-only opening-exhaustion reversal v2 for upside opening drives.",
        allow_long=False,
    )


def c16_opening_exhaustion_balance_v3(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c6_opening_exhaustion_reversal_balance_v2(or_width_min=or_width_min)
    return replace(
        base,
        name="c16_opening_exhaustion_balance_v3",
        description=(
            "Opening-exhaustion reversal v3: slightly looser drive geometry and shorter hold to increase "
            "frequency while keeping the reversal-through-value structure."
        ),
        opening_range_minutes=5,
        entry_start_time="09:35",
        take_profit_rr=1.0,
        break_even_trigger_rr=0.55,
        early_fail_minutes=10,
        early_fail_min_rr=0.03,
        max_hold_minutes=40,
        relative_volume_min=0.85,
        drive_min_abs_return_pct=0.0025,
        drive_close_location_min=0.58,
        drive_pullback_min_retrace_frac=0.15,
        drive_pullback_max_retrace_frac=1.00,
        drive_touch_ma_buffer_pct=0.0012,
        drive_reclaim_close_location_min=0.50,
        drive_stop_buffer_range_frac=0.035,
        drive_max_pullback_bars=9,
    )


def c16_opening_exhaustion_quality_v3(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c16_opening_exhaustion_balance_v3(or_width_min=or_width_min)
    return replace(
        base,
        name="c16_opening_exhaustion_quality_v3",
        description=(
            "Quality-biased opening-exhaustion reversal v3 with stronger opening drive and slightly tighter "
            "reversal structure."
        ),
        relative_volume_min=0.95,
        take_profit_rr=1.10,
        max_hold_minutes=35,
        drive_min_abs_return_pct=0.0030,
        drive_close_location_min=0.64,
        drive_pullback_min_retrace_frac=0.20,
        drive_pullback_max_retrace_frac=0.90,
        drive_reclaim_close_location_min=0.56,
        drive_stop_buffer_range_frac=0.030,
        drive_max_pullback_bars=7,
    )


def c16_opening_exhaustion_regime_v3(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c16_opening_exhaustion_quality_v3(or_width_min=or_width_min)
    return replace(
        base,
        name="c16_opening_exhaustion_regime_v3",
        description=(
            "Opening-exhaustion reversal v3 on calmer sessions only, to avoid the highest-volatility days where "
            "failed opening pushes tend to keep trending."
        ),
        require_vol_regime_filter=True,
        vol_regime_min=10.0,
        vol_regime_max=34.0,
        require_prior_day_range_filter=True,
        prior_day_range_max_pct=0.025,
    )


def c16_opening_exhaustion_long_only_v3(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c16_opening_exhaustion_regime_v3(or_width_min=or_width_min)
    return replace(
        base,
        name="c16_opening_exhaustion_long_only_v3",
        description="Long-only opening-exhaustion reversal v3 for downside opening drives.",
        allow_short=False,
    )


def c16_opening_exhaustion_short_only_v3(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c16_opening_exhaustion_regime_v3(or_width_min=or_width_min)
    return replace(
        base,
        name="c16_opening_exhaustion_short_only_v3",
        description="Short-only opening-exhaustion reversal v3 for upside opening drives.",
        allow_long=False,
    )


def c18_vwap_mr_balance_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_mr_vwap_zscore_v2_fast(or_width_min=or_width_min)
    return replace(
        base,
        name="c18_vwap_mr_balance_v1",
        description=(
            "Higher-frequency VWAP mean reversion with balanced z-score thresholds and short intraday holds."
        ),
        require_relative_volume=False,
        allow_short=True,
        mr_zscore_entry=1.15,
        mr_zscore_reentry=0.55,
        mr_zscore_stop=2.0,
        mr_zscore_target=0.18,
        mr_vwap_slope_max_pct=0.0030,
        max_hold_minutes=30,
        opposite_candle_min_hold_minutes=3,
    )


def c18_vwap_mr_quality_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c18_vwap_mr_balance_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c18_vwap_mr_quality_v1",
        description=(
            "Quality-biased higher-frequency VWAP mean reversion with tighter slope and sigma controls."
        ),
        require_relative_volume=True,
        relative_volume_min=1.05,
        mr_zscore_entry=1.35,
        mr_zscore_reentry=0.65,
        mr_zscore_stop=2.15,
        mr_zscore_target=0.15,
        mr_sigma_min_pct=0.0005,
        mr_sigma_max_pct=0.016,
        mr_vwap_slope_max_pct=0.0020,
        max_hold_minutes=25,
    )


def c18_vwap_mr_regime_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c18_vwap_mr_quality_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c18_vwap_mr_regime_v1",
        description=(
            "Quality-biased higher-frequency VWAP mean reversion gated to calmer intraday volatility regimes."
        ),
        require_vol_regime_filter=True,
        vol_regime_min=12.0,
        vol_regime_max=32.0,
        require_prior_day_range_filter=True,
        prior_day_range_max_pct=0.022,
    )


def c18_vwap_mr_opportunity_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c18_vwap_mr_balance_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c18_vwap_mr_opportunity_v1",
        description=(
            "More opportunistic higher-frequency VWAP mean reversion with smaller excursion requirements."
        ),
        mr_zscore_entry=1.0,
        mr_zscore_reentry=0.45,
        mr_zscore_stop=1.8,
        mr_zscore_target=0.20,
        max_hold_minutes=35,
        opposite_candle_min_hold_minutes=2,
    )


def c18_vwap_mr_fast_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c18_vwap_mr_balance_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c18_vwap_mr_fast_v1",
        description=(
            "Fast higher-frequency VWAP mean reversion with earlier exits and tighter time in trade."
        ),
        mr_zscore_entry=1.2,
        mr_zscore_reentry=0.5,
        mr_zscore_stop=1.95,
        mr_zscore_target=0.12,
        max_hold_minutes=20,
        opposite_candle_min_hold_minutes=2,
    )


def c18_vwap_mr_long_only_balance_v2(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c18_vwap_mr_quality_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c18_vwap_mr_long_only_balance_v2",
        description=(
            "Long-only VWAP mean reversion with tighter downside control and faster monetization."
        ),
        allow_short=False,
        relative_volume_min=1.0,
        mr_zscore_entry=1.25,
        mr_zscore_reentry=0.60,
        mr_zscore_stop=1.90,
        mr_zscore_target=0.14,
        mr_sigma_min_pct=0.0006,
        mr_sigma_max_pct=0.013,
        mr_vwap_slope_max_pct=0.0018,
        break_even_trigger_rr=0.35,
        max_hold_minutes=22,
        opposite_candle_min_hold_minutes=2,
    )


def c18_vwap_mr_long_only_quality_v2(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c18_vwap_mr_long_only_balance_v2(or_width_min=or_width_min)
    return replace(
        base,
        name="c18_vwap_mr_long_only_quality_v2",
        description=(
            "Long-only VWAP mean reversion with stronger continuation quality and tighter holding discipline."
        ),
        require_relative_volume=True,
        relative_volume_min=1.05,
        mr_zscore_entry=1.40,
        mr_zscore_reentry=0.68,
        mr_zscore_stop=2.00,
        mr_zscore_target=0.12,
        mr_sigma_min_pct=0.0008,
        mr_sigma_max_pct=0.011,
        mr_vwap_slope_max_pct=0.0015,
        break_even_trigger_rr=0.30,
        max_hold_minutes=18,
        opposite_candle_min_hold_minutes=2,
    )


def c18_vwap_mr_long_only_regime_v2(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c18_vwap_mr_long_only_quality_v2(or_width_min=or_width_min)
    return replace(
        base,
        name="c18_vwap_mr_long_only_regime_v2",
        description=(
            "Long-only VWAP mean reversion restricted to calmer, narrower prior-day conditions."
        ),
        require_vol_regime_filter=True,
        vol_regime_min=14.0,
        vol_regime_max=28.0,
        require_prior_day_range_filter=True,
        prior_day_range_max_pct=0.018,
    )


def c18_vwap_mr_candidates(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> List[OrbProfile]:
    return [
        c18_vwap_mr_balance_v1(or_width_min=or_width_min),
        c18_vwap_mr_quality_v1(or_width_min=or_width_min),
        c18_vwap_mr_regime_v1(or_width_min=or_width_min),
        c18_vwap_mr_opportunity_v1(or_width_min=or_width_min),
        c18_vwap_mr_fast_v1(or_width_min=or_width_min),
    ]


def c18_vwap_mr_candidates_v2(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> List[OrbProfile]:
    return [
        c18_vwap_mr_long_only_balance_v2(or_width_min=or_width_min),
        c18_vwap_mr_long_only_quality_v2(or_width_min=or_width_min),
        c18_vwap_mr_long_only_regime_v2(or_width_min=or_width_min),
    ]


def c7_opening_failure_reversal_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_orb_failure_fade_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c7_opening_failure_reversal_v1",
        description=(
            "Opening failure reversal: trade failed opening-range breakouts back into range with tighter timing and "
            "cleaner structural exits."
        ),
        opening_range_minutes=5,
        entry_start_time="09:35",
        entry_cutoff_time="10:30",
        entry_trigger_mode="stop_touch",
        stop_mode="range",
        take_profit_rr=1.25,
        break_even_trigger_rr=0.50,
        max_hold_minutes=45,
        relative_volume_min=0.85,
    )


def c7_opening_failure_reversal_quality_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c7_opening_failure_reversal_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c7_opening_failure_reversal_quality_v1",
        description=(
            "Higher-quality opening failure reversal: slightly wider opening range, stronger RVOL, and shorter "
            "holding horizon."
        ),
        opening_range_min_width_pct=0.0015,
        relative_volume_min=1.0,
        take_profit_rr=1.10,
        max_hold_minutes=35,
    )


def c7_opening_failure_reversal_regime_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c7_opening_failure_reversal_quality_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c7_opening_failure_reversal_regime_v1",
        description=(
            "Opening failure reversal with calmer-day filters to avoid persistent trend days where failed "
            "breakouts are less likely to mean-revert."
        ),
        require_vol_regime_filter=True,
        vol_regime_min=10.0,
        vol_regime_max=35.0,
        require_prior_day_range_filter=True,
        prior_day_range_max_pct=0.025,
    )


def c7_opening_failure_reversal_long_only_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c7_opening_failure_reversal_regime_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c7_opening_failure_reversal_long_only_v1",
        description="Long-only opening failure reversal for downside failed breaks.",
        allow_short=False,
    )


def c7_opening_failure_reversal_short_only_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c7_opening_failure_reversal_regime_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c7_opening_failure_reversal_short_only_v1",
        description="Short-only opening failure reversal for upside failed breaks.",
        allow_long=False,
    )


def c7_opening_failure_reversal_long_only_balance_v2(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c7_opening_failure_reversal_long_only_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c7_opening_failure_reversal_long_only_balance_v2",
        description=(
            "Opening failure reversal v2 balance: long-only, with OR-width and RVOL relaxed after the v1 audit "
            "showed those filters were suppressing too many otherwise valid reversal days."
        ),
        require_or_width_filter=False,
        relative_volume_min=0.75,
        take_profit_rr=1.00,
        break_even_trigger_rr=0.40,
        early_fail_minutes=12,
        early_fail_min_rr=0.05,
        max_hold_minutes=35,
    )


def c7_opening_failure_reversal_long_only_regime_v2(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c7_opening_failure_reversal_long_only_balance_v2(or_width_min=or_width_min)
    return replace(
        base,
        name="c7_opening_failure_reversal_long_only_regime_v2",
        description=(
            "Opening failure reversal v2 with calmer-day filters, keeping the looser long-only balance profile "
            "while excluding higher-volatility sessions that tend to keep trending after the false break."
        ),
        require_vol_regime_filter=True,
        vol_regime_min=10.0,
        vol_regime_max=35.0,
        require_prior_day_range_filter=True,
        prior_day_range_max_pct=0.025,
    )


def c4_orb_event_drive_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_orb_momentum_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_orb_event_drive_v1",
        description=(
            "Event-day directional ORB: prioritize large gap sessions and trade first strong continuation."
        ),
        strategy_variant="orb_event_drive_v1",
        take_profit_rr=2.0,
        max_hold_minutes=60,
        event_drive_min_gap_abs_return=0.006,
        event_drive_min_breakout_or_frac=0.10,
        event_drive_close_location_min=0.60,
        event_drive_min_volume_multiple=1.3,
    )


def c4_orb_transition_compression_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_orb_failure_fade_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_orb_transition_compression_v1",
        description=(
            "Transition-session compression breakout: identify short volatility coils and trade the first expansion."
        ),
        strategy_variant="orb_transition_compression_v1",
        stop_mode="opening_bar_atr",
        stop_loss_atr_distance=1.0,
        take_profit_rr=1.5,
        max_hold_minutes=60,
        compression_lookback_bars=5,
        compression_max_range_pct=0.0025,
        compression_breakout_buffer_or_frac=0.03,
        compression_min_volume_multiple=1.2,
    )


def c4_orb_option_structure_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_long_only_rr15(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_orb_option_structure_v1",
        description=(
            "C4 long-only with strict option microstructure and contract structure filters to avoid low-quality fills."
        ),
        strategy_variant="orb_qc",
        option_structure_filter_enabled=True,
        option_structure_min_open_interest=1200,
        option_structure_min_entry_volume=150,
        option_structure_max_entry_spread_pct=0.18,
        option_structure_max_entry_bar_range_pct=0.30,
        option_structure_min_entry_price=0.8,
        require_option_microstructure_filter=True,
        option_min_entry_volume=100,
        option_max_entry_bar_range_pct=0.35,
        option_min_entry_price=0.6,
    )


def c4_momentum_accel_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_orb_momentum_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_momentum_accel_v1",
        description=(
            "Momentum acceleration profile: tighter EMA trend confirmation and stronger breakout strength."
        ),
        take_profit_rr=2.2,
        max_hold_minutes=45,
        momentum_breakout_min_or_frac=0.14,
        momentum_breakout_max_or_frac=0.8,
        momentum_close_location_min=0.70,
        momentum_min_ema_spread_pct=0.0010,
        momentum_pullback_to_ema_max_pct=0.004,
        momentum_volume_multiple_min=1.6,
        momentum_min_body_or_frac=0.08,
        momentum_max_opposite_wick_body_ratio=1.2,
        momentum_atr_range_min=0.50,
        momentum_trend_bars_min=3,
        volume_spike_multiple=1.5,
        trend_ema_fast=5,
        trend_ema_slow=13,
    )


def c4_momentum_pullback_fast_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_orb_trend_pullback_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_momentum_pullback_fast_v1",
        description=(
            "Fast pullback continuation profile with shorter timeout and tighter confirmation."
        ),
        take_profit_rr=1.6,
        max_hold_minutes=45,
        trend_pullback_max_bars_after_breakout=6,
        trend_pullback_ema_buffer_pct=0.0010,
        trend_pullback_min_breakout_or_frac=0.08,
        trend_pullback_min_volume_multiple=1.4,
    )


def c4_momentum_quality_v2(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_orb_momentum_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_momentum_quality_v2",
        description=(
            "Quality-biased momentum breakout profile with stronger body/ATR expansion and anti-overextension guard."
        ),
        take_profit_rr=1.9,
        max_hold_minutes=55,
        momentum_breakout_min_or_frac=0.12,
        momentum_breakout_max_or_frac=0.75,
        momentum_close_location_min=0.70,
        momentum_min_ema_spread_pct=0.0010,
        momentum_pullback_to_ema_max_pct=0.005,
        momentum_confirmation_bars=2,
        momentum_volume_multiple_min=1.6,
        momentum_min_body_or_frac=0.08,
        momentum_max_opposite_wick_body_ratio=1.0,
        momentum_atr_range_min=0.45,
        momentum_trend_bars_min=3,
        volume_spike_multiple=1.6,
    )


def c4_momentum_loose(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_orb_momentum_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_momentum_loose",
        description=(
            "Loose momentum continuation variant from sweeps with open-any entry and softer RVOL "
            "requirements while preserving the core breakout/trend template."
        ),
        require_breakout_open_inside_range=False,
        relative_volume_min=0.85,
        max_hold_minutes=60,
    )


def c4_momentum_loose_no_spike_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_momentum_loose(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_momentum_loose_no_spike_v1",
        description=(
            "Loose momentum continuation variant that disables the volume-spike gate and lowers "
            "breakout strength requirements to improve opportunity count."
        ),
        require_volume_spike=False,
        volume_spike_multiple=1.0,
        momentum_breakout_min_or_frac=0.08,
        momentum_volume_multiple_min=1.0,
        momentum_close_location_min=0.60,
    )


def c4_momentum_loose_no_trend_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_momentum_loose(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_momentum_loose_no_trend_v1",
        description=(
            "Loose momentum continuation variant that removes EMA trend-alignment persistence so "
            "the profile can participate in early regime shifts."
        ),
        require_trend_alignment=False,
        momentum_breakout_min_or_frac=0.08,
        momentum_close_location_min=0.60,
        momentum_min_ema_spread_pct=0.0,
        momentum_trend_bars_min=1,
    )


def c4_momentum_loose_relaxed_v3(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_momentum_loose(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_momentum_loose_relaxed_v3",
        description=(
            "Broad relaxed momentum continuation profile that removes spike/trend hard gates and "
            "leans on breakout quality plus a slightly longer hold horizon."
        ),
        require_volume_spike=False,
        require_trend_alignment=False,
        volume_spike_multiple=1.0,
        relative_volume_min=0.80,
        momentum_breakout_min_or_frac=0.08,
        momentum_close_location_min=0.60,
        momentum_min_ema_spread_pct=0.0,
        momentum_volume_multiple_min=1.0,
        momentum_trend_bars_min=1,
        max_hold_minutes=75,
    )


def c4_momentum_loose_cost_guard_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_momentum_loose_relaxed_v3(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_momentum_loose_cost_guard_v1",
        description=(
            "Cost-aware momentum continuation variant that exits faster and avoids chasing "
            "extended breakouts to improve slippage resilience."
        ),
        take_profit_rr=1.35,
        opposite_candle_min_hold_minutes=5,
        max_hold_minutes=45,
        relative_volume_min=0.90,
        momentum_breakout_max_or_frac=0.65,
        momentum_pullback_to_ema_max_pct=0.0045,
        momentum_min_body_or_frac=0.04,
        momentum_max_opposite_wick_body_ratio=1.0,
    )


def c4_momentum_vwap_reclaim_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_orb_trend_pullback_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_momentum_vwap_reclaim_v1",
        description=(
            "Trend reclaim continuation profile: participate after the first clean pullback into the "
            "trend mean, then require a reclaim candle before re-entry."
        ),
        strategy_variant="orb_vwap_reclaim_v1",
        take_profit_rr=1.45,
        max_hold_minutes=50,
        require_volume_spike=False,
        volume_spike_multiple=1.0,
        relative_volume_min=0.95,
        trend_ema_fast=5,
        trend_ema_slow=13,
        trend_pullback_max_bars_after_breakout=5,
        trend_pullback_ema_buffer_pct=0.0010,
        trend_pullback_require_orb_reclaim=False,
        trend_pullback_min_breakout_or_frac=0.05,
        trend_pullback_min_volume_multiple=1.05,
    )


def c4_momentum_vwap_reclaim_recovery_v2(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_momentum_vwap_reclaim_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_momentum_vwap_reclaim_recovery_v2",
        description=(
            "Causal momentum recovery profile: slightly easier reclaim participation and shorter failure horizon "
            "to keep event momentum viable after next-bar-open entry semantics."
        ),
        take_profit_rr=1.30,
        max_hold_minutes=42,
        relative_volume_min=0.90,
        trend_pullback_max_bars_after_breakout=6,
        trend_pullback_ema_buffer_pct=0.0012,
        trend_pullback_min_breakout_or_frac=0.04,
        trend_pullback_min_volume_multiple=1.00,
        event_drive_min_gap_abs_return=0.0045,
    )


def c4_momentum_break_retest_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_orb_trend_pullback_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_momentum_break_retest_v1",
        description=(
            "Break-and-retest continuation profile: require an initial impulse, a shallow retest, "
            "and a reclaim through the breakout level."
        ),
        take_profit_rr=1.6,
        max_hold_minutes=55,
        relative_volume_min=1.0,
        require_volume_spike=True,
        volume_spike_multiple=1.2,
        trend_ema_fast=5,
        trend_ema_slow=13,
        trend_pullback_max_bars_after_breakout=4,
        trend_pullback_ema_buffer_pct=0.0008,
        trend_pullback_require_orb_reclaim=True,
        trend_pullback_min_breakout_or_frac=0.08,
        trend_pullback_min_volume_multiple=1.20,
    )


def c4_momentum_gap_go_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_orb_event_drive_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_momentum_gap_go_v1",
        description=(
            "Gap-and-go continuation profile: require a larger opening impulse and faster follow-through "
            "to avoid late entries on event sessions."
        ),
        take_profit_rr=1.7,
        max_hold_minutes=40,
        relative_volume_min=1.15,
        require_volume_spike=True,
        volume_spike_multiple=1.4,
        event_drive_min_gap_abs_return=0.008,
        event_drive_min_breakout_or_frac=0.12,
        event_drive_close_location_min=0.65,
        event_drive_min_volume_multiple=1.45,
    )


def c4_momentum_adx_confirm_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_momentum_loose_cost_guard_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_momentum_adx_confirm_v1",
        description=(
            "ADX-confirmed continuation profile: keep the cost-aware momentum template but require "
            "observable directional trend strength before entry."
        ),
        require_trend_alignment=True,
        trend_ema_fast=5,
        trend_ema_slow=13,
        relative_volume_min=1.0,
        momentum_volume_multiple_min=1.2,
        momentum_trend_bars_min=2,
        momentum_adx_period=8,
        momentum_adx_min=18.0,
    )


def c4_orb_momentum_short_hold(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_orb_momentum_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_orb_momentum_short_hold",
        description=(
            "Short-hold momentum breakout variant from sweeps with faster profit-taking to reduce "
            "late-morning reversal exposure."
        ),
        max_hold_minutes=45,
        take_profit_rr=1.4,
    )


def c4_momentum_accel_relaxed_v2(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_momentum_accel_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_momentum_accel_relaxed_v2",
        description=(
            "Relaxed momentum acceleration variant from sweeps with softer breakout and volume "
            "requirements and a wider holding horizon."
        ),
        momentum_breakout_min_or_frac=0.10,
        momentum_close_location_min=0.62,
        momentum_volume_multiple_min=1.3,
        max_hold_minutes=70,
    )


def c4_momentum_pullback_guard_v2(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_momentum_pullback_fast_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_momentum_pullback_guard_v2",
        description=(
            "Guarded momentum pullback continuation variant from sweeps with tighter EMA reclaim "
            "discipline and a modestly longer hold cap."
        ),
        trend_pullback_ema_buffer_pct=0.0010,
        trend_pullback_min_volume_multiple=1.4,
        max_hold_minutes=50,
    )


def c4_trend_pullback_fast_v2(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_orb_trend_pullback_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_trend_pullback_fast_v2",
        description=(
            "Fast trend-pullback continuation variant from sweeps with shorter breakout-to-retest "
            "window and faster profit-taking."
        ),
        trend_pullback_max_bars_after_breakout=6,
        max_hold_minutes=45,
        take_profit_rr=1.4,
    )


def c4_trend_pullback_tight(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_orb_trend_pullback_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_trend_pullback_tight",
        description=(
            "Tight trend-pullback continuation variant from sweeps with faster exit timing and "
            "slightly smaller reward target."
        ),
        max_hold_minutes=45,
        take_profit_rr=1.6,
    )


def c21_trend_pullback_balance_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_orb_trend_pullback_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c21_trend_pullback_balance_v1",
        description=(
            "Long-only trend-pullback continuation with tighter OR-based risk and slightly looser "
            "breakout strength/volume gates than the original momentum profile."
        ),
        allow_short=False,
        stop_mode="range",
        take_profit_rr=1.45,
        break_even_trigger_rr=0.55,
        early_fail_minutes=18,
        early_fail_min_rr=0.08,
        max_hold_minutes=55,
        require_volume_spike=False,
        relative_volume_min=0.95,
        trend_ema_fast=5,
        trend_ema_slow=13,
        trend_pullback_max_bars_after_breakout=6,
        trend_pullback_ema_buffer_pct=0.0010,
        trend_pullback_require_orb_reclaim=True,
        trend_pullback_min_breakout_or_frac=0.05,
        trend_pullback_min_volume_multiple=1.10,
    )


def c21_trend_pullback_quality_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c21_trend_pullback_balance_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c21_trend_pullback_quality_v1",
        description=(
            "Higher-quality trend-pullback continuation requiring stronger breakout force and "
            "cleaner retest timing before re-entry."
        ),
        take_profit_rr=1.60,
        break_even_trigger_rr=0.60,
        early_fail_minutes=15,
        max_hold_minutes=45,
        require_relative_volume=True,
        relative_volume_min=1.00,
        require_volume_spike=True,
        volume_spike_multiple=1.15,
        trend_pullback_max_bars_after_breakout=5,
        trend_pullback_ema_buffer_pct=0.0008,
        trend_pullback_min_breakout_or_frac=0.07,
        trend_pullback_min_volume_multiple=1.25,
    )


def c21_trend_pullback_regime_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c21_trend_pullback_quality_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c21_trend_pullback_regime_v1",
        description=(
            "Trend-pullback continuation with calm-day regime guards to avoid overstretched sessions "
            "where the retest tends to fail or the options become too expensive."
        ),
        require_vol_regime_filter=True,
        vol_regime_min=12.0,
        vol_regime_max=35.0,
        require_prior_day_range_filter=True,
        prior_day_range_max_pct=0.025,
    )


def c21_trend_pullback_fast_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c21_trend_pullback_balance_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c21_trend_pullback_fast_v1",
        description=(
            "Faster monetization trend-pullback continuation with shorter hold and quicker "
            "break-even behavior for option-friendly execution."
        ),
        take_profit_rr=1.25,
        break_even_trigger_rr=0.45,
        early_fail_minutes=12,
        max_hold_minutes=35,
        trend_pullback_max_bars_after_breakout=5,
        trend_pullback_ema_buffer_pct=0.0012,
        trend_pullback_min_breakout_or_frac=0.04,
        trend_pullback_min_volume_multiple=1.00,
    )


def c21_trend_pullback_candidates(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> List[OrbProfile]:
    return [
        c21_trend_pullback_balance_v1(or_width_min=or_width_min),
        c21_trend_pullback_quality_v1(or_width_min=or_width_min),
        c21_trend_pullback_regime_v1(or_width_min=or_width_min),
        c21_trend_pullback_fast_v1(or_width_min=or_width_min),
    ]


def c4_trend_short_guard_v2(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_orb_trend_short_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_trend_short_guard_v2",
        description=(
            "Guarded downside momentum variant from sweeps with a stronger RVOL gate and modestly "
            "longer hold cap."
        ),
        relative_volume_min=1.15,
        max_hold_minutes=55,
    )


def c22_trend_short_balance_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_orb_trend_short_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c22_trend_short_balance_v1",
        description=(
            "Short-side trend continuation for long-put entries with OR-based risk and slightly looser "
            "breakdown confirmation than the original downside momentum profile."
        ),
        take_profit_rr=1.40,
        break_even_trigger_rr=0.55,
        early_fail_minutes=18,
        early_fail_min_rr=0.08,
        max_hold_minutes=55,
        require_volume_spike=False,
        relative_volume_min=0.95,
    )


def c22_trend_short_quality_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c22_trend_short_balance_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c22_trend_short_quality_v1",
        description=(
            "Higher-quality downside continuation requiring stronger RVOL and stricter breakout "
            "confirmation before entering long puts."
        ),
        take_profit_rr=1.55,
        break_even_trigger_rr=0.60,
        early_fail_minutes=15,
        max_hold_minutes=45,
        require_relative_volume=True,
        relative_volume_min=1.05,
        require_volume_spike=True,
        volume_spike_multiple=1.15,
    )


def c22_trend_short_regime_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c22_trend_short_quality_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c22_trend_short_regime_v1",
        description=(
            "Downside continuation with calm-day regime guards to avoid panic sessions where put "
            "spreads widen too aggressively."
        ),
        require_vol_regime_filter=True,
        vol_regime_min=12.0,
        vol_regime_max=35.0,
        require_prior_day_range_filter=True,
        prior_day_range_max_pct=0.025,
    )


def c22_trend_short_fast_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c22_trend_short_balance_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c22_trend_short_fast_v1",
        description=(
            "Faster downside continuation with shorter hold and quicker break-even to improve "
            "put monetization under realistic fills."
        ),
        take_profit_rr=1.20,
        break_even_trigger_rr=0.45,
        early_fail_minutes=12,
        max_hold_minutes=35,
    )


def c22_trend_short_candidates(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> List[OrbProfile]:
    return [
        c22_trend_short_balance_v1(or_width_min=or_width_min),
        c22_trend_short_quality_v1(or_width_min=or_width_min),
        c22_trend_short_regime_v1(or_width_min=or_width_min),
        c22_trend_short_fast_v1(or_width_min=or_width_min),
    ]


def c4_dispersion_breakout_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_orb_transition_compression_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_dispersion_breakout_v1",
        description=(
            "Dispersion breakout proxy: expansion from compressed conditions in high-volatility sessions."
        ),
        require_vol_regime_filter=True,
        vol_regime_min=18.0,
        vol_regime_max=55.0,
        require_relative_volume=True,
        relative_volume_min=1.1,
        compression_max_range_pct=0.0035,
        compression_breakout_buffer_or_frac=0.05,
        compression_min_volume_multiple=1.35,
        take_profit_rr=1.8,
        max_hold_minutes=45,
    )


def c4_dispersion_revert_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_mr_vwap_zscore_v2(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_dispersion_revert_v1",
        description=(
            "Dispersion mean-reversion proxy using larger z-score excursions in elevated volatility."
        ),
        require_relative_volume=True,
        relative_volume_min=1.0,
        require_vol_regime_filter=True,
        vol_regime_min=16.0,
        vol_regime_max=60.0,
        mr_zscore_entry=2.1,
        mr_zscore_reentry=1.1,
        mr_zscore_stop=3.0,
        mr_zscore_target=0.18,
        max_hold_minutes=40,
    )


def c4_dispersion_breakout_breadth_v2(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_dispersion_breakout_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_dispersion_breakout_breadth_v2",
        description=(
            "Breadth-style dispersion breakout profile: accept slightly broader compression, but require "
            "follow-through volume and shorter trend persistence."
        ),
        vol_regime_min=16.0,
        vol_regime_max=60.0,
        relative_volume_min=1.05,
        compression_max_range_pct=0.0040,
        compression_breakout_buffer_or_frac=0.04,
        compression_min_volume_multiple=1.25,
        take_profit_rr=1.6,
        max_hold_minutes=50,
    )


def c4_dispersion_breakout_relative_v2(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_dispersion_breakout_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_dispersion_breakout_relative_v2",
        description=(
            "Relative-strength dispersion breakout profile: tighter breakout buffer and stronger RVOL "
            "to focus on cleaner leadership expansions."
        ),
        opening_range_min_width_pct=max(float(or_width_min), 0.0025),
        vol_regime_min=14.0,
        vol_regime_max=45.0,
        relative_volume_min=1.20,
        compression_max_range_pct=0.0030,
        compression_breakout_buffer_or_frac=0.025,
        compression_min_volume_multiple=1.45,
        take_profit_rr=1.5,
        max_hold_minutes=35,
    )


def c4_dispersion_revert_rotation_v2(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_dispersion_revert_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_dispersion_revert_rotation_v2",
        description=(
            "Rotation-style dispersion revert profile: moderate excursion threshold with a slightly "
            "longer hold horizon to capture cross-sector normalization."
        ),
        require_relative_volume=False,
        vol_regime_min=12.0,
        vol_regime_max=40.0,
        mr_zscore_entry=1.9,
        mr_zscore_reentry=0.9,
        mr_zscore_stop=2.7,
        mr_zscore_target=0.22,
        max_hold_minutes=50,
    )


def c4_dispersion_revert_exhaustion_v2(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_dispersion_revert_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_dispersion_revert_exhaustion_v2",
        description=(
            "Exhaustion-style dispersion revert profile: require a more extreme excursion and take "
            "profits faster once the snapback begins."
        ),
        require_relative_volume=True,
        relative_volume_min=1.15,
        vol_regime_min=18.0,
        vol_regime_max=65.0,
        mr_zscore_entry=2.4,
        mr_zscore_reentry=1.2,
        mr_zscore_stop=3.2,
        mr_zscore_target=0.15,
        max_hold_minutes=30,
    )


def c4_dispersion_relative_breakout_v3(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_dispersion_breakout_relative_v2(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_dispersion_relative_breakout_v3",
        description=(
            "Proxy-relative dispersion breakout: require the primary to clear the opening range while "
            "outperforming an aligned benchmark proxy by a minimum relative-strength edge."
        ),
        strategy_variant="dispersion_relative_breakout_v1",
        dispersion_proxy_ticker="AUTO",
        dispersion_beta_lookback=24,
        dispersion_min_correlation=0.08,
        dispersion_rel_strength_entry_pct=0.0030,
        dispersion_rel_strength_exit_pct=0.0010,
        dispersion_rel_strength_stop_pct=0.0060,
        dispersion_primary_min_abs_move_pct=0.0030,
        dispersion_proxy_max_abs_move_pct=0.0100,
        require_relative_volume=True,
        relative_volume_min=0.95,
        require_vol_regime_filter=True,
        vol_regime_min=12.0,
        vol_regime_max=45.0,
        take_profit_rr=1.5,
        max_hold_minutes=45,
    )


def c4_dispersion_relative_breakout_guard_v3(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_dispersion_relative_breakout_v3(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_dispersion_relative_breakout_guard_v3",
        description=(
            "Guarded proxy-relative dispersion breakout: stronger relative edge, tighter proxy-move "
            "cap, and faster exits to reduce pure-beta participation."
        ),
        dispersion_rel_strength_entry_pct=0.0045,
        dispersion_rel_strength_exit_pct=0.0015,
        dispersion_rel_strength_stop_pct=0.0055,
        dispersion_primary_min_abs_move_pct=0.0040,
        dispersion_proxy_max_abs_move_pct=0.0075,
        dispersion_beta_shock_max_pct=0.0060,
        dispersion_time_to_work_bars=3,
        dispersion_breakout_rel_strength_floor_frac=0.60,
        relative_volume_min=1.05,
        take_profit_rr=1.35,
        max_hold_minutes=35,
    )


def c4_dispersion_relative_breakout_guard_hold30_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_dispersion_relative_breakout_guard_v3(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_dispersion_relative_breakout_guard_hold30_v1",
        description=(
            "Shorter-hold guarded dispersion breakout that keeps the guard_v3 shape while tightening "
            "the beta-shock veto and demanding the relative edge prove out within two bars."
        ),
        dispersion_beta_shock_max_pct=0.0055,
        dispersion_time_to_work_bars=2,
        dispersion_breakout_rel_strength_floor_frac=0.70,
        take_profit_rr=1.25,
        max_hold_minutes=30,
    )


def c4_dispersion_relative_breakout_guard_density_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_dispersion_relative_breakout_guard_v3(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_dispersion_relative_breakout_guard_density_v1",
        description=(
            "Density-restored guarded dispersion breakout that relaxes the entry edge and proxy-move "
            "cap just enough to rebuild trade count without dropping the beta-shock guard."
        ),
        dispersion_rel_strength_entry_pct=0.0040,
        dispersion_proxy_max_abs_move_pct=0.0085,
        require_relative_volume=True,
        relative_volume_min=1.00,
        dispersion_breakout_rel_strength_floor_frac=0.58,
        take_profit_rr=1.30,
        max_hold_minutes=40,
    )


def c4_dispersion_relative_breakout_guard_density_spy_dia_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> OrbProfile:
    base = c4_dispersion_relative_breakout_guard_density_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_dispersion_relative_breakout_guard_density_spy_dia_v1",
        description=(
            "Guard-density dispersion breakout with an SPY-only DIA proxy override so the index sleeve is "
            "measured against a broader market benchmark without disturbing the default proxy map elsewhere."
        ),
        dispersion_proxy_ticker="AUTO_SPY_DIA",
    )


def c4_dispersion_relative_breakout_guard_density_spy_dia_balance_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> OrbProfile:
    base = c4_dispersion_relative_breakout_guard_density_spy_dia_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_dispersion_relative_breakout_guard_density_spy_dia_balance_v1",
        description=(
            "Balanced SPY-DIA guarded dispersion breakout: preserve the density-restored shell while easing "
            "entry and beta-shock guards enough to rebuild SPY participation under the proxy repair."
        ),
        dispersion_rel_strength_entry_pct=0.0034,
        dispersion_primary_min_abs_move_pct=0.0030,
        dispersion_proxy_max_abs_move_pct=0.0110,
        dispersion_beta_shock_max_pct=0.0075,
        dispersion_time_to_work_bars=2,
        relative_volume_min=0.95,
        dispersion_breakout_rel_strength_floor_frac=0.50,
        take_profit_rr=1.25,
        max_hold_minutes=40,
    )


def c4_dispersion_relative_breakout_guard_density_spy_dia_offset_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> OrbProfile:
    base = c4_dispersion_relative_breakout_guard_density_spy_dia_balance_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_dispersion_relative_breakout_guard_density_spy_dia_offset_v1",
        description=(
            "Offset-seeking SPY-DIA guarded dispersion breakout: nudge the balanced repair toward slightly "
            "earlier participation so the lane can add overlap and more ORB-down-day offsets without "
            "abandoning the guarded density shell."
        ),
        dispersion_rel_strength_entry_pct=0.0032,
        dispersion_primary_min_abs_move_pct=0.0028,
        dispersion_proxy_max_abs_move_pct=0.0120,
        dispersion_beta_shock_max_pct=0.0080,
        dispersion_breakout_rel_strength_floor_frac=0.46,
        take_profit_rr=1.22,
    )


def c4_dispersion_relative_revert_v3(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_dispersion_revert_rotation_v2(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_dispersion_relative_revert_v3",
        description=(
            "Proxy-relative dispersion reversion: fade intraday spread extremes versus a benchmark "
            "proxy using spread z-score normalization."
        ),
        strategy_variant="dispersion_relative_revert_v1",
        dispersion_proxy_ticker="AUTO",
        dispersion_beta_lookback=24,
        dispersion_zscore_window=36,
        dispersion_zscore_entry=1.8,
        dispersion_zscore_reentry=0.8,
        dispersion_zscore_exit=0.25,
        dispersion_zscore_stop=2.8,
        dispersion_min_correlation=0.08,
        dispersion_proxy_max_abs_move_pct=0.0150,
        require_relative_volume=False,
        require_vol_regime_filter=True,
        vol_regime_min=10.0,
        vol_regime_max=40.0,
        take_profit_rr=1.2,
        max_hold_minutes=50,
    )


def c4_dispersion_relative_revert_exhaustion_v3(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_dispersion_relative_revert_v3(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_dispersion_relative_revert_exhaustion_v3",
        description=(
            "Exhaustion-biased proxy-relative dispersion revert: require larger spread dislocations "
            "and exit sooner after the cross-asset snapback starts."
        ),
        dispersion_zscore_window=48,
        dispersion_zscore_entry=2.2,
        dispersion_zscore_reentry=1.0,
        dispersion_zscore_exit=0.20,
        dispersion_zscore_stop=3.1,
        dispersion_min_correlation=0.12,
        dispersion_proxy_max_abs_move_pct=0.0200,
        require_relative_volume=True,
        relative_volume_min=0.95,
        vol_regime_min=14.0,
        vol_regime_max=55.0,
        take_profit_rr=1.0,
        max_hold_minutes=35,
    )


def c4_dispersion_relative_revert_confirm_v4(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_dispersion_relative_revert_v3(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_dispersion_relative_revert_confirm_v4",
        description=(
            "Confirmed proxy-relative dispersion revert: require spread improvement, a primary reversal "
            "candle, and a minimum relative-strength dislocation."
        ),
        dispersion_rel_strength_confirm_pct=0.0025,
        dispersion_zscore_improvement_min=0.20,
        dispersion_reversal_body_min_frac=0.15,
        dispersion_reversal_wick_min_frac=0.10,
        dispersion_beta_shock_max_pct=0.0080,
        dispersion_time_to_work_bars=3,
        dispersion_time_to_work_improvement_min=0.20,
        take_profit_rr=1.1,
        max_hold_minutes=45,
    )


def c4_dispersion_relative_revert_quality_v4(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_dispersion_relative_revert_confirm_v4(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_dispersion_relative_revert_quality_v4",
        description=(
            "Quality-biased proxy-relative dispersion revert with stronger confirmation and slightly faster exits."
        ),
        require_relative_volume=True,
        relative_volume_min=0.95,
        dispersion_min_correlation=0.12,
        dispersion_rel_strength_confirm_pct=0.0035,
        dispersion_zscore_improvement_min=0.35,
        dispersion_reversal_body_min_frac=0.20,
        dispersion_reversal_wick_min_frac=0.15,
        dispersion_beta_shock_max_pct=0.0065,
        dispersion_time_to_work_bars=2,
        dispersion_time_to_work_improvement_min=0.25,
        take_profit_rr=1.0,
        max_hold_minutes=35,
    )


def c4_dispersion_relative_revert_recovery_v6(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_dispersion_relative_revert_confirm_v4(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_dispersion_relative_revert_recovery_v6",
        description=(
            "Recovery-oriented dispersion revert: lighter confirmation and slightly longer hold to restore "
            "trade count without fully removing the beta-shock and reversal-candle guards."
        ),
        dispersion_zscore_entry=1.55,
        dispersion_zscore_exit=0.20,
        dispersion_zscore_stop=2.6,
        dispersion_rel_strength_confirm_pct=0.0015,
        dispersion_zscore_improvement_min=0.10,
        dispersion_reversal_body_min_frac=0.10,
        dispersion_reversal_wick_min_frac=0.05,
        dispersion_beta_shock_max_pct=0.0095,
        dispersion_time_to_work_bars=3,
        dispersion_time_to_work_improvement_min=0.12,
        max_hold_minutes=55,
    )


def c4_dispersion_relative_breakout_decay_v4(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_dispersion_relative_breakout_guard_v3(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_dispersion_relative_breakout_decay_v4",
        description=(
            "Decay-guarded relative dispersion breakout: stricter beta-shock veto and early exit if "
            "relative edge collapses after entry."
        ),
        dispersion_rel_strength_entry_pct=0.0038,
        dispersion_rel_strength_exit_pct=0.0012,
        dispersion_rel_strength_stop_pct=0.0050,
        dispersion_beta_shock_max_pct=0.0055,
        dispersion_time_to_work_bars=2,
        dispersion_breakout_rel_strength_floor_frac=0.72,
        max_hold_minutes=30,
    )


def c4_dispersion_relative_breakout_recovery_v5(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_dispersion_relative_breakout_decay_v4(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_dispersion_relative_breakout_recovery_v5",
        description=(
            "Recovery-oriented dispersion breakout: slightly looser relative-strength and decay floors to see "
            "whether the family still has life under the repaired causal contract."
        ),
        dispersion_rel_strength_entry_pct=0.0032,
        dispersion_primary_min_abs_move_pct=0.0030,
        dispersion_proxy_max_abs_move_pct=0.0105,
        dispersion_beta_shock_max_pct=0.0065,
        dispersion_breakout_rel_strength_floor_frac=0.64,
        dispersion_time_to_work_bars=3,
        max_hold_minutes=40,
    )


def c4_dispersion_relative_breakout_repair_candidates_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> List[OrbProfile]:
    return [
        c4_dispersion_relative_breakout_decay_v4(or_width_min=or_width_min),
        c4_dispersion_relative_breakout_guard_density_v1(or_width_min=or_width_min),
        c4_dispersion_relative_breakout_guard_density_spy_dia_balance_v1(or_width_min=or_width_min),
        c4_dispersion_relative_breakout_guard_density_spy_dia_offset_v1(or_width_min=or_width_min),
    ]


def c4_dispersion_relative_revert_decay_v5(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_dispersion_relative_revert_quality_v4(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_dispersion_relative_revert_decay_v5",
        description=(
            "Decay-guarded relative dispersion revert: faster stall exit and lower beta-shock tolerance "
            "for cleaner cross-sectional mean reversion."
        ),
        dispersion_zscore_entry=2.0,
        dispersion_zscore_reentry=0.9,
        dispersion_zscore_exit=0.20,
        dispersion_zscore_stop=2.9,
        dispersion_beta_shock_max_pct=0.0055,
        dispersion_time_to_work_bars=2,
        dispersion_time_to_work_improvement_min=0.30,
        max_hold_minutes=30,
    )


def c4_dispersion_relative_revert_candidates_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> List[OrbProfile]:
    return [
        c4_dispersion_relative_revert_v3(or_width_min=or_width_min),
        c4_dispersion_relative_revert_confirm_v4(or_width_min=or_width_min),
        c4_dispersion_relative_revert_quality_v4(or_width_min=or_width_min),
        c4_dispersion_relative_revert_exhaustion_v3(or_width_min=or_width_min),
        c4_dispersion_relative_revert_recovery_v6(or_width_min=or_width_min),
        c4_dispersion_relative_revert_decay_v5(or_width_min=or_width_min),
    ]


def c4_pairs_spread_proxy_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_mr_vwap_zscore_v2_conservative(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_pairs_spread_proxy_v1",
        description=(
            "Pairs spread proxy (single-leg execution): conservative z-score reversion with low-trend gating."
        ),
        require_relative_volume=False,
        require_vol_regime_filter=True,
        vol_regime_min=10.0,
        vol_regime_max=35.0,
        mr_zscore_window=30,
        mr_zscore_entry=1.7,
        mr_zscore_reentry=0.9,
        mr_zscore_stop=2.6,
        mr_zscore_target=0.20,
        max_hold_minutes=50,
    )


def c4_pairs_spread_intraday_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_pairs_spread_proxy_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_pairs_spread_intraday_v1",
        description=(
            "True pairs spread intraday profile using spread z-score reversion against a dynamic hedge ticker."
        ),
        strategy_variant="pairs_spread_v1",
        pairs_hedge_ticker="AUTO",
        pairs_beta_lookback=24,
        pairs_zscore_window=48,
        pairs_zscore_entry=1.8,
        pairs_zscore_reentry=0.8,
        pairs_zscore_exit=0.25,
        pairs_zscore_stop=2.8,
        pairs_min_correlation=0.18,
        take_profit_rr=1.2,
        max_hold_minutes=55,
        require_breakout_open_inside_range=False,
    )


def c4_pairs_spread_intraday_relaxed_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_pairs_spread_intraday_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_pairs_spread_intraday_relaxed_v1",
        description=(
            "Relaxed true pairs intraday profile with lower spread threshold for higher turnover."
        ),
        pairs_zscore_entry=1.55,
        pairs_zscore_reentry=0.70,
        pairs_zscore_exit=0.20,
        pairs_zscore_stop=2.5,
        pairs_min_correlation=0.12,
        max_hold_minutes=65,
    )


def c4_pairs_spread_intraday_quality_v2(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_pairs_spread_intraday_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_pairs_spread_intraday_quality_v2",
        description=(
            "Quality-biased true pairs intraday profile with stricter correlation and z-score excursion gates."
        ),
        pairs_beta_lookback=32,
        pairs_zscore_window=64,
        pairs_zscore_entry=2.0,
        pairs_zscore_reentry=0.9,
        pairs_zscore_exit=0.20,
        pairs_zscore_stop=3.0,
        pairs_min_correlation=0.25,
        take_profit_rr=1.0,
        max_hold_minutes=45,
    )


def c4_pairs_spread_intraday_range_quality_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_pairs_spread_intraday_quality_v2(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_pairs_spread_intraday_range_quality_v1",
        description=(
            "Range-quality intraday pairs profile for ORB-weak sessions: stronger correlation and excursion "
            "quality with a shorter hold cap and low-vol/range bias."
        ),
        require_vol_regime_filter=True,
        vol_regime_min=10.0,
        vol_regime_max=24.0,
        pairs_beta_lookback=36,
        pairs_zscore_window=72,
        pairs_zscore_entry=2.15,
        pairs_zscore_reentry=0.95,
        pairs_zscore_exit=0.18,
        pairs_zscore_stop=2.60,
        pairs_min_correlation=0.30,
        take_profit_rr=0.90,
        max_hold_minutes=36,
    )


def c4_pairs_spread_intraday_bear_reversal_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_pairs_spread_intraday_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_pairs_spread_intraday_bear_reversal_v1",
        description=(
            "Bear-reversal intraday pairs profile for anti-trend sessions: demand a wider spread excursion and "
            "fail faster when the dislocation keeps widening."
        ),
        require_vol_regime_filter=True,
        vol_regime_min=18.0,
        vol_regime_max=42.0,
        pairs_beta_lookback=28,
        pairs_zscore_window=56,
        pairs_zscore_entry=2.35,
        pairs_zscore_reentry=1.05,
        pairs_zscore_exit=0.30,
        pairs_zscore_stop=2.45,
        pairs_min_correlation=0.22,
        take_profit_rr=0.85,
        max_hold_minutes=28,
    )


def c4_pairs_spread_intraday_recovery_v3(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_pairs_spread_intraday_relaxed_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_pairs_spread_intraday_recovery_v3",
        description=(
            "Post-fix intraday pairs recovery profile: use the true spread signal instead of overnight state, "
            "with slightly easier z-score thresholds and a longer hold cap."
        ),
        pairs_beta_lookback=20,
        pairs_zscore_window=40,
        pairs_zscore_entry=1.40,
        pairs_zscore_reentry=0.60,
        pairs_zscore_exit=0.15,
        pairs_zscore_stop=2.4,
        pairs_min_correlation=0.10,
        take_profit_rr=1.0,
        max_hold_minutes=75,
    )


def c4_pairs_overnight_proxy_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_mr_overnight_regime_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_pairs_overnight_proxy_v1",
        description=(
            "Pairs overnight proxy: tighter late-session extreme fade with reduced trend persistence tolerance."
        ),
        mr_overnight_abs_return_min=0.003,
        mr_overnight_close_to_range_extreme_pct=0.15,
        mr_overnight_efficiency_ratio_max=0.35,
        mr_stop_buffer_or_mult=0.30,
    )


def c4_pairs_overnight_defensive_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_pairs_overnight_proxy_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_pairs_overnight_defensive_v1",
        description=(
            "Defensive overnight pairs/MR complement for ORB-weak regimes: fade only tighter late-session "
            "extremes and veto stronger persistence before the next-open exit."
        ),
        mr_overnight_abs_return_min=0.0035,
        mr_overnight_close_to_range_extreme_pct=0.10,
        mr_overnight_efficiency_ratio_max=0.25,
        mr_overnight_min_session_range_pct=0.004,
        mr_stop_buffer_or_mult=0.25,
        max_hold_minutes=60,
    )


def c4_mr_vwap_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    return OrbProfile(
        name="c4_mr_vwap_v1",
        description=(
            "Intraday VWAP mean-reversion profile for choppy sessions: both directions, "
            "VWAP target, and short max-hold."
        ),
        strategy_variant="mr_vwap_revert_v1",
        require_or_width_filter=False,
        opening_range_min_width_pct=0.0,
        opening_range_max_width_pct=1.0,
        allow_short=True,
        require_breakout_open_inside_range=False,
        require_relative_volume=False,
        entry_trigger_mode="close_breakout",
        stop_mode="range",
        take_profit_rr=0.0,
        exit_on_opposite_candle=True,
        opposite_candle_min_hold_minutes=5,
        max_hold_minutes=75,
        mr_band_or_mult=0.9,
        mr_min_distance_from_vwap_pct=0.001,
        mr_reentry_buffer_or_mult=0.15,
        mr_stop_buffer_or_mult=0.15,
        mr_take_profit_mode="vwap",
        mr_take_profit_rr=1.0,
        mr_require_reversal_candle=True,
    )


def c4_mr_vwap_conservative_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_mr_vwap_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_mr_vwap_conservative_v1",
        description=(
            "Conservative VWAP mean-reversion profile: larger deviation band and stronger "
            "relative-volume floor to avoid weak reversion attempts."
        ),
        require_relative_volume=True,
        relative_volume_min=1.1,
        mr_band_or_mult=1.2,
        mr_reentry_buffer_or_mult=0.2,
        max_hold_minutes=60,
    )


def c4_mr_vwap_zscore_v2(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    return OrbProfile(
        name="c4_mr_vwap_zscore_v2",
        description=(
            "VWAP z-score mean-reversion profile for range sessions: z-score re-entry trigger, "
            "VWAP slope guard, and short max-hold without ORB-width prefiltering."
        ),
        strategy_variant="mr_vwap_zscore_v2",
        require_or_width_filter=False,
        opening_range_min_width_pct=0.0,
        opening_range_max_width_pct=1.0,
        allow_short=True,
        require_breakout_open_inside_range=False,
        require_relative_volume=False,
        entry_trigger_mode="close_breakout",
        stop_mode="range",
        take_profit_rr=0.0,
        exit_on_opposite_candle=True,
        opposite_candle_min_hold_minutes=5,
        max_hold_minutes=60,
        mr_take_profit_mode="zscore",
        mr_take_profit_rr=1.0,
        mr_require_reversal_candle=True,
        mr_zscore_window=20,
        mr_zscore_entry=1.6,
        mr_zscore_reentry=0.8,
        mr_zscore_stop=2.4,
        mr_zscore_target=0.25,
        mr_sigma_min_pct=0.0,
        mr_sigma_max_pct=1.0,
        mr_vwap_slope_lookback=3,
        mr_vwap_slope_max_pct=0.0025,
    )


def c4_mr_vwap_zscore_v2_conservative(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_mr_vwap_zscore_v2(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_mr_vwap_zscore_v2_conservative",
        description=(
            "Conservative z-score MR: wider excursion threshold, stronger RVOL floor, and "
            "narrower acceptable intraday sigma regime."
        ),
        require_relative_volume=True,
        relative_volume_min=1.1,
        mr_zscore_entry=1.9,
        mr_zscore_reentry=1.0,
        mr_zscore_stop=2.8,
        mr_zscore_target=0.20,
        mr_sigma_min_pct=0.0007,
        mr_sigma_max_pct=0.012,
        mr_vwap_slope_max_pct=0.0017,
        max_hold_minutes=45,
    )


def c4_mr_vwap_zscore_v2_fast(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_mr_vwap_zscore_v2(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_mr_vwap_zscore_v2_fast",
        description=(
            "Higher-frequency z-score MR: lower excursion threshold and shorter hold horizon "
            "to realize quick mean reversion."
        ),
        mr_zscore_entry=1.3,
        mr_zscore_reentry=0.6,
        mr_zscore_stop=2.1,
        mr_zscore_target=0.15,
        max_hold_minutes=35,
        opposite_candle_min_hold_minutes=3,
    )


def c4_mr_vwap_zscore_v3_adaptive(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_mr_vwap_zscore_v2(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_mr_vwap_zscore_v3_adaptive",
        description=(
            "Adaptive z-score MR that tightens/loosens entry and stop thresholds from trend and volatility pressure."
        ),
        mr_adaptive_enabled=True,
        mr_adaptive_entry_min=1.35,
        mr_adaptive_entry_max=2.45,
        mr_adaptive_stop_min=2.1,
        mr_adaptive_stop_max=3.4,
        mr_adaptive_trend_weight=0.70,
        mr_adaptive_vol_weight=0.30,
        mr_zscore_target=0.20,
        max_hold_minutes=50,
        require_relative_volume=True,
        relative_volume_min=1.05,
    )


def c4_mr_vwap_zscore_v3_adaptive_quality_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_mr_vwap_zscore_v3_adaptive(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_mr_vwap_zscore_v3_adaptive_quality_v1",
        description=(
            "Quality-biased adaptive MR profile with tighter sigma/slope regime and stronger RVOL floor."
        ),
        require_relative_volume=True,
        relative_volume_min=1.10,
        mr_sigma_min_pct=0.0007,
        mr_sigma_max_pct=0.012,
        mr_vwap_slope_max_pct=0.0018,
        mr_adaptive_entry_min=1.5,
        mr_adaptive_entry_max=2.6,
        mr_adaptive_stop_min=2.3,
        mr_adaptive_stop_max=3.6,
        max_hold_minutes=45,
    )


def c4_mr_vwap_zscore_v2_rr(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_mr_vwap_zscore_v2(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_mr_vwap_zscore_v2_rr",
        description="Z-score MR with fixed R-multiple exits instead of VWAP/z-score target exits.",
        mr_take_profit_mode="rr",
        mr_take_profit_rr=1.2,
    )


def c4_mr_vwap_zscore_v2_long_only(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_mr_vwap_zscore_v2_conservative(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_mr_vwap_zscore_v2_long_only",
        description="Conservative z-score MR restricted to long-call entries only.",
        allow_short=False,
    )


def c4_mr_vwap_zscore_v2_sideways(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_mr_vwap_zscore_v2_conservative(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_mr_vwap_zscore_v2_sideways",
        description="Conservative z-score MR with additional volatility-regime bounds for sideways sessions.",
        require_vol_regime_filter=True,
        vol_regime_min=14.0,
        vol_regime_max=30.0,
    )


def c4_mr_vwap_exhaustion_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_mr_vwap_zscore_v2(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_mr_vwap_exhaustion_v1",
        description=(
            "VWAP exhaustion MR: require a real stretch beyond the opening range plus a reclaim "
            "candle before fading back toward VWAP."
        ),
        strategy_variant="mr_vwap_exhaustion_v1",
        require_relative_volume=True,
        relative_volume_min=0.95,
        mr_zscore_entry=1.8,
        mr_zscore_reentry=0.55,
        mr_zscore_stop=2.7,
        mr_zscore_target=0.18,
        mr_vwap_slope_max_pct=0.0018,
        mr_session_extension_min_or_frac=0.18,
        mr_reversal_body_min_frac=0.18,
        mr_reversal_wick_min_frac=0.18,
        mr_trend_ema_spread_max_pct=0.0030,
        mr_volume_climax_multiple_min=1.15,
        mr_trend_day_max_move_pct=0.0080,
        mr_time_to_work_bars=3,
        mr_time_to_work_min_rr=0.10,
        mr_target_stretch_frac=0.75,
        max_hold_minutes=40,
    )


def c4_mr_vwap_exhaustion_quality_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_mr_vwap_exhaustion_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_mr_vwap_exhaustion_quality_v1",
        description=(
            "Quality-biased exhaustion MR with stronger stretch, reversal, and trend-neutrality guards."
        ),
        relative_volume_min=1.05,
        mr_zscore_entry=2.1,
        mr_zscore_reentry=0.75,
        mr_zscore_stop=3.0,
        mr_zscore_target=0.15,
        mr_session_extension_min_or_frac=0.28,
        mr_reversal_body_min_frac=0.22,
        mr_reversal_wick_min_frac=0.22,
        mr_trend_ema_spread_max_pct=0.0022,
        mr_volume_climax_multiple_min=1.25,
        mr_trend_day_max_move_pct=0.0060,
        mr_time_to_work_bars=2,
        mr_time_to_work_min_rr=0.15,
        mr_target_stretch_frac=0.60,
        max_hold_minutes=30,
    )


def c4_mr_vwap_exhaustion_relaxed_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_mr_vwap_exhaustion_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_mr_vwap_exhaustion_relaxed_v1",
        description=(
            "Relaxed exhaustion MR that keeps the stretch/reclaim archetype but lowers the confirmation burden."
        ),
        require_relative_volume=False,
        mr_zscore_entry=1.5,
        mr_zscore_reentry=0.45,
        mr_zscore_stop=2.4,
        mr_zscore_target=0.22,
        mr_session_extension_min_or_frac=0.10,
        mr_reversal_body_min_frac=0.10,
        mr_reversal_wick_min_frac=0.12,
        mr_trend_ema_spread_max_pct=0.0038,
        mr_volume_climax_multiple_min=1.0,
        mr_trend_day_max_move_pct=0.0100,
        mr_time_to_work_bars=4,
        mr_time_to_work_min_rr=0.05,
        mr_target_stretch_frac=0.90,
        max_hold_minutes=50,
    )


def c4_mr_vwap_exhaustion_guard_v2(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_mr_vwap_exhaustion_quality_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_mr_vwap_exhaustion_guard_v2",
        description=(
            "Guarded exhaustion MR: stronger anti-trend veto, faster time-to-work failure, and "
            "more conservative stretch-normalized targets."
        ),
        relative_volume_min=1.0,
        mr_zscore_entry=1.95,
        mr_zscore_reentry=0.70,
        mr_zscore_stop=2.9,
        mr_zscore_target=0.18,
        mr_session_extension_min_or_frac=0.24,
        mr_trend_day_max_move_pct=0.0055,
        mr_time_to_work_bars=2,
        mr_time_to_work_min_rr=0.18,
        mr_target_stretch_frac=0.55,
        max_hold_minutes=28,
    )


def c4_mr_overnight_regime_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    _ = or_width_min  # retained to keep a consistent profile function signature
    return OrbProfile(
        name="c4_mr_overnight_regime_v1",
        description=(
            "Regime-aware overnight mean reversion: fade late-session extremes in choppy sessions and exit next open."
        ),
        strategy_variant="mr_overnight_regime_v1",
        entry_start_time="15:50",
        entry_cutoff_time="15:59",
        exit_time="09:31",
        allow_short=True,
        require_breakout_open_inside_range=False,
        require_or_width_filter=False,
        opening_range_min_width_pct=0.0,
        opening_range_max_width_pct=1.0,
        require_relative_volume=False,
        exit_on_opposite_candle=False,
        max_hold_minutes=0,
        mr_overnight_abs_return_min=0.004,
        mr_overnight_close_to_range_extreme_pct=0.20,
        mr_overnight_efficiency_ratio_max=0.45,
        mr_overnight_min_session_range_pct=0.003,
        mr_stop_buffer_or_mult=0.35,
    )


def c4_momentum_accel_tight_v2(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_momentum_accel_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_momentum_accel_tight_v2",
        description=(
            "Tight momentum acceleration variant from phase sweeps: stronger breakout and volume "
            "confirmation with shorter holding horizon."
        ),
        momentum_breakout_min_or_frac=0.16,
        momentum_close_location_min=0.72,
        momentum_volume_multiple_min=1.7,
        max_hold_minutes=45,
    )


def c4_dispersion_revert_tight(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_dispersion_revert_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_dispersion_revert_tight",
        description=(
            "Tight dispersion mean-reversion variant from phase sweeps with stricter z-score entry."
        ),
        mr_zscore_entry=1.9,
        mr_zscore_stop=2.8,
        max_hold_minutes=50,
    )


def c4_dispersion_revert_quality_v3(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_dispersion_revert_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_dispersion_revert_quality_v3",
        description=(
            "Quality-biased dispersion revert variant from phase sweeps with stricter z-score "
            "and RVOL constraints."
        ),
        mr_zscore_entry=2.0,
        mr_zscore_stop=2.9,
        mr_zscore_target=0.22,
        max_hold_minutes=45,
        relative_volume_min=1.10,
    )


def c4_pairs_overnight_relaxed(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_pairs_overnight_proxy_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_pairs_overnight_relaxed",
        description=(
            "Relaxed pairs overnight proxy variant from phase sweeps with lower overnight move "
            "threshold and looser efficiency cap."
        ),
        mr_overnight_abs_return_min=0.003,
        mr_overnight_efficiency_ratio_max=0.50,
    )


def c4_pairs_overnight_fast_v2(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_pairs_overnight_proxy_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_pairs_overnight_fast_v2",
        description=(
            "Fast pairs overnight proxy variant from phase sweeps with tighter hold cap."
        ),
        mr_overnight_abs_return_min=0.004,
        max_hold_minutes=45,
    )


def c4_mr_side_loose(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_mr_vwap_zscore_v2_conservative(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_mr_side_loose",
        description=(
            "Loose sideways MR variant from phase sweeps with easier entry and wider hold horizon."
        ),
        mr_zscore_entry=1.4,
        mr_zscore_stop=2.2,
        mr_zscore_target=0.30,
        max_hold_minutes=75,
    )


def c4_mr_rr_fast_v2(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_mr_vwap_zscore_v2_rr(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_mr_rr_fast_v2",
        description=(
            "Fast RR-based MR variant from phase sweeps with tighter entry/stop and shorter hold cap."
        ),
        mr_zscore_entry=1.8,
        mr_zscore_stop=2.6,
        max_hold_minutes=50,
    )


def c4_mr_rr_fast_guard_v3(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_mr_rr_fast_v2(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_mr_rr_fast_guard_v3",
        description=(
            "Guarded fast RR MR: modest anti-trend veto and early time-to-work exit to avoid fading "
            "persistent directional sessions."
        ),
        mr_zscore_entry=1.85,
        mr_zscore_stop=2.55,
        mr_zscore_target=0.20,
        mr_vwap_slope_max_pct=0.0018,
        mr_trend_day_max_move_pct=0.0065,
        mr_time_to_work_bars=2,
        mr_time_to_work_min_rr=0.12,
        mr_target_stretch_frac=0.70,
        max_hold_minutes=40,
    )


def c4_mr_rr_fast_recovery_v4(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_mr_rr_fast_guard_v3(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_mr_rr_fast_recovery_v4",
        description=(
            "Post-fix MR recovery profile: keep the anti-trend veto, but relax entry and hold constraints enough "
            "to recover trade count under the repaired causal framework."
        ),
        mr_zscore_entry=1.65,
        mr_zscore_stop=2.45,
        mr_zscore_target=0.18,
        mr_vwap_slope_max_pct=0.0022,
        mr_trend_day_max_move_pct=0.0072,
        mr_time_to_work_bars=3,
        mr_time_to_work_min_rr=0.08,
        mr_target_stretch_frac=0.78,
        max_hold_minutes=55,
    )


def c4_mr_vwap_exhaustion_balance_v3(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_mr_vwap_exhaustion_guard_v2(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_mr_vwap_exhaustion_balance_v3",
        description=(
            "Balanced exhaustion MR: softer stretch and trend guards than the guarded variant, while keeping "
            "reclaim confirmation and time-to-work exits."
        ),
        mr_zscore_entry=1.75,
        mr_zscore_reentry=0.75,
        mr_zscore_stop=2.70,
        mr_zscore_target=0.20,
        mr_session_extension_min_or_frac=0.18,
        mr_trend_day_max_move_pct=0.0065,
        mr_time_to_work_bars=3,
        mr_time_to_work_min_rr=0.10,
        mr_target_stretch_frac=0.62,
        max_hold_minutes=36,
    )


def c4_mr_overnight_relaxed_v2(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_mr_overnight_regime_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_mr_overnight_relaxed_v2",
        description=(
            "Relaxed overnight MR variant from phase sweeps with lower move threshold and "
            "looser efficiency cap."
        ),
        mr_overnight_abs_return_min=0.003,
        mr_overnight_efficiency_ratio_max=0.50,
        max_hold_minutes=90,
    )


def c4_mr_complement_candidates_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> List[OrbProfile]:
    return [
        c18_vwap_mr_balance_v1(or_width_min=or_width_min),
        c18_vwap_mr_quality_v1(or_width_min=or_width_min),
        c18_vwap_mr_regime_v1(or_width_min=or_width_min),
        c18_vwap_mr_fast_v1(or_width_min=or_width_min),
        c18_vwap_mr_long_only_quality_v2(or_width_min=or_width_min),
        c18_vwap_mr_long_only_regime_v2(or_width_min=or_width_min),
        c4_mr_vwap_zscore_v2_sideways(or_width_min=or_width_min),
        c4_mr_vwap_zscore_v3_adaptive_quality_v1(or_width_min=or_width_min),
        c4_mr_vwap_exhaustion_guard_v2(or_width_min=or_width_min),
        c4_mr_vwap_exhaustion_balance_v3(or_width_min=or_width_min),
        c4_mr_rr_fast_recovery_v4(or_width_min=or_width_min),
        c4_mr_overnight_regime_v1(or_width_min=or_width_min),
        c4_mr_overnight_relaxed_v2(or_width_min=or_width_min),
    ]


def c4_paper_winners() -> List[OrbProfile]:
    return [
        c4_long_only_rr15(),
        c4_long_only_rr15_recovery_v2(),
        c4_rr15_r1(),
        c4_freq_v1(),
        c4_freq_v1_f4(),
        c4_dispersion_breakout_v1(),
        c4_dispersion_relative_revert_confirm_v4(),
        c4_dispersion_relative_revert_recovery_v6(),
        c4_mr_overnight_regime_v1(),
        c4_mr_overnight_relaxed_v2(),
        c4_mr_vwap_exhaustion_v1(),
        c4_mr_vwap_exhaustion_balance_v3(),
        c4_pairs_overnight_proxy_v1(),
        c4_pairs_spread_intraday_recovery_v3(),
        c4_pairs_overnight_relaxed(),
        c4_mr_rr_fast_v2(),
        c4_mr_rr_fast_recovery_v4(),
        c4_momentum_accel_tight_v2(),
        c4_momentum_vwap_reclaim_recovery_v2(),
    ]


def c5_opening_drive_candidates(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> List[OrbProfile]:
    return [
        c5_opening_drive_pullback_v1(or_width_min=or_width_min),
        c5_opening_drive_pullback_guard_v1(or_width_min=or_width_min),
        c5_opening_drive_pullback_relaxed_v1(or_width_min=or_width_min),
        c5_opening_drive_pullback_long_only_v1(or_width_min=or_width_min),
        c5_opening_drive_pullback_reclaim_v2(or_width_min=or_width_min),
        c5_opening_drive_pullback_quality_v2(or_width_min=or_width_min),
        c5_opening_drive_pullback_long_only_v2(or_width_min=or_width_min),
        c5_opening_drive_pullback_prev_break_v3(or_width_min=or_width_min),
        c5_opening_drive_pullback_hold_open_v3(or_width_min=or_width_min),
        c5_opening_drive_pullback_long_only_balance_v4(or_width_min=or_width_min),
        c5_opening_drive_pullback_long_only_fast_v4(or_width_min=or_width_min),
        c5_opening_drive_pullback_long_only_regime_v5(or_width_min=or_width_min),
    ]


def c6_opening_exhaustion_candidates(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> List[OrbProfile]:
    return [
        c6_opening_exhaustion_reversal_v1(or_width_min=or_width_min),
        c6_opening_exhaustion_reversal_quality_v1(or_width_min=or_width_min),
        c6_opening_exhaustion_reversal_regime_v1(or_width_min=or_width_min),
        c6_opening_exhaustion_reversal_long_only_v1(or_width_min=or_width_min),
        c6_opening_exhaustion_reversal_short_only_v1(or_width_min=or_width_min),
        c6_opening_exhaustion_reversal_balance_v2(or_width_min=or_width_min),
        c6_opening_exhaustion_reversal_regime_v2(or_width_min=or_width_min),
        c6_opening_exhaustion_reversal_long_only_v2(or_width_min=or_width_min),
        c6_opening_exhaustion_reversal_short_only_v2(or_width_min=or_width_min),
    ]


def c16_opening_exhaustion_candidates(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> List[OrbProfile]:
    return [
        c16_opening_exhaustion_balance_v3(or_width_min=or_width_min),
        c16_opening_exhaustion_quality_v3(or_width_min=or_width_min),
        c16_opening_exhaustion_regime_v3(or_width_min=or_width_min),
        c16_opening_exhaustion_long_only_v3(or_width_min=or_width_min),
        c16_opening_exhaustion_short_only_v3(or_width_min=or_width_min),
    ]


def c7_opening_failure_candidates(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> List[OrbProfile]:
    return [
        c7_opening_failure_reversal_v1(or_width_min=or_width_min),
        c7_opening_failure_reversal_quality_v1(or_width_min=or_width_min),
        c7_opening_failure_reversal_regime_v1(or_width_min=or_width_min),
        c7_opening_failure_reversal_long_only_v1(or_width_min=or_width_min),
        c7_opening_failure_reversal_short_only_v1(or_width_min=or_width_min),
        c7_opening_failure_reversal_long_only_balance_v2(or_width_min=or_width_min),
        c7_opening_failure_reversal_long_only_regime_v2(or_width_min=or_width_min),
    ]


def c8_event_drive_balance_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_orb_event_drive_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c8_event_drive_balance_v1",
        description=(
            "Event-drive continuation: require a meaningful gap day and first strong continuation, "
            "but with tighter risk and faster monetization than the generic event-drive profile."
        ),
        stop_mode="range",
        take_profit_rr=1.25,
        max_hold_minutes=45,
        early_fail_minutes=18,
        early_fail_min_rr=0.08,
        break_even_trigger_rr=0.45,
        require_breakout_open_inside_range=False,
        relative_volume_min=0.9,
        event_drive_min_gap_abs_return=0.0045,
        event_drive_min_breakout_or_frac=0.08,
        event_drive_close_location_min=0.58,
        event_drive_min_volume_multiple=1.15,
    )


def c8_event_drive_quality_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c8_event_drive_balance_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c8_event_drive_quality_v1",
        description=(
            "Higher-conviction event-drive continuation: stronger gap, stronger close location, "
            "and slightly higher relative-volume demand."
        ),
        relative_volume_min=1.0,
        event_drive_min_gap_abs_return=0.006,
        event_drive_min_breakout_or_frac=0.10,
        event_drive_close_location_min=0.63,
        event_drive_min_volume_multiple=1.30,
        take_profit_rr=1.35,
    )


def c8_event_drive_regime_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c8_event_drive_quality_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c8_event_drive_regime_v1",
        description=(
            "Calmer-day event-drive continuation: keep the gap and drive quality, but only participate "
            "when broader realized volatility and prior-day range are not already extreme."
        ),
        require_vol_regime_filter=True,
        vol_regime_min=10.0,
        vol_regime_max=35.0,
        require_prior_day_range_filter=True,
        prior_day_range_max_pct=0.025,
    )


def c8_event_drive_long_only_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c8_event_drive_regime_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c8_event_drive_long_only_v1",
        description=(
            "Long-only event-drive continuation tuned for index ETFs, keeping only upside event sessions "
            "and cutting the historically weaker short branch."
        ),
        allow_long=True,
        allow_short=False,
    )


def c8_event_drive_fast_v2(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c8_event_drive_long_only_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c8_event_drive_fast_v2",
        description=(
            "Fast event-drive continuation: slightly looser gap threshold and faster exit profile to "
            "trade more often without relying on long holding periods."
        ),
        relative_volume_min=0.85,
        event_drive_min_gap_abs_return=0.004,
        event_drive_min_breakout_or_frac=0.06,
        event_drive_min_volume_multiple=1.05,
        take_profit_rr=1.10,
        break_even_trigger_rr=0.35,
        early_fail_minutes=12,
        early_fail_min_rr=0.05,
        max_hold_minutes=35,
    )


def c8_event_drive_candidates(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> List[OrbProfile]:
    return [
        c8_event_drive_balance_v1(or_width_min=or_width_min),
        c8_event_drive_quality_v1(or_width_min=or_width_min),
        c8_event_drive_regime_v1(or_width_min=or_width_min),
        c8_event_drive_long_only_v1(or_width_min=or_width_min),
        c8_event_drive_fast_v2(or_width_min=or_width_min),
    ]


def c19_event_drive_balance_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_orb_event_drive_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c19_event_drive_balance_v1",
        description=(
            "Higher-frequency event-drive continuation that keeps the opening gap requirement, but lowers the "
            "breakout and volume bars enough to trade more often on ETF index event days."
        ),
        stop_mode="range",
        take_profit_rr=1.20,
        max_hold_minutes=45,
        early_fail_minutes=14,
        early_fail_min_rr=0.05,
        break_even_trigger_rr=0.35,
        require_breakout_open_inside_range=False,
        relative_volume_min=0.85,
        event_drive_min_gap_abs_return=0.0035,
        event_drive_min_breakout_or_frac=0.06,
        event_drive_close_location_min=0.55,
        event_drive_min_volume_multiple=1.05,
    )


def c19_event_drive_quality_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c19_event_drive_balance_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c19_event_drive_quality_v1",
        description=(
            "Higher-conviction version of the event-drive continuation with stronger close location and volume."
        ),
        relative_volume_min=0.95,
        take_profit_rr=1.30,
        event_drive_min_gap_abs_return=0.0045,
        event_drive_min_breakout_or_frac=0.08,
        event_drive_close_location_min=0.60,
        event_drive_min_volume_multiple=1.15,
    )


def c19_event_drive_regime_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c19_event_drive_quality_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c19_event_drive_regime_v1",
        description=(
            "Event-drive continuation restricted to calmer volatility regimes so the first continuation has a "
            "better chance of sustaining without extreme slippage."
        ),
        require_vol_regime_filter=True,
        vol_regime_min=10.0,
        vol_regime_max=34.0,
        require_prior_day_range_filter=True,
        prior_day_range_max_pct=0.025,
        allow_short=False,
    )


def c19_event_drive_fast_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c19_event_drive_balance_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c19_event_drive_fast_v1",
        description=(
            "Fast event-drive continuation with shorter hold, lower target, and earlier break-even to improve "
            "survivability under option execution costs."
        ),
        take_profit_rr=1.00,
        max_hold_minutes=30,
        early_fail_minutes=10,
        early_fail_min_rr=0.03,
        break_even_trigger_rr=0.25,
        event_drive_min_gap_abs_return=0.0030,
        event_drive_min_breakout_or_frac=0.05,
        event_drive_close_location_min=0.52,
        event_drive_min_volume_multiple=1.00,
    )


def c19_event_drive_candidates(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> List[OrbProfile]:
    return [
        c19_event_drive_balance_v1(or_width_min=or_width_min),
        c19_event_drive_quality_v1(or_width_min=or_width_min),
        c19_event_drive_regime_v1(or_width_min=or_width_min),
        c19_event_drive_fast_v1(or_width_min=or_width_min),
    ]


def c57_event_drive_preopen_balance_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c19_event_drive_balance_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c57_event_drive_preopen_balance_v1",
        description=(
            "Event-drive continuation with causal pre-open context gating on premarket bars, gap, range, and "
            "recent realized volume so liquid gap days can be filtered before the open."
        ),
        require_premarket_context=True,
        premarket_bars_min=10,
        premarket_volume_pct_adv_min=0.02,
        premarket_gap_abs_return_min=0.003,
        premarket_range_min_pct=0.0015,
        premarket_range_max_pct=0.0250,
        recent_daily_volume_ratio_min=0.95,
    )


def c57_event_drive_preopen_quality_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c57_event_drive_preopen_balance_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c57_event_drive_preopen_quality_v1",
        description=(
            "Higher-conviction pre-open event-drive continuation with stronger premarket volume, gap, and "
            "range requirements."
        ),
        premarket_volume_pct_adv_min=0.04,
        premarket_gap_abs_return_min=0.005,
        premarket_range_min_pct=0.0025,
        premarket_range_max_pct=0.0300,
        recent_daily_volume_ratio_min=1.05,
        event_drive_min_volume_multiple=1.15,
    )


def c57_event_drive_preopen_regime_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c57_event_drive_preopen_quality_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c57_event_drive_preopen_regime_v1",
        description=(
            "Pre-open event-drive continuation with the quality gates plus calm-regime and prior-range filters."
        ),
        require_vol_regime_filter=True,
        vol_regime_min=12.0,
        vol_regime_max=35.0,
        require_prior_day_range_filter=True,
        prior_day_range_max_pct=0.025,
    )


def c57_event_drive_preopen_candidates_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> List[OrbProfile]:
    return [
        c57_event_drive_preopen_balance_v1(or_width_min=or_width_min),
        c57_event_drive_preopen_quality_v1(or_width_min=or_width_min),
        c57_event_drive_preopen_regime_v1(or_width_min=or_width_min),
    ]


def c9_opening_compression_balance_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_orb_transition_compression_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c9_opening_compression_balance_v1",
        description=(
            "Opening compression expansion: trade the first clean expansion after a short coil, "
            "using tighter structural risk than the generic compression baseline."
        ),
        stop_mode="range",
        take_profit_rr=1.25,
        break_even_trigger_rr=0.45,
        early_fail_minutes=15,
        early_fail_min_rr=0.06,
        max_hold_minutes=40,
        require_relative_volume=True,
        relative_volume_min=0.85,
        compression_lookback_bars=4,
        compression_max_range_pct=0.0030,
        compression_breakout_buffer_or_frac=0.02,
        compression_min_volume_multiple=1.05,
    )


def c9_opening_compression_quality_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c9_opening_compression_balance_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c9_opening_compression_quality_v1",
        description=(
            "Higher-conviction opening compression expansion: demand a tighter coil and stronger expansion volume."
        ),
        relative_volume_min=0.95,
        compression_lookback_bars=5,
        compression_max_range_pct=0.0022,
        compression_breakout_buffer_or_frac=0.03,
        compression_min_volume_multiple=1.20,
        take_profit_rr=1.35,
    )


def c9_opening_compression_regime_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c9_opening_compression_quality_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c9_opening_compression_regime_v1",
        description=(
            "Calmer-day opening compression expansion: keep only sessions where broader volatility is not already extreme."
        ),
        require_vol_regime_filter=True,
        vol_regime_min=10.0,
        vol_regime_max=32.0,
        require_prior_day_range_filter=True,
        prior_day_range_max_pct=0.022,
    )


def c9_opening_compression_long_only_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c9_opening_compression_regime_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c9_opening_compression_long_only_v1",
        description=(
            "Long-only opening compression expansion tuned for index ETFs, removing the weaker short branch."
        ),
        allow_long=True,
        allow_short=False,
    )


def c9_opening_compression_fast_v2(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c9_opening_compression_long_only_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c9_opening_compression_fast_v2",
        description=(
            "Faster opening compression expansion: looser compression requirements and quicker monetization."
        ),
        relative_volume_min=0.80,
        take_profit_rr=1.05,
        break_even_trigger_rr=0.35,
        early_fail_minutes=10,
        early_fail_min_rr=0.04,
        max_hold_minutes=30,
        compression_lookback_bars=3,
        compression_max_range_pct=0.0035,
        compression_breakout_buffer_or_frac=0.015,
        compression_min_volume_multiple=0.95,
    )


def c9_opening_compression_candidates(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> List[OrbProfile]:
    return [
        c9_opening_compression_balance_v1(or_width_min=or_width_min),
        c9_opening_compression_quality_v1(or_width_min=or_width_min),
        c9_opening_compression_regime_v1(or_width_min=or_width_min),
        c9_opening_compression_long_only_v1(or_width_min=or_width_min),
        c9_opening_compression_fast_v2(or_width_min=or_width_min),
    ]


def c58_orb_transition_compression_consistency_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> OrbProfile:
    base = c4_orb_transition_compression_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c58_orb_transition_compression_consistency_v1",
        description=(
            "Consistency-focused transition compression breakout: tighter coils, calmer-day filters, "
            "and earlier risk reduction to improve fold-level stability."
        ),
        take_profit_rr=1.35,
        break_even_trigger_rr=0.35,
        early_fail_minutes=15,
        early_fail_min_rr=0.05,
        max_hold_minutes=45,
        require_relative_volume=True,
        relative_volume_min=0.95,
        require_vol_regime_filter=True,
        vol_regime_min=10.0,
        vol_regime_max=30.0,
        require_prior_day_range_filter=True,
        prior_day_range_max_pct=0.022,
        compression_lookback_bars=6,
        compression_max_range_pct=0.0020,
        compression_breakout_buffer_or_frac=0.025,
        compression_min_volume_multiple=1.25,
    )


def c58_opening_compression_consistency_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c58_orb_transition_compression_consistency_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c58_opening_compression_consistency_v1",
        description=(
            "Opening compression balance candidate tuned for robustness: tighter coil quality, "
            "quicker invalidation, and shorter hold to reduce noisy late-session drift."
        ),
        stop_mode="range",
        take_profit_rr=1.15,
        break_even_trigger_rr=0.35,
        early_fail_minutes=12,
        early_fail_min_rr=0.08,
        max_hold_minutes=32,
        relative_volume_min=1.0,
        compression_lookback_bars=5,
        compression_max_range_pct=0.0022,
        compression_breakout_buffer_or_frac=0.025,
        compression_min_volume_multiple=1.20,
    )


def c58_opening_compression_consistency_regime_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> OrbProfile:
    base = c58_opening_compression_consistency_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c58_opening_compression_consistency_regime_v1",
        description=(
            "Calmer-day opening compression consistency candidate with tighter session filtering "
            "and stronger breakout volume."
        ),
        require_vol_regime_filter=True,
        vol_regime_min=10.0,
        vol_regime_max=26.0,
        require_prior_day_range_filter=True,
        prior_day_range_max_pct=0.018,
        relative_volume_min=1.05,
        compression_min_volume_multiple=1.25,
        take_profit_rr=1.20,
    )


def c58_opening_compression_consistency_candidates_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> List[OrbProfile]:
    return [
        c58_opening_compression_consistency_v1(or_width_min=or_width_min),
        c58_opening_compression_consistency_regime_v1(or_width_min=or_width_min),
    ]


def c61_opening_compression_stability_balance_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_orb_transition_compression_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c61_opening_compression_stability_balance_v1",
        description=(
            "Midpoint opening compression expansion between c9 frequency and c58 strictness, "
            "keeping calmer-day filters without starving the trade count."
        ),
        stop_mode="range",
        take_profit_rr=1.20,
        break_even_trigger_rr=0.40,
        early_fail_minutes=12,
        early_fail_min_rr=0.06,
        max_hold_minutes=34,
        require_relative_volume=True,
        relative_volume_min=0.90,
        require_vol_regime_filter=True,
        vol_regime_min=10.0,
        vol_regime_max=28.0,
        require_prior_day_range_filter=True,
        prior_day_range_max_pct=0.020,
        compression_lookback_bars=5,
        compression_max_range_pct=0.0025,
        compression_breakout_buffer_or_frac=0.0225,
        compression_min_volume_multiple=1.15,
    )


def c61_opening_compression_stability_regime_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c61_opening_compression_stability_balance_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c61_opening_compression_stability_regime_v1",
        description=(
            "Calmer-day midpoint opening compression expansion with a slightly tighter prior-range "
            "and volume confirmation filter."
        ),
        relative_volume_min=1.00,
        vol_regime_max=24.0,
        prior_day_range_max_pct=0.017,
        compression_min_volume_multiple=1.20,
        take_profit_rr=1.15,
    )


def c61_opening_compression_stability_candidates_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> List[OrbProfile]:
    return [
        c61_opening_compression_stability_balance_v1(or_width_min=or_width_min),
        c61_opening_compression_stability_regime_v1(or_width_min=or_width_min),
    ]


def c63_opening_compression_smoother_balance_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c9_opening_compression_balance_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c63_opening_compression_smoother_balance_v1",
        description=(
            "Smoother opening compression balance candidate that keeps c9 trade density while "
            "tightening exit timing and compression quality to reduce month-to-month path swings."
        ),
        stop_mode="range",
        take_profit_rr=1.10,
        break_even_trigger_rr=0.30,
        early_fail_minutes=10,
        early_fail_min_rr=0.05,
        max_hold_minutes=28,
        require_relative_volume=True,
        relative_volume_min=0.90,
        compression_lookback_bars=4,
        compression_max_range_pct=0.0028,
        compression_breakout_buffer_or_frac=0.018,
        compression_min_volume_multiple=1.08,
    )


def c63_opening_compression_smoother_quality_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c63_opening_compression_smoother_balance_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c63_opening_compression_smoother_quality_v1",
        description=(
            "Higher-conviction smoother opening compression candidate that adds calmer-day "
            "filters without collapsing the c9-style setup count."
        ),
        relative_volume_min=0.95,
        require_vol_regime_filter=True,
        vol_regime_min=10.0,
        vol_regime_max=30.0,
        require_prior_day_range_filter=True,
        prior_day_range_max_pct=0.023,
        compression_min_volume_multiple=1.15,
    )


def c63_opening_compression_smoother_candidates_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> List[OrbProfile]:
    return [
        c63_opening_compression_smoother_balance_v1(or_width_min=or_width_min),
        c63_opening_compression_smoother_quality_v1(or_width_min=or_width_min),
    ]


def c10_relative_strength_balance_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    return OrbProfile(
        name="c10_relative_strength_balance_v1",
        description=(
            "Intraday relative-strength continuation: buy the symbol only when it leads its benchmark "
            "proxy, survives a controlled pullback into value, and reclaims trend support."
        ),
        strategy_variant="relative_strength_continuation_v1",
        opening_range_minutes=5,
        entry_start_time="09:35",
        entry_cutoff_time="11:45",
        exit_time="15:55",
        allow_long=True,
        allow_short=False,
        stop_mode="range",
        take_profit_rr=1.35,
        break_even_trigger_rr=0.50,
        early_fail_minutes=15,
        early_fail_min_rr=0.05,
        max_hold_minutes=50,
        require_relative_volume=True,
        relative_volume_min=0.90,
        trend_ema_fast=8,
        trend_ema_slow=21,
        require_vol_regime_filter=False,
        dispersion_proxy_ticker="AUTO",
        dispersion_beta_lookback=18,
        dispersion_min_correlation=0.10,
        dispersion_rel_strength_entry_pct=0.0035,
        dispersion_rel_strength_exit_pct=0.0012,
        dispersion_rel_strength_stop_pct=0.0050,
        dispersion_primary_min_abs_move_pct=0.0035,
        dispersion_proxy_max_abs_move_pct=0.0120,
        dispersion_rel_strength_confirm_pct=0.0025,
        dispersion_beta_shock_max_pct=0.0080,
        dispersion_time_to_work_bars=3,
        dispersion_breakout_rel_strength_floor_frac=0.65,
        drive_min_abs_return_pct=0.0035,
        drive_pullback_min_retrace_frac=0.10,
        drive_pullback_max_retrace_frac=0.45,
        drive_touch_ma_buffer_pct=0.0015,
        drive_reclaim_close_location_min=0.55,
        drive_reclaim_min_volume_multiple=0.90,
        drive_pullback_require_hold_drive_open=True,
        drive_max_pullback_bars=5,
        drive_stop_buffer_range_frac=0.05,
    )


def c10_relative_strength_quality_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c10_relative_strength_balance_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c10_relative_strength_quality_v1",
        description=(
            "Higher-conviction relative-strength continuation: require stronger proxy outperformance, "
            "tighter pullback geometry, and cleaner reclaim candles."
        ),
        relative_volume_min=1.0,
        take_profit_rr=1.45,
        max_hold_minutes=45,
        dispersion_min_correlation=0.15,
        dispersion_rel_strength_entry_pct=0.0050,
        dispersion_rel_strength_exit_pct=0.0015,
        dispersion_rel_strength_stop_pct=0.0045,
        dispersion_primary_min_abs_move_pct=0.0045,
        dispersion_proxy_max_abs_move_pct=0.0100,
        dispersion_rel_strength_confirm_pct=0.0035,
        dispersion_beta_shock_max_pct=0.0065,
        dispersion_time_to_work_bars=2,
        dispersion_breakout_rel_strength_floor_frac=0.75,
        drive_min_abs_return_pct=0.0045,
        drive_pullback_min_retrace_frac=0.12,
        drive_pullback_max_retrace_frac=0.35,
        drive_touch_ma_buffer_pct=0.0010,
        drive_reclaim_close_location_min=0.65,
        drive_reclaim_min_volume_multiple=1.0,
        drive_max_pullback_bars=4,
        drive_stop_buffer_range_frac=0.04,
    )


def c10_relative_strength_regime_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c10_relative_strength_quality_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c10_relative_strength_regime_v1",
        description=(
            "Calmer-day relative-strength continuation: keep only sessions where broader volatility and "
            "prior-day expansion are still in a tradeable range."
        ),
        require_vol_regime_filter=True,
        vol_regime_min=10.0,
        vol_regime_max=34.0,
        require_prior_day_range_filter=True,
        prior_day_range_max_pct=0.025,
    )


def c10_relative_strength_loose_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c10_relative_strength_balance_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c10_relative_strength_loose_v1",
        description=(
            "Looser relative-strength continuation tuned to lift frequency while keeping the same cross-asset thesis."
        ),
        relative_volume_min=0.80,
        take_profit_rr=1.20,
        break_even_trigger_rr=0.40,
        early_fail_minutes=12,
        early_fail_min_rr=0.04,
        max_hold_minutes=40,
        dispersion_rel_strength_entry_pct=0.0025,
        dispersion_rel_strength_exit_pct=0.0010,
        dispersion_rel_strength_stop_pct=0.0055,
        dispersion_primary_min_abs_move_pct=0.0028,
        dispersion_proxy_max_abs_move_pct=0.0140,
        dispersion_rel_strength_confirm_pct=0.0015,
        dispersion_beta_shock_max_pct=0.0090,
        drive_min_abs_return_pct=0.0028,
        drive_pullback_min_retrace_frac=0.08,
        drive_pullback_max_retrace_frac=0.55,
        drive_reclaim_close_location_min=0.50,
        drive_reclaim_min_volume_multiple=0.80,
        drive_max_pullback_bars=6,
    )


def c10_relative_strength_fast_v2(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c10_relative_strength_loose_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c10_relative_strength_fast_v2",
        description=(
            "Faster relative-strength continuation: monetize the edge sooner and cut laggards earlier."
        ),
        take_profit_rr=1.05,
        break_even_trigger_rr=0.35,
        early_fail_minutes=10,
        early_fail_min_rr=0.03,
        max_hold_minutes=30,
        dispersion_time_to_work_bars=2,
        dispersion_breakout_rel_strength_floor_frac=0.55,
    )


def c10_relative_strength_candidates(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> List[OrbProfile]:
    return [
        c10_relative_strength_balance_v1(or_width_min=or_width_min),
        c10_relative_strength_quality_v1(or_width_min=or_width_min),
        c10_relative_strength_regime_v1(or_width_min=or_width_min),
        c10_relative_strength_loose_v1(or_width_min=or_width_min),
        c10_relative_strength_fast_v2(or_width_min=or_width_min),
    ]


def c11_proxy_vwap_reclaim_balance_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    return OrbProfile(
        name="c11_proxy_vwap_reclaim_balance_v1",
        description=(
            "Proxy-confirmed VWAP reclaim: buy a lagging symbol only after its benchmark is already trending "
            "and the symbol reclaims VWAP while closing the relative-strength gap."
        ),
        strategy_variant="proxy_vwap_reclaim_v1",
        opening_range_minutes=5,
        entry_start_time="09:40",
        entry_cutoff_time="11:50",
        exit_time="15:55",
        allow_long=True,
        allow_short=False,
        stop_mode="range",
        take_profit_rr=1.25,
        break_even_trigger_rr=0.45,
        early_fail_minutes=12,
        early_fail_min_rr=0.05,
        max_hold_minutes=45,
        require_relative_volume=True,
        relative_volume_min=0.85,
        trend_ema_fast=8,
        trend_ema_slow=21,
        dispersion_proxy_ticker="AUTO",
        dispersion_beta_lookback=18,
        dispersion_min_correlation=0.10,
        dispersion_rel_strength_entry_pct=0.0030,
        dispersion_rel_strength_confirm_pct=0.0015,
        dispersion_primary_min_abs_move_pct=0.0035,
        dispersion_proxy_max_abs_move_pct=0.0040,
        dispersion_beta_shock_max_pct=0.0100,
        dispersion_time_to_work_bars=3,
        dispersion_time_to_work_improvement_min=0.0015,
        dispersion_breakout_rel_strength_floor_frac=0.35,
        drive_pullback_min_retrace_frac=0.05,
        drive_pullback_max_retrace_frac=0.45,
        drive_touch_ma_buffer_pct=0.0015,
        drive_reclaim_close_location_min=0.55,
        drive_reclaim_min_volume_multiple=0.90,
        drive_pullback_require_hold_drive_open=True,
        drive_reclaim_requires_prev_extreme_break=True,
        drive_max_pullback_bars=6,
        drive_stop_buffer_range_frac=0.05,
    )


def c11_proxy_vwap_reclaim_quality_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c11_proxy_vwap_reclaim_balance_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c11_proxy_vwap_reclaim_quality_v1",
        description=(
            "Higher-conviction proxy VWAP reclaim: stronger proxy trend, cleaner reclaim, and tighter lag-catchup geometry."
        ),
        relative_volume_min=0.95,
        take_profit_rr=1.35,
        max_hold_minutes=40,
        dispersion_min_correlation=0.15,
        dispersion_rel_strength_entry_pct=0.0040,
        dispersion_rel_strength_confirm_pct=0.0020,
        dispersion_primary_min_abs_move_pct=0.0045,
        dispersion_proxy_max_abs_move_pct=0.0030,
        dispersion_beta_shock_max_pct=0.0080,
        dispersion_time_to_work_bars=2,
        dispersion_time_to_work_improvement_min=0.0020,
        dispersion_breakout_rel_strength_floor_frac=0.45,
        drive_pullback_min_retrace_frac=0.08,
        drive_pullback_max_retrace_frac=0.35,
        drive_touch_ma_buffer_pct=0.0010,
        drive_reclaim_close_location_min=0.62,
        drive_reclaim_min_volume_multiple=1.0,
        drive_max_pullback_bars=5,
        drive_stop_buffer_range_frac=0.04,
    )


def c11_proxy_vwap_reclaim_regime_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c11_proxy_vwap_reclaim_quality_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c11_proxy_vwap_reclaim_regime_v1",
        description=(
            "Calmer-day proxy VWAP reclaim: keep only sessions where broader volatility and prior-day expansion remain contained."
        ),
        require_vol_regime_filter=True,
        vol_regime_min=10.0,
        vol_regime_max=32.0,
        require_prior_day_range_filter=True,
        prior_day_range_max_pct=0.025,
    )


def c11_proxy_vwap_reclaim_loose_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c11_proxy_vwap_reclaim_balance_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c11_proxy_vwap_reclaim_loose_v1",
        description=(
            "Looser proxy VWAP reclaim tuned to lift trade count while keeping the proxy-confirmation structure."
        ),
        relative_volume_min=0.75,
        take_profit_rr=1.10,
        break_even_trigger_rr=0.35,
        early_fail_minutes=10,
        early_fail_min_rr=0.04,
        max_hold_minutes=35,
        dispersion_rel_strength_entry_pct=0.0020,
        dispersion_rel_strength_confirm_pct=0.0010,
        dispersion_primary_min_abs_move_pct=0.0025,
        dispersion_proxy_max_abs_move_pct=0.0055,
        dispersion_beta_shock_max_pct=0.0120,
        dispersion_time_to_work_bars=2,
        dispersion_time_to_work_improvement_min=0.0010,
        dispersion_breakout_rel_strength_floor_frac=0.25,
        drive_pullback_min_retrace_frac=0.03,
        drive_pullback_max_retrace_frac=0.55,
        drive_reclaim_close_location_min=0.50,
        drive_reclaim_min_volume_multiple=0.80,
        drive_reclaim_requires_prev_extreme_break=False,
        drive_max_pullback_bars=7,
    )


def c11_proxy_vwap_reclaim_fast_v2(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c11_proxy_vwap_reclaim_loose_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c11_proxy_vwap_reclaim_fast_v2",
        description="Faster proxy VWAP reclaim: monetize catch-up moves earlier and cut stalls sooner.",
        take_profit_rr=1.0,
        break_even_trigger_rr=0.30,
        early_fail_minutes=8,
        early_fail_min_rr=0.03,
        max_hold_minutes=28,
        dispersion_time_to_work_bars=2,
        dispersion_time_to_work_improvement_min=0.0012,
    )


def c11_proxy_vwap_reclaim_opportunity_v3(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c11_proxy_vwap_reclaim_loose_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c11_proxy_vwap_reclaim_opportunity_v3",
        description="Higher-frequency proxy VWAP reclaim tuned to increase catch-up opportunities.",
        entry_start_time="09:35",
        entry_cutoff_time="12:10",
        relative_volume_min=0.70,
        take_profit_rr=1.05,
        break_even_trigger_rr=0.25,
        early_fail_minutes=8,
        early_fail_min_rr=0.03,
        max_hold_minutes=35,
        dispersion_rel_strength_entry_pct=0.0012,
        dispersion_rel_strength_confirm_pct=0.0005,
        dispersion_primary_min_abs_move_pct=0.0018,
        dispersion_proxy_max_abs_move_pct=0.0070,
        dispersion_beta_shock_max_pct=0.0140,
        dispersion_time_to_work_bars=2,
        dispersion_time_to_work_improvement_min=0.0008,
        dispersion_breakout_rel_strength_floor_frac=0.15,
        drive_pullback_min_retrace_frac=0.02,
        drive_pullback_max_retrace_frac=0.65,
        drive_reclaim_close_location_min=0.45,
        drive_reclaim_min_volume_multiple=0.70,
        drive_pullback_require_hold_drive_open=False,
        drive_reclaim_requires_prev_extreme_break=False,
        drive_max_pullback_bars=8,
        drive_stop_buffer_range_frac=0.03,
    )


def c11_proxy_vwap_reclaim_opportunity_regime_v3(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c11_proxy_vwap_reclaim_opportunity_v3(or_width_min=or_width_min)
    return replace(
        base,
        name="c11_proxy_vwap_reclaim_opportunity_regime_v3",
        description="Higher-frequency proxy VWAP reclaim with calm-day regime guard.",
        require_vol_regime_filter=True,
        vol_regime_min=10.0,
        vol_regime_max=35.0,
        require_prior_day_range_filter=True,
        prior_day_range_max_pct=0.03,
    )


def c56_proxy_vwap_reclaim_opportunity_guard_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c11_proxy_vwap_reclaim_opportunity_v3(or_width_min=or_width_min)
    return replace(
        base,
        name="c56_proxy_vwap_reclaim_opportunity_guard_v1",
        description=(
            "Guarded proxy VWAP reclaim that keeps the higher-frequency c11 opportunity shape but trims late, noisy "
            "setups and requires cleaner catch-up geometry."
        ),
        entry_cutoff_time="11:30",
        relative_volume_min=0.80,
        take_profit_rr=1.10,
        break_even_trigger_rr=0.30,
        early_fail_minutes=8,
        early_fail_min_rr=0.04,
        max_hold_minutes=30,
        dispersion_rel_strength_entry_pct=0.0018,
        dispersion_rel_strength_confirm_pct=0.0008,
        dispersion_primary_min_abs_move_pct=0.0022,
        dispersion_proxy_max_abs_move_pct=0.0055,
        dispersion_beta_shock_max_pct=0.0120,
        dispersion_time_to_work_bars=2,
        dispersion_time_to_work_improvement_min=0.0010,
        dispersion_breakout_rel_strength_floor_frac=0.25,
        drive_pullback_min_retrace_frac=0.03,
        drive_pullback_max_retrace_frac=0.50,
        drive_reclaim_close_location_min=0.52,
        drive_reclaim_min_volume_multiple=0.85,
        drive_pullback_require_hold_drive_open=True,
        drive_reclaim_requires_prev_extreme_break=False,
        drive_max_pullback_bars=6,
        drive_stop_buffer_range_frac=0.04,
    )


def c56_proxy_vwap_reclaim_opportunity_guard_regime_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> OrbProfile:
    base = c56_proxy_vwap_reclaim_opportunity_guard_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c56_proxy_vwap_reclaim_opportunity_guard_regime_v1",
        description="Guarded proxy VWAP reclaim with calm-day regime filters.",
        require_vol_regime_filter=True,
        vol_regime_min=10.0,
        vol_regime_max=32.0,
        require_prior_day_range_filter=True,
        prior_day_range_max_pct=0.025,
    )


def c11_proxy_vwap_reclaim_candidates(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> List[OrbProfile]:
    return [
        c11_proxy_vwap_reclaim_balance_v1(or_width_min=or_width_min),
        c11_proxy_vwap_reclaim_quality_v1(or_width_min=or_width_min),
        c11_proxy_vwap_reclaim_regime_v1(or_width_min=or_width_min),
        c11_proxy_vwap_reclaim_loose_v1(or_width_min=or_width_min),
        c11_proxy_vwap_reclaim_fast_v2(or_width_min=or_width_min),
        c11_proxy_vwap_reclaim_opportunity_v3(or_width_min=or_width_min),
        c11_proxy_vwap_reclaim_opportunity_regime_v3(or_width_min=or_width_min),
    ]


def c56_proxy_vwap_reclaim_followup_candidates_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> List[OrbProfile]:
    return [
        c11_proxy_vwap_reclaim_quality_v1(or_width_min=or_width_min),
        c11_proxy_vwap_reclaim_regime_v1(or_width_min=or_width_min),
        c11_proxy_vwap_reclaim_fast_v2(or_width_min=or_width_min),
        c11_proxy_vwap_reclaim_opportunity_v3(or_width_min=or_width_min),
        c11_proxy_vwap_reclaim_opportunity_regime_v3(or_width_min=or_width_min),
        c56_proxy_vwap_reclaim_opportunity_guard_v1(or_width_min=or_width_min),
        c56_proxy_vwap_reclaim_opportunity_guard_regime_v1(or_width_min=or_width_min),
    ]


def c12_relative_strength_opportunity_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    return OrbProfile(
        name="c12_relative_strength_opportunity_v1",
        description=(
            "Higher-frequency relative-strength continuation: buy only when the symbol is outperforming its proxy, "
            "pulls back into value, and reclaims trend support with enough room left to continue."
        ),
        strategy_variant="relative_strength_continuation_v1",
        opening_range_minutes=5,
        entry_start_time="09:35",
        entry_cutoff_time="12:10",
        exit_time="15:55",
        allow_long=True,
        allow_short=False,
        stop_mode="range",
        take_profit_rr=1.15,
        break_even_trigger_rr=0.40,
        early_fail_minutes=10,
        early_fail_min_rr=0.04,
        max_hold_minutes=45,
        require_relative_volume=True,
        relative_volume_min=0.80,
        trend_ema_fast=8,
        trend_ema_slow=21,
        dispersion_proxy_ticker="AUTO",
        dispersion_beta_lookback=16,
        dispersion_min_correlation=0.08,
        dispersion_rel_strength_entry_pct=0.0018,
        dispersion_rel_strength_exit_pct=0.0008,
        dispersion_rel_strength_stop_pct=0.0048,
        dispersion_primary_min_abs_move_pct=0.0022,
        dispersion_proxy_max_abs_move_pct=0.0180,
        dispersion_rel_strength_confirm_pct=0.0008,
        dispersion_beta_shock_max_pct=0.0120,
        dispersion_time_to_work_bars=2,
        dispersion_breakout_rel_strength_floor_frac=0.45,
        drive_min_abs_return_pct=0.0022,
        drive_pullback_min_retrace_frac=0.05,
        drive_pullback_max_retrace_frac=0.55,
        drive_touch_ma_buffer_pct=0.0015,
        drive_reclaim_close_location_min=0.45,
        drive_reclaim_min_volume_multiple=0.75,
        drive_pullback_require_hold_drive_open=False,
        drive_reclaim_requires_prev_extreme_break=False,
        drive_max_pullback_bars=7,
        drive_stop_buffer_range_frac=0.04,
    )


def c12_relative_strength_balance_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c12_relative_strength_opportunity_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c12_relative_strength_balance_v1",
        description="Balanced relative-strength continuation with tighter confirmation and slightly cleaner pullback geometry.",
        relative_volume_min=0.85,
        take_profit_rr=1.20,
        break_even_trigger_rr=0.45,
        early_fail_minutes=12,
        max_hold_minutes=45,
        dispersion_min_correlation=0.10,
        dispersion_rel_strength_entry_pct=0.0022,
        dispersion_rel_strength_exit_pct=0.0010,
        dispersion_rel_strength_stop_pct=0.0045,
        dispersion_primary_min_abs_move_pct=0.0028,
        dispersion_proxy_max_abs_move_pct=0.0150,
        dispersion_rel_strength_confirm_pct=0.0012,
        dispersion_beta_shock_max_pct=0.0100,
        dispersion_breakout_rel_strength_floor_frac=0.55,
        drive_min_abs_return_pct=0.0028,
        drive_pullback_min_retrace_frac=0.08,
        drive_pullback_max_retrace_frac=0.48,
        drive_reclaim_close_location_min=0.50,
        drive_reclaim_min_volume_multiple=0.85,
        drive_max_pullback_bars=6,
    )


def c12_relative_strength_opportunity_plus_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c12_relative_strength_opportunity_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c12_relative_strength_opportunity_plus_v1",
        description="Opportunity-biased relative-strength continuation with slightly tighter confirmation and cleaner reclaim structure.",
        relative_volume_min=0.85,
        take_profit_rr=1.20,
        break_even_trigger_rr=0.45,
        early_fail_minutes=10,
        early_fail_min_rr=0.04,
        max_hold_minutes=40,
        dispersion_rel_strength_entry_pct=0.0022,
        dispersion_rel_strength_exit_pct=0.0010,
        dispersion_rel_strength_stop_pct=0.0045,
        dispersion_primary_min_abs_move_pct=0.0026,
        dispersion_proxy_max_abs_move_pct=0.0160,
        dispersion_rel_strength_confirm_pct=0.0011,
        dispersion_beta_shock_max_pct=0.0105,
        dispersion_breakout_rel_strength_floor_frac=0.50,
        drive_min_abs_return_pct=0.0026,
        drive_pullback_min_retrace_frac=0.06,
        drive_pullback_max_retrace_frac=0.50,
        drive_reclaim_close_location_min=0.48,
        drive_reclaim_min_volume_multiple=0.80,
        drive_max_pullback_bars=6,
    )


def c12_relative_strength_quality_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c12_relative_strength_balance_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c12_relative_strength_quality_v1",
        description="Higher-conviction relative-strength continuation with stronger edge, cleaner pullback, and tighter proxy drift.",
        relative_volume_min=0.95,
        take_profit_rr=1.30,
        break_even_trigger_rr=0.50,
        early_fail_minutes=12,
        early_fail_min_rr=0.05,
        max_hold_minutes=40,
        dispersion_min_correlation=0.12,
        dispersion_rel_strength_entry_pct=0.0030,
        dispersion_rel_strength_exit_pct=0.0012,
        dispersion_rel_strength_stop_pct=0.0040,
        dispersion_primary_min_abs_move_pct=0.0035,
        dispersion_proxy_max_abs_move_pct=0.0120,
        dispersion_rel_strength_confirm_pct=0.0018,
        dispersion_beta_shock_max_pct=0.0080,
        dispersion_breakout_rel_strength_floor_frac=0.65,
        drive_min_abs_return_pct=0.0035,
        drive_pullback_min_retrace_frac=0.10,
        drive_pullback_max_retrace_frac=0.40,
        drive_reclaim_close_location_min=0.58,
        drive_reclaim_min_volume_multiple=0.95,
        drive_pullback_require_hold_drive_open=True,
        drive_max_pullback_bars=5,
    )


def c12_relative_strength_opportunity_regime_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c12_relative_strength_opportunity_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c12_relative_strength_opportunity_regime_v1",
        description="Opportunity-biased relative-strength continuation with calm-day volatility and prior-range guardrails.",
        require_vol_regime_filter=True,
        vol_regime_min=10.0,
        vol_regime_max=35.0,
        require_prior_day_range_filter=True,
        prior_day_range_max_pct=0.03,
    )


def c12_relative_strength_regime_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c12_relative_strength_quality_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c12_relative_strength_regime_v1",
        description="Calmer-day relative-strength continuation with volatility and prior-range guardrails.",
        require_vol_regime_filter=True,
        vol_regime_min=10.0,
        vol_regime_max=35.0,
        require_prior_day_range_filter=True,
        prior_day_range_max_pct=0.03,
    )


def c12_relative_strength_fast_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c12_relative_strength_opportunity_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c12_relative_strength_fast_v1",
        description="Faster relative-strength continuation that monetizes the first extension and cuts stalls quickly.",
        take_profit_rr=1.00,
        break_even_trigger_rr=0.30,
        early_fail_minutes=8,
        early_fail_min_rr=0.03,
        max_hold_minutes=30,
        dispersion_time_to_work_bars=2,
        dispersion_breakout_rel_strength_floor_frac=0.40,
        drive_max_pullback_bars=5,
    )


def c12_relative_strength_quote_tight_v2(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c12_relative_strength_opportunity_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c12_relative_strength_quote_tight_v2",
        description=(
            "Quote-aware relative-strength continuation tuned to monetize the first clean continuation leg "
            "with earlier protection, shorter hold, and stricter reclaim quality."
        ),
        relative_volume_min=0.90,
        take_profit_rr=1.00,
        break_even_trigger_rr=0.22,
        early_fail_minutes=6,
        early_fail_min_rr=0.02,
        max_hold_minutes=28,
        dispersion_rel_strength_entry_pct=0.0022,
        dispersion_rel_strength_exit_pct=0.0010,
        dispersion_rel_strength_stop_pct=0.0042,
        dispersion_primary_min_abs_move_pct=0.0028,
        dispersion_proxy_max_abs_move_pct=0.0140,
        dispersion_rel_strength_confirm_pct=0.0012,
        dispersion_beta_shock_max_pct=0.0090,
        dispersion_breakout_rel_strength_floor_frac=0.55,
        drive_min_abs_return_pct=0.0028,
        drive_pullback_min_retrace_frac=0.08,
        drive_pullback_max_retrace_frac=0.40,
        drive_reclaim_close_location_min=0.56,
        drive_reclaim_min_volume_multiple=0.95,
        drive_pullback_require_hold_drive_open=True,
        drive_max_pullback_bars=5,
        dispersion_time_to_work_bars=2,
    )


def c12_relative_strength_quote_opportunity_v2(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c12_relative_strength_opportunity_plus_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c12_relative_strength_quote_opportunity_v2",
        description=(
            "Opportunity-biased quote-aware relative-strength continuation with earlier monetization "
            "and tighter continuation structure than the original opportunity branch."
        ),
        relative_volume_min=0.90,
        take_profit_rr=1.05,
        break_even_trigger_rr=0.25,
        early_fail_minutes=7,
        early_fail_min_rr=0.025,
        max_hold_minutes=30,
        dispersion_rel_strength_entry_pct=0.0022,
        dispersion_rel_strength_exit_pct=0.0010,
        dispersion_rel_strength_stop_pct=0.0042,
        dispersion_primary_min_abs_move_pct=0.0028,
        dispersion_proxy_max_abs_move_pct=0.0145,
        dispersion_rel_strength_confirm_pct=0.0012,
        dispersion_beta_shock_max_pct=0.0095,
        dispersion_breakout_rel_strength_floor_frac=0.55,
        drive_min_abs_return_pct=0.0028,
        drive_pullback_min_retrace_frac=0.08,
        drive_pullback_max_retrace_frac=0.42,
        drive_reclaim_close_location_min=0.54,
        drive_reclaim_min_volume_multiple=0.90,
        drive_pullback_require_hold_drive_open=True,
        drive_max_pullback_bars=5,
        dispersion_time_to_work_bars=2,
    )


def c12_relative_strength_quote_regime_v2(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c12_relative_strength_quote_tight_v2(or_width_min=or_width_min)
    return replace(
        base,
        name="c12_relative_strength_quote_regime_v2",
        description=(
            "Quote-aware relative-strength continuation with calm-day regime guards and faster stall control "
            "for the proven d23 / er_side_loose pocket."
        ),
        require_vol_regime_filter=True,
        vol_regime_min=12.0,
        vol_regime_max=32.0,
        require_prior_day_range_filter=True,
        prior_day_range_max_pct=0.025,
        relative_volume_min=0.95,
        take_profit_rr=1.00,
        break_even_trigger_rr=0.20,
        early_fail_minutes=6,
        early_fail_min_rr=0.025,
        max_hold_minutes=26,
        dispersion_rel_strength_entry_pct=0.0024,
        dispersion_rel_strength_exit_pct=0.0010,
        dispersion_rel_strength_stop_pct=0.0040,
        dispersion_primary_min_abs_move_pct=0.0030,
        dispersion_proxy_max_abs_move_pct=0.0130,
        dispersion_rel_strength_confirm_pct=0.0014,
        dispersion_beta_shock_max_pct=0.0085,
        dispersion_breakout_rel_strength_floor_frac=0.60,
        drive_min_abs_return_pct=0.0030,
        drive_pullback_min_retrace_frac=0.10,
        drive_pullback_max_retrace_frac=0.38,
        drive_reclaim_close_location_min=0.60,
        drive_reclaim_min_volume_multiple=1.00,
        drive_pullback_require_hold_drive_open=True,
        drive_max_pullback_bars=4,
        dispersion_time_to_work_bars=2,
    )


def c12_relative_strength_candidates(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> List[OrbProfile]:
    return [
        c12_relative_strength_opportunity_v1(or_width_min=or_width_min),
        c12_relative_strength_opportunity_plus_v1(or_width_min=or_width_min),
        c12_relative_strength_opportunity_regime_v1(or_width_min=or_width_min),
        c12_relative_strength_balance_v1(or_width_min=or_width_min),
        c12_relative_strength_quality_v1(or_width_min=or_width_min),
        c12_relative_strength_regime_v1(or_width_min=or_width_min),
        c12_relative_strength_fast_v1(or_width_min=or_width_min),
    ]


def c12_relative_strength_quote_candidates_v2(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> List[OrbProfile]:
    return [
        c12_relative_strength_quote_tight_v2(or_width_min=or_width_min),
        c12_relative_strength_quote_opportunity_v2(or_width_min=or_width_min),
        c12_relative_strength_quote_regime_v2(or_width_min=or_width_min),
        c12_relative_strength_opportunity_v1(or_width_min=or_width_min),
        c12_relative_strength_opportunity_plus_v1(or_width_min=or_width_min),
        c12_relative_strength_opportunity_regime_v1(or_width_min=or_width_min),
        c12_relative_strength_fast_v1(or_width_min=or_width_min),
        c12_relative_strength_regime_v1(or_width_min=or_width_min),
    ]


def c12_relative_strength_option_native_v3(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c12_relative_strength_opportunity_plus_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c12_relative_strength_option_native_v3",
        description=(
            "Options-native relative-strength continuation that prefers higher-intrinsic contracts and only takes "
            "setups whose planned move is large enough to outrun extrinsic and spread cost."
        ),
        take_profit_rr=1.55,
        break_even_trigger_rr=0.60,
        early_fail_minutes=8,
        early_fail_min_rr=0.03,
        max_hold_minutes=36,
        relative_volume_min=0.92,
        dispersion_rel_strength_entry_pct=0.0024,
        dispersion_rel_strength_exit_pct=0.0011,
        dispersion_rel_strength_stop_pct=0.0042,
        dispersion_primary_min_abs_move_pct=0.0030,
        dispersion_proxy_max_abs_move_pct=0.0135,
        dispersion_rel_strength_confirm_pct=0.0014,
        dispersion_beta_shock_max_pct=0.0090,
        dispersion_breakout_rel_strength_floor_frac=0.58,
        drive_min_abs_return_pct=0.0030,
        drive_pullback_min_retrace_frac=0.08,
        drive_pullback_max_retrace_frac=0.38,
        drive_reclaim_close_location_min=0.58,
        drive_reclaim_min_volume_multiple=0.95,
        drive_pullback_require_hold_drive_open=True,
        drive_reclaim_requires_prev_extreme_break=True,
        drive_max_pullback_bars=5,
        option_structure_filter_enabled=True,
        option_structure_min_open_interest=1400,
        option_structure_min_entry_volume=100,
        option_structure_max_entry_spread_pct=0.12,
        option_structure_max_entry_bar_range_pct=0.24,
        option_structure_min_entry_price=0.85,
        option_selection_intrinsic_weight=12.0,
        option_selection_min_intrinsic_share=0.18,
        option_min_expected_move_to_extrinsic_ratio=2.20,
        option_min_expected_move_to_spread_ratio=8.0,
    )


def c12_relative_strength_option_native_quality_v3(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c12_relative_strength_option_native_v3(or_width_min=or_width_min)
    return replace(
        base,
        name="c12_relative_strength_option_native_quality_v3",
        description="Higher-conviction options-native relative-strength continuation with larger gross target and stricter contract efficiency.",
        take_profit_rr=1.75,
        break_even_trigger_rr=0.70,
        early_fail_minutes=8,
        early_fail_min_rr=0.035,
        max_hold_minutes=34,
        relative_volume_min=0.98,
        dispersion_rel_strength_entry_pct=0.0028,
        dispersion_primary_min_abs_move_pct=0.0034,
        dispersion_proxy_max_abs_move_pct=0.0120,
        dispersion_rel_strength_confirm_pct=0.0018,
        dispersion_breakout_rel_strength_floor_frac=0.64,
        drive_pullback_min_retrace_frac=0.10,
        drive_pullback_max_retrace_frac=0.34,
        drive_reclaim_close_location_min=0.62,
        drive_reclaim_min_volume_multiple=1.05,
        option_structure_min_open_interest=1800,
        option_structure_min_entry_volume=140,
        option_structure_max_entry_spread_pct=0.10,
        option_structure_min_entry_price=1.05,
        option_selection_intrinsic_weight=16.0,
        option_selection_min_intrinsic_share=0.25,
        option_min_expected_move_to_extrinsic_ratio=2.75,
        option_min_expected_move_to_spread_ratio=10.0,
    )


def c12_relative_strength_option_native_regime_v3(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c12_relative_strength_option_native_quality_v3(or_width_min=or_width_min)
    return replace(
        base,
        name="c12_relative_strength_option_native_regime_v3",
        description="Calmer-day options-native relative-strength continuation for the proven d23 pocket with stronger move-to-cost requirements.",
        require_vol_regime_filter=True,
        vol_regime_min=12.0,
        vol_regime_max=30.0,
        require_prior_day_range_filter=True,
        prior_day_range_max_pct=0.024,
        take_profit_rr=1.65,
        break_even_trigger_rr=0.65,
        max_hold_minutes=34,
        option_selection_intrinsic_weight=18.0,
        option_selection_min_intrinsic_share=0.28,
        option_min_expected_move_to_extrinsic_ratio=2.90,
        option_min_expected_move_to_spread_ratio=10.5,
    )


def c12_relative_strength_option_native_candidates_v3(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> List[OrbProfile]:
    return [
        c12_relative_strength_option_native_v3(or_width_min=or_width_min),
        c12_relative_strength_option_native_quality_v3(or_width_min=or_width_min),
        c12_relative_strength_option_native_regime_v3(or_width_min=or_width_min),
        c12_relative_strength_opportunity_v1(or_width_min=or_width_min),
        c12_relative_strength_opportunity_plus_v1(or_width_min=or_width_min),
        c12_relative_strength_opportunity_regime_v1(or_width_min=or_width_min),
        c12_relative_strength_quote_regime_v2(or_width_min=or_width_min),
    ]


def c4_long_only_rr15_option_native_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_long_only_rr15_recovery_v2(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_long_only_rr15_option_native_v1",
        description=(
            "Option-native breakout redesign around the recovery control: favor higher-intrinsic contracts, "
            "tighten quote-quality ranking, and require larger gross winners so quote-aware fills still leave edge."
        ),
        take_profit_rr=1.70,
        break_even_trigger_rr=0.95,
        early_fail_minutes=20,
        early_fail_min_rr=0.06,
        max_hold_minutes=60,
        require_option_microstructure_filter=True,
        option_min_open_interest=1200,
        option_min_entry_volume=100,
        option_max_entry_bar_range_pct=0.22,
        option_min_entry_price=1.00,
        option_selection_spread_weight=10.0,
        option_selection_max_quote_spread_pct=0.25,
        option_selection_spread_to_ask_weight=14.0,
        option_selection_max_spread_to_ask_ratio=0.12,
        option_selection_intrinsic_weight=12.0,
        option_selection_min_intrinsic_share=0.20,
        option_min_expected_move_to_extrinsic_ratio=2.40,
        option_min_expected_move_to_spread_ratio=9.0,
    )


def c4_long_only_rr15_option_native_quality_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_long_only_rr15_option_native_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_long_only_rr15_option_native_quality_v1",
        description=(
            "Higher-conviction option-native breakout profile: tighten RVOL/OR-width and demand stricter quote "
            "quality plus higher intrinsic share."
        ),
        take_profit_rr=1.90,
        break_even_trigger_rr=1.05,
        early_fail_minutes=18,
        early_fail_min_rr=0.08,
        max_hold_minutes=55,
        relative_volume_min=1.00,
        opening_range_min_width_pct=max(or_width_min, 0.0020),
        option_min_open_interest=1800,
        option_min_entry_volume=140,
        option_max_entry_bar_range_pct=0.18,
        option_min_entry_price=1.15,
        option_selection_spread_weight=12.0,
        option_selection_max_quote_spread_pct=0.18,
        option_selection_spread_to_ask_weight=18.0,
        option_selection_max_spread_to_ask_ratio=0.08,
        option_selection_intrinsic_weight=16.0,
        option_selection_min_intrinsic_share=0.28,
        option_min_expected_move_to_extrinsic_ratio=2.80,
        option_min_expected_move_to_spread_ratio=10.5,
    )


def c4_long_only_rr15_openany_option_native_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_long_only_rr15_openany_tight_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_long_only_rr15_openany_option_native_v1",
        description=(
            "Open-any breakout option-native profile: preserve the validated looser entry gate, but monetize with "
            "higher-intrinsic contracts and tighter spread-to-ask controls."
        ),
        take_profit_rr=1.75,
        break_even_trigger_rr=0.90,
        early_fail_minutes=20,
        early_fail_min_rr=0.05,
        max_hold_minutes=60,
        require_option_microstructure_filter=True,
        option_min_open_interest=1000,
        option_min_entry_volume=90,
        option_max_entry_bar_range_pct=0.22,
        option_min_entry_price=0.95,
        option_selection_spread_weight=10.0,
        option_selection_max_quote_spread_pct=0.22,
        option_selection_spread_to_ask_weight=14.0,
        option_selection_max_spread_to_ask_ratio=0.12,
        option_selection_intrinsic_weight=10.0,
        option_selection_min_intrinsic_share=0.16,
        option_min_expected_move_to_extrinsic_ratio=2.10,
        option_min_expected_move_to_spread_ratio=8.0,
    )


def c4_long_only_rr15_option_native_candidates_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> List[OrbProfile]:
    return [
        c4_long_only_rr15_option_native_v1(or_width_min=or_width_min),
        c4_long_only_rr15_option_native_quality_v1(or_width_min=or_width_min),
        c4_long_only_rr15_openany_option_native_v1(or_width_min=or_width_min),
    ]


def c4_long_only_rr15_option_native_v2(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_long_only_rr15_recovery_v2(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_long_only_rr15_option_native_v2",
        description=(
            "Breakout monetization v2: keep the winning recovery signal, but bias contract selection toward "
            "deeper-ITM, higher-delta longs with enough quote efficiency to survive quote-aware costs."
        ),
        take_profit_rr=2.10,
        break_even_trigger_rr=1.20,
        early_fail_minutes=22,
        early_fail_min_rr=0.05,
        max_hold_minutes=75,
        require_option_microstructure_filter=True,
        option_min_open_interest=900,
        option_min_entry_volume=80,
        option_max_entry_bar_range_pct=0.25,
        option_min_entry_price=0.85,
        option_selection_spread_weight=8.0,
        option_selection_max_quote_spread_pct=0.28,
        option_selection_spread_to_ask_weight=10.0,
        option_selection_max_spread_to_ask_ratio=0.15,
        option_selection_intrinsic_weight=14.0,
        option_selection_min_intrinsic_share=0.22,
        option_selection_target_abs_delta=0.65,
        option_selection_delta_weight=10.0,
        option_selection_min_abs_delta=0.50,
        option_selection_max_abs_delta=0.85,
        option_min_expected_move_to_extrinsic_ratio=2.10,
        option_min_expected_move_to_spread_ratio=7.50,
    )


def c4_long_only_rr15_option_native_quality_v2(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_long_only_rr15_option_native_v2(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_long_only_rr15_option_native_quality_v2",
        description=(
            "Higher-conviction breakout monetization v2: larger winners, tighter RVOL/OR geometry, and a "
            "narrower higher-delta contract band."
        ),
        take_profit_rr=2.35,
        break_even_trigger_rr=1.35,
        early_fail_minutes=20,
        early_fail_min_rr=0.07,
        max_hold_minutes=70,
        relative_volume_min=1.00,
        opening_range_min_width_pct=max(or_width_min, 0.0020),
        option_min_open_interest=1400,
        option_min_entry_volume=120,
        option_max_entry_bar_range_pct=0.20,
        option_min_entry_price=1.10,
        option_selection_spread_weight=10.0,
        option_selection_max_quote_spread_pct=0.22,
        option_selection_spread_to_ask_weight=12.0,
        option_selection_max_spread_to_ask_ratio=0.10,
        option_selection_intrinsic_weight=18.0,
        option_selection_min_intrinsic_share=0.32,
        option_selection_target_abs_delta=0.72,
        option_selection_delta_weight=12.0,
        option_selection_min_abs_delta=0.60,
        option_selection_max_abs_delta=0.88,
        option_min_expected_move_to_extrinsic_ratio=2.40,
        option_min_expected_move_to_spread_ratio=8.50,
    )


def c4_long_only_rr15_openany_option_native_v2(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_long_only_rr15_openany_tight_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_long_only_rr15_openany_option_native_v2",
        description=(
            "Open-any breakout monetization v2: preserve the looser entry gate while forcing higher-delta, "
            "more intrinsic contracts with controlled spread drag."
        ),
        take_profit_rr=2.00,
        break_even_trigger_rr=1.10,
        early_fail_minutes=22,
        early_fail_min_rr=0.04,
        max_hold_minutes=75,
        require_option_microstructure_filter=True,
        option_min_open_interest=800,
        option_min_entry_volume=70,
        option_max_entry_bar_range_pct=0.25,
        option_min_entry_price=0.85,
        option_selection_spread_weight=8.0,
        option_selection_max_quote_spread_pct=0.26,
        option_selection_spread_to_ask_weight=10.0,
        option_selection_max_spread_to_ask_ratio=0.15,
        option_selection_intrinsic_weight=12.0,
        option_selection_min_intrinsic_share=0.20,
        option_selection_target_abs_delta=0.60,
        option_selection_delta_weight=9.0,
        option_selection_min_abs_delta=0.45,
        option_selection_max_abs_delta=0.82,
        option_min_expected_move_to_extrinsic_ratio=2.00,
        option_min_expected_move_to_spread_ratio=7.00,
    )


def c4_long_only_rr15_option_native_candidates_v2(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> List[OrbProfile]:
    return [
        c4_long_only_rr15_option_native_v2(or_width_min=or_width_min),
        c4_long_only_rr15_option_native_quality_v2(or_width_min=or_width_min),
        c4_long_only_rr15_openany_option_native_v2(or_width_min=or_width_min),
    ]


def c4_long_only_rr15_put_credit_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_long_only_rr15_recovery_v2(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_long_only_rr15_put_credit_v1",
        description=(
            "Breakout bull put credit spread: short premium outside the near-term noise band with a defined-risk "
            "hedge and premium-native exits."
        ),
        option_structure_mode="vertical_credit",
        max_hold_minutes=45,
        early_fail_minutes=15,
        early_fail_min_rr=0.02,
        require_option_microstructure_filter=True,
        option_min_open_interest=1200,
        option_min_entry_volume=100,
        option_max_entry_bar_range_pct=0.25,
        option_selection_spread_weight=12.0,
        option_selection_max_quote_spread_pct=0.20,
        option_selection_spread_to_ask_weight=12.0,
        option_selection_max_spread_to_ask_ratio=0.10,
        option_vertical_credit_long_leg_steps=1,
        option_vertical_credit_fallback_long_leg_steps=2,
        option_vertical_min_credit_to_width_ratio=0.18,
        option_vertical_max_credit_to_width_ratio=0.42,
        option_vertical_max_combined_spread_to_credit_ratio=0.30,
        option_credit_min_short_bid=0.25,
        option_credit_min_short_strike_buffer_pct=0.004,
        option_credit_min_expected_move_buffer_ratio=0.80,
        option_credit_min_entry_credit=0.25,
        option_credit_take_profit_capture_pct=0.55,
        option_credit_stop_loss_multiple=1.75,
        option_selection_target_abs_delta=0.28,
        option_selection_delta_weight=8.0,
        option_selection_min_abs_delta=0.18,
        option_selection_max_abs_delta=0.40,
    )


def c4_long_only_rr15_put_credit_quality_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_long_only_rr15_put_credit_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_long_only_rr15_put_credit_quality_v1",
        description=(
            "Higher-conviction bull put credit spread: larger strike buffer, tighter spread economics, and "
            "more conservative premium management."
        ),
        max_hold_minutes=40,
        early_fail_minutes=12,
        early_fail_min_rr=0.03,
        relative_volume_min=1.00,
        opening_range_min_width_pct=max(or_width_min, 0.0020),
        option_min_open_interest=1800,
        option_min_entry_volume=140,
        option_max_entry_bar_range_pct=0.20,
        option_vertical_min_credit_to_width_ratio=0.22,
        option_vertical_max_credit_to_width_ratio=0.38,
        option_vertical_max_combined_spread_to_credit_ratio=0.24,
        option_credit_min_short_strike_buffer_pct=0.006,
        option_credit_min_expected_move_buffer_ratio=1.00,
        option_credit_min_entry_credit=0.30,
        option_credit_take_profit_capture_pct=0.60,
        option_credit_stop_loss_multiple=1.60,
        option_selection_target_abs_delta=0.24,
        option_selection_delta_weight=10.0,
        option_selection_min_abs_delta=0.15,
        option_selection_max_abs_delta=0.32,
        option_selection_max_quote_spread_pct=0.16,
        option_selection_max_spread_to_ask_ratio=0.08,
    )


def c4_long_only_rr15_openany_put_credit_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_long_only_rr15_openany_tight_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_long_only_rr15_openany_put_credit_v1",
        description=(
            "Open-any bull put credit spread: looser entry gate with defined-risk short premium and moderate "
            "strike buffer requirements."
        ),
        option_structure_mode="vertical_credit",
        max_hold_minutes=45,
        early_fail_minutes=15,
        early_fail_min_rr=0.015,
        require_option_microstructure_filter=True,
        option_min_open_interest=1000,
        option_min_entry_volume=90,
        option_max_entry_bar_range_pct=0.25,
        option_vertical_min_credit_to_width_ratio=0.16,
        option_vertical_max_credit_to_width_ratio=0.40,
        option_vertical_max_combined_spread_to_credit_ratio=0.30,
        option_credit_min_short_bid=0.25,
        option_credit_min_short_strike_buffer_pct=0.0035,
        option_credit_min_expected_move_buffer_ratio=0.80,
        option_credit_min_entry_credit=0.20,
        option_credit_take_profit_capture_pct=0.50,
        option_credit_stop_loss_multiple=1.80,
        option_selection_target_abs_delta=0.30,
        option_selection_delta_weight=7.0,
        option_selection_min_abs_delta=0.20,
        option_selection_max_abs_delta=0.42,
        option_selection_max_quote_spread_pct=0.20,
        option_selection_max_spread_to_ask_ratio=0.10,
    )


def c4_long_only_rr15_put_credit_candidates_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> List[OrbProfile]:
    return [
        c4_long_only_rr15_put_credit_v1(or_width_min=or_width_min),
        c4_long_only_rr15_put_credit_quality_v1(or_width_min=or_width_min),
        c4_long_only_rr15_openany_put_credit_v1(or_width_min=or_width_min),
    ]


def c19_relative_strength_debit_spread_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c12_relative_strength_opportunity_regime_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c19_relative_strength_debit_spread_v1",
        description=(
            "Relative-strength continuation designed for quote-aware vertical debit spreads with moderate hold time "
            "and cleaner continuation follow-through."
        ),
        take_profit_rr=1.40,
        break_even_trigger_rr=0.55,
        max_hold_minutes=36,
        option_structure_mode="vertical_debit",
        option_vertical_short_leg_steps=1,
        option_vertical_fallback_short_leg_steps=2,
        option_vertical_max_debit_to_width_ratio=0.68,
        option_vertical_min_short_bid=0.10,
        option_vertical_max_combined_spread_to_debit_ratio=0.32,
    )


def c19_relative_strength_debit_spread_quality_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c19_relative_strength_debit_spread_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c19_relative_strength_debit_spread_quality_v1",
        description=(
            "Higher-conviction relative-strength vertical debit spread with tighter continuation quality and "
            "stricter structure filters."
        ),
        relative_volume_min=0.98,
        take_profit_rr=1.55,
        break_even_trigger_rr=0.65,
        dispersion_rel_strength_entry_pct=0.0028,
        dispersion_primary_min_abs_move_pct=0.0034,
        dispersion_proxy_max_abs_move_pct=0.0120,
        dispersion_rel_strength_confirm_pct=0.0018,
        dispersion_breakout_rel_strength_floor_frac=0.64,
        drive_pullback_min_retrace_frac=0.10,
        drive_pullback_max_retrace_frac=0.34,
        drive_reclaim_close_location_min=0.62,
        drive_reclaim_min_volume_multiple=1.05,
        option_structure_filter_enabled=True,
        option_structure_min_open_interest=1200,
        option_structure_min_entry_volume=80,
        option_structure_max_entry_spread_pct=0.16,
        option_structure_max_entry_bar_range_pct=0.24,
        option_structure_min_entry_price=0.85,
    )


def c19_relative_strength_debit_spread_regime_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c19_relative_strength_debit_spread_quality_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c19_relative_strength_debit_spread_regime_v1",
        description=(
            "Calmer-day relative-strength vertical debit spread that keeps the proven er_side_loose pocket but "
            "tightens continuation quality and prior-range drift."
        ),
        require_vol_regime_filter=True,
        vol_regime_min=10.0,
        vol_regime_max=32.0,
        require_prior_day_range_filter=True,
        prior_day_range_max_pct=0.025,
    )


def c19_relative_strength_debit_spread_candidates_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> List[OrbProfile]:
    return [
        c19_relative_strength_debit_spread_v1(or_width_min=or_width_min),
        c19_relative_strength_debit_spread_quality_v1(or_width_min=or_width_min),
        c19_relative_strength_debit_spread_regime_v1(or_width_min=or_width_min),
    ]


def c19_relative_strength_debit_spread_v2(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c19_relative_strength_debit_spread_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c19_relative_strength_debit_spread_v2",
        description=(
            "Relative-strength continuation debit spread with ranked short-leg selection and tighter debit economics."
        ),
        option_vertical_short_leg_steps=2,
        option_vertical_fallback_short_leg_steps=3,
        option_vertical_max_debit_to_width_ratio=0.55,
        option_vertical_max_combined_spread_to_debit_ratio=0.25,
        option_min_expected_move_to_debit_ratio=1.25,
        option_structure_filter_enabled=False,
    )


def c19_relative_strength_debit_spread_quality_v2(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c19_relative_strength_debit_spread_quality_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c19_relative_strength_debit_spread_quality_v2",
        description=(
            "Higher-conviction relative-strength debit spread with ranked short-leg selection and tighter debit economics."
        ),
        option_vertical_short_leg_steps=2,
        option_vertical_fallback_short_leg_steps=3,
        option_vertical_max_debit_to_width_ratio=0.55,
        option_vertical_max_combined_spread_to_debit_ratio=0.25,
        option_min_expected_move_to_debit_ratio=1.25,
        option_structure_filter_enabled=False,
        option_structure_min_open_interest=0,
        option_structure_min_entry_volume=0,
        option_structure_max_entry_spread_pct=1.0,
        option_structure_max_entry_bar_range_pct=1.0,
        option_structure_min_entry_price=0.0,
    )


def c19_relative_strength_debit_spread_regime_v2(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c19_relative_strength_debit_spread_regime_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c19_relative_strength_debit_spread_regime_v2",
        description=(
            "Calmer-day relative-strength debit spread with ranked short-leg selection and tighter debit economics."
        ),
        option_vertical_short_leg_steps=2,
        option_vertical_fallback_short_leg_steps=3,
        option_vertical_max_debit_to_width_ratio=0.55,
        option_vertical_max_combined_spread_to_debit_ratio=0.25,
        option_min_expected_move_to_debit_ratio=1.25,
        option_structure_filter_enabled=False,
        option_structure_min_open_interest=0,
        option_structure_min_entry_volume=0,
        option_structure_max_entry_spread_pct=1.0,
        option_structure_max_entry_bar_range_pct=1.0,
        option_structure_min_entry_price=0.0,
    )


def c19_relative_strength_debit_spread_candidates_v2(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> List[OrbProfile]:
    return [
        c19_relative_strength_debit_spread_v2(or_width_min=or_width_min),
        c19_relative_strength_debit_spread_quality_v2(or_width_min=or_width_min),
        c19_relative_strength_debit_spread_regime_v2(or_width_min=or_width_min),
    ]


def c4_breakout_debit_spread_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_long_only_rr15_openany_tight_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_breakout_debit_spread_v1",
        description="Breakout benchmark expressed as a quote-aware vertical debit spread with the same structure rules as c19.",
        option_structure_mode="vertical_debit",
        option_vertical_short_leg_steps=1,
        option_vertical_fallback_short_leg_steps=2,
        option_vertical_max_debit_to_width_ratio=0.68,
        option_vertical_min_short_bid=0.10,
        option_vertical_max_combined_spread_to_debit_ratio=0.32,
    )


def c4_breakout_debit_spread_quality_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c4_long_only_rr15_recovery_v2(or_width_min=or_width_min)
    return replace(
        base,
        name="c4_breakout_debit_spread_quality_v1",
        description="Higher-quality breakout benchmark expressed as a quote-aware vertical debit spread.",
        option_structure_mode="vertical_debit",
        option_vertical_short_leg_steps=1,
        option_vertical_fallback_short_leg_steps=2,
        option_vertical_max_debit_to_width_ratio=0.68,
        option_vertical_min_short_bid=0.10,
        option_vertical_max_combined_spread_to_debit_ratio=0.32,
    )


def c13_orb_fib_pullback_balance_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    return OrbProfile(
        name="c13_orb_fib_pullback_balance_v1",
        description="Long-only ORB fib pullback that buys the first controlled retrace into the breakout leg.",
        strategy_variant="orb_fib_pullback",
        allow_long=True,
        allow_short=False,
        require_breakout_open_inside_range=False,
        entry_trigger_mode="close_breakout",
        stop_mode="range",
        take_profit_rr=1.0,
        break_even_trigger_rr=0.30,
        exit_on_opposite_candle=True,
        opposite_candle_min_hold_minutes=10,
        early_fail_minutes=12,
        early_fail_min_rr=0.03,
        max_hold_minutes=55,
        require_relative_volume=True,
        relative_volume_min=0.90,
        require_trend_alignment=True,
        trend_ema_fast=8,
        trend_ema_slow=21,
        require_or_width_filter=True,
        opening_range_min_width_pct=max(float(or_width_min), 0.0018),
        opening_range_max_width_pct=0.018,
        fib_entry_level_low=0.382,
        fib_entry_level_high=0.618,
        fib_target_extension=1.272,
        fib_require_confirmation=True,
    )


def c13_orb_fib_pullback_quality_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c13_orb_fib_pullback_balance_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c13_orb_fib_pullback_quality_v1",
        description="Higher-quality long-only ORB fib pullback with tighter retrace band and stronger continuation confirmation.",
        relative_volume_min=1.00,
        break_even_trigger_rr=0.35,
        early_fail_minutes=10,
        early_fail_min_rr=0.04,
        max_hold_minutes=45,
        fib_entry_level_low=0.382,
        fib_entry_level_high=0.50,
        fib_target_extension=1.18,
        fib_require_confirmation=True,
    )


def c13_orb_fib_pullback_opportunity_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c13_orb_fib_pullback_balance_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c13_orb_fib_pullback_opportunity_v1",
        description="Opportunity-biased ORB fib pullback that allows a deeper retrace and earlier monetization.",
        relative_volume_min=0.85,
        break_even_trigger_rr=0.25,
        early_fail_minutes=10,
        early_fail_min_rr=0.02,
        max_hold_minutes=40,
        fib_entry_level_low=0.50,
        fib_entry_level_high=0.786,
        fib_target_extension=1.00,
        fib_require_confirmation=False,
    )


def c13_orb_fib_pullback_regime_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c13_orb_fib_pullback_quality_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c13_orb_fib_pullback_regime_v1",
        description="Calmer-day ORB fib pullback using volatility and prior-day range guardrails.",
        require_vol_regime_filter=True,
        vol_regime_min=10.0,
        vol_regime_max=32.0,
        require_prior_day_range_filter=True,
        prior_day_range_max_pct=0.028,
    )


def c13_orb_fib_pullback_fast_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c13_orb_fib_pullback_opportunity_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c13_orb_fib_pullback_fast_v1",
        description="Fast ORB fib pullback that targets the first extension and exits stalled continuations quickly.",
        break_even_trigger_rr=0.20,
        early_fail_minutes=8,
        early_fail_min_rr=0.02,
        max_hold_minutes=30,
        fib_target_extension=0.886,
    )


def c13_orb_fib_pullback_candidates(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> List[OrbProfile]:
    return [
        c13_orb_fib_pullback_balance_v1(or_width_min=or_width_min),
        c13_orb_fib_pullback_quality_v1(or_width_min=or_width_min),
        c13_orb_fib_pullback_opportunity_v1(or_width_min=or_width_min),
        c13_orb_fib_pullback_regime_v1(or_width_min=or_width_min),
        c13_orb_fib_pullback_fast_v1(or_width_min=or_width_min),
    ]


def c14_gap_rejection_balance_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c6_opening_exhaustion_reversal_balance_v2(or_width_min=or_width_min)
    return replace(
        base,
        name="c14_gap_rejection_balance_v1",
        description=(
            "Failed-gap reversal that requires a meaningful opening gap, a drive in the same direction as the gap, "
            "and then trades the first reclaim back through value."
        ),
        entry_start_time="09:36",
        entry_cutoff_time="10:45",
        stop_mode="range",
        take_profit_rr=1.10,
        break_even_trigger_rr=0.35,
        early_fail_minutes=15,
        early_fail_min_rr=0.04,
        max_hold_minutes=45,
        require_relative_volume=True,
        relative_volume_min=0.90,
        event_drive_min_gap_abs_return=0.0040,
        drive_min_abs_return_pct=0.0032,
        drive_close_location_min=0.60,
        drive_pullback_min_retrace_frac=0.22,
        drive_pullback_max_retrace_frac=0.92,
        drive_touch_ma_buffer_pct=0.0012,
        drive_reclaim_close_location_min=0.55,
        drive_stop_buffer_range_frac=0.04,
        drive_max_pullback_bars=7,
    )


def c14_gap_rejection_quality_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c14_gap_rejection_balance_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c14_gap_rejection_quality_v1",
        description=(
            "Higher-conviction failed-gap reversal with stronger gap/drive quality and a cleaner reclaim."
        ),
        relative_volume_min=1.00,
        take_profit_rr=1.20,
        break_even_trigger_rr=0.45,
        early_fail_minutes=12,
        early_fail_min_rr=0.05,
        max_hold_minutes=40,
        event_drive_min_gap_abs_return=0.0055,
        drive_min_abs_return_pct=0.0040,
        drive_close_location_min=0.68,
        drive_pullback_min_retrace_frac=0.28,
        drive_pullback_max_retrace_frac=0.85,
        drive_touch_ma_buffer_pct=0.0016,
        drive_reclaim_close_location_min=0.62,
        drive_stop_buffer_range_frac=0.03,
        drive_max_pullback_bars=6,
    )


def c14_gap_rejection_opportunity_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c14_gap_rejection_balance_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c14_gap_rejection_opportunity_v1",
        description=(
            "Opportunity-biased failed-gap reversal with a smaller minimum gap and faster monetization."
        ),
        relative_volume_min=0.85,
        take_profit_rr=1.00,
        break_even_trigger_rr=0.25,
        early_fail_minutes=10,
        early_fail_min_rr=0.03,
        max_hold_minutes=35,
        event_drive_min_gap_abs_return=0.0035,
        drive_min_abs_return_pct=0.0028,
        drive_pullback_min_retrace_frac=0.18,
        drive_pullback_max_retrace_frac=0.95,
        drive_reclaim_close_location_min=0.50,
        drive_max_pullback_bars=8,
    )


def c14_gap_rejection_regime_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c14_gap_rejection_quality_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c14_gap_rejection_regime_v1",
        description=(
            "Failed-gap reversal on calmer days only, filtering out the highest-volatility sessions where "
            "opening gaps tend to continue instead of mean-revert."
        ),
        require_vol_regime_filter=True,
        vol_regime_min=10.0,
        vol_regime_max=32.0,
        require_prior_day_range_filter=True,
        prior_day_range_max_pct=0.024,
    )


def c14_gap_rejection_long_only_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c14_gap_rejection_regime_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c14_gap_rejection_long_only_v1",
        description="Long-only failed-gap reversal for downside opening gaps that wash out and reclaim value.",
        allow_short=False,
    )




def c15_failure_fade_balance_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    return OrbProfile(
        name="c15_failure_fade_balance_v1",
        description=(
            "Bidirectional failed-breakout fade: wait for a real OR break, then fade the failure back into range "
            "on calmer intraday sessions with moderate opening width."
        ),
        strategy_variant="orb_failure_fade",
        require_or_width_filter=True,
        opening_range_min_width_pct=max(float(or_width_min), 0.0015),
        opening_range_max_width_pct=0.02,
        opening_range_minutes=5,
        entry_start_time="09:35",
        entry_cutoff_time="11:00",
        exit_time="15:55",
        allow_long=True,
        allow_short=True,
        require_breakout_open_inside_range=False,
        entry_trigger_mode="close_breakout",
        stop_mode="breakout_candle",
        take_profit_rr=1.00,
        exit_on_opposite_candle=True,
        opposite_candle_min_hold_minutes=4,
        early_fail_minutes=12,
        early_fail_min_rr=0.04,
        max_hold_minutes=35,
        require_relative_volume=True,
        relative_volume_min=0.85,
    )


def c15_failure_fade_quality_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c15_failure_fade_balance_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c15_failure_fade_quality_v1",
        description=(
            "Higher-conviction failed-breakout fade: require stronger opening participation and tighter OR width."
        ),
        opening_range_min_width_pct=max(float(or_width_min), 0.0020),
        opening_range_max_width_pct=0.015,
        take_profit_rr=1.10,
        opposite_candle_min_hold_minutes=5,
        early_fail_minutes=10,
        max_hold_minutes=30,
        relative_volume_min=1.00,
    )


def c15_failure_fade_regime_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c15_failure_fade_quality_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c15_failure_fade_regime_v1",
        description=(
            "Calmer-day failed-breakout fade with volatility and prior-range guardrails to avoid trend days."
        ),
        require_vol_regime_filter=True,
        vol_regime_min=10.0,
        vol_regime_max=30.0,
        require_prior_day_range_filter=True,
        prior_day_range_max_pct=0.025,
    )


def c15_failure_fade_fast_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c15_failure_fade_balance_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c15_failure_fade_fast_v1",
        description=(
            "Faster failed-breakout fade that monetizes the first move back into range and cuts laggards quickly."
        ),
        take_profit_rr=0.90,
        opposite_candle_min_hold_minutes=3,
        early_fail_minutes=8,
        early_fail_min_rr=0.03,
        max_hold_minutes=25,
        relative_volume_min=0.80,
    )


def c15_failure_fade_long_only_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c15_failure_fade_regime_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c15_failure_fade_long_only_v1",
        description=(
            "Long-only failed-breakout fade for bullish failed downside breaks in otherwise calmer sessions."
        ),
        allow_short=False,
    )


def c15_failure_fade_candidates(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> List[OrbProfile]:
    return [
        c15_failure_fade_balance_v1(or_width_min=or_width_min),
        c15_failure_fade_quality_v1(or_width_min=or_width_min),
        c15_failure_fade_regime_v1(or_width_min=or_width_min),
        c15_failure_fade_fast_v1(or_width_min=or_width_min),
        c15_failure_fade_long_only_v1(or_width_min=or_width_min),
    ]

def c14_gap_rejection_candidates(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> List[OrbProfile]:
    return [
        c14_gap_rejection_balance_v1(or_width_min=or_width_min),
        c14_gap_rejection_quality_v1(or_width_min=or_width_min),
        c14_gap_rejection_opportunity_v1(or_width_min=or_width_min),
        c14_gap_rejection_regime_v1(or_width_min=or_width_min),
        c14_gap_rejection_long_only_v1(or_width_min=or_width_min),
    ]


def c4_confluence_candidates(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> List[OrbProfile]:
    base = c4_long_only_rr15(or_width_min=or_width_min)
    return [
        base,
        replace(
            base,
            name="c4_vol_regime_12_35",
            description="C4 + volatility-regime guard (12-35).",
            require_vol_regime_filter=True,
            vol_regime_min=12.0,
            vol_regime_max=35.0,
        ),
        replace(
            base,
            name="c4_micro_oi500",
            description="C4 + option microstructure/oi guard.",
            option_min_open_interest=500,
            require_option_microstructure_filter=True,
            option_min_entry_volume=100,
            option_max_entry_bar_range_pct=0.35,
            option_min_entry_price=0.2,
        ),
        replace(
            base,
            name="c4_insidebar_comp",
            description="C4 + prior-day inside-bar compression filter.",
            require_prior_day_inside_bar=True,
            require_prior_day_range_filter=True,
            prior_day_range_max_pct=0.02,
            require_vol_regime_filter=True,
            vol_regime_min=12.0,
            vol_regime_max=35.0,
        ),
    ]


def c4_frequency_candidates() -> List[OrbProfile]:
    return [
        c4_freq_v1(),
        c4_freq_v1_f4(),
        c4_freq_ls_v1(),
        c4_freq_ls_trend_v1(),
        c4_orb_momentum_v1(),
        c4_momentum_accel_v1(),
        c4_momentum_accel_relaxed_v2(),
        c4_momentum_adx_confirm_v1(),
        c4_momentum_break_retest_v1(),
        c4_momentum_gap_go_v1(),
        c4_momentum_loose_no_spike_v1(),
        c4_momentum_loose_no_trend_v1(),
        c4_momentum_loose_relaxed_v3(),
        c4_momentum_loose_cost_guard_v1(),
        c4_momentum_quality_v2(),
        c4_momentum_loose(),
        c4_momentum_pullback_fast_v1(),
        c4_momentum_pullback_guard_v2(),
        c4_momentum_vwap_reclaim_v1(),
        c4_momentum_vwap_reclaim_recovery_v2(),
        c4_orb_momentum_short_hold(),
        c4_orb_trend_pullback_v1(),
        c4_trend_pullback_fast_v2(),
        c4_trend_pullback_tight(),
        c21_trend_pullback_balance_v1(),
        c21_trend_pullback_quality_v1(),
        c21_trend_pullback_regime_v1(),
        c21_trend_pullback_fast_v1(),
        c4_orb_event_drive_v1(),
        c4_orb_transition_compression_v1(),
        c4_dispersion_breakout_v1(),
        c4_dispersion_breakout_breadth_v2(),
        c4_dispersion_breakout_relative_v2(),
        c4_dispersion_relative_breakout_v3(),
        c4_dispersion_relative_breakout_guard_v3(),
        c4_dispersion_relative_breakout_decay_v4(),
        c4_dispersion_relative_breakout_guard_hold30_v1(),
        c4_dispersion_relative_breakout_guard_density_v1(),
        c4_dispersion_relative_breakout_guard_density_spy_dia_v1(),
        c4_dispersion_relative_breakout_guard_density_spy_dia_balance_v1(),
        c4_dispersion_relative_breakout_guard_density_spy_dia_offset_v1(),
        c4_dispersion_relative_breakout_recovery_v5(),
        c4_dispersion_revert_v1(),
        c4_dispersion_revert_rotation_v2(),
        c4_dispersion_revert_exhaustion_v2(),
        c4_dispersion_relative_revert_v3(),
        c4_dispersion_relative_revert_exhaustion_v3(),
        c4_dispersion_relative_revert_confirm_v4(),
        c4_dispersion_relative_revert_quality_v4(),
        c4_dispersion_relative_revert_decay_v5(),
        c4_dispersion_relative_revert_recovery_v6(),
        c4_pairs_spread_proxy_v1(),
        c4_pairs_spread_intraday_v1(),
        c4_pairs_spread_intraday_relaxed_v1(),
        c4_pairs_spread_intraday_quality_v2(),
        c4_pairs_spread_intraday_recovery_v3(),
        c4_pairs_overnight_proxy_v1(),
        c4_mr_vwap_zscore_v3_adaptive(),
        c4_mr_vwap_zscore_v3_adaptive_quality_v1(),
        c4_mr_vwap_exhaustion_v1(),
        c4_mr_vwap_exhaustion_quality_v1(),
        c4_mr_vwap_exhaustion_relaxed_v1(),
        c4_mr_vwap_exhaustion_guard_v2(),
        c4_mr_vwap_exhaustion_balance_v3(),
        c4_mr_rr_fast_guard_v3(),
        c4_mr_rr_fast_recovery_v4(),
        c4_orb_option_structure_v1(),
        c4_orb_trend_short_v1(),
        c4_trend_short_guard_v2(),
        c4_orb_failure_fade_v1(),
    ]


def c4_recovery_finalists() -> List[OrbProfile]:
    return [
        c4_long_only_rr15_recovery_v2(),
        c4_long_only_rr15_option_native_v1(),
        c4_long_only_rr15_option_native_quality_v1(),
        c4_long_only_rr15_openany_option_native_v1(),
        c4_momentum_vwap_reclaim_recovery_v2(),
        c4_pairs_spread_intraday_recovery_v3(),
        c4_dispersion_relative_revert_recovery_v6(),
        c4_dispersion_relative_breakout_recovery_v5(),
        c4_mr_rr_fast_recovery_v4(),
        c4_mr_vwap_exhaustion_balance_v3(),
    ]


def c4_breakout_phase89_finalists() -> List[OrbProfile]:
    return [
        c4_long_only_rr15(),
        c4_long_only_rr15_recovery_v2(),
        c4_long_only_rr15_openany_tight_v1(),
        c4_long_only_rr15_pocket_v1(),
        c4_long_only_rr15_pocket_v2(),
        c4_long_only_rr15_openany_pocket_v1(),
        c4_freq_v1(),
        c4_freq_v1_f4(),
        c4_freq_breakout_hybrid_v1(),
        c4_freq_breakout_hybrid_v2(),
    ]


def c4_lfcm_v1() -> OrbProfile:
    """Low-Float Catalyst Momentum (pessimistic spec, long-only, stock fills).

    Signal hypothesis: low-float stock (2M–10M shares) gaps ≥8% pre-market on
    a verifiable hard catalyst, with bar1 closing above the pre-market high at a
    high close-location and elevated volume.  Entry on bar2_open.

    All detection and exit logic is delegated to lfcm.py::find_lfcm_setup /
    resolve_lfcm_exit — the OrbProfile fields below are only used by the engine
    scaffolding (equity sizing, session bounds, etc.).
    """
    return OrbProfile(
        name="c4_lfcm_v1",
        description=(
            "Low-Float Catalyst Momentum v1: gap ≥8%, hard catalyst, bar1 confirms above "
            "pre-market high. Entry bar2_open; blended T1/T2 exit. Pessimistic defaults."
        ),
        strategy_variant="lfcm_v1",
        opening_range_minutes=1,
        entry_start_time="09:31",
        entry_cutoff_time="09:45",
        exit_time="10:14",
        allow_long=True,
        allow_short=False,
        require_breakout_open_inside_range=False,
        entry_trigger_mode="close_breakout",
        stop_mode="range",
        stop_loss_atr_distance=1.0,
        take_profit_rr=0.0,
        break_even_trigger_rr=0.0,
        exit_on_opposite_candle=False,
        max_hold_minutes=44,
        require_relative_volume=False,
        require_or_width_filter=False,
    )


def apply_options_discovery_wrapper_v1(
    profile: OrbProfile,
    *,
    quality: str,
    direction: str,
) -> OrbProfile:
    normalized_quality = str(quality or "").strip().lower()
    normalized_direction = str(direction or "").strip().lower()
    if normalized_quality not in {"balance", "quality", "regime"}:
        raise ValueError(f"Unsupported discovery wrapper quality: {quality}")
    if normalized_direction not in {"long", "short"}:
        raise ValueError(f"Unsupported discovery wrapper direction: {direction}")

    wrapped = replace(
        profile,
        allow_long=normalized_direction == "long",
        allow_short=normalized_direction == "short",
        option_structure_mode="single_leg",
        require_option_microstructure_filter=True,
        option_min_open_interest=100,
        option_min_entry_volume=50,
        option_max_entry_bar_range_pct=0.30,
        option_min_entry_price=0.70,
        option_selection_spread_weight=10.0,
        option_selection_max_quote_spread_pct=0.35,
        option_selection_spread_to_ask_weight=6.0,
        option_selection_max_spread_to_ask_ratio=0.18,
        option_selection_intrinsic_weight=8.0,
        option_selection_min_intrinsic_share=0.10,
        option_selection_target_abs_delta=0.50,
        option_selection_delta_weight=2.0,
        option_selection_min_abs_delta=0.0,
        option_selection_max_abs_delta=1.0,
        option_min_expected_move_to_extrinsic_ratio=1.60,
        option_min_expected_move_to_spread_ratio=5.00,
        take_profit_rr=1.40,
        break_even_trigger_rr=0.60,
        early_fail_minutes=18,
        early_fail_min_rr=0.03,
        max_hold_minutes=45,
    )
    if normalized_quality in {"quality", "regime"}:
        wrapped = replace(
            wrapped,
            option_min_open_interest=250,
            option_min_entry_volume=80,
            option_max_entry_bar_range_pct=0.24,
            option_min_entry_price=0.85,
            option_selection_max_quote_spread_pct=0.28,
            option_selection_max_spread_to_ask_ratio=0.14,
            option_selection_min_intrinsic_share=0.18,
            option_selection_target_abs_delta=0.55,
            option_selection_delta_weight=3.0,
            option_selection_min_abs_delta=0.0,
            option_selection_max_abs_delta=1.0,
            option_min_expected_move_to_extrinsic_ratio=1.90,
            option_min_expected_move_to_spread_ratio=6.00,
            take_profit_rr=1.55,
            break_even_trigger_rr=0.70,
            max_hold_minutes=42,
        )
    return wrapped


def _wave_long_profile(
    *,
    name: str,
    description: str,
    strategy_variant: str,
    entry_start_time: str,
    entry_cutoff_time: str,
    quality: str,
    or_width_min: float,
    **overrides: Any,
) -> OrbProfile:
    base = OrbProfile(
        name=name,
        description=description,
        strategy_variant=strategy_variant,
        entry_start_time=entry_start_time,
        entry_cutoff_time=entry_cutoff_time,
        require_breakout_open_inside_range=False,
        require_or_width_filter=True,
        opening_range_min_width_pct=max(float(or_width_min), 0.0015),
        opening_range_max_width_pct=0.035,
        require_relative_volume=False,
        stop_mode="breakout_candle",
    )
    wrapped = apply_options_discovery_wrapper_v1(base, quality=quality, direction="long")
    return replace(wrapped, **overrides)


def _wave_short_profile(
    *,
    name: str,
    description: str,
    strategy_variant: str,
    entry_start_time: str,
    entry_cutoff_time: str,
    quality: str,
    or_width_min: float,
    **overrides: Any,
) -> OrbProfile:
    base = OrbProfile(
        name=name,
        description=description,
        strategy_variant=strategy_variant,
        entry_start_time=entry_start_time,
        entry_cutoff_time=entry_cutoff_time,
        require_breakout_open_inside_range=False,
        require_or_width_filter=True,
        opening_range_min_width_pct=max(float(or_width_min), 0.0015),
        opening_range_max_width_pct=0.035,
        require_relative_volume=False,
        stop_mode="breakout_candle",
    )
    wrapped = apply_options_discovery_wrapper_v1(base, quality=quality, direction="short")
    return replace(wrapped, **overrides)


def c23_failed_break_reclaim_balance_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    return _wave_long_profile(
        name="c23_failed_break_reclaim_balance_v1",
        description="OR-low sweep fails and reclaims back above VWAP / OR midpoint; long on follow-through.",
        strategy_variant="failed_break_reclaim_v1",
        entry_start_time="09:40",
        entry_cutoff_time="11:00",
        quality="balance",
        or_width_min=or_width_min,
        trend_pullback_min_breakout_or_frac=0.10,
        trend_pullback_max_bars_after_breakout=30,
        drive_reclaim_close_location_min=0.55,
        require_trend_alignment=True,
        opposite_candle_min_hold_minutes=8,
    )


def c23_failed_break_reclaim_quality_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c23_failed_break_reclaim_balance_v1(or_width_min=or_width_min)
    return replace(
        apply_options_discovery_wrapper_v1(base, quality="quality", direction="long"),
        name="c23_failed_break_reclaim_quality_v1",
        description="Quality-biased failed-break reclaim with tighter RVOL and faster reclaim window.",
        require_relative_volume=True,
        relative_volume_min=1.0,
        entry_cutoff_time="10:30",
        trend_pullback_max_bars_after_breakout=20,
        drive_reclaim_close_location_min=0.60,
        option_max_entry_bar_range_pct=0.22,
    )


def c23_failed_break_reclaim_regime_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c23_failed_break_reclaim_quality_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c23_failed_break_reclaim_regime_v1",
        description="Quality failed-break reclaim plus calmer non-bearish volatility regime filter.",
        require_vol_regime_filter=True,
        vol_regime_min=10.0,
        vol_regime_max=35.0,
    )


def c23_failed_break_reclaim_candidates(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> List[OrbProfile]:
    return [
        c23_failed_break_reclaim_balance_v1(or_width_min=or_width_min),
        c23_failed_break_reclaim_quality_v1(or_width_min=or_width_min),
        c23_failed_break_reclaim_regime_v1(or_width_min=or_width_min),
    ]


def c24_pause_go_continuation_balance_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    return _wave_long_profile(
        name="c24_pause_go_continuation_balance_v1",
        description="Early breakout, pause above OR high, then continuation break of the pause high.",
        strategy_variant="pause_go_continuation_v1",
        entry_start_time="09:40",
        entry_cutoff_time="11:00",
        quality="balance",
        or_width_min=or_width_min,
        compression_lookback_bars=4,
        compression_max_range_pct=0.0030,
        compression_breakout_buffer_or_frac=0.02,
        compression_min_volume_multiple=1.0,
    )


def c24_pause_go_continuation_quality_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c24_pause_go_continuation_balance_v1(or_width_min=or_width_min)
    return replace(
        apply_options_discovery_wrapper_v1(base, quality="quality", direction="long"),
        name="c24_pause_go_continuation_quality_v1",
        description="Pause-go continuation with tighter compression and stronger RVOL floor.",
        require_relative_volume=True,
        relative_volume_min=1.0,
        compression_max_range_pct=0.0022,
        compression_min_volume_multiple=1.1,
    )


def c24_pause_go_continuation_regime_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c24_pause_go_continuation_quality_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c24_pause_go_continuation_regime_v1",
        description="Quality pause-go continuation gated to bullish / neutral-bull volatility regimes.",
        require_vol_regime_filter=True,
        vol_regime_min=10.0,
        vol_regime_max=32.0,
    )


def c24_pause_go_continuation_candidates(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> List[OrbProfile]:
    return [
        c24_pause_go_continuation_balance_v1(or_width_min=or_width_min),
        c24_pause_go_continuation_quality_v1(or_width_min=or_width_min),
        c24_pause_go_continuation_regime_v1(or_width_min=or_width_min),
    ]


def c25_vwap_support_continuation_balance_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    return _wave_long_profile(
        name="c25_vwap_support_continuation_balance_v1",
        description="Breakout, first pullback into VWAP / fast EMA, then long on reclaim.",
        strategy_variant="orb_trend_pullback_v1",
        entry_start_time="09:45",
        entry_cutoff_time="11:30",
        quality="balance",
        or_width_min=or_width_min,
        trend_pullback_max_bars_after_breakout=6,
        trend_pullback_ema_buffer_pct=0.0015,
        trend_pullback_require_orb_reclaim=True,
        trend_pullback_min_breakout_or_frac=0.04,
        trend_pullback_min_volume_multiple=1.0,
        require_trend_alignment=True,
    )


def c25_vwap_support_continuation_quality_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c25_vwap_support_continuation_balance_v1(or_width_min=or_width_min)
    return replace(
        apply_options_discovery_wrapper_v1(base, quality="quality", direction="long"),
        name="c25_vwap_support_continuation_quality_v1",
        description="VWAP-support continuation with shallower pullback and cleaner structure.",
        require_relative_volume=True,
        relative_volume_min=1.0,
        trend_pullback_max_bars_after_breakout=5,
        trend_pullback_ema_buffer_pct=0.0010,
        trend_pullback_min_breakout_or_frac=0.05,
        trend_pullback_min_volume_multiple=1.1,
        require_trend_alignment=True,
    )


def c25_vwap_support_continuation_regime_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c25_vwap_support_continuation_quality_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c25_vwap_support_continuation_regime_v1",
        description="Quality VWAP-support continuation plus non-bearish regime filter.",
        require_vol_regime_filter=True,
        vol_regime_min=10.0,
        vol_regime_max=34.0,
    )


def c25_vwap_support_continuation_candidates(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> List[OrbProfile]:
    return [
        c25_vwap_support_continuation_balance_v1(or_width_min=or_width_min),
        c25_vwap_support_continuation_quality_v1(or_width_min=or_width_min),
        c25_vwap_support_continuation_regime_v1(or_width_min=or_width_min),
    ]


def c26_gap_reclaim_continuation_balance_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    return _wave_long_profile(
        name="c26_gap_reclaim_continuation_balance_v1",
        description="Gap-up session, support-hold reclaim, then long continuation after reclaim.",
        strategy_variant="orb_event_drive_v1",
        entry_start_time="09:40",
        entry_cutoff_time="11:00",
        quality="balance",
        or_width_min=or_width_min,
        event_gap_abs_return=0.004,
        event_gap_direction=1,
        event_drive_min_gap_abs_return=0.004,
        event_drive_min_breakout_or_frac=0.04,
        event_drive_close_location_min=0.55,
        event_drive_min_volume_multiple=1.0,
    )


def c26_gap_reclaim_continuation_quality_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c26_gap_reclaim_continuation_balance_v1(or_width_min=or_width_min)
    return replace(
        apply_options_discovery_wrapper_v1(base, quality="quality", direction="long"),
        name="c26_gap_reclaim_continuation_quality_v1",
        description="Gap reclaim continuation with stronger gap and RVOL requirements.",
        require_relative_volume=True,
        relative_volume_min=1.0,
        event_gap_abs_return=0.006,
        event_drive_min_gap_abs_return=0.006,
        event_drive_min_breakout_or_frac=0.05,
        event_drive_min_volume_multiple=1.1,
    )


def c26_gap_reclaim_continuation_regime_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c26_gap_reclaim_continuation_quality_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c26_gap_reclaim_continuation_regime_v1",
        description="Quality gap reclaim continuation plus favorable index-volatility regime guard.",
        require_vol_regime_filter=True,
        vol_regime_min=10.0,
        vol_regime_max=32.0,
    )


def c26_gap_reclaim_continuation_candidates(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> List[OrbProfile]:
    return [
        c26_gap_reclaim_continuation_balance_v1(or_width_min=or_width_min),
        c26_gap_reclaim_continuation_quality_v1(or_width_min=or_width_min),
        c26_gap_reclaim_continuation_regime_v1(or_width_min=or_width_min),
    ]


def c27_intraday_compression_release_balance_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    return _wave_long_profile(
        name="c27_intraday_compression_release_balance_v1",
        description="Bullish drift above VWAP compresses near highs, then long on release.",
        strategy_variant="orb_transition_compression_v1",
        entry_start_time="10:00",
        entry_cutoff_time="12:00",
        quality="balance",
        or_width_min=or_width_min,
        compression_lookback_bars=4,
        compression_max_range_pct=0.0022,
        compression_breakout_buffer_or_frac=0.02,
        compression_min_volume_multiple=1.0,
        require_trend_alignment=True,
    )


def c27_intraday_compression_release_quality_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c27_intraday_compression_release_balance_v1(or_width_min=or_width_min)
    return replace(
        apply_options_discovery_wrapper_v1(base, quality="quality", direction="long"),
        name="c27_intraday_compression_release_quality_v1",
        description="Compression release with narrower structure and stronger RVOL.",
        require_relative_volume=True,
        relative_volume_min=1.0,
        compression_max_range_pct=0.0018,
        compression_min_volume_multiple=1.1,
        require_trend_alignment=True,
    )


def c27_intraday_compression_release_regime_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c27_intraday_compression_release_quality_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c27_intraday_compression_release_regime_v1",
        description="Quality compression release gated to bullish or neutral volatility regimes.",
        require_vol_regime_filter=True,
        vol_regime_min=10.0,
        vol_regime_max=30.0,
    )


def c27_intraday_compression_release_candidates(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> List[OrbProfile]:
    return [
        c27_intraday_compression_release_balance_v1(or_width_min=or_width_min),
        c27_intraday_compression_release_quality_v1(or_width_min=or_width_min),
        c27_intraday_compression_release_regime_v1(or_width_min=or_width_min),
    ]


def c28_failed_breakdown_reversal_balance_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    return _wave_long_profile(
        name="c28_failed_breakdown_reversal_balance_v1",
        description="Downside sweep reverses back above VWAP / OR midpoint; long on reversal follow-through.",
        strategy_variant="opening_exhaustion_reversal_v1",
        entry_start_time="09:40",
        entry_cutoff_time="11:30",
        quality="balance",
        or_width_min=or_width_min,
        require_breakout_open_inside_range=False,
    )


def c28_failed_breakdown_reversal_quality_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c28_failed_breakdown_reversal_balance_v1(or_width_min=or_width_min)
    return replace(
        apply_options_discovery_wrapper_v1(base, quality="quality", direction="long"),
        name="c28_failed_breakdown_reversal_quality_v1",
        description="Failed-breakdown reversal with stronger reversal close and shorter time budget.",
        require_relative_volume=True,
        relative_volume_min=1.0,
        entry_cutoff_time="11:00",
    )


def c28_failed_breakdown_reversal_regime_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c28_failed_breakdown_reversal_quality_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c28_failed_breakdown_reversal_regime_v1",
        description="Quality failed-breakdown reversal with non-bearish regime guard.",
        require_vol_regime_filter=True,
        vol_regime_min=10.0,
        vol_regime_max=34.0,
    )


def c28_failed_breakdown_reversal_candidates(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> List[OrbProfile]:
    return [
        c28_failed_breakdown_reversal_balance_v1(or_width_min=or_width_min),
        c28_failed_breakdown_reversal_quality_v1(or_width_min=or_width_min),
        c28_failed_breakdown_reversal_regime_v1(or_width_min=or_width_min),
    ]


def c29_open_drive_pullback_balance_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    return _wave_long_profile(
        name="c29_open_drive_pullback_balance_v1",
        description="Strong opening drive, shallow pullback above VWAP / OR high, then long on resumption.",
        strategy_variant="opening_drive_pullback_v1",
        entry_start_time="09:35",
        entry_cutoff_time="10:30",
        quality="balance",
        or_width_min=or_width_min,
        drive_min_abs_return_pct=0.004,
        drive_close_location_min=0.60,
        drive_pullback_min_retrace_frac=0.12,
        drive_pullback_max_retrace_frac=0.50,
        drive_reclaim_close_location_min=0.55,
        drive_reclaim_min_volume_multiple=0.9,
        drive_max_pullback_bars=6,
        require_trend_alignment=True,
    )


def c29_open_drive_pullback_quality_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c29_open_drive_pullback_balance_v1(or_width_min=or_width_min)
    return replace(
        apply_options_discovery_wrapper_v1(base, quality="quality", direction="long"),
        name="c29_open_drive_pullback_quality_v1",
        description="Opening-drive pullback with stronger drive and shallower pullback requirements.",
        require_relative_volume=True,
        relative_volume_min=1.0,
        drive_min_abs_return_pct=0.005,
        drive_pullback_max_retrace_frac=0.40,
        drive_reclaim_min_volume_multiple=1.0,
    )


def c29_open_drive_pullback_regime_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c29_open_drive_pullback_quality_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c29_open_drive_pullback_regime_v1",
        description="Quality opening-drive pullback gated to bullish regimes.",
        require_vol_regime_filter=True,
        vol_regime_min=10.0,
        vol_regime_max=30.0,
    )


def c29_open_drive_pullback_candidates(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> List[OrbProfile]:
    return [
        c29_open_drive_pullback_balance_v1(or_width_min=or_width_min),
        c29_open_drive_pullback_quality_v1(or_width_min=or_width_min),
        c29_open_drive_pullback_regime_v1(or_width_min=or_width_min),
    ]


def c30_orb_retest_higher_low_balance_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    return _wave_long_profile(
        name="c30_orb_retest_higher_low_balance_v1",
        description="ORB retest holds as a higher low above VWAP, then long on retest high break.",
        strategy_variant="orb_trend_pullback_v1",
        entry_start_time="09:40",
        entry_cutoff_time="11:15",
        quality="balance",
        or_width_min=or_width_min,
        trend_pullback_max_bars_after_breakout=5,
        trend_pullback_ema_buffer_pct=0.0012,
        trend_pullback_require_orb_reclaim=True,
        trend_pullback_min_breakout_or_frac=0.04,
        trend_pullback_min_volume_multiple=1.0,
        require_trend_alignment=True,
    )


def c30_orb_retest_higher_low_quality_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c30_orb_retest_higher_low_balance_v1(or_width_min=or_width_min)
    return replace(
        apply_options_discovery_wrapper_v1(base, quality="quality", direction="long"),
        name="c30_orb_retest_higher_low_quality_v1",
        description="Higher-low retest with earlier structure deadline and stronger RVOL.",
        require_relative_volume=True,
        relative_volume_min=1.0,
        entry_cutoff_time="10:45",
        trend_pullback_max_bars_after_breakout=4,
        trend_pullback_min_volume_multiple=1.1,
    )


def c30_orb_retest_higher_low_regime_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c30_orb_retest_higher_low_quality_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c30_orb_retest_higher_low_regime_v1",
        description="Quality retest-higher-low continuation with bullish or neutral regime guard.",
        require_vol_regime_filter=True,
        vol_regime_min=10.0,
        vol_regime_max=32.0,
    )


def c30_orb_retest_higher_low_candidates(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> List[OrbProfile]:
    return [
        c30_orb_retest_higher_low_balance_v1(or_width_min=or_width_min),
        c30_orb_retest_higher_low_quality_v1(or_width_min=or_width_min),
        c30_orb_retest_higher_low_regime_v1(or_width_min=or_width_min),
    ]


def c31_vwap_rollover_short_balance_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    return _wave_short_profile(
        name="c31_vwap_rollover_short_balance_v1",
        description="Failed bounce below VWAP forms a lower high, then short on rollover continuation.",
        strategy_variant="vwap_rollover_short_v1",
        entry_start_time="09:45",
        entry_cutoff_time="11:30",
        quality="balance",
        or_width_min=or_width_min,
        trend_pullback_max_bars_after_breakout=8,
        trend_pullback_ema_buffer_pct=0.0012,
        drive_reclaim_close_location_min=0.55,
        require_trend_alignment=True,
    )


def c31_vwap_rollover_short_quality_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c31_vwap_rollover_short_balance_v1(or_width_min=or_width_min)
    return replace(
        apply_options_discovery_wrapper_v1(base, quality="quality", direction="short"),
        name="c31_vwap_rollover_short_quality_v1",
        description="VWAP rollover short with stronger rejection structure and RVOL floor.",
        require_relative_volume=True,
        relative_volume_min=1.0,
        require_trend_alignment=True,
        trend_pullback_max_bars_after_breakout=6,
        drive_reclaim_close_location_min=0.60,
        trend_ema_fast=8,
        trend_ema_slow=21,
    )


def c31_vwap_rollover_short_regime_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c31_vwap_rollover_short_quality_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c31_vwap_rollover_short_regime_v1",
        description="Quality VWAP rollover short gated to bearish or neutral-bear regimes.",
        require_vol_regime_filter=True,
        vol_regime_min=10.0,
        vol_regime_max=36.0,
    )


def c31_vwap_rollover_short_candidates(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> List[OrbProfile]:
    return [
        c31_vwap_rollover_short_balance_v1(or_width_min=or_width_min),
        c31_vwap_rollover_short_quality_v1(or_width_min=or_width_min),
        c31_vwap_rollover_short_regime_v1(or_width_min=or_width_min),
    ]


def c32_gap_up_fail_fade_balance_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    return _wave_short_profile(
        name="c32_gap_up_fail_fade_balance_v1",
        description="Gap-up session fails to reclaim VWAP; short the failed-bounce continuation.",
        strategy_variant="orb_failure_fade",
        entry_start_time="09:40",
        entry_cutoff_time="11:00",
        quality="balance",
        or_width_min=or_width_min,
        event_gap_abs_return=0.004,
        event_gap_direction=1,
    )


def c32_gap_up_fail_fade_quality_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c32_gap_up_fail_fade_balance_v1(or_width_min=or_width_min)
    return replace(
        apply_options_discovery_wrapper_v1(base, quality="quality", direction="short"),
        name="c32_gap_up_fail_fade_quality_v1",
        description="Gap-up fail fade with stronger gap, rejection quality, and tighter bounce structure.",
        require_relative_volume=True,
        relative_volume_min=1.0,
        entry_cutoff_time="10:45",
        event_gap_abs_return=0.006,
    )


def c32_gap_up_fail_fade_regime_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c32_gap_up_fail_fade_quality_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c32_gap_up_fail_fade_regime_v1",
        description="Quality gap-up fail fade gated to bearish or weak-breadth volatility regimes.",
        require_vol_regime_filter=True,
        vol_regime_min=10.0,
        vol_regime_max=36.0,
    )


def c32_gap_up_fail_fade_candidates(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> List[OrbProfile]:
    return [
        c32_gap_up_fail_fade_balance_v1(or_width_min=or_width_min),
        c32_gap_up_fail_fade_quality_v1(or_width_min=or_width_min),
        c32_gap_up_fail_fade_regime_v1(or_width_min=or_width_min),
    ]


def _apply_option_explore_overlay_v1(
    profile: OrbProfile,
    *,
    name: str,
    description: str,
    option_min_dte: int,
    option_target_dte: int,
    option_max_dte: int,
    option_structure_mode: str = "single_leg",
    structure_filter_enabled: Optional[bool] = None,
) -> OrbProfile:
    effective_structure_filter = (
        bool(profile.option_structure_filter_enabled)
        if structure_filter_enabled is None
        else bool(structure_filter_enabled)
    )
    wrapped = replace(
        profile,
        name=name,
        description=description,
        option_min_open_interest=0,
        require_option_microstructure_filter=True,
        option_min_dte=int(option_min_dte),
        option_target_dte=int(option_target_dte),
        option_max_dte=int(option_max_dte),
        option_min_entry_volume=25,
        option_min_entry_price=0.60,
        option_max_entry_bar_range_pct=0.35,
        option_min_quote_coverage_pct=0.35,
        option_min_chain_coverage_pct=0.35,
        option_structure_mode=str(option_structure_mode or "single_leg"),
        option_structure_filter_enabled=effective_structure_filter,
        option_structure_min_open_interest=0,
        option_structure_min_entry_volume=25 if effective_structure_filter else 0,
        option_structure_max_entry_spread_pct=0.35 if effective_structure_filter else 1.0,
        option_structure_max_entry_bar_range_pct=0.35 if effective_structure_filter else 1.0,
        option_structure_min_entry_price=0.60 if effective_structure_filter else 0.0,
    )
    if str(option_structure_mode or "").strip().lower() == "vertical_debit":
        wrapped = replace(
            wrapped,
            option_vertical_short_leg_steps=2,
            option_vertical_fallback_short_leg_steps=3,
            option_vertical_max_debit_to_width_ratio=0.55,
            option_vertical_min_short_bid=0.10,
            option_vertical_max_combined_spread_to_debit_ratio=0.25,
            option_min_expected_move_to_debit_ratio=1.25,
        )
    return wrapped


def _resolve_dispersion_relative_breakout_base_profile(
    name: str,
    *,
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> Optional[OrbProfile]:
    normalized = str(name or "").strip().lower()
    builders = {
        "c4_dispersion_relative_breakout_v3": c4_dispersion_relative_breakout_v3,
        "dispersion_relative_breakout_v3": c4_dispersion_relative_breakout_v3,
        "c4_dispersion_relative_breakout_guard_v3": c4_dispersion_relative_breakout_guard_v3,
        "dispersion_relative_breakout_guard_v3": c4_dispersion_relative_breakout_guard_v3,
        "c4_dispersion_relative_breakout_decay_v4": c4_dispersion_relative_breakout_decay_v4,
        "dispersion_relative_breakout_decay_v4": c4_dispersion_relative_breakout_decay_v4,
        "c4_dispersion_relative_breakout_guard_hold30_v1": c4_dispersion_relative_breakout_guard_hold30_v1,
        "dispersion_relative_breakout_guard_hold30_v1": c4_dispersion_relative_breakout_guard_hold30_v1,
        "c4_dispersion_relative_breakout_guard_density_v1": c4_dispersion_relative_breakout_guard_density_v1,
        "dispersion_relative_breakout_guard_density_v1": c4_dispersion_relative_breakout_guard_density_v1,
        "c4_dispersion_relative_breakout_guard_density_spy_dia_v1": c4_dispersion_relative_breakout_guard_density_spy_dia_v1,
        "dispersion_relative_breakout_guard_density_spy_dia_v1": c4_dispersion_relative_breakout_guard_density_spy_dia_v1,
        "c4_dispersion_relative_breakout_guard_density_spy_dia_balance_v1": c4_dispersion_relative_breakout_guard_density_spy_dia_balance_v1,
        "dispersion_relative_breakout_guard_density_spy_dia_balance_v1": c4_dispersion_relative_breakout_guard_density_spy_dia_balance_v1,
        "c4_dispersion_relative_breakout_guard_density_spy_dia_offset_v1": c4_dispersion_relative_breakout_guard_density_spy_dia_offset_v1,
        "dispersion_relative_breakout_guard_density_spy_dia_offset_v1": c4_dispersion_relative_breakout_guard_density_spy_dia_offset_v1,
        "c4_dispersion_relative_breakout_recovery_v5": c4_dispersion_relative_breakout_recovery_v5,
        "dispersion_relative_breakout_recovery_v5": c4_dispersion_relative_breakout_recovery_v5,
    }
    builder = builders.get(normalized)
    if builder is None:
        return None
    return builder(or_width_min=or_width_min)


def _apply_dispersion_relative_breakout_option_followup_overlay_v1(
    profile: OrbProfile,
    *,
    option_structure_mode: str,
    name: str,
    description: str,
) -> OrbProfile:
    structure_mode = str(option_structure_mode or "single_leg").strip().lower() or "single_leg"
    wrapped = _apply_option_explore_overlay_v1(
        profile,
        name=name,
        description=description,
        option_min_dte=2,
        option_target_dte=3,
        option_max_dte=5,
        option_structure_mode=structure_mode,
        structure_filter_enabled=True,
    )
    common = dict(
        option_min_open_interest=1200,
        require_option_microstructure_filter=True,
        option_min_entry_volume=30,
        option_min_entry_price=0.70,
        option_selection_spread_weight=10.0,
        option_selection_max_quote_spread_pct=0.18,
        option_selection_spread_to_ask_weight=14.0,
        option_selection_max_spread_to_ask_ratio=0.10,
        option_selection_intrinsic_weight=14.0,
        option_selection_min_intrinsic_share=0.22,
        option_selection_target_abs_delta=0.50,
        option_selection_min_abs_delta=0.45,
        option_selection_max_abs_delta=0.60,
        option_structure_filter_enabled=True,
        option_structure_min_open_interest=1200,
        option_structure_min_entry_volume=30,
        option_structure_max_entry_spread_pct=0.18,
        option_structure_max_entry_bar_range_pct=0.35,
        option_structure_min_entry_price=0.70,
        early_fail_minutes=10,
        early_fail_min_rr=0.03,
    )
    if structure_mode == "vertical_debit":
        return replace(
            wrapped,
            **common,
            option_structure_mode="vertical_debit",
            option_vertical_short_leg_steps=1,
            option_vertical_fallback_short_leg_steps=2,
            option_vertical_min_short_bid=0.10,
            option_vertical_max_debit_to_width_ratio=0.65,
            option_vertical_max_combined_spread_to_debit_ratio=0.25,
            option_min_expected_move_to_debit_ratio=1.50,
            take_profit_rr=1.40,
            break_even_trigger_rr=0.45,
            max_hold_minutes=30,
            option_take_profit_pct=0.60,
            option_max_loss_pct=0.35,
        )
    return replace(
        wrapped,
        **common,
        option_structure_mode="single_leg",
        option_min_expected_move_to_extrinsic_ratio=1.75,
        option_min_expected_move_to_spread_ratio=5.75,
        take_profit_rr=1.55,
        break_even_trigger_rr=0.55,
        max_hold_minutes=35,
        option_take_profit_pct=0.75,
        option_max_loss_pct=0.40,
    )


def _maybe_build_dispersion_relative_breakout_option_followup_profile(
    name: str,
    *,
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> Optional[OrbProfile]:
    normalized = str(name or "").strip().lower()
    suffix_map = {
        "_option_native_single_dte35_v1": "single_leg",
        "_option_native_vertical_dte35_v1": "vertical_debit",
    }
    for suffix, structure_mode in suffix_map.items():
        if not normalized.endswith(suffix):
            continue
        base_name = normalized[: -len(suffix)]
        base = _resolve_dispersion_relative_breakout_base_profile(base_name, or_width_min=or_width_min)
        if base is None:
            return None
        description = (
            "Quote-aware single-leg 2-5 DTE option-native follow-up overlay for the selected "
            "dispersion-relative breakout stock survivor."
            if structure_mode == "single_leg"
            else "Quote-aware vertical-debit 2-5 DTE option-native follow-up overlay for the selected "
            "dispersion-relative breakout stock survivor."
        )
        return _apply_dispersion_relative_breakout_option_followup_overlay_v1(
            base,
            option_structure_mode=structure_mode,
            name=f"{base.name}{suffix}",
            description=description,
        )
    return None


def c4_dispersion_relative_breakout_guard_v3_option_native_single_dte35_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> OrbProfile:
    profile = _maybe_build_dispersion_relative_breakout_option_followup_profile(
        "c4_dispersion_relative_breakout_guard_v3_option_native_single_dte35_v1",
        or_width_min=or_width_min,
    )
    if profile is None:
        raise ValueError("failed to build c4 dispersion single-leg option-native follow-up profile")
    return profile


def c4_dispersion_relative_breakout_guard_v3_option_native_vertical_dte35_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> OrbProfile:
    profile = _maybe_build_dispersion_relative_breakout_option_followup_profile(
        "c4_dispersion_relative_breakout_guard_v3_option_native_vertical_dte35_v1",
        or_width_min=or_width_min,
    )
    if profile is None:
        raise ValueError("failed to build c4 dispersion vertical-debit option-native follow-up profile")
    return profile


def c33_gap_rejection_option_native_balance_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c14_gap_rejection_balance_v1(or_width_min=or_width_min)
    return _apply_option_explore_overlay_v1(
        base,
        name="c33_gap_rejection_option_native_balance_v1",
        description="Option-native gap rejection balance candidate with quote-aware single-leg execution.",
        option_min_dte=0,
        option_target_dte=1,
        option_max_dte=2,
    )


def c33_gap_rejection_option_native_quality_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c14_gap_rejection_quality_v1(or_width_min=or_width_min)
    return _apply_option_explore_overlay_v1(
        base,
        name="c33_gap_rejection_option_native_quality_v1",
        description="Higher-conviction option-native gap rejection candidate with quote-aware single-leg execution.",
        option_min_dte=0,
        option_target_dte=1,
        option_max_dte=2,
    )


def c33_gap_rejection_option_native_opportunity_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c14_gap_rejection_opportunity_v1(or_width_min=or_width_min)
    return _apply_option_explore_overlay_v1(
        base,
        name="c33_gap_rejection_option_native_opportunity_v1",
        description="Opportunity-biased option-native gap rejection candidate with quote-aware single-leg execution.",
        option_min_dte=0,
        option_target_dte=1,
        option_max_dte=2,
    )


def c33_gap_rejection_option_native_regime_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c14_gap_rejection_regime_v1(or_width_min=or_width_min)
    return _apply_option_explore_overlay_v1(
        base,
        name="c33_gap_rejection_option_native_regime_v1",
        description="Calmer-day option-native gap rejection candidate with quote-aware single-leg execution.",
        option_min_dte=0,
        option_target_dte=1,
        option_max_dte=2,
    )


def c33_gap_rejection_option_native_long_only_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c14_gap_rejection_long_only_v1(or_width_min=or_width_min)
    return _apply_option_explore_overlay_v1(
        base,
        name="c33_gap_rejection_option_native_long_only_v1",
        description="Long-only option-native gap rejection candidate with quote-aware single-leg execution.",
        option_min_dte=0,
        option_target_dte=1,
        option_max_dte=2,
    )


def c33_gap_rejection_option_native_candidates_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> List[OrbProfile]:
    return [
        c33_gap_rejection_option_native_balance_v1(or_width_min=or_width_min),
        c33_gap_rejection_option_native_quality_v1(or_width_min=or_width_min),
        c33_gap_rejection_option_native_opportunity_v1(or_width_min=or_width_min),
        c33_gap_rejection_option_native_regime_v1(or_width_min=or_width_min),
        c33_gap_rejection_option_native_long_only_v1(or_width_min=or_width_min),
    ]


def c34_failure_fade_option_native_balance_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c15_failure_fade_balance_v1(or_width_min=or_width_min)
    return _apply_option_explore_overlay_v1(
        base,
        name="c34_failure_fade_option_native_balance_v1",
        description="Option-native failure-fade balance candidate with quote-aware single-leg execution.",
        option_min_dte=0,
        option_target_dte=1,
        option_max_dte=2,
    )


def c34_failure_fade_option_native_quality_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c15_failure_fade_quality_v1(or_width_min=or_width_min)
    return _apply_option_explore_overlay_v1(
        base,
        name="c34_failure_fade_option_native_quality_v1",
        description="Higher-conviction option-native failure-fade candidate with quote-aware single-leg execution.",
        option_min_dte=0,
        option_target_dte=1,
        option_max_dte=2,
    )


def c34_failure_fade_option_native_regime_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c15_failure_fade_regime_v1(or_width_min=or_width_min)
    return _apply_option_explore_overlay_v1(
        base,
        name="c34_failure_fade_option_native_regime_v1",
        description="Calmer-day option-native failure-fade candidate with quote-aware single-leg execution.",
        option_min_dte=0,
        option_target_dte=1,
        option_max_dte=2,
    )


def c34_failure_fade_option_native_fast_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c15_failure_fade_fast_v1(or_width_min=or_width_min)
    return _apply_option_explore_overlay_v1(
        base,
        name="c34_failure_fade_option_native_fast_v1",
        description="Faster option-native failure-fade candidate with quote-aware single-leg execution.",
        option_min_dte=0,
        option_target_dte=1,
        option_max_dte=2,
    )


def c34_failure_fade_option_native_long_only_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c15_failure_fade_long_only_v1(or_width_min=or_width_min)
    return _apply_option_explore_overlay_v1(
        base,
        name="c34_failure_fade_option_native_long_only_v1",
        description="Long-only option-native failure-fade candidate with quote-aware single-leg execution.",
        option_min_dte=0,
        option_target_dte=1,
        option_max_dte=2,
    )


def c34_failure_fade_option_native_candidates_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> List[OrbProfile]:
    return [
        c34_failure_fade_option_native_balance_v1(or_width_min=or_width_min),
        c34_failure_fade_option_native_quality_v1(or_width_min=or_width_min),
        c34_failure_fade_option_native_regime_v1(or_width_min=or_width_min),
        c34_failure_fade_option_native_fast_v1(or_width_min=or_width_min),
        c34_failure_fade_option_native_long_only_v1(or_width_min=or_width_min),
    ]


def c35_failed_break_reclaim_option_native_balance_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c23_failed_break_reclaim_balance_v1(or_width_min=or_width_min)
    return _apply_option_explore_overlay_v1(
        base,
        name="c35_failed_break_reclaim_option_native_balance_v1",
        description="Option-native failed-break reclaim balance candidate with quote-aware single-leg execution.",
        option_min_dte=0,
        option_target_dte=1,
        option_max_dte=2,
    )


def c35_failed_break_reclaim_option_native_quality_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c23_failed_break_reclaim_quality_v1(or_width_min=or_width_min)
    return _apply_option_explore_overlay_v1(
        base,
        name="c35_failed_break_reclaim_option_native_quality_v1",
        description="Higher-conviction option-native failed-break reclaim candidate with quote-aware single-leg execution.",
        option_min_dte=0,
        option_target_dte=1,
        option_max_dte=2,
    )


def c35_failed_break_reclaim_option_native_regime_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c23_failed_break_reclaim_regime_v1(or_width_min=or_width_min)
    return _apply_option_explore_overlay_v1(
        base,
        name="c35_failed_break_reclaim_option_native_regime_v1",
        description="Calmer-day option-native failed-break reclaim candidate with quote-aware single-leg execution.",
        option_min_dte=0,
        option_target_dte=1,
        option_max_dte=2,
    )


def c35_failed_break_reclaim_option_native_candidates_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> List[OrbProfile]:
    return [
        c35_failed_break_reclaim_option_native_balance_v1(or_width_min=or_width_min),
        c35_failed_break_reclaim_option_native_quality_v1(or_width_min=or_width_min),
        c35_failed_break_reclaim_option_native_regime_v1(or_width_min=or_width_min),
    ]


def c36_vwap_mr_option_native_balance_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c18_vwap_mr_balance_v1(or_width_min=or_width_min)
    return _apply_option_explore_overlay_v1(
        base,
        name="c36_vwap_mr_option_native_balance_v1",
        description="Option-native VWAP mean-reversion balance candidate with quote-aware single-leg execution.",
        option_min_dte=0,
        option_target_dte=1,
        option_max_dte=2,
    )


def c36_vwap_mr_option_native_quality_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c18_vwap_mr_quality_v1(or_width_min=or_width_min)
    return _apply_option_explore_overlay_v1(
        base,
        name="c36_vwap_mr_option_native_quality_v1",
        description="Higher-conviction option-native VWAP mean-reversion candidate with quote-aware single-leg execution.",
        option_min_dte=0,
        option_target_dte=1,
        option_max_dte=2,
    )


def c36_vwap_mr_option_native_regime_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c18_vwap_mr_regime_v1(or_width_min=or_width_min)
    return _apply_option_explore_overlay_v1(
        base,
        name="c36_vwap_mr_option_native_regime_v1",
        description="Calmer-day option-native VWAP mean-reversion candidate with quote-aware single-leg execution.",
        option_min_dte=0,
        option_target_dte=1,
        option_max_dte=2,
    )


def c36_vwap_mr_option_native_opportunity_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c18_vwap_mr_opportunity_v1(or_width_min=or_width_min)
    return _apply_option_explore_overlay_v1(
        base,
        name="c36_vwap_mr_option_native_opportunity_v1",
        description="Opportunity-biased option-native VWAP mean-reversion candidate with quote-aware single-leg execution.",
        option_min_dte=0,
        option_target_dte=1,
        option_max_dte=2,
    )


def c36_vwap_mr_option_native_fast_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c18_vwap_mr_fast_v1(or_width_min=or_width_min)
    return _apply_option_explore_overlay_v1(
        base,
        name="c36_vwap_mr_option_native_fast_v1",
        description="Faster option-native VWAP mean-reversion candidate with quote-aware single-leg execution.",
        option_min_dte=0,
        option_target_dte=1,
        option_max_dte=2,
    )


def c36_vwap_mr_option_native_candidates_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> List[OrbProfile]:
    return [
        c36_vwap_mr_option_native_balance_v1(or_width_min=or_width_min),
        c36_vwap_mr_option_native_quality_v1(or_width_min=or_width_min),
        c36_vwap_mr_option_native_regime_v1(or_width_min=or_width_min),
        c36_vwap_mr_option_native_opportunity_v1(or_width_min=or_width_min),
        c36_vwap_mr_option_native_fast_v1(or_width_min=or_width_min),
    ]


def _c55_vwap_mr_option_native_density_base(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c18_vwap_mr_quality_v1(or_width_min=or_width_min)
    return replace(
        base,
        require_relative_volume=True,
        relative_volume_min=0.95,
        mr_zscore_entry=1.20,
        mr_zscore_reentry=0.58,
        mr_zscore_stop=2.00,
        mr_zscore_target=0.17,
        mr_sigma_min_pct=0.0004,
        mr_sigma_max_pct=0.018,
        mr_vwap_slope_max_pct=0.0024,
        max_hold_minutes=28,
    )


def c55_vwap_mr_option_native_density_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = _c55_vwap_mr_option_native_density_base(or_width_min=or_width_min)
    return _apply_option_explore_overlay_v1(
        base,
        name="c55_vwap_mr_option_native_density_v1",
        description="Denser option-native VWAP mean-reversion candidate that relaxes the c36 quality gate without dropping quote-aware single-leg execution.",
        option_min_dte=0,
        option_target_dte=1,
        option_max_dte=2,
    )


def c55_vwap_mr_option_native_density_regime_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = replace(
        _c55_vwap_mr_option_native_density_base(or_width_min=or_width_min),
        require_vol_regime_filter=True,
        vol_regime_min=12.0,
        vol_regime_max=34.0,
        require_prior_day_range_filter=True,
        prior_day_range_max_pct=0.024,
    )
    return _apply_option_explore_overlay_v1(
        base,
        name="c55_vwap_mr_option_native_density_regime_v1",
        description="Denser option-native VWAP mean-reversion candidate restricted to calmer, narrower prior-day conditions.",
        option_min_dte=0,
        option_target_dte=1,
        option_max_dte=2,
    )


def c55_vwap_mr_option_native_opportunity_guard_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = replace(
        c18_vwap_mr_opportunity_v1(or_width_min=or_width_min),
        require_relative_volume=True,
        relative_volume_min=0.90,
        mr_zscore_entry=1.08,
        mr_zscore_reentry=0.50,
        mr_zscore_stop=1.85,
        mr_zscore_target=0.18,
        mr_sigma_min_pct=0.0003,
        mr_sigma_max_pct=0.020,
        mr_vwap_slope_max_pct=0.0026,
        max_hold_minutes=32,
    )
    return _apply_option_explore_overlay_v1(
        base,
        name="c55_vwap_mr_option_native_opportunity_guard_v1",
        description="Opportunity-biased option-native VWAP mean-reversion candidate with a tighter relative-volume and sigma guardrail.",
        option_min_dte=0,
        option_target_dte=1,
        option_max_dte=2,
    )


def c55_vwap_mr_option_native_candidates_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> List[OrbProfile]:
    return [
        c55_vwap_mr_option_native_density_v1(or_width_min=or_width_min),
        c55_vwap_mr_option_native_density_regime_v1(or_width_min=or_width_min),
        c55_vwap_mr_option_native_opportunity_guard_v1(or_width_min=or_width_min),
    ]


def c37_vwap_mr_debit_spread_balance_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c18_vwap_mr_long_only_balance_v2(or_width_min=or_width_min)
    return _apply_option_explore_overlay_v1(
        base,
        name="c37_vwap_mr_debit_spread_balance_v1",
        description="VWAP mean-reversion debit-spread balance candidate with quote-aware spread execution.",
        option_min_dte=2,
        option_target_dte=3,
        option_max_dte=5,
        option_structure_mode="vertical_debit",
    )


def c37_vwap_mr_debit_spread_quality_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c18_vwap_mr_long_only_quality_v2(or_width_min=or_width_min)
    return _apply_option_explore_overlay_v1(
        base,
        name="c37_vwap_mr_debit_spread_quality_v1",
        description="Higher-conviction VWAP mean-reversion debit-spread candidate with quote-aware spread execution.",
        option_min_dte=2,
        option_target_dte=3,
        option_max_dte=5,
        option_structure_mode="vertical_debit",
    )


def c37_vwap_mr_debit_spread_regime_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c18_vwap_mr_long_only_regime_v2(or_width_min=or_width_min)
    return _apply_option_explore_overlay_v1(
        base,
        name="c37_vwap_mr_debit_spread_regime_v1",
        description="Calmer-day VWAP mean-reversion debit-spread candidate with quote-aware spread execution.",
        option_min_dte=2,
        option_target_dte=3,
        option_max_dte=5,
        option_structure_mode="vertical_debit",
    )


def c37_vwap_mr_debit_spread_candidates_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> List[OrbProfile]:
    return [
        c37_vwap_mr_debit_spread_balance_v1(or_width_min=or_width_min),
        c37_vwap_mr_debit_spread_quality_v1(or_width_min=or_width_min),
        c37_vwap_mr_debit_spread_regime_v1(or_width_min=or_width_min),
    ]


def c52_opening_compression_option_native_balance_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c9_opening_compression_balance_v1(or_width_min=or_width_min)
    return _apply_option_explore_overlay_v1(
        base,
        name="c52_opening_compression_option_native_balance_v1",
        description="Option-native opening compression balance candidate with quote-aware single-leg execution.",
        option_min_dte=0,
        option_target_dte=1,
        option_max_dte=2,
    )


def c52_opening_compression_option_native_long_only_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c9_opening_compression_long_only_v1(or_width_min=or_width_min)
    return _apply_option_explore_overlay_v1(
        base,
        name="c52_opening_compression_option_native_long_only_v1",
        description="Long-only option-native opening compression candidate with quote-aware single-leg execution.",
        option_min_dte=0,
        option_target_dte=1,
        option_max_dte=2,
    )


def c52_opening_compression_option_native_candidates_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> List[OrbProfile]:
    return [
        c52_opening_compression_option_native_balance_v1(or_width_min=or_width_min),
        c52_opening_compression_option_native_long_only_v1(or_width_min=or_width_min),
    ]


def c53_intraday_compression_release_option_native_balance_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> OrbProfile:
    base = c27_intraday_compression_release_balance_v1(or_width_min=or_width_min)
    return _apply_option_explore_overlay_v1(
        base,
        name="c53_intraday_compression_release_option_native_balance_v1",
        description="Option-native intraday compression-release balance candidate with quote-aware single-leg execution.",
        option_min_dte=0,
        option_target_dte=1,
        option_max_dte=2,
    )


def c53_intraday_compression_release_option_native_quality_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> OrbProfile:
    base = c27_intraday_compression_release_quality_v1(or_width_min=or_width_min)
    return _apply_option_explore_overlay_v1(
        base,
        name="c53_intraday_compression_release_option_native_quality_v1",
        description="Higher-conviction option-native intraday compression-release candidate with quote-aware single-leg execution.",
        option_min_dte=0,
        option_target_dte=1,
        option_max_dte=2,
    )


def c53_intraday_compression_release_option_native_regime_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> OrbProfile:
    base = c27_intraday_compression_release_regime_v1(or_width_min=or_width_min)
    return _apply_option_explore_overlay_v1(
        base,
        name="c53_intraday_compression_release_option_native_regime_v1",
        description="Calmer-day option-native intraday compression-release candidate with quote-aware single-leg execution.",
        option_min_dte=0,
        option_target_dte=1,
        option_max_dte=2,
    )


def c53_intraday_compression_release_option_native_candidates_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> List[OrbProfile]:
    return [
        c53_intraday_compression_release_option_native_balance_v1(or_width_min=or_width_min),
        c53_intraday_compression_release_option_native_quality_v1(or_width_min=or_width_min),
        c53_intraday_compression_release_option_native_regime_v1(or_width_min=or_width_min),
    ]


def c54_opening_compression_option_native_balance_dte35_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> OrbProfile:
    base = c9_opening_compression_balance_v1(or_width_min=or_width_min)
    return _apply_option_explore_overlay_v1(
        base,
        name="c54_opening_compression_option_native_balance_dte35_v1",
        description="Opening compression balance candidate with quote-aware single-leg execution and 3-5 DTE targeting.",
        option_min_dte=2,
        option_target_dte=3,
        option_max_dte=5,
    )


def c54_opening_compression_option_native_quality_dte35_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> OrbProfile:
    base = c9_opening_compression_quality_v1(or_width_min=or_width_min)
    return _apply_option_explore_overlay_v1(
        base,
        name="c54_opening_compression_option_native_quality_dte35_v1",
        description="Higher-conviction opening compression candidate with quote-aware single-leg execution and 3-5 DTE targeting.",
        option_min_dte=2,
        option_target_dte=3,
        option_max_dte=5,
    )


def c54_opening_compression_option_native_regime_dte35_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> OrbProfile:
    base = c9_opening_compression_regime_v1(or_width_min=or_width_min)
    return _apply_option_explore_overlay_v1(
        base,
        name="c54_opening_compression_option_native_regime_dte35_v1",
        description="Calmer-day opening compression candidate with quote-aware single-leg execution and 3-5 DTE targeting.",
        option_min_dte=2,
        option_target_dte=3,
        option_max_dte=5,
    )


def c54_opening_compression_option_native_dte35_candidates_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> List[OrbProfile]:
    return [
        c54_opening_compression_option_native_balance_dte35_v1(or_width_min=or_width_min),
        c54_opening_compression_option_native_quality_dte35_v1(or_width_min=or_width_min),
        c54_opening_compression_option_native_regime_dte35_v1(or_width_min=or_width_min),
    ]


def c59_opening_compression_option_native_consistency_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> OrbProfile:
    base = c58_opening_compression_consistency_v1(or_width_min=or_width_min)
    wrapped = _apply_option_explore_overlay_v1(
        base,
        name="c59_opening_compression_option_native_consistency_v1",
        description=(
            "Consistency-focused opening compression single-leg wrapper with 3-5 DTE targeting "
            "and explicit option-structure gating."
        ),
        option_min_dte=2,
        option_target_dte=3,
        option_max_dte=5,
        structure_filter_enabled=True,
    )
    return replace(
        wrapped,
        option_min_open_interest=250,
        option_min_entry_volume=40,
        option_min_entry_price=0.80,
        option_max_entry_bar_range_pct=0.28,
        option_min_quote_coverage_pct=0.45,
        option_min_chain_coverage_pct=0.45,
        option_min_expected_move_to_extrinsic_ratio=2.10,
        option_min_expected_move_to_spread_ratio=7.0,
        option_selection_target_abs_delta=0.45,
        option_selection_min_intrinsic_share=0.10,
        option_selection_max_quote_spread_pct=0.24,
        option_selection_max_spread_to_ask_ratio=0.12,
        option_structure_filter_enabled=True,
        option_structure_min_open_interest=600,
        option_structure_min_entry_volume=40,
        option_structure_max_entry_spread_pct=0.22,
        option_structure_max_entry_bar_range_pct=0.28,
        option_structure_min_entry_price=0.80,
    )


def c59_opening_compression_option_native_consistency_regime_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> OrbProfile:
    base = c58_opening_compression_consistency_regime_v1(or_width_min=or_width_min)
    wrapped = _apply_option_explore_overlay_v1(
        base,
        name="c59_opening_compression_option_native_consistency_regime_v1",
        description=(
            "Calmer-day consistency-focused opening compression wrapper with tighter contract "
            "quality filters and 3-5 DTE targeting."
        ),
        option_min_dte=2,
        option_target_dte=3,
        option_max_dte=5,
        structure_filter_enabled=True,
    )
    return replace(
        wrapped,
        option_min_open_interest=300,
        option_min_entry_volume=50,
        option_min_entry_price=0.85,
        option_max_entry_bar_range_pct=0.26,
        option_min_quote_coverage_pct=0.45,
        option_min_chain_coverage_pct=0.45,
        option_min_expected_move_to_extrinsic_ratio=2.20,
        option_min_expected_move_to_spread_ratio=7.5,
        option_selection_target_abs_delta=0.50,
        option_selection_min_intrinsic_share=0.12,
        option_selection_max_quote_spread_pct=0.22,
        option_selection_max_spread_to_ask_ratio=0.11,
        option_structure_filter_enabled=True,
        option_structure_min_open_interest=900,
        option_structure_min_entry_volume=50,
        option_structure_max_entry_spread_pct=0.20,
        option_structure_max_entry_bar_range_pct=0.26,
        option_structure_min_entry_price=0.85,
    )


def c59_opening_compression_option_native_consistency_candidates_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> List[OrbProfile]:
    return [
        c59_opening_compression_option_native_consistency_v1(or_width_min=or_width_min),
        c59_opening_compression_option_native_consistency_regime_v1(or_width_min=or_width_min),
    ]


def c60_opening_compression_option_native_hybrid_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> OrbProfile:
    base = c58_opening_compression_consistency_regime_v1(or_width_min=or_width_min)
    wrapped = _apply_option_explore_overlay_v1(
        base,
        name="c60_opening_compression_option_native_hybrid_v1",
        description=(
            "Hybrid opening compression wrapper that keeps the calmer c58 regime signal, "
            "uses 3-5 DTE targeting, and applies moderate quote/cost guards without the "
            "heavy structure filter that starved c59."
        ),
        option_min_dte=2,
        option_target_dte=3,
        option_max_dte=5,
        structure_filter_enabled=False,
    )
    return replace(
        wrapped,
        option_min_open_interest=75,
        option_min_entry_volume=30,
        option_min_entry_price=0.70,
        option_max_entry_bar_range_pct=0.32,
        option_min_quote_coverage_pct=0.40,
        option_min_chain_coverage_pct=0.40,
        option_min_expected_move_to_extrinsic_ratio=1.75,
        option_min_expected_move_to_spread_ratio=5.75,
        option_selection_target_abs_delta=0.45,
        option_selection_min_intrinsic_share=0.08,
        option_selection_max_quote_spread_pct=0.30,
        option_selection_max_spread_to_ask_ratio=0.15,
        option_structure_filter_enabled=False,
        option_structure_min_open_interest=0,
        option_structure_min_entry_volume=0,
        option_structure_max_entry_spread_pct=1.0,
        option_structure_max_entry_bar_range_pct=1.0,
        option_structure_min_entry_price=0.0,
    )


def c60_opening_compression_option_native_hybrid_candidates_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> List[OrbProfile]:
    return [
        c60_opening_compression_option_native_hybrid_v1(or_width_min=or_width_min),
    ]


def c62_opening_compression_option_native_stability_fast_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> OrbProfile:
    base = c61_opening_compression_stability_balance_v1(or_width_min=or_width_min)
    return _apply_option_explore_overlay_v1(
        base,
        name="c62_opening_compression_option_native_stability_fast_v1",
        description=(
            "Option-native midpoint opening compression candidate using the c61 balance signal and "
            "0-2 DTE single-leg execution."
        ),
        option_min_dte=0,
        option_target_dte=1,
        option_max_dte=2,
    )


def c62_opening_compression_option_native_stability_dte35_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> OrbProfile:
    base = c61_opening_compression_stability_regime_v1(or_width_min=or_width_min)
    return _apply_option_explore_overlay_v1(
        base,
        name="c62_opening_compression_option_native_stability_dte35_v1",
        description=(
            "Option-native midpoint opening compression candidate using the c61 regime signal and "
            "2-5 DTE single-leg execution."
        ),
        option_min_dte=2,
        option_target_dte=3,
        option_max_dte=5,
    )


def c62_opening_compression_option_native_stability_candidates_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> List[OrbProfile]:
    return [
        c62_opening_compression_option_native_stability_fast_v1(or_width_min=or_width_min),
        c62_opening_compression_option_native_stability_dte35_v1(or_width_min=or_width_min),
    ]


def c63_opening_compression_option_native_balance_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> OrbProfile:
    base = c63_opening_compression_smoother_balance_v1(or_width_min=or_width_min)
    return _apply_option_explore_overlay_v1(
        base,
        name="c63_opening_compression_option_native_balance_v1",
        description=(
            "Option-native smoother opening compression balance candidate with quote-aware "
            "single-leg execution at 0-2 DTE."
        ),
        option_min_dte=0,
        option_target_dte=1,
        option_max_dte=2,
    )


def c63_opening_compression_option_native_quality_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> OrbProfile:
    base = c63_opening_compression_smoother_quality_v1(or_width_min=or_width_min)
    return _apply_option_explore_overlay_v1(
        base,
        name="c63_opening_compression_option_native_quality_v1",
        description=(
            "Higher-conviction option-native smoother opening compression candidate with "
            "quote-aware single-leg execution at 0-2 DTE."
        ),
        option_min_dte=0,
        option_target_dte=1,
        option_max_dte=2,
    )


def c63_opening_compression_option_native_candidates_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> List[OrbProfile]:
    return [
        c63_opening_compression_option_native_balance_v1(or_width_min=or_width_min),
        c63_opening_compression_option_native_quality_v1(or_width_min=or_width_min),
    ]


def c64_opening_compression_option_native_balance_dte35_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> OrbProfile:
    base = c9_opening_compression_balance_v1(or_width_min=or_width_min)
    return _apply_option_explore_overlay_v1(
        base,
        name="c64_opening_compression_option_native_balance_dte35_v1",
        description=(
            "Opening compression balance candidate with quote-aware single-leg execution and "
            "2-5 DTE targeting for the slower robustness lane."
        ),
        option_min_dte=2,
        option_target_dte=3,
        option_max_dte=5,
    )


def c64_opening_compression_option_native_stability_balance_dte35_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> OrbProfile:
    base = c61_opening_compression_stability_balance_v1(or_width_min=or_width_min)
    return _apply_option_explore_overlay_v1(
        base,
        name="c64_opening_compression_option_native_stability_balance_dte35_v1",
        description=(
            "Midpoint opening compression balance candidate with quote-aware single-leg "
            "execution and 2-5 DTE targeting."
        ),
        option_min_dte=2,
        option_target_dte=3,
        option_max_dte=5,
    )


def c64_opening_compression_option_native_dte35_candidates_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> List[OrbProfile]:
    return [
        c64_opening_compression_option_native_balance_dte35_v1(or_width_min=or_width_min),
        c64_opening_compression_option_native_stability_balance_dte35_v1(or_width_min=or_width_min),
    ]


def c65_opening_compression_short_quality_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c63_opening_compression_smoother_quality_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c65_opening_compression_short_quality_v1",
        description=(
            "Short-only smoother opening compression candidate that keeps the c63 quality shape "
            "while modestly loosening density filters."
        ),
        allow_long=False,
        allow_short=True,
        relative_volume_min=0.92,
        prior_day_range_max_pct=0.024,
        compression_min_volume_multiple=1.10,
    )


def c65_opening_compression_long_balance_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    base = c9_opening_compression_balance_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c65_opening_compression_long_balance_v1",
        description=(
            "Long-only smoother opening compression candidate that keeps c9 density while using "
            "the faster c63-style exit timing."
        ),
        allow_long=True,
        allow_short=False,
        take_profit_rr=1.10,
        break_even_trigger_rr=0.30,
        early_fail_minutes=10,
        early_fail_min_rr=0.05,
        max_hold_minutes=28,
        relative_volume_min=0.88,
        compression_lookback_bars=4,
        compression_max_range_pct=0.0028,
        compression_breakout_buffer_or_frac=0.018,
        compression_min_volume_multiple=1.05,
    )


def c65_opening_compression_directional_candidates_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> List[OrbProfile]:
    return [
        c65_opening_compression_short_quality_v1(or_width_min=or_width_min),
        c65_opening_compression_long_balance_v1(or_width_min=or_width_min),
    ]


def c65_opening_compression_option_native_short_quality_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> OrbProfile:
    base = c65_opening_compression_short_quality_v1(or_width_min=or_width_min)
    return _apply_option_explore_overlay_v1(
        base,
        name="c65_opening_compression_option_native_short_quality_v1",
        description=(
            "Short-only option-native smoother opening compression candidate with quote-aware "
            "single-leg execution at 0-2 DTE."
        ),
        option_min_dte=0,
        option_target_dte=1,
        option_max_dte=2,
    )


def c65_opening_compression_option_native_long_balance_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> OrbProfile:
    base = c65_opening_compression_long_balance_v1(or_width_min=or_width_min)
    return _apply_option_explore_overlay_v1(
        base,
        name="c65_opening_compression_option_native_long_balance_v1",
        description=(
            "Long-only option-native smoother opening compression candidate with quote-aware "
            "single-leg execution at 0-2 DTE."
        ),
        option_min_dte=0,
        option_target_dte=1,
        option_max_dte=2,
    )


def c65_opening_compression_option_native_directional_candidates_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> List[OrbProfile]:
    return [
        c65_opening_compression_option_native_short_quality_v1(or_width_min=or_width_min),
        c65_opening_compression_option_native_long_balance_v1(or_width_min=or_width_min),
    ]


def c66_opening_compression_option_native_short_balance_dte35_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> OrbProfile:
    base = replace(
        c9_opening_compression_balance_v1(or_width_min=or_width_min),
        allow_long=False,
        allow_short=True,
        take_profit_rr=1.10,
        break_even_trigger_rr=0.30,
        early_fail_minutes=10,
        early_fail_min_rr=0.05,
        max_hold_minutes=28,
        require_vol_regime_filter=True,
        vol_regime_min=10.0,
        vol_regime_max=30.0,
        require_prior_day_range_filter=True,
        prior_day_range_max_pct=0.024,
        relative_volume_min=0.90,
        compression_lookback_bars=4,
        compression_max_range_pct=0.0028,
        compression_breakout_buffer_or_frac=0.018,
        compression_min_volume_multiple=1.10,
    )
    return _apply_option_explore_overlay_v1(
        base,
        name="c66_opening_compression_option_native_short_balance_dte35_v1",
        description=(
            "Short-only slower-DTE opening compression candidate with quote-aware single-leg "
            "execution and mild calmer-day filters."
        ),
        option_min_dte=2,
        option_target_dte=3,
        option_max_dte=5,
    )


def c66_opening_compression_option_native_dte35_candidates_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> List[OrbProfile]:
    return [
        c66_opening_compression_option_native_short_balance_dte35_v1(or_width_min=or_width_min),
    ]


def c95_opening_compression_option_native_short_balance_dte35_band22_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> OrbProfile:
    base = c66_opening_compression_option_native_short_balance_dte35_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c95_opening_compression_option_native_short_balance_dte35_band22_v1",
        description=(
            "c66-derived short-only slower-DTE opening compression candidate that keeps the original "
            "signal shape but ranks the local ATM, two-ITM, and two-OTM strike neighborhood by "
            "quote quality and entry-bar liquidity."
        ),
        option_selection_use_quote_spread=True,
        option_selection_quote_top_n=8,
        option_selection_spread_weight=10.0,
        option_selection_max_quote_spread_pct=0.30,
        option_selection_spread_to_ask_weight=6.0,
        option_selection_max_spread_to_ask_ratio=0.18,
        option_selection_delta_weight=4.0,
        option_selection_target_abs_delta=0.50,
        option_selection_min_abs_delta=0.20,
        option_selection_max_abs_delta=0.80,
        option_selection_local_itm_steps=2,
        option_selection_local_otm_steps=2,
        option_selection_entry_bar_volume_weight=2.0,
    )


def c95_opening_compression_option_native_dte35_band22_candidates_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> List[OrbProfile]:
    return [
        c95_opening_compression_option_native_short_balance_dte35_band22_v1(or_width_min=or_width_min),
    ]


def c96_opening_compression_option_native_short_balance_dte35_etf_liquidity_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> OrbProfile:
    base = c95_opening_compression_option_native_short_balance_dte35_band22_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c96_opening_compression_option_native_short_balance_dte35_etf_liquidity_v1",
        description=(
            "c95-derived short-only slower-DTE ETF candidate that keeps the c66 signal unchanged but "
            "relaxes ETF option-quality thresholds enough to admit more liquid breadth candidates."
        ),
        option_min_entry_volume=15,
        option_min_quote_coverage_pct=0.30,
        option_min_chain_coverage_pct=0.30,
        option_max_entry_bar_range_pct=0.30,
        option_selection_max_quote_spread_pct=0.28,
        option_selection_max_spread_to_ask_ratio=0.15,
    )


def c97_opening_compression_option_native_short_balance_dte35_etf_breadth_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> OrbProfile:
    base = c96_opening_compression_option_native_short_balance_dte35_etf_liquidity_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c97_opening_compression_option_native_short_balance_dte35_etf_breadth_v1",
        description=(
            "c96-derived short-only slower-DTE ETF candidate that modestly relaxes the c66 signal "
            "filters while preserving the 2-ITM/2-OTM local strike selector."
        ),
        relative_volume_min=0.85,
        compression_max_range_pct=0.0030,
        compression_min_volume_multiple=1.05,
        vol_regime_max=32.0,
        prior_day_range_max_pct=0.026,
    )


def c98_opening_compression_option_native_short_balance_dte35_etf_sizeaware_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> OrbProfile:
    base = c96_opening_compression_option_native_short_balance_dte35_etf_liquidity_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c98_opening_compression_option_native_short_balance_dte35_etf_sizeaware_v1",
        description=(
            "c96-derived short-only slower-DTE ETF candidate that keeps the c66/c95 signal shape "
            "but switches the microstructure gate to size-aware absolute entry-volume checks."
        ),
        option_microstructure_gate_mode="size_aware_absolute",
        option_min_entry_volume=10,
    )


def c99_opening_compression_option_native_short_balance_dte35_etf_retry2_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> OrbProfile:
    base = c96_opening_compression_option_native_short_balance_dte35_etf_liquidity_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c99_opening_compression_option_native_short_balance_dte35_etf_retry2_v1",
        description=(
            "c96-derived short-only ETF candidate that keeps the same signal and local 2-ITM/2-OTM "
            "selector, but retries up to two alternates from the ranked contract pool when the "
            "primary contract fails a retryable post-selection microstructure gate."
        ),
        option_post_selection_conversion_mode="retry_ranked_pool_v1",
        option_post_selection_max_alternates=2,
    )


def c100_opening_compression_option_native_short_balance_dte35_etf_retry4_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> OrbProfile:
    base = c96_opening_compression_option_native_short_balance_dte35_etf_liquidity_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c100_opening_compression_option_native_short_balance_dte35_etf_retry4_v1",
        description=(
            "c96-derived short-only ETF candidate that expands post-selection conversion to four "
            "alternates from the same ranked contract pool."
        ),
        option_post_selection_conversion_mode="retry_ranked_pool_v1",
        option_post_selection_max_alternates=4,
    )


def c101_opening_compression_option_native_short_balance_dte35_etf_breadth_retry2_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> OrbProfile:
    base = c97_opening_compression_option_native_short_balance_dte35_etf_breadth_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c101_opening_compression_option_native_short_balance_dte35_etf_breadth_retry2_v1",
        description=(
            "c97-derived short-only ETF breadth candidate that adds two ranked-pool post-selection "
            "conversion retries without changing the broadened c97 signal thresholds."
        ),
        option_post_selection_conversion_mode="retry_ranked_pool_v1",
        option_post_selection_max_alternates=2,
    )


def c102_opening_compression_option_native_short_balance_dte35_etf_quality_retry2_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> OrbProfile:
    base = c96_opening_compression_option_native_short_balance_dte35_etf_liquidity_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c102_opening_compression_option_native_short_balance_dte35_etf_quality_retry2_v1",
        description=(
            "c96-derived short-only ETF candidate that keeps the local 2-ITM/2-OTM selector, "
            "raises entry-bar-volume selection weight, and retries only rank-2 quality-banded "
            "alternates from the existing ranked pool."
        ),
        option_selection_entry_bar_volume_weight=4.0,
        option_post_selection_conversion_mode="retry_ranked_pool_quality_band_v1",
        option_post_selection_max_alternates=2,
        option_post_selection_max_final_rank=2,
        option_post_selection_max_final_strike_distance_steps=1,
    )


def c103_opening_compression_option_native_short_balance_dte35_etf_sameexpiry_retry4_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> OrbProfile:
    base = c96_opening_compression_option_native_short_balance_dte35_etf_liquidity_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c103_opening_compression_option_native_short_balance_dte35_etf_sameexpiry_retry4_v1",
        description=(
            "c96-derived short-only ETF candidate that biases primary selection toward better "
            "entry-minute liquidity and allows same-expiry quality-banded conversion up to rank 3."
        ),
        option_selection_entry_bar_volume_weight=4.0,
        option_post_selection_conversion_mode="retry_same_expiry_quality_band_v1",
        option_post_selection_max_alternates=4,
        option_post_selection_max_final_rank=3,
        option_post_selection_max_final_strike_distance_steps=1,
    )


def c104_opening_compression_option_native_short_balance_dte35_etf_breadth_sameexpiry_retry2_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> OrbProfile:
    base = c97_opening_compression_option_native_short_balance_dte35_etf_breadth_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c104_opening_compression_option_native_short_balance_dte35_etf_breadth_sameexpiry_retry2_v1",
        description=(
            "c97-derived short-only ETF breadth candidate that keeps the broader signal relaxations "
            "but limits conversion to same-expiry rank-2 quality-banded alternates."
        ),
        option_selection_entry_bar_volume_weight=4.0,
        option_post_selection_conversion_mode="retry_same_expiry_quality_band_v1",
        option_post_selection_max_alternates=2,
        option_post_selection_max_final_rank=2,
        option_post_selection_max_final_strike_distance_steps=1,
    )


def c66_opening_compression_option_native_dte35_etf_conversion_candidates_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> List[OrbProfile]:
    return [
        c66_opening_compression_option_native_short_balance_dte35_v1(or_width_min=or_width_min),
        c95_opening_compression_option_native_short_balance_dte35_band22_v1(or_width_min=or_width_min),
        c96_opening_compression_option_native_short_balance_dte35_etf_liquidity_v1(or_width_min=or_width_min),
        c99_opening_compression_option_native_short_balance_dte35_etf_retry2_v1(or_width_min=or_width_min),
        c100_opening_compression_option_native_short_balance_dte35_etf_retry4_v1(or_width_min=or_width_min),
        c101_opening_compression_option_native_short_balance_dte35_etf_breadth_retry2_v1(
            or_width_min=or_width_min
        ),
    ]


def c66_opening_compression_option_native_dte35_etf_quality_conversion_candidates_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> List[OrbProfile]:
    return [
        c66_opening_compression_option_native_short_balance_dte35_v1(or_width_min=or_width_min),
        c96_opening_compression_option_native_short_balance_dte35_etf_liquidity_v1(or_width_min=or_width_min),
        c102_opening_compression_option_native_short_balance_dte35_etf_quality_retry2_v1(
            or_width_min=or_width_min
        ),
        c103_opening_compression_option_native_short_balance_dte35_etf_sameexpiry_retry4_v1(
            or_width_min=or_width_min
        ),
        c104_opening_compression_option_native_short_balance_dte35_etf_breadth_sameexpiry_retry2_v1(
            or_width_min=or_width_min
        ),
    ]


def c66_opening_compression_option_native_dte35_etf_breadth_candidates_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> List[OrbProfile]:
    return [
        c66_opening_compression_option_native_short_balance_dte35_v1(or_width_min=or_width_min),
        c95_opening_compression_option_native_short_balance_dte35_band22_v1(or_width_min=or_width_min),
        c96_opening_compression_option_native_short_balance_dte35_etf_liquidity_v1(or_width_min=or_width_min),
        c97_opening_compression_option_native_short_balance_dte35_etf_breadth_v1(or_width_min=or_width_min),
        c98_opening_compression_option_native_short_balance_dte35_etf_sizeaware_v1(or_width_min=or_width_min),
    ]


def c67_opening_compression_option_native_broad_etf_balance_dte35_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> OrbProfile:
    base = replace(
        c9_opening_compression_balance_v1(or_width_min=or_width_min),
        allow_long=True,
        allow_short=True,
        take_profit_rr=1.20,
        break_even_trigger_rr=0.40,
        early_fail_minutes=12,
        early_fail_min_rr=0.05,
        max_hold_minutes=34,
        require_vol_regime_filter=False,
        vol_regime_min=0.0,
        vol_regime_max=1000.0,
        require_prior_day_range_filter=False,
        prior_day_range_max_pct=1.0,
        relative_volume_min=0.85,
        compression_lookback_bars=4,
        compression_max_range_pct=0.0032,
        compression_breakout_buffer_or_frac=0.018,
        compression_min_volume_multiple=1.00,
    )
    wrapped = _apply_option_explore_overlay_v1(
        base,
        name="c67_opening_compression_option_native_broad_etf_balance_dte35_v1",
        description=(
            "Balanced slower-DTE opening compression profile tuned for broader ETF baskets: "
            "lighter signal gating, both directions enabled, and less punitive ETF option "
            "entry-volume thresholds."
        ),
        option_min_dte=3,
        option_target_dte=4,
        option_max_dte=7,
    )
    return replace(
        wrapped,
        option_min_entry_volume=10,
        option_min_entry_price=0.50,
        option_min_quote_coverage_pct=0.25,
        option_min_chain_coverage_pct=0.25,
    )


def c67_opening_compression_option_native_broad_etf_dte35_candidates_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> List[OrbProfile]:
    return [
        c67_opening_compression_option_native_broad_etf_balance_dte35_v1(or_width_min=or_width_min),
    ]


def c68_opening_compression_option_native_sideways_broad_etf_balance_dte35_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> OrbProfile:
    return replace(
        c67_opening_compression_option_native_broad_etf_balance_dte35_v1(or_width_min=or_width_min),
        name="c68_opening_compression_option_native_sideways_broad_etf_balance_dte35_v1",
        description=(
            "Sideways-only slower-DTE opening compression variant for broad ETF baskets: "
            "tighter compression, shorter holds, and stricter option-entry quality than c67."
        ),
        take_profit_rr=1.10,
        break_even_trigger_rr=0.30,
        early_fail_minutes=10,
        max_hold_minutes=28,
        relative_volume_min=0.95,
        compression_max_range_pct=0.0028,
        compression_min_volume_multiple=1.10,
        option_min_dte=2,
        option_target_dte=3,
        option_max_dte=5,
        option_min_entry_volume=15,
        option_max_entry_bar_range_pct=0.04,
        option_min_entry_price=0.55,
        option_min_quote_coverage_pct=0.30,
        option_min_chain_coverage_pct=0.30,
        option_selection_max_quote_spread_pct=0.30,
        option_selection_max_spread_to_ask_ratio=0.85,
    )


def c68_opening_compression_option_native_sideways_broad_etf_dte35_candidates_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> List[OrbProfile]:
    return [
        c68_opening_compression_option_native_sideways_broad_etf_balance_dte35_v1(or_width_min=or_width_min),
    ]


def c69_opening_compression_option_native_broad_etf_quality_balance_dte35_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> OrbProfile:
    return replace(
        c67_opening_compression_option_native_broad_etf_balance_dte35_v1(or_width_min=or_width_min),
        name="c69_opening_compression_option_native_broad_etf_quality_balance_dte35_v1",
        description=(
            "Balanced broad-ETF opening compression variant with tighter option-entry quality "
            "and calmer trade management than c67, while still trading both trending and sideways regimes."
        ),
        take_profit_rr=1.15,
        break_even_trigger_rr=0.35,
        early_fail_minutes=10,
        max_hold_minutes=30,
        relative_volume_min=0.90,
        compression_max_range_pct=0.0030,
        compression_min_volume_multiple=1.05,
        option_min_dte=2,
        option_target_dte=3,
        option_max_dte=5,
        option_min_entry_volume=15,
        option_max_entry_bar_range_pct=0.08,
        option_min_entry_price=0.55,
        option_min_quote_coverage_pct=0.30,
        option_min_chain_coverage_pct=0.30,
        option_selection_max_quote_spread_pct=0.30,
        option_selection_max_spread_to_ask_ratio=0.85,
    )


def c69_opening_compression_option_native_broad_etf_quality_dte35_candidates_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> List[OrbProfile]:
    return [
        c69_opening_compression_option_native_broad_etf_quality_balance_dte35_v1(or_width_min=or_width_min),
    ]


def c70_opening_compression_option_native_broad_etf_calm_balance_dte35_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> OrbProfile:
    return replace(
        c69_opening_compression_option_native_broad_etf_quality_balance_dte35_v1(or_width_min=or_width_min),
        name="c70_opening_compression_option_native_broad_etf_calm_balance_dte35_v1",
        description=(
            "Balanced broad-ETF opening compression variant for calmer days: c69 option-entry "
            "quality plus restored vol-regime and prior-range filters."
        ),
        require_vol_regime_filter=True,
        vol_regime_min=10.0,
        vol_regime_max=28.0,
        require_prior_day_range_filter=True,
        prior_day_range_max_pct=0.024,
        relative_volume_min=0.92,
        compression_max_range_pct=0.0028,
        compression_min_volume_multiple=1.10,
        take_profit_rr=1.10,
        break_even_trigger_rr=0.30,
        early_fail_minutes=10,
        max_hold_minutes=28,
    )


def c70_opening_compression_option_native_broad_etf_calm_dte35_candidates_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> List[OrbProfile]:
    return [
        c70_opening_compression_option_native_broad_etf_calm_balance_dte35_v1(or_width_min=or_width_min),
    ]


def c71_opening_compression_option_native_broad_etf_moderate_balance_dte35_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> OrbProfile:
    return replace(
        c67_opening_compression_option_native_broad_etf_balance_dte35_v1(or_width_min=or_width_min),
        name="c71_opening_compression_option_native_broad_etf_moderate_balance_dte35_v1",
        description=(
            "Balanced broad-ETF opening compression variant that stays broader than c69 while "
            "tightening signal and option quality relative to c67."
        ),
        take_profit_rr=1.20,
        break_even_trigger_rr=0.35,
        early_fail_minutes=12,
        max_hold_minutes=32,
        relative_volume_min=0.88,
        compression_max_range_pct=0.0031,
        compression_min_volume_multiple=1.00,
        option_min_dte=3,
        option_target_dte=4,
        option_max_dte=7,
        option_min_entry_volume=12,
        option_max_entry_bar_range_pct=0.10,
        option_min_entry_price=0.50,
        option_min_quote_coverage_pct=0.28,
        option_min_chain_coverage_pct=0.28,
        option_selection_max_quote_spread_pct=0.32,
        option_selection_max_spread_to_ask_ratio=0.90,
    )


def c71_opening_compression_option_native_broad_etf_moderate_dte35_candidates_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> List[OrbProfile]:
    return [
        c71_opening_compression_option_native_broad_etf_moderate_balance_dte35_v1(or_width_min=or_width_min),
    ]


def c72_opening_compression_option_native_broad_etf_moderate_rangecap_balance_dte35_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> OrbProfile:
    return replace(
        c71_opening_compression_option_native_broad_etf_moderate_balance_dte35_v1(or_width_min=or_width_min),
        name="c72_opening_compression_option_native_broad_etf_moderate_rangecap_balance_dte35_v1",
        description=(
            "Balanced broad-ETF opening compression variant that trims the weaker mid-range entry-bar sleeve "
            "without collapsing the universal basket."
        ),
        take_profit_rr=1.15,
        break_even_trigger_rr=0.30,
        max_hold_minutes=30,
        compression_max_range_pct=0.0030,
        option_max_entry_bar_range_pct=0.06,
    )


def c72_opening_compression_option_native_broad_etf_moderate_rangecap_dte35_candidates_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> List[OrbProfile]:
    return [
        c72_opening_compression_option_native_broad_etf_moderate_rangecap_balance_dte35_v1(
            or_width_min=or_width_min
        ),
    ]


def c73_opening_compression_option_native_broad_etf_moderate_rvolcap_balance_dte35_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> OrbProfile:
    return replace(
        c71_opening_compression_option_native_broad_etf_moderate_balance_dte35_v1(or_width_min=or_width_min),
        name="c73_opening_compression_option_native_broad_etf_moderate_rvolcap_balance_dte35_v1",
        description=(
            "Balanced broad-ETF opening compression variant that caps higher relative-volume days while "
            "keeping the universal thesis and moderate option quality."
        ),
        relative_volume_max=1.60,
        compression_min_volume_multiple=1.05,
        option_max_entry_bar_range_pct=0.08,
    )


def c73_opening_compression_option_native_broad_etf_moderate_rvolcap_dte35_candidates_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> List[OrbProfile]:
    return [
        c73_opening_compression_option_native_broad_etf_moderate_rvolcap_balance_dte35_v1(
            or_width_min=or_width_min
        ),
    ]


def c74_opening_compression_option_native_broad_etf_moderate_rvolband_balance_dte35_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> OrbProfile:
    return replace(
        c71_opening_compression_option_native_broad_etf_moderate_balance_dte35_v1(or_width_min=or_width_min),
        name="c74_opening_compression_option_native_broad_etf_moderate_rvolband_balance_dte35_v1",
        description=(
            "Balanced broad-ETF opening compression variant that concentrates on the strongest low-to-mid "
            "relative-volume band while keeping trade count viable."
        ),
        relative_volume_min=0.95,
        relative_volume_max=1.35,
        compression_max_range_pct=0.0033,
        compression_min_volume_multiple=0.95,
        option_min_entry_volume=10,
        option_max_entry_bar_range_pct=0.08,
    )


def c74_opening_compression_option_native_broad_etf_moderate_rvolband_dte35_candidates_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> List[OrbProfile]:
    return [
        c74_opening_compression_option_native_broad_etf_moderate_rvolband_balance_dte35_v1(
            or_width_min=or_width_min
        ),
    ]


def c75_opening_compression_option_native_broad_etf_moderate_fastcarry_balance_dte35_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> OrbProfile:
    return replace(
        c71_opening_compression_option_native_broad_etf_moderate_balance_dte35_v1(or_width_min=or_width_min),
        name="c75_opening_compression_option_native_broad_etf_moderate_fastcarry_balance_dte35_v1",
        description=(
            "Balanced broad-ETF opening compression variant with faster carry realization and tighter entry "
            "quality, still evaluated as one universal profile."
        ),
        option_min_dte=2,
        option_target_dte=3,
        option_max_dte=5,
        take_profit_rr=1.10,
        break_even_trigger_rr=0.30,
        early_fail_minutes=10,
        max_hold_minutes=28,
        option_min_entry_volume=15,
        option_min_quote_coverage_pct=0.30,
        option_min_chain_coverage_pct=0.30,
        option_max_entry_bar_range_pct=0.06,
    )


def c75_opening_compression_option_native_broad_etf_moderate_fastcarry_dte35_candidates_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> List[OrbProfile]:
    return [
        c75_opening_compression_option_native_broad_etf_moderate_fastcarry_balance_dte35_v1(
            or_width_min=or_width_min
        ),
    ]


def c76_opening_compression_option_native_broad_etf_meta_rv_defensive_dte35_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> OrbProfile:
    return replace(
        c71_opening_compression_option_native_broad_etf_moderate_balance_dte35_v1(or_width_min=or_width_min),
        name="c76_opening_compression_option_native_broad_etf_meta_rv_defensive_dte35_v1",
        description=(
            "Broad-ETF universal shell that keeps the moderate c71 envelope but enables meta RV defensive "
            "routing to suppress the weak trend-call sleeve."
        ),
        regime_v2_enabled=True,
        regime_v2_router_enabled=True,
        regime_v2_router_mode="meta_rv_defensive_v1",
        regime_v2_min_confidence=0.35,
        regime_v2_router_high_rv_min=1.25,
    )


def c76_opening_compression_option_native_broad_etf_meta_rv_defensive_dte35_candidates_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> List[OrbProfile]:
    return [
        c76_opening_compression_option_native_broad_etf_meta_rv_defensive_dte35_v1(
            or_width_min=or_width_min
        ),
    ]


def c77_opening_compression_option_native_broad_etf_meta_rv_defensive_rangecap_dte35_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> OrbProfile:
    return replace(
        c72_opening_compression_option_native_broad_etf_moderate_rangecap_balance_dte35_v1(
            or_width_min=or_width_min
        ),
        name="c77_opening_compression_option_native_broad_etf_meta_rv_defensive_rangecap_dte35_v1",
        description=(
            "Broad-ETF universal shell that pairs the c72 range cap with meta RV defensive routing."
        ),
        regime_v2_enabled=True,
        regime_v2_router_enabled=True,
        regime_v2_router_mode="meta_rv_defensive_v1",
        regime_v2_min_confidence=0.35,
        regime_v2_router_high_rv_min=1.25,
    )


def c77_opening_compression_option_native_broad_etf_meta_rv_defensive_rangecap_dte35_candidates_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> List[OrbProfile]:
    return [
        c77_opening_compression_option_native_broad_etf_meta_rv_defensive_rangecap_dte35_v1(
            or_width_min=or_width_min
        ),
    ]


def c78_opening_compression_option_native_broad_etf_meta_rv_defensive_rvolcap_dte35_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> OrbProfile:
    return replace(
        c73_opening_compression_option_native_broad_etf_moderate_rvolcap_balance_dte35_v1(
            or_width_min=or_width_min
        ),
        name="c78_opening_compression_option_native_broad_etf_meta_rv_defensive_rvolcap_dte35_v1",
        description=(
            "Broad-ETF universal shell that pairs the c73 RV cap with meta RV defensive routing."
        ),
        regime_v2_enabled=True,
        regime_v2_router_enabled=True,
        regime_v2_router_mode="meta_rv_defensive_v1",
        regime_v2_min_confidence=0.35,
        regime_v2_router_high_rv_min=1.25,
    )


def c78_opening_compression_option_native_broad_etf_meta_rv_defensive_rvolcap_dte35_candidates_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> List[OrbProfile]:
    return [
        c78_opening_compression_option_native_broad_etf_meta_rv_defensive_rvolcap_dte35_v1(
            or_width_min=or_width_min
        ),
    ]


def c79_opening_compression_option_native_broad_etf_gapdown_eventdrive_dte35_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> OrbProfile:
    return replace(
        c71_opening_compression_option_native_broad_etf_moderate_balance_dte35_v1(or_width_min=or_width_min),
        name="c79_opening_compression_option_native_broad_etf_gapdown_eventdrive_dte35_v1",
        description=(
            "Broad-ETF universal shell that keeps the c71 envelope but routes gap-down event sessions into "
            "the existing event-drive sleeve."
        ),
        regime_v2_enabled=True,
        regime_v2_router_enabled=True,
        regime_v2_router_mode="core_gapdown_eventdrive_v1",
        regime_v2_min_confidence=0.35,
        regime_v2_router_high_rv_min=1.25,
    )


def c79_opening_compression_option_native_broad_etf_gapdown_eventdrive_dte35_candidates_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> List[OrbProfile]:
    return [
        c79_opening_compression_option_native_broad_etf_gapdown_eventdrive_dte35_v1(
            or_width_min=or_width_min
        ),
    ]


def c80_opening_compression_option_native_broad_etf_meta_trendfilter_balanced_dte35_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> OrbProfile:
    return replace(
        c71_opening_compression_option_native_broad_etf_moderate_balance_dte35_v1(or_width_min=or_width_min),
        name="c80_opening_compression_option_native_broad_etf_meta_trendfilter_balanced_dte35_v1",
        description=(
            "Broad-ETF universal shell that keeps the moderate c71 envelope but suppresses weak trend states "
            "using entry-range and relative-volume aware routing."
        ),
        regime_v2_enabled=True,
        regime_v2_router_enabled=True,
        regime_v2_router_mode="meta_trend_filter_balanced_v1",
        regime_v2_min_confidence=0.35,
        regime_v2_router_trend_up_rv_max=1.30,
        regime_v2_router_trend_down_rv_max=1.35,
        regime_v2_router_trend_up_entry_bar_range_min_pct=0.04,
        regime_v2_router_trend_down_entry_bar_range_min_pct=0.04,
    )


def c80_opening_compression_option_native_broad_etf_meta_trendfilter_balanced_dte35_candidates_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> List[OrbProfile]:
    return [
        c80_opening_compression_option_native_broad_etf_meta_trendfilter_balanced_dte35_v1(
            or_width_min=or_width_min
        ),
    ]


def c81_opening_compression_option_native_broad_etf_meta_trendfilter_strict_dte35_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> OrbProfile:
    return replace(
        c71_opening_compression_option_native_broad_etf_moderate_balance_dte35_v1(or_width_min=or_width_min),
        name="c81_opening_compression_option_native_broad_etf_meta_trendfilter_strict_dte35_v1",
        description=(
            "Broad-ETF universal shell that uses strict trend-up suppression while preserving the c71 "
            "downtrend, range, and event routing envelope."
        ),
        regime_v2_enabled=True,
        regime_v2_router_enabled=True,
        regime_v2_router_mode="meta_trend_filter_strict_v1",
        regime_v2_min_confidence=0.35,
        regime_v2_router_trend_up_rv_max=1.30,
        regime_v2_router_trend_down_rv_max=1.35,
        regime_v2_router_trend_up_entry_bar_range_min_pct=0.04,
        regime_v2_router_trend_down_entry_bar_range_min_pct=0.04,
    )


def c81_opening_compression_option_native_broad_etf_meta_trendfilter_strict_dte35_candidates_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> List[OrbProfile]:
    return [
        c81_opening_compression_option_native_broad_etf_meta_trendfilter_strict_dte35_v1(
            or_width_min=or_width_min
        ),
    ]


def c82_opening_compression_option_native_broad_etf_meta_trendfilter_rangecap_dte35_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> OrbProfile:
    return replace(
        c72_opening_compression_option_native_broad_etf_moderate_rangecap_balance_dte35_v1(
            or_width_min=or_width_min
        ),
        name="c82_opening_compression_option_native_broad_etf_meta_trendfilter_rangecap_dte35_v1",
        description=(
            "Broad-ETF universal shell that pairs the c72 entry-range cap with the balanced trend-filter "
            "router."
        ),
        regime_v2_enabled=True,
        regime_v2_router_enabled=True,
        regime_v2_router_mode="meta_trend_filter_balanced_v1",
        regime_v2_min_confidence=0.35,
        regime_v2_router_trend_up_rv_max=1.30,
        regime_v2_router_trend_down_rv_max=1.35,
        regime_v2_router_trend_up_entry_bar_range_min_pct=0.04,
        regime_v2_router_trend_down_entry_bar_range_min_pct=0.04,
    )


def c82_opening_compression_option_native_broad_etf_meta_trendfilter_rangecap_dte35_candidates_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> List[OrbProfile]:
    return [
        c82_opening_compression_option_native_broad_etf_meta_trendfilter_rangecap_dte35_v1(
            or_width_min=or_width_min
        ),
    ]


def c83_opening_compression_option_native_broad_etf_meta_trendpullback_fallback_dte35_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> OrbProfile:
    return replace(
        c71_opening_compression_option_native_broad_etf_moderate_balance_dte35_v1(or_width_min=or_width_min),
        name="c83_opening_compression_option_native_broad_etf_meta_trendpullback_fallback_dte35_v1",
        description=(
            "Broad-ETF universal shell that preserves the c71 base envelope and only overrides flagged "
            "trend sleeves to long-only trend pullback while falling back to the base shell elsewhere."
        ),
        regime_v2_enabled=True,
        regime_v2_router_enabled=True,
        regime_v2_router_mode="meta_trend_pullback_fallback_v1",
        regime_v2_min_confidence=0.35,
        regime_v2_router_trend_up_rv_max=1.30,
        regime_v2_router_trend_down_rv_max=1.35,
        regime_v2_router_trend_up_entry_bar_range_min_pct=0.04,
        regime_v2_router_trend_down_entry_bar_range_min_pct=0.04,
    )


def c83_opening_compression_option_native_broad_etf_meta_trendpullback_fallback_dte35_candidates_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> List[OrbProfile]:
    return [
        c83_opening_compression_option_native_broad_etf_meta_trendpullback_fallback_dte35_v1(
            or_width_min=or_width_min
        ),
    ]


def c84_opening_compression_option_native_broad_etf_meta_trendmr_fallback_dte35_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> OrbProfile:
    return replace(
        c71_opening_compression_option_native_broad_etf_moderate_balance_dte35_v1(or_width_min=or_width_min),
        name="c84_opening_compression_option_native_broad_etf_meta_trendmr_fallback_dte35_v1",
        description=(
            "Broad-ETF universal shell that preserves the c71 base envelope and only overrides flagged "
            "trend-up sleeves to mean reversion while falling back to the base shell elsewhere."
        ),
        regime_v2_enabled=True,
        regime_v2_router_enabled=True,
        regime_v2_router_mode="meta_trend_mr_fallback_v1",
        regime_v2_min_confidence=0.35,
        regime_v2_router_trend_up_rv_max=1.30,
        regime_v2_router_trend_down_rv_max=1.35,
        regime_v2_router_trend_up_entry_bar_range_min_pct=0.04,
        regime_v2_router_trend_down_entry_bar_range_min_pct=0.04,
    )


def c84_opening_compression_option_native_broad_etf_meta_trendmr_fallback_dte35_candidates_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> List[OrbProfile]:
    return [
        c84_opening_compression_option_native_broad_etf_meta_trendmr_fallback_dte35_v1(
            or_width_min=or_width_min
        ),
    ]


def c85_opening_compression_option_native_broad_etf_meta_trendpullback_rangecap_dte35_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> OrbProfile:
    return replace(
        c72_opening_compression_option_native_broad_etf_moderate_rangecap_balance_dte35_v1(
            or_width_min=or_width_min
        ),
        name="c85_opening_compression_option_native_broad_etf_meta_trendpullback_rangecap_dte35_v1",
        description=(
            "Broad-ETF universal shell that pairs the c72 range cap with the trade-preserving "
            "trend-pullback fallback router."
        ),
        regime_v2_enabled=True,
        regime_v2_router_enabled=True,
        regime_v2_router_mode="meta_trend_pullback_fallback_v1",
        regime_v2_min_confidence=0.35,
        regime_v2_router_trend_up_rv_max=1.30,
        regime_v2_router_trend_down_rv_max=1.35,
        regime_v2_router_trend_up_entry_bar_range_min_pct=0.04,
        regime_v2_router_trend_down_entry_bar_range_min_pct=0.04,
    )


def c85_opening_compression_option_native_broad_etf_meta_trendpullback_rangecap_dte35_candidates_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> List[OrbProfile]:
    return [
        c85_opening_compression_option_native_broad_etf_meta_trendpullback_rangecap_dte35_v1(
            or_width_min=or_width_min
        ),
    ]


def c86_opening_compression_option_native_broad_etf_meta_trendmr_fulltrend_fallback_dte35_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> OrbProfile:
    return replace(
        c71_opening_compression_option_native_broad_etf_moderate_balance_dte35_v1(or_width_min=or_width_min),
        name="c86_opening_compression_option_native_broad_etf_meta_trendmr_fulltrend_fallback_dte35_v1",
        description=(
            "Broad-ETF universal shell that keeps the c84 envelope but always overrides trend-up days to "
            "mean reversion while preserving fallback behavior elsewhere."
        ),
        regime_v2_enabled=True,
        regime_v2_router_enabled=True,
        regime_v2_router_mode="meta_trendmr_fulltrend_fallback_v1",
        regime_v2_min_confidence=0.35,
        regime_v2_router_trend_up_rv_max=1.30,
        regime_v2_router_trend_down_rv_max=1.35,
        regime_v2_router_trend_up_entry_bar_range_min_pct=0.04,
        regime_v2_router_trend_down_entry_bar_range_min_pct=0.04,
        regime_v2_router_low_confidence_mr_rv_max=1.15,
        regime_v2_router_low_confidence_mr_entry_bar_range_max_pct=0.03,
        regime_v2_router_low_confidence_skip_rv_min=1.60,
        regime_v2_router_low_confidence_skip_entry_bar_range_min_pct=0.06,
    )


def c86_opening_compression_option_native_broad_etf_meta_trendmr_fulltrend_fallback_dte35_candidates_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> List[OrbProfile]:
    return [
        c86_opening_compression_option_native_broad_etf_meta_trendmr_fulltrend_fallback_dte35_v1(
            or_width_min=or_width_min
        ),
    ]


def c87_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_dte35_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> OrbProfile:
    return replace(
        c71_opening_compression_option_native_broad_etf_moderate_balance_dte35_v1(or_width_min=or_width_min),
        name="c87_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_dte35_v1",
        description=(
            "Broad-ETF universal shell that keeps the c84 envelope, always routes trend-up to mean "
            "reversion, and guards high-risk low-confidence days."
        ),
        regime_v2_enabled=True,
        regime_v2_router_enabled=True,
        regime_v2_router_mode="meta_trendmr_lowconf_guard_v1",
        regime_v2_min_confidence=0.35,
        regime_v2_router_trend_up_rv_max=1.30,
        regime_v2_router_trend_down_rv_max=1.35,
        regime_v2_router_trend_up_entry_bar_range_min_pct=0.04,
        regime_v2_router_trend_down_entry_bar_range_min_pct=0.04,
        regime_v2_router_low_confidence_mr_rv_max=1.15,
        regime_v2_router_low_confidence_mr_entry_bar_range_max_pct=0.03,
        regime_v2_router_low_confidence_skip_rv_min=1.60,
        regime_v2_router_low_confidence_skip_entry_bar_range_min_pct=0.06,
    )


def c87_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_dte35_candidates_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> List[OrbProfile]:
    return [
        c87_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_dte35_v1(
            or_width_min=or_width_min
        ),
    ]


def c88_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_rangecap_dte35_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> OrbProfile:
    return replace(
        c72_opening_compression_option_native_broad_etf_moderate_rangecap_balance_dte35_v1(
            or_width_min=or_width_min
        ),
        name="c88_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_rangecap_dte35_v1",
        description=(
            "Broad-ETF universal shell that pairs the c72 range cap with the low-confidence guard "
            "mean-reversion router."
        ),
        regime_v2_enabled=True,
        regime_v2_router_enabled=True,
        regime_v2_router_mode="meta_trendmr_lowconf_guard_v1",
        regime_v2_min_confidence=0.35,
        regime_v2_router_trend_up_rv_max=1.30,
        regime_v2_router_trend_down_rv_max=1.35,
        regime_v2_router_trend_up_entry_bar_range_min_pct=0.04,
        regime_v2_router_trend_down_entry_bar_range_min_pct=0.04,
        regime_v2_router_low_confidence_mr_rv_max=1.15,
        regime_v2_router_low_confidence_mr_entry_bar_range_max_pct=0.03,
        regime_v2_router_low_confidence_skip_rv_min=1.60,
        regime_v2_router_low_confidence_skip_entry_bar_range_min_pct=0.06,
    )


def c88_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_rangecap_dte35_candidates_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> List[OrbProfile]:
    return [
        c88_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_rangecap_dte35_v1(
            or_width_min=or_width_min
        ),
    ]


def c89_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_dte35_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> OrbProfile:
    return replace(
        c87_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_dte35_v1(
            or_width_min=or_width_min
        ),
        name="c89_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_dte35_v1",
        description=(
            "c87 broad-ETF shell with a route-scoped trend-up range cap overlay to deconcentrate "
            "the residual trend-up sleeve without applying c72 globally."
        ),
        regime_v2_router_mode="meta_trendmr_lowconf_guard_trendcap_v1",
        regime_v2_router_trend_up_overlay_compression_max_range_pct=0.0030,
        regime_v2_router_trend_up_overlay_option_max_entry_bar_range_pct=0.06,
    )


def c89_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_dte35_candidates_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> List[OrbProfile]:
    return [
        c89_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_dte35_v1(
            or_width_min=or_width_min
        ),
    ]


def c90_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_eventgap_dte35_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> OrbProfile:
    return replace(
        c87_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_dte35_v1(
            or_width_min=or_width_min
        ),
        name="c90_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_eventgap_dte35_v1",
        description=(
            "c87 broad-ETF shell with a targeted event-gap loser filter that keeps the positive "
            "event-gap sleeve intact while skipping the narrow mid-RV gap bucket."
        ),
        regime_v2_router_mode="meta_trendmr_lowconf_guard_eventgap_v1",
        regime_v2_router_event_gap_tight_entry_bar_range_max_pct=0.01,
        regime_v2_router_event_gap_mid_rv_min=1.0,
        regime_v2_router_event_gap_mid_rv_max=2.0,
        regime_v2_router_event_gap_mid_entry_bar_range_max_pct=0.025,
    )


def c90_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_eventgap_dte35_candidates_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> List[OrbProfile]:
    return [
        c90_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_eventgap_dte35_v1(
            or_width_min=or_width_min
        ),
    ]


def c91_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_eventgap_dte35_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> OrbProfile:
    return replace(
        c87_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_dte35_v1(
            or_width_min=or_width_min
        ),
        name="c91_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_eventgap_dte35_v1",
        description=(
            "c87 broad-ETF shell that combines the route-scoped trend-up range cap overlay with "
            "the targeted event-gap loser filter."
        ),
        regime_v2_router_mode="meta_trendmr_lowconf_guard_trendcap_eventgap_v1",
        regime_v2_router_trend_up_overlay_compression_max_range_pct=0.0030,
        regime_v2_router_trend_up_overlay_option_max_entry_bar_range_pct=0.06,
        regime_v2_router_event_gap_tight_entry_bar_range_max_pct=0.01,
        regime_v2_router_event_gap_mid_rv_min=1.0,
        regime_v2_router_event_gap_mid_rv_max=2.0,
        regime_v2_router_event_gap_mid_entry_bar_range_max_pct=0.025,
    )


def c91_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_eventgap_dte35_candidates_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> List[OrbProfile]:
    return [
        c91_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_eventgap_dte35_v1(
            or_width_min=or_width_min
        ),
    ]


def c92_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_eventgapsoft_dte35_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> OrbProfile:
    return replace(
        c87_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_dte35_v1(
            or_width_min=or_width_min
        ),
        name="c92_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_eventgapsoft_dte35_v1",
        description=(
            "c87 broad-ETF shell with the route-scoped trend-up MR rangecap overlay plus a softer "
            "event-gap overlay that only skips the tightest event-gap bucket."
        ),
        regime_v2_router_mode="meta_trendmr_lowconf_guard_trendcap_eventgap_soft_v1",
        regime_v2_router_trend_up_overlay_compression_max_range_pct=0.0030,
        regime_v2_router_trend_up_overlay_option_max_entry_bar_range_pct=0.06,
        regime_v2_router_event_gap_tight_entry_bar_range_max_pct=0.01,
        regime_v2_router_event_gap_overlay_compression_max_range_pct=0.0030,
        regime_v2_router_event_gap_overlay_option_max_entry_bar_range_pct=0.06,
    )


def c92_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_eventgapsoft_dte35_candidates_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> List[OrbProfile]:
    return [
        c92_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_eventgapsoft_dte35_v1(
            or_width_min=or_width_min
        ),
    ]


def c93_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_eventgapsoft_rangelow_dte35_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> OrbProfile:
    return replace(
        c92_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_eventgapsoft_dte35_v1(
            or_width_min=or_width_min
        ),
        name="c93_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_eventgapsoft_rangelow_dte35_v1",
        description=(
            "c92 broad-ETF shell plus a tight low-RV range-low-vol skip that trims the weakest "
            "micro-range subset without suppressing the broader positive sleeve."
        ),
        regime_v2_router_mode="meta_trendmr_lowconf_guard_trendcap_eventgap_soft_rangelow_v1",
        regime_v2_router_range_low_vol_tight_rv_max=0.95,
        regime_v2_router_range_low_vol_tight_entry_bar_range_max_pct=0.005,
    )


def c93_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_eventgapsoft_rangelow_dte35_candidates_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> List[OrbProfile]:
    return [
        c93_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_eventgapsoft_rangelow_dte35_v1(
            or_width_min=or_width_min
        ),
    ]


def c94_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_eventgapsoft_rangelow_transition_dte35_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> OrbProfile:
    return replace(
        c93_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_eventgapsoft_rangelow_dte35_v1(
            or_width_min=or_width_min
        ),
        name="c94_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_eventgapsoft_rangelow_transition_dte35_v1",
        description=(
            "c93 broad-ETF shell plus an extreme high-RV wide-range transition skip to trim the "
            "remaining transition tail without muting normal transition days."
        ),
        regime_v2_router_mode="meta_trendmr_lowconf_guard_trendcap_eventgap_soft_rangelow_transition_v1",
        regime_v2_router_transition_high_rv_min=2.0,
        regime_v2_router_transition_wide_entry_bar_range_min_pct=0.05,
    )


def c94_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_eventgapsoft_rangelow_transition_dte35_candidates_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> List[OrbProfile]:
    return [
        c94_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_eventgapsoft_rangelow_transition_dte35_v1(
            or_width_min=or_width_min
        ),
    ]


def get_orb_profile(name: str, or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    normalized = str(name or "").strip().lower()
    if normalized in {"c40_daily_ewmac_fast_v1", "c40_ewmac_fast", "carver_ewmac_fast"}:
        return c40_daily_ewmac_fast_v1(or_width_min=or_width_min)
    if normalized in {"c41_daily_ewmac_slow_v1", "c41_ewmac_slow", "carver_ewmac_slow"}:
        return c41_daily_ewmac_slow_v1(or_width_min=or_width_min)
    if normalized in {"c42_daily_breakout_medium_v1", "c42_breakout_medium", "carver_breakout_medium"}:
        return c42_daily_breakout_medium_v1(or_width_min=or_width_min)
    if normalized in {"c43_daily_breakout_slow_v1", "c43_breakout_slow", "carver_breakout_slow"}:
        return c43_daily_breakout_slow_v1(or_width_min=or_width_min)
    if normalized in {"c52_daily_trend_pullback_v1", "c52_trend_pullback", "carver_trend_pullback"}:
        return c52_daily_trend_pullback_v1(or_width_min=or_width_min)
    if normalized in {"c44_daily_relmom_bucket_v1", "c44_relmom_bucket", "carver_relmom_bucket"}:
        return c44_daily_relmom_bucket_v1(or_width_min=or_width_min)
    if normalized in {"c45_daily_assettrend_bucket_v1", "c45_assettrend_bucket", "carver_assettrend_bucket"}:
        return c45_daily_assettrend_bucket_v1(or_width_min=or_width_min)
    if normalized in {"c46_surface_ivrv_overlay_v1", "c46_ivrv_overlay"}:
        return c46_surface_ivrv_overlay_v1(or_width_min=or_width_min)
    if normalized in {"c47_surface_term_structure_overlay_v1", "c47_term_structure_overlay"}:
        return c47_surface_term_structure_overlay_v1(or_width_min=or_width_min)
    if normalized in {"c48_surface_skew_overlay_v1", "c48_skew_overlay"}:
        return c48_surface_skew_overlay_v1(or_width_min=or_width_min)
    if normalized in {"c50_carver_core_combo_v1", "c50_carver_core_combo", "carver_core_combo"}:
        return c50_carver_core_combo_v1(or_width_min=or_width_min)
    if normalized in {"c51_carver_hybrid_portfolio_v1", "c51_carver_hybrid_portfolio", "carver_hybrid"}:
        return c51_carver_hybrid_portfolio_v1(or_width_min=or_width_min)
    if normalized in {"c4", "c4_long_only_rr15"}:
        return c4_long_only_rr15(or_width_min=or_width_min)
    if normalized in {"c4_rr15_r1", "rr15_r1"}:
        return c4_rr15_r1(or_width_min=or_width_min)
    if normalized in {"c4_long_only_rr15_recovery_v2", "rr15_recovery_v2", "rr15_recovery"}:
        return c4_long_only_rr15_recovery_v2(or_width_min=or_width_min)
    if normalized in {
        "c4_long_only_rr15_option_native_v1",
        "rr15_option_native_v1",
        "c4_option_native",
    }:
        return c4_long_only_rr15_option_native_v1(or_width_min=or_width_min)
    if normalized in {
        "c4_long_only_rr15_option_native_v2",
        "rr15_option_native_v2",
        "c4_option_native_v2",
    }:
        return c4_long_only_rr15_option_native_v2(or_width_min=or_width_min)
    if normalized in {
        "c4_long_only_rr15_option_native_quality_v1",
        "rr15_option_native_quality_v1",
        "c4_option_native_quality",
    }:
        return c4_long_only_rr15_option_native_quality_v1(or_width_min=or_width_min)
    if normalized in {
        "c4_long_only_rr15_option_native_quality_v2",
        "rr15_option_native_quality_v2",
        "c4_option_native_quality_v2",
    }:
        return c4_long_only_rr15_option_native_quality_v2(or_width_min=or_width_min)
    if normalized in {
        "c4_long_only_rr15_openany_option_native_v1",
        "rr15_openany_option_native_v1",
        "c4_openany_option_native",
    }:
        return c4_long_only_rr15_openany_option_native_v1(or_width_min=or_width_min)
    if normalized in {
        "c4_long_only_rr15_openany_option_native_v2",
        "rr15_openany_option_native_v2",
        "c4_openany_option_native_v2",
    }:
        return c4_long_only_rr15_openany_option_native_v2(or_width_min=or_width_min)
    if normalized in {
        "c4_long_only_rr15_put_credit_v1",
        "rr15_put_credit_v1",
        "c4_put_credit_v1",
    }:
        return c4_long_only_rr15_put_credit_v1(or_width_min=or_width_min)
    if normalized in {
        "c4_long_only_rr15_put_credit_quality_v1",
        "rr15_put_credit_quality_v1",
        "c4_put_credit_quality_v1",
    }:
        return c4_long_only_rr15_put_credit_quality_v1(or_width_min=or_width_min)
    if normalized in {
        "c4_long_only_rr15_openany_put_credit_v1",
        "rr15_openany_put_credit_v1",
        "c4_openany_put_credit_v1",
    }:
        return c4_long_only_rr15_openany_put_credit_v1(or_width_min=or_width_min)
    if normalized in {"c4_long_only_rr15_defensive_v1", "c4_defensive", "rr15_defensive"}:
        return c4_long_only_rr15_defensive_v1(or_width_min=or_width_min)
    if normalized in {
        "c4_long_only_rr15_openany_tight_v1",
        "c4_rr15_openany_tight",
        "rr15_openany_tight",
    }:
        return c4_long_only_rr15_openany_tight_v1(or_width_min=or_width_min)
    if normalized in {"c4_long_only_rr15_pocket_v1", "rr15_pocket_v1"}:
        return c4_long_only_rr15_pocket_v1(or_width_min=or_width_min)
    if normalized in {"c4_long_only_rr15_pocket_v2", "rr15_pocket_v2"}:
        return c4_long_only_rr15_pocket_v2(or_width_min=or_width_min)
    if normalized in {"c4_long_only_rr15_openany_pocket_v1", "rr15_openany_pocket_v1"}:
        return c4_long_only_rr15_openany_pocket_v1(or_width_min=or_width_min)
    if normalized in {"c4_long_slip10_v1", "c4_slip10", "slip10"}:
        return c4_long_slip10_v1(or_width_min=or_width_min)
    if normalized in {"c4_long_slip10_strict_v1", "c4_slip10_strict", "slip10_strict"}:
        return c4_long_slip10_strict_v1(or_width_min=or_width_min)
    if normalized in {"c4_orw30_rvol12_noopp_rr20", "orw30_rvol12_noopp_rr20", "rr20_orw30_rvol12"}:
        return c4_orw30_rvol12_noopp_rr20(or_width_min=or_width_min)
    if normalized in {
        "c4_orw30_rvol12_noopp_rr20_openany",
        "orw30_rvol12_noopp_rr20_openany",
        "rr20_orw30_rvol12_openany",
    }:
        return c4_orw30_rvol12_noopp_rr20_openany(or_width_min=or_width_min)
    if normalized in {"c4_orw25_rvol12_noopp_rr20", "orw25_rvol12_noopp_rr20", "rr20_orw25_rvol12"}:
        return c4_orw25_rvol12_noopp_rr20(or_width_min=or_width_min)
    if normalized in {
        "c4_orw25_rvol12_noopp_rr20_openany",
        "orw25_rvol12_noopp_rr20_openany",
        "rr20_orw25_rvol12_openany",
    }:
        return c4_orw25_rvol12_noopp_rr20_openany(or_width_min=or_width_min)
    if normalized in {
        "c4_orw25_rvol12_noopp_rr20_stop_touch_openany",
        "orw25_rvol12_noopp_rr20_stop_touch_openany",
        "rr20_orw25_rvol12_stop_touch_openany",
    }:
        return c4_orw25_rvol12_noopp_rr20_stop_touch_openany(or_width_min=or_width_min)
    if normalized in {
        "c4_orw25_rvol12_noopp_rr20_stop_touch_realism",
        "orw25_rvol12_noopp_rr20_stop_touch_realism",
        "rr20_orw25_rvol12_stop_touch_realism",
    }:
        return c4_orw25_rvol12_noopp_rr20_stop_touch_realism(or_width_min=or_width_min)
    if normalized in {
        "c4_orw25_rvol12_noopp_rr20_ls_openany",
        "orw25_rvol12_noopp_rr20_ls_openany",
        "rr20_orw25_rvol12_ls_openany",
    }:
        return c4_orw25_rvol12_noopp_rr20_ls_openany(or_width_min=or_width_min)
    if normalized in {"c4_freq_v1", "c4_freq", "freq"}:
        return c4_freq_v1()
    if normalized in {"c4_freq_v1_f4", "c4_freq_f4", "freq_f4"}:
        return c4_freq_v1_f4()
    if normalized in {"c4_freq_breakout_hybrid_v1", "freq_breakout_hybrid_v1"}:
        return c4_freq_breakout_hybrid_v1()
    if normalized in {"c4_freq_breakout_hybrid_v2", "freq_breakout_hybrid_v2"}:
        return c4_freq_breakout_hybrid_v2()
    if normalized in {"c4_long_only_rr15_quote_guard_v1", "long_only_rr15_quote_guard_v1"}:
        return c4_long_only_rr15_quote_guard_v1(or_width_min=or_width_min)
    if normalized in {"c4_freq_breakout_quote_guard_v1", "freq_breakout_quote_guard_v1"}:
        return c4_freq_breakout_quote_guard_v1()
    if normalized in {"c4_freq_ls_v1", "c4_freq_long_short", "freq_ls"}:
        return c4_freq_ls_v1()
    if normalized in {"c4_freq_ls_trend_v1", "c4_freq_long_short_trend", "freq_ls_trend"}:
        return c4_freq_ls_trend_v1()
    if normalized in {"c4_orb_trend_short_v1", "orb_trend_short_v1", "trend_short"}:
        return c4_orb_trend_short_v1(or_width_min=or_width_min)
    if normalized in {"c4_orb_failure_fade_v1", "orb_failure_fade_v1", "failure_fade"}:
        return c4_orb_failure_fade_v1(or_width_min=or_width_min)
    if normalized in {"c4_orb_momentum_v1", "orb_momentum_v1", "momentum"}:
        return c4_orb_momentum_v1(or_width_min=or_width_min)
    if normalized in {"c4_momentum_accel_v1", "momentum_accel", "orb_momentum_accel_v1"}:
        return c4_momentum_accel_v1(or_width_min=or_width_min)
    if normalized in {"c4_momentum_accel_relaxed_v2", "momentum_accel_relaxed_v2"}:
        return c4_momentum_accel_relaxed_v2(or_width_min=or_width_min)
    if normalized in {"c4_momentum_adx_confirm_v1", "momentum_adx_confirm_v1"}:
        return c4_momentum_adx_confirm_v1(or_width_min=or_width_min)
    if normalized in {"c4_momentum_break_retest_v1", "momentum_break_retest_v1"}:
        return c4_momentum_break_retest_v1(or_width_min=or_width_min)
    if normalized in {"c4_momentum_gap_go_v1", "momentum_gap_go_v1"}:
        return c4_momentum_gap_go_v1(or_width_min=or_width_min)
    if normalized in {"c4_momentum_quality_v2", "momentum_quality_v2"}:
        return c4_momentum_quality_v2(or_width_min=or_width_min)
    if normalized in {"c4_momentum_loose", "momentum_loose"}:
        return c4_momentum_loose(or_width_min=or_width_min)
    if normalized in {"c4_momentum_loose_no_spike_v1", "momentum_loose_no_spike_v1"}:
        return c4_momentum_loose_no_spike_v1(or_width_min=or_width_min)
    if normalized in {"c4_momentum_loose_no_trend_v1", "momentum_loose_no_trend_v1"}:
        return c4_momentum_loose_no_trend_v1(or_width_min=or_width_min)
    if normalized in {"c4_momentum_loose_relaxed_v3", "momentum_loose_relaxed_v3"}:
        return c4_momentum_loose_relaxed_v3(or_width_min=or_width_min)
    if normalized in {"c4_momentum_loose_cost_guard_v1", "momentum_loose_cost_guard_v1"}:
        return c4_momentum_loose_cost_guard_v1(or_width_min=or_width_min)
    if normalized in {"c4_momentum_pullback_fast_v1", "momentum_pullback_fast", "orb_pullback_fast_v1"}:
        return c4_momentum_pullback_fast_v1(or_width_min=or_width_min)
    if normalized in {"c4_momentum_pullback_guard_v2", "momentum_pullback_guard_v2"}:
        return c4_momentum_pullback_guard_v2(or_width_min=or_width_min)
    if normalized in {"c4_momentum_vwap_reclaim_v1", "momentum_vwap_reclaim_v1"}:
        return c4_momentum_vwap_reclaim_v1(or_width_min=or_width_min)
    if normalized in {"c4_momentum_vwap_reclaim_recovery_v2", "momentum_vwap_reclaim_recovery_v2"}:
        return c4_momentum_vwap_reclaim_recovery_v2(or_width_min=or_width_min)
    if normalized in {"c4_orb_momentum_short_hold", "orb_momentum_short_hold", "momentum_short_hold"}:
        return c4_orb_momentum_short_hold(or_width_min=or_width_min)
    if normalized in {"c4_orb_trend_pullback_v1", "orb_trend_pullback_v1", "trend_pullback"}:
        return c4_orb_trend_pullback_v1(or_width_min=or_width_min)
    if normalized in {"c5_opening_drive_pullback_v1", "opening_drive_pullback_v1", "drive_pullback_v1"}:
        return c5_opening_drive_pullback_v1(or_width_min=or_width_min)
    if normalized in {"c5_opening_drive_pullback_guard_v1", "opening_drive_pullback_guard_v1", "drive_pullback_guard_v1"}:
        return c5_opening_drive_pullback_guard_v1(or_width_min=or_width_min)
    if normalized in {"c5_opening_drive_pullback_relaxed_v1", "opening_drive_pullback_relaxed_v1", "drive_pullback_relaxed_v1"}:
        return c5_opening_drive_pullback_relaxed_v1(or_width_min=or_width_min)
    if normalized in {"c5_opening_drive_pullback_long_only_v1", "opening_drive_pullback_long_only_v1", "drive_pullback_long_only_v1"}:
        return c5_opening_drive_pullback_long_only_v1(or_width_min=or_width_min)
    if normalized in {"c5_opening_drive_pullback_reclaim_v2", "opening_drive_pullback_reclaim_v2", "drive_pullback_reclaim_v2"}:
        return c5_opening_drive_pullback_reclaim_v2(or_width_min=or_width_min)
    if normalized in {"c5_opening_drive_pullback_quality_v2", "opening_drive_pullback_quality_v2", "drive_pullback_quality_v2"}:
        return c5_opening_drive_pullback_quality_v2(or_width_min=or_width_min)
    if normalized in {"c5_opening_drive_pullback_long_only_v2", "opening_drive_pullback_long_only_v2", "drive_pullback_long_only_v2"}:
        return c5_opening_drive_pullback_long_only_v2(or_width_min=or_width_min)
    if normalized in {"c5_opening_drive_pullback_prev_break_v3", "opening_drive_pullback_prev_break_v3", "drive_pullback_prev_break_v3"}:
        return c5_opening_drive_pullback_prev_break_v3(or_width_min=or_width_min)
    if normalized in {"c5_opening_drive_pullback_hold_open_v3", "opening_drive_pullback_hold_open_v3", "drive_pullback_hold_open_v3"}:
        return c5_opening_drive_pullback_hold_open_v3(or_width_min=or_width_min)
    if normalized in {"c5_opening_drive_pullback_long_only_balance_v4", "opening_drive_pullback_long_only_balance_v4", "drive_pullback_long_only_balance_v4"}:
        return c5_opening_drive_pullback_long_only_balance_v4(or_width_min=or_width_min)
    if normalized in {"c5_opening_drive_pullback_long_only_fast_v4", "opening_drive_pullback_long_only_fast_v4", "drive_pullback_long_only_fast_v4"}:
        return c5_opening_drive_pullback_long_only_fast_v4(or_width_min=or_width_min)
    if normalized in {"c5_opening_drive_pullback_long_only_regime_v5", "opening_drive_pullback_long_only_regime_v5", "drive_pullback_long_only_regime_v5"}:
        return c5_opening_drive_pullback_long_only_regime_v5(or_width_min=or_width_min)
    if normalized in {"c6_opening_exhaustion_reversal_v1", "opening_exhaustion_reversal_v1", "opening_reversal_v1"}:
        return c6_opening_exhaustion_reversal_v1(or_width_min=or_width_min)
    if normalized in {"c6_opening_exhaustion_reversal_quality_v1", "opening_exhaustion_reversal_quality_v1", "opening_reversal_quality_v1"}:
        return c6_opening_exhaustion_reversal_quality_v1(or_width_min=or_width_min)
    if normalized in {"c6_opening_exhaustion_reversal_regime_v1", "opening_exhaustion_reversal_regime_v1", "opening_reversal_regime_v1"}:
        return c6_opening_exhaustion_reversal_regime_v1(or_width_min=or_width_min)
    if normalized in {"c6_opening_exhaustion_reversal_long_only_v1", "opening_exhaustion_reversal_long_only_v1", "opening_reversal_long_only_v1"}:
        return c6_opening_exhaustion_reversal_long_only_v1(or_width_min=or_width_min)
    if normalized in {"c6_opening_exhaustion_reversal_short_only_v1", "opening_exhaustion_reversal_short_only_v1", "opening_reversal_short_only_v1"}:
        return c6_opening_exhaustion_reversal_short_only_v1(or_width_min=or_width_min)
    if normalized in {"c6_opening_exhaustion_reversal_balance_v2", "opening_exhaustion_reversal_balance_v2", "opening_reversal_balance_v2"}:
        return c6_opening_exhaustion_reversal_balance_v2(or_width_min=or_width_min)
    if normalized in {"c6_opening_exhaustion_reversal_regime_v2", "opening_exhaustion_reversal_regime_v2", "opening_reversal_regime_v2"}:
        return c6_opening_exhaustion_reversal_regime_v2(or_width_min=or_width_min)
    if normalized in {"c6_opening_exhaustion_reversal_long_only_v2", "opening_exhaustion_reversal_long_only_v2", "opening_reversal_long_only_v2"}:
        return c6_opening_exhaustion_reversal_long_only_v2(or_width_min=or_width_min)
    if normalized in {"c6_opening_exhaustion_reversal_short_only_v2", "opening_exhaustion_reversal_short_only_v2", "opening_reversal_short_only_v2"}:
        return c6_opening_exhaustion_reversal_short_only_v2(or_width_min=or_width_min)
    if normalized in {"c16_opening_exhaustion_balance_v3", "opening_exhaustion_balance_v3", "c16_balance", "opening_exhaustion_balance"}:
        return c16_opening_exhaustion_balance_v3(or_width_min=or_width_min)
    if normalized in {"c16_opening_exhaustion_quality_v3", "opening_exhaustion_quality_v3", "c16_quality", "opening_exhaustion_quality"}:
        return c16_opening_exhaustion_quality_v3(or_width_min=or_width_min)
    if normalized in {"c16_opening_exhaustion_regime_v3", "opening_exhaustion_regime_v3", "c16_regime", "opening_exhaustion_regime"}:
        return c16_opening_exhaustion_regime_v3(or_width_min=or_width_min)
    if normalized in {"c16_opening_exhaustion_long_only_v3", "opening_exhaustion_long_only_v3", "c16_long_only", "opening_exhaustion_long_only"}:
        return c16_opening_exhaustion_long_only_v3(or_width_min=or_width_min)
    if normalized in {"c16_opening_exhaustion_short_only_v3", "opening_exhaustion_short_only_v3", "c16_short_only", "opening_exhaustion_short_only"}:
        return c16_opening_exhaustion_short_only_v3(or_width_min=or_width_min)
    if normalized in {"c17_option_structure_strength_balance_v1", "option_structure_strength_balance_v1", "c17_balance", "option_structure_strength_balance"}:
        return c17_option_structure_strength_balance_v1(or_width_min=or_width_min)
    if normalized in {"c17_option_structure_strength_quality_v1", "option_structure_strength_quality_v1", "c17_quality", "option_structure_strength_quality"}:
        return c17_option_structure_strength_quality_v1(or_width_min=or_width_min)
    if normalized in {"c17_option_structure_strength_regime_v1", "option_structure_strength_regime_v1", "c17_regime", "option_structure_strength_regime"}:
        return c17_option_structure_strength_regime_v1(or_width_min=or_width_min)
    if normalized in {"c17_option_structure_strength_opportunity_v1", "option_structure_strength_opportunity_v1", "c17_opportunity", "option_structure_strength_opportunity"}:
        return c17_option_structure_strength_opportunity_v1(or_width_min=or_width_min)
    if normalized in {"c18_vwap_mr_balance_v1", "vwap_mr_balance_v1", "c18_balance", "vwap_mr_balance"}:
        return c18_vwap_mr_balance_v1(or_width_min=or_width_min)
    if normalized in {"c18_vwap_mr_quality_v1", "vwap_mr_quality_v1", "c18_quality", "vwap_mr_quality"}:
        return c18_vwap_mr_quality_v1(or_width_min=or_width_min)
    if normalized in {"c18_vwap_mr_regime_v1", "vwap_mr_regime_v1", "c18_regime", "vwap_mr_regime"}:
        return c18_vwap_mr_regime_v1(or_width_min=or_width_min)
    if normalized in {"c18_vwap_mr_opportunity_v1", "vwap_mr_opportunity_v1", "c18_opportunity", "vwap_mr_opportunity"}:
        return c18_vwap_mr_opportunity_v1(or_width_min=or_width_min)
    if normalized in {"c18_vwap_mr_fast_v1", "vwap_mr_fast_v1", "c18_fast", "vwap_mr_fast"}:
        return c18_vwap_mr_fast_v1(or_width_min=or_width_min)
    if normalized in {"c18_vwap_mr_long_only_balance_v2", "vwap_mr_long_only_balance_v2", "c18_balance_v2", "vwap_mr_balance_v2"}:
        return c18_vwap_mr_long_only_balance_v2(or_width_min=or_width_min)
    if normalized in {"c18_vwap_mr_long_only_quality_v2", "vwap_mr_long_only_quality_v2", "c18_quality_v2", "vwap_mr_quality_v2"}:
        return c18_vwap_mr_long_only_quality_v2(or_width_min=or_width_min)
    if normalized in {"c18_vwap_mr_long_only_regime_v2", "vwap_mr_long_only_regime_v2", "c18_regime_v2", "vwap_mr_regime_v2"}:
        return c18_vwap_mr_long_only_regime_v2(or_width_min=or_width_min)
    if normalized in {"c7_opening_failure_reversal_v1", "opening_failure_reversal_v1", "failure_reversal_v1"}:
        return c7_opening_failure_reversal_v1(or_width_min=or_width_min)
    if normalized in {"c7_opening_failure_reversal_quality_v1", "opening_failure_reversal_quality_v1", "failure_reversal_quality_v1"}:
        return c7_opening_failure_reversal_quality_v1(or_width_min=or_width_min)
    if normalized in {"c7_opening_failure_reversal_regime_v1", "opening_failure_reversal_regime_v1", "failure_reversal_regime_v1"}:
        return c7_opening_failure_reversal_regime_v1(or_width_min=or_width_min)
    if normalized in {"c7_opening_failure_reversal_long_only_v1", "opening_failure_reversal_long_only_v1", "failure_reversal_long_only_v1"}:
        return c7_opening_failure_reversal_long_only_v1(or_width_min=or_width_min)
    if normalized in {"c7_opening_failure_reversal_short_only_v1", "opening_failure_reversal_short_only_v1", "failure_reversal_short_only_v1"}:
        return c7_opening_failure_reversal_short_only_v1(or_width_min=or_width_min)
    if normalized in {
        "c7_opening_failure_reversal_long_only_balance_v2",
        "opening_failure_reversal_long_only_balance_v2",
        "failure_reversal_long_only_balance_v2",
    }:
        return c7_opening_failure_reversal_long_only_balance_v2(or_width_min=or_width_min)
    if normalized in {
        "c7_opening_failure_reversal_long_only_regime_v2",
        "opening_failure_reversal_long_only_regime_v2",
        "failure_reversal_long_only_regime_v2",
    }:
        return c7_opening_failure_reversal_long_only_regime_v2(or_width_min=or_width_min)
    if normalized in {"c8_event_drive_balance_v1", "event_drive_balance_v1"}:
        return c8_event_drive_balance_v1(or_width_min=or_width_min)
    if normalized in {"c8_event_drive_quality_v1", "event_drive_quality_v1"}:
        return c8_event_drive_quality_v1(or_width_min=or_width_min)
    if normalized in {"c8_event_drive_regime_v1", "event_drive_regime_v1"}:
        return c8_event_drive_regime_v1(or_width_min=or_width_min)
    if normalized in {"c8_event_drive_long_only_v1", "event_drive_long_only_v1"}:
        return c8_event_drive_long_only_v1(or_width_min=or_width_min)
    if normalized in {"c8_event_drive_fast_v2", "event_drive_fast_v2"}:
        return c8_event_drive_fast_v2(or_width_min=or_width_min)
    if normalized in {"c19_event_drive_balance_v1", "c19_event_drive_balance", "event_drive_balance_v3"}:
        return c19_event_drive_balance_v1(or_width_min=or_width_min)
    if normalized in {"c19_event_drive_quality_v1", "c19_event_drive_quality", "event_drive_quality_v3"}:
        return c19_event_drive_quality_v1(or_width_min=or_width_min)
    if normalized in {"c19_event_drive_regime_v1", "c19_event_drive_regime", "event_drive_regime_v3"}:
        return c19_event_drive_regime_v1(or_width_min=or_width_min)
    if normalized in {"c19_event_drive_fast_v1", "c19_event_drive_fast", "event_drive_fast_v3"}:
        return c19_event_drive_fast_v1(or_width_min=or_width_min)
    if normalized in {"c57_event_drive_preopen_balance_v1", "c57_preopen_balance", "event_drive_preopen_balance_v1"}:
        return c57_event_drive_preopen_balance_v1(or_width_min=or_width_min)
    if normalized in {"c57_event_drive_preopen_quality_v1", "c57_preopen_quality", "event_drive_preopen_quality_v1"}:
        return c57_event_drive_preopen_quality_v1(or_width_min=or_width_min)
    if normalized in {"c57_event_drive_preopen_regime_v1", "c57_preopen_regime", "event_drive_preopen_regime_v1"}:
        return c57_event_drive_preopen_regime_v1(or_width_min=or_width_min)
    if normalized in {"c9_opening_compression_balance_v1", "opening_compression_balance_v1"}:
        return c9_opening_compression_balance_v1(or_width_min=or_width_min)
    if normalized in {"c9_opening_compression_quality_v1", "opening_compression_quality_v1"}:
        return c9_opening_compression_quality_v1(or_width_min=or_width_min)
    if normalized in {"c9_opening_compression_regime_v1", "opening_compression_regime_v1"}:
        return c9_opening_compression_regime_v1(or_width_min=or_width_min)
    if normalized in {"c9_opening_compression_long_only_v1", "opening_compression_long_only_v1"}:
        return c9_opening_compression_long_only_v1(or_width_min=or_width_min)
    if normalized in {"c9_opening_compression_fast_v2", "opening_compression_fast_v2"}:
        return c9_opening_compression_fast_v2(or_width_min=or_width_min)
    if normalized in {
        "c58_orb_transition_compression_consistency_v1",
        "transition_compression_consistency_v1",
        "c58_transition_consistency",
    }:
        return c58_orb_transition_compression_consistency_v1(or_width_min=or_width_min)
    if normalized in {
        "c58_opening_compression_consistency_v1",
        "opening_compression_consistency_v1",
        "c58_consistency",
    }:
        return c58_opening_compression_consistency_v1(or_width_min=or_width_min)
    if normalized in {
        "c58_opening_compression_consistency_regime_v1",
        "opening_compression_consistency_regime_v1",
        "c58_consistency_regime",
    }:
        return c58_opening_compression_consistency_regime_v1(or_width_min=or_width_min)
    if normalized in {
        "c61_opening_compression_stability_balance_v1",
        "opening_compression_stability_balance_v1",
        "c61_balance",
    }:
        return c61_opening_compression_stability_balance_v1(or_width_min=or_width_min)
    if normalized in {
        "c61_opening_compression_stability_regime_v1",
        "opening_compression_stability_regime_v1",
        "c61_regime",
    }:
        return c61_opening_compression_stability_regime_v1(or_width_min=or_width_min)
    if normalized in {
        "c63_opening_compression_smoother_balance_v1",
        "opening_compression_smoother_balance_v1",
        "c63_balance",
    }:
        return c63_opening_compression_smoother_balance_v1(or_width_min=or_width_min)
    if normalized in {
        "c63_opening_compression_smoother_quality_v1",
        "opening_compression_smoother_quality_v1",
        "c63_quality",
    }:
        return c63_opening_compression_smoother_quality_v1(or_width_min=or_width_min)
    if normalized in {"c10_relative_strength_balance_v1", "relative_strength_balance_v1"}:
        return c10_relative_strength_balance_v1(or_width_min=or_width_min)
    if normalized in {"c10_relative_strength_quality_v1", "relative_strength_quality_v1"}:
        return c10_relative_strength_quality_v1(or_width_min=or_width_min)
    if normalized in {"c10_relative_strength_regime_v1", "relative_strength_regime_v1"}:
        return c10_relative_strength_regime_v1(or_width_min=or_width_min)
    if normalized in {"c10_relative_strength_loose_v1", "relative_strength_loose_v1"}:
        return c10_relative_strength_loose_v1(or_width_min=or_width_min)
    if normalized in {"c10_relative_strength_fast_v2", "relative_strength_fast_v2"}:
        return c10_relative_strength_fast_v2(or_width_min=or_width_min)
    if normalized in {"c11_proxy_vwap_reclaim_balance_v1", "proxy_vwap_reclaim_balance_v1", "c11_balance"}:
        return c11_proxy_vwap_reclaim_balance_v1(or_width_min=or_width_min)
    if normalized in {"c11_proxy_vwap_reclaim_quality_v1", "proxy_vwap_reclaim_quality_v1", "c11_quality"}:
        return c11_proxy_vwap_reclaim_quality_v1(or_width_min=or_width_min)
    if normalized in {"c11_proxy_vwap_reclaim_regime_v1", "proxy_vwap_reclaim_regime_v1", "c11_regime"}:
        return c11_proxy_vwap_reclaim_regime_v1(or_width_min=or_width_min)
    if normalized in {"c11_proxy_vwap_reclaim_loose_v1", "proxy_vwap_reclaim_loose_v1", "c11_loose"}:
        return c11_proxy_vwap_reclaim_loose_v1(or_width_min=or_width_min)
    if normalized in {"c11_proxy_vwap_reclaim_fast_v2", "proxy_vwap_reclaim_fast_v2", "c11_fast"}:
        return c11_proxy_vwap_reclaim_fast_v2(or_width_min=or_width_min)
    if normalized in {"c11_proxy_vwap_reclaim_opportunity_v3", "proxy_vwap_reclaim_opportunity_v3", "c11_opportunity"}:
        return c11_proxy_vwap_reclaim_opportunity_v3(or_width_min=or_width_min)
    if normalized in {
        "c11_proxy_vwap_reclaim_opportunity_regime_v3",
        "proxy_vwap_reclaim_opportunity_regime_v3",
        "c11_opportunity_regime",
    }:
        return c11_proxy_vwap_reclaim_opportunity_regime_v3(or_width_min=or_width_min)
    if normalized in {"c56_proxy_vwap_reclaim_opportunity_guard_v1", "c56_guard", "proxy_vwap_reclaim_guard_v1"}:
        return c56_proxy_vwap_reclaim_opportunity_guard_v1(or_width_min=or_width_min)
    if normalized in {
        "c56_proxy_vwap_reclaim_opportunity_guard_regime_v1",
        "c56_guard_regime",
        "proxy_vwap_reclaim_guard_regime_v1",
    }:
        return c56_proxy_vwap_reclaim_opportunity_guard_regime_v1(or_width_min=or_width_min)
    if normalized in {"c12_relative_strength_opportunity_v1", "relative_strength_opportunity_v1", "c12_opportunity"}:
        return c12_relative_strength_opportunity_v1(or_width_min=or_width_min)
    if normalized in {"c12_relative_strength_opportunity_plus_v1", "relative_strength_opportunity_plus_v1", "c12_opportunity_plus"}:
        return c12_relative_strength_opportunity_plus_v1(or_width_min=or_width_min)
    if normalized in {"c12_relative_strength_opportunity_regime_v1", "relative_strength_opportunity_regime_v1", "c12_opportunity_regime"}:
        return c12_relative_strength_opportunity_regime_v1(or_width_min=or_width_min)
    if normalized in {"c12_relative_strength_balance_v1", "relative_strength_balance_v2", "c12_balance"}:
        return c12_relative_strength_balance_v1(or_width_min=or_width_min)
    if normalized in {"c12_relative_strength_quality_v1", "relative_strength_quality_v2", "c12_quality"}:
        return c12_relative_strength_quality_v1(or_width_min=or_width_min)
    if normalized in {"c12_relative_strength_regime_v1", "relative_strength_regime_v2", "c12_regime"}:
        return c12_relative_strength_regime_v1(or_width_min=or_width_min)
    if normalized in {"c12_relative_strength_fast_v1", "relative_strength_fast_v3", "c12_fast"}:
        return c12_relative_strength_fast_v1(or_width_min=or_width_min)
    if normalized in {"c12_relative_strength_quote_tight_v2", "relative_strength_quote_tight_v2", "c12_quote_tight"}:
        return c12_relative_strength_quote_tight_v2(or_width_min=or_width_min)
    if normalized in {"c12_relative_strength_quote_opportunity_v2", "relative_strength_quote_opportunity_v2", "c12_quote_opportunity"}:
        return c12_relative_strength_quote_opportunity_v2(or_width_min=or_width_min)
    if normalized in {"c12_relative_strength_quote_regime_v2", "relative_strength_quote_regime_v2", "c12_quote_regime"}:
        return c12_relative_strength_quote_regime_v2(or_width_min=or_width_min)
    if normalized in {
        "c12_relative_strength_option_native_v3",
        "relative_strength_option_native_v3",
        "c12_option_native",
    }:
        return c12_relative_strength_option_native_v3(or_width_min=or_width_min)
    if normalized in {
        "c12_relative_strength_option_native_quality_v3",
        "relative_strength_option_native_quality_v3",
        "c12_option_native_quality",
    }:
        return c12_relative_strength_option_native_quality_v3(or_width_min=or_width_min)
    if normalized in {
        "c12_relative_strength_option_native_regime_v3",
        "relative_strength_option_native_regime_v3",
        "c12_option_native_regime",
    }:
        return c12_relative_strength_option_native_regime_v3(or_width_min=or_width_min)
    if normalized in {
        "c19_relative_strength_debit_spread_v1",
        "relative_strength_debit_spread_v1",
        "c19_debit_spread",
    }:
        return c19_relative_strength_debit_spread_v1(or_width_min=or_width_min)
    if normalized in {
        "c19_relative_strength_debit_spread_v2",
        "relative_strength_debit_spread_v2",
        "c19_debit_spread_v2",
    }:
        return c19_relative_strength_debit_spread_v2(or_width_min=or_width_min)
    if normalized in {
        "c19_relative_strength_debit_spread_quality_v1",
        "relative_strength_debit_spread_quality_v1",
        "c19_debit_spread_quality",
    }:
        return c19_relative_strength_debit_spread_quality_v1(or_width_min=or_width_min)
    if normalized in {
        "c19_relative_strength_debit_spread_quality_v2",
        "relative_strength_debit_spread_quality_v2",
        "c19_debit_spread_quality_v2",
    }:
        return c19_relative_strength_debit_spread_quality_v2(or_width_min=or_width_min)
    if normalized in {
        "c19_relative_strength_debit_spread_regime_v1",
        "relative_strength_debit_spread_regime_v1",
        "c19_debit_spread_regime",
    }:
        return c19_relative_strength_debit_spread_regime_v1(or_width_min=or_width_min)
    if normalized in {
        "c19_relative_strength_debit_spread_regime_v2",
        "relative_strength_debit_spread_regime_v2",
        "c19_debit_spread_regime_v2",
    }:
        return c19_relative_strength_debit_spread_regime_v2(or_width_min=or_width_min)
    if normalized in {
        "c4_breakout_debit_spread_v1",
        "breakout_debit_spread_v1",
        "c4_breakout_debit_spread",
    }:
        return c4_breakout_debit_spread_v1(or_width_min=or_width_min)
    if normalized in {
        "c4_breakout_debit_spread_quality_v1",
        "breakout_debit_spread_quality_v1",
        "c4_breakout_debit_spread_quality",
    }:
        return c4_breakout_debit_spread_quality_v1(or_width_min=or_width_min)
    if normalized in {"c13_orb_fib_pullback_balance_v1", "orb_fib_pullback_balance_v1", "c13_balance", "fib_balance"}:
        return c13_orb_fib_pullback_balance_v1(or_width_min=or_width_min)
    if normalized in {"c13_orb_fib_pullback_quality_v1", "orb_fib_pullback_quality_v1", "c13_quality", "fib_quality"}:
        return c13_orb_fib_pullback_quality_v1(or_width_min=or_width_min)
    if normalized in {
        "c13_orb_fib_pullback_opportunity_v1",
        "orb_fib_pullback_opportunity_v1",
        "c13_opportunity",
        "fib_opportunity",
    }:
        return c13_orb_fib_pullback_opportunity_v1(or_width_min=or_width_min)
    if normalized in {"c13_orb_fib_pullback_regime_v1", "orb_fib_pullback_regime_v1", "c13_regime", "fib_regime"}:
        return c13_orb_fib_pullback_regime_v1(or_width_min=or_width_min)
    if normalized in {"c13_orb_fib_pullback_fast_v1", "orb_fib_pullback_fast_v1", "c13_fast", "fib_fast"}:
        return c13_orb_fib_pullback_fast_v1(or_width_min=or_width_min)
    if normalized in {
        "c14_gap_rejection_balance_v1",
        "gap_rejection_balance_v1",
        "c14_balance",
        "gap_balance",
    }:
        return c14_gap_rejection_balance_v1(or_width_min=or_width_min)
    if normalized in {
        "c14_gap_rejection_quality_v1",
        "gap_rejection_quality_v1",
        "c14_quality",
        "gap_quality",
    }:
        return c14_gap_rejection_quality_v1(or_width_min=or_width_min)
    if normalized in {
        "c14_gap_rejection_opportunity_v1",
        "gap_rejection_opportunity_v1",
        "c14_opportunity",
        "gap_opportunity",
    }:
        return c14_gap_rejection_opportunity_v1(or_width_min=or_width_min)
    if normalized in {
        "c14_gap_rejection_regime_v1",
        "gap_rejection_regime_v1",
        "c14_regime",
        "gap_regime",
    }:
        return c14_gap_rejection_regime_v1(or_width_min=or_width_min)
    if normalized in {
        "c14_gap_rejection_long_only_v1",
        "gap_rejection_long_only_v1",
        "c14_long_only",
        "gap_long_only",
    }:
        return c14_gap_rejection_long_only_v1(or_width_min=or_width_min)
    if normalized in {
        "c15_failure_fade_balance_v1",
        "failure_fade_balance_v1",
        "c15_balance",
        "failure_fade_balance",
    }:
        return c15_failure_fade_balance_v1(or_width_min=or_width_min)
    if normalized in {
        "c15_failure_fade_quality_v1",
        "failure_fade_quality_v1",
        "c15_quality",
        "failure_fade_quality",
    }:
        return c15_failure_fade_quality_v1(or_width_min=or_width_min)
    if normalized in {
        "c15_failure_fade_regime_v1",
        "failure_fade_regime_v1",
        "c15_regime",
        "failure_fade_regime",
    }:
        return c15_failure_fade_regime_v1(or_width_min=or_width_min)
    if normalized in {
        "c15_failure_fade_fast_v1",
        "failure_fade_fast_v1",
        "c15_fast",
        "failure_fade_fast",
    }:
        return c15_failure_fade_fast_v1(or_width_min=or_width_min)
    if normalized in {
        "c15_failure_fade_long_only_v1",
        "failure_fade_long_only_v1",
        "c15_long_only",
        "failure_fade_long_only",
    }:
        return c15_failure_fade_long_only_v1(or_width_min=or_width_min)
    if normalized in {"c4_trend_pullback_fast_v2", "trend_pullback_fast_v2"}:
        return c4_trend_pullback_fast_v2(or_width_min=or_width_min)
    if normalized in {"c4_trend_pullback_tight", "trend_pullback_tight"}:
        return c4_trend_pullback_tight(or_width_min=or_width_min)
    if normalized in {"c21_trend_pullback_balance_v1", "trend_pullback_balance_v1", "c21_balance"}:
        return c21_trend_pullback_balance_v1(or_width_min=or_width_min)
    if normalized in {"c21_trend_pullback_quality_v1", "trend_pullback_quality_v1", "c21_quality"}:
        return c21_trend_pullback_quality_v1(or_width_min=or_width_min)
    if normalized in {"c21_trend_pullback_regime_v1", "trend_pullback_regime_v1", "c21_regime"}:
        return c21_trend_pullback_regime_v1(or_width_min=or_width_min)
    if normalized in {"c21_trend_pullback_fast_v1", "trend_pullback_fast_v1", "c21_fast"}:
        return c21_trend_pullback_fast_v1(or_width_min=or_width_min)
    if normalized in {"c4_orb_event_drive_v1", "orb_event_drive_v1", "event_drive"}:
        return c4_orb_event_drive_v1(or_width_min=or_width_min)
    if normalized in {"c4_orb_transition_compression_v1", "orb_transition_compression_v1", "transition_compression"}:
        return c4_orb_transition_compression_v1(or_width_min=or_width_min)
    if normalized in {"c4_orb_option_structure_v1", "orb_option_structure_v1", "option_structure"}:
        return c4_orb_option_structure_v1(or_width_min=or_width_min)
    if normalized in {"c4_trend_short_guard_v2", "trend_short_guard_v2"}:
        return c4_trend_short_guard_v2(or_width_min=or_width_min)
    if normalized in {"c22_trend_short_balance_v1", "trend_short_balance_v1", "c22_balance"}:
        return c22_trend_short_balance_v1(or_width_min=or_width_min)
    if normalized in {"c22_trend_short_quality_v1", "trend_short_quality_v1", "c22_quality"}:
        return c22_trend_short_quality_v1(or_width_min=or_width_min)
    if normalized in {"c22_trend_short_regime_v1", "trend_short_regime_v1", "c22_regime"}:
        return c22_trend_short_regime_v1(or_width_min=or_width_min)
    if normalized in {"c22_trend_short_fast_v1", "trend_short_fast_v1", "c22_fast"}:
        return c22_trend_short_fast_v1(or_width_min=or_width_min)
    if normalized in {"c23_failed_break_reclaim_balance_v1", "failed_break_reclaim_balance_v1", "c23_balance"}:
        return c23_failed_break_reclaim_balance_v1(or_width_min=or_width_min)
    if normalized in {"c23_failed_break_reclaim_quality_v1", "failed_break_reclaim_quality_v1", "c23_quality"}:
        return c23_failed_break_reclaim_quality_v1(or_width_min=or_width_min)
    if normalized in {"c23_failed_break_reclaim_regime_v1", "failed_break_reclaim_regime_v1", "c23_regime"}:
        return c23_failed_break_reclaim_regime_v1(or_width_min=or_width_min)
    if normalized in {"c24_pause_go_continuation_balance_v1", "pause_go_continuation_balance_v1", "c24_balance"}:
        return c24_pause_go_continuation_balance_v1(or_width_min=or_width_min)
    if normalized in {"c24_pause_go_continuation_quality_v1", "pause_go_continuation_quality_v1", "c24_quality"}:
        return c24_pause_go_continuation_quality_v1(or_width_min=or_width_min)
    if normalized in {"c24_pause_go_continuation_regime_v1", "pause_go_continuation_regime_v1", "c24_regime"}:
        return c24_pause_go_continuation_regime_v1(or_width_min=or_width_min)
    if normalized in {"c25_vwap_support_continuation_balance_v1", "vwap_support_continuation_balance_v1", "c25_balance"}:
        return c25_vwap_support_continuation_balance_v1(or_width_min=or_width_min)
    if normalized in {"c25_vwap_support_continuation_quality_v1", "vwap_support_continuation_quality_v1", "c25_quality"}:
        return c25_vwap_support_continuation_quality_v1(or_width_min=or_width_min)
    if normalized in {"c25_vwap_support_continuation_regime_v1", "vwap_support_continuation_regime_v1", "c25_regime"}:
        return c25_vwap_support_continuation_regime_v1(or_width_min=or_width_min)
    if normalized in {"c26_gap_reclaim_continuation_balance_v1", "gap_reclaim_continuation_balance_v1", "c26_balance"}:
        return c26_gap_reclaim_continuation_balance_v1(or_width_min=or_width_min)
    if normalized in {"c26_gap_reclaim_continuation_quality_v1", "gap_reclaim_continuation_quality_v1", "c26_quality"}:
        return c26_gap_reclaim_continuation_quality_v1(or_width_min=or_width_min)
    if normalized in {"c26_gap_reclaim_continuation_regime_v1", "gap_reclaim_continuation_regime_v1", "c26_regime"}:
        return c26_gap_reclaim_continuation_regime_v1(or_width_min=or_width_min)
    if normalized in {"c27_intraday_compression_release_balance_v1", "intraday_compression_release_balance_v1", "c27_balance"}:
        return c27_intraday_compression_release_balance_v1(or_width_min=or_width_min)
    if normalized in {"c27_intraday_compression_release_quality_v1", "intraday_compression_release_quality_v1", "c27_quality"}:
        return c27_intraday_compression_release_quality_v1(or_width_min=or_width_min)
    if normalized in {"c27_intraday_compression_release_regime_v1", "intraday_compression_release_regime_v1", "c27_regime"}:
        return c27_intraday_compression_release_regime_v1(or_width_min=or_width_min)
    if normalized in {"c28_failed_breakdown_reversal_balance_v1", "failed_breakdown_reversal_balance_v1", "c28_balance"}:
        return c28_failed_breakdown_reversal_balance_v1(or_width_min=or_width_min)
    if normalized in {"c28_failed_breakdown_reversal_quality_v1", "failed_breakdown_reversal_quality_v1", "c28_quality"}:
        return c28_failed_breakdown_reversal_quality_v1(or_width_min=or_width_min)
    if normalized in {"c28_failed_breakdown_reversal_regime_v1", "failed_breakdown_reversal_regime_v1", "c28_regime"}:
        return c28_failed_breakdown_reversal_regime_v1(or_width_min=or_width_min)
    if normalized in {"c29_open_drive_pullback_balance_v1", "open_drive_pullback_balance_v1", "c29_balance"}:
        return c29_open_drive_pullback_balance_v1(or_width_min=or_width_min)
    if normalized in {"c29_open_drive_pullback_quality_v1", "open_drive_pullback_quality_v1", "c29_quality"}:
        return c29_open_drive_pullback_quality_v1(or_width_min=or_width_min)
    if normalized in {"c29_open_drive_pullback_regime_v1", "open_drive_pullback_regime_v1", "c29_regime"}:
        return c29_open_drive_pullback_regime_v1(or_width_min=or_width_min)
    if normalized in {"c30_orb_retest_higher_low_balance_v1", "orb_retest_higher_low_balance_v1", "c30_balance"}:
        return c30_orb_retest_higher_low_balance_v1(or_width_min=or_width_min)
    if normalized in {"c30_orb_retest_higher_low_quality_v1", "orb_retest_higher_low_quality_v1", "c30_quality"}:
        return c30_orb_retest_higher_low_quality_v1(or_width_min=or_width_min)
    if normalized in {"c30_orb_retest_higher_low_regime_v1", "orb_retest_higher_low_regime_v1", "c30_regime"}:
        return c30_orb_retest_higher_low_regime_v1(or_width_min=or_width_min)
    if normalized in {"c31_vwap_rollover_short_balance_v1", "vwap_rollover_short_balance_v1", "c31_balance"}:
        return c31_vwap_rollover_short_balance_v1(or_width_min=or_width_min)
    if normalized in {"c31_vwap_rollover_short_quality_v1", "vwap_rollover_short_quality_v1", "c31_quality"}:
        return c31_vwap_rollover_short_quality_v1(or_width_min=or_width_min)
    if normalized in {"c31_vwap_rollover_short_regime_v1", "vwap_rollover_short_regime_v1", "c31_regime"}:
        return c31_vwap_rollover_short_regime_v1(or_width_min=or_width_min)
    if normalized in {"c32_gap_up_fail_fade_balance_v1", "gap_up_fail_fade_balance_v1", "c32_balance"}:
        return c32_gap_up_fail_fade_balance_v1(or_width_min=or_width_min)
    if normalized in {"c32_gap_up_fail_fade_quality_v1", "gap_up_fail_fade_quality_v1", "c32_quality"}:
        return c32_gap_up_fail_fade_quality_v1(or_width_min=or_width_min)
    if normalized in {"c32_gap_up_fail_fade_regime_v1", "gap_up_fail_fade_regime_v1", "c32_regime"}:
        return c32_gap_up_fail_fade_regime_v1(or_width_min=or_width_min)
    if normalized in {"c4_mr_vwap_v1", "mr_vwap_v1", "mr_vwap"}:
        return c4_mr_vwap_v1(or_width_min=or_width_min)
    if normalized in {"c4_mr_vwap_conservative_v1", "mr_vwap_conservative_v1", "mr_vwap_conservative"}:
        return c4_mr_vwap_conservative_v1(or_width_min=or_width_min)
    if normalized in {"c4_mr_vwap_zscore_v2", "mr_vwap_zscore_v2", "mr_zscore"}:
        return c4_mr_vwap_zscore_v2(or_width_min=or_width_min)
    if normalized in {"c4_mr_vwap_zscore_v2_conservative", "mr_vwap_zscore_v2_conservative", "mr_zscore_cons"}:
        return c4_mr_vwap_zscore_v2_conservative(or_width_min=or_width_min)
    if normalized in {"c4_mr_vwap_zscore_v2_fast", "mr_vwap_zscore_v2_fast", "mr_zscore_fast"}:
        return c4_mr_vwap_zscore_v2_fast(or_width_min=or_width_min)
    if normalized in {"c4_mr_vwap_zscore_v2_rr", "mr_vwap_zscore_v2_rr", "mr_zscore_rr"}:
        return c4_mr_vwap_zscore_v2_rr(or_width_min=or_width_min)
    if normalized in {"c4_mr_vwap_zscore_v2_long_only", "mr_vwap_zscore_v2_long_only", "mr_zscore_long_only"}:
        return c4_mr_vwap_zscore_v2_long_only(or_width_min=or_width_min)
    if normalized in {"c4_mr_vwap_zscore_v2_sideways", "mr_vwap_zscore_v2_sideways", "mr_zscore_sideways"}:
        return c4_mr_vwap_zscore_v2_sideways(or_width_min=or_width_min)
    if normalized in {"c4_mr_vwap_exhaustion_v1", "mr_vwap_exhaustion_v1", "mr_exhaustion"}:
        return c4_mr_vwap_exhaustion_v1(or_width_min=or_width_min)
    if normalized in {"c4_mr_vwap_exhaustion_quality_v1", "mr_vwap_exhaustion_quality_v1", "mr_exhaustion_quality"}:
        return c4_mr_vwap_exhaustion_quality_v1(or_width_min=or_width_min)
    if normalized in {"c4_mr_vwap_exhaustion_relaxed_v1", "mr_vwap_exhaustion_relaxed_v1", "mr_exhaustion_relaxed"}:
        return c4_mr_vwap_exhaustion_relaxed_v1(or_width_min=or_width_min)
    if normalized in {"c4_mr_vwap_exhaustion_guard_v2", "mr_vwap_exhaustion_guard_v2", "mr_exhaustion_guard"}:
        return c4_mr_vwap_exhaustion_guard_v2(or_width_min=or_width_min)
    if normalized in {"c4_mr_vwap_exhaustion_balance_v3", "mr_vwap_exhaustion_balance_v3", "mr_exhaustion_balance"}:
        return c4_mr_vwap_exhaustion_balance_v3(or_width_min=or_width_min)
    if normalized in {"c4_mr_overnight_regime_v1", "mr_overnight_regime_v1", "mr_overnight", "overnight_mr"}:
        return c4_mr_overnight_regime_v1(or_width_min=or_width_min)
    if normalized in {"c4_mr_overnight_relaxed_v2", "mr_overnight_relaxed_v2", "overnight_mr_relaxed"}:
        return c4_mr_overnight_relaxed_v2(or_width_min=or_width_min)
    if normalized in {"c4_mr_rr_fast_v2", "mr_rr_fast_v2", "mr_fast_v2"}:
        return c4_mr_rr_fast_v2(or_width_min=or_width_min)
    if normalized in {"c4_mr_rr_fast_guard_v3", "mr_rr_fast_guard_v3", "mr_fast_guard_v3"}:
        return c4_mr_rr_fast_guard_v3(or_width_min=or_width_min)
    if normalized in {"c4_mr_rr_fast_recovery_v4", "mr_rr_fast_recovery_v4", "mr_fast_recovery_v4"}:
        return c4_mr_rr_fast_recovery_v4(or_width_min=or_width_min)
    if normalized in {"c4_mr_side_loose", "mr_side_loose"}:
        return c4_mr_side_loose(or_width_min=or_width_min)
    if normalized in {"c4_dispersion_breakout_v1", "dispersion_breakout", "orb_dispersion_breakout_v1"}:
        return c4_dispersion_breakout_v1(or_width_min=or_width_min)
    if normalized in {"c4_dispersion_breakout_breadth_v2", "dispersion_breakout_breadth_v2"}:
        return c4_dispersion_breakout_breadth_v2(or_width_min=or_width_min)
    if normalized in {"c4_dispersion_breakout_relative_v2", "dispersion_breakout_relative_v2"}:
        return c4_dispersion_breakout_relative_v2(or_width_min=or_width_min)
    if normalized in {"c4_dispersion_relative_breakout_v3", "dispersion_relative_breakout_v3"}:
        return c4_dispersion_relative_breakout_v3(or_width_min=or_width_min)
    if normalized in {"c4_dispersion_relative_breakout_guard_v3", "dispersion_relative_breakout_guard_v3"}:
        return c4_dispersion_relative_breakout_guard_v3(or_width_min=or_width_min)
    if normalized in {"c4_dispersion_relative_breakout_decay_v4", "dispersion_relative_breakout_decay_v4"}:
        return c4_dispersion_relative_breakout_decay_v4(or_width_min=or_width_min)
    if normalized in {
        "c4_dispersion_relative_breakout_guard_hold30_v1",
        "dispersion_relative_breakout_guard_hold30_v1",
    }:
        return c4_dispersion_relative_breakout_guard_hold30_v1(or_width_min=or_width_min)
    if normalized in {
        "c4_dispersion_relative_breakout_guard_density_v1",
        "dispersion_relative_breakout_guard_density_v1",
    }:
        return c4_dispersion_relative_breakout_guard_density_v1(or_width_min=or_width_min)
    if normalized in {
        "c4_dispersion_relative_breakout_guard_density_spy_dia_v1",
        "dispersion_relative_breakout_guard_density_spy_dia_v1",
    }:
        return c4_dispersion_relative_breakout_guard_density_spy_dia_v1(or_width_min=or_width_min)
    if normalized in {
        "c4_dispersion_relative_breakout_guard_density_spy_dia_balance_v1",
        "dispersion_relative_breakout_guard_density_spy_dia_balance_v1",
    }:
        return c4_dispersion_relative_breakout_guard_density_spy_dia_balance_v1(or_width_min=or_width_min)
    if normalized in {
        "c4_dispersion_relative_breakout_guard_density_spy_dia_offset_v1",
        "dispersion_relative_breakout_guard_density_spy_dia_offset_v1",
    }:
        return c4_dispersion_relative_breakout_guard_density_spy_dia_offset_v1(or_width_min=or_width_min)
    if normalized in {"c4_dispersion_relative_breakout_recovery_v5", "dispersion_relative_breakout_recovery_v5"}:
        return c4_dispersion_relative_breakout_recovery_v5(or_width_min=or_width_min)
    dynamic_dispersion_option = _maybe_build_dispersion_relative_breakout_option_followup_profile(
        normalized,
        or_width_min=or_width_min,
    )
    if dynamic_dispersion_option is not None:
        return dynamic_dispersion_option
    if normalized in {"c4_dispersion_revert_tight", "dispersion_revert_tight"}:
        return c4_dispersion_revert_tight(or_width_min=or_width_min)
    if normalized in {"c4_dispersion_revert_quality_v3", "dispersion_revert_quality_v3"}:
        return c4_dispersion_revert_quality_v3(or_width_min=or_width_min)
    if normalized in {"c4_dispersion_revert_v1", "dispersion_revert", "mr_dispersion_revert_v1"}:
        return c4_dispersion_revert_v1(or_width_min=or_width_min)
    if normalized in {"c4_dispersion_revert_rotation_v2", "dispersion_revert_rotation_v2"}:
        return c4_dispersion_revert_rotation_v2(or_width_min=or_width_min)
    if normalized in {"c4_dispersion_revert_exhaustion_v2", "dispersion_revert_exhaustion_v2"}:
        return c4_dispersion_revert_exhaustion_v2(or_width_min=or_width_min)
    if normalized in {"c4_dispersion_relative_revert_v3", "dispersion_relative_revert_v3"}:
        return c4_dispersion_relative_revert_v3(or_width_min=or_width_min)
    if normalized in {"c4_dispersion_relative_revert_exhaustion_v3", "dispersion_relative_revert_exhaustion_v3"}:
        return c4_dispersion_relative_revert_exhaustion_v3(or_width_min=or_width_min)
    if normalized in {"c4_dispersion_relative_revert_confirm_v4", "dispersion_relative_revert_confirm_v4"}:
        return c4_dispersion_relative_revert_confirm_v4(or_width_min=or_width_min)
    if normalized in {"c4_dispersion_relative_revert_quality_v4", "dispersion_relative_revert_quality_v4"}:
        return c4_dispersion_relative_revert_quality_v4(or_width_min=or_width_min)
    if normalized in {"c4_dispersion_relative_revert_decay_v5", "dispersion_relative_revert_decay_v5"}:
        return c4_dispersion_relative_revert_decay_v5(or_width_min=or_width_min)
    if normalized in {"c4_dispersion_relative_revert_recovery_v6", "dispersion_relative_revert_recovery_v6"}:
        return c4_dispersion_relative_revert_recovery_v6(or_width_min=or_width_min)
    if normalized in {"c4_pairs_spread_proxy_v1", "pairs_spread_proxy", "pairs_proxy"}:
        return c4_pairs_spread_proxy_v1(or_width_min=or_width_min)
    if normalized in {"c4_pairs_spread_intraday_v1", "pairs_spread_intraday_v1", "pairs_spread_v1"}:
        return c4_pairs_spread_intraday_v1(or_width_min=or_width_min)
    if normalized in {
        "c4_pairs_spread_intraday_relaxed_v1",
        "pairs_spread_intraday_relaxed_v1",
        "pairs_spread_relaxed_v1",
    }:
        return c4_pairs_spread_intraday_relaxed_v1(or_width_min=or_width_min)
    if normalized in {"c4_pairs_spread_intraday_quality_v2", "pairs_spread_intraday_quality_v2"}:
        return c4_pairs_spread_intraday_quality_v2(or_width_min=or_width_min)
    if normalized in {
        "c4_pairs_spread_intraday_range_quality_v1",
        "pairs_spread_intraday_range_quality_v1",
        "pairs_spread_range_quality_v1",
    }:
        return c4_pairs_spread_intraday_range_quality_v1(or_width_min=or_width_min)
    if normalized in {
        "c4_pairs_spread_intraday_bear_reversal_v1",
        "pairs_spread_intraday_bear_reversal_v1",
        "pairs_spread_bear_reversal_v1",
    }:
        return c4_pairs_spread_intraday_bear_reversal_v1(or_width_min=or_width_min)
    if normalized in {"c4_pairs_spread_intraday_recovery_v3", "pairs_spread_intraday_recovery_v3", "pairs_intraday_recovery_v3"}:
        return c4_pairs_spread_intraday_recovery_v3(or_width_min=or_width_min)
    if normalized in {"c4_pairs_overnight_relaxed", "pairs_overnight_relaxed"}:
        return c4_pairs_overnight_relaxed(or_width_min=or_width_min)
    if normalized in {"c4_pairs_overnight_fast_v2", "pairs_overnight_fast_v2"}:
        return c4_pairs_overnight_fast_v2(or_width_min=or_width_min)
    if normalized in {"c4_pairs_overnight_proxy_v1", "pairs_overnight_proxy", "pairs_overnight"}:
        return c4_pairs_overnight_proxy_v1(or_width_min=or_width_min)
    if normalized in {"c4_pairs_overnight_defensive_v1", "pairs_overnight_defensive_v1"}:
        return c4_pairs_overnight_defensive_v1(or_width_min=or_width_min)
    if normalized in {"c52_opening_compression_option_native_balance_v1", "c52_balance"}:
        return c52_opening_compression_option_native_balance_v1(or_width_min=or_width_min)
    if normalized in {"c52_opening_compression_option_native_long_only_v1", "c52_long_only"}:
        return c52_opening_compression_option_native_long_only_v1(or_width_min=or_width_min)
    if normalized in {"c53_intraday_compression_release_option_native_balance_v1", "c53_balance"}:
        return c53_intraday_compression_release_option_native_balance_v1(or_width_min=or_width_min)
    if normalized in {"c53_intraday_compression_release_option_native_quality_v1", "c53_quality"}:
        return c53_intraday_compression_release_option_native_quality_v1(or_width_min=or_width_min)
    if normalized in {"c53_intraday_compression_release_option_native_regime_v1", "c53_regime"}:
        return c53_intraday_compression_release_option_native_regime_v1(or_width_min=or_width_min)
    if normalized in {"c54_opening_compression_option_native_balance_dte35_v1", "c54_balance"}:
        return c54_opening_compression_option_native_balance_dte35_v1(or_width_min=or_width_min)
    if normalized in {"c54_opening_compression_option_native_quality_dte35_v1", "c54_quality"}:
        return c54_opening_compression_option_native_quality_dte35_v1(or_width_min=or_width_min)
    if normalized in {"c54_opening_compression_option_native_regime_dte35_v1", "c54_regime"}:
        return c54_opening_compression_option_native_regime_dte35_v1(or_width_min=or_width_min)
    if normalized in {
        "c59_opening_compression_option_native_consistency_v1",
        "c59_consistency",
    }:
        return c59_opening_compression_option_native_consistency_v1(or_width_min=or_width_min)
    if normalized in {
        "c59_opening_compression_option_native_consistency_regime_v1",
        "c59_consistency_regime",
    }:
        return c59_opening_compression_option_native_consistency_regime_v1(or_width_min=or_width_min)
    if normalized in {
        "c60_opening_compression_option_native_hybrid_v1",
        "c60_hybrid",
        "opening_compression_option_native_hybrid_v1",
    }:
        return c60_opening_compression_option_native_hybrid_v1(or_width_min=or_width_min)
    if normalized in {
        "c62_opening_compression_option_native_stability_fast_v1",
        "c62_fast",
        "opening_compression_option_native_stability_fast_v1",
    }:
        return c62_opening_compression_option_native_stability_fast_v1(or_width_min=or_width_min)
    if normalized in {
        "c62_opening_compression_option_native_stability_dte35_v1",
        "c62_dte35",
        "opening_compression_option_native_stability_dte35_v1",
    }:
        return c62_opening_compression_option_native_stability_dte35_v1(or_width_min=or_width_min)
    if normalized in {
        "c63_opening_compression_option_native_balance_v1",
        "c63_option_balance",
        "opening_compression_option_native_balance_v2",
    }:
        return c63_opening_compression_option_native_balance_v1(or_width_min=or_width_min)
    if normalized in {
        "c63_opening_compression_option_native_quality_v1",
        "c63_option_quality",
        "opening_compression_option_native_quality_v2",
    }:
        return c63_opening_compression_option_native_quality_v1(or_width_min=or_width_min)
    if normalized in {
        "c64_opening_compression_option_native_balance_dte35_v1",
        "c64_balance",
        "opening_compression_option_native_balance_dte35_v2",
    }:
        return c64_opening_compression_option_native_balance_dte35_v1(or_width_min=or_width_min)
    if normalized in {
        "c64_opening_compression_option_native_stability_balance_dte35_v1",
        "c64_stability",
        "opening_compression_option_native_stability_balance_dte35_v1",
    }:
        return c64_opening_compression_option_native_stability_balance_dte35_v1(or_width_min=or_width_min)
    if normalized in {
        "c65_opening_compression_short_quality_v1",
        "c65_short_quality",
        "opening_compression_short_quality_v1",
    }:
        return c65_opening_compression_short_quality_v1(or_width_min=or_width_min)
    if normalized in {
        "c65_opening_compression_long_balance_v1",
        "c65_long_balance",
        "opening_compression_long_balance_v1",
    }:
        return c65_opening_compression_long_balance_v1(or_width_min=or_width_min)
    if normalized in {
        "c65_opening_compression_option_native_short_quality_v1",
        "c65_option_short_quality",
        "opening_compression_option_native_short_quality_v1",
    }:
        return c65_opening_compression_option_native_short_quality_v1(or_width_min=or_width_min)
    if normalized in {
        "c65_opening_compression_option_native_long_balance_v1",
        "c65_option_long_balance",
        "opening_compression_option_native_long_balance_v1",
    }:
        return c65_opening_compression_option_native_long_balance_v1(or_width_min=or_width_min)
    if normalized in {
        "c66_opening_compression_option_native_short_balance_dte35_v1",
        "c66_short_balance",
        "opening_compression_option_native_short_balance_dte35_v1",
    }:
        return c66_opening_compression_option_native_short_balance_dte35_v1(or_width_min=or_width_min)
    if normalized in {
        "c95_opening_compression_option_native_short_balance_dte35_band22_v1",
        "c95_short_balance_band22",
        "c95_c66_band22",
        "opening_compression_option_native_short_balance_dte35_band22_v1",
    }:
        return c95_opening_compression_option_native_short_balance_dte35_band22_v1(or_width_min=or_width_min)
    if normalized in {
        "c96_opening_compression_option_native_short_balance_dte35_etf_liquidity_v1",
        "c96_etf_liquidity",
        "opening_compression_option_native_short_balance_dte35_etf_liquidity_v1",
    }:
        return c96_opening_compression_option_native_short_balance_dte35_etf_liquidity_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c97_opening_compression_option_native_short_balance_dte35_etf_breadth_v1",
        "c97_etf_breadth",
        "opening_compression_option_native_short_balance_dte35_etf_breadth_v1",
    }:
        return c97_opening_compression_option_native_short_balance_dte35_etf_breadth_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c98_opening_compression_option_native_short_balance_dte35_etf_sizeaware_v1",
        "c98_etf_sizeaware",
        "opening_compression_option_native_short_balance_dte35_etf_sizeaware_v1",
    }:
        return c98_opening_compression_option_native_short_balance_dte35_etf_sizeaware_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c99_opening_compression_option_native_short_balance_dte35_etf_retry2_v1",
        "c99_etf_retry2",
        "opening_compression_option_native_short_balance_dte35_etf_retry2_v1",
    }:
        return c99_opening_compression_option_native_short_balance_dte35_etf_retry2_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c100_opening_compression_option_native_short_balance_dte35_etf_retry4_v1",
        "c100_etf_retry4",
        "opening_compression_option_native_short_balance_dte35_etf_retry4_v1",
    }:
        return c100_opening_compression_option_native_short_balance_dte35_etf_retry4_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c101_opening_compression_option_native_short_balance_dte35_etf_breadth_retry2_v1",
        "c101_etf_breadth_retry2",
        "opening_compression_option_native_short_balance_dte35_etf_breadth_retry2_v1",
    }:
        return c101_opening_compression_option_native_short_balance_dte35_etf_breadth_retry2_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c102_opening_compression_option_native_short_balance_dte35_etf_quality_retry2_v1",
        "c102_etf_quality_retry2",
        "opening_compression_option_native_short_balance_dte35_etf_quality_retry2_v1",
    }:
        return c102_opening_compression_option_native_short_balance_dte35_etf_quality_retry2_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c103_opening_compression_option_native_short_balance_dte35_etf_sameexpiry_retry4_v1",
        "c103_etf_sameexpiry_retry4",
        "opening_compression_option_native_short_balance_dte35_etf_sameexpiry_retry4_v1",
    }:
        return c103_opening_compression_option_native_short_balance_dte35_etf_sameexpiry_retry4_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c104_opening_compression_option_native_short_balance_dte35_etf_breadth_sameexpiry_retry2_v1",
        "c104_etf_breadth_sameexpiry_retry2",
        "opening_compression_option_native_short_balance_dte35_etf_breadth_sameexpiry_retry2_v1",
    }:
        return c104_opening_compression_option_native_short_balance_dte35_etf_breadth_sameexpiry_retry2_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c67_opening_compression_option_native_broad_etf_balance_dte35_v1",
        "c67_broad_etf_balance",
        "opening_compression_option_native_broad_etf_balance_dte35_v1",
    }:
        return c67_opening_compression_option_native_broad_etf_balance_dte35_v1(or_width_min=or_width_min)
    if normalized in {
        "c68_opening_compression_option_native_sideways_broad_etf_balance_dte35_v1",
        "c68_sideways_broad_etf_balance",
        "opening_compression_option_native_sideways_broad_etf_balance_dte35_v1",
    }:
        return c68_opening_compression_option_native_sideways_broad_etf_balance_dte35_v1(or_width_min=or_width_min)
    if normalized in {
        "c69_opening_compression_option_native_broad_etf_quality_balance_dte35_v1",
        "c69_broad_etf_quality_balance",
        "opening_compression_option_native_broad_etf_quality_balance_dte35_v1",
    }:
        return c69_opening_compression_option_native_broad_etf_quality_balance_dte35_v1(or_width_min=or_width_min)
    if normalized in {
        "c70_opening_compression_option_native_broad_etf_calm_balance_dte35_v1",
        "c70_broad_etf_calm_balance",
        "opening_compression_option_native_broad_etf_calm_balance_dte35_v1",
    }:
        return c70_opening_compression_option_native_broad_etf_calm_balance_dte35_v1(or_width_min=or_width_min)
    if normalized in {
        "c71_opening_compression_option_native_broad_etf_moderate_balance_dte35_v1",
        "c71_broad_etf_moderate_balance",
        "opening_compression_option_native_broad_etf_moderate_balance_dte35_v1",
    }:
        return c71_opening_compression_option_native_broad_etf_moderate_balance_dte35_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c72_opening_compression_option_native_broad_etf_moderate_rangecap_balance_dte35_v1",
        "c72_broad_etf_moderate_rangecap_balance",
        "opening_compression_option_native_broad_etf_moderate_rangecap_balance_dte35_v1",
    }:
        return c72_opening_compression_option_native_broad_etf_moderate_rangecap_balance_dte35_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c73_opening_compression_option_native_broad_etf_moderate_rvolcap_balance_dte35_v1",
        "c73_broad_etf_moderate_rvolcap_balance",
        "opening_compression_option_native_broad_etf_moderate_rvolcap_balance_dte35_v1",
    }:
        return c73_opening_compression_option_native_broad_etf_moderate_rvolcap_balance_dte35_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c74_opening_compression_option_native_broad_etf_moderate_rvolband_balance_dte35_v1",
        "c74_broad_etf_moderate_rvolband_balance",
        "opening_compression_option_native_broad_etf_moderate_rvolband_balance_dte35_v1",
    }:
        return c74_opening_compression_option_native_broad_etf_moderate_rvolband_balance_dte35_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c75_opening_compression_option_native_broad_etf_moderate_fastcarry_balance_dte35_v1",
        "c75_broad_etf_moderate_fastcarry_balance",
        "opening_compression_option_native_broad_etf_moderate_fastcarry_balance_dte35_v1",
    }:
        return c75_opening_compression_option_native_broad_etf_moderate_fastcarry_balance_dte35_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c80_opening_compression_option_native_broad_etf_meta_trendfilter_balanced_dte35_v1",
        "c80_broad_etf_meta_trendfilter_balanced",
        "opening_compression_option_native_broad_etf_meta_trendfilter_balanced_dte35_v1",
    }:
        return c80_opening_compression_option_native_broad_etf_meta_trendfilter_balanced_dte35_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c81_opening_compression_option_native_broad_etf_meta_trendfilter_strict_dte35_v1",
        "c81_broad_etf_meta_trendfilter_strict",
        "opening_compression_option_native_broad_etf_meta_trendfilter_strict_dte35_v1",
    }:
        return c81_opening_compression_option_native_broad_etf_meta_trendfilter_strict_dte35_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c82_opening_compression_option_native_broad_etf_meta_trendfilter_rangecap_dte35_v1",
        "c82_broad_etf_meta_trendfilter_rangecap",
        "opening_compression_option_native_broad_etf_meta_trendfilter_rangecap_dte35_v1",
    }:
        return c82_opening_compression_option_native_broad_etf_meta_trendfilter_rangecap_dte35_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c83_opening_compression_option_native_broad_etf_meta_trendpullback_fallback_dte35_v1",
        "c83_broad_etf_meta_trendpullback_fallback",
        "opening_compression_option_native_broad_etf_meta_trendpullback_fallback_dte35_v1",
    }:
        return c83_opening_compression_option_native_broad_etf_meta_trendpullback_fallback_dte35_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c84_opening_compression_option_native_broad_etf_meta_trendmr_fallback_dte35_v1",
        "c84_broad_etf_meta_trendmr_fallback",
        "opening_compression_option_native_broad_etf_meta_trendmr_fallback_dte35_v1",
    }:
        return c84_opening_compression_option_native_broad_etf_meta_trendmr_fallback_dte35_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c85_opening_compression_option_native_broad_etf_meta_trendpullback_rangecap_dte35_v1",
        "c85_broad_etf_meta_trendpullback_rangecap",
        "opening_compression_option_native_broad_etf_meta_trendpullback_rangecap_dte35_v1",
    }:
        return c85_opening_compression_option_native_broad_etf_meta_trendpullback_rangecap_dte35_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c86_opening_compression_option_native_broad_etf_meta_trendmr_fulltrend_fallback_dte35_v1",
        "c86_broad_etf_meta_trendmr_fulltrend_fallback",
        "opening_compression_option_native_broad_etf_meta_trendmr_fulltrend_fallback_dte35_v1",
    }:
        return c86_opening_compression_option_native_broad_etf_meta_trendmr_fulltrend_fallback_dte35_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c87_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_dte35_v1",
        "c87_broad_etf_meta_trendmr_lowconf_guard",
        "opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_dte35_v1",
    }:
        return c87_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_dte35_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c88_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_rangecap_dte35_v1",
        "c88_broad_etf_meta_trendmr_lowconf_guard_rangecap",
        "opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_rangecap_dte35_v1",
    }:
        return c88_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_rangecap_dte35_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c89_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_dte35_v1",
        "c89_broad_etf_meta_trendmr_lowconf_guard_trendcap",
        "opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_dte35_v1",
    }:
        return c89_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_dte35_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c90_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_eventgap_dte35_v1",
        "c90_broad_etf_meta_trendmr_lowconf_guard_eventgap",
        "opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_eventgap_dte35_v1",
    }:
        return c90_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_eventgap_dte35_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c91_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_eventgap_dte35_v1",
        "c91_broad_etf_meta_trendmr_lowconf_guard_trendcap_eventgap",
        "opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_eventgap_dte35_v1",
    }:
        return c91_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_eventgap_dte35_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c92_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_eventgapsoft_dte35_v1",
        "c92_broad_etf_meta_trendmr_lowconf_guard_trendcap_eventgapsoft",
        "opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_eventgapsoft_dte35_v1",
    }:
        return c92_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_eventgapsoft_dte35_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c93_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_eventgapsoft_rangelow_dte35_v1",
        "c93_broad_etf_meta_trendmr_lowconf_guard_trendcap_eventgapsoft_rangelow",
        "opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_eventgapsoft_rangelow_dte35_v1",
    }:
        return c93_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_eventgapsoft_rangelow_dte35_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c94_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_eventgapsoft_rangelow_transition_dte35_v1",
        "c94_broad_etf_meta_trendmr_lowconf_guard_trendcap_eventgapsoft_rangelow_transition",
        "opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_eventgapsoft_rangelow_transition_dte35_v1",
    }:
        return c94_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_eventgapsoft_rangelow_transition_dte35_v1(
            or_width_min=or_width_min
        )
    if normalized in {"c4_momentum_accel_tight_v2", "momentum_accel_tight_v2"}:
        return c4_momentum_accel_tight_v2(or_width_min=or_width_min)
    if normalized in {"c4_mr_vwap_zscore_v3_adaptive", "mr_vwap_zscore_v3_adaptive", "mr_zscore_adaptive"}:
        return c4_mr_vwap_zscore_v3_adaptive(or_width_min=or_width_min)
    if normalized in {"c4_mr_vwap_zscore_v3_adaptive_quality_v1", "mr_zscore_adaptive_quality_v1"}:
        return c4_mr_vwap_zscore_v3_adaptive_quality_v1(or_width_min=or_width_min)
    if normalized in {"c4_lfcm_v1", "lfcm_v1", "lfcm"}:
        return c4_lfcm_v1()
    raise ValueError(f"Unknown ORB profile: {name}")


def build_orb_profile_set(name: str, or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> List[OrbProfile]:
    normalized = str(name or "").strip().lower()
    if normalized in {
        "c40_carver_daily",
        "c40_carver_daily_candidates_v1",
        "carver_daily_candidates",
        "carver_wave01_candidates",
    }:
        return c40_carver_daily_candidates_v1(or_width_min=or_width_min)
    if normalized in {
        "c40_carver_complement",
        "c40_carver_complement_candidates_v1",
        "carver_complement_candidates",
        "carver_low_corr_candidates",
    }:
        return c40_carver_complement_candidates_v1(or_width_min=or_width_min)
    if normalized == "c4_only":
        return [c4_long_only_rr15(or_width_min=or_width_min)]
    if normalized in {"c4_plus_confluence", "c4_candidates"}:
        return [
            c4_long_slip10_v1(or_width_min=or_width_min),
            c4_long_slip10_strict_v1(or_width_min=or_width_min),
            *c4_confluence_candidates(or_width_min=or_width_min),
        ]
    if normalized in {"c4_frequency", "c4_freq"}:
        return c4_frequency_candidates()
    if normalized in {
        "c4_dispersion_relative_breakout_repair",
        "c4_dispersion_relative_breakout_repair_candidates_v1",
        "dispersion_relative_breakout_repair_candidates_v1",
    }:
        return c4_dispersion_relative_breakout_repair_candidates_v1(or_width_min=or_width_min)
    if normalized in {"c4_paper_winners", "paper_winners", "winners"}:
        return c4_paper_winners()
    if normalized in {"c4_recovery_finalists", "c4_recovery", "recovery_finalists", "recovery"}:
        return c4_recovery_finalists()
    if normalized in {
        "c4_long_only_rr15_option_native_v1",
        "c4_long_only_rr15_option_native_candidates_v1",
        "c4_option_native",
        "c4_option_native_candidates",
    }:
        return c4_long_only_rr15_option_native_candidates_v1(or_width_min=or_width_min)
    if normalized in {
        "c4_long_only_rr15_option_native_v2",
        "c4_long_only_rr15_option_native_candidates_v2",
        "c4_option_native_v2",
        "c4_option_native_v2_candidates",
    }:
        return c4_long_only_rr15_option_native_candidates_v2(or_width_min=or_width_min)
    if normalized in {
        "c4_long_only_rr15_put_credit_v1",
        "c4_long_only_rr15_put_credit_candidates_v1",
        "c4_put_credit_v1",
        "c4_put_credit_candidates_v1",
    }:
        return c4_long_only_rr15_put_credit_candidates_v1(or_width_min=or_width_min)
    if normalized in {"c11_proxy_vwap_reclaim", "c11_proxy_vwap_reclaim_candidates", "proxy_vwap_reclaim_candidates"}:
        return c11_proxy_vwap_reclaim_candidates(or_width_min=or_width_min)
    if normalized in {
        "c56_proxy_vwap_reclaim_followup",
        "c56_proxy_vwap_reclaim_followup_candidates_v1",
        "proxy_vwap_reclaim_followup_candidates_v1",
    }:
        return c56_proxy_vwap_reclaim_followup_candidates_v1(or_width_min=or_width_min)
    if normalized in {"c4_breakout_phase89_finalists", "c4_phase89_breakout", "phase89_breakout"}:
        return c4_breakout_phase89_finalists()
    if normalized in {"c5_opening_drive", "c5_opening_drive_candidates", "opening_drive_candidates"}:
        return c5_opening_drive_candidates(or_width_min=or_width_min)
    if normalized in {"c6_opening_exhaustion", "c6_opening_exhaustion_candidates", "opening_exhaustion_candidates"}:
        return c6_opening_exhaustion_candidates(or_width_min=or_width_min)
    if normalized in {"c16_opening_exhaustion", "c16_opening_exhaustion_candidates", "opening_exhaustion_v3_candidates"}:
        return c16_opening_exhaustion_candidates(or_width_min=or_width_min)
    if normalized in {"c17_option_structure_strength", "c17_option_structure_strength_candidates", "option_structure_strength_candidates"}:
        return c17_option_structure_strength_candidates(or_width_min=or_width_min)
    if normalized in {"c18_vwap_mr", "c18_vwap_mr_candidates", "vwap_mr_candidates"}:
        return c18_vwap_mr_candidates(or_width_min=or_width_min)
    if normalized in {"c18_vwap_mr_v2", "c18_vwap_mr_candidates_v2", "vwap_mr_candidates_v2"}:
        return c18_vwap_mr_candidates_v2(or_width_min=or_width_min)
    if normalized in {
        "c4_mr_complement",
        "c4_mr_complement_candidates_v1",
        "mr_complement_candidates",
        "mr_low_corr_candidates",
    }:
        return c4_mr_complement_candidates_v1(or_width_min=or_width_min)
    if normalized in {"c7_opening_failure", "c7_opening_failure_candidates", "opening_failure_candidates"}:
        return c7_opening_failure_candidates(or_width_min=or_width_min)
    if normalized in {"c8_event_drive", "c8_event_drive_candidates", "event_drive_candidates"}:
        return c8_event_drive_candidates(or_width_min=or_width_min)
    if normalized in {"c19_event_drive", "c19_event_drive_candidates", "event_drive_candidates_v3"}:
        return c19_event_drive_candidates(or_width_min=or_width_min)
    if normalized in {
        "c57_event_drive_preopen",
        "c57_event_drive_preopen_candidates_v1",
        "event_drive_preopen_candidates_v1",
    }:
        return c57_event_drive_preopen_candidates_v1(or_width_min=or_width_min)
    if normalized in {"c9_opening_compression", "c9_opening_compression_candidates", "opening_compression_candidates"}:
        return c9_opening_compression_candidates(or_width_min=or_width_min)
    if normalized in {"c21_trend_pullback", "c21_trend_pullback_candidates", "trend_pullback_candidates_v2"}:
        return c21_trend_pullback_candidates(or_width_min=or_width_min)
    if normalized in {"c22_trend_short", "c22_trend_short_candidates", "trend_short_candidates_v2"}:
        return c22_trend_short_candidates(or_width_min=or_width_min)
    if normalized in {"c23_failed_break_reclaim", "c23_failed_break_reclaim_candidates", "failed_break_reclaim_candidates"}:
        return c23_failed_break_reclaim_candidates(or_width_min=or_width_min)
    if normalized in {"c24_pause_go_continuation", "c24_pause_go_continuation_candidates", "pause_go_continuation_candidates"}:
        return c24_pause_go_continuation_candidates(or_width_min=or_width_min)
    if normalized in {"c25_vwap_support_continuation", "c25_vwap_support_continuation_candidates", "vwap_support_continuation_candidates"}:
        return c25_vwap_support_continuation_candidates(or_width_min=or_width_min)
    if normalized in {"c26_gap_reclaim_continuation", "c26_gap_reclaim_continuation_candidates", "gap_reclaim_continuation_candidates"}:
        return c26_gap_reclaim_continuation_candidates(or_width_min=or_width_min)
    if normalized in {"c27_intraday_compression_release", "c27_intraday_compression_release_candidates", "intraday_compression_release_candidates"}:
        return c27_intraday_compression_release_candidates(or_width_min=or_width_min)
    if normalized in {"c28_failed_breakdown_reversal", "c28_failed_breakdown_reversal_candidates", "failed_breakdown_reversal_candidates"}:
        return c28_failed_breakdown_reversal_candidates(or_width_min=or_width_min)
    if normalized in {"c29_open_drive_pullback", "c29_open_drive_pullback_candidates", "open_drive_pullback_candidates"}:
        return c29_open_drive_pullback_candidates(or_width_min=or_width_min)
    if normalized in {"c30_orb_retest_higher_low", "c30_orb_retest_higher_low_candidates", "orb_retest_higher_low_candidates"}:
        return c30_orb_retest_higher_low_candidates(or_width_min=or_width_min)
    if normalized in {"c31_vwap_rollover_short", "c31_vwap_rollover_short_candidates", "vwap_rollover_short_candidates"}:
        return c31_vwap_rollover_short_candidates(or_width_min=or_width_min)
    if normalized in {"c32_gap_up_fail_fade", "c32_gap_up_fail_fade_candidates", "gap_up_fail_fade_candidates"}:
        return c32_gap_up_fail_fade_candidates(or_width_min=or_width_min)
    if normalized in {"c58_opening_compression_consistency", "c58_opening_compression_consistency_candidates_v1"}:
        return c58_opening_compression_consistency_candidates_v1(or_width_min=or_width_min)
    if normalized in {"c59_opening_compression_option_native_consistency", "c59_opening_compression_option_native_consistency_candidates_v1"}:
        return c59_opening_compression_option_native_consistency_candidates_v1(or_width_min=or_width_min)
    if normalized in {"c60_opening_compression_option_native_hybrid", "c60_opening_compression_option_native_hybrid_candidates_v1"}:
        return c60_opening_compression_option_native_hybrid_candidates_v1(or_width_min=or_width_min)
    if normalized in {"c61_opening_compression_stability", "c61_opening_compression_stability_candidates_v1"}:
        return c61_opening_compression_stability_candidates_v1(or_width_min=or_width_min)
    if normalized in {"c62_opening_compression_option_native_stability", "c62_opening_compression_option_native_stability_candidates_v1"}:
        return c62_opening_compression_option_native_stability_candidates_v1(or_width_min=or_width_min)
    if normalized in {"c63_opening_compression_smoother", "c63_opening_compression_smoother_candidates_v1"}:
        return c63_opening_compression_smoother_candidates_v1(or_width_min=or_width_min)
    if normalized in {"c63_opening_compression_option_native", "c63_opening_compression_option_native_candidates_v1"}:
        return c63_opening_compression_option_native_candidates_v1(or_width_min=or_width_min)
    if normalized in {"c64_opening_compression_option_native_dte35", "c64_opening_compression_option_native_dte35_candidates_v1"}:
        return c64_opening_compression_option_native_dte35_candidates_v1(or_width_min=or_width_min)
    if normalized in {"c65_opening_compression_directional", "c65_opening_compression_directional_candidates_v1"}:
        return c65_opening_compression_directional_candidates_v1(or_width_min=or_width_min)
    if normalized in {
        "c65_opening_compression_option_native_directional",
        "c65_opening_compression_option_native_directional_candidates_v1",
    }:
        return c65_opening_compression_option_native_directional_candidates_v1(or_width_min=or_width_min)
    if normalized in {"c66_opening_compression_option_native_dte35", "c66_opening_compression_option_native_dte35_candidates_v1"}:
        return c66_opening_compression_option_native_dte35_candidates_v1(or_width_min=or_width_min)
    if normalized in {
        "c95_opening_compression_option_native_dte35_band22",
        "c95_opening_compression_option_native_dte35_band22_candidates_v1",
    }:
        return c95_opening_compression_option_native_dte35_band22_candidates_v1(or_width_min=or_width_min)
    if normalized in {
        "c66_opening_compression_option_native_dte35_etf_breadth",
        "c66_opening_compression_option_native_dte35_etf_breadth_candidates_v1",
    }:
        return c66_opening_compression_option_native_dte35_etf_breadth_candidates_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c66_opening_compression_option_native_dte35_etf_conversion",
        "c66_opening_compression_option_native_dte35_etf_conversion_candidates_v1",
    }:
        return c66_opening_compression_option_native_dte35_etf_conversion_candidates_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c67_opening_compression_option_native_broad_etf_dte35",
        "c67_opening_compression_option_native_broad_etf_dte35_candidates_v1",
    }:
        return c67_opening_compression_option_native_broad_etf_dte35_candidates_v1(or_width_min=or_width_min)
    if normalized in {
        "c68_opening_compression_option_native_sideways_broad_etf_dte35",
        "c68_opening_compression_option_native_sideways_broad_etf_dte35_candidates_v1",
    }:
        return c68_opening_compression_option_native_sideways_broad_etf_dte35_candidates_v1(or_width_min=or_width_min)
    if normalized in {
        "c69_opening_compression_option_native_broad_etf_quality_dte35",
        "c69_opening_compression_option_native_broad_etf_quality_dte35_candidates_v1",
    }:
        return c69_opening_compression_option_native_broad_etf_quality_dte35_candidates_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c70_opening_compression_option_native_broad_etf_calm_dte35",
        "c70_opening_compression_option_native_broad_etf_calm_dte35_candidates_v1",
    }:
        return c70_opening_compression_option_native_broad_etf_calm_dte35_candidates_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c71_opening_compression_option_native_broad_etf_moderate_dte35",
        "c71_opening_compression_option_native_broad_etf_moderate_dte35_candidates_v1",
    }:
        return c71_opening_compression_option_native_broad_etf_moderate_dte35_candidates_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c72_opening_compression_option_native_broad_etf_moderate_rangecap_dte35",
        "c72_opening_compression_option_native_broad_etf_moderate_rangecap_dte35_candidates_v1",
    }:
        return c72_opening_compression_option_native_broad_etf_moderate_rangecap_dte35_candidates_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c73_opening_compression_option_native_broad_etf_moderate_rvolcap_dte35",
        "c73_opening_compression_option_native_broad_etf_moderate_rvolcap_dte35_candidates_v1",
    }:
        return c73_opening_compression_option_native_broad_etf_moderate_rvolcap_dte35_candidates_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c74_opening_compression_option_native_broad_etf_moderate_rvolband_dte35",
        "c74_opening_compression_option_native_broad_etf_moderate_rvolband_dte35_candidates_v1",
    }:
        return c74_opening_compression_option_native_broad_etf_moderate_rvolband_dte35_candidates_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c75_opening_compression_option_native_broad_etf_moderate_fastcarry_dte35",
        "c75_opening_compression_option_native_broad_etf_moderate_fastcarry_dte35_candidates_v1",
    }:
        return c75_opening_compression_option_native_broad_etf_moderate_fastcarry_dte35_candidates_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c80_opening_compression_option_native_broad_etf_meta_trendfilter_balanced_dte35",
        "c80_opening_compression_option_native_broad_etf_meta_trendfilter_balanced_dte35_candidates_v1",
    }:
        return c80_opening_compression_option_native_broad_etf_meta_trendfilter_balanced_dte35_candidates_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c81_opening_compression_option_native_broad_etf_meta_trendfilter_strict_dte35",
        "c81_opening_compression_option_native_broad_etf_meta_trendfilter_strict_dte35_candidates_v1",
    }:
        return c81_opening_compression_option_native_broad_etf_meta_trendfilter_strict_dte35_candidates_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c82_opening_compression_option_native_broad_etf_meta_trendfilter_rangecap_dte35",
        "c82_opening_compression_option_native_broad_etf_meta_trendfilter_rangecap_dte35_candidates_v1",
    }:
        return c82_opening_compression_option_native_broad_etf_meta_trendfilter_rangecap_dte35_candidates_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c83_opening_compression_option_native_broad_etf_meta_trendpullback_fallback_dte35",
        "c83_opening_compression_option_native_broad_etf_meta_trendpullback_fallback_dte35_candidates_v1",
    }:
        return c83_opening_compression_option_native_broad_etf_meta_trendpullback_fallback_dte35_candidates_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c84_opening_compression_option_native_broad_etf_meta_trendmr_fallback_dte35",
        "c84_opening_compression_option_native_broad_etf_meta_trendmr_fallback_dte35_candidates_v1",
    }:
        return c84_opening_compression_option_native_broad_etf_meta_trendmr_fallback_dte35_candidates_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c85_opening_compression_option_native_broad_etf_meta_trendpullback_rangecap_dte35",
        "c85_opening_compression_option_native_broad_etf_meta_trendpullback_rangecap_dte35_candidates_v1",
    }:
        return c85_opening_compression_option_native_broad_etf_meta_trendpullback_rangecap_dte35_candidates_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c86_opening_compression_option_native_broad_etf_meta_trendmr_fulltrend_fallback_dte35",
        "c86_opening_compression_option_native_broad_etf_meta_trendmr_fulltrend_fallback_dte35_candidates_v1",
    }:
        return c86_opening_compression_option_native_broad_etf_meta_trendmr_fulltrend_fallback_dte35_candidates_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c87_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_dte35",
        "c87_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_dte35_candidates_v1",
    }:
        return c87_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_dte35_candidates_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c88_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_rangecap_dte35",
        "c88_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_rangecap_dte35_candidates_v1",
    }:
        return c88_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_rangecap_dte35_candidates_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c89_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_dte35",
        "c89_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_dte35_candidates_v1",
    }:
        return c89_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_dte35_candidates_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c90_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_eventgap_dte35",
        "c90_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_eventgap_dte35_candidates_v1",
    }:
        return c90_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_eventgap_dte35_candidates_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c91_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_eventgap_dte35",
        "c91_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_eventgap_dte35_candidates_v1",
    }:
        return c91_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_eventgap_dte35_candidates_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c92_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_eventgapsoft_dte35",
        "c92_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_eventgapsoft_dte35_candidates_v1",
    }:
        return c92_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_eventgapsoft_dte35_candidates_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c93_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_eventgapsoft_rangelow_dte35",
        "c93_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_eventgapsoft_rangelow_dte35_candidates_v1",
    }:
        return c93_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_eventgapsoft_rangelow_dte35_candidates_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c94_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_eventgapsoft_rangelow_transition_dte35",
        "c94_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_eventgapsoft_rangelow_transition_dte35_candidates_v1",
    }:
        return c94_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_eventgapsoft_rangelow_transition_dte35_candidates_v1(
            or_width_min=or_width_min
        )
    if normalized in {"c10_relative_strength", "c10_relative_strength_candidates", "relative_strength_candidates"}:
        return c10_relative_strength_candidates(or_width_min=or_width_min)
    if normalized in {"c12_relative_strength", "c12_relative_strength_candidates", "relative_strength_candidates_v2"}:
        return c12_relative_strength_candidates(or_width_min=or_width_min)
    if normalized in {"c12_relative_strength_quote", "c12_relative_strength_quote_candidates_v2", "relative_strength_quote_candidates_v2"}:
        return c12_relative_strength_quote_candidates_v2(or_width_min=or_width_min)
    if normalized in {
        "c12_relative_strength_option_native",
        "c12_relative_strength_option_native_candidates_v3",
        "relative_strength_option_native_candidates_v3",
    }:
        return c12_relative_strength_option_native_candidates_v3(or_width_min=or_width_min)
    if normalized in {
        "c19_relative_strength_debit_spread",
        "c19_relative_strength_debit_spread_candidates_v1",
        "relative_strength_debit_spread_candidates_v1",
    }:
        return c19_relative_strength_debit_spread_candidates_v1(or_width_min=or_width_min)
    if normalized in {
        "c19_relative_strength_debit_spread_v2",
        "c19_relative_strength_debit_spread_candidates_v2",
        "relative_strength_debit_spread_candidates_v2",
    }:
        return c19_relative_strength_debit_spread_candidates_v2(or_width_min=or_width_min)
    if normalized in {"c13_orb_fib_pullback", "c13_orb_fib_pullback_candidates", "orb_fib_pullback_candidates", "fib_pullback_candidates"}:
        return c13_orb_fib_pullback_candidates(or_width_min=or_width_min)
    if normalized in {
        "c14_gap_rejection",
        "c14_gap_rejection_candidates",
        "gap_rejection_candidates",
    }:
        return c14_gap_rejection_candidates(or_width_min=or_width_min)
    if normalized in {
        "c15_failure_fade",
        "c15_failure_fade_candidates",
        "failure_fade_candidates",
    }:
        return c15_failure_fade_candidates(or_width_min=or_width_min)
    if normalized in {
        "c4_dispersion_relative_revert",
        "c4_dispersion_relative_revert_candidates_v1",
        "dispersion_relative_revert_candidates",
        "dispersion_low_corr_candidates",
    }:
        return c4_dispersion_relative_revert_candidates_v1(or_width_min=or_width_min)
    raise ValueError(f"Unknown ORB profile set: {name}")


from . import opening_range_profiles_registry as _opening_range_profiles_registry

OpeningRangeProfile = OrbProfile
get_opening_range_profile = _opening_range_profiles_registry.get_opening_range_profile
build_opening_range_profile_set = _opening_range_profiles_registry.build_opening_range_profile_set
get_orb_profile = get_opening_range_profile
build_orb_profile_set = build_opening_range_profile_set
