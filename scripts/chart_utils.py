#!/usr/bin/env python3
"""
Shared chart generation utilities.

Both generate_email_chart.py and generate_strategy_chart.py previously
contained near-identical implementations. This module is the single source
of truth for cumulative-P&L chart logic.
"""
from __future__ import annotations

import sqlite3
import io
import base64
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

_COLORS = ['#667eea', '#f56565', '#48bb78', '#ed8936', '#4299e1']


def build_cumulative_pnl_chart(
    db_path: str = 'trading.db',
    days: int = 7,
    figsize: tuple = (10, 4),
) -> str:
    """Generate a cumulative-P&L-by-strategy line chart.

    Args:
        db_path: Path to the SQLite trading database.
        days:    Number of calendar days to include on the x-axis.
        figsize: Matplotlib figure size as (width, height) inches.

    Returns:
        Base-64 encoded PNG string suitable for embedding in HTML.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    strategies = conn.execute('SELECT id, name FROM strategies ORDER BY id').fetchall()

    end_date = datetime.now()
    start_date = end_date - timedelta(days=days - 1)
    date_labels = [
        (start_date + timedelta(days=i)).strftime('%m/%d') for i in range(days)
    ]

    fig, ax = plt.subplots(figsize=figsize)
    fig.patch.set_facecolor('#f9fafb')
    ax.set_facecolor('#ffffff')

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
            date_str = (start_date + timedelta(days=i)).strftime('%Y-%m-%d')
            total += pnl_by_date.get(date_str, 0)
            cumulative.append(total)

        ax.plot(
            date_labels, cumulative,
            marker='o', linewidth=2.5,
            label=strategy['name'],
            color=_COLORS[idx % len(_COLORS)],
            markersize=6,
        )

    ax.set_xlabel('Date', fontsize=11, fontweight='600', color='#4b5563')
    ax.set_ylabel('Cumulative P&L ($)', fontsize=11, fontweight='600', color='#4b5563')
    ax.set_title(
        f'Strategy Performance — Last {days} Days',
        fontsize=14, fontweight='700', color='#1e3a5f', pad=15,
    )
    ax.legend(loc='upper left', frameon=True, fancybox=True, shadow=True, fontsize=9)
    ax.grid(True, alpha=0.2, linestyle='--')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.axhline(y=0, color='gray', linestyle='-', linewidth=0.5, alpha=0.5)
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100, bbox_inches='tight', facecolor='#f9fafb')
    buf.seek(0)
    encoded = base64.b64encode(buf.read()).decode()
    plt.close()
    conn.close()
    return encoded
