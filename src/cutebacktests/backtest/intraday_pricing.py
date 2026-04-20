from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from math import sqrt
import random
from statistics import pstdev
import sys
from typing import Any, Dict, Iterator, List, Optional, Sequence
from zoneinfo import ZoneInfo

from ..models import BacktestTrade
from ..utils import parse_datetime

_fit = sys.modules.get("cutebacktests.backtest.intraday_options") or sys.modules.get("__main__")
if _fit is not None:
    for _name, _value in vars(_fit).items():
        if _name.startswith("__"):
            continue
        globals().setdefault(_name, _value)

_ET_ZONE = globals().get("_ET_ZONE", ZoneInfo("America/New_York"))


def _mean_fast(values: Sequence[float]) -> float:
    count = len(values)
    if count <= 0:
        return 0.0
    return sum(float(value) for value in values) / float(count)


def _simulate_historical_option_trade(
    self,
    ticker: str,
    day: date,
    setup: Dict[str, Any],
    exit_plan: Dict[str, Any],
    current_equity: float,
    config: IntradayOptionsBacktestConfig,
) -> Optional[BacktestTrade]:
    delegated_impl = globals().get("_simulate_historical_option_trade_impl")
    if callable(delegated_impl) and delegated_impl is not _simulate_historical_option_trade:
        return delegated_impl(self, ticker, day, setup, exit_plan, current_equity, config)

    self._bump_option_funnel("historical_option_attempts")
    if self.cutemarkets_provider is None and self.alpaca_data_provider is None:
        self._bump_option_rejection("no_option_market_data_provider")
        return None

    direction = int(setup["direction"])
    structure_mode = str(config.option_structure_mode or "single_leg").strip().lower()
    is_vertical_debit = structure_mode == "vertical_debit"
    is_vertical_credit = structure_mode == "vertical_credit"
    is_vertical_pair = is_vertical_debit or is_vertical_credit
    enrichment_mode = _normalize_option_chain_snapshot_enrichment_mode(
        getattr(config, "option_chain_snapshot_enrichment_mode", "full")
    )

    selected_contract = self._select_contract(
        ticker=ticker,
        day=day,
        direction=direction,
        entry_underlying=float(setup["entry_underlying"]),
        config=config,
        selection_ts=setup.get("entry_ts") if isinstance(setup.get("entry_ts"), datetime) else None,
    )
    selection_meta = dict(self._last_contract_selection_meta or {})
    if int(selection_meta.get("pool_contract_count") or 0) > 0 or selected_contract is not None:
        self._bump_option_funnel("option_chain_available")
    if selected_contract is None:
        selection_rejections = dict(selection_meta.get("rejection_counts") or {})
        for reason, amount in selection_rejections.items():
            self._bump_option_rejection(str(reason), int(amount or 0))
        final_reason = str(self._last_contract_selection_reason or "contract_not_found")
        if final_reason not in selection_rejections:
            self._bump_option_rejection(final_reason)
        return None
    self._bump_option_funnel("contract_selected")

    long_contract: Optional[Dict[str, Any]] = None
    short_contract: Optional[Dict[str, Any]] = None
    short_option_symbol = ""
    long_option_symbol = ""
    short_strike = 0.0
    long_strike = 0.0
    spread_width: Optional[float] = None
    option_leg_count = 1
    if is_vertical_credit:
        short_contract = dict(selected_contract)
        short_contract = self._maybe_fill_contract_open_interest(
            ticker=ticker,
            day=day,
            contract=short_contract,
            enrichment_mode=enrichment_mode,
        )
        short_option_symbol = str(short_contract.get("symbol") or "").strip()
        if not short_option_symbol:
            self._bump_option_rejection("contract_symbol_missing")
            return None
        short_strike = _safe_float(short_contract.get("strike_price")) or 0.0
        long_contract = self._select_vertical_credit_long_leg(
            ticker=ticker,
            day=day,
            direction=direction,
            short_contract=short_contract,
            config=config,
            selection_ts=setup.get("entry_ts") if isinstance(setup.get("entry_ts"), datetime) else None,
        )
        if long_contract is None:
            return None
        long_contract = self._maybe_fill_contract_open_interest(
            ticker=ticker,
            day=day,
            contract=dict(long_contract),
            enrichment_mode=enrichment_mode,
        )
        long_option_symbol = str(long_contract.get("symbol") or "").strip()
        if not long_option_symbol:
            self._bump_option_rejection("vertical_credit_long_leg_missing")
            return None
        long_strike = _safe_float(long_contract.get("strike_price")) or 0.0
        spread_width = abs(float(short_strike) - float(long_strike))
        if spread_width <= 0.0:
            self._bump_option_rejection("vertical_credit_long_leg_missing")
            return None
        option_leg_count = 2
    else:
        long_contract = dict(selected_contract)
        long_contract = self._maybe_fill_contract_open_interest(
            ticker=ticker,
            day=day,
            contract=long_contract,
            enrichment_mode=enrichment_mode,
        )
        long_option_symbol = str(long_contract.get("symbol") or "").strip()
        if not long_option_symbol:
            self._bump_option_rejection("contract_symbol_missing")
            return None
        long_strike = _safe_float(long_contract.get("strike_price")) or 0.0
    if is_vertical_debit:
        short_contract = self._select_vertical_short_leg(
            ticker=ticker,
            day=day,
            direction=direction,
            long_contract=long_contract or {},
            config=config,
            selection_ts=setup.get("entry_ts") if isinstance(setup.get("entry_ts"), datetime) else None,
        )
        if short_contract is None:
            return None
        short_contract = self._maybe_fill_contract_open_interest(
            ticker=ticker,
            day=day,
            contract=dict(short_contract),
            enrichment_mode=enrichment_mode,
        )
        short_option_symbol = str(short_contract.get("symbol") or "").strip()
        if not short_option_symbol:
            self._bump_option_rejection("vertical_short_leg_missing")
            return None
        short_strike = _safe_float(short_contract.get("strike_price")) or 0.0
        spread_width = abs(float(short_strike) - float(long_strike))
        if spread_width <= 0.0:
            self._bump_option_rejection("vertical_short_leg_missing")
            return None
        option_leg_count = 2
    trade_option_symbol = (
        long_option_symbol
        if not is_vertical_pair
        else f"VERTICAL:{long_option_symbol}|{short_option_symbol}"
    )

    exit_day_raw = exit_plan.get("exit_day")
    exit_day = exit_day_raw if isinstance(exit_day_raw, date) else day
    primary_option_symbol = short_option_symbol if is_vertical_credit else long_option_symbol
    entry_bars = self._load_option_bars(symbol=primary_option_symbol, day=day)
    if not entry_bars:
        self._bump_option_rejection("option_bars_missing")
        return None
    if exit_day == day:
        exit_bars = entry_bars
    else:
        exit_bars = self._load_option_bars(symbol=primary_option_symbol, day=exit_day)
        if not exit_bars:
            self._bump_option_rejection("option_bars_missing")
            return None
    secondary_entry_bars: Optional[List[Dict[str, Any]]] = None
    secondary_exit_bars: Optional[List[Dict[str, Any]]] = None
    if is_vertical_pair:
        secondary_symbol = short_option_symbol if is_vertical_debit else long_option_symbol
        secondary_entry_bars = self._load_option_bars(symbol=secondary_symbol, day=day)
        if exit_day == day:
            secondary_exit_bars = secondary_entry_bars
        elif secondary_entry_bars:
            secondary_exit_bars = self._load_option_bars(symbol=secondary_symbol, day=exit_day)

    entry_delay_base = max(int(config.execution_entry_delay_minutes), 0)
    exit_delay_base = max(int(config.execution_exit_delay_minutes), 0)
    randomization_enabled = bool(config.execution_delay_randomization)
    entry_delay = _jittered_delay_minutes(
        base_delay_minutes=entry_delay_base,
        jitter_minutes=max(int(config.execution_entry_delay_jitter_minutes), 0),
        randomization_enabled=randomization_enabled,
        random_seed=int(config.execution_delay_random_seed),
        seed_key=(
            f"{ticker}|{day.isoformat()}|{trade_option_symbol}|entry|"
            f"{setup['entry_ts'].isoformat() if isinstance(setup.get('entry_ts'), datetime) else setup.get('entry_ts')}"
        ),
    )
    exit_delay = _jittered_delay_minutes(
        base_delay_minutes=exit_delay_base,
        jitter_minutes=max(int(config.execution_exit_delay_jitter_minutes), 0),
        randomization_enabled=randomization_enabled,
        random_seed=int(config.execution_delay_random_seed),
        seed_key=(
            f"{ticker}|{day.isoformat()}|{trade_option_symbol}|exit|"
            f"{exit_plan['exit_ts'].isoformat() if isinstance(exit_plan.get('exit_ts'), datetime) else exit_plan.get('exit_ts')}"
        ),
    )
    delayed_entry_ts = setup["entry_ts"] + timedelta(minutes=entry_delay)
    delayed_exit_ts = exit_plan["exit_ts"] + timedelta(minutes=exit_delay)
    delayed_entry_ts = _apply_execution_timing_model(
        delayed_entry_ts,
        model=str(config.execution_timing_model or "bar_open"),
        poll_seconds=int(config.execution_poll_seconds),
        signal_confirm_seconds=int(config.execution_entry_signal_confirm_seconds),
        fill_latency_seconds=int(config.execution_entry_fill_latency_seconds),
    )
    delayed_exit_ts = _apply_execution_timing_model(
        delayed_exit_ts,
        model=str(config.execution_timing_model or "bar_open"),
        poll_seconds=int(config.execution_poll_seconds),
        signal_confirm_seconds=int(config.execution_exit_signal_confirm_seconds),
        fill_latency_seconds=int(config.execution_exit_fill_latency_seconds),
    )

    entry_bar = _first_bar_on_or_after(entry_bars, delayed_entry_ts)
    exit_bar = _first_bar_on_or_after(exit_bars, delayed_exit_ts)
    if entry_bar is None or exit_bar is None:
        self._bump_option_rejection("entry_or_exit_bar_missing")
        return None

    entry_bar_close = float(entry_bar.get("close") or 0.0)
    entry_fill_ts = entry_bar["ts"]
    entry_raw = _causal_bar_fill_price(entry_bar)
    exit_fill_ts = exit_bar["ts"]
    exit_raw = _causal_bar_fill_price(exit_bar)
    effective_exit_reason = str(exit_plan.get("exit_reason") or "")
    effective_exit_ts = delayed_exit_ts
    option_premium_stop_triggered = False
    option_premium_stop_price_raw: Optional[float] = None
    entry_volume = int(entry_bar.get("volume") or 0)
    entry_high = float(entry_bar.get("high") or 0.0)
    entry_low = float(entry_bar.get("low") or 0.0)
    entry_bar_range_pct = ((entry_high - entry_low) / entry_bar_close) if entry_bar_close > 0 else 0.0
    short_entry_volume = 0
    short_entry_bar_range_pct = 0.0

    quote_pricing_enabled = bool(config.use_option_quotes_for_fills)
    quote_fallback_enabled = bool(config.option_quote_fill_fallback_to_bar_close)
    fill_pricing_source = "bar_open"
    used_quote_fallback = False
    can_use_quote_fill = False

    entry_quote: Optional[Dict[str, Any]] = None
    exit_quote: Optional[Dict[str, Any]] = None
    entry_quote_bid: Optional[float] = None
    entry_quote_ask: Optional[float] = None
    entry_quote_mid: Optional[float] = None
    entry_quote_spread_abs: Optional[float] = None
    entry_quote_spread_pct: Optional[float] = None
    exit_quote_bid: Optional[float] = None
    exit_quote_ask: Optional[float] = None
    short_entry_quote: Optional[Dict[str, Any]] = None
    short_exit_quote: Optional[Dict[str, Any]] = None
    short_entry_quote_bid: Optional[float] = None
    short_entry_quote_ask: Optional[float] = None
    short_exit_quote_bid: Optional[float] = None
    short_exit_quote_ask: Optional[float] = None
    entry_combined_spread_abs: Optional[float] = None
    entry_combined_spread_to_debit_ratio: Optional[float] = None
    entry_combined_spread_to_credit_ratio: Optional[float] = None
    expected_move_to_extrinsic_ratio: Optional[float] = None
    expected_move_to_spread_ratio: Optional[float] = None
    expected_move_to_debit_ratio: Optional[float] = None
    short_strike_buffer_pct: Optional[float] = None
    credit_to_width_ratio: Optional[float] = None
    premium_take_profit_triggered = False
    premium_stop_triggered = False
    option_take_profit_pct = max(float(config.option_take_profit_pct), 0.0)
    option_max_loss_pct = max(float(config.option_max_loss_pct), 0.0)
    short_contract_open_interest = int(short_contract.get("open_interest") or 0) if isinstance(short_contract, dict) else 0
    secondary_entry_bar: Optional[Dict[str, Any]] = None
    secondary_exit_bar: Optional[Dict[str, Any]] = None
    if is_vertical_pair and secondary_entry_bars and secondary_exit_bars:
        secondary_entry_bar = _first_bar_on_or_after(secondary_entry_bars, delayed_entry_ts)
        secondary_exit_bar = _first_bar_on_or_after(secondary_exit_bars, delayed_exit_ts)
        if secondary_entry_bar is None or secondary_exit_bar is None:
            self._bump_option_rejection("entry_or_exit_bar_missing")
            return None
        short_entry_volume = int(secondary_entry_bar.get("volume") or 0)
        short_entry_high = float(secondary_entry_bar.get("high") or 0.0)
        short_entry_low = float(secondary_entry_bar.get("low") or 0.0)
        short_entry_close = float(secondary_entry_bar.get("close") or 0.0)
        short_entry_bar_range_pct = (
            (short_entry_high - short_entry_low) / short_entry_close
            if short_entry_close > 0.0
            else 0.0
        )
    self._bump_option_funnel("entry_exit_bars_available")
    entry_quote_ready = False
    exit_quote_ready = False

    if quote_pricing_enabled:
        entry_quotes = self._load_option_quotes(symbol=primary_option_symbol, day=day)
        entry_quote = self._lookup_option_quote_on_or_after(
            symbol=primary_option_symbol,
            day=day,
            ts=delayed_entry_ts,
        )
        if entry_quote is not None:
            entry_quote_bid = _safe_float(entry_quote.get("bid"))
            entry_quote_ask = _safe_float(entry_quote.get("ask"))
            if entry_quote_bid is not None and entry_quote_bid > 0 and entry_quote_ask is not None and entry_quote_ask > 0:
                entry_quote_mid = (entry_quote_bid + entry_quote_ask) / 2.0
                entry_quote_spread_abs = max(entry_quote_ask - entry_quote_bid, 0.0)
                if entry_quote_mid > 0:
                    entry_quote_spread_pct = entry_quote_spread_abs / entry_quote_mid
        if is_vertical_pair:
            secondary_symbol = short_option_symbol if is_vertical_debit else long_option_symbol
            short_entry_quotes = self._load_option_quotes(symbol=secondary_symbol, day=day)
            short_entry_quote = self._lookup_option_quote_on_or_after(
                symbol=secondary_symbol,
                day=day,
                ts=delayed_entry_ts,
            )
            if short_entry_quote is not None:
                short_entry_quote_bid = _safe_float(short_entry_quote.get("bid"))
                short_entry_quote_ask = _safe_float(short_entry_quote.get("ask"))
        if is_vertical_debit:
            entry_quote_ready = bool(
                entry_quote_ask is not None
                and entry_quote_ask > 0.0
                and short_entry_quote_bid is not None
                and short_entry_quote_bid > 0.0
            )
        elif is_vertical_credit:
            entry_quote_ready = bool(
                entry_quote_bid is not None
                and entry_quote_bid > 0.0
                and short_entry_quote_ask is not None
                and short_entry_quote_ask > 0.0
            )
        else:
            entry_quote_ready = bool(entry_quote_ask is not None and entry_quote_ask > 0.0)

    if is_vertical_credit:
        if not secondary_entry_bars or not secondary_exit_bars:
            self._bump_option_rejection("option_bars_missing")
            return None
        fallback_stop = _apply_vertical_credit_premium_exits(
            entry_credit_raw=max(float(entry_raw), 0.0),
            take_profit_capture_pct=float(config.option_credit_take_profit_capture_pct),
            stop_loss_multiple=float(config.option_credit_stop_loss_multiple),
            short_entry_bar=entry_bar,
            short_exit_bar=exit_bar,
            short_entry_bars=entry_bars,
            short_exit_bars=exit_bars,
            long_entry_bars=secondary_entry_bars or [],
            long_exit_bars=secondary_exit_bars or [],
            day=day,
            exit_day=exit_day,
            default_exit_reason=str(exit_plan.get("exit_reason") or ""),
            default_exit_ts=delayed_exit_ts,
        )
    elif is_vertical_debit:
        if secondary_entry_bar is None or secondary_exit_bar is None or not secondary_entry_bars or not secondary_exit_bars:
            self._bump_option_rejection("option_bars_missing")
            return None
        fallback_stop = _apply_vertical_debit_premium_exits(
            entry_debit_raw=max(
                _causal_bar_fill_price(entry_bar) - _causal_bar_fill_price(secondary_entry_bar),
                0.0,
            ),
            option_take_profit_pct=option_take_profit_pct,
            option_max_loss_pct=option_max_loss_pct,
            long_entry_bar=entry_bar,
            long_exit_bar=exit_bar,
            long_entry_bars=entry_bars,
            long_exit_bars=exit_bars,
            short_entry_bar=secondary_entry_bar,
            short_exit_bar=secondary_exit_bar,
            short_entry_bars=secondary_entry_bars,
            short_exit_bars=secondary_exit_bars,
            day=day,
            exit_day=exit_day,
            default_exit_reason=str(exit_plan.get("exit_reason") or ""),
            default_exit_ts=delayed_exit_ts,
        )
    else:
        fallback_stop = _apply_option_premium_stop(
            entry_price_raw=entry_raw,
            option_take_profit_pct=option_take_profit_pct,
            option_max_loss_pct=option_max_loss_pct,
            entry_bar=entry_bar,
            exit_bar=exit_bar,
            entry_bars=entry_bars,
            exit_bars=exit_bars,
            day=day,
            exit_day=exit_day,
            default_exit_reason=str(exit_plan.get("exit_reason") or ""),
            default_exit_ts=delayed_exit_ts,
        )

    if quote_pricing_enabled and (
        (is_vertical_credit and entry_quote_bid is not None and entry_quote_bid > 0.0)
        or (entry_quote_ask is not None and entry_quote_ask > 0.0)
    ):
        if is_vertical_credit:
            quote_stop = dict(fallback_stop)
        elif is_vertical_debit:
            if short_entry_quote_bid is not None and short_entry_quote_bid > 0.0:
                if secondary_entry_bar is None or secondary_exit_bar is None or not secondary_entry_bars or not secondary_exit_bars:
                    self._bump_option_rejection("option_bars_missing")
                    return None
                long_default_exit_quotes = (
                    entry_quotes
                    if exit_day == day
                    else self._load_option_quotes(symbol=primary_option_symbol, day=exit_day)
                )
                short_default_exit_quotes = (
                    short_entry_quotes
                    if exit_day == day
                    else self._load_option_quotes(symbol=secondary_symbol, day=exit_day)
                )
                entry_quote_ts = (
                    max(
                        [entry_quote["ts"], short_entry_quote["ts"]],
                        key=_as_utc_aware,
                    )
                    if isinstance(entry_quote.get("ts"), datetime)
                    and isinstance(short_entry_quote.get("ts"), datetime)
                    else delayed_entry_ts
                )
                quote_stop = _apply_vertical_debit_premium_exits_from_quotes(
                    entry_debit_raw=max(float(entry_quote_ask) - float(short_entry_quote_bid), 0.0),
                    option_take_profit_pct=option_take_profit_pct,
                    option_max_loss_pct=option_max_loss_pct,
                    entry_fill_ts=entry_quote_ts,
                    default_exit_bar=exit_bar,
                    default_exit_reason=str(exit_plan.get("exit_reason") or ""),
                    default_exit_ts=delayed_exit_ts,
                    long_same_day_quotes=entry_quotes,
                    long_exit_day_quotes=long_default_exit_quotes,
                    short_same_day_quotes=short_entry_quotes,
                    short_exit_day_quotes=short_default_exit_quotes,
                    day=day,
                    exit_day=exit_day,
                )
            else:
                quote_stop = dict(fallback_stop)
        else:
            default_exit_quotes = (
                entry_quotes
                if exit_day == day
                else self._load_option_quotes(symbol=primary_option_symbol, day=exit_day)
            )
            quote_stop = _apply_option_premium_stop_from_quotes(
                entry_price_raw=float(entry_quote_ask),
                option_take_profit_pct=option_take_profit_pct,
                option_max_loss_pct=option_max_loss_pct,
                entry_fill_ts=entry_quote["ts"] if isinstance(entry_quote.get("ts"), datetime) else delayed_entry_ts,
                default_exit_bar=exit_bar,
                default_exit_reason=str(exit_plan.get("exit_reason") or ""),
                default_exit_ts=delayed_exit_ts,
                same_day_quotes=entry_quotes,
                exit_day_quotes=default_exit_quotes,
                day=day,
                exit_day=exit_day,
            )
        quote_exit_day = _as_et(quote_stop["effective_exit_ts"]).date()
        if quote_exit_day == day:
            exit_quotes = entry_quotes
        else:
            exit_quotes = self._load_option_quotes(symbol=primary_option_symbol, day=quote_exit_day)
        exit_quote = self._lookup_option_quote_on_or_after(
            symbol=primary_option_symbol,
            day=quote_exit_day,
            ts=quote_stop["effective_exit_ts"],
            fallback_last=False,
        )
        if exit_quote is not None:
            exit_quote_bid = _safe_float(exit_quote.get("bid"))
            exit_quote_ask = _safe_float(exit_quote.get("ask"))
        if is_vertical_pair:
            secondary_symbol = short_option_symbol if is_vertical_debit else long_option_symbol
            if quote_exit_day == day:
                short_exit_quotes = self._load_option_quotes(symbol=secondary_symbol, day=day)
            else:
                short_exit_quotes = self._load_option_quotes(symbol=secondary_symbol, day=quote_exit_day)
            short_exit_quote = self._lookup_option_quote_on_or_after(
                symbol=secondary_symbol,
                day=quote_exit_day,
                ts=quote_stop["effective_exit_ts"],
                fallback_last=False,
            )
            if short_exit_quote is not None:
                short_exit_quote_bid = _safe_float(short_exit_quote.get("bid"))
                short_exit_quote_ask = _safe_float(short_exit_quote.get("ask"))
            if is_vertical_debit:
                can_use_quote_fill = bool(
                    short_entry_quote_bid is not None
                    and short_entry_quote_bid > 0.0
                    and exit_quote_bid is not None
                    and exit_quote_bid > 0.0
                    and short_exit_quote_ask is not None
                    and short_exit_quote_ask > 0.0
                )
            else:
                can_use_quote_fill = bool(
                    entry_quote_bid is not None
                    and entry_quote_bid > 0.0
                    and short_entry_quote_ask is not None
                    and short_entry_quote_ask > 0.0
                    and exit_quote_ask is not None
                    and exit_quote_ask > 0.0
                    and short_exit_quote_bid is not None
                    and short_exit_quote_bid >= 0.0
                )
        else:
            can_use_quote_fill = bool(exit_quote_bid is not None and exit_quote_bid > 0)
        if is_vertical_debit:
            exit_quote_ready = bool(
                exit_quote_bid is not None
                and exit_quote_bid > 0.0
                and short_exit_quote_ask is not None
                and short_exit_quote_ask > 0.0
            )
        elif is_vertical_credit:
            exit_quote_ready = bool(
                exit_quote_ask is not None
                and exit_quote_ask > 0.0
                and short_exit_quote_bid is not None
                and short_exit_quote_bid >= 0.0
            )
        else:
            exit_quote_ready = bool(exit_quote_bid is not None and exit_quote_bid > 0.0)
        if can_use_quote_fill:
            self._bump_option_funnel("quote_fill_available")
            if is_vertical_debit:
                entry_raw = float(entry_quote_ask) - float(short_entry_quote_bid)
            elif is_vertical_credit:
                entry_raw = float(entry_quote_bid) - float(short_entry_quote_ask)
            else:
                entry_raw = float(entry_quote_ask)
            if is_vertical_pair:
                pair_entry_ts_candidates = [
                    quote.get("ts")
                    for quote in (entry_quote, short_entry_quote)
                    if isinstance(quote, dict) and isinstance(quote.get("ts"), datetime)
                ]
                if pair_entry_ts_candidates:
                    entry_fill_ts = max(pair_entry_ts_candidates, key=_as_utc_aware)
            elif isinstance(entry_quote.get("ts"), datetime):
                entry_fill_ts = entry_quote["ts"]
            exit_bar = quote_stop["exit_bar"]
            effective_exit_reason = str(quote_stop["effective_exit_reason"] or "")
            effective_exit_ts = quote_stop["effective_exit_ts"]
            option_premium_stop_triggered = bool(quote_stop.get("option_premium_stop_triggered"))
            option_premium_stop_price_raw = quote_stop.get("option_premium_stop_price_raw")
            premium_take_profit_triggered = bool(quote_stop.get("premium_take_profit_triggered"))
            premium_stop_triggered = bool(quote_stop.get("premium_stop_triggered"))
            if is_vertical_debit:
                exit_raw = max(float(exit_quote_bid) - float(short_exit_quote_ask), 0.0)
                fill_pricing_source = "quotes_vertical_debit"
                pair_exit_ts_candidates = [
                    quote.get("ts")
                    for quote in (exit_quote, short_exit_quote)
                    if isinstance(quote, dict) and isinstance(quote.get("ts"), datetime)
                ]
                if pair_exit_ts_candidates:
                    exit_fill_ts = max(pair_exit_ts_candidates, key=_as_utc_aware)
            elif is_vertical_credit:
                exit_raw = max(float(exit_quote_ask) - float(short_exit_quote_bid), 0.0)
                fill_pricing_source = "quotes_vertical_credit"
                pair_exit_ts_candidates = [
                    quote.get("ts")
                    for quote in (exit_quote, short_exit_quote)
                    if isinstance(quote, dict) and isinstance(quote.get("ts"), datetime)
                ]
                if pair_exit_ts_candidates:
                    exit_fill_ts = max(pair_exit_ts_candidates, key=_as_utc_aware)
            else:
                exit_raw = float(exit_quote_bid)
                if isinstance(exit_quote.get("ts"), datetime):
                    exit_fill_ts = exit_quote["ts"]
                fill_pricing_source = "quotes"
                if premium_take_profit_triggered:
                    fill_pricing_source = "quotes_premium_take_profit"
                if option_premium_stop_triggered and option_premium_stop_price_raw is not None:
                    fill_pricing_source = "quotes_option_premium_stop"
                    exit_raw = min(exit_raw, float(option_premium_stop_price_raw))

    if not can_use_quote_fill:
        exit_bar = fallback_stop["exit_bar"]
        effective_exit_reason = str(fallback_stop["effective_exit_reason"] or "")
        effective_exit_ts = fallback_stop["effective_exit_ts"]
        option_premium_stop_triggered = bool(fallback_stop.get("option_premium_stop_triggered"))
        option_premium_stop_price_raw = fallback_stop.get("option_premium_stop_price_raw")
        premium_take_profit_triggered = bool(fallback_stop.get("premium_take_profit_triggered"))
        premium_stop_triggered = bool(fallback_stop.get("premium_stop_triggered"))
        if is_vertical_pair:
            if secondary_entry_bar is None or secondary_exit_bar is None:
                self._bump_option_rejection("option_bars_missing")
                return None
            if is_vertical_debit:
                entry_raw = _causal_bar_fill_price(entry_bar) - _causal_bar_fill_price(secondary_entry_bar or {})
                exit_raw = max(float(fallback_stop["exit_raw"]) - _causal_bar_fill_price(secondary_exit_bar or {}), 0.0)
                fill_pricing_source = "bar_open_vertical_debit"
            else:
                entry_raw = _causal_bar_fill_price(entry_bar) - _causal_bar_fill_price(secondary_entry_bar or {})
                exit_raw = float(fallback_stop["exit_raw"])
                fill_pricing_source = "bar_open_vertical_credit"
        else:
            entry_raw = _causal_bar_fill_price(entry_bar)
            exit_raw = float(fallback_stop["exit_raw"])
        entry_fill_ts = entry_bar["ts"]
        exit_fill_ts = exit_bar["ts"]
        if quote_pricing_enabled:
            if quote_fallback_enabled:
                used_quote_fallback = True
                self._bump_option_funnel("quote_fill_fallback_used")
                fill_pricing_source = (
                    "bar_open_quote_fallback_vertical_debit"
                    if is_vertical_debit
                    else ("bar_open_quote_fallback_vertical_credit" if is_vertical_credit else "bar_open_quote_fallback")
                )
            else:
                if not entry_quote_ready:
                    self._bump_option_rejection("quote_missing_after_entry_ts")
                elif not exit_quote_ready:
                    self._bump_option_rejection("quote_missing_after_exit_ts")
                self._bump_option_rejection("quotes_unavailable_without_fallback")
                return None

    if entry_raw <= 0:
        self._bump_option_rejection("entry_price_nonpositive")
        return None
    if (
        isinstance(entry_fill_ts, datetime)
        and isinstance(effective_exit_ts, datetime)
        and _as_utc_aware(entry_fill_ts) >= _as_utc_aware(effective_exit_ts)
    ):
        self._bump_option_rejection("entry_after_effective_exit")
        return None
    if (
        isinstance(entry_fill_ts, datetime)
        and isinstance(exit_fill_ts, datetime)
        and _as_utc_aware(entry_fill_ts) >= _as_utc_aware(exit_fill_ts)
    ):
        self._bump_option_rejection("entry_after_exit_fill")
        return None
    self._bump_option_funnel("pricing_resolved")
    if is_vertical_pair:
        if short_entry_quote is not None:
            short_entry_volume = max(
                int(short_entry_quote.get("bid_size") or 0),
                int(short_entry_quote.get("ask_size") or 0),
                short_entry_volume,
            )
        if short_entry_volume > 0:
            entry_volume = min(entry_volume, short_entry_volume) if entry_volume > 0 else short_entry_volume
        if short_entry_bar_range_pct > 0.0:
            entry_bar_range_pct = max(entry_bar_range_pct, short_entry_bar_range_pct)
        if spread_width is None or spread_width <= 0.0:
            self._bump_option_rejection("vertical_short_leg_missing" if is_vertical_debit else "vertical_credit_long_leg_missing")
            return None
        if is_vertical_debit:
            debit_to_width_ratio = float(entry_raw) / float(spread_width)
            if debit_to_width_ratio > max(float(config.option_vertical_max_debit_to_width_ratio), 0.0):
                self._bump_option_rejection("vertical_debit_to_width_ratio")
                return None
            if (
                entry_quote_bid is not None
                and entry_quote_ask is not None
                and short_entry_quote_bid is not None
                and short_entry_quote_ask is not None
            ):
                entry_combined_spread_abs = max(float(entry_quote_ask) - float(entry_quote_bid), 0.0) + max(
                    float(short_entry_quote_ask) - float(short_entry_quote_bid),
                    0.0,
                )
                if entry_raw > 0.0:
                    entry_combined_spread_to_debit_ratio = entry_combined_spread_abs / float(entry_raw)
                    if (
                        entry_combined_spread_to_debit_ratio
                        > max(float(config.option_vertical_max_combined_spread_to_debit_ratio), 0.0)
                    ):
                        self._bump_option_rejection("vertical_combined_spread_to_debit_ratio")
                        return None
        else:
            credit_to_width_ratio = float(entry_raw) / float(spread_width)
            if credit_to_width_ratio < max(float(config.option_vertical_min_credit_to_width_ratio), 0.0):
                self._bump_option_rejection("vertical_credit_to_width_ratio")
                return None
            max_credit_to_width = max(float(config.option_vertical_max_credit_to_width_ratio), 0.0)
            if max_credit_to_width > 0.0 and credit_to_width_ratio > max_credit_to_width:
                self._bump_option_rejection("vertical_credit_to_width_ratio")
                return None
            if entry_raw < max(float(config.option_credit_min_entry_credit), 0.0):
                self._bump_option_rejection("vertical_credit_to_width_ratio")
                return None
            short_strike_buffer_pct = (
                abs(float(setup.get("entry_underlying") or 0.0) - float(short_strike))
                / max(float(setup.get("entry_underlying") or 0.0), 1.0)
            )
            if short_strike_buffer_pct < max(float(config.option_credit_min_short_strike_buffer_pct), 0.0):
                self._bump_option_rejection("vertical_credit_buffer_too_small")
                return None
            if (
                entry_quote_bid is not None
                and entry_quote_ask is not None
                and short_entry_quote_bid is not None
                and short_entry_quote_ask is not None
            ):
                entry_combined_spread_abs = max(float(entry_quote_ask) - float(entry_quote_bid), 0.0) + max(
                    float(short_entry_quote_ask) - float(short_entry_quote_bid),
                    0.0,
                )
                if entry_raw > 0.0:
                    entry_combined_spread_to_credit_ratio = entry_combined_spread_abs / float(entry_raw)
                    if (
                        entry_combined_spread_to_credit_ratio
                        > max(float(config.option_vertical_max_combined_spread_to_credit_ratio), 0.0)
                    ):
                        self._bump_option_rejection("vertical_combined_spread_to_credit_ratio")
                        return None
    self._bump_option_funnel("structure_filters_passed")

    micro_filter_active = bool(config.require_option_microstructure_filter) or bool(
        config.option_structure_filter_enabled
    )
    if micro_filter_active:
        min_entry_volume = 0
        if bool(config.require_option_microstructure_filter):
            min_entry_volume = max(min_entry_volume, max(int(config.option_min_entry_volume), 0))
        if bool(config.option_structure_filter_enabled):
            min_entry_volume = max(min_entry_volume, max(int(config.option_structure_min_entry_volume), 0))
        if entry_volume < min_entry_volume:
            self._bump_option_rejection("micro_entry_volume")
            return None

        max_range_pct = 0.0
        if bool(config.require_option_microstructure_filter):
            max_range_pct = max(float(config.option_max_entry_bar_range_pct), 0.0)
        if bool(config.option_structure_filter_enabled):
            structure_cap = max(float(config.option_structure_max_entry_bar_range_pct), 0.0)
            max_range_pct = structure_cap if max_range_pct <= 0 else min(max_range_pct, structure_cap)
        if max_range_pct > 0 and entry_bar_range_pct > max_range_pct:
            self._bump_option_rejection("micro_entry_range")
            return None

        min_entry_price = 0.0
        if bool(config.require_option_microstructure_filter):
            min_entry_price = max(min_entry_price, max(float(config.option_min_entry_price), 0.0))
        if bool(config.option_structure_filter_enabled):
            min_entry_price = max(min_entry_price, max(float(config.option_structure_min_entry_price), 0.0))
        if entry_raw < min_entry_price:
            self._bump_option_rejection("micro_entry_price")
            return None

        max_spread_pct = 0.0
        if bool(config.require_option_microstructure_filter):
            max_spread_pct = max(float(config.option_max_entry_spread_pct), 0.0)
        if bool(config.option_structure_filter_enabled):
            structure_spread_cap = max(float(config.option_structure_max_entry_spread_pct), 0.0)
            max_spread_pct = structure_spread_cap if max_spread_pct <= 0 else min(
                max_spread_pct,
                structure_spread_cap,
            )
        if max_spread_pct > 0 and can_use_quote_fill:
            if entry_quote_spread_pct is None or entry_quote_spread_pct > max_spread_pct:
                self._bump_option_rejection("micro_quote_spread")
                return None
    self._bump_option_funnel("microstructure_filters_passed")

    expected_move = _expected_underlying_target_move(
        setup=setup,
        take_profit_rr=float(config.take_profit_rr),
    )
    if expected_move is not None:
        if (not is_vertical_pair) and can_use_quote_fill and entry_quote_ask is not None and entry_quote_ask > 0:
            option_type = "call" if int(setup.get("direction") or 0) > 0 else "put"
            intrinsic_value = _option_intrinsic_value(
                option_type=option_type,
                underlying_price=float(setup.get("entry_underlying") or 0.0),
                strike=float(long_contract.get("strike_price") or 0.0),
            )
            extrinsic_value = max(float(entry_quote_ask) - intrinsic_value, 0.0)
            min_move_to_extrinsic = max(float(config.option_min_expected_move_to_extrinsic_ratio), 0.0)
            min_move_to_spread = max(float(config.option_min_expected_move_to_spread_ratio), 0.0)
            if min_move_to_extrinsic > 0.0:
                if extrinsic_value <= 0.0:
                    move_to_extrinsic_ratio = float("inf")
                else:
                    move_to_extrinsic_ratio = float(expected_move) / float(extrinsic_value)
                expected_move_to_extrinsic_ratio = move_to_extrinsic_ratio
                if move_to_extrinsic_ratio < min_move_to_extrinsic:
                    self._bump_option_rejection("move_to_cost_extrinsic_ratio")
                    return None
            if min_move_to_spread > 0.0:
                if entry_quote_spread_abs is None or entry_quote_spread_abs <= 0.0:
                    self._bump_option_rejection("move_to_cost_spread_ratio")
                    return None
                move_to_spread_ratio = float(expected_move) / float(entry_quote_spread_abs)
                expected_move_to_spread_ratio = move_to_spread_ratio
                if move_to_spread_ratio < min_move_to_spread:
                    self._bump_option_rejection("move_to_cost_spread_ratio")
                    return None
        if is_vertical_debit:
            min_move_to_debit = max(float(config.option_min_expected_move_to_debit_ratio), 0.0)
            if min_move_to_debit > 0.0:
                if entry_raw <= 0.0:
                    self._bump_option_rejection("move_to_cost_debit_ratio")
                    return None
                expected_move_to_debit_ratio = float(expected_move) / float(entry_raw)
                if expected_move_to_debit_ratio < min_move_to_debit:
                    self._bump_option_rejection("move_to_cost_debit_ratio")
                    return None
        if is_vertical_credit:
            min_buffer_ratio = max(float(config.option_credit_min_expected_move_buffer_ratio), 0.0)
            if min_buffer_ratio > 0.0:
                short_strike_buffer = abs(float(setup.get("entry_underlying") or 0.0) - float(short_strike))
                if expected_move <= 0.0:
                    buffer_ratio = float("inf")
                else:
                    buffer_ratio = short_strike_buffer / float(expected_move)
                expected_move_to_debit_ratio = buffer_ratio
                if buffer_ratio < min_buffer_ratio:
                    self._bump_option_rejection("vertical_credit_buffer_too_small")
                    return None
    self._bump_option_funnel("move_cost_filters_passed")

    static_slippage_bps = max(float(config.option_slippage_bps), 0.0)
    range_slippage_bps = max(float(config.option_range_adverse_fill_fraction), 0.0) * max(
        entry_bar_range_pct,
        0.0,
    ) * 10000.0
    max_range_slippage_bps = max(float(config.option_range_adverse_fill_max_bps), 0.0)
    if max_range_slippage_bps > 0:
        range_slippage_bps = min(range_slippage_bps, max_range_slippage_bps)
    total_slippage_bps = static_slippage_bps + range_slippage_bps
    slippage = total_slippage_bps / 10000.0
    if is_vertical_credit:
        entry_price = max(0.0, entry_raw * (1.0 - slippage))
        exit_price = max(0.0, exit_raw * (1.0 + slippage))
    else:
        entry_price = entry_raw * (1.0 + slippage)
        exit_price = max(0.0, exit_raw * (1.0 - slippage))

    risk_notional = max(float(current_equity), 0.0) * max(float(config.risk_per_trade), 0.0)
    sizing_mode = str(config.option_risk_sizing_mode or "premium_at_risk").strip().lower()
    sizing_loss_fraction = (
        max(float(config.option_max_loss_pct), 0.0)
        if sizing_mode == "premium_stop" and 0.0 < float(config.option_max_loss_pct) <= 1.0
        else 1.0
    )
    commission_risk = (
        max(float(config.option_commission_per_contract), 0.0) * 2.0 * max(int(option_leg_count), 1)
        if bool(config.option_sizing_include_commission)
        else 0.0
    )
    if is_vertical_credit:
        max_loss_per_contract = max(float(spread_width or 0.0) - float(entry_price), 0.0) * 100.0
        per_contract_risk_capital = max_loss_per_contract + commission_risk
        qty = int(risk_notional / per_contract_risk_capital) if per_contract_risk_capital > 0 else 0
    else:
        per_contract_risk_capital = (entry_price * 100.0 * sizing_loss_fraction) + commission_risk
        qty = _option_qty_for_risk(
            risk_notional=risk_notional,
            entry_price=entry_price,
            commission_per_contract=float(config.option_commission_per_contract),
            include_commission=bool(config.option_sizing_include_commission),
            min_entry_price=float(config.option_sizing_min_entry_price),
            sizing_mode=sizing_mode,
            option_max_loss_pct=float(config.option_max_loss_pct),
            option_leg_count=int(option_leg_count),
        )
    qty_before_liquidity_caps = qty
    long_contract_open_interest = int(long_contract.get("open_interest") or 0)
    contract_open_interest = (
        min(long_contract_open_interest, short_contract_open_interest)
        if is_vertical_pair and short_contract_open_interest > 0
        else long_contract_open_interest
    )
    volume_cap_qty = qty
    oi_cap_qty = qty
    if config.enforce_option_liquidity_caps:
        max_volume_participation = max(float(config.option_max_entry_volume_participation), 0.0)
        if max_volume_participation <= 0:
            qty = 0
        else:
            volume_cap_qty = int(max(float(entry_volume), 0.0) * max_volume_participation)
            qty = min(qty, volume_cap_qty)

        max_oi_participation = max(float(config.option_max_open_interest_participation), 0.0)
        if max_oi_participation <= 0:
            qty = 0
        elif contract_open_interest > 0:
            oi_cap_qty = int(float(contract_open_interest) * max_oi_participation)
            qty = min(qty, oi_cap_qty)

    if qty < 1:
        self._bump_option_rejection("qty_below_1_after_caps")
        return None
    self._bump_option_funnel("sizing_passed")
    volume_participation = (float(qty) / float(entry_volume)) if entry_volume > 0 else 0.0
    oi_participation = (float(qty) / float(contract_open_interest)) if contract_open_interest > 0 else 0.0

    if is_vertical_credit:
        gross_pnl = qty * (entry_price - exit_price) * 100.0
    else:
        gross_pnl = qty * (exit_price - entry_price) * 100.0
    commission = qty * max(float(config.option_commission_per_contract), 0.0) * 2.0 * max(
        int(option_leg_count),
        1,
    )
    pnl = gross_pnl - commission
    invested = qty * per_contract_risk_capital if is_vertical_credit else qty * entry_price * 100.0
    trade_return = (pnl / invested) if invested > 0 else 0.0
    self._bump_option_funnel("entry_constructed")
    self._bump_option_funnel("trades_created")

    return BacktestTrade(
        trade_id=str(uuid.uuid4()),
        signal_id=str(uuid.uuid4()),
        ticker=ticker,
        option_symbol=trade_option_symbol,
        entry_ts=entry_fill_ts,
        exit_ts=exit_fill_ts,
        side=(
            "bull_put_credit"
            if is_vertical_credit and direction > 0
            else (
                "bear_call_credit"
                if is_vertical_credit
                else ("long_call" if direction > 0 else "long_put")
            )
        ),
        qty=qty,
        entry_price=entry_price,
        exit_price=exit_price,
        pnl=pnl,
        return_pct=trade_return,
        status="closed",
        metadata={
            "strategy": "intraday_opening_range_stocks_in_play_options",
            "strategy_variant": str(setup.get("strategy_variant") or config.strategy_variant),
            "execution_mode": "historical_options",
            "direction": direction,
            "entry_underlying": float(setup["entry_underlying"]),
            "exit_underlying": float(exit_plan["exit_underlying"]),
            "stop_underlying": float(setup["stop_underlying"]),
            "exit_reason": effective_exit_reason,
            "exit_reason_base": str(exit_plan["exit_reason"]),
            "orb_high": float(setup["orb_high"]),
            "orb_low": float(setup["orb_low"]),
            "opening_range_minutes": int(setup.get("opening_range_minutes") or 0),
            "opening_bar_direction": int(setup.get("opening_bar_direction") or 0),
            "trend_ema_fast": float(setup["trend_ema_fast"]),
            "trend_ema_slow": float(setup["trend_ema_slow"]),
            "volume_ratio": float(setup["volume_ratio"]),
            "relative_opening_volume": _safe_float(setup.get("relative_opening_volume")),
            "gap_return": _safe_float(setup.get("gap_return")),
            "atr_value": _safe_float(setup.get("atr_value")),
            "vol_regime_prev_close": _safe_float(setup.get("vol_regime_prev_close")),
            "market_regime_label": _normalize_regime_label(setup.get("market_regime_label")),
            "regime_v2_state": str(setup.get("regime_v2_state") or "unknown"),
            "regime_v2_route_state": str(setup.get("regime_v2_route_state") or "unknown"),
            "regime_v2_route_action": str(setup.get("regime_v2_route_action") or ""),
            "regime_v2_confidence": _safe_float(setup.get("regime_v2_confidence")),
            "regime_v2_selected_variant": str(setup.get("regime_v2_selected_variant") or ""),
            "regime_v2_skip_reason": str(setup.get("regime_v2_skip_reason") or ""),
            "fvg_gap": float(setup["fvg_gap"]),
            "fib_anchor": _safe_float(setup.get("fib_anchor")),
            "fib_impulse_extreme": _safe_float(setup.get("fib_impulse_extreme")),
            "fib_entry_zone_low": _safe_float(setup.get("fib_entry_zone_low")),
            "fib_entry_zone_high": _safe_float(setup.get("fib_entry_zone_high")),
            "fill_pricing_source": fill_pricing_source,
            "option_structure_mode": structure_mode,
            "option_leg_count": int(option_leg_count),
            "long_leg_symbol": long_option_symbol,
            "short_leg_symbol": short_option_symbol or None,
            "long_leg_strike": float(long_strike),
            "short_leg_strike": float(short_strike) if short_option_symbol else None,
            "spread_width": float(spread_width) if spread_width is not None else None,
            "entry_debit": float(entry_raw) if is_vertical_debit else None,
            "exit_credit": float(exit_raw) if is_vertical_debit else None,
            "entry_credit": float(entry_raw) if is_vertical_credit else None,
            "exit_debit": float(exit_raw) if is_vertical_credit else None,
            "entry_combined_spread_abs": (
                float(entry_combined_spread_abs) if entry_combined_spread_abs is not None else None
            ),
            "entry_combined_spread_to_debit_ratio": (
                float(entry_combined_spread_to_debit_ratio)
                if entry_combined_spread_to_debit_ratio is not None
                else None
            ),
            "entry_combined_spread_to_credit_ratio": (
                float(entry_combined_spread_to_credit_ratio)
                if entry_combined_spread_to_credit_ratio is not None
                else None
            ),
            "credit_to_width_ratio": float(credit_to_width_ratio) if credit_to_width_ratio is not None else None,
            "short_strike_buffer_pct": (
                float(short_strike_buffer_pct) if short_strike_buffer_pct is not None else None
            ),
            "expected_move_to_debit_ratio": (
                float(expected_move_to_debit_ratio) if expected_move_to_debit_ratio is not None else None
            ),
            "short_leg_bid_at_entry": (
                float(entry_quote_bid) if is_vertical_credit and entry_quote_bid is not None else (
                    float(short_entry_quote_bid) if short_entry_quote_bid is not None else None
                )
            ),
            "short_leg_ask_at_exit": (
                float(exit_quote_ask) if is_vertical_credit and exit_quote_ask is not None else (
                    float(short_exit_quote_ask) if short_exit_quote_ask is not None else None
                )
            ),
            "long_leg_ask_at_entry": (
                float(short_entry_quote_ask) if is_vertical_credit and short_entry_quote_ask is not None else (
                    float(entry_quote_ask) if is_vertical_debit and entry_quote_ask is not None else None
                )
            ),
            "long_leg_bid_at_exit": (
                float(short_exit_quote_bid) if is_vertical_credit and short_exit_quote_bid is not None else (
                    float(exit_quote_bid) if is_vertical_debit and exit_quote_bid is not None else None
                )
            ),
            "option_quote_pricing_enabled": bool(config.use_option_quotes_for_fills),
            "option_quote_fill_fallback_enabled": quote_fallback_enabled,
            "option_quote_fallback_used": used_quote_fallback,
            "entry_quote_ts": (
                entry_quote["ts"].isoformat()
                if isinstance(entry_quote, dict) and isinstance(entry_quote.get("ts"), datetime)
                else None
            ),
            "entry_quote_bid": entry_quote_bid,
            "entry_quote_ask": entry_quote_ask,
            "entry_quote_mid": entry_quote_mid,
            "entry_quote_spread_abs": entry_quote_spread_abs,
            "entry_quote_spread_pct": entry_quote_spread_pct,
            "exit_quote_ts": (
                exit_quote["ts"].isoformat()
                if isinstance(exit_quote, dict) and isinstance(exit_quote.get("ts"), datetime)
                else None
            ),
            "exit_quote_bid": exit_quote_bid,
            "exit_quote_ask": exit_quote_ask,
            "short_entry_quote_ts": (
                short_entry_quote["ts"].isoformat()
                if isinstance(short_entry_quote, dict) and isinstance(short_entry_quote.get("ts"), datetime)
                else None
            ),
            "short_exit_quote_ts": (
                short_exit_quote["ts"].isoformat()
                if isinstance(short_exit_quote, dict) and isinstance(short_exit_quote.get("ts"), datetime)
                else None
            ),
            "short_entry_quote_bid": short_entry_quote_bid,
            "short_entry_quote_ask": short_entry_quote_ask,
            "short_exit_quote_bid": short_exit_quote_bid,
            "short_exit_quote_ask": short_exit_quote_ask,
            "entry_price_raw": entry_raw,
            "entry_volume": entry_volume,
            "entry_volume_long_leg": int(entry_bar.get("volume") or 0),
            "entry_volume_short_leg": int(short_entry_volume),
            "entry_bar_range_pct": entry_bar_range_pct,
            "exit_price_raw": exit_raw,
            "entry_price_effective": entry_price,
            "exit_price_effective": exit_price,
            "option_take_profit_pct": option_take_profit_pct,
            "option_max_loss_pct": option_max_loss_pct,
            "option_premium_stop_triggered": option_premium_stop_triggered,
            "option_premium_stop_price_raw": option_premium_stop_price_raw,
            "premium_take_profit_triggered": premium_take_profit_triggered,
            "premium_stop_triggered": premium_stop_triggered,
            "option_slippage_bps": total_slippage_bps,
            "option_slippage_static_bps": static_slippage_bps,
            "option_slippage_range_bps": range_slippage_bps,
            "option_commission_total": commission,
            "execution_entry_delay_base_minutes": entry_delay_base,
            "execution_exit_delay_base_minutes": exit_delay_base,
            "execution_entry_delay_minutes": entry_delay,
            "execution_exit_delay_minutes": exit_delay,
            "execution_delay_randomization": randomization_enabled,
            "execution_entry_delay_jitter_minutes": int(config.execution_entry_delay_jitter_minutes),
            "execution_exit_delay_jitter_minutes": int(config.execution_exit_delay_jitter_minutes),
            "execution_delay_random_seed": int(config.execution_delay_random_seed),
            "execution_timing_model": str(config.execution_timing_model or "bar_open"),
            "execution_poll_seconds": int(config.execution_poll_seconds),
            "execution_entry_signal_confirm_seconds": int(config.execution_entry_signal_confirm_seconds),
            "execution_exit_signal_confirm_seconds": int(config.execution_exit_signal_confirm_seconds),
            "execution_entry_fill_latency_seconds": int(config.execution_entry_fill_latency_seconds),
            "execution_exit_fill_latency_seconds": int(config.execution_exit_fill_latency_seconds),
            "delayed_entry_signal_ts": delayed_entry_ts.isoformat(),
            "delayed_exit_signal_ts": delayed_exit_ts.isoformat(),
            "entry_fill_ts": (
                entry_fill_ts.isoformat()
                if isinstance(entry_fill_ts, datetime)
                else str(entry_fill_ts)
            ),
            "exit_fill_ts": (
                exit_fill_ts.isoformat()
                if isinstance(exit_fill_ts, datetime)
                else str(exit_fill_ts)
            ),
            "effective_exit_signal_ts": (
                effective_exit_ts.isoformat()
                if isinstance(effective_exit_ts, datetime)
                else str(effective_exit_ts)
            ),
            "gross_pnl": gross_pnl,
            "contract_expiration": long_contract.get("expiration_date"),
            "contract_strike": float(long_contract.get("strike_price") or 0.0),
            "contract_status": long_contract.get("status"),
            "contract_open_interest": contract_open_interest,
            "contract_open_interest_long_leg": long_contract_open_interest,
            "contract_open_interest_short_leg": short_contract_open_interest if short_option_symbol else None,
            "contract_volume_snapshot": int(long_contract.get("volume") or 0),
            "contract_volume_snapshot_short_leg": (
                int(short_contract.get("volume") or 0) if isinstance(short_contract, dict) else None
            ),
            "option_structure_filter_enabled": bool(config.option_structure_filter_enabled),
            "option_structure_min_open_interest": int(config.option_structure_min_open_interest),
            "option_structure_min_entry_volume": int(config.option_structure_min_entry_volume),
            "option_structure_max_entry_spread_pct": float(config.option_structure_max_entry_spread_pct),
            "option_structure_max_entry_bar_range_pct": float(config.option_structure_max_entry_bar_range_pct),
            "option_structure_min_entry_price": float(config.option_structure_min_entry_price),
            "option_vertical_short_leg_steps": int(config.option_vertical_short_leg_steps),
            "option_vertical_fallback_short_leg_steps": int(config.option_vertical_fallback_short_leg_steps),
            "option_vertical_max_debit_to_width_ratio": float(config.option_vertical_max_debit_to_width_ratio),
            "option_vertical_min_short_bid": float(config.option_vertical_min_short_bid),
            "option_vertical_max_combined_spread_to_debit_ratio": float(
                config.option_vertical_max_combined_spread_to_debit_ratio
            ),
            "option_vertical_credit_long_leg_steps": int(config.option_vertical_credit_long_leg_steps),
            "option_vertical_credit_fallback_long_leg_steps": int(
                config.option_vertical_credit_fallback_long_leg_steps
            ),
            "option_vertical_min_credit_to_width_ratio": float(config.option_vertical_min_credit_to_width_ratio),
            "option_vertical_max_credit_to_width_ratio": float(config.option_vertical_max_credit_to_width_ratio),
            "option_vertical_max_combined_spread_to_credit_ratio": float(
                config.option_vertical_max_combined_spread_to_credit_ratio
            ),
            "option_credit_min_short_bid": float(config.option_credit_min_short_bid),
            "option_credit_min_short_strike_buffer_pct": float(
                config.option_credit_min_short_strike_buffer_pct
            ),
            "option_credit_min_expected_move_buffer_ratio": float(
                config.option_credit_min_expected_move_buffer_ratio
            ),
            "option_credit_min_entry_credit": float(config.option_credit_min_entry_credit),
            "option_credit_take_profit_capture_pct": float(config.option_credit_take_profit_capture_pct),
            "option_credit_stop_loss_multiple": float(config.option_credit_stop_loss_multiple),
            "option_min_expected_move_to_debit_ratio": float(config.option_min_expected_move_to_debit_ratio),
            "liquidity_caps_enabled": bool(config.enforce_option_liquidity_caps),
            "option_sizing_include_commission": bool(config.option_sizing_include_commission),
            "option_sizing_min_entry_price": float(config.option_sizing_min_entry_price),
            "option_risk_sizing_mode": sizing_mode,
            "option_risk_sizing_loss_fraction": float(sizing_loss_fraction),
            "per_contract_risk_capital": float(per_contract_risk_capital),
            "option_max_entry_volume_participation": float(config.option_max_entry_volume_participation),
            "option_max_open_interest_participation": float(config.option_max_open_interest_participation),
            "option_use_contract_open_interest": bool(config.option_use_contract_open_interest),
            "open_interest_liquidity_cap_enabled": bool(
                config.enforce_option_liquidity_caps
                and float(config.option_max_open_interest_participation) > 0.0
            ),
            "open_interest_data_available": bool(contract_open_interest > 0),
            "open_interest_cap_applied": bool(
                config.enforce_option_liquidity_caps
                and float(config.option_max_open_interest_participation) > 0.0
                and contract_open_interest > 0
            ),
            "qty_before_liquidity_caps": int(qty_before_liquidity_caps),
            "qty_after_liquidity_caps": int(qty),
            "entry_volume_participation": volume_participation,
            "open_interest_participation": oi_participation,
            "volume_cap_qty": int(volume_cap_qty),
            "open_interest_cap_qty": int(oi_cap_qty),
            "contract_selection_dte": int(long_contract.get("_selection_dte") or 0),
            "contract_selection_moneyness": _safe_float(long_contract.get("_selection_moneyness")),
            "contract_selection_oi_bonus": _safe_float(long_contract.get("_selection_oi_bonus")),
            "contract_selection_score": _safe_float(long_contract.get("_selection_score")),
            "contract_selection_requested_status": str(long_contract.get("_selection_requested_status") or ""),
            "contract_selection_intrinsic_value": _safe_float(long_contract.get("_selection_intrinsic_value")),
            "contract_selection_intrinsic_share": _safe_float(long_contract.get("_selection_intrinsic_share")),
            "contract_selection_extrinsic_value": _safe_float(long_contract.get("_selection_extrinsic_value")),
            "expected_move_to_extrinsic_ratio": expected_move_to_extrinsic_ratio,
            "expected_move_to_spread_ratio": expected_move_to_spread_ratio,
        },
    )


def _map_alpaca_option_bar(symbol: str, row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    ts = parse_datetime(row.get("t"))
    if ts is None:
        return None
    return {
        "symbol": symbol,
        "ts": ts,
        "open": float(row.get("o") or 0.0),
        "high": float(row.get("h") or 0.0),
        "low": float(row.get("l") or 0.0),
        "close": float(row.get("c") or 0.0),
        "volume": int(row.get("v") or 0),
    }


def _map_alpaca_option_quote(symbol: str, row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    ts = parse_datetime(row.get("t"))
    if ts is None:
        return None
    bid = _safe_float(row.get("bp", row.get("bid_price")))
    ask = _safe_float(row.get("ap", row.get("ask_price")))
    if bid is not None and bid < 0:
        bid = None
    if ask is not None and ask < 0:
        ask = None
    if bid is None and ask is None:
        return None
    return {
        "symbol": symbol,
        "ts": ts,
        "bid": bid,
        "ask": ask,
        "bid_size": int(row.get("bs", row.get("bid_size")) or 0),
        "ask_size": int(row.get("as", row.get("ask_size")) or 0),
    }


def _map_alpaca_stock_bar(ticker: str, row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    ts = parse_datetime(row.get("t"))
    if ts is None:
        return None
    if ts.tzinfo is not None:
        ts = ts.astimezone(timezone.utc).replace(tzinfo=None)
    return {
        "ticker": ticker,
        "ts": ts,
        "open": float(row.get("o") or 0.0),
        "high": float(row.get("h") or 0.0),
        "low": float(row.get("l") or 0.0),
        "close": float(row.get("c") or 0.0),
        "volume": int(row.get("v") or 0),
    }


def _as_utc_aware(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def _as_et(ts: datetime) -> datetime:
    return _as_utc_aware(ts).astimezone(_ET_ZONE)


def _parse_hhmm(value: str, default_value: str) -> time:
    text = (value or "").strip() or default_value
    try:
        hour_text, minute_text = text.split(":", 1)
        hour = max(0, min(23, int(hour_text)))
        minute = max(0, min(59, int(minute_text)))
        return time(hour=hour, minute=minute)
    except (TypeError, ValueError):
        hour_text, minute_text = default_value.split(":", 1)
        return time(hour=int(hour_text), minute=int(minute_text))


def _default_entry_start(opening_range_minutes: int) -> str:
    effective = max(int(opening_range_minutes), 1)
    minute_total = (9 * 60) + 30 + effective
    hour = minute_total // 60
    minute = minute_total % 60
    return f"{hour:02d}:{minute:02d}"


def _bars_through_et_time(bars: Sequence[Dict[str, Any]], cutoff_time: time) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for bar in bars:
        ts = bar.get("ts")
        if not isinstance(ts, datetime):
            continue
        bar_time = _as_et(ts).time()
        if bar_time <= cutoff_time:
            out.append(bar)
            continue
        # Session bars arrive in chronological order, so nothing later can re-enter.
        break
    return out


def _iter_dates(start_day: date, end_day: date) -> List[date]:
    days: List[date] = []
    cur = start_day
    while cur <= end_day:
        days.append(cur)
        cur += timedelta(days=1)
    return days


def _first_bar_on_or_after(
    bars: List[Dict[str, Any]],
    ts: datetime,
    fallback_last: bool = False,
) -> Optional[Dict[str, Any]]:
    target_ts = _as_utc_aware(ts)
    for bar in bars:
        bar_ts = bar.get("ts")
        if not isinstance(bar_ts, datetime):
            continue
        if _as_utc_aware(bar_ts) >= target_ts:
            return bar
    if fallback_last and bars:
        return bars[-1]
    return None


def _bar_index_by_ts(bars: List[Dict[str, Any]], ts: datetime) -> Optional[int]:
    for idx, bar in enumerate(bars):
        if bar.get("ts") == ts:
            return idx
    return None


def _next_observable_exit_target(
    *,
    scan_bars: Sequence[Dict[str, Any]],
    trigger_index: int,
    default_exit_bar: Dict[str, Any],
    default_exit_ts: datetime,
) -> Tuple[Dict[str, Any], datetime]:
    next_index = int(trigger_index) + 1
    if 0 <= next_index < len(scan_bars):
        next_bar = scan_bars[next_index]
        next_ts = next_bar.get("ts")
        if isinstance(next_ts, datetime):
            return next_bar, next_ts
        return next_bar, default_exit_ts
    trigger_bar = scan_bars[trigger_index] if 0 <= int(trigger_index) < len(scan_bars) else {}
    trigger_ts = trigger_bar.get("ts")
    if isinstance(trigger_ts, datetime):
        return default_exit_bar, _as_utc_aware(trigger_ts) + timedelta(minutes=1)
    return default_exit_bar, default_exit_ts


def _quotes_in_window(
    *,
    same_day_quotes: Sequence[Dict[str, Any]],
    exit_day_quotes: Sequence[Dict[str, Any]],
    day: date,
    exit_day: date,
    start_ts: datetime,
    end_ts: datetime,
) -> List[Dict[str, Any]]:
    start_utc = _as_utc_aware(start_ts)
    end_utc = _as_utc_aware(end_ts)
    rows: List[Dict[str, Any]] = []

    def _extend(quotes: Sequence[Dict[str, Any]]) -> None:
        for quote in quotes:
            quote_ts = quote.get("ts")
            if not isinstance(quote_ts, datetime):
                continue
            quote_utc = _as_utc_aware(quote_ts)
            if start_utc <= quote_utc <= end_utc:
                rows.append(quote)

    _extend(same_day_quotes)
    if exit_day != day:
        _extend(exit_day_quotes)
    rows.sort(key=lambda row: _as_utc_aware(row["ts"]))
    return rows


def _iter_quote_pairs_in_window(
    *,
    primary_same_day_quotes: Sequence[Dict[str, Any]],
    primary_exit_day_quotes: Sequence[Dict[str, Any]],
    secondary_same_day_quotes: Sequence[Dict[str, Any]],
    secondary_exit_day_quotes: Sequence[Dict[str, Any]],
    day: date,
    exit_day: date,
    start_ts: datetime,
    end_ts: datetime,
) -> Iterator[Tuple[datetime, Dict[str, Any], Dict[str, Any]]]:
    primary_quotes = _quotes_in_window(
        same_day_quotes=primary_same_day_quotes,
        exit_day_quotes=primary_exit_day_quotes,
        day=day,
        exit_day=exit_day,
        start_ts=start_ts,
        end_ts=end_ts,
    )
    secondary_quotes = _quotes_in_window(
        same_day_quotes=secondary_same_day_quotes,
        exit_day_quotes=secondary_exit_day_quotes,
        day=day,
        exit_day=exit_day,
        start_ts=start_ts,
        end_ts=end_ts,
    )
    if not primary_quotes or not secondary_quotes:
        return

    timeline = sorted(
        {
            _as_utc_aware(quote["ts"])
            for quote in list(primary_quotes) + list(secondary_quotes)
            if isinstance(quote.get("ts"), datetime)
        }
    )
    primary_index = 0
    secondary_index = 0
    latest_primary: Optional[Dict[str, Any]] = None
    latest_secondary: Optional[Dict[str, Any]] = None
    for ts in timeline:
        while primary_index < len(primary_quotes):
            current = primary_quotes[primary_index]
            current_ts = current.get("ts")
            if not isinstance(current_ts, datetime) or _as_utc_aware(current_ts) > ts:
                break
            latest_primary = current
            primary_index += 1
        while secondary_index < len(secondary_quotes):
            current = secondary_quotes[secondary_index]
            current_ts = current.get("ts")
            if not isinstance(current_ts, datetime) or _as_utc_aware(current_ts) > ts:
                break
            latest_secondary = current
            secondary_index += 1
        if latest_primary is None or latest_secondary is None:
            continue
        yield ts, latest_primary, latest_secondary


def _apply_option_premium_stop_from_quotes(
    *,
    entry_price_raw: float,
    option_take_profit_pct: float,
    option_max_loss_pct: float,
    entry_fill_ts: datetime,
    default_exit_bar: Dict[str, Any],
    default_exit_reason: str,
    default_exit_ts: datetime,
    same_day_quotes: Sequence[Dict[str, Any]],
    exit_day_quotes: Sequence[Dict[str, Any]],
    day: date,
    exit_day: date,
) -> Dict[str, Any]:
    selected_exit_bar = default_exit_bar
    exit_raw = 0.0
    effective_exit_reason = str(default_exit_reason or "")
    effective_exit_ts = default_exit_ts
    premium_take_profit_triggered = False
    premium_take_profit_price_raw: Optional[float] = None
    option_premium_stop_triggered = False
    option_premium_stop_price_raw: Optional[float] = None

    take_profit_price_raw = (
        entry_price_raw * (1.0 + option_take_profit_pct)
        if option_take_profit_pct > 0 and entry_price_raw > 0
        else None
    )
    stop_price_raw = (
        entry_price_raw * (1.0 - option_max_loss_pct)
        if option_max_loss_pct > 0 and entry_price_raw > 0
        else None
    )
    scan_quotes = _quotes_in_window(
        same_day_quotes=same_day_quotes,
        exit_day_quotes=exit_day_quotes,
        day=day,
        exit_day=exit_day,
        start_ts=entry_fill_ts,
        end_ts=default_exit_ts,
    )
    for quote in scan_quotes:
        quote_ts = quote.get("ts")
        if not isinstance(quote_ts, datetime):
            continue
        exit_mark = _safe_float(quote.get("bid"))
        if exit_mark is None or exit_mark <= 0.0:
            continue
        if stop_price_raw is not None and exit_mark <= stop_price_raw:
            option_premium_stop_triggered = True
            option_premium_stop_price_raw = max(stop_price_raw, 0.0)
            effective_exit_reason = "option_premium_stop"
            effective_exit_ts = quote_ts
            exit_raw = exit_mark
            break
        if take_profit_price_raw is not None and exit_mark >= take_profit_price_raw:
            premium_take_profit_triggered = True
            premium_take_profit_price_raw = max(take_profit_price_raw, 0.0)
            effective_exit_reason = "premium_take_profit"
            effective_exit_ts = quote_ts
            exit_raw = exit_mark
            break

    return {
        "exit_bar": selected_exit_bar,
        "exit_raw": exit_raw,
        "effective_exit_reason": effective_exit_reason,
        "effective_exit_ts": effective_exit_ts,
        "premium_take_profit_triggered": premium_take_profit_triggered,
        "premium_take_profit_price_raw": premium_take_profit_price_raw,
        "option_premium_stop_triggered": option_premium_stop_triggered,
        "option_premium_stop_price_raw": option_premium_stop_price_raw,
    }


def _apply_vertical_debit_premium_exits_from_quotes(
    *,
    entry_debit_raw: float,
    option_take_profit_pct: float,
    option_max_loss_pct: float,
    entry_fill_ts: datetime,
    default_exit_bar: Dict[str, Any],
    default_exit_reason: str,
    default_exit_ts: datetime,
    long_same_day_quotes: Sequence[Dict[str, Any]],
    long_exit_day_quotes: Sequence[Dict[str, Any]],
    short_same_day_quotes: Sequence[Dict[str, Any]],
    short_exit_day_quotes: Sequence[Dict[str, Any]],
    day: date,
    exit_day: date,
) -> Dict[str, Any]:
    selected_exit_bar = default_exit_bar
    effective_exit_reason = str(default_exit_reason or "")
    effective_exit_ts = default_exit_ts
    premium_take_profit_triggered = False
    option_premium_stop_triggered = False
    premium_stop_triggered = False
    option_premium_stop_price_raw: Optional[float] = None
    exit_raw = 0.0

    take_profit_mark = (
        entry_debit_raw * (1.0 + option_take_profit_pct)
        if entry_debit_raw > 0.0 and option_take_profit_pct > 0.0
        else None
    )
    stop_mark = (
        entry_debit_raw * (1.0 - option_max_loss_pct)
        if entry_debit_raw > 0.0 and option_max_loss_pct > 0.0
        else None
    )
    for ts, long_quote, short_quote in _iter_quote_pairs_in_window(
        primary_same_day_quotes=long_same_day_quotes,
        primary_exit_day_quotes=long_exit_day_quotes,
        secondary_same_day_quotes=short_same_day_quotes,
        secondary_exit_day_quotes=short_exit_day_quotes,
        day=day,
        exit_day=exit_day,
        start_ts=entry_fill_ts,
        end_ts=default_exit_ts,
    ):
        long_bid = _safe_float(long_quote.get("bid"))
        short_ask = _safe_float(short_quote.get("ask"))
        if long_bid is None or long_bid <= 0.0 or short_ask is None or short_ask <= 0.0:
            continue
        spread_mark = max(float(long_bid) - float(short_ask), 0.0)
        if stop_mark is not None and spread_mark <= stop_mark:
            effective_exit_reason = "option_premium_stop"
            effective_exit_ts = ts
            option_premium_stop_triggered = True
            premium_stop_triggered = True
            option_premium_stop_price_raw = max(stop_mark, 0.0)
            exit_raw = spread_mark
            break
        if take_profit_mark is not None and spread_mark >= take_profit_mark:
            effective_exit_reason = "premium_take_profit"
            effective_exit_ts = ts
            premium_take_profit_triggered = True
            exit_raw = spread_mark
            break

    return {
        "exit_bar": selected_exit_bar,
        "exit_raw": exit_raw,
        "effective_exit_reason": effective_exit_reason,
        "effective_exit_ts": effective_exit_ts,
        "premium_take_profit_triggered": premium_take_profit_triggered,
        "premium_stop_triggered": premium_stop_triggered,
        "option_premium_stop_triggered": option_premium_stop_triggered,
        "option_premium_stop_price_raw": option_premium_stop_price_raw,
    }


def _apply_option_premium_stop(
    *,
    entry_price_raw: float,
    option_take_profit_pct: float,
    option_max_loss_pct: float,
    entry_bar: Dict[str, Any],
    exit_bar: Dict[str, Any],
    entry_bars: List[Dict[str, Any]],
    exit_bars: List[Dict[str, Any]],
    day: date,
    exit_day: date,
    default_exit_reason: str,
    default_exit_ts: datetime,
) -> Dict[str, Any]:
    selected_exit_bar = exit_bar
    exit_raw = _causal_bar_fill_price(selected_exit_bar)
    effective_exit_reason = str(default_exit_reason or "")
    effective_exit_ts = default_exit_ts
    premium_take_profit_triggered = False
    premium_take_profit_price_raw: Optional[float] = None
    option_premium_stop_triggered = False
    option_premium_stop_price_raw: Optional[float] = None

    take_profit_price_raw = (
        entry_price_raw * (1.0 + option_take_profit_pct)
        if option_take_profit_pct > 0 and entry_price_raw > 0
        else None
    )
    stop_price_raw = (
        entry_price_raw * (1.0 - option_max_loss_pct)
        if option_max_loss_pct > 0 and entry_price_raw > 0
        else None
    )

    if take_profit_price_raw is not None or stop_price_raw is not None:
        scan_bars: List[Dict[str, Any]] = []
        if exit_day == day:
            scan_bars = list(entry_bars)
        else:
            scan_bars.extend(
                row for row in entry_bars if isinstance(row.get("ts"), datetime) and row["ts"] >= entry_bar["ts"]
            )
            scan_bars.extend(
                row
                for row in exit_bars
                if isinstance(row.get("ts"), datetime) and row["ts"] <= exit_bar["ts"]
            )
            scan_bars.sort(key=lambda row: row["ts"])
        entry_bar_idx = _bar_index_by_ts(scan_bars, entry_bar["ts"])
        exit_bar_idx = _bar_index_by_ts(scan_bars, exit_bar["ts"])
        if entry_bar_idx is not None and exit_bar_idx is not None and exit_bar_idx >= entry_bar_idx:
            for scan_idx in range(entry_bar_idx, exit_bar_idx + 1):
                scan_bar = scan_bars[scan_idx]
                scan_high = float(scan_bar.get("high") or 0.0)
                scan_low = float(scan_bar.get("low") or 0.0)
                take_profit_hit = bool(
                    take_profit_price_raw is not None and scan_high > 0 and scan_high >= take_profit_price_raw
                )
                stop_hit = bool(stop_price_raw is not None and scan_low > 0 and scan_low <= stop_price_raw)
                if stop_hit:
                    selected_exit_bar, effective_exit_ts = _next_observable_exit_target(
                        scan_bars=scan_bars,
                        trigger_index=scan_idx,
                        default_exit_bar=exit_bar,
                        default_exit_ts=default_exit_ts,
                    )
                    option_premium_stop_triggered = True
                    option_premium_stop_price_raw = max(stop_price_raw, 0.0)
                    effective_exit_reason = "option_premium_stop"
                    exit_raw = option_premium_stop_price_raw
                    break
                if take_profit_hit:
                    selected_exit_bar, effective_exit_ts = _next_observable_exit_target(
                        scan_bars=scan_bars,
                        trigger_index=scan_idx,
                        default_exit_bar=exit_bar,
                        default_exit_ts=default_exit_ts,
                    )
                    premium_take_profit_triggered = True
                    premium_take_profit_price_raw = max(take_profit_price_raw, 0.0)
                    effective_exit_reason = "premium_take_profit"
                    exit_raw = premium_take_profit_price_raw
                    break

    return {
        "exit_bar": selected_exit_bar,
        "exit_raw": exit_raw,
        "effective_exit_reason": effective_exit_reason,
        "effective_exit_ts": effective_exit_ts,
        "premium_take_profit_triggered": premium_take_profit_triggered,
        "premium_take_profit_price_raw": premium_take_profit_price_raw,
        "option_premium_stop_triggered": option_premium_stop_triggered,
        "option_premium_stop_price_raw": option_premium_stop_price_raw,
    }


def _apply_vertical_credit_premium_exits(
    *,
    entry_credit_raw: float,
    take_profit_capture_pct: float,
    stop_loss_multiple: float,
    short_entry_bar: Dict[str, Any],
    short_exit_bar: Dict[str, Any],
    short_entry_bars: List[Dict[str, Any]],
    short_exit_bars: List[Dict[str, Any]],
    long_entry_bars: List[Dict[str, Any]],
    long_exit_bars: List[Dict[str, Any]],
    day: date,
    exit_day: date,
    default_exit_reason: str,
    default_exit_ts: datetime,
) -> Dict[str, Any]:
    selected_exit_bar = short_exit_bar
    effective_exit_reason = str(default_exit_reason or "")
    effective_exit_ts = default_exit_ts
    premium_take_profit_triggered = False
    premium_stop_triggered = False
    exit_raw = max(
        _causal_bar_fill_price(short_exit_bar) - _causal_bar_fill_price(long_exit_bars[_bar_index_by_ts(long_exit_bars, short_exit_bar["ts"])]),
        0.0,
    ) if _bar_index_by_ts(long_exit_bars, short_exit_bar["ts"]) is not None else max(_causal_bar_fill_price(short_exit_bar), 0.0)

    take_profit_mark = (
        entry_credit_raw * (1.0 - max(min(float(take_profit_capture_pct), 1.0), 0.0))
        if entry_credit_raw > 0.0 and take_profit_capture_pct > 0.0
        else None
    )
    stop_mark = (
        entry_credit_raw * max(float(stop_loss_multiple), 0.0)
        if entry_credit_raw > 0.0 and stop_loss_multiple > 0.0
        else None
    )
    if take_profit_mark is None and stop_mark is None:
        return {
            "exit_bar": selected_exit_bar,
            "exit_raw": exit_raw,
            "effective_exit_reason": effective_exit_reason,
            "effective_exit_ts": effective_exit_ts,
            "premium_take_profit_triggered": premium_take_profit_triggered,
            "premium_stop_triggered": premium_stop_triggered,
        }

    def _bars_in_window(
        bars_same_day: List[Dict[str, Any]],
        bars_exit_day: List[Dict[str, Any]],
        *,
        start_ts: datetime,
        end_ts: datetime,
    ) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        if exit_day == day:
            rows = list(bars_same_day)
        else:
            rows.extend(
                row
                for row in bars_same_day
                if isinstance(row.get("ts"), datetime) and row["ts"] >= start_ts
            )
            rows.extend(
                row
                for row in bars_exit_day
                if isinstance(row.get("ts"), datetime) and row["ts"] <= end_ts
            )
            rows.sort(key=lambda row: row["ts"])
        return rows

    short_scan_bars = _bars_in_window(
        short_entry_bars,
        short_exit_bars,
        start_ts=short_entry_bar["ts"],
        end_ts=short_exit_bar["ts"],
    )
    long_scan_bars = _bars_in_window(
        long_entry_bars,
        long_exit_bars,
        start_ts=short_entry_bar["ts"],
        end_ts=short_exit_bar["ts"],
    )
    long_by_ts = {
        row["ts"]: row
        for row in long_scan_bars
        if isinstance(row.get("ts"), datetime)
    }
    entry_bar_idx = _bar_index_by_ts(short_scan_bars, short_entry_bar["ts"])
    exit_bar_idx = _bar_index_by_ts(short_scan_bars, short_exit_bar["ts"])
    if entry_bar_idx is None or exit_bar_idx is None or exit_bar_idx < entry_bar_idx:
        return {
            "exit_bar": selected_exit_bar,
            "exit_raw": exit_raw,
            "effective_exit_reason": effective_exit_reason,
            "effective_exit_ts": effective_exit_ts,
            "premium_take_profit_triggered": premium_take_profit_triggered,
            "premium_stop_triggered": premium_stop_triggered,
        }

    for scan_idx in range(entry_bar_idx, exit_bar_idx + 1):
        short_bar = short_scan_bars[scan_idx]
        ts = short_bar.get("ts")
        if not isinstance(ts, datetime):
            continue
        long_bar = long_by_ts.get(ts)
        if long_bar is None:
            continue
        spread_mark = max(_causal_bar_fill_price(short_bar) - _causal_bar_fill_price(long_bar), 0.0)
        if stop_mark is not None and spread_mark >= stop_mark:
            selected_exit_bar = short_bar
            effective_exit_reason = "premium_stop"
            effective_exit_ts = ts
            premium_stop_triggered = True
            exit_raw = spread_mark
            break
        if take_profit_mark is not None and spread_mark <= take_profit_mark:
            selected_exit_bar = short_bar
            effective_exit_reason = "premium_take_profit"
            effective_exit_ts = ts
            premium_take_profit_triggered = True
            exit_raw = spread_mark
            break

    return {
        "exit_bar": selected_exit_bar,
        "exit_raw": exit_raw,
        "effective_exit_reason": effective_exit_reason,
        "effective_exit_ts": effective_exit_ts,
        "premium_take_profit_triggered": premium_take_profit_triggered,
        "premium_stop_triggered": premium_stop_triggered,
    }


def _apply_vertical_debit_premium_exits(
    *,
    entry_debit_raw: float,
    option_take_profit_pct: float,
    option_max_loss_pct: float,
    long_entry_bar: Dict[str, Any],
    long_exit_bar: Dict[str, Any],
    long_entry_bars: List[Dict[str, Any]],
    long_exit_bars: List[Dict[str, Any]],
    short_entry_bar: Dict[str, Any],
    short_exit_bar: Dict[str, Any],
    short_entry_bars: List[Dict[str, Any]],
    short_exit_bars: List[Dict[str, Any]],
    day: date,
    exit_day: date,
    default_exit_reason: str,
    default_exit_ts: datetime,
) -> Dict[str, Any]:
    selected_exit_bar = long_exit_bar
    effective_exit_reason = str(default_exit_reason or "")
    effective_exit_ts = default_exit_ts
    premium_take_profit_triggered = False
    option_premium_stop_triggered = False
    premium_stop_triggered = False
    option_premium_stop_price_raw: Optional[float] = None
    exit_raw = max(
        _causal_bar_fill_price(long_exit_bar)
        - _causal_bar_fill_price(short_exit_bars[_bar_index_by_ts(short_exit_bars, long_exit_bar["ts"])]),
        0.0,
    ) if _bar_index_by_ts(short_exit_bars, long_exit_bar["ts"]) is not None else max(_causal_bar_fill_price(long_exit_bar), 0.0)

    take_profit_mark = (
        entry_debit_raw * (1.0 + option_take_profit_pct)
        if entry_debit_raw > 0.0 and option_take_profit_pct > 0.0
        else None
    )
    stop_mark = (
        entry_debit_raw * (1.0 - option_max_loss_pct)
        if entry_debit_raw > 0.0 and option_max_loss_pct > 0.0
        else None
    )
    if take_profit_mark is None and stop_mark is None:
        return {
            "exit_bar": selected_exit_bar,
            "exit_raw": exit_raw,
            "effective_exit_reason": effective_exit_reason,
            "effective_exit_ts": effective_exit_ts,
            "premium_take_profit_triggered": premium_take_profit_triggered,
            "premium_stop_triggered": premium_stop_triggered,
            "option_premium_stop_triggered": option_premium_stop_triggered,
            "option_premium_stop_price_raw": option_premium_stop_price_raw,
        }

    def _bars_in_window(
        bars_same_day: List[Dict[str, Any]],
        bars_exit_day: List[Dict[str, Any]],
        *,
        start_ts: datetime,
        end_ts: datetime,
    ) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        if exit_day == day:
            rows = list(bars_same_day)
        else:
            rows.extend(
                row
                for row in bars_same_day
                if isinstance(row.get("ts"), datetime) and row["ts"] >= start_ts
            )
            rows.extend(
                row
                for row in bars_exit_day
                if isinstance(row.get("ts"), datetime) and row["ts"] <= end_ts
            )
            rows.sort(key=lambda row: row["ts"])
        return rows

    long_scan_bars = _bars_in_window(
        long_entry_bars,
        long_exit_bars,
        start_ts=long_entry_bar["ts"],
        end_ts=long_exit_bar["ts"],
    )
    short_scan_bars = _bars_in_window(
        short_entry_bars,
        short_exit_bars,
        start_ts=short_entry_bar["ts"],
        end_ts=short_exit_bar["ts"],
    )
    short_by_ts = {
        row["ts"]: row
        for row in short_scan_bars
        if isinstance(row.get("ts"), datetime)
    }
    entry_bar_idx = _bar_index_by_ts(long_scan_bars, long_entry_bar["ts"])
    exit_bar_idx = _bar_index_by_ts(long_scan_bars, long_exit_bar["ts"])
    if entry_bar_idx is None or exit_bar_idx is None or exit_bar_idx < entry_bar_idx:
        return {
            "exit_bar": selected_exit_bar,
            "exit_raw": exit_raw,
            "effective_exit_reason": effective_exit_reason,
            "effective_exit_ts": effective_exit_ts,
            "premium_take_profit_triggered": premium_take_profit_triggered,
            "premium_stop_triggered": premium_stop_triggered,
            "option_premium_stop_triggered": option_premium_stop_triggered,
            "option_premium_stop_price_raw": option_premium_stop_price_raw,
        }

    for scan_idx in range(entry_bar_idx, exit_bar_idx + 1):
        long_bar = long_scan_bars[scan_idx]
        ts = long_bar.get("ts")
        if not isinstance(ts, datetime):
            continue
        short_bar = short_by_ts.get(ts)
        if short_bar is None:
            continue
        spread_mark = max(_causal_bar_fill_price(long_bar) - _causal_bar_fill_price(short_bar), 0.0)
        if stop_mark is not None and spread_mark <= stop_mark:
            selected_exit_bar, effective_exit_ts = _next_observable_exit_target(
                scan_bars=long_scan_bars,
                trigger_index=scan_idx,
                default_exit_bar=long_exit_bar,
                default_exit_ts=default_exit_ts,
            )
            effective_exit_reason = "option_premium_stop"
            option_premium_stop_triggered = True
            premium_stop_triggered = True
            option_premium_stop_price_raw = max(stop_mark, 0.0)
            exit_raw = spread_mark
            break
        if take_profit_mark is not None and spread_mark >= take_profit_mark:
            selected_exit_bar, effective_exit_ts = _next_observable_exit_target(
                scan_bars=long_scan_bars,
                trigger_index=scan_idx,
                default_exit_bar=long_exit_bar,
                default_exit_ts=default_exit_ts,
            )
            effective_exit_reason = "premium_take_profit"
            premium_take_profit_triggered = True
            exit_raw = spread_mark
            break

    return {
        "exit_bar": selected_exit_bar,
        "exit_raw": exit_raw,
        "effective_exit_reason": effective_exit_reason,
        "effective_exit_ts": effective_exit_ts,
        "premium_take_profit_triggered": premium_take_profit_triggered,
        "premium_stop_triggered": premium_stop_triggered,
        "option_premium_stop_triggered": option_premium_stop_triggered,
        "option_premium_stop_price_raw": option_premium_stop_price_raw,
    }


def _first_quote_on_or_after(
    quotes: List[Dict[str, Any]],
    ts: datetime,
    fallback_last: bool = False,
) -> Optional[Dict[str, Any]]:
    target_ts = _as_utc_aware(ts)
    for quote in quotes:
        quote_ts = quote.get("ts")
        if not isinstance(quote_ts, datetime):
            continue
        if _as_utc_aware(quote_ts) >= target_ts:
            return quote
    if fallback_last and quotes:
        return quotes[-1]
    return None


def _jittered_delay_minutes(
    *,
    base_delay_minutes: int,
    jitter_minutes: int,
    randomization_enabled: bool,
    random_seed: int,
    seed_key: str,
) -> int:
    base = max(int(base_delay_minutes), 0)
    jitter = max(int(jitter_minutes), 0)
    if not randomization_enabled or jitter <= 0:
        return base
    rng = random.Random(f"{int(random_seed)}|{seed_key}")
    return max(0, base + rng.randint(-jitter, jitter))


def _snap_to_poll_boundary(ts: datetime, poll_seconds: int) -> datetime:
    poll = max(int(poll_seconds), 1)
    seconds = (
        ts.hour * 3600
        + ts.minute * 60
        + ts.second
        + (ts.microsecond / 1_000_000.0)
    )
    remainder = seconds % float(poll)
    if remainder <= 0:
        return ts
    return ts + timedelta(seconds=float(poll) - remainder)


def _apply_execution_timing_model(
    ts: datetime,
    *,
    model: str,
    poll_seconds: int,
    signal_confirm_seconds: int,
    fill_latency_seconds: int,
) -> datetime:
    normalized_model = str(model or "bar_open").strip().lower()
    effective = ts + timedelta(seconds=max(int(signal_confirm_seconds), 0))
    if normalized_model == "live_poll":
        effective = _snap_to_poll_boundary(effective, max(int(poll_seconds), 1))
    effective = effective + timedelta(seconds=max(int(fill_latency_seconds), 0))
    return effective


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _causal_bar_fill_price(row: Dict[str, Any]) -> float:
    open_price = float(row.get("open") or 0.0)
    if open_price > 0:
        return open_price
    return float(row.get("close") or 0.0)


def _option_qty_for_risk(
    *,
    risk_notional: float,
    entry_price: float,
    commission_per_contract: float,
    include_commission: bool,
    min_entry_price: float,
    sizing_mode: str = "premium_at_risk",
    option_max_loss_pct: float = 0.0,
    option_leg_count: int = 1,
) -> int:
    risk_capital = max(float(risk_notional), 0.0)
    effective_entry_price = max(float(entry_price), max(float(min_entry_price), 0.0))
    if risk_capital <= 0.0 or effective_entry_price <= 0.0:
        return 0
    normalized_mode = str(sizing_mode or "premium_at_risk").strip().lower()
    loss_fraction = 1.0
    if normalized_mode == "premium_stop":
        candidate = max(float(option_max_loss_pct), 0.0)
        if 0.0 < candidate <= 1.0:
            loss_fraction = candidate
    per_contract_cost = effective_entry_price * 100.0 * loss_fraction
    if include_commission:
        per_contract_cost += max(float(commission_per_contract), 0.0) * 2.0 * max(int(option_leg_count), 1)
    if per_contract_cost <= 0.0:
        return 0
    return int(risk_capital / per_contract_cost)


def _option_intrinsic_value(option_type: str, underlying_price: float, strike: float) -> float:
    normalized = str(option_type or "").strip().lower()
    underlying = max(float(underlying_price), 0.0)
    strike_px = max(float(strike), 0.0)
    if normalized == "put":
        return max(strike_px - underlying, 0.0)
    return max(underlying - strike_px, 0.0)


def _expected_underlying_target_move(
    *,
    setup: Dict[str, Any],
    take_profit_rr: float,
) -> Optional[float]:
    entry_underlying = _safe_float(setup.get("entry_underlying"))
    stop_underlying = _safe_float(setup.get("stop_underlying"))
    if entry_underlying is None or entry_underlying <= 0:
        return None
    target_underlying = _safe_float(setup.get("mr_target_underlying"))
    if target_underlying is None and stop_underlying is not None and stop_underlying > 0 and take_profit_rr > 0:
        risk_per_share = abs(entry_underlying - stop_underlying)
        if risk_per_share > 0:
            direction = 1 if int(setup.get("direction") or 0) >= 0 else -1
            target_underlying = entry_underlying + (direction * risk_per_share * float(take_profit_rr))
    if target_underlying is None or target_underlying <= 0:
        return None
    move = abs(float(target_underlying) - float(entry_underlying))
    return move if move > 0 else None


def _normalize_regime_label(value: Any) -> str:
    label = str(value or "").strip().lower()
    if label in {"trending", "trend", "trending_up", "trending_down", "momentum", "breakout"}:
        return "trending"
    if label in {"sideways", "sideway", "choppy", "range", "mean_reversion"}:
        return "sideways"
    if label in {"neutral", "transition", "mixed"}:
        return "neutral"
    return "unknown"


def _empty_regime_label_counts() -> Dict[str, int]:
    return {
        "trending": 0,
        "sideways": 0,
        "neutral": 0,
        "unknown": 0,
    }


def _empty_regime_v2_state_counts() -> Dict[str, int]:
    return {
        "trend_up": 0,
        "trend_down": 0,
        "range_low_vol": 0,
        "range_high_vol": 0,
        "event_gap": 0,
        "transition": 0,
        "defensive": 0,
        "unknown": 0,
    }


def _parse_regime_label_allowlist(value: Any) -> set[str]:
    raw = str(value or "").strip()
    if not raw:
        return {"trending", "sideways", "neutral", "unknown"}
    out: set[str] = set()
    for item in raw.split(","):
        label = _normalize_regime_label(item)
        out.add(label)
    if not out:
        out.add("unknown")
    return out


def _route_strategy_for_regime_v2(
    *,
    base_variant: str,
    base_allow_long: bool,
    base_allow_short: bool,
    regime_v2_state: str,
    confidence: float,
    router_enabled: bool,
    router_mode: str,
    min_confidence: float,
    trend_up_min_confidence: Optional[float] = None,
    trend_down_min_confidence: Optional[float] = None,
    range_low_vol_min_confidence: Optional[float] = None,
    relative_opening_volume: Optional[float] = None,
    entry_bar_range_pct: Optional[float] = None,
    gap_return: Optional[float] = None,
    high_rv_min: float = 1.15,
    trend_up_rv_max: float = 1.30,
    trend_down_rv_max: float = 1.35,
    trend_up_entry_bar_range_min_pct: float = 0.04,
    trend_down_entry_bar_range_min_pct: float = 0.04,
    low_confidence_mr_rv_max: float = 1.15,
    low_confidence_mr_entry_bar_range_max_pct: float = 0.03,
    low_confidence_skip_rv_min: float = 1.60,
    low_confidence_skip_entry_bar_range_min_pct: float = 0.06,
    trend_up_overlay_compression_max_range_pct: float = 0.0030,
    trend_up_overlay_option_max_entry_bar_range_pct: float = 0.06,
    event_gap_tight_entry_bar_range_max_pct: float = 0.01,
    event_gap_mid_rv_min: float = 1.0,
    event_gap_mid_rv_max: float = 2.0,
    event_gap_mid_entry_bar_range_max_pct: float = 0.025,
    event_gap_overlay_compression_max_range_pct: float = 0.0030,
    event_gap_overlay_option_max_entry_bar_range_pct: float = 0.06,
    range_low_vol_tight_rv_max: float = 0.95,
    range_low_vol_tight_entry_bar_range_max_pct: float = 0.005,
    transition_high_rv_min: float = 2.0,
    transition_wide_entry_bar_range_min_pct: float = 0.05,
) -> Dict[str, Any]:
    base_variant_text = str(base_variant or "orb_qc")
    base = {
        "route_state": str(regime_v2_state or "unknown"),
        "selected_variant": base_variant_text,
        "allow_long": bool(base_allow_long),
        "allow_short": bool(base_allow_short),
        "skip_day": False,
        "skip_reason": "",
        "route_action": "fallback_base",
        "route_overlay_name": "",
        "setup_overrides": {},
    }
    if not bool(router_enabled):
        return base

    safe_conf = float(confidence or 0.0)
    min_conf = max(float(min_confidence), 0.0)
    state = str(regime_v2_state or "unknown").strip().lower() or "unknown"
    mode = str(router_mode or "core").strip().lower() or "core"
    def _normalize_state_min_confidence(value: Optional[float]) -> float:
        if value in (None, ""):
            return min_conf
        try:
            normalized = float(value)
        except (TypeError, ValueError):
            return min_conf
        if normalized <= 0.0:
            return min_conf
        return max(normalized, 0.0)

    trend_up_min_conf = _normalize_state_min_confidence(trend_up_min_confidence)
    trend_down_min_conf = _normalize_state_min_confidence(trend_down_min_confidence)
    range_low_vol_min_conf = _normalize_state_min_confidence(range_low_vol_min_confidence)
    rel_opening_vol = _safe_float(relative_opening_volume)
    normalized_entry_bar_range_pct = _safe_float(entry_bar_range_pct)
    normalized_gap_return = _safe_float(gap_return)
    is_high_rv = rel_opening_vol is not None and rel_opening_vol >= max(float(high_rv_min), 0.0)
    trend_up_rv_cap = max(float(trend_up_rv_max), 0.0)
    trend_down_rv_cap = max(float(trend_down_rv_max), 0.0)
    trend_up_entry_range_min = max(float(trend_up_entry_bar_range_min_pct), 0.0)
    trend_down_entry_range_min = max(float(trend_down_entry_bar_range_min_pct), 0.0)
    low_confidence_mr_rv_cap = max(float(low_confidence_mr_rv_max), 0.0)
    low_confidence_mr_entry_range_cap = max(float(low_confidence_mr_entry_bar_range_max_pct), 0.0)
    low_confidence_skip_rv_floor = max(float(low_confidence_skip_rv_min), 0.0)
    low_confidence_skip_entry_range_floor = max(
        float(low_confidence_skip_entry_bar_range_min_pct),
        0.0,
    )
    trend_up_overlay_compression_cap = max(float(trend_up_overlay_compression_max_range_pct), 0.0)
    trend_up_overlay_option_range_cap = max(
        float(trend_up_overlay_option_max_entry_bar_range_pct),
        0.0,
    )
    event_gap_tight_entry_range_cap = max(float(event_gap_tight_entry_bar_range_max_pct), 0.0)
    event_gap_mid_rv_floor = max(float(event_gap_mid_rv_min), 0.0)
    event_gap_mid_rv_cap = max(float(event_gap_mid_rv_max), event_gap_mid_rv_floor)
    event_gap_mid_entry_range_cap = max(float(event_gap_mid_entry_bar_range_max_pct), 0.0)
    event_gap_overlay_compression_cap = max(float(event_gap_overlay_compression_max_range_pct), 0.0)
    event_gap_overlay_option_range_cap = max(float(event_gap_overlay_option_max_entry_bar_range_pct), 0.0)
    range_low_vol_tight_rv_cap = max(float(range_low_vol_tight_rv_max), 0.0)
    range_low_vol_tight_entry_range_cap = max(float(range_low_vol_tight_entry_bar_range_max_pct), 0.0)
    transition_high_rv_floor = max(float(transition_high_rv_min), 0.0)
    transition_wide_entry_range_floor = max(float(transition_wide_entry_bar_range_min_pct), 0.0)

    def _finish() -> Dict[str, Any]:
        if bool(base.get("skip_day")):
            base["route_action"] = "skip_day"
        else:
            selected_variant = str(base.get("selected_variant") or base_variant_text)
            allow_long = bool(base.get("allow_long"))
            allow_short = bool(base.get("allow_short"))
            if (
                str(base.get("route_action") or "") == "override_variant"
                or selected_variant != base_variant_text
                or allow_long != bool(base_allow_long)
                or allow_short != bool(base_allow_short)
            ):
                base["route_action"] = "override_variant"
            else:
                base["route_action"] = "fallback_base"
        return base

    def _fallback(route_state: Optional[str] = None) -> Dict[str, Any]:
        if route_state is not None:
            base["route_state"] = str(route_state)
        base["selected_variant"] = base_variant_text
        base["allow_long"] = bool(base_allow_long)
        base["allow_short"] = bool(base_allow_short)
        base["skip_day"] = False
        base["skip_reason"] = ""
        base["route_action"] = "fallback_base"
        base["route_overlay_name"] = ""
        base["setup_overrides"] = {}
        return _finish()

    def _override(
        *,
        selected_variant: str,
        allow_long: bool,
        allow_short: bool,
        route_state: Optional[str] = None,
        route_overlay_name: str = "",
        setup_overrides: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        if route_state is not None:
            base["route_state"] = str(route_state)
        base["selected_variant"] = str(selected_variant)
        base["allow_long"] = bool(allow_long)
        base["allow_short"] = bool(allow_short)
        base["skip_day"] = False
        base["skip_reason"] = ""
        base["route_action"] = "override_variant"
        base["route_overlay_name"] = str(route_overlay_name or "")
        base["setup_overrides"] = dict(setup_overrides or {})
        return _finish()

    def _fallback_with_overlay(
        *,
        route_state: Optional[str] = None,
        route_overlay_name: str,
        setup_overrides: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        if route_state is not None:
            base["route_state"] = str(route_state)
        base["selected_variant"] = base_variant_text
        base["allow_long"] = bool(base_allow_long)
        base["allow_short"] = bool(base_allow_short)
        base["skip_day"] = False
        base["skip_reason"] = ""
        base["route_action"] = "fallback_base"
        base["route_overlay_name"] = str(route_overlay_name or "")
        base["setup_overrides"] = dict(setup_overrides or {})
        return _finish()

    def _skip(skip_reason: str, *, route_state: Optional[str] = None) -> Dict[str, Any]:
        base["route_state"] = str(route_state or skip_reason)
        base["skip_day"] = True
        base["skip_reason"] = str(skip_reason)
        base["route_action"] = "skip_day"
        base["route_overlay_name"] = ""
        base["setup_overrides"] = {}
        return _finish()

    def _effective_min_confidence() -> float:
        if state == "trend_up":
            return trend_up_min_conf
        if state == "trend_down":
            return trend_down_min_conf
        if state == "range_low_vol":
            return range_low_vol_min_conf
        return min_conf

    def _low_confidence_guard(*, route_state: str = "low_confidence") -> Dict[str, Any]:
        if (
            rel_opening_vol is not None
            and rel_opening_vol <= low_confidence_mr_rv_cap
            and normalized_entry_bar_range_pct is not None
            and normalized_entry_bar_range_pct <= low_confidence_mr_entry_range_cap
        ):
            return _override(
                selected_variant="mr_vwap_zscore_v2",
                allow_long=True,
                allow_short=True,
                route_state=route_state,
            )
        if (
            (rel_opening_vol is not None and rel_opening_vol >= low_confidence_skip_rv_floor)
            or (
                normalized_entry_bar_range_pct is not None
                and normalized_entry_bar_range_pct >= low_confidence_skip_entry_range_floor
            )
        ):
            return _skip(
                "low_confidence_high_risk_skip",
                route_state="low_confidence_high_risk_skip",
            )
        return _fallback(route_state)

    def _trend_down_guarded_fallback() -> Dict[str, Any]:
        if (
            normalized_entry_bar_range_pct is not None
            and normalized_entry_bar_range_pct >= trend_down_entry_range_min
            and rel_opening_vol is not None
            and rel_opening_vol < trend_down_rv_cap
        ):
            return _override(
                selected_variant="orb_momentum_v1",
                allow_long=False,
                allow_short=True,
                route_state="trend_down",
            )
        return _fallback("trend_down")

    def _trend_up_trendcap_override() -> Dict[str, Any]:
        return _override(
            selected_variant="mr_vwap_zscore_v2",
            allow_long=True,
            allow_short=True,
            route_state="trend_up",
            route_overlay_name="trend_up_rangecap_overlay",
            setup_overrides={
                "compression_max_range_pct": trend_up_overlay_compression_cap,
                "option_max_entry_bar_range_pct": trend_up_overlay_option_range_cap,
            },
        )

    def _event_gap_guard() -> Dict[str, Any]:
        if (
            normalized_entry_bar_range_pct is not None
            and normalized_entry_bar_range_pct < event_gap_tight_entry_range_cap
            and rel_opening_vol is not None
            and rel_opening_vol >= event_gap_mid_rv_floor
        ):
            return _skip("event_gap_tight_skip", route_state="event_gap_tight_skip")
        if (
            rel_opening_vol is not None
            and event_gap_mid_rv_floor <= rel_opening_vol < event_gap_mid_rv_cap
            and normalized_entry_bar_range_pct is not None
            and normalized_entry_bar_range_pct < event_gap_mid_entry_range_cap
        ):
            return _skip(
                "event_gap_midrv_narrow_skip",
                route_state="event_gap_midrv_narrow_skip",
            )
        return _fallback("event_gap")

    def _event_gap_softcap_fallback() -> Dict[str, Any]:
        if (
            normalized_entry_bar_range_pct is not None
            and normalized_entry_bar_range_pct < event_gap_tight_entry_range_cap
            and rel_opening_vol is not None
            and rel_opening_vol >= event_gap_mid_rv_floor
        ):
            return _skip("event_gap_tight_skip", route_state="event_gap_tight_skip")
        return _fallback_with_overlay(
            route_state="event_gap",
            route_overlay_name="event_gap_softcap_overlay",
            setup_overrides={
                "compression_max_range_pct": event_gap_overlay_compression_cap,
                "option_max_entry_bar_range_pct": event_gap_overlay_option_range_cap,
            },
        )

    def _range_low_vol_tight_guard() -> Dict[str, Any]:
        if (
            normalized_entry_bar_range_pct is not None
            and normalized_entry_bar_range_pct <= range_low_vol_tight_entry_range_cap
            and rel_opening_vol is not None
            and rel_opening_vol <= range_low_vol_tight_rv_cap
        ):
            return _skip("range_low_vol_tight_skip", route_state="range_low_vol_tight_skip")
        return _fallback("range_low_vol")

    def _transition_high_rv_wide_guard() -> Dict[str, Any]:
        if (
            normalized_entry_bar_range_pct is not None
            and normalized_entry_bar_range_pct >= transition_wide_entry_range_floor
            and rel_opening_vol is not None
            and rel_opening_vol >= transition_high_rv_floor
        ):
            return _skip("transition_high_rv_wide_skip", route_state="transition_high_rv_wide_skip")
        return _fallback("transition")

    if safe_conf < _effective_min_confidence():
        if mode in {
            "meta_trend_pullback_fallback_v1",
            "meta_trend_mr_fallback_v1",
            "meta_trendmr_fulltrend_fallback_v1",
        }:
            return _fallback("low_confidence")
        if mode == "meta_trendmr_lowconf_guard_v1":
            return _low_confidence_guard()
        if mode in {
            "meta_trendmr_lowconf_guard_trendcap_v1",
            "meta_trendmr_lowconf_guard_eventgap_v1",
            "meta_trendmr_lowconf_guard_trendcap_eventgap_v1",
            "meta_trendmr_lowconf_guard_trendcap_eventgap_soft_v1",
            "meta_trendmr_lowconf_guard_trendcap_eventgap_soft_rangelow_v1",
            "meta_trendmr_lowconf_guard_trendcap_eventgap_soft_rangelow_transition_v1",
        }:
            return _low_confidence_guard()
        return _skip("low_confidence_skip")

    if mode == "meta_v1":
        if state == "trend_up":
            return _override(
                selected_variant="orb_trend_pullback_v1",
                allow_long=True,
                allow_short=False,
            )
        if state == "trend_down":
            return _override(
                selected_variant="orb_momentum_v1",
                allow_long=False,
                allow_short=True,
            )
        if state == "range_low_vol":
            return _override(
                selected_variant="mr_vwap_zscore_v2",
                allow_long=True,
                allow_short=True,
            )
        if state == "range_high_vol":
            return _override(
                selected_variant="orb_transition_compression_v1",
                allow_long=True,
                allow_short=True,
            )
        if state == "event_gap":
            return _override(
                selected_variant="orb_event_drive_v1",
                allow_long=True,
                allow_short=True,
            )
        if state == "transition":
            return _override(
                selected_variant="orb_transition_compression_v1",
                allow_long=True,
                allow_short=True,
            )
        return _skip("unknown_state_skip")

    if mode == "core_eventskip_v1":
        if state == "trend_up":
            return _override(selected_variant="orb_momentum_v1", allow_long=True, allow_short=False)
        if state == "trend_down":
            return _override(selected_variant="orb_momentum_v1", allow_long=False, allow_short=True)
        if state == "range_low_vol":
            return _override(selected_variant="mr_vwap_zscore_v2", allow_long=True, allow_short=True)
        if state == "range_high_vol":
            return _skip("range_high_vol_skip")
        if state == "event_gap":
            return _skip("event_gap_skip")
        if state == "transition":
            return _skip("transition_skip")
        return _skip("unknown_state_skip")

    if mode == "core_eventdrive_v1":
        if state == "trend_up":
            return _override(selected_variant="orb_momentum_v1", allow_long=True, allow_short=False)
        if state == "trend_down":
            return _override(selected_variant="orb_momentum_v1", allow_long=False, allow_short=True)
        if state == "range_low_vol":
            return _override(selected_variant="mr_vwap_zscore_v2", allow_long=True, allow_short=True)
        if state == "range_high_vol":
            return _skip("range_high_vol_skip")
        if state == "event_gap":
            return _override(selected_variant="orb_event_drive_v1", allow_long=True, allow_short=True)
        if state == "transition":
            return _skip("transition_skip")
        return _skip("unknown_state_skip")

    if mode == "core_trendonly_v1":
        if state == "trend_up":
            return _override(selected_variant="orb_momentum_v1", allow_long=True, allow_short=False)
        if state == "trend_down":
            return _override(selected_variant="orb_momentum_v1", allow_long=False, allow_short=True)
        if state == "range_low_vol":
            return _skip("non_trend_skip")
        if state == "range_high_vol":
            return _skip("range_high_vol_skip")
        if state == "event_gap":
            return _skip("event_gap_skip")
        if state == "transition":
            return _skip("transition_skip")
        return _skip("unknown_state_skip")

    if mode == "meta_defensive_v2":
        if state == "trend_up":
            return _override(selected_variant="orb_trend_pullback_v1", allow_long=True, allow_short=False)
        if state == "trend_down":
            return _override(selected_variant="orb_momentum_v1", allow_long=False, allow_short=True)
        if state == "range_low_vol":
            return _override(selected_variant="mr_vwap_zscore_v2", allow_long=True, allow_short=True)
        if state == "range_high_vol":
            return _skip("range_high_vol_skip")
        if state == "event_gap":
            return _override(selected_variant="orb_event_drive_v1", allow_long=True, allow_short=True)
        if state == "transition":
            return _skip("transition_skip")
        return _skip("unknown_state_skip")

    if mode == "core_trendup_pullback_v1":
        if state == "trend_up":
            return _override(selected_variant="orb_trend_pullback_v1", allow_long=True, allow_short=False)
        if state == "trend_down":
            return _override(selected_variant="orb_momentum_v1", allow_long=False, allow_short=True)
        if state == "range_low_vol":
            return _override(selected_variant="mr_vwap_zscore_v2", allow_long=True, allow_short=True)
        if state == "range_high_vol":
            return _skip("range_high_vol_skip")
        if state == "event_gap":
            return _skip("event_gap_skip")
        if state == "transition":
            return _skip("transition_skip")
        return _skip("unknown_state_skip")

    if mode == "core_bullhighrv_skip_v1":
        if is_high_rv and state in {"trend_up", "event_gap"}:
            return _skip("bull_high_rv_skip")
        if state == "trend_up":
            return _override(selected_variant="orb_momentum_v1", allow_long=True, allow_short=False)
        if state == "trend_down":
            return _override(selected_variant="orb_momentum_v1", allow_long=False, allow_short=True)
        if state == "range_low_vol":
            return _override(selected_variant="mr_vwap_zscore_v2", allow_long=True, allow_short=True)
        if state == "range_high_vol":
            return _skip("range_high_vol_skip")
        if state == "event_gap":
            return _skip("event_gap_skip")
        if state == "transition":
            return _skip("transition_skip")
        return _skip("unknown_state_skip")

    if mode == "core_gapdown_eventdrive_v1":
        if state == "trend_up":
            return _override(selected_variant="orb_trend_pullback_v1", allow_long=True, allow_short=False)
        if state == "trend_down":
            return _override(selected_variant="orb_momentum_v1", allow_long=False, allow_short=True)
        if state == "range_low_vol":
            return _override(selected_variant="mr_vwap_zscore_v2", allow_long=True, allow_short=True)
        if state == "range_high_vol":
            return _skip("range_high_vol_skip")
        if state == "event_gap":
            if float(normalized_gap_return or 0.0) < 0.0:
                return _override(selected_variant="orb_event_drive_v1", allow_long=True, allow_short=True)
            return _skip("positive_event_gap_skip")
        if state == "transition":
            return _skip("transition_skip")
        return _skip("unknown_state_skip")

    if mode == "meta_rv_defensive_v1":
        if state == "trend_up":
            if is_high_rv:
                return _skip("bull_high_rv_skip")
            return _override(selected_variant="orb_trend_pullback_v1", allow_long=True, allow_short=False)
        if state == "trend_down":
            return _override(selected_variant="orb_momentum_v1", allow_long=False, allow_short=True)
        if state == "range_low_vol":
            return _override(selected_variant="mr_vwap_zscore_v2", allow_long=True, allow_short=True)
        if state == "range_high_vol":
            return _skip("range_high_vol_skip")
        if state == "event_gap":
            if float(normalized_gap_return or 0.0) < 0.0:
                return _override(selected_variant="orb_event_drive_v1", allow_long=True, allow_short=True)
            return _skip("positive_event_gap_skip")
        if state == "transition":
            return _skip("transition_skip")
        return _skip("unknown_state_skip")

    if mode == "core_downrange_conf20_v1":
        if state == "trend_down":
            return _override(selected_variant="orb_momentum_v1", allow_long=False, allow_short=True)
        if state == "range_low_vol":
            return _override(selected_variant="mr_vwap_zscore_v2", allow_long=True, allow_short=True)
        if state == "trend_up":
            return _skip("non_trend_skip")
        if state == "range_high_vol":
            return _skip("range_high_vol_skip")
        if state == "event_gap":
            return _skip("event_gap_skip")
        if state == "transition":
            return _skip("transition_skip")
        return _skip("unknown_state_skip")

    if mode in {
        "core_conf20_v1",
        "core_conf15_v1",
        "core_asym_conf_v1",
    }:
        pass

    if mode == "core_bullhighrv_conf20_v1":
        if is_high_rv and state in {"trend_up", "event_gap"}:
            return _skip("bull_high_rv_skip")
        if state == "trend_up":
            return _override(selected_variant="orb_momentum_v1", allow_long=True, allow_short=False)
        if state == "trend_down":
            return _override(selected_variant="orb_momentum_v1", allow_long=False, allow_short=True)
        if state == "range_low_vol":
            return _override(selected_variant="mr_vwap_zscore_v2", allow_long=True, allow_short=True)
        if state == "range_high_vol":
            return _skip("range_high_vol_skip")
        if state == "event_gap":
            return _skip("event_gap_skip")
        if state == "transition":
            return _skip("transition_skip")
        return _skip("unknown_state_skip")

    if mode == "meta_trend_filter_balanced_v1":
        if state == "trend_up":
            if (
                normalized_entry_bar_range_pct is not None
                and normalized_entry_bar_range_pct < trend_up_entry_range_min
            ):
                return _skip("trend_up_tight_skip")
            if rel_opening_vol is not None and rel_opening_vol >= trend_up_rv_cap:
                return _skip("trend_up_high_rv_skip")
            return _override(selected_variant="mr_vwap_zscore_v2", allow_long=True, allow_short=True)
        if state == "trend_down":
            if (
                normalized_entry_bar_range_pct is not None
                and normalized_entry_bar_range_pct < trend_down_entry_range_min
            ):
                return _skip("trend_down_tight_skip")
            if rel_opening_vol is not None and rel_opening_vol >= trend_down_rv_cap:
                return _skip("trend_down_high_rv_skip")
            return _override(selected_variant="orb_momentum_v1", allow_long=False, allow_short=True)
        if state == "range_low_vol":
            return _override(selected_variant="mr_vwap_zscore_v2", allow_long=True, allow_short=True)
        if state == "range_high_vol":
            return _skip("range_high_vol_skip")
        if state == "event_gap":
            if float(normalized_gap_return or 0.0) < 0.0:
                return _override(selected_variant="orb_event_drive_v1", allow_long=True, allow_short=True)
            return _skip("positive_event_gap_skip")
        if state == "transition":
            return _skip("transition_skip")
        return _skip("unknown_state_skip")

    if mode == "meta_trend_filter_strict_v1":
        if state == "trend_up":
            return _skip("trend_up_skip")
        if state == "trend_down":
            if (
                normalized_entry_bar_range_pct is not None
                and normalized_entry_bar_range_pct < trend_down_entry_range_min
            ):
                return _skip("trend_down_tight_skip")
            if rel_opening_vol is not None and rel_opening_vol >= trend_down_rv_cap:
                return _skip("trend_down_high_rv_skip")
            return _override(selected_variant="orb_momentum_v1", allow_long=False, allow_short=True)
        if state == "range_low_vol":
            return _override(selected_variant="mr_vwap_zscore_v2", allow_long=True, allow_short=True)
        if state == "range_high_vol":
            return _skip("range_high_vol_skip")
        if state == "event_gap":
            if float(normalized_gap_return or 0.0) < 0.0:
                return _override(selected_variant="orb_event_drive_v1", allow_long=True, allow_short=True)
            return _skip("positive_event_gap_skip")
        if state == "transition":
            return _skip("transition_skip")
        return _skip("unknown_state_skip")

    if mode == "meta_trend_pullback_fallback_v1":
        if state == "trend_up":
            if (
                normalized_entry_bar_range_pct is not None
                and normalized_entry_bar_range_pct < trend_up_entry_range_min
            ) or (rel_opening_vol is not None and rel_opening_vol >= trend_up_rv_cap):
                return _override(
                    selected_variant="orb_trend_pullback_v1",
                    allow_long=True,
                    allow_short=False,
                    route_state="trend_up",
                )
            return _fallback("trend_up")
        if state == "trend_down":
            if (
                normalized_entry_bar_range_pct is not None
                and normalized_entry_bar_range_pct >= trend_down_entry_range_min
                and rel_opening_vol is not None
                and rel_opening_vol < trend_down_rv_cap
            ):
                return _override(
                    selected_variant="orb_momentum_v1",
                    allow_long=False,
                    allow_short=True,
                    route_state="trend_down",
                )
            return _fallback("trend_down")
        if state in {"range_low_vol", "range_high_vol", "event_gap", "transition", "unknown"}:
            return _fallback(state)
        return _fallback("unknown")

    if mode == "meta_trend_mr_fallback_v1":
        if state == "trend_up":
            if (
                normalized_entry_bar_range_pct is not None
                and normalized_entry_bar_range_pct < trend_up_entry_range_min
            ) or (rel_opening_vol is not None and rel_opening_vol >= trend_up_rv_cap):
                return _override(
                    selected_variant="mr_vwap_zscore_v2",
                    allow_long=True,
                    allow_short=True,
                    route_state="trend_up",
                )
            return _fallback("trend_up")
        if state == "trend_down":
            if (
                normalized_entry_bar_range_pct is not None
                and normalized_entry_bar_range_pct >= trend_down_entry_range_min
                and rel_opening_vol is not None
                and rel_opening_vol < trend_down_rv_cap
            ):
                return _override(
                    selected_variant="orb_momentum_v1",
                    allow_long=False,
                    allow_short=True,
                    route_state="trend_down",
                )
            return _fallback("trend_down")
        if state in {"range_low_vol", "range_high_vol", "event_gap", "transition", "unknown"}:
            return _fallback(state)
        return _fallback("unknown")

    if mode == "meta_trendmr_fulltrend_fallback_v1":
        if state == "trend_up":
            return _override(
                selected_variant="mr_vwap_zscore_v2",
                allow_long=True,
                allow_short=True,
                route_state="trend_up",
            )
        if state == "trend_down":
            return _trend_down_guarded_fallback()
        if state in {"low_confidence", "range_low_vol", "range_high_vol", "event_gap", "transition", "unknown"}:
            return _fallback(state)
        return _fallback("unknown")

    if mode == "meta_trendmr_lowconf_guard_v1":
        if state == "low_confidence":
            return _low_confidence_guard()
        if state == "trend_up":
            return _override(
                selected_variant="mr_vwap_zscore_v2",
                allow_long=True,
                allow_short=True,
                route_state="trend_up",
            )
        if state == "trend_down":
            return _trend_down_guarded_fallback()
        if state in {"range_low_vol", "range_high_vol", "event_gap", "transition", "unknown"}:
            return _fallback(state)
        return _fallback("unknown")

    if mode == "meta_trendmr_lowconf_guard_trendcap_v1":
        if state == "low_confidence":
            return _low_confidence_guard()
        if state == "trend_up":
            return _trend_up_trendcap_override()
        if state == "trend_down":
            return _trend_down_guarded_fallback()
        if state in {"range_low_vol", "range_high_vol", "event_gap", "transition", "unknown"}:
            return _fallback(state)
        return _fallback("unknown")

    if mode == "meta_trendmr_lowconf_guard_eventgap_v1":
        if state == "low_confidence":
            return _low_confidence_guard()
        if state == "trend_up":
            return _override(
                selected_variant="mr_vwap_zscore_v2",
                allow_long=True,
                allow_short=True,
                route_state="trend_up",
            )
        if state == "trend_down":
            return _trend_down_guarded_fallback()
        if state == "event_gap":
            return _event_gap_guard()
        if state in {"range_low_vol", "range_high_vol", "transition", "unknown"}:
            return _fallback(state)
        return _fallback("unknown")

    if mode == "meta_trendmr_lowconf_guard_trendcap_eventgap_v1":
        if state == "low_confidence":
            return _low_confidence_guard()
        if state == "trend_up":
            return _trend_up_trendcap_override()
        if state == "trend_down":
            return _trend_down_guarded_fallback()
        if state == "event_gap":
            return _event_gap_guard()
        if state in {"range_low_vol", "range_high_vol", "transition", "unknown"}:
            return _fallback(state)
        return _fallback("unknown")

    if mode == "meta_trendmr_lowconf_guard_trendcap_eventgap_soft_v1":
        if state == "low_confidence":
            return _low_confidence_guard()
        if state == "trend_up":
            return _trend_up_trendcap_override()
        if state == "trend_down":
            return _trend_down_guarded_fallback()
        if state == "event_gap":
            return _event_gap_softcap_fallback()
        if state in {"range_low_vol", "range_high_vol", "transition", "unknown"}:
            return _fallback(state)
        return _fallback("unknown")

    if mode == "meta_trendmr_lowconf_guard_trendcap_eventgap_soft_rangelow_v1":
        if state == "low_confidence":
            return _low_confidence_guard()
        if state == "trend_up":
            return _trend_up_trendcap_override()
        if state == "trend_down":
            return _trend_down_guarded_fallback()
        if state == "event_gap":
            return _event_gap_softcap_fallback()
        if state == "range_low_vol":
            return _range_low_vol_tight_guard()
        if state in {"range_high_vol", "transition", "unknown"}:
            return _fallback(state)
        return _fallback("unknown")

    if mode == "meta_trendmr_lowconf_guard_trendcap_eventgap_soft_rangelow_transition_v1":
        if state == "low_confidence":
            return _low_confidence_guard()
        if state == "trend_up":
            return _trend_up_trendcap_override()
        if state == "trend_down":
            return _trend_down_guarded_fallback()
        if state == "event_gap":
            return _event_gap_softcap_fallback()
        if state == "range_low_vol":
            return _range_low_vol_tight_guard()
        if state == "transition":
            return _transition_high_rv_wide_guard()
        if state in {"range_high_vol", "unknown"}:
            return _fallback(state)
        return _fallback("unknown")

    if state == "trend_up":
        return _override(selected_variant="orb_momentum_v1", allow_long=True, allow_short=False)
    if state == "trend_down":
        return _override(selected_variant="orb_momentum_v1", allow_long=False, allow_short=True)
    if state == "range_low_vol":
        return _override(selected_variant="mr_vwap_zscore_v2", allow_long=True, allow_short=True)
    if state in {"range_high_vol", "event_gap"}:
        return _override(selected_variant="orb_failure_fade", allow_long=True, allow_short=True)
    if state == "transition":
        return _skip("transition_skip")
    if state == "unknown":
        return _skip("unknown_state_skip")
    return _finish()


def _serialize_backtest_trade(trade: BacktestTrade) -> Dict[str, Any]:
    return {
        "trade_id": trade.trade_id,
        "signal_id": trade.signal_id,
        "ticker": trade.ticker,
        "option_symbol": trade.option_symbol,
        "entry_ts": trade.entry_ts.isoformat() if isinstance(trade.entry_ts, datetime) else str(trade.entry_ts),
        "exit_ts": trade.exit_ts.isoformat() if isinstance(trade.exit_ts, datetime) else str(trade.exit_ts),
        "side": trade.side,
        "qty": int(trade.qty),
        "entry_price": float(trade.entry_price),
        "exit_price": float(trade.exit_price),
        "pnl": float(trade.pnl),
        "return_pct": float(trade.return_pct),
        "status": trade.status,
        "metadata": dict(trade.metadata or {}),
    }


def _summarize_trades(
    trades: List[BacktestTrade],
    returns: List[float],
    initial_equity: float,
    final_equity: float,
    start: datetime,
    end: datetime,
) -> Dict[str, Any]:
    total_return = (final_equity / initial_equity) - 1.0 if initial_equity > 0 else 0.0
    years = max((end - start).days / 365.25, 1.0 / 365.25)
    cagr = ((final_equity / initial_equity) ** (1.0 / years) - 1.0) if initial_equity > 0 else 0.0

    win_rate = 0.0
    if trades:
        win_rate = sum(1 for trade in trades if trade.pnl > 0) / len(trades)

    avg_return = _mean_fast(returns) if returns else 0.0
    sharpe = 0.0
    if len(returns) > 1:
        volatility = pstdev(returns)
        if volatility > 0:
            sharpe = (avg_return / volatility) * sqrt(252.0)

    sortino = 0.0
    if returns:
        downside_squares = [min(value, 0.0) ** 2 for value in returns]
        downside_deviation = sqrt(sum(downside_squares) / len(downside_squares))
        if downside_deviation > 0:
            sortino = (avg_return / downside_deviation) * sqrt(252.0)

    max_drawdown = _max_drawdown(initial_equity=initial_equity, trades=trades)

    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "trades": len(trades),
        "initial_equity": round(initial_equity, 2),
        "final_equity": round(final_equity, 2),
        "total_return": round(total_return, 6),
        "cagr": round(cagr, 6),
        "win_rate": round(win_rate, 6),
        "avg_trade_return": round(avg_return, 6),
        "sharpe": round(sharpe, 6),
        "sortino": round(sortino, 6),
        "max_drawdown": round(max_drawdown, 6),
    }


def _max_drawdown(initial_equity: float, trades: List[BacktestTrade]) -> float:
    high_water = initial_equity
    equity = initial_equity
    max_dd = 0.0
    for trade in trades:
        equity += trade.pnl
        if equity > high_water:
            high_water = equity
        drawdown = (equity / high_water) - 1.0 if high_water > 0 else 0.0
        if drawdown < max_dd:
            max_dd = drawdown
    return max_dd
