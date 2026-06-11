#!/usr/bin/env python3
"""
Cash Management System
Prevents overdraft and manages cash allocation across strategies
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class CashManager:
    """Manages cash allocation across multiple strategies"""

    def __init__(self, total_cash: float, num_strategies: int = 5):
        self.total_cash = total_cash
        self.num_strategies = num_strategies
        self.allocated_cash = {}
        # Ceiling for release_cash: a strategy can never be released back above
        # its own allocation, so double-release bugs surface as a clamp warning
        # instead of silently handing one strategy the whole portfolio.
        self.max_allocation: dict[int, float] = {}
        self.reserved_cash = 0.0

        # Allocate cash equally to strategies
        cash_per_strategy = total_cash / num_strategies
        for i in range(1, num_strategies + 1):
            self.allocated_cash[i] = cash_per_strategy
            self.max_allocation[i] = cash_per_strategy

        logger.info(
            f"Cash Manager initialized: ${total_cash:,.2f} total, ${cash_per_strategy:,.2f} per strategy"
        )

    def check_available_cash(self, strategy_id: int, amount: float) -> bool:
        """Check if strategy has enough cash for trade"""
        available = self.allocated_cash.get(strategy_id, 0)
        return available >= amount

    def reserve_cash(self, strategy_id: int, amount: float) -> bool:
        """
        Reserve cash for a trade

        Returns:
            True if successful, False if insufficient funds
        """
        if not self.check_available_cash(strategy_id, amount):
            logger.warning(
                f"Strategy {strategy_id} has insufficient cash: needs ${amount:.2f}, has ${self.allocated_cash.get(strategy_id, 0):.2f}"
            )
            return False

        self.allocated_cash[strategy_id] -= amount
        self.reserved_cash += amount
        logger.info(
            f"Reserved ${amount:.2f} for strategy {strategy_id}, remaining: ${self.allocated_cash[strategy_id]:.2f}"
        )
        return True

    def release_cash(self, strategy_id: int, amount: float):
        """Release reserved cash back to strategy.

        Clamps the result to a non-negative balance so double-release calls
        (e.g. releasing cash that was never reserved) cannot inflate available funds.
        """
        new_balance = self.allocated_cash.get(strategy_id, 0) + amount
        # Clamp: a strategy's available balance must not exceed ITS OWN allocation
        # (not the whole portfolio). Without this, double-release calls silently
        # inflate one strategy's buying power up to total capital.
        max_allowed = self.max_allocation.get(strategy_id, self.total_cash)
        if new_balance > max_allowed + 0.01:
            logger.warning(
                "release_cash clamp: strategy %s release of $%.2f would exceed its "
                "allocation ($%.2f > $%.2f) — likely a double release; truncating",
                strategy_id,
                amount,
                new_balance,
                max_allowed,
            )
        self.allocated_cash[strategy_id] = max(0.0, min(new_balance, max_allowed))
        self.reserved_cash = max(0.0, self.reserved_cash - amount)
        logger.info(
            f"Released ${amount:.2f} to strategy {strategy_id}, new balance: ${self.allocated_cash[strategy_id]:.2f}"
        )

    def validate_invariants(self) -> bool:
        """Check that allocated + reserved ≤ total capital.

        Returns True if the invariant holds; logs a WARNING and returns False if
        cash has drifted (e.g., due to double-release bugs or mid-run reallocations).
        """
        total_allocated = sum(self.allocated_cash.values())
        total_accounted = total_allocated + self.reserved_cash
        # Allow a small float tolerance
        if total_accounted > self.total_cash * 1.001:
            logger.warning(
                "CashManager invariant violated: allocated($%.2f) + reserved($%.2f) = $%.2f "
                "> total($%.2f) — possible double-release or reallocation drift",
                total_allocated,
                self.reserved_cash,
                total_accounted,
                self.total_cash,
            )
            return False
        return True

    def sync_from_broker(self, broker_cash: float) -> None:
        """Sync total_cash from the actual broker account balance.

        Called at the start of each run to prevent the in-memory cash model
        from drifting away from real broker state (e.g., after dividends, fees,
        or manual adjustments). Scales all per-strategy allocations proportionally.
        """
        if broker_cash <= 0:
            return
        old_total = self.total_cash
        if abs(broker_cash - old_total) < 1.0:
            return  # negligible drift — skip
        scale = broker_cash / old_total if old_total > 0 else 1.0
        for sid in self.allocated_cash:
            self.allocated_cash[sid] = max(0.0, self.allocated_cash[sid] * scale)
        for sid in self.max_allocation:
            self.max_allocation[sid] = max(0.0, self.max_allocation[sid] * scale)
        self.total_cash = broker_cash
        logger.info(
            "CashManager synced from broker: $%.2f → $%.2f (scale=%.4f)",
            old_total,
            broker_cash,
            scale,
        )

    def set_allocations(
        self,
        allocations: dict[int, float],
        exposures: dict[int, float] | None = None,
        min_cash_pct: float = 0.0,
    ):
        """
        Update cash allocations per strategy.

        Args:
            allocations: Dict of {strategy_id: total capital allocation}
            exposures: Dict of {strategy_id: current exposure} to reserve against allocations
        """
        self.total_cash = sum(allocations.values())
        self.allocated_cash = {}
        self.max_allocation = {}
        self.reserved_cash = 0.0

        exposures = exposures or {}
        for strategy_id, allocation in allocations.items():
            exposure = exposures.get(strategy_id, 0)
            min_cash = max(allocation * min_cash_pct, 0)
            available = max(allocation - exposure, min_cash)
            self.allocated_cash[strategy_id] = available
            self.max_allocation[strategy_id] = allocation
            self.reserved_cash += max(exposure, allocation - available)

        logger.info("Updated cash allocations per strategy")

    def prioritize_trades(self, all_trades: list[dict]) -> list[dict]:
        """
        Prioritize trades when total cash needed exceeds available

        Args:
            all_trades: List of trade dicts with 'strategy_id', 'value', 'confidence'

        Returns:
            Filtered list of trades that fit within cash constraints
        """
        # Sort by confidence (highest first)
        sorted_trades = sorted(all_trades, key=lambda x: x.get("confidence", 0.5), reverse=True)

        approved_trades = []
        # Key by ACTUAL bucket IDs — strategy IDs are not contiguous once
        # strategies are disabled (range(1, N+1) silently missed real IDs).
        strategy_cash_used = {sid: 0.0 for sid in self.allocated_cash}

        for trade in sorted_trades:
            strategy_id = trade.get("strategy_id", 1)
            trade_value = trade.get("value", 0)

            # Check if strategy has enough cash
            cash_available = self.allocated_cash.get(strategy_id, 0) - strategy_cash_used.get(
                strategy_id, 0.0
            )

            if cash_available >= trade_value:
                approved_trades.append(trade)
                strategy_cash_used[strategy_id] = (
                    strategy_cash_used.get(strategy_id, 0.0) + trade_value
                )
            else:
                logger.warning(f"Skipping trade for {trade.get('symbol')} - insufficient cash")

        logger.info(
            f"Prioritized {len(approved_trades)}/{len(all_trades)} trades based on available cash"
        )
        return approved_trades

    def get_status(self) -> dict:
        """Get current cash status"""
        return {
            "total_cash": self.total_cash,
            "reserved_cash": self.reserved_cash,
            "available_cash": sum(self.allocated_cash.values()),
            "per_strategy": self.allocated_cash.copy(),
        }
