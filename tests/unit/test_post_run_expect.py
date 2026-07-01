#!/usr/bin/env python3
"""
Regression tests for post-run expectation checks.

The 2026-06-11 run was flagged YELLOW with "Run None: 0 signals generated"
even though it generated 10 raw signals and placed 6 orders: the AUTO_SYNC
broker_state row was written with a local-time 'YYYY-MM-DDTHH:MM:SS'
created_at while engine rows use the UTC space format, and 'T' > ' ' made
the SYNC row win ORDER BY created_at DESC. The checks must pick the latest
*trading run* by insertion order, immune to timestamp-format drift.
"""
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.post_run_expect import (
    check_portfolio_value,
    check_reconciliation,
    check_signals_generated,
    check_sweep_deploying,
)


@pytest.fixture
def conn():
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE broker_state (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            snapshot_date TEXT NOT NULL,
            snapshot_type TEXT NOT NULL,
            cash REAL NOT NULL,
            portfolio_value REAL NOT NULL,
            buying_power REAL NOT NULL,
            positions_json TEXT,
            reconciliation_status TEXT,
            discrepancies_json TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE signal_funnel (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            strategy_id INTEGER NOT NULL,
            strategy_name TEXT NOT NULL,
            raw_signals_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    yield conn
    conn.close()


def _add_broker_row(conn, run_id, snapshot_type, created_at, pv=96000.0, recon="PASS"):
    conn.execute(
        """
        INSERT INTO broker_state
        (run_id, snapshot_date, snapshot_type, cash, portfolio_value,
         buying_power, reconciliation_status, created_at)
        VALUES (?, '2026-06-11', ?, 4000.0, ?, 8000.0, ?, ?)
        """,
        (run_id, snapshot_type, pv, recon, created_at),
    )


def _seed_run_with_trailing_sync(conn):
    """Reproduce the 2026-06-11 layout: engine rows in UTC space format,
    then an AUTO_SYNC row whose T-format created_at string-sorts above them."""
    run = "20260611_055503_test"
    _add_broker_row(conn, run, "START", "2026-06-11 05:55:11")
    _add_broker_row(conn, run, "RECONCILIATION", "2026-06-11 05:55:11")
    _add_broker_row(conn, run, "END", "2026-06-11 05:55:16")
    # Written earlier in wall-clock time but string-sorts AFTER ('T' > ' ')
    _add_broker_row(conn, "AUTO_SYNC", "SYNC", "2026-06-11T05:46:05.553206", recon="SYNCED")
    conn.execute(
        "INSERT INTO signal_funnel (run_id, strategy_id, strategy_name, raw_signals_count) "
        "VALUES (?, 1, 'RSI Mean Reversion', 10)",
        (run,),
    )
    conn.commit()
    return run


def test_signals_check_ignores_auto_sync_rows(conn):
    run = _seed_run_with_trailing_sync(conn)
    ok, detail = check_signals_generated(conn, "2026-06-11")
    assert ok, detail
    assert run in detail
    assert "None" not in detail


def test_signals_check_fails_when_run_truly_has_no_signals(conn):
    _seed_run_with_trailing_sync(conn)
    conn.execute("DELETE FROM signal_funnel")
    conn.commit()
    ok, detail = check_signals_generated(conn, "2026-06-11")
    assert not ok


def test_reconciliation_check_uses_insertion_order_not_created_at(conn):
    _seed_run_with_trailing_sync(conn)
    ok, detail = check_reconciliation(conn, "2026-06-11")
    assert ok, detail
    assert "PASS" in detail


def test_portfolio_value_check_reads_latest_row_by_id(conn):
    _seed_run_with_trailing_sync(conn)
    # A newer row with a different value must win regardless of created_at format
    _add_broker_row(conn, "AUTO_SYNC", "SYNC", "2026-06-11 06:10:00", pv=95000.0, recon="SYNCED")
    conn.commit()
    ok, detail = check_portfolio_value(conn, "2026-06-11")
    assert ok, detail
    assert "95,000" in detail


# ---------------------------------------------------------------------------
# check_sweep_deploying: the sweep silently stopped filling (broker_expired)
# for two weeks in June 2026 while reconciliation self-healed and the run
# stayed GREEN. Cash sat idle. This check must catch that.
# ---------------------------------------------------------------------------


@pytest.fixture
def sweep_conn():
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE strategies (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE order_intents (
            intent_id TEXT, strategy_id INTEGER, symbol TEXT, side TEXT,
            status TEXT, error_code TEXT, created_at TEXT
        );
        INSERT INTO strategies (id, name) VALUES (12, 'Cash Sweep');
        """
    )
    yield conn
    conn.close()


def _add_intent(conn, day, status, error_code=None, side="BUY"):
    conn.execute(
        "INSERT INTO order_intents (intent_id, strategy_id, symbol, side, status, "
        "error_code, created_at) VALUES (?, 12, 'SPY', ?, ?, ?, ?)",
        (f"i{day}", side, status, error_code, f"2026-06-{day} 05:48:00"),
    )


def test_sweep_deploying_fails_when_last_three_expired(sweep_conn):
    for day in ("26", "29", "30"):
        _add_intent(sweep_conn, day, "FAILED", "broker_expired")
    # today's optimistic FILLED intent must be excluded from the verdict
    _add_intent(sweep_conn, "01", "FILLED")  # will read as 2026-06-01, still < today
    sweep_conn.commit()
    ok, detail = check_sweep_deploying(sweep_conn, "2026-07-01")
    assert not ok
    assert "has not deployed" in detail


def test_sweep_deploying_passes_when_orders_fill(sweep_conn):
    for day in ("26", "29", "30"):
        _add_intent(sweep_conn, day, "FILLED")
    sweep_conn.commit()
    ok, detail = check_sweep_deploying(sweep_conn, "2026-07-01")
    assert ok, detail


def test_sweep_deploying_excludes_todays_optimistic_fill(sweep_conn):
    # Prior days all expired; today shows an (optimistic) FILLED — the verdict
    # must be driven by the settled prior days, not today's not-yet-trued row.
    for day in ("26", "29", "30"):
        _add_intent(sweep_conn, day, "FAILED", "broker_expired")
    sweep_conn.execute(
        "INSERT INTO order_intents (intent_id, strategy_id, symbol, side, status, "
        "error_code, created_at) VALUES ('today', 12, 'SPY', 'BUY', 'FILLED', NULL, "
        "'2026-07-01 05:48:00')"
    )
    sweep_conn.commit()
    ok, _ = check_sweep_deploying(sweep_conn, "2026-07-01")
    assert not ok
