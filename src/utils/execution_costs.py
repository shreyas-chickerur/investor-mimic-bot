#!/usr/bin/env python3
"""
Execution Cost Model
Adds realistic slippage and transaction costs to trades
"""
import logging

logger = logging.getLogger(__name__)

class ExecutionCostModel:
    """Models realistic execution costs for trading"""
    
    def __init__(self, 
                 slippage_bps: float = 7.5,  # 7.5 basis points (0.075%)
                 commission_per_share: float = 0.005):  # $0.005 per share
        """
        Initialize cost model
        
        Args:
            slippage_bps: Slippage in basis points (default 7.5 = 0.075%)
            commission_per_share: Commission cost per share
        """
        self.slippage_bps = slippage_bps
        self.commission_per_share = commission_per_share
        
        logger.info(f"Execution costs: {slippage_bps} bps slippage, ${commission_per_share}/share commission")
    
    def calculate_execution_price(self, quoted_price: float, side: str, shares: int) -> tuple:
        """
        Calculate realistic execution price including slippage
        
        Args:
            quoted_price: Market price
            side: 'BUY' or 'SELL'
            shares: Number of shares
            
        Returns:
            (execution_price, slippage_cost, commission_cost, total_cost)
        """
        # Slippage (worse price for larger orders)
        slippage_pct = self.slippage_bps / 10000
        
        if side == 'BUY':
            # Pay more when buying
            execution_price = quoted_price * (1 + slippage_pct)
            slippage_cost = (execution_price - quoted_price) * shares
        else:  # SELL
            # Receive less when selling
            execution_price = quoted_price * (1 - slippage_pct)
            slippage_cost = (quoted_price - execution_price) * shares
        
        # Commission
        commission_cost = shares * self.commission_per_share
        
        # Total cost
        total_cost = slippage_cost + commission_cost
        
        logger.debug(f"{side} {shares} @ ${quoted_price:.2f} → ${execution_price:.2f} "
                    f"(slippage: ${slippage_cost:.2f}, commission: ${commission_cost:.2f})")
        
        return execution_price, slippage_cost, commission_cost, total_cost
    
    def adjust_order_for_costs(self, quoted_price: float, side: str, target_value: float) -> int:
        """
        Calculate shares to buy/sell accounting for costs
        
        Args:
            quoted_price: Market price
            side: 'BUY' or 'SELL'
            target_value: Target position value
            
        Returns:
            Number of shares to trade
        """
        slippage_pct = self.slippage_bps / 10000
        
        if side == 'BUY':
            # Account for slippage and commission when buying
            effective_price = quoted_price * (1 + slippage_pct) + self.commission_per_share
            shares = int(target_value / effective_price)
        else:  # SELL
            # Account for slippage and commission when selling
            effective_price = quoted_price * (1 - slippage_pct) - self.commission_per_share
            shares = int(target_value / effective_price)
        
        return max(shares, 0)

# Global instance
cost_model = ExecutionCostModel()
