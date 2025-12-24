#!/usr/bin/env python3
"""
Cash Management System
Prevents overdraft and manages cash allocation across strategies
"""
import logging
from typing import List, Dict, Tuple

logger = logging.getLogger(__name__)

class CashManager:
    """Manages cash allocation across multiple strategies"""
    
    def __init__(self, total_cash: float, num_strategies: int = 5):
        self.total_cash = total_cash
        self.num_strategies = num_strategies
        self.allocated_cash = {}
        self.reserved_cash = 0
        
        # Allocate cash equally to strategies
        cash_per_strategy = total_cash / num_strategies
        for i in range(1, num_strategies + 1):
            self.allocated_cash[i] = cash_per_strategy
        
        logger.info(f"Cash Manager initialized: ${total_cash:,.2f} total, ${cash_per_strategy:,.2f} per strategy")
    
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
            logger.warning(f"Strategy {strategy_id} has insufficient cash: needs ${amount:.2f}, has ${self.allocated_cash.get(strategy_id, 0):.2f}")
            return False
        
        self.allocated_cash[strategy_id] -= amount
        self.reserved_cash += amount
        logger.info(f"Reserved ${amount:.2f} for strategy {strategy_id}, remaining: ${self.allocated_cash[strategy_id]:.2f}")
        return True
    
    def release_cash(self, strategy_id: int, amount: float):
        """Release reserved cash back to strategy"""
        self.allocated_cash[strategy_id] += amount
        self.reserved_cash -= amount
        logger.info(f"Released ${amount:.2f} to strategy {strategy_id}, new balance: ${self.allocated_cash[strategy_id]:.2f}")

    def set_allocations(self, allocations: Dict[int, float], exposures: Dict[int, float] = None):
        """
        Update cash allocations per strategy.

        Args:
            allocations: Dict of {strategy_id: total capital allocation}
            exposures: Dict of {strategy_id: current exposure} to reserve against allocations
        """
        self.total_cash = sum(allocations.values())
        self.allocated_cash = {}
        self.reserved_cash = 0

        exposures = exposures or {}
        for strategy_id, allocation in allocations.items():
            exposure = exposures.get(strategy_id, 0)
            available = max(allocation - exposure, 0)
            self.allocated_cash[strategy_id] = available
            self.reserved_cash += max(exposure, 0)

        logger.info("Updated cash allocations per strategy")
    
    def prioritize_trades(self, all_trades: List[Dict]) -> List[Dict]:
        """
        Prioritize trades when total cash needed exceeds available
        
        Args:
            all_trades: List of trade dicts with 'strategy_id', 'value', 'confidence'
        
        Returns:
            Filtered list of trades that fit within cash constraints
        """
        # Sort by confidence (highest first)
        sorted_trades = sorted(all_trades, key=lambda x: x.get('confidence', 0.5), reverse=True)
        
        approved_trades = []
        strategy_cash_used = {i: 0 for i in range(1, self.num_strategies + 1)}
        
        for trade in sorted_trades:
            strategy_id = trade.get('strategy_id', 1)
            trade_value = trade.get('value', 0)
            
            # Check if strategy has enough cash
            cash_available = self.allocated_cash.get(strategy_id, 0) - strategy_cash_used[strategy_id]
            
            if cash_available >= trade_value:
                approved_trades.append(trade)
                strategy_cash_used[strategy_id] += trade_value
            else:
                logger.warning(f"Skipping trade for {trade.get('symbol')} - insufficient cash")
        
        logger.info(f"Prioritized {len(approved_trades)}/{len(all_trades)} trades based on available cash")
        return approved_trades
    
    def get_status(self) -> Dict:
        """Get current cash status"""
        return {
            'total_cash': self.total_cash,
            'reserved_cash': self.reserved_cash,
            'available_cash': sum(self.allocated_cash.values()),
            'per_strategy': self.allocated_cash.copy()
        }
