"""Demonstrate the public walk-forward helpers on synthetic fold metrics."""

from __future__ import annotations

from datetime import datetime

from cutebacktests.backtest import (
    generate_walkforward_folds,
    holdout_fold_metrics_row,
    summarize_out_of_sample,
)


def main() -> None:
    folds = generate_walkforward_folds(
        start=datetime(2025, 1, 1),
        end=datetime(2025, 12, 31),
        train_days=120,
        test_days=20,
        step_days=20,
        purge_days=2,
        expanding_train=True,
    )
    print("generated_folds=", len(folds))
    for fold in folds[:3]:
        print(" ", fold.as_dict())

    raw_results = [
        {"trades": 18, "total_return": 0.031, "sharpe": 1.1, "sortino": 1.7, "max_drawdown": -0.018, "roci": 0.42},
        {"trades": 7, "total_return": -0.006, "sharpe": -0.1, "sortino": -0.2, "max_drawdown": -0.027, "roci": -0.08},
        {"trades": 22, "total_return": 0.024, "sharpe": 0.9, "sortino": 1.4, "max_drawdown": -0.015, "roci": 0.35},
    ]
    rows = [
        holdout_fold_metrics_row(name=f"fold_{index + 1}", result=result, min_test_trades=10)
        for index, result in enumerate(raw_results)
    ]
    included = [row for row in rows if row["included"]]
    print("included_folds=", len(included))
    print(summarize_out_of_sample(included, total_folds=len(rows)))


if __name__ == "__main__":
    main()
