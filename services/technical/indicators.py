"""
Technical Indicators Service - Calculate RSI, MACD, Moving Averages, etc.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class TechnicalIndicators:
    """
    Calculate technical indicators for stocks.
    """

    @staticmethod
    def calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
        """
        Calculate Relative Strength Index (RSI).

        Args:
            prices: Series of closing prices
            period: RSI period (default 14)

        Returns:
            Series of RSI values (0-100)
        """
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    @staticmethod
    def calculate_macd(
        prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
    ) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        Calculate MACD (Moving Average Convergence Divergence).

        Args:
            prices: Series of closing prices
            fast: Fast EMA period
            slow: Slow EMA period
            signal: Signal line period

        Returns:
            Tuple of (MACD line, Signal line, Histogram)
        """
        ema_fast = prices.ewm(span=fast, adjust=False).mean()
        ema_slow = prices.ewm(span=slow, adjust=False).mean()

        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line

        return macd_line, signal_line, histogram

    @staticmethod
    def calculate_moving_averages(
        prices: pd.Series, periods: List[int] = [20, 50, 200]
    ) -> Dict[int, pd.Series]:
        """
        Calculate Simple Moving Averages.

        Args:
            prices: Series of closing prices
            periods: List of MA periods

        Returns:
            Dict mapping period to MA series
        """
        mas = {}
        for period in periods:
            mas[period] = prices.rolling(window=period).mean()
        return mas

    @staticmethod
    def calculate_bollinger_bands(
        prices: pd.Series, period: int = 20, std_dev: float = 2.0
    ) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        Calculate Bollinger Bands.

        Args:
            prices: Series of closing prices
            period: MA period
            std_dev: Standard deviations for bands

        Returns:
            Tuple of (Upper band, Middle band, Lower band)
        """
        middle = prices.rolling(window=period).mean()
        std = prices.rolling(window=period).std()

        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)

        return upper, middle, lower


class TechnicalSignalGenerator:
    """
    Generate trading signals from technical indicators.
    """

    def __init__(self):
        self.indicators = TechnicalIndicators()

    def analyze_symbol(self, prices: pd.DataFrame, symbol: str) -> Dict:
        """
        Analyze a symbol and generate technical signals.

        Args:
            prices: DataFrame with 'close' column
            symbol: Stock symbol

        Returns:
            Dict with analysis results
        """
        if prices.empty or "close" not in prices.columns:
            return {"symbol": symbol, "signal": 0.0, "confidence": 0.0, "indicators": {}}

        close_prices = prices["close"]

        # Calculate indicators
        rsi = self.indicators.calculate_rsi(close_prices)
        macd_line, signal_line, histogram = self.indicators.calculate_macd(close_prices)
        mas = self.indicators.calculate_moving_averages(close_prices)

        # Get latest values
        latest_rsi = rsi.iloc[-1] if not rsi.empty else 50
        latest_macd = macd_line.iloc[-1] if not macd_line.empty else 0
        latest_signal = signal_line.iloc[-1] if not signal_line.empty else 0
        latest_price = close_prices.iloc[-1]

        # Calculate signals
        signals = []

        # RSI Signal
        if latest_rsi < 30:
            signals.append(("rsi_oversold", 0.8))  # Strong buy
        elif latest_rsi < 40:
            signals.append(("rsi_low", 0.5))  # Moderate buy
        elif latest_rsi > 70:
            signals.append(("rsi_overbought", -0.8))  # Strong sell
        elif latest_rsi > 60:
            signals.append(("rsi_high", -0.5))  # Moderate sell

        # MACD Signal
        if latest_macd > latest_signal:
            signals.append(("macd_bullish", 0.6))
        else:
            signals.append(("macd_bearish", -0.6))

        # Moving Average Signal
        if 20 in mas and 50 in mas:
            ma20 = mas[20].iloc[-1] if not mas[20].empty else latest_price
            ma50 = mas[50].iloc[-1] if not mas[50].empty else latest_price

            if ma20 > ma50:
                signals.append(("ma_bullish", 0.5))
            else:
                signals.append(("ma_bearish", -0.5))

        # Price vs MA200
        if 200 in mas:
            ma200 = mas[200].iloc[-1] if not mas[200].empty else latest_price
            if latest_price > ma200:
                signals.append(("above_ma200", 0.4))
            else:
                signals.append(("below_ma200", -0.4))

        # Aggregate signals
        if signals:
            avg_signal = sum(s[1] for s in signals) / len(signals)
            confidence = min(1.0, len(signals) / 5.0)
        else:
            avg_signal = 0.0
            confidence = 0.0

        return {
            "symbol": symbol,
            "signal": avg_signal,
            "confidence": confidence,
            "indicators": {
                "rsi": latest_rsi,
                "macd": latest_macd,
                "signal_line": latest_signal,
                "price": latest_price,
                "ma20": mas[20].iloc[-1] if 20 in mas and not mas[20].empty else None,
                "ma50": mas[50].iloc[-1] if 50 in mas and not mas[50].empty else None,
                "ma200": mas[200].iloc[-1] if 200 in mas and not mas[200].empty else None,
            },
            "signals": signals,
        }

    def generate_signals(
        self, symbols: List[str], price_data: Dict[str, pd.DataFrame], min_confidence: float = 0.3
    ) -> Dict[str, float]:
        """
        Generate technical signals for multiple symbols.

        Args:
            symbols: List of symbols
            price_data: Dict mapping symbol to price DataFrame
            min_confidence: Minimum confidence threshold

        Returns:
            Dict mapping symbol to signal strength
        """
        signals = {}

        for symbol in symbols:
            if symbol not in price_data:
                continue

            analysis = self.analyze_symbol(price_data[symbol], symbol)

            if analysis["confidence"] >= min_confidence and analysis["signal"] > 0:
                signals[symbol] = analysis["signal"] * analysis["confidence"]

        return signals

    def get_mock_signals(
        self, symbols: List[str], conviction_weights: Dict[str, float]
    ) -> Dict[str, float]:
        """
        Generate mock technical signals.

        This is a placeholder until real price data is integrated.

        Args:
            symbols: List of symbols
            conviction_weights: 13F conviction scores

        Returns:
            Mock technical signals
        """
        # Generate signals that add momentum to top picks
        signals = {}

        sorted_symbols = sorted(
            [(s, conviction_weights.get(s, 0)) for s in symbols], key=lambda x: x[1], reverse=True
        )

        top_40_pct = int(len(sorted_symbols) * 0.4)

        for i, (symbol, conv_score) in enumerate(sorted_symbols[:top_40_pct]):
            if conv_score > 0:
                # Momentum factor
                momentum = 1.0 - (i / top_40_pct) * 0.6
                signals[symbol] = conv_score * momentum * 0.25

        return signals
