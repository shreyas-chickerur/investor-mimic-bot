"""
Advanced Risk Management System - Maximize returns while minimizing risk.

Features:
- Dynamic position sizing based on volatility
- Correlation analysis to reduce concentration
- Market regime detection
- Portfolio hedging
- Volatility-based adjustments
- Kelly Criterion for optimal bet sizing
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class RiskMetrics:
    """Risk metrics for a position or portfolio."""

    volatility: float
    beta: float
    sharpe_ratio: float
    max_drawdown: float
    var_95: float  # Value at Risk (95% confidence)
    correlation_to_market: float


@dataclass
class MarketRegime:
    """Current market regime."""

    regime: str  # 'bull', 'bear', 'sideways', 'high_volatility'
    confidence: float
    vix_level: float
    trend_strength: float


class AdvancedRiskManager:
    """
    Advanced risk management for maximum resilience and returns.
    """

    def __init__(
        self,
        max_portfolio_volatility: float = 0.20,  # 20% annual volatility target
        max_position_size: float = 0.10,  # 10% max per position
        max_sector_exposure: float = 0.30,  # 30% max per sector
        max_correlation: float = 0.70,  # Max correlation between positions
        target_sharpe: float = 2.0,  # Target Sharpe ratio
        cash_buffer_pct: float = 0.10,  # 10% cash buffer
    ):
        """
        Initialize advanced risk manager.

        Args:
            max_portfolio_volatility: Maximum portfolio volatility
            max_position_size: Maximum size per position
            max_sector_exposure: Maximum exposure per sector
            max_correlation: Maximum correlation between positions
            target_sharpe: Target Sharpe ratio
            cash_buffer_pct: Cash buffer percentage
        """
        self.max_portfolio_volatility = max_portfolio_volatility
        self.max_position_size = max_position_size
        self.max_sector_exposure = max_sector_exposure
        self.max_correlation = max_correlation
        self.target_sharpe = target_sharpe
        self.cash_buffer_pct = cash_buffer_pct

    def calculate_optimal_position_sizes(
        self,
        signals: Dict[str, float],
        volatilities: Dict[str, float],
        correlations: pd.DataFrame,
        total_capital: Decimal,
    ) -> Dict[str, Decimal]:
        """
        Calculate optimal position sizes using Kelly Criterion and volatility scaling.

        Args:
            signals: Dict of {symbol: signal_strength}
            volatilities: Dict of {symbol: annualized_volatility}
            correlations: Correlation matrix between symbols
            total_capital: Total capital to allocate

        Returns:
            Dict of {symbol: position_size_dollars}
        """
        # Apply cash buffer
        investable = total_capital * Decimal(str(1 - self.cash_buffer_pct))

        # Calculate Kelly-adjusted weights
        kelly_weights = {}
        for symbol, signal in signals.items():
            if symbol not in volatilities:
                continue

            vol = volatilities[symbol]

            # Kelly Criterion: f = (p*b - q) / b
            # Simplified: weight = signal / volatility
            # With half-Kelly for safety
            kelly_weight = (signal / vol) * 0.5  # Half-Kelly for safety
            kelly_weights[symbol] = max(0, kelly_weight)

        if not kelly_weights:
            return {}

        # Normalize weights
        total_weight = sum(kelly_weights.values())
        if total_weight > 0:
            kelly_weights = {k: v / total_weight for k, v in kelly_weights.items()}

        # Apply position size limits
        for symbol in list(kelly_weights.keys()):
            if kelly_weights[symbol] > self.max_position_size:
                kelly_weights[symbol] = self.max_position_size

        # Re-normalize after limits
        total_weight = sum(kelly_weights.values())
        if total_weight > 0:
            kelly_weights = {k: v / total_weight for k, v in kelly_weights.items()}

        # Adjust for correlations (reduce highly correlated positions)
        adjusted_weights = self._adjust_for_correlations(kelly_weights, correlations)

        # Convert to dollar amounts
        position_sizes = {symbol: investable * Decimal(str(weight)) for symbol, weight in adjusted_weights.items()}

        return position_sizes

    def _adjust_for_correlations(self, weights: Dict[str, float], correlations: pd.DataFrame) -> Dict[str, float]:
        """
        Adjust weights to reduce concentration from high correlations.

        Args:
            weights: Initial weights
            correlations: Correlation matrix

        Returns:
            Adjusted weights
        """
        if correlations.empty:
            return weights

        adjusted = weights.copy()
        symbols = list(weights.keys())

        # Penalize highly correlated pairs
        for i, sym1 in enumerate(symbols):
            for sym2 in symbols[i + 1 :]:
                if sym1 in correlations.index and sym2 in correlations.columns:
                    corr = abs(correlations.loc[sym1, sym2])

                    if corr > self.max_correlation:
                        # Reduce weights proportionally
                        penalty = (corr - self.max_correlation) * 0.5
                        adjusted[sym1] *= 1 - penalty
                        adjusted[sym2] *= 1 - penalty

        # Re-normalize
        total = sum(adjusted.values())
        if total > 0:
            adjusted = {k: v / total for k, v in adjusted.items()}

        return adjusted

    def detect_market_regime(self, market_prices: pd.DataFrame, vix_level: Optional[float] = None) -> MarketRegime:
        """
        Detect current market regime to adjust strategy.

        Args:
            market_prices: DataFrame with market index prices
            vix_level: Current VIX level (if available)

        Returns:
            MarketRegime object
        """
        if market_prices.empty:
            return MarketRegime(regime="unknown", confidence=0.0, vix_level=vix_level or 20.0, trend_strength=0.0)

        # Calculate returns
        returns = market_prices["close"].pct_change().dropna()

        # Calculate trend (20-day vs 50-day MA)
        ma_20 = market_prices["close"].rolling(20).mean()
        ma_50 = market_prices["close"].rolling(50).mean()

        if len(ma_20) > 0 and len(ma_50) > 0:
            trend = (ma_20.iloc[-1] - ma_50.iloc[-1]) / ma_50.iloc[-1]
        else:
            trend = 0.0

        # Calculate volatility
        volatility = returns.std() * np.sqrt(252)

        # Determine regime
        if vix_level and vix_level > 30:
            regime = "high_volatility"
            confidence = min(1.0, vix_level / 50)
        elif trend > 0.05:
            regime = "bull"
            confidence = min(1.0, abs(trend) * 10)
        elif trend < -0.05:
            regime = "bear"
            confidence = min(1.0, abs(trend) * 10)
        else:
            regime = "sideways"
            confidence = 0.6

        return MarketRegime(
            regime=regime,
            confidence=confidence,
            vix_level=vix_level or (volatility * 100),
            trend_strength=trend,
        )

    def adjust_for_market_regime(self, position_sizes: Dict[str, Decimal], regime: MarketRegime) -> Dict[str, Decimal]:
        """
        Adjust position sizes based on market regime.

        Args:
            position_sizes: Initial position sizes
            regime: Current market regime

        Returns:
            Adjusted position sizes
        """
        adjustment_factor = 1.0

        if regime.regime == "high_volatility":
            # Reduce exposure in high volatility
            adjustment_factor = 0.70  # 30% reduction
            logger.info(f"High volatility detected (VIX: {regime.vix_level:.1f}), reducing exposure by 30%")

        elif regime.regime == "bear":
            # Reduce exposure in bear market
            adjustment_factor = 0.75  # 25% reduction
            logger.info(f"Bear market detected, reducing exposure by 25%")

        elif regime.regime == "bull":
            # Slightly increase in bull market (but stay conservative)
            adjustment_factor = 1.10  # 10% increase
            logger.info(f"Bull market detected, increasing exposure by 10%")

        # Apply adjustment
        adjusted = {symbol: size * Decimal(str(adjustment_factor)) for symbol, size in position_sizes.items()}

        return adjusted

    def calculate_portfolio_var(
        self, positions: Dict[str, Dict], correlations: pd.DataFrame, confidence: float = 0.95
    ) -> float:
        """
        Calculate portfolio Value at Risk (VaR).

        Args:
            positions: Dict of {symbol: {value, volatility}}
            correlations: Correlation matrix
            confidence: Confidence level (default 95%)

        Returns:
            VaR as percentage of portfolio
        """
        if not positions:
            return 0.0

        # Calculate portfolio variance
        symbols = list(positions.keys())
        weights = np.array([positions[s]["value"] for s in symbols])
        weights = weights / weights.sum()

        volatilities = np.array([positions[s].get("volatility", 0.20) for s in symbols])

        # Build covariance matrix
        if not correlations.empty:
            cov_matrix = np.outer(volatilities, volatilities) * correlations.loc[symbols, symbols].values
        else:
            # Assume 0.5 correlation if no data
            cov_matrix = np.outer(volatilities, volatilities) * 0.5
            np.fill_diagonal(cov_matrix, volatilities**2)

        # Portfolio variance
        portfolio_var = np.dot(weights, np.dot(cov_matrix, weights))
        portfolio_vol = np.sqrt(portfolio_var)

        # VaR calculation (parametric method)
        # VaR = mean - z_score * std_dev
        # For 95% confidence, z_score = 1.645
        z_score = 1.645 if confidence == 0.95 else 2.326  # 99%

        var = z_score * portfolio_vol

        return var

    def generate_hedging_recommendations(
        self, portfolio_value: Decimal, market_regime: MarketRegime, portfolio_beta: float
    ) -> List[Dict]:
        """
        Generate hedging recommendations to protect against downside.

        Args:
            portfolio_value: Total portfolio value
            market_regime: Current market regime
            portfolio_beta: Portfolio beta to market

        Returns:
            List of hedging recommendations
        """
        recommendations = []

        # High volatility or bear market: recommend hedges
        if market_regime.regime in ["high_volatility", "bear"]:
            # 1. Cash hedge (increase cash buffer)
            if market_regime.regime == "high_volatility":
                recommendations.append(
                    {
                        "type": "cash_increase",
                        "action": "Increase cash buffer to 20%",
                        "rationale": f"High volatility (VIX: {market_regime.vix_level:.1f})",
                        "amount": portfolio_value * Decimal("0.20"),
                    }
                )

            # 2. Defensive stocks
            recommendations.append(
                {
                    "type": "defensive_allocation",
                    "action": "Increase allocation to defensive sectors",
                    "rationale": f"{market_regime.regime.title()} market detected",
                    "sectors": ["Consumer Staples", "Utilities", "Healthcare"],
                }
            )

            # 3. Reduce beta exposure
            if portfolio_beta > 1.2:
                recommendations.append(
                    {
                        "type": "beta_reduction",
                        "action": "Reduce high-beta positions",
                        "rationale": f"Portfolio beta ({portfolio_beta:.2f}) too high for {market_regime.regime} market",
                        "target_beta": 1.0,
                    }
                )

        return recommendations

    def calculate_risk_adjusted_scores(
        self,
        signals: Dict[str, float],
        volatilities: Dict[str, float],
        betas: Dict[str, float],
        market_regime: MarketRegime,
    ) -> Dict[str, float]:
        """
        Adjust signal scores for risk to maximize risk-adjusted returns.

        Args:
            signals: Raw signal scores
            volatilities: Stock volatilities
            betas: Stock betas
            market_regime: Current market regime

        Returns:
            Risk-adjusted scores
        """
        adjusted = {}

        for symbol, signal in signals.items():
            vol = volatilities.get(symbol, 0.20)
            beta = betas.get(symbol, 1.0)

            # Risk-adjusted score = signal / volatility
            # This favors high signal with low volatility
            risk_adj = signal / vol

            # Adjust for beta in different regimes
            if market_regime.regime == "bear":
                # Penalize high-beta stocks in bear market
                if beta > 1.2:
                    risk_adj *= 0.80
            elif market_regime.regime == "bull":
                # Favor high-beta stocks in bull market
                if beta > 1.2:
                    risk_adj *= 1.10

            adjusted[symbol] = risk_adj

        # Normalize
        total = sum(adjusted.values())
        if total > 0:
            adjusted = {k: v / total for k, v in adjusted.items()}

        return adjusted

    def validate_portfolio_risk(
        self, positions: Dict[str, Decimal], sector_map: Dict[str, str]
    ) -> Tuple[bool, List[str]]:
        """
        Validate portfolio meets risk constraints.

        Args:
            positions: Dict of {symbol: position_size}
            sector_map: Dict of {symbol: sector}

        Returns:
            Tuple of (is_valid, list_of_violations)
        """
        violations = []

        total = sum(positions.values())
        if total == 0:
            return True, []

        # Check position size limits
        for symbol, size in positions.items():
            pct = float(size / total)
            if pct > self.max_position_size:
                violations.append(f"{symbol}: {pct:.1%} exceeds max position size {self.max_position_size:.1%}")

        # Check sector exposure
        sector_exposure = {}
        for symbol, size in positions.items():
            sector = sector_map.get(symbol, "Unknown")
            sector_exposure[sector] = sector_exposure.get(sector, Decimal(0)) + size

        for sector, exposure in sector_exposure.items():
            pct = float(exposure / total)
            if pct > self.max_sector_exposure:
                violations.append(f"{sector}: {pct:.1%} exceeds max sector exposure {self.max_sector_exposure:.1%}")

        is_valid = len(violations) == 0
        return is_valid, violations
