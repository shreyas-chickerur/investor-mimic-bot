#!/usr/bin/env python3
"""
Disabled-strategy wind-down tests.

initialize_strategies() filters disabled strategies out entirely, so their
open positions would never receive exit signals — only catastrophe stops.
The engine must emit OPG SELL (longs) / BUY-to-cover (shorts) for every
position whose strategy is inactive (excluding BROKER_SYNC and Cash Sweep).
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import src.core.execution_engine as ee  # noqa: E402


def _fake_account():
    account = MagicMock()
    account.portfolio_value = "96000"
    account.cash = "50000"
    account.buying_power = "192000"
    return account


def _fake_order(order_id="wd-ord-1"):
    order = MagicMock()
    order.id = order_id
    order.status = "accepted"
    order.filled_qty = None
    order.filled_avg_price = None
    return order


@pytest.fixture
def engine(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ALPACA_API_KEY", "test_key")  # pragma: allowlist secret
    monkeypatch.setenv("ALPACA_SECRET_KEY", "test_secret")  # pragma: allowlist secret
    monkeypatch.setenv("ALPACA_PAPER", "true")
    monkeypatch.setenv("DRY_RUN", "false")

    fake_client = MagicMock()
    fake_client.get_account.return_value = _fake_account()
    fake_client.get_all_positions.return_value = []
    fake_client.get_orders.return_value = []
    fake_client.submit_order.return_value = _fake_order()

    monkeypatch.setattr(ee, "TradingClient", lambda *a, **k: fake_client)
    monkeypatch.setattr(
        "src.risk.broker_reconciler.TradingClient", lambda *a, **k: fake_client, raising=False
    )
    runner = ee.MultiStrategyRunner()
    runner._test_client = fake_client
    runner.asof_date = "2026-06-12"
    return runner


def _create_strategy_row(engine, name):
    import sqlite3

    conn = sqlite3.connect(engine.db.db_path)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO strategies (name, description, capital_allocation, initial_capital, status)"
        " VALUES (?, 'test', 0, 0, 'active')",
        (name,),
    )
    conn.commit()
    sid = cur.lastrowid
    conn.close()
    return sid


def _market_data(symbols_prices: dict) -> pd.DataFrame:
    dates = pd.bdate_range("2026-06-01", periods=10)
    frames = []
    for sym, px in symbols_prices.items():
        frames.append(pd.DataFrame({"symbol": sym, "close": px}, index=dates))
    return pd.concat(frames).sort_index()


def _active_stub(sid):
    s = MagicMock()
    s.strategy_id = sid
    return s


class TestWinddown:
    def test_long_position_of_inactive_strategy_sold(self, engine):
        dead_sid = _create_strategy_row(engine, "Dead Strategy")
        engine.db.update_position(
            strategy_id=dead_sid, symbol="XYZ", shares=10.0, avg_price=90.0, current_price=100.0
        )
        engine._winddown_inactive_strategy_positions([], _market_data({"XYZ": 100.0}))

        req = engine._test_client.submit_order.call_args.args[0]
        assert req.symbol == "XYZ"
        assert "sell" in str(req.side).lower()
        assert "OPG" in str(req.time_in_force).upper()
        assert engine.db.get_position(dead_sid, "XYZ") is None

    def test_short_position_covered(self, engine):
        dead_sid = _create_strategy_row(engine, "Dead Pairs")
        engine.db.update_position(
            strategy_id=dead_sid, symbol="SHRT", shares=-8.0, avg_price=50.0, current_price=45.0
        )
        engine._winddown_inactive_strategy_positions([], _market_data({"SHRT": 45.0}))

        req = engine._test_client.submit_order.call_args.args[0]
        assert req.symbol == "SHRT"
        assert "buy" in str(req.side).lower()
        assert engine.db.get_position(dead_sid, "SHRT") is None

    def test_winddown_records_pnl_with_direction(self, engine):
        dead_sid = _create_strategy_row(engine, "Dead Pairs")
        engine.db.update_position(
            strategy_id=dead_sid, symbol="SHRT", shares=-8.0, avg_price=50.0, current_price=45.0
        )
        engine._winddown_inactive_strategy_positions([], _market_data({"SHRT": 45.0}))

        import sqlite3

        conn = sqlite3.connect(engine.db.db_path)
        row = conn.execute(
            "SELECT direction, exit_reason FROM trade_pnl_detail WHERE strategy_id=?",
            (dead_sid,),
        ).fetchone()
        conn.close()
        assert row is not None
        assert row[0].lower() == "short"
        assert "wind-down" in row[1]

    def test_active_strategy_positions_untouched(self, engine):
        live_sid = _create_strategy_row(engine, "Live Strategy")
        engine.db.update_position(
            strategy_id=live_sid, symbol="KEEP", shares=5.0, avg_price=10.0, current_price=11.0
        )
        engine._winddown_inactive_strategy_positions(
            [_active_stub(live_sid)], _market_data({"KEEP": 11.0})
        )
        assert engine._test_client.submit_order.call_count == 0
        assert engine.db.get_position(live_sid, "KEEP") is not None

    def test_broker_sync_and_sweep_protected(self, engine):
        bs_sid = _create_strategy_row(engine, "BROKER_SYNC")
        sweep_sid = engine._sweep_strategy_id()
        engine.db.update_position(
            strategy_id=bs_sid, symbol="BSYM", shares=3.0, avg_price=10.0, current_price=10.0
        )
        engine.db.update_position(
            strategy_id=sweep_sid, symbol="SPY", shares=100.0, avg_price=500.0, current_price=500.0
        )
        engine._winddown_inactive_strategy_positions([], _market_data({"BSYM": 10.0, "SPY": 500.0}))
        assert engine._test_client.submit_order.call_count == 0

    def test_missing_market_data_defers(self, engine):
        dead_sid = _create_strategy_row(engine, "Dead Strategy")
        engine.db.update_position(
            strategy_id=dead_sid, symbol="NODATA", shares=10.0, avg_price=90.0, current_price=95.0
        )
        engine._winddown_inactive_strategy_positions([], _market_data({"OTHER": 50.0}))
        assert engine._test_client.submit_order.call_count == 0
        assert engine.db.get_position(dead_sid, "NODATA") is not None  # deferred, not deleted

    def test_idempotent_within_day(self, engine):
        dead_sid = _create_strategy_row(engine, "Dead Strategy")
        engine.db.update_position(
            strategy_id=dead_sid, symbol="XYZ", shares=10.0, avg_price=90.0, current_price=100.0
        )
        md = _market_data({"XYZ": 100.0})
        engine._winddown_inactive_strategy_positions([], md)
        # restore the position row as if the fill hadn't trued up yet
        engine.db.update_position(
            strategy_id=dead_sid, symbol="XYZ", shares=10.0, avg_price=90.0, current_price=100.0
        )
        engine._winddown_inactive_strategy_positions([], md)
        assert engine._test_client.submit_order.call_count == 1
