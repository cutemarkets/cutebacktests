from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class DisclosureEvent:
    id: str
    person: str
    ticker: str
    transaction_type: str
    amount_bucket: str
    owner: str
    traded_at: Optional[datetime]
    disclosed_at: Optional[datetime]
    source: str = "external"
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Signal:
    id: str
    disclosure_id: str
    ticker: str
    direction: int  # +1 bullish, -1 bearish
    conviction: float
    generated_at: datetime
    model_tag: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OptionContract:
    symbol: str
    underlying: str
    option_type: str  # call / put
    expiration: datetime
    strike: float
    bid: float
    ask: float
    delta: Optional[float]
    iv: Optional[float]
    open_interest: int
    volume: int
    snapshot_at: datetime

    @property
    def mid(self) -> float:
        if self.bid <= 0 and self.ask <= 0:
            return 0.0
        if self.bid <= 0:
            return self.ask
        if self.ask <= 0:
            return self.bid
        return (self.bid + self.ask) / 2.0


@dataclass
class BacktestTrade:
    trade_id: str
    signal_id: str
    ticker: str
    option_symbol: str
    entry_ts: datetime
    exit_ts: datetime
    side: str
    qty: int
    entry_price: float
    exit_price: float
    pnl: float
    return_pct: float
    status: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PaperOrder:
    local_id: str
    signal_id: str
    ticker: str
    option_symbol: str
    side: str
    qty: int
    limit_price: float
    status: str
    submitted_at: datetime
    broker_order_id: str
    raw: Dict[str, Any] = field(default_factory=dict)
