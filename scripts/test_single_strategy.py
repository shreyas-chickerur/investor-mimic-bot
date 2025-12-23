#!/usr/bin/env python3
"""
Test individual strategies to verify signal generation
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import pandas as pd
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import strategies
from strategies.strategy_rsi_mean_reversion import RSIMeanReversionStrategy
from strategies.strategy_ma_crossover import MACrossoverStrategy
from strategies.strategy_volatility_breakout import VolatilityBreakoutStrategy

def test_strategy(strategy_class, name, market_data):
    """Test a single strategy"""
    logger.info(f"\n{'='*60}")
    logger.info(f"Testing: {name}")
    logger.info(f"{'='*60}")
    
    try:
        strategy = strategy_class(1, 20000)
        
        # Test on recent data
        recent_data = market_data.tail(1000)
        logger.info(f"Data: {len(recent_data)} rows, {recent_data['symbol'].nunique()} symbols")
        logger.info(f"Date range: {recent_data.index.min()} to {recent_data.index.max()}")
        
        signals = strategy.generate_signals(recent_data)
        
        if signals and len(signals) > 0:
            logger.info(f"✅ Generated {len(signals)} signals")
            for i, sig in enumerate(signals[:3]):
                logger.info(f"  Signal {i+1}: {sig['action']} {sig['symbol']} @ ${sig['price']:.2f}")
        else:
            logger.warning(f"❌ No signals generated")
        
        return len(signals) if signals else 0
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 0

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
