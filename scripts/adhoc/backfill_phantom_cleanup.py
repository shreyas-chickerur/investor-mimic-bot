"""One-shot phantom-position cleanup.

Calls the new ExecutionEngine._reconcile_optimistic_fills() in isolation
against the current DB + paper Alpaca to wipe phantom ABBV/AMD/AMZN
positions that accumulated before the reconciliation fix was wired in.

Idempotent: safe to re-run; only acts on intents whose broker truth
contradicts local state.

Usage: python3 scripts/adhoc/backfill_phantom_cleanup.py
"""
from __future__ import annotations

import logging
import os
import sqlite3
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("backfill")

from alpaca.trading.client import TradingClient  # noqa: E402

from src.core.database import TradingDatabase  # noqa: E402
from src.risk.stop_loss_manager import StopLossManager  # noqa: E402


class MiniEngine:
    """Minimum stand-in for ExecutionEngine carrying just the methods needed
    for `_reconcile_optimistic_fills`. We don't instantiate the full engine
    because it spins up broker streams, regime detector, etc., which we
    don't need for a one-shot DB cleanup."""

    def __init__(self):
        self.db = TradingDatabase()
        api_key = os.getenv("ALPACA_API_KEY")
        secret_key = os.getenv("ALPACA_SECRET_KEY")
        if not api_key or not secret_key:
            raise RuntimeError("Missing Alpaca credentials in .env")
        self.trading_client = TradingClient(api_key, secret_key, paper=True)
        self.stop_loss_manager = StopLossManager(self.db)

    # Reuse the production methods by importing them dynamically.
    from src.core.execution_engine import MultiStrategyRunner

    _reconcile_optimistic_fills = MultiStrategyRunner._reconcile_optimistic_fills
    _reverse_optimistic_fill = MultiStrategyRunner._reverse_optimistic_fill
    _update_position_record = MultiStrategyRunner._update_position_record


def show_positions(db: TradingDatabase, label: str):
    conn = sqlite3.connect(db.db_path)
    rows = conn.execute(
        """
        SELECT s.name, p.symbol, p.shares, p.avg_price
        FROM positions p JOIN strategies s ON p.strategy_id=s.id
        WHERE p.shares != 0 ORDER BY p.symbol
        """
    ).fetchall()
    print(f"\n=== {label} ({len(rows)} open) ===")
    for name, sym, sh, px in rows:
        print(f"  {name:<22} {sym:<6} {sh:>6.2f} @ ${px:.2f}")
    conn.close()


def main() -> None:
    engine = MiniEngine()
    show_positions(engine.db, "BEFORE")
    engine._reconcile_optimistic_fills()  # type: ignore[misc]
    show_positions(engine.db, "AFTER")


if __name__ == "__main__":
    main()
