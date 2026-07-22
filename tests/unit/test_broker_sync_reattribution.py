#!/usr/bin/env python3
"""
Tests for the one-off BROKER_SYNC orphan re-attribution migration
(TradingDatabase._reattribute_broker_sync_orphans).

Background (2026-07-21 audit): after PR #60 switched entries to DAY
marketable limits, orders fill intraday AFTER the pre-market run ends. When
the optimistic local position was lost before the next sync, the fill was
adopted under BROKER_SYNC with the adoption date as entry_date — orphaned
from its strategy's exit logic (CSCO/QCOM from RSI, GIS from Earnings Drift;
11/16 position slots were orphans, causing 129 max_positions_reached
rejections in 2 weeks). The migration joins the orphans back to the
historical order_intents that bought them.
"""
import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.database import TradingDatabase

FLAG = TradingDatabase._ORPHAN_REATTRIBUTION_FLAG


@pytest.fixture
def db_path(tmp_path):
    """A real-schema DB (first init sets the migration flag on the empty DB)."""
    path = str(tmp_path / "trading.db")
    TradingDatabase(db_path=path)
    return path


def _seed(db_path, sql, params=()):
    conn = sqlite3.connect(db_path)
    conn.execute(sql, params)
    conn.commit()
    conn.close()


def _seed_strategy(db_path, name, sid=None):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    if sid is not None:
        cur.execute(
            "INSERT INTO strategies (id, name, capital_allocation, initial_capital) "
            "VALUES (?, ?, 0.2, 20000.0)",
            (sid, name),
        )
    else:
        cur.execute(
            "INSERT INTO strategies (name, capital_allocation, initial_capital) "
            "VALUES (?, 0.2, 20000.0)",
            (name,),
        )
        sid = cur.lastrowid
    conn.commit()
    conn.close()
    return sid


def _seed_position(db_path, sid, symbol, shares, avg_price, entry_date):
    _seed(
        db_path,
        "INSERT INTO positions (strategy_id, symbol, shares, avg_price, entry_date, "
        " last_updated) VALUES (?, ?, ?, ?, ?, '2026-07-08T05:55:00')",
        (sid, symbol, shares, avg_price, entry_date),
    )


def _seed_intent(
    db_path,
    sid,
    symbol,
    target_qty,
    created_at,
    side="BUY",
    status="FILLED",
    intent_id=None,
):
    _seed(
        db_path,
        "INSERT INTO order_intents (intent_id, run_id, strategy_id, symbol, side, "
        " target_qty, status, created_at, submitted_at, filled_at) "
        "VALUES (?, '20260707_055001_test', ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            intent_id or f"intent_{sid}_{symbol}_{created_at}",
            sid,
            symbol,
            side,
            target_qty,
            status,
            created_at,
            created_at,
            created_at if status == "FILLED" else None,
        ),
    )


def _clear_flag_and_migrate(db_path):
    """Simulate the production artifact DB: orphans exist, flag not yet set."""
    _seed(db_path, "DELETE FROM system_state WHERE key = ?", (FLAG,))
    TradingDatabase(db_path=db_path)


def _position(db_path, symbol):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = [
        dict(r)
        for r in conn.execute(
            "SELECT p.*, s.name AS strategy_name FROM positions p "
            "JOIN strategies s ON s.id = p.strategy_id WHERE p.symbol = ?",
            (symbol,),
        ).fetchall()
    ]
    conn.close()
    return rows


def _flag_value(db_path):
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT value FROM system_state WHERE key = ?", (FLAG,)).fetchone()
    conn.close()
    return json.loads(row[0]) if row else None


class TestOrphanReattribution:
    def test_orphan_moved_to_intent_strategy_with_fill_date(self, db_path):
        """The 2026-07-08 production shape: CSCO bought by RSI on 07-07,
        adopted as a BROKER_SYNC orphan on 07-08. Must move back to RSI with
        the intent's fill date as entry_date and the broker basis preserved."""
        rsi = _seed_strategy(db_path, "RSI Mean Reversion")
        sync = _seed_strategy(db_path, "BROKER_SYNC")
        _seed_position(db_path, sync, "CSCO", 43, 68.42, "2026-07-08")
        _seed_intent(db_path, rsi, "CSCO", 43, "2026-07-07 05:50:00")

        _clear_flag_and_migrate(db_path)

        rows = _position(db_path, "CSCO")
        assert len(rows) == 1
        assert rows[0]["strategy_name"] == "RSI Mean Reversion"
        assert rows[0]["entry_date"] == "2026-07-07"
        assert rows[0]["avg_price"] == pytest.approx(68.42)
        assert rows[0]["shares"] == pytest.approx(43)

        flag = _flag_value(db_path)
        assert flag is not None
        assert len(flag["moves"]) == 1
        assert flag["moves"][0]["symbol"] == "CSCO"

    def test_orphan_merged_into_existing_strategy_row(self, db_path):
        """If the strategy already holds some shares, the orphan merges in:
        summed shares, weighted basis, earlier entry_date, orphan row gone."""
        rsi = _seed_strategy(db_path, "RSI Mean Reversion")
        sync = _seed_strategy(db_path, "BROKER_SYNC")
        _seed_position(db_path, rsi, "QCOM", 10, 150.0, "2026-07-01")
        _seed_position(db_path, sync, "QCOM", 30, 160.0, "2026-07-08")
        _seed_intent(db_path, rsi, "QCOM", 30, "2026-07-07 05:50:00")

        _clear_flag_and_migrate(db_path)

        rows = _position(db_path, "QCOM")
        assert len(rows) == 1
        assert rows[0]["strategy_name"] == "RSI Mean Reversion"
        assert rows[0]["shares"] == pytest.approx(40)
        # (10*150 + 30*160) / 40 = 157.50
        assert rows[0]["avg_price"] == pytest.approx(157.50)
        assert rows[0]["entry_date"] == "2026-07-01"

    def test_orphan_without_intent_stays_broker_sync(self, db_path):
        """A genuinely manual/unknown position keeps the BROKER_SYNC fallback."""
        _seed_strategy(db_path, "RSI Mean Reversion")
        sync = _seed_strategy(db_path, "BROKER_SYNC")
        _seed_position(db_path, sync, "MYST", 5, 42.0, "2026-07-08")

        _clear_flag_and_migrate(db_path)

        rows = _position(db_path, "MYST")
        assert rows[0]["strategy_name"] == "BROKER_SYNC"
        assert _flag_value(db_path)["moves"] == []

    def test_intent_outside_window_ignored(self, db_path):
        """Intents created after adoption, or more than the window before it,
        must not claim the orphan."""
        rsi = _seed_strategy(db_path, "RSI Mean Reversion")
        sync = _seed_strategy(db_path, "BROKER_SYNC")
        _seed_position(db_path, sync, "GIS", 88, 55.10, "2026-07-08")
        _seed_intent(db_path, rsi, "GIS", 88, "2026-06-25 05:50:00")  # too old
        _seed_intent(db_path, rsi, "GIS", 88, "2026-07-10 05:50:00")  # after adoption

        _clear_flag_and_migrate(db_path)

        assert _position(db_path, "GIS")[0]["strategy_name"] == "BROKER_SYNC"

    def test_short_orphan_untouched(self, db_path):
        """Shorts (negative shares) have no opening BUY intent — never moved."""
        rsi = _seed_strategy(db_path, "RSI Mean Reversion")
        sync = _seed_strategy(db_path, "BROKER_SYNC")
        _seed_position(db_path, sync, "NFLX", -24, 700.0, "2026-07-08")
        _seed_intent(db_path, rsi, "NFLX", 24, "2026-07-07 05:50:00")

        _clear_flag_and_migrate(db_path)

        rows = _position(db_path, "NFLX")
        assert rows[0]["strategy_name"] == "BROKER_SYNC"
        assert rows[0]["shares"] == pytest.approx(-24)

    def test_exact_qty_match_preferred(self, db_path):
        """With two candidate intents in the window, the exact-qty match wins
        even when the other is more recent."""
        rsi = _seed_strategy(db_path, "RSI Mean Reversion")
        drift = _seed_strategy(db_path, "Earnings Drift")
        sync = _seed_strategy(db_path, "BROKER_SYNC")
        _seed_position(db_path, sync, "GIS", 88, 55.10, "2026-07-08")
        _seed_intent(db_path, drift, "GIS", 88, "2026-07-06 05:50:00")  # exact, older
        _seed_intent(db_path, rsi, "GIS", 12, "2026-07-07 05:50:00")  # newer, wrong qty

        _clear_flag_and_migrate(db_path)

        assert _position(db_path, "GIS")[0]["strategy_name"] == "Earnings Drift"

    def test_migration_runs_once(self, db_path):
        """The flag makes the repair one-shot: a matching intent seeded AFTER
        the migration ran must not move later BROKER_SYNC rows on re-init."""
        rsi = _seed_strategy(db_path, "RSI Mean Reversion")
        sync = _seed_strategy(db_path, "BROKER_SYNC")
        _clear_flag_and_migrate(db_path)  # runs with nothing to move, sets flag

        _seed_position(db_path, sync, "CSCO", 43, 68.42, "2026-07-08")
        _seed_intent(db_path, rsi, "CSCO", 43, "2026-07-07 05:50:00")
        TradingDatabase(db_path=db_path)  # re-init: flag present, no migration

        assert _position(db_path, "CSCO")[0]["strategy_name"] == "BROKER_SYNC"

    def test_fresh_db_sets_flag_without_orphans(self, db_path):
        """A fresh DB (no BROKER_SYNC strategy at all) records the flag."""
        assert _flag_value(db_path) is not None
        assert _flag_value(db_path)["moves"] == []

    def test_production_shape_multiple_orphans(self, db_path):
        """The actual 2026-07-07 incident: CSCO+QCOM from RSI (strategy 1),
        GIS from Earnings Drift (strategy 3), all sitting under BROKER_SYNC
        (strategy 5) with entry_date 2026-07-08."""
        rsi = _seed_strategy(db_path, "RSI Mean Reversion", sid=1)
        drift = _seed_strategy(db_path, "Earnings Drift", sid=3)
        sync = _seed_strategy(db_path, "BROKER_SYNC", sid=5)
        for sym, qty, px, strat in [
            ("CSCO", 43, 68.42, rsi),
            ("QCOM", 18, 158.30, rsi),
            ("GIS", 88, 55.10, drift),
        ]:
            _seed_position(db_path, sync, sym, qty, px, "2026-07-08")
            _seed_intent(db_path, strat, sym, qty, "2026-07-07 05:50:00")

        _clear_flag_and_migrate(db_path)

        assert _position(db_path, "CSCO")[0]["strategy_name"] == "RSI Mean Reversion"
        assert _position(db_path, "QCOM")[0]["strategy_name"] == "RSI Mean Reversion"
        assert _position(db_path, "GIS")[0]["strategy_name"] == "Earnings Drift"
        conn = sqlite3.connect(db_path)
        remaining = conn.execute(
            "SELECT COUNT(*) FROM positions WHERE strategy_id = ?", (sync,)
        ).fetchone()[0]
        conn.close()
        assert remaining == 0
        assert len(_flag_value(db_path)["moves"]) == 3
