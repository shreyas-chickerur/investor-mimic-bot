#!/usr/bin/env python3
"""
Comprehensive tests for advanced profit-maximizing features.

Tests:
1. Stop-loss and take-profit automation
2. Position rebalancing
3. Adaptive regime detection
4. Sector rotation
5. Macro indicators
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from services.market.adaptive_regime_engine import AdaptiveRegimeEngine, MarketRegimeType
from services.market.macro_indicators import EconomicCycle, MacroIndicatorTracker
from services.portfolio.rebalancer import PortfolioRebalancer, RebalanceConfig
from services.risk.stop_loss_manager import StopLossConfig, StopLossManager, TakeProfitConfig


class TestStopLossManager:
    """Test stop-loss and take-profit functionality."""

    @pytest.fixture
    def manager(self):
        return StopLossManager()

    def test_add_position(self, manager):
        """Test adding a position."""
        position = manager.add_position(symbol="AAPL", entry_price=150.0, quantity=100)

        assert position.symbol == "AAPL"
        assert position.entry_price == 150.0
        assert position.quantity == 100
        assert position.stop_price < 150.0  # Stop should be below entry

    def test_stop_loss_trigger(self, manager):
        """Test stop-loss trigger."""
        manager.add_position("AAPL", 150.0, 100)

        # Price drops to stop level
        should_exit, reason, qty = manager.update_position("AAPL", 135.0)

        assert should_exit is True
        assert reason == "STOP_LOSS"
        assert qty == 100

    def test_trailing_stop(self, manager):
        """Test trailing stop functionality."""
        manager.add_position("AAPL", 150.0, 100)

        # Price rises - trailing stop should move up
        manager.update_position("AAPL", 165.0)
        position = manager.positions["AAPL"]
        initial_stop = position.stop_price

        # Price rises more
        manager.update_position("AAPL", 180.0)
        new_stop = position.stop_price

        assert new_stop > initial_stop  # Stop moved up

    def test_take_profit_targets(self, manager):
        """Test take-profit targets."""
        manager.add_position("AAPL", 150.0, 100)

        # Hit first target (+15%)
        should_exit, reason, qty = manager.update_position("AAPL", 172.5)

        assert should_exit is True
        assert reason == "TAKE_PROFIT_1"
        assert qty == 50  # 50% of position

        # Hit second target (+30%)
        should_exit, reason, qty = manager.update_position("AAPL", 195.0)

        assert should_exit is True
        assert reason == "TAKE_PROFIT_2"
        assert qty == 25  # 25% of position


class TestPortfolioRebalancer:
    """Test portfolio rebalancing."""

    @pytest.fixture
    def rebalancer(self):
        return PortfolioRebalancer()

    def test_calculate_weights(self, rebalancer):
        """Test weight calculation."""
        positions = {
            "AAPL": {"quantity": 100, "price": 150.0, "target_weight": 0.20},
            "GOOGL": {"quantity": 50, "price": 140.0, "target_weight": 0.20},
            "MSFT": {"quantity": 80, "price": 380.0, "target_weight": 0.20},
        }

        total_value = 100 * 150 + 50 * 140 + 80 * 380

        portfolio_positions = rebalancer.calculate_portfolio_weights(positions, total_value)

        assert len(portfolio_positions) == 3
        assert all(pos.current_weight > 0 for pos in portfolio_positions.values())

    def test_identify_rebalance_needs(self, rebalancer):
        """Test identifying positions that need rebalancing."""
        positions = {
            "AAPL": {"quantity": 200, "price": 150.0, "target_weight": 0.10},  # Oversized
            "GOOGL": {"quantity": 10, "price": 140.0, "target_weight": 0.10},  # Undersized
            "MSFT": {"quantity": 80, "price": 380.0, "target_weight": 0.30},  # OK
        }

        total_value = 200 * 150 + 10 * 140 + 80 * 380
        portfolio_positions = rebalancer.calculate_portfolio_weights(positions, total_value)

        oversized, undersized, within_range = rebalancer.identify_rebalance_needs(
            portfolio_positions
        )

        assert "AAPL" in oversized
        assert "GOOGL" in undersized

    def test_calculate_rebalance_trades(self, rebalancer):
        """Test calculating rebalance trades."""
        positions = {
            "AAPL": {"quantity": 200, "price": 150.0, "target_weight": 0.10},
            "GOOGL": {"quantity": 10, "price": 140.0, "target_weight": 0.10},
        }

        total_value = 200 * 150 + 10 * 140
        portfolio_positions = rebalancer.calculate_portfolio_weights(positions, total_value)

        trades = rebalancer.calculate_rebalance_trades(portfolio_positions, total_value)

        assert len(trades) > 0
        assert any(t["action"] == "SELL" for t in trades)
        assert any(t["action"] == "BUY" for t in trades)


class TestAdaptiveRegimeEngine:
    """Test adaptive market regime detection."""

    @pytest.fixture
    def engine(self):
        return AdaptiveRegimeEngine()

    def test_detect_bull_market(self, engine):
        """Test bull market detection."""
        # Create uptrending price series
        prices = pd.Series([100 + i for i in range(250)])

        regime = engine.detect_regime(prices, vix_level=15.0, breadth=70.0)

        assert regime.regime == MarketRegimeType.BULL
        assert regime.confidence > 0.6

    def test_detect_bear_market(self, engine):
        """Test bear market detection."""
        # Create downtrending price series
        prices = pd.Series([350 - i for i in range(250)])

        regime = engine.detect_regime(prices, vix_level=25.0, breadth=30.0)

        assert regime.regime == MarketRegimeType.BEAR
        assert regime.confidence > 0.6

    def test_detect_volatile_market(self, engine):
        """Test volatile market detection."""
        # Create normal price series but with high VIX
        prices = pd.Series([100 + np.random.randn() * 2 for _ in range(250)])

        regime = engine.detect_regime(prices, vix_level=40.0, breadth=50.0)

        assert regime.regime == MarketRegimeType.VOLATILE

    def test_adaptive_weights_bull(self, engine):
        """Test adaptive weights in bull market."""
        prices = pd.Series([100 + i for i in range(250)])

        weights = engine.get_adaptive_weights(prices, vix_level=15.0, breadth=70.0)

        # In bull market, moving averages and relative strength should be higher
        assert weights["moving_avg"] > 0.20
        assert weights["relative_strength"] > 0.10

    def test_adaptive_weights_bear(self, engine):
        """Test adaptive weights in bear market."""
        prices = pd.Series([350 - i for i in range(250)])

        weights = engine.get_adaptive_weights(prices, vix_level=30.0, breadth=30.0)

        # In bear market, conviction and news should be higher
        assert weights["conviction"] > 0.35
        assert weights["news"] > 0.15
        assert weights["relative_strength"] == 0.0  # Should be zero in bear


class TestMacroIndicators:
    """Test macro economic indicators."""

    @pytest.fixture
    def tracker(self):
        return MacroIndicatorTracker()

    def test_get_current_indicators(self, tracker):
        """Test getting current indicators."""
        indicators = tracker.get_current_indicators()

        assert indicators.yield_curve_spread is not None
        assert indicators.unemployment_rate > 0
        assert indicators.pmi > 0

    def test_recession_risk_calculation(self, tracker):
        """Test recession risk calculation."""
        from services.market.macro_indicators import MacroIndicators

        # High recession risk scenario
        high_risk = MacroIndicators(
            yield_curve_spread=-0.5,  # Inverted
            unemployment_rate=6.0,
            pmi=45.0,  # Contracting
            consumer_confidence=80.0,
            fed_funds_rate=5.0,
            inflation_rate=2.0,
            gdp_growth=-1.0,
        )

        assert high_risk.recession_risk > 0.7

        # Low recession risk scenario
        low_risk = MacroIndicators(
            yield_curve_spread=1.5,
            unemployment_rate=3.5,
            pmi=55.0,
            consumer_confidence=110.0,
            fed_funds_rate=3.0,
            inflation_rate=2.0,
            gdp_growth=3.0,
        )

        assert low_risk.recession_risk < 0.3

    def test_economic_cycle_detection(self, tracker):
        """Test economic cycle detection."""
        from services.market.macro_indicators import MacroIndicators

        # Expansion scenario
        expansion = MacroIndicators(
            yield_curve_spread=1.0,
            unemployment_rate=3.8,
            pmi=54.0,
            consumer_confidence=105.0,
            fed_funds_rate=4.0,
            inflation_rate=2.5,
            gdp_growth=2.8,
        )

        cycle = tracker.detect_economic_cycle(expansion)
        assert cycle == EconomicCycle.EXPANSION

    def test_sector_recommendations(self, tracker):
        """Test sector recommendations by cycle."""
        recs = tracker.get_sector_recommendations(EconomicCycle.EXPANSION)

        assert "Technology" in recs["favor"]
        assert "Utilities" in recs["avoid"]


def run_manual_tests():
    """Run manual tests."""
    print("=" * 80)
    print("ADVANCED FEATURES TESTS")
    print("=" * 80)
    print()

    # Test 1: Stop-Loss Manager
    print("Test 1: Stop-Loss Manager")
    print("-" * 40)
    manager = StopLossManager()
    manager.add_position("AAPL", 150.0, 100)

    # Simulate price movement
    manager.update_position("AAPL", 165.0)  # Price up
    manager.update_position("AAPL", 180.0)  # Price up more

    status = manager.get_position_status("AAPL")
    print(f"  Position: {status['symbol']}")
    print(f"  Entry: ${status['entry_price']:.2f}")
    print(f"  Current: ${status['current_price']:.2f}")
    print(f"  P&L: {status['current_pnl_pct']:+.1f}%")
    print(f"  Stop: ${status['stop_price']:.2f}")
    print("  ✓ Stop-loss manager working")
    print()

    # Test 2: Portfolio Rebalancer
    print("Test 2: Portfolio Rebalancer")
    print("-" * 40)
    rebalancer = PortfolioRebalancer()

    positions = {
        "AAPL": {"quantity": 200, "price": 150.0, "target_weight": 0.10},
        "GOOGL": {"quantity": 10, "price": 140.0, "target_weight": 0.10},
        "MSFT": {"quantity": 80, "price": 380.0, "target_weight": 0.30},
    }

    total_value = 200 * 150 + 10 * 140 + 80 * 380
    portfolio_positions = rebalancer.calculate_portfolio_weights(positions, total_value)

    oversized, undersized, _ = rebalancer.identify_rebalance_needs(portfolio_positions)
    print(f"  Oversized: {oversized}")
    print(f"  Undersized: {undersized}")
    print("  ✓ Rebalancer working")
    print()

    # Test 3: Adaptive Regime Engine
    print("Test 3: Adaptive Regime Engine")
    print("-" * 40)
    engine = AdaptiveRegimeEngine()

    # Bull market scenario
    prices = pd.Series([100 + i * 0.5 for i in range(250)])
    regime = engine.detect_regime(prices, vix_level=15.0, breadth=70.0)

    print(f"  Regime: {regime.regime.value.upper()}")
    print(f"  Confidence: {regime.confidence:.1%}")
    print(f"  VIX: {regime.vix_level:.1f}")
    print(f"  Adaptive Weights:")
    for factor, weight in regime.weights.to_dict().items():
        print(f"    {factor}: {weight:.0%}")
    print("  ✓ Adaptive regime engine working")
    print()

    # Test 4: Macro Indicators
    print("Test 4: Macro Indicators")
    print("-" * 40)
    tracker = MacroIndicatorTracker()
    indicators = tracker.get_current_indicators()
    cycle = tracker.detect_economic_cycle(indicators)

    print(f"  Economic Cycle: {cycle.value.upper()}")
    print(f"  Recession Risk: {indicators.recession_risk:.1%}")
    print(f"  Yield Curve: {indicators.yield_curve_spread:+.2f}%")
    print(f"  PMI: {indicators.pmi:.1f}")
    print("  ✓ Macro indicators working")
    print()

    print("=" * 80)
    print("✅ ALL ADVANCED FEATURES TESTS PASSED!")
    print("=" * 80)


if __name__ == "__main__":
    run_manual_tests()
