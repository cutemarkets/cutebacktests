from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class ProxyLeveragePricer:
    """
    First-pass options pricing proxy.
    Maps underlying return into option return with leverage + theta drag.
    """

    base_leverage: float = 3.0
    theta_per_day: float = 0.006
    iv_penalty_threshold: float = 0.45
    max_gain: float = 4.0

    def option_return(
        self,
        direction: int,
        underlying_return: float,
        days_held: int,
        conviction: float,
        iv: Optional[float] = None,
    ) -> float:
        conviction_multiplier = 0.8 + 0.4 * max(0.0, min(1.0, conviction))
        leverage = self.base_leverage * conviction_multiplier

        gross = leverage * direction * underlying_return
        theta_drag = self.theta_per_day * max(days_held, 1)

        iv_drag = 0.0
        if iv is not None and iv > self.iv_penalty_threshold:
            iv_drag = (iv - self.iv_penalty_threshold) * 0.2

        value = gross - theta_drag - iv_drag
        if value < -1.0:
            return -1.0
        if value > self.max_gain:
            return self.max_gain
        return value
