#!/usr/bin/env python3
"""
Production-parity backtester tests.

The legacy backtester gates (0.60 confidence floor, 3 buys/day, 10d cooldown,
5.0x static ATR stop) diverge from production and invalidated evidence runs.
Parity mode sources gates/stops from trading_config.yaml and replicates the
production breakeven/lock ratchet stop.
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.integration.portfolio_backtester import PortfolioBacktester  # noqa: E402
from src.utils.config_loader import get_config  # noqa: E402


class TestFromConfig:
    def test_parity_sources_production_yaml(self):
        config = get_config()
        bt = PortfolioBacktester.from_config(config)
        assert bt.stop_loss_atr_mult == pytest.approx(
            float(config.get("risk.stop_loss_atr_multiplier", 2.5))
        )
        assert bt.max_portfolio_heat == pytest.approx(
            float(config.get("risk.max_portfolio_heat", 0.40))
        )
        assert bt.slippage_bps == pytest.approx(float(config.get("execution.slippage_bps", 5.0)))
        assert bt.breakeven_atr == pytest.approx(
            float(config.get("risk.trailing_breakeven_atr", 1.0))
        )
        assert bt.lock_atr == pytest.approx(float(config.get("risk.trailing_lock_atr", 2.0)))

    def test_parity_removes_synthetic_gates(self):
        bt = PortfolioBacktester.from_config(get_config())
        assert bt.min_buy_confidence == 0.0
        assert bt.cooldown_days == 0
        assert bt.max_daily_buys >= 1000

    def test_legacy_defaults_unchanged(self):
        bt = PortfolioBacktester()
        assert bt.stop_loss_atr_mult == 5.0
        assert bt.min_buy_confidence == 0.60
        assert bt.cooldown_days == 10
        assert bt.max_daily_buys == 3
        assert bt.breakeven_atr is None  # ratchet disabled in legacy mode


class _OneShotBuyStrategy:
    """Emits a single BUY on the first signal call, then stays silent."""

    def __init__(self, strategy_id=1, capital=100_000.0):
        self.strategy_id = strategy_id
        self.capital = capital
        self.name = "OneShot"
        self.positions = {}
        self.entry_dates = {}
        self._fired = False

    def generate_signals(self, historical):
        if self._fired:
            return []
        self._fired = True
        last = historical.iloc[-1]
        return [
            {
                "symbol": "TEST",
                "action": "BUY",
                "shares": 10,
                "price": float(last["close"]),
                "confidence": 0.9,
                "asof_date": historical.index[-1],
                "reasoning": "test entry",
                "atr": 2.0,
            }
        ]


def _scenario_frame(closes):
    dates = pd.bdate_range("2025-01-02", periods=len(closes))
    return pd.DataFrame({"symbol": "TEST", "close": closes}, index=dates)


def _run(bt, closes):
    # train 5d / test covers the rest; entry happens on the first sim day
    df = _scenario_frame(closes)
    return bt.run_walk_forward(
        market_data=df,
        strategy_classes=[_OneShotBuyStrategy],
        train_days=5,
        test_days=len(closes) - 5,
        step_days=len(closes) - 5,
    )


class TestRatchetStop:
    # OPG semantics: signal at sim day 0's close (100) fills at day +1's
    # open (=close in these frames, 100; exec ~100.05 with 5bps), ATR 2.
    # Day +2: 105 → profit ≈ 4.95 ≥ lock (2×ATR=4) → stop ratchets to
    # entry+1×ATR ≈ 102.05. Day +3: 101.5 ≤ stop → profitable stop exit.
    CLOSES = [100.0] * 5 + [100.0, 100.0, 105.0, 101.5, 101.5, 101.5]

    def test_parity_ratchet_locks_profit(self):
        bt = PortfolioBacktester.from_config(get_config())
        results = _run(bt, self.CLOSES)
        trades = results["all_trades"]
        sells = trades[trades["action"] == "SELL"]
        assert len(sells) == 1, "ratcheted stop should have fired"
        assert sells.iloc[0]["reason"] == "STOP_LOSS"
        assert sells.iloc[0]["pnl"] > 0, "ratchet must lock in profit, not realize a loss"

    def test_legacy_static_stop_never_fires_here(self):
        bt = PortfolioBacktester()  # 5x ATR static stop at ~90, no ratchet
        results = _run(bt, self.CLOSES)
        trades = results["all_trades"]
        sells = trades[trades["action"] == "SELL"]
        assert len(sells) == 0, "legacy static stop at entry-10 must not trigger at 101.5"

    def test_stop_never_ratchets_down(self):
        bt = PortfolioBacktester.from_config(get_config())
        # Fill day +1, rises to lock tier, then hovers just above the stop:
        closes = [100.0] * 5 + [100.0, 100.0, 105.0, 103.0, 103.0, 103.0]
        results = _run(bt, closes)
        trades = results["all_trades"]
        sells = trades[trades["action"] == "SELL"]
        assert len(sells) == 0, "price stayed above the ratcheted stop — no exit"


class TestConfidenceFloorRemoved:
    def test_low_confidence_signal_executes_in_parity(self):
        class LowConfStrategy(_OneShotBuyStrategy):
            def generate_signals(self, historical):
                sigs = super().generate_signals(historical)
                for s in sigs:
                    s["confidence"] = 0.40  # below the legacy 0.60 floor
                return sigs

        closes = [100.0] * 5 + [100.0] * 6
        df = _scenario_frame(closes)

        bt = PortfolioBacktester.from_config(get_config())
        results = bt.run_walk_forward(df, [LowConfStrategy], 5, 6, 6)
        buys = results["all_trades"]
        assert len(buys[buys["action"] == "BUY"]) == 1

        bt_legacy = PortfolioBacktester()
        results_legacy = bt_legacy.run_walk_forward(df, [LowConfStrategy], 5, 6, 6)
        buys_legacy = results_legacy["all_trades"]
        assert buys_legacy.empty, "legacy floor must reject the 0.40-confidence signal"
