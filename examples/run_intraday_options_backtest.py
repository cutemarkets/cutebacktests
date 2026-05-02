"""Run the intraday options backtester directly.

This example uses the public runtime classes rather than the CLI so you can
adapt it for notebooks or larger research scripts.
"""

from __future__ import annotations

from datetime import datetime

from cutebacktests import IntradayOptionsBacktestConfig, IntradayOptionsBacktester
from cutebacktests.providers import CuteMarketsProvider
from cutebacktests.settings import Settings
from cutebacktests.storage import DataStore


def main() -> None:
    settings = Settings.from_env(".env")
    store = DataStore(settings.db_path)
    try:
        backtester = IntradayOptionsBacktester(
            store=store,
            cutemarkets_provider=CuteMarketsProvider(settings),
        )
        result = backtester.run(
            IntradayOptionsBacktestConfig(
                ticker="SPY",
                start=datetime(2025, 1, 1),
                end=datetime(2025, 1, 31),
                strategy_variant="mr_vwap_zscore_v2",
                instrument_mode="options",
                return_trade_log=True,
            )
        )
        print(
            {
                "ticker": result.get("ticker"),
                "trades": result.get("trades"),
                "total_return": result.get("total_return"),
                "max_drawdown": result.get("max_drawdown"),
            }
        )
    finally:
        store.close()


if __name__ == "__main__":
    main()
