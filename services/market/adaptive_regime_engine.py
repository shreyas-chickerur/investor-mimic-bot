"""
Adaptive Market Regime Engine

Dynamically adjusts factor weights based on market conditions.
Different indicators work better in different market regimes.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class MarketRegimeType(Enum):
    """Market regime types."""

    BULL = "bull"
    BEAR = "bear"
    SIDEWAYS = "sideways"
    VOLATILE = "volatile"
    UNKNOWN = "unknown"


@dataclass
class RegimeWeights:
    """Factor weights for a specific regime."""

    conviction_13f: float
    news_sentiment: float
    insider_trading: float
    technical: float
    moving_averages: float
    volume: float
    relative_strength: float
    earnings: float
    cash_allocation: float = 0.0  # Cash to hold in this regime

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary."""
        return {
            "conviction": self.conviction_13f,
            "news": self.news_sentiment,
            "insider": self.insider_trading,
            "technical": self.technical,
            "moving_avg": self.moving_averages,
            "volume": self.volume,
            "relative_strength": self.relative_strength,
            "earnings": self.earnings,
            "cash": self.cash_allocation,
        }


@dataclass
class MarketRegime:
    """Market regime detection result."""

    regime: MarketRegimeType
    confidence: float
    vix_level: float
    trend_strength: float
    breadth: float  # % of stocks above 50-day MA
    weights: RegimeWeights
    indicators: Dict[str, float]


class AdaptiveRegimeEngine:
    """
    Detects market regime and adjusts factor weights accordingly.
    """

    # Optimal weights for each regime (based on quantitative research)
    REGIME_WEIGHTS = {
        MarketRegimeType.BULL: RegimeWeights(
            conviction_13f=0.25,  # ↓ Less important in momentum
            news_sentiment=0.08,  # ↓ Noise in bull markets
            insider_trading=0.03,  # ↓ Insiders sell in rallies
            technical=0.10,  # ↑ Momentum works
            moving_averages=0.25,  # ↑ Trend is strong
            volume=0.12,  # ↑ Confirms breakouts
            relative_strength=0.15,  # ↑ Leaders keep leading
            earnings=0.02,  # Same
            cash_allocation=0.05,  # Low cash in bull
        ),
        MarketRegimeType.BEAR: RegimeWeights(
            conviction_13f=0.40,  # ↑ Smart money matters most
            news_sentiment=0.20,  # ↑ Fear drives markets
            insider_trading=0.15,  # ↑ Insider buying = bottom
            technical=0.08,  # Same (mean reversion)
            moving_averages=0.10,  # ↓ Trends are down
            volume=0.05,  # ↓ Less reliable
            relative_strength=0.00,  # ↓ Everything falls
            earnings=0.02,  # Same
            cash_allocation=0.20,  # High cash in bear
        ),
        MarketRegimeType.SIDEWAYS: RegimeWeights(
            conviction_13f=0.20,  # ↓ Less directional
            news_sentiment=0.15,  # ↑ Catalysts matter
            insider_trading=0.15,  # ↑ Stock-specific
            technical=0.20,  # ↑ Range-bound works
            moving_averages=0.10,  # ↓ No trend
            volume=0.10,  # Same
            relative_strength=0.08,  # Same
            earnings=0.02,  # Same
            cash_allocation=0.10,  # Moderate cash
        ),
        MarketRegimeType.VOLATILE: RegimeWeights(
            conviction_13f=0.50,  # ↑ Only trust smart money
            news_sentiment=0.05,  # ↓ Too much noise
            insider_trading=0.10,  # Insider buying
            technical=0.05,  # ↓ Doesn't work in chaos
            moving_averages=0.00,  # ↓ Whipsaws
            volume=0.00,  # ↓ Unreliable
            relative_strength=0.00,  # ↓ Everything volatile
            earnings=0.00,  # ↓ Ignored in panic
            cash_allocation=0.30,  # Very high cash
        ),
    }

    def detect_regime(
        self,
        spy_prices: pd.Series,
        vix_level: Optional[float] = None,
        breadth: Optional[float] = None,
    ) -> MarketRegime:
        """
        Detect current market regime.

        Args:
            spy_prices: SPY price series
            vix_level: Current VIX level
            breadth: % of stocks above 50-day MA

        Returns:
            MarketRegime object
        """
        if len(spy_prices) < 200:
            logger.warning("Insufficient data for regime detection")
            return self._unknown_regime()

        # Calculate indicators
        ma_50 = spy_prices.rolling(window=50).mean().iloc[-1]
        ma_200 = spy_prices.rolling(window=200).mean().iloc[-1]
        current_price = spy_prices.iloc[-1]

        # Price vs MAs
        price_vs_ma50 = ((current_price - ma_50) / ma_50) * 100
        price_vs_ma200 = ((current_price - ma_200) / ma_200) * 100

        # Trend strength
        ma_separation = ((ma_50 - ma_200) / ma_200) * 100

        # Volatility
        returns = spy_prices.pct_change().dropna()
        volatility = returns.std() * np.sqrt(252) * 100  # Annualized

        # Use provided VIX or estimate
        if vix_level is None:
            vix_level = volatility

        # Use provided breadth or estimate
        if breadth is None:
            breadth = 50.0  # Neutral assumption

        # Detect regime
        regime, confidence = self._classify_regime(
            price_vs_ma50=price_vs_ma50,
            price_vs_ma200=price_vs_ma200,
            ma_separation=ma_separation,
            vix_level=vix_level,
            breadth=breadth,
            volatility=volatility,
        )

        # Get weights for regime
        weights = self.REGIME_WEIGHTS.get(regime, self.REGIME_WEIGHTS[MarketRegimeType.SIDEWAYS])

        indicators = {
            "price_vs_ma50": price_vs_ma50,
            "price_vs_ma200": price_vs_ma200,
            "ma_separation": ma_separation,
            "vix": vix_level,
            "breadth": breadth,
            "volatility": volatility,
        }

        return MarketRegime(
            regime=regime,
            confidence=confidence,
            vix_level=vix_level,
            trend_strength=ma_separation,
            breadth=breadth,
            weights=weights,
            indicators=indicators,
        )

    def _classify_regime(
        self,
        price_vs_ma50: float,
        price_vs_ma200: float,
        ma_separation: float,
        vix_level: float,
        breadth: float,
        volatility: float,
    ) -> Tuple[MarketRegimeType, float]:
        """Classify market regime based on indicators."""

        # HIGH VOLATILITY regime (crisis/panic)
        if vix_level > 35 or volatility > 30:
            confidence = min(1.0, (vix_level - 35) / 20 + 0.7)
            return MarketRegimeType.VOLATILE, confidence

        # BULL MARKET regime
        bull_score = 0.0
        if price_vs_ma50 > 0:
            bull_score += 0.3
        if price_vs_ma200 > 0:
            bull_score += 0.3
        if ma_separation > 5:  # 50-day MA well above 200-day MA
            bull_score += 0.2
        if breadth > 60:
            bull_score += 0.2

        if bull_score >= 0.7:
            return MarketRegimeType.BULL, bull_score

        # BEAR MARKET regime
        bear_score = 0.0
        if price_vs_ma50 < 0:
            bear_score += 0.3
        if price_vs_ma200 < 0:
            bear_score += 0.3
        if ma_separation < -5:  # 50-day MA well below 200-day MA
            bear_score += 0.2
        if breadth < 40:
            bear_score += 0.2

        if bear_score >= 0.7:
            return MarketRegimeType.BEAR, bear_score

        # SIDEWAYS regime (default)
        confidence = 1.0 - max(bull_score, bear_score)
        return MarketRegimeType.SIDEWAYS, confidence

    def _unknown_regime(self) -> MarketRegime:
        """Return unknown regime with default weights."""
        return MarketRegime(
            regime=MarketRegimeType.UNKNOWN,
            confidence=0.5,
            vix_level=20.0,
            trend_strength=0.0,
            breadth=50.0,
            weights=self.REGIME_WEIGHTS[MarketRegimeType.SIDEWAYS],
            indicators={},
        )

    def get_adaptive_weights(
        self,
        spy_prices: pd.Series,
        vix_level: Optional[float] = None,
        breadth: Optional[float] = None,
    ) -> Dict[str, float]:
        """
        Get adaptive factor weights based on current market regime.

        Args:
            spy_prices: SPY price series
            vix_level: Current VIX level
            breadth: Market breadth

        Returns:
            Dictionary of factor weights
        """
        regime = self.detect_regime(spy_prices, vix_level, breadth)

        logger.info(
            f"Market Regime: {regime.regime.value.upper()} (confidence: {regime.confidence:.1%})"
        )
        logger.info(
            f"  VIX: {regime.vix_level:.1f}, Trend: {regime.trend_strength:+.1f}%, Breadth: {regime.breadth:.0f}%"
        )

        return regime.weights.to_dict()

    def explain_regime(self, regime: MarketRegime) -> str:
        """Generate human-readable regime explanation."""

        explanation = f"""
MARKET REGIME ANALYSIS
{'=' * 60}

Current Regime: {regime.regime.value.upper()}
Confidence: {regime.confidence:.1%}

INDICATORS:
  VIX Level:          {regime.vix_level:.1f}
  Trend Strength:     {regime.trend_strength:+.1f}%
  Market Breadth:     {regime.breadth:.0f}%
  Price vs 50-day MA: {regime.indicators.get('price_vs_ma50', 0):+.1f}%
  Price vs 200-day MA: {regime.indicators.get('price_vs_ma200', 0):+.1f}%

ADAPTIVE FACTOR WEIGHTS:
  13F Conviction:     {regime.weights.conviction_13f:.0%}
  News Sentiment:     {regime.weights.news_sentiment:.0%}
  Insider Trading:    {regime.weights.insider_trading:.0%}
  Technical:          {regime.weights.technical:.0%}
  Moving Averages:    {regime.weights.moving_averages:.0%}
  Volume:             {regime.weights.volume:.0%}
  Relative Strength:  {regime.weights.relative_strength:.0%}
  Earnings:           {regime.weights.earnings:.0%}
  Cash Allocation:    {regime.weights.cash_allocation:.0%}

REGIME CHARACTERISTICS:
"""

        if regime.regime == MarketRegimeType.BULL:
            explanation += """
  • Strong uptrend - follow momentum
  • Moving averages and relative strength most important
  • Reduce cash, increase equity exposure
  • Focus on market leaders
"""
        elif regime.regime == MarketRegimeType.BEAR:
            explanation += """
  • Downtrend - focus on quality and smart money
  • 13F conviction and news sentiment most important
  • Increase cash, reduce equity exposure
  • Avoid relative strength (everything falls)
"""
        elif regime.regime == MarketRegimeType.SIDEWAYS:
            explanation += """
  • Range-bound market - stock picking matters
  • Technical and news catalysts important
  • Balanced approach across factors
  • Moderate cash allocation
"""
        elif regime.regime == MarketRegimeType.VOLATILE:
            explanation += """
  • High volatility - capital preservation mode
  • Only trust smart money (13F conviction)
  • High cash allocation (30%)
  • Avoid technical indicators (whipsaws)
"""

        return explanation


class SectorRotationDetector:
    """
    Detects sector rotation opportunities.
    """

    SECTORS = [
        "XLK",  # Technology
        "XLF",  # Financials
        "XLV",  # Healthcare
        "XLE",  # Energy
        "XLI",  # Industrials
        "XLY",  # Consumer Discretionary
        "XLP",  # Consumer Staples
        "XLB",  # Materials
        "XLRE",  # Real Estate
        "XLU",  # Utilities
        "XLC",  # Communication Services
    ]

    def calculate_sector_momentum(
        self, sector_prices: Dict[str, pd.Series], spy_prices: pd.Series, period: int = 60
    ) -> Dict[str, float]:
        """
        Calculate relative momentum for each sector.

        Args:
            sector_prices: Dictionary of sector ETF prices
            spy_prices: SPY prices for comparison
            period: Lookback period in days

        Returns:
            Dictionary of sector -> relative strength score
        """
        sector_momentum = {}

        # Calculate SPY return
        spy_return = (
            (spy_prices.iloc[-1] - spy_prices.iloc[-period]) / spy_prices.iloc[-period]
        ) * 100

        for sector, prices in sector_prices.items():
            if len(prices) < period:
                continue

            # Calculate sector return
            sector_return = ((prices.iloc[-1] - prices.iloc[-period]) / prices.iloc[-period]) * 100

            # Relative strength vs SPY
            relative_strength = sector_return - spy_return

            sector_momentum[sector] = relative_strength

        return sector_momentum

    def get_rotation_recommendations(
        self, sector_momentum: Dict[str, float], top_n: int = 3, bottom_n: int = 3
    ) -> Dict[str, List[str]]:
        """
        Get sector rotation recommendations.

        Args:
            sector_momentum: Sector momentum scores
            top_n: Number of top sectors to overweight
            bottom_n: Number of bottom sectors to underweight

        Returns:
            Dictionary with overweight and underweight sectors
        """
        # Sort sectors by momentum
        sorted_sectors = sorted(sector_momentum.items(), key=lambda x: x[1], reverse=True)

        overweight = [s for s, _ in sorted_sectors[:top_n]]
        underweight = [s for s, _ in sorted_sectors[-bottom_n:]]

        return {
            "overweight": overweight,
            "underweight": underweight,
            "momentum_scores": sector_momentum,
        }
