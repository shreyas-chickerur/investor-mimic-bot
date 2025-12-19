from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class RiskControls(BaseModel):
    # Position sizing
    max_position_size_pct: float = Field(
        0.05,  # Max 5% of portfolio in any single position
        ge=0.01,  # At least 1%
        le=0.20,  # At most 20%
        description="Maximum percentage of portfolio value for a single position",
    )

    # Order limits
    max_orders_per_day: int = Field(
        3,  # Maximum number of orders per day
        ge=1,
        le=10,
        description="Maximum number of orders to place in a single day",
    )

    # Cash buffer (in dollars)
    cash_buffer: Decimal = Field(
        Decimal("1000.00"),  # Keep $1000 in cash
        ge=Decimal("0.00"),
        description="Minimum cash balance to maintain",
    )

    # Loss limits
    daily_loss_limit_pct: float = Field(
        0.02,  # 2% max daily loss
        ge=0.01,
        le=0.10,
        description="Maximum allowed daily portfolio loss percentage",
    )

    # Position entry/exit limits
    max_trade_size_pct: float = Field(
        0.10,  # Max 10% of average daily volume
        ge=0.01,
        le=0.25,
        description="Maximum trade size as percentage of average daily volume",
    )

    # Market hours restrictions
    trade_only_during_market_hours: bool = True

    # Kill switch
    trading_enabled: bool = Field(True, description="Global kill switch to enable/disable trading")

    # Semi-auto mode
    require_manual_confirmation: bool = Field(
        True, description="Whether to require manual confirmation before executing trades"
    )

    # Funding rules
    allocation_percent: float = Field(
        1.0,  # 100% of available funds (after buffer)
        ge=0.0,
        le=1.0,
        description="Percentage of available funds to allocate to investments",
    )
    min_investment: Decimal = Field(
        Decimal("100.00"), ge=Decimal("0.00"), description="Minimum investment amount per position"
    )
    round_to_nearest: Decimal = Field(
        Decimal("1.00"),
        ge=Decimal("0.01"),
        description="Round investment amounts to nearest increment",
    )


# Default risk controls
default_risk_controls = RiskControls()
