from __future__ import annotations

from dataclasses import replace
from typing import List

from .opening_range_profiles_core import DEFAULT_OR_WIDTH_MIN, OrbProfile


def apply_carver_daily_wrapper_v1(
    profile: OrbProfile,
    *,
    forecast_family: str,
    forecast_group: str,
    strategy_sleeve: str,
    forecast_weight: float,
    risk_budget_share: float,
    overlay_enabled: bool = False,
) -> OrbProfile:
    return replace(
        profile,
        signal_cadence="daily_eod",
        strategy_sleeve=str(strategy_sleeve),
        forecast_group=str(forecast_group),
        forecast_family=str(forecast_family),
        forecast_weight=float(forecast_weight),
        option_structure_mode="single_leg",
        require_option_microstructure_filter=False,
        option_min_dte=21,
        option_target_dte=45,
        option_max_dte=75,
        option_min_open_interest=50,
        option_selection_intrinsic_weight=6.0,
        option_selection_min_intrinsic_share=0.10,
        option_selection_delta_weight=3.0,
        option_selection_target_abs_delta=0.55,
        option_selection_min_abs_delta=0.0,
        option_selection_max_abs_delta=1.0,
        option_min_expected_move_to_extrinsic_ratio=1.2,
        option_min_expected_move_to_spread_ratio=4.0,
        option_microstructure_gate_mode="coverage_speed_limit",
        option_tradability_availability_mode="vendor_limited_current_proxy",
        option_min_quote_coverage_pct=0.80,
        option_min_chain_coverage_pct=0.80,
        option_liquidity_sampling_days=90,
        option_cost_speed_limit_ratio=999.0,
        option_tradeable_after_sample_days=1,
        portfolio_target_vol_annualized=0.10,
        premium_at_risk_pct_nav_cap=0.0035,
        total_premium_at_risk_pct_nav_cap=0.025,
        risk_budget_share=float(risk_budget_share),
        max_calendar_hold_days=30,
        overlay_enabled=bool(overlay_enabled),
        overlay_ivrv_scale_down_zscore=1.0,
        overlay_ivrv_scale_up_zscore=-0.5,
        overlay_ivrv_scale_down_multiplier=0.50,
        overlay_ivrv_scale_up_multiplier=1.15,
        overlay_term_structure_veto_threshold=0.04,
        overlay_skew_veto_threshold=0.12,
        take_profit_rr=0.0,
        break_even_trigger_rr=0.0,
        exit_on_opposite_candle=False,
        early_fail_minutes=0,
        max_hold_minutes=0,
    )


def _carver_daily_profile(
    *,
    name: str,
    description: str,
    forecast_family: str,
    forecast_group: str,
    strategy_sleeve: str = "core_daily",
    forecast_weight: float = 1.0,
    risk_budget_share: float = 0.70,
    overlay_enabled: bool = False,
    allow_long: bool = True,
    allow_short: bool = True,
    lookback_fast: int = 16,
    lookback_slow: int = 64,
    lookback_breakout: int = 40,
    lookback_relative: int = 63,
) -> OrbProfile:
    base = OrbProfile(
        name=name,
        description=description,
        strategy_variant="daily_forecast_v1",
        allow_long=bool(allow_long),
        allow_short=bool(allow_short),
        lookback_fast=int(lookback_fast),
        lookback_slow=int(lookback_slow),
        lookback_breakout=int(lookback_breakout),
        lookback_relative=int(lookback_relative),
        forecast_cap=20.0,
        vol_attenuation_enabled=forecast_family in {
            "c40_daily_ewmac_fast_v1",
            "c41_daily_ewmac_slow_v1",
            "c42_daily_breakout_medium_v1",
            "c43_daily_breakout_slow_v1",
            "c52_daily_trend_pullback_v1",
            "c50_carver_core_combo_v1",
            "c51_carver_hybrid_portfolio_v1",
        },
        vol_percentile_lookback=252,
        vol_attenuation_hi_pct=80.0,
        vol_attenuation_extreme_pct=90.0,
    )
    return apply_carver_daily_wrapper_v1(
        base,
        forecast_family=forecast_family,
        forecast_group=forecast_group,
        strategy_sleeve=str(strategy_sleeve),
        forecast_weight=float(forecast_weight),
        risk_budget_share=float(risk_budget_share),
        overlay_enabled=bool(overlay_enabled),
    )


def c40_daily_ewmac_fast_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    return _carver_daily_profile(
        name="c40_daily_ewmac_fast_v1",
        description="Fast EWMAC daily forecast expressed through liquid single-leg options.",
        forecast_family="c40_daily_ewmac_fast_v1",
        forecast_group="trendy",
        forecast_weight=0.15,
        lookback_fast=16,
        lookback_slow=64,
    )


def c41_daily_ewmac_slow_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    return _carver_daily_profile(
        name="c41_daily_ewmac_slow_v1",
        description="Slow EWMAC daily forecast expressed through liquid single-leg options.",
        forecast_family="c41_daily_ewmac_slow_v1",
        forecast_group="trendy",
        forecast_weight=0.20,
        lookback_fast=32,
        lookback_slow=128,
    )


def c42_daily_breakout_medium_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    return _carver_daily_profile(
        name="c42_daily_breakout_medium_v1",
        description="Medium-horizon daily breakout forecast wrapped in long-premium options.",
        forecast_family="c42_daily_breakout_medium_v1",
        forecast_group="trendy",
        forecast_weight=0.10,
        lookback_breakout=40,
    )


def c43_daily_breakout_slow_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    return _carver_daily_profile(
        name="c43_daily_breakout_slow_v1",
        description="Slow breakout daily forecast wrapped in longer-dated options.",
        forecast_family="c43_daily_breakout_slow_v1",
        forecast_group="trendy",
        forecast_weight=0.20,
        lookback_breakout=80,
    )


def c52_daily_trend_pullback_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    return replace(
        _carver_daily_profile(
            name="c52_daily_trend_pullback_v1",
            description="ETF trend-pullback daily forecast expressed through 3-5 day swing options.",
            forecast_family="c52_daily_trend_pullback_v1",
            forecast_group="trendy",
            forecast_weight=1.0,
            lookback_fast=8,
            lookback_slow=21,
        ),
        option_min_dte=14,
        option_target_dte=30,
        option_max_dte=45,
        option_selection_min_intrinsic_share=0.05,
        option_selection_target_abs_delta=0.45,
        max_calendar_hold_days=5,
    )


def c44_daily_relmom_bucket_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    return _carver_daily_profile(
        name="c44_daily_relmom_bucket_v1",
        description="Cross-sectional relative momentum within liquid ETF asset buckets.",
        forecast_family="c44_daily_relmom_bucket_v1",
        forecast_group="diversifier",
        forecast_weight=0.20,
        lookback_relative=63,
    )


def c45_daily_assettrend_bucket_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    return _carver_daily_profile(
        name="c45_daily_assettrend_bucket_v1",
        description="Bucket-level asset trend forecast for diversified ETF sleeves.",
        forecast_family="c45_daily_assettrend_bucket_v1",
        forecast_group="diversifier",
        forecast_weight=0.15,
        lookback_relative=63,
    )


def c46_surface_ivrv_overlay_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    return _carver_daily_profile(
        name="c46_surface_ivrv_overlay_v1",
        description="Overlay-only IV versus realized-vol richness monitor for premium buys.",
        forecast_family="c46_surface_ivrv_overlay_v1",
        forecast_group="surface_overlay",
        strategy_sleeve="surface_overlay",
        forecast_weight=1.0,
        risk_budget_share=0.20,
        overlay_enabled=True,
    )


def c47_surface_term_structure_overlay_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    return _carver_daily_profile(
        name="c47_surface_term_structure_overlay_v1",
        description="Overlay-only front/back term-structure veto lane for long-premium trades.",
        forecast_family="c47_surface_term_structure_overlay_v1",
        forecast_group="surface_overlay",
        strategy_sleeve="surface_overlay",
        forecast_weight=1.0,
        risk_budget_share=0.20,
        overlay_enabled=True,
    )


def c48_surface_skew_overlay_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    return _carver_daily_profile(
        name="c48_surface_skew_overlay_v1",
        description="Overlay-only skew veto lane for adverse wing pricing in premium buys.",
        forecast_family="c48_surface_skew_overlay_v1",
        forecast_group="surface_overlay",
        strategy_sleeve="surface_overlay",
        forecast_weight=1.0,
        risk_budget_share=0.20,
        overlay_enabled=True,
    )


def c50_carver_core_combo_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    return _carver_daily_profile(
        name="c50_carver_core_combo_v1",
        description="Hand-weighted Carver-style daily combo across trend and bucket diversifiers.",
        forecast_family="c50_carver_core_combo_v1",
        forecast_group="combo",
        strategy_sleeve="core_daily",
        forecast_weight=1.0,
        risk_budget_share=0.70,
        overlay_enabled=False,
    )


def c51_carver_hybrid_portfolio_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    return replace(
        _carver_daily_profile(
            name="c51_carver_hybrid_portfolio_v1",
            description="Hybrid daily combo with options-surface overlay and tactical sleeve budget metadata.",
            forecast_family="c51_carver_hybrid_portfolio_v1",
            forecast_group="combo",
            strategy_sleeve="core_daily",
            forecast_weight=1.0,
            risk_budget_share=0.70,
            overlay_enabled=True,
        ),
        hybrid_core_weight=0.70,
        hybrid_overlay_weight=0.20,
        hybrid_tactical_weight=0.10,
        hybrid_tactical_profiles="c4_long_only_rr15_recovery_v2,c18_vwap_mr_quality_v1,c4_orb_trend_short_v1",
    )


def c40_carver_daily_candidates_v1(or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> List[OrbProfile]:
    return [
        c40_daily_ewmac_fast_v1(or_width_min=or_width_min),
        c41_daily_ewmac_slow_v1(or_width_min=or_width_min),
        c42_daily_breakout_medium_v1(or_width_min=or_width_min),
        c43_daily_breakout_slow_v1(or_width_min=or_width_min),
        c52_daily_trend_pullback_v1(or_width_min=or_width_min),
        c44_daily_relmom_bucket_v1(or_width_min=or_width_min),
        c45_daily_assettrend_bucket_v1(or_width_min=or_width_min),
        c46_surface_ivrv_overlay_v1(or_width_min=or_width_min),
        c47_surface_term_structure_overlay_v1(or_width_min=or_width_min),
        c48_surface_skew_overlay_v1(or_width_min=or_width_min),
        c50_carver_core_combo_v1(or_width_min=or_width_min),
        c51_carver_hybrid_portfolio_v1(or_width_min=or_width_min),
    ]
