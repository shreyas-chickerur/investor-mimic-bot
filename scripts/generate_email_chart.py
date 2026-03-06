#!/usr/bin/env python3
"""
Generate Performance Chart for Email
Creates a chart from actual database data for the daily email digest.

Chart rendering is delegated to scripts/chart_utils.py — the single source
of truth for cumulative-P&L chart logic shared with generate_strategy_chart.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from chart_utils import build_cumulative_pnl_chart


def generate_performance_chart(db_path: str = 'trading.db', days: int = 7) -> str:
    """Generate performance chart from database data.

    Args:
        db_path: Path to the SQLite trading database.
        days:    Number of calendar days to include.

    Returns:
        Base-64 encoded PNG string.
    """
    return build_cumulative_pnl_chart(db_path=db_path, days=days, figsize=(10, 4))


if __name__ == '__main__':
    chart = generate_performance_chart()
    print(f"Chart generated successfully ({len(chart)} bytes)")
