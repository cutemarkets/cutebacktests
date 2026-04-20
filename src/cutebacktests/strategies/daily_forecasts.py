from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from math import sqrt
from statistics import median
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple


CARVER_UNIVERSE: Tuple[str, ...] = (
    "SPY",
    "QQQ",
    "IWM",
    "EFA",
    "EEM",
    "TLT",
    "IEF",
    "GLD",
    "XLK",
    "XLE",
    "XLF",
    "XLV",
)

ASSET_BUCKET_MEMBERS: Dict[str, Tuple[str, ...]] = {
    "broad_equity": ("SPY", "QQQ", "IWM", "EFA", "EEM"),
    "rates": ("TLT", "IEF"),
    "defensive_metals": ("GLD", "XLV"),
    "cyclical_sectors": ("XLK", "XLE", "XLF"),
}
ASSET_BUCKET_BY_TICKER: Dict[str, str] = {
    ticker: bucket
    for bucket, members in ASSET_BUCKET_MEMBERS.items()
    for ticker in members
}

TREND_FAMILY_WEIGHTS: Dict[str, float] = {
    "c40_daily_ewmac_fast_v1": 0.15,
    "c41_daily_ewmac_slow_v1": 0.20,
    "c42_daily_breakout_medium_v1": 0.10,
    "c43_daily_breakout_slow_v1": 0.20,
}
DIVERSIFIER_FAMILY_WEIGHTS: Dict[str, float] = {
    "c44_daily_relmom_bucket_v1": 0.20,
    "c45_daily_assettrend_bucket_v1": 0.15,
}
CARVER_FAMILY_WEIGHTS: Dict[str, float] = {
    **TREND_FAMILY_WEIGHTS,
    **DIVERSIFIER_FAMILY_WEIGHTS,
}
TREND_FAMILIES = frozenset(set(TREND_FAMILY_WEIGHTS) | {"c52_daily_trend_pullback_v1"})
DIVERSIFIER_FAMILIES = frozenset(DIVERSIFIER_FAMILY_WEIGHTS)
OVERLAY_FAMILIES = frozenset(
    {
        "c46_surface_ivrv_overlay_v1",
        "c47_surface_term_structure_overlay_v1",
        "c48_surface_skew_overlay_v1",
    }
)
COMBO_FAMILIES = frozenset({"c50_carver_core_combo_v1", "c51_carver_hybrid_portfolio_v1"})


@dataclass(frozen=True)
class DailyForecastConfig:
    signal_cadence: str = "daily_eod"
    forecast_family: str = ""
    lookback_fast: int = 16
    lookback_slow: int = 64
    lookback_breakout: int = 40
    lookback_relative: int = 63
    forecast_cap: float = 20.0
    vol_attenuation_enabled: bool = True
    vol_percentile_lookback: int = 252
    vol_attenuation_hi_pct: float = 80.0
    vol_attenuation_extreme_pct: float = 90.0


@dataclass(frozen=True)
class DailyForecastSnapshot:
    day: date
    ticker: str
    strategy_sleeve: str
    asset_bucket: str
    forecast_group: str
    forecast_family: str
    forecast_raw: float
    forecast_scaled: float
    forecast_capped: float
    forecast_weight: float
    combined_forecast: float
    forecast_turnover: float
    realized_vol_annualized: Optional[float]
    vol_percentile: Optional[float]
    attenuation_multiplier: float
    coverage_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "day": self.day.isoformat(),
            "ticker": self.ticker,
            "strategy_sleeve": self.strategy_sleeve,
            "asset_bucket": self.asset_bucket,
            "forecast_group": self.forecast_group,
            "forecast_family": self.forecast_family,
            "forecast_raw": float(self.forecast_raw),
            "forecast_scaled": float(self.forecast_scaled),
            "forecast_capped": float(self.forecast_capped),
            "forecast_weight": float(self.forecast_weight),
            "combined_forecast": float(self.combined_forecast),
            "forecast_turnover": float(self.forecast_turnover),
            "realized_vol_annualized": self.realized_vol_annualized,
            "vol_percentile": self.vol_percentile,
            "attenuation_multiplier": float(self.attenuation_multiplier),
            "coverage_count": int(self.coverage_count),
        }


def infer_asset_bucket(ticker: str) -> str:
    return ASSET_BUCKET_BY_TICKER.get(str(ticker or "").strip().upper(), "other")


def forecast_group_for_family(forecast_family: str) -> str:
    family = str(forecast_family or "").strip()
    if family in TREND_FAMILIES:
        return "trendy"
    if family in DIVERSIFIER_FAMILIES:
        return "diversifier"
    if family in OVERLAY_FAMILIES:
        return "surface_overlay"
    if family in COMBO_FAMILIES:
        return "combo"
    return "single"


def forecast_weight_for_family(forecast_family: str) -> float:
    family = str(forecast_family or "").strip()
    return float(CARVER_FAMILY_WEIGHTS.get(family, 1.0))


def bucket_members_for_ticker(ticker: str) -> Tuple[str, ...]:
    bucket = infer_asset_bucket(ticker)
    return ASSET_BUCKET_MEMBERS.get(bucket, (str(ticker or "").strip().upper(),))


def daily_row_lookup(rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    ordered: List[Dict[str, Any]] = []
    for row in rows:
        ts = row.get("ts")
        if not isinstance(ts, datetime):
            continue
        close = _safe_float(row.get("close"))
        open_ = _safe_float(row.get("open"))
        high = _safe_float(row.get("high"))
        low = _safe_float(row.get("low"))
        volume = int(row.get("volume") or 0)
        if close is None or close <= 0.0:
            continue
        ordered.append(
            {
                "day": _coerce_day(row.get("day")) or ts.date(),
                "ts": ts,
                "open": open_ if open_ is not None and open_ > 0.0 else close,
                "high": high if high is not None and high > 0.0 else close,
                "low": low if low is not None and low > 0.0 else close,
                "close": close,
                "volume": volume,
            }
        )
    ordered.sort(key=lambda item: item["day"])
    return ordered


def build_daily_forecast_snapshot(
    *,
    ticker: str,
    day: date,
    daily_rows: Sequence[Mapping[str, Any]],
    config: DailyForecastConfig,
    strategy_sleeve: str,
    peer_daily_rows: Optional[Mapping[str, Sequence[Mapping[str, Any]]]] = None,
    previous_snapshot: Optional[DailyForecastSnapshot] = None,
) -> Optional[DailyForecastSnapshot]:
    family = str(config.forecast_family or "").strip()
    if not family:
        return None
    ordered = daily_row_lookup(daily_rows)
    index = _row_index_for_day(ordered, day)
    if index is None:
        return None
    asset_bucket = infer_asset_bucket(ticker)
    raw, scaled, capped, realized_vol, vol_percentile, attenuation_multiplier, coverage_count = _compute_family_forecast(
        ticker=str(ticker or "").strip().upper(),
        family=family,
        rows=ordered,
        index=index,
        config=config,
        peer_daily_rows=peer_daily_rows,
    )
    if raw is None or scaled is None or capped is None:
        return None
    weight = forecast_weight_for_family(family)
    combined = capped * weight
    turnover = abs(capped - previous_snapshot.forecast_capped) if previous_snapshot is not None else abs(capped)
    return DailyForecastSnapshot(
        day=day,
        ticker=str(ticker or "").strip().upper(),
        strategy_sleeve=str(strategy_sleeve or "").strip() or "core_daily",
        asset_bucket=asset_bucket,
        forecast_group=forecast_group_for_family(family),
        forecast_family=family,
        forecast_raw=float(raw),
        forecast_scaled=float(scaled),
        forecast_capped=float(capped),
        forecast_weight=float(weight),
        combined_forecast=float(combined),
        forecast_turnover=float(turnover),
        realized_vol_annualized=realized_vol,
        vol_percentile=vol_percentile,
        attenuation_multiplier=float(attenuation_multiplier),
        coverage_count=int(coverage_count),
    )


def build_combo_forecast_snapshot(
    *,
    ticker: str,
    day: date,
    daily_rows: Sequence[Mapping[str, Any]],
    config: DailyForecastConfig,
    strategy_sleeve: str,
    peer_daily_rows: Optional[Mapping[str, Sequence[Mapping[str, Any]]]] = None,
    previous_combined_forecast: Optional[float] = None,
) -> Optional[DailyForecastSnapshot]:
    component_snapshots: List[DailyForecastSnapshot] = []
    for family in CARVER_FAMILY_WEIGHTS:
        component = build_daily_forecast_snapshot(
            ticker=ticker,
            day=day,
            daily_rows=daily_rows,
            config=DailyForecastConfig(
                signal_cadence=config.signal_cadence,
                forecast_family=family,
                lookback_fast=config.lookback_fast,
                lookback_slow=config.lookback_slow,
                lookback_breakout=config.lookback_breakout,
                lookback_relative=config.lookback_relative,
                forecast_cap=config.forecast_cap,
                vol_attenuation_enabled=config.vol_attenuation_enabled,
                vol_percentile_lookback=config.vol_percentile_lookback,
                vol_attenuation_hi_pct=config.vol_attenuation_hi_pct,
                vol_attenuation_extreme_pct=config.vol_attenuation_extreme_pct,
            ),
            strategy_sleeve=strategy_sleeve,
            peer_daily_rows=peer_daily_rows,
            previous_snapshot=None,
        )
        if component is not None:
            component_snapshots.append(component)
    if not component_snapshots:
        return None
    ordered = daily_row_lookup(daily_rows)
    index = _row_index_for_day(ordered, day)
    if index is None:
        return None
    realized_vol = _realized_vol_annualized(ordered, index=index, lookback=20)
    combined = sum(snapshot.combined_forecast for snapshot in component_snapshots)
    combined_capped = _cap_value(combined, config.forecast_cap)
    raw_proxy = sum(snapshot.forecast_raw * snapshot.forecast_weight for snapshot in component_snapshots)
    scaled_proxy = sum(snapshot.forecast_scaled * snapshot.forecast_weight for snapshot in component_snapshots)
    vol_percentile = _vol_percentile(
        ordered,
        index=index,
        lookback=max(int(config.vol_percentile_lookback), 20),
    )
    turnover = abs(combined_capped - float(previous_combined_forecast or 0.0))
    family = str(config.forecast_family or "c50_carver_core_combo_v1").strip()
    return DailyForecastSnapshot(
        day=day,
        ticker=str(ticker or "").strip().upper(),
        strategy_sleeve=str(strategy_sleeve or "").strip() or "core_daily",
        asset_bucket=infer_asset_bucket(ticker),
        forecast_group="combo",
        forecast_family=family,
        forecast_raw=float(raw_proxy),
        forecast_scaled=float(scaled_proxy),
        forecast_capped=float(combined_capped),
        forecast_weight=1.0,
        combined_forecast=float(combined_capped),
        forecast_turnover=float(turnover),
        realized_vol_annualized=realized_vol,
        vol_percentile=vol_percentile,
        attenuation_multiplier=1.0,
        coverage_count=len(component_snapshots),
    )


def _compute_family_forecast(
    *,
    ticker: str,
    family: str,
    rows: Sequence[Mapping[str, Any]],
    index: int,
    config: DailyForecastConfig,
    peer_daily_rows: Optional[Mapping[str, Sequence[Mapping[str, Any]]]],
) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float], Optional[float], float, int]:
    close = _safe_float(rows[index].get("close"))
    if close is None or close <= 0.0:
        return None, None, None, None, None, 1.0, 0
    realized_vol = _realized_vol_annualized(rows, index=index, lookback=20)
    vol_scale = max(realized_vol or 0.20, 0.05)
    if family == "c40_daily_ewmac_fast_v1":
        raw = _ewmac_raw(rows, index=index, fast=max(int(config.lookback_fast), 2), slow=max(int(config.lookback_slow), 3))
    elif family == "c41_daily_ewmac_slow_v1":
        raw = _ewmac_raw(rows, index=index, fast=max(int(config.lookback_fast), 4), slow=max(int(config.lookback_slow), 6))
    elif family == "c42_daily_breakout_medium_v1":
        raw = _breakout_raw(rows, index=index, lookback=max(int(config.lookback_breakout), 5))
    elif family == "c43_daily_breakout_slow_v1":
        raw = _breakout_raw(rows, index=index, lookback=max(int(config.lookback_breakout), 10))
    elif family == "c52_daily_trend_pullback_v1":
        raw = _trend_pullback_raw(
            rows,
            index=index,
            fast=max(int(config.lookback_fast), 2),
            slow=max(int(config.lookback_slow), max(int(config.lookback_fast), 2) + 1),
        )
    elif family == "c44_daily_relmom_bucket_v1":
        raw, coverage_count = _relative_momentum_raw(
            ticker=ticker,
            rows=rows,
            index=index,
            lookback=max(int(config.lookback_relative), 5),
            peer_daily_rows=peer_daily_rows,
        )
        attenuation_multiplier = 1.0
        scaled = raw
        capped = _cap_value(scaled, config.forecast_cap)
        return raw, scaled, capped, realized_vol, None, attenuation_multiplier, coverage_count
    elif family == "c45_daily_assettrend_bucket_v1":
        raw, coverage_count = _asset_trend_raw(
            ticker=ticker,
            rows=rows,
            index=index,
            lookback=max(int(config.lookback_relative), 5),
            peer_daily_rows=peer_daily_rows,
        )
        attenuation_multiplier = 1.0
        scaled = raw
        capped = _cap_value(scaled, config.forecast_cap)
        return raw, scaled, capped, realized_vol, None, attenuation_multiplier, coverage_count
    else:
        return None, None, None, realized_vol, None, 1.0, 0
    scaled = raw / max(vol_scale, 1e-6)
    attenuation_multiplier = 1.0
    vol_percentile = None
    if family in TREND_FAMILIES and bool(config.vol_attenuation_enabled):
        vol_percentile = _vol_percentile(rows, index=index, lookback=max(int(config.vol_percentile_lookback), 20))
        if vol_percentile is not None:
            if vol_percentile > float(config.vol_attenuation_extreme_pct):
                attenuation_multiplier = 0.25
            elif vol_percentile > float(config.vol_attenuation_hi_pct):
                attenuation_multiplier = 0.50
    scaled *= attenuation_multiplier * 10.0
    capped = _cap_value(scaled, config.forecast_cap)
    return raw, scaled, capped, realized_vol, vol_percentile, attenuation_multiplier, 1


def _coerce_day(value: Any) -> Optional[date]:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if value is None:
        return None
    try:
        return datetime.fromisoformat(str(value)).date()
    except Exception:
        return None


def _safe_float(value: Any) -> Optional[float]:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if out != out:
        return None
    return out


def _row_index_for_day(rows: Sequence[Mapping[str, Any]], target_day: date) -> Optional[int]:
    for index, row in enumerate(rows):
        if row.get("day") == target_day:
            return index
    return None


def _cap_value(value: float, forecast_cap: float) -> float:
    cap = abs(float(forecast_cap or 20.0))
    return max(min(float(value), cap), -cap)


def _ema(values: Sequence[float], length: int) -> Optional[float]:
    if length <= 0 or len(values) < length:
        return None
    alpha = 2.0 / (float(length) + 1.0)
    ema_value = float(values[0])
    for value in values[1:]:
        ema_value = (alpha * float(value)) + ((1.0 - alpha) * ema_value)
    return ema_value


def _ewmac_raw(rows: Sequence[Mapping[str, Any]], *, index: int, fast: int, slow: int) -> float:
    closes = [float(row.get("close") or 0.0) for row in rows[: index + 1] if float(row.get("close") or 0.0) > 0.0]
    if len(closes) < max(slow, fast, 5):
        return 0.0
    fast_ema = _ema(closes[-fast:], fast)
    slow_ema = _ema(closes[-slow:], slow)
    close = closes[-1]
    if fast_ema is None or slow_ema is None or close <= 0.0:
        return 0.0
    return ((fast_ema - slow_ema) / close) * 100.0


def _breakout_raw(rows: Sequence[Mapping[str, Any]], *, index: int, lookback: int) -> float:
    if index < lookback:
        return 0.0
    window = rows[index - lookback:index]
    highs = [float(row.get("high") or 0.0) for row in window if float(row.get("high") or 0.0) > 0.0]
    lows = [float(row.get("low") or 0.0) for row in window if float(row.get("low") or 0.0) > 0.0]
    close = float(rows[index].get("close") or 0.0)
    if not highs or not lows or close <= 0.0:
        return 0.0
    window_high = max(highs)
    window_low = min(lows)
    if window_high <= window_low:
        return 0.0
    position = ((close - window_low) / (window_high - window_low)) * 2.0 - 1.0
    return position * 2.0


def _trend_pullback_raw(rows: Sequence[Mapping[str, Any]], *, index: int, fast: int, slow: int) -> float:
    closes = [float(row.get("close") or 0.0) for row in rows[: index + 1] if float(row.get("close") or 0.0) > 0.0]
    if len(closes) < max(slow, fast, 5):
        return 0.0
    fast_ema = _ema(closes[-fast:], fast)
    slow_ema = _ema(closes[-slow:], slow)
    close = closes[-1]
    if fast_ema is None or slow_ema is None or close <= 0.0:
        return 0.0

    sign = 0
    if fast_ema > slow_ema and slow_ema < close < fast_ema:
        sign = 1
    elif fast_ema < slow_ema and fast_ema < close < slow_ema:
        sign = -1
    if sign == 0:
        return 0.0

    trend_pct = abs((fast_ema - slow_ema) / close) * 100.0
    pullback_score = min((abs((fast_ema - close) / close) * 100.0) / 0.75, 1.0)
    return float(sign) * min(trend_pct, 3.0) * pullback_score


def _daily_return_from_rows(rows: Sequence[Mapping[str, Any]], *, index: int, lookback: int) -> Optional[float]:
    if index < lookback:
        return None
    start_close = _safe_float(rows[index - lookback].get("close"))
    end_close = _safe_float(rows[index].get("close"))
    if start_close is None or start_close <= 0.0 or end_close is None or end_close <= 0.0:
        return None
    return (end_close / start_close) - 1.0


def _relative_momentum_raw(
    *,
    ticker: str,
    rows: Sequence[Mapping[str, Any]],
    index: int,
    lookback: int,
    peer_daily_rows: Optional[Mapping[str, Sequence[Mapping[str, Any]]]],
) -> Tuple[float, int]:
    bucket_members = bucket_members_for_ticker(ticker)
    peer_map = dict(peer_daily_rows or {})
    scores: List[Tuple[str, float]] = []
    for member in bucket_members:
        member_rows = daily_row_lookup(peer_map.get(member) or rows if member == ticker else peer_map.get(member) or [])
        if not member_rows:
            continue
        member_index = _row_index_for_day(member_rows, rows[index]["day"])
        if member_index is None:
            continue
        trailing_return = _daily_return_from_rows(member_rows, index=member_index, lookback=lookback)
        if trailing_return is None:
            continue
        scores.append((member, trailing_return))
    if not scores:
        return 0.0, 0
    scores.sort(key=lambda item: item[1])
    rank_lookup = {member: rank for rank, (member, _) in enumerate(scores)}
    rank = rank_lookup.get(ticker)
    if rank is None:
        return 0.0, len(scores)
    if len(scores) == 1:
        return 0.0, 1
    percentile = float(rank) / float(len(scores) - 1)
    centered = (percentile * 2.0) - 1.0
    return centered * 20.0, len(scores)


def _asset_trend_raw(
    *,
    ticker: str,
    rows: Sequence[Mapping[str, Any]],
    index: int,
    lookback: int,
    peer_daily_rows: Optional[Mapping[str, Sequence[Mapping[str, Any]]]],
) -> Tuple[float, int]:
    target_day = rows[index]["day"]
    bucket_members = bucket_members_for_ticker(ticker)
    peer_map = dict(peer_daily_rows or {})
    bucket_closes: List[Tuple[str, float, float]] = []
    for member in bucket_members:
        member_rows = daily_row_lookup(peer_map.get(member) or rows if member == ticker else peer_map.get(member) or [])
        if not member_rows:
            continue
        member_index = _row_index_for_day(member_rows, target_day)
        if member_index is None or member_index < lookback:
            continue
        current_close = _safe_float(member_rows[member_index].get("close"))
        past_close = _safe_float(member_rows[member_index - lookback].get("close"))
        if current_close is None or current_close <= 0.0 or past_close is None or past_close <= 0.0:
            continue
        bucket_closes.append((member, past_close, current_close))
    if not bucket_closes:
        return 0.0, 0
    start_avg = sum(item[1] for item in bucket_closes) / float(len(bucket_closes))
    end_avg = sum(item[2] for item in bucket_closes) / float(len(bucket_closes))
    if start_avg <= 0.0 or end_avg <= 0.0:
        return 0.0, len(bucket_closes)
    trend_return = (end_avg / start_avg) - 1.0
    member_returns = [abs((item[2] / item[1]) - 1.0) for item in bucket_closes if item[1] > 0.0]
    dispersion = median(member_returns) if member_returns else 0.01
    scaled = (trend_return / max(dispersion, 0.005)) * 5.0
    return _cap_value(scaled, 20.0), len(bucket_closes)


def _realized_vol_annualized(rows: Sequence[Mapping[str, Any]], *, index: int, lookback: int) -> Optional[float]:
    if index < 1:
        return None
    start = max(index - lookback + 1, 1)
    returns: List[float] = []
    for idx in range(start, index + 1):
        current_close = _safe_float(rows[idx].get("close"))
        prev_close = _safe_float(rows[idx - 1].get("close"))
        if current_close is None or current_close <= 0.0 or prev_close is None or prev_close <= 0.0:
            continue
        returns.append((current_close / prev_close) - 1.0)
    if len(returns) < 2:
        return None
    mean_return = sum(returns) / float(len(returns))
    variance = sum((item - mean_return) ** 2 for item in returns) / float(len(returns))
    return sqrt(max(variance, 0.0)) * sqrt(252.0)


def _vol_percentile(rows: Sequence[Mapping[str, Any]], *, index: int, lookback: int) -> Optional[float]:
    current = _realized_vol_annualized(rows, index=index, lookback=20)
    if current is None:
        return None
    values: List[float] = []
    start = max(index - lookback + 1, 20)
    for idx in range(start, index + 1):
        value = _realized_vol_annualized(rows, index=idx, lookback=20)
        if value is not None:
            values.append(value)
    if not values:
        return None
    below = sum(1 for value in values if value <= current)
    return (float(below) / float(len(values))) * 100.0
