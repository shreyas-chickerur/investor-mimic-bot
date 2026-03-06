#!/usr/bin/env python3
"""
Generate Strategy Performance Chart

Creates a two-panel chart (cumulative P&L + win-rate) for strategy performance.
The P&L panel is built by the shared chart_utils.build_cumulative_pnl_chart;
the win-rate panel is unique to this script.
"""
from __future__ import annotations

import sys
import sqlite3
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from pathlib import Path
import io
import base64

sys.path.insert(0, str(Path(__file__).parent))
from chart_utils import build_cumulative_pnl_chart  # noqa: F401 – re-exported for callers

_WIN_COLORS = ['#4A90E2', '#FF6B35', '#48bb78', '#ed8936', '#9f7aea']


def generate_strategy_chart(db_path: str = 'trading.db', days: int = 7) -> str:
    """Generate strategy performance chart with cumulative P&L and win-rate panels.

    Args:
        db_path: Path to the SQLite trading database.
        days:    Number of calendar days to show in the P&L panel.

    Returns:
        Base-64 encoded PNG string.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    strategies = conn.execute('SELECT id, name FROM strategies ORDER BY id').fetchall()
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days - 1)
    date_labels = [
        (start_date + timedelta(days=i)).strftime('%m/%d') for i in range(days)
    ]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
    fig.patch.set_facecolor('#f9fafb')

    # --- Panel 1: Cumulative P&L (reuses chart_utils logic inline for the axes object) ---
    ax1.set_facecolor('#ffffff')
    for idx, strategy in enumerate(strategies):
        rows = conn.execute(
            '''
            SELECT DATE(executed_at) AS date, SUM(pnl) AS daily_pnl
            FROM trades
            WHERE strategy_id = ? AND pnl IS NOT NULL
              AND DATE(executed_at) >= DATE(?)
            GROUP BY DATE(executed_at)
            ORDER BY date
            ''',
            (strategy['id'], start_date.strftime('%Y-%m-%d')),
        ).fetchall()
        pnl_by_date = {r['date']: float(r['daily_pnl']) for r in rows}
        cumulative, total = [], 0
        for i in range(days):
            total += pnl_by_date.get((start_date + timedelta(days=i)).strftime('%Y-%m-%d'), 0)
            cumulative.append(total)
        ax1.plot(date_labels, cumulative, marker='o', linewidth=2.5,
                 label=strategy['name'], color=_WIN_COLORS[idx % len(_WIN_COLORS)], markersize=6)

    ax1.set_xlabel('Date', fontsize=11, fontweight='600', color='#4b5563')
    ax1.set_ylabel('Cumulative P&L ($)', fontsize=11, fontweight='600', color='#4b5563')
    ax1.set_title(f'Strategy Performance — Last {days} Days',
                  fontsize=14, fontweight='700', color='#1e3a5f', pad=15)
    ax1.legend(loc='upper left', frameon=True, fancybox=True, shadow=True, fontsize=9)
    ax1.grid(True, alpha=0.2, linestyle='--')
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)
    ax1.axhline(y=0, color='gray', linestyle='-', linewidth=0.5, alpha=0.5)

    # --- Panel 2: Win Rate by Strategy (last 30 days) ---
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
        
        bars = ax2.barh(strategy_names, win_rates, color=_WIN_COLORS[:len(strategy_names)])
        
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
