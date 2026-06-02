#!/usr/bin/env python3
"""
Record a lightweight daily portfolio snapshot from Alpaca.

Used by the portfolio_snapshot GHA workflow on non-trading days (weekends,
holidays) so the equity curve in daily_portfolio_snapshot has no gaps.
The main trading workflow also records a snapshot via TradingDatabase; this
script simply does the same thing independently using only the broker state.
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DB_PATH = Path(os.getenv("DB_PATH", "trading.db"))


def _get_broker_state() -> dict:
    from alpaca.trading.client import TradingClient

    api_key = os.getenv("ALPACA_API_KEY")
    secret_key = os.getenv("ALPACA_SECRET_KEY")
    paper = os.getenv("ALPACA_PAPER", "true").lower() != "false"

    client = TradingClient(api_key, secret_key, paper=paper)
    account = client.get_account()

    portfolio_value = float(account.portfolio_value)
    cash = float(account.cash)
    positions_value = portfolio_value - cash

    positions = client.get_all_positions()
    allocation_json = json.dumps({p.symbol: float(p.market_value) for p in positions})
    num_positions = len(positions)

    return {
        "portfolio_value": portfolio_value,
        "cash": cash,
        "positions_value": positions_value,
        "allocation_json": allocation_json,
        "num_positions": num_positions,
    }


def _record_snapshot(state: dict) -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT portfolio_value, peak_value FROM daily_portfolio_snapshot ORDER BY snapshot_date DESC LIMIT 1"
    )
    prev = cursor.fetchone()
    prev_value = prev[0] if prev else state["portfolio_value"]
    prev_peak = prev[1] if prev else state["portfolio_value"]

    daily_pnl = state["portfolio_value"] - prev_value
    daily_pnl_pct = daily_pnl / prev_value if prev_value else 0.0
    peak_value = max(prev_peak, state["portfolio_value"])

    # Use the first recorded portfolio value as baseline for cumulative P&L.
    # SUM(initial_capital) across strategies exceeds the actual account value because
    # strategies were added over time — each carries its own initial_capital budget,
    # making the total appear far larger than what the broker ever held.
    cursor.execute(
        "SELECT portfolio_value FROM daily_portfolio_snapshot ORDER BY snapshot_date ASC LIMIT 1"
    )
    first_row = cursor.fetchone()
    initial_capital = first_row[0] if first_row else state["portfolio_value"]
    cumulative_pnl = state["portfolio_value"] - initial_capital
    drawdown_pct = (state["portfolio_value"] - peak_value) / peak_value if peak_value else 0.0

    cursor.execute(
        """
        INSERT INTO daily_portfolio_snapshot
        (run_id, snapshot_date, portfolio_value, cash, positions_value,
         heat_pct, daily_pnl, daily_pnl_pct, cumulative_pnl, drawdown_pct,
         peak_value, num_open_positions, vix, regime, allocation_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(snapshot_date) DO UPDATE SET
            portfolio_value = excluded.portfolio_value,
            cash = excluded.cash,
            positions_value = excluded.positions_value,
            daily_pnl = excluded.daily_pnl,
            daily_pnl_pct = excluded.daily_pnl_pct,
            cumulative_pnl = excluded.cumulative_pnl,
            drawdown_pct = excluded.drawdown_pct,
            peak_value = excluded.peak_value,
            num_open_positions = excluded.num_open_positions,
            allocation_json = excluded.allocation_json
        """,
        (
            "snapshot",
            today,
            state["portfolio_value"],
            state["cash"],
            state["positions_value"],
            0.0,  # heat_pct not available without strategy context
            daily_pnl,
            daily_pnl_pct,
            cumulative_pnl,
            drawdown_pct,
            peak_value,
            state["num_positions"],
            None,  # vix
            None,  # regime
            state["allocation_json"],
        ),
    )
    conn.commit()
    conn.close()
    logger.info(
        "Snapshot recorded for %s: portfolio=$%.2f daily_pnl=$%.2f",
        today,
        state["portfolio_value"],
        daily_pnl,
    )


def main():
    logger.info("Fetching broker state from Alpaca...")
    state = _get_broker_state()
    logger.info(
        "Portfolio: $%.2f | Cash: $%.2f | Positions: %d",
        state["portfolio_value"],
        state["cash"],
        state["num_positions"],
    )
    _record_snapshot(state)


if __name__ == "__main__":
    main()
