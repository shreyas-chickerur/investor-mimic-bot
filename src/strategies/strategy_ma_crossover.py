#!/usr/bin/env python3
"""
Strategy 4: Moving Average Crossover
Buy on golden cross (50-day MA > 200-day MA), sell on death cross
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from strategy_base import TradingStrategy
from typing import List, Dict
import pandas as pd


class MACrossoverStrategy(TradingStrategy):
    """Moving Average crossover strategy"""
    
    def __init__(self, strategy_id: int, capital: float):
        super().__init__(
            strategy_id=strategy_id,
            name="MA Crossover",
            capital=capital
        )
        self.short_window = 50
        self.long_window = 200
    
    def generate_signals(self, market_data: pd.DataFrame) -> List[Dict]:
        """Generate signals based on MA crossovers"""
        signals = []
        
        for symbol in market_data['symbol'].unique():
            symbol_data = market_data[market_data['symbol'] == symbol]
            
            if len(symbol_data) < self.long_window:
                continue
            
            # Calculate moving averages
            symbol_data = symbol_data.copy()
            symbol_data['ma_short'] = symbol_data['close'].rolling(window=self.short_window).mean()
            symbol_data['ma_long'] = symbol_data['close'].rolling(window=self.long_window).mean()
            
            current = symbol_data.iloc[-1]
            previous = symbol_data.iloc[-2]
            
            price = current['close']
            ma_short_current = current['ma_short']
            ma_long_current = current['ma_long']
            ma_short_prev = previous['ma_short']
            ma_long_prev = previous['ma_long']
            
            # Golden cross: short MA crosses above long MA
            if (ma_short_prev <= ma_long_prev and ma_short_current > ma_long_current and 
                symbol not in self.positions):
                shares = self.calculate_position_size(price, max_position_pct=0.10)
                
                signals.append({
                    'symbol': symbol,
                    'action': 'BUY',
                    'shares': shares,
                    'price': price,
                    'value': shares * price,
                    'confidence': 0.8,
                    'reasoning': f'Golden cross: {self.short_window}MA crossed above {self.long_window}MA'
                })
            
            # Death cross: short MA crosses below long MA
            elif (ma_short_prev >= ma_long_prev and ma_short_current < ma_long_current and 
                  symbol in self.positions):
                shares = self.positions[symbol]
                
                signals.append({
                    'symbol': symbol,
                    'action': 'SELL',
                    'shares': shares,
                    'price': price,
                    'value': shares * price,
                    'confidence': 0.8,
                    'reasoning': f'Death cross: {self.short_window}MA crossed below {self.long_window}MA'
                })
        
        return signals
    
    def get_description(self) -> str:
        return f"Buy on golden cross ({self.short_window}/{self.long_window}MA), sell on death cross"
