#!/usr/bin/env python3
"""
Strategy 1: RSI Mean Reversion
Buy when RSI < 30 (oversold), sell after 20 days
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from strategy_base import TradingStrategy
from typing import List, Dict
import pandas as pd


class RSIMeanReversionStrategy(TradingStrategy):
    """RSI-based mean reversion strategy"""
    
    def __init__(self, strategy_id: int, capital: float):
        super().__init__(
            strategy_id=strategy_id,
            name="RSI Mean Reversion",
            capital=capital
        )
        self.rsi_threshold = 30
        self.hold_days = 20
        self.entry_dates = {}  # Track when positions were entered
    
    def generate_signals(self, market_data: pd.DataFrame) -> List[Dict]:
        """Generate buy signals for oversold stocks"""
        signals = []
        
        for symbol in market_data['symbol'].unique():
            symbol_data = market_data[market_data['symbol'] == symbol].iloc[-1]
            
            # Check if we have RSI data
            if pd.isna(symbol_data.get('rsi')):
                continue
            
            rsi = symbol_data['rsi']
            price = symbol_data['close']
            
            # Buy signal: RSI < 30 and we don't already own it
            if rsi < self.rsi_threshold and symbol not in self.positions:
                shares = self.calculate_position_size(price, max_position_pct=0.10)
                
                signals.append({
                    'symbol': symbol,
                    'action': 'BUY',
                    'shares': shares,
                    'price': price,
                    'value': shares * price,
                    'confidence': (30 - rsi) / 30,  # Higher confidence for lower RSI
                    'reasoning': f'RSI {rsi:.1f} < {self.rsi_threshold} (oversold)'
                })
            
            # Sell signal: Held for 20 days
            elif symbol in self.positions:
                days_held = self.entry_dates.get(symbol, 0)
                if days_held >= self.hold_days:
                    shares = self.positions[symbol]
                    
                    signals.append({
                        'symbol': symbol,
                        'action': 'SELL',
                        'shares': shares,
                        'price': price,
                        'value': shares * price,
                        'confidence': 1.0,
                        'reasoning': f'Held for {days_held} days (target: {self.hold_days})'
                    })
        
        return signals
    
    def get_description(self) -> str:
        return f"Buy when RSI < {self.rsi_threshold}, sell after {self.hold_days} days"
