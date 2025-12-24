#!/usr/bin/env python3
"""
Generate Performance Chart for Email
Creates a chart from actual database data for the daily email digest
"""
import sqlite3
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from pathlib import Path
import io
import base64

def generate_performance_chart(db_path='trading.db', days=7):
    """Generate performance chart from database data"""
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    # Get all strategies
    strategies = conn.execute('SELECT id, name FROM strategies ORDER BY id').fetchall()
    
    # Get date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days-1)
    
    # Create figure
    fig, ax = plt.subplots(figsize=(10, 4))
    fig.patch.set_facecolor('#f9fafb')
    ax.set_facecolor('#ffffff')
    
    colors = ['#667eea', '#f56565', '#48bb78', '#ed8936', '#4299e1']
    
    # Generate date labels
    date_labels = [(start_date + timedelta(days=i)).strftime('%m/%d') for i in range(days)]
    
    # Plot each strategy
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
        ax.plot(date_labels, cumulative_pnl, marker='o', linewidth=2.5, 
                label=strategy['name'], color=color, markersize=6)
    
    ax.set_xlabel('Date', fontsize=11, fontweight='600', color='#4b5563')
    ax.set_ylabel('Cumulative P&L ($)', fontsize=11, fontweight='600', color='#4b5563')
    ax.set_title(f'Strategy Performance - Last {days} Days', fontsize=14, fontweight='700', 
                 color='#1e3a5f', pad=15)
    ax.legend(loc='upper left', frameon=True, fancybox=True, shadow=True, fontsize=9)
    ax.grid(True, alpha=0.2, linestyle='--')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    plt.tight_layout()
    
    # Save to bytes and encode as base64
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100, bbox_inches='tight', facecolor='#f9fafb')
    buf.seek(0)
    chart_data = base64.b64encode(buf.read()).decode()
    plt.close()
    
    conn.close()
    
    return chart_data

if __name__ == '__main__':
    # Test chart generation
    chart = generate_performance_chart()
    print(f"Chart generated successfully ({len(chart)} bytes)")
