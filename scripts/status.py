#!/usr/bin/env python3
"""
Trading System Status Dashboard
One-stop command to see everything: positions, P&L, signals, strategy health.

Usage:
    python3 scripts/status.py            # Full dashboard
    python3 scripts/status.py --brief    # One-line summary per strategy
    python3 scripts/status.py --trades   # Recent trades only
"""
from __future__ import annotations

import sys
import argparse
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.database import TradingDatabase

RESET  = "\033[0m"
BOLD   = "\033[1m"
GREEN  = "\033[32m"
RED    = "\033[31m"
YELLOW = "\033[33m"
CYAN   = "\033[36m"
DIM    = "\033[2m"


def _c(text: str, color: str) -> str:
    return f"{color}{text}{RESET}"


def print_header(title: str) -> None:
    width = 80
    print("\n" + _c("=" * width, BOLD))
    print(_c(f"  {title}", BOLD + CYAN))
    print(_c("=" * width, BOLD))


def fmt_pct(v: float, *, bold_threshold: float = 0.0) -> str:
    sign = "+" if v >= 0 else ""
    color = GREEN if v > bold_threshold else (RED if v < 0 else YELLOW)
    return _c(f"{sign}{v:.2f}%", color)


def fmt_dollar(v: float) -> str:
    sign = "+" if v > 0 else ""
    color = GREEN if v > 0 else (RED if v < 0 else RESET)
    return _c(f"{sign}${v:,.2f}", color)


def section_portfolio(db: TradingDatabase) -> None:
    print_header("PORTFOLIO OVERVIEW")
    conn = sqlite3.connect(db.db_path)
    conn.row_factory = sqlite3.Row

    # Latest broker snapshot
    row = conn.execute(
        """
        SELECT portfolio_value, cash, buying_power, snapshot_date
        FROM broker_state
        WHERE snapshot_type = 'END'
        ORDER BY created_at DESC LIMIT 1
        """
    ).fetchone()

    if row:
        pv = row["portfolio_value"]
        cash = row["cash"]
        invested = pv - cash
        print(f"  {'Snapshot date':<22} {row['snapshot_date']}")
        print(f"  {'Portfolio value':<22} {_c(f'${pv:,.2f}', BOLD)}")
        print(f"  {'Cash':<22} ${cash:,.2f}")
        print(f"  {'Invested':<22} ${invested:,.2f}  ({invested/pv*100:.1f}%)")
        print(f"  {'Buying power':<22} ${row['buying_power']:,.2f}")
    else:
        print(_c("  No broker snapshots yet — run the trading system first.", YELLOW))

    # 30-day return from first/last END snapshots
    rows = conn.execute(
        """
        SELECT portfolio_value, snapshot_date
        FROM broker_state
        WHERE snapshot_type = 'END'
        ORDER BY created_at ASC
        """
    ).fetchall()
    if len(rows) >= 2:
        first_val = rows[0]["portfolio_value"]
        last_val  = rows[-1]["portfolio_value"]
        first_date = rows[0]["snapshot_date"]
        last_date  = rows[-1]["snapshot_date"]
        total_ret  = (last_val - first_val) / first_val * 100
        print(f"\n  {'Total return since start':<22} {fmt_pct(total_ret)} "
              f"{_c(f'({first_date} → {last_date})', DIM)}")

    conn.close()


def section_positions(db: TradingDatabase) -> None:
    print_header("OPEN POSITIONS")
    conn = sqlite3.connect(db.db_path)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """
        SELECT p.symbol, p.shares, p.avg_price, p.current_price,
               p.unrealized_pnl, p.entry_date, s.name AS strategy
        FROM positions p
        JOIN strategies s ON s.id = p.strategy_id
        WHERE p.shares > 0
        ORDER BY s.name, p.symbol
        """
    ).fetchall()

    if not rows:
        print(_c("  No open positions.", YELLOW))
        conn.close()
        return

    print(f"  {'Symbol':<8} {'Strategy':<20} {'Shares':>6} {'AvgCost':>9} "
          f"{'Current':>9} {'UnrealPnL':>12} {'Entry'}")
    print("  " + "-" * 78)
    total_unrealized = 0.0
    for r in rows:
        cp   = r["current_price"] or r["avg_price"]
        upnl = r["unrealized_pnl"] or ((cp - r["avg_price"]) * r["shares"])
        total_unrealized += upnl
        pnl_str = fmt_dollar(upnl)
        entry = (r["entry_date"] or "")[:10]
        print(f"  {r['symbol']:<8} {r['strategy']:<20} {r['shares']:>6.0f} "
              f"${r['avg_price']:>8.2f} ${cp:>8.2f} {pnl_str:>20}  {entry}")

    print("  " + "-" * 78)
    print(f"  {'Total unrealized P&L':<46} {fmt_dollar(total_unrealized)}")
    conn.close()


def section_trades(db: TradingDatabase, days: int = 10) -> None:
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    print_header(f"RECENT TRADES (last {days} days)")
    conn = sqlite3.connect(db.db_path)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """
        SELECT t.action, t.symbol, t.shares, t.exec_price, t.pnl,
               t.executed_at, s.name AS strategy
        FROM trades t
        JOIN strategies s ON s.id = t.strategy_id
        WHERE t.executed_at >= ?
        ORDER BY t.executed_at DESC
        LIMIT 30
        """,
        (since,)
    ).fetchall()

    if not rows:
        print(_c(f"  No trades in the last {days} days.", YELLOW))
        conn.close()
        return

    print(f"  {'Date':<12} {'Act':<5} {'Symbol':<8} {'Strategy':<20} "
          f"{'Shares':>6} {'Price':>9} {'P&L':>12}")
    print("  " + "-" * 78)
    for r in rows:
        icon = _c("BUY ", GREEN) if r["action"] == "BUY" else _c("SELL", RED)
        pnl  = r["pnl"]
        pnl_str = fmt_dollar(pnl) if pnl is not None else _c("  —", DIM)
        date_str = (r["executed_at"] or "")[:10]
        print(f"  {date_str:<12} {icon} {r['symbol']:<8} {r['strategy']:<20} "
              f"{r['shares']:>6.0f} ${r['exec_price']:>8.2f} {pnl_str:>20}")

    conn.close()


def section_strategy_health(db: TradingDatabase) -> None:
    print_header("STRATEGY PERFORMANCE SNAPSHOT")
    strategies = db.get_all_strategies()
    if not strategies:
        print(_c("  No strategies initialized yet.", YELLOW))
        return

    conn = sqlite3.connect(db.db_path)
    conn.row_factory = sqlite3.Row
    print(f"  {'Strategy':<24} {'Alloc':>9} {'Positions':>10} "
          f"{'Trades':>7} {'Last Return':>13}")
    print("  " + "-" * 70)

    for strat in strategies:
        sid = strat["id"]
        perf = db.get_latest_performance(sid)
        trades = conn.execute(
            "SELECT COUNT(*) as n FROM trades WHERE strategy_id=?", (sid,)
        ).fetchone()["n"]
        positions = conn.execute(
            "SELECT COUNT(*) as n FROM positions WHERE strategy_id=? AND shares>0", (sid,)
        ).fetchone()["n"]

        return_str = fmt_pct(perf["total_return_pct"]) if perf else _c("no data", DIM)
        alloc = strat.get("capital_allocation", 0)
        print(f"  {strat['name']:<24} ${alloc:>8,.0f} {positions:>10}  "
              f"{trades:>6}  {return_str:>21}")

    conn.close()


def section_signals(db: TradingDatabase, days: int = 3) -> None:
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    print_header(f"SIGNALS — last {days} days")
    conn = sqlite3.connect(db.db_path)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """
        SELECT s.symbol, s.signal_type, s.confidence, s.terminal_state,
               s.reasoning, s.asof_date, st.name AS strategy
        FROM signals s
        JOIN strategies st ON st.id = s.strategy_id
        WHERE s.asof_date >= ?
          AND st.name != 'BROKER_SYNC'
        ORDER BY s.generated_at DESC
        LIMIT 40
        """,
        (since,),
    ).fetchall()

    if not rows:
        print(_c(f"  No signals in the last {days} days.", YELLOW))
        conn.close()
        return

    print(f"  {'Date':<12} {'Strategy':<22} {'Symbol':<8} {'Type':<5} "
          f"{'Conf':>5} {'State':<12} Reasoning")
    print("  " + "-" * 100)
    for r in rows:
        state = r["terminal_state"] or "OPEN"
        state_color = GREEN if state == "EXECUTED" else (RED if state == "FILTERED" else YELLOW)
        reasoning = (r["reasoning"] or "")[:55]
        print(f"  {r['asof_date']:<12} {r['strategy']:<22} {r['symbol']:<8} "
              f"{r['signal_type']:<5} {r['confidence']:>4.0%} "
              f"{_c(state, state_color):<20}  {reasoning}")

    conn.close()


def section_funnel(db: TradingDatabase) -> None:
    print_header("SIGNAL FUNNEL (latest run)")
    conn = sqlite3.connect(db.db_path)
    conn.row_factory = sqlite3.Row

    latest_run = conn.execute(
        "SELECT run_id FROM signal_funnel ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    if not latest_run:
        print(_c("  No funnel data yet.", YELLOW))
        conn.close()
        return

    rows = conn.execute(
        """
        SELECT strategy_name, raw_signals_count, after_regime_count,
               after_correlation_count, after_risk_count, executed_count
        FROM signal_funnel
        WHERE run_id = ?
        ORDER BY strategy_name
        """,
        (latest_run["run_id"],),
    ).fetchall()

    print(f"  Run: {_c(latest_run['run_id'], DIM)}\n")
    print(f"  {'Strategy':<24} {'Raw':>5} {'Regime':>7} {'Corr':>6} {'Risk':>6} {'Exec':>6}")
    print("  " + "-" * 58)
    for r in rows:
        exec_color = GREEN if r["executed_count"] > 0 else YELLOW
        print(f"  {r['strategy_name']:<24} {r['raw_signals_count']:>5} "
              f"{r['after_regime_count']:>7} {r['after_correlation_count']:>6} "
              f"{r['after_risk_count']:>6} {_c(str(r['executed_count']), exec_color):>14}")

    conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Trading system status dashboard")
    parser.add_argument("--brief",  action="store_true", help="One-line summary only")
    parser.add_argument("--trades", action="store_true", help="Recent trades only")
    parser.add_argument("--days",   type=int, default=10, help="Lookback days for trades/signals")
    args = parser.parse_args()

    db = TradingDatabase()
    print(f"\n{_c('INVESTOR-MIMIC-BOT', BOLD + CYAN)}  |  "
          f"{_c(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), DIM)}")

    if args.trades:
        section_trades(db, days=args.days)
        return

    if args.brief:
        section_strategy_health(db)
        return

    section_portfolio(db)
    section_positions(db)
    section_strategy_health(db)
    section_signals(db, days=args.days)
    section_funnel(db)
    section_trades(db, days=args.days)
    print("\n")


if __name__ == "__main__":
    main()
