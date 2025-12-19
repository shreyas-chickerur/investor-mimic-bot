from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import List


@dataclass(frozen=True)
class TradeOrder:
    symbol: str
    side: str
    qty: Decimal
    limit_price: Decimal
    notional: Decimal


@dataclass(frozen=True)
class TradePlan:
    created_at: datetime
    total_equity: Decimal
    orders: List[TradeOrder] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)
