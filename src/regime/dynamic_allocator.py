#!/usr/bin/env python3
"""
Dynamic Strategy Allocation
Adjusts capital allocation based on strategy performance
"""
from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger(__name__)


class DynamicAllocator:
    """Dynamically allocates capital based on strategy performance"""

    def __init__(
        self,
        total_capital: float,
        lookback_days: int = 60,
        max_allocation_pct: float = 0.35,
        min_allocation_pct: float = 0.10,
    ):
        """
        Initialize dynamic allocator

        Args:
            total_capital: Total portfolio capital
            lookback_days: Days to look back for performance calculation
            max_allocation_pct: Maximum allocation to any strategy (35%)
            min_allocation_pct: Minimum allocation to any strategy (10%)
        """
        self.total_capital = total_capital
        self.lookback_days = lookback_days
        self.max_allocation = max_allocation_pct
        self.min_allocation = min_allocation_pct

        logger.info(
            f"Dynamic Allocator: max={max_allocation_pct*100}%, min={min_allocation_pct*100}%"
        )

    def calculate_sharpe_ratios(
        self, strategy_performance: dict[int, list[float]]
    ) -> dict[int, float]:
        """
        Calculate Sharpe ratio for each strategy

        Args:
            strategy_performance: Dict of {strategy_id: [daily_returns]}

        Returns:
            Dict of {strategy_id: sharpe_ratio}
        """
        sharpe_ratios = {}

        for strategy_id, returns in strategy_performance.items():
            if len(returns) < 20:  # Need minimum data
                sharpe_ratios[strategy_id] = 0.0
                continue

            returns_array = np.array(returns)

            if returns_array.std(ddof=1) == 0:
                sharpe_ratios[strategy_id] = 0.0
            else:
                # Annualized Sharpe ratio (ddof=1 consistent with PerformanceMetrics)
                sharpe = np.sqrt(252) * (returns_array.mean() / returns_array.std(ddof=1))
                sharpe_ratios[strategy_id] = sharpe

        return sharpe_ratios

    def calculate_allocations(
        self,
        strategy_ids: list[int],
        strategy_performance: dict[int, list[float]] | None = None,
        per_strategy_max: dict[int, float] | None = None,
        prior_sharpes: dict[int, float] | None = None,
    ) -> dict[int, float]:
        """
        Calculate dynamic capital allocations

        Args:
            strategy_ids: List of strategy IDs
            strategy_performance: Optional performance data for dynamic weighting
            per_strategy_max: Optional per-strategy max allocation overrides {strategy_id: max_pct}
            prior_sharpes: Backtest-derived Sharpes used when live history < 20 days

        Returns:
            Dict of {strategy_id: capital_allocation}
        """
        per_strategy_max = per_strategy_max or {}
        prior_sharpes = prior_sharpes or {}
        num_strategies = len(strategy_ids)

        def _max(sid: int) -> float:
            return per_strategy_max.get(sid, self.max_allocation)

        # Calculate live Sharpe ratios from returns history
        sharpe_ratios = self.calculate_sharpe_ratios(strategy_performance or {})

        # For strategies with < 20 live returns, substitute backtest prior Sharpe.
        # This prevents cold-start equal-weight fallback from ignoring known edge differences.
        for sid in strategy_ids:
            live_returns = (strategy_performance or {}).get(sid, [])
            if len(live_returns) < 20 and sid in prior_sharpes:
                sharpe_ratios[sid] = prior_sharpes[sid]
                logger.info(
                    f"Strategy {sid}: using prior Sharpe {prior_sharpes[sid]:.2f} (only {len(live_returns)} live days)"
                )

        # If all Sharpe ratios are 0 or negative (e.g. no priors and no live data),
        # fall back to equal weighting clipped to per-strategy caps
        total_sharpe = sum(sharpe_ratios.values())
        if total_sharpe <= 0:
            equal_weight = 1.0 / num_strategies
            weights = {}
            for sid in strategy_ids:
                weights[sid] = max(self.min_allocation, min(equal_weight, _max(sid)))
            total = sum(weights.values())
            if total < 1.0 - 1e-6:
                uncapped = [sid for sid in strategy_ids if weights[sid] < _max(sid)]
                bonus = (1.0 - total) / max(len(uncapped), 1)
                for sid in uncapped:
                    weights[sid] = min(weights[sid] + bonus, _max(sid))
            allocations = {sid: w * self.total_capital for sid, w in weights.items()}
            logger.info(
                f"All Sharpe ≤ 0, using equal allocation (with caps): ${self.total_capital/num_strategies:,.2f} base"
            )
            return allocations

        # Weight by Sharpe ratio
        raw_weights = {}
        for strategy_id in strategy_ids:
            sharpe = sharpe_ratios.get(strategy_id, 0.0)
            weight = sharpe / total_sharpe
            raw_weights[strategy_id] = weight

        # Apply min/max constraints and normalize iteratively
        constrained_weights = {}
        remaining_ids = list(strategy_ids)
        remaining_weight = 1.0

        # First pass: apply constraints
        for strategy_id in strategy_ids:
            weight = raw_weights[strategy_id]
            max_alloc = _max(strategy_id)

            if weight < self.min_allocation:
                constrained_weights[strategy_id] = self.min_allocation
                remaining_weight -= self.min_allocation
                remaining_ids.remove(strategy_id)
            elif weight > max_alloc:
                constrained_weights[strategy_id] = max_alloc
                remaining_weight -= max_alloc
                remaining_ids.remove(strategy_id)

        # Second pass: distribute remaining weight
        if remaining_ids and remaining_weight > 0:
            remaining_sharpe = sum(sharpe_ratios.get(sid, 0.0) for sid in remaining_ids)
            if remaining_sharpe > 0:
                for strategy_id in remaining_ids:
                    sharpe = sharpe_ratios.get(strategy_id, 0.0)
                    weight = (sharpe / remaining_sharpe) * remaining_weight
                    weight = max(self.min_allocation, min(_max(strategy_id), weight))
                    constrained_weights[strategy_id] = weight
            else:
                equal_weight = remaining_weight / len(remaining_ids)
                for strategy_id in remaining_ids:
                    constrained_weights[strategy_id] = equal_weight

        # Final adjustment to ensure sum = 1.0 while respecting per-strategy bounds
        adjusted_weights = constrained_weights.copy()
        residual = 1.0 - sum(adjusted_weights.values())
        tolerance = 1e-6

        while abs(residual) > tolerance:
            adjustable = [
                sid
                for sid, weight in adjusted_weights.items()
                if (residual > 0 and weight < _max(sid))
                or (residual < 0 and weight > self.min_allocation)
            ]

            if not adjustable:
                break

            share = residual / len(adjustable)
            for sid in adjustable:
                current = adjusted_weights[sid]
                proposed = current + share

                if residual > 0:
                    capped = min(_max(sid), proposed)
                else:
                    capped = max(self.min_allocation, proposed)

                adjusted_weights[sid] = capped
                residual -= capped - current

            if abs(residual) <= tolerance:
                break

        normalized_allocations = {
            sid: weight * self.total_capital for sid, weight in adjusted_weights.items()
        }

        # Log allocations
        for strategy_id, allocation in normalized_allocations.items():
            sharpe = sharpe_ratios.get(strategy_id, 0.0)
            pct = (allocation / self.total_capital) * 100
            logger.info(
                f"Strategy {strategy_id}: ${allocation:,.2f} ({pct:.1f}%, Sharpe: {sharpe:.2f})"
            )

        return normalized_allocations

    def rebalance_needed(
        self,
        current_allocations: dict[int, float],
        target_allocations: dict[int, float],
        threshold: float = 0.10,
    ) -> bool:
        """
        Check if rebalancing is needed

        Args:
            current_allocations: Current capital allocations
            target_allocations: Target allocations
            threshold: Rebalance if any strategy differs by more than this (10%)

        Returns:
            True if rebalancing needed
        """
        for strategy_id, target in target_allocations.items():
            current = current_allocations.get(strategy_id, 0)

            if target > 0 and abs(current - target) / target > threshold:
                logger.info(
                    f"Rebalance needed: Strategy {strategy_id} "
                    f"current=${current:,.2f} vs target=${target:,.2f}"
                )
                return True

        return False
