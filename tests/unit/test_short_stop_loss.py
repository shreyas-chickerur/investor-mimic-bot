#!/usr/bin/env python3
"""
Short-selling correctness: direction-aware stop losses, short P&L sign,
and position-record cover semantics (pairs trading SHORT_SELL/BUY_TO_COVER).
"""
import sys
from pathlib import Path

import pytest

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.core.database import TradingDatabase
from src.core.execution_engine import MultiStrategyRunner
from src.risk.stop_loss_manager import StopLossManager


@pytest.fixture
def db(tmp_path):
    return TradingDatabase(db_path=str(tmp_path / "test.db"))


class TestShortStopLossManager:
    def setup_method(self):
        self.manager = StopLossManager(atr_multiplier=2.5)

    def test_short_stop_sits_above_entry(self):
        self.manager.set_stop_loss("BAC", entry_price=40.0, atr=1.0, direction="short")
        assert self.manager.get_stop_price("BAC") == pytest.approx(42.5)
        assert self.manager.get_direction("BAC") == "short"

    def test_short_stop_triggers_on_rise_not_fall(self):
        self.manager.set_stop_loss("BAC", entry_price=40.0, atr=1.0, direction="short")
        assert self.manager.check_stop_loss("BAC", 42.5) is True
        assert self.manager.check_stop_loss("BAC", 43.0) is True
        # Falling price is PROFIT for a short — must not trigger
        assert self.manager.check_stop_loss("BAC", 38.0) is False

    def test_short_stop_capped_at_150pct_of_entry(self):
        self.manager.set_stop_loss("BAC", entry_price=40.0, atr=50.0, direction="short")
        assert self.manager.get_stop_price("BAC") == pytest.approx(60.0)

    def test_short_stop_atr_fallback(self):
        # No ATR → 7% fallback, placed ABOVE entry for shorts
        self.manager.set_stop_loss("BAC", entry_price=40.0, atr=0.0, direction="short")
        assert self.manager.get_stop_price("BAC") == pytest.approx(40.0 * 1.175)

    def test_long_behavior_unchanged(self):
        self.manager.set_stop_loss("AAPL", entry_price=100.0, atr=2.0)
        assert self.manager.get_stop_price("AAPL") == pytest.approx(95.0)
        assert self.manager.get_direction("AAPL") == "long"
        assert self.manager.check_stop_loss("AAPL", 94.0) is True
        assert self.manager.check_stop_loss("AAPL", 96.0) is False

    def test_trailing_and_ratchet_are_noops_for_shorts(self):
        self.manager.set_stop_loss("BAC", entry_price=40.0, atr=1.0, direction="short")
        stop_before = self.manager.get_stop_price("BAC")
        self.manager.update_trailing_stop("BAC", current_price=35.0, atr=1.0)
        self.manager.update_ratchet_stop("BAC", current_price=35.0, atr=1.0)
        assert self.manager.get_stop_price("BAC") == stop_before

    def test_direction_persists_across_restart(self, db):
        m1 = StopLossManager(db=db)
        m1.set_stop_loss("BAC", entry_price=40.0, atr=1.0, direction="short")
        m1.set_stop_loss("AAPL", entry_price=100.0, atr=2.0)

        m2 = StopLossManager(db=db)
        assert m2.get_direction("BAC") == "short"
        assert m2.get_direction("AAPL") == "long"
        assert m2.check_stop_loss("BAC", 50.0) is True

    def test_audit_repairs_short_position_with_stop_above(self):
        positions = [{"symbol": "BAC", "shares": -25.0, "avg_price": 40.0, "atr": 0.0}]
        repaired = self.manager.audit_and_repair_stops(positions, {"BAC": 39.0})
        assert repaired == ["BAC"]
        assert self.manager.get_direction("BAC") == "short"
        assert self.manager.get_stop_price("BAC") > 40.0


class TestShortTradePnl:
    def test_profitable_short_records_positive_pnl(self, db):
        db.log_trade_pnl(
            strategy_id=1,
            strategy_name="Pairs Trading",
            symbol="BAC",
            sell_run_id="run1",
            entry_price=40.0,
            exit_price=36.0,
            shares=25.0,
            direction="short",
        )
        stats = db.get_strategy_pnl_stats(1)
        assert stats["trades"] == 1
        assert stats["win_rate"] == 1.0  # price fell → short won

        import sqlite3

        with sqlite3.connect(db.db_path) as conn:
            row = conn.execute(
                "SELECT gross_pnl, gross_pnl_pct, direction, tax_treatment " "FROM trade_pnl_detail"
            ).fetchone()
        assert row[0] == pytest.approx(100.0)  # (40-36)*25
        assert row[1] == pytest.approx(0.10)
        assert row[2] == "short"
        assert row[3] == "STCG"  # shorts are always short-term gains

    def test_losing_short_records_negative_pnl(self, db):
        db.log_trade_pnl(
            strategy_id=1,
            strategy_name="Pairs Trading",
            symbol="BAC",
            sell_run_id="run1",
            entry_price=40.0,
            exit_price=44.0,
            shares=25.0,
            direction="short",
        )
        import sqlite3

        with sqlite3.connect(db.db_path) as conn:
            row = conn.execute("SELECT gross_pnl, is_winner FROM trade_pnl_detail").fetchone()
        assert row[0] == pytest.approx(-100.0)
        assert row[1] == 0

    def test_long_pnl_unchanged(self, db):
        db.log_trade_pnl(
            strategy_id=1,
            strategy_name="RSI",
            symbol="AAPL",
            sell_run_id="run1",
            entry_price=100.0,
            exit_price=110.0,
            shares=10.0,
        )
        import sqlite3

        with sqlite3.connect(db.db_path) as conn:
            row = conn.execute("SELECT gross_pnl, direction FROM trade_pnl_detail").fetchone()
        assert row[0] == pytest.approx(100.0)
        assert row[1] == "long"


class _EngineStub:
    """Bare object exposing only what _update_position_record touches."""

    def __init__(self, db):
        self.db = db


class TestPositionRecordShorts:
    """_update_position_record cover/short semantics (tested via the unbound method)."""

    def _update(self, db, *args, **kwargs):
        MultiStrategyRunner._update_position_record(_EngineStub(db), *args, **kwargs)

    def _seed_short(self, db, shares=-100.0, avg=50.0):
        db.update_position(
            strategy_id=1, symbol="BAC", shares=shares, avg_price=avg, current_price=avg
        )

    def test_partial_cover_keeps_entry_price(self, db):
        self._seed_short(db)
        self._update(db, 1, "BAC", 40, 45.0)  # cover 40 of 100 at $45
        pos = db.get_position(1, "BAC")
        assert float(pos["shares"]) == pytest.approx(-60.0)
        assert float(pos["avg_price"]) == pytest.approx(50.0), "cover must not move entry price"

    def test_full_cover_deletes_position(self, db):
        self._seed_short(db)
        self._update(db, 1, "BAC", 100, 45.0)
        assert db.get_position(1, "BAC") is None

    def test_crossover_clamps_to_flat(self, db):
        self._seed_short(db)
        self._update(db, 1, "BAC", 150, 45.0)  # cover more than short size
        assert db.get_position(1, "BAC") is None, "must flatten, never flip long"

    def test_adding_to_short_recalculates_avg(self, db):
        self._seed_short(db, shares=-100.0, avg=50.0)
        self._update(db, 1, "BAC", -100, 40.0)  # short 100 more at $40
        pos = db.get_position(1, "BAC")
        assert float(pos["shares"]) == pytest.approx(-200.0)
        assert float(pos["avg_price"]) == pytest.approx(45.0)

    def test_long_semantics_unchanged(self, db):
        db.update_position(
            strategy_id=1, symbol="AAPL", shares=10.0, avg_price=100.0, current_price=100.0
        )
        self._update(db, 1, "AAPL", 10, 120.0)  # buy 10 more
        pos = db.get_position(1, "AAPL")
        assert float(pos["avg_price"]) == pytest.approx(110.0)
        self._update(db, 1, "AAPL", -5, 130.0)  # sell 5
        pos = db.get_position(1, "AAPL")
        assert float(pos["shares"]) == pytest.approx(15.0)
        assert float(pos["avg_price"]) == pytest.approx(110.0)
        self._update(db, 1, "AAPL", -15, 130.0)  # sell rest
        assert db.get_position(1, "AAPL") is None
