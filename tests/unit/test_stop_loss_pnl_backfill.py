#!/usr/bin/env python3
"""
Tests for the one-off stop-loss trades.pnl backfill migration
(TradingDatabase._backfill_stop_loss_trade_pnl).

Background (2026-07-27 audit, PR #65): the stop-loss exit path recorded
realized P&L into trade_pnl_detail but called log_trade without pnl, leaving
trades.pnl NULL. performance_tracker and check_live_readiness.py read
trades.pnl, so every stop-loss LOSS was invisible to win-rate / profit-factor
and the readiness gate over-counted the record. This migration copies gross_pnl
from the matching trade_pnl_detail row (keyed on sell_run_id/strategy_id/symbol)
into the NULL exit trades, leaving unmatched exits (sync-churn / wind-down with
no basis) and entries untouched.
"""
import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.database import TradingDatabase

FLAG = TradingDatabase._STOP_LOSS_PNL_BACKFILL_FLAG


@pytest.fixture
def db_path(tmp_path):
    """A real-schema DB (first init sets the migration flag on the empty DB)."""
    path = str(tmp_path / "trading.db")
    TradingDatabase(db_path=path)
    return path


def _seed_strategy(db_path, name, sid):
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO strategies (id, name, capital_allocation, initial_capital) "
        "VALUES (?, ?, 0.2, 20000.0)",
        (sid, name),
    )
    conn.commit()
    conn.close()


def _seed_trade(db_path, run_id, sid, symbol, action, shares, pnl=None):
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO trades (run_id, strategy_id, symbol, action, shares, "
        "requested_price, exec_price, slippage_cost, commission_cost, "
        "total_cost, notional, order_id, executed_at, pnl) "
        "VALUES (?, ?, ?, ?, ?, 0, 0, 0, 0, 0, 0, 'ord', datetime('now'), ?)",
        (run_id, sid, symbol, action, shares, pnl),
    )
    conn.commit()
    conn.close()


def _seed_pnl_detail(db_path, run_id, sid, symbol, gross_pnl, direction="long"):
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO trade_pnl_detail (strategy_id, strategy_name, symbol, "
        "sell_run_id, exit_date, entry_price, exit_price, shares, gross_pnl, "
        "gross_pnl_pct, exit_reason, is_winner, direction) "
        "VALUES (?, 'S', ?, ?, '2026-07-17', 100, 90, 1, ?, -0.1, 'STOP_LOSS', ?, ?)",
        (sid, symbol, run_id, gross_pnl, 1 if gross_pnl > 0 else 0, direction),
    )
    conn.commit()
    conn.close()


def _clear_flag_and_migrate(db_path):
    """Simulate the production artifact DB: NULL exits exist, flag not yet set."""
    conn = sqlite3.connect(db_path)
    conn.execute("DELETE FROM system_state WHERE key = ?", (FLAG,))
    conn.commit()
    conn.close()
    TradingDatabase(db_path=db_path)


def _pnl(db_path, symbol, action="SELL"):
    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT pnl FROM trades WHERE symbol = ? AND action = ?", (symbol, action)
    ).fetchone()
    conn.close()
    return row[0] if row else "MISSING"


def _flag_value(db_path):
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT value FROM system_state WHERE key = ?", (FLAG,)).fetchone()
    conn.close()
    return json.loads(row[0]) if row else None


class TestStopLossPnlBackfill:
    def test_matched_exit_gets_pnl(self, db_path):
        """The production shape: MU stop-loss SELL with NULL pnl in trades but a
        -301.67 loss in trade_pnl_detail is backfilled to -301.67."""
        _seed_strategy(db_path, "Factor Momentum", 4)
        _seed_trade(db_path, "run_mu", 4, "MU", "SELL", 1, pnl=None)
        _seed_pnl_detail(db_path, "run_mu", 4, "MU", -301.67)

        _clear_flag_and_migrate(db_path)

        assert _pnl(db_path, "MU") == pytest.approx(-301.67)
        flag = _flag_value(db_path)
        assert flag is not None
        assert flag["backfilled"] == [{"symbol": "MU", "pnl": -301.67}]

    def test_unmatched_exit_stays_null(self, db_path):
        """A SELL with no matching trade_pnl_detail row (sync-churn / wind-down
        with no basis) is left NULL — it represents no realized round-trip."""
        _seed_strategy(db_path, "RSI Mean Reversion", 5)
        _seed_trade(db_path, "run_churn", 5, "QCOM", "SELL", 5, pnl=None)

        _clear_flag_and_migrate(db_path)

        assert _pnl(db_path, "QCOM") is None

    def test_entry_buy_never_touched(self, db_path):
        """A BUY entry legitimately has NULL pnl even if a same-run detail row
        exists for the symbol — entries are excluded from the backfill."""
        _seed_strategy(db_path, "RSI Mean Reversion", 5)
        _seed_trade(db_path, "run_x", 5, "MU", "BUY", 1, pnl=None)
        _seed_pnl_detail(db_path, "run_x", 5, "MU", 50.0)

        _clear_flag_and_migrate(db_path)

        assert _pnl(db_path, "MU", action="BUY") is None

    def test_existing_pnl_not_overwritten(self, db_path):
        """A winning SELL that already recorded pnl must be left as-is."""
        _seed_strategy(db_path, "RSI Mean Reversion", 5)
        _seed_trade(db_path, "run_w", 5, "PSX", "SELL", 3, pnl=116.91)
        _seed_pnl_detail(db_path, "run_w", 5, "PSX", 999.0)  # should NOT be applied

        _clear_flag_and_migrate(db_path)

        assert _pnl(db_path, "PSX") == pytest.approx(116.91)

    def test_migration_runs_once(self, db_path):
        """After the flag is set, a later NULL exit is NOT retroactively filled."""
        _seed_strategy(db_path, "Factor Momentum", 4)
        _seed_trade(db_path, "run_mu", 4, "MU", "SELL", 1, pnl=None)
        _seed_pnl_detail(db_path, "run_mu", 4, "MU", -301.67)
        _clear_flag_and_migrate(db_path)
        assert _pnl(db_path, "MU") == pytest.approx(-301.67)

        # New NULL exit appears; re-init must NOT touch it (flag already set).
        _seed_strategy(db_path, "MA Crossover", 7)
        _seed_trade(db_path, "run_hd", 7, "HD", "SELL", 1, pnl=None)
        _seed_pnl_detail(db_path, "run_hd", 7, "HD", -26.31)
        TradingDatabase(db_path=db_path)
        assert _pnl(db_path, "HD") is None

    def test_fresh_db_sets_flag_without_rows(self, db_path):
        """An empty DB still records the flag so the migration never re-runs."""
        # db_path fixture already ran init once on the empty DB.
        assert _flag_value(db_path) is not None
