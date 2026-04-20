"""Low-Float Catalyst Momentum (LFCM_v1) strategy.

Signal hypothesis
-----------------
A low-float stock that gaps up ≥8% pre-market with a verifiable hard catalyst
(earnings beat, FDA approval, contract award, analyst upgrade) and shows
strong first-bar confirmation (closes above pre-market high, high close
location, elevated volume) tends to continue intraday.

Backtest mode
-------------
All defaults are set to the *pessimistic* spec from LFCM_v1 backtest_mode.
Key pessimistic adjustments vs. the raw spec:
  - Float universe tightened to 2M–10M (vs. 1M–15M in spec)
  - Float drift factor 0.80/year applied for historical extrapolation
  - Round-trip cost = (spread_fraction × bar_range_pct + slippage + buffer) × 2
  - Entry on bar2_open (one bar after signal bar)
  - fill_rate = 0.85 (15% of trades modelled as missed fills)
  - max_hold_minutes = 44 (not 45, avoids EOD session boundary)
  - Catalyst: hard phrase match only, on_unclear = reject
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo


_ET_ZONE = ZoneInfo("America/New_York")

# ---------------------------------------------------------------------------
# Catalyst phrase tables (from LFCM_v1 spec, hard_match_only mode)
# ---------------------------------------------------------------------------

_CATALYST_VALID_PHRASES: Dict[str, List[str]] = {
    "earnings_beat": ["beats estimates", "tops estimates", "eps beat"],
    "fda_approval":  ["fda approved", "fda approval", "fda clears"],
    "contract":      ["awarded contract", "signed agreement"],
    "upgrade":       ["upgraded to buy", "upgraded to outperform"],
}

_CATALYST_DISQUALIFIERS: List[str] = [
    "social_pump", "unusual options", "wsb", "trending",
    "short squeeze", "speculation", "rumor", "unconfirmed",
]


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

@dataclass
class LFCMConfig:
    """Pessimistic-mode configuration for LFCM_v1.

    All float/universe bounds reflect the *pessimistic_universe* from the spec
    (2M–10M), not the wider spec_universe (1M–15M).
    """

    # --- Universe ---
    float_min_shares: int = 2_000_000
    float_max_shares: int = 10_000_000
    # Per-year multiplicative drift applied when estimating historical float
    # from current CuteMarkets reference data. 0.80 = assume float was 20% smaller per year
    # in the past (conservative: makes the universe narrower historically).
    float_drift_factor_per_year: float = 0.80
    price_min: float = 2.0
    price_max: float = 20.0
    avg_daily_volume_min: int = 500_000
    avg_daily_volume_max: int = 8_000_000
    avg_daily_volume_lookback_days: int = 20

    # --- Premarket filter ---
    gap_min_pct: float = 0.08
    premarket_volume_min_pct_of_avg_daily: float = 0.20
    require_news: bool = True

    # --- Entry window (ET) ---
    entry_window_start: str = "09:31"
    entry_window_end: str = "09:45"

    # --- Entry bar conditions ---
    # bar1 must close above premarket_high
    # bar1 volume >= bar1_volume_multiple × expected_avg_volume_per_minute
    bar1_volume_multiple: float = 1.5
    # bar1 close must be in top fraction of bar range: (close-low)/(high-low)
    bar1_close_location_min: float = 0.66
    # spread proxy: (high - low) / close — used as bid/ask spread approximation
    spread_proxy_max_pct: float = 0.003

    # --- Stop ---
    # Initial stop = bar1_low; trailing activates after trailing_trigger_rr
    trailing_trigger_rr: float = 1.0

    # --- Targets (blended single-exit model) ---
    # T1: close 50% at t1_rr, move stop to break-even
    t1_rr: float = 2.0
    t1_size_pct: float = 0.50
    # T2: trailing stop under previous bar low

    # --- Exit guards ---
    volume_dry_up_multiple: float = 0.30   # exit if volume < 0.30× rolling avg
    volume_ma_window: int = 5              # bars for rolling volume average
    max_hold_minutes: int = 44             # hard time cap (not 45 to avoid EOD)

    # --- Pessimistic transaction costs ---
    # round_trip = (spread_fraction × bar_range_pct + slippage + buffer) × 2
    spread_fraction: float = 0.25
    additional_slippage_pct: float = 0.002
    stop_slippage_pct: float = 0.001
    spread_buffer_pct: float = 0.001

    # --- Execution assumptions ---
    entry_bar_delay_bars: int = 1    # signal on bar N → entry on bar N+1 open
    fill_rate: float = 0.85          # fraction of qualifying setups that fill


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_hhmm(value: str, default: str) -> time:
    text = (value or "").strip() or default
    try:
        h, m = text.split(":", 1)
        return time(hour=max(0, min(23, int(h))), minute=max(0, min(59, int(m))))
    except (ValueError, TypeError):
        h, m = default.split(":", 1)
        return time(hour=int(h), minute=int(m))


def _to_et_time(ts: datetime) -> time:
    aware = ts.replace(tzinfo=timezone.utc) if ts.tzinfo is None else ts.astimezone(timezone.utc)
    return aware.astimezone(_ET_ZONE).time()


def _safe_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _inc(counter: Dict[str, int], key: str, n: int = 1) -> None:
    counter[key] = counter.get(key, 0) + n


# ---------------------------------------------------------------------------
# Catalyst classification
# ---------------------------------------------------------------------------

def classify_catalyst(headlines: List[str]) -> Optional[str]:
    """Hard-phrase match against LFCM valid catalyst phrases.

    Returns the catalyst type string (e.g. "earnings_beat") on the first
    match, None if no valid phrase is found or a disqualifier fires.

    Policy: ``on_unclear = reject`` — any ambiguity returns None.
    """
    combined = " ".join(h.lower() for h in headlines if h)

    for disqualifier in _CATALYST_DISQUALIFIERS:
        if disqualifier in combined:
            return None

    for catalyst_type, phrases in _CATALYST_VALID_PHRASES.items():
        for phrase in phrases:
            if phrase in combined:
                return catalyst_type

    return None


# ---------------------------------------------------------------------------
# Universe helpers
# ---------------------------------------------------------------------------

def compute_premarket_high(premarket_bars: List[Dict[str, Any]]) -> Optional[float]:
    """Return the highest high across all pre-market bars (04:00–09:30 ET)."""
    highs = [_safe_float(bar.get("high")) for bar in premarket_bars]
    valid = [h for h in highs if h is not None and h > 0]
    return max(valid) if valid else None


def compute_premarket_volume(premarket_bars: List[Dict[str, Any]]) -> float:
    """Return total volume across all pre-market bars."""
    return sum(
        max(float(bar.get("volume") or 0), 0.0)
        for bar in premarket_bars
    )


def compute_avg_daily_volume(
    daily_bars: List[Dict[str, Any]],
    lookback: int,
) -> Optional[float]:
    """Mean daily volume over the last *lookback* daily bars (excluding today)."""
    if not daily_bars or lookback < 1:
        return None
    recent = daily_bars[-lookback:]
    volumes = [_safe_float(bar.get("volume")) for bar in recent]
    valid = [v for v in volumes if v is not None and v > 0]
    return sum(valid) / len(valid) if valid else None


def estimate_historical_float(
    current_float: int,
    years_ago: float,
    drift_factor_per_year: float = 0.80,
) -> int:
    """Estimate what the float *years_ago* was, given the current float.

    Models share-count drift as a geometric decay:
        historical_float = current_float × drift_factor^years_ago

    With drift_factor=0.80 (pessimistic spec), float was ~20% smaller per year
    in the past, so the historical estimate is *narrower* than current → more
    trades are rejected, which is the conservative direction.
    """
    if years_ago <= 0 or drift_factor_per_year <= 0:
        return int(current_float)
    factor = drift_factor_per_year ** years_ago
    return int(round(current_float * factor))


def compute_round_trip_cost_pct(
    bar_high: float,
    bar_low: float,
    bar_close: float,
    cfg: LFCMConfig,
) -> float:
    """Compute the estimated round-trip cost as a fraction of price.

    Formula from pessimistic spec:
        (spread_fraction × bar_range_pct + slippage + buffer) × 2
    """
    if bar_close <= 0:
        return 0.0
    bar_range_pct = (bar_high - bar_low) / bar_close
    one_way = cfg.spread_fraction * bar_range_pct + cfg.additional_slippage_pct + cfg.spread_buffer_pct
    return one_way * 2.0


# ---------------------------------------------------------------------------
# Signal detection
# ---------------------------------------------------------------------------

def find_lfcm_setup(
    session_bars: List[Dict[str, Any]],
    *,
    premarket_bars: List[Dict[str, Any]],
    prev_close: float,
    avg_daily_volume: Optional[float],
    current_float: Optional[int],
    years_ago: float = 0.0,
    catalyst_headlines: Optional[List[str]] = None,
    cfg: LFCMConfig,
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """Find the first qualifying LFCM entry setup for a session.

    Parameters
    ----------
    session_bars:
        1-minute bars for the regular session (09:30–16:00 ET), sorted asc.
    premarket_bars:
        1-minute bars for pre-market (04:00–09:30 ET), sorted asc.
    prev_close:
        Previous session's closing price (for gap calculation).
    avg_daily_volume:
        20-day average daily volume (shares).  None disables the volume filter.
    current_float:
        Current shares outstanding / float from CuteMarkets reference data.
        None disables the float filter.
    years_ago:
        How many years before today the backtest date falls.  Used to apply
        float drift for historical extrapolation.
    catalyst_headlines:
        List of news headlines published before market open.  None or [] with
        require_news=True → rejected.
    cfg:
        LFCMConfig instance.

    Returns
    -------
    (setup_dict, audit_dict)
        setup_dict is None if no qualifying setup is found.
    """
    audit: Dict[str, Any] = {
        "strategy_variant": "lfcm_v1",
        "opportunities_before_filters": 0,
        "opportunities_after_filters": 0,
        "rejections": {},
    }

    # ------------------------------------------------------------------
    # 1. Float filter (universe)
    # ------------------------------------------------------------------
    if current_float is not None:
        hist_float = estimate_historical_float(
            current_float,
            years_ago=years_ago,
            drift_factor_per_year=cfg.float_drift_factor_per_year,
        )
        if hist_float < cfg.float_min_shares or hist_float > cfg.float_max_shares:
            _inc(audit["rejections"], "float_out_of_range")
            return None, audit
    # (if current_float is None, float filter is skipped — caller must decide)

    # ------------------------------------------------------------------
    # 2. Gap filter
    # ------------------------------------------------------------------
    if prev_close <= 0:
        _inc(audit["rejections"], "invalid_prev_close")
        return None, audit

    premarket_high = compute_premarket_high(premarket_bars)
    if premarket_high is None or premarket_high <= 0:
        _inc(audit["rejections"], "no_premarket_high")
        return None, audit

    gap_pct = (premarket_high / prev_close) - 1.0
    if gap_pct < cfg.gap_min_pct:
        _inc(audit["rejections"], "gap_too_small")
        return None, audit

    # ------------------------------------------------------------------
    # 3. Premarket volume filter
    # ------------------------------------------------------------------
    if avg_daily_volume is not None and avg_daily_volume > 0:
        premarket_vol = compute_premarket_volume(premarket_bars)
        required_premarket_vol = avg_daily_volume * cfg.premarket_volume_min_pct_of_avg_daily
        if premarket_vol < required_premarket_vol:
            _inc(audit["rejections"], "premarket_volume_too_low")
            return None, audit

    # ------------------------------------------------------------------
    # 4. Catalyst filter
    # ------------------------------------------------------------------
    catalyst_type: Optional[str] = None
    if cfg.require_news:
        headlines = catalyst_headlines or []
        catalyst_type = classify_catalyst(headlines)
        if catalyst_type is None:
            _inc(audit["rejections"], "no_valid_catalyst")
            return None, audit

    # ------------------------------------------------------------------
    # 5. Price filter (use session open as proxy for current price)
    # ------------------------------------------------------------------
    if session_bars:
        session_open = _safe_float(session_bars[0].get("open"))
        if session_open is not None:
            if session_open < cfg.price_min or session_open > cfg.price_max:
                _inc(audit["rejections"], "price_out_of_range")
                return None, audit

    # ------------------------------------------------------------------
    # 6. Average daily volume universe filter
    # ------------------------------------------------------------------
    if avg_daily_volume is not None:
        if avg_daily_volume < cfg.avg_daily_volume_min or avg_daily_volume > cfg.avg_daily_volume_max:
            _inc(audit["rejections"], "adv_out_of_range")
            return None, audit

    # ------------------------------------------------------------------
    # 7. Scan entry window for first qualifying bar
    # ------------------------------------------------------------------
    entry_start = _parse_hhmm(cfg.entry_window_start, "09:31")
    entry_end = _parse_hhmm(cfg.entry_window_end, "09:45")

    # Expected volume per minute = avg_daily_volume / 390 trading minutes
    expected_vol_per_min = (avg_daily_volume / 390.0) if avg_daily_volume and avg_daily_volume > 0 else None

    # Rolling volume prefix for dry-up detection later
    vol_window = max(cfg.volume_ma_window, 1)

    for idx, bar in enumerate(session_bars):
        bar_time = _to_et_time(bar["ts"])
        if bar_time < entry_start:
            continue
        if bar_time > entry_end:
            break

        open_price  = _safe_float(bar.get("open"))
        high_price  = _safe_float(bar.get("high"))
        low_price   = _safe_float(bar.get("low"))
        close_price = _safe_float(bar.get("close"))
        volume      = max(float(bar.get("volume") or 0), 0.0)

        if not all(v is not None and v > 0 for v in (open_price, high_price, low_price, close_price)):
            continue

        audit["opportunities_before_filters"] += 1

        # a) Close must be above pre-market high
        if close_price <= premarket_high:
            _inc(audit["rejections"], "bar1_close_below_premarket_high")
            continue

        # b) Volume confirmation
        if expected_vol_per_min is not None and expected_vol_per_min > 0:
            if volume < cfg.bar1_volume_multiple * expected_vol_per_min:
                _inc(audit["rejections"], "bar1_volume_too_low")
                continue

        # c) Close location (strong close: top 34% of bar range)
        bar_range = high_price - low_price
        if bar_range > 0:
            close_location = (close_price - low_price) / bar_range
            if close_location < cfg.bar1_close_location_min:
                _inc(audit["rejections"], "bar1_close_location_weak")
                continue

        # d) Spread proxy filter
        if close_price > 0:
            spread_proxy = (high_price - low_price) / close_price
            if spread_proxy > cfg.spread_proxy_max_pct:
                _inc(audit["rejections"], "spread_too_wide")
                continue

        # All bar1 checks passed — entry is bar N+delay open
        entry_idx = idx + cfg.entry_bar_delay_bars
        if entry_idx >= len(session_bars):
            _inc(audit["rejections"], "no_entry_bar")
            continue

        entry_bar = session_bars[entry_idx]
        entry_price = _safe_float(entry_bar.get("open"))
        if entry_price is None or entry_price <= 0:
            _inc(audit["rejections"], "invalid_entry_price")
            continue

        stop_price = low_price  # initial stop = bar1_low

        if stop_price >= entry_price:
            _inc(audit["rejections"], "stop_above_entry")
            continue

        risk_per_share = entry_price - stop_price
        t1_price = entry_price + risk_per_share * cfg.t1_rr

        # Round-trip cost for this specific bar
        round_trip_cost_pct = compute_round_trip_cost_pct(
            bar_high=high_price,
            bar_low=low_price,
            bar_close=close_price,
            cfg=cfg,
        )
        # Pessimistic effective entry (one-way cost applied to entry)
        one_way_cost_pct = round_trip_cost_pct / 2.0
        effective_entry = entry_price * (1.0 + one_way_cost_pct)

        audit["opportunities_after_filters"] += 1
        return {
            "strategy_variant": "lfcm_v1",
            "direction": 1,                          # long only
            "signal_idx": idx,
            "signal_ts": bar["ts"],
            "entry_idx": entry_idx,
            "entry_ts": entry_bar["ts"],
            "entry_underlying": entry_price,
            "entry_effective": effective_entry,       # incl. one-way cost
            "stop_underlying": stop_price,
            "t1_price": t1_price,
            "orb_high": premarket_high,               # reuse orb_high slot
            "orb_low": low_price,
            "opening_bar_open": open_price,
            "opening_bar_close": close_price,
            "opening_bar_direction": 1,
            "volume_ratio": (volume / expected_vol_per_min) if expected_vol_per_min else 1.0,
            "relative_opening_volume": None,
            "atr_value": None,
            "fvg_gap": 0.0,
            "opening_range_minutes": 1,
            "orb_width_pct": gap_pct,
            # LFCM metadata
            "lfcm_gap_pct": gap_pct,
            "lfcm_premarket_high": premarket_high,
            "lfcm_catalyst_type": catalyst_type,
            "lfcm_close_location": close_location if bar_range > 0 else None,
            "lfcm_spread_proxy_pct": spread_proxy if close_price > 0 else None,
            "lfcm_round_trip_cost_pct": round_trip_cost_pct,
            "lfcm_fill_rate": cfg.fill_rate,
        }, audit

    if audit["opportunities_before_filters"] == 0:
        _inc(audit["rejections"], "no_bar_in_entry_window")
    return None, audit


# ---------------------------------------------------------------------------
# Exit logic (blended T1/T2 single-trade model)
# ---------------------------------------------------------------------------

def resolve_lfcm_exit(
    session_bars: List[Dict[str, Any]],
    setup: Dict[str, Any],
    cfg: LFCMConfig,
) -> Optional[Dict[str, Any]]:
    """Resolve the exit for an LFCM setup.

    T1/T2 split modelled as a *blended single exit*:
      - When T1 (2R) is hit: record t1_price, move stop to break-even,
        activate trailing stop (under previous bar low).
      - When T2 exits (trailing stop or time): compute weighted average
        exit = t1_size_pct × t1_price + (1 − t1_size_pct) × t2_price.
      - If T1 is never hit: single exit at stop / time / volume dry-up.

    Exit priority (matches spec):
      1. Stop triggered (full close)
      2. T1 reached → partial, move stop to BE, trailing active
      3. bar_close < bar1_low (signal bar low — momentum invalidated)
      4. Volume dry-up (volume < 0.30× rolling average)
      5. max_hold_minutes reached
      6. T2 trailing stop triggered
    """
    if not session_bars:
        return None

    direction    = int(setup.get("direction") or 1)
    entry_idx    = int(setup.get("entry_idx") or 0)
    entry_price  = float(setup.get("entry_underlying") or 0.0)
    stop_price   = float(setup.get("stop_underlying") or 0.0)
    t1_price     = float(setup.get("t1_price") or (entry_price * (1 + cfg.t1_rr * 0.02)))
    bar1_low     = float(setup.get("orb_low") or stop_price)
    entry_ts     = setup.get("entry_ts")

    if entry_price <= 0 or stop_price <= 0:
        return None

    risk = entry_price - stop_price
    if risk <= 0:
        return None

    trailing_trigger_price = entry_price + risk * cfg.trailing_trigger_rr
    exit_cutoff = time(15, 55)  # hard EOD

    t1_hit       = False
    t1_exit_price: Optional[float] = None
    trailing_active = False
    dynamic_stop    = stop_price
    trailing_stop   = stop_price  # tracks previous bar low once active

    # rolling volume for dry-up
    vol_window = max(cfg.volume_ma_window, 1)

    for idx in range(entry_idx + 1, len(session_bars)):
        bar        = session_bars[idx]
        bar_time   = _to_et_time(bar["ts"])
        open_p     = float(bar.get("open")   or 0.0)
        high_p     = float(bar.get("high")   or 0.0)
        low_p      = float(bar.get("low")    or 0.0)
        close_p    = float(bar.get("close")  or 0.0)
        volume     = float(bar.get("volume") or 0.0)

        if open_p <= 0 or high_p <= 0 or low_p <= 0 or close_p <= 0:
            continue

        elapsed_minutes: Optional[float] = None
        if isinstance(entry_ts, datetime) and isinstance(bar.get("ts"), datetime):
            elapsed_minutes = (bar["ts"] - entry_ts).total_seconds() / 60.0

        effective_stop = max(dynamic_stop, trailing_stop) if trailing_active else dynamic_stop

        # ---- Priority 1: stop loss ----------------------------------------
        if low_p <= effective_stop:
            fill = min(effective_stop, open_p) if open_p > 0 else effective_stop
            # apply stop slippage pessimistically
            fill = fill * (1.0 - cfg.stop_slippage_pct)
            return _blended_exit(
                idx=idx, bar=bar,
                t1_hit=t1_hit, t1_exit_price=t1_exit_price,
                t2_price=fill, t2_reason="stop_loss",
                cfg=cfg,
            )

        # ---- Priority 2: T1 hit (first time only) -------------------------
        if not t1_hit and high_p >= t1_price:
            t1_hit = True
            t1_exit_price = t1_price
            dynamic_stop = entry_price          # move stop to break-even
            trailing_active = True
            trailing_stop = low_p               # init trailing under this bar

        # Update trailing stop to previous bar low once active
        if trailing_active:
            trailing_stop = max(trailing_stop, low_p)

        # ---- Priority 3: close below bar1_low (momentum failure) ----------
        if close_p < bar1_low:
            return _blended_exit(
                idx=idx, bar=bar,
                t1_hit=t1_hit, t1_exit_price=t1_exit_price,
                t2_price=close_p, t2_reason="bar1_low_breach",
                cfg=cfg,
            )

        # ---- Priority 4: volume dry-up ------------------------------------
        if idx >= vol_window:
            lookback_vols = [
                float(session_bars[i].get("volume") or 0)
                for i in range(idx - vol_window, idx)
            ]
            avg_vol = sum(lookback_vols) / vol_window if lookback_vols else 0.0
            if avg_vol > 0 and volume < cfg.volume_dry_up_multiple * avg_vol:
                return _blended_exit(
                    idx=idx, bar=bar,
                    t1_hit=t1_hit, t1_exit_price=t1_exit_price,
                    t2_price=close_p, t2_reason="volume_dry_up",
                    cfg=cfg,
                )

        # ---- Priority 5: max hold time ------------------------------------
        if (
            cfg.max_hold_minutes > 0
            and elapsed_minutes is not None
            and elapsed_minutes >= cfg.max_hold_minutes
        ):
            return _blended_exit(
                idx=idx, bar=bar,
                t1_hit=t1_hit, t1_exit_price=t1_exit_price,
                t2_price=close_p, t2_reason="max_hold_time",
                cfg=cfg,
            )

        # ---- Priority 6: T2 trailing stop ---------------------------------
        if trailing_active and low_p <= trailing_stop:
            fill = min(trailing_stop, open_p) if open_p > 0 else trailing_stop
            return _blended_exit(
                idx=idx, bar=bar,
                t1_hit=t1_hit, t1_exit_price=t1_exit_price,
                t2_price=fill, t2_reason="trailing_stop",
                cfg=cfg,
            )

        # ---- EOD hard exit ------------------------------------------------
        if bar_time >= exit_cutoff:
            return _blended_exit(
                idx=idx, bar=bar,
                t1_hit=t1_hit, t1_exit_price=t1_exit_price,
                t2_price=close_p, t2_reason="time_exit",
                cfg=cfg,
            )

    # Session ended with open position
    last = session_bars[-1]
    last_close = float(last.get("close") or 0.0)
    if last_close <= 0:
        return None
    return _blended_exit(
        idx=len(session_bars) - 1, bar=last,
        t1_hit=t1_hit, t1_exit_price=t1_exit_price,
        t2_price=last_close, t2_reason="session_close",
        cfg=cfg,
    )


def _blended_exit(
    *,
    idx: int,
    bar: Dict[str, Any],
    t1_hit: bool,
    t1_exit_price: Optional[float],
    t2_price: float,
    t2_reason: str,
    cfg: LFCMConfig,
) -> Dict[str, Any]:
    """Return a single blended exit record.

    If T1 was hit: exit_underlying = t1_size_pct × t1_price + (1-t1_size_pct) × t2_price.
    Otherwise:    exit_underlying = t2_price.
    """
    if t1_hit and t1_exit_price is not None:
        blended = cfg.t1_size_pct * t1_exit_price + (1.0 - cfg.t1_size_pct) * t2_price
        exit_reason = f"t1_then_{t2_reason}"
    else:
        blended = t2_price
        exit_reason = t2_reason

    return {
        "exit_idx":        idx,
        "exit_ts":         bar["ts"],
        "exit_underlying": blended,
        "exit_reason":     exit_reason,
        "lfcm_t1_hit":     t1_hit,
        "lfcm_t1_price":   t1_exit_price,
        "lfcm_t2_price":   t2_price,
        "lfcm_t2_reason":  t2_reason,
    }
