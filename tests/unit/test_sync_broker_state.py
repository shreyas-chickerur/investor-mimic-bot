#!/usr/bin/env python3
"""
Tests for sync_broker_state.py corrective sync logic.

Verifies that the sync script correctly adjusts local positions to match
broker state without destructively wiping strategy-level tracking.
"""
import os
import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.sync_broker_state import (
    _find_entry_intent,
    _get_local_positions,
    _get_or_create_broker_sync_strategy,
    sync_broker_to_database,
)


@pytest.fixture
def temp_db():
    """Create a temporary database with the required schema."""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    tmp.close()
    conn = sqlite3.connect(tmp.name)
    cursor = conn.cursor()

    cursor.execute(
        """CREATE TABLE strategies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        capital_allocation REAL DEFAULT 0.0,
        initial_capital REAL DEFAULT 0.0,
        status TEXT DEFAULT 'active'
    )"""
    )

    cursor.execute(
        """CREATE TABLE positions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        strategy_id INTEGER NOT NULL,
        symbol TEXT NOT NULL,
        shares REAL DEFAULT 0.0,
        avg_price REAL DEFAULT 0.0,
        current_price REAL,
        market_value REAL,
        unrealized_pnl REAL,
        last_updated TEXT,
        entry_date TEXT,
        UNIQUE(strategy_id, symbol),
        FOREIGN KEY (strategy_id) REFERENCES strategies(id)
    )"""
    )

    cursor.execute(
        """CREATE TABLE order_intents (
        intent_id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        strategy_id INTEGER NOT NULL,
        symbol TEXT NOT NULL,
        side TEXT NOT NULL,
        target_qty REAL NOT NULL,
        status TEXT NOT NULL,
        broker_order_id TEXT,
        error_code TEXT,
        error_message TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        submitted_at TEXT,
        acked_at TEXT,
        filled_at TEXT,
        FOREIGN KEY (strategy_id) REFERENCES strategies(id)
    )"""
    )

    cursor.execute(
        """CREATE TABLE broker_state (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT,
        snapshot_date TEXT,
        snapshot_type TEXT,
        cash REAL,
        portfolio_value REAL,
        buying_power REAL,
        positions_json TEXT,
        reconciliation_status TEXT,
        created_at TEXT
    )"""
    )

    conn.commit()
    conn.close()
    yield tmp.name
    os.unlink(tmp.name)


def _seed_strategy(db_path, name, capital=20000.0):
    """Helper to insert a strategy and return its id."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO strategies (name, description, capital_allocation, initial_capital, status) "
        "VALUES (?, ?, 0.2, ?, 'active')",
        (name, f"{name} strategy", capital),
    )
    sid = cursor.lastrowid
    conn.commit()
    conn.close()
    return sid


def _seed_position(db_path, strategy_id, symbol, shares, avg_price):
    """Helper to insert a position."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO positions (strategy_id, symbol, shares, avg_price, last_updated) "
        "VALUES (?, ?, ?, ?, ?)",
        (strategy_id, symbol, shares, avg_price, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def _seed_intent(
    db_path,
    strategy_id,
    symbol,
    side="BUY",
    target_qty=10.0,
    status="FILLED",
    days_ago=1,
    intent_id=None,
):
    """Helper to insert an order intent created `days_ago` days ago (UTC)."""
    created = (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO order_intents (intent_id, run_id, strategy_id, symbol, side, "
        " target_qty, status, broker_order_id, created_at, submitted_at, filled_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            intent_id or f"intent_{strategy_id}_{symbol}_{side}_{days_ago}",
            "20260707_055001_test",
            strategy_id,
            symbol,
            side,
            target_qty,
            status,
            "broker-order-1",
            created,
            created,
            created if status == "FILLED" else None,
        ),
    )
    conn.commit()
    conn.close()
    return created[:10]  # the DATE() the sync should adopt as entry_date


def _get_all_positions(db_path):
    """Helper to read all positions from the database."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM positions WHERE shares != 0")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def _mock_broker_state(positions_dict, cash=50000.0, portfolio_value=100000.0):
    """Build a broker_state dict matching BrokerReconciler.get_broker_state() format."""
    return {
        "positions": {
            sym: {"qty": qty, "avg_price": avg} for sym, (qty, avg) in positions_dict.items()
        },
        "cash": cash,
        "portfolio_value": portfolio_value,
        "buying_power": cash,
    }


# ---------------------------------------------------------------------------
# Unit tests for helper functions
# ---------------------------------------------------------------------------


class TestGetLocalPositions:
    """Tests for _get_local_positions."""

    def test_empty_database(self, temp_db):
        conn = sqlite3.connect(temp_db)
        result = _get_local_positions(conn.cursor())
        conn.close()
        assert result == {}

    def test_single_strategy_single_symbol(self, temp_db):
        sid = _seed_strategy(temp_db, "RSI")
        _seed_position(temp_db, sid, "AAPL", 10, 150.0)

        conn = sqlite3.connect(temp_db)
        result = _get_local_positions(conn.cursor())
        conn.close()

        assert "AAPL" in result
        assert result["AAPL"]["total"] == 10.0
        assert len(result["AAPL"]["strategies"]) == 1

    def test_multiple_strategies_same_symbol(self, temp_db):
        sid1 = _seed_strategy(temp_db, "RSI")
        sid2 = _seed_strategy(temp_db, "MA")
        _seed_position(temp_db, sid1, "AAPL", 10, 150.0)
        _seed_position(temp_db, sid2, "AAPL", 5, 155.0)

        conn = sqlite3.connect(temp_db)
        result = _get_local_positions(conn.cursor())
        conn.close()

        assert result["AAPL"]["total"] == 15.0
        assert len(result["AAPL"]["strategies"]) == 2

    def test_zero_share_positions_excluded(self, temp_db):
        sid = _seed_strategy(temp_db, "RSI")
        _seed_position(temp_db, sid, "AAPL", 0, 150.0)

        conn = sqlite3.connect(temp_db)
        result = _get_local_positions(conn.cursor())
        conn.close()

        assert result == {}

    def test_short_positions_included(self, temp_db):
        """Regression: shorts (negative shares) must be visible to the
        post-sync verifier. See run 25943767585: a -24 NFLX short was
        invisible because the query used `WHERE shares > 0`, so the
        verifier kept reporting local=0 vs broker=-24 even after the
        sync had inserted the negative-share row."""
        sid = _seed_strategy(temp_db, "BROKER_SYNC")
        _seed_position(temp_db, sid, "NFLX", -24, 700.0)

        conn = sqlite3.connect(temp_db)
        result = _get_local_positions(conn.cursor())
        conn.close()

        assert "NFLX" in result
        assert result["NFLX"]["total"] == -24.0
        assert len(result["NFLX"]["strategies"]) == 1


class TestGetOrCreateBrokerSyncStrategy:
    """Tests for _get_or_create_broker_sync_strategy."""

    def test_creates_new_strategy(self, temp_db):
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        sid = _get_or_create_broker_sync_strategy(cursor, 100000.0)
        conn.commit()
        conn.close()

        assert sid is not None
        assert sid > 0

    def test_returns_existing_strategy(self, temp_db):
        # Create it first
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        sid1 = _get_or_create_broker_sync_strategy(cursor, 100000.0)
        conn.commit()

        # Call again — should return the same id
        sid2 = _get_or_create_broker_sync_strategy(cursor, 200000.0)
        conn.close()

        assert sid1 == sid2


# ---------------------------------------------------------------------------
# Integration tests for sync_broker_to_database
# ---------------------------------------------------------------------------


class TestSyncBrokerToDatabase:
    """Tests for the full corrective sync flow."""

    @patch("scripts.sync_broker_state.BrokerReconciler")
    def test_in_sync_no_changes(self, MockReconciler, temp_db):
        """When local matches broker, no changes should be made."""
        sid = _seed_strategy(temp_db, "RSI")
        _seed_position(temp_db, sid, "AAPL", 10, 150.0)

        mock_rec = MockReconciler.return_value
        mock_rec.get_broker_state.return_value = _mock_broker_state({"AAPL": (10, 150.0)})

        result = sync_broker_to_database(temp_db)
        assert result is True

        positions = _get_all_positions(temp_db)
        assert len(positions) == 1
        assert positions[0]["shares"] == 10.0

    @patch("scripts.sync_broker_state.BrokerReconciler")
    def test_new_broker_position_added_as_broker_sync(self, MockReconciler, temp_db):
        """A position in broker but not local should be added under BROKER_SYNC."""
        mock_rec = MockReconciler.return_value
        mock_rec.get_broker_state.return_value = _mock_broker_state({"AAPL": (10, 150.0)})

        result = sync_broker_to_database(temp_db)
        assert result is True

        positions = _get_all_positions(temp_db)
        assert len(positions) == 1
        assert positions[0]["symbol"] == "AAPL"
        assert positions[0]["shares"] == 10.0

        # Verify it was assigned to BROKER_SYNC strategy
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT s.name FROM strategies s JOIN positions p ON s.id = p.strategy_id WHERE p.symbol = 'AAPL'"
        )
        name = cursor.fetchone()[0]
        conn.close()
        assert name == "BROKER_SYNC"

    @patch("scripts.sync_broker_state.BrokerReconciler")
    def test_zero_broker_avg_price_falls_back_to_implied(self, MockReconciler, temp_db):
        """avg_price=0 from the broker must not be written as 0 (corrupts P&L and
        disables the stop-loss audit). It falls back to market_value/qty."""
        mock_rec = MockReconciler.return_value
        state = _mock_broker_state({"VZ": (25, 0.0)})  # broker reports avg_price 0
        state["positions"]["VZ"]["market_value"] = 1150.0  # implies $46.00/share
        mock_rec.get_broker_state.return_value = state

        result = sync_broker_to_database(temp_db)
        assert result is True

        conn = sqlite3.connect(temp_db)
        avg = conn.execute("SELECT avg_price FROM positions WHERE symbol='VZ'").fetchone()[0]
        conn.close()
        assert avg == pytest.approx(46.0), f"expected implied 46.0, got {avg}"

    @patch("scripts.sync_broker_state.BrokerReconciler")
    def test_local_less_than_broker_adds_shares(self, MockReconciler, temp_db):
        """When local has fewer shares, the difference is added to the largest strategy."""
        sid = _seed_strategy(temp_db, "RSI")
        _seed_position(temp_db, sid, "AAPL", 8, 150.0)

        mock_rec = MockReconciler.return_value
        mock_rec.get_broker_state.return_value = _mock_broker_state({"AAPL": (14, 152.0)})

        result = sync_broker_to_database(temp_db)
        assert result is True

        positions = _get_all_positions(temp_db)
        total = sum(p["shares"] for p in positions if p["symbol"] == "AAPL")
        assert total == 14.0

    @patch("scripts.sync_broker_state.BrokerReconciler")
    def test_local_more_than_broker_reduces_shares(self, MockReconciler, temp_db):
        """When local has more shares, excess is removed from the largest strategy."""
        sid = _seed_strategy(temp_db, "RSI")
        _seed_position(temp_db, sid, "AAPL", 20, 150.0)

        mock_rec = MockReconciler.return_value
        mock_rec.get_broker_state.return_value = _mock_broker_state({"AAPL": (14, 150.0)})

        result = sync_broker_to_database(temp_db)
        assert result is True

        positions = _get_all_positions(temp_db)
        total = sum(p["shares"] for p in positions if p["symbol"] == "AAPL")
        assert total == 14.0

    @patch("scripts.sync_broker_state.BrokerReconciler")
    def test_local_position_removed_when_not_in_broker(self, MockReconciler, temp_db):
        """Positions that exist locally but not in broker should be removed."""
        sid = _seed_strategy(temp_db, "RSI")
        _seed_position(temp_db, sid, "AAPL", 10, 150.0)
        _seed_position(temp_db, sid, "MSFT", 5, 300.0)

        mock_rec = MockReconciler.return_value
        mock_rec.get_broker_state.return_value = _mock_broker_state(
            {"AAPL": (10, 150.0)}  # MSFT not in broker
        )

        result = sync_broker_to_database(temp_db)
        assert result is True

        positions = _get_all_positions(temp_db)
        symbols = [p["symbol"] for p in positions]
        assert "AAPL" in symbols
        assert "MSFT" not in symbols

    @patch("scripts.sync_broker_state.BrokerReconciler")
    def test_reduce_removes_position_when_zero(self, MockReconciler, temp_db):
        """When broker has 0 for a symbol that exists locally, position is deleted."""
        sid = _seed_strategy(temp_db, "RSI")
        _seed_position(temp_db, sid, "AAPL", 10, 150.0)

        mock_rec = MockReconciler.return_value
        # Broker has no AAPL at all
        mock_rec.get_broker_state.return_value = _mock_broker_state({})

        result = sync_broker_to_database(temp_db)
        assert result is True

        positions = _get_all_positions(temp_db)
        assert len(positions) == 0

    @patch("scripts.sync_broker_state.BrokerReconciler")
    def test_multi_strategy_adds_to_largest(self, MockReconciler, temp_db):
        """When multiple strategies hold a symbol, shares are added to the largest."""
        sid1 = _seed_strategy(temp_db, "RSI")
        sid2 = _seed_strategy(temp_db, "MA")
        _seed_position(temp_db, sid1, "AAPL", 5, 150.0)
        _seed_position(temp_db, sid2, "AAPL", 10, 155.0)  # MA has more

        mock_rec = MockReconciler.return_value
        mock_rec.get_broker_state.return_value = _mock_broker_state({"AAPL": (20, 152.0)})

        result = sync_broker_to_database(temp_db)
        assert result is True

        # MA strategy should have received the extra 5 shares (10 + 5 = 15)
        conn = sqlite3.connect(temp_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT shares FROM positions WHERE strategy_id = ? AND symbol = 'AAPL'",
            (sid2,),
        )
        ma_shares = cursor.fetchone()["shares"]
        conn.close()

        assert ma_shares == 15.0

    @patch("scripts.sync_broker_state.BrokerReconciler")
    def test_broker_state_failure_returns_false(self, MockReconciler, temp_db):
        """If broker state can't be fetched, sync should return False."""
        mock_rec = MockReconciler.return_value
        mock_rec.get_broker_state.return_value = {}

        result = sync_broker_to_database(temp_db)
        assert result is False

    @patch("scripts.sync_broker_state.BrokerReconciler")
    def test_sync_records_broker_state_entry(self, MockReconciler, temp_db):
        """Sync should record a SYNC entry in broker_state table."""
        mock_rec = MockReconciler.return_value
        mock_rec.get_broker_state.return_value = _mock_broker_state({"AAPL": (10, 150.0)})

        sync_broker_to_database(temp_db)

        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT run_id, snapshot_type, reconciliation_status FROM broker_state")
        row = cursor.fetchone()
        conn.close()

        assert row is not None
        assert row[0] == "AUTO_SYNC"
        assert row[1] == "SYNC"
        assert row[2] == "SYNCED"

    @patch("scripts.sync_broker_state.BrokerReconciler")
    def test_complex_multi_symbol_sync(self, MockReconciler, temp_db):
        """Test a realistic scenario with multiple symbols and strategies."""
        sid1 = _seed_strategy(temp_db, "RSI")
        sid2 = _seed_strategy(temp_db, "MA")

        # Local state
        _seed_position(temp_db, sid1, "AAPL", 10, 150.0)  # matches broker
        _seed_position(temp_db, sid2, "AAPL", 4, 155.0)  # total 14, broker has 14
        _seed_position(temp_db, sid1, "MSFT", 20, 300.0)  # local only, not in broker
        _seed_position(temp_db, sid2, "ADBE", 6, 500.0)  # broker has 12

        mock_rec = MockReconciler.return_value
        mock_rec.get_broker_state.return_value = _mock_broker_state(
            {
                "AAPL": (14, 152.0),  # matches local total
                "ADBE": (12, 510.0),  # local has 6, need +6
                "PG": (13, 160.0),  # new, not in local
            }
        )

        result = sync_broker_to_database(temp_db)
        assert result is True

        positions = _get_all_positions(temp_db)
        by_symbol = {}
        for p in positions:
            by_symbol.setdefault(p["symbol"], 0)
            by_symbol[p["symbol"]] += p["shares"]

        assert by_symbol.get("AAPL") == 14.0
        assert by_symbol.get("ADBE") == 12.0
        assert by_symbol.get("PG") == 13.0
        assert "MSFT" not in by_symbol  # removed


# ---------------------------------------------------------------------------
# Intent-based attribution of untracked broker positions
# ---------------------------------------------------------------------------


def _strategy_of(db_path, symbol):
    """Return (strategy_name, entry_date) for the position holding `symbol`."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT s.name, p.entry_date FROM positions p "
        "JOIN strategies s ON s.id = p.strategy_id WHERE p.symbol = ?",
        (symbol,),
    )
    row = cursor.fetchone()
    conn.close()
    return row


class TestIntentAttribution:
    """Regression tests for the PR #60 orphan-adoption bug.

    DAY marketable-limit entries fill intraday AFTER the pre-market run ends.
    If the optimistic local position is lost before the next morning's sync
    (e.g. a same-day duplicate run's "not in broker" sweep), the fill used to
    be adopted under BROKER_SYNC — orphaned from its strategy's exit logic and
    permanently consuming a max_positions slot (11/16 slots by 2026-07-21,
    129 max_positions_reached rejections in 2 weeks). The sync must instead
    match the fill against the previous day's order_intents and book it under
    the originating strategy.
    """

    @patch("scripts.sync_broker_state.BrokerReconciler")
    def test_untracked_fill_attributed_to_intent_strategy(self, MockReconciler, temp_db):
        """A broker position matching yesterday's BUY intent goes to that
        strategy — not BROKER_SYNC — with the intent's fill date as entry_date."""
        rsi = _seed_strategy(temp_db, "RSI Mean Reversion")
        fill_date = _seed_intent(temp_db, rsi, "CSCO", target_qty=43, days_ago=1)

        mock_rec = MockReconciler.return_value
        mock_rec.get_broker_state.return_value = _mock_broker_state({"CSCO": (43, 68.42)})

        assert sync_broker_to_database(temp_db) is True

        name, entry_date = _strategy_of(temp_db, "CSCO")
        assert name == "RSI Mean Reversion"
        assert entry_date == fill_date

    @patch("scripts.sync_broker_state.BrokerReconciler")
    def test_stale_intent_falls_back_to_broker_sync(self, MockReconciler, temp_db):
        """Intents older than the lookback window must not claim the position."""
        rsi = _seed_strategy(temp_db, "RSI Mean Reversion")
        _seed_intent(temp_db, rsi, "CSCO", target_qty=43, days_ago=10)

        mock_rec = MockReconciler.return_value
        mock_rec.get_broker_state.return_value = _mock_broker_state({"CSCO": (43, 68.42)})

        assert sync_broker_to_database(temp_db) is True
        assert _strategy_of(temp_db, "CSCO")[0] == "BROKER_SYNC"

    @patch("scripts.sync_broker_state.BrokerReconciler")
    def test_failed_intent_ignored(self, MockReconciler, temp_db):
        """A FAILED (reversed-phantom) intent must not claim the position."""
        rsi = _seed_strategy(temp_db, "RSI Mean Reversion")
        _seed_intent(temp_db, rsi, "CSCO", target_qty=43, status="FAILED", days_ago=1)

        mock_rec = MockReconciler.return_value
        mock_rec.get_broker_state.return_value = _mock_broker_state({"CSCO": (43, 68.42)})

        assert sync_broker_to_database(temp_db) is True
        assert _strategy_of(temp_db, "CSCO")[0] == "BROKER_SYNC"

    @patch("scripts.sync_broker_state.BrokerReconciler")
    def test_sell_intent_not_matched_for_long(self, MockReconciler, temp_db):
        """Only BUY intents explain a long broker position."""
        rsi = _seed_strategy(temp_db, "RSI Mean Reversion")
        _seed_intent(temp_db, rsi, "CSCO", side="SELL", target_qty=43, days_ago=1)

        mock_rec = MockReconciler.return_value
        mock_rec.get_broker_state.return_value = _mock_broker_state({"CSCO": (43, 68.42)})

        assert sync_broker_to_database(temp_db) is True
        assert _strategy_of(temp_db, "CSCO")[0] == "BROKER_SYNC"

    @patch("scripts.sync_broker_state.BrokerReconciler")
    def test_short_position_never_attributed(self, MockReconciler, temp_db):
        """Shorts don't record an opening BUY intent — they keep the
        BROKER_SYNC fallback (negative shares preserved)."""
        rsi = _seed_strategy(temp_db, "RSI Mean Reversion")
        _seed_intent(temp_db, rsi, "NFLX", side="BUY", target_qty=24, days_ago=1)

        mock_rec = MockReconciler.return_value
        mock_rec.get_broker_state.return_value = _mock_broker_state({"NFLX": (-24, 700.0)})

        assert sync_broker_to_database(temp_db) is True
        assert _strategy_of(temp_db, "NFLX")[0] == "BROKER_SYNC"
        positions = _get_all_positions(temp_db)
        assert positions[0]["shares"] == -24.0

    @patch("scripts.sync_broker_state.BrokerReconciler")
    def test_exact_qty_match_preferred_over_recency(self, MockReconciler, temp_db):
        """When two strategies bought the same symbol recently, the intent
        whose target_qty matches the broker position wins over a newer
        different-qty intent."""
        rsi = _seed_strategy(temp_db, "RSI Mean Reversion")
        ma = _seed_strategy(temp_db, "MA Crossover")
        _seed_intent(temp_db, ma, "GIS", target_qty=88, days_ago=2)  # exact match, older
        _seed_intent(temp_db, rsi, "GIS", target_qty=30, days_ago=1)  # newer, wrong qty

        mock_rec = MockReconciler.return_value
        mock_rec.get_broker_state.return_value = _mock_broker_state({"GIS": (88, 55.10)})

        assert sync_broker_to_database(temp_db) is True
        assert _strategy_of(temp_db, "GIS")[0] == "MA Crossover"

    @patch("scripts.sync_broker_state.BrokerReconciler")
    def test_missing_order_intents_table_falls_back(self, MockReconciler, temp_db):
        """Older DBs without order_intents must not crash the sync."""
        conn = sqlite3.connect(temp_db)
        conn.execute("DROP TABLE order_intents")
        conn.commit()
        conn.close()

        mock_rec = MockReconciler.return_value
        mock_rec.get_broker_state.return_value = _mock_broker_state({"CSCO": (43, 68.42)})

        assert sync_broker_to_database(temp_db) is True
        assert _strategy_of(temp_db, "CSCO")[0] == "BROKER_SYNC"

    def test_find_entry_intent_rejects_short_qty(self, temp_db):
        """_find_entry_intent never matches a non-positive broker qty."""
        rsi = _seed_strategy(temp_db, "RSI Mean Reversion")
        _seed_intent(temp_db, rsi, "CSCO", target_qty=43, days_ago=1)
        conn = sqlite3.connect(temp_db)
        assert _find_entry_intent(conn.cursor(), "CSCO", -43) is None
        assert _find_entry_intent(conn.cursor(), "CSCO", 0) is None
        conn.close()
