#!/usr/bin/env python3
"""
Minimal backtest test to trace signal flow
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import pandas as pd
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

from portfolio_backtester import PortfolioBacktester
from regime_detector import RegimeDetector
from correlation_filter import CorrelationFilter
from portfolio_risk_manager import PortfolioRiskManager
from execution_costs import ExecutionCostModel

from strategies.strategy_rsi_mean_reversion import RSIMeanReversionStrategy

def main():
    """Test minimal backtest with single strategy"""
    logger.info("="*60)
    logger.info("MINIMAL BACKTEST TEST")
    logger.info("="*60)
    
    # Load recent data
    df = pd.read_csv('data/training_data.csv', index_col=0)
    df.index = pd.to_datetime(df.index)
    
    # Use last 100 days
    recent = df.tail(1000)
    logger.info(f"Data: {len(recent)} rows, {recent['symbol'].nunique()} symbols")
    logger.info(f"Date range: {recent.index.min()} to {recent.index.max()}")
    
    # Initialize single strategy
    strategy = RSIMeanReversionStrategy(1, 20000)
    
    # Test signal generation first
    logger.info("\n1. Testing signal generation...")
    signals = strategy.generate_signals(recent)
    logger.info(f"   Signals generated: {len(signals) if signals else 0}")
    if signals:
        for sig in signals[:3]:
            logger.info(f"   - {sig['action']} {sig['symbol']} @ ${sig['price']:.2f}, {sig['shares']} shares")
    
    # Initialize modules
    regime_detector = RegimeDetector()
    correlation_filter = CorrelationFilter()
    portfolio_risk = PortfolioRiskManager()
    cost_model = ExecutionCostModel()
    
    # Run minimal backtest
    logger.info("\n2. Running minimal backtest...")
    backtester = PortfolioBacktester(
        initial_capital=100000,
        start_date=recent.index.min().strftime('%Y-%m-%d'),
        end_date=recent.index.max().strftime('%Y-%m-%d')
    )
    
    results = backtester.run_backtest(
        market_data=recent,
        strategies=[strategy],
        regime_detector=regime_detector,
        correlation_filter=correlation_filter,
        portfolio_risk=portfolio_risk,
        cost_model=cost_model
    )
    
    logger.info("\n3. Results:")
    logger.info(f"   Total trades: {results.get('total_trades', 0)}")
    logger.info(f"   Final value: ${results.get('final_value', 0):,.2f}")
    logger.info(f"   Return: {results.get('total_return', 0):.2f}%")
    
    if results.get('total_trades', 0) == 0:
        logger.error("\n❌ STILL NO TRADES - Need deeper investigation")
        return 1
    else:
        logger.info("\n✅ Trades executed successfully!")
        return 0

if __name__ == '__main__':
    sys.exit(main())
