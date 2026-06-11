#!/usr/bin/env python3
"""
Cash sweep tests: idle cash flows into the core index sleeve (SPY) after
strategies trade; the sleeve sells down when cash falls below the buffer.

Built on the order-path harness pattern (real engine + DB, mocked broker).
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import src.core.execution_engine as ee  # noqa: E402


def _fake_account(pv="96000", cash="92000", buying_power="192000"):
    account = MagicMock()
    account.portfolio_value = pv
    account.cash = cash
    account.buying_power = buying_power
    return account


def _fake_order(order_id="sweep-ord-1", status="accepted"):
    order = MagicMock()
    order.id = order_id
    order.status = status
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
    fake_client.get_order_by_id.return_value = _fake_order(status="accepted")

    monkeypatch.setattr(ee, "TradingClient", lambda *a, **k: fake_client)
    monkeypatch.setattr(
        "src.risk.broker_reconciler.TradingClient", lambda *a, **k: fake_client, raising=False
    )
    runner = ee.MultiStrategyRunner()
    runner._test_client = fake_client
    runner.asof_date = "2026-06-11"
    runner._current_vix = 18.0
    runner._typical_prices = {"SPY": 500.0}
    return runner


PRICES = {"SPY": 500.0}


def _sweep_position(engine):
    sid = engine._sweep_strategy_id()
    return engine.db.get_position(sid, "SPY")


class TestSweepBuy:
    def test_idle_cash_buys_spy_opg(self, engine):
        # cash 92k, equity 96k, buffer 15% = 14.4k → investable ≈ 77.6k
        engine._execute_cash_sweep(PRICES)

        order_call = engine._test_client.submit_order.call_args
        assert order_call is not None, "sweep should have submitted a BUY"
        req = order_call.args[0] if order_call.args else order_call.kwargs["order_data"]
        assert req.symbol == "SPY"
        assert str(req.side).endswith("BUY") or "buy" in str(req.side).lower()
        assert "OPG" in str(req.time_in_force).upper() or "opg" in str(req.time_in_force)

        pos = _sweep_position(engine)
        assert pos is not None
        # limit = 500 * 1.01 = 505; investable = (92000 - 14400) = 77600 → 153 shares
        assert pos["shares"] == pytest.approx(int(77600 // 505))

    def test_no_buy_when_cash_at_buffer(self, engine):
        engine._test_client.get_account.return_value = _fake_account(cash="14000")
        engine._execute_cash_sweep(PRICES)
        assert engine._test_client.submit_order.call_count == 0
        assert _sweep_position(engine) is None

    def test_pending_opg_buys_reduce_investable(self, engine):
        engine._pending_opg_value = 80_000.0  # strategies already spent the cash
        engine._execute_cash_sweep(PRICES)
        assert engine._test_client.submit_order.call_count == 0

    def test_vix_above_35_disables_buys(self, engine):
        engine._current_vix = 40.0
        engine._execute_cash_sweep(PRICES)
        assert engine._test_client.submit_order.call_count == 0

    def test_vix_25_to_35_halves_size(self, engine):
        engine._current_vix = 28.0
        engine._execute_cash_sweep(PRICES)
        pos = _sweep_position(engine)
        assert pos is not None
        assert pos["shares"] == pytest.approx(int((77600 * 0.5) // 505))

    def test_kill_switch_skips_sweep(self, engine):
        engine.kill_switch.is_killed = True
        engine._execute_cash_sweep(PRICES)
        assert engine._test_client.submit_order.call_count == 0

    def test_disabled_by_config(self, engine, monkeypatch):
        monkeypatch.setattr(
            engine.config,
            "get",
            lambda key, default=None: False if key == "sweep.enabled" else default,
        )
        engine._execute_cash_sweep(PRICES)
        assert engine._test_client.submit_order.call_count == 0

    def test_idempotent_within_day(self, engine):
        engine._execute_cash_sweep(PRICES)
        first_shares = _sweep_position(engine)["shares"]
        engine._pending_opg_value = 0.0  # pretend a fresh look at the same day
        engine._execute_cash_sweep(PRICES)
        assert engine._test_client.submit_order.call_count == 1
        assert _sweep_position(engine)["shares"] == first_shares


class TestSweepSell:
    def _seed_sleeve(self, engine, shares=100.0, avg_price=480.0):
        sid = engine._sweep_strategy_id()
        engine.db.update_position(
            strategy_id=sid,
            symbol="SPY",
            shares=shares,
            avg_price=avg_price,
            current_price=500.0,
            entry_date="2026-06-01",
        )
        return sid

    def test_low_cash_sells_sleeve_to_restore_buffer(self, engine):
        sid = self._seed_sleeve(engine)
        # cash 2k << buffer/2 (7.2k) → sell ~ (14400-2000)/495 + 1 = 26 shares
        engine._test_client.get_account.return_value = _fake_account(cash="2000")
        engine._execute_cash_sweep(PRICES)

        order_call = engine._test_client.submit_order.call_args
        assert order_call is not None, "sweep should have submitted a SELL"
        req = order_call.args[0] if order_call.args else order_call.kwargs["order_data"]
        assert "sell" in str(req.side).lower()

        pos = engine.db.get_position(sid, "SPY")
        expected_sold = int((14400 - 2000) // round(500 * 0.99, 2)) + 1
        assert pos["shares"] == pytest.approx(100.0 - expected_sold)

    def test_sell_records_realized_pnl(self, engine):
        sid = self._seed_sleeve(engine, shares=100.0, avg_price=480.0)
        engine._test_client.get_account.return_value = _fake_account(cash="2000")
        engine._execute_cash_sweep(PRICES)

        import sqlite3

        conn = sqlite3.connect(engine.db.db_path)
        row = conn.execute(
            "SELECT entry_price, exit_price, direction FROM trade_pnl_detail "
            "WHERE strategy_id = ? AND symbol='SPY'",
            (sid,),
        ).fetchone()
        conn.close()
        assert row is not None
        assert row[0] == pytest.approx(480.0)
        assert row[2].lower() == "long"

    def test_no_sell_when_no_sleeve_held(self, engine):
        engine._test_client.get_account.return_value = _fake_account(cash="2000")
        engine._execute_cash_sweep(PRICES)
        assert engine._test_client.submit_order.call_count == 0


class TestSweepIsolation:
    def test_sweep_strategy_row_reused(self, engine):
        sid1 = engine._sweep_strategy_id()
        sid2 = engine._sweep_strategy_id()
        assert sid1 == sid2

    def test_sweep_excluded_from_heat_exposures(self, engine):
        self_sid = engine._sweep_strategy_id()
        engine.db.update_position(
            strategy_id=self_sid,
            symbol="SPY",
            shares=100.0,
            avg_price=480.0,
            current_price=500.0,
        )
        exposures = engine._calculate_strategy_exposures([], {"SPY": 500.0})
        assert self_sid not in exposures
        assert "BROKER_SYNC" not in exposures or exposures.get("BROKER_SYNC", 0) == 0
