from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime
import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np


REGIME_TRENDING = "trending"
REGIME_SIDEWAYS = "sideways"
REGIME_NEUTRAL = "neutral"
REGIME_UNKNOWN = "unknown"
REGIME_LABELS = (REGIME_TRENDING, REGIME_SIDEWAYS, REGIME_NEUTRAL, REGIME_UNKNOWN)

# Intraday + macro composite states for regime_v2.
REGIME_V2_TREND_UP = "trend_up"
REGIME_V2_TREND_DOWN = "trend_down"
REGIME_V2_RANGE_LOW_VOL = "range_low_vol"
REGIME_V2_RANGE_HIGH_VOL = "range_high_vol"
REGIME_V2_EVENT_GAP = "event_gap"
REGIME_V2_TRANSITION = "transition"
REGIME_V2_DEFENSIVE = "defensive"
REGIME_V2_UNKNOWN = "unknown"
REGIME_V2_STATES = (
    REGIME_V2_TREND_UP,
    REGIME_V2_TREND_DOWN,
    REGIME_V2_RANGE_LOW_VOL,
    REGIME_V2_RANGE_HIGH_VOL,
    REGIME_V2_EVENT_GAP,
    REGIME_V2_TRANSITION,
    REGIME_V2_DEFENSIVE,
    REGIME_V2_UNKNOWN,
)


@dataclass(frozen=True)
class RegimeModelConfig:
    enabled: bool = True
    model: str = "threshold"  # threshold | er | hmm
    lookback_days: int = 20
    trend_abs_return_min: float = 0.03
    trend_drift_to_range_min: float = 0.55
    sideways_abs_return_max: float = 0.015
    sideways_range_max: float = 0.045
    er_trend_min: float = 0.45
    er_sideways_max: float = 0.20
    hmm_states: int = 3
    hmm_min_train_days: int = 90
    hmm_retrain_interval_days: int = 5
    hmm_max_iter: int = 25
    random_seed: int = 42


@dataclass(frozen=True)
class RegimeV2Config:
    enabled: bool = False
    min_intraday_bars: int = 30
    intraday_er_trend_min: float = 0.45
    intraday_er_sideways_max: float = 0.20
    intraday_direction_abs_return_min: float = 0.001
    range_low_vol_max_pct: float = 0.012
    range_high_vol_min_pct: float = 0.020
    event_gap_abs_return_min: float = 0.006
    event_gap_min_range_pct: float = 0.004
    min_confidence: float = 0.35


def normalize_regime_label(value: Any) -> str:
    label = str(value or "").strip().lower()
    if label in {REGIME_TRENDING, "trend", "trending_up", "trending_down", "breakout", "momentum"}:
        return REGIME_TRENDING
    if label in {REGIME_SIDEWAYS, "sideway", "choppy", "range", "mean_reversion"}:
        return REGIME_SIDEWAYS
    if label in {REGIME_NEUTRAL, "transition", "mixed"}:
        return REGIME_NEUTRAL
    if label in {REGIME_UNKNOWN, "", "na", "n/a", "none", "null"}:
        return REGIME_UNKNOWN
    return REGIME_UNKNOWN


def empty_regime_counts() -> Dict[str, int]:
    return {
        REGIME_TRENDING: 0,
        REGIME_SIDEWAYS: 0,
        REGIME_NEUTRAL: 0,
        REGIME_UNKNOWN: 0,
    }


def regime_counts(regime_map: Dict[date, str]) -> Dict[str, int]:
    counts = empty_regime_counts()
    for value in regime_map.values():
        label = normalize_regime_label(value)
        counts[label] = int(counts.get(label, 0)) + 1
    return counts


def build_day_regime_map(
    *,
    daily_rows: Sequence[Dict[str, Any]],
    config: RegimeModelConfig,
) -> Tuple[Dict[date, str], Dict[str, Any]]:
    model = str(config.model or "threshold").strip().lower()
    if not bool(config.enabled):
        return {}, {
            "enabled": False,
            "model": model,
            "status": "disabled",
            "label_counts": empty_regime_counts(),
            "known_days": 0,
            "unknown_days": 0,
            "config": asdict(config),
        }

    if model == "threshold":
        mapping = build_threshold_regime_map(
            daily_rows=daily_rows,
            lookback_days=int(config.lookback_days),
            trend_abs_return_min=float(config.trend_abs_return_min),
            trend_drift_to_range_min=float(config.trend_drift_to_range_min),
            sideways_abs_return_max=float(config.sideways_abs_return_max),
            sideways_range_max=float(config.sideways_range_max),
        )
        counts = regime_counts(mapping)
        return mapping, {
            "enabled": True,
            "model": model,
            "status": "ok",
            "label_counts": counts,
            "known_days": int(sum(counts[label] for label in (REGIME_TRENDING, REGIME_SIDEWAYS, REGIME_NEUTRAL))),
            "unknown_days": int(counts.get(REGIME_UNKNOWN, 0)),
            "config": asdict(config),
        }

    if model == "er":
        mapping = build_er_regime_map(
            daily_rows=daily_rows,
            lookback_days=int(config.lookback_days),
            trend_abs_return_min=float(config.trend_abs_return_min),
            sideways_abs_return_max=float(config.sideways_abs_return_max),
            er_trend_min=float(config.er_trend_min),
            er_sideways_max=float(config.er_sideways_max),
        )
        counts = regime_counts(mapping)
        return mapping, {
            "enabled": True,
            "model": model,
            "status": "ok",
            "label_counts": counts,
            "known_days": int(sum(counts[label] for label in (REGIME_TRENDING, REGIME_SIDEWAYS, REGIME_NEUTRAL))),
            "unknown_days": int(counts.get(REGIME_UNKNOWN, 0)),
            "config": asdict(config),
        }

    if model == "hmm":
        mapping, hmm_meta = build_hmm_regime_map(
            daily_rows=daily_rows,
            lookback_days=int(config.lookback_days),
            states=int(config.hmm_states),
            min_train_days=int(config.hmm_min_train_days),
            retrain_interval_days=int(config.hmm_retrain_interval_days),
            max_iter=int(config.hmm_max_iter),
            seed=int(config.random_seed),
        )
        counts = regime_counts(mapping)
        meta = {
            "enabled": True,
            "model": model,
            "status": "ok",
            "label_counts": counts,
            "known_days": int(sum(counts[label] for label in (REGIME_TRENDING, REGIME_SIDEWAYS, REGIME_NEUTRAL))),
            "unknown_days": int(counts.get(REGIME_UNKNOWN, 0)),
            "config": asdict(config),
        }
        meta.update(hmm_meta)
        return mapping, meta

    return {}, {
        "enabled": True,
        "model": model,
        "status": "unsupported_model",
        "label_counts": empty_regime_counts(),
        "known_days": 0,
        "unknown_days": 0,
        "config": asdict(config),
    }


def build_threshold_regime_map(
    *,
    daily_rows: Sequence[Dict[str, Any]],
    lookback_days: int,
    trend_abs_return_min: float,
    trend_drift_to_range_min: float,
    sideways_abs_return_max: float,
    sideways_range_max: float,
) -> Dict[date, str]:
    ordered_days, closes = _extract_days_and_closes(daily_rows)
    if not ordered_days:
        return {}
    lookback = max(int(lookback_days), 2)
    out: Dict[date, str] = {}
    for idx, day in enumerate(ordered_days):
        if idx < lookback:
            out[day] = REGIME_UNKNOWN
            continue
        window = closes[idx - lookback : idx]
        start_close = float(window[0])
        end_close = float(window[-1])
        if start_close <= 0.0 or end_close <= 0.0:
            out[day] = REGIME_UNKNOWN
            continue

        drift = (end_close / start_close) - 1.0
        max_close = max(window)
        min_close = min(window)
        trailing_range = ((max_close - min_close) / start_close) if start_close > 0 else 0.0
        drift_to_range = abs(drift) / max(trailing_range, 1e-9)

        if abs(drift) >= float(trend_abs_return_min) and drift_to_range >= float(trend_drift_to_range_min):
            out[day] = REGIME_TRENDING
        elif abs(drift) <= float(sideways_abs_return_max) and trailing_range <= float(sideways_range_max):
            out[day] = REGIME_SIDEWAYS
        else:
            out[day] = REGIME_NEUTRAL
    return out


def build_er_regime_map(
    *,
    daily_rows: Sequence[Dict[str, Any]],
    lookback_days: int,
    trend_abs_return_min: float,
    sideways_abs_return_max: float,
    er_trend_min: float,
    er_sideways_max: float,
) -> Dict[date, str]:
    ordered_days, closes = _extract_days_and_closes(daily_rows)
    if not ordered_days:
        return {}
    lookback = max(int(lookback_days), 2)
    out: Dict[date, str] = {}
    for idx, day in enumerate(ordered_days):
        if idx < lookback:
            out[day] = REGIME_UNKNOWN
            continue
        window = closes[idx - lookback : idx]
        start_close = float(window[0])
        end_close = float(window[-1])
        if start_close <= 0.0 or end_close <= 0.0:
            out[day] = REGIME_UNKNOWN
            continue
        drift = (end_close / start_close) - 1.0
        travel = float(np.abs(np.diff(np.asarray(window, dtype=float))).sum())
        if travel <= 0:
            out[day] = REGIME_SIDEWAYS if abs(drift) <= float(sideways_abs_return_max) else REGIME_NEUTRAL
            continue
        er = abs(end_close - start_close) / travel
        if er >= float(er_trend_min) and abs(drift) >= float(trend_abs_return_min):
            out[day] = REGIME_TRENDING
        elif er <= float(er_sideways_max) and abs(drift) <= float(sideways_abs_return_max):
            out[day] = REGIME_SIDEWAYS
        else:
            out[day] = REGIME_NEUTRAL
    return out


def build_hmm_regime_map(
    *,
    daily_rows: Sequence[Dict[str, Any]],
    lookback_days: int,
    states: int,
    min_train_days: int,
    retrain_interval_days: int,
    max_iter: int,
    seed: int,
) -> Tuple[Dict[date, str], Dict[str, Any]]:
    ordered_days, closes = _extract_days_and_closes(daily_rows)
    if len(ordered_days) < 2:
        return {}, {
            "hmm_refits": 0,
            "hmm_train_windows": 0,
            "hmm_states": int(max(states, 2)),
            "hmm_status": "insufficient_days",
        }

    returns = np.full(len(ordered_days), np.nan, dtype=float)
    for idx in range(1, len(ordered_days)):
        prev_close = float(closes[idx - 1])
        cur_close = float(closes[idx])
        if prev_close <= 0.0 or cur_close <= 0.0:
            continue
        returns[idx] = math.log(cur_close / prev_close)

    lookback = max(int(lookback_days), 20)
    min_train = max(int(min_train_days), 20)
    # Use a training window that can actually satisfy min_train. The previous
    # behavior used lookback as a hard cap, which made default configs
    # (lookback=20, min_train=90) impossible and produced all-unknown labels.
    train_window = max(lookback, min_train)
    retrain_every = max(int(retrain_interval_days), 1)
    k_states = max(int(states), 2)
    max_fit_iter = max(int(max_iter), 3)

    out: Dict[date, str] = {day: REGIME_UNKNOWN for day in ordered_days}
    fit_model: Optional[Dict[str, Any]] = None
    state_to_label: Dict[int, str] = {}
    last_filtered: Optional[np.ndarray] = None
    last_fit_idx = -1
    refit_count = 0
    train_windows = 0

    for idx, day in enumerate(ordered_days):
        if idx <= 1:
            out[day] = REGIME_UNKNOWN
            continue

        train_start = max(1, idx - train_window)
        train_series = np.asarray(returns[train_start:idx], dtype=float)
        train_series = train_series[np.isfinite(train_series)]
        if train_series.size < min_train:
            out[day] = REGIME_UNKNOWN
            continue

        train_windows += 1
        need_refit = fit_model is None or (idx - last_fit_idx) >= retrain_every
        if need_refit:
            fit_model = _fit_hmm_hard_em(
                train_values=train_series,
                states=k_states,
                max_iter=max_fit_iter,
                seed=seed + idx,
            )
            if fit_model is None:
                out[day] = REGIME_UNKNOWN
                last_filtered = None
                continue
            state_to_label = _map_hmm_states_to_regimes(
                means=np.asarray(fit_model["means"], dtype=float),
                variances=np.asarray(fit_model["variances"], dtype=float),
            )
            last_filtered = np.asarray(fit_model["filtered"][-1], dtype=float)
            last_fit_idx = idx
            refit_count += 1

        if fit_model is None or last_filtered is None:
            out[day] = REGIME_UNKNOWN
            continue

        transitions = np.asarray(fit_model["transitions"], dtype=float)
        means = np.asarray(fit_model["means"], dtype=float)
        variances = np.asarray(fit_model["variances"], dtype=float)

        prior = np.dot(last_filtered, transitions)
        if not np.isfinite(prior).all() or float(prior.sum()) <= 0:
            prior = np.full(k_states, 1.0 / float(k_states), dtype=float)
        else:
            prior = prior / float(prior.sum())
        state = int(np.argmax(prior))
        out[day] = normalize_regime_label(state_to_label.get(state))

        obs = float(returns[idx])
        if math.isfinite(obs):
            emission = _gaussian_emission_probs(obs, means, variances)
            posterior = prior * emission
            total = float(posterior.sum())
            if total <= 0:
                posterior = np.full(k_states, 1.0 / float(k_states), dtype=float)
            else:
                posterior = posterior / total
            last_filtered = posterior
        else:
            last_filtered = prior

    return out, {
        "hmm_refits": int(refit_count),
        "hmm_train_windows": int(train_windows),
        "hmm_states": int(k_states),
        "hmm_train_window_days": int(train_window),
        "hmm_min_train_days": int(min_train),
        "hmm_status": "ok" if refit_count > 0 else "insufficient_train_windows",
    }


def _extract_days_and_closes(daily_rows: Sequence[Dict[str, Any]]) -> Tuple[List[date], List[float]]:
    dedup: Dict[date, float] = {}
    for row in daily_rows:
        if not isinstance(row, dict):
            continue
        day = _coerce_day(row.get("day"))
        if day is None:
            day = _coerce_day(row.get("ts"))
        close = _safe_float(row.get("close"))
        if day is None or close is None or close <= 0.0:
            continue
        dedup[day] = float(close)
    ordered_days = sorted(dedup.keys())
    closes = [float(dedup[day]) for day in ordered_days]
    return ordered_days, closes


def _coerce_day(value: Any) -> Optional[date]:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except Exception:
        pass
    try:
        return datetime.fromisoformat(raw[:10]).date()
    except Exception:
        return None


def _safe_float(value: Any) -> Optional[float]:
    try:
        out = float(value)
    except Exception:
        return None
    if not math.isfinite(out):
        return None
    return out


def _gaussian_emission_probs(observation: float, means: np.ndarray, variances: np.ndarray) -> np.ndarray:
    obs = float(observation)
    var = np.maximum(np.asarray(variances, dtype=float), 1e-8)
    std = np.sqrt(var)
    z = (obs - np.asarray(means, dtype=float)) / std
    norm = 1.0 / (np.sqrt(2.0 * np.pi) * std)
    probs = norm * np.exp(-0.5 * np.square(z))
    probs = np.maximum(probs, 1e-15)
    return probs


def _forward_filter(
    *,
    values: np.ndarray,
    pi: np.ndarray,
    transitions: np.ndarray,
    means: np.ndarray,
    variances: np.ndarray,
) -> np.ndarray:
    t_count = int(values.shape[0])
    k_states = int(pi.shape[0])
    filtered = np.zeros((t_count, k_states), dtype=float)
    emission0 = _gaussian_emission_probs(float(values[0]), means, variances)
    alpha = np.asarray(pi, dtype=float) * emission0
    total = float(alpha.sum())
    if total <= 0:
        alpha = np.full(k_states, 1.0 / float(k_states), dtype=float)
    else:
        alpha = alpha / total
    filtered[0] = alpha
    for idx in range(1, t_count):
        prior = np.dot(alpha, transitions)
        prior_sum = float(prior.sum())
        if prior_sum <= 0:
            prior = np.full(k_states, 1.0 / float(k_states), dtype=float)
        else:
            prior = prior / prior_sum
        emission = _gaussian_emission_probs(float(values[idx]), means, variances)
        alpha = prior * emission
        total = float(alpha.sum())
        if total <= 0:
            alpha = np.full(k_states, 1.0 / float(k_states), dtype=float)
        else:
            alpha = alpha / total
        filtered[idx] = alpha
    return filtered


def _viterbi_decode(
    *,
    values: np.ndarray,
    pi: np.ndarray,
    transitions: np.ndarray,
    means: np.ndarray,
    variances: np.ndarray,
) -> np.ndarray:
    t_count = int(values.shape[0])
    k_states = int(pi.shape[0])
    log_pi = np.log(np.maximum(np.asarray(pi, dtype=float), 1e-15))
    log_trans = np.log(np.maximum(np.asarray(transitions, dtype=float), 1e-15))
    deltas = np.zeros((t_count, k_states), dtype=float)
    psi = np.zeros((t_count, k_states), dtype=int)

    first_emission = np.log(_gaussian_emission_probs(float(values[0]), means, variances))
    deltas[0] = log_pi + first_emission
    for idx in range(1, t_count):
        emission = np.log(_gaussian_emission_probs(float(values[idx]), means, variances))
        for state in range(k_states):
            candidates = deltas[idx - 1] + log_trans[:, state]
            best_prev = int(np.argmax(candidates))
            deltas[idx, state] = float(candidates[best_prev]) + float(emission[state])
            psi[idx, state] = best_prev

    states = np.zeros(t_count, dtype=int)
    states[-1] = int(np.argmax(deltas[-1]))
    for idx in range(t_count - 2, -1, -1):
        states[idx] = int(psi[idx + 1, states[idx + 1]])
    return states


def _fit_hmm_hard_em(
    *,
    train_values: np.ndarray,
    states: int,
    max_iter: int,
    seed: int,
) -> Optional[Dict[str, Any]]:
    values = np.asarray(train_values, dtype=float)
    values = values[np.isfinite(values)]
    if values.size < max(12, int(states) * 5):
        return None

    k_states = max(int(states), 2)
    rng = np.random.default_rng(int(seed))
    quantiles = np.linspace(0.0, 1.0, num=k_states + 2)[1:-1]
    means = np.quantile(values, quantiles)
    if np.unique(np.round(means, 10)).size < k_states:
        means = means + rng.normal(0.0, float(np.std(values) or 1e-3) * 0.01, size=k_states)
    variances = np.full(k_states, max(float(np.var(values)), 1e-6), dtype=float)
    assignments = np.argmin(np.abs(values[:, None] - means[None, :]), axis=1).astype(int)

    transitions = np.full((k_states, k_states), 1.0 / float(k_states), dtype=float)
    pi = np.full(k_states, 1.0 / float(k_states), dtype=float)

    for _ in range(max(int(max_iter), 3)):
        for state in range(k_states):
            mask = assignments == state
            if np.any(mask):
                vals = values[mask]
                means[state] = float(np.mean(vals))
                variances[state] = max(float(np.var(vals)), 1e-6)

        trans_counts = np.full((k_states, k_states), 1e-2, dtype=float)
        for prev_state, next_state in zip(assignments[:-1], assignments[1:]):
            trans_counts[int(prev_state), int(next_state)] += 1.0
        transitions = trans_counts / np.maximum(trans_counts.sum(axis=1, keepdims=True), 1e-12)

        pi_counts = np.full(k_states, 1e-2, dtype=float)
        pi_counts[int(assignments[0])] += 1.0
        pi = pi_counts / np.maximum(float(pi_counts.sum()), 1e-12)

        decoded = _viterbi_decode(
            values=values,
            pi=pi,
            transitions=transitions,
            means=means,
            variances=variances,
        )
        if np.array_equal(decoded, assignments):
            assignments = decoded
            break
        assignments = decoded

    filtered = _forward_filter(
        values=values,
        pi=pi,
        transitions=transitions,
        means=means,
        variances=variances,
    )
    return {
        "pi": pi,
        "transitions": transitions,
        "means": means,
        "variances": variances,
        "states": assignments,
        "filtered": filtered,
    }


def _map_hmm_states_to_regimes(*, means: np.ndarray, variances: np.ndarray) -> Dict[int, str]:
    k_states = int(len(means))
    if k_states <= 0:
        return {}
    variances = np.maximum(np.asarray(variances, dtype=float), 1e-8)
    means = np.asarray(means, dtype=float)
    trend_score = np.abs(means) / np.sqrt(variances)

    sideways_state = int(np.argmin(variances))
    trend_order = list(np.argsort(-trend_score))
    trending_state = int(trend_order[0]) if trend_order else sideways_state
    if trending_state == sideways_state and len(trend_order) > 1:
        trending_state = int(trend_order[1])

    out = {state: REGIME_NEUTRAL for state in range(k_states)}
    out[sideways_state] = REGIME_SIDEWAYS
    out[trending_state] = REGIME_TRENDING
    return out


def classify_intraday_macro_regime(
    *,
    session_rows: Sequence[Dict[str, Any]],
    previous_close: Optional[float],
    macro_label: Any,
    config: RegimeV2Config,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "enabled": bool(config.enabled),
        "status": "disabled",
        "state": REGIME_V2_UNKNOWN,
        "route_state": REGIME_V2_UNKNOWN,
        "confidence": 0.0,
        "macro_label": normalize_regime_label(macro_label),
        "intraday_label": REGIME_UNKNOWN,
        "intraday_er": None,
        "intraday_return": None,
        "intraday_range_pct": None,
        "gap_return": None,
    }
    if not bool(config.enabled):
        return out

    points = _extract_intraday_points(session_rows)
    if int(points["closes"].size) < max(int(config.min_intraday_bars), 2):
        out["status"] = "insufficient_bars"
        out["route_state"] = REGIME_V2_DEFENSIVE
        return out

    open_price = float(points["open"])
    close_price = float(points["closes"][-1])
    if open_price <= 0.0 or close_price <= 0.0:
        out["status"] = "invalid_prices"
        out["route_state"] = REGIME_V2_DEFENSIVE
        return out

    intraday_return = (close_price / open_price) - 1.0
    intraday_high = float(np.max(points["highs"]))
    intraday_low = float(np.min(points["lows"]))
    intraday_range_pct = ((intraday_high - intraday_low) / open_price) if open_price > 0 else 0.0
    travel = float(np.abs(np.diff(points["closes"])).sum())
    er = abs(close_price - open_price) / travel if travel > 0 else 1.0

    intraday_label = REGIME_NEUTRAL
    if er >= float(config.intraday_er_trend_min):
        intraday_label = REGIME_TRENDING
    elif er <= float(config.intraday_er_sideways_max):
        intraday_label = REGIME_SIDEWAYS

    gap_return: Optional[float] = None
    prev_close = _safe_float(previous_close)
    if prev_close is not None and prev_close > 0.0:
        gap_return = (open_price / prev_close) - 1.0

    abs_dir_min = max(float(config.intraday_direction_abs_return_min), 0.0)
    direction = 0
    if intraday_return > abs_dir_min:
        direction = 1
    elif intraday_return < -abs_dir_min:
        direction = -1

    if (
        gap_return is not None
        and abs(gap_return) >= max(float(config.event_gap_abs_return_min), 0.0)
        and intraday_range_pct >= max(float(config.event_gap_min_range_pct), 0.0)
    ):
        state = REGIME_V2_EVENT_GAP
    elif intraday_label == REGIME_TRENDING:
        if direction > 0:
            state = REGIME_V2_TREND_UP
        elif direction < 0:
            state = REGIME_V2_TREND_DOWN
        else:
            state = REGIME_V2_TRANSITION
    elif intraday_label == REGIME_SIDEWAYS:
        if intraday_range_pct >= max(float(config.range_high_vol_min_pct), 0.0):
            state = REGIME_V2_RANGE_HIGH_VOL
        else:
            state = REGIME_V2_RANGE_LOW_VOL
    else:
        state = REGIME_V2_TRANSITION

    confidence = _regime_v2_confidence(
        state=state,
        macro_label=normalize_regime_label(macro_label),
        er=er,
        gap_return=gap_return,
        config=config,
    )
    route_state = state if confidence >= max(float(config.min_confidence), 0.0) else REGIME_V2_DEFENSIVE

    out.update(
        {
            "status": "ok",
            "state": state,
            "route_state": route_state,
            "confidence": confidence,
            "intraday_label": intraday_label,
            "intraday_er": float(er),
            "intraday_return": float(intraday_return),
            "intraday_range_pct": float(intraday_range_pct),
            "gap_return": float(gap_return) if gap_return is not None else None,
        }
    )
    return out


def _extract_intraday_points(session_rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    size = len(session_rows)
    closes = np.zeros(size, dtype=float)
    highs = np.zeros(size, dtype=float)
    lows = np.zeros(size, dtype=float)
    open_price = 0.0
    count = 0
    for row in session_rows:
        if not isinstance(row, dict):
            continue
        open_value = row.get("open") if "open" in row else row.get("o")
        high_value = row.get("high") if "high" in row else row.get("h")
        low_value = row.get("low") if "low" in row else row.get("l")
        close_value = row.get("close") if "close" in row else row.get("c")
        try:
            o = float(open_value)
            h = float(high_value)
            l = float(low_value)
            c = float(close_value)
        except (TypeError, ValueError):
            continue
        if o <= 0.0 or h <= 0.0 or l <= 0.0 or c <= 0.0:
            continue
        if count <= 0:
            open_price = float(o)
        closes[count] = float(c)
        highs[count] = float(h)
        lows[count] = float(l)
        count += 1
    return {
        "open": float(open_price),
        "closes": closes[:count],
        "highs": highs[:count],
        "lows": lows[:count],
    }


def _regime_v2_confidence(
    *,
    state: str,
    macro_label: str,
    er: float,
    gap_return: Optional[float],
    config: RegimeV2Config,
) -> float:
    trend_min = max(float(config.intraday_er_trend_min), 1e-6)
    side_max = max(float(config.intraday_er_sideways_max), 1e-6)
    if state == REGIME_V2_EVENT_GAP:
        gap = abs(float(gap_return or 0.0))
        base = gap / max(float(config.event_gap_abs_return_min), 1e-6)
    elif state in {REGIME_V2_TREND_UP, REGIME_V2_TREND_DOWN}:
        base = (float(er) - trend_min) / max(1.0 - trend_min, 1e-6)
    elif state in {REGIME_V2_RANGE_LOW_VOL, REGIME_V2_RANGE_HIGH_VOL}:
        base = (side_max - float(er)) / max(side_max, 1e-6)
    else:
        center = (trend_min + side_max) / 2.0
        spread = max(abs(trend_min - side_max), 1e-6)
        base = 0.5 * (1.0 - (abs(float(er) - center) / spread))

    adjustment = 0.0
    if macro_label == REGIME_TRENDING and state in {REGIME_V2_TREND_UP, REGIME_V2_TREND_DOWN}:
        adjustment += 0.10
    if macro_label == REGIME_SIDEWAYS and state in {REGIME_V2_RANGE_LOW_VOL, REGIME_V2_RANGE_HIGH_VOL}:
        adjustment += 0.10
    if macro_label == REGIME_NEUTRAL and state == REGIME_V2_TRANSITION:
        adjustment += 0.05
    if macro_label == REGIME_UNKNOWN:
        adjustment -= 0.05

    return _clamp01(base + adjustment)


def _clamp01(value: float) -> float:
    try:
        out = float(value)
    except Exception:
        return 0.0
    if out < 0.0:
        return 0.0
    if out > 1.0:
        return 1.0
    return out
