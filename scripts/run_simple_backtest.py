#!/usr/bin/env python3
"""
Simple backtest runner - focuses on getting trades to execute
Temporarily simplified to debug the zero-trade issue
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import pandas as pd
import logging
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from portfolio_backtester import PortfolioBacktester
from regime_detector import RegimeDetector
from correlation_filter import CorrelationFilter
from portfolio_risk_manager import PortfolioRiskManager
from execution_costs import ExecutionCostModel

# Only use RSI strategy (we know it works)
from strategies.strategy_rsi_mean_reversion import RSIMeanReversionStrategy

def main():
    """Run simplified backtest"""
    logger.info("="*80)
    logger.info("SIMPLIFIED BACKTEST - DEBUGGING ZERO TRADES")
    logger.info("="*80)
    
    # Load data
    logger.info("\nLoading data...")
    df = pd.read_csv('data/training_data.csv', index_col=0)
    df.index = pd.to_datetime(df.index)
    
    # Use last 2 years of data
    end_date = df.index.max()
    start_date = end_date - timedelta(days=730)
    test_data = df[(df.index >= start_date) & (df.index <= end_date)]
    
    logger.info(f"Data: {len(test_data)} rows")
    logger.info(f"Date range: {test_data.index.min().date()} to {test_data.index.max().date()}")
    logger.info(f"Symbols: {test_data['symbol'].nunique()}")
    
    # Initialize single strategy
    logger.info("\nInitializing RSI strategy...")
    strategies = [RSIMeanReversionStrategy(1, 100000)]
    
    # Initialize modules
    regime_detector = RegimeDetector()
    correlation_filter = CorrelationFilter()
    portfolio_risk = PortfolioRiskManager()
    cost_model = ExecutionCostModel()
    
    # Run backtest
    logger.info("\nRunning backtest...")
    backtester = PortfolioBacktester(
        initial_capital=100000,
        start_date=start_date.strftime('%Y-%m-%d'),
        end_date=end_date.strftime('%Y-%m-%d')
    )
    
    results = backtester.run_backtest(
        market_data=test_data,
        strategies=strategies,
        regime_detector=regime_detector,
        correlation_filter=correlation_filter,
        portfolio_risk=portfolio_risk,
        cost_model=cost_model
    )
    
    # Print results
    logger.info("\n" + "="*80)
    logger.info("RESULTS")
    logger.info("="*80)
    logger.info(f"Initial Capital:  ${results.get('initial_capital', 0):,.2f}")
    logger.info(f"Final Value:      ${results.get('final_value', 0):,.2f}")
    logger.info(f"Total Return:     {results.get('total_return', 0):.2f}%")
    logger.info(f"Total Trades:     {results.get('total_trades', 0)}")
    logger.info(f"Sharpe Ratio:     {results.get('sharpe_ratio', 0):.2f}")
    logger.info(f"Max Drawdown:     {results.get('max_drawdown', 0):.2f}%")
    
    if results.get('total_trades', 0) > 0:
        logger.info("\n✅ SUCCESS - Trades executed!")
        return 0
    else:
        logger.error("\n❌ FAILURE - Still no trades")
        logger.error("\nDEBUG INFO:")
        logger.error("This means either:")
        logger.error("1. No RSI < 30 conditions occurred in the 2-year period")
        logger.error("2. RSI slope was never positive when RSI < 30")
        logger.error("3. Portfolio risk checks blocked all trades")
        logger.error("4. Data format issue in backtester")
        return 1

if __name__ == '__main__':
    sys.exit(main())
