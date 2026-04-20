from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import mean, median, pstdev
from typing import Dict, List


@dataclass
class WalkForwardFold:
    name: str
    train_start: datetime
    train_end: datetime
    test_start: datetime
    test_end: datetime
    purge_days: int

    def as_dict(self) -> Dict[str, str]:
        return {
            "name": self.name,
            "train_start": self.train_start.isoformat(),
            "train_end": self.train_end.isoformat(),
            "test_start": self.test_start.isoformat(),
            "test_end": self.test_end.isoformat(),
            "purge_days": self.purge_days,
        }


def generate_walkforward_folds(
    start: datetime,
    end: datetime,
    train_days: int,
    test_days: int,
    step_days: int,
    purge_days: int = 0,
    expanding_train: bool = True,
) -> List[WalkForwardFold]:
    if train_days <= 0:
        raise ValueError("train_days must be > 0")
    if test_days <= 0:
        raise ValueError("test_days must be > 0")
    if step_days <= 0:
        raise ValueError("step_days must be > 0")
    if end < start:
        raise ValueError("end must be >= start")

    folds: List[WalkForwardFold] = []
    safe_purge = max(purge_days, 0)

    if expanding_train:
        train_start = start
        train_end = start + timedelta(days=train_days - 1)
        index = 1
        while True:
            test_start = train_end + timedelta(days=safe_purge + 1)
            test_end = test_start + timedelta(days=test_days - 1)
            if test_end > end:
                break
            folds.append(
                WalkForwardFold(
                    name=f"fold_{index}",
                    train_start=train_start,
                    train_end=train_end,
                    test_start=test_start,
                    test_end=test_end,
                    purge_days=safe_purge,
                )
            )
            train_end = train_end + timedelta(days=step_days)
            index += 1
        return folds

    train_start = start
    index = 1
    while True:
        train_end = train_start + timedelta(days=train_days - 1)
        test_start = train_end + timedelta(days=safe_purge + 1)
        test_end = test_start + timedelta(days=test_days - 1)
        if test_end > end:
            break
        folds.append(
            WalkForwardFold(
                name=f"fold_{index}",
                train_start=train_start,
                train_end=train_end,
                test_start=test_start,
                test_end=test_end,
                purge_days=safe_purge,
            )
        )
        train_start = train_start + timedelta(days=step_days)
        index += 1
    return folds


def summarize_out_of_sample(
    fold_metrics: List[Dict[str, float]],
    total_folds: int,
    weight_sortino: float = 1.0,
    weight_return: float = 2.0,
    weight_roci: float = 2.0,
    stability_penalty: float = 2.0,
    drawdown_penalty: float = 1.0,
    tail_penalty: float = 1.0,
    coverage_bonus: float = 0.5,
    sortino_cap: float = 15.0,
) -> Dict[str, float]:
    if not fold_metrics:
        return {
            "folds_total": total_folds,
            "folds_valid": 0,
            "coverage": 0.0,
            "median_return": 0.0,
            "mean_return": 0.0,
            "std_return": 0.0,
            "worst_return": 0.0,
            "compounded_return": 0.0,
            "median_sharpe": 0.0,
            "median_sortino": 0.0,
            "median_sortino_capped": 0.0,
            "median_roci": 0.0,
            "median_max_drawdown": 0.0,
            "total_trades": 0,
            "robust_score": 0.0,
        }

    returns = [float(row.get("total_return") or 0.0) for row in fold_metrics]
    sharpes = [float(row.get("sharpe") or 0.0) for row in fold_metrics]
    sortinos = [float(row.get("sortino") or 0.0) for row in fold_metrics]
    rocis = [float(row.get("roci") or 0.0) for row in fold_metrics]
    drawdowns = [float(row.get("max_drawdown") or 0.0) for row in fold_metrics]
    trades = [int(row.get("trades") or 0) for row in fold_metrics]

    compounded = 1.0
    for value in returns:
        compounded *= (1.0 + value)
    compounded -= 1.0

    median_return = median(returns)
    mean_return = mean(returns)
    std_return = pstdev(returns) if len(returns) > 1 else 0.0
    worst_return = min(returns)
    median_sharpe = median(sharpes)
    median_sortino = median(sortinos)
    capped_sortino = max(min(median_sortino, abs(sortino_cap)), -abs(sortino_cap))
    median_roci = median(rocis)
    median_drawdown = median(drawdowns)
    coverage = len(fold_metrics) / max(total_folds, 1)
    tail_loss = abs(min(worst_return, 0.0))

    robust_score = (
        (weight_sortino * capped_sortino)
        + (weight_return * median_return)
        + (weight_roci * median_roci)
        - (stability_penalty * std_return)
        - (drawdown_penalty * abs(median_drawdown))
        - (tail_penalty * tail_loss)
        + (coverage_bonus * coverage)
    )

    return {
        "folds_total": total_folds,
        "folds_valid": len(fold_metrics),
        "coverage": round(coverage, 6),
        "median_return": round(median_return, 6),
        "mean_return": round(mean_return, 6),
        "std_return": round(std_return, 6),
        "worst_return": round(worst_return, 6),
        "compounded_return": round(compounded, 6),
        "median_sharpe": round(median_sharpe, 6),
        "median_sortino": round(median_sortino, 6),
        "median_sortino_capped": round(capped_sortino, 6),
        "median_roci": round(median_roci, 6),
        "median_max_drawdown": round(median_drawdown, 6),
        "total_trades": int(sum(trades)),
        "robust_score": round(robust_score, 6),
    }


def fold_metrics_row(name: str, result: Dict[str, float], included: bool, reason: str = "") -> Dict[str, float]:
    return {
        "name": name,
        "included": included,
        "reason": reason,
        "trades": int(result.get("trades") or 0),
        "total_return": float(result.get("total_return") or 0.0),
        "sharpe": float(result.get("sharpe") or 0.0),
        "sortino": float(result.get("sortino") or 0.0),
        "max_drawdown": float(result.get("max_drawdown") or 0.0),
        "roci": float(result.get("roci") or 0.0),
    }


def holdout_fold_metrics_row(name: str, result: Dict[str, float], min_test_trades: int) -> Dict[str, float]:
    threshold = max(int(min_test_trades), 1)
    trades = int(result.get("trades") or 0)
    included = trades >= threshold
    reason = "" if included else f"test_trades<{threshold}"
    return fold_metrics_row(name=name, result=result, included=included, reason=reason)
