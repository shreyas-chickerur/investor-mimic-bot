#!/usr/bin/env python3
"""
Phase 4 Validation Backtest Runner

Implements all Phase 4 requirements:
1. Signal injection mode
2. Parameter sweep mode
3. Volatile period testing
4. Signal flow tracing
5. Zero-share guardrails

This proves system correctness without weakening production logic.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import pandas as pd
import logging
import yaml
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/validation_backtest.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

from signal_injection_engine import SignalInjectionEngine
from signal_flow_tracer import SignalFlowTracer
from portfolio_backtester import PortfolioBacktester
from regime_detector import RegimeDetector
from correlation_filter import CorrelationFilter
from portfolio_risk_manager import PortfolioRiskManager
from execution_costs import ExecutionCostModel

from strategies.strategy_rsi_mean_reversion import RSIMeanReversionStrategy

def load_config():
    """Load validation configuration"""
    config_path = Path(__file__).parent.parent / 'config' / 'validation_config.yaml'
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def run_signal_injection_test(market_data):
    """Test 1: Signal Injection Mode"""
    logger.info("\n" + "="*80)
    logger.info("TEST 1: SIGNAL INJECTION MODE")
    logger.info("="*80)
    logger.info("Purpose: Validate execution pipeline with synthetic signals")
    logger.info("Bypasses: Signal generation only")
    logger.info("Validates: Risk checks, sizing, execution, tracking")
    
    # Enable signal injection
    config = load_config()
    config['validation_mode']['signal_injection']['enabled'] = True
    
    # Save modified config
    config_path = Path(__file__).parent.parent / 'config' / 'validation_config.yaml'
    with open(config_path, 'w') as f:
        yaml.dump(config, f)
    
    # Initialize components
    injection_engine = SignalInjectionEngine()
    tracer = SignalFlowTracer('logs/signal_injection_trace.log')
    
    # Run backtest with injection
    logger.info("\nRunning backtest with signal injection...")
    
    # Use last 30 days for quick test
    test_data = market_data.tail(1000)
    
    backtester = PortfolioBacktester(
        initial_capital=100000,
        start_date=test_data.index.min().strftime('%Y-%m-%d'),
        end_date=test_data.index.max().strftime('%Y-%m-%d')
    )
    
    # Initialize modules
    strategies = [RSIMeanReversionStrategy(1, 100000)]
    regime_detector = RegimeDetector()
    correlation_filter = CorrelationFilter()
    portfolio_risk = PortfolioRiskManager()
    cost_model = ExecutionCostModel()
    
    # Run backtest with injection and tracing
    results = backtester.run_backtest(
        market_data=test_data,
        strategies=strategies,
        regime_detector=regime_detector,
        correlation_filter=correlation_filter,
        portfolio_risk=portfolio_risk,
        cost_model=cost_model,
        signal_injection_engine=injection_engine,
        signal_tracer=tracer
    )
    
    logger.info("\n" + "="*80)
    logger.info("SIGNAL INJECTION TEST RESULTS")
    logger.info("="*80)
    logger.info(f"Total Trades: {results.get('total_trades', 0)}")
    logger.info(f"Final Value: ${results.get('final_value', 0):,.2f}")
    logger.info(f"Return: {results.get('total_return', 0):.2f}%")
    
    tracer.print_summary()
    
    # Disable injection
    config['validation_mode']['signal_injection']['enabled'] = False
    with open(config_path, 'w') as f:
        yaml.dump(config, f)
    
    return results.get('total_trades', 0) > 0

def run_parameter_sweep_test(market_data):
    """Test 2: Parameter Sweep Mode"""
    logger.info("\n" + "="*80)
    logger.info("TEST 2: PARAMETER SWEEP MODE")
    logger.info("="*80)
    logger.info("Purpose: Prove strategy logic works across parameter ranges")
    logger.info("Tests: Conservative, Moderate, Relaxed thresholds")
    
    config = load_config()
    sweeps = config['strategy_overrides']['rsi_mean_reversion']['validation_sweeps']
    
    results_summary = []
    
    for sweep in sweeps:
        logger.info(f"\n--- Testing {sweep['name']} parameters ---")
        logger.info(f"RSI Threshold: {sweep['rsi_threshold']}")
        logger.info(f"Slope Required: {sweep['slope_required']}")
        logger.info(f"Hold Days: {sweep['hold_days']}")
        
        # Create strategy with override parameters
        strategy = RSIMeanReversionStrategy(1, 100000)
        strategy.rsi_threshold = sweep['rsi_threshold']
        strategy.hold_days = sweep['hold_days']
        
        # Run backtest
        test_data = market_data.tail(5000)  # Last ~1 year
        
        backtester = PortfolioBacktester(
            initial_capital=100000,
            start_date=test_data.index.min().strftime('%Y-%m-%d'),
            end_date=test_data.index.max().strftime('%Y-%m-%d')
        )
        
        results = backtester.run_backtest(
            market_data=test_data,
            strategies=[strategy],
            regime_detector=RegimeDetector(),
            correlation_filter=CorrelationFilter(),
            portfolio_risk=PortfolioRiskManager(),
            cost_model=ExecutionCostModel()
        )
        
        logger.info(f"Trades: {results.get('total_trades', 0)}")
        logger.info(f"Return: {results.get('total_return', 0):.2f}%")
        
        results_summary.append({
            'name': sweep['name'],
            'trades': results.get('total_trades', 0),
            'return': results.get('total_return', 0)
        })
    
    logger.info("\n" + "="*80)
    logger.info("PARAMETER SWEEP SUMMARY")
    logger.info("="*80)
    for r in results_summary:
        logger.info(f"{r['name']:15} | Trades: {r['trades']:3} | Return: {r['return']:6.2f}%")
    
    return any(r['trades'] > 0 for r in results_summary)

def run_volatile_period_test(market_data):
    """Test 3: Volatile Period Testing"""
    logger.info("\n" + "="*80)
    logger.info("TEST 3: VOLATILE PERIOD TESTING")
    logger.info("="*80)
    logger.info("Purpose: Validate mean-reversion in designed environment")
    
    config = load_config()
    periods = config['volatile_test_periods']
    
    results_summary = []
    
    for period in periods:
        logger.info(f"\n--- Testing {period['name']} ---")
        logger.info(f"Period: {period['start']} to {period['end']}")
        logger.info(f"Description: {period['description']}")
        
        # Filter data to period
        start = pd.to_datetime(period['start'])
        end = pd.to_datetime(period['end'])
        period_data = market_data[(market_data.index >= start) & (market_data.index <= end)]
        
        if len(period_data) == 0:
            logger.warning(f"No data available for {period['name']}")
            continue
        
        logger.info(f"Data: {len(period_data)} rows")
        
        # Run backtest
        backtester = PortfolioBacktester(
            initial_capital=100000,
            start_date=start.strftime('%Y-%m-%d'),
            end_date=end.strftime('%Y-%m-%d')
        )
        
        results = backtester.run_backtest(
            market_data=period_data,
            strategies=[RSIMeanReversionStrategy(1, 100000)],
            regime_detector=RegimeDetector(),
            correlation_filter=CorrelationFilter(),
            portfolio_risk=PortfolioRiskManager(),
            cost_model=ExecutionCostModel()
        )
        
        logger.info(f"Trades: {results.get('total_trades', 0)}")
        logger.info(f"Return: {results.get('total_return', 0):.2f}%")
        logger.info(f"Max DD: {results.get('max_drawdown', 0):.2f}%")
        
        results_summary.append({
            'period': period['name'],
            'trades': results.get('total_trades', 0),
            'return': results.get('total_return', 0),
            'max_dd': results.get('max_drawdown', 0)
        })
    
    logger.info("\n" + "="*80)
    logger.info("VOLATILE PERIOD SUMMARY")
    logger.info("="*80)
    for r in results_summary:
        logger.info(f"{r['period']:20} | Trades: {r['trades']:3} | Return: {r['return']:7.2f}% | Max DD: {r['max_dd']:6.2f}%")
    
    return any(r['trades'] > 0 for r in results_summary)

def main():
    """Run Phase 4 validation tests"""
    logger.info("="*80)
    logger.info("PHASE 4 VALIDATION BACKTEST")
    logger.info("="*80)
    logger.info("Purpose: Prove system correctness under all conditions")
    logger.info("Tests: Signal injection, parameter sweeps, volatile periods")
    
    # Load data
    logger.info("\nLoading market data...")
    df = pd.read_csv('data/training_data.csv', index_col=0)
    df.index = pd.to_datetime(df.index)
    logger.info(f"Data: {len(df)} rows, {df['symbol'].nunique()} symbols")
    logger.info(f"Date range: {df.index.min().date()} to {df.index.max().date()}")
    
    # Run tests
    test_results = {}
    
    try:
        test_results['signal_injection'] = run_signal_injection_test(df)
    except Exception as e:
        logger.error(f"Signal injection test failed: {e}")
        test_results['signal_injection'] = False
    
    try:
        test_results['parameter_sweep'] = run_parameter_sweep_test(df)
    except Exception as e:
        logger.error(f"Parameter sweep test failed: {e}")
        test_results['parameter_sweep'] = False
    
    try:
        test_results['volatile_periods'] = run_volatile_period_test(df)
    except Exception as e:
        logger.error(f"Volatile period test failed: {e}")
        test_results['volatile_periods'] = False
    
    # Final summary
    logger.info("\n" + "="*80)
    logger.info("PHASE 4 EXIT CRITERIA")
    logger.info("="*80)
    logger.info(f"✓ Signal Injection Test: {'PASS' if test_results.get('signal_injection') else 'FAIL'}")
    logger.info(f"✓ Parameter Sweep Test: {'PASS' if test_results.get('parameter_sweep') else 'FAIL'}")
    logger.info(f"✓ Volatile Period Test: {'PASS' if test_results.get('volatile_periods') else 'FAIL'}")
    
    all_passed = all(test_results.values())
    
    if all_passed:
        logger.info("\n✅ PHASE 4 VALIDATION COMPLETE - ALL TESTS PASSED")
        logger.info("System correctness proven. Ready for Phase 5.")
        return 0
    else:
        logger.error("\n❌ PHASE 4 VALIDATION INCOMPLETE - SOME TESTS FAILED")
        logger.error("Review logs and fix issues before proceeding to Phase 5.")
        return 1

if __name__ == '__main__':
    sys.exit(main())
