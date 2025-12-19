"""
Feature Engineering Pipeline

Creates comprehensive features from all data sources for ML training.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List
import json

from utils.enhanced_logging import get_logger
from db.connection_pool import get_db_session

logger = get_logger(__name__)


class FeatureEngineer:
    """Creates ML features from raw data."""

    def __init__(self):
        self.feature_names = []

    def create_features_for_ticker(self, ticker: str, date: datetime) -> Dict:
        """
        Create comprehensive features for a ticker on a specific date.

        Args:
            ticker: Stock ticker
            date: Date for feature calculation

        Returns:
            Dictionary of features
        """
        features = {}

        # Get all data sources
        features.update(self._get_13f_features(ticker, date))
        features.update(self._get_news_features(ticker, date))
        features.update(self._get_technical_features(ticker, date))
        features.update(self._get_fundamental_features(ticker, date))
        features.update(self._get_social_features(ticker, date))

        return features

    def _get_13f_features(self, ticker: str, date: datetime) -> Dict:
        """Extract 13F-based features."""
        features = {}

        with get_db_session() as session:
            # Get recent 13F data
            query = """
                SELECT 
                    COUNT(DISTINCT investor_id) as num_investors,
                    SUM(shares) as total_shares,
                    AVG(shares) as avg_shares,
                    SUM(CASE WHEN change_type = 'NEW' THEN 1 ELSE 0 END) as new_positions,
                    SUM(CASE WHEN change_type = 'INCREASED' THEN 1 ELSE 0 END) as increased_positions,
                    SUM(CASE WHEN change_type = 'DECREASED' THEN 1 ELSE 0 END) as decreased_positions
                FROM holdings
                WHERE ticker = :ticker
                  AND filing_date <= :date
                  AND filing_date >= :date - INTERVAL '180 days'
            """

            result = session.execute(query, {"ticker": ticker, "date": date})
            row = result.fetchone()

            if row:
                features["13f_num_investors"] = float(row[0] or 0)
                features["13f_total_shares"] = float(row[1] or 0)
                features["13f_avg_shares"] = float(row[2] or 0)
                features["13f_new_positions"] = float(row[3] or 0)
                features["13f_increased_positions"] = float(row[4] or 0)
                features["13f_decreased_positions"] = float(row[5] or 0)

                # Calculate conviction score
                total_changes = (
                    features["13f_new_positions"]
                    + features["13f_increased_positions"]
                    + features["13f_decreased_positions"]
                )
                if total_changes > 0:
                    features["13f_conviction"] = (
                        features["13f_new_positions"] + features["13f_increased_positions"]
                    ) / total_changes
                else:
                    features["13f_conviction"] = 0.5

            # Get investor performance correlation
            query = """
                SELECT AVG(ip.quarterly_return)
                FROM holdings h
                JOIN investor_performance ip ON h.investor_id = ip.investor_id
                WHERE h.ticker = :ticker
                  AND h.filing_date <= :date
                  AND ip.quarter <= :date
                  AND ip.quarter >= :date - INTERVAL '365 days'
            """

            result = session.execute(query, {"ticker": ticker, "date": date})
            row = result.fetchone()
            features["13f_investor_avg_return"] = float(row[0] or 0) if row else 0.0

        return features

    def _get_news_features(self, ticker: str, date: datetime) -> Dict:
        """Extract news sentiment features."""
        features = {}

        with get_db_session() as session:
            # Get recent news sentiment
            for days in [7, 30, 90]:
                query = """
                    SELECT 
                        AVG(sentiment_score) as avg_sentiment,
                        COUNT(*) as article_count,
                        SUM(CASE WHEN sentiment_label = 'Bullish' THEN 1 ELSE 0 END) as bullish_count,
                        SUM(CASE WHEN sentiment_label = 'Bearish' THEN 1 ELSE 0 END) as bearish_count
                    FROM news_articles
                    WHERE ticker = :ticker
                      AND published_at <= :date
                      AND published_at >= :date - INTERVAL ':days days'
                """

                result = session.execute(query, {"ticker": ticker, "date": date, "days": days})
                row = result.fetchone()

                if row:
                    features[f"news_sentiment_{days}d"] = float(row[0] or 0)
                    features[f"news_count_{days}d"] = float(row[1] or 0)
                    features[f"news_bullish_{days}d"] = float(row[2] or 0)
                    features[f"news_bearish_{days}d"] = float(row[3] or 0)

                    # Calculate sentiment ratio
                    total = features[f"news_bullish_{days}d"] + features[f"news_bearish_{days}d"]
                    if total > 0:
                        features[f"news_sentiment_ratio_{days}d"] = features[f"news_bullish_{days}d"] / total
                    else:
                        features[f"news_sentiment_ratio_{days}d"] = 0.5

        return features

    def _get_technical_features(self, ticker: str, date: datetime) -> Dict:
        """Extract technical indicator features."""
        features = {}

        with get_db_session() as session:
            query = """
                SELECT 
                    rsi_14, macd, macd_signal, bollinger_width,
                    atr_14, adx_14, stochastic_k, stochastic_d,
                    volume_ratio, momentum_10, momentum_20,
                    roc_10, roc_20, williams_r, cci
                FROM technical_indicators
                WHERE ticker = :ticker
                  AND date = :date
            """

            result = session.execute(query, {"ticker": ticker, "date": date})
            row = result.fetchone()

            if row:
                feature_names = [
                    "rsi_14",
                    "macd",
                    "macd_signal",
                    "bollinger_width",
                    "atr_14",
                    "adx_14",
                    "stochastic_k",
                    "stochastic_d",
                    "volume_ratio",
                    "momentum_10",
                    "momentum_20",
                    "roc_10",
                    "roc_20",
                    "williams_r",
                    "cci",
                ]

                for i, name in enumerate(feature_names):
                    features[f"tech_{name}"] = float(row[i] or 0)

        return features

    def _get_fundamental_features(self, ticker: str, date: datetime) -> Dict:
        """Extract fundamental features."""
        features = {}

        with get_db_session() as session:
            query = """
                SELECT 
                    revenue_growth, earnings_growth, profit_margin,
                    roe, debt_to_equity, pe_ratio, pb_ratio,
                    ps_ratio, peg_ratio, dividend_yield
                FROM fundamentals
                WHERE ticker = :ticker
                  AND quarter <= :date
                ORDER BY quarter DESC
                LIMIT 1
            """

            result = session.execute(query, {"ticker": ticker, "date": date})
            row = result.fetchone()

            if row:
                feature_names = [
                    "revenue_growth",
                    "earnings_growth",
                    "profit_margin",
                    "roe",
                    "debt_to_equity",
                    "pe_ratio",
                    "pb_ratio",
                    "ps_ratio",
                    "peg_ratio",
                    "dividend_yield",
                ]

                for i, name in enumerate(feature_names):
                    features[f"fund_{name}"] = float(row[i] or 0)

        return features

    def _get_social_features(self, ticker: str, date: datetime) -> Dict:
        """Extract social sentiment features."""
        features = {}

        with get_db_session() as session:
            query = """
                SELECT 
                    AVG(sentiment_score) as avg_sentiment,
                    SUM(mention_count) as total_mentions,
                    AVG(trending_score) as avg_trending
                FROM social_sentiment
                WHERE ticker = :ticker
                  AND date <= :date
                  AND date >= :date - INTERVAL '7 days'
            """

            result = session.execute(query, {"ticker": ticker, "date": date})
            row = result.fetchone()

            if row:
                features["social_sentiment_7d"] = float(row[0] or 0)
                features["social_mentions_7d"] = float(row[1] or 0)
                features["social_trending_7d"] = float(row[2] or 0)

        return features

    def calculate_target_returns(self, ticker: str, date: datetime) -> Dict:
        """
        Calculate target returns for different horizons.

        Args:
            ticker: Stock ticker
            date: Current date

        Returns:
            Dictionary of target returns
        """
        targets = {}

        with get_db_session() as session:
            # Get current price
            query = """
                SELECT close 
                FROM price_history 
                WHERE ticker = :ticker AND date = :date
            """
            result = session.execute(query, {"ticker": ticker, "date": date})
            row = result.fetchone()

            if not row:
                return targets

            current_price = float(row[0])

            # Calculate returns for different horizons
            for days in [1, 5, 10, 20]:
                future_date = date + timedelta(days=days)
                query = """
                    SELECT close 
                    FROM price_history 
                    WHERE ticker = :ticker 
                      AND date >= :future_date
                    ORDER BY date ASC
                    LIMIT 1
                """

                result = session.execute(query, {"ticker": ticker, "future_date": future_date})
                row = result.fetchone()

                if row:
                    future_price = float(row[0])
                    targets[f"target_return_{days}d"] = (future_price - current_price) / current_price
                else:
                    targets[f"target_return_{days}d"] = None

        return targets

    def create_training_samples(self, tickers: List[str], start_date: datetime, end_date: datetime):
        """
        Create training samples for all tickers over date range.

        Args:
            tickers: List of stock tickers
            start_date: Start date
            end_date: End date
        """
        logger.info(f"Creating training samples for {len(tickers)} tickers from {start_date} to {end_date}")

        samples_created = 0

        for ticker in tickers:
            current_date = start_date

            while current_date <= end_date:
                try:
                    # Create features
                    features = self.create_features_for_ticker(ticker, current_date)

                    if not features:
                        current_date += timedelta(days=1)
                        continue

                    # Calculate targets
                    targets = self.calculate_target_returns(ticker, current_date)

                    # Store in database
                    self._store_training_sample(ticker, current_date, features, targets)

                    samples_created += 1

                    if samples_created % 100 == 0:
                        logger.info(f"Created {samples_created} training samples...")

                except Exception as e:
                    logger.error(f"Error creating sample for {ticker} on {current_date}: {e}")

                current_date += timedelta(days=1)

        logger.info(f"Total training samples created: {samples_created}")

    def _store_training_sample(self, ticker: str, date: datetime, features: Dict, targets: Dict):
        """Store training sample in database."""
        with get_db_session() as session:
            try:
                session.execute(
                    """
                    INSERT INTO training_data 
                    (ticker, date, features, target_return_1d, target_return_5d, 
                     target_return_10d, target_return_20d)
                    VALUES (:ticker, :date, :features, :t1d, :t5d, :t10d, :t20d)
                    ON CONFLICT (ticker, date) DO UPDATE SET
                        features = EXCLUDED.features,
                        target_return_1d = EXCLUDED.target_return_1d,
                        target_return_5d = EXCLUDED.target_return_5d,
                        target_return_10d = EXCLUDED.target_return_10d,
                        target_return_20d = EXCLUDED.target_return_20d
                    """,
                    {
                        "ticker": ticker,
                        "date": date,
                        "features": json.dumps(features),
                        "t1d": targets.get("target_return_1d"),
                        "t5d": targets.get("target_return_5d"),
                        "t10d": targets.get("target_return_10d"),
                        "t20d": targets.get("target_return_20d"),
                    },
                )
            except Exception as e:
                logger.error(f"Error storing training sample: {e}")


def generate_training_data(tickers: List[str], years: int = 3):
    """
    Generate training data for tickers.

    Args:
        tickers: List of stock tickers
        years: Years of historical data
    """
    engineer = FeatureEngineer()

    end_date = datetime.now()
    start_date = end_date - timedelta(days=years * 365)

    engineer.create_training_samples(tickers, start_date, end_date)


if __name__ == "__main__":
    # Example usage
    sp500_tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]  # Add more
    generate_training_data(sp500_tickers, years=3)
