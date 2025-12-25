#!/usr/bin/env python3
"""
Multi-Strategy Analysis - Check all 5 strategies for signals
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

print("=" * 80)
print("MULTI-STRATEGY SIGNAL ANALYSIS")
print("=" * 80)

# Load data
df = pd.read_csv('data/training_data.csv', index_col=0)
df.index = pd.to_datetime(df.index)

# Get recent data
latest_date = df.index.max()
cutoff_date = latest_date - timedelta(days=100)
recent = df[df.index >= cutoff_date].copy()

print(f"\n📊 Data loaded: {len(recent)} rows from {recent.index.min().date()} to {recent.index.max().date()}")
print(f"   Symbols: {recent['symbol'].nunique()}")

# Get latest data for each symbol
latest = recent.groupby('symbol').tail(1)

# Calculate volatility threshold
def calculate_volatility(prices, period=20):
    returns = prices.pct_change()
    return returns.rolling(window=period).std()

stock_data = recent[['symbol', 'close']].copy()
stock_data['date'] = recent.index

volatility_data = []
for symbol, group in stock_data.groupby('symbol'):
    group = group.sort_values('date')
    group['volatility_20d'] = calculate_volatility(group['close'], 20)
    volatility_data.append(group[['date', 'volatility_20d']])

all_vol = pd.concat(volatility_data)
all_vol = all_vol.sort_values('date')
all_vol['vol_median_rolling'] = all_vol['volatility_20d'].expanding().median()
vol_median = all_vol['vol_median_rolling'].iloc[-1]
vol_threshold = vol_median * 1.25

# Strategy results
results = []

# STRATEGY 1: RSI Mean Reversion (RSI < 30 + Low Volatility)
print(f"\n{'=' * 80}")
print("📈 STRATEGY 1: RSI Mean Reversion")
print(f"{'=' * 80}")
print(f"Criteria: RSI < 30 AND Volatility < {vol_threshold:.6f}")

s1_signals = latest[(latest['rsi'] < 30) & (latest['volatility_20d'] < vol_threshold)]
print(f"Signals: {len(s1_signals)}")
if len(s1_signals) > 0:
    print(s1_signals[['symbol', 'close', 'rsi', 'volatility_20d']].to_string())
else:
    print("No signals - market not oversold with low volatility")
results.append(('RSI Mean Reversion', len(s1_signals), s1_signals))

# STRATEGY 2: MA Crossover (50 MA > 200 MA - Golden Cross)
print(f"\n{'=' * 80}")
print("📈 STRATEGY 2: MA Crossover (Golden Cross)")
print(f"{'=' * 80}")
print("Criteria: SMA_50 > SMA_200 (uptrend)")

s2_signals = latest[(latest['sma_50'] > latest['sma_200']) & (latest['close'] > latest['sma_50'])]
print(f"Signals: {len(s2_signals)}")
if len(s2_signals) > 0:
    print(s2_signals[['symbol', 'close', 'sma_50', 'sma_200']].head(10).to_string())
else:
    print("No signals - no golden cross patterns")
results.append(('MA Crossover', len(s2_signals), s2_signals.head(10) if len(s2_signals) > 0 else pd.DataFrame()))

# STRATEGY 3: Volatility Breakout (High volume + price above upper BB)
print(f"\n{'=' * 80}")
print("📈 STRATEGY 3: Volatility Breakout")
print(f"{'=' * 80}")
print("Criteria: Volume > 1.5x average AND volatility increasing")

s3_signals = latest[(latest['volume_ratio'] > 1.5) & (latest['volatility_20d'] > vol_median)]
print(f"Signals: {len(s3_signals)}")
if len(s3_signals) > 0:
    print(s3_signals[['symbol', 'close', 'volume_ratio', 'volatility_20d']].head(10).to_string())
else:
    print("No signals - no breakout patterns")
results.append(('Volatility Breakout', len(s3_signals), s3_signals.head(10) if len(s3_signals) > 0 else pd.DataFrame()))

# STRATEGY 4: Momentum (Strong recent returns)
print(f"\n{'=' * 80}")
print("📈 STRATEGY 4: Momentum")
print(f"{'=' * 80}")
print("Criteria: 20-day return > 5% AND price > SMA_20")

s4_signals = latest[(latest['returns_20d'] > 0.05) & (latest['close'] > latest['sma_20'])]
print(f"Signals: {len(s4_signals)}")
if len(s4_signals) > 0:
    print(s4_signals[['symbol', 'close', 'returns_20d', 'sma_20']].head(10).to_string())
else:
    print("No signals - no strong momentum")
results.append(('Momentum', len(s4_signals), s4_signals.head(10) if len(s4_signals) > 0 else pd.DataFrame()))

# STRATEGY 5: Value (Price below moving averages - potential reversal)
print(f"\n{'=' * 80}")
print("📈 STRATEGY 5: Value/Reversal")
print(f"{'=' * 80}")
print("Criteria: Price < SMA_50 AND RSI < 50 (oversold but not extreme)")

s5_signals = latest[(latest['close'] < latest['sma_50']) & (latest['rsi'] < 50) & (latest['rsi'] > 30)]
print(f"Signals: {len(s5_signals)}")
if len(s5_signals) > 0:
    print(s5_signals[['symbol', 'close', 'sma_50', 'rsi']].head(10).to_string())
else:
    print("No signals - no value opportunities")
results.append(('Value/Reversal', len(s5_signals), s5_signals.head(10) if len(s5_signals) > 0 else pd.DataFrame()))

# DASHBOARD SUMMARY
print(f"\n{'=' * 80}")
print("📊 MULTI-STRATEGY DASHBOARD")
print(f"{'=' * 80}")

print(f"\n{'Strategy':<25} {'Signals':<10} {'Status':<30}")
print("-" * 80)

total_signals = 0
for name, count, _ in results:
    status = "✅ Active" if count > 0 else "⏸️  Waiting"
    print(f"{name:<25} {count:<10} {status:<30}")
    total_signals += count

print("-" * 80)
print(f"{'TOTAL SIGNALS':<25} {total_signals:<10}")

# Show actionable signals
if total_signals > 0:
    print(f"\n{'=' * 80}")
    print("🎯 ACTIONABLE SIGNALS (Top 5 from each strategy)")
    print(f"{'=' * 80}")
    
    for name, count, signals in results:
        if count > 0 and len(signals) > 0:
            print(f"\n📌 {name} ({count} total):")
            for idx, row in signals.head(5).iterrows():
                print(f"   • {row['symbol']}: BUY @ ${row['close']:.2f}")
else:
    print(f"\n{'=' * 80}")
    print("⚠️  NO SIGNALS FROM ANY STRATEGY")
    print(f"{'=' * 80}")
    print("\nCurrent market conditions:")
    print("  • Most stocks not oversold (RSI > 30)")
    print("  • Volatility elevated in oversold stocks")
    print("  • Limited momentum opportunities")
    print("  • System will continue monitoring daily")

print(f"\n{'=' * 80}")
print(f"Analysis completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"{'=' * 80}")
