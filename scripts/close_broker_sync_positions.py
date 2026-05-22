#!/usr/bin/env python3
"""
Close all BROKER_SYNC positions at Alpaca and remove them from the local DB.

For symbols held by BOTH BROKER_SYNC and a real strategy, only the BROKER_SYNC
shares are closed (partial close); the strategy-tracked shares are untouched.

Run once interactively — confirms before submitting any orders.
"""
from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import ClosePositionRequest

DB_PATH = Path(os.getenv("DB_PATH", "trading.db"))
PAPER = os.getenv("ALPACA_PAPER", "true").lower() != "false"


def get_broker_sync_positions(conn: sqlite3.Connection) -> dict[str, float]:
    """Return {symbol: shares} for BROKER_SYNC rows with shares > 0."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT p.symbol, p.shares
        FROM positions p
        JOIN strategies s ON p.strategy_id = s.id
        WHERE s.name = 'BROKER_SYNC' AND p.shares > 0
        """
    )
    return {row[0]: float(row[1]) for row in cur.fetchall()}


def get_strategy_positions(conn: sqlite3.Connection) -> dict[str, float]:
    """Return {symbol: total_shares} for non-BROKER_SYNC strategies (shares > 0)."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT p.symbol, SUM(p.shares)
        FROM positions p
        JOIN strategies s ON p.strategy_id = s.id
        WHERE s.name != 'BROKER_SYNC' AND p.shares > 0
        GROUP BY p.symbol
        """
    )
    return {row[0]: float(row[1]) for row in cur.fetchall()}


def remove_broker_sync_positions(conn: sqlite3.Connection, symbols: list[str]) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        DELETE FROM positions
        WHERE strategy_id = (SELECT id FROM strategies WHERE name = 'BROKER_SYNC')
          AND symbol IN ({})
        """.format(
            ",".join("?" * len(symbols))
        ),
        symbols,
    )
    conn.commit()


def main() -> None:
    client = TradingClient(
        os.getenv("ALPACA_API_KEY"),
        os.getenv("ALPACA_SECRET_KEY"),
        paper=PAPER,
    )

    conn = sqlite3.connect(DB_PATH)
    bs_positions = get_broker_sync_positions(conn)
    strat_positions = get_strategy_positions(conn)

    if not bs_positions:
        print("No BROKER_SYNC positions found in DB — nothing to do.")
        conn.close()
        return

    print(f"\nFound {len(bs_positions)} BROKER_SYNC positions in local DB:")
    print(f"{'Symbol':<8} {'BS shares':>10} {'Strat shares':>13} {'Action':>20}")
    print("-" * 55)

    plan: list[tuple[str, float, bool]] = []  # (symbol, qty_to_close, full_close)
    for symbol, bs_shares in sorted(bs_positions.items()):
        strat_shares = strat_positions.get(symbol, 0.0)
        if strat_shares > 0:
            action = f"partial close {int(bs_shares)} shares"
            plan.append((symbol, bs_shares, False))
        else:
            action = "full close"
            plan.append((symbol, bs_shares, True))
        print(f"{symbol:<8} {bs_shares:>10.0f} {strat_shares:>13.0f} {action:>20}")

    total_approx = sum(s for _, s, _ in plan)
    print(f"\nTotal BROKER_SYNC shares to close: {total_approx:.0f}")
    print(f"Mode: {'PAPER' if PAPER else 'LIVE'}")

    confirm = input("\nType YES to submit close orders: ").strip()
    if confirm != "YES":
        print("Aborted.")
        conn.close()
        return

    # Fetch live broker positions to validate
    try:
        broker_pos = {p.symbol: float(p.qty) for p in client.get_all_positions()}
    except Exception as exc:
        print(f"Could not fetch broker positions: {exc}")
        conn.close()
        return

    closed: list[str] = []
    failed: list[str] = []

    for symbol, qty_to_close, full_close in plan:
        broker_qty = broker_pos.get(symbol, 0.0)
        if broker_qty <= 0:
            print(
                f"  {symbol}: not at broker (broker_qty={broker_qty}) — skipping order, will clean DB"
            )
            closed.append(symbol)
            continue

        try:
            if full_close and abs(broker_qty - qty_to_close) < 1:
                client.close_position(symbol)
                print(f"  {symbol}: closed all {int(broker_qty)} shares ✓")
            else:
                # Partial close — only close the BROKER_SYNC portion
                qty = min(qty_to_close, broker_qty)
                client.close_position(symbol, ClosePositionRequest(qty=str(int(qty))))
                print(f"  {symbol}: partial close {int(qty)} of {int(broker_qty)} shares ✓")
            closed.append(symbol)
        except Exception as exc:
            print(f"  {symbol}: FAILED — {exc}")
            failed.append(symbol)

    if closed:
        remove_broker_sync_positions(conn, closed)
        print(f"\nRemoved {len(closed)} BROKER_SYNC rows from local DB.")

    if failed:
        print(f"\n⚠️  {len(failed)} symbols failed to close: {failed}")
        print("Re-run the script to retry, or close them manually in Alpaca.")

    conn.close()
    print("\nDone. Run sync_broker_state.py afterward to verify reconciliation.")


if __name__ == "__main__":
    main()
