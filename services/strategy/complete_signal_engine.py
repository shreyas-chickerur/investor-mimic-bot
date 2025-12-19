"""
Complete Multi-Signal Engine - Integrates all signal sources.
Combines 13F, News, Insider Trading, and Technical signals.
"""

import logging
from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional

from services.news.news_api import NewsAPIService
from services.news.sentiment_analyzer import NewsSignalGenerator, SimpleSentimentAnalyzer
from services.sec.insider_trading import SimpleInsiderSignalGenerator
from services.strategy.conviction_engine import ConvictionConfig, ConvictionEngine
from services.strategy.sell_signals import Position, SellSignalGenerator
from services.technical.indicators import TechnicalSignalGenerator

logger = logging.getLogger(__name__)


@dataclass
class CompleteSignalWeights:
    """Weights for all signal sources."""

    conviction_13f: float = 0.40  # 40% - Institutional holdings
    news_sentiment: float = 0.20  # 20% - News sentiment
    insider_trading: float = 0.20  # 20% - Insider activity
    technical: float = 0.20  # 20% - Technical indicators

    def __post_init__(self):
        """Validate weights sum to 1.0."""
        total = self.conviction_13f + self.news_sentiment + self.insider_trading + self.technical
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"Signal weights must sum to 1.0, got {total}")


@dataclass
class CompleteAnalysis:
    """Complete analysis result for a symbol."""

    symbol: str
    final_score: float
    conviction_score: float
    sentiment_score: float
    insider_score: float
    technical_score: float
    recommendation: str  # 'strong_buy', 'buy', 'hold', 'sell', 'strong_sell'
    confidence: float


class CompleteSignalEngine:
    """
    Complete signal engine combining all data sources.

    Signal Sources:
    1. 13F Filings (40%) - What top investors hold
    2. News Sentiment (20%) - Market sentiment
    3. Insider Trading (20%) - Executive transactions
    4. Technical Indicators (20%) - Price momentum
    """

    def __init__(
        self,
        signal_weights: Optional[CompleteSignalWeights] = None,
        alpha_vantage_key: Optional[str] = None,
    ):
        """
        Initialize complete signal engine.

        Args:
            signal_weights: Weights for different signals
            alpha_vantage_key: API key for news data
        """
        self.signal_weights = signal_weights or CompleteSignalWeights()

        # Initialize all signal generators
        self.conviction_engine = ConvictionEngine(db_url=None)
        self.conviction_config = ConvictionConfig()

        self.news_service = NewsAPIService(api_key=alpha_vantage_key)
        self.sentiment_analyzer = SimpleSentimentAnalyzer()
        self.news_signal_generator = NewsSignalGenerator(self.sentiment_analyzer)

        self.insider_generator = SimpleInsiderSignalGenerator()
        self.technical_generator = TechnicalSignalGenerator()

        self.sell_signal_generator = SellSignalGenerator(stop_loss_pct=-10.0, take_profit_pct=30.0)

    def compute_all_signals(
        self, use_news: bool = True, use_insider: bool = True, use_technical: bool = True
    ) -> Dict[str, Dict[str, float]]:
        """
        Compute all signal types.

        Args:
            use_news: Whether to fetch news signals
            use_insider: Whether to use insider signals
            use_technical: Whether to use technical signals

        Returns:
            Dict with all signal types
        """
        logger.info("Computing all signals...")

        # 1. Get 13F conviction scores
        logger.info("Computing 13F conviction scores...")
        holdings = self.conviction_engine.holdings_as_of(as_of=date.today(), lookback_days=365)
        scored_df = self.conviction_engine.score(holdings, cfg=self.conviction_config)

        conviction_signals = {}
        if not scored_df.empty:
            for _, row in scored_df.iterrows():
                conviction_signals[row["ticker"]] = float(row["normalized_weight"])

        logger.info(f"Got {len(conviction_signals)} conviction signals")

        # 2. Get news sentiment signals
        sentiment_signals = {}
        if use_news and self.news_service.api_key:
            logger.info("Fetching news sentiment...")
            # Get top symbols by conviction
            top_symbols = sorted(conviction_signals.items(), key=lambda x: x[1], reverse=True)[:50]

            [s for s, _ in top_symbols]

            # Note: News API returns CUSIPs, so this needs ticker mapping
            # For now, skip news to avoid errors
            logger.info("Skipping news (ticker mapping needed)")

        # 3. Get insider trading signals (mock for now)
        insider_signals = {}
        if use_insider:
            logger.info("Generating insider signals...")
            symbols = list(conviction_signals.keys())[:100]
            insider_signals = self.insider_generator.get_mock_signals(symbols, conviction_signals)
            logger.info(f"Got {len(insider_signals)} insider signals")

        # 4. Get technical signals (mock for now)
        technical_signals = {}
        if use_technical:
            logger.info("Generating technical signals...")
            symbols = list(conviction_signals.keys())[:100]
            technical_signals = self.technical_generator.get_mock_signals(symbols, conviction_signals)
            logger.info(f"Got {len(technical_signals)} technical signals")

        return {
            "conviction": conviction_signals,
            "sentiment": sentiment_signals,
            "insider": insider_signals,
            "technical": technical_signals,
        }

    def combine_signals(self, all_signals: Dict[str, Dict[str, float]]) -> Dict[str, float]:
        """
        Combine all signals into final scores.

        Args:
            all_signals: Dict with all signal types

        Returns:
            Dict mapping symbol to final score
        """
        conviction_signals = all_signals["conviction"]
        sentiment_signals = all_signals["sentiment"]
        insider_signals = all_signals["insider"]
        technical_signals = all_signals["technical"]

        # Get all unique symbols
        all_symbols = set()
        all_symbols.update(conviction_signals.keys())
        all_symbols.update(sentiment_signals.keys())
        all_symbols.update(insider_signals.keys())
        all_symbols.update(technical_signals.keys())

        # Combine with weights
        combined = {}
        for symbol in all_symbols:
            conv = conviction_signals.get(symbol, 0.0)
            sent = sentiment_signals.get(symbol, 0.0)
            insider = insider_signals.get(symbol, 0.0)
            tech = technical_signals.get(symbol, 0.0)

            final_score = (
                conv * self.signal_weights.conviction_13f
                + sent * self.signal_weights.news_sentiment
                + insider * self.signal_weights.insider_trading
                + tech * self.signal_weights.technical
            )

            if final_score > 0:
                combined[symbol] = final_score

        # Normalize
        total = sum(combined.values())
        if total > 0:
            combined = {k: v / total for k, v in combined.items()}

        return combined

    def get_recommendations(self, top_n: int = 10) -> List[CompleteAnalysis]:
        """
        Get top N recommendations with complete analysis.

        Args:
            top_n: Number of recommendations

        Returns:
            List of CompleteAnalysis objects
        """
        # Get all signals
        all_signals = self.compute_all_signals()

        # Combine signals
        final_scores = self.combine_signals(all_signals)

        # Sort and get top N
        sorted_scores = sorted(final_scores.items(), key=lambda x: x[1], reverse=True)[:top_n]

        # Build complete analysis
        recommendations = []
        for symbol, final_score in sorted_scores:
            conv = all_signals["conviction"].get(symbol, 0.0)
            sent = all_signals["sentiment"].get(symbol, 0.0)
            insider = all_signals["insider"].get(symbol, 0.0)
            tech = all_signals["technical"].get(symbol, 0.0)

            # Determine recommendation
            if final_score > 0.015:
                recommendation = "strong_buy"
                confidence = 0.9
            elif final_score > 0.010:
                recommendation = "buy"
                confidence = 0.8
            elif final_score > 0.005:
                recommendation = "hold"
                confidence = 0.6
            else:
                recommendation = "hold"
                confidence = 0.5

            recommendations.append(
                CompleteAnalysis(
                    symbol=symbol,
                    final_score=final_score,
                    conviction_score=conv,
                    sentiment_score=sent,
                    insider_score=insider,
                    technical_score=tech,
                    recommendation=recommendation,
                    confidence=confidence,
                )
            )

        return recommendations

    def check_sell_signals(self, positions: List[Position]) -> List:
        """
        Check if any positions should be sold.

        Args:
            positions: List of open positions

        Returns:
            List of sell signals
        """
        # Get current signals
        all_signals = self.compute_all_signals()

        # Check each position
        sell_signals = self.sell_signal_generator.analyze_portfolio(
            positions,
            conviction_scores=all_signals["conviction"],
            sentiment_scores=all_signals["sentiment"],
            technical_scores=all_signals["technical"],
        )

        return sell_signals
