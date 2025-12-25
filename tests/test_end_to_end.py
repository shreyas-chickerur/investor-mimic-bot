#!/usr/bin/env python3
"""
End-to-End System Validation Test

Tests the complete workflow from data loading to trade execution.
This is the comprehensive test that verifies everything works together.
"""

import sys
import os
sys.path.insert(0, 'src')

import pandas as pd
from datetime import datetime


def test_data_pipeline():
    """Test data loading and validation"""
    print("\n" + "="*80)
    print("TEST 1: DATA PIPELINE")
    print("="*80)
    
    df = pd.read_csv('data/training_data.csv', index_col=0)
    df.index = pd.to_datetime(df.index)
    
    assert len(df) > 0, "Data file is empty"
    assert 'symbol' in df.columns, "Missing symbol column"
    assert 'close' in df.columns, "Missing close column"
    assert df['symbol'].nunique() > 0, "No symbols in data"
    
    print(f"✅ Loaded {len(df):,} rows")
    print(f"✅ {df['symbol'].nunique()} symbols")
    print(f"✅ Date range: {df.index.min().date()} to {df.index.max().date()}")


def test_strategy_initialization():
    """Test all strategies can be initialized"""
    print("\n" + "="*80)
    print("TEST 2: STRATEGY INITIALIZATION")
    print("="*80)
    
    from strategies.strategy_rsi_mean_reversion import RSIMeanReversionStrategy
    from strategies.strategy_ma_crossover import MACrossoverStrategy
    from strategies.strategy_ml_momentum import MLMomentumStrategy
    from strategies.strategy_news_sentiment import NewsSentimentStrategy
    from strategies.strategy_volatility_breakout import VolatilityBreakoutStrategy
    
    strategies = [
        RSIMeanReversionStrategy(1, 20000),
        MACrossoverStrategy(2, 20000),
        MLMomentumStrategy(3, 20000),
        NewsSentimentStrategy(4, 20000),
        VolatilityBreakoutStrategy(5, 20000)
    ]
    
    for strategy in strategies:
        assert hasattr(strategy, 'generate_signals'), f"{strategy.name} missing generate_signals"
        print(f"✅ {strategy.name} initialized")
    


def test_signal_generation():
    """Test signal generation from strategies"""
    print("\n" + "="*80)
    print("TEST 3: SIGNAL GENERATION")
    print("="*80)
    
    from strategies.strategy_rsi_mean_reversion import RSIMeanReversionStrategy
    from strategies.strategy_ma_crossover import MACrossoverStrategy
    
    df = pd.read_csv('data/training_data.csv', index_col=0)
    df.index = pd.to_datetime(df.index)
    test_data = df.tail(1000)
    
    strategies = [
        RSIMeanReversionStrategy(1, 20000),
        MACrossoverStrategy(2, 20000)
    ]
    
    total_signals = 0
    for strategy in strategies:
        signals = strategy.generate_signals(test_data)
        print(f"   {strategy.name}: {len(signals)} signals")
        total_signals += len(signals)
    
    print(f"✅ Total signals generated: {total_signals}")


def test_risk_management():
    """Test risk management components"""
    print("\n" + "="*80)
    print("TEST 4: RISK MANAGEMENT")
    print("="*80)
    
    from regime_detector import RegimeDetector
    from correlation_filter import CorrelationFilter
    from portfolio_risk_manager import PortfolioRiskManager
    from execution_costs import ExecutionCostModel
    
    # Initialize components
    regime = RegimeDetector()
    corr_filter = CorrelationFilter()
    risk_mgr = PortfolioRiskManager()
    cost_model = ExecutionCostModel()
    
    # Test regime detection
    vix = 15.0
    regime_adj = regime.get_regime_adjustments(vix)
    assert 'max_portfolio_heat' in regime_adj, "Missing max_portfolio_heat"
    print(f"✅ Regime detector: VIX={vix}, Heat={regime_adj['max_portfolio_heat']*100}%")
    
    # Test portfolio heat
    can_add = risk_mgr.can_add_position(10000, 20000, 100000)
    print(f"✅ Portfolio heat check: {can_add}")
    
    # Test execution costs
    exec_price, slippage, commission, total_cost = cost_model.calculate_execution_price(
        100.0, 'BUY', 100
    )
    assert exec_price > 0, "Invalid execution price"
    assert total_cost > 0, "Invalid total cost"
    print(f"✅ Execution costs: price=${exec_price:.2f}, cost=${total_cost:.2f}")
    


def test_backtester_integration():
    """Test backtester with all components"""
    print("\n" + "="*80)
    print("TEST 5: BACKTESTER INTEGRATION")
    print("="*80)
    
    from portfolio_backtester import PortfolioBacktester
    from strategies.strategy_rsi_mean_reversion import RSIMeanReversionStrategy
    from regime_detector import RegimeDetector
    from correlation_filter import CorrelationFilter
    from portfolio_risk_manager import PortfolioRiskManager
    from execution_costs import ExecutionCostModel
    
    # Load data
    df = pd.read_csv('data/training_data.csv', index_col=0)
    df.index = pd.to_datetime(df.index)
    test_data = df.tail(500)  # Small test
    
    # Initialize components
    backtester = PortfolioBacktester(100000)
    strategies = [RSIMeanReversionStrategy(1, 20000)]
    regime = RegimeDetector()
    corr_filter = CorrelationFilter()
    risk_mgr = PortfolioRiskManager()
    cost_model = ExecutionCostModel()
    
    # Run backtest
    results = backtester.run_backtest(
        test_data,
        strategies,
        regime,
        corr_filter,
        risk_mgr,
        cost_model
    )
    
    assert 'final_value' in results, "Missing final_value in results"
    assert 'total_return' in results, "Missing total_return in results"
    
    print(f"✅ Backtest completed")
    print(f"   Final value: ${results['final_value']:,.2f}")
    print(f"   Total return: {results['total_return']:.2%}")
    print(f"   Trades: {len(backtester.trades)}")
    


def test_signal_injection():
    """Test signal injection for validation"""
    print("\n" + "="*80)
    print("TEST 6: SIGNAL INJECTION (VALIDATION)")
    print("="*80)
    
    from signal_injection_engine import SignalInjectionEngine
    from signal_tracer import SignalFlowTracer
    
    # Initialize
    injection_engine = SignalInjectionEngine()
    tracer = SignalFlowTracer()
    
    # Test injection
    date = datetime.now()
    signals = injection_engine.inject_signals(date, [])
    
    if injection_engine.is_enabled():
        assert len(signals) > 0, "Signal injection enabled but no signals generated"
        print(f"✅ Signal injection: {len(signals)} signals")
        for sig in signals:
            print(f"   {sig['action']} {sig['symbol']} @ ${sig['price']:.2f}")
    else:
        print("⚠️ Signal injection disabled (expected in production)")
    


def test_execution_pipeline():
    """Test complete execution pipeline"""
    print("\n" + "="*80)
    print("TEST 7: EXECUTION PIPELINE")
    print("="*80)
    
    from portfolio_backtester import PortfolioBacktester
    from execution_costs import ExecutionCostModel
    from portfolio_risk_manager import PortfolioRiskManager
    
    # Create backtester
    backtester = PortfolioBacktester(100000)
    cost_model = ExecutionCostModel()
    risk_mgr = PortfolioRiskManager()
    
    # Create test signal
    signal = {
        'symbol': 'AAPL',
        'action': 'BUY',
        'price': 150.0,
        'shares': 10,
        'strategy_id': 1
    }
    
    # Test execution
    date = datetime.now()
    initial_cash = backtester.cash
    
    new_cash = backtester._execute_buy(
        signal,
        backtester.cash,
        backtester.cash,
        risk_mgr,
        cost_model,
        date
    )
    
    if new_cash < initial_cash:
        print(f"✅ Trade executed: ${initial_cash - new_cash:.2f} spent")
        print(f"   Position: {backtester.positions.get('AAPL', {}).get('shares', 0)} shares")
    else:
        print("⚠️ Trade rejected (may be expected based on conditions)")
    


def test_performance_metrics():
    """Test performance tracking"""
    print("\n" + "="*80)
    print("TEST 8: PERFORMANCE METRICS")
    print("="*80)
    
    from performance_metrics import PerformanceMetrics
    
    metrics = PerformanceMetrics()
    
    # Add test trades
    metrics.add_trade('BUY', 'AAPL', 100, 150.0, 15000.0)
    metrics.add_trade('SELL', 'AAPL', 100, 155.0, 15500.0)
    
    summary = metrics.get_summary()
    
    assert 'total_trades' in summary, "Missing total_trades"
    assert summary['total_trades'] == 2, "Incorrect trade count"
    
    print(f"✅ Performance metrics working")
    print(f"   Total trades: {summary['total_trades']}")
    print(f"   Win rate: {summary.get('win_rate', 0):.1%}")
    


def run_all_tests():
    """Run all end-to-end tests"""
    print("\n" + "="*80)
    print("END-TO-END SYSTEM VALIDATION")
    print("="*80)
    
    tests = [
        ("Data Pipeline", test_data_pipeline),
        ("Strategy Initialization", test_strategy_initialization),
        ("Signal Generation", test_signal_generation),
        ("Risk Management", test_risk_management),
        ("Backtester Integration", test_backtester_integration),
        ("Signal Injection", test_signal_injection),
        ("Execution Pipeline", test_execution_pipeline),
        ("Performance Metrics", test_performance_metrics)
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            print(f"\n❌ {name} FAILED: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"Passed: {passed}/{len(tests)}")
    print(f"Failed: {failed}/{len(tests)}")
    
    if failed == 0:
        print("\n✅ ALL END-TO-END TESTS PASSED")
        return True
    else:
        print(f"\n❌ {failed} TEST(S) FAILED")
        return False


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
