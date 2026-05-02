"""Run a named opening-range profile through the public runtime."""

from __future__ import annotations

from datetime import datetime
import os

from cutebacktests import IntradayOptionsBacktestConfig, IntradayOptionsBacktester, get_opening_range_profile
from cutebacktests.providers import CuteMarketsProvider
from cutebacktests.settings import Settings
from cutebacktests.storage import DataStore


def main() -> None:
    settings = Settings.from_env(".env")
    profile_name = os.environ.get("CUTEBACKTESTS_PROFILE", "c4_long_only_rr15").strip()
    profile = get_opening_range_profile(profile_name)

    store = DataStore(settings.db_path)
    try:
        backtester = IntradayOptionsBacktester(
            store=store,
            cutemarkets_provider=CuteMarketsProvider(settings),
        )
        config = IntradayOptionsBacktestConfig(
            start=datetime(2025, 1, 1),
            end=datetime(2025, 1, 31),
            ticker="SPY",
            return_trade_log=True,
            **profile.to_intraday_strategy_kwargs(),
        )
        result = backtester.run(config)
        print(
            {
                "profile_name": profile.name,
                "strategy_variant": profile.strategy_variant,
                "trades": result.get("trades"),
                "total_return": result.get("total_return"),
            }
        )
    finally:
        store.close()


if __name__ == "__main__":
    main()
