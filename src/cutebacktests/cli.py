from __future__ import annotations

import argparse
import json
from datetime import datetime
from typing import Any, Dict

from .backtest.intraday_options import IntradayOptionsBacktestConfig, IntradayOptionsBacktester
from .profiles import get_opening_range_profile
from .providers.alpaca import AlpacaDataProvider
from .providers.cutemarkets import CuteMarketsProvider
from .settings import Settings
from .storage import DataStore


def _parse_date(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _parse_bool(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _base_intraday_kwargs(args: argparse.Namespace) -> Dict[str, Any]:
    return {
        "start": _parse_date(args.start),
        "end": _parse_date(args.end),
        "ticker": str(args.ticker).upper(),
        "initial_equity": float(args.initial_equity),
        "risk_per_trade": float(args.risk_per_trade),
        "max_trades_per_day": int(args.max_trades_per_day),
        "instrument_mode": str(args.instrument_mode),
        "option_mode": str(args.option_mode),
        "option_contract_status": str(args.option_contract_status),
        "option_min_dte": int(args.option_min_dte),
        "option_target_dte": int(args.option_target_dte),
        "option_max_dte": int(args.option_max_dte),
        "option_min_open_interest": int(args.option_min_open_interest),
        "use_option_quotes_for_fills": _parse_bool(args.use_option_quotes_for_fills),
        "option_quote_fill_fallback_to_bar_close": _parse_bool(args.option_quote_fill_fallback_to_bar_close),
        "option_max_entry_spread_pct": float(args.option_max_entry_spread_pct),
        "option_max_loss_pct": float(args.option_max_loss_pct),
        "option_use_contract_open_interest": _parse_bool(args.option_use_contract_open_interest),
        "require_option_microstructure_filter": _parse_bool(args.require_option_microstructure_filter),
        "option_min_entry_volume": int(args.option_min_entry_volume),
        "option_max_entry_bar_range_pct": float(args.option_max_entry_bar_range_pct),
        "option_min_entry_price": float(args.option_min_entry_price),
        "proxy_option_leverage": float(args.proxy_option_leverage),
        "option_slippage_bps": float(args.option_slippage_bps),
        "option_commission_per_contract": float(args.option_commission_per_contract),
        "execution_entry_delay_minutes": int(args.execution_entry_delay_minutes),
        "execution_exit_delay_minutes": int(args.execution_exit_delay_minutes),
        "execution_delay_randomization": _parse_bool(args.execution_delay_randomization),
        "execution_entry_delay_jitter_minutes": int(args.execution_entry_delay_jitter_minutes),
        "execution_exit_delay_jitter_minutes": int(args.execution_exit_delay_jitter_minutes),
        "execution_delay_random_seed": int(args.execution_delay_random_seed),
        "persist_trades": _parse_bool(args.persist_trades),
        "opening_range_minutes": int(args.opening_range_minutes),
        "entry_start_time": str(args.entry_start_time),
        "entry_cutoff_time": str(args.entry_cutoff_time),
        "exit_time": str(args.exit_time),
        "strategy_variant": str(args.strategy_variant),
        "allow_long": _parse_bool(args.allow_long),
        "allow_short": _parse_bool(args.allow_short),
        "use_opening_bar_direction": _parse_bool(args.use_opening_bar_direction),
        "require_breakout_open_inside_range": _parse_bool(args.require_breakout_open_inside_range),
        "entry_trigger_mode": str(args.entry_trigger_mode),
        "stop_mode": str(args.stop_mode),
        "stop_loss_atr_distance": float(args.stop_loss_atr_distance),
        "take_profit_rr": float(args.take_profit_rr),
        "break_even_trigger_rr": float(args.break_even_trigger_rr),
        "exit_on_opposite_candle": _parse_bool(args.exit_on_opposite_candle),
        "opposite_candle_min_hold_minutes": int(args.opposite_candle_min_hold_minutes),
        "early_fail_minutes": int(args.early_fail_minutes),
        "early_fail_min_rr": float(args.early_fail_min_rr),
        "max_hold_minutes": int(args.max_hold_minutes),
        "fib_entry_level_low": float(args.fib_entry_level_low),
        "fib_entry_level_high": float(args.fib_entry_level_high),
        "fib_target_extension": float(args.fib_target_extension),
        "fib_require_confirmation": _parse_bool(args.fib_require_confirmation),
        "mr_band_or_mult": float(args.mr_band_or_mult),
        "mr_min_distance_from_vwap_pct": float(args.mr_min_distance_from_vwap_pct),
        "mr_reentry_buffer_or_mult": float(args.mr_reentry_buffer_or_mult),
        "mr_stop_buffer_or_mult": float(args.mr_stop_buffer_or_mult),
        "mr_take_profit_mode": str(args.mr_take_profit_mode),
        "mr_take_profit_rr": float(args.mr_take_profit_rr),
        "mr_require_reversal_candle": _parse_bool(args.mr_require_reversal_candle),
        "mr_zscore_window": int(args.mr_zscore_window),
        "mr_zscore_entry": float(args.mr_zscore_entry),
        "mr_zscore_reentry": float(args.mr_zscore_reentry),
        "mr_zscore_stop": float(args.mr_zscore_stop),
        "mr_zscore_target": float(args.mr_zscore_target),
        "mr_sigma_min_pct": float(args.mr_sigma_min_pct),
        "mr_sigma_max_pct": float(args.mr_sigma_max_pct),
        "mr_vwap_slope_lookback": int(args.mr_vwap_slope_lookback),
        "mr_vwap_slope_max_pct": float(args.mr_vwap_slope_max_pct),
        "max_positions": int(args.max_positions),
        "stop_loss_risk_size": float(args.stop_loss_risk_size),
        "stock_slippage_bps": float(args.stock_slippage_bps),
        "stock_commission_per_share": float(args.stock_commission_per_share),
        "require_relative_volume": _parse_bool(args.require_relative_volume),
        "relative_volume_min": float(args.relative_volume_min),
        "relative_volume_lookback_days": int(args.relative_volume_lookback_days),
        "require_atr_filter": _parse_bool(args.require_atr_filter),
        "atr_lookback_days": int(args.atr_lookback_days),
        "atr_min": float(args.atr_min),
        "volume_ma_window": int(args.volume_ma_window),
        "volume_spike_multiple": float(args.volume_spike_multiple),
        "trend_ema_fast": int(args.trend_ema_fast),
        "trend_ema_slow": int(args.trend_ema_slow),
        "require_fvg": _parse_bool(args.require_fvg),
        "require_volume_spike": _parse_bool(args.require_volume_spike),
        "require_trend_alignment": _parse_bool(args.require_trend_alignment),
        "require_or_width_filter": _parse_bool(args.require_or_width_filter),
        "opening_range_min_width_pct": float(args.opening_range_min_width_pct),
        "opening_range_max_width_pct": float(args.opening_range_max_width_pct),
        "require_macro_release_filter": _parse_bool(args.require_macro_release_filter),
        "macro_release_times_et": str(args.macro_release_times_et),
        "macro_post_release_block_minutes": int(args.macro_post_release_block_minutes),
        "require_vol_regime_filter": _parse_bool(args.require_vol_regime_filter),
        "vol_regime_ticker": str(args.vol_regime_ticker),
        "vol_regime_proxy_ticker": str(args.vol_regime_proxy_ticker),
        "vol_regime_min": float(args.vol_regime_min),
        "vol_regime_max": float(args.vol_regime_max),
    }


def _build_backtester(
    settings: Settings,
    store: DataStore,
    *,
    include_alpaca: bool = False,
) -> IntradayOptionsBacktester:
    return IntradayOptionsBacktester(
        store=store,
        cutemarkets_provider=CuteMarketsProvider(settings),
        alpaca_data_provider=AlpacaDataProvider(settings) if include_alpaca else None,
    )


def cmd_run_intraday_options_backtest(args: argparse.Namespace, settings: Settings) -> Dict[str, Any]:
    store = DataStore(settings.db_path)
    try:
        backtester = _build_backtester(
            settings=settings,
            store=store,
            include_alpaca=bool(getattr(args, "with_alpaca", False)),
        )
        return backtester.run(IntradayOptionsBacktestConfig(**_base_intraday_kwargs(args)))
    finally:
        store.close()


def cmd_run_opening_range_profile_backtest(args: argparse.Namespace, settings: Settings) -> Dict[str, Any]:
    store = DataStore(settings.db_path)
    try:
        backtester = _build_backtester(
            settings=settings,
            store=store,
            include_alpaca=bool(getattr(args, "with_alpaca", False)),
        )
        profile = get_opening_range_profile(name=str(args.profile_name), or_width_min=float(args.or_width_min))
        cfg_kwargs = profile.to_intraday_strategy_kwargs()
        cfg_kwargs.update(_base_intraday_kwargs(args))
        cfg_kwargs["return_trade_log"] = _parse_bool(args.return_trade_log)
        result = backtester.run(IntradayOptionsBacktestConfig(**cfg_kwargs))
        result["profile_name"] = profile.name
        return result
    finally:
        store.close()


def _add_common_intraday_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--ticker", default="SPY")
    parser.add_argument("--start", required=True, help="YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="YYYY-MM-DD")
    parser.add_argument("--initial-equity", type=float, default=100000.0)
    parser.add_argument("--risk-per-trade", type=float, default=0.02)
    parser.add_argument("--max-trades-per-day", type=int, default=1)
    parser.add_argument("--instrument-mode", choices=["options", "stocks"], default="options")
    parser.add_argument("--option-mode", choices=["auto", "historical", "proxy"], default="auto")
    parser.add_argument("--option-contract-status", choices=["inactive", "active"], default="inactive")
    parser.add_argument("--option-min-dte", type=int, default=0)
    parser.add_argument("--option-target-dte", type=int, default=1)
    parser.add_argument("--option-max-dte", type=int, default=7)
    parser.add_argument("--option-min-open-interest", type=int, default=0)
    parser.add_argument("--use-option-quotes-for-fills", default="true")
    parser.add_argument("--option-quote-fill-fallback-to-bar-close", default="false")
    parser.add_argument("--option-max-entry-spread-pct", type=float, default=1.0)
    parser.add_argument("--option-max-loss-pct", type=float, default=0.0)
    parser.add_argument("--option-use-contract-open-interest", default="false")
    parser.add_argument("--require-option-microstructure-filter", default="false")
    parser.add_argument("--option-min-entry-volume", type=int, default=0)
    parser.add_argument("--option-max-entry-bar-range-pct", type=float, default=1.0)
    parser.add_argument("--option-min-entry-price", type=float, default=0.0)
    parser.add_argument("--proxy-option-leverage", type=float, default=7.5)
    parser.add_argument(
        "--with-alpaca",
        dest="with_alpaca",
        action="store_true",
        help="Optionally enable the auxiliary Alpaca provider. CuteMarkets remains the default data path.",
    )
    parser.add_argument(
        "--without-alpaca",
        dest="with_alpaca",
        action="store_false",
        help=argparse.SUPPRESS,
    )
    parser.set_defaults(with_alpaca=False)
    parser.add_argument("--opening-range-minutes", type=int, default=5)
    parser.add_argument("--entry-start-time", default="09:35")
    parser.add_argument("--entry-cutoff-time", default="12:00")
    parser.add_argument("--exit-time", default="15:55")
    parser.add_argument(
        "--strategy-variant",
        choices=[
            "orb_qc",
            "orb_fib_pullback",
            "orb_momentum_v1",
            "orb_trend_pullback_v1",
            "orb_event_drive_v1",
            "orb_transition_compression_v1",
            "orb_trend_short",
            "orb_failure_fade",
            "mr_vwap_revert_v1",
            "mr_vwap_zscore_v2",
            "mr_overnight_regime_v1",
        ],
        default="orb_qc",
    )
    parser.add_argument("--allow-long", default="true")
    parser.add_argument("--allow-short", default="true")
    parser.add_argument("--use-opening-bar-direction", default="false")
    parser.add_argument("--require-breakout-open-inside-range", default="true")
    parser.add_argument("--entry-trigger-mode", choices=["close_breakout", "stop_touch"], default="close_breakout")
    parser.add_argument("--stop-mode", choices=["range", "breakout_candle", "opening_bar_atr"], default="range")
    parser.add_argument("--stop-loss-atr-distance", type=float, default=1.0)
    parser.add_argument("--take-profit-rr", type=float, default=0.0)
    parser.add_argument("--break-even-trigger-rr", type=float, default=0.0)
    parser.add_argument("--exit-on-opposite-candle", default="false")
    parser.add_argument("--opposite-candle-min-hold-minutes", type=int, default=0)
    parser.add_argument("--early-fail-minutes", type=int, default=0)
    parser.add_argument("--early-fail-min-rr", type=float, default=0.0)
    parser.add_argument("--max-hold-minutes", type=int, default=0)
    parser.add_argument("--fib-entry-level-low", type=float, default=0.5)
    parser.add_argument("--fib-entry-level-high", type=float, default=0.618)
    parser.add_argument("--fib-target-extension", type=float, default=1.444)
    parser.add_argument("--fib-require-confirmation", default="true")
    parser.add_argument("--mr-band-or-mult", type=float, default=1.0)
    parser.add_argument("--mr-min-distance-from-vwap-pct", type=float, default=0.0)
    parser.add_argument("--mr-reentry-buffer-or-mult", type=float, default=0.1)
    parser.add_argument("--mr-stop-buffer-or-mult", type=float, default=0.15)
    parser.add_argument("--mr-take-profit-mode", choices=["vwap", "rr", "none", "zscore"], default="vwap")
    parser.add_argument("--mr-take-profit-rr", type=float, default=1.0)
    parser.add_argument("--mr-require-reversal-candle", default="true")
    parser.add_argument("--mr-zscore-window", type=int, default=20)
    parser.add_argument("--mr-zscore-entry", type=float, default=1.6)
    parser.add_argument("--mr-zscore-reentry", type=float, default=0.8)
    parser.add_argument("--mr-zscore-stop", type=float, default=2.4)
    parser.add_argument("--mr-zscore-target", type=float, default=0.25)
    parser.add_argument("--mr-sigma-min-pct", type=float, default=0.0)
    parser.add_argument("--mr-sigma-max-pct", type=float, default=1.0)
    parser.add_argument("--mr-vwap-slope-lookback", type=int, default=3)
    parser.add_argument("--mr-vwap-slope-max-pct", type=float, default=1.0)
    parser.add_argument("--max-positions", type=int, default=20)
    parser.add_argument("--stop-loss-risk-size", type=float, default=0.01)
    parser.add_argument("--stock-slippage-bps", type=float, default=0.0)
    parser.add_argument("--stock-commission-per-share", type=float, default=0.0)
    parser.add_argument("--require-relative-volume", default="true")
    parser.add_argument("--relative-volume-min", type=float, default=1.0)
    parser.add_argument("--relative-volume-lookback-days", type=int, default=14)
    parser.add_argument("--require-atr-filter", default="false")
    parser.add_argument("--atr-lookback-days", type=int, default=14)
    parser.add_argument("--atr-min", type=float, default=0.0)
    parser.add_argument("--volume-ma-window", type=int, default=20)
    parser.add_argument("--volume-spike-multiple", type=float, default=1.2)
    parser.add_argument("--trend-ema-fast", type=int, default=20)
    parser.add_argument("--trend-ema-slow", type=int, default=50)
    parser.add_argument("--require-fvg", default="false")
    parser.add_argument("--require-volume-spike", default="false")
    parser.add_argument("--require-trend-alignment", default="false")
    parser.add_argument("--require-or-width-filter", default="false")
    parser.add_argument("--opening-range-min-width-pct", type=float, default=0.0)
    parser.add_argument("--opening-range-max-width-pct", type=float, default=1.0)
    parser.add_argument("--require-macro-release-filter", default="false")
    parser.add_argument("--macro-release-times-et", default="10:00")
    parser.add_argument("--macro-post-release-block-minutes", type=int, default=15)
    parser.add_argument("--require-vol-regime-filter", default="false")
    parser.add_argument("--vol-regime-ticker", default="I:VIX1D")
    parser.add_argument("--vol-regime-proxy-ticker", default="VIXY")
    parser.add_argument("--vol-regime-min", type=float, default=0.0)
    parser.add_argument("--vol-regime-max", type=float, default=1000.0)
    parser.add_argument("--option-slippage-bps", type=float, default=0.0)
    parser.add_argument("--option-commission-per-contract", type=float, default=0.0)
    parser.add_argument("--execution-entry-delay-minutes", type=int, default=0)
    parser.add_argument("--execution-exit-delay-minutes", type=int, default=0)
    parser.add_argument("--execution-delay-randomization", default="true")
    parser.add_argument("--execution-entry-delay-jitter-minutes", type=int, default=2)
    parser.add_argument("--execution-exit-delay-jitter-minutes", type=int, default=2)
    parser.add_argument("--execution-delay-random-seed", type=int, default=42)
    parser.add_argument("--persist-trades", default="true")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="cutebacktests CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    intraday = subparsers.add_parser("run-intraday-options-backtest")
    _add_common_intraday_args(intraday)

    opening_range = subparsers.add_parser("run-opening-range-profile-backtest")
    _add_common_intraday_args(opening_range)
    opening_range.add_argument("--profile-name", default="c4_long_only_rr15")
    opening_range.add_argument("--or-width-min", type=float, default=0.002)
    opening_range.add_argument("--return-trade-log", default="false")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    settings = Settings.from_env()
    command_map = {
        "run-intraday-options-backtest": cmd_run_intraday_options_backtest,
        "run-opening-range-profile-backtest": cmd_run_opening_range_profile_backtest,
    }
    result = command_map[str(args.command)](args, settings)
    if result is not None:
        print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
