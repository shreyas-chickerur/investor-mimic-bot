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
        """Generate signals using sentiment as FILTER, not trigger"""
        signals = []
        
        for symbol in market_data['symbol'].unique():
            symbol_data = market_data[market_data['symbol'] == symbol].iloc[-1]
            latest_date = symbol_data.name
            
            price = symbol_data['close']
            rsi = symbol_data.get('rsi', 50)
            volume_ratio = symbol_data.get('volume_ratio', 1.0)
            atr = symbol_data.get('atr_20', None)
            returns_5d = symbol_data.get('returns_5d', 0)

            # Placeholder: Use momentum as sentiment proxy until news API is integrated
            sentiment_score = max(0.0, min(1.0, 0.5 + returns_5d))
            
            # IMPROVED: Sentiment as FILTER, momentum as TRIGGER
            # Buy signal: Momentum signal (positive 5d return) + sentiment confirmation
            if (returns_5d > 0.02 and  # Momentum trigger (2% gain)
                sentiment_score > 0.6 and  # Sentiment filter
                rsi < 60 and  # Not overbought
                volume_ratio > 1.2 and  # Volume confirmation
                symbol not in self.positions):
                
                # Volatility-adjusted position sizing
                shares = self.calculate_position_size(price, atr=atr, max_position_pct=0.10)
                
                signals.append({
                    'symbol': symbol,
                    'action': 'BUY',
                    'shares': shares,
                    'price': price,
                    'value': shares * price,
                    'confidence': sentiment_score * 0.8,  # Slightly lower confidence
                    'reasoning': f'Momentum {returns_5d*100:.1f}% + sentiment filter ({sentiment_score:.2f})',
                    'asof_date': latest_date
                })
            
            # Sell signal: Negative sentiment or held long enough
            elif symbol in self.positions:
                days_held = self.get_days_held(symbol, latest_date)
                if sentiment_score < 0.4 or days_held >= self.hold_days:
                    shares = self.positions[symbol]
                    
                    signals.append({
                        'symbol': symbol,
                        'action': 'SELL',
                        'shares': shares,
                        'price': price,
                        'value': shares * price,
                        'confidence': 1.0 - sentiment_score if sentiment_score < 0.4 else 1.0,
                        'reasoning': f'Negative sentiment' if sentiment_score < 0.4 else f'Held {days_held} days',
                        'asof_date': latest_date
                    })
        
        return signals
    
    def get_description(self) -> str:
        return "Buy on momentum signals with positive sentiment filter (sentiment confirms, not triggers) with technical indicators (RSI)"
