#!/usr/bin/env python3
"""
Dual Momentum strategy tests: 12-1 cross-sectional momentum, absolute
momentum filter, rank-hysteresis exits, signal contract.
"""
import sys
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.strategies.strategy_dual_momentum import DualMomentumStrategy  # noqa: E402


def _trend_frame(symbol, n=300, daily_ret=0.001, base=100.0):
    dates = pd.bdate_range("2025-01-02", periods=n)
    closes = base * np.cumprod(np.full(n, 1 + daily_ret))
    return pd.DataFrame({"symbol": symbol, "close": closes, "atr_20": closes * 0.015}, index=dates)


def _market(symbol_rets: dict, n=300):
    frames = [_trend_frame(sym, n=n, daily_ret=r) for sym, r in symbol_rets.items()]
    return pd.concat(frames).sort_index()


@pytest.fixture
def strat():
    return DualMomentumStrategy(strategy_id=11, capital=20_000)


class TestMomentumComputation:
    def test_12_1_skips_recent_month(self, strat):
        # Flat for 252 days, then +50% in the last 21 days: the 12-1 window
        # must NOT see the recent spike.
        n = 300
        closes = np.full(n, 100.0)
        closes[-21:] = 150.0
        mom = strat._momentum_12_1(pd.Series(closes))
        assert mom == pytest.approx(0.0, abs=1e-9)

    def test_insufficient_history_returns_none(self, strat):
        assert strat._momentum_12_1(pd.Series(np.full(100, 100.0))) is None


class TestEntries:
    def test_buys_top_momentum_names(self, strat):
        md = _market({"HI1": 0.002, "HI2": 0.0018, "MID": 0.0008, "LO": -0.001, "SPY": 0.0005})
        signals = strat.generate_signals(md)
        buys = [s for s in signals if s["action"] == "BUY"]
        symbols = [s["symbol"] for s in buys]
        assert "HI1" in symbols and "HI2" in symbols
        assert "LO" not in symbols, "negative absolute momentum must never be bought"
        assert "SPY" not in symbols, "benchmarks are not tradeable"

    def test_signal_contract(self, strat):
        md = _market({"HI1": 0.002, "SPY": 0.0005})
        for sig in strat.generate_signals(md):
            for key in ("symbol", "action", "shares", "price", "confidence", "asof_date"):
                assert key in sig, f"missing {key}"
            assert 0 < sig["confidence"] <= 1

    def test_spy_negative_momentum_blocks_entries(self, strat):
        md = _market({"HI1": 0.002, "HI2": 0.0018, "SPY": -0.001})
        buys = [s for s in strat.generate_signals(md) if s["action"] == "BUY"]
        assert buys == [], "absolute market filter must block entries in downtrends"

    def test_no_spy_falls_back_to_per_name_filter(self, strat):
        md = _market({"HI1": 0.002, "LO": -0.001})  # no SPY at all
        buys = [s for s in strat.generate_signals(md) if s["action"] == "BUY"]
        assert [s["symbol"] for s in buys] == ["HI1"]


class TestExits:
    def test_top_ranked_loser_holds_past_soft(self, strat):
        md = _market({"HELD": 0.002, "OTHER": 0.001, "SPY": 0.0005})
        strat.positions["HELD"] = 10
        strat.entry_prices["HELD"] = 1e9  # deep loss
        strat.entry_dates["HELD"] = md.index[-1] - timedelta(days=40)  # past soft 35
        sells = [
            s for s in strat.generate_signals(md) if s["action"] == "SELL" and s["symbol"] == "HELD"
        ]
        assert sells == [], "top-band loser holds to the ceiling"

    def test_rank_dropout_exits_at_soft(self, strat):
        # 12 names, HELD has the WORST momentum → far outside top 2*top_n=10
        rets = {f"S{i:02d}": 0.001 + i * 0.0002 for i in range(11)}
        rets["HELD"] = -0.002
        rets["SPY"] = 0.0005
        md = _market(rets)
        strat.positions["HELD"] = 10
        strat.entry_prices["HELD"] = 1e9
        strat.entry_dates["HELD"] = md.index[-1] - timedelta(days=40)
        sells = [
            s for s in strat.generate_signals(md) if s["action"] == "SELL" and s["symbol"] == "HELD"
        ]
        assert len(sells) == 1
        assert "thesis" in sells[0]["reasoning"]

    def test_max_ceiling(self, strat):
        md = _market({"HELD": 0.002, "SPY": 0.0005})
        strat.positions["HELD"] = 10
        strat.entry_prices["HELD"] = 1e9
        strat.entry_dates["HELD"] = md.index[-1] - timedelta(days=75)  # past max 70
        sells = [s for s in strat.generate_signals(md) if s["action"] == "SELL"]
        assert len(sells) == 1
        assert "ceiling" in sells[0]["reasoning"]
