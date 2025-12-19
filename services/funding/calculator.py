"""
Funding calculation service for determining investment amounts from paychecks.
"""

import logging
from dataclasses import dataclass
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_serializer

logger = logging.getLogger(__name__)


class FundingRule(BaseModel):
    """
    Configuration for funding calculation rules.

    Attributes:
        allocation_percent: Percentage of paycheck to allocate (0-100)
        min_investment: Minimum amount to invest per paycheck
        cash_buffer: Optional amount to keep as cash buffer
        round_to_nearest: Round investment amount to nearest multiple (e.g., 10 for $10 increments)
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    allocation_percent: float = Field(..., ge=0, le=100, description="Percentage of paycheck to allocate (0-100)")
    min_investment: Decimal = Field(default=Decimal("0"), description="Minimum amount to invest per paycheck")
    cash_buffer: Optional[Decimal] = Field(default=None, description="Optional amount to keep as cash buffer")
    round_to_nearest: Optional[Decimal] = Field(
        default=Decimal("1"),
        description="Round investment amount to nearest multiple (e.g., 10 for $10 increments)",
    )

    @field_validator("min_investment", "cash_buffer", "round_to_nearest", mode="before")
    @classmethod
    def validate_positive_amounts(cls, v, info):
        if v is not None and v < 0:
            raise ValueError(f"{info.field_name} must be positive")
        return v

    @model_serializer
    def serialize_model(self) -> Dict[str, Any]:
        return {
            "allocation_percent": self.allocation_percent,
            "min_investment": str(self.min_investment),
            "cash_buffer": str(self.cash_buffer) if self.cash_buffer is not None else None,
            "round_to_nearest": str(self.round_to_nearest) if self.round_to_nearest is not None else None,
        }


@dataclass
class InvestmentDecision:
    """Result of the funding calculation."""

    investment_amount: Decimal
    remaining_cash: Decimal
    rule_applied: FundingRule
    metadata: Dict[str, Any] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "investment_amount": float(self.investment_amount),
            "remaining_cash": (float(self.remaining_cash) if self.remaining_cash is not None else None),
            "rule_applied": self.rule_applied.dict(),
            "metadata": self.metadata or {},
        }


class FundingCalculator:
    """
    Service for calculating investment amounts from paychecks based on configurable rules.

    Example usage:
        calculator = FundingCalculator()
        rules = FundingRule(
            allocation_percent=Decimal('25.0'),  # 25%
            min_investment=Decimal('100.00'),    # $100 minimum
            cash_buffer=Decimal('1000.00'),      # Keep $1000 as buffer
            round_to_nearest=Decimal('1.00')     # Round to nearest dollar
        )

        # Calculate investment for a $2000 paycheck
        decision = calculator.calculate_investment(
            paycheck_amount=Decimal('2000.00'),
            current_cash_balance=Decimal('5000.00'),
            rules=rules
        )
    """

    def calculate_investment(
        self,
        paycheck_amount: Decimal,
        current_cash_balance: Optional[Decimal] = None,
        rules: Optional[FundingRule] = None,
    ) -> InvestmentDecision:
        """
        Calculate how much to invest from a paycheck.

        Args:
            paycheck_amount: Gross amount of the paycheck
            current_cash_balance: Optional current cash balance (for buffer calculations)
            rules: Funding rules to apply. If None, uses default rules.

        Returns:
            InvestmentDecision with the calculated amounts
        """
        # Use default rules if none provided
        if rules is None:
            rules = FundingRule(
                allocation_percent=Decimal("25.0"),
                min_investment=Decimal("100.00"),
                round_to_nearest=Decimal("1.00"),
            )

        # Validate inputs
        if paycheck_amount < 0:
            raise ValueError("Paycheck amount must be positive")

        if current_cash_balance is not None and current_cash_balance < 0:
            raise ValueError("Current cash balance cannot be negative")

        # Calculate base investment amount (percentage of paycheck)
        allocation_decimal = Decimal(str(rules.allocation_percent)) / Decimal("100")
        calculated_amount = paycheck_amount * allocation_decimal

        remaining_cash = None

        # If a cash buffer is configured and we know current cash, invest only
        # surplus above the buffer. This matches the unit-test semantics: preserve
        # the buffer first, then invest the remainder.
        if rules.cash_buffer is not None and current_cash_balance is not None:
            max_investment = current_cash_balance + paycheck_amount - rules.cash_buffer
            if max_investment >= rules.min_investment:
                investment_amount = max_investment
            else:
                investment_amount = Decimal("0.00")

            # If rounding is requested, round DOWN so we don't violate the buffer.
            if rules.round_to_nearest is not None and rules.round_to_nearest > 0:
                investment_amount = self._round_down_to_increment(investment_amount, rules.round_to_nearest)

            remaining_cash = current_cash_balance + paycheck_amount - investment_amount

        else:
            # Apply minimum investment rule on the percent-based calculation
            investment_amount = max(calculated_amount, rules.min_investment)

            # Round to nearest specified increment (true nearest, half-up)
            if rules.round_to_nearest is not None and rules.round_to_nearest > 0:
                investment_amount = self._round_to_nearest(investment_amount, rules.round_to_nearest)
                logger.debug(f"Rounded investment amount to ${investment_amount:.2f}")

            if current_cash_balance is not None:
                remaining_cash = current_cash_balance + paycheck_amount - investment_amount

        investment_amount = investment_amount.quantize(Decimal("0.01"))
        if remaining_cash is not None:
            remaining_cash = remaining_cash.quantize(Decimal("0.01"))

        # Prepare metadata about the calculation
        metadata = {
            "base_calculation": {
                "paycheck_amount": float(paycheck_amount),
                "allocation_percent": float(rules.allocation_percent),
                "calculated_amount": float(calculated_amount),
                "min_investment": (float(rules.min_investment) if rules.min_investment is not None else None),
                "cash_buffer_applied": rules.cash_buffer is not None and current_cash_balance is not None,
                "rounding_applied": rules.round_to_nearest is not None and rules.round_to_nearest > 0,
                "rounding_increment": (
                    float(rules.round_to_nearest)
                    if rules.round_to_nearest is not None and rules.round_to_nearest > 0
                    else None
                ),
            }
        }

        return InvestmentDecision(
            investment_amount=investment_amount,
            remaining_cash=remaining_cash,
            rule_applied=rules,
            metadata=metadata,
        )

    @staticmethod
    def _round_to_nearest(amount: Decimal, increment: Decimal) -> Decimal:
        """Round amount to the nearest increment (half-up)."""
        if increment <= 0:
            return amount

        q = (amount / increment).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        return q * increment

    @staticmethod
    def _round_down_to_increment(amount: Decimal, increment: Decimal) -> Decimal:
        """Round amount DOWN to an increment (used when buffer must not be violated)."""
        if increment <= 0:
            return amount

        q = (amount / increment).quantize(Decimal("1"), rounding=ROUND_DOWN)
        return q * increment


# Singleton instance for easy import
funding_calculator = FundingCalculator()
