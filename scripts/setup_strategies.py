#!/usr/bin/env python3
"""
Setup Strategies
Initialize the multi-strategy testing framework
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from strategy_database import StrategyDatabase
from strategy_runner import StrategyRunner

print("=" * 80)
print("MULTI-STRATEGY FRAMEWORK SETUP")
print("=" * 80)

print("\n📊 Setting up strategy performance database...")
db = StrategyDatabase()
print("✅ Database initialized")

print("\n🤖 Initializing 5 trading strategies...")
runner = StrategyRunner()
runner.initialize_strategies(total_capital=100000)

print("\n" + "=" * 80)
print("✅ SETUP COMPLETE")
print("=" * 80)

print("\n📋 What's Ready:")
print("   ✅ 5 strategies initialized")
print("   ✅ $20,000 allocated to each strategy")
print("   ✅ Performance tracking database ready")
print("   ✅ All systems operational")

print("\n🚀 Next Steps:")
print("   1. Run strategies: python3 scripts/run_strategies_daily.py")
print("   2. View dashboard: python3 src/strategy_dashboard.py")
print("   3. Check results after 1 month of testing")

print("\n💡 Strategies:")
strategies = db.get_all_strategies()
for s in strategies:
    print(f"   • {s['name']}: ${s['capital_allocation']:,.0f}")

print("\n✅ Ready to start testing tomorrow morning!")
