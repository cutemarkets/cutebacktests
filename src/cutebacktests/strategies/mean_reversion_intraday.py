from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import numpy as np


_ET_ZONE = ZoneInfo("America/New_York")


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


def _parse_hhmm_list(value: str, default_value: str) -> List[time]:
    text = (value or "").strip() or default_value
    parts = [part.strip() for part in text.replace(";", ",").split(",") if part.strip()]
    if not parts:
        parts = [default_value]
    return [_parse_hhmm(part, default_value) for part in parts]


def _default_entry_start(opening_range_minutes: int) -> str:
    effective = max(int(opening_range_minutes), 1)
    minute_total = (9 * 60) + 30 + effective
    hour = minute_total // 60
    minute = minute_total % 60
    return f"{hour:02d}:{minute:02d}"


@lru_cache(maxsize=262144)
def _to_et_time(ts: datetime) -> time:
    if ts.tzinfo is None:
        aware = ts.replace(tzinfo=timezone.utc)
    else:
        aware = ts.astimezone(timezone.utc)
    return aware.astimezone(_ET_ZONE).time()


def _is_in_macro_release_block(bar_time: time, release_times: List[time], block_minutes: int) -> bool:
    effective_block = max(int(block_minutes), 0)
    if effective_block <= 0 or not release_times:
        return False
    bar_minute = (bar_time.hour * 60) + bar_time.minute
    for release_time in release_times:
        release_minute = (release_time.hour * 60) + release_time.minute
        if release_minute <= bar_minute < (release_minute + effective_block):
            return True
    return False


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _inc_reason(counter: Dict[str, int], reason: str, amount: int = 1) -> None:
    key = str(reason or "unknown").strip() or "unknown"
    counter[key] = int(counter.get(key) or 0) + max(int(amount), 1)


def _session_bar_arrays(session_bars: List[Dict[str, Any]]) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    size = len(session_bars)
    opens = np.zeros(size, dtype=float)
    highs = np.zeros(size, dtype=float)
    lows = np.zeros(size, dtype=float)
    closes = np.zeros(size, dtype=float)
    volumes = np.zeros(size, dtype=float)
    for idx, bar in enumerate(session_bars):
        opens[idx] = float(bar.get("open") or 0.0)
        highs[idx] = float(bar.get("high") or 0.0)
        lows[idx] = float(bar.get("low") or 0.0)
        closes[idx] = float(bar.get("close") or 0.0)
        volumes[idx] = float(bar.get("volume") or 0.0)
    return opens, highs, lows, closes, volumes


def _ema_array(values: np.ndarray, period: int) -> np.ndarray:
    values_array = np.asarray(values, dtype=float)
    if values_array.size <= 0:
        return np.empty(0, dtype=float)
    effective_period = max(int(period), 1)
    alpha = 2.0 / (effective_period + 1.0)
    out = np.empty(values_array.size, dtype=float)
    ema = float(values_array[0])
    for idx, value in enumerate(values_array):
        ema = (alpha * float(value)) + ((1.0 - alpha) * ema)
        out[idx] = ema
    return out


def _ema_series(values: List[float], period: int) -> List[float]:
    return _ema_array(np.asarray(values, dtype=float), period).tolist()


def _rolling_std_array(values: np.ndarray, window: int) -> np.ndarray:
    values_array = np.asarray(values, dtype=float)
    out = np.full(values_array.size, np.nan, dtype=float)
    if values_array.size <= 0:
        return out

    effective_window = max(int(window), 2)
    if values_array.size < effective_window:
        return out

    cumulative = np.concatenate(([0.0], np.cumsum(values_array, dtype=float)))
    cumulative_sq = np.concatenate(([0.0], np.cumsum(values_array * values_array, dtype=float)))
    window_sums = cumulative[effective_window:] - cumulative[:-effective_window]
    window_sums_sq = cumulative_sq[effective_window:] - cumulative_sq[:-effective_window]
    means = window_sums / float(effective_window)
    variances = np.maximum((window_sums_sq / float(effective_window)) - (means * means), 0.0)
    out[effective_window - 1 :] = np.sqrt(variances)
    return out


def _rolling_std_series(values: List[float], window: int) -> List[Optional[float]]:
    out = _rolling_std_array(np.asarray(values, dtype=float), window)
    return [None if np.isnan(value) else float(value) for value in out]


def _forward_fill(values: np.ndarray) -> np.ndarray:
    values_array = np.asarray(values, dtype=float)
    if values_array.size <= 0:
        return np.empty(0, dtype=float)
    valid_idx = np.where(np.isfinite(values_array), np.arange(values_array.size), -1)
    np.maximum.accumulate(valid_idx, out=valid_idx)
    out = np.zeros(values_array.size, dtype=float)
    mask = valid_idx >= 0
    out[mask] = values_array[valid_idx[mask]]
    return out


def _running_vwap_array(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, volumes: np.ndarray) -> np.ndarray:
    highs_array = np.asarray(highs, dtype=float)
    lows_array = np.asarray(lows, dtype=float)
    closes_array = np.asarray(closes, dtype=float)
    volumes_array = np.asarray(volumes, dtype=float)
    if closes_array.size <= 0:
        return np.empty(0, dtype=float)

    valid = (highs_array > 0.0) & (lows_array > 0.0) & (closes_array > 0.0) & (volumes_array > 0.0)
    typical_price = (highs_array + lows_array + closes_array) / 3.0
    cumulative_notional = np.cumsum(np.where(valid, typical_price * volumes_array, 0.0), dtype=float)
    cumulative_volume = np.cumsum(np.where(valid, volumes_array, 0.0), dtype=float)

    vwap = np.full(closes_array.size, np.nan, dtype=float)
    positive_volume = cumulative_volume > 0.0
    vwap[positive_volume] = cumulative_notional[positive_volume] / cumulative_volume[positive_volume]

    out = np.full(closes_array.size, np.nan, dtype=float)
    out[valid] = vwap[valid]

    close_fallback = (~valid) & (closes_array > 0.0)
    out[close_fallback] = closes_array[close_fallback]
    return _forward_fill(out)


def _running_vwap_series(session_bars: List[Dict[str, Any]]) -> List[float]:
    _, highs, lows, closes, volumes = _session_bar_arrays(session_bars)
    return _running_vwap_array(highs, lows, closes, volumes).tolist()


def _bar_body_fraction(*, open_price: float, high_price: float, low_price: float, close_price: float) -> float:
    bar_range = high_price - low_price
    if bar_range <= 0.0:
        return 0.0
    return abs(close_price - open_price) / bar_range


def _reversal_wick_fraction(
    *,
    direction: int,
    open_price: float,
    high_price: float,
    low_price: float,
    close_price: float,
) -> float:
    bar_range = high_price - low_price
    if bar_range <= 0.0:
        return 0.0
    if direction > 0:
        wick = max(min(open_price, close_price) - low_price, 0.0)
    else:
        wick = max(high_price - max(open_price, close_price), 0.0)
    return wick / bar_range


def find_mr_vwap_exhaustion_setup_with_audit(
    session_bars: List[Dict[str, Any]],
    cfg: Any,
    relative_opening_volume: Optional[float],
    atr_value: Optional[float],
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    audit: Dict[str, Any] = {
        "strategy_variant": "mr_vwap_exhaustion_v1",
        "opportunities_before_filters": 0,
        "opportunities_after_filters": 0,
        "rejections": {},
    }
    opening_range_count = max(int(getattr(cfg, "opening_range_minutes", 5)), 1)
    zscore_window = max(int(getattr(cfg, "mr_zscore_window", 20) or 20), 5)
    if len(session_bars) < (opening_range_count + zscore_window + 2):
        _inc_reason(audit["rejections"], "insufficient_bars")
        return None, audit

    opens, highs, lows, closes, volumes = _session_bar_arrays(session_bars)
    opening_slice = slice(0, opening_range_count)
    orb_high = float(np.max(highs[opening_slice]))
    orb_low = float(np.min(lows[opening_slice]))
    orb_open = float(opens[0])
    orb_close = float(closes[opening_range_count - 1])
    if orb_high <= 0 or orb_low <= 0 or orb_high <= orb_low:
        _inc_reason(audit["rejections"], "invalid_opening_range")
        return None, audit

    orb_width = orb_high - orb_low
    orb_width_pct = orb_width / max(orb_open, 1.0)
    if bool(getattr(cfg, "require_or_width_filter", False)):
        min_width = max(float(getattr(cfg, "opening_range_min_width_pct", 0.0)), 0.0)
        max_width = max(float(getattr(cfg, "opening_range_max_width_pct", 1.0)), min_width)
        if orb_width_pct < min_width or orb_width_pct > max_width:
            _inc_reason(audit["rejections"], "orb_width_filter")
            return None, audit

    opening_bar_direction = 0
    if orb_close > orb_open:
        opening_bar_direction = 1
    elif orb_close < orb_open:
        opening_bar_direction = -1

    ema_fast = _ema_array(closes, int(getattr(cfg, "trend_ema_fast", 20)))
    ema_slow = _ema_array(closes, int(getattr(cfg, "trend_ema_slow", 50)))
    vwap_series = _running_vwap_array(highs, lows, closes, volumes)
    residuals = closes - vwap_series
    residual_std = _rolling_std_array(residuals, zscore_window)
    zscores = np.full(residuals.size, np.nan, dtype=float)
    valid_sigma = residual_std > 0.0
    zscores[valid_sigma] = residuals[valid_sigma] / residual_std[valid_sigma]

    entry_start = _parse_hhmm(str(getattr(cfg, "entry_start_time", "")), _default_entry_start(opening_range_count))
    entry_cutoff = _parse_hhmm(str(getattr(cfg, "entry_cutoff_time", "")), "12:00")
    macro_release_times = (
        _parse_hhmm_list(str(getattr(cfg, "macro_release_times_et", "")), "10:00")
        if bool(getattr(cfg, "require_macro_release_filter", False))
        else []
    )
    macro_block_minutes = max(int(getattr(cfg, "macro_post_release_block_minutes", 0)), 0)

    stop_buffer_or_mult = max(float(getattr(cfg, "mr_stop_buffer_or_mult", 0.0)), 0.0)
    take_profit_mode = str(getattr(cfg, "mr_take_profit_mode", "zscore") or "zscore").strip().lower()
    take_profit_rr = max(float(getattr(cfg, "mr_take_profit_rr", 1.0)), 0.0)
    require_reversal = bool(getattr(cfg, "mr_require_reversal_candle", True))
    z_entry = max(float(getattr(cfg, "mr_zscore_entry", 1.6)), 0.1)
    z_reentry = min(max(float(getattr(cfg, "mr_zscore_reentry", 0.8)), 0.0), z_entry)
    z_stop = max(float(getattr(cfg, "mr_zscore_stop", 2.4)), z_entry)
    z_target = max(float(getattr(cfg, "mr_zscore_target", 0.25)), 0.0)
    sigma_min_pct = max(float(getattr(cfg, "mr_sigma_min_pct", 0.0)), 0.0)
    sigma_max_pct = max(float(getattr(cfg, "mr_sigma_max_pct", 1.0)), sigma_min_pct)
    vwap_slope_lookback = max(int(getattr(cfg, "mr_vwap_slope_lookback", 3)), 1)
    vwap_slope_max_pct = max(float(getattr(cfg, "mr_vwap_slope_max_pct", 1.0)), 0.0)
    mr_adaptive_enabled = bool(getattr(cfg, "mr_adaptive_enabled", False))
    mr_adaptive_entry_min = max(float(getattr(cfg, "mr_adaptive_entry_min", z_entry)), 0.1)
    mr_adaptive_entry_max = max(float(getattr(cfg, "mr_adaptive_entry_max", z_entry)), mr_adaptive_entry_min)
    mr_adaptive_stop_min = max(float(getattr(cfg, "mr_adaptive_stop_min", z_stop)), mr_adaptive_entry_min)
    mr_adaptive_stop_max = max(float(getattr(cfg, "mr_adaptive_stop_max", z_stop)), mr_adaptive_stop_min)
    mr_adaptive_trend_weight = max(float(getattr(cfg, "mr_adaptive_trend_weight", 0.65)), 0.0)
    mr_adaptive_vol_weight = max(float(getattr(cfg, "mr_adaptive_vol_weight", 0.35)), 0.0)
    session_extension_min_or_frac = max(float(getattr(cfg, "mr_session_extension_min_or_frac", 0.0)), 0.0)
    reversal_body_min_frac = max(float(getattr(cfg, "mr_reversal_body_min_frac", 0.0)), 0.0)
    reversal_wick_min_frac = max(float(getattr(cfg, "mr_reversal_wick_min_frac", 0.0)), 0.0)
    trend_ema_spread_max_pct = max(float(getattr(cfg, "mr_trend_ema_spread_max_pct", 1.0)), 0.0)
    volume_climax_multiple_min = max(float(getattr(cfg, "mr_volume_climax_multiple_min", 0.0)), 0.0)
    trend_day_max_move_pct = max(float(getattr(cfg, "mr_trend_day_max_move_pct", 1.0)), 0.0)
    time_to_work_bars = max(int(getattr(cfg, "mr_time_to_work_bars", 0)), 0)
    time_to_work_min_rr = max(float(getattr(cfg, "mr_time_to_work_min_rr", 0.0)), 0.0)
    target_stretch_frac = max(float(getattr(cfg, "mr_target_stretch_frac", 0.0)), 0.0)
    volume_ma_window = max(int(getattr(cfg, "volume_ma_window", 20)), 1)
    volume_prefix = np.concatenate(([0.0], np.cumsum(volumes, dtype=float)))

    if take_profit_mode not in {"vwap", "rr", "none", "zscore"}:
        take_profit_mode = "zscore"

    for idx in range(max(opening_range_count, 1), len(session_bars) - 1):
        bar = session_bars[idx]
        bar_time = _to_et_time(bar["ts"])
        if bar_time < entry_start or bar_time > entry_cutoff:
            continue

        if bool(getattr(cfg, "require_macro_release_filter", False)) and _is_in_macro_release_block(
            bar_time,
            macro_release_times,
            macro_block_minutes,
        ):
            _inc_reason(audit["rejections"], "macro_release_block")
            continue

        open_price = float(opens[idx])
        high_price = float(highs[idx])
        low_price = float(lows[idx])
        close_price = float(closes[idx])
        prev_low = float(lows[idx - 1])
        prev_high = float(highs[idx - 1])
        if open_price <= 0 or high_price <= 0 or low_price <= 0 or close_price <= 0 or prev_low <= 0 or prev_high <= 0:
            continue

        if bool(getattr(cfg, "require_relative_volume", False)):
            relative_volume_min = float(getattr(cfg, "relative_volume_min", 1.0))
            if relative_opening_volume is None or relative_opening_volume < relative_volume_min:
                _inc_reason(audit["rejections"], "relative_volume_filter")
                continue

        if bool(getattr(cfg, "require_atr_filter", False)):
            atr_min = float(getattr(cfg, "atr_min", 0.0))
            if atr_value is None or atr_value < atr_min:
                _inc_reason(audit["rejections"], "atr_filter")
                continue

        volume_ratio = 1.0
        if idx >= volume_ma_window:
            avg_volume = float(volume_prefix[idx] - volume_prefix[idx - volume_ma_window]) / float(volume_ma_window)
            if avg_volume > 0:
                volume_ratio = float(volumes[idx]) / avg_volume
        if volume_climax_multiple_min > 0 and volume_ratio < volume_climax_multiple_min:
            _inc_reason(audit["rejections"], "mr_volume_climax_filter")
            continue

        vwap_value = float(vwap_series[idx])
        sigma = float(residual_std[idx])
        z_now = float(zscores[idx])
        z_prev = float(zscores[idx - 1]) if idx > 0 else float("nan")
        if vwap_value <= 0 or np.isnan(sigma) or sigma <= 0.0 or np.isnan(z_now) or np.isnan(z_prev):
            _inc_reason(audit["rejections"], "mr_zscore_warmup")
            continue

        sigma_pct = sigma / max(close_price, 1.0)
        if sigma_pct < sigma_min_pct or sigma_pct > sigma_max_pct:
            _inc_reason(audit["rejections"], "mr_sigma_regime_filter")
            continue

        vwap_slope_abs_pct = 0.0
        if idx >= vwap_slope_lookback:
            prior_vwap = float(vwap_series[idx - vwap_slope_lookback])
            vwap_slope_abs_pct = abs(vwap_value - prior_vwap) / max(close_price, 1.0)
            if vwap_slope_abs_pct > vwap_slope_max_pct:
                _inc_reason(audit["rejections"], "mr_vwap_slope_filter")
                continue

        effective_z_entry = z_entry
        effective_z_reentry = z_reentry
        effective_z_stop = z_stop
        if mr_adaptive_enabled:
            trend_pressure = 0.0
            if vwap_slope_max_pct > 0:
                trend_pressure = min(max(vwap_slope_abs_pct / vwap_slope_max_pct, 0.0), 1.0)
            vol_range = max(sigma_max_pct - sigma_min_pct, 1e-9)
            vol_pressure = min(max((sigma_pct - sigma_min_pct) / vol_range, 0.0), 1.0)
            adaptive_total_weight = max(mr_adaptive_trend_weight + mr_adaptive_vol_weight, 1e-9)
            adaptive_pressure = (
                (trend_pressure * mr_adaptive_trend_weight)
                + (vol_pressure * mr_adaptive_vol_weight)
            ) / adaptive_total_weight
            effective_z_entry = mr_adaptive_entry_min + (adaptive_pressure * (mr_adaptive_entry_max - mr_adaptive_entry_min))
            effective_z_entry = min(max(effective_z_entry, mr_adaptive_entry_min), mr_adaptive_entry_max)
            effective_z_stop = mr_adaptive_stop_min + (adaptive_pressure * (mr_adaptive_stop_max - mr_adaptive_stop_min))
            effective_z_stop = min(max(effective_z_stop, mr_adaptive_stop_min), mr_adaptive_stop_max)
            effective_z_stop = max(effective_z_stop, effective_z_entry)
            reentry_ratio = (z_reentry / z_entry) if z_entry > 0 else 0.0
            effective_z_reentry = min(max(effective_z_entry * reentry_ratio, 0.0), effective_z_entry)

        ema_spread_pct = abs(float(ema_fast[idx]) - float(ema_slow[idx])) / max(close_price, 1.0)
        if trend_ema_spread_max_pct > 0 and ema_spread_pct > trend_ema_spread_max_pct:
            _inc_reason(audit["rejections"], "mr_trend_spread_filter")
            continue

        lower_threshold = vwap_value - (effective_z_entry * sigma)
        upper_threshold = vwap_value + (effective_z_entry * sigma)
        lower_reclaim = vwap_value - (effective_z_reentry * sigma)
        upper_reclaim = vwap_value + (effective_z_reentry * sigma)
        extension_buffer = orb_width * session_extension_min_or_frac

        bar_body_frac = _bar_body_fraction(
            open_price=open_price,
            high_price=high_price,
            low_price=low_price,
            close_price=close_price,
        )
        lower_wick_frac = _reversal_wick_fraction(
            direction=1,
            open_price=open_price,
            high_price=high_price,
            low_price=low_price,
            close_price=close_price,
        )
        upper_wick_frac = _reversal_wick_fraction(
            direction=-1,
            open_price=open_price,
            high_price=high_price,
            low_price=low_price,
            close_price=close_price,
        )

        long_reversal_ok = (
            (close_price > open_price and bar_body_frac >= reversal_body_min_frac)
            or (reversal_wick_min_frac > 0.0 and lower_wick_frac >= reversal_wick_min_frac and close_price >= open_price)
        )
        short_reversal_ok = (
            (close_price < open_price and bar_body_frac >= reversal_body_min_frac)
            or (reversal_wick_min_frac > 0.0 and upper_wick_frac >= reversal_wick_min_frac and close_price <= open_price)
        )

        long_signal = (
            low_price <= lower_threshold
            and close_price >= lower_reclaim
            and z_now > z_prev
            and (session_extension_min_or_frac <= 0.0 or low_price <= (orb_low - extension_buffer))
            and ((not require_reversal) or long_reversal_ok)
        )
        short_signal = (
            high_price >= upper_threshold
            and close_price <= upper_reclaim
            and z_now < z_prev
            and (session_extension_min_or_frac <= 0.0 or high_price >= (orb_high + extension_buffer))
            and ((not require_reversal) or short_reversal_ok)
        )

        raw_directions: List[int] = []
        if long_signal:
            raw_directions.append(1)
        if short_signal:
            raw_directions.append(-1)
        if not raw_directions:
            continue

        audit["opportunities_before_filters"] = int(audit.get("opportunities_before_filters") or 0) + len(raw_directions)

        candidate_directions: List[int] = []
        for direction in raw_directions:
            if direction > 0 and bool(getattr(cfg, "allow_long", True)):
                candidate_directions.append(direction)
            elif direction < 0 and bool(getattr(cfg, "allow_short", True)):
                candidate_directions.append(direction)
            else:
                _inc_reason(audit["rejections"], "direction_not_allowed")
        if not candidate_directions:
            continue

        if bool(getattr(cfg, "use_opening_bar_direction", False)):
            filtered = [direction for direction in candidate_directions if direction == opening_bar_direction]
            dropped = len(candidate_directions) - len(filtered)
            if dropped > 0:
                _inc_reason(audit["rejections"], "opening_bar_direction_mismatch", dropped)
            candidate_directions = filtered
            if not candidate_directions:
                continue

        direction = candidate_directions[0]
        if len(candidate_directions) > 1:
            _inc_reason(audit["rejections"], "secondary_direction_dropped", len(candidate_directions) - 1)

        trend_against_move = (-direction) * ((close_price / max(orb_open, 1.0)) - 1.0)
        if trend_day_max_move_pct > 0 and trend_against_move > trend_day_max_move_pct:
            _inc_reason(audit["rejections"], "mr_trend_day_veto")
            continue

        entry_idx = idx + 1
        entry_bar = session_bars[entry_idx]
        entry_price = float(opens[entry_idx])
        if entry_price <= 0:
            _inc_reason(audit["rejections"], "invalid_entry_price")
            continue

        if direction > 0:
            stop_core = min(low_price, prev_low, vwap_value - (effective_z_stop * sigma))
            stop_price = stop_core - (orb_width * stop_buffer_or_mult)
        else:
            stop_core = max(high_price, prev_high, vwap_value + (effective_z_stop * sigma))
            stop_price = stop_core + (orb_width * stop_buffer_or_mult)
        if direction > 0 and stop_price >= entry_price:
            _inc_reason(audit["rejections"], "invalid_stop")
            continue
        if direction < 0 and stop_price <= entry_price:
            _inc_reason(audit["rejections"], "invalid_stop")
            continue

        risk_per_share = abs(entry_price - stop_price)
        if risk_per_share <= 0:
            _inc_reason(audit["rejections"], "invalid_stop")
            continue

        if take_profit_mode == "none":
            target_underlying: Optional[float] = None
        elif take_profit_mode == "rr":
            target_underlying = (
                entry_price + (risk_per_share * take_profit_rr)
                if direction > 0
                else entry_price - (risk_per_share * take_profit_rr)
            )
        elif take_profit_mode == "zscore":
            target_underlying = (
                vwap_value + (z_target * sigma)
                if direction > 0
                else vwap_value - (z_target * sigma)
            )
        else:
            target_underlying = vwap_value

        if target_underlying is not None:
            if direction > 0 and target_underlying <= entry_price:
                target_underlying = entry_price + max(risk_per_share * 0.4, sigma * 0.5, orb_width * 0.2)
            elif direction < 0 and target_underlying >= entry_price:
                target_underlying = entry_price - max(risk_per_share * 0.4, sigma * 0.5, orb_width * 0.2)
            if target_stretch_frac > 0.0:
                stretch_extreme = low_price if direction > 0 else high_price
                stretch_distance = abs(vwap_value - stretch_extreme)
                normalized_distance = max(risk_per_share * 0.5, stretch_distance * target_stretch_frac)
                normalized_target = (
                    entry_price + normalized_distance
                    if direction > 0
                    else entry_price - normalized_distance
                )
                if direction > 0:
                    target_underlying = min(float(target_underlying), float(normalized_target))
                else:
                    target_underlying = max(float(target_underlying), float(normalized_target))

        audit["opportunities_after_filters"] = int(audit.get("opportunities_after_filters") or 0) + 1
        return {
            "direction": direction,
            "signal_idx": idx,
            "signal_ts": bar["ts"],
            "entry_idx": entry_idx,
            "entry_ts": entry_bar["ts"],
            "entry_underlying": entry_price,
            "stop_underlying": stop_price,
            "orb_high": orb_high,
            "orb_low": orb_low,
            "opening_bar_open": orb_open,
            "opening_bar_close": orb_close,
            "opening_bar_direction": opening_bar_direction,
            "trend_ema_fast": float(ema_fast[idx]),
            "trend_ema_slow": float(ema_slow[idx]),
            "volume_ratio": volume_ratio,
            "relative_opening_volume": relative_opening_volume,
            "atr_value": atr_value,
            "fvg_gap": 0.0,
            "opening_range_minutes": opening_range_count,
            "orb_width_pct": orb_width_pct,
            "strategy_variant": "mr_vwap_exhaustion_v1",
            "mr_vwap_at_signal": vwap_value,
            "mr_sigma_at_signal": float(sigma),
            "mr_zscore_at_signal": float(z_now),
            "mr_take_profit_mode": take_profit_mode,
            "mr_target_underlying": target_underlying,
            "mr_zscore_entry": effective_z_entry,
            "mr_zscore_reentry": effective_z_reentry,
            "mr_zscore_stop": effective_z_stop,
            "mr_zscore_target": z_target,
            "mr_sigma_pct_at_signal": sigma_pct,
            "mr_adaptive_enabled": mr_adaptive_enabled,
            "mr_body_frac_at_signal": bar_body_frac,
            "mr_reversal_wick_frac_at_signal": lower_wick_frac if direction > 0 else upper_wick_frac,
            "mr_session_extension_min_or_frac": session_extension_min_or_frac,
            "mr_time_to_work_bars": time_to_work_bars,
            "mr_time_to_work_min_rr": time_to_work_min_rr,
            "mr_target_stretch_frac": target_stretch_frac,
        }, audit

    if int(audit.get("opportunities_before_filters") or 0) == 0:
        _inc_reason(audit["rejections"], "mr_exhaustion_no_signal")
    return None, audit


def find_mr_vwap_zscore_setup_with_audit(
    session_bars: List[Dict[str, Any]],
    cfg: Any,
    relative_opening_volume: Optional[float],
    atr_value: Optional[float],
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    audit: Dict[str, Any] = {
        "strategy_variant": "mr_vwap_zscore_v2",
        "opportunities_before_filters": 0,
        "opportunities_after_filters": 0,
        "rejections": {},
    }
    opening_range_count = max(int(getattr(cfg, "opening_range_minutes", 5)), 1)
    if len(session_bars) < (opening_range_count + 5):
        _inc_reason(audit["rejections"], "insufficient_bars")
        return None, audit

    opens, highs, lows, closes, volumes = _session_bar_arrays(session_bars)
    opening_slice = slice(0, opening_range_count)
    orb_high = float(np.max(highs[opening_slice]))
    orb_low = float(np.min(lows[opening_slice]))
    orb_open = float(opens[0])
    orb_close = float(closes[opening_range_count - 1])
    if orb_high <= 0 or orb_low <= 0 or orb_high <= orb_low:
        _inc_reason(audit["rejections"], "invalid_opening_range")
        return None, audit

    orb_width = orb_high - orb_low
    orb_width_pct = orb_width / max(orb_open, 1.0)
    if bool(getattr(cfg, "require_or_width_filter", False)):
        min_width = max(float(getattr(cfg, "opening_range_min_width_pct", 0.0)), 0.0)
        max_width = max(float(getattr(cfg, "opening_range_max_width_pct", 1.0)), min_width)
        if orb_width_pct < min_width or orb_width_pct > max_width:
            _inc_reason(audit["rejections"], "orb_width_filter")
            return None, audit

    opening_bar_direction = 0
    if orb_close > orb_open:
        opening_bar_direction = 1
    elif orb_close < orb_open:
        opening_bar_direction = -1

    ema_fast = _ema_array(closes, int(getattr(cfg, "trend_ema_fast", 20)))
    ema_slow = _ema_array(closes, int(getattr(cfg, "trend_ema_slow", 50)))
    vwap_series = _running_vwap_array(highs, lows, closes, volumes)
    residuals = closes - vwap_series

    zscore_window = max(int(getattr(cfg, "mr_zscore_window", 20) or 20), 5)
    residual_std = _rolling_std_array(residuals, zscore_window)
    zscores = np.full(residuals.size, np.nan, dtype=float)
    valid_sigma = residual_std > 0.0
    zscores[valid_sigma] = residuals[valid_sigma] / residual_std[valid_sigma]

    entry_start = _parse_hhmm(str(getattr(cfg, "entry_start_time", "")), _default_entry_start(opening_range_count))
    entry_cutoff = _parse_hhmm(str(getattr(cfg, "entry_cutoff_time", "")), "12:00")
    macro_release_times = (
        _parse_hhmm_list(str(getattr(cfg, "macro_release_times_et", "")), "10:00")
        if bool(getattr(cfg, "require_macro_release_filter", False))
        else []
    )
    macro_block_minutes = max(int(getattr(cfg, "macro_post_release_block_minutes", 0)), 0)

    stop_buffer_or_mult = max(float(getattr(cfg, "mr_stop_buffer_or_mult", 0.0)), 0.0)
    take_profit_mode = str(getattr(cfg, "mr_take_profit_mode", "zscore") or "zscore").strip().lower()
    take_profit_rr = max(float(getattr(cfg, "mr_take_profit_rr", 1.0)), 0.0)
    require_reversal = bool(getattr(cfg, "mr_require_reversal_candle", True))
    z_entry = max(float(getattr(cfg, "mr_zscore_entry", 1.6)), 0.1)
    z_reentry = min(max(float(getattr(cfg, "mr_zscore_reentry", 0.8)), 0.0), z_entry)
    z_stop = max(float(getattr(cfg, "mr_zscore_stop", 2.4)), z_entry)
    z_target = max(float(getattr(cfg, "mr_zscore_target", 0.25)), 0.0)
    sigma_min_pct = max(float(getattr(cfg, "mr_sigma_min_pct", 0.0)), 0.0)
    sigma_max_pct = max(float(getattr(cfg, "mr_sigma_max_pct", 1.0)), sigma_min_pct)
    vwap_slope_lookback = max(int(getattr(cfg, "mr_vwap_slope_lookback", 3)), 1)
    vwap_slope_max_pct = max(float(getattr(cfg, "mr_vwap_slope_max_pct", 1.0)), 0.0)
    mr_adaptive_enabled = bool(getattr(cfg, "mr_adaptive_enabled", False))
    mr_adaptive_entry_min = max(float(getattr(cfg, "mr_adaptive_entry_min", z_entry)), 0.1)
    mr_adaptive_entry_max = max(float(getattr(cfg, "mr_adaptive_entry_max", z_entry)), mr_adaptive_entry_min)
    mr_adaptive_stop_min = max(float(getattr(cfg, "mr_adaptive_stop_min", z_stop)), mr_adaptive_entry_min)
    mr_adaptive_stop_max = max(float(getattr(cfg, "mr_adaptive_stop_max", z_stop)), mr_adaptive_stop_min)
    mr_adaptive_trend_weight = max(float(getattr(cfg, "mr_adaptive_trend_weight", 0.65)), 0.0)
    mr_adaptive_vol_weight = max(float(getattr(cfg, "mr_adaptive_vol_weight", 0.35)), 0.0)
    volume_ma_window = max(int(getattr(cfg, "volume_ma_window", 20)), 1)
    volume_prefix = np.concatenate(([0.0], np.cumsum(volumes, dtype=float)))

    if take_profit_mode not in {"vwap", "rr", "none", "zscore"}:
        take_profit_mode = "zscore"

    for idx in range(max(opening_range_count, 1), len(session_bars) - 1):
        bar = session_bars[idx]
        bar_time = _to_et_time(bar["ts"])
        if bar_time < entry_start or bar_time > entry_cutoff:
            continue

        if bool(getattr(cfg, "require_macro_release_filter", False)) and _is_in_macro_release_block(
            bar_time,
            macro_release_times,
            macro_block_minutes,
        ):
            _inc_reason(audit["rejections"], "macro_release_block")
            continue

        open_price = float(opens[idx])
        high_price = float(highs[idx])
        low_price = float(lows[idx])
        close_price = float(closes[idx])
        prev_open = float(opens[idx - 1])
        prev_close = float(closes[idx - 1])
        prev_low = float(lows[idx - 1])
        prev_high = float(highs[idx - 1])
        if (
            open_price <= 0
            or high_price <= 0
            or low_price <= 0
            or close_price <= 0
            or prev_open <= 0
            or prev_close <= 0
            or prev_low <= 0
            or prev_high <= 0
        ):
            continue

        if bool(getattr(cfg, "require_relative_volume", False)):
            relative_volume_min = float(getattr(cfg, "relative_volume_min", 1.0))
            if relative_opening_volume is None or relative_opening_volume < relative_volume_min:
                _inc_reason(audit["rejections"], "relative_volume_filter")
                continue

        if bool(getattr(cfg, "require_atr_filter", False)):
            atr_min = float(getattr(cfg, "atr_min", 0.0))
            if atr_value is None or atr_value < atr_min:
                _inc_reason(audit["rejections"], "atr_filter")
                continue

        if bool(getattr(cfg, "require_volume_spike", False)):
            if idx < volume_ma_window:
                _inc_reason(audit["rejections"], "volume_ma_warmup")
                continue
            avg_volume = float(volume_prefix[idx] - volume_prefix[idx - volume_ma_window]) / float(volume_ma_window)
            if avg_volume <= 0:
                _inc_reason(audit["rejections"], "volume_ma_invalid")
                continue
            volume_ratio = float(volumes[idx]) / avg_volume
            if volume_ratio < float(getattr(cfg, "volume_spike_multiple", 1.2)):
                _inc_reason(audit["rejections"], "volume_spike_filter")
                continue
        else:
            volume_ratio = 1.0

        vwap_value = float(vwap_series[idx])
        if vwap_value <= 0:
            _inc_reason(audit["rejections"], "invalid_vwap")
            continue

        sigma = float(residual_std[idx])
        z_now = float(zscores[idx])
        z_prev = float(zscores[idx - 1]) if idx > 0 else float("nan")
        if np.isnan(sigma) or sigma <= 0.0 or np.isnan(z_now) or np.isnan(z_prev):
            _inc_reason(audit["rejections"], "mr_zscore_warmup")
            continue

        sigma_pct = float(sigma) / max(close_price, 1.0)
        if sigma_pct < sigma_min_pct or sigma_pct > sigma_max_pct:
            _inc_reason(audit["rejections"], "mr_sigma_regime_filter")
            continue

        vwap_slope_abs_pct = 0.0
        if idx >= vwap_slope_lookback:
            prior_vwap = float(vwap_series[idx - vwap_slope_lookback])
            vwap_slope_abs_pct = abs(vwap_value - prior_vwap) / max(close_price, 1.0)
            if vwap_slope_abs_pct > vwap_slope_max_pct:
                _inc_reason(audit["rejections"], "mr_vwap_slope_filter")
                continue

        effective_z_entry = z_entry
        effective_z_reentry = z_reentry
        effective_z_stop = z_stop
        if mr_adaptive_enabled:
            trend_pressure = 0.0
            if vwap_slope_max_pct > 0:
                trend_pressure = min(max(vwap_slope_abs_pct / vwap_slope_max_pct, 0.0), 1.0)
            vol_range = max(sigma_max_pct - sigma_min_pct, 1e-9)
            vol_pressure = min(max((sigma_pct - sigma_min_pct) / vol_range, 0.0), 1.0)
            adaptive_total_weight = max(mr_adaptive_trend_weight + mr_adaptive_vol_weight, 1e-9)
            adaptive_pressure = (
                (trend_pressure * mr_adaptive_trend_weight)
                + (vol_pressure * mr_adaptive_vol_weight)
            ) / adaptive_total_weight
            effective_z_entry = mr_adaptive_entry_min + (adaptive_pressure * (mr_adaptive_entry_max - mr_adaptive_entry_min))
            effective_z_entry = min(max(effective_z_entry, mr_adaptive_entry_min), mr_adaptive_entry_max)
            effective_z_stop = mr_adaptive_stop_min + (adaptive_pressure * (mr_adaptive_stop_max - mr_adaptive_stop_min))
            effective_z_stop = min(max(effective_z_stop, mr_adaptive_stop_min), mr_adaptive_stop_max)
            effective_z_stop = max(effective_z_stop, effective_z_entry)
            reentry_ratio = (z_reentry / z_entry) if z_entry > 0 else 0.0
            effective_z_reentry = min(max(effective_z_entry * reentry_ratio, 0.0), effective_z_entry)

        long_signal = (
            (z_prev <= -effective_z_entry and z_now >= -effective_z_reentry)
            or (
                low_price <= (vwap_value - (effective_z_entry * sigma))
                and close_price >= (vwap_value - (effective_z_reentry * sigma))
            )
        )
        short_signal = (
            (z_prev >= effective_z_entry and z_now <= effective_z_reentry)
            or (
                high_price >= (vwap_value + (effective_z_entry * sigma))
                and close_price <= (vwap_value + (effective_z_reentry * sigma))
            )
        )

        raw_directions: List[int] = []
        if long_signal:
            raw_directions.append(1)
        if short_signal:
            raw_directions.append(-1)
        if not raw_directions:
            continue

        audit["opportunities_before_filters"] = int(audit.get("opportunities_before_filters") or 0) + len(raw_directions)

        candidate_directions: List[int] = []
        for direction in raw_directions:
            if direction > 0 and bool(getattr(cfg, "allow_long", True)):
                candidate_directions.append(direction)
            elif direction < 0 and bool(getattr(cfg, "allow_short", True)):
                candidate_directions.append(direction)
            else:
                _inc_reason(audit["rejections"], "direction_not_allowed")
        if not candidate_directions:
            continue

        if require_reversal:
            filtered: List[int] = []
            for direction in candidate_directions:
                if direction > 0 and close_price > open_price:
                    filtered.append(direction)
                elif direction < 0 and close_price < open_price:
                    filtered.append(direction)
                else:
                    _inc_reason(audit["rejections"], "reversal_candle_filter")
            candidate_directions = filtered
            if not candidate_directions:
                continue

        if bool(getattr(cfg, "use_opening_bar_direction", False)):
            filtered = [direction for direction in candidate_directions if direction == opening_bar_direction]
            dropped = len(candidate_directions) - len(filtered)
            if dropped > 0:
                _inc_reason(audit["rejections"], "opening_bar_direction_mismatch", dropped)
            candidate_directions = filtered
            if not candidate_directions:
                continue

        direction = candidate_directions[0]
        if len(candidate_directions) > 1:
            _inc_reason(audit["rejections"], "secondary_direction_dropped", len(candidate_directions) - 1)

        if bool(getattr(cfg, "require_trend_alignment", False)):
            if direction > 0 and not (float(ema_fast[idx]) > float(ema_slow[idx])):
                _inc_reason(audit["rejections"], "trend_alignment_filter")
                continue
            if direction < 0 and not (float(ema_fast[idx]) < float(ema_slow[idx])):
                _inc_reason(audit["rejections"], "trend_alignment_filter")
                continue

        entry_idx = idx + 1
        entry_bar = session_bars[entry_idx]
        entry_price = float(opens[entry_idx])
        if entry_price <= 0:
            _inc_reason(audit["rejections"], "invalid_entry_price")
            continue

        if direction > 0:
            stop_core = min(low_price, prev_low, vwap_value - (effective_z_stop * sigma))
            stop_price = stop_core - (orb_width * stop_buffer_or_mult)
        else:
            stop_core = max(high_price, prev_high, vwap_value + (effective_z_stop * sigma))
            stop_price = stop_core + (orb_width * stop_buffer_or_mult)

        if direction > 0 and stop_price >= entry_price:
            _inc_reason(audit["rejections"], "invalid_stop")
            continue
        if direction < 0 and stop_price <= entry_price:
            _inc_reason(audit["rejections"], "invalid_stop")
            continue

        risk_per_share = abs(entry_price - stop_price)
        if risk_per_share <= 0:
            _inc_reason(audit["rejections"], "invalid_stop")
            continue

        target_underlying: Optional[float]
        if take_profit_mode == "none":
            target_underlying = None
        elif take_profit_mode == "rr":
            target_underlying = (
                entry_price + (risk_per_share * take_profit_rr)
                if direction > 0
                else entry_price - (risk_per_share * take_profit_rr)
            )
        elif take_profit_mode == "zscore":
            target_underlying = (
                vwap_value + (z_target * sigma)
                if direction > 0
                else vwap_value - (z_target * sigma)
            )
        else:
            target_underlying = vwap_value

        if target_underlying is not None:
            if direction > 0 and target_underlying <= entry_price:
                target_underlying = entry_price + max(risk_per_share * 0.4, sigma * 0.5, orb_width * 0.2)
            elif direction < 0 and target_underlying >= entry_price:
                target_underlying = entry_price - max(risk_per_share * 0.4, sigma * 0.5, orb_width * 0.2)

        audit["opportunities_after_filters"] = int(audit.get("opportunities_after_filters") or 0) + 1
        setup = {
            "direction": direction,
            "signal_idx": idx,
            "signal_ts": bar["ts"],
            "entry_idx": entry_idx,
            "entry_ts": entry_bar["ts"],
            "entry_underlying": entry_price,
            "stop_underlying": stop_price,
            "orb_high": orb_high,
            "orb_low": orb_low,
            "opening_bar_open": orb_open,
            "opening_bar_close": orb_close,
            "opening_bar_direction": opening_bar_direction,
            "trend_ema_fast": float(ema_fast[idx]),
            "trend_ema_slow": float(ema_slow[idx]),
            "volume_ratio": volume_ratio,
            "relative_opening_volume": relative_opening_volume,
            "atr_value": atr_value,
            "fvg_gap": 0.0,
            "opening_range_minutes": opening_range_count,
            "orb_width_pct": orb_width_pct,
            "strategy_variant": "mr_vwap_zscore_v2",
            "mr_vwap_at_signal": vwap_value,
            "mr_sigma_at_signal": float(sigma),
            "mr_zscore_at_signal": float(z_now),
            "mr_take_profit_mode": take_profit_mode,
            "mr_target_underlying": target_underlying,
            "mr_zscore_entry": effective_z_entry,
            "mr_zscore_reentry": effective_z_reentry,
            "mr_zscore_stop": effective_z_stop,
            "mr_zscore_target": z_target,
            "mr_sigma_pct_at_signal": sigma_pct,
            "mr_adaptive_enabled": mr_adaptive_enabled,
        }
        return setup, audit

    if int(audit.get("opportunities_before_filters") or 0) == 0:
        _inc_reason(audit["rejections"], "mr_zscore_no_signal")
    return None, audit


def find_mr_vwap_setup_with_audit(
    session_bars: List[Dict[str, Any]],
    cfg: Any,
    relative_opening_volume: Optional[float],
    atr_value: Optional[float],
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    audit: Dict[str, Any] = {
        "strategy_variant": "mr_vwap_revert_v1",
        "opportunities_before_filters": 0,
        "opportunities_after_filters": 0,
        "rejections": {},
    }
    opening_range_count = max(int(getattr(cfg, "opening_range_minutes", 5)), 1)
    if len(session_bars) < (opening_range_count + 3):
        _inc_reason(audit["rejections"], "insufficient_bars")
        return None, audit

    opens, highs, lows, closes, volumes = _session_bar_arrays(session_bars)
    opening_slice = slice(0, opening_range_count)
    orb_high = float(np.max(highs[opening_slice]))
    orb_low = float(np.min(lows[opening_slice]))
    orb_open = float(opens[0])
    orb_close = float(closes[opening_range_count - 1])
    if orb_high <= 0 or orb_low <= 0 or orb_high <= orb_low:
        _inc_reason(audit["rejections"], "invalid_opening_range")
        return None, audit

    orb_width = orb_high - orb_low
    orb_width_pct = orb_width / max(orb_open, 1.0)
    if bool(getattr(cfg, "require_or_width_filter", False)):
        min_width = max(float(getattr(cfg, "opening_range_min_width_pct", 0.0)), 0.0)
        max_width = max(float(getattr(cfg, "opening_range_max_width_pct", 1.0)), min_width)
        if orb_width_pct < min_width or orb_width_pct > max_width:
            _inc_reason(audit["rejections"], "orb_width_filter")
            return None, audit

    opening_bar_direction = 0
    if orb_close > orb_open:
        opening_bar_direction = 1
    elif orb_close < orb_open:
        opening_bar_direction = -1

    ema_fast = _ema_array(closes, int(getattr(cfg, "trend_ema_fast", 20)))
    ema_slow = _ema_array(closes, int(getattr(cfg, "trend_ema_slow", 50)))
    vwap_series = _running_vwap_array(highs, lows, closes, volumes)

    entry_start = _parse_hhmm(str(getattr(cfg, "entry_start_time", "")), _default_entry_start(opening_range_count))
    entry_cutoff = _parse_hhmm(str(getattr(cfg, "entry_cutoff_time", "")), "12:00")
    macro_release_times = (
        _parse_hhmm_list(str(getattr(cfg, "macro_release_times_et", "")), "10:00")
        if bool(getattr(cfg, "require_macro_release_filter", False))
        else []
    )
    macro_block_minutes = max(int(getattr(cfg, "macro_post_release_block_minutes", 0)), 0)

    band_or_mult = max(float(getattr(cfg, "mr_band_or_mult", 1.0)), 0.0)
    min_distance_pct = max(float(getattr(cfg, "mr_min_distance_from_vwap_pct", 0.0)), 0.0)
    reentry_or_mult = max(float(getattr(cfg, "mr_reentry_buffer_or_mult", 0.0)), 0.0)
    stop_buffer_or_mult = max(float(getattr(cfg, "mr_stop_buffer_or_mult", 0.0)), 0.0)
    take_profit_mode = str(getattr(cfg, "mr_take_profit_mode", "vwap") or "vwap").strip().lower()
    take_profit_rr = max(float(getattr(cfg, "mr_take_profit_rr", 1.0)), 0.0)
    require_reversal = bool(getattr(cfg, "mr_require_reversal_candle", True))
    volume_ma_window = max(int(getattr(cfg, "volume_ma_window", 20)), 1)
    volume_prefix = np.concatenate(([0.0], np.cumsum(volumes, dtype=float)))

    if take_profit_mode not in {"vwap", "rr", "none", "zscore"}:
        take_profit_mode = "vwap"

    for idx in range(max(opening_range_count, 1), len(session_bars) - 1):
        bar = session_bars[idx]
        bar_time = _to_et_time(bar["ts"])
        if bar_time < entry_start or bar_time > entry_cutoff:
            continue

        if bool(getattr(cfg, "require_macro_release_filter", False)) and _is_in_macro_release_block(
            bar_time,
            macro_release_times,
            macro_block_minutes,
        ):
            _inc_reason(audit["rejections"], "macro_release_block")
            continue

        open_price = float(opens[idx])
        high_price = float(highs[idx])
        low_price = float(lows[idx])
        close_price = float(closes[idx])
        prev_open = float(opens[idx - 1])
        prev_close = float(closes[idx - 1])
        prev_low = float(lows[idx - 1])
        prev_high = float(highs[idx - 1])
        if (
            open_price <= 0
            or high_price <= 0
            or low_price <= 0
            or close_price <= 0
            or prev_open <= 0
            or prev_close <= 0
            or prev_low <= 0
            or prev_high <= 0
        ):
            continue

        if bool(getattr(cfg, "require_relative_volume", False)):
            relative_volume_min = float(getattr(cfg, "relative_volume_min", 1.0))
            if relative_opening_volume is None or relative_opening_volume < relative_volume_min:
                _inc_reason(audit["rejections"], "relative_volume_filter")
                continue

        if bool(getattr(cfg, "require_atr_filter", False)):
            atr_min = float(getattr(cfg, "atr_min", 0.0))
            if atr_value is None or atr_value < atr_min:
                _inc_reason(audit["rejections"], "atr_filter")
                continue

        if bool(getattr(cfg, "require_volume_spike", False)):
            if idx < volume_ma_window:
                _inc_reason(audit["rejections"], "volume_ma_warmup")
                continue
            avg_volume = float(volume_prefix[idx] - volume_prefix[idx - volume_ma_window]) / float(volume_ma_window)
            if avg_volume <= 0:
                _inc_reason(audit["rejections"], "volume_ma_invalid")
                continue
            volume_ratio = float(volumes[idx]) / avg_volume
            if volume_ratio < float(getattr(cfg, "volume_spike_multiple", 1.2)):
                _inc_reason(audit["rejections"], "volume_spike_filter")
                continue
        else:
            volume_ratio = 1.0

        vwap_value = float(vwap_series[idx])
        if vwap_value <= 0:
            _inc_reason(audit["rejections"], "invalid_vwap")
            continue

        distance_floor = max(close_price * min_distance_pct, 0.0)
        band_distance = max(orb_width * band_or_mult, distance_floor)
        if band_distance <= 0:
            _inc_reason(audit["rejections"], "invalid_mr_band")
            continue

        lower_band = vwap_value - band_distance
        upper_band = vwap_value + band_distance
        reclaim_buffer = band_distance * reentry_or_mult

        long_signal = (
            (prev_close < lower_band and close_price >= (lower_band + reclaim_buffer))
            or (low_price <= lower_band and close_price >= (lower_band + reclaim_buffer))
        )
        short_signal = (
            (prev_close > upper_band and close_price <= (upper_band - reclaim_buffer))
            or (high_price >= upper_band and close_price <= (upper_band - reclaim_buffer))
        )

        raw_directions: List[int] = []
        if long_signal:
            raw_directions.append(1)
        if short_signal:
            raw_directions.append(-1)
        if not raw_directions:
            continue

        audit["opportunities_before_filters"] = int(audit.get("opportunities_before_filters") or 0) + len(raw_directions)

        candidate_directions: List[int] = []
        for direction in raw_directions:
            if direction > 0 and bool(getattr(cfg, "allow_long", True)):
                candidate_directions.append(direction)
            elif direction < 0 and bool(getattr(cfg, "allow_short", True)):
                candidate_directions.append(direction)
            else:
                _inc_reason(audit["rejections"], "direction_not_allowed")
        if not candidate_directions:
            continue

        if require_reversal:
            filtered: List[int] = []
            for direction in candidate_directions:
                if direction > 0 and close_price > open_price:
                    filtered.append(direction)
                elif direction < 0 and close_price < open_price:
                    filtered.append(direction)
                else:
                    _inc_reason(audit["rejections"], "reversal_candle_filter")
            candidate_directions = filtered
            if not candidate_directions:
                continue

        if bool(getattr(cfg, "use_opening_bar_direction", False)):
            filtered = [direction for direction in candidate_directions if direction == opening_bar_direction]
            dropped = len(candidate_directions) - len(filtered)
            if dropped > 0:
                _inc_reason(audit["rejections"], "opening_bar_direction_mismatch", dropped)
            candidate_directions = filtered
            if not candidate_directions:
                continue

        direction = candidate_directions[0]
        if len(candidate_directions) > 1:
            _inc_reason(audit["rejections"], "secondary_direction_dropped", len(candidate_directions) - 1)

        if bool(getattr(cfg, "require_trend_alignment", False)):
            if direction > 0 and not (float(ema_fast[idx]) > float(ema_slow[idx])):
                _inc_reason(audit["rejections"], "trend_alignment_filter")
                continue
            if direction < 0 and not (float(ema_fast[idx]) < float(ema_slow[idx])):
                _inc_reason(audit["rejections"], "trend_alignment_filter")
                continue

        entry_idx = idx + 1
        entry_bar = session_bars[entry_idx]
        entry_price = float(opens[entry_idx])
        if entry_price <= 0:
            _inc_reason(audit["rejections"], "invalid_entry_price")
            continue

        if direction > 0:
            stop_price = min(low_price, prev_low) - (orb_width * stop_buffer_or_mult)
        else:
            stop_price = max(high_price, prev_high) + (orb_width * stop_buffer_or_mult)

        if direction > 0 and stop_price >= entry_price:
            _inc_reason(audit["rejections"], "invalid_stop")
            continue
        if direction < 0 and stop_price <= entry_price:
            _inc_reason(audit["rejections"], "invalid_stop")
            continue

        risk_per_share = abs(entry_price - stop_price)
        target_underlying: Optional[float]
        if take_profit_mode == "none":
            target_underlying = None
        elif take_profit_mode == "rr" and risk_per_share > 0:
            target_underlying = (
                entry_price + (risk_per_share * take_profit_rr)
                if direction > 0
                else entry_price - (risk_per_share * take_profit_rr)
            )
        else:
            target_underlying = vwap_value
            if direction > 0 and target_underlying <= entry_price:
                target_underlying = entry_price + max(risk_per_share * 0.5, orb_width * 0.25)
            elif direction < 0 and target_underlying >= entry_price:
                target_underlying = entry_price - max(risk_per_share * 0.5, orb_width * 0.25)

        audit["opportunities_after_filters"] = int(audit.get("opportunities_after_filters") or 0) + 1
        setup = {
            "direction": direction,
            "signal_idx": idx,
            "signal_ts": bar["ts"],
            "entry_idx": entry_idx,
            "entry_ts": entry_bar["ts"],
            "entry_underlying": entry_price,
            "stop_underlying": stop_price,
            "orb_high": orb_high,
            "orb_low": orb_low,
            "opening_bar_open": orb_open,
            "opening_bar_close": orb_close,
            "opening_bar_direction": opening_bar_direction,
            "trend_ema_fast": float(ema_fast[idx]),
            "trend_ema_slow": float(ema_slow[idx]),
            "volume_ratio": volume_ratio,
            "relative_opening_volume": relative_opening_volume,
            "atr_value": atr_value,
            "fvg_gap": 0.0,
            "opening_range_minutes": opening_range_count,
            "orb_width_pct": orb_width_pct,
            "strategy_variant": "mr_vwap_revert_v1",
            "mr_vwap_at_signal": vwap_value,
            "mr_band_distance": band_distance,
            "mr_take_profit_mode": take_profit_mode,
            "mr_target_underlying": target_underlying,
        }
        return setup, audit

    if int(audit.get("opportunities_before_filters") or 0) == 0:
        _inc_reason(audit["rejections"], "mr_no_signal")
    return None, audit


def resolve_mr_vwap_exit(
    session_bars: List[Dict[str, Any]],
    setup: Dict[str, Any],
    cfg: Any,
) -> Optional[Dict[str, Any]]:
    if not session_bars:
        return None

    direction = int(setup["direction"])
    entry_idx = int(setup["entry_idx"])
    entry_underlying = float(setup["entry_underlying"])
    stop_underlying = float(setup["stop_underlying"])
    entry_ts = setup.get("entry_ts")
    exit_cutoff = _parse_hhmm(str(getattr(cfg, "exit_time", "")), "15:55")

    risk_per_share = abs(entry_underlying - stop_underlying)
    break_even_trigger_rr = max(float(getattr(cfg, "break_even_trigger_rr", 0.0)), 0.0)
    early_fail_minutes = max(int(getattr(cfg, "early_fail_minutes", 0)), 0)
    early_fail_min_rr = float(getattr(cfg, "early_fail_min_rr", 0.0))
    max_hold_minutes = max(int(getattr(cfg, "max_hold_minutes", 0)), 0)
    time_to_work_bars = max(int(setup.get("mr_time_to_work_bars") or getattr(cfg, "mr_time_to_work_bars", 0)), 0)
    time_to_work_min_rr = max(
        float(setup.get("mr_time_to_work_min_rr") or getattr(cfg, "mr_time_to_work_min_rr", 0.0)),
        0.0,
    )
    dynamic_stop_underlying = stop_underlying
    break_even_armed = False

    take_profit_mode = str(setup.get("mr_take_profit_mode") or getattr(cfg, "mr_take_profit_mode", "vwap")).strip().lower()
    if take_profit_mode not in {"vwap", "rr", "none", "zscore"}:
        take_profit_mode = "vwap"

    take_profit: Optional[float] = None
    if take_profit_mode == "rr" and risk_per_share > 0:
        rr_target = max(float(getattr(cfg, "mr_take_profit_rr", 1.0)), 0.0)
        take_profit = (
            entry_underlying + (risk_per_share * rr_target)
            if direction > 0
            else entry_underlying - (risk_per_share * rr_target)
        )
    elif take_profit_mode in {"vwap", "zscore"}:
        take_profit = _safe_float(setup.get("mr_target_underlying"))
        if take_profit is None:
            take_profit = _safe_float(setup.get("mr_vwap_at_signal"))

    if take_profit is not None:
        if direction > 0 and take_profit <= entry_underlying:
            take_profit = None
        if direction < 0 and take_profit >= entry_underlying:
            take_profit = None

    opposite_min_hold_ts: Optional[datetime] = None
    if isinstance(entry_ts, datetime):
        min_hold = max(int(getattr(cfg, "opposite_candle_min_hold_minutes", 0)), 0)
        opposite_min_hold_ts = entry_ts + timedelta(minutes=min_hold)

    for idx in range(entry_idx + 1, len(session_bars)):
        bar = session_bars[idx]
        bar_time = _to_et_time(bar["ts"])
        open_price = float(bar.get("open") or 0.0)
        high_price = float(bar.get("high") or 0.0)
        low_price = float(bar.get("low") or 0.0)
        close_price = float(bar.get("close") or 0.0)
        if open_price <= 0 or high_price <= 0 or low_price <= 0 or close_price <= 0:
            continue

        elapsed_minutes: Optional[float] = None
        if isinstance(entry_ts, datetime) and isinstance(bar.get("ts"), datetime):
            elapsed_minutes = (bar["ts"] - entry_ts).total_seconds() / 60.0

        if direction > 0 and low_price <= dynamic_stop_underlying:
            return {
                "exit_idx": idx,
                "exit_ts": bar["ts"],
                "exit_underlying": dynamic_stop_underlying,
                "exit_reason": "stop_loss",
            }
        if direction < 0 and high_price >= dynamic_stop_underlying:
            return {
                "exit_idx": idx,
                "exit_ts": bar["ts"],
                "exit_underlying": dynamic_stop_underlying,
                "exit_reason": "stop_loss",
            }

        if take_profit is not None:
            target_reason = (
                "mr_target_vwap"
                if take_profit_mode == "vwap"
                else ("mr_target_zscore" if take_profit_mode == "zscore" else "take_profit")
            )
            if direction > 0 and high_price >= take_profit:
                return {
                    "exit_idx": idx,
                    "exit_ts": bar["ts"],
                    "exit_underlying": take_profit,
                    "exit_reason": target_reason,
                }
            if direction < 0 and low_price <= take_profit:
                return {
                    "exit_idx": idx,
                    "exit_ts": bar["ts"],
                    "exit_underlying": take_profit,
                    "exit_reason": target_reason,
                }

        if bool(getattr(cfg, "exit_on_opposite_candle", False)):
            if opposite_min_hold_ts is not None and bar["ts"] < opposite_min_hold_ts:
                pass
            elif direction > 0 and close_price < open_price:
                return {
                    "exit_idx": idx,
                    "exit_ts": bar["ts"],
                    "exit_underlying": close_price,
                    "exit_reason": "opposite_color_candle",
                }
            elif direction < 0 and close_price > open_price:
                return {
                    "exit_idx": idx,
                    "exit_ts": bar["ts"],
                    "exit_underlying": close_price,
                    "exit_reason": "opposite_color_candle",
                }

        if (
            early_fail_minutes > 0
            and elapsed_minutes is not None
            and elapsed_minutes >= float(early_fail_minutes)
            and risk_per_share > 0
        ):
            rr_now = (
                (close_price - entry_underlying) / risk_per_share
                if direction > 0
                else (entry_underlying - close_price) / risk_per_share
            )
            if rr_now < early_fail_min_rr:
                return {
                    "exit_idx": idx,
                    "exit_ts": bar["ts"],
                    "exit_underlying": close_price,
                    "exit_reason": "early_fail_r",
                }

        if (
            max_hold_minutes > 0
            and elapsed_minutes is not None
            and elapsed_minutes >= float(max_hold_minutes)
        ):
            return {
                "exit_idx": idx,
                "exit_ts": bar["ts"],
                "exit_underlying": close_price,
                    "exit_reason": "max_hold_time",
                }

        if time_to_work_bars > 0 and risk_per_share > 0 and (idx - entry_idx) >= time_to_work_bars:
            rr_now = (
                (close_price - entry_underlying) / risk_per_share
                if direction > 0
                else (entry_underlying - close_price) / risk_per_share
            )
            if rr_now < time_to_work_min_rr:
                return {
                    "exit_idx": idx,
                    "exit_ts": bar["ts"],
                    "exit_underlying": close_price,
                    "exit_reason": "mr_time_to_work_fail",
                }

        if (
            (not break_even_armed)
            and break_even_trigger_rr > 0
            and risk_per_share > 0
        ):
            trigger_underlying = (
                entry_underlying + (risk_per_share * break_even_trigger_rr)
                if direction > 0
                else entry_underlying - (risk_per_share * break_even_trigger_rr)
            )
            trigger_hit = (
                (direction > 0 and high_price >= trigger_underlying)
                or (direction < 0 and low_price <= trigger_underlying)
            )
            if trigger_hit:
                break_even_armed = True
                if direction > 0:
                    dynamic_stop_underlying = max(dynamic_stop_underlying, entry_underlying)
                else:
                    dynamic_stop_underlying = min(dynamic_stop_underlying, entry_underlying)

        if bar_time >= exit_cutoff:
            return {
                "exit_idx": idx,
                "exit_ts": bar["ts"],
                "exit_underlying": close_price,
                "exit_reason": "time_exit",
            }

    last_bar = session_bars[-1]
    last_close = float(last_bar.get("close") or 0.0)
    if last_close <= 0:
        return None
    return {
        "exit_idx": len(session_bars) - 1,
        "exit_ts": last_bar["ts"],
        "exit_underlying": last_close,
        "exit_reason": "session_close",
    }
