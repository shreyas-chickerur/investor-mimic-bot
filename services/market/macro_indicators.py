"""
Macro Economic Indicators

Tracks economic indicators that drive market cycles and sector performance.
Helps position portfolio for economic expansions and contractions.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class EconomicCycle(Enum):
    """Economic cycle phases."""

    EXPANSION = "expansion"
    PEAK = "peak"
    CONTRACTION = "contraction"
    TROUGH = "trough"
    UNKNOWN = "unknown"


@dataclass
class MacroIndicators:
    """Macro economic indicators."""

    yield_curve_spread: float  # 10Y - 2Y Treasury spread
    unemployment_rate: float
    pmi: float  # Purchasing Managers Index
    consumer_confidence: float
    fed_funds_rate: float
    inflation_rate: float
    gdp_growth: float

    @property
    def yield_curve_inverted(self) -> bool:
        """Is the yield curve inverted (recession signal)?"""
        return self.yield_curve_spread < 0

    @property
    def recession_risk(self) -> float:
        """Calculate recession risk score (0-1)."""
        risk = 0.0

        # Inverted yield curve (strongest signal)
        if self.yield_curve_inverted:
            risk += 0.4

        # Rising unemployment
        if self.unemployment_rate > 5.0:
            risk += 0.2

        # Contracting PMI
        if self.pmi < 50:
            risk += 0.2

        # Falling consumer confidence
        if self.consumer_confidence < 90:
            risk += 0.1

        # Negative GDP growth
        if self.gdp_growth < 0:
            risk += 0.1

        return min(1.0, risk)


class MacroIndicatorTracker:
    """
    Tracks and analyzes macro economic indicators.
    """

    def __init__(self):
        """Initialize macro tracker."""
        self.history: List[MacroIndicators] = []

    def get_current_indicators(self) -> MacroIndicators:
        """
        Get current macro indicators.

        Note: In production, this would fetch real data from FRED, Bloomberg, etc.
        For now, returns estimated/mock data.
        """
        # Mock data - replace with real API calls in production
        return MacroIndicators(
            yield_curve_spread=0.5,  # 10Y-2Y spread (positive = normal)
            unemployment_rate=3.8,  # Current unemployment
            pmi=52.0,  # PMI > 50 = expansion
            consumer_confidence=102.0,
            fed_funds_rate=5.25,
            inflation_rate=3.2,
            gdp_growth=2.5,
        )

    def detect_economic_cycle(self, indicators: MacroIndicators) -> EconomicCycle:
        """
        Detect current phase of economic cycle.

        Args:
            indicators: Current macro indicators

        Returns:
            Economic cycle phase
        """
        # Expansion: Growing economy, low unemployment, rising PMI
        if (
            indicators.gdp_growth > 2.0
            and indicators.pmi > 52
            and indicators.unemployment_rate < 4.5
        ):
            return EconomicCycle.EXPANSION

        # Peak: Strong economy but showing signs of overheating
        if (
            indicators.gdp_growth > 3.0
            and indicators.inflation_rate > 4.0
            and indicators.unemployment_rate < 4.0
        ):
            return EconomicCycle.PEAK

        # Contraction: Slowing economy, rising unemployment
        if (
            indicators.gdp_growth < 1.0
            or indicators.pmi < 50
            or indicators.unemployment_rate > 5.0
            or indicators.yield_curve_inverted
        ):
            return EconomicCycle.CONTRACTION

        # Trough: Economy bottoming, early recovery signs
        if (
            indicators.gdp_growth < 0
            and indicators.pmi > 48
            and indicators.unemployment_rate > 6.0  # PMI improving but still weak
        ):
            return EconomicCycle.TROUGH

        return EconomicCycle.UNKNOWN

    def get_sector_recommendations(self, cycle: EconomicCycle) -> Dict[str, List[str]]:
        """
        Get sector recommendations based on economic cycle.

        Args:
            cycle: Current economic cycle

        Returns:
            Dictionary with favored and avoid sectors
        """
        recommendations = {
            EconomicCycle.EXPANSION: {
                "favor": ["Technology", "Consumer Discretionary", "Industrials", "Financials"],
                "avoid": ["Utilities", "Consumer Staples", "Real Estate"],
            },
            EconomicCycle.PEAK: {
                "favor": ["Energy", "Materials", "Financials"],
                "avoid": ["Technology", "Consumer Discretionary"],
            },
            EconomicCycle.CONTRACTION: {
                "favor": ["Consumer Staples", "Healthcare", "Utilities"],
                "avoid": ["Financials", "Industrials", "Energy"],
            },
            EconomicCycle.TROUGH: {
                "favor": ["Technology", "Consumer Discretionary", "Financials"],
                "avoid": ["Energy", "Materials"],
            },
        }

        return recommendations.get(cycle, {"favor": [], "avoid": []})

    def get_portfolio_positioning(
        self, indicators: MacroIndicators, cycle: EconomicCycle
    ) -> Dict[str, any]:
        """
        Get portfolio positioning recommendations.

        Args:
            indicators: Current macro indicators
            cycle: Economic cycle

        Returns:
            Portfolio positioning recommendations
        """
        recession_risk = indicators.recession_risk

        # Determine equity allocation
        if cycle == EconomicCycle.EXPANSION:
            equity_allocation = 0.90  # Aggressive
            cash_allocation = 0.10
        elif cycle == EconomicCycle.PEAK:
            equity_allocation = 0.75  # Start reducing
            cash_allocation = 0.25
        elif cycle == EconomicCycle.CONTRACTION:
            equity_allocation = 0.50  # Defensive
            cash_allocation = 0.50
        elif cycle == EconomicCycle.TROUGH:
            equity_allocation = 0.80  # Start adding
            cash_allocation = 0.20
        else:
            equity_allocation = 0.70  # Neutral
            cash_allocation = 0.30

        # Adjust for recession risk
        if recession_risk > 0.5:
            equity_allocation *= 0.7  # Reduce equity exposure
            cash_allocation = 1.0 - equity_allocation

        sector_recs = self.get_sector_recommendations(cycle)

        return {
            "cycle": cycle.value,
            "recession_risk": recession_risk,
            "equity_allocation": equity_allocation,
            "cash_allocation": cash_allocation,
            "favored_sectors": sector_recs["favor"],
            "avoid_sectors": sector_recs["avoid"],
            "duration_bias": "short" if indicators.fed_funds_rate > 4.0 else "long",
            "quality_bias": "high" if recession_risk > 0.3 else "balanced",
        }

    def generate_macro_report(self, indicators: MacroIndicators) -> str:
        """Generate macro economic report."""

        cycle = self.detect_economic_cycle(indicators)
        positioning = self.get_portfolio_positioning(indicators, cycle)

        report = f"""
MACRO ECONOMIC ANALYSIS
{'=' * 60}

ECONOMIC CYCLE: {cycle.value.upper()}
Recession Risk: {indicators.recession_risk:.1%}

KEY INDICATORS:
  Yield Curve (10Y-2Y):    {indicators.yield_curve_spread:+.2f}% {'⚠️ INVERTED' if indicators.yield_curve_inverted else '✓ Normal'}
  Unemployment Rate:       {indicators.unemployment_rate:.1f}%
  PMI (Manufacturing):     {indicators.pmi:.1f} {'✓ Expansion' if indicators.pmi > 50 else '⚠️ Contraction'}
  Consumer Confidence:     {indicators.consumer_confidence:.1f}
  Fed Funds Rate:          {indicators.fed_funds_rate:.2f}%
  Inflation Rate:          {indicators.inflation_rate:.1f}%
  GDP Growth:              {indicators.gdp_growth:+.1f}%

PORTFOLIO POSITIONING:
  Recommended Equity:      {positioning['equity_allocation']:.0%}
  Recommended Cash:        {positioning['cash_allocation']:.0%}
  Duration Bias:           {positioning['duration_bias'].upper()}
  Quality Bias:            {positioning['quality_bias'].upper()}

SECTOR ROTATION:
  Favor:  {', '.join(positioning['favored_sectors'])}
  Avoid:  {', '.join(positioning['avoid_sectors'])}

INTERPRETATION:
"""

        if cycle == EconomicCycle.EXPANSION:
            report += "  • Economy is growing - favor cyclical sectors\n"
            report += "  • High equity allocation appropriate\n"
            report += "  • Focus on growth stocks\n"
        elif cycle == EconomicCycle.PEAK:
            report += "  • Economy may be overheating - start taking profits\n"
            report += "  • Reduce equity exposure gradually\n"
            report += "  • Shift to defensive sectors\n"
        elif cycle == EconomicCycle.CONTRACTION:
            report += "  • Economic slowdown - preserve capital\n"
            report += "  • High cash allocation recommended\n"
            report += "  • Focus on quality and defensive sectors\n"
        elif cycle == EconomicCycle.TROUGH:
            report += "  • Economy bottoming - start accumulating\n"
            report += "  • Increase equity exposure on weakness\n"
            report += "  • Focus on early cycle sectors\n"

        if indicators.yield_curve_inverted:
            report += "\n⚠️  WARNING: Inverted yield curve signals recession within 12-18 months\n"

        if indicators.recession_risk > 0.5:
            report += f"\n⚠️  HIGH RECESSION RISK ({indicators.recession_risk:.0%}) - Defensive positioning recommended\n"

        return report


class FedPolicyTracker:
    """
    Tracks Federal Reserve policy and its market implications.
    """

    def __init__(self):
        """Initialize Fed policy tracker."""
        self.rate_history: List[Tuple[datetime, float]] = []

    def analyze_fed_policy(
        self, current_rate: float, inflation: float, unemployment: float
    ) -> Dict[str, any]:
        """
        Analyze Fed policy stance and implications.

        Args:
            current_rate: Current Fed funds rate
            inflation: Current inflation rate
            unemployment: Current unemployment rate

        Returns:
            Fed policy analysis
        """
        # Determine policy stance
        if current_rate < 2.0:
            stance = "ACCOMMODATIVE"
            market_impact = "BULLISH"
        elif current_rate > 5.0:
            stance = "RESTRICTIVE"
            market_impact = "BEARISH"
        else:
            stance = "NEUTRAL"
            market_impact = "NEUTRAL"

        # Predict next move
        if inflation > 3.0 and unemployment < 4.5:
            next_move = "HIKE"
            probability = 0.7
        elif inflation < 2.0 or unemployment > 5.0:
            next_move = "CUT"
            probability = 0.7
        else:
            next_move = "HOLD"
            probability = 0.6

        return {
            "current_rate": current_rate,
            "stance": stance,
            "market_impact": market_impact,
            "next_move": next_move,
            "move_probability": probability,
            "inflation_target_gap": inflation - 2.0,  # Fed targets 2%
            "unemployment_gap": unemployment - 4.0,  # Natural rate ~4%
        }
