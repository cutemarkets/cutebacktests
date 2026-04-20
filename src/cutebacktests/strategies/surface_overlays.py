from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .daily_forecasts import _cap_value, _safe_float


@dataclass(frozen=True)
class SurfaceOverlayDecision:
    forecast_scale_multiplier: float = 1.0
    veto_new_trade: bool = False
    ivrv_zscore: Optional[float] = None
    term_structure_slope: Optional[float] = None
    skew_value: Optional[float] = None
    scale_up: bool = False
    scale_down: bool = False
    veto_reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "forecast_scale_multiplier": float(self.forecast_scale_multiplier),
            "veto_new_trade": bool(self.veto_new_trade),
            "ivrv_zscore": self.ivrv_zscore,
            "term_structure_slope": self.term_structure_slope,
            "skew_value": self.skew_value,
            "scale_up": bool(self.scale_up),
            "scale_down": bool(self.scale_down),
            "veto_reason": str(self.veto_reason or ""),
        }


def apply_surface_overlay_to_forecast(
    *,
    base_forecast: float,
    chain_snapshot: Sequence[Dict[str, Any]],
    realized_vol_annualized: Optional[float],
    option_type: str,
    forecast_cap: float = 20.0,
    ivrv_scale_down_zscore: float = 1.0,
    ivrv_scale_up_zscore: float = -0.5,
    ivrv_scale_down_multiplier: float = 0.50,
    ivrv_scale_up_multiplier: float = 1.15,
    term_structure_veto_threshold: float = 0.04,
    skew_veto_threshold: float = 0.12,
) -> SurfaceOverlayDecision:
    front_iv = _median_iv(chain_snapshot, min_dte=21, max_dte=35)
    back_iv = _median_iv(chain_snapshot, min_dte=50, max_dte=75)
    skew_value = _skew_value(chain_snapshot, option_type=option_type)
    term_structure_slope = None
    if front_iv is not None and back_iv is not None:
        term_structure_slope = front_iv - back_iv
    ivrv_zscore = None
    if front_iv is not None and realized_vol_annualized is not None and realized_vol_annualized > 0.0:
        ivrv_zscore = (front_iv - realized_vol_annualized) / realized_vol_annualized

    scale = 1.0
    scale_up = False
    scale_down = False
    veto = False
    veto_reason = ""
    if ivrv_zscore is not None:
        if ivrv_zscore > float(ivrv_scale_down_zscore):
            scale = min(scale, float(ivrv_scale_down_multiplier))
            scale_down = True
        elif ivrv_zscore < float(ivrv_scale_up_zscore):
            scale = max(scale, float(ivrv_scale_up_multiplier))
            scale_up = True
    if term_structure_slope is not None and term_structure_slope > float(term_structure_veto_threshold):
        veto = True
        veto_reason = "term_structure_rich_front"
    if skew_value is not None and skew_value > float(skew_veto_threshold):
        veto = True
        veto_reason = veto_reason or "adverse_skew"
    adjusted = _cap_value(float(base_forecast) * scale, forecast_cap)
    if abs(adjusted) > abs(float(base_forecast)) and abs(float(base_forecast)) >= abs(float(forecast_cap)):
        scale_up = False
    return SurfaceOverlayDecision(
        forecast_scale_multiplier=float(scale),
        veto_new_trade=bool(veto),
        ivrv_zscore=ivrv_zscore,
        term_structure_slope=term_structure_slope,
        skew_value=skew_value,
        scale_up=bool(scale_up),
        scale_down=bool(scale_down),
        veto_reason=veto_reason,
    )


def _median_iv(chain_snapshot: Sequence[Dict[str, Any]], *, min_dte: int, max_dte: int) -> Optional[float]:
    values: List[float] = []
    for row in chain_snapshot:
        dte = _safe_float(row.get("dte"))
        if dte is None:
            expiration = row.get("expiration")
            day = row.get("day")
            if day is not None and expiration is not None:
                try:
                    dte = float((expiration.date() if hasattr(expiration, "date") else expiration) - day).days
                except Exception:
                    dte = None
        if dte is None or dte < float(min_dte) or dte > float(max_dte):
            continue
        iv = _safe_float(row.get("iv"))
        if iv is None or iv <= 0.0:
            continue
        values.append(float(iv))
    if not values:
        return None
    values.sort()
    middle = len(values) // 2
    if len(values) % 2 == 1:
        return values[middle]
    return (values[middle - 1] + values[middle]) / 2.0


def _skew_value(chain_snapshot: Sequence[Dict[str, Any]], *, option_type: str) -> Optional[float]:
    atm_values: List[float] = []
    wing_values: List[float] = []
    normalized_type = str(option_type or "call").strip().lower()
    for row in chain_snapshot:
        row_type = str(row.get("option_type") or "").strip().lower()
        iv = _safe_float(row.get("iv"))
        abs_delta = abs(float(row.get("delta") or 0.0)) if row.get("delta") is not None else None
        if iv is None or iv <= 0.0 or abs_delta is None or abs_delta <= 0.0:
            continue
        if 0.45 <= abs_delta <= 0.55:
            atm_values.append(float(iv))
        if row_type == normalized_type and 0.20 <= abs_delta <= 0.30:
            wing_values.append(float(iv))
    if not atm_values or not wing_values:
        return None
    atm_values.sort()
    wing_values.sort()
    atm_iv = atm_values[len(atm_values) // 2]
    wing_iv = wing_values[len(wing_values) // 2]
    if atm_iv <= 0.0:
        return None
    return max((wing_iv - atm_iv) / atm_iv, 0.0)
