"""Build a historical options feed slice for one ticker.

This example demonstrates the public historical-options ingestion path that
backs the research workflows in the wider stack.
"""

from __future__ import annotations

from datetime import date
import os

from cutebacktests.historical_options_feed import HistoricalOptionsFeed, HistoricalOptionsFeedConfig
from cutebacktests.providers import CuteMarketsProvider
from cutebacktests.settings import Settings
from cutebacktests.storage import DataStore


def main() -> None:
    settings = Settings.from_env(".env")
    ticker = os.environ.get("CUTEBACKTESTS_TICKER", "SPY").strip().upper()
    start_day = date.fromisoformat(os.environ.get("CUTEBACKTESTS_START_DAY", "2026-02-03"))
    end_day = date.fromisoformat(os.environ.get("CUTEBACKTESTS_END_DAY", "2026-02-05"))

    store = DataStore(settings.db_path)
    try:
        feed = HistoricalOptionsFeed(
            cutemarkets_provider=CuteMarketsProvider(settings),
            store=store,
        )
        summary = feed.ingest_range(
            config=HistoricalOptionsFeedConfig(
                start_day=start_day,
                end_day=end_day,
                tickers=(ticker,),
                option_min_dte=0,
                option_max_dte=7,
                option_type="all",
            )
        )
        print(summary)
        print(feed.stats())
    finally:
        store.close()


if __name__ == "__main__":
    main()
