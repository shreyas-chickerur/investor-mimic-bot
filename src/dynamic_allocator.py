#!/usr/bin/env python3
"""
Dynamic Strategy Allocation
Adjusts capital allocation based on strategy performance
"""
import logging
from typing import Dict, List
import numpy as np

logger = logging.getLogger(__name__)

class DynamicAllocator:
    """Dynamically allocates capital based on strategy performance"""
    
    def __init__(self, 
                 total_capital: float,
                 lookback_days: int = 60,
                 max_allocation_pct: float = 0.35,
                 min_allocation_pct: float = 0.10):
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
        
        logger.info(f"Dynamic Allocator: max={max_allocation_pct*100}%, min={min_allocation_pct*100}%")
    
    def calculate_sharpe_ratios(self, strategy_performance: Dict[int, List[float]]) -> Dict[int, float]:
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
            
            if returns_array.std() == 0:
                sharpe_ratios[strategy_id] = 0.0
            else:
                # Annualized Sharpe ratio
                sharpe = np.sqrt(252) * (returns_array.mean() / returns_array.std())
                sharpe_ratios[strategy_id] = max(sharpe, 0.0)  # Floor at 0
        
        return sharpe_ratios
    
    def calculate_allocations(self, 
                             strategy_ids: List[int],
                             strategy_performance: Dict[int, List[float]] = None) -> Dict[int, float]:
        """
        Calculate dynamic capital allocations
        
        Args:
            strategy_ids: List of strategy IDs
            strategy_performance: Optional performance data for dynamic weighting
            
        Returns:
            Dict of {strategy_id: capital_allocation}
        """
        num_strategies = len(strategy_ids)
        
        # If no performance data, use equal weighting
        if not strategy_performance or all(len(perf) < 20 for perf in strategy_performance.values()):
            equal_allocation = self.total_capital / num_strategies
            allocations = {sid: equal_allocation for sid in strategy_ids}
            logger.info(f"Using equal allocation: ${equal_allocation:,.2f} per strategy")
            return allocations
        
        # Calculate Sharpe ratios
        sharpe_ratios = self.calculate_sharpe_ratios(strategy_performance)
        
        # If all Sharpe ratios are 0 or negative, use equal weighting
        total_sharpe = sum(sharpe_ratios.values())
        if total_sharpe <= 0:
            equal_allocation = self.total_capital / num_strategies
            allocations = {sid: equal_allocation for sid in strategy_ids}
            logger.info(f"All Sharpe ≤ 0, using equal allocation: ${equal_allocation:,.2f}")
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
            
            if weight < self.min_allocation:
                constrained_weights[strategy_id] = self.min_allocation
                remaining_weight -= self.min_allocation
                remaining_ids.remove(strategy_id)
            elif weight > self.max_allocation:
                constrained_weights[strategy_id] = self.max_allocation
                remaining_weight -= self.max_allocation
                remaining_ids.remove(strategy_id)
        
        # Second pass: distribute remaining weight
        if remaining_ids and remaining_weight > 0:
            remaining_sharpe = sum(sharpe_ratios.get(sid, 0.0) for sid in remaining_ids)
            if remaining_sharpe > 0:
                for strategy_id in remaining_ids:
                    sharpe = sharpe_ratios.get(strategy_id, 0.0)
                    weight = (sharpe / remaining_sharpe) * remaining_weight
                    # Ensure still within bounds
                    weight = max(self.min_allocation, min(self.max_allocation, weight))
                    constrained_weights[strategy_id] = weight
            else:
                # Equal distribution of remaining
                equal_weight = remaining_weight / len(remaining_ids)
                for strategy_id in remaining_ids:
                    constrained_weights[strategy_id] = equal_weight
        
        # Final adjustment to ensure sum = 1.0 while respecting bounds
        adjusted_weights = constrained_weights.copy()
        residual = 1.0 - sum(adjusted_weights.values())
        tolerance = 1e-6

        while abs(residual) > tolerance:
            adjustable = [
                sid for sid, weight in adjusted_weights.items()
                if (residual > 0 and weight < self.max_allocation)
                or (residual < 0 and weight > self.min_allocation)
            ]

            if not adjustable:
                break

            share = residual / len(adjustable)
            for sid in adjustable:
                current = adjusted_weights[sid]
                proposed = current + share

                if residual > 0:
                    capped = min(self.max_allocation, proposed)
                else:
                    capped = max(self.min_allocation, proposed)

                adjusted_weights[sid] = capped
                residual -= (capped - current)

            if abs(residual) <= tolerance:
                break

        normalized_allocations = {
            sid: weight * self.total_capital
            for sid, weight in adjusted_weights.items()
        }
        
        # Log allocations
        for strategy_id, allocation in normalized_allocations.items():
            sharpe = sharpe_ratios.get(strategy_id, 0.0)
            pct = (allocation / self.total_capital) * 100
            logger.info(f"Strategy {strategy_id}: ${allocation:,.2f} ({pct:.1f}%, Sharpe: {sharpe:.2f})")
        
        return normalized_allocations
    
    def rebalance_needed(self, 
                        current_allocations: Dict[int, float],
                        target_allocations: Dict[int, float],
                        threshold: float = 0.10) -> bool:
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
            
            if abs(current - target) / target > threshold:
                logger.info(f"Rebalance needed: Strategy {strategy_id} "
                          f"current=${current:,.2f} vs target=${target:,.2f}")
                return True
        
        return False
