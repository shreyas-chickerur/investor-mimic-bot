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
        """Generate buy signals for oversold stocks with improved filters"""
        signals = []
        
        for symbol in market_data['symbol'].unique():
            symbol_data = market_data[market_data['symbol'] == symbol]
            
            if len(symbol_data) < 2:
                continue
            
            # Get latest values
            latest = symbol_data.iloc[-1]
            
            # Check if we have RSI
            if 'rsi' not in latest.index or pd.isna(latest['rsi']):
                continue
            
            rsi = latest['rsi']
            price = latest['close']
            
            # Calculate RSI slope
            if len(symbol_data) >= 2:
                rsi_slope = symbol_data['rsi'].iloc[-1] - symbol_data['rsi'].iloc[-2]
            else:
                rsi_slope = 0
            
            # Get VWAP (use close as fallback)
            vwap = latest.get('vwap', price)
            atr = latest.get('atr_20', None)
            
            # IMPROVED Buy signal: RSI < 30 AND RSI slope > 0 (turning up)
            if rsi < self.rsi_threshold and rsi_slope > 0 and symbol not in self.positions:
                # Volatility-adjusted position sizing
                shares = self.calculate_position_size(price, atr=atr, max_position_pct=0.10)
                    
                signals.append({
                    'symbol': symbol,
                    'action': 'BUY',
                    'shares': shares,
                    'price': price,
                    'value': shares * price,
                    'confidence': (30 - rsi) / 30,  # Higher confidence for lower RSI
                    'reasoning': f'RSI {rsi:.1f} < {self.rsi_threshold}, slope {rsi_slope:.2f} > 0 (turning up)'
                })
            
            # IMPROVED Sell signal: RSI > 50 OR price >= VWAP OR held for 20 days
            if symbol in self.positions:
                days_held = self.entry_dates.get(symbol, 0)
                shares = self.positions[symbol]
                
                # Exit conditions (any one triggers exit)
                exit_reason = None
                if rsi > 50:
                    exit_reason = f'RSI {rsi:.1f} > 50 (mean reversion complete)'
                elif price >= vwap:
                    exit_reason = f'Price ${price:.2f} >= VWAP ${vwap:.2f} (profitable exit)'
                elif days_held >= self.hold_days:
                    exit_reason = f'Held for {days_held} days (time-based exit)'
                
                if exit_reason:
                    signals.append({
                        'symbol': symbol,
                        'action': 'SELL',
                        'shares': shares,
                        'price': price,
                        'value': shares * price,
                        'confidence': 1.0,
                        'reasoning': exit_reason
                    })
        
        return signals
    
    def get_description(self) -> str:
        return f"Buy when RSI < {self.rsi_threshold}, sell after {self.hold_days} days"
