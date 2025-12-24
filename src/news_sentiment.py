#!/usr/bin/env python3
"""
News Sentiment Provider
Fetches sentiment scores for symbols using external news APIs.
"""
import os
import logging
from typing import Optional
import requests

logger = logging.getLogger(__name__)


class NewsSentimentProvider:
    """Fetch sentiment scores from a configured provider."""

    def __init__(self):
        self.provider = os.getenv("NEWS_SENTIMENT_PROVIDER", "newsapi").lower()
        self.api_key = os.getenv("NEWS_API_KEY")
        self.enabled = bool(self.api_key)

        if not self.enabled:
            logger.warning("News sentiment disabled: NEWS_API_KEY not set")

    def get_sentiment_score(self, symbol: str) -> Optional[float]:
        """Return sentiment score in [0,1] or None if unavailable."""
        if not self.enabled:
            return None

        if self.provider == "newsapi":
            return self._get_newsapi_sentiment(symbol)

        logger.warning(f"Unknown sentiment provider: {self.provider}")
        return None

    def _get_newsapi_sentiment(self, symbol: str) -> Optional[float]:
        url = "https://newsapi.org/v2/everything"
        params = {
            "q": symbol,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": 20,
            "apiKey": self.api_key,
        }

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            articles = data.get("articles", [])
            if not articles:
                return 0.5

            positive = 0
            negative = 0
            for article in articles:
                title = (article.get("title") or "").lower()
                if any(word in title for word in ["beat", "surge", "strong", "growth", "upgrade"]):
                    positive += 1
                if any(word in title for word in ["miss", "drop", "weak", "downgrade", "lawsuit"]):
                    negative += 1

            score = 0.5 + (positive - negative) / max(len(articles), 1) / 2
            return max(0.0, min(1.0, score))
        except Exception as exc:
            logger.error(f"News sentiment fetch failed for {symbol}: {exc}")
            return None
