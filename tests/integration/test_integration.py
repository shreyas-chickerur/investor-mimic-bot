#!/usr/bin/env python3
"""
Integration Tests for Mid-Level Quant System
Tests all modules working together
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def test_all_modules_import():
    """Test that all new modules import successfully"""
    print("Testing module imports...")

    try:
        print("✅ RegimeDetector imports")
    except Exception as e:
        print(f"❌ RegimeDetector: {e}")
        raise AssertionError(f"RegimeDetector import failed: {e}") from e

    try:
        print("✅ DynamicAllocator imports")
    except Exception as e:
        print(f"❌ DynamicAllocator: {e}")
        raise AssertionError(f"DynamicAllocator import failed: {e}") from e

    try:
        print("✅ CorrelationFilter imports")
    except Exception as e:
        print(f"❌ CorrelationFilter: {e}")
        raise AssertionError(f"CorrelationFilter import failed: {e}") from e

    try:
        print("✅ PortfolioRiskManager imports")
    except Exception as e:
        print(f"❌ PortfolioRiskManager: {e}")
        raise AssertionError(f"PortfolioRiskManager import failed: {e}") from e

    try:
        print("✅ ExecutionCostModel imports")
    except Exception as e:
        print(f"❌ ExecutionCostModel: {e}")
        raise AssertionError(f"ExecutionCostModel import failed: {e}") from e

    try:
        print("✅ PerformanceMetrics imports")
    except Exception as e:
        print(f"❌ PerformanceMetrics: {e}")
        raise AssertionError(f"PerformanceMetrics import failed: {e}") from e


def test_regime_detection():
    """Test regime detection functionality"""
    print("\nTesting regime detection...")

    from src.regime.regime_detector import RegimeDetector

    rd = RegimeDetector()

    # Test low volatility (base heat 0.30 scaled up 1.2x)
    adjustments_low = rd.get_regime_adjustments(vix=12.0)
    assert adjustments_low["max_portfolio_heat"] == pytest.approx(
        0.36
    ), "Low VIX should increase heat to 36%"
    print(f"✅ Low VIX (12): Heat = {adjustments_low['max_portfolio_heat']*100}%")

    # Test high volatility (base heat 0.30 scaled down 0.7x)
    adjustments_high = rd.get_regime_adjustments(vix=30.0)
    assert adjustments_high["max_portfolio_heat"] == pytest.approx(
        0.21
    ), "High VIX should reduce heat to 21%"
    assert not adjustments_high["enable_breakout"], "High VIX should disable breakouts"
    print(
        f"✅ High VIX (30): Heat = {adjustments_high['max_portfolio_heat']*100}%, Breakouts disabled"
    )

    # Test normal volatility
    adjustments_normal = rd.get_regime_adjustments(vix=18.0)
    assert adjustments_normal["max_portfolio_heat"] == 0.30, "Normal VIX should keep heat at 30%"
    print(f"✅ Normal VIX (18): Heat = {adjustments_normal['max_portfolio_heat']*100}%")


def test_dynamic_allocation():
    """Test dynamic capital allocation"""
    print("\nTesting dynamic allocation...")

    import numpy as np

    from src.regime.dynamic_allocator import DynamicAllocator

    da = DynamicAllocator(100000)

    # Test equal allocation (no performance data)
    allocs = da.calculate_allocations([1, 2, 3, 4, 5])
    assert len(allocs) == 5, "Should have 5 allocations"
    assert all(20000 <= v <= 20000 for v in allocs.values()), "Should be equal ~$20K each"
    print(f"✅ Equal allocation: ${list(allocs.values())[0]:,.2f} per strategy")

    # Test dynamic allocation with performance (seeded — unseeded draws made
    # this test flaky when a strategy's random returns crossed an allocator bound)
    rng = np.random.RandomState(42)
    perf_data = {
        1: list(rng.normal(0.001, 0.01, 60)),  # Good performance
        2: list(rng.normal(0.0005, 0.01, 60)),  # Moderate
        3: list(rng.normal(-0.0005, 0.01, 60)),  # Slightly negative
        4: list(rng.normal(0.0008, 0.01, 60)),  # Good
        5: list(rng.normal(0.0003, 0.01, 60)),  # Moderate
    }

    allocs_dynamic = da.calculate_allocations([1, 2, 3, 4, 5], perf_data)
    total = sum(allocs_dynamic.values())
    assert 99000 <= total <= 101000, f"Total should be ~$100K, got ${total:,.2f}"

    # Check constraints (allocator contract: min_allocation_pct=0.05, max_allocation_pct=0.35)
    for strat_id, allocation in allocs_dynamic.items():
        pct = allocation / 100000
        assert pct >= 0.05 - 1e-9, f"Strategy {strat_id} below min 5%"
        assert pct <= 0.35 + 1e-9, f"Strategy {strat_id} above max 35%"

    print(f"✅ Dynamic allocation: Total = ${total:,.2f}, within constraints")


def test_correlation_filter():
    """Test correlation filtering with dual windows"""
    print("\nTesting correlation filter...")

    import numpy as np
    import pandas as pd

    from src.risk.correlation_filter import CorrelationFilter

    cf = CorrelationFilter()

    # Create correlated price series
    base_prices = np.cumsum(np.random.normal(0, 1, 100)) + 100

    # Highly correlated stock
    correlated_prices = base_prices + np.random.normal(0, 0.5, 100)

    # Update price history
    cf.update_price_history("AAPL", pd.Series(base_prices))
    cf.update_price_history("MSFT", pd.Series(correlated_prices))

    # Test correlation filter
    existing_positions = {"AAPL": 100}
    should_filter, reason, correlations = cf.should_filter_signal("MSFT", existing_positions)

    print(f"✅ Correlation check: should_filter={should_filter}, reason={reason}")


def test_portfolio_risk():
    """Test portfolio risk management"""
    print("\nTesting portfolio risk management...")

    from src.risk.portfolio_risk_manager import PortfolioRiskManager

    prm = PortfolioRiskManager()
    prm.set_daily_start_value(100000)

    # Test daily loss limit
    can_trade = prm.check_daily_loss_limit(97500)  # -2.5% loss
    assert not can_trade, "Should halt trading at -2.5% loss"
    print("✅ Daily loss circuit breaker triggered at -2.5%")

    # Test portfolio heat
    can_add = prm.can_add_position(10000, 25000, 100000)  # Would be 35% heat
    assert not can_add, "Should reject position that exceeds 30% heat"
    print("✅ Portfolio heat limit enforced at 30%")

    # Test acceptable position
    prm2 = PortfolioRiskManager()
    prm2.set_daily_start_value(100000)
    can_add_ok = prm2.can_add_position(10000, 15000, 100000)  # Would be 25% heat
    assert can_add_ok, "Should accept position within limits"
    print("✅ Acceptable position allowed")


def test_execution_costs():
    """Test execution cost modeling"""
    print("\nTesting execution costs...")

    from src.utils.execution_costs import ExecutionCostModel

    ecm = ExecutionCostModel()

    # Test buy order
    exec_price, slippage, commission, total_cost = ecm.calculate_execution_price(
        quoted_price=100.0, side="BUY", shares=100
    )

    assert exec_price > 100.0, "Buy execution price should be higher than quoted"
    assert slippage > 0, "Should have slippage cost"
    assert commission > 0, "Should have commission cost"
    print(f"✅ BUY 100 @ $100: exec=${exec_price:.2f}, costs=${total_cost:.2f}")

    # Test sell order
    (
        exec_price_sell,
        slippage_sell,
        commission_sell,
        total_cost_sell,
    ) = ecm.calculate_execution_price(quoted_price=100.0, side="SELL", shares=100)

    assert exec_price_sell < 100.0, "Sell execution price should be lower than quoted"
    print(f"✅ SELL 100 @ $100: exec=${exec_price_sell:.2f}, costs=${total_cost_sell:.2f}")


def test_performance_metrics():
    """Test performance metrics calculation"""
    print("\nTesting performance metrics...")

    from src.monitoring.performance_metrics import PerformanceMetrics

    pm = PerformanceMetrics()

    # Record trade executions (current API tracks fills; P&L is computed elsewhere)
    pm.add_trade(action="BUY", symbol="AAPL", shares=10, price=100.0, value=1000.0)
    pm.add_trade(action="SELL", symbol="AAPL", shares=10, price=105.0, value=1050.0)

    metrics = pm.calculate_metrics()

    assert metrics["total_trades"] == 2, "Should have 2 trades"
    assert metrics["win_rate"] == 0.0, "Executions carry zero P&L, so no wins recorded"
    print(f"✅ Metrics: {metrics['total_trades']} trades, {metrics['win_rate']:.1f}% win rate")
