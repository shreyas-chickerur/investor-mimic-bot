#!/usr/bin/env python3
"""
Strategy 5: Volatility Breakout
Buy on volume + price breakouts above Bollinger Bands
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from strategy_base import TradingStrategy
from typing import List, Dict
import pandas as pd
import numpy as np


class VolatilityBreakoutStrategy(TradingStrategy):
    """Volatility breakout strategy using Bollinger Bands"""
    
    def __init__(self, strategy_id: int, capital: float):
        super().__init__(
            strategy_id=strategy_id,
            name="Volatility Breakout",
            capital=capital
        )
        self.bb_period = 20
        self.bb_std = 2
        self.hold_days = 7
    
    def _calculate_bollinger_bands(self, prices: pd.Series):
        """Calculate Bollinger Bands"""
        ma = prices.rolling(window=self.bb_period).mean()
        std = prices.rolling(window=self.bb_period).std()
        upper_band = ma + (std * self.bb_std)
        lower_band = ma - (std * self.bb_std)
        return ma, upper_band, lower_band
    
    def generate_signals(self, market_data: pd.DataFrame) -> List[Dict]:
        """Generate signals based on volatility breakouts with false breakout protection"""
        signals = []
        
        for symbol in market_data['symbol'].unique():
            symbol_data = market_data[market_data['symbol'] == symbol]
            
            if len(symbol_data) < self.bb_period + 5:
                continue
            
            # Calculate Bollinger Bands
            ma, upper_band, lower_band = self._calculate_bollinger_bands(symbol_data['close'])
            
            current = symbol_data.iloc[-1]
            previous = symbol_data.iloc[-2]
            latest_date = symbol_data.index[-1]
            price = current['close']
            prev_price = previous['close']
            volume = current['volume']
            avg_volume = symbol_data['volume'].iloc[-20:].mean()
            atr = current.get('atr_20', None)
            
            current_upper = upper_band.iloc[-1]
            prev_upper = upper_band.iloc[-2]
            current_lower = lower_band.iloc[-1]
            
            # IMPROVED Buy signal: 2 consecutive closes above upper band (false breakout protection)
            if (price > current_upper and 
                prev_price > prev_upper and  # 2 consecutive bars above band
                volume > avg_volume * 1.5 and 
                symbol not in self.positions):
                
                # Volatility-adjusted position sizing
                shares = self.calculate_position_size(price, atr=atr, max_position_pct=0.10)
                
                signals.append({
                    'symbol': symbol,
                    'action': 'BUY',
                    'shares': shares,
                    'price': price,
                    'value': shares * price,
                    'confidence': min((volume / avg_volume) / 2, 1.0),
                    'reasoning': f'2-bar breakout above BB with {volume/avg_volume:.1f}x volume (false breakout protected)',
                    'asof_date': latest_date
                })
            
            # Sell signal: Price drops below lower band or held long enough
            elif symbol in self.positions:
                days_held = self.get_days_held(symbol, latest_date)
                if price < current_lower or days_held >= self.hold_days:
                    shares = self.positions[symbol]
                    
                    signals.append({
                        'symbol': symbol,
                        'action': 'SELL',
                        'shares': shares,
                        'price': price,
                        'value': shares * price,
                        'confidence': 1.0,
                        'reasoning': f'Below BB lower band' if price < current_lower else f'Held {days_held} days',
                        'asof_date': latest_date
                    })
        
        return signals
    
    def get_description(self) -> str:
        return f"Buy on 2-bar breakouts above Bollinger Bands with high volume (false breakout protected)"
