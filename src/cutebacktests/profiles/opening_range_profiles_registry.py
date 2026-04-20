from __future__ import annotations

import importlib
import sys

from .opening_range_profiles_core import DEFAULT_OR_WIDTH_MIN, OrbProfile

try:
    _profiles = importlib.import_module("cutebacktests.profiles.opening_range_profiles")
except Exception:
    _profiles = sys.modules.get("cutebacktests.profiles.opening_range_profiles") or sys.modules.get("__main__")
if _profiles is not None:
    for _name, _value in vars(_profiles).items():
        if _name.startswith("__"):
            continue
        globals().setdefault(_name, _value)


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
    if normalized in {"c33_gap_rejection_option_native_balance_v1", "c33_balance"}:
        return c33_gap_rejection_option_native_balance_v1(or_width_min=or_width_min)
    if normalized in {"c33_gap_rejection_option_native_quality_v1", "c33_quality"}:
        return c33_gap_rejection_option_native_quality_v1(or_width_min=or_width_min)
    if normalized in {"c33_gap_rejection_option_native_opportunity_v1", "c33_opportunity"}:
        return c33_gap_rejection_option_native_opportunity_v1(or_width_min=or_width_min)
    if normalized in {"c33_gap_rejection_option_native_regime_v1", "c33_regime"}:
        return c33_gap_rejection_option_native_regime_v1(or_width_min=or_width_min)
    if normalized in {"c33_gap_rejection_option_native_long_only_v1", "c33_long_only"}:
        return c33_gap_rejection_option_native_long_only_v1(or_width_min=or_width_min)
    if normalized in {"c34_failure_fade_option_native_balance_v1", "c34_balance"}:
        return c34_failure_fade_option_native_balance_v1(or_width_min=or_width_min)
    if normalized in {"c34_failure_fade_option_native_quality_v1", "c34_quality"}:
        return c34_failure_fade_option_native_quality_v1(or_width_min=or_width_min)
    if normalized in {"c34_failure_fade_option_native_regime_v1", "c34_regime"}:
        return c34_failure_fade_option_native_regime_v1(or_width_min=or_width_min)
    if normalized in {"c34_failure_fade_option_native_fast_v1", "c34_fast"}:
        return c34_failure_fade_option_native_fast_v1(or_width_min=or_width_min)
    if normalized in {"c34_failure_fade_option_native_long_only_v1", "c34_long_only"}:
        return c34_failure_fade_option_native_long_only_v1(or_width_min=or_width_min)
    if normalized in {"c35_failed_break_reclaim_option_native_balance_v1", "c35_balance"}:
        return c35_failed_break_reclaim_option_native_balance_v1(or_width_min=or_width_min)
    if normalized in {"c35_failed_break_reclaim_option_native_quality_v1", "c35_quality"}:
        return c35_failed_break_reclaim_option_native_quality_v1(or_width_min=or_width_min)
    if normalized in {"c35_failed_break_reclaim_option_native_regime_v1", "c35_regime"}:
        return c35_failed_break_reclaim_option_native_regime_v1(or_width_min=or_width_min)
    if normalized in {"c36_vwap_mr_option_native_balance_v1", "c36_balance"}:
        return c36_vwap_mr_option_native_balance_v1(or_width_min=or_width_min)
    if normalized in {"c36_vwap_mr_option_native_quality_v1", "c36_quality"}:
        return c36_vwap_mr_option_native_quality_v1(or_width_min=or_width_min)
    if normalized in {"c36_vwap_mr_option_native_regime_v1", "c36_regime"}:
        return c36_vwap_mr_option_native_regime_v1(or_width_min=or_width_min)
    if normalized in {"c36_vwap_mr_option_native_opportunity_v1", "c36_opportunity"}:
        return c36_vwap_mr_option_native_opportunity_v1(or_width_min=or_width_min)
    if normalized in {"c36_vwap_mr_option_native_fast_v1", "c36_fast"}:
        return c36_vwap_mr_option_native_fast_v1(or_width_min=or_width_min)
    if normalized in {"c55_vwap_mr_option_native_density_v1", "c55_density"}:
        return c55_vwap_mr_option_native_density_v1(or_width_min=or_width_min)
    if normalized in {"c55_vwap_mr_option_native_density_regime_v1", "c55_density_regime"}:
        return c55_vwap_mr_option_native_density_regime_v1(or_width_min=or_width_min)
    if normalized in {"c55_vwap_mr_option_native_opportunity_guard_v1", "c55_opportunity_guard"}:
        return c55_vwap_mr_option_native_opportunity_guard_v1(or_width_min=or_width_min)
    if normalized in {"c37_vwap_mr_debit_spread_balance_v1", "c37_balance"}:
        return c37_vwap_mr_debit_spread_balance_v1(or_width_min=or_width_min)
    if normalized in {"c37_vwap_mr_debit_spread_quality_v1", "c37_quality"}:
        return c37_vwap_mr_debit_spread_quality_v1(or_width_min=or_width_min)
    if normalized in {"c37_vwap_mr_debit_spread_regime_v1", "c37_regime"}:
        return c37_vwap_mr_debit_spread_regime_v1(or_width_min=or_width_min)
    if normalized in {"c52_opening_compression_option_native_balance_v1", "c52_balance"}:
        return c52_opening_compression_option_native_balance_v1(or_width_min=or_width_min)
    if normalized in {"c52_opening_compression_option_native_long_only_v1", "c52_long_only"}:
        return c52_opening_compression_option_native_long_only_v1(or_width_min=or_width_min)
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
    if normalized in {
        "c65_opening_compression_short_quality_v1",
        "opening_compression_short_quality_v1",
        "c65_short_quality",
    }:
        return c65_opening_compression_short_quality_v1(or_width_min=or_width_min)
    if normalized in {
        "c65_opening_compression_long_balance_v1",
        "opening_compression_long_balance_v1",
        "c65_long_balance",
    }:
        return c65_opening_compression_long_balance_v1(or_width_min=or_width_min)
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
        return c69_opening_compression_option_native_broad_etf_quality_balance_dte35_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c70_opening_compression_option_native_broad_etf_calm_balance_dte35_v1",
        "c70_broad_etf_calm_balance",
        "opening_compression_option_native_broad_etf_calm_balance_dte35_v1",
    }:
        return c70_opening_compression_option_native_broad_etf_calm_balance_dte35_v1(
            or_width_min=or_width_min
        )
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
        "c76_opening_compression_option_native_broad_etf_meta_rv_defensive_dte35_v1",
        "c76_broad_etf_meta_rv_defensive",
        "opening_compression_option_native_broad_etf_meta_rv_defensive_dte35_v1",
    }:
        return c76_opening_compression_option_native_broad_etf_meta_rv_defensive_dte35_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c77_opening_compression_option_native_broad_etf_meta_rv_defensive_rangecap_dte35_v1",
        "c77_broad_etf_meta_rv_defensive_rangecap",
        "opening_compression_option_native_broad_etf_meta_rv_defensive_rangecap_dte35_v1",
    }:
        return c77_opening_compression_option_native_broad_etf_meta_rv_defensive_rangecap_dte35_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c78_opening_compression_option_native_broad_etf_meta_rv_defensive_rvolcap_dte35_v1",
        "c78_broad_etf_meta_rv_defensive_rvolcap",
        "opening_compression_option_native_broad_etf_meta_rv_defensive_rvolcap_dte35_v1",
    }:
        return c78_opening_compression_option_native_broad_etf_meta_rv_defensive_rvolcap_dte35_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c79_opening_compression_option_native_broad_etf_gapdown_eventdrive_dte35_v1",
        "c79_broad_etf_gapdown_eventdrive",
        "opening_compression_option_native_broad_etf_gapdown_eventdrive_dte35_v1",
    }:
        return c79_opening_compression_option_native_broad_etf_gapdown_eventdrive_dte35_v1(
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
    if normalized in {
        "c58_opening_compression_consistency",
        "c58_opening_compression_consistency_candidates_v1",
        "opening_compression_consistency_candidates_v1",
    }:
        return c58_opening_compression_consistency_candidates_v1(or_width_min=or_width_min)
    if normalized in {
        "c61_opening_compression_stability",
        "c61_opening_compression_stability_candidates_v1",
        "opening_compression_stability_candidates_v1",
    }:
        return c61_opening_compression_stability_candidates_v1(or_width_min=or_width_min)
    if normalized in {
        "c63_opening_compression_smoother",
        "c63_opening_compression_smoother_candidates_v1",
        "opening_compression_smoother_candidates_v1",
    }:
        return c63_opening_compression_smoother_candidates_v1(or_width_min=or_width_min)
    if normalized in {
        "c65_opening_compression_directional",
        "c65_opening_compression_directional_candidates_v1",
        "opening_compression_directional_candidates_v1",
    }:
        return c65_opening_compression_directional_candidates_v1(or_width_min=or_width_min)
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
    if normalized in {
        "c33_gap_rejection_option_native",
        "c33_gap_rejection_option_native_candidates_v1",
        "gap_rejection_option_native_candidates_v1",
    }:
        return c33_gap_rejection_option_native_candidates_v1(or_width_min=or_width_min)
    if normalized in {
        "c34_failure_fade_option_native",
        "c34_failure_fade_option_native_candidates_v1",
        "failure_fade_option_native_candidates_v1",
    }:
        return c34_failure_fade_option_native_candidates_v1(or_width_min=or_width_min)
    if normalized in {
        "c35_failed_break_reclaim_option_native",
        "c35_failed_break_reclaim_option_native_candidates_v1",
        "failed_break_reclaim_option_native_candidates_v1",
    }:
        return c35_failed_break_reclaim_option_native_candidates_v1(or_width_min=or_width_min)
    if normalized in {
        "c36_vwap_mr_option_native",
        "c36_vwap_mr_option_native_candidates_v1",
        "vwap_mr_option_native_candidates_v1",
    }:
        return c36_vwap_mr_option_native_candidates_v1(or_width_min=or_width_min)
    if normalized in {
        "c55_vwap_mr_option_native",
        "c55_vwap_mr_option_native_candidates_v1",
        "vwap_mr_option_native_candidates_v2",
    }:
        return c55_vwap_mr_option_native_candidates_v1(or_width_min=or_width_min)
    if normalized in {
        "c37_vwap_mr_debit_spread",
        "c37_vwap_mr_debit_spread_candidates_v1",
        "vwap_mr_debit_spread_candidates_v1",
    }:
        return c37_vwap_mr_debit_spread_candidates_v1(or_width_min=or_width_min)
    if normalized in {
        "c52_opening_compression_option_native",
        "c52_opening_compression_option_native_candidates_v1",
        "opening_compression_option_native_candidates_v1",
    }:
        return c52_opening_compression_option_native_candidates_v1(or_width_min=or_width_min)
    if normalized in {
        "c53_intraday_compression_release_option_native",
        "c53_intraday_compression_release_option_native_candidates_v1",
        "intraday_compression_release_option_native_candidates_v1",
    }:
        return c53_intraday_compression_release_option_native_candidates_v1(or_width_min=or_width_min)
    if normalized in {
        "c54_opening_compression_option_native_dte35",
        "c54_opening_compression_option_native_dte35_candidates_v1",
        "opening_compression_option_native_dte35_candidates_v1",
    }:
        return c54_opening_compression_option_native_dte35_candidates_v1(or_width_min=or_width_min)
    if normalized in {
        "c59_opening_compression_option_native_consistency",
        "c59_opening_compression_option_native_consistency_candidates_v1",
        "opening_compression_option_native_consistency_candidates_v1",
    }:
        return c59_opening_compression_option_native_consistency_candidates_v1(or_width_min=or_width_min)
    if normalized in {
        "c60_opening_compression_option_native_hybrid",
        "c60_opening_compression_option_native_hybrid_candidates_v1",
        "opening_compression_option_native_hybrid_candidates_v1",
    }:
        return c60_opening_compression_option_native_hybrid_candidates_v1(or_width_min=or_width_min)
    if normalized in {
        "c62_opening_compression_option_native_stability",
        "c62_opening_compression_option_native_stability_candidates_v1",
        "opening_compression_option_native_stability_candidates_v1",
    }:
        return c62_opening_compression_option_native_stability_candidates_v1(or_width_min=or_width_min)
    if normalized in {
        "c63_opening_compression_option_native",
        "c63_opening_compression_option_native_candidates_v1",
        "opening_compression_option_native_smoother_candidates_v1",
    }:
        return c63_opening_compression_option_native_candidates_v1(or_width_min=or_width_min)
    if normalized in {
        "c64_opening_compression_option_native_dte35",
        "c64_opening_compression_option_native_dte35_candidates_v1",
        "opening_compression_option_native_dte35_candidates_v2",
    }:
        return c64_opening_compression_option_native_dte35_candidates_v1(or_width_min=or_width_min)
    if normalized in {
        "c65_opening_compression_option_native_directional",
        "c65_opening_compression_option_native_directional_candidates_v1",
        "opening_compression_option_native_directional_candidates_v1",
    }:
        return c65_opening_compression_option_native_directional_candidates_v1(or_width_min=or_width_min)
    if normalized in {
        "c66_opening_compression_option_native_dte35",
        "c66_opening_compression_option_native_dte35_candidates_v1",
        "opening_compression_option_native_short_dte35_candidates_v1",
    }:
        return c66_opening_compression_option_native_dte35_candidates_v1(or_width_min=or_width_min)
    if normalized in {
        "c95_opening_compression_option_native_dte35_band22",
        "c95_opening_compression_option_native_dte35_band22_candidates_v1",
        "opening_compression_option_native_short_dte35_band22_candidates_v1",
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
        "opening_compression_option_native_broad_etf_dte35_candidates_v1",
    }:
        return c67_opening_compression_option_native_broad_etf_dte35_candidates_v1(or_width_min=or_width_min)
    if normalized in {
        "c68_opening_compression_option_native_sideways_broad_etf_dte35",
        "c68_opening_compression_option_native_sideways_broad_etf_dte35_candidates_v1",
        "opening_compression_option_native_sideways_broad_etf_dte35_candidates_v1",
    }:
        return c68_opening_compression_option_native_sideways_broad_etf_dte35_candidates_v1(or_width_min=or_width_min)
    if normalized in {
        "c69_opening_compression_option_native_broad_etf_quality_dte35",
        "c69_opening_compression_option_native_broad_etf_quality_dte35_candidates_v1",
        "opening_compression_option_native_broad_etf_quality_dte35_candidates_v1",
    }:
        return c69_opening_compression_option_native_broad_etf_quality_dte35_candidates_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c70_opening_compression_option_native_broad_etf_calm_dte35",
        "c70_opening_compression_option_native_broad_etf_calm_dte35_candidates_v1",
        "opening_compression_option_native_broad_etf_calm_dte35_candidates_v1",
    }:
        return c70_opening_compression_option_native_broad_etf_calm_dte35_candidates_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c71_opening_compression_option_native_broad_etf_moderate_dte35",
        "c71_opening_compression_option_native_broad_etf_moderate_dte35_candidates_v1",
        "opening_compression_option_native_broad_etf_moderate_dte35_candidates_v1",
    }:
        return c71_opening_compression_option_native_broad_etf_moderate_dte35_candidates_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c72_opening_compression_option_native_broad_etf_moderate_rangecap_dte35",
        "c72_opening_compression_option_native_broad_etf_moderate_rangecap_dte35_candidates_v1",
        "opening_compression_option_native_broad_etf_moderate_rangecap_dte35_candidates_v1",
    }:
        return c72_opening_compression_option_native_broad_etf_moderate_rangecap_dte35_candidates_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c73_opening_compression_option_native_broad_etf_moderate_rvolcap_dte35",
        "c73_opening_compression_option_native_broad_etf_moderate_rvolcap_dte35_candidates_v1",
        "opening_compression_option_native_broad_etf_moderate_rvolcap_dte35_candidates_v1",
    }:
        return c73_opening_compression_option_native_broad_etf_moderate_rvolcap_dte35_candidates_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c74_opening_compression_option_native_broad_etf_moderate_rvolband_dte35",
        "c74_opening_compression_option_native_broad_etf_moderate_rvolband_dte35_candidates_v1",
        "opening_compression_option_native_broad_etf_moderate_rvolband_dte35_candidates_v1",
    }:
        return c74_opening_compression_option_native_broad_etf_moderate_rvolband_dte35_candidates_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c75_opening_compression_option_native_broad_etf_moderate_fastcarry_dte35",
        "c75_opening_compression_option_native_broad_etf_moderate_fastcarry_dte35_candidates_v1",
        "opening_compression_option_native_broad_etf_moderate_fastcarry_dte35_candidates_v1",
    }:
        return c75_opening_compression_option_native_broad_etf_moderate_fastcarry_dte35_candidates_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c76_opening_compression_option_native_broad_etf_meta_rv_defensive_dte35",
        "c76_opening_compression_option_native_broad_etf_meta_rv_defensive_dte35_candidates_v1",
        "opening_compression_option_native_broad_etf_meta_rv_defensive_dte35_candidates_v1",
    }:
        return c76_opening_compression_option_native_broad_etf_meta_rv_defensive_dte35_candidates_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c77_opening_compression_option_native_broad_etf_meta_rv_defensive_rangecap_dte35",
        "c77_opening_compression_option_native_broad_etf_meta_rv_defensive_rangecap_dte35_candidates_v1",
        "opening_compression_option_native_broad_etf_meta_rv_defensive_rangecap_dte35_candidates_v1",
    }:
        return c77_opening_compression_option_native_broad_etf_meta_rv_defensive_rangecap_dte35_candidates_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c78_opening_compression_option_native_broad_etf_meta_rv_defensive_rvolcap_dte35",
        "c78_opening_compression_option_native_broad_etf_meta_rv_defensive_rvolcap_dte35_candidates_v1",
        "opening_compression_option_native_broad_etf_meta_rv_defensive_rvolcap_dte35_candidates_v1",
    }:
        return c78_opening_compression_option_native_broad_etf_meta_rv_defensive_rvolcap_dte35_candidates_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c79_opening_compression_option_native_broad_etf_gapdown_eventdrive_dte35",
        "c79_opening_compression_option_native_broad_etf_gapdown_eventdrive_dte35_candidates_v1",
        "opening_compression_option_native_broad_etf_gapdown_eventdrive_dte35_candidates_v1",
    }:
        return c79_opening_compression_option_native_broad_etf_gapdown_eventdrive_dte35_candidates_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c80_opening_compression_option_native_broad_etf_meta_trendfilter_balanced_dte35",
        "c80_opening_compression_option_native_broad_etf_meta_trendfilter_balanced_dte35_candidates_v1",
        "opening_compression_option_native_broad_etf_meta_trendfilter_balanced_dte35_candidates_v1",
    }:
        return c80_opening_compression_option_native_broad_etf_meta_trendfilter_balanced_dte35_candidates_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c81_opening_compression_option_native_broad_etf_meta_trendfilter_strict_dte35",
        "c81_opening_compression_option_native_broad_etf_meta_trendfilter_strict_dte35_candidates_v1",
        "opening_compression_option_native_broad_etf_meta_trendfilter_strict_dte35_candidates_v1",
    }:
        return c81_opening_compression_option_native_broad_etf_meta_trendfilter_strict_dte35_candidates_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c82_opening_compression_option_native_broad_etf_meta_trendfilter_rangecap_dte35",
        "c82_opening_compression_option_native_broad_etf_meta_trendfilter_rangecap_dte35_candidates_v1",
        "opening_compression_option_native_broad_etf_meta_trendfilter_rangecap_dte35_candidates_v1",
    }:
        return c82_opening_compression_option_native_broad_etf_meta_trendfilter_rangecap_dte35_candidates_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c83_opening_compression_option_native_broad_etf_meta_trendpullback_fallback_dte35",
        "c83_opening_compression_option_native_broad_etf_meta_trendpullback_fallback_dte35_candidates_v1",
        "opening_compression_option_native_broad_etf_meta_trendpullback_fallback_dte35_candidates_v1",
    }:
        return c83_opening_compression_option_native_broad_etf_meta_trendpullback_fallback_dte35_candidates_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c84_opening_compression_option_native_broad_etf_meta_trendmr_fallback_dte35",
        "c84_opening_compression_option_native_broad_etf_meta_trendmr_fallback_dte35_candidates_v1",
        "opening_compression_option_native_broad_etf_meta_trendmr_fallback_dte35_candidates_v1",
    }:
        return c84_opening_compression_option_native_broad_etf_meta_trendmr_fallback_dte35_candidates_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c85_opening_compression_option_native_broad_etf_meta_trendpullback_rangecap_dte35",
        "c85_opening_compression_option_native_broad_etf_meta_trendpullback_rangecap_dte35_candidates_v1",
        "opening_compression_option_native_broad_etf_meta_trendpullback_rangecap_dte35_candidates_v1",
    }:
        return c85_opening_compression_option_native_broad_etf_meta_trendpullback_rangecap_dte35_candidates_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c86_opening_compression_option_native_broad_etf_meta_trendmr_fulltrend_fallback_dte35",
        "c86_opening_compression_option_native_broad_etf_meta_trendmr_fulltrend_fallback_dte35_candidates_v1",
        "opening_compression_option_native_broad_etf_meta_trendmr_fulltrend_fallback_dte35_candidates_v1",
    }:
        return c86_opening_compression_option_native_broad_etf_meta_trendmr_fulltrend_fallback_dte35_candidates_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c87_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_dte35",
        "c87_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_dte35_candidates_v1",
        "opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_dte35_candidates_v1",
    }:
        return c87_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_dte35_candidates_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c88_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_rangecap_dte35",
        "c88_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_rangecap_dte35_candidates_v1",
        "opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_rangecap_dte35_candidates_v1",
    }:
        return c88_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_rangecap_dte35_candidates_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c89_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_dte35",
        "c89_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_dte35_candidates_v1",
        "opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_dte35_candidates_v1",
    }:
        return c89_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_dte35_candidates_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c90_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_eventgap_dte35",
        "c90_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_eventgap_dte35_candidates_v1",
        "opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_eventgap_dte35_candidates_v1",
    }:
        return c90_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_eventgap_dte35_candidates_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c91_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_eventgap_dte35",
        "c91_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_eventgap_dte35_candidates_v1",
        "opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_eventgap_dte35_candidates_v1",
    }:
        return c91_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_eventgap_dte35_candidates_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c92_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_eventgapsoft_dte35",
        "c92_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_eventgapsoft_dte35_candidates_v1",
        "opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_eventgapsoft_dte35_candidates_v1",
    }:
        return c92_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_eventgapsoft_dte35_candidates_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c93_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_eventgapsoft_rangelow_dte35",
        "c93_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_eventgapsoft_rangelow_dte35_candidates_v1",
        "opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_eventgapsoft_rangelow_dte35_candidates_v1",
    }:
        return c93_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_eventgapsoft_rangelow_dte35_candidates_v1(
            or_width_min=or_width_min
        )
    if normalized in {
        "c94_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_eventgapsoft_rangelow_transition_dte35",
        "c94_opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_eventgapsoft_rangelow_transition_dte35_candidates_v1",
        "opening_compression_option_native_broad_etf_meta_trendmr_lowconf_guard_trendcap_eventgapsoft_rangelow_transition_dte35_candidates_v1",
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


def get_opening_range_profile(name: str, or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> OrbProfile:
    return get_orb_profile(name=name, or_width_min=or_width_min)


def build_opening_range_profile_set(name: str, or_width_min: float = DEFAULT_OR_WIDTH_MIN) -> List[OrbProfile]:
    return build_orb_profile_set(name=name, or_width_min=or_width_min)
