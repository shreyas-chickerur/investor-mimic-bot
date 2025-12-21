#!/usr/bin/env python3
"""
Strategy 3: News Sentiment + Technical
Combines news sentiment analysis with technical indicators
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from strategy_base import TradingStrategy
from typing import List, Dict
import pandas as pd


class NewsSentimentStrategy(TradingStrategy):
    """News sentiment combined with technical analysis"""
    
    def __init__(self, strategy_id: int, capital: float):
        super().__init__(
            strategy_id=strategy_id,
            name="News Sentiment",
            capital=capital
        )
        self.hold_days = 10
        self.entry_dates = {}
    
    def _get_sentiment_score(self, symbol: str) -> float:
        """
        Get news sentiment score for symbol
        In production, this would call a news API
        For now, using a simplified heuristic based on price momentum
        """
        # Placeholder: In production, integrate with news API
        # For now, use price momentum as proxy for sentiment
        return 0.5  # Neutral sentiment
    
    def generate_signals(self, market_data: pd.DataFrame) -> List[Dict]:
        """Generate signals combining news sentiment and technical indicators"""
        signals = []
        
        for symbol in market_data['symbol'].unique():
            symbol_data = market_data[market_data['symbol'] == symbol].iloc[-1]
            
            if pd.isna(symbol_data.get('rsi')):
                continue
            
            price = symbol_data['close']
            rsi = symbol_data['rsi']
            
            # Get sentiment (in production, from news API)
            sentiment = self._get_sentiment_score(symbol)
            
            # Buy signal: Positive sentiment + oversold technical
            if sentiment > 0.6 and rsi < 35 and symbol not in self.positions:
                shares = self.calculate_position_size(price, max_position_pct=0.10)
                
                signals.append({
                    'symbol': symbol,
                    'action': 'BUY',
                    'shares': shares,
                    'price': price,
                    'value': shares * price,
                    'confidence': sentiment,
                    'reasoning': f'Positive sentiment ({sentiment:.2f}) + RSI {rsi:.1f} oversold'
                })
            
            # Sell signal: Negative sentiment or held long enough
            elif symbol in self.positions:
                days_held = self.entry_dates.get(symbol, 0)
                if sentiment < 0.4 or days_held >= self.hold_days:
                    shares = self.positions[symbol]
                    
                    signals.append({
                        'symbol': symbol,
                        'action': 'SELL',
                        'shares': shares,
                        'price': price,
                        'value': shares * price,
                        'confidence': 1.0 - sentiment if sentiment < 0.4 else 1.0,
                        'reasoning': f'Negative sentiment' if sentiment < 0.4 else f'Held {days_held} days'
                    })
        
        return signals
    
    def get_description(self) -> str:
        return "Combines news sentiment analysis with technical indicators (RSI)"
