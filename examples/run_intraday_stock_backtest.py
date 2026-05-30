from datetime import datetime

from cutebacktests import IntradayOptionsBacktestConfig, IntradayOptionsBacktester, get_opening_range_profile
from cutebacktests.providers import CuteMarketsProvider
from cutebacktests.settings import Settings
from cutebacktests.storage import DataStore


def main() -> None:
    settings = Settings.from_env(".env")
    store = DataStore(settings.db_path)
    profile = get_opening_range_profile("c4_long_only_rr15")

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
                instrument_mode="stocks",
                stock_slippage_bps=1.0,
                stock_commission_per_share=0.0,
                return_trade_log=True,
                **profile.to_intraday_strategy_kwargs(),
            )
        )
        print({"trades": result["trades"], "total_return": result.get("total_return")})
    finally:
        store.close()


if __name__ == "__main__":
    main()
