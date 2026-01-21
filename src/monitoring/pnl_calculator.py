#!/usr/bin/env python3
"""
P&L Calculator - Proper profit/loss attribution per strategy

Tracks entry and exit prices for each position and calculates realized P&L
when positions are closed. Uses FIFO (First In First Out) for partial closes.
"""

import logging
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from collections import defaultdict

logger = logging.getLogger(__name__)


class PnLCalculator:
    """
    Calculate realized P&L for trades with proper position tracking.
    
    Handles:
    - FIFO lot tracking for partial position closes
    - Realized P&L calculation on sells
    - Unrealized P&L for open positions
    - Per-strategy P&L attribution
    """
    
    def __init__(self, db):
        """
        Initialize P&L calculator.
        
        Args:
            db: TradingDatabase instance
        """
        self.db = db
        # Track open lots per strategy per symbol: {strategy_id: {symbol: [lots]}}
        self.open_lots = defaultdict(lambda: defaultdict(list))
        self._load_open_positions()
    
    def _load_open_positions(self):
        """Load current open positions from database as lots."""
        try:
            conn = self.db._get_connection()
            cursor = conn.cursor()
            
            # Get all open positions
            cursor.execute('''
                SELECT strategy_id, symbol, shares, avg_price, entry_date
                FROM positions
                WHERE shares > 0
            ''')
            
            for row in cursor.fetchall():
                strategy_id, symbol, shares, avg_price, entry_date = row
                # Create a single lot for existing position
                self.open_lots[strategy_id][symbol].append({
                    'shares': shares,
                    'price': avg_price,
                    'date': entry_date or datetime.now().isoformat()
                })
            
            conn.close()
            logger.info(f"Loaded open positions for {len(self.open_lots)} strategies")
            
        except Exception as e:
            logger.error(f"Error loading open positions: {e}")
    
    def calculate_trade_pnl(self, strategy_id: int, symbol: str, action: str, 
                           shares: float, price: float, costs: float = 0.0) -> Tuple[float, str]:
        """
        Calculate P&L for a trade.
        
        Args:
            strategy_id: Strategy ID
            symbol: Stock symbol
            action: 'BUY' or 'SELL'
            shares: Number of shares
            price: Execution price
            costs: Total costs (slippage + commission)
        
        Returns:
            Tuple of (pnl, explanation)
        """
        if action == 'BUY':
            # Add to open lots
            self.open_lots[strategy_id][symbol].append({
                'shares': shares,
                'price': price,
                'date': datetime.now().isoformat()
            })
            return 0.0, f"BUY: Added {shares} shares @ ${price:.2f} to open lots"
        
        elif action == 'SELL':
            # Calculate realized P&L using FIFO
            return self._calculate_sell_pnl(strategy_id, symbol, shares, price, costs)
        
        return 0.0, "Unknown action"
    
    def _calculate_sell_pnl(self, strategy_id: int, symbol: str, 
                           shares_to_sell: float, sell_price: float, 
                           costs: float) -> Tuple[float, str]:
        """
        Calculate P&L for a sell using FIFO lot matching.
        
        Args:
            strategy_id: Strategy ID
            symbol: Stock symbol
            shares_to_sell: Number of shares to sell
            sell_price: Sell price
            costs: Total costs
        
        Returns:
            Tuple of (realized_pnl, explanation)
        """
        lots = self.open_lots[strategy_id][symbol]
        
        if not lots:
            logger.warning(f"SELL without open position: {symbol} for strategy {strategy_id}")
            return 0.0, "SELL: No open position (short not supported)"
        
        total_pnl = 0.0
        shares_remaining = shares_to_sell
        lots_used = []
        explanation_parts = []
        
        # FIFO: Use oldest lots first
        for lot in lots:
            if shares_remaining <= 0:
                break
            
            shares_from_lot = min(lot['shares'], shares_remaining)
            
            # Calculate P&L for this lot
            proceeds = shares_from_lot * sell_price
            cost_basis = shares_from_lot * lot['price']
            lot_costs = (shares_from_lot / shares_to_sell) * costs  # Proportional costs
            lot_pnl = proceeds - cost_basis - lot_costs
            
            total_pnl += lot_pnl
            shares_remaining -= shares_from_lot
            
            explanation_parts.append(
                f"{shares_from_lot:.0f}@${lot['price']:.2f}→${sell_price:.2f} = ${lot_pnl:+.2f}"
            )
            
            # Update or remove lot
            if shares_from_lot >= lot['shares']:
                lots_used.append(lot)
            else:
                lot['shares'] -= shares_from_lot
        
        # Remove fully used lots
        for lot in lots_used:
            lots.remove(lot)
        
        if shares_remaining > 0:
            logger.warning(f"Sold more shares than available: {symbol} (short {shares_remaining})")
        
        explanation = f"SELL: {'; '.join(explanation_parts)} | Total: ${total_pnl:+.2f}"
        return total_pnl, explanation
    
    def get_unrealized_pnl(self, strategy_id: int, symbol: str, 
                          current_price: float) -> Tuple[float, Dict]:
        """
        Calculate unrealized P&L for open position.
        
        Args:
            strategy_id: Strategy ID
            symbol: Stock symbol
            current_price: Current market price
        
        Returns:
            Tuple of (unrealized_pnl, details_dict)
        """
        lots = self.open_lots[strategy_id][symbol]
        
        if not lots:
            return 0.0, {'shares': 0, 'avg_price': 0, 'current_price': current_price}
        
        total_shares = sum(lot['shares'] for lot in lots)
        total_cost = sum(lot['shares'] * lot['price'] for lot in lots)
        avg_price = total_cost / total_shares if total_shares > 0 else 0
        
        current_value = total_shares * current_price
        unrealized_pnl = current_value - total_cost
        
        return unrealized_pnl, {
            'shares': total_shares,
            'avg_price': avg_price,
            'current_price': current_price,
            'cost_basis': total_cost,
            'market_value': current_value
        }
    
    def get_strategy_pnl_summary(self, strategy_id: int, 
                                current_prices: Dict[str, float]) -> Dict:
        """
        Get complete P&L summary for a strategy.
        
        Args:
            strategy_id: Strategy ID
            current_prices: Dict of {symbol: current_price}
        
        Returns:
            Dict with realized_pnl, unrealized_pnl, total_pnl, positions
        """
        # Get realized P&L from database
        try:
            conn = self.db._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT COALESCE(SUM(pnl), 0) as realized_pnl
                FROM trades
                WHERE strategy_id = ? AND pnl IS NOT NULL
            ''', (strategy_id,))
            
            realized_pnl = cursor.fetchone()[0]
            conn.close()
            
        except Exception as e:
            logger.error(f"Error getting realized P&L: {e}")
            realized_pnl = 0.0
        
        # Calculate unrealized P&L for all open positions
        unrealized_pnl = 0.0
        positions = []
        
        for symbol in self.open_lots[strategy_id]:
            current_price = current_prices.get(symbol, 0)
            if current_price > 0:
                upnl, details = self.get_unrealized_pnl(strategy_id, symbol, current_price)
                unrealized_pnl += upnl
                positions.append({
                    'symbol': symbol,
                    **details,
                    'unrealized_pnl': upnl
                })
        
        return {
            'strategy_id': strategy_id,
            'realized_pnl': realized_pnl,
            'unrealized_pnl': unrealized_pnl,
            'total_pnl': realized_pnl + unrealized_pnl,
            'positions': positions
        }
