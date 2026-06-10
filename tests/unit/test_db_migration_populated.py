#!/usr/bin/env python3
"""
Migration safety net: every schema change must apply cleanly to a POPULATED
legacy database, because production downloads its trading.db from a GHA
artifact each run — a failed migration kills the entire trading day.

The legacy baseline (tests/fixtures/legacy_schema_2026_05.sql) is the real
schema dumped from the 2026-05-29 production artifact, predating the
trade_pnl_detail unique index, tax_treatment, and signal sentiment columns.

When you add a schema change to TradingDatabase._init_database, extend
_seed_legacy_data with rows that stress it (e.g., rows that would violate a
new constraint) and assert the migrated result here.
"""
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.database import TradingDatabase

FIXTURE = Path(__file__).parent.parent / "fixtures" / "legacy_schema_2026_05.sql"


def _seed_legacy_data(conn: sqlite3.Connection) -> None:
    """Populate the legacy DB with realistic production-shaped rows."""
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO strategies (id, name, status, capital_allocation, initial_capital) "
        "VALUES (1, 'RSI Mean Reversion', 'active', 12500.0, 12500.0)"
    )
    cur.execute(
        "INSERT INTO strategies (id, name, status, capital_allocation, initial_capital) "
        "VALUES (2, 'Pairs Trading', 'active', 12500.0, 12500.0)"
    )
    cur.execute(
        "INSERT INTO positions (strategy_id, symbol, shares, avg_price, current_price, "
        " entry_date, last_updated) "
        "VALUES (1, 'UNH', 3.0, 295.50, 301.20, '2026-05-12', '2026-05-29T05:55:00')"
    )
    # A short position (negative shares) must survive migration untouched
    cur.execute(
        "INSERT INTO positions (strategy_id, symbol, shares, avg_price, current_price, "
        " entry_date, last_updated) "
        "VALUES (2, 'BAC', -25.0, 39.10, 38.55, '2026-05-20', '2026-05-29T05:55:00')"
    )
    cur.execute(
        "INSERT INTO trades (strategy_id, symbol, action, shares, requested_price, "
        " exec_price, notional, executed_at, run_id) "
        "VALUES (1, 'UNH', 'BUY', 3.0, 295.00, 295.50, 886.50, '2026-05-12T13:30:00', "
        "        '20260512_055001_test')"
    )
    # Duplicate trade_pnl_detail pair: violates the unique index added 2026-06-09
    # (strategy_id, symbol, sell_run_id, exit_date). Migration must dedup, not die.
    for _ in range(2):
        cur.execute(
            "INSERT INTO trade_pnl_detail "
            "(strategy_id, strategy_name, symbol, sell_run_id, exit_date, entry_price, "
            " exit_price, shares, gross_pnl, gross_pnl_pct, is_winner) "
            "VALUES (1, 'RSI Mean Reversion', 'VZ', '20260521_055001_test', '2026-05-21', "
            "        40.0, 42.0, 25.0, 50.0, 0.05, 1)"
        )
    # A distinct row that must NOT be removed by the dedup
    cur.execute(
        "INSERT INTO trade_pnl_detail "
        "(strategy_id, strategy_name, symbol, sell_run_id, exit_date, entry_price, "
        " exit_price, shares, gross_pnl, gross_pnl_pct, is_winner) "
        "VALUES (2, 'Pairs Trading', 'JPM', '20260522_055001_test', '2026-05-22', "
        "        180.0, 175.0, 10.0, -50.0, -0.028, 0)"
    )
    cur.execute(
        "INSERT INTO broker_state "
        "(run_id, snapshot_date, snapshot_type, cash, portfolio_value, buying_power, "
        " positions_json, reconciliation_status, discrepancies_json) "
        "VALUES ('20260529_055501_test', '2026-05-29', 'END', 92107.25, 96115.72, 184214.50, "
        "        '[]', 'PASS', '[]')"
    )
    cur.execute("INSERT INTO system_state (key, value) VALUES ('peak_portfolio_value', '97855.08')")
    cur.execute(
        "INSERT INTO stop_loss_state (symbol, stop_price, entry_price, entry_atr) "
        "VALUES ('UNH', 280.0, 295.50, 5.2)"
    )
    conn.commit()


@pytest.fixture
def legacy_db(tmp_path):
    """A populated database with the real 2026-05-29 production schema."""
    db_path = tmp_path / "legacy_trading.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(FIXTURE.read_text())
    _seed_legacy_data(conn)
    conn.close()
    return str(db_path)


def _columns(db_path, table):
    with sqlite3.connect(db_path) as conn:
        return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _count(db_path, sql):
    with sqlite3.connect(db_path) as conn:
        return conn.execute(sql).fetchone()[0]


def test_legacy_fixture_is_actually_legacy(legacy_db):
    """Guard: the fixture must predate the migrations we are testing."""
    assert "tax_treatment" not in _columns(legacy_db, "trade_pnl_detail")
    assert "sentiment_score" not in _columns(legacy_db, "signals")
    with sqlite3.connect(legacy_db) as conn:
        indexes = {
            r[0]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()
        }
    assert "idx_trade_pnl_no_dup" not in indexes


def test_migration_applies_cleanly_to_populated_legacy_db(legacy_db):
    """The exact production path: TradingDatabase init against the artifact DB."""
    TradingDatabase(db_path=legacy_db)  # must not raise

    # New columns exist with defaults
    assert "tax_treatment" in _columns(legacy_db, "trade_pnl_detail")
    assert "sentiment_score" in _columns(legacy_db, "signals")
    assert "direction" in _columns(legacy_db, "trade_pnl_detail")
    assert "direction" in _columns(legacy_db, "stop_loss_state")

    # Pre-existing rows get the long default
    with sqlite3.connect(legacy_db) as conn:
        assert (
            conn.execute("SELECT direction FROM stop_loss_state WHERE symbol='UNH'").fetchone()[0]
            == "long"
        )

    # Pre-existing data preserved
    assert _count(legacy_db, "SELECT COUNT(*) FROM positions") == 2
    assert (
        _count(legacy_db, "SELECT COUNT(*) FROM positions WHERE shares < 0") == 1
    ), "short position must survive migration"
    assert _count(legacy_db, "SELECT COUNT(*) FROM broker_state") == 1
    assert (
        _count(
            legacy_db,
            "SELECT COUNT(*) FROM system_state WHERE key='peak_portfolio_value'",
        )
        == 1
    )


def test_migration_dedups_trade_pnl_before_unique_index(legacy_db):
    """Pre-existing duplicate rows must be deduplicated, not crash the run."""
    TradingDatabase(db_path=legacy_db)

    # The duplicate VZ pair collapses to one row; the distinct JPM row survives
    assert (
        _count(
            legacy_db,
            "SELECT COUNT(*) FROM trade_pnl_detail WHERE symbol='VZ'",
        )
        == 1
    )
    assert (
        _count(
            legacy_db,
            "SELECT COUNT(*) FROM trade_pnl_detail WHERE symbol='JPM'",
        )
        == 1
    )

    # And the unique index is now actually in place
    with sqlite3.connect(legacy_db) as conn:
        indexes = {
            r[0]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()
        }
    assert "idx_trade_pnl_no_dup" in indexes


def test_migration_is_idempotent(legacy_db):
    """Running init twice (every GHA run does this) must be a no-op."""
    TradingDatabase(db_path=legacy_db)
    before = _count(legacy_db, "SELECT COUNT(*) FROM trade_pnl_detail")
    TradingDatabase(db_path=legacy_db)
    assert _count(legacy_db, "SELECT COUNT(*) FROM trade_pnl_detail") == before
    assert _count(legacy_db, "SELECT COUNT(*) FROM positions") == 2
