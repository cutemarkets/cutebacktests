from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time as dt_time, timedelta, timezone
from statistics import median
from typing import Any, Dict, Iterable, List, Sequence
from zoneinfo import ZoneInfo

from ..providers.alpaca import AlpacaDataProvider
from ..settings import Settings
from ..utils import parse_datetime

_ET_ZONE = ZoneInfo("America/New_York")


@dataclass
class PreOpenSelectorConfig:
    snapshot_time_et: str = "09:25"
    dynamic_max_adds: int = 2
    min_premarket_bars: int = 3
    min_premarket_dollar_volume_m: float = 0.05
    min_option_median_open_interest: float = 100.0
    option_lookahead_days: int = 7
    weight_premarket_dollar_volume: float = 0.5
    weight_premarket_range: float = 0.3
    weight_option_liquidity: float = 0.2


def select_preopen_stocks_in_play(
    *,
    settings: Settings,
    data_provider: AlpacaDataProvider,
    as_of_utc: datetime,
    core_tickers: Sequence[str],
    dynamic_candidates: Sequence[str],
    config: PreOpenSelectorConfig,
) -> Dict[str, Any]:
    as_of_et = _as_et(as_of_utc)
    session_day = as_of_et.date()
    snapshot_time = _parse_hhmm(config.snapshot_time_et, default_value="09:25")
    is_ready = as_of_et.time() >= snapshot_time

    base = _normalize_tickers(core_tickers)
    candidates = [ticker for ticker in _normalize_tickers(dynamic_candidates) if ticker not in set(base)]
    if not candidates:
        return {
            "enabled": True,
            "status": "no_candidates",
            "day_et": session_day.isoformat(),
            "as_of_utc": _as_utc_naive(as_of_utc).isoformat(),
            "as_of_et": as_of_et.isoformat(),
            "snapshot_time_et": config.snapshot_time_et,
            "core_tickers": base,
            "dynamic_candidates": [],
            "selected_adds": [],
            "selected_universe": base,
            "ranking": [],
        }

    if not is_ready:
        return {
            "enabled": True,
            "status": "waiting_snapshot",
            "day_et": session_day.isoformat(),
            "as_of_utc": _as_utc_naive(as_of_utc).isoformat(),
            "as_of_et": as_of_et.isoformat(),
            "snapshot_time_et": config.snapshot_time_et,
            "core_tickers": base,
            "dynamic_candidates": candidates,
            "selected_adds": [],
            "selected_universe": base,
            "ranking": [],
        }

    rows: List[Dict[str, Any]] = []
    for ticker in candidates:
        metrics = _collect_candidate_metrics(
            settings=settings,
            data_provider=data_provider,
            ticker=ticker,
            session_day=session_day,
            as_of_et=as_of_et,
            config=config,
        )
        rows.append(metrics)

    eligible = [row for row in rows if bool(row.get("eligible"))]
    _attach_scores(eligible=eligible, config=config)
    ranked = sorted(rows, key=lambda row: float(row.get("score") or 0.0), reverse=True)

    max_adds = max(int(config.dynamic_max_adds), 0)
    selected_adds = [row["ticker"] for row in ranked if bool(row.get("eligible"))][:max_adds]
    selected_universe = base + [ticker for ticker in selected_adds if ticker not in set(base)]

    return {
        "enabled": True,
        "status": "selected",
        "day_et": session_day.isoformat(),
        "as_of_utc": _as_utc_naive(as_of_utc).isoformat(),
        "as_of_et": as_of_et.isoformat(),
        "snapshot_time_et": config.snapshot_time_et,
        "core_tickers": base,
        "dynamic_candidates": candidates,
        "selected_adds": selected_adds,
        "selected_universe": selected_universe,
        "ranking": ranked,
    }


def _collect_candidate_metrics(
    *,
    settings: Settings,
    data_provider: AlpacaDataProvider,
    ticker: str,
    session_day: date,
    as_of_et: datetime,
    config: PreOpenSelectorConfig,
) -> Dict[str, Any]:
    start_utc = datetime.combine(session_day, dt_time(0, 0), tzinfo=_ET_ZONE).astimezone(timezone.utc)
    end_utc = datetime.combine(session_day + timedelta(days=1), dt_time(0, 0), tzinfo=_ET_ZONE).astimezone(timezone.utc)
    start_iso = start_utc.isoformat().replace("+00:00", "Z")
    end_iso = end_utc.isoformat().replace("+00:00", "Z")

    try:
        bars = data_provider.fetch_stock_bars(
            symbol=ticker,
            start=start_iso,
            end=end_iso,
            timeframe="1Min",
        )
    except Exception as exc:
        return {
            "ticker": ticker,
            "eligible": False,
            "rejection_reason": f"stock_fetch_error:{type(exc).__name__}",
            "premarket_bars": 0,
            "premarket_dollar_volume_m": 0.0,
            "premarket_range_pct": 0.0,
            "option_contracts_lookahead": 0,
            "option_median_open_interest": 0.0,
            "score": 0.0,
        }

    premarket = _premarket_window_rows(rows=bars, session_day=session_day, as_of_et=as_of_et)
    bar_count = len(premarket)
    premarket_dollar_volume = sum(float(row["close"]) * float(row["volume"]) for row in premarket)
    premarket_dollar_volume_m = premarket_dollar_volume / 1_000_000.0

    premarket_range_pct = 0.0
    if premarket:
        lows = [float(row["low"]) for row in premarket if float(row["low"]) > 0]
        highs = [float(row["high"]) for row in premarket if float(row["high"]) > 0]
        if lows and highs:
            low = min(lows)
            high = max(highs)
            if low > 0 and high >= low:
                premarket_range_pct = ((high - low) / low) * 100.0

    end_day = session_day + timedelta(days=max(int(config.option_lookahead_days), 0))
    try:
        contracts = data_provider.fetch_option_contracts(
            underlying_symbol=ticker,
            expiration_date_gte=session_day.isoformat(),
            expiration_date_lte=end_day.isoformat(),
            status="active",
            limit=1000,
        )
    except Exception:
        contracts = []
    open_interests = [int(row.get("open_interest") or 0) for row in contracts if int(row.get("open_interest") or 0) > 0]
    median_open_interest = float(median(open_interests)) if open_interests else 0.0

    eligible = True
    rejection_reason = ""
    if bar_count < max(int(config.min_premarket_bars), 1):
        eligible = False
        rejection_reason = "premarket_bars_below_min"
    elif premarket_dollar_volume_m < max(float(config.min_premarket_dollar_volume_m), 0.0):
        eligible = False
        rejection_reason = "premarket_dollar_volume_below_min"
    elif median_open_interest < max(float(config.min_option_median_open_interest), 0.0):
        eligible = False
        rejection_reason = "option_median_oi_below_min"

    return {
        "ticker": ticker,
        "eligible": bool(eligible),
        "rejection_reason": rejection_reason,
        "premarket_bars": bar_count,
        "premarket_dollar_volume_m": premarket_dollar_volume_m,
        "premarket_range_pct": premarket_range_pct,
        "option_contracts_lookahead": len(contracts),
        "option_median_open_interest": median_open_interest,
        "score": 0.0,
    }


def _premarket_window_rows(
    *,
    rows: Iterable[Dict[str, Any]],
    session_day: date,
    as_of_et: datetime,
) -> List[Dict[str, Any]]:
    start_et = dt_time(4, 0)
    end_et = dt_time(9, 30)
    out: List[Dict[str, Any]] = []
    for row in rows:
        ts = parse_datetime((row or {}).get("t"))
        if ts is None:
            continue
        ts_et = _as_et(ts)
        if ts_et.date() != session_day:
            continue
        if ts_et > as_of_et:
            continue
        local_time = ts_et.time()
        if local_time < start_et or local_time >= end_et:
            continue

        close = float(row.get("c") or 0.0)
        high = float(row.get("h") or 0.0)
        low = float(row.get("l") or 0.0)
        volume = float(row.get("v") or 0.0)
        if close <= 0 or high <= 0 or low <= 0 or volume <= 0:
            continue
        out.append(
            {
                "ts_et": ts_et,
                "close": close,
                "high": high,
                "low": low,
                "volume": volume,
            }
        )
    out.sort(key=lambda row: row["ts_et"])
    return out


def _attach_scores(*, eligible: List[Dict[str, Any]], config: PreOpenSelectorConfig) -> None:
    if not eligible:
        return
    dv_values = [float(row["premarket_dollar_volume_m"]) for row in eligible]
    range_values = [float(row["premarket_range_pct"]) for row in eligible]
    oi_values = [float(row["option_median_open_interest"]) for row in eligible]

    for row in eligible:
        dv_norm = _min_max_normalize(float(row["premarket_dollar_volume_m"]), dv_values)
        range_norm = _min_max_normalize(float(row["premarket_range_pct"]), range_values)
        oi_norm = _min_max_normalize(float(row["option_median_open_interest"]), oi_values)
        score = (
            float(config.weight_premarket_dollar_volume) * dv_norm
            + float(config.weight_premarket_range) * range_norm
            + float(config.weight_option_liquidity) * oi_norm
        )
        row["score"] = float(score)


def _min_max_normalize(value: float, values: Sequence[float]) -> float:
    if not values:
        return 0.0
    lower = min(values)
    upper = max(values)
    if upper <= lower:
        return 1.0
    return max(0.0, min(1.0, (value - lower) / (upper - lower)))


def _as_utc_naive(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts
    return ts.astimezone(timezone.utc).replace(tzinfo=None)


def _as_et(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        aware = ts.replace(tzinfo=timezone.utc)
    else:
        aware = ts.astimezone(timezone.utc)
    return aware.astimezone(_ET_ZONE)


def _parse_hhmm(value: str, default_value: str) -> dt_time:
    text = (value or "").strip() or default_value
    try:
        hh, mm = text.split(":", 1)
        return dt_time(hour=max(0, min(23, int(hh))), minute=max(0, min(59, int(mm))))
    except Exception:
        hh, mm = default_value.split(":", 1)
        return dt_time(hour=int(hh), minute=int(mm))


def _normalize_tickers(values: Sequence[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for raw in values:
        ticker = str(raw or "").strip().upper()
        if not ticker or ticker in seen:
            continue
        seen.add(ticker)
        out.append(ticker)
    return out
