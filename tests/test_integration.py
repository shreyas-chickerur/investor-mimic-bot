#!/usr/bin/env python3
"""
Integration Tests for Mid-Level Quant System
Tests all modules working together
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

def test_all_modules_import():
    """Test that all new modules import successfully"""
    print("Testing module imports...")
    
    try:
        from regime_detector import RegimeDetector
        print("✅ RegimeDetector imports")
    except Exception as e:
        print(f"❌ RegimeDetector: {e}")
        return False
    
    try:
        from dynamic_allocator import DynamicAllocator
        print("✅ DynamicAllocator imports")
    except Exception as e:
        print(f"❌ DynamicAllocator: {e}")
        return False
    
    try:
        from correlation_filter import CorrelationFilter
        print("✅ CorrelationFilter imports")
    except Exception as e:
        print(f"❌ CorrelationFilter: {e}")
        return False
    
    try:
        from portfolio_risk_manager import PortfolioRiskManager
        print("✅ PortfolioRiskManager imports")
    except Exception as e:
        print(f"❌ PortfolioRiskManager: {e}")
        return False
    
    try:
        from execution_costs import ExecutionCostModel
        print("✅ ExecutionCostModel imports")
    except Exception as e:
        print(f"❌ ExecutionCostModel: {e}")
        return False
    
    try:
        from performance_metrics import PerformanceMetrics
        print("✅ PerformanceMetrics imports")
    except Exception as e:
        print(f"❌ PerformanceMetrics: {e}")
        return False
    
    return True

def test_regime_detection():
    """Test regime detection functionality"""
    print("\nTesting regime detection...")
    
    from regime_detector import RegimeDetector
    
    rd = RegimeDetector()
    
    # Test low volatility
    adjustments_low = rd.get_regime_adjustments(vix=12.0)
    assert adjustments_low['max_portfolio_heat'] == 0.40, "Low VIX should increase heat to 40%"
    print(f"✅ Low VIX (12): Heat = {adjustments_low['max_portfolio_heat']*100}%")
    
    # Test high volatility
    adjustments_high = rd.get_regime_adjustments(vix=30.0)
    assert adjustments_high['max_portfolio_heat'] == 0.20, "High VIX should reduce heat to 20%"
    assert not adjustments_high['enable_breakout'], "High VIX should disable breakouts"
    print(f"✅ High VIX (30): Heat = {adjustments_high['max_portfolio_heat']*100}%, Breakouts disabled")
    
    # Test normal volatility
    adjustments_normal = rd.get_regime_adjustments(vix=18.0)
    assert adjustments_normal['max_portfolio_heat'] == 0.30, "Normal VIX should keep heat at 30%"
    print(f"✅ Normal VIX (18): Heat = {adjustments_normal['max_portfolio_heat']*100}%")
    
    return True

def test_dynamic_allocation():
    """Test dynamic capital allocation"""
    print("\nTesting dynamic allocation...")
    
    from dynamic_allocator import DynamicAllocator
    import numpy as np
    
    da = DynamicAllocator(100000)
    
    # Test equal allocation (no performance data)
    allocs = da.calculate_allocations([1, 2, 3, 4, 5])
    assert len(allocs) == 5, "Should have 5 allocations"
    assert all(20000 <= v <= 20000 for v in allocs.values()), "Should be equal ~$20K each"
    print(f"✅ Equal allocation: ${list(allocs.values())[0]:,.2f} per strategy")
    
    # Test dynamic allocation with performance
    perf_data = {
        1: list(np.random.normal(0.001, 0.01, 60)),  # Good performance
        2: list(np.random.normal(0.0005, 0.01, 60)),  # Moderate
        3: list(np.random.normal(-0.0005, 0.01, 60)),  # Slightly negative
        4: list(np.random.normal(0.0008, 0.01, 60)),  # Good
        5: list(np.random.normal(0.0003, 0.01, 60))   # Moderate
    }
    
    allocs_dynamic = da.calculate_allocations([1, 2, 3, 4, 5], perf_data)
    total = sum(allocs_dynamic.values())
    assert 99000 <= total <= 101000, f"Total should be ~$100K, got ${total:,.2f}"
    
    # Check constraints
    for strat_id, allocation in allocs_dynamic.items():
        pct = allocation / 100000
        assert pct >= 0.10, f"Strategy {strat_id} below min 10%"
        assert pct <= 0.35, f"Strategy {strat_id} above max 35%"
    
    print(f"✅ Dynamic allocation: Total = ${total:,.2f}, within constraints")
    
    return True

def test_correlation_filter():
    """Test correlation filtering with dual windows"""
    print("\nTesting correlation filter...")
    
    from correlation_filter import CorrelationFilter
    import pandas as pd
    import numpy as np
    
    cf = CorrelationFilter()
    
    # Create correlated price series
    dates = pd.date_range('2024-01-01', periods=100)
    base_prices = np.cumsum(np.random.normal(0, 1, 100)) + 100
    
    # Highly correlated stock
    correlated_prices = base_prices + np.random.normal(0, 0.5, 100)
    
    # Update price history
    cf.update_price_history('AAPL', pd.Series(base_prices))
    cf.update_price_history('MSFT', pd.Series(correlated_prices))
    
    # Check correlation
    is_acceptable, corr, symbol = cf.check_correlation('MSFT', ['AAPL'])
    
    print(f"✅ Correlation check: corr={corr:.2f}, acceptable={is_acceptable}")
    
    return True

def test_portfolio_risk():
    """Test portfolio risk management"""
    print("\nTesting portfolio risk management...")
    
    from portfolio_risk_manager import PortfolioRiskManager
    
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
    
    return True

def test_execution_costs():
    """Test execution cost modeling"""
    print("\nTesting execution costs...")
    
    from execution_costs import ExecutionCostModel
    
    ecm = ExecutionCostModel()
    
    # Test buy order
    exec_price, slippage, commission, total_cost = ecm.calculate_execution_price(
        quoted_price=100.0,
        side='BUY',
        shares=100
    )
    
    assert exec_price > 100.0, "Buy execution price should be higher than quoted"
    assert slippage > 0, "Should have slippage cost"
    assert commission > 0, "Should have commission cost"
    print(f"✅ BUY 100 @ $100: exec=${exec_price:.2f}, costs=${total_cost:.2f}")
    
    # Test sell order
    exec_price_sell, slippage_sell, commission_sell, total_cost_sell = ecm.calculate_execution_price(
        quoted_price=100.0,
        side='SELL',
        shares=100
    )
    
    assert exec_price_sell < 100.0, "Sell execution price should be lower than quoted"
    print(f"✅ SELL 100 @ $100: exec=${exec_price_sell:.2f}, costs=${total_cost_sell:.2f}")
    
    return True

def test_performance_metrics():
    """Test performance metrics calculation"""
    print("\nTesting performance metrics...")
    
    from performance_metrics import PerformanceMetrics
    from datetime import datetime, timedelta
    
    pm = PerformanceMetrics()
    
    # Add some trades
    base_date = datetime(2024, 1, 1)
    pm.add_trade(
        entry_price=100.0,
        exit_price=105.0,
        shares=10,
        entry_date=base_date,
        exit_date=base_date + timedelta(days=5),
        costs=5.0
    )
    
    pm.add_trade(
        entry_price=200.0,
        exit_price=195.0,
        shares=5,
        entry_date=base_date + timedelta(days=10),
        exit_date=base_date + timedelta(days=15),
        costs=3.0
    )
    
    metrics = pm.calculate_metrics()
    
    assert metrics['total_trades'] == 2, "Should have 2 trades"
    assert metrics['win_rate'] == 50.0, "Should have 50% win rate"
    print(f"✅ Metrics: {metrics['total_trades']} trades, {metrics['win_rate']:.1f}% win rate")
    
    return True

def run_all_tests():
    """Run all integration tests"""
    print("=" * 80)
    print("INTEGRATION TESTS - MID-LEVEL QUANT SYSTEM")
    print("=" * 80)
    
    tests = [
        ("Module Imports", test_all_modules_import),
        ("Regime Detection", test_regime_detection),
        ("Dynamic Allocation", test_dynamic_allocation),
        ("Correlation Filter", test_correlation_filter),
        ("Portfolio Risk", test_portfolio_risk),
        ("Execution Costs", test_execution_costs),
        ("Performance Metrics", test_performance_metrics)
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
                print(f"\n✅ {name} PASSED\n")
            else:
                failed += 1
                print(f"\n❌ {name} FAILED\n")
        except Exception as e:
            failed += 1
            print(f"\n❌ {name} FAILED: {e}\n")
    
    print("=" * 80)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 80)
    
    return failed == 0

if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
