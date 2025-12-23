#!/usr/bin/env python3
"""
View Multi-Strategy Performance Dashboard
Shows individual performance for each of the 5 strategies
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from strategy_database import StrategyDatabase
from datetime import datetime
import sqlite3

def main():
    db = StrategyDatabase()
    
    print("=" * 100)
    print("MULTI-STRATEGY PERFORMANCE DASHBOARD")
    print("=" * 100)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    strategies = db.get_all_strategies()
    
    if not strategies:
        print("\n⚠️  No strategies found. Run multi_strategy_main.py first to initialize.")
        return
    
    # Overall summary
    print(f"\n{'Strategy':<25} {'Capital':<12} {'Return %':<10} {'Positions':<10} {'Trades':<10} {'Status':<10}")
    print("-" * 100)
    
    total_capital = 0
    total_return = 0
    total_trades = 0
    
    for strat in strategies:
        perf = db.get_latest_performance(strat['id'])
        trades = db.get_strategy_trades(strat['id'])
        
        capital = strat['capital_allocation']
        total_capital += capital
        
        if perf:
            return_pct = perf['total_return_pct']
            num_positions = perf['num_positions']
            total_return += (capital * return_pct / 100)
        else:
            return_pct = 0.0
            num_positions = 0
        
        num_trades = len(trades)
        total_trades += num_trades
        
        status = "✅ Active" if num_positions > 0 or num_trades > 0 else "⏸️  Idle"
        
        print(f"{strat['name']:<25} ${capital:<11,.0f} {return_pct:>+8.2f}% {num_positions:<10} {num_trades:<10} {status:<10}")
    
    print("-" * 100)
    
    if total_capital > 0:
        avg_return = (total_return / total_capital) * 100
        print(f"{'TOTAL/AVERAGE':<25} ${total_capital:<11,.0f} {avg_return:>+8.2f}% {'-':<10} {total_trades:<10}")
    
    # Detailed breakdown
    print(f"\n{'=' * 100}")
    print("DETAILED STRATEGY BREAKDOWN")
    print(f"{'=' * 100}")
    
    for strat in strategies:
        print(f"\n📊 {strat['name']}")
        print("-" * 100)
        print(f"Description: {strat['description']}")
        print(f"Capital Allocated: ${strat['capital_allocation']:,.2f}")
        
        # Performance
        perf = db.get_latest_performance(strat['id'])
        if perf:
            print(f"\n💰 Current Performance:")
            print(f"  Portfolio Value: ${perf['portfolio_value']:,.2f}")
            print(f"  Cash: ${perf['cash']:,.2f}")
            print(f"  Positions Value: ${perf['positions_value']:,.2f}")
            print(f"  Total Return: {perf['total_return_pct']:+.2f}%")
            print(f"  Active Positions: {perf['num_positions']}")
        else:
            print(f"\n💰 No performance data yet")
        
        # Recent trades
        trades = db.get_strategy_trades(strat['id'])
        if trades:
            print(f"\n📈 Recent Trades (Last 5):")
            for trade in trades[:5]:
                action_icon = "🟢" if trade['action'] == 'BUY' else "🔴"
                print(f"  {action_icon} {trade['action']} {trade['shares']:.0f} {trade['symbol']} @ ${trade['price']:.2f} = ${trade['value']:,.2f}")
                print(f"     Executed: {trade['executed_at']}")
        else:
            print(f"\n📈 No trades executed yet")
        
        # Signals
        conn = sqlite3.connect(db.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT symbol, signal, confidence, reasoning, generated_at 
            FROM strategy_signals 
            WHERE strategy_id = ? 
            ORDER BY generated_at DESC LIMIT 5
        ''', (strat['id'],))
        signals = cursor.fetchall()
        conn.close()
        
        if signals:
            print(f"\n🎯 Recent Signals (Last 5):")
            for sig in signals:
                print(f"  • {sig[0]}: {sig[1]} (Confidence: {sig[2]:.0%})")
                print(f"    Reason: {sig[3]}")
                print(f"    Generated: {sig[4]}")
        else:
            print(f"\n🎯 No signals generated yet")
    
    print(f"\n{'=' * 100}")
    print("END OF DASHBOARD")
    print(f"{'=' * 100}")

if __name__ == '__main__':
    main()
