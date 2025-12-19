"""
Multi-Signal Strategy Engine - Combines multiple data sources for trading decisions.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

from services.news.news_api import NewsAPIService
from services.news.sentiment_analyzer import NewsSignalGenerator, SimpleSentimentAnalyzer
from services.strategy.conviction_engine import ConvictionConfig, ConvictionEngine

logger = logging.getLogger(__name__)


@dataclass
class SignalWeights:
    """Weights for different signal sources."""

    conviction_13f: float = 0.70  # 70% weight on 13F filings
    news_sentiment: float = 0.30  # 30% weight on news sentiment

    def __post_init__(self):
        """Validate weights sum to 1.0."""
        total = self.conviction_13f + self.news_sentiment
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"Signal weights must sum to 1.0, got {total}")


@dataclass
class MultiSignalResult:
    """Result from multi-signal analysis."""

    symbol: str
    combined_score: float
    conviction_score: float
    sentiment_score: float
    article_count: int
    confidence: float


class MultiSignalEngine:
    """
    Combines multiple signal sources for better trading decisions.

    Currently supports:
    - 13F filings (conviction-based)
    - News sentiment analysis

    Future additions:
    - Insider trading (Form 4)
    - Technical indicators
    - Options flow
    """

    def __init__(
        self,
        conviction_config: Optional[ConvictionConfig] = None,
        signal_weights: Optional[SignalWeights] = None,
        alpha_vantage_key: Optional[str] = None,
    ):
        """
        Initialize multi-signal engine.

        Args:
            conviction_config: Configuration for 13F conviction engine
            signal_weights: Weights for different signals
            alpha_vantage_key: API key for news data
        """
        # ConvictionEngine expects db_url, not config
        self.conviction_engine = ConvictionEngine(db_url=None)  # Uses default from settings
        self.conviction_config = conviction_config or ConvictionConfig()
        self.signal_weights = signal_weights or SignalWeights()

        self.news_service = NewsAPIService(api_key=alpha_vantage_key)
        self.sentiment_analyzer = SimpleSentimentAnalyzer()
        self.signal_generator = NewsSignalGenerator(self.sentiment_analyzer)

    def compute_multi_signal_scores(
        self, fetch_news: bool = True, news_lookback_hours: int = 48
    ) -> Dict[str, float]:
        """
        Compute combined scores from all signal sources.

        Args:
            fetch_news: Whether to fetch and analyze news
            news_lookback_hours: Hours of news to analyze

        Returns:
            Dictionary mapping symbol to combined score
        """
        logger.info("Computing multi-signal scores...")

        # 1. Get 13F conviction scores
        logger.info("Computing 13F conviction scores...")
        from datetime import date

        # Get holdings and compute scores (use 365 days lookback)
        holdings = self.conviction_engine.holdings_as_of(as_of=date.today(), lookback_days=365)

        scored_df = self.conviction_engine.score(holdings, cfg=self.conviction_config)

        # Convert to dict
        conviction_weights = {}
        if not scored_df.empty:
            for _, row in scored_df.iterrows():
                conviction_weights[row["ticker"]] = float(row["normalized_weight"])

        logger.info(f"Got conviction scores for {len(conviction_weights)} securities")

        if not fetch_news or not self.news_service.api_key:
            logger.info("Skipping news analysis (disabled or no API key)")
            return conviction_weights

        # 2. Get news sentiment for top conviction picks
        logger.info("Fetching news for top securities...")
        top_symbols = sorted(conviction_weights.items(), key=lambda x: x[1], reverse=True)[
            :50
        ]  # Top 50 by conviction

        symbols_to_check = [s for s, _ in top_symbols]

        # Fetch news
        articles_by_symbol = self.news_service.fetch_news_batch(
            symbols_to_check, limit_per_symbol=20
        )

        if not articles_by_symbol:
            logger.warning("No news articles fetched")
            return conviction_weights

        logger.info(f"Fetched news for {len(articles_by_symbol)} symbols")

        # 3. Analyze sentiment
        logger.info("Analyzing news sentiment...")
        sentiment_scores = self.sentiment_analyzer.analyze_batch(articles_by_symbol)

        # 4. Generate sentiment signals
        sentiment_signals = self.signal_generator.generate_signals(
            sentiment_scores, min_confidence=0.3, min_score=0.2
        )

        logger.info(f"Generated sentiment signals for {len(sentiment_signals)} symbols")

        # 5. Combine signals
        logger.info("Combining signals...")
        combined_weights = self.signal_generator.combine_with_conviction(
            conviction_weights,
            sentiment_signals,
            sentiment_weight=self.signal_weights.news_sentiment,
        )

        logger.info(f"Final combined scores for {len(combined_weights)} securities")

        return combined_weights

    def get_detailed_analysis(self, symbols: List[str]) -> List[MultiSignalResult]:
        """
        Get detailed multi-signal analysis for specific symbols.

        Args:
            symbols: List of stock symbols to analyze

        Returns:
            List of MultiSignalResult objects
        """
        # Get conviction scores
        conviction_weights = self.conviction_engine.compute_conviction_scores()

        # Fetch news
        articles_by_symbol = self.news_service.fetch_news_batch(symbols)

        # Analyze sentiment
        sentiment_scores = self.sentiment_analyzer.analyze_batch(articles_by_symbol)

        # Generate signals
        sentiment_signals = self.signal_generator.generate_signals(sentiment_scores)

        # Combine
        combined = self.signal_generator.combine_with_conviction(
            conviction_weights,
            sentiment_signals,
            sentiment_weight=self.signal_weights.news_sentiment,
        )

        # Build detailed results
        results = []
        for symbol in symbols:
            conv_score = conviction_weights.get(symbol, 0.0)
            sent_score = sentiment_signals.get(symbol, 0.0)
            combined_score = combined.get(symbol, 0.0)

            sentiment = sentiment_scores.get(symbol)
            article_count = sentiment.article_count if sentiment else 0
            confidence = sentiment.confidence if sentiment else 0.0

            results.append(
                MultiSignalResult(
                    symbol=symbol,
                    combined_score=combined_score,
                    conviction_score=conv_score,
                    sentiment_score=sent_score,
                    article_count=article_count,
                    confidence=confidence,
                )
            )

        return results

    def explain_recommendation(self, symbol: str) -> Dict:
        """
        Explain why a symbol is recommended.

        Args:
            symbol: Stock symbol

        Returns:
            Dictionary with explanation details
        """
        # Get conviction score
        conviction_weights = self.conviction_engine.compute_conviction_scores()
        conv_score = conviction_weights.get(symbol, 0.0)

        # Get news sentiment
        articles = self.news_service.fetch_news_for_symbol(symbol, limit=20)

        sentiment_score = 0.0
        article_count = 0
        recent_headlines = []

        if articles:
            sentiment_scores = self.sentiment_analyzer.analyze_batch({symbol: articles})
            if symbol in sentiment_scores:
                sentiment = sentiment_scores[symbol]
                sentiment_score = sentiment.score
                article_count = sentiment.article_count

            # Get recent headlines
            recent_headlines = [
                {
                    "title": a.title,
                    "source": a.source,
                    "published": a.published_at.strftime("%Y-%m-%d %H:%M"),
                    "sentiment": self.sentiment_analyzer.analyze_text(a.title),
                }
                for a in articles[:5]
            ]

        return {
            "symbol": symbol,
            "conviction_score": conv_score,
            "conviction_weight": self.signal_weights.conviction_13f,
            "sentiment_score": sentiment_score,
            "sentiment_weight": self.signal_weights.news_sentiment,
            "article_count": article_count,
            "recent_headlines": recent_headlines,
            "explanation": self._generate_explanation(conv_score, sentiment_score, article_count),
        }

    def _generate_explanation(
        self, conv_score: float, sent_score: float, article_count: int
    ) -> str:
        """Generate human-readable explanation."""
        parts = []

        if conv_score > 0:
            parts.append(f"Top investors hold this stock (conviction score: {conv_score:.3f})")

        if sent_score > 0.3:
            parts.append(f"Very positive news sentiment ({article_count} recent articles)")
        elif sent_score > 0:
            parts.append(f"Positive news sentiment ({article_count} recent articles)")
        elif sent_score < -0.3:
            parts.append(f"Negative news sentiment ({article_count} recent articles)")

        if not parts:
            return "No strong signals detected"

        return ". ".join(parts) + "."
