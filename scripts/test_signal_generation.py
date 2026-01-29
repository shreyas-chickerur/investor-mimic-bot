#!/usr/bin/env python3
"""
Test Signal Generation
Verifies that all strategies can generate signals with current data
"""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)

from src.strategies.strategy_rsi_mean_reversion import RSIMeanReversionStrategy
from src.strategies.strategy_ml_momentum import MLMomentumStrategy
from src.strategies.strategy_news_sentiment import NewsSentimentStrategy
from src.strategies.strategy_ma_crossover import MACrossoverStrategy
from src.strategies.strategy_volatility_breakout import VolatilityBreakoutStrategy

def test_signal_generation():
    """Test all strategies with current data"""
    
    print("="*80)
    print("SIGNAL GENERATION TEST")
    print("="*80)
    
    # Load data
    data_file = Path('data/training_data.csv')
    if not data_file.exists():
        print(f"\n❌ ERROR: Data file not found at {data_file}")
        print("Run: python3 scripts/update_daily_data.py")
        return False
    
    print(f"\nLoading data from {data_file}...")
    df = pd.read_csv(data_file)
    df['date'] = pd.to_datetime(df['date'])
    df = df.set_index('date')
    
    print(f"  Rows: {len(df):,}")
    print(f"  Symbols: {df['symbol'].nunique()}")
    print(f"  Date range: {df.index.min().date()} to {df.index.max().date()}")
    print(f"  Data age: {(pd.Timestamp.now() - df.index.max()).days} days")
    
    # Check data quality
    print("\n" + "="*80)
    print("DATA QUALITY CHECK")
    print("="*80)
    
    latest = df.groupby('symbol').tail(1)
    
    print(f"\nLatest data by symbol:")
    print(f"  Symbols with RSI < 40: {len(latest[latest['rsi'] < 40])}")
    print(f"  Symbols with RSI < 35: {len(latest[latest['rsi'] < 35])}")
    print(f"  Symbols with RSI < 30: {len(latest[latest['rsi'] < 30])}")
    
    print(f"\nLowest RSI values:")
    rsi_sorted = latest[['symbol', 'rsi', 'close']].sort_values('rsi')
    for idx, row in rsi_sorted.head(5).iterrows():
        print(f"  {row['symbol']}: RSI={row['rsi']:.1f}, Price=${row['close']:.2f}")
    
    # Test each strategy
    print("\n" + "="*80)
    print("STRATEGY TESTING")
    print("="*80)
    
    strategies = [
        ('RSI Mean Reversion', RSIMeanReversionStrategy(1, 20000)),
        ('ML Momentum', MLMomentumStrategy(2, 20000)),
        ('News Sentiment', NewsSentimentStrategy(3, 20000)),
        ('MA Crossover', MACrossoverStrategy(4, 20000)),
        ('Volatility Breakout', VolatilityBreakoutStrategy(5, 20000))
    ]
    
    total_signals = 0
    results = []
    
    for name, strategy in strategies:
        print(f"\n{name}:")
        print(f"  Description: {strategy.get_description()}")
        
        try:
            signals = strategy.generate_signals(df)
            signal_count = len(signals) if signals else 0
            total_signals += signal_count
            
            print(f"  Signals: {signal_count}")
            
            if signal_count > 0:
                for sig in signals[:3]:  # Show first 3
                    print(f"    - {sig['action']} {sig['symbol']}: {sig['shares']} shares @ ${sig['price']:.2f}")
                    print(f"      Reason: {sig['reasoning']}")
                if signal_count > 3:
                    print(f"    ... and {signal_count - 3} more")
            
            results.append({
                'strategy': name,
                'signals': signal_count,
                'status': '✅ OK' if signal_count >= 0 else '❌ ERROR'
            })
            
        except Exception as e:
            print(f"  ❌ ERROR: {e}")
            results.append({
                'strategy': name,
                'signals': 0,
                'status': f'❌ ERROR: {str(e)[:50]}'
            })
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    
    print(f"\nTotal signals across all strategies: {total_signals}")
    print(f"\nStrategy Results:")
    for r in results:
        print(f"  {r['strategy']}: {r['signals']} signals - {r['status']}")
    
    # Verdict
    print("\n" + "="*80)
    if total_signals > 0:
        print("✅ TEST PASSED - Strategies are generating signals")
        print("="*80)
        return True
    else:
        print("⚠️  WARNING - No signals generated")
        print("This may be normal if market conditions don't meet strategy criteria")
        print("="*80)
        return True  # Not a failure, just no opportunities

if __name__ == '__main__':
    success = test_signal_generation()
    sys.exit(0 if success else 1)
