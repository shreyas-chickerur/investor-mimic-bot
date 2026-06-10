#!/usr/bin/env python3
"""
Zero-out local DB positions after a broker-side force-close.

Run this ONLY after confirming the broker (Alpaca) shows 0 open positions.
If the auto-reconciliation handles it on the next bot run, this script is
not needed — use it only as a manual recovery tool.

Usage:
    # Dry-run (default): shows what would be wiped
    python scripts/reset_local_positions.py

    # Confirm: actually wipes positions in local DB
    python scripts/reset_local_positions.py --confirm
"""
import os
import sqlite3
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))

load_dotenv()

DB_PATH = os.getenv("DB_PATH", "trading.db")


def broker_position_count() -> int:
    """Return number of open positions in Alpaca right now."""
    try:
        from alpaca.trading.client import TradingClient

        client = TradingClient(
            os.getenv("ALPACA_API_KEY"),
            os.getenv("ALPACA_SECRET_KEY"),
            paper=os.getenv("ALPACA_PAPER", "true").lower() == "true",
        )
        return len(client.get_all_positions())
    except Exception as exc:
        print(f"WARNING: Could not reach Alpaca to verify broker state: {exc}")
        return -1


def local_open_positions(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, strategy_id, symbol, shares FROM positions WHERE shares > 0"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def reset_positions(db_path: str, confirm: bool = False):
    broker_count = broker_position_count()
    if broker_count > 0:
        print(
            f"ERROR: Broker still shows {broker_count} open position(s). "
            "Close them first before resetting the local DB."
        )
        return False
    if broker_count == -1:
        print("WARNING: Could not verify broker state — proceeding with caution.")

    positions = local_open_positions(db_path)
    if not positions:
        print("Local DB already has 0 open positions — nothing to do.")
        return True

    print(f"{'DRY RUN — ' if not confirm else ''}Found {len(positions)} local positions to zero:")
    for p in positions:
        print(f"  strategy_id={p['strategy_id']}  {p['symbol']}  {p['shares']} shares")

    if not confirm:
        print("\nRun with --confirm to zero all local positions.")
        return True

    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE positions SET shares = 0, current_price = NULL WHERE shares > 0")
    conn.commit()
    conn.close()
    print(f"\nZeroed {len(positions)} positions in {db_path}")
    return True


if __name__ == "__main__":
    confirm = "--confirm" in sys.argv
    ok = reset_positions(DB_PATH, confirm=confirm)
    sys.exit(0 if ok else 1)
