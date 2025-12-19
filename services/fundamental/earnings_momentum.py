"""
Earnings Momentum Tracker

Tracks earnings beats/misses, guidance changes, and fundamental catalysts
to maximize profit by identifying stocks with strong earnings momentum.
"""

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


@dataclass
class EarningsEvent:
    """Earnings event data."""

    symbol: str
    report_date: datetime
    eps_estimate: float
    eps_actual: float
    revenue_estimate: float
    revenue_actual: float
    guidance: str  # 'raise', 'lower', 'maintain', 'unknown'
    surprise_percent: float

    @property
    def beat_earnings(self) -> bool:
        """Did the company beat earnings estimates?"""
        return self.eps_actual > self.eps_estimate

    @property
    def beat_revenue(self) -> bool:
        """Did the company beat revenue estimates?"""
        return self.revenue_actual > self.revenue_estimate

    @property
    def is_strong_beat(self) -> bool:
        """Is this a strong earnings beat (>5% surprise)?"""
        return self.surprise_percent > 5.0


class EarningsMomentumTracker:
    """
    Track earnings momentum for profit maximization.
    """

    def __init__(self, alpha_vantage_key: Optional[str] = None):
        """
        Initialize earnings tracker.

        Args:
            alpha_vantage_key: Alpha Vantage API key
        """
        self.api_key = alpha_vantage_key or os.getenv("ALPHA_VANTAGE_API_KEY")
        self.base_url = "https://www.alphavantage.co/query"

    def get_earnings_data(self, symbol: str) -> Optional[EarningsEvent]:
        """
        Get latest earnings data for a symbol.

        Args:
            symbol: Stock symbol

        Returns:
            EarningsEvent or None if not available
        """
        if not self.api_key:
            logger.warning("No Alpha Vantage API key configured")
            return None

        try:
            # Get earnings data from Alpha Vantage
            params = {"function": "EARNINGS", "symbol": symbol, "apikey": self.api_key}

            response = requests.get(self.base_url, params=params, timeout=10)
            data = response.json()

            if "quarterlyEarnings" not in data or len(data["quarterlyEarnings"]) == 0:
                logger.warning(f"No earnings data for {symbol}")
                return None

            # Get most recent earnings
            latest = data["quarterlyEarnings"][0]

            # Parse data
            eps_estimate = float(latest.get("estimatedEPS", 0))
            eps_actual = float(latest.get("reportedEPS", 0))

            # Calculate surprise
            if eps_estimate != 0:
                surprise_percent = ((eps_actual - eps_estimate) / abs(eps_estimate)) * 100
            else:
                surprise_percent = 0.0

            # Create earnings event
            event = EarningsEvent(
                symbol=symbol,
                report_date=datetime.strptime(latest["fiscalDateEnding"], "%Y-%m-%d"),
                eps_estimate=eps_estimate,
                eps_actual=eps_actual,
                revenue_estimate=0.0,  # Not available in free API
                revenue_actual=0.0,
                guidance="unknown",  # Not available in free API
                surprise_percent=surprise_percent,
            )

            return event

        except Exception as e:
            logger.error(f"Error fetching earnings for {symbol}: {e}")
            return None

    def calculate_earnings_signal(self, symbol: str) -> Dict[str, any]:
        """
        Calculate earnings momentum signal.

        Args:
            symbol: Stock symbol

        Returns:
            Dictionary with earnings signal and metrics
        """
        event = self.get_earnings_data(symbol)

        if not event:
            # No earnings data - neutral signal
            return {
                "symbol": symbol,
                "signal": 0.0,
                "has_data": False,
                "earnings_beat": False,
                "surprise_percent": 0.0,
                "recommendation": "NEUTRAL",
            }

        # Calculate signal based on earnings performance
        signal = 0.0

        # Strong beat (>5% surprise) is very bullish
        if event.surprise_percent > 5:
            signal = 1.0
        # Beat (0-5% surprise) is bullish
        elif event.surprise_percent > 0:
            signal = 0.5
        # Miss (0 to -5% surprise) is bearish
        elif event.surprise_percent > -5:
            signal = -0.5
        # Big miss (<-5% surprise) is very bearish
        else:
            signal = -1.0

        # Adjust for recency (earnings older than 90 days are less relevant)
        days_since_earnings = (datetime.now() - event.report_date).days
        if days_since_earnings > 90:
            recency_factor = max(0.3, 1.0 - (days_since_earnings - 90) / 180)
            signal *= recency_factor

        return {
            "symbol": symbol,
            "signal": signal,
            "has_data": True,
            "earnings_beat": event.beat_earnings,
            "surprise_percent": event.surprise_percent,
            "days_since_report": days_since_earnings,
            "recommendation": "BUY" if signal > 0.3 else "SELL" if signal < -0.3 else "HOLD",
            "confidence": abs(signal),
        }

    def generate_signals_batch(self, symbols: List[str]) -> List[Dict]:
        """
        Generate earnings signals for multiple symbols.

        Args:
            symbols: List of stock symbols

        Returns:
            List of signal dictionaries
        """
        signals = []

        for symbol in symbols:
            try:
                signal = self.calculate_earnings_signal(symbol)
                signals.append(signal)
            except Exception as e:
                logger.error(f"Error generating earnings signal for {symbol}: {e}")
                # Add neutral signal on error
                signals.append({"symbol": symbol, "signal": 0.0, "has_data": False, "error": str(e)})

        return signals


class SimplifiedEarningsMomentum:
    """
    Simplified earnings momentum using mock data for testing.

    In production, this would be replaced with real earnings data.
    """

    def calculate_earnings_signal(self, symbol: str) -> Dict[str, any]:
        """
        Calculate simplified earnings signal.

        Uses heuristics based on stock characteristics:
        - Large cap tech stocks tend to beat earnings
        - High growth stocks have positive momentum

        Args:
            symbol: Stock symbol

        Returns:
            Dictionary with earnings signal
        """
        # Mock earnings momentum based on symbol characteristics
        # In production, replace with real earnings data

        # Tech stocks with strong momentum
        strong_momentum = ["NVDA", "META", "GOOGL", "MSFT", "AAPL", "AMZN", "TSLA"]
        moderate_momentum = ["AMD", "NFLX", "CRM", "ADBE", "INTC"]

        if symbol in strong_momentum:
            signal = 0.7  # Strong positive earnings momentum
            recommendation = "BUY"
        elif symbol in moderate_momentum:
            signal = 0.4  # Moderate positive momentum
            recommendation = "BUY"
        else:
            signal = 0.0  # Neutral
            recommendation = "HOLD"

        return {
            "symbol": symbol,
            "signal": signal,
            "has_data": True,
            "earnings_beat": signal > 0,
            "surprise_percent": signal * 10,
            "recommendation": recommendation,
            "confidence": abs(signal),
            "note": "Using simplified earnings model - replace with real data in production",
        }

    def generate_signals_batch(self, symbols: List[str]) -> List[Dict]:
        """Generate signals for multiple symbols."""
        return [self.calculate_earnings_signal(symbol) for symbol in symbols]
