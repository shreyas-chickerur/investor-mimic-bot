#!/usr/bin/env python3
"""
Run Strategies Daily
Execute all 5 strategies and track performance
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from strategy_runner import StrategyRunner
from datetime import datetime

print("=" * 80)
print(f"DAILY STRATEGY EXECUTION - {datetime.now().strftime('%Y-%m-%d')}")
print("=" * 80)

# Initialize runner
runner = StrategyRunner()

# Load strategies
print("\n📊 Loading strategies...")
runner.initialize_strategies(total_capital=100000)

# Fetch market data
print("\n📈 Fetching market data...")
market_data = runner.fetch_market_data()
print(f"✅ Loaded data for {len(market_data)} symbols")

# Run all strategies
print("\n🤖 Executing all strategies...")
signals = runner.run_all_strategies(market_data, execute_trades=True)

# Show summary
print("\n" + "=" * 80)
print("DAILY SUMMARY")
print("=" * 80)

rankings = runner.get_rankings()
print("\n🏆 Current Rankings:")
for i, strategy in enumerate(rankings, 1):
    medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}️⃣"
    print(f"{medal} {strategy['name']}: {strategy['return_pct']:+.2f}% "
          f"(${strategy['portfolio_value']:,.0f})")

print(f"\n📊 Total Signals Generated: {len(signals)}")
print(f"📅 Next Run: Tomorrow at same time")
print(f"📈 View Dashboard: python3 src/strategy_dashboard.py")

print("\n✅ Daily execution complete!")
