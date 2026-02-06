#!/usr/bin/env python3
"""
Tests for sync_broker_state.py corrective sync logic.

Verifies that the sync script correctly adjusts local positions to match
broker state without destructively wiping strategy-level tracking.
"""
import os
import sys
import sqlite3
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, Mock, MagicMock
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.sync_broker_state import (
    _get_local_positions,
    _get_or_create_broker_sync_strategy,
    sync_broker_to_database,
)


@pytest.fixture
def temp_db():
    """Create a temporary database with the required schema."""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    tmp.close()
    conn = sqlite3.connect(tmp.name)
    cursor = conn.cursor()

    cursor.execute('''CREATE TABLE strategies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        capital_allocation REAL DEFAULT 0.0,
        initial_capital REAL DEFAULT 0.0,
        status TEXT DEFAULT 'active'
    )''')

    cursor.execute('''CREATE TABLE positions (
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
    )''')

    cursor.execute('''CREATE TABLE broker_state (
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
    )''')

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
        (name, f'{name} strategy', capital),
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


def _get_all_positions(db_path):
    """Helper to read all positions from the database."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM positions WHERE shares > 0")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def _mock_broker_state(positions_dict, cash=50000.0, portfolio_value=100000.0):
    """Build a broker_state dict matching BrokerReconciler.get_broker_state() format."""
    return {
        'positions': {
            sym: {'qty': qty, 'avg_price': avg}
            for sym, (qty, avg) in positions_dict.items()
        },
        'cash': cash,
        'portfolio_value': portfolio_value,
        'buying_power': cash,
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
        sid = _seed_strategy(temp_db, 'RSI')
        _seed_position(temp_db, sid, 'AAPL', 10, 150.0)

        conn = sqlite3.connect(temp_db)
        result = _get_local_positions(conn.cursor())
        conn.close()

        assert 'AAPL' in result
        assert result['AAPL']['total'] == 10.0
        assert len(result['AAPL']['strategies']) == 1

    def test_multiple_strategies_same_symbol(self, temp_db):
        sid1 = _seed_strategy(temp_db, 'RSI')
        sid2 = _seed_strategy(temp_db, 'MA')
        _seed_position(temp_db, sid1, 'AAPL', 10, 150.0)
        _seed_position(temp_db, sid2, 'AAPL', 5, 155.0)

        conn = sqlite3.connect(temp_db)
        result = _get_local_positions(conn.cursor())
        conn.close()

        assert result['AAPL']['total'] == 15.0
        assert len(result['AAPL']['strategies']) == 2

    def test_zero_share_positions_excluded(self, temp_db):
        sid = _seed_strategy(temp_db, 'RSI')
        _seed_position(temp_db, sid, 'AAPL', 0, 150.0)

        conn = sqlite3.connect(temp_db)
        result = _get_local_positions(conn.cursor())
        conn.close()

        assert result == {}


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

    @patch('scripts.sync_broker_state.BrokerReconciler')
    def test_in_sync_no_changes(self, MockReconciler, temp_db):
        """When local matches broker, no changes should be made."""
        sid = _seed_strategy(temp_db, 'RSI')
        _seed_position(temp_db, sid, 'AAPL', 10, 150.0)

        mock_rec = MockReconciler.return_value
        mock_rec.get_broker_state.return_value = _mock_broker_state(
            {'AAPL': (10, 150.0)}
        )

        result = sync_broker_to_database(temp_db)
        assert result is True

        positions = _get_all_positions(temp_db)
        assert len(positions) == 1
        assert positions[0]['shares'] == 10.0

    @patch('scripts.sync_broker_state.BrokerReconciler')
    def test_new_broker_position_added_as_broker_sync(self, MockReconciler, temp_db):
        """A position in broker but not local should be added under BROKER_SYNC."""
        mock_rec = MockReconciler.return_value
        mock_rec.get_broker_state.return_value = _mock_broker_state(
            {'AAPL': (10, 150.0)}
        )

        result = sync_broker_to_database(temp_db)
        assert result is True

        positions = _get_all_positions(temp_db)
        assert len(positions) == 1
        assert positions[0]['symbol'] == 'AAPL'
        assert positions[0]['shares'] == 10.0

        # Verify it was assigned to BROKER_SYNC strategy
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT s.name FROM strategies s JOIN positions p ON s.id = p.strategy_id WHERE p.symbol = 'AAPL'"
        )
        name = cursor.fetchone()[0]
        conn.close()
        assert name == 'BROKER_SYNC'

    @patch('scripts.sync_broker_state.BrokerReconciler')
    def test_local_less_than_broker_adds_shares(self, MockReconciler, temp_db):
        """When local has fewer shares, the difference is added to the largest strategy."""
        sid = _seed_strategy(temp_db, 'RSI')
        _seed_position(temp_db, sid, 'AAPL', 8, 150.0)

        mock_rec = MockReconciler.return_value
        mock_rec.get_broker_state.return_value = _mock_broker_state(
            {'AAPL': (14, 152.0)}
        )

        result = sync_broker_to_database(temp_db)
        assert result is True

        positions = _get_all_positions(temp_db)
        total = sum(p['shares'] for p in positions if p['symbol'] == 'AAPL')
        assert total == 14.0

    @patch('scripts.sync_broker_state.BrokerReconciler')
    def test_local_more_than_broker_reduces_shares(self, MockReconciler, temp_db):
        """When local has more shares, excess is removed from the largest strategy."""
        sid = _seed_strategy(temp_db, 'RSI')
        _seed_position(temp_db, sid, 'AAPL', 20, 150.0)

        mock_rec = MockReconciler.return_value
        mock_rec.get_broker_state.return_value = _mock_broker_state(
            {'AAPL': (14, 150.0)}
        )

        result = sync_broker_to_database(temp_db)
        assert result is True

        positions = _get_all_positions(temp_db)
        total = sum(p['shares'] for p in positions if p['symbol'] == 'AAPL')
        assert total == 14.0

    @patch('scripts.sync_broker_state.BrokerReconciler')
    def test_local_position_removed_when_not_in_broker(self, MockReconciler, temp_db):
        """Positions that exist locally but not in broker should be removed."""
        sid = _seed_strategy(temp_db, 'RSI')
        _seed_position(temp_db, sid, 'AAPL', 10, 150.0)
        _seed_position(temp_db, sid, 'MSFT', 5, 300.0)

        mock_rec = MockReconciler.return_value
        mock_rec.get_broker_state.return_value = _mock_broker_state(
            {'AAPL': (10, 150.0)}  # MSFT not in broker
        )

        result = sync_broker_to_database(temp_db)
        assert result is True

        positions = _get_all_positions(temp_db)
        symbols = [p['symbol'] for p in positions]
        assert 'AAPL' in symbols
        assert 'MSFT' not in symbols

    @patch('scripts.sync_broker_state.BrokerReconciler')
    def test_reduce_removes_position_when_zero(self, MockReconciler, temp_db):
        """When broker has 0 for a symbol that exists locally, position is deleted."""
        sid = _seed_strategy(temp_db, 'RSI')
        _seed_position(temp_db, sid, 'AAPL', 10, 150.0)

        mock_rec = MockReconciler.return_value
        # Broker has no AAPL at all
        mock_rec.get_broker_state.return_value = _mock_broker_state({})

        result = sync_broker_to_database(temp_db)
        assert result is True

        positions = _get_all_positions(temp_db)
        assert len(positions) == 0

    @patch('scripts.sync_broker_state.BrokerReconciler')
    def test_multi_strategy_adds_to_largest(self, MockReconciler, temp_db):
        """When multiple strategies hold a symbol, shares are added to the largest."""
        sid1 = _seed_strategy(temp_db, 'RSI')
        sid2 = _seed_strategy(temp_db, 'MA')
        _seed_position(temp_db, sid1, 'AAPL', 5, 150.0)
        _seed_position(temp_db, sid2, 'AAPL', 10, 155.0)  # MA has more

        mock_rec = MockReconciler.return_value
        mock_rec.get_broker_state.return_value = _mock_broker_state(
            {'AAPL': (20, 152.0)}
        )

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
        ma_shares = cursor.fetchone()['shares']
        conn.close()

        assert ma_shares == 15.0

    @patch('scripts.sync_broker_state.BrokerReconciler')
    def test_broker_state_failure_returns_false(self, MockReconciler, temp_db):
        """If broker state can't be fetched, sync should return False."""
        mock_rec = MockReconciler.return_value
        mock_rec.get_broker_state.return_value = {}

        result = sync_broker_to_database(temp_db)
        assert result is False

    @patch('scripts.sync_broker_state.BrokerReconciler')
    def test_sync_records_broker_state_entry(self, MockReconciler, temp_db):
        """Sync should record a SYNC entry in broker_state table."""
        mock_rec = MockReconciler.return_value
        mock_rec.get_broker_state.return_value = _mock_broker_state(
            {'AAPL': (10, 150.0)}
        )

        sync_broker_to_database(temp_db)

        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT run_id, snapshot_type, reconciliation_status FROM broker_state"
        )
        row = cursor.fetchone()
        conn.close()

        assert row is not None
        assert row[0] == 'AUTO_SYNC'
        assert row[1] == 'SYNC'
        assert row[2] == 'SYNCED'

    @patch('scripts.sync_broker_state.BrokerReconciler')
    def test_complex_multi_symbol_sync(self, MockReconciler, temp_db):
        """Test a realistic scenario with multiple symbols and strategies."""
        sid1 = _seed_strategy(temp_db, 'RSI')
        sid2 = _seed_strategy(temp_db, 'MA')

        # Local state
        _seed_position(temp_db, sid1, 'AAPL', 10, 150.0)   # matches broker
        _seed_position(temp_db, sid2, 'AAPL', 4, 155.0)     # total 14, broker has 14
        _seed_position(temp_db, sid1, 'MSFT', 20, 300.0)    # local only, not in broker
        _seed_position(temp_db, sid2, 'ADBE', 6, 500.0)     # broker has 12

        mock_rec = MockReconciler.return_value
        mock_rec.get_broker_state.return_value = _mock_broker_state({
            'AAPL': (14, 152.0),   # matches local total
            'ADBE': (12, 510.0),   # local has 6, need +6
            'PG': (13, 160.0),     # new, not in local
        })

        result = sync_broker_to_database(temp_db)
        assert result is True

        positions = _get_all_positions(temp_db)
        by_symbol = {}
        for p in positions:
            by_symbol.setdefault(p['symbol'], 0)
            by_symbol[p['symbol']] += p['shares']

        assert by_symbol.get('AAPL') == 14.0
        assert by_symbol.get('ADBE') == 12.0
        assert by_symbol.get('PG') == 13.0
        assert 'MSFT' not in by_symbol  # removed
