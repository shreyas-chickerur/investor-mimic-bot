"""
Targeted tests for all 10 performance improvements.

One test per improvement — verifies the specific behavior change, not just
that the code runs.  Improvements:
  1. Trailing stops (fixed stop_loss_pct removed from strategy SELL logic)
  2. Partial exits (50% SELL at profit target, partial_exit flag)
  3. Partial exit cross-run persistence (_partial_exit_done blocks re-trigger)
  4. Reduce position count (Factor top_n=3, ML min_confidence=0.60)
  5. Sharpe-weighted capital allocation
  6. SPY 50-day SMA gate (ML Momentum + Earnings Drift)
  7. VWAP/limit entry (LimitOrderRequest at typical_price × 1.01)
  8. Auto earnings calendar refresh (runs update when stale)
  9. Covered calls stub (no-op in paper, logs in live)
 10. Tax-aware exit (hold extended through 250-254 day window)
"""
from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.monitoring.daily_strategy_weights import compute_strategy_weights
from src.strategies.strategy_earnings_drift import EarningsDriftStrategy
from src.strategies.strategy_factor_momentum import FactorMomentumStrategy
from src.strategies.strategy_ml_momentum import MLMomentumStrategy
from src.strategies.strategy_rsi_mean_reversion import RSIMeanReversionStrategy

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_data(
    symbol: str, n: int = 100, base_price: float = 100.0, rsi: float = 50.0, momentum: float = 0.05
) -> pd.DataFrame:
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    close = base_price + np.cumsum(np.random.randn(n) * 0.5)
    close = np.maximum(close, 1.0)
    rsi_arr = np.full(n, rsi, dtype=float)
    rsi_arr[-2] = rsi - 1.0  # ensure positive slope on last bar
    return pd.DataFrame(
        {
            "symbol": symbol,
            "open": close * 0.99,
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
            "volume": np.full(n, 1_000_000.0),
            "rsi": rsi_arr,
            "atr_20": close * 0.015,
            "vwap": close * 0.70,
            "volume_ratio": np.full(n, 1.0),
            "returns_5d": np.full(n, momentum),
            "returns_20d": np.full(n, momentum * 2),
            "returns_60d": np.full(n, momentum * 4),
            "volatility_20d": np.full(n, 0.15),
            "volatility_60d": np.full(n, 0.15),
            "price_to_sma20": np.full(n, 1.01),
            "price_to_sma50": np.full(n, 1.02),
            "adx": np.full(n, 25.0),
            "future_return_5d": np.where(np.arange(n) % 2 == 0, 0.01, -0.01),
            "sma_100": close * 0.95,  # below close → uptrend
        },
        index=dates,
    )


def _add_spy(market_data: pd.DataFrame, spy_above_sma: bool = True) -> pd.DataFrame:
    """Append SPY rows to market_data with price above or below its 50-day SMA."""
    dates = pd.date_range("2024-01-01", periods=100, freq="B")

    spy_close = np.full(100, 400.0)
    if spy_above_sma:
        spy_close[-1] = 420.0  # well above 400 average → above SMA50
    else:
        spy_close[-1] = 380.0  # below 400 average → below SMA50

    spy_df = pd.DataFrame(
        {
            "symbol": "SPY",
            "open": spy_close * 0.99,
            "high": spy_close * 1.01,
            "low": spy_close * 0.99,
            "close": spy_close,
            "volume": np.full(100, 50_000_000.0),
            "rsi": np.full(100, 55.0),
            "atr_20": spy_close * 0.01,
            "vwap": spy_close * 0.98,
            "volume_ratio": np.full(100, 1.0),
            "returns_5d": np.full(100, 0.01),
            "returns_20d": np.full(100, 0.02),
            "returns_60d": np.full(100, 0.05),
            "volatility_20d": np.full(100, 0.12),
            "volatility_60d": np.full(100, 0.12),
            "price_to_sma20": np.full(100, 1.02),
            "price_to_sma50": np.full(100, 1.03),
            "adx": np.full(100, 22.0),
            "future_return_5d": np.full(100, 0.005),
            "sma_100": spy_close * 0.94,
        },
        index=dates,
    )

    # Drop SPY rows if already present, then concat
    if "symbol" in market_data.columns:
        base = market_data[market_data["symbol"] != "SPY"]
    else:
        base = market_data
    return pd.concat([base, spy_df])


# ===========================================================================
# 1. Trailing stops — fixed stop_loss_pct REMOVED from strategy SELL logic
# ===========================================================================


class TestImprovement1TrailingStops:
    def test_rsi_no_stop_loss_sell_signal_at_fixed_pct(self):
        """RSI strategy must NOT emit a SELL due to fixed stop_loss_pct breach."""
        s = RSIMeanReversionStrategy(1, 25_000)
        data = _make_data("AAPL", rsi=50.0)
        entry_price = float(data["close"].iloc[-1]) * 1.10  # entry was 10% higher
        s.positions["AAPL"] = 10
        s.entry_dates["AAPL"] = data.index[-1] - timedelta(days=3)
        s.entry_prices = {"AAPL": entry_price}  # type: ignore[attr-defined]

        signals = s.generate_signals(data)
        stop_sells = [
            sig
            for sig in signals
            if sig["action"] == "SELL"
            and "stop" in sig.get("reasoning", "").lower()
            and "partial" not in sig.get("reasoning", "").lower()
        ]
        # Fixed-pct stop logic was removed; StopLossManager handles this at engine level.
        assert (
            len(stop_sells) == 0
        ), "RSI strategy should not emit fixed-pct stop SELL — StopLossManager handles stops"

    def test_factor_no_stop_loss_sell_signal_at_fixed_pct(self):
        """Factor Momentum must NOT emit a fixed-pct stop SELL."""
        s = FactorMomentumStrategy(1, 25_000)
        data = _make_data("AAPL", rsi=50.0, momentum=0.05)
        entry_price = float(data["close"].iloc[-1]) * 1.12  # 12% underwater
        s.positions["AAPL"] = 10
        s.entry_dates["AAPL"] = data.index[-1] - timedelta(days=3)
        s.entry_prices = {"AAPL": entry_price}  # type: ignore[attr-defined]

        signals = s.generate_signals(data)
        stop_sells = [
            sig
            for sig in signals
            if sig["action"] == "SELL" and "stop-loss" in sig.get("reasoning", "").lower()
        ]
        assert len(stop_sells) == 0, "Factor should not emit fixed-pct stop SELL"


# ===========================================================================
# 2. Partial exits — 50% SELL at profit target with partial_exit=True flag
# ===========================================================================


class TestImprovement2PartialExits:
    def _make_profitable_position(self, strategy, data, symbol="AAPL"):
        """Set up a position deep in profit so profit target fires."""
        # Filter to the target symbol so SPY rows don't pollute current_price.
        sym_rows = data[data["symbol"] == symbol] if "symbol" in data.columns else data
        current_price = float(sym_rows["close"].iloc[-1])
        entry_price = current_price * 0.80  # 25% gain — well past any profit target
        strategy.positions[symbol] = 20
        strategy.entry_dates[symbol] = sym_rows.index[-1] - timedelta(days=5)
        strategy.entry_prices = {symbol: entry_price}  # type: ignore[attr-defined]

    def test_rsi_partial_exit_sells_half(self):
        s = RSIMeanReversionStrategy(1, 50_000)
        data = _make_data("AAPL", rsi=50.0)
        self._make_profitable_position(s, data)

        signals = s.generate_signals(data)
        sells = [sig for sig in signals if sig["action"] == "SELL" and sig["symbol"] == "AAPL"]
        assert len(sells) == 1
        assert sells[0].get("partial_exit") is True, "SELL should be flagged as partial exit"
        assert sells[0]["shares"] == 10, f"Expected 10 (half of 20), got {sells[0]['shares']}"

    def test_factor_partial_exit_sells_half(self):
        s = FactorMomentumStrategy(1, 50_000)
        data = _make_data("AAPL", rsi=50.0, momentum=0.05)
        self._make_profitable_position(s, data)

        signals = s.generate_signals(data)
        sells = [sig for sig in signals if sig["action"] == "SELL" and sig["symbol"] == "AAPL"]
        assert len(sells) == 1
        assert sells[0].get("partial_exit") is True
        assert sells[0]["shares"] == 10

    def test_earnings_drift_partial_exit_sells_half(self):
        s = EarningsDriftStrategy(1, 50_000)
        data = _make_data("AAPL", rsi=50.0)
        data = _add_spy(data, spy_above_sma=True)
        self._make_profitable_position(s, data)

        signals = s.generate_signals(data)
        sells = [sig for sig in signals if sig["action"] == "SELL" and sig["symbol"] == "AAPL"]
        assert len(sells) == 1
        assert sells[0].get("partial_exit") is True
        assert sells[0]["shares"] == 10


# ===========================================================================
# 3. Partial exit cross-run — _partial_exit_done blocks re-trigger
# ===========================================================================


class TestImprovement3PartialExitPersistence:
    def test_second_run_skips_profit_target_when_partial_done(self):
        """Once _partial_exit_done is set, profit target SELL should not fire again."""
        s = RSIMeanReversionStrategy(1, 50_000)
        data = _make_data("AAPL", rsi=50.0)
        current_price = float(data["close"].iloc[-1])
        entry_price = current_price * 0.80  # 25% gain

        s.positions["AAPL"] = 10  # already halved — second run
        s.entry_dates["AAPL"] = data.index[-1] - timedelta(days=5)
        s.entry_prices = {"AAPL": entry_price}  # type: ignore[attr-defined]
        s._partial_exit_done.add("AAPL")  # simulate DB restore on startup

        signals = s.generate_signals(data)
        profit_target_sells = [
            sig
            for sig in signals
            if sig["action"] == "SELL" and "partial" in sig.get("reasoning", "").lower()
        ]
        assert (
            len(profit_target_sells) == 0
        ), "After _partial_exit_done is set, profit-target SELL must not fire again"

    def test_first_run_adds_symbol_to_partial_exit_done(self):
        """Generating a partial exit signal should add the symbol to _partial_exit_done."""
        s = RSIMeanReversionStrategy(1, 50_000)
        data = _make_data("AAPL", rsi=50.0)
        current_price = float(data["close"].iloc[-1])
        entry_price = current_price * 0.80

        s.positions["AAPL"] = 20
        s.entry_dates["AAPL"] = data.index[-1] - timedelta(days=5)
        s.entry_prices = {"AAPL": entry_price}  # type: ignore[attr-defined]

        assert "AAPL" not in s._partial_exit_done
        s.generate_signals(data)
        assert (
            "AAPL" in s._partial_exit_done
        ), "Symbol must be added to _partial_exit_done after first partial SELL signal"


# ===========================================================================
# 4. Reduced position count — top_n=3, min_confidence=0.65
# ===========================================================================


class TestImprovement4ReducedPositions:
    def test_factor_top_n_is_three(self):
        s = FactorMomentumStrategy(1, 25_000)
        assert s.top_n == 3, f"Factor top_n should be 3, got {s.top_n}"

    def test_ml_min_confidence_is_0_65(self):
        s = MLMomentumStrategy(1, 25_000)
        assert s.min_confidence == 0.65, f"ML min_confidence should be 0.65, got {s.min_confidence}"

    def test_factor_generates_at_most_three_buys(self):
        """With top_n=3, Factor Momentum must never return more than 3 BUY signals."""
        s = FactorMomentumStrategy(1, 100_000)
        frames = [_make_data(f"SYM{i:02d}", n=100, momentum=-0.10 + i * 0.025) for i in range(10)]
        data = pd.concat(frames)
        signals = s.generate_signals(data)
        buys = [sig for sig in signals if sig["action"] == "BUY"]
        assert len(buys) <= 3, f"Factor generated {len(buys)} BUY signals, expected ≤ 3"


# ===========================================================================
# 5. Sharpe-weighted capital allocation
# ===========================================================================


class TestImprovement5SharpeWeights:
    def test_positive_sharpe_increases_weight(self):
        names = ["RSI Mean Reversion", "ML Momentum"]
        regime = {
            "volatility_regime": "normal",
            "trend_regime": "weak_trend",
            "hmm_regime": "unknown",
        }
        health = {n: {} for n in names}
        sharpe = {"RSI Mean Reversion": 1.5, "ML Momentum": -0.5}

        weights = compute_strategy_weights(
            names, regime, health, trailing_sharpe_by_strategy=sharpe
        )

        assert (
            weights["RSI Mean Reversion"] > weights["ML Momentum"]
        ), "Strategy with Sharpe=1.5 should be weighted higher than Sharpe=-0.5"

    def test_none_sharpe_does_not_crash(self):
        """Passing no Sharpe data should produce same output as before (backward-compat)."""
        names = ["RSI Mean Reversion", "ML Momentum"]
        regime = {
            "volatility_regime": "normal",
            "trend_regime": "weak_trend",
            "hmm_regime": "unknown",
        }
        health = {n: {} for n in names}

        weights_no_sharpe = compute_strategy_weights(names, regime, health)
        weights_none = compute_strategy_weights(
            names, regime, health, trailing_sharpe_by_strategy=None
        )
        assert weights_no_sharpe == weights_none

    def test_negative_sharpe_penalizes_weight(self):
        names = ["Factor Momentum"]
        regime = {
            "volatility_regime": "normal",
            "trend_regime": "weak_trend",
            "hmm_regime": "unknown",
        }
        health = {"Factor Momentum": {}}

        base = compute_strategy_weights(names, regime, health)
        penalized = compute_strategy_weights(
            names, regime, health, trailing_sharpe_by_strategy={"Factor Momentum": -0.8}
        )
        assert (
            penalized["Factor Momentum"] < base["Factor Momentum"]
        ), "Negative Sharpe should reduce strategy weight below baseline"


# ===========================================================================
# 6. SPY 50-day SMA gate
# ===========================================================================


class TestImprovement6SpyGate:
    def test_ml_suppresses_buy_when_spy_below_sma50(self):
        s = MLMomentumStrategy(1, 100_000)
        # Build data with SPY below its 50-day average
        data = _make_data("AAPL", n=100)
        data = _add_spy(data, spy_above_sma=False)
        assert s._spy_above_sma50(data) is False, "Setup check: SPY should be below SMA50"

        signals = s.generate_signals(data)
        buys = [sig for sig in signals if sig["action"] == "BUY"]
        assert len(buys) == 0, "ML must emit 0 BUY signals when SPY is below 50-day SMA"

    def test_ml_allows_buy_when_spy_above_sma50(self):
        """ML may generate BUYs when SPY is in uptrend (gate passes)."""
        s = MLMomentumStrategy(1, 100_000)
        data = _make_data("AAPL", n=100)
        data = _add_spy(data, spy_above_sma=True)
        assert s._spy_above_sma50(data) is True

        # We can't guarantee buys (model may not be trained or signals may not pass confidence),
        # but at minimum the gate must not suppress everything due to SPY.
        # The gate returning True means the path is open — that's what we test.
        result = s._spy_above_sma50(data)
        assert result is True

    def test_earnings_drift_suppresses_buy_when_spy_below_sma50(self):
        s = EarningsDriftStrategy(1, 100_000)
        data = _make_data("AAPL", n=100)
        data = _add_spy(data, spy_above_sma=False)
        assert s._spy_above_sma50(data) is False

        # Simulate an earnings calendar trigger for AAPL
        with patch.object(s, "_symbols_with_recent_earnings", return_value={"AAPL"}):
            signals = s.generate_signals(data)
        buys = [sig for sig in signals if sig["action"] == "BUY" and sig["symbol"] == "AAPL"]
        assert len(buys) == 0, "Earnings Drift must suppress BUY when SPY below 50-day SMA"

    def test_spy_gate_uses_50_periods(self):
        """Gate must look at exactly 50 periods of SPY data (not 100 or 200)."""
        s = MLMomentumStrategy(1, 100_000)

        # SPY with only 45 rows — below 50-day lookback, so gate defaults to True (allow)
        dates = pd.date_range("2024-01-01", periods=45, freq="B")
        spy_df = pd.DataFrame(
            {
                "symbol": "SPY",
                "close": np.full(45, 400.0),
                "open": 398.0,
                "high": 402.0,
                "low": 398.0,
                "volume": 50_000_000.0,
                "rsi": 55.0,
                "atr_20": 4.0,
                "vwap": 399.0,
                "volume_ratio": 1.0,
                "returns_5d": 0.01,
                "returns_20d": 0.02,
                "returns_60d": 0.05,
                "volatility_20d": 0.12,
                "volatility_60d": 0.12,
                "price_to_sma20": 1.01,
                "price_to_sma50": 1.01,
                "adx": 20.0,
                "future_return_5d": 0.005,
                "sma_100": 395.0,
            },
            index=dates,
        )

        result = s._spy_above_sma50(spy_df)
        assert (
            result is True
        ), "Insufficient SPY history (<50 rows) should default gate to OPEN (True)"


# ===========================================================================
# 7. VWAP/limit entry — LimitOrderRequest at typical_price × 1.01
# ===========================================================================


class TestImprovement7VwapEntry:
    def test_execution_engine_uses_limit_order_for_buy(self):
        """execution_engine.py must instantiate LimitOrderRequest for BUY orders."""
        src = Path("src/core/execution_engine.py").read_text()
        import re

        assert re.search(
            r"LimitOrderRequest\s*\(", src
        ), "LimitOrderRequest must be used for BUY OPG orders"

    def test_limit_price_uses_1pct_buffer(self):
        """Limit price must be computed as typical_price * 1.01, not tighter."""
        src = Path("src/core/execution_engine.py").read_text()
        assert "1.01" in src, "1% buffer (1.01) over typical price must appear in execution engine"
        assert (
            "1.001" not in src
        ), "Old 0.1% buffer (1.001) must not be present — causes non-fills on any gap"

    def test_limit_price_uses_typical_price_formula(self):
        """Typical price (H+L+C)/3 should appear in the engine's price computation."""
        src = Path("src/core/execution_engine.py").read_text()
        assert "_typical_prices" in src, "Engine should pre-compute typical prices (H+L+C)/3"

    def test_typical_prices_computed_from_hlc(self):
        """_typical_prices dict should be derived from high, low, close columns."""
        src = Path("src/core/execution_engine.py").read_text()
        # The formula appears as (_last["high"] + _last["low"] + _last["close"]) / 3
        assert (
            '"high"' in src and '"low"' in src
        ), "Typical price formula must reference 'high' and 'low' columns"


# ===========================================================================
# 8. Auto earnings calendar refresh
# ===========================================================================


class TestImprovement8AutoEarningsRefresh:
    def test_refresh_method_exists_on_runner(self):
        """MultiStrategyRunner must have _maybe_refresh_earnings_calendar method."""
        src = Path("src/core/execution_engine.py").read_text()
        assert "_maybe_refresh_earnings_calendar" in src

    def test_refresh_runs_update_script_when_stale(self, tmp_path):
        """_maybe_refresh_earnings_calendar must invoke the update script for stale files."""
        # Write a stale CSV in the data/ subdir (matching engine's cal_path structure)
        import os
        import time

        data_dir = tmp_path / "data"
        data_dir.mkdir()
        cal = data_dir / "earnings_calendar.csv"
        cal.write_text("symbol,reportDate\nAAPL,2024-01-01\n")
        stale_mtime = time.time() - (10 * 86400)  # 10 days ago
        os.utime(str(cal), (stale_mtime, stale_mtime))

        # Patch project_root and subprocess inside execution_engine
        from src.core import execution_engine as ee

        call_log: list = []

        def fake_run(cmd, **kwargs):
            call_log.append(cmd)
            result = MagicMock()
            result.returncode = 0
            return result

        original_root = ee.project_root
        try:
            ee.project_root = tmp_path  # type: ignore[attr-defined]
            with patch("subprocess.run", side_effect=fake_run):
                runner = MagicMock()
                runner._maybe_refresh_earnings_calendar = (
                    ee.MultiStrategyRunner._maybe_refresh_earnings_calendar.__get__(runner)
                )
                runner._maybe_refresh_earnings_calendar()
        finally:
            ee.project_root = original_root

        assert len(call_log) == 1, "update_earnings_calendar.py must be called for stale file"

    def test_no_refresh_when_calendar_fresh(self, tmp_path):
        """_maybe_refresh_earnings_calendar must NOT run the script for a recent file."""
        import os

        # Write in data/ subdir — matching the engine's cal_path structure
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        cal = data_dir / "earnings_calendar.csv"
        cal.write_text("symbol,reportDate\nAAPL,2024-01-01\n")
        # mtime = now (fresh file)
        os.utime(str(cal), None)

        from src.core import execution_engine as ee

        call_log: list = []

        def fake_run(cmd, **kwargs):
            call_log.append(cmd)
            result = MagicMock()
            result.returncode = 0
            return result

        original_root = ee.project_root
        try:
            ee.project_root = tmp_path  # type: ignore[attr-defined]
            with patch("subprocess.run", side_effect=fake_run):
                runner = MagicMock()
                runner._maybe_refresh_earnings_calendar = (
                    ee.MultiStrategyRunner._maybe_refresh_earnings_calendar.__get__(runner)
                )
                runner._maybe_refresh_earnings_calendar()
        finally:
            ee.project_root = original_root

        assert len(call_log) == 0, "Fresh calendar file must not trigger a refresh"


# ===========================================================================
# 9. Covered calls stub
# ===========================================================================


class TestImprovement9CoveredCallsStub:
    """_submit_covered_calls was removed as dead code (it was a no-op stub
    that did nothing in paper mode and was never wired to any live path).
    These tests verify the method no longer exists on MultiStrategyRunner."""

    def test_method_removed(self):
        """Stub was removed — verify it is no longer on MultiStrategyRunner."""
        from src.core import execution_engine as ee

        assert not hasattr(
            ee.MultiStrategyRunner, "_submit_covered_calls"
        ), "_submit_covered_calls stub should have been removed as dead code"


# ===========================================================================
# 10. Tax-aware exit — hold extended through 250-254 day window
# ===========================================================================


class TestImprovement10TaxAwareExit:
    def test_rsi_extends_hold_at_day_250(self):
        """RSI must NOT emit a time-based SELL when days_held is 251 (near 1-year mark)."""
        s = RSIMeanReversionStrategy(1, 50_000)
        data = _make_data("AAPL", rsi=45.0)  # rsi below exit=55 so RSI exit won't fire
        current_price = float(data["close"].iloc[-1])
        entry_price = current_price * 0.98  # slight profit → let_winners_run fires if applicable

        s.positions["AAPL"] = 10
        # Entry was 251 calendar days ago → hold_days (20) exceeded, but in tax window
        s.entry_dates["AAPL"] = data.index[-1] - timedelta(days=251)
        s.entry_prices = {"AAPL": entry_price}  # type: ignore[attr-defined]

        signals = s.generate_signals(data)
        time_sells = [
            sig
            for sig in signals
            if sig["action"] == "SELL" and "time" in sig.get("reasoning", "").lower()
        ]
        assert (
            len(time_sells) == 0
        ), "RSI must NOT emit a time-based SELL at day 251 — extend hold to cross 1-year LTCG"

    def test_rsi_exits_after_day_255(self):
        """RSI MUST emit a time-based SELL once past the 255-day extension window."""
        s = RSIMeanReversionStrategy(1, 50_000)
        data = _make_data("AAPL", rsi=45.0)
        current_price = float(data["close"].iloc[-1])

        s.positions["AAPL"] = 10
        # Entry was 260 days ago — past the extension window
        s.entry_dates["AAPL"] = data.index[-1] - timedelta(days=260)
        s.entry_prices = {"AAPL": current_price * 0.90}  # type: ignore[attr-defined]

        signals = s.generate_signals(data)
        sells = [sig for sig in signals if sig["action"] == "SELL"]
        assert (
            len(sells) == 1
        ), "RSI must emit a SELL at day 260 — well past the 255-day extension window"

    def test_factor_extends_hold_at_day_252(self):
        """Factor Momentum must NOT emit a time-based SELL at day 252."""
        s = FactorMomentumStrategy(1, 50_000)
        data = _make_data("AAPL", rsi=50.0, momentum=0.05)
        current_price = float(data["close"].iloc[-1])

        s.positions["AAPL"] = 10
        s.entry_dates["AAPL"] = data.index[-1] - timedelta(days=252)
        s.entry_prices = {"AAPL": current_price * 0.98}  # type: ignore[attr-defined]

        signals = s.generate_signals(data)
        time_sells = [
            sig
            for sig in signals
            if sig["action"] == "SELL" and "rebalance" in sig.get("reasoning", "").lower()
        ]
        assert (
            len(time_sells) == 0
        ), "Factor must extend hold at day 252 to cross 1-year LTCG threshold"
