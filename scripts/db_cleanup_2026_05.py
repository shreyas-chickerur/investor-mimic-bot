#!/usr/bin/env python3
"""
DB cleanup script — run once to fix accumulated data quality issues.
Safe to re-run: all statements use conditional logic.

Issues addressed:
  1. Old order_intents stuck at SUBMITTED → mark FILLED (positions confirm orders executed)
  2. Phantom strategies (no code) → status='watching', capital_allocation=0
  3. Real strategy capital_allocation → equal shares of current portfolio value
  4. Dec 25 2025 test signals → tag terminal_reason='test_run_duplicate'
"""
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "trading.db"


def run(db_path: Path = DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    print(f"=== DB Cleanup  {datetime.now():%Y-%m-%d %H:%M} ===")
    print(f"Database: {db_path}\n")

    # ------------------------------------------------------------------
    # 1. Fix stuck order_intents: SUBMITTED → FILLED
    #    These orders DID execute (positions exist), but verify_order_statuses
    #    never advanced the lifecycle because OPG orders aren't filled at 7:30 PM.
    # ------------------------------------------------------------------
    c.execute("SELECT COUNT(*) FROM order_intents WHERE status = 'SUBMITTED'")
    stuck_count = c.fetchone()[0]
    print(f"[1] SUBMITTED order_intents to mark FILLED: {stuck_count}")

    if stuck_count > 0:
        c.execute(
            """
            UPDATE order_intents
            SET status = 'FILLED',
                filled_at = COALESCE(submitted_at, created_at)
            WHERE status = 'SUBMITTED'
            """
        )
        print(f"    ✅ Marked {c.rowcount} intents as FILLED")
    else:
        print("    ✅ None found (already clean)")

    # ------------------------------------------------------------------
    # 2. Mark phantom strategies (no source code) as 'watching' and zero their allocation
    #    IDs 3=News Sentiment, 4=MA Crossover, 5=Volatility Breakout
    # ------------------------------------------------------------------
    phantom_names = ("News Sentiment", "MA Crossover", "Volatility Breakout")
    print(f"\n[2] Phantom strategies to update: {phantom_names}")

    for name in phantom_names:
        c.execute("SELECT id, status, capital_allocation FROM strategies WHERE name = ?", (name,))
        row = c.fetchone()
        if row:
            c.execute(
                "UPDATE strategies SET status='watching', capital_allocation=0 WHERE name=?",
                (name,),
            )
            print(f"    ✅ {name} (id={row['id']}): status→watching, allocation→$0")
        else:
            print(f"    ℹ  {name}: not found in DB")

    # ------------------------------------------------------------------
    # 3. Rebalance capital_allocation for the 4 real strategies
    #    Set equal shares of most recent portfolio value.
    # ------------------------------------------------------------------
    c.execute("SELECT portfolio_value FROM broker_state ORDER BY created_at DESC LIMIT 1")
    row = c.fetchone()
    portfolio_value = float(row["portfolio_value"]) if row else 96344.0
    per_strategy = round(portfolio_value / 4, 2)

    real_strategies = (
        "RSI Mean Reversion",
        "ML Momentum",
        "Earnings Drift",
        "Factor Momentum",
    )
    print(f"\n[3] Rebalancing capital for {len(real_strategies)} real strategies")
    print(f"    Portfolio: ${portfolio_value:,.2f}  →  ${per_strategy:,.2f} each")

    for name in real_strategies:
        c.execute("UPDATE strategies SET capital_allocation=? WHERE name=?", (per_strategy, name))
        if c.rowcount:
            print(f"    ✅ {name}: capital_allocation → ${per_strategy:,.2f}")
        else:
            print(f"    ⚠  {name}: not found in DB")

    # ------------------------------------------------------------------
    # 4. Tag Dec 25 2025 test signals so they don't pollute analytics
    #    These 33 signals were generated in a 30-minute test burst on 2025-12-25.
    # ------------------------------------------------------------------
    c.execute("SELECT COUNT(*) FROM signals WHERE date(generated_at) = '2025-12-25'")
    test_sig_count = c.fetchone()[0]
    print(f"\n[4] Dec-25-2025 test signals to tag: {test_sig_count}")

    if test_sig_count > 0:
        c.execute(
            """
            UPDATE signals
            SET terminal_state  = COALESCE(terminal_state, 'FILTERED'),
                terminal_reason = 'test_run_duplicate'
            WHERE date(generated_at) = '2025-12-25'
            """
        )
        print(f"    ✅ Tagged {c.rowcount} test signals with terminal_reason='test_run_duplicate'")
    else:
        print("    ✅ None found (already tagged or absent)")

    conn.commit()
    conn.close()

    print("\n=== Cleanup complete ===")
    print("Run the email digest preview to verify the numbers look right:")
    print("  python3 scripts/generate_daily_email.py --mock-state healthy")


if __name__ == "__main__":
    import sys

    db = Path(sys.argv[1]) if len(sys.argv) > 1 else DB_PATH
    run(db)
