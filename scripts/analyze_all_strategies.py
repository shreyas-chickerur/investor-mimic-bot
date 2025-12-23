#!/usr/bin/env python3
"""
Analyze All 5 Strategies for Current Signals
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import pandas as pd
from datetime import datetime, timedelta

# Load existing data
print("=" * 80)
print("MULTI-STRATEGY SIGNAL ANALYSIS")
print("=" * 80)

print("\n📊 Loading market data...")
df = pd.read_csv('data/training_data.csv', index_col=0)
df.index = pd.to_datetime(df.index)

# Get recent data
latest_date = df.index.max()
cutoff_date = latest_date - timedelta(days=100)
market_data = df[df.index >= cutoff_date].copy()

print(f"✅ Loaded {len(market_data)} rows")
print(f"   Date range: {market_data.index.min().date()} to {market_data.index.max().date()}")
print(f"   Symbols: {market_data['symbol'].nunique()}")

# Initialize strategies
from strategies.strategy_rsi_mean_reversion import RSIMeanReversionStrategy
from strategies.strategy_ml_momentum import MLMomentumStrategy
from strategies.strategy_news_sentiment import NewsSentimentStrategy
from strategies.strategy_ma_crossover import MACrossoverStrategy
from strategies.strategy_volatility_breakout import VolatilityBreakoutStrategy

capital_per_strategy = 20000

strategies = [
    ("RSI Mean Reversion", RSIMeanReversionStrategy(capital_per_strategy)),
    ("ML Momentum", MLMomentumStrategy(capital_per_strategy)),
    ("News Sentiment", NewsSentimentStrategy(capital_per_strategy)),
    ("MA Crossover", MACrossoverStrategy(capital_per_strategy)),
    ("Volatility Breakout", VolatilityBreakoutStrategy(capital_per_strategy))
]

# Run each strategy
all_results = []

for name, strategy in strategies:
    print(f"\n{'=' * 80}")
    print(f"📈 {name}")
    print(f"{'=' * 80}")
    
    try:
        signals = strategy.generate_signals(market_data)
        
        if signals is not None and len(signals) > 0:
            print(f"✅ Found {len(signals)} signals:")
            # Show key columns
            cols_to_show = ['symbol', 'signal']
            if 'price' in signals.columns:
                cols_to_show.append('price')
            if 'rsi' in signals.columns:
                cols_to_show.append('rsi')
            if 'confidence' in signals.columns:
                cols_to_show.append('confidence')
            
            print(signals[cols_to_show].head(10).to_string(index=False))
            
            all_results.append({
                'strategy': name,
                'signals': len(signals),
                'status': 'Success',
                'top_signals': signals.head(5)
            })
        else:
            print("❌ No signals generated")
            all_results.append({
                'strategy': name,
                'signals': 0,
                'status': 'No signals',
                'top_signals': None
            })
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        all_results.append({
            'strategy': name,
            'signals': 0,
            'status': f'Error: {str(e)[:50]}',
            'top_signals': None
        })

# Generate summary dashboard
print(f"\n{'=' * 80}")
print("📊 STRATEGY DASHBOARD SUMMARY")
print(f"{'=' * 80}")

print(f"\n{'Strategy':<25} {'Signals':<10} {'Status':<30}")
print("-" * 80)

total_signals = 0
strategies_with_signals = 0

for result in all_results:
    print(f"{result['strategy']:<25} {result['signals']:<10} {result['status']:<30}")
    total_signals += result['signals']
    if result['signals'] > 0:
        strategies_with_signals += 1

print("-" * 80)
print(f"{'TOTAL':<25} {total_signals:<10} {strategies_with_signals} strategies active")

# Show actionable signals
if total_signals > 0:
    print(f"\n{'=' * 80}")
    print("🎯 ACTIONABLE SIGNALS (Top 3 per strategy)")
    print(f"{'=' * 80}")
    
    for result in all_results:
        if result['top_signals'] is not None and len(result['top_signals']) > 0:
            print(f"\n📌 {result['strategy']}:")
            signals = result['top_signals']
            for idx, row in signals.head(3).iterrows():
                symbol = row.get('symbol', 'N/A')
                signal_type = row.get('signal', 'BUY')
                price = row.get('price', row.get('close', 0))
                print(f"   • {symbol}: {signal_type} @ ${price:.2f}")
else:
    print(f"\n{'=' * 80}")
    print("⚠️  NO SIGNALS FROM ANY STRATEGY")
    print(f"{'=' * 80}")
    print("\nThis is normal behavior:")
    print("  • Strategies are selective and wait for optimal conditions")
    print("  • Current market may not meet entry criteria")
    print("  • System will continue monitoring daily")

print(f"\n{'=' * 80}")
print(f"Analysis completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"{'=' * 80}")
