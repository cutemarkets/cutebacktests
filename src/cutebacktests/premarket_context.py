from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo


ET = ZoneInfo("America/New_York")
PREMARKET_START_ET = time(4, 0)
PREMARKET_END_ET = time(9, 30)


def safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def as_et(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc).astimezone(ET)
    return ts.astimezone(ET)


def iter_weekdays(start_day: date, end_day: date) -> Iterable[date]:
    cursor = start_day
    while cursor <= end_day:
        if cursor.weekday() < 5:
            yield cursor
        cursor += timedelta(days=1)


def next_weekday(day: date) -> date:
    cursor = day + timedelta(days=1)
    while cursor.weekday() >= 5:
        cursor += timedelta(days=1)
    return cursor


def _coerce_ts(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def normalize_stock_bar_row(ticker: str, row: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    ts = _coerce_ts(row.get("ts") or row.get("timestamp") or row.get("t"))
    if ts is None:
        return None
    out = {
        "ticker": str(ticker or row.get("ticker") or row.get("symbol") or "").strip().upper(),
        "ts": ts,
        "open": safe_float(row.get("open") if "open" in row else row.get("o")),
        "high": safe_float(row.get("high") if "high" in row else row.get("h")),
        "low": safe_float(row.get("low") if "low" in row else row.get("l")),
        "close": safe_float(row.get("close") if "close" in row else row.get("c")),
        "volume": int(row.get("volume") or row.get("v") or 0),
    }
    if not out["ticker"]:
        out["ticker"] = str(ticker or "").strip().upper()
    return out


def group_premarket_rows_by_day(
    *,
    ticker: str,
    rows: Sequence[Mapping[str, Any]],
    start_day: date,
    end_day: date,
) -> Tuple[Dict[date, List[Dict[str, Any]]], int]:
    grouped: Dict[date, List[Dict[str, Any]]] = defaultdict(list)
    normalization_failures = 0
    for raw_row in rows:
        normalized = normalize_stock_bar_row(ticker, raw_row)
        if normalized is None:
            normalization_failures += 1
            continue
        et_dt = as_et(normalized["ts"])
        if et_dt.date() < start_day or et_dt.date() > end_day:
            continue
        if not (PREMARKET_START_ET <= et_dt.time() < PREMARKET_END_ET):
            continue
        grouped[et_dt.date()].append(normalized)
    for day_rows in grouped.values():
        day_rows.sort(key=lambda row: row["ts"])
    return dict(grouped), normalization_failures


def _store_rows_in_window(
    store: Any,
    *,
    ticker: str,
    start_day: date,
    end_day: date,
) -> List[Mapping[str, Any]]:
    start_dt = datetime.combine(start_day, time(0, 0))
    end_dt = datetime.combine(end_day + timedelta(days=1), time(0, 0))
    range_getter = getattr(store, "get_stock_bars_range", None)
    if callable(range_getter):
        return list(range_getter(ticker=ticker.upper(), start=start_dt, end=end_dt) or [])
    return list(store.get_stock_bars(ticker=ticker.upper(), start=start_dt, end=end_dt) or [])


def load_store_premarket_bars_by_day(
    store: Any,
    *,
    ticker: str,
    start_day: date,
    end_day: date,
) -> Tuple[Dict[date, List[Dict[str, Any]]], int]:
    if store is None:
        return {}, 0
    try:
        rows = _store_rows_in_window(store, ticker=ticker, start_day=start_day, end_day=end_day)
    except Exception:
        return {}, 0
    return group_premarket_rows_by_day(
        ticker=ticker,
        rows=rows,
        start_day=start_day,
        end_day=end_day,
    )


def load_cutemarkets_premarket_bars_by_day(
    cutemarkets: Any,
    *,
    ticker: str,
    start_day: date,
    end_day: date,
) -> Tuple[Dict[date, List[Dict[str, Any]]], int]:
    if cutemarkets is None:
        return {}, 0
    try:
        rows = cutemarkets.fetch_stock_bars(
            ticker=ticker,
            start=start_day,
            end=end_day,
            multiplier=1,
            timespan="minute",
        )
    except Exception:
        return {}, 0
    return group_premarket_rows_by_day(
        ticker=ticker,
        rows=list(rows or []),
        start_day=start_day,
        end_day=end_day,
    )


def load_alpaca_premarket_bars_by_day(
    alpaca: Any,
    *,
    ticker: str,
    start_day: date,
    end_day: date,
) -> Tuple[Dict[date, List[Dict[str, Any]]], int]:
    if alpaca is None:
        return {}, 0
    try:
        rows = alpaca.fetch_stock_bars(
            symbol=ticker,
            start=f"{start_day.isoformat()}T00:00:00Z",
            end=f"{(end_day + timedelta(days=1)).isoformat()}T00:00:00Z",
            timeframe="1Min",
            limit=10000,
        )
    except Exception:
        return {}, 0
    return group_premarket_rows_by_day(
        ticker=ticker,
        rows=list(rows or []),
        start_day=start_day,
        end_day=end_day,
    )


def load_premarket_source_maps(
    *,
    store: Any,
    cutemarkets: Any,
    alpaca: Any,
    ticker: str,
    start_day: date,
    end_day: date,
) -> Dict[str, Any]:
    store_map, store_failures = load_store_premarket_bars_by_day(
        store,
        ticker=ticker,
        start_day=start_day,
        end_day=end_day,
    )
    cutemarkets_map, cutemarkets_failures = load_cutemarkets_premarket_bars_by_day(
        cutemarkets,
        ticker=ticker,
        start_day=start_day,
        end_day=end_day,
    )
    alpaca_map, alpaca_failures = load_alpaca_premarket_bars_by_day(
        alpaca,
        ticker=ticker,
        start_day=start_day,
        end_day=end_day,
    )
    return {
        "store": store_map,
        "cutemarkets": cutemarkets_map,
        "alpaca": alpaca_map,
        "normalization_failures": {
            "store": int(store_failures),
            "cutemarkets": int(cutemarkets_failures),
            "alpaca": int(alpaca_failures),
        },
    }


def resolve_premarket_day(
    *,
    store_rows: Sequence[Mapping[str, Any]],
    cutemarkets_rows: Sequence[Mapping[str, Any]],
    alpaca_rows: Sequence[Mapping[str, Any]],
) -> Tuple[List[Dict[str, Any]], str, str]:
    if store_rows:
        return [dict(row) for row in store_rows], "store", "primary_store"
    if cutemarkets_rows:
        return [dict(row) for row in cutemarkets_rows], "cutemarkets", "store_empty_cutemarkets_fallback"
    if alpaca_rows:
        if cutemarkets_rows:
            return [dict(row) for row in alpaca_rows], "alpaca", "cutemarkets_error_alpaca_fallback"
        return [dict(row) for row in alpaca_rows], "alpaca", "store_empty_alpaca_fallback"
    return [], "none", "no_source_coverage"


def resolve_premarket_days_with_fallback(
    *,
    source_maps: Mapping[str, Mapping[date, Sequence[Mapping[str, Any]]]],
    start_day: date,
    end_day: date,
) -> Tuple[Dict[date, List[Dict[str, Any]]], Dict[date, str], Dict[str, int]]:
    resolved: Dict[date, List[Dict[str, Any]]] = {}
    source_used: Dict[date, str] = {}
    fallback_counts: Dict[str, int] = defaultdict(int)
    for day in iter_weekdays(start_day, end_day):
        bars, source, reason = resolve_premarket_day(
            store_rows=list((source_maps.get("store") or {}).get(day, [])),
            cutemarkets_rows=list((source_maps.get("cutemarkets") or {}).get(day, [])),
            alpaca_rows=list((source_maps.get("alpaca") or {}).get(day, [])),
        )
        resolved[day] = bars
        source_used[day] = source
        fallback_counts[reason] += 1
    return resolved, source_used, {key: int(value) for key, value in fallback_counts.items()}


def fetch_cutemarkets_headlines_by_scan_date(
    cutemarkets: Any,
    *,
    ticker: str,
    start_day: date,
    end_day: date,
) -> Dict[date, List[str]]:
    if cutemarkets is None:
        return {}
    prev_dt = datetime.combine(start_day - timedelta(days=1), time(16, 0), tzinfo=ET)
    cur_dt = datetime.combine(end_day, time(9, 30), tzinfo=ET)
    try:
        articles = cutemarkets.fetch_news(
            ticker=ticker,
            published_after=prev_dt.astimezone(timezone.utc).replace(tzinfo=None),
            published_before=cur_dt.astimezone(timezone.utc).replace(tzinfo=None),
            limit=1000,
        )
    except Exception:
        return {}

    grouped: Dict[date, List[str]] = defaultdict(list)
    for article in articles or []:
        headline = str(article.get("headline") or "").strip()
        published_utc = article.get("published_utc")
        if not headline or not isinstance(published_utc, datetime):
            continue
        published_et = as_et(published_utc)
        if published_et.time() >= time(16, 0):
            scan_day = next_weekday(published_et.date())
        elif published_et.time() <= time(9, 30):
            scan_day = published_et.date()
        else:
            continue
        if scan_day < start_day or scan_day > end_day or scan_day.weekday() >= 5:
            continue
        grouped[scan_day].append(headline)
    return dict(grouped)


def fetch_alpaca_headlines_by_scan_date(
    alpaca: Any,
    *,
    ticker: str,
    start_day: date,
    end_day: date,
) -> Dict[date, List[str]]:
    if alpaca is None:
        return {}
    prev_dt = datetime.combine(start_day - timedelta(days=1), time(16, 0), tzinfo=ET)
    cur_dt = datetime.combine(end_day, time(9, 30), tzinfo=ET)
    try:
        articles = alpaca.fetch_news(
            ticker=ticker,
            published_after=prev_dt.astimezone(timezone.utc).replace(tzinfo=None),
            published_before=cur_dt.astimezone(timezone.utc).replace(tzinfo=None),
            limit=1000,
        )
    except Exception:
        return {}

    grouped: Dict[date, List[str]] = defaultdict(list)
    for article in articles or []:
        headline = str(article.get("headline") or "").strip()
        published_utc = article.get("published_utc")
        if not headline or not isinstance(published_utc, datetime):
            continue
        published_et = as_et(published_utc)
        if published_et.time() >= time(16, 0):
            scan_day = next_weekday(published_et.date())
        elif published_et.time() <= time(9, 30):
            scan_day = published_et.date()
        else:
            continue
        if scan_day < start_day or scan_day > end_day or scan_day.weekday() >= 5:
            continue
        grouped[scan_day].append(headline)
    return dict(grouped)


def merge_headlines_by_scan_date(
    primary: Mapping[date, Sequence[str]],
    secondary: Mapping[date, Sequence[str]],
) -> Dict[date, List[str]]:
    merged: Dict[date, List[str]] = {}
    for scan_day in sorted(set(primary) | set(secondary)):
        seen: set[str] = set()
        ordered: List[str] = []
        for headline in list(primary.get(scan_day) or []) + list(secondary.get(scan_day) or []):
            text = str(headline or "").strip()
            if not text:
                continue
            normalized = text.lower()
            if normalized in seen:
                continue
            seen.add(normalized)
            ordered.append(text)
        if ordered:
            merged[scan_day] = ordered
    return merged


def build_store_day_features(
    store: Any,
    *,
    ticker: str,
    start_day: date,
    end_day: date,
    lookback_days: int = 60,
) -> Dict[str, Any]:
    rows = _store_rows_in_window(
        store,
        ticker=ticker,
        start_day=start_day - timedelta(days=max(int(lookback_days), 1)),
        end_day=end_day,
    )
    day_volume_by_day: Dict[date, float] = defaultdict(float)
    day_last_close_by_day: Dict[date, float] = {}
    premarket_bars_by_day: Dict[date, List[Dict[str, Any]]] = defaultdict(list)
    for raw_row in rows:
        normalized = normalize_stock_bar_row(ticker, raw_row)
        if normalized is None:
            continue
        et_dt = as_et(normalized["ts"])
        day = et_dt.date()
        if day < (start_day - timedelta(days=max(int(lookback_days), 1))) or day > end_day:
            continue
        volume = float(normalized.get("volume") or 0.0)
        day_volume_by_day[day] = day_volume_by_day.get(day, 0.0) + max(volume, 0.0)
        close_value = safe_float(normalized.get("close"))
        if close_value is not None:
            day_last_close_by_day[day] = close_value
        if PREMARKET_START_ET <= et_dt.time() < PREMARKET_END_ET:
            premarket_bars_by_day[day].append(normalized)
    for day_rows in premarket_bars_by_day.values():
        day_rows.sort(key=lambda row: row["ts"])
    trading_days = sorted(day_last_close_by_day)
    return {
        "premarket_bars_by_day": dict(premarket_bars_by_day),
        "day_volume_by_day": dict(day_volume_by_day),
        "day_last_close_by_day": dict(day_last_close_by_day),
        "trading_days": trading_days,
    }


def resolve_prev_close_from_features(
    *,
    day_last_close_by_day: Mapping[date, float],
    trading_days: Sequence[date],
    day: date,
) -> Optional[float]:
    prior_days = [candidate for candidate in trading_days if candidate < day]
    if not prior_days:
        return None
    return safe_float(day_last_close_by_day.get(prior_days[-1]))


def resolve_avg_daily_volume_from_features(
    *,
    day_volume_by_day: Mapping[date, float],
    trading_days: Sequence[date],
    day: date,
    lookback_days: int = 20,
) -> Optional[float]:
    prior_days = [candidate for candidate in trading_days if candidate < day]
    if not prior_days:
        return None
    window = prior_days[-max(int(lookback_days), 1) :]
    volumes = [float(day_volume_by_day.get(candidate) or 0.0) for candidate in window if float(day_volume_by_day.get(candidate) or 0.0) > 0.0]
    if not volumes:
        return None
    return sum(volumes) / len(volumes)


def resolve_recent_daily_volume_ratio_from_features(
    *,
    day_volume_by_day: Mapping[date, float],
    trading_days: Sequence[date],
    day: date,
    fast_lookback: int = 5,
    slow_lookback: int = 20,
) -> Optional[float]:
    fast_avg = resolve_avg_daily_volume_from_features(
        day_volume_by_day=day_volume_by_day,
        trading_days=trading_days,
        day=day,
        lookback_days=fast_lookback,
    )
    slow_avg = resolve_avg_daily_volume_from_features(
        day_volume_by_day=day_volume_by_day,
        trading_days=trading_days,
        day=day,
        lookback_days=slow_lookback,
    )
    if fast_avg is None or slow_avg is None or slow_avg <= 0.0:
        return None
    return float(fast_avg) / float(slow_avg)


def build_preopen_context_row(
    *,
    ticker: str,
    day: date,
    source_used: str,
    premarket_bars: Sequence[Mapping[str, Any]],
    prev_close: Optional[float],
    adv_20: Optional[float],
    recent_daily_volume_ratio_5d_20d: Optional[float],
    vix_prev_close: Optional[float] = None,
    vix_5d_change_pct: Optional[float] = None,
) -> Dict[str, Any]:
    bars = sorted([dict(row) for row in premarket_bars], key=lambda row: row.get("ts"))
    prev_close_value = safe_float(prev_close)
    adv_20_value = safe_float(adv_20)
    premarket_bar_count = len(bars)
    premarket_volume = int(sum(int(row.get("volume") or 0) for row in bars))
    premarket_dollar_volume = 0.0
    pm_high: Optional[float] = None
    pm_low: Optional[float] = None
    last_close: Optional[float] = None
    for row in bars:
        close_value = safe_float(row.get("close"))
        open_value = safe_float(row.get("open"))
        high_value = safe_float(row.get("high"))
        low_value = safe_float(row.get("low"))
        volume_value = int(row.get("volume") or 0)
        px_for_dv = close_value if close_value is not None else open_value
        if px_for_dv is not None and volume_value > 0:
            premarket_dollar_volume += float(px_for_dv) * float(volume_value)
        if high_value is not None:
            pm_high = high_value if pm_high is None else max(pm_high, high_value)
        if low_value is not None:
            pm_low = low_value if pm_low is None else min(pm_low, low_value)
        if close_value is not None:
            last_close = close_value

    premarket_range_pct: Optional[float] = None
    premarket_high_gap_pct: Optional[float] = None
    premarket_last_gap_pct: Optional[float] = None
    if prev_close_value is not None and prev_close_value > 0.0:
        if pm_high is not None and pm_low is not None and pm_high >= pm_low:
            premarket_range_pct = (float(pm_high) - float(pm_low)) / float(prev_close_value)
        if pm_high is not None:
            premarket_high_gap_pct = (float(pm_high) - float(prev_close_value)) / float(prev_close_value)
        if last_close is not None:
            premarket_last_gap_pct = (float(last_close) - float(prev_close_value)) / float(prev_close_value)

    premarket_volume_pct_of_adv: Optional[float] = None
    if adv_20_value is not None and adv_20_value > 0.0:
        premarket_volume_pct_of_adv = float(premarket_volume) / float(adv_20_value)

    eligible = True
    reject_reason = ""
    if premarket_bar_count <= 0:
        eligible = False
        reject_reason = "missing_premarket_bars"
    elif prev_close_value is None or prev_close_value <= 0.0:
        eligible = False
        reject_reason = "missing_prev_close"
    elif adv_20_value is None or adv_20_value <= 0.0:
        eligible = False
        reject_reason = "missing_adv_20"

    return {
        "ticker": str(ticker or "").strip().upper(),
        "day": day.isoformat(),
        "source_used": str(source_used or "none"),
        "premarket_bar_count": int(premarket_bar_count),
        "premarket_volume": int(premarket_volume),
        "premarket_dollar_volume": round(float(premarket_dollar_volume), 4),
        "premarket_range_pct": premarket_range_pct,
        "premarket_high_gap_pct": premarket_high_gap_pct,
        "premarket_last_gap_pct": premarket_last_gap_pct,
        "prev_close": prev_close_value,
        "adv_20": adv_20_value,
        "premarket_volume_pct_of_adv": premarket_volume_pct_of_adv,
        "recent_daily_volume_ratio_5d_20d": safe_float(recent_daily_volume_ratio_5d_20d),
        "vix_prev_close": safe_float(vix_prev_close),
        "vix_5d_change_pct": safe_float(vix_5d_change_pct),
        "eligible": bool(eligible),
        "reject_reason": str(reject_reason),
    }
