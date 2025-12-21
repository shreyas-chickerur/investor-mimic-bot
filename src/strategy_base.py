#!/usr/bin/env python3
"""
Strategy Base Class
All trading strategies inherit from this base class
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from datetime import datetime
import pandas as pd


class TradingStrategy(ABC):
    """Base class for all trading strategies"""
    
    def __init__(self, strategy_id: int, name: str, capital: float):
        self.strategy_id = strategy_id
        self.name = name
        self.capital = capital
        self.initial_capital = capital
        self.positions = {}  # {symbol: shares}
        self.trade_history = []
        
    @abstractmethod
    def generate_signals(self, market_data: pd.DataFrame) -> List[Dict]:
        """
        Generate trading signals based on strategy logic
        
        Args:
            market_data: DataFrame with OHLCV data and indicators
        
        Returns:
            List of signal dicts: [{'symbol': 'AAPL', 'action': 'BUY', 'shares': 10, ...}]
        """
        pass
    
    @abstractmethod
    def get_description(self) -> str:
        """Return strategy description"""
        pass
    
    def calculate_position_size(self, price: float, max_position_pct: float = 0.1) -> int:
        """Calculate number of shares to buy"""
        max_investment = self.capital * max_position_pct
        shares = int(max_investment / price)
        return max(1, shares)
    
    def update_capital(self, amount: float):
        """Update available capital"""
        self.capital += amount
    
    def add_position(self, symbol: str, shares: float):
        """Add or update position"""
        if symbol in self.positions:
            self.positions[symbol] += shares
        else:
            self.positions[symbol] = shares
    
    def remove_position(self, symbol: str, shares: float = None):
        """Remove or reduce position"""
        if symbol in self.positions:
            if shares is None:
                del self.positions[symbol]
            else:
                self.positions[symbol] -= shares
                if self.positions[symbol] <= 0:
                    del self.positions[symbol]
    
    def get_portfolio_value(self, current_prices: Dict[str, float]) -> float:
        """Calculate total portfolio value"""
        positions_value = sum(
            shares * current_prices.get(symbol, 0)
            for symbol, shares in self.positions.items()
        )
        return self.capital + positions_value
    
    def get_return_pct(self, current_prices: Dict[str, float]) -> float:
        """Calculate total return percentage"""
        current_value = self.get_portfolio_value(current_prices)
        return ((current_value - self.initial_capital) / self.initial_capital) * 100
    
    def record_trade(self, trade: Dict):
        """Record a trade in history"""
        trade['strategy_id'] = self.strategy_id
        trade['strategy_name'] = self.name
        trade['timestamp'] = datetime.now().isoformat()
        self.trade_history.append(trade)
    
    def get_metrics(self, current_prices: Dict[str, float]) -> Dict:
        """Get current performance metrics"""
        portfolio_value = self.get_portfolio_value(current_prices)
        return_pct = self.get_return_pct(current_prices)
        
        return {
            'strategy_id': self.strategy_id,
            'name': self.name,
            'portfolio_value': portfolio_value,
            'cash': self.capital,
            'positions_value': portfolio_value - self.capital,
            'return_pct': return_pct,
            'num_positions': len(self.positions),
            'num_trades': len(self.trade_history)
        }
