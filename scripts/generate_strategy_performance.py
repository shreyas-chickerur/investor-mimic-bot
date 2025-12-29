#!/usr/bin/env python3
"""
Generate Strategy Performance Report

Analyzes strategy performance from database and generates:
- Per-strategy metrics (P&L, win rate, Sharpe, etc.)
- Strategy comparison tables
- Performance rankings
- Risk metrics by strategy
"""
import sys
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
import json

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / 'src'))

def calculate_sharpe_ratio(returns, risk_free_rate=0.0):
    """Calculate Sharpe ratio from returns list"""
    if not returns or len(returns) < 2:
        return 0.0
    
    import statistics
    avg_return = statistics.mean(returns)
    std_return = statistics.stdev(returns)
    
    if std_return == 0:
        return 0.0
    
    return (avg_return - risk_free_rate) / std_return

def get_strategy_performance(db_path='trading.db', days=30):
    """Get comprehensive strategy performance metrics"""
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    # Get all strategies
    strategies = conn.execute('SELECT id, name FROM strategies ORDER BY id').fetchall()
    
    performance = {}
    
    for strategy in strategies:
        strategy_id = strategy['id']
        strategy_name = strategy['name']
        
        # Get trades for this strategy
        query = '''
            SELECT 
                DATE(executed_at) as date,
                pnl
            FROM trades
            WHERE strategy_id = ?
            AND executed_at >= DATE('now', ?)
            AND pnl IS NOT NULL
            ORDER BY executed_at
        '''
        
        trades = conn.execute(query, (strategy_id, f'-{days} days')).fetchall()
        
        if not trades:
            performance[strategy_name] = {
                'total_trades': 0,
                'wins': 0,
                'losses': 0,
                'win_rate': 0.0,
                'total_pnl': 0.0,
                'avg_pnl': 0.0,
                'max_win': 0.0,
                'max_loss': 0.0,
                'sharpe_ratio': 0.0,
                'profit_factor': 0.0,
                'daily_returns': [],
                'cumulative_pnl': []
            }
            continue
        
        # Calculate metrics
        total_trades = len(trades)
        wins = sum(1 for t in trades if t['pnl'] > 0)
        losses = sum(1 for t in trades if t['pnl'] < 0)
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0.0
        
        pnls = [t['pnl'] for t in trades]
        total_pnl = sum(pnls)
        avg_pnl = total_pnl / total_trades if total_trades > 0 else 0.0
        max_win = max(pnls) if pnls else 0.0
        max_loss = min(pnls) if pnls else 0.0
        
        # Calculate profit factor
        gross_profit = sum(p for p in pnls if p > 0)
        gross_loss = abs(sum(p for p in pnls if p < 0))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 0.0
        
        # Group by date for daily returns
        daily_pnl = defaultdict(float)
        for trade in trades:
            daily_pnl[trade['date']] += trade['pnl']
        
        daily_returns = list(daily_pnl.values())
        sharpe_ratio = calculate_sharpe_ratio(daily_returns)
        
        # Calculate cumulative P&L
        cumulative = []
        total = 0
        for pnl in pnls:
            total += pnl
            cumulative.append(total)
        
        performance[strategy_name] = {
            'total_trades': total_trades,
            'wins': wins,
            'losses': losses,
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'avg_pnl': avg_pnl,
            'max_win': max_win,
            'max_loss': max_loss,
            'sharpe_ratio': sharpe_ratio,
            'profit_factor': profit_factor,
            'daily_returns': daily_returns,
            'cumulative_pnl': cumulative
        }
    
    conn.close()
    return performance

def rank_strategies(performance):
    """Rank strategies by multiple metrics"""
    
    strategies = list(performance.keys())
    
    # Filter out strategies with no trades
    active_strategies = [s for s in strategies if performance[s]['total_trades'] > 0]
    
    if not active_strategies:
        return {
            'by_pnl': [],
            'by_win_rate': [],
            'by_sharpe': [],
            'by_profit_factor': []
        }
    
    rankings = {
        'by_pnl': sorted(active_strategies, key=lambda s: performance[s]['total_pnl'], reverse=True),
        'by_win_rate': sorted(active_strategies, key=lambda s: performance[s]['win_rate'], reverse=True),
        'by_sharpe': sorted(active_strategies, key=lambda s: performance[s]['sharpe_ratio'], reverse=True),
        'by_profit_factor': sorted(active_strategies, key=lambda s: performance[s]['profit_factor'], reverse=True)
    }
    
    return rankings

def generate_strategy_summary(performance, rankings, days=30):
    """Generate human-readable strategy summary"""
    
    summary = f"STRATEGY PERFORMANCE SUMMARY - Last {days} Days\n"
    summary += "=" * 80 + "\n\n"
    
    # Overall statistics
    total_trades = sum(p['total_trades'] for p in performance.values())
    total_pnl = sum(p['total_pnl'] for p in performance.values())
    
    summary += f"Total Trades: {total_trades}\n"
    summary += f"Total P&L: ${total_pnl:,.2f}\n\n"
    
    # Top performers
    summary += "TOP PERFORMERS BY P&L:\n"
    summary += "-" * 80 + "\n"
    for i, strategy in enumerate(rankings['by_pnl'][:3], 1):
        perf = performance[strategy]
        summary += f"{i}. {strategy}\n"
        summary += f"   P&L: ${perf['total_pnl']:,.2f} | "
        summary += f"Win Rate: {perf['win_rate']:.1f}% | "
        summary += f"Trades: {perf['total_trades']} | "
        summary += f"Sharpe: {perf['sharpe_ratio']:.2f}\n"
    
    summary += "\n"
    
    # Detailed breakdown
    summary += "DETAILED STRATEGY BREAKDOWN:\n"
    summary += "-" * 80 + "\n"
    
    for strategy in sorted(performance.keys()):
        perf = performance[strategy]
        
        if perf['total_trades'] == 0:
            summary += f"\n{strategy}: No trades\n"
            continue
        
        summary += f"\n{strategy}:\n"
        summary += f"  Trades: {perf['total_trades']} ({perf['wins']}W / {perf['losses']}L)\n"
        summary += f"  Win Rate: {perf['win_rate']:.1f}%\n"
        summary += f"  Total P&L: ${perf['total_pnl']:,.2f}\n"
        summary += f"  Avg P&L: ${perf['avg_pnl']:.2f}\n"
        summary += f"  Max Win: ${perf['max_win']:.2f}\n"
        summary += f"  Max Loss: ${perf['max_loss']:.2f}\n"
        summary += f"  Sharpe Ratio: {perf['sharpe_ratio']:.2f}\n"
        summary += f"  Profit Factor: {perf['profit_factor']:.2f}\n"
    
    return summary

def save_performance_data(performance, rankings, output_path='/tmp/strategy_performance.json'):
    """Save performance data as JSON for email generation"""
    
    data = {
        'performance': performance,
        'rankings': rankings,
        'generated_at': datetime.now().isoformat()
    }
    
    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2)
    
    return output_path

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate strategy performance report')
    parser.add_argument('--days', type=int, default=30, help='Number of days to analyze')
    parser.add_argument('--db', default='trading.db', help='Database path')
    args = parser.parse_args()
    
    print(f"Analyzing strategy performance (last {args.days} days)...")
    
    # Get performance data
    performance = get_strategy_performance(args.db, args.days)
    rankings = rank_strategies(performance)
    
    # Generate summary
    summary = generate_strategy_summary(performance, rankings, args.days)
    print(summary)
    
    # Save data for email generation
    output_path = save_performance_data(performance, rankings)
    print(f"\n✅ Performance data saved to: {output_path}")
    
    sys.exit(0)
