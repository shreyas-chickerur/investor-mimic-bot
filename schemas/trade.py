from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class TradeType(str, Enum):
    BUY = "buy"
    SELL = "sell"


class TradeBase(BaseModel):
    portfolio_id: int
    security_id: int
    type: TradeType
    quantity: float = Field(..., gt=0, description="The quantity of the security to trade")
    price: float = Field(..., gt=0, description="The price per unit of the security")
    total_amount: float = Field(..., gt=0, description="The total amount of the trade")


class TradeCreate(TradeBase):
    pass


class TradeUpdate(BaseModel):
    price: Optional[float] = None
    quantity: Optional[float] = None
    total_amount: Optional[float] = None


class TradeInDB(TradeBase):
    id: int
    timestamp: datetime

    model_config = ConfigDict(
        from_attributes=True, arbitrary_types_allowed=True  # Replaces orm_mode in Pydantic v2
    )


class PositionBase(BaseModel):
    portfolio_id: int
    security_id: int
    quantity: float
    average_cost: float
    current_value: float
    last_updated: datetime


class PositionInDB(PositionBase):
    id: int
    security: Dict[str, Any] = {}

    model_config = ConfigDict(
        from_attributes=True, arbitrary_types_allowed=True  # Replaces orm_mode in Pydantic v2
    )


class TradeExecution(BaseModel):
    portfolio_id: int
    symbol: str
    quantity: float
    side: str  # 'buy' or 'sell'
    order_type: str = "market"
    time_in_force: str = "day"


class PortfolioPerformance(BaseModel):
    portfolio_id: int
    total_invested: float
    total_current_value: float
    total_unrealized_pnl: float
    total_unrealized_pnl_pct: float
    positions_count: int


class TradeHistory(BaseModel):
    id: int
    symbol: str
    security_name: str
    type: str
    quantity: float
    price: float
    total_amount: float
    timestamp: str
