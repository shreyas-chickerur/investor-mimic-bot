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
        # IMPROVED: Faster MAs (20/100 instead of 50/200)
        self.short_window = 20
        self.long_window = 100
        self.adx_threshold = 20  # Minimum trend strength
    
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
            latest_date = symbol_data.index[-1]
            
            price = current['close']
            ma_short_current = current['ma_short']
            ma_long_current = current['ma_long']
            ma_short_prev = previous['ma_short']
            ma_long_prev = previous['ma_long']
            adx = current.get('adx', 0)
            atr = current.get('atr_20', None)
            
            # Golden cross: short MA crosses above long MA AND trend confirmation
            # Relaxed ADX threshold from 25 to 20 for more opportunities
            if (ma_short_prev <= ma_long_prev and ma_short_current > ma_long_current and 
                adx > 20 and  # Trend confirmation (relaxed from 25)
                symbol not in self.positions):
                
                # Volatility-adjusted position sizing
                shares = self.calculate_position_size(price, atr=atr, max_position_pct=0.10)
                
                signals.append({
                    'symbol': symbol,
                    'action': 'BUY',
                    'shares': shares,
                    'price': price,
                    'value': shares * price,
                    'confidence': min(adx / 40, 1.0),  # Higher confidence for stronger trends
                    'reasoning': f'Golden cross: {self.short_window}MA crossed above {self.long_window}MA, ADX={adx:.1f}',
                    'asof_date': latest_date
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
                    'reasoning': f'Death cross: {self.short_window}MA crossed below {self.long_window}MA',
                    'asof_date': latest_date
                })
        
        return signals
    
    def get_description(self) -> str:
        return f"Buy on golden cross ({self.short_window}/{self.long_window}MA) with ADX>{self.adx_threshold}, sell on death cross"
