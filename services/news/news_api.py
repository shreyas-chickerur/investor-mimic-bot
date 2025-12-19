"""
News API Service - Fetch financial news from multiple sources.
"""

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


@dataclass
class NewsArticle:
    """Represents a news article."""

    title: str
    description: str
    source: str
    published_at: datetime
    url: str
    symbols: List[str]  # Stock symbols mentioned


class NewsAPIService:
    """
    Fetch financial news from Alpha Vantage and other sources.
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize news service.

        Args:
            api_key: Alpha Vantage API key (or from env)
        """
        self.api_key = api_key or os.getenv("ALPHA_VANTAGE_API_KEY")
        self.base_url = "https://www.alphavantage.co/query"

    def fetch_news_for_symbol(self, symbol: str, limit: int = 50) -> List[NewsArticle]:
        """
        Fetch recent news for a specific stock symbol.

        Args:
            symbol: Stock ticker symbol
            limit: Maximum number of articles

        Returns:
            List of NewsArticle objects
        """
        if not self.api_key:
            logger.warning("No Alpha Vantage API key configured")
            return []

        try:
            params = {
                "function": "NEWS_SENTIMENT",
                "tickers": symbol,
                "apikey": self.api_key,
                "limit": limit,
            }

            response = requests.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if "feed" not in data:
                logger.warning(f"No news feed in response for {symbol}")
                return []

            articles = []
            for item in data["feed"]:
                try:
                    # Parse published time
                    time_str = item.get("time_published", "")
                    published_at = datetime.strptime(time_str, "%Y%m%dT%H%M%S")

                    # Extract symbols
                    ticker_sentiment = item.get("ticker_sentiment", [])
                    symbols = [ts.get("ticker") for ts in ticker_sentiment if ts.get("ticker")]

                    article = NewsArticle(
                        title=item.get("title", ""),
                        description=item.get("summary", ""),
                        source=item.get("source", "Unknown"),
                        published_at=published_at,
                        url=item.get("url", ""),
                        symbols=symbols,
                    )
                    articles.append(article)

                except Exception as e:
                    logger.debug(f"Error parsing article: {e}")
                    continue

            logger.info(f"Fetched {len(articles)} articles for {symbol}")
            return articles

        except Exception as e:
            logger.error(f"Error fetching news for {symbol}: {e}")
            return []

    def fetch_news_batch(
        self, symbols: List[str], limit_per_symbol: int = 20
    ) -> Dict[str, List[NewsArticle]]:
        """
        Fetch news for multiple symbols.

        Args:
            symbols: List of stock symbols
            limit_per_symbol: Articles per symbol

        Returns:
            Dictionary mapping symbol to articles
        """
        results = {}

        for symbol in symbols:
            articles = self.fetch_news_for_symbol(symbol, limit=limit_per_symbol)
            if articles:
                results[symbol] = articles

        return results

    def fetch_market_news(self, limit: int = 50) -> List[NewsArticle]:
        """
        Fetch general market news (not symbol-specific).

        Args:
            limit: Maximum number of articles

        Returns:
            List of NewsArticle objects
        """
        if not self.api_key:
            logger.warning("No Alpha Vantage API key configured")
            return []

        try:
            params = {"function": "NEWS_SENTIMENT", "apikey": self.api_key, "limit": limit}

            response = requests.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if "feed" not in data:
                return []

            articles = []
            for item in data["feed"]:
                try:
                    time_str = item.get("time_published", "")
                    published_at = datetime.strptime(time_str, "%Y%m%dT%H%M%S")

                    ticker_sentiment = item.get("ticker_sentiment", [])
                    symbols = [ts.get("ticker") for ts in ticker_sentiment if ts.get("ticker")]

                    article = NewsArticle(
                        title=item.get("title", ""),
                        description=item.get("summary", ""),
                        source=item.get("source", "Unknown"),
                        published_at=published_at,
                        url=item.get("url", ""),
                        symbols=symbols,
                    )
                    articles.append(article)

                except Exception as e:
                    logger.debug(f"Error parsing article: {e}")
                    continue

            logger.info(f"Fetched {len(articles)} market news articles")
            return articles

        except Exception as e:
            logger.error(f"Error fetching market news: {e}")
            return []
