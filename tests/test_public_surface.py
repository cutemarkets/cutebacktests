from __future__ import annotations

from datetime import date, datetime, timedelta
import os
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest
from unittest.mock import patch

import cutebacktests
import cutebacktests.cli as public_cli
from cutebacktests.backtest import IntradayOptionsBacktestConfig, IntradayOptionsBacktester
from cutebacktests.profiles import OpeningRangeProfile, build_opening_range_profile_set, get_opening_range_profile
from cutebacktests.providers.cutemarkets import CuteMarketsProvider
from cutebacktests.settings import Settings
from cutebacktests.storage import DataStore
from cutebacktests.strategies import IntradayStrategyConfig, audit_intraday_funnel, find_intraday_setup, resolve_intraday_exit


def _session_bar(
    ts: datetime,
    open_price: float,
    high_price: float,
    low_price: float,
    close_price: float,
    volume: int,
    ticker: str = "SPY",
) -> dict:
    return {
        "ts": ts,
        "open": open_price,
        "high": high_price,
        "low": low_price,
        "close": close_price,
        "volume": volume,
        "ticker": ticker,
    }


def _pairs_mean_revert_fixture() -> tuple[date, list[dict], list[dict]]:
    day = date.fromisoformat("2026-02-24")
    base = datetime(2026, 2, 24, 14, 30)
    pair_closes = [
        99.9443,
        99.7848,
        99.9254,
        99.7188,
        99.7904,
        99.7598,
        99.5446,
        99.5990,
        99.3715,
        99.3817,
        99.1736,
        98.9781,
        98.9828,
        99.2289,
        99.0532,
        98.9371,
        99.0636,
        99.3822,
        99.4785,
        99.4665,
        99.8022,
        99.5802,
        99.8452,
        99.7690,
    ]
    spreads = [
        -0.3202,
        -0.6642,
        -0.8365,
        -0.5520,
        -0.8394,
        -0.7659,
        -0.6409,
        -0.7557,
        -0.7128,
        -1.1063,
        -1.5026,
        -1.7673,
        -1.6049,
        -1.6701,
        -1.8373,
        -1.7603,
        -1.8025,
        -1.9827,
        -1.7177,
        -1.5386,
        -1.7689,
        -1.7020,
        -1.6793,
        -1.3417,
    ]
    session_bars = []
    pair_bars = []
    for idx, spread in enumerate(spreads):
        pair_close = pair_closes[idx]
        primary_close = pair_close + spread
        ts = base + timedelta(minutes=idx)
        session_bars.append(
            _session_bar(
                ts,
                primary_close - 0.02,
                primary_close + 0.03,
                primary_close - 0.03,
                primary_close,
                180,
                ticker="SPY",
            )
        )
        pair_bars.append(
            _session_bar(
                ts,
                pair_close - 0.02,
                pair_close + 0.03,
                pair_close - 0.03,
                pair_close,
                200,
                ticker="QQQ",
            )
        )
    return day, session_bars, pair_bars


class _PairsSessionBacktester(IntradayOptionsBacktester):
    def __init__(self, store: DataStore, bars_by_ticker_day):
        super().__init__(store=store, cutemarkets_provider=None, alpaca_data_provider=None)
        self._bars_by_ticker_day = {
            (str(ticker).upper(), day): list(rows)
            for (ticker, day), rows in bars_by_ticker_day.items()
        }
        self.session_loads = []

    def _load_session_bars(self, ticker, day):  # type: ignore[override]
        key = (str(ticker).upper(), day)
        self.session_loads.append(key)
        return list(self._bars_by_ticker_day.get(key, []))


class PublicSurfaceTests(unittest.TestCase):
    def test_public_imports_resolve(self) -> None:
        self.assertEqual(
            cutebacktests.__all__,
            [
                "IntradayOptionsBacktestConfig",
                "IntradayOptionsBacktester",
                "OpeningRangeProfile",
                "get_opening_range_profile",
                "build_opening_range_profile_set",
            ],
        )
        self.assertIs(OpeningRangeProfile, get_opening_range_profile("c4_long_only_rr15").__class__)
        self.assertTrue(callable(build_opening_range_profile_set))
        self.assertTrue(callable(find_intraday_setup))
        self.assertTrue(callable(audit_intraday_funnel))
        self.assertTrue(callable(resolve_intraday_exit))

    def test_public_cli_accepts_new_commands(self) -> None:
        parser = public_cli.build_parser()
        intraday_args = parser.parse_args(
            ["run-intraday-options-backtest", "--start", "2025-01-01", "--end", "2025-01-02"]
        )
        profile_args = parser.parse_args(
            [
                "run-opening-range-profile-backtest",
                "--start",
                "2025-01-01",
                "--end",
                "2025-01-02",
            ]
        )
        self.assertEqual(intraday_args.command, "run-intraday-options-backtest")
        self.assertEqual(profile_args.command, "run-opening-range-profile-backtest")
        self.assertFalse(intraday_args.with_alpaca)
        self.assertFalse(profile_args.with_alpaca)

        explicit_aux = parser.parse_args(
            ["run-intraday-options-backtest", "--start", "2025-01-01", "--end", "2025-01-02", "--with-alpaca"]
        )
        compatibility_alias = parser.parse_args(
            [
                "run-opening-range-profile-backtest",
                "--start",
                "2025-01-01",
                "--end",
                "2025-01-02",
                "--without-alpaca",
            ]
        )
        self.assertTrue(explicit_aux.with_alpaca)
        self.assertFalse(compatibility_alias.with_alpaca)

    def test_public_cli_main_prints_json(self) -> None:
        fake_settings = SimpleNamespace(log_level="INFO")
        with patch.object(public_cli.Settings, "from_env", return_value=fake_settings), patch.object(
            public_cli, "cmd_run_intraday_options_backtest", return_value={"status": "ok"}
        ), patch("builtins.print") as print_mock, patch.object(
            sys,
            "argv",
            ["cutebacktests.cli", "run-intraday-options-backtest", "--start", "2025-01-01", "--end", "2025-01-02"],
        ):
            public_cli.main()
        print_mock.assert_called_once()

    def test_public_aliases_point_to_expected_types(self) -> None:
        self.assertIsInstance(get_opening_range_profile("c4_long_only_rr15"), OpeningRangeProfile)
        self.assertEqual(IntradayOptionsBacktestConfig.__name__, "IntradayOptionsBacktestConfig")
        self.assertEqual(IntradayStrategyConfig.__name__, "IntradayStrategyConfig")
        self.assertEqual(IntradayOptionsBacktester.__name__, "IntradayOptionsBacktester")
        self.assertEqual(CuteMarketsProvider.__name__, "CuteMarketsProvider")

    def test_settings_accept_cutemarkets_env_names(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            env_path = Path(tmp_dir) / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        "CUTEMARKETS_API_KEY=cm-key",
                        "CUTEMARKETS_BASE_URL=https://api.cutemarkets.com",
                        f"CUTEBACKTESTS_DATA_DIR={Path(tmp_dir) / 'data'}",
                        "ALPACA_API_KEY=alpaca",
                        "ALPACA_SECRET_KEY=secret",
                    ]
                ),
                encoding="utf-8",
            )
            with patch.dict(os.environ, {}, clear=True):
                settings = Settings.from_env(str(env_path))

        self.assertEqual(settings.cutemarkets_api_key, "cm-key")
        self.assertEqual(settings.cutemarkets_base_url, "https://api.cutemarkets.com")
        self.assertEqual(
            settings.required_keys_present(["cutemarkets", "alpaca"]),
            {"cutemarkets": True, "alpaca": True},
        )

    def test_opening_range_profile_kwargs_build_intraday_config(self) -> None:
        profile = get_opening_range_profile("c4_long_only_rr15")
        cfg = IntradayOptionsBacktestConfig(
            start=datetime(2025, 1, 1),
            end=datetime(2025, 1, 31),
            ticker="SPY",
            **profile.to_intraday_strategy_kwargs(),
        )
        self.assertEqual(cfg.strategy_variant, profile.strategy_variant)
        self.assertEqual(cfg.opening_range_minutes, profile.opening_range_minutes)

    def test_fixture_pairs_spread_backtest_runs_under_public_package(self) -> None:
        base_day, session_bars, pair_bars = _pairs_mean_revert_fixture()

        with tempfile.TemporaryDirectory() as tmp_dir:
            store = DataStore(Path(tmp_dir) / "cutebacktests_test.duckdb")
            try:
                backtester = _PairsSessionBacktester(
                    store=store,
                    bars_by_ticker_day={
                        ("SPY", base_day): session_bars,
                        ("QQQ", base_day): pair_bars,
                    },
                )
                result = backtester.run(
                    IntradayOptionsBacktestConfig(
                        start=datetime(2026, 2, 24),
                        end=datetime(2026, 2, 24),
                        ticker="SPY",
                        instrument_mode="stocks",
                        strategy_variant="pairs_spread_v1",
                        pairs_hedge_ticker="QQQ",
                        pairs_beta_lookback=6,
                        pairs_zscore_window=8,
                        pairs_zscore_entry=1.0,
                        pairs_zscore_reentry=0.35,
                        pairs_zscore_exit=0.25,
                        pairs_zscore_stop=2.8,
                        pairs_min_correlation=0.0,
                        take_profit_rr=0.0,
                        require_relative_volume=False,
                        require_breakout_open_inside_range=False,
                        return_trade_log=True,
                    )
                )
            finally:
                store.close()

        self.assertEqual(result["trades"], 1)
        self.assertIn(("SPY", base_day), backtester.session_loads)
        self.assertIn(("QQQ", base_day), backtester.session_loads)
        self.assertEqual(result["trade_log"][0]["metadata"]["exit_reason"], "pairs_mean_revert")


if __name__ == "__main__":
    unittest.main()
