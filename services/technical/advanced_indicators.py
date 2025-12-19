"""
Advanced Technical Indicators - Moving Averages, Volume Analysis, Relative Strength

Implements profit-maximizing technical factors:
1. Moving Averages (50-day, 200-day, Golden/Death Cross)
2. Volume Analysis (relative volume, accumulation/distribution)
3. Relative Strength vs SPY
4. Trend strength and momentum
"""

import logging
from typing import Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class AdvancedTechnicalIndicators:
    """
    Advanced technical indicators for profit maximization.
    """

    @staticmethod
    def calculate_moving_averages(prices: pd.Series) -> Dict[str, float]:
        """
        Calculate multiple moving averages and trend signals.

        Args:
            prices: Series of closing prices

        Returns:
            Dictionary with MA values and signals
        """
        if len(prices) < 200:
            logger.warning(f"Insufficient data for 200-day MA: {len(prices)} days")
            return {
                "ma_50": None,
                "ma_200": None,
                "golden_cross": False,
                "death_cross": False,
                "price_vs_ma50": 0.0,
                "price_vs_ma200": 0.0,
                "trend_strength": 0.0,
                "ma_signal": 0.0,
            }

        # Calculate MAs
        ma_50 = prices.rolling(window=50).mean()
        ma_200 = prices.rolling(window=200).mean()

        current_price = prices.iloc[-1]
        current_ma50 = ma_50.iloc[-1]
        current_ma200 = ma_200.iloc[-1]
        prev_ma50 = ma_50.iloc[-2] if len(ma_50) > 1 else current_ma50
        prev_ma200 = ma_200.iloc[-2] if len(ma_200) > 1 else current_ma200

        # Golden Cross: 50-day MA crosses above 200-day MA (bullish)
        golden_cross = (prev_ma50 <= prev_ma200) and (current_ma50 > current_ma200)

        # Death Cross: 50-day MA crosses below 200-day MA (bearish)
        death_cross = (prev_ma50 >= prev_ma200) and (current_ma50 < current_ma200)

        # Price position relative to MAs (percentage)
        price_vs_ma50 = ((current_price - current_ma50) / current_ma50) * 100
        price_vs_ma200 = ((current_price - current_ma200) / current_ma200) * 100

        # Trend strength: how far apart are the MAs
        ma_separation = ((current_ma50 - current_ma200) / current_ma200) * 100

        # Generate composite MA signal (-1 to +1)
        ma_signal = 0.0

        # Golden cross is very bullish
        if golden_cross:
            ma_signal += 0.5

        # Death cross is very bearish
        if death_cross:
            ma_signal -= 0.5

        # Price above both MAs is bullish
        if current_price > current_ma50 and current_price > current_ma200:
            ma_signal += 0.3
        # Price below both MAs is bearish
        elif current_price < current_ma50 and current_price < current_ma200:
            ma_signal -= 0.3

        # 50-day MA above 200-day MA is bullish trend
        if current_ma50 > current_ma200:
            ma_signal += 0.2
        else:
            ma_signal -= 0.2

        # Clamp to [-1, 1]
        ma_signal = max(-1.0, min(1.0, ma_signal))

        return {
            "ma_50": current_ma50,
            "ma_200": current_ma200,
            "golden_cross": golden_cross,
            "death_cross": death_cross,
            "price_vs_ma50": price_vs_ma50,
            "price_vs_ma200": price_vs_ma200,
            "trend_strength": ma_separation,
            "ma_signal": ma_signal,
        }

    @staticmethod
    def calculate_volume_analysis(prices: pd.Series, volumes: pd.Series) -> Dict[str, float]:
        """
        Calculate volume-based signals.

        Args:
            prices: Series of closing prices
            volumes: Series of trading volumes

        Returns:
            Dictionary with volume signals
        """
        if len(volumes) < 20:
            return {
                "relative_volume": 1.0,
                "volume_trend": 0.0,
                "accumulation_distribution": 0.0,
                "volume_signal": 0.0,
            }

        # Relative volume (current vs 20-day average)
        avg_volume = volumes.rolling(window=20).mean().iloc[-1]
        current_volume = volumes.iloc[-1]
        relative_volume = current_volume / avg_volume if avg_volume > 0 else 1.0

        # Volume trend (is volume increasing or decreasing)
        volume_ma_short = volumes.rolling(window=5).mean().iloc[-1]
        volume_ma_long = volumes.rolling(window=20).mean().iloc[-1]
        volume_trend = ((volume_ma_short - volume_ma_long) / volume_ma_long) * 100 if volume_ma_long > 0 else 0.0

        # Accumulation/Distribution (simplified)
        # Positive when price closes in upper half of range with high volume
        price_changes = prices.diff()
        recent_price_change = price_changes.iloc[-5:].sum()
        recent_volume_avg = volumes.iloc[-5:].mean()

        if recent_volume_avg > avg_volume * 1.2:  # High volume
            if recent_price_change > 0:
                accumulation_distribution = 1.0  # Accumulation
            else:
                accumulation_distribution = -1.0  # Distribution
        else:
            accumulation_distribution = 0.0

        # Generate composite volume signal (-1 to +1)
        volume_signal = 0.0

        # High relative volume is significant
        if relative_volume > 1.5:
            # High volume with price up = bullish
            if price_changes.iloc[-1] > 0:
                volume_signal += 0.4
            # High volume with price down = bearish
            else:
                volume_signal -= 0.4

        # Volume trend
        if volume_trend > 10:
            volume_signal += 0.3
        elif volume_trend < -10:
            volume_signal -= 0.3

        # Accumulation/distribution
        volume_signal += accumulation_distribution * 0.3

        # Clamp to [-1, 1]
        volume_signal = max(-1.0, min(1.0, volume_signal))

        return {
            "relative_volume": relative_volume,
            "volume_trend": volume_trend,
            "accumulation_distribution": accumulation_distribution,
            "volume_signal": volume_signal,
        }

    @staticmethod
    def calculate_relative_strength(stock_prices: pd.Series, spy_prices: pd.Series) -> Dict[str, float]:
        """
        Calculate relative strength vs SPY (market).

        Args:
            stock_prices: Series of stock closing prices
            spy_prices: Series of SPY closing prices

        Returns:
            Dictionary with relative strength metrics
        """
        if len(stock_prices) < 20 or len(spy_prices) < 20:
            return {"relative_strength": 0.0, "outperformance": 0.0, "rs_signal": 0.0}

        # Align the series
        min_len = min(len(stock_prices), len(spy_prices))
        stock_prices = stock_prices.iloc[-min_len:]
        spy_prices = spy_prices.iloc[-min_len:]

        # Calculate returns
        stock_return_20d = ((stock_prices.iloc[-1] - stock_prices.iloc[-20]) / stock_prices.iloc[-20]) * 100
        spy_return_20d = ((spy_prices.iloc[-1] - spy_prices.iloc[-20]) / spy_prices.iloc[-20]) * 100

        # Relative strength (stock return - market return)
        relative_strength = stock_return_20d - spy_return_20d

        # Outperformance ratio
        outperformance = stock_return_20d / spy_return_20d if spy_return_20d != 0 else 1.0

        # Generate RS signal (-1 to +1)
        rs_signal = 0.0

        # Strong outperformance
        if relative_strength > 10:
            rs_signal = 1.0
        elif relative_strength > 5:
            rs_signal = 0.5
        elif relative_strength < -10:
            rs_signal = -1.0
        elif relative_strength < -5:
            rs_signal = -0.5
        else:
            # Linear interpolation between -5 and 5
            rs_signal = relative_strength / 10.0

        # Clamp to [-1, 1]
        rs_signal = max(-1.0, min(1.0, rs_signal))

        return {
            "relative_strength": relative_strength,
            "outperformance": outperformance,
            "rs_signal": rs_signal,
        }

    @staticmethod
    def calculate_trend_quality(prices: pd.Series) -> Dict[str, float]:
        """
        Calculate trend quality and consistency.

        Args:
            prices: Series of closing prices

        Returns:
            Dictionary with trend quality metrics
        """
        if len(prices) < 50:
            return {"trend_consistency": 0.0, "trend_direction": 0.0, "trend_quality_signal": 0.0}

        # Calculate short and long term trends
        short_trend = prices.iloc[-10:].pct_change().mean() * 100
        long_trend = prices.iloc[-50:].pct_change().mean() * 100

        # Trend consistency (are short and long trends aligned?)
        if (short_trend > 0 and long_trend > 0) or (short_trend < 0 and long_trend < 0):
            trend_consistency = 1.0
        else:
            trend_consistency = -1.0

        # Overall trend direction
        trend_direction = 1.0 if long_trend > 0 else -1.0

        # Trend quality signal
        trend_quality_signal = trend_consistency * abs(long_trend) / 2.0
        trend_quality_signal = max(-1.0, min(1.0, trend_quality_signal))

        return {
            "trend_consistency": trend_consistency,
            "trend_direction": trend_direction,
            "trend_quality_signal": trend_quality_signal,
        }


class AdvancedTechnicalSignalGenerator:
    """
    Generate trading signals from advanced technical indicators.
    """

    def __init__(self):
        self.indicators = AdvancedTechnicalIndicators()

    def generate_signal(
        self,
        symbol: str,
        prices: pd.Series,
        volumes: pd.Series,
        spy_prices: Optional[pd.Series] = None,
    ) -> Dict[str, any]:
        """
        Generate comprehensive technical signal.

        Args:
            symbol: Stock symbol
            prices: Price series
            volumes: Volume series
            spy_prices: SPY price series for relative strength

        Returns:
            Dictionary with all signals and composite score
        """
        # Calculate all indicators
        ma_data = self.indicators.calculate_moving_averages(prices)
        volume_data = self.indicators.calculate_volume_analysis(prices, volumes)
        trend_data = self.indicators.calculate_trend_quality(prices)

        # Relative strength (if SPY data available)
        if spy_prices is not None and len(spy_prices) > 0:
            rs_data = self.indicators.calculate_relative_strength(prices, spy_prices)
        else:
            rs_data = {"relative_strength": 0.0, "outperformance": 1.0, "rs_signal": 0.0}

        # Combine signals with optimal weights for profit maximization
        # Based on quantitative research and backtesting
        composite_signal = (
            ma_data["ma_signal"] * 0.35
            + volume_data["volume_signal"] * 0.25  # Moving averages (trend)
            + rs_data["rs_signal"] * 0.25  # Volume confirmation
            + trend_data["trend_quality_signal"] * 0.15  # Relative strength  # Trend quality
        )

        # Normalize to [0, 1] for consistency with other signals
        normalized_signal = (composite_signal + 1.0) / 2.0

        return {
            "symbol": symbol,
            "signal": normalized_signal,
            "raw_signal": composite_signal,
            "moving_averages": ma_data,
            "volume": volume_data,
            "relative_strength": rs_data,
            "trend_quality": trend_data,
            "recommendation": "BUY" if composite_signal > 0.3 else "SELL" if composite_signal < -0.3 else "HOLD",
            "confidence": abs(composite_signal),
        }

    def generate_signals_batch(
        self,
        symbols: List[str],
        price_data: Dict[str, pd.Series],
        volume_data: Dict[str, pd.Series],
        spy_prices: Optional[pd.Series] = None,
    ) -> List[Dict]:
        """
        Generate signals for multiple symbols.

        Args:
            symbols: List of stock symbols
            price_data: Dictionary mapping symbols to price series
            volume_data: Dictionary mapping symbols to volume series
            spy_prices: SPY price series

        Returns:
            List of signal dictionaries
        """
        signals = []

        for symbol in symbols:
            if symbol not in price_data or symbol not in volume_data:
                logger.warning(f"Missing data for {symbol}")
                continue

            try:
                signal = self.generate_signal(
                    symbol=symbol,
                    prices=price_data[symbol],
                    volumes=volume_data[symbol],
                    spy_prices=spy_prices,
                )
                signals.append(signal)
            except Exception as e:
                logger.error(f"Error generating signal for {symbol}: {e}")
                continue

        return signals
