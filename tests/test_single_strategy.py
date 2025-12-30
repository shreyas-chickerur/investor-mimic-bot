#!/usr/bin/env python3
"""
Test individual strategies to verify signal generation
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import logging
import pandas as pd
import pytest

# Import strategies
from strategies.strategy_rsi_mean_reversion import RSIMeanReversionStrategy
from strategies.strategy_ma_crossover import MACrossoverStrategy
from strategies.strategy_volatility_breakout import VolatilityBreakoutStrategy

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

@pytest.fixture(scope="module")
def market_data():
    """Load market data for testing"""
    data_file = Path(__file__).parent.parent / 'data' / 'training_data.csv'
    df = pd.read_csv(data_file, index_col=0)
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    return df

def test_rsi_strategy(market_data):
    """Test RSI Mean Reversion strategy"""
    strategy = RSIMeanReversionStrategy(1, 20000)
    recent_data = market_data.groupby("symbol", group_keys=False).tail(1000)
    signals = strategy.generate_signals(recent_data)
    assert signals is not None
    assert isinstance(signals, list)

def test_ma_crossover_strategy(market_data):
    """Test MA Crossover strategy"""
    strategy = MACrossoverStrategy(1, 20000)
    recent_data = market_data.groupby("symbol", group_keys=False).tail(1000)
    signals = strategy.generate_signals(recent_data)
    assert signals is not None
    assert isinstance(signals, list)

def test_volatility_breakout_strategy(market_data):
    """Test Volatility Breakout strategy"""
    strategy = VolatilityBreakoutStrategy(1, 20000)
    recent_data = market_data.groupby("symbol", group_keys=False).tail(1000)
    signals = strategy.generate_signals(recent_data)
    assert signals is not None
    assert isinstance(signals, list)

@pytest.mark.parametrize("strategy_name", ["RSI", "Trend", "Breakout"])
def test_strategy(strategy_name, market_data):
    """Run a single strategy and verify signal generation."""
    logger.info(f"\nTesting {strategy_name}...")
    if strategy_name == "RSI":
        strategy_class = RSIMeanReversionStrategy
    elif strategy_name == "Trend":
        strategy_class = MACrossoverStrategy
    elif strategy_name == "Breakout":
        strategy_class = VolatilityBreakoutStrategy
    else:
        raise ValueError("Invalid strategy name")
    
    strategy = strategy_class(1, 20000)
    recent_data = market_data.groupby("symbol", group_keys=False).tail(1000)
    signals = strategy.generate_signals(recent_data)
    count = len(signals) if signals else 0
    logger.info(f"Generated {count} signals")
    
    # Assert instead of return
    assert signals is not None
    assert isinstance(signals, list)

def main():
    """Test all strategies"""
    logger.info("="*60)
    logger.info("STRATEGY SIGNAL GENERATION TEST")
    logger.info("="*60)
    
    # Load data
    data_file = Path('data/training_data.csv')
    logger.info(f"\nLoading data from {data_file}...")
    
    df = pd.read_csv(data_file, index_col=0)
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    
    logger.info(f"Loaded {len(df)} rows, {df['symbol'].nunique()} symbols")
    
    # Test each strategy
    strategies = [
        (RSIMeanReversionStrategy, "RSI Mean Reversion"),
        (MACrossoverStrategy, "MA Crossover"),
        (VolatilityBreakoutStrategy, "Volatility Breakout"),
    ]
    
    results = {}
    for strategy_class, name in strategies:
        count = test_strategy(strategy_class, name, df)
        results[name] = count
    
    # Summary
    logger.info(f"\n{'='*60}")
    logger.info("SUMMARY")
    logger.info(f"{'='*60}")
    for name, count in results.items():
        status = "✅" if count > 0 else "❌"
        logger.info(f"{status} {name}: {count} signals")
    
    total = sum(results.values())
    logger.info(f"\nTotal signals: {total}")
    
    if total == 0:
        logger.error("\n⚠️  NO SIGNALS GENERATED - CRITICAL ISSUE")
        return 1
    else:
        logger.info(f"\n✅ Signal generation working ({total} total signals)")
        return 0

if __name__ == '__main__':
    sys.exit(main())
