from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
import json
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
from cutebacktests.providers.cutemarkets_paper import CuteMarketsPaperBroker
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


class _FakeResponse:
    def __init__(self, payload=None, status_code: int = 200):
        self._payload = payload or {}
        self.status_code = status_code
        self.text = "" if status_code == 204 else json.dumps(self._payload)

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self._payload


class _FakePaperSession:
    def __init__(self):
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        if url.endswith("/accounts/"):
            return _FakeResponse({"results": [{"id": "acct_1", "name": "demo"}]})
        if url.endswith("/orders:by_client_order_id"):
            return _FakeResponse({"id": "ord_by_client_id", "client_order_id": kwargs["params"]["client_order_id"]})
        if url.endswith("/positions/"):
            return _FakeResponse({"results": [{"symbol": "AAPL", "qty": "1"}]})
        return _FakeResponse({"id": "acct_1"})

    def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        if url.endswith("/orders/"):
            payload = dict(kwargs["json"])
            payload.setdefault("id", "ord_1")
            return _FakeResponse(payload)
        return _FakeResponse({"account": {"id": "acct_1", **kwargs["json"]}})

    def patch(self, url, **kwargs):
        self.calls.append(("PATCH", url, kwargs))
        return _FakeResponse({"account": {"id": "acct_1", **kwargs["json"]}})

    def delete(self, url, **kwargs):
        self.calls.append(("DELETE", url, kwargs))
        return _FakeResponse(status_code=204)


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
        self.assertFalse(public_cli.build_parser().parse_args(["sample-option-tradability", "--end-day", "2025-01-02"]).output_dir)

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
        self.assertEqual(
            parser.parse_args(
                [
                    "run-walk-forward-profile-backtest",
                    "--start",
                    "2025-01-01",
                    "--end",
                    "2025-01-31",
                ]
            ).command,
            "run-walk-forward-profile-backtest",
        )

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

    def test_public_cli_allows_config_backfilled_dates(self) -> None:
        fake_settings = SimpleNamespace(log_level="INFO")
        with patch.object(public_cli.Settings, "from_env", return_value=fake_settings), patch.object(
            public_cli, "cmd_run_intraday_options_backtest", return_value={"status": "ok"}
        ) as command_mock, patch("builtins.print"):
            public_cli.main(
                [
                    "run-intraday-options-backtest",
                    "--config-json",
                    json.dumps({"start": "2025-01-01", "end": "2025-01-02", "ticker": "QQQ"}),
                ]
            )
        parsed_args = command_mock.call_args[0][0]
        self.assertEqual(parsed_args.start, "2025-01-01")
        self.assertEqual(parsed_args.end, "2025-01-02")
        self.assertEqual(parsed_args.ticker, "QQQ")

    def test_intraday_cli_explicit_args_override_config_json(self) -> None:
        fake_settings = SimpleNamespace(log_level="INFO")
        with patch.object(public_cli.Settings, "from_env", return_value=fake_settings), patch.object(
            public_cli, "cmd_run_intraday_options_backtest", return_value={"status": "ok"}
        ) as command_mock, patch("builtins.print"):
            public_cli.main(
                [
                    "run-intraday-options-backtest",
                    "--start",
                    "2025-01-09",
                    "--end",
                    "2025-01-10",
                    "--config-json",
                    json.dumps({"start": "2025-01-01", "end": "2025-01-02", "ticker": "QQQ"}),
                ]
            )
        parsed_args = command_mock.call_args[0][0]
        self.assertEqual(parsed_args.start, "2025-01-09")
        self.assertEqual(parsed_args.end, "2025-01-10")
        self.assertEqual(parsed_args.ticker, "QQQ")

    def test_output_dir_writes_summary_and_trade_log_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "artifacts"
            db_path = Path(tmp_dir) / "cutebacktests.duckdb"
            fake_settings = Settings(
                cutemarkets_api_key="cm-key",
                alpaca_api_key="",
                alpaca_secret_key="",
                cutemarkets_base_url="https://api.cutemarkets.com",
                alpaca_paper_base_url="https://paper-api.alpaca.markets",
                alpaca_data_base_url="https://data.alpaca.markets",
                data_dir=Path(tmp_dir),
                db_path=db_path,
                log_level="INFO",
            )
            fake_trade_log = [
                {
                    "ticker": "SPY",
                    "entered_at": datetime(2025, 1, 2, 14, 35),
                    "pnl": 123.4,
                }
            ]
            with patch.object(
                public_cli,
                "_run_intraday_backtest",
                return_value=(
                    {"trades": 1, "total_return": 0.01, "trade_log": fake_trade_log},
                    SimpleNamespace(take_stats=lambda reset=False: {"request_count": 2}),
                ),
            ):
                result = public_cli.cmd_run_intraday_options_backtest(
                    argparse.Namespace(
                        ticker="SPY",
                        start="2025-01-01",
                        end="2025-01-03",
                        initial_equity=100000.0,
                        risk_per_trade=0.02,
                        max_trades_per_day=1,
                        instrument_mode="options",
                        option_mode="auto",
                        option_contract_status="inactive",
                        option_min_dte=0,
                        option_target_dte=1,
                        option_max_dte=7,
                        option_min_open_interest=0,
                        use_option_quotes_for_fills="true",
                        option_quote_fill_fallback_to_bar_close="false",
                        option_max_entry_spread_pct=1.0,
                        option_max_loss_pct=0.0,
                        option_use_contract_open_interest="false",
                        require_option_microstructure_filter="false",
                        option_min_entry_volume=0,
                        option_max_entry_bar_range_pct=1.0,
                        option_min_entry_price=0.0,
                        proxy_option_leverage=7.5,
                        option_slippage_bps=0.0,
                        option_commission_per_contract=0.0,
                        execution_entry_delay_minutes=0,
                        execution_exit_delay_minutes=0,
                        execution_delay_randomization="true",
                        execution_entry_delay_jitter_minutes=2,
                        execution_exit_delay_jitter_minutes=2,
                        execution_delay_random_seed=42,
                        persist_trades="true",
                        return_trade_log="false",
                        opening_range_minutes=5,
                        entry_start_time="09:35",
                        entry_cutoff_time="12:00",
                        exit_time="15:55",
                        strategy_variant="orb_qc",
                        allow_long="true",
                        allow_short="true",
                        use_opening_bar_direction="false",
                        require_breakout_open_inside_range="true",
                        entry_trigger_mode="close_breakout",
                        stop_mode="range",
                        stop_loss_atr_distance=1.0,
                        take_profit_rr=0.0,
                        break_even_trigger_rr=0.0,
                        exit_on_opposite_candle="false",
                        opposite_candle_min_hold_minutes=0,
                        early_fail_minutes=0,
                        early_fail_min_rr=0.0,
                        max_hold_minutes=0,
                        fib_entry_level_low=0.5,
                        fib_entry_level_high=0.618,
                        fib_target_extension=1.444,
                        fib_require_confirmation="true",
                        mr_band_or_mult=1.0,
                        mr_min_distance_from_vwap_pct=0.0,
                        mr_reentry_buffer_or_mult=0.1,
                        mr_stop_buffer_or_mult=0.15,
                        mr_take_profit_mode="vwap",
                        mr_take_profit_rr=1.0,
                        mr_require_reversal_candle="true",
                        mr_zscore_window=20,
                        mr_zscore_entry=1.6,
                        mr_zscore_reentry=0.8,
                        mr_zscore_stop=2.4,
                        mr_zscore_target=0.25,
                        mr_sigma_min_pct=0.0,
                        mr_sigma_max_pct=1.0,
                        mr_vwap_slope_lookback=3,
                        mr_vwap_slope_max_pct=1.0,
                        max_positions=20,
                        stop_loss_risk_size=0.01,
                        stock_slippage_bps=0.0,
                        stock_commission_per_share=0.0,
                        require_relative_volume="true",
                        relative_volume_min=1.0,
                        relative_volume_lookback_days=14,
                        require_atr_filter="false",
                        atr_lookback_days=14,
                        atr_min=0.0,
                        volume_ma_window=20,
                        volume_spike_multiple=1.2,
                        trend_ema_fast=20,
                        trend_ema_slow=50,
                        require_fvg="false",
                        require_volume_spike="false",
                        require_trend_alignment="false",
                        require_or_width_filter="false",
                        opening_range_min_width_pct=0.0,
                        opening_range_max_width_pct=1.0,
                        require_macro_release_filter="false",
                        macro_release_times_et="10:00",
                        macro_post_release_block_minutes=15,
                        require_vol_regime_filter="false",
                        vol_regime_ticker="I:VIX1D",
                        vol_regime_proxy_ticker="VIXY",
                        vol_regime_min=0.0,
                        vol_regime_max=1000.0,
                        with_alpaca=False,
                        output_dir=str(output_dir),
                    ),
                    fake_settings,
                )
            self.assertEqual(result["trades"], 1)
            self.assertNotIn("trade_log", result)
            self.assertTrue((output_dir / "summary.json").exists())
            self.assertTrue((output_dir / "trade_log.csv").exists())
            self.assertTrue((output_dir / "config.json").exists())
            self.assertTrue((output_dir / "provider_stats.json").exists())
            summary_payload = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary_payload["trades"], 1)

    def test_public_aliases_point_to_expected_types(self) -> None:
        self.assertIsInstance(get_opening_range_profile("c4_long_only_rr15"), OpeningRangeProfile)
        self.assertEqual(IntradayOptionsBacktestConfig.__name__, "IntradayOptionsBacktestConfig")
        self.assertEqual(IntradayStrategyConfig.__name__, "IntradayStrategyConfig")
        self.assertEqual(IntradayOptionsBacktester.__name__, "IntradayOptionsBacktester")
        self.assertEqual(CuteMarketsProvider.__name__, "CuteMarketsProvider")
        self.assertEqual(CuteMarketsPaperBroker.__name__, "CuteMarketsPaperBroker")

    def test_settings_accept_cutemarkets_env_names(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            env_path = Path(tmp_dir) / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        "CUTEMARKETS_API_KEY=cm-key",
                        "CUTEMARKETS_STOCKS_API_KEY=cm-stocks",
                        "CUTEMARKETS_PAPER_API_KEY=cm-paper",
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
        self.assertEqual(settings.cutemarkets_stocks_api_key, "cm-stocks")
        self.assertEqual(settings.cutemarkets_paper_api_key, "cm-paper")
        self.assertEqual(settings.cutemarkets_base_url, "https://api.cutemarkets.com")
        self.assertEqual(
            settings.required_keys_present(["cutemarkets", "cutemarkets_stocks", "cutemarkets_paper", "alpaca"]),
            {"cutemarkets": True, "cutemarkets_stocks": True, "cutemarkets_paper": True, "alpaca": True},
        )

    def test_cutemarkets_paper_broker_uses_paper_key_and_request_bodies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            settings = Settings(
                cutemarkets_api_key="cm-default",
                alpaca_api_key="",
                alpaca_secret_key="",
                cutemarkets_base_url="https://api.cutemarkets.test",
                alpaca_paper_base_url="https://paper-api.alpaca.markets",
                alpaca_data_base_url="https://data.alpaca.markets",
                data_dir=Path(tmp_dir),
                db_path=Path(tmp_dir) / "db.duckdb",
                log_level="INFO",
                cutemarkets_paper_api_key="cm-paper",
            )
            session = _FakePaperSession()
            broker = CuteMarketsPaperBroker(settings, session=session)

            self.assertEqual(broker.list_accounts()[0]["id"], "acct_1")
            order = broker.place_stock_order("acct_1", symbol="aapl", qty=1, side="buy", client_order_id="demo-1")
            self.assertEqual(order["qty"], "1")
            self.assertEqual(order["symbol"], "AAPL")
            self.assertEqual(broker.list_positions("acct_1")[0]["symbol"], "AAPL")
            self.assertEqual(broker.cancel_order("acct_1", "ord_1"), {})

        method, url, kwargs = session.calls[1]
        self.assertEqual(method, "POST")
        self.assertEqual(url, "https://api.cutemarkets.test/v1/paper/accounts/acct_1/orders/")
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer cm-paper")
        self.assertEqual(kwargs["json"]["client_order_id"], "demo-1")

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
