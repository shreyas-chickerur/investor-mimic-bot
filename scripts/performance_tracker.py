#!/usr/bin/env python3
"""
Live Performance Tracker
Computes CAGR, Sharpe, Sortino, win rate, max drawdown, profit factor
from the live trades table and broker_state daily snapshots.

Usage:
    python3 scripts/performance_tracker.py [--db trading.db] [--json]
"""
from __future__ import annotations

import argparse
import json
import math
import sqlite3
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _q(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> List[dict]:
    """Run a query on an already-open connection."""
    rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Core metric calculations
# ---------------------------------------------------------------------------

def _sharpe(daily_rets: List[float], risk_free_daily: float = 0.0) -> Optional[float]:
    if len(daily_rets) < 10:
        return None
    n = len(daily_rets)
    mean = sum(daily_rets) / n
    variance = sum((r - mean) ** 2 for r in daily_rets) / (n - 1)
    std = math.sqrt(variance) if variance > 0 else 0
    if std == 0:
        return None
    return round((mean - risk_free_daily) / std * math.sqrt(252), 3)


def _sortino(daily_rets: List[float], risk_free_daily: float = 0.0) -> Optional[float]:
    if len(daily_rets) < 10:
        return None
    mean = sum(daily_rets) / len(daily_rets)
    downside = [r for r in daily_rets if r < risk_free_daily]
    if not downside:
        return None
    down_var = sum((r - risk_free_daily) ** 2 for r in downside) / len(downside)
    down_std = math.sqrt(down_var)
    if down_std == 0:
        return None
    return round((mean - risk_free_daily) / down_std * math.sqrt(252), 3)


def _max_drawdown(equity_curve: List[float]) -> Tuple[float, int]:
    """Returns (max_drawdown_pct, drawdown_duration_days)."""
    if len(equity_curve) < 2:
        return 0.0, 0
    peak = equity_curve[0]
    max_dd = 0.0
    dd_start = 0
    max_dd_duration = 0
    current_dd_start = 0
    for i, val in enumerate(equity_curve):
        if val > peak:
            peak = val
            current_dd_start = i
        dd = (peak - val) / peak if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd
            dd_start = current_dd_start
            max_dd_duration = i - dd_start
    return round(max_dd, 4), max_dd_duration


def _cagr(start_val: float, end_val: float, trading_days: int) -> Optional[float]:
    if start_val <= 0 or end_val <= 0 or trading_days < 5:
        return None
    years = trading_days / 252
    return round((end_val / start_val) ** (1.0 / years) - 1, 4)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_trades(conn: sqlite3.Connection) -> List[dict]:
    return _q(conn, """
        SELECT t.*, s.name strategy_name
        FROM trades t
        LEFT JOIN strategies s ON t.strategy_id = s.id
        WHERE s.name != 'BROKER_SYNC' OR s.name IS NULL
        ORDER BY t.executed_at
    """)


def load_portfolio_snapshots(conn: sqlite3.Connection) -> List[dict]:
    """Load daily START snapshots for portfolio equity curve."""
    return _q(conn, """
        SELECT snapshot_date, portfolio_value, cash
        FROM broker_state
        WHERE snapshot_type = 'START'
        ORDER BY snapshot_date
    """)


# ---------------------------------------------------------------------------
# Portfolio-level metrics
# ---------------------------------------------------------------------------

def compute_portfolio_metrics(db_path: str) -> Dict:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        snapshots = load_portfolio_snapshots(conn)
        trades = load_trades(conn)
    finally:
        conn.close()

    result: Dict = {
        'computed_at': datetime.now().isoformat(),
        'data_since': None,
        'trading_days': 0,
        'total_trades': len([t for t in trades if t.get('pnl') is not None]),
        'wins': 0,
        'losses': 0,
        'win_rate': None,
        'total_pnl': 0.0,
        'avg_win': None,
        'avg_loss': None,
        'profit_factor': None,
        'cagr': None,
        'sharpe': None,
        'sortino': None,
        'max_drawdown': None,
        'max_drawdown_days': None,
        'portfolio_start': None,
        'portfolio_current': None,
        'total_return_pct': None,
        'strategy_breakdown': {},
    }

    # --- Trade-level metrics ---
    closed = [t for t in trades if t.get('pnl') is not None]
    if closed:
        wins = [t['pnl'] for t in closed if t['pnl'] > 0]
        losses = [t['pnl'] for t in closed if t['pnl'] <= 0]
        result['wins'] = len(wins)
        result['losses'] = len(losses)
        result['win_rate'] = round(len(wins) / len(closed), 4) if closed else None
        result['total_pnl'] = round(sum(t['pnl'] for t in closed), 2)
        result['avg_win'] = round(sum(wins) / len(wins), 2) if wins else None
        result['avg_loss'] = round(sum(losses) / len(losses), 2) if losses else None
        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))
        result['profit_factor'] = round(gross_profit / gross_loss, 3) if gross_loss > 0 else None

    # --- Portfolio equity curve metrics ---
    if len(snapshots) >= 2:
        values = [s['portfolio_value'] for s in snapshots if s['portfolio_value']]
        if len(values) >= 2:
            result['portfolio_start'] = round(values[0], 2)
            result['portfolio_current'] = round(values[-1], 2)
            result['data_since'] = snapshots[0]['snapshot_date']
            result['trading_days'] = len(values)
            result['total_return_pct'] = round(
                (values[-1] - values[0]) / values[0] * 100, 3
            ) if values[0] > 0 else None
            result['cagr'] = _cagr(values[0], values[-1], len(values))

            # Daily returns for Sharpe/Sortino
            daily_rets = [
                (values[i] - values[i - 1]) / values[i - 1]
                for i in range(1, len(values))
                if values[i - 1] > 0
            ]
            result['sharpe'] = _sharpe(daily_rets)
            result['sortino'] = _sortino(daily_rets)
            dd, dd_days = _max_drawdown(values)
            result['max_drawdown'] = round(dd * 100, 2)
            result['max_drawdown_days'] = dd_days

    # --- Per-strategy breakdown ---
    by_strat: Dict[str, Dict] = {}
    for t in closed:
        sname = t.get('strategy_name') or 'Unknown'
        if sname not in by_strat:
            by_strat[sname] = {'trades': 0, 'wins': 0, 'pnl': 0.0}
        by_strat[sname]['trades'] += 1
        by_strat[sname]['pnl'] = round(by_strat[sname]['pnl'] + t['pnl'], 2)
        if t['pnl'] > 0:
            by_strat[sname]['wins'] += 1
    for sname, d in by_strat.items():
        d['win_rate'] = round(d['wins'] / d['trades'], 3) if d['trades'] > 0 else None
    result['strategy_breakdown'] = by_strat

    return result


# ---------------------------------------------------------------------------
# Pretty-print report
# ---------------------------------------------------------------------------

def print_report(metrics: Dict) -> None:
    def _pct(v, decimals=1):
        return f"{v:.{decimals}f}%" if v is not None else "N/A"

    def _val(v, decimals=2):
        return f"${v:,.{decimals}f}" if v is not None else "N/A"

    def _f(v, decimals=3):
        return f"{v:.{decimals}f}" if v is not None else "N/A"

    since = metrics.get('data_since') or 'N/A'
    days = metrics.get('trading_days') or 0
    print(f"\n{'='*54}")
    print(f"  LIVE PERFORMANCE REPORT  (since {since}, {days}d)")
    print(f"{'='*54}")
    print(f"  Portfolio start : {_val(metrics.get('portfolio_start'))}")
    print(f"  Portfolio now   : {_val(metrics.get('portfolio_current'))}")
    print(f"  Total return    : {_pct(metrics.get('total_return_pct'))}")
    print(f"  CAGR            : {_pct((metrics.get('cagr') or 0) * 100, 2)}")
    print(f"  Sharpe (ann.)   : {_f(metrics.get('sharpe'))}")
    print(f"  Sortino (ann.)  : {_f(metrics.get('sortino'))}")
    print(f"  Max drawdown    : {_pct(metrics.get('max_drawdown'))} "
          f"({metrics.get('max_drawdown_days') or 0}d)")
    print(f"\n  Trades total    : {metrics.get('total_trades')}")
    print(f"  Win rate        : {_pct((metrics.get('win_rate') or 0) * 100)}")
    print(f"  Avg win         : {_val(metrics.get('avg_win'))}")
    print(f"  Avg loss        : {_val(metrics.get('avg_loss'))}")
    print(f"  Profit factor   : {_f(metrics.get('profit_factor'))}")
    print(f"  Total P&L       : {_val(metrics.get('total_pnl'))}")

    breakdown = metrics.get('strategy_breakdown') or {}
    if breakdown:
        print(f"\n  Per-strategy:")
        for sname, d in sorted(breakdown.items(), key=lambda x: -x[1]['pnl']):
            wr = f"{d['win_rate']*100:.0f}%" if d['win_rate'] is not None else "N/A"
            print(f"    {sname:<26} {d['trades']:>3} trades  "
                  f"WR={wr}  P&L={_val(d['pnl'])}")
    print(f"{'='*54}\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Live trading performance tracker")
    parser.add_argument('--db', default='trading.db', help='Path to trading.db')
    parser.add_argument('--json', action='store_true', help='Output raw JSON')
    args = parser.parse_args()

    db_path = str(Path(args.db).resolve())
    if not Path(db_path).exists():
        print(f"Database not found: {db_path}")
        return

    metrics = compute_portfolio_metrics(db_path)

    if args.json:
        print(json.dumps(metrics, indent=2))
    else:
        print_report(metrics)


if __name__ == '__main__':
    main()
