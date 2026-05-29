#!/usr/bin/env python3
"""Strategy attribution report.

Outputs which strategies triggered which trades and positions, plus
per-strategy aggregate P&L. Useful for diagnosing cross-strategy
overlap (e.g. AMD held by both RSI Mean Reversion and ML Momentum)
and for evaluating which strategies are actually contributing returns.

Usage:
  python3 scripts/strategy_attribution.py            # text report to stdout
  python3 scripts/strategy_attribution.py --csv      # CSV to stdout
  python3 scripts/strategy_attribution.py --days 30  # last 30 days only
"""
from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "trading.db"


def fetch_trades(conn: sqlite3.Connection, days: int | None) -> list[dict]:
    where = "WHERE s.name != 'BROKER_SYNC'"
    if days:
        where += f" AND DATE(t.executed_at) >= DATE('now', '-{int(days)} days')"
    rows = conn.execute(
        f"""
        SELECT t.executed_at, t.symbol, t.action, t.shares, t.exec_price,
               t.notional, t.pnl, s.name AS strategy
        FROM trades t
        JOIN strategies s ON s.id = t.strategy_id
        {where}
        ORDER BY t.executed_at
        """
    ).fetchall()
    return [
        dict(
            zip(
                [
                    "executed_at",
                    "symbol",
                    "action",
                    "shares",
                    "exec_price",
                    "notional",
                    "pnl",
                    "strategy",
                ],
                r,
            )
        )
        for r in rows
    ]


def fetch_positions(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT s.name AS strategy, p.symbol, p.shares, p.avg_price,
               p.current_price, p.unrealized_pnl, p.entry_date
        FROM positions p
        JOIN strategies s ON s.id = p.strategy_id
        WHERE p.shares != 0 AND s.name != 'BROKER_SYNC'
        ORDER BY s.name, p.symbol
        """
    ).fetchall()
    return [
        dict(
            zip(
                [
                    "strategy",
                    "symbol",
                    "shares",
                    "avg_price",
                    "current_price",
                    "unrealized_pnl",
                    "entry_date",
                ],
                r,
            )
        )
        for r in rows
    ]


def detect_overlaps(positions: list[dict]) -> dict[str, list[str]]:
    by_symbol: dict[str, list[str]] = defaultdict(list)
    for p in positions:
        by_symbol[p["symbol"]].append(p["strategy"])
    return {sym: strats for sym, strats in by_symbol.items() if len(strats) > 1}


def text_report(trades: list[dict], positions: list[dict]) -> str:
    lines: list[str] = []
    lines.append("=" * 78)
    lines.append("STRATEGY ATTRIBUTION REPORT")
    lines.append("=" * 78)

    # Per-strategy aggregates
    agg: dict[str, dict[str, float]] = defaultdict(
        lambda: {"trades": 0, "buys": 0, "sells": 0, "realized_pnl": 0.0, "notional": 0.0}
    )
    for t in trades:
        a = agg[t["strategy"]]
        a["trades"] += 1
        if t["action"] == "BUY":
            a["buys"] += 1
        else:
            a["sells"] += 1
        a["realized_pnl"] += float(t["pnl"] or 0)
        a["notional"] += float(t["notional"] or 0)

    lines.append("")
    lines.append(
        f"{'Strategy':<22} {'Trades':>7} {'Buys':>6} {'Sells':>6} "
        f"{'Notional':>14} {'Realized P&L':>14}"
    )
    lines.append("-" * 78)
    for strat, a in sorted(agg.items()):
        lines.append(
            f"{strat:<22} {int(a['trades']):>7} {int(a['buys']):>6} "
            f"{int(a['sells']):>6} ${a['notional']:>12,.0f} ${a['realized_pnl']:>+12,.2f}"
        )

    # Open positions by strategy
    lines.append("")
    lines.append("OPEN POSITIONS BY STRATEGY")
    lines.append("-" * 78)
    by_strat: dict[str, list[dict]] = defaultdict(list)
    for p in positions:
        by_strat[p["strategy"]].append(p)
    for strat in sorted(by_strat):
        lines.append(f"\n  {strat} ({len(by_strat[strat])} positions)")
        for p in by_strat[strat]:
            unr = float(p["unrealized_pnl"] or 0)
            lines.append(
                f"    {p['symbol']:<6} {float(p['shares']):>6.0f} sh  "
                f"avg ${float(p['avg_price'] or 0):>8.2f}  "
                f"now ${float(p['current_price'] or 0):>8.2f}  "
                f"unrealized ${unr:>+10.2f}  entered {p['entry_date']}"
            )

    # Cross-strategy overlap
    overlaps = detect_overlaps(positions)
    lines.append("")
    lines.append("CROSS-STRATEGY OVERLAP")
    lines.append("-" * 78)
    if overlaps:
        for sym, strats in overlaps.items():
            lines.append(f"  {sym}: held by {', '.join(strats)}")
    else:
        lines.append("  (none — every symbol held by at most one strategy)")

    lines.append("")
    return "\n".join(lines)


def csv_report(trades: list[dict], writer: csv._writer) -> None:  # type: ignore[name-defined]
    writer.writerow(
        ["executed_at", "strategy", "symbol", "action", "shares", "exec_price", "notional", "pnl"]
    )
    for t in trades:
        writer.writerow(
            [
                t["executed_at"],
                t["strategy"],
                t["symbol"],
                t["action"],
                t["shares"],
                t["exec_price"],
                t["notional"],
                t["pnl"],
            ]
        )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", action="store_true", help="emit CSV instead of text")
    ap.add_argument("--days", type=int, default=None, help="only trades within last N days")
    args = ap.parse_args()

    if not DB_PATH.exists():
        print(f"trading.db not found at {DB_PATH}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(DB_PATH)
    try:
        trades = fetch_trades(conn, args.days)
        positions = fetch_positions(conn)
    finally:
        conn.close()

    if args.csv:
        csv_report(trades, csv.writer(sys.stdout))
    else:
        print(text_report(trades, positions))
    return 0


if __name__ == "__main__":
    sys.exit(main())
