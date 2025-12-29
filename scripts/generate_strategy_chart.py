#!/usr/bin/env python3
"""
Generate Strategy Performance Chart

Creates visual charts for strategy performance to embed in emails
"""
import sys
import sqlite3
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from pathlib import Path
import io
import base64

def generate_strategy_chart(db_path='trading.db', days=7):
    """Generate strategy performance chart with cumulative P&L"""
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    # Get all strategies
    strategies = conn.execute('SELECT id, name FROM strategies ORDER BY id').fetchall()
    
    # Get date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days-1)
    
    # Create figure with 2 subplots
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
    fig.patch.set_facecolor('#f9fafb')
    
    colors = ['#4A90E2', '#FF6B35', '#48bb78', '#ed8936', '#9f7aea']
    
    # Generate date labels
    date_labels = [(start_date + timedelta(days=i)).strftime('%m/%d') for i in range(days)]
    
    # Plot 1: Cumulative P&L by strategy
    ax1.set_facecolor('#ffffff')
    
    for idx, strategy in enumerate(strategies):
        # Get daily P&L for this strategy
        query = '''
            SELECT DATE(executed_at) as date, SUM(pnl) as daily_pnl
            FROM trades
            WHERE strategy_id = ? 
            AND pnl IS NOT NULL
            AND DATE(executed_at) >= DATE(?)
            GROUP BY DATE(executed_at)
            ORDER BY date
        '''
        
        trades = conn.execute(query, (strategy['id'], start_date.strftime('%Y-%m-%d'))).fetchall()
        
        # Build cumulative P&L array
        pnl_by_date = {t['date']: float(t['daily_pnl']) for t in trades}
        cumulative_pnl = []
        total = 0
        
        for i in range(days):
            date_str = (start_date + timedelta(days=i)).strftime('%Y-%m-%d')
            total += pnl_by_date.get(date_str, 0)
            cumulative_pnl.append(total)
        
        # Plot line
        color = colors[idx % len(colors)]
        ax1.plot(date_labels, cumulative_pnl, marker='o', linewidth=2.5, 
                label=strategy['name'], color=color, markersize=6)
    
    ax1.set_xlabel('Date', fontsize=11, fontweight='600', color='#4b5563')
    ax1.set_ylabel('Cumulative P&L ($)', fontsize=11, fontweight='600', color='#4b5563')
    ax1.set_title(f'Strategy Performance - Last {days} Days', fontsize=14, fontweight='700', 
                 color='#1e3a5f', pad=15)
    ax1.legend(loc='upper left', frameon=True, fancybox=True, shadow=True, fontsize=9)
    ax1.grid(True, alpha=0.2, linestyle='--')
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)
    ax1.axhline(y=0, color='gray', linestyle='-', linewidth=0.5, alpha=0.5)
    
    # Plot 2: Win Rate by Strategy (last 30 days)
    ax2.set_facecolor('#ffffff')
    
    query = '''
        SELECT 
            s.name,
            COUNT(*) as total_trades,
            SUM(CASE WHEN t.pnl > 0 THEN 1 ELSE 0 END) as wins
        FROM trades t
        JOIN strategies s ON t.strategy_id = s.id
        WHERE t.pnl IS NOT NULL
        AND DATE(t.executed_at) >= DATE('now', '-30 days')
        GROUP BY s.name
        HAVING total_trades > 0
        ORDER BY s.id
    '''
    
    results = conn.execute(query).fetchall()
    
    if results:
        strategy_names = [r['name'] for r in results]
        win_rates = [(r['wins'] / r['total_trades'] * 100) if r['total_trades'] > 0 else 0 for r in results]
        
        bars = ax2.barh(strategy_names, win_rates, color=colors[:len(strategy_names)])
        
        # Add value labels on bars
        for i, (bar, rate) in enumerate(zip(bars, win_rates)):
            ax2.text(rate + 1, i, f'{rate:.1f}%', va='center', fontsize=9, fontweight='600')
        
        ax2.set_xlabel('Win Rate (%)', fontsize=11, fontweight='600', color='#4b5563')
        ax2.set_title('Win Rate by Strategy (Last 30 Days)', fontsize=14, fontweight='700', 
                     color='#1e3a5f', pad=15)
        ax2.set_xlim(0, 100)
        ax2.grid(True, alpha=0.2, linestyle='--', axis='x')
        ax2.spines['top'].set_visible(False)
        ax2.spines['right'].set_visible(False)
    
    plt.tight_layout()
    
    # Save to bytes and encode as base64
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100, bbox_inches='tight', facecolor='#f9fafb')
    buf.seek(0)
    chart_data = base64.b64encode(buf.read()).decode()
    plt.close()
    
    conn.close()
    
    return chart_data

def save_chart_as_html_embed(chart_data, output_path='/tmp/strategy_chart.html'):
    """Save chart as HTML img tag for email embedding"""
    
    html = f'<img src="data:image/png;base64,{chart_data}" style="width: 100%; max-width: 800px; height: auto; border-radius: 8px; margin: 20px 0;" alt="Strategy Performance Chart">'
    
    with open(output_path, 'w') as f:
        f.write(html)
    
    return output_path

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate strategy performance chart')
    parser.add_argument('--days', type=int, default=7, help='Number of days to show')
    parser.add_argument('--db', default='trading.db', help='Database path')
    args = parser.parse_args()
    
    print(f"Generating strategy performance chart (last {args.days} days)...")
    
    chart = generate_strategy_chart(args.db, args.days)
    output_path = save_chart_as_html_embed(chart)
    
    print(f"✅ Chart generated: {output_path}")
    print(f"   Chart size: {len(chart)} bytes")
    
    sys.exit(0)
