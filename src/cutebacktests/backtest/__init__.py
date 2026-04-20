"""Public backtesting interfaces for cutebacktests."""

from .intraday_options import IntradayOptionsBacktestConfig, IntradayOptionsBacktester
from .pricing import ProxyLeveragePricer
from .robust import (
    WalkForwardFold,
    fold_metrics_row,
    generate_walkforward_folds,
    holdout_fold_metrics_row,
    summarize_out_of_sample,
)

__all__ = [
    "IntradayOptionsBacktestConfig",
    "IntradayOptionsBacktester",
    "ProxyLeveragePricer",
    "WalkForwardFold",
    "generate_walkforward_folds",
    "summarize_out_of_sample",
    "fold_metrics_row",
    "holdout_fold_metrics_row",
]
