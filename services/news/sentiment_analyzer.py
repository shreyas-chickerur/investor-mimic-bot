"""
Sentiment Analysis Service - Analyze financial news sentiment.
Uses VADER for simple sentiment analysis (no ML dependencies needed).
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List

logger = logging.getLogger(__name__)


@dataclass
class SentimentScore:
    """Sentiment score for a stock."""

    symbol: str
    score: float  # -1 (very negative) to +1 (very positive)
    article_count: int
    latest_article_time: datetime
    confidence: float  # 0 to 1


class SimpleSentimentAnalyzer:
    """
    Simple rule-based sentiment analyzer for financial news.
    Uses keyword matching for speed and simplicity.
    """

    # Positive keywords
    POSITIVE_WORDS = {
        "beat",
        "beats",
        "surge",
        "surges",
        "soar",
        "soars",
        "rally",
        "rallies",
        "gain",
        "gains",
        "rise",
        "rises",
        "jump",
        "jumps",
        "upgrade",
        "upgraded",
        "strong",
        "strength",
        "bullish",
        "positive",
        "growth",
        "profit",
        "profits",
        "revenue",
        "earnings",
        "outperform",
        "outperforms",
        "breakthrough",
        "innovation",
        "success",
        "successful",
        "record",
        "high",
        "highs",
        "buy",
        "buying",
    }

    # Negative keywords
    NEGATIVE_WORDS = {
        "fall",
        "falls",
        "drop",
        "drops",
        "plunge",
        "plunges",
        "crash",
        "crashes",
        "decline",
        "declines",
        "loss",
        "losses",
        "miss",
        "misses",
        "downgrade",
        "downgraded",
        "weak",
        "weakness",
        "bearish",
        "negative",
        "concern",
        "concerns",
        "risk",
        "risks",
        "lawsuit",
        "investigation",
        "fraud",
        "scandal",
        "bankruptcy",
        "debt",
        "cut",
        "cuts",
        "layoff",
        "layoffs",
        "sell",
        "selling",
        "underperform",
        "underperforms",
    }

    def analyze_text(self, text: str) -> float:
        """
        Analyze sentiment of a text.

        Args:
            text: Text to analyze

        Returns:
            Sentiment score from -1 to +1
        """
        if not text:
            return 0.0

        text_lower = text.lower()
        words = text_lower.split()

        positive_count = sum(1 for word in words if word in self.POSITIVE_WORDS)
        negative_count = sum(1 for word in words if word in self.NEGATIVE_WORDS)

        total = positive_count + negative_count
        if total == 0:
            return 0.0

        # Normalize to -1 to +1
        score = (positive_count - negative_count) / total
        return max(-1.0, min(1.0, score))

    def analyze_articles(self, articles: List, recency_weight: float = 0.7) -> float:
        """
        Analyze sentiment across multiple articles.

        Args:
            articles: List of NewsArticle objects
            recency_weight: Weight for recent articles (0-1)

        Returns:
            Aggregate sentiment score
        """
        if not articles:
            return 0.0

        scores = []
        weights = []
        now = datetime.utcnow()

        for article in articles:
            # Analyze title and description
            title_score = self.analyze_text(article.title)
            desc_score = self.analyze_text(article.description)

            # Weight title more heavily
            article_score = (title_score * 0.6) + (desc_score * 0.4)

            # Calculate recency weight (exponential decay)
            hours_old = (now - article.published_at).total_seconds() / 3600
            recency = recency_weight ** (hours_old / 24)  # Decay over days

            scores.append(article_score)
            weights.append(recency)

        # Weighted average
        if sum(weights) == 0:
            return 0.0

        weighted_score = sum(s * w for s, w in zip(scores, weights)) / sum(weights)
        return weighted_score

    def analyze_batch(
        self, articles_by_symbol: Dict[str, List], min_articles: int = 3
    ) -> Dict[str, SentimentScore]:
        """
        Analyze sentiment for multiple symbols.

        Args:
            articles_by_symbol: Dict mapping symbol to articles
            min_articles: Minimum articles needed for confidence

        Returns:
            Dict mapping symbol to SentimentScore
        """
        results = {}

        for symbol, articles in articles_by_symbol.items():
            if not articles:
                continue

            score = self.analyze_articles(articles)

            # Calculate confidence based on article count
            confidence = min(1.0, len(articles) / 10.0)

            # Reduce confidence if too few articles
            if len(articles) < min_articles:
                confidence *= 0.5

            latest_time = max(a.published_at for a in articles)

            results[symbol] = SentimentScore(
                symbol=symbol,
                score=score,
                article_count=len(articles),
                latest_article_time=latest_time,
                confidence=confidence,
            )

        return results


class NewsSignalGenerator:
    """
    Generate trading signals from news sentiment.
    """

    def __init__(self, sentiment_analyzer: SimpleSentimentAnalyzer = None):
        self.analyzer = sentiment_analyzer or SimpleSentimentAnalyzer()

    def generate_signals(
        self,
        sentiment_scores: Dict[str, SentimentScore],
        min_confidence: float = 0.3,
        min_score: float = 0.2,
    ) -> Dict[str, float]:
        """
        Generate trading signals from sentiment scores.

        Args:
            sentiment_scores: Dict of SentimentScore objects
            min_confidence: Minimum confidence threshold
            min_score: Minimum absolute sentiment score

        Returns:
            Dict mapping symbol to signal strength (0-1)
        """
        signals = {}

        for symbol, sentiment in sentiment_scores.items():
            # Filter by confidence
            if sentiment.confidence < min_confidence:
                continue

            # Filter by minimum score
            if abs(sentiment.score) < min_score:
                continue

            # Only positive signals (for buying)
            if sentiment.score > 0:
                # Signal strength = sentiment * confidence
                signal = sentiment.score * sentiment.confidence
                signals[symbol] = signal

        return signals

    def combine_with_conviction(
        self,
        conviction_weights: Dict[str, float],
        sentiment_signals: Dict[str, float],
        sentiment_weight: float = 0.25,
    ) -> Dict[str, float]:
        """
        Combine sentiment signals with conviction scores.

        Args:
            conviction_weights: 13F-based conviction scores
            sentiment_signals: News sentiment signals
            sentiment_weight: Weight for sentiment (0-1)

        Returns:
            Combined weights
        """
        conviction_weight = 1.0 - sentiment_weight

        # Get all symbols
        all_symbols = set(conviction_weights.keys()) | set(sentiment_signals.keys())

        combined = {}
        for symbol in all_symbols:
            conv_score = conviction_weights.get(symbol, 0.0)
            sent_score = sentiment_signals.get(symbol, 0.0)

            # Weighted combination
            combined_score = (conv_score * conviction_weight) + (sent_score * sentiment_weight)

            if combined_score > 0:
                combined[symbol] = combined_score

        # Normalize
        total = sum(combined.values())
        if total > 0:
            combined = {k: v / total for k, v in combined.items()}

        return combined
