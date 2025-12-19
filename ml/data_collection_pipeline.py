"""
Enhanced Data Collection Pipeline

Collects comprehensive data from multiple sources for ML training.
"""

import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from utils.enhanced_logging import get_logger
from utils.rate_limiter import RateLimiter
from db.connection_pool import get_db_session

logger = get_logger(__name__)


class EnhancedDataCollector:
    """Collects comprehensive data for ML training."""

    def __init__(self):
        self.rate_limiters = {
            "alpha_vantage": RateLimiter(calls_per_window=5, window_seconds=60),
            "finnhub": RateLimiter(calls_per_window=60, window_seconds=60),
            "newsapi": RateLimiter(calls_per_window=100, window_seconds=86400),
        }

    def collect_historical_13f_data(self, years: int = 5) -> pd.DataFrame:
        """
        Collect comprehensive historical 13F data.

        Args:
            years: Number of years of historical data

        Returns:
            DataFrame with historical 13F data
        """
        logger.info(f"Collecting {years} years of historical 13F data")

        from services.sec.edgar_fetcher import fetch_13f_filings

        end_date = datetime.now()
        start_date = end_date - timedelta(days=years * 365)

        all_filings = []

        # Collect quarterly filings
        current_date = start_date
        while current_date <= end_date:
            try:
                filings = fetch_13f_filings(current_date)
                all_filings.extend(filings)
                logger.info(f"Collected {len(filings)} filings for {current_date.date()}")
            except Exception as e:
                logger.error(f"Error collecting 13F data for {current_date}: {e}")

            # Move to next quarter
            current_date += timedelta(days=90)

        df = pd.DataFrame(all_filings)
        logger.info(f"Total 13F records collected: {len(df)}")

        return df

    def collect_news_sentiment(self, ticker: str, days: int = 30) -> List[Dict]:
        """
        Collect news sentiment from multiple sources.

        Args:
            ticker: Stock ticker
            days: Number of days of historical news

        Returns:
            List of news articles with sentiment
        """
        articles = []

        # Alpha Vantage News
        try:
            self.rate_limiters["alpha_vantage"].acquire()
            av_articles = self._fetch_alpha_vantage_news(ticker)
            articles.extend(av_articles)
        except Exception as e:
            logger.error(f"Alpha Vantage news error for {ticker}: {e}")

        # Finnhub News
        try:
            self.rate_limiters["finnhub"].acquire()
            fh_articles = self._fetch_finnhub_news(ticker, days)
            articles.extend(fh_articles)
        except Exception as e:
            logger.error(f"Finnhub news error for {ticker}: {e}")

        logger.info(f"Collected {len(articles)} news articles for {ticker}")
        return articles

    def _fetch_alpha_vantage_news(self, ticker: str) -> List[Dict]:
        """Fetch news from Alpha Vantage."""
        from utils.environment import env

        api_key = env.get("ALPHA_VANTAGE_API_KEY")
        if not api_key:
            return []

        url = "https://www.alphavantage.co/query"
        params = {"function": "NEWS_SENTIMENT", "tickers": ticker, "apikey": api_key, "limit": 50}

        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()

        data = response.json()
        articles = []

        for item in data.get("feed", []):
            articles.append(
                {
                    "ticker": ticker,
                    "source": "alpha_vantage",
                    "title": item.get("title"),
                    "content": item.get("summary"),
                    "sentiment_score": float(item.get("overall_sentiment_score", 0)),
                    "sentiment_label": item.get("overall_sentiment_label"),
                    "published_at": datetime.strptime(item.get("time_published"), "%Y%m%dT%H%M%S"),
                    "relevance_score": float(item.get("relevance_score", 0)),
                }
            )

        return articles

    def _fetch_finnhub_news(self, ticker: str, days: int) -> List[Dict]:
        """Fetch news from Finnhub."""
        from utils.environment import env

        api_key = env.get("FINNHUB_API_KEY")
        if not api_key:
            return []

        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        url = "https://finnhub.io/api/v1/company-news"
        params = {
            "symbol": ticker,
            "from": start_date.strftime("%Y-%m-%d"),
            "to": end_date.strftime("%Y-%m-%d"),
            "token": api_key,
        }

        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()

        data = response.json()
        articles = []

        for item in data:
            # Simple sentiment analysis (would use NLP model in production)
            sentiment_score = self._analyze_sentiment(item.get("headline", "") + " " + item.get("summary", ""))

            articles.append(
                {
                    "ticker": ticker,
                    "source": "finnhub",
                    "title": item.get("headline"),
                    "content": item.get("summary"),
                    "sentiment_score": sentiment_score,
                    "sentiment_label": self._sentiment_label(sentiment_score),
                    "published_at": datetime.fromtimestamp(item.get("datetime")),
                    "relevance_score": 1.0,
                }
            )

        return articles

    def _analyze_sentiment(self, text: str) -> float:
        """Simple sentiment analysis (placeholder for NLP model)."""
        # In production, use transformers or similar
        positive_words = ["beat", "surge", "growth", "profit", "gain", "up", "rise", "strong", "positive"]
        negative_words = ["miss", "drop", "loss", "decline", "down", "fall", "weak", "negative", "concern"]

        text_lower = text.lower()
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)

        total = positive_count + negative_count
        if total == 0:
            return 0.0

        return (positive_count - negative_count) / total

    def _sentiment_label(self, score: float) -> str:
        """Convert sentiment score to label."""
        if score > 0.2:
            return "Bullish"
        elif score < -0.2:
            return "Bearish"
        else:
            return "Neutral"

    def collect_fundamentals(self, ticker: str) -> Dict:
        """
        Collect fundamental data for a stock.

        Args:
            ticker: Stock ticker

        Returns:
            Dictionary of fundamental metrics
        """
        from utils.environment import env

        api_key = env.get("ALPHA_VANTAGE_API_KEY")
        if not api_key:
            return {}

        try:
            self.rate_limiters["alpha_vantage"].acquire()

            # Company overview
            url = "https://www.alphavantage.co/query"
            params = {"function": "OVERVIEW", "symbol": ticker, "apikey": api_key}

            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            fundamentals = {
                "ticker": ticker,
                "quarter": datetime.now().date(),
                "revenue": float(data.get("RevenueTTM", 0) or 0),
                "net_income": float(data.get("NetIncomeTTM", 0) or 0),
                "eps": float(data.get("EPS", 0) or 0),
                "revenue_growth": float(data.get("QuarterlyRevenueGrowthYOY", 0) or 0),
                "earnings_growth": float(data.get("QuarterlyEarningsGrowthYOY", 0) or 0),
                "profit_margin": float(data.get("ProfitMargin", 0) or 0),
                "roe": float(data.get("ReturnOnEquityTTM", 0) or 0),
                "debt_to_equity": float(data.get("DebtToEquity", 0) or 0),
                "pe_ratio": float(data.get("PERatio", 0) or 0),
                "pb_ratio": float(data.get("PriceToBookRatio", 0) or 0),
                "ps_ratio": float(data.get("PriceToSalesRatioTTM", 0) or 0),
                "peg_ratio": float(data.get("PEGRatio", 0) or 0),
                "dividend_yield": float(data.get("DividendYield", 0) or 0),
            }

            logger.info(f"Collected fundamentals for {ticker}")
            return fundamentals

        except Exception as e:
            logger.error(f"Error collecting fundamentals for {ticker}: {e}")
            return {}

    def collect_technical_indicators(self, ticker: str, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate comprehensive technical indicators.

        Args:
            ticker: Stock ticker
            df: DataFrame with OHLCV data

        Returns:
            DataFrame with technical indicators
        """
        from services.technical.advanced_features import AdvancedFeatureEngineer

        engineer = AdvancedFeatureEngineer()
        df_with_features = engineer.create_all_features(df)

        logger.info(f"Calculated {len(engineer.feature_names)} technical indicators for {ticker}")
        return df_with_features

    def store_news_articles(self, articles: List[Dict]):
        """Store news articles in database."""
        if not articles:
            return

        with get_db_session() as session:
            for article in articles:
                try:
                    session.execute(
                        """
                        INSERT INTO news_articles
                        (ticker, source, title, content, sentiment_score, sentiment_label,
                         published_at, relevance_score)
                        VALUES (:ticker, :source, :title, :content, :sentiment_score,
                                :sentiment_label, :published_at, :relevance_score)
                        ON CONFLICT DO NOTHING
                        """,
                        article,
                    )
                except Exception as e:
                    logger.error(f"Error storing news article: {e}")

        logger.info(f"Stored {len(articles)} news articles")

    def store_fundamentals(self, fundamentals: Dict):
        """Store fundamental data in database."""
        if not fundamentals:
            return

        with get_db_session() as session:
            try:
                session.execute(
                    """
                    INSERT INTO fundamentals
                    (ticker, quarter, revenue, net_income, eps, revenue_growth, earnings_growth,
                     profit_margin, roe, debt_to_equity, pe_ratio, pb_ratio, ps_ratio,
                     peg_ratio, dividend_yield)
                    VALUES (:ticker, :quarter, :revenue, :net_income, :eps, :revenue_growth,
                            :earnings_growth, :profit_margin, :roe, :debt_to_equity,
                            :pe_ratio, :pb_ratio, :ps_ratio, :peg_ratio, :dividend_yield)
                    ON CONFLICT (ticker, quarter)
                    DO UPDATE SET
                        revenue = EXCLUDED.revenue,
                        net_income = EXCLUDED.net_income,
                        eps = EXCLUDED.eps,
                        revenue_growth = EXCLUDED.revenue_growth,
                        earnings_growth = EXCLUDED.earnings_growth,
                        profit_margin = EXCLUDED.profit_margin,
                        roe = EXCLUDED.roe,
                        debt_to_equity = EXCLUDED.debt_to_equity,
                        pe_ratio = EXCLUDED.pe_ratio,
                        pb_ratio = EXCLUDED.pb_ratio,
                        ps_ratio = EXCLUDED.ps_ratio,
                        peg_ratio = EXCLUDED.peg_ratio,
                        dividend_yield = EXCLUDED.dividend_yield
                    """,
                    fundamentals,
                )
                logger.info(f"Stored fundamentals for {fundamentals['ticker']}")
            except Exception as e:
                logger.error(f"Error storing fundamentals: {e}")

    def update_collection_status(self, source: str, records: int, status: str, error: Optional[str] = None):
        """Update data collection status."""
        with get_db_session() as session:
            try:
                session.execute(
                    """
                    INSERT INTO data_collection_status
                    (data_source, last_collection_time, records_collected, status, error_message)
                    VALUES (:source, :time, :records, :status, :error)
                    """,
                    {
                        "source": source,
                        "time": datetime.now(),
                        "records": records,
                        "status": status,
                        "error": error,
                    },
                )
            except Exception as e:
                logger.error(f"Error updating collection status: {e}")


def collect_comprehensive_data(tickers: List[str], years: int = 3):
    """
    Collect comprehensive data for all tickers.

    Args:
        tickers: List of stock tickers
        years: Years of historical data
    """
    collector = EnhancedDataCollector()

    # Collect 13F data
    logger.info("Collecting historical 13F data...")
    try:
        df_13f = collector.collect_historical_13f_data(years=years)
        collector.update_collection_status("13f_filings", len(df_13f), "success")
    except Exception as e:
        logger.error(f"13F collection failed: {e}")
        collector.update_collection_status("13f_filings", 0, "failed", str(e))

    # Collect data for each ticker
    for ticker in tickers:
        logger.info(f"Collecting data for {ticker}...")

        # News sentiment
        try:
            articles = collector.collect_news_sentiment(ticker, days=90)
            collector.store_news_articles(articles)
            collector.update_collection_status(f"news_{ticker}", len(articles), "success")
        except Exception as e:
            logger.error(f"News collection failed for {ticker}: {e}")
            collector.update_collection_status(f"news_{ticker}", 0, "failed", str(e))

        # Fundamentals
        try:
            fundamentals = collector.collect_fundamentals(ticker)
            collector.store_fundamentals(fundamentals)
            collector.update_collection_status(f"fundamentals_{ticker}", 1, "success")
        except Exception as e:
            logger.error(f"Fundamentals collection failed for {ticker}: {e}")
            collector.update_collection_status(f"fundamentals_{ticker}", 0, "failed", str(e))

    logger.info("Data collection complete!")
