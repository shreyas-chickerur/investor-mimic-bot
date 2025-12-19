"""
Advanced Feature Engineering

Creates sophisticated features for ML models to improve prediction accuracy.
"""

from typing import Dict, List

import numpy as np
import pandas as pd

from utils.enhanced_logging import get_logger

logger = get_logger(__name__)


class AdvancedFeatureEngineer:
    """Advanced feature engineering for stock analysis."""

    def __init__(self):
        self.feature_names = []

    def create_momentum_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create momentum-based features."""

        # Rate of change over different periods
        for period in [5, 10, 20, 50]:
            df[f"roc_{period}"] = df["close"].pct_change(period)

        # Momentum (price - price N days ago)
        for period in [10, 20, 50]:
            df[f"momentum_{period}"] = df["close"] - df["close"].shift(period)

        # ADX (Average Directional Index)
        df["adx_14"] = self._calculate_adx(df, 14)

        # Stochastic Oscillator
        df["stoch_k"], df["stoch_d"] = self._calculate_stochastic(df, 14)

        logger.debug("Created momentum features")
        return df

    def create_volatility_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create volatility-based features."""

        # Historical volatility
        for period in [10, 20, 50]:
            df[f"volatility_{period}"] = df["close"].pct_change().rolling(period).std() * np.sqrt(252)

        # ATR (Average True Range)
        df["atr_14"] = self._calculate_atr(df, 14)

        # Bollinger Bands
        for period in [20, 50]:
            ma = df["close"].rolling(period).mean()
            std = df["close"].rolling(period).std()
            df[f"bb_upper_{period}"] = ma + (2 * std)
            df[f"bb_lower_{period}"] = ma - (2 * std)
            df[f"bb_width_{period}"] = (df[f"bb_upper_{period}"] - df[f"bb_lower_{period}"]) / ma
            df[f"bb_position_{period}"] = (df["close"] - df[f"bb_lower_{period}"]) / (
                df[f"bb_upper_{period}"] - df[f"bb_lower_{period}"]
            )

        logger.debug("Created volatility features")
        return df

    def create_volume_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create volume-based features."""

        # Volume ratios
        for period in [5, 10, 20]:
            df[f"volume_ratio_{period}"] = df["volume"] / df["volume"].rolling(period).mean()

        # On-Balance Volume (OBV)
        df["obv"] = (np.sign(df["close"].diff()) * df["volume"]).fillna(0).cumsum()

        # Volume-weighted average price
        df["vwap"] = (df["close"] * df["volume"]).cumsum() / df["volume"].cumsum()

        # Money Flow Index
        df["mfi_14"] = self._calculate_mfi(df, 14)

        logger.debug("Created volume features")
        return df

    def create_price_pattern_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create price pattern features."""

        # Higher highs, lower lows
        df["higher_high"] = (df["high"] > df["high"].shift(1)).astype(int)
        df["lower_low"] = (df["low"] < df["low"].shift(1)).astype(int)

        # Gap detection
        df["gap_up"] = (df["low"] > df["high"].shift(1)).astype(int)
        df["gap_down"] = (df["high"] < df["low"].shift(1)).astype(int)

        # Candle patterns
        df["body"] = df["close"] - df["open"]
        df["body_pct"] = df["body"] / df["open"]
        df["upper_shadow"] = df["high"] - df[["open", "close"]].max(axis=1)
        df["lower_shadow"] = df[["open", "close"]].min(axis=1) - df["low"]

        # Doji detection (small body relative to range)
        df["is_doji"] = (abs(df["body"]) / (df["high"] - df["low"]) < 0.1).astype(int)

        logger.debug("Created price pattern features")
        return df

    def create_trend_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create trend-based features."""

        # Moving averages
        for period in [5, 10, 20, 50, 200]:
            df[f"sma_{period}"] = df["close"].rolling(period).mean()
            df[f"ema_{period}"] = df["close"].ewm(span=period).mean()

        # MA crossovers
        df["sma_20_50_cross"] = (df["sma_20"] > df["sma_50"]).astype(int)
        df["sma_50_200_cross"] = (df["sma_50"] > df["sma_200"]).astype(int)

        # Distance from moving averages
        for period in [20, 50, 200]:
            df[f"dist_from_sma_{period}"] = (df["close"] - df[f"sma_{period}"]) / df[f"sma_{period}"]

        # Trend strength
        df["trend_strength_20"] = (
            df["close"].rolling(20).apply(lambda x: np.polyfit(range(len(x)), x, 1)[0] if len(x) == 20 else 0)
        )

        logger.debug("Created trend features")
        return df

    def create_all_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create all advanced features."""

        df = self.create_momentum_features(df)
        df = self.create_volatility_features(df)
        df = self.create_volume_features(df)
        df = self.create_price_pattern_features(df)
        df = self.create_trend_features(df)

        # Store feature names
        self.feature_names = [col for col in df.columns if col not in ["open", "high", "low", "close", "volume"]]

        logger.info(f"Created {len(self.feature_names)} advanced features")
        return df

    def _calculate_adx(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Average Directional Index."""
        high = df["high"]
        low = df["low"]
        close = df["close"]

        plus_dm = high.diff()
        minus_dm = -low.diff()
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm < 0] = 0

        tr = pd.concat([high - low, abs(high - close.shift()), abs(low - close.shift())], axis=1).max(axis=1)

        atr = tr.rolling(period).mean()
        plus_di = 100 * (plus_dm.rolling(period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(period).mean() / atr)

        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(period).mean()

        return adx

    def _calculate_stochastic(self, df: pd.DataFrame, period: int = 14) -> tuple:
        """Calculate Stochastic Oscillator."""
        low_min = df["low"].rolling(period).min()
        high_max = df["high"].rolling(period).max()

        k = 100 * (df["close"] - low_min) / (high_max - low_min)
        d = k.rolling(3).mean()

        return k, d

    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Average True Range."""
        high = df["high"]
        low = df["low"]
        close = df["close"]

        tr = pd.concat([high - low, abs(high - close.shift()), abs(low - close.shift())], axis=1).max(axis=1)

        atr = tr.rolling(period).mean()
        return atr

    def _calculate_mfi(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Money Flow Index."""
        typical_price = (df["high"] + df["low"] + df["close"]) / 3
        money_flow = typical_price * df["volume"]

        positive_flow = money_flow.where(typical_price > typical_price.shift(1), 0)
        negative_flow = money_flow.where(typical_price < typical_price.shift(1), 0)

        positive_mf = positive_flow.rolling(period).sum()
        negative_mf = negative_flow.rolling(period).sum()

        mfi = 100 - (100 / (1 + positive_mf / negative_mf))
        return mfi


def create_advanced_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convenience function to create all advanced features.

    Usage:
        from services.technical.advanced_features import create_advanced_features

        df = create_advanced_features(price_data)
    """
    engineer = AdvancedFeatureEngineer()
    return engineer.create_all_features(df)
