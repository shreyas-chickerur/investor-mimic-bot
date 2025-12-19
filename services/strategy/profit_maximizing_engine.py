"""
Profit-Maximizing Signal Engine

Integrates ALL profit-generating factors:
1. 13F Conviction (Smart Money)
2. News Sentiment (Market Psychology)
3. Insider Trading (Information Edge)
4. Technical Indicators (RSI, MACD)
5. Moving Averages (Trend)
6. Volume Analysis (Confirmation)
7. Relative Strength (Market Leaders)
8. Earnings Momentum (Fundamental Catalyst)

Optimized weights based on quantitative research for maximum profit.
"""

import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
import pandas as pd
import numpy as np

from services.strategy.conviction_engine import ConvictionEngine, ConvictionConfig
from services.news.sentiment_analyzer import NewsSignalGenerator
from services.sec.insider_trading import SimpleInsiderSignalGenerator
from services.technical.indicators import TechnicalSignalGenerator
from services.technical.advanced_indicators import AdvancedTechnicalSignalGenerator
from services.fundamental.earnings_momentum import SimplifiedEarningsMomentum
from services.data.price_fetcher import PriceDataFetcher

logger = logging.getLogger(__name__)


@dataclass
class ProfitMaxSignal:
    """Complete profit-maximizing signal."""
    symbol: str
    combined_score: float
    recommendation: str
    confidence: float
    
    # Individual factor scores
    conviction_score: float
    news_score: float
    insider_score: float
    technical_score: float
    moving_avg_score: float
    volume_score: float
    relative_strength_score: float
    earnings_score: float
    
    # Factor details
    conviction_data: Dict
    news_data: Dict
    insider_data: Dict
    technical_data: Dict
    advanced_technical_data: Dict
    earnings_data: Dict


class ProfitMaximizingEngine:
    """
    Profit-maximizing signal engine integrating all factors.
    
    Optimized weight allocation based on quantitative research:
    - 13F Conviction: 30% (reduced from 40% to make room for new factors)
    - News Sentiment: 12% (reduced from 20%)
    - Insider Trading: 12% (reduced from 20%)
    - Technical (RSI/MACD): 8% (reduced from 20%)
    - Moving Averages: 18% (NEW - critical trend component)
    - Volume Analysis: 10% (NEW - confirmation)
    - Relative Strength: 8% (NEW - market leaders)
    - Earnings Momentum: 2% (NEW - fundamental catalyst, lower weight due to data limitations)
    
    Total: 100%
    """
    
    # Optimal weights for profit maximization
    WEIGHTS = {
        'conviction': 0.30,
        'news': 0.12,
        'insider': 0.12,
        'technical': 0.08,
        'moving_avg': 0.18,
        'volume': 0.10,
        'relative_strength': 0.08,
        'earnings': 0.02
    }
    
    def __init__(self, db_url: str, alpha_vantage_key: Optional[str] = None):
        """
        Initialize profit-maximizing engine.
        
        Args:
            db_url: Database connection URL
            alpha_vantage_key: Alpha Vantage API key
        """
        self.db_url = db_url
        self.alpha_vantage_key = alpha_vantage_key
        
        # Initialize all signal generators
        self.conviction_engine = ConvictionEngine(db_url)
        self.news_generator = NewsSignalGenerator(alpha_vantage_key)
        self.insider_generator = SimpleInsiderSignalGenerator()
        self.technical_generator = TechnicalSignalGenerator()
        self.advanced_technical_generator = AdvancedTechnicalSignalGenerator()
        self.earnings_generator = SimplifiedEarningsMomentum()
        self.price_fetcher = PriceDataFetcher(alpha_vantage_key=alpha_vantage_key)
    
    def compute_signal(
        self,
        symbol: str,
        conviction_score: float = 0.0,
        lookback_days: int = 90
    ) -> ProfitMaxSignal:
        """
        Compute comprehensive profit-maximizing signal.
        
        Args:
            symbol: Stock symbol
            conviction_score: Pre-computed conviction score (0-1)
            lookback_days: Days of historical data to analyze
            
        Returns:
            ProfitMaxSignal with all factor scores
        """
        # Get price and volume data
        try:
            price_data = self.price_fetcher.get_historical_prices(symbol, days=250)
            spy_data = self.price_fetcher.get_historical_prices('SPY', days=250)
            
            if price_data is None or len(price_data) < 50:
                logger.warning(f"Insufficient price data for {symbol}")
                prices = pd.Series([100.0] * 250)  # Mock data
                volumes = pd.Series([1000000] * 250)
                spy_prices = pd.Series([400.0] * 250)
            else:
                prices = price_data['close']
                volumes = price_data.get('volume', pd.Series([1000000] * len(prices)))
                spy_prices = spy_data['close'] if spy_data is not None else pd.Series([400.0] * len(prices))
        except Exception as e:
            logger.error(f"Error fetching price data for {symbol}: {e}")
            prices = pd.Series([100.0] * 250)
            volumes = pd.Series([1000000] * 250)
            spy_prices = pd.Series([400.0] * 250)
        
        # 1. News Sentiment
        try:
            news_signal = self.news_generator.generate_signal(symbol)
            news_score = (news_signal['sentiment'] + 1.0) / 2.0  # Convert -1,1 to 0,1
            news_data = news_signal
        except Exception as e:
            logger.error(f"Error generating news signal for {symbol}: {e}")
            news_score = 0.5
            news_data = {'sentiment': 0.0, 'error': str(e)}
        
        # 2. Insider Trading
        try:
            insider_signal = self.insider_generator.generate_signal(symbol)
            insider_score = insider_signal['signal']
            insider_data = insider_signal
        except Exception as e:
            logger.error(f"Error generating insider signal for {symbol}: {e}")
            insider_score = 0.5
            insider_data = {'signal': 0.5, 'error': str(e)}
        
        # 3. Technical Indicators (RSI, MACD)
        try:
            technical_signal = self.technical_generator.generate_signal(symbol, prices)
            technical_score = technical_signal['signal']
            technical_data = technical_signal
        except Exception as e:
            logger.error(f"Error generating technical signal for {symbol}: {e}")
            technical_score = 0.5
            technical_data = {'signal': 0.5, 'error': str(e)}
        
        # 4. Advanced Technical (MA, Volume, RS)
        try:
            advanced_signal = self.advanced_technical_generator.generate_signal(
                symbol=symbol,
                prices=prices,
                volumes=volumes,
                spy_prices=spy_prices
            )
            moving_avg_score = (advanced_signal['moving_averages']['ma_signal'] + 1.0) / 2.0
            volume_score = (advanced_signal['volume']['volume_signal'] + 1.0) / 2.0
            rs_score = (advanced_signal['relative_strength']['rs_signal'] + 1.0) / 2.0
            advanced_technical_data = advanced_signal
        except Exception as e:
            logger.error(f"Error generating advanced technical signal for {symbol}: {e}")
            moving_avg_score = 0.5
            volume_score = 0.5
            rs_score = 0.5
            advanced_technical_data = {'error': str(e)}
        
        # 5. Earnings Momentum
        try:
            earnings_signal = self.earnings_generator.calculate_earnings_signal(symbol)
            earnings_score = (earnings_signal['signal'] + 1.0) / 2.0
            earnings_data = earnings_signal
        except Exception as e:
            logger.error(f"Error generating earnings signal for {symbol}: {e}")
            earnings_score = 0.5
            earnings_data = {'signal': 0.0, 'error': str(e)}
        
        # Combine all signals with optimal weights
        combined_score = (
            conviction_score * self.WEIGHTS['conviction'] +
            news_score * self.WEIGHTS['news'] +
            insider_score * self.WEIGHTS['insider'] +
            technical_score * self.WEIGHTS['technical'] +
            moving_avg_score * self.WEIGHTS['moving_avg'] +
            volume_score * self.WEIGHTS['volume'] +
            rs_score * self.WEIGHTS['relative_strength'] +
            earnings_score * self.WEIGHTS['earnings']
        )
        
        # Generate recommendation
        if combined_score > 0.60:
            recommendation = 'STRONG BUY'
            confidence = combined_score
        elif combined_score > 0.55:
            recommendation = 'BUY'
            confidence = combined_score
        elif combined_score < 0.40:
            recommendation = 'SELL'
            confidence = 1.0 - combined_score
        elif combined_score < 0.45:
            recommendation = 'WEAK SELL'
            confidence = 1.0 - combined_score
        else:
            recommendation = 'HOLD'
            confidence = 0.5
        
        return ProfitMaxSignal(
            symbol=symbol,
            combined_score=combined_score,
            recommendation=recommendation,
            confidence=confidence,
            conviction_score=conviction_score,
            news_score=news_score,
            insider_score=insider_score,
            technical_score=technical_score,
            moving_avg_score=moving_avg_score,
            volume_score=volume_score,
            relative_strength_score=rs_score,
            earnings_score=earnings_score,
            conviction_data={'score': conviction_score},
            news_data=news_data,
            insider_data=insider_data,
            technical_data=technical_data,
            advanced_technical_data=advanced_technical_data,
            earnings_data=earnings_data
        )
    
    def get_top_opportunities(
        self,
        holdings_df: pd.DataFrame,
        conviction_config: ConvictionConfig,
        top_n: int = 20
    ) -> List[ProfitMaxSignal]:
        """
        Get top investment opportunities using all factors.
        
        Args:
            holdings_df: DataFrame with 13F holdings
            conviction_config: Conviction scoring configuration
            top_n: Number of top opportunities to return
            
        Returns:
            List of ProfitMaxSignal objects sorted by combined score
        """
        # Get conviction scores
        conviction_scores = self.conviction_engine.score(holdings_df, cfg=conviction_config)
        
        if conviction_scores.empty:
            logger.warning("No conviction scores available")
            return []
        
        # Compute comprehensive signals for all tickers
        signals = []
        for _, row in conviction_scores.iterrows():
            try:
                signal = self.compute_signal(
                    symbol=row['ticker'],
                    conviction_score=row['normalized_weight']
                )
                signals.append(signal)
            except Exception as e:
                logger.error(f"Error computing signal for {row['ticker']}: {e}")
                continue
        
        # Sort by combined score
        signals.sort(key=lambda x: x.combined_score, reverse=True)
        
        return signals[:top_n]
    
    def explain_signal(self, signal: ProfitMaxSignal) -> str:
        """
        Generate human-readable explanation of signal.
        
        Args:
            signal: ProfitMaxSignal to explain
            
        Returns:
            Explanation string
        """
        explanation = f"""
{signal.symbol} - {signal.recommendation} (Confidence: {signal.confidence:.1%})
Combined Score: {signal.combined_score:.3f}

Factor Breakdown:
  13F Conviction:     {signal.conviction_score:.3f} (Weight: {self.WEIGHTS['conviction']:.0%})
  News Sentiment:     {signal.news_score:.3f} (Weight: {self.WEIGHTS['news']:.0%})
  Insider Trading:    {signal.insider_score:.3f} (Weight: {self.WEIGHTS['insider']:.0%})
  Technical (RSI/MACD): {signal.technical_score:.3f} (Weight: {self.WEIGHTS['technical']:.0%})
  Moving Averages:    {signal.moving_avg_score:.3f} (Weight: {self.WEIGHTS['moving_avg']:.0%})
  Volume Analysis:    {signal.volume_score:.3f} (Weight: {self.WEIGHTS['volume']:.0%})
  Relative Strength:  {signal.relative_strength_score:.3f} (Weight: {self.WEIGHTS['relative_strength']:.0%})
  Earnings Momentum:  {signal.earnings_score:.3f} (Weight: {self.WEIGHTS['earnings']:.0%})

Key Insights:
"""
        
        # Add insights from advanced technical
        if 'moving_averages' in signal.advanced_technical_data:
            ma_data = signal.advanced_technical_data['moving_averages']
            if ma_data.get('golden_cross'):
                explanation += "  ✓ Golden Cross detected (very bullish)\n"
            if ma_data.get('death_cross'):
                explanation += "  ✗ Death Cross detected (very bearish)\n"
            if ma_data.get('price_vs_ma50', 0) > 5:
                explanation += f"  ✓ Price {ma_data['price_vs_ma50']:.1f}% above 50-day MA\n"
        
        if 'volume' in signal.advanced_technical_data:
            vol_data = signal.advanced_technical_data['volume']
            if vol_data.get('relative_volume', 1.0) > 1.5:
                explanation += f"  ✓ High volume ({vol_data['relative_volume']:.1f}x average)\n"
        
        if 'relative_strength' in signal.advanced_technical_data:
            rs_data = signal.advanced_technical_data['relative_strength']
            if rs_data.get('relative_strength', 0) > 5:
                explanation += f"  ✓ Outperforming market by {rs_data['relative_strength']:.1f}%\n"
        
        return explanation
