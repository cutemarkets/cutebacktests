from __future__ import annotations

from dataclasses import replace
from typing import List

from .opening_range_profiles_core import DEFAULT_OR_WIDTH_MIN, OrbProfile


def c17_option_structure_strength_balance_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> OrbProfile:
    from . import opening_range_profiles as _opening_range_profiles

    base = _opening_range_profiles.c12_relative_strength_opportunity_regime_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c17_option_structure_strength_balance_v1",
        description=(
            "Relative-strength continuation with explicit option-structure gating so the signal is only traded when "
            "the contract itself is liquid enough to survive realistic execution."
        ),
        option_structure_filter_enabled=True,
        option_structure_min_open_interest=1200,
        option_structure_min_entry_volume=100,
        option_structure_max_entry_spread_pct=0.14,
        option_structure_max_entry_bar_range_pct=0.28,
        option_structure_min_entry_price=0.90,
        take_profit_rr=1.10,
        break_even_trigger_rr=0.40,
        early_fail_minutes=10,
        max_hold_minutes=40,
    )


def c17_option_structure_strength_quality_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> OrbProfile:
    base = c17_option_structure_strength_balance_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c17_option_structure_strength_quality_v1",
        description=(
            "Higher-quality option-structure continuation with tighter spread and stronger quote-quality gating."
        ),
        option_structure_min_open_interest=1800,
        option_structure_min_entry_volume=150,
        option_structure_max_entry_spread_pct=0.10,
        option_structure_max_entry_bar_range_pct=0.22,
        option_structure_min_entry_price=1.10,
        relative_volume_min=0.90,
        take_profit_rr=1.15,
        max_hold_minutes=35,
        drive_reclaim_min_volume_multiple=0.85,
    )


def c17_option_structure_strength_regime_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> OrbProfile:
    base = c17_option_structure_strength_quality_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c17_option_structure_strength_regime_v1",
        description=(
            "Option-structure continuation on calmer sessions, combining relative-strength confirmation with "
            "stricter contract quality."
        ),
        require_vol_regime_filter=True,
        vol_regime_min=10.0,
        vol_regime_max=32.0,
        require_prior_day_range_filter=True,
        prior_day_range_max_pct=0.026,
    )


def c17_option_structure_strength_opportunity_v1(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> OrbProfile:
    base = c17_option_structure_strength_balance_v1(or_width_min=or_width_min)
    return replace(
        base,
        name="c17_option_structure_strength_opportunity_v1",
        description="Slightly looser option-structure continuation intended to preserve setup frequency while keeping the contract tradable.",
        option_structure_min_open_interest=1000,
        option_structure_min_entry_volume=80,
        option_structure_max_entry_spread_pct=0.16,
        option_structure_max_entry_bar_range_pct=0.30,
        option_structure_min_entry_price=0.85,
        relative_volume_min=0.80,
        take_profit_rr=1.05,
        max_hold_minutes=45,
    )


def c17_option_structure_strength_candidates(
    or_width_min: float = DEFAULT_OR_WIDTH_MIN,
) -> List[OrbProfile]:
    return [
        c17_option_structure_strength_balance_v1(or_width_min=or_width_min),
        c17_option_structure_strength_quality_v1(or_width_min=or_width_min),
        c17_option_structure_strength_regime_v1(or_width_min=or_width_min),
        c17_option_structure_strength_opportunity_v1(or_width_min=or_width_min),
    ]
