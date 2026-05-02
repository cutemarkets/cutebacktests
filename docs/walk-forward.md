# Walk-Forward Evaluation

`cutebacktests` includes public helpers for walk-forward splitting and out-of-sample aggregation because a backtest runtime is not very useful if it cannot separate training luck from repeatable behavior. The relevant public helpers live in `cutebacktests.backtest`:

- `generate_walkforward_folds`
- `fold_metrics_row`
- `holdout_fold_metrics_row`
- `summarize_out_of_sample`

## What robustness means in this repo

Robustness in this public runtime means more than a high in-sample return. A strategy has to survive multiple test windows, maintain reasonable trade coverage, and avoid hiding its edge in one or two lucky slices. The helpers in this repo summarize that idea with fold-level coverage, return stability, drawdown, and trade-count aware inclusion rules.

The runtime does not expose one canonical Sharpe-only promotion rule. Instead, it gives you primitives that let you build a stricter evaluation surface.

## Fold generation

`generate_walkforward_folds` supports both expanding and rolling training windows with explicit purge days. That makes it usable for strategy families where nearby samples can leak information through overlapping conditions or market regimes.

Example:

```python
from datetime import datetime
from cutebacktests.backtest import generate_walkforward_folds

folds = generate_walkforward_folds(
    start=datetime(2025, 1, 1),
    end=datetime(2025, 12, 31),
    train_days=120,
    test_days=20,
    step_days=20,
    purge_days=2,
)
```

## Out-of-sample aggregation

`summarize_out_of_sample` aggregates fold metrics into a single summary that explicitly penalizes instability and drawdown while rewarding coverage. The exact scoring formula is public in `src/cutebacktests/backtest/robust.py`, including:

- median and mean return
- compounded return
- standard deviation of fold returns
- median Sharpe and Sortino
- median drawdown
- total trades
- a composite `robust_score`

This is not identical to a full deflated-Sharpe or PBO implementation, but it serves the same public purpose: do not trust a strategy because one slice looked strong.

## Trade-count aware inclusion

`holdout_fold_metrics_row` marks low-trade folds explicitly instead of silently treating them as equal evidence. That matters for intraday options strategies where signal density often collapses once more realistic filters are turned on.

In practical terms, the public runtime encourages you to ask:

- how many folds produced enough trades to be informative
- whether the worst fold is catastrophic
- whether the edge survives after removing low-coverage windows

Those are usually better questions than “what was the best Sharpe in the sweep?”
