# Profile Catalog

`cutebacktests` exposes named profile helpers so a researcher can move from a stable profile identifier to a fully resolved strategy configuration. The public entrypoints are:

- `get_opening_range_profile(name, or_width_min=...)`
- `build_opening_range_profile_set(name, or_width_min=...)`

Those functions resolve the opening-range and intraday strategy profiles published in the registry under `src/cutebacktests/profiles/`.

## What the public profiles represent

The public registry includes several kinds of profiles:

- baseline opening-range breakout variants used as research controls
- opening-range pullback and trend variants
- failure and fade variants
- mean-reversion overlays that move beyond classic ORB logic
- option-native execution overlays that tighten contract selection and entry quality

The important point is that a profile name is not just a label. It is a compact handle for a full parameter bundle: opening-range width, entry timing, stop logic, take-profit rules, relative-volume filters, and option microstructure constraints.

## Educational vs production-worthy

The public repo should be read as a research runtime first. Some profiles are useful because they are simple baselines and easy to reason about. Others are more realistic because they include option-native or quote-aware overlays. Neither category should be treated as live trading advice by default.

Practical examples:

- `c4_long_only_rr15` is a straightforward public baseline that is useful for understanding the runtime and profile resolution flow.
- `c36_quality` is a stronger public example of a quote-aware, option-native mean-reversion path, but it is documented separately in [`cute-intraday-option-strats`](https://github.com/cutemarkets/cute-intraday-option-strats) because that repo acts as the public model card.

## How to inspect profiles

Use Python when you want resolved parameters:

```python
from cutebacktests import get_opening_range_profile

profile = get_opening_range_profile("c4_long_only_rr15")
print(profile.name)
print(profile.strategy_variant)
print(profile.to_intraday_strategy_kwargs())
```

Use the registry source when you want to inspect lineage or add a new public profile:

- `src/cutebacktests/profiles/opening_range_profiles_registry.py`
- `src/cutebacktests/profiles/opening_range_profiles.py`

## Recommended workflow

1. Start from a named profile.
2. Resolve it to config kwargs.
3. Run a narrow backtest or walk-forward sweep.
4. Inspect trade density and failure reasons before you optimize further.

That flow keeps profile work reproducible and makes it easier to compare like with like across experiments.
