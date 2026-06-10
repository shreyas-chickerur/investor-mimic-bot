#!/usr/bin/env python3
"""
Order-path unit tests for MultiStrategyRunner: BUY / SELL guards /
SHORT_SELL / BUY_TO_COVER / stop-loss exits (long and short).

The engine is constructed for real (real TradingDatabase, CashManager,
StopLossManager) with the Alpaca TradingClient class patched out, so these
tests exercise the genuine bookkeeping paths without any network.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import src.core.execution_engine as ee  # noqa: E402


def _fake_account():
    account = MagicMock()
    account.portfolio_value = "100000"
    account.cash = "100000"
    account.buying_power = "100000"
    return account


def _fake_order(order_id="ord-1", status="accepted"):
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
    # BrokerReconciler builds its own client — patch its class too
    monkeypatch.setattr(
        "src.risk.broker_reconciler.TradingClient", lambda *a, **k: fake_client, raising=False
    )

    runner = ee.MultiStrategyRunner()
    runner._test_client = fake_client
    return runner


def _strategy_stub(strategy_id=1, name="Test Strategy", capital=20_000.0):
    s = MagicMock()
    s.strategy_id = strategy_id
    s.name = name
    s.capital = capital
    s.positions = {}
    s.entry_dates = {}
    s.entry_prices = {}
    return s


class TestShortSellPath:
    def test_short_sell_creates_negative_position_and_stop(self, engine):
        strategy = _strategy_stub()
        signal = {
            "symbol": "BAC",
            "action": "SHORT_SELL",
            "shares": 25,
            "price": 40.0,
            "confidence": 0.8,
            "reasoning": "pairs short leg",
            "atr": 1.0,
        }
        executed, _ = engine._execute_strategy_trades(strategy, [signal], 0.0, 100_000.0)

        assert any(t["action"] == "SHORT_SELL" for t in executed)
        pos = engine.db.get_position(1, "BAC")
        assert pos is not None and float(pos["shares"]) == -25.0

        # Stop must sit ABOVE entry and be marked short
        assert engine.stop_loss_manager.get_direction("BAC") == "short"
        assert engine.stop_loss_manager.get_stop_price("BAC") > 40.0

        # Symbol is held (blocks later BUYs) and buying power decremented
        assert "BAC" in engine._held_symbols
        assert engine.buying_power == pytest.approx(100_000 - 25 * 40.0)

    def test_short_sell_skipped_when_already_long(self, engine):
        engine._held_symbols.add("BAC")
        strategy = _strategy_stub()
        signal = {
            "symbol": "BAC",
            "action": "SHORT_SELL",
            "shares": 25,
            "price": 40.0,
            "confidence": 0.8,
            "reasoning": "x",
        }
        executed, _ = engine._execute_strategy_trades(strategy, [signal], 0.0, 100_000.0)
        assert executed == []
        assert engine.db.get_position(1, "BAC") is None


class TestBuyToCoverPath:
    def _open_short(self, engine, shares=-25.0, avg=40.0):
        engine.db.update_position(
            strategy_id=1, symbol="BAC", shares=shares, avg_price=avg, current_price=avg
        )

    def test_full_cover_closes_position_and_records_pnl(self, engine):
        self._open_short(engine)
        engine.stop_loss_manager.set_stop_loss("BAC", 40.0, 1.0, direction="short")
        engine._held_symbols.add("BAC")
        strategy = _strategy_stub()
        signal = {
            "symbol": "BAC",
            "action": "BUY_TO_COVER",
            "shares": 25,
            "price": 36.0,
            "confidence": 0.85,
            "reasoning": "pairs exit",
        }
        executed, _ = engine._execute_strategy_trades(strategy, [signal], 0.0, 100_000.0)

        assert any(t["action"] == "BUY_TO_COVER" for t in executed)
        assert engine.db.get_position(1, "BAC") is None
        # Profitable short: price 40 -> 36 on 25 shares = +$100
        stats = engine.db.get_strategy_pnl_stats(1)
        assert stats["trades"] == 1 and stats["win_rate"] == 1.0
        # Stop + hold released
        assert engine.stop_loss_manager.get_stop_price("BAC") == 0.0
        assert "BAC" not in engine._held_symbols

    def test_partial_cover_keeps_remaining_short(self, engine):
        self._open_short(engine, shares=-25.0)
        strategy = _strategy_stub()
        signal = {
            "symbol": "BAC",
            "action": "BUY_TO_COVER",
            "shares": 10,
            "price": 36.0,
            "confidence": 0.85,
            "reasoning": "partial",
        }
        engine._execute_strategy_trades(strategy, [signal], 0.0, 100_000.0)
        pos = engine.db.get_position(1, "BAC")
        assert pos is not None and float(pos["shares"]) == -15.0
        assert float(pos["avg_price"]) == pytest.approx(40.0), "cover must not move entry price"

    def test_cover_without_short_is_skipped(self, engine):
        strategy = _strategy_stub()
        signal = {
            "symbol": "BAC",
            "action": "BUY_TO_COVER",
            "shares": 10,
            "price": 36.0,
            "confidence": 0.85,
            "reasoning": "x",
        }
        executed, _ = engine._execute_strategy_trades(strategy, [signal], 0.0, 100_000.0)
        assert executed == []


class TestStopLossExits:
    def test_long_stop_exit_sells_and_zeroes_position(self, engine):
        engine.db.update_position(
            strategy_id=1, symbol="AAPL", shares=10.0, avg_price=100.0, current_price=90.0
        )
        engine.execute_stop_loss_exits(
            [
                {
                    "symbol": "AAPL",
                    "strategy_id": 1,
                    "shares": 10.0,
                    "current_price": 90.0,
                    "stop_price": 92.0,
                    "entry_price": 100.0,
                    "avg_price": 100.0,
                    "reason": "CATASTROPHE_STOP_LOSS",
                }
            ]
        )
        assert engine.db.get_position(1, "AAPL") is None
        submitted = engine._test_client.submit_order.call_args[0][0]
        assert submitted.side.name == "SELL"
        assert float(submitted.qty) == 10.0

    def test_short_stop_exit_buys_to_cover(self, engine):
        engine.db.update_position(
            strategy_id=1, symbol="BAC", shares=-25.0, avg_price=40.0, current_price=44.0
        )
        engine.execute_stop_loss_exits(
            [
                {
                    "symbol": "BAC",
                    "strategy_id": 1,
                    "shares": -25.0,
                    "current_price": 44.0,
                    "stop_price": 42.5,
                    "entry_price": 40.0,
                    "avg_price": 40.0,
                    "reason": "CATASTROPHE_STOP_LOSS",
                }
            ]
        )
        assert engine.db.get_position(1, "BAC") is None
        submitted = engine._test_client.submit_order.call_args[0][0]
        assert submitted.side.name == "BUY", "short protective exit must BUY to cover"
        assert float(submitted.qty) == 25.0
        # Losing short (40 -> 44): P&L must be NEGATIVE
        import sqlite3

        with sqlite3.connect(engine.db.db_path) as conn:
            row = conn.execute(
                "SELECT gross_pnl, direction FROM trade_pnl_detail WHERE symbol='BAC'"
            ).fetchone()
        assert row is not None
        assert row[0] == pytest.approx(-100.0)
        assert row[1] == "short"

    def test_double_exit_guard_long(self, engine):
        # No DB position at all — exit must be skipped, no order submitted
        engine._test_client.submit_order.reset_mock()
        engine.execute_stop_loss_exits(
            [
                {
                    "symbol": "AAPL",
                    "strategy_id": 1,
                    "shares": 10.0,
                    "current_price": 90.0,
                    "stop_price": 92.0,
                    "entry_price": 100.0,
                    "reason": "CATASTROPHE_STOP_LOSS",
                }
            ]
        )
        engine._test_client.submit_order.assert_not_called()

    def test_double_exit_guard_short(self, engine):
        engine._test_client.submit_order.reset_mock()
        engine.execute_stop_loss_exits(
            [
                {
                    "symbol": "BAC",
                    "strategy_id": 1,
                    "shares": -25.0,
                    "current_price": 44.0,
                    "stop_price": 42.5,
                    "entry_price": 40.0,
                    "reason": "CATASTROPHE_STOP_LOSS",
                }
            ]
        )
        engine._test_client.submit_order.assert_not_called()
