#!/usr/bin/env python3
"""
Backtester production-fidelity tests (2026-06):

1. OPG semantics — signals queue at day t's close and fill at day t+1's
   OPEN; a gap through the limit (buy: open > close*1.01, sell: open <
   close*0.99) leaves the order unfilled, like a real expiring OPG.
2. Partial exits — a SELL signal's share count is respected (50% tranches);
   previously any SELL dumped the entire position.
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.integration.portfolio_backtester import PortfolioBacktester  # noqa: E402
from src.utils.config_loader import get_config  # noqa: E402


def _frame(closes, opens=None):
    dates = pd.bdate_range("2025-01-02", periods=len(closes))
    df = pd.DataFrame({"symbol": "TEST", "close": closes}, index=dates)
    if opens is not None:
        df["open"] = opens
    return df


class _ScriptedStrategy:
    """Emits a scripted signal on the Nth generate_signals call."""

    script: dict = {}  # {call_index: signal_dict}

    def __init__(self, strategy_id=1, capital=100_000.0):
        self.strategy_id = strategy_id
        self.capital = capital
        self.name = "Scripted"
        self.positions = {}
        self.entry_dates = {}
        self._calls = -1

    def generate_signals(self, historical):
        self._calls += 1
        sig = self.script.get(self._calls)
        if not sig:
            return []
        out = dict(sig)
        out.setdefault("asof_date", historical.index[-1])
        return [out]


def _run(closes, opens, script):
    _ScriptedStrategy.script = script
    bt = PortfolioBacktester.from_config(get_config())
    return bt.run_walk_forward(
        market_data=_frame(closes, opens),
        strategy_classes=[_ScriptedStrategy],
        train_days=3,
        test_days=len(closes) - 3,
        step_days=len(closes) - 3,
    )


_BUY = {"symbol": "TEST", "action": "BUY", "shares": 10, "price": 100.0, "confidence": 0.9}


class TestOpgFills:
    def test_buy_fills_at_next_open_not_signal_close(self):
        closes = [100.0] * 3 + [100.0, 100.0, 100.0, 100.0]
        opens = [100.0] * 3 + [100.0, 100.8, 100.0, 100.0]  # day+1 open within limit
        results = _run(closes, opens, {0: dict(_BUY)})
        buys = results["all_trades"]
        buys = buys[buys["action"] == "BUY"]
        assert len(buys) == 1
        # exec price = next day's OPEN (100.8) + 5bps, not the signal close 100
        assert buys.iloc[0]["price"] == pytest.approx(100.8 * 1.0005, rel=1e-4)

    def test_gap_up_buy_expires_unfilled(self):
        closes = [100.0] * 3 + [100.0, 103.0, 103.0, 103.0]
        opens = [100.0] * 3 + [100.0, 102.5, 103.0, 103.0]  # opens 2.5% above limit
        results = _run(closes, opens, {0: dict(_BUY)})
        assert results["all_trades"].empty, "gap above the 1% OPG limit must expire unfilled"

    def test_gap_down_sell_expires_unfilled_and_position_stays(self):
        closes = [100.0] * 3 + [100.0, 100.0, 100.0, 95.0, 95.0]
        opens = [100.0] * 3 + [100.0, 100.0, 100.0, 95.0, 95.0]  # sell day opens -5%
        script = {
            0: dict(_BUY),
            2: {
                "symbol": "TEST",
                "action": "SELL",
                "shares": 10,
                "price": 100.0,
                "confidence": 0.9,
            },
        }
        results = _run(closes, opens, script)
        trades = results["all_trades"]
        # SELL signal at call 2 (close 100) → next open 95 < 99 limit → unfilled
        assert len(trades[trades["action"] == "SELL"]) == 0
        assert results["equity_curve"].iloc[-1]["num_positions"] == 1


class TestPartialExits:
    def test_sell_respects_tranche_share_count(self):
        closes = [100.0] * 3 + [100.0] * 6
        opens = closes
        script = {
            0: dict(_BUY),
            3: {
                "symbol": "TEST",
                "action": "SELL",
                "shares": 5,
                "price": 100.0,
                "confidence": 0.9,
                "partial_exit": True,
            },
        }
        results = _run(closes, opens, script)
        trades = results["all_trades"]
        sells = trades[trades["action"] == "SELL"]
        assert len(sells) == 1
        assert sells.iloc[0]["shares"] == 5, "must sell the tranche, not the whole position"
        assert results["equity_curve"].iloc[-1]["num_positions"] == 1, "remaining half stays open"

    def test_full_sell_when_no_share_count(self):
        closes = [100.0] * 3 + [100.0] * 6
        script = {
            0: dict(_BUY),
            3: {"symbol": "TEST", "action": "SELL", "shares": 0, "price": 100.0, "confidence": 0.9},
        }
        results = _run(closes, closes, script)
        sells = results["all_trades"]
        sells = sells[sells["action"] == "SELL"]
        assert len(sells) == 1
        assert sells.iloc[0]["shares"] == 10
        assert results["equity_curve"].iloc[-1]["num_positions"] == 0
