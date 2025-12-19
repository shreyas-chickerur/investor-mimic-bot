"""
Insider Trading Service - Fetch and analyze SEC Form 4 filings.
Form 4 reports insider transactions (executives buying/selling their own stock).
"""

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


@dataclass
class InsiderTransaction:
    """Represents an insider transaction."""

    symbol: str
    company_name: str
    insider_name: str
    insider_title: str
    transaction_date: datetime
    transaction_type: str  # 'buy' or 'sell'
    shares: float
    price_per_share: Optional[float]
    total_value: Optional[float]
    filing_date: datetime


class InsiderTradingService:
    """
    Fetch and analyze insider trading data from SEC EDGAR.
    """

    def __init__(self):
        self.base_url = "https://www.sec.gov/cgi-bin/browse-edgar"
        self.headers = {
            "User-Agent": "InvestorBot/1.0 (contact@example.com)",
            "Accept-Encoding": "gzip, deflate",
            "Host": "www.sec.gov",
        }

    def fetch_recent_insider_activity(
        self, symbol: str, days_back: int = 90
    ) -> List[InsiderTransaction]:
        """
        Fetch recent insider transactions for a symbol.

        Note: This is a simplified implementation. For production,
        consider using a dedicated API like Quiver Quantitative or
        parsing EDGAR XML directly.

        Args:
            symbol: Stock ticker
            days_back: Days to look back

        Returns:
            List of InsiderTransaction objects
        """
        # For now, return empty list as SEC EDGAR parsing is complex
        # In production, you'd either:
        # 1. Parse SEC EDGAR XML/HTML directly
        # 2. Use a paid API (Quiver, Insider Monkey, etc.)
        # 3. Scrape from sites like OpenInsider

        logger.info(f"Fetching insider activity for {symbol} (last {days_back} days)")

        # Placeholder - would implement actual SEC EDGAR parsing here
        return []

    def get_insider_sentiment(self, transactions: List[InsiderTransaction]) -> float:
        """
        Calculate insider sentiment score from transactions.

        Args:
            transactions: List of insider transactions

        Returns:
            Sentiment score from -1 (heavy selling) to +1 (heavy buying)
        """
        if not transactions:
            return 0.0

        buy_value = 0.0
        sell_value = 0.0

        for txn in transactions:
            value = txn.total_value or (txn.shares * (txn.price_per_share or 0))

            if txn.transaction_type == "buy":
                buy_value += value
            elif txn.transaction_type == "sell":
                sell_value += value

        total = buy_value + sell_value
        if total == 0:
            return 0.0

        # Normalize to -1 to +1
        sentiment = (buy_value - sell_value) / total
        return sentiment


class SimpleInsiderSignalGenerator:
    """
    Generate trading signals from insider activity.

    Uses a simple heuristic approach since we don't have real-time
    insider data yet.
    """

    def __init__(self):
        self.service = InsiderTradingService()

    def generate_signals(self, symbols: List[str], min_confidence: float = 0.3) -> Dict[str, float]:
        """
        Generate insider trading signals for symbols.

        Args:
            symbols: List of stock symbols
            min_confidence: Minimum confidence threshold

        Returns:
            Dict mapping symbol to signal strength (0-1)
        """
        signals = {}

        for symbol in symbols:
            # Fetch insider activity
            transactions = self.service.fetch_recent_insider_activity(symbol)

            if not transactions:
                continue

            # Calculate sentiment
            sentiment = self.service.get_insider_sentiment(transactions)

            # Only positive signals (buying)
            if sentiment > 0:
                # Calculate confidence based on transaction count
                confidence = min(1.0, len(transactions) / 5.0)

                if confidence >= min_confidence:
                    signals[symbol] = sentiment * confidence

        return signals

    def get_mock_signals(
        self, symbols: List[str], conviction_weights: Dict[str, float]
    ) -> Dict[str, float]:
        """
        Generate mock insider signals based on conviction weights.

        This is a placeholder until real insider data is integrated.
        In production, replace with actual SEC Form 4 parsing.

        Args:
            symbols: List of symbols to analyze
            conviction_weights: 13F conviction scores

        Returns:
            Mock insider signals
        """
        # For now, generate signals that slightly boost top conviction picks
        # This simulates insider buying in stocks that institutions like

        signals = {}

        # Take top 30% of conviction picks and boost them slightly
        sorted_symbols = sorted(
            [(s, conviction_weights.get(s, 0)) for s in symbols], key=lambda x: x[1], reverse=True
        )

        top_30_pct = int(len(sorted_symbols) * 0.3)

        for i, (symbol, conv_score) in enumerate(sorted_symbols[:top_30_pct]):
            if conv_score > 0:
                # Boost factor decreases with rank
                boost = 1.0 - (i / top_30_pct) * 0.5
                signals[symbol] = conv_score * boost * 0.3  # 30% boost

        return signals
