#!/usr/bin/env python3
"""
True up fill quality from ACTUAL broker fills.

Paper mode books OPG entries optimistically at the limit price; the engine's
order-time fill_quality rows therefore measure nothing. This script fetches
recently CLOSED orders from Alpaca, matches them to the trades table by
broker order id, and records (booked price vs actual filled_avg_price) —
the dataset that validates (or corrects) the 5bps slippage assumption used
by the cost model and every backtest. Going live requires this loop.

Run after the pre-trading broker sync (workflow step `record_fill_quality`).

    python3 scripts/record_fill_quality.py [--db trading.db] [--days 3]
    python3 scripts/record_fill_quality.py --report   # 30d deviation summary
"""
from __future__ import annotations

import argparse
import logging
import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def true_up(db_path: str, days: int) -> int:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.enums import QueryOrderStatus
    from alpaca.trading.requests import GetOrdersRequest

    client = TradingClient(
        os.getenv("ALPACA_API_KEY"),
        os.getenv("ALPACA_SECRET_KEY"),
        paper=os.getenv("ALPACA_PAPER", "true").lower() == "true",
    )
    # alpaca-py 0.11.0 serializes datetimes as `isoformat() + "Z"` with no
    # naive-check, so a tz-aware UTC value becomes the invalid `...+00:00Z`
    # (offset AND Z) → Alpaca 422. Pass NAIVE UTC so it serializes to a clean
    # `...Z`. (0.43.4 coerces naive→UTC and is also fine with this.)
    after = (datetime.now(timezone.utc) - timedelta(days=days)).replace(tzinfo=None)
    orders = client.get_orders(
        GetOrdersRequest(status=QueryOrderStatus.CLOSED, after=after, limit=200)
    )

    conn = sqlite3.connect(db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    recorded = 0
    for order in orders:
        filled_px = getattr(order, "filled_avg_price", None)
        filled_qty = getattr(order, "filled_qty", None)
        if not filled_px or not filled_qty or float(filled_qty) <= 0:
            continue  # expired/cancelled (e.g. unfilled OPG) — no fill to record
        trade = cur.execute(
            "SELECT run_id, strategy_id, symbol, action, exec_price FROM trades "
            "WHERE order_id = ? ORDER BY id DESC LIMIT 1",
            (str(order.id),),
        ).fetchone()
        if not trade:
            continue  # not one of ours (manual order, etc.)
        booked = float(trade["exec_price"])
        actual = float(filled_px)
        if booked <= 0:
            continue
        deviation_bps = int(round((actual - booked) / booked * 10_000))
        # Idempotency: skip if this exact true-up already exists
        dup = cur.execute(
            "SELECT 1 FROM fill_quality WHERE run_id=? AND symbol=? AND action=? "
            "AND ABS(expected_price - ?) < 0.001 AND ABS(fill_price - ?) < 0.001",
            (trade["run_id"], trade["symbol"], trade["action"], booked, actual),
        ).fetchone()
        if dup:
            continue
        cur.execute(
            "INSERT INTO fill_quality (run_id, strategy_id, symbol, action, "
            "expected_price, fill_price, shares, deviation_bps) VALUES (?,?,?,?,?,?,?,?)",
            (
                trade["run_id"],
                trade["strategy_id"],
                trade["symbol"],
                trade["action"],
                booked,
                actual,
                float(filled_qty),
                deviation_bps,
            ),
        )
        recorded += 1
        logger.info(
            "Fill true-up %s %s: booked %.4f actual %.4f (%+d bps)",
            trade["action"],
            trade["symbol"],
            booked,
            actual,
            deviation_bps,
        )
    conn.commit()
    conn.close()
    logger.info("Recorded %d fill true-up(s) from %d closed order(s)", recorded, len(orders))
    return recorded


def report(db_path: str, days: int = 30) -> None:
    conn = sqlite3.connect(db_path, timeout=10)
    rows = conn.execute(
        "SELECT action, COUNT(*), ROUND(AVG(deviation_bps),1), ROUND(AVG(ABS(deviation_bps)),1), "
        "MIN(deviation_bps), MAX(deviation_bps) FROM fill_quality "
        "WHERE recorded_at >= datetime('now', ?) GROUP BY action",
        (f"-{days} days",),
    ).fetchall()
    conn.close()
    print(f"Fill quality, last {days} days (cost model assumes 5 bps slippage):")
    print(f"{'action':<8}{'n':>5}{'avg bps':>9}{'avg|bps|':>9}{'min':>6}{'max':>6}")
    for r in rows:
        print(f"{r[0]:<8}{r[1]:>5}{r[2]:>9}{r[3]:>9}{r[4]:>6}{r[5]:>6}")
    if not rows:
        print("  (no fill-quality rows yet)")


def main() -> None:
    parser = argparse.ArgumentParser(description="True up fill quality from broker fills")
    parser.add_argument("--db", default="trading.db")
    parser.add_argument("--days", type=int, default=3)
    parser.add_argument("--report", action="store_true", help="print 30d deviation summary")
    args = parser.parse_args()
    if args.report:
        report(args.db)
        return
    true_up(args.db, args.days)
    report(args.db)


if __name__ == "__main__":
    main()
