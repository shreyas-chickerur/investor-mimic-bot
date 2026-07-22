#!/usr/bin/env python3
"""
Disabled-strategy wind-down tests.

initialize_strategies() filters disabled strategies out entirely, so their
open positions would never receive exit signals — only catastrophe stops.
The engine must emit DAY SELL (longs) / BUY-to-cover (shorts) for every
position whose strategy is inactive (excluding Cash Sweep, and BROKER_SYNC
longs — BROKER_SYNC *shorts* are always accidental and are covered).

Every wind-down order is clamped to the broker-confirmed quantity: the
June–July 2026 VZ incident sold the same phantom DB lot on ~12 consecutive
runs and left a real -26 short once DAY orders started filling.
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


def _broker_pos(symbol, qty):
    p = MagicMock()
    p.symbol = symbol
    p.qty = str(qty)
    p.market_value = "0"
    return p


def _set_broker_positions(engine, positions):
    """positions: list of (symbol, qty) the broker actually holds."""
    engine._test_client.get_all_positions.return_value = [
        _broker_pos(sym, qty) for sym, qty in positions
    ]


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
        _set_broker_positions(engine, [("XYZ", 10)])
        engine._winddown_inactive_strategy_positions([], _market_data({"XYZ": 100.0}))

        req = engine._test_client.submit_order.call_args.args[0]
        assert req.symbol == "XYZ"
        assert "sell" in str(req.side).lower()
        # DAY, not OPG: an OPG wind-down that misses the opening auction expires
        # and the position is restored next run (infinite non-close loop).
        assert "DAY" in str(req.time_in_force).upper()
        assert engine.db.get_position(dead_sid, "XYZ") is None

    def test_short_position_covered(self, engine):
        dead_sid = _create_strategy_row(engine, "Dead Pairs")
        engine.db.update_position(
            strategy_id=dead_sid, symbol="SHRT", shares=-8.0, avg_price=50.0, current_price=45.0
        )
        _set_broker_positions(engine, [("SHRT", -8)])
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
        _set_broker_positions(engine, [("SHRT", -8)])
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
        _set_broker_positions(engine, [("XYZ", 10)])
        engine._winddown_inactive_strategy_positions([], md)
        # restore the position row as if the fill hadn't trued up yet
        engine.db.update_position(
            strategy_id=dead_sid, symbol="XYZ", shares=10.0, avg_price=90.0, current_price=100.0
        )
        engine._winddown_inactive_strategy_positions([], md)
        assert engine._test_client.submit_order.call_count == 1


class TestWinddownBrokerClamp:
    """Regression: the June–July 2026 VZ over-sell.

    The wind-down sized orders from the LOCAL DB row. Expired/reversed fills
    kept restoring a phantom position, so the same lot was re-sold on ~12
    consecutive runs; once PR #60's DAY orders actually filled, the over-sells
    executed and left a real -26 VZ short at the broker under BROKER_SYNC.
    Every order must be clamped to broker-confirmed quantity, phantom rows
    trued instead of traded, and accidental BROKER_SYNC shorts covered.
    """

    def test_phantom_long_places_no_order_and_trues_row(self, engine):
        dead_sid = _create_strategy_row(engine, "Dead Strategy")
        engine.db.update_position(
            strategy_id=dead_sid, symbol="VZ", shares=25.0, avg_price=46.0, current_price=42.0
        )
        _set_broker_positions(engine, [])  # broker is flat — the row is phantom
        engine._winddown_inactive_strategy_positions([], _market_data({"VZ": 42.0}))

        assert engine._test_client.submit_order.call_count == 0
        assert engine.db.get_position(dead_sid, "VZ") is None  # trued to broker (flat)

    def test_phantom_restore_loop_never_resells(self, engine):
        """The exact VZ failure: row restored each run, broker already flat."""
        dead_sid = _create_strategy_row(engine, "Dead News Sentiment")
        md = _market_data({"VZ": 42.0})
        _set_broker_positions(engine, [])
        for _run in range(3):
            engine.db.update_position(
                strategy_id=dead_sid, symbol="VZ", shares=25.0, avg_price=46.0, current_price=42.0
            )
            engine._winddown_inactive_strategy_positions([], md)
        assert engine._test_client.submit_order.call_count == 0

    def test_oversized_row_clamped_to_broker_qty(self, engine):
        dead_sid = _create_strategy_row(engine, "Dead Strategy")
        engine.db.update_position(
            strategy_id=dead_sid, symbol="VZ", shares=25.0, avg_price=46.0, current_price=42.0
        )
        _set_broker_positions(engine, [("VZ", 13)])  # broker holds only 13
        engine._winddown_inactive_strategy_positions([], _market_data({"VZ": 42.0}))

        req = engine._test_client.submit_order.call_args.args[0]
        assert req.symbol == "VZ"
        assert float(req.qty) == 13.0  # clamped: never sell more than broker holds
        assert engine.db.get_position(dead_sid, "VZ") is None  # residual phantom trued away

    def test_broker_sync_short_is_covered(self, engine):
        """An accidental short adopted by the sync must be bought to cover."""
        bs_sid = _create_strategy_row(engine, "BROKER_SYNC")
        engine.db.update_position(
            strategy_id=bs_sid, symbol="VZ", shares=-26.0, avg_price=42.6, current_price=43.6
        )
        _set_broker_positions(engine, [("VZ", -26)])
        engine._winddown_inactive_strategy_positions([], _market_data({"VZ": 43.6}))

        req = engine._test_client.submit_order.call_args.args[0]
        assert req.symbol == "VZ"
        assert "buy" in str(req.side).lower()
        assert float(req.qty) == 26.0
        assert "DAY" in str(req.time_in_force).upper()
        assert engine.db.get_position(bs_sid, "VZ") is None

    def test_broker_sync_long_still_protected(self, engine):
        bs_sid = _create_strategy_row(engine, "BROKER_SYNC")
        engine.db.update_position(
            strategy_id=bs_sid, symbol="CSCO", shares=8.0, avg_price=113.0, current_price=114.0
        )
        _set_broker_positions(engine, [("CSCO", 8)])
        engine._winddown_inactive_strategy_positions([], _market_data({"CSCO": 114.0}))
        assert engine._test_client.submit_order.call_count == 0
        assert engine.db.get_position(bs_sid, "CSCO") is not None

    def test_broker_unavailable_skips_winddown_entirely(self, engine):
        dead_sid = _create_strategy_row(engine, "Dead Strategy")
        engine.db.update_position(
            strategy_id=dead_sid, symbol="XYZ", shares=10.0, avg_price=90.0, current_price=100.0
        )
        engine._test_client.get_all_positions.side_effect = RuntimeError("broker down")
        engine._winddown_inactive_strategy_positions([], _market_data({"XYZ": 100.0}))
        # Fail-safe: no blind orders, position untouched for a later run.
        assert engine._test_client.submit_order.call_count == 0
        assert engine.db.get_position(dead_sid, "XYZ") is not None

    def test_other_local_rows_claim_subtracted(self, engine):
        """Broker qty is net per symbol; another strategy's holding of the same
        symbol must not be sellable by the orphan's wind-down."""
        dead_sid = _create_strategy_row(engine, "Dead Strategy")
        live_sid = _create_strategy_row(engine, "Live Strategy")
        engine.db.update_position(
            strategy_id=dead_sid, symbol="XYZ", shares=10.0, avg_price=90.0, current_price=100.0
        )
        engine.db.update_position(
            strategy_id=live_sid, symbol="XYZ", shares=5.0, avg_price=95.0, current_price=100.0
        )
        # Broker net 10: 5 belong to the live strategy, so only 5 are the
        # orphan's to sell.
        _set_broker_positions(engine, [("XYZ", 10)])
        engine._winddown_inactive_strategy_positions(
            [_active_stub(live_sid)], _market_data({"XYZ": 100.0})
        )
        req = engine._test_client.submit_order.call_args.args[0]
        assert float(req.qty) == 5.0
        assert engine.db.get_position(live_sid, "XYZ") is not None


class TestStaleOrderCancellationOrdering:
    """Regression: _cancel_stale_orders must run BEFORE the defensive-exit phase.

    The wind-down (and stop-loss exits) place new OPG orders. If
    _cancel_stale_orders ran *after* them — as it did before 2026-06-19 — it
    cancelled the very wind-down SELL just submitted, which _reconcile_optimistic_fills
    then reversed as a "phantom", so a disabled strategy's position could never
    actually be wound down and re-tripped a reconciliation discrepancy every run
    (stranded VZ News-Sentiment position). Lock the ordering so it can't regress.
    """

    def test_cancel_runs_before_winddown_and_stoplosses(self):
        import inspect

        src = inspect.getsource(ee.MultiStrategyRunner.run_all_strategies)
        i_cancel = src.find("self._cancel_stale_orders(")
        i_reconcile = src.find("self._reconcile_optimistic_fills(")
        i_winddown = src.find("self._winddown_inactive_strategy_positions(")
        # Stop-loss checks were extracted into _run_defensive_stop_losses so the
        # duplicate-run guard's early-return branch can also invoke them
        # unconditionally (regression: stop-losses must fire even on a
        # detected duplicate run, since it may be the only pass today that
        # sees a price move past a stop level). That means the FIRST call
        # site in source order is the duplicate-guard's — intentionally
        # before _cancel_stale_orders. The ordering invariant this test
        # guards applies to the main-path call, i.e. the occurrence at/after
        # i_cancel.
        assert i_cancel != -1, "_cancel_stale_orders no longer called in run()"
        i_stops_guard = src.find("self._run_defensive_stop_losses(")
        assert i_stops_guard != -1, "stop-loss check no longer called in run()"
        assert i_stops_guard < i_cancel, (
            "duplicate-run guard must call _run_defensive_stop_losses before "
            "_cancel_stale_orders (it returns early and never reaches it)"
        )
        i_stops = src.find("self._run_defensive_stop_losses(", i_cancel)
        assert i_stops != -1, "main-path stop-loss check no longer called in run()"
        assert i_winddown != -1, "wind-down no longer called in run()"
        assert i_reconcile != -1, "_reconcile_optimistic_fills no longer called in run()"

        # Cancellation + optimistic-fill reconciliation must precede BOTH
        # defensive-exit phases so their freshly-placed orders survive.
        assert i_cancel < i_stops, "_cancel_stale_orders must run before stop-losses"
        assert i_cancel < i_winddown, "_cancel_stale_orders must run before wind-down"
        assert i_reconcile < i_winddown, "_reconcile_optimistic_fills must run before wind-down"
