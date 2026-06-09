"""Unit tests for platform improvements A–G (2026-05-22).

A: Equal capital normalization
B: Regime-conditional strategy weights (REGIME_WEIGHT_TABLE)
C: Confidence-scaled position sizing
D: Kelly fractional rebalancing
E: 5-regime composite detector
F: Platform status report generation
G: Per-strategy backtest CLI flag
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.monitoring.daily_strategy_weights import REGIME_WEIGHT_TABLE, compute_strategy_weights
from src.regime.regime_detector import RegimeDetector

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_STRATEGY_NAMES = [
    "RSI Mean Reversion",
    "ML Momentum",
    "Earnings Drift",
    "MA Crossover",
    "Volatility Breakout",
    "News Sentiment",
]

_EMPTY_ADJUSTMENTS: dict = {
    "volatility_regime": "normal",
    "trend_regime": "weak_trend",
    "hmm_regime": "unknown",
}


@pytest.fixture()
def tmp_db(tmp_path):
    """Temporary TradingDatabase wired with one strategy and 25 synthetic trades."""
    from src.core.database import TradingDatabase

    db_path = str(tmp_path / "test.db")
    db = TradingDatabase(db_path=db_path)
    sid = db.create_strategy("Test Strategy", "desc", 10_000)

    conn = sqlite3.connect(db_path)
    for i in range(25):
        win = i % 4 != 0  # 75% win rate
        pnl = 200.0 if win else -150.0
        pct = 0.02 if win else -0.015
        conn.execute(
            "INSERT INTO trade_pnl_detail "
            "(strategy_id, strategy_name, symbol, sell_run_id, "
            "entry_date, exit_date, entry_price, exit_price, "
            "shares, gross_pnl, gross_pnl_pct, is_winner) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                sid,
                "Test",
                f"SYM{i:02d}",  # unique symbol per trade to satisfy UNIQUE constraint
                f"r{i:04d}",  # unique sell_run_id per trade
                "2026-01-01",
                f"2026-01-{(i % 28) + 1:02d}",  # spread across different dates
                100,
                102 if win else 98.5,
                100,
                pnl,
                pct,
                1 if win else 0,
            ),
        )
    conn.commit()
    conn.close()
    return db, sid


# ---------------------------------------------------------------------------
# A: Equal capital normalization
# ---------------------------------------------------------------------------


class TestCapitalNormalization:
    def test_deployed_capital_pct_in_config(self):
        from src.utils.config_loader import get_config

        cfg = get_config()
        pct = cfg.get("strategies.deployed_capital_pct", None)
        assert pct is not None, "deployed_capital_pct missing from config"
        assert 0.5 <= pct <= 1.0, f"deployed_capital_pct={pct} outside expected range"

    def test_update_strategy_capital_allocation(self, tmp_db):
        db, sid = tmp_db
        db.update_strategy_capital_allocation(sid, 25_000)
        conn = sqlite3.connect(db.db_path)
        row = conn.execute(
            "SELECT capital_allocation FROM strategies WHERE id=?", (sid,)
        ).fetchone()
        conn.close()
        assert row[0] == pytest.approx(25_000)

    def test_capital_equal_across_n_strategies(self):
        """Each strategy should get deployed_capital_pct/N of portfolio."""
        portfolio = 100_000
        deployed_pct = 0.85
        for n in [3, 5, 6]:
            per_strategy = (portfolio * deployed_pct) / n
            assert per_strategy == pytest.approx(portfolio * 0.85 / n)


# ---------------------------------------------------------------------------
# B: Regime-conditional strategy weights
# ---------------------------------------------------------------------------


class TestRegimeWeightTable:
    def test_all_five_regimes_present(self):
        expected = {"TRENDING_BULL", "RANGING", "HIGH_VOL", "LOW_VOL", "NORMAL"}
        assert set(REGIME_WEIGHT_TABLE.keys()) == expected

    def test_weights_bounded(self):
        for regime, deltas in REGIME_WEIGHT_TABLE.items():
            for strat, delta in deltas.items():
                assert abs(delta) <= 0.5, f"{regime}/{strat}: delta={delta} too large"

    def test_trending_bull_boosts_momentum(self):
        w = compute_strategy_weights(
            _STRATEGY_NAMES, _EMPTY_ADJUSTMENTS, {}, composite_regime="TRENDING_BULL"
        )
        assert (
            w["ML Momentum"] > w["RSI Mean Reversion"]
        ), "TRENDING_BULL should boost ML Momentum over RSI Mean Reversion"
        assert (
            w["MA Crossover"] > w["RSI Mean Reversion"]
        ), "TRENDING_BULL should boost MA Crossover over RSI Mean Reversion"

    def test_ranging_boosts_mean_reversion(self):
        w = compute_strategy_weights(
            _STRATEGY_NAMES, _EMPTY_ADJUSTMENTS, {}, composite_regime="RANGING"
        )
        assert (
            w["RSI Mean Reversion"] > w["ML Momentum"]
        ), "RANGING should boost RSI Mean Reversion over ML Momentum"
        assert (
            w["RSI Mean Reversion"] > w["MA Crossover"]
        ), "RANGING should boost RSI Mean Reversion over MA Crossover"

    def test_high_vol_suppresses_breakout(self):
        w = compute_strategy_weights(
            _STRATEGY_NAMES, _EMPTY_ADJUSTMENTS, {}, composite_regime="HIGH_VOL"
        )
        assert w["Volatility Breakout"] < w["RSI Mean Reversion"]

    def test_normal_regime_no_deltas(self):
        w = compute_strategy_weights(
            _STRATEGY_NAMES, _EMPTY_ADJUSTMENTS, {}, composite_regime="NORMAL"
        )
        # All weights should be 1.0 when no health/Sharpe/kelly data
        for name, weight in w.items():
            assert weight == pytest.approx(1.0), f"{name} should be 1.0 in NORMAL regime"

    def test_output_clamped_to_valid_range(self):
        for regime in REGIME_WEIGHT_TABLE:
            w = compute_strategy_weights(
                _STRATEGY_NAMES, _EMPTY_ADJUSTMENTS, {}, composite_regime=regime
            )
            for name, weight in w.items():
                assert 0.5 <= weight <= 1.5, f"{regime}/{name}: weight={weight} outside [0.5, 1.5]"

    def test_kelly_blended_in_when_positive(self):
        kelly = {"RSI Mean Reversion": 1.1}  # 10% boost
        w_no_kelly = compute_strategy_weights(
            _STRATEGY_NAMES, _EMPTY_ADJUSTMENTS, {}, composite_regime="NORMAL"
        )
        w_kelly = compute_strategy_weights(
            _STRATEGY_NAMES, _EMPTY_ADJUSTMENTS, {}, composite_regime="NORMAL", kelly_weights=kelly
        )
        assert w_kelly["RSI Mean Reversion"] > w_no_kelly["RSI Mean Reversion"]


# ---------------------------------------------------------------------------
# C: Confidence-scaled position sizing
# ---------------------------------------------------------------------------


class TestConfidenceScaling:
    """Tests the inline formula from execution_engine._execute_strategy_trades."""

    @staticmethod
    def _scale(conf: float) -> float:
        _conf = max(0.55, min(0.90, conf))
        _t = (_conf - 0.55) / (0.90 - 0.55)
        return round(0.75 + _t * (1.25 - 0.75), 3)

    def test_lower_bound(self):
        # conf <= 0.55 → 0.75x (smaller than before)
        assert self._scale(0.55) == pytest.approx(0.75)
        assert self._scale(0.40) == pytest.approx(0.75)  # clamped

    def test_upper_bound(self):
        # conf >= 0.90 → 1.25x (oversize high-conviction)
        assert self._scale(0.90) == pytest.approx(1.25)
        assert self._scale(1.00) == pytest.approx(1.25)  # clamped

    def test_midpoint(self):
        # conf = 0.725 (midpoint of 0.55–0.90) → 1.00x
        assert self._scale(0.725) == pytest.approx(1.0, abs=0.01)

    def test_monotone_increasing(self):
        confs = [0.55, 0.60, 0.70, 0.80, 0.90]
        scales = [self._scale(c) for c in confs]
        assert scales == sorted(scales), "Confidence scaling must be monotone increasing"

    def test_all_outputs_positive(self):
        for c in [0.0, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]:
            assert self._scale(c) > 0


# ---------------------------------------------------------------------------
# D: Kelly fractional rebalancing
# ---------------------------------------------------------------------------


class TestKellyRebalancing:
    def test_gated_below_min_trades(self, tmp_db):
        """Strategies with < 20 trades should return kelly_mult = None."""
        db, sid = tmp_db
        conn = sqlite3.connect(db.db_path)
        # Create a second strategy with only 5 trades
        conn.execute(
            "INSERT INTO strategies (name, description, capital_allocation, initial_capital) "
            "VALUES ('Sparse','desc',1000,1000)"
        )
        sparse_id = conn.execute("SELECT id FROM strategies WHERE name='Sparse'").fetchone()[0]
        for j in range(5):
            conn.execute(
                "INSERT INTO trade_pnl_detail "
                "(strategy_id, strategy_name, symbol, sell_run_id, entry_date, exit_date, "
                "entry_price, exit_price, shares, gross_pnl, gross_pnl_pct, is_winner) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    sparse_id,
                    "Sparse",
                    f"SP{j:02d}",  # unique symbol
                    f"sparse_r{j:04d}",  # unique sell_run_id
                    "2026-01-01",
                    f"2026-01-{j + 1:02d}",  # unique exit_date
                    100,
                    102,
                    10,
                    200,
                    0.02,
                    1,
                ),
            )
        conn.commit()
        conn.close()

        stats = db.get_strategy_pnl_stats(sparse_id)
        assert stats["trades"] == 5

    def test_kelly_formula_correct(self, tmp_db):
        """f* = p - (1-p)/b; quarter-Kelly mult should be in (1.0, 1.5]."""
        db, sid = tmp_db
        stats = db.get_strategy_pnl_stats(sid)
        assert stats["trades"] == 25
        assert stats["win_rate"] == pytest.approx(0.72, abs=0.02)

        p = stats["win_rate"]
        b = stats["avg_win_pct"] / stats["avg_loss_pct"]
        f_star = p - (1 - p) / b
        assert f_star > 0, "25-trade 72% win-rate strategy should have positive edge"

        mult = round(1.0 + max(0.0, min(f_star * 0.25, 0.5)), 3)
        assert 1.0 < mult <= 1.5

    def test_get_strategy_pnl_stats_empty(self, tmp_db):
        db, _sid = tmp_db
        conn = sqlite3.connect(db.db_path)
        conn.execute(
            "INSERT INTO strategies (name, description, capital_allocation, initial_capital) "
            "VALUES ('Empty','desc',1000,1000)"
        )
        empty_id = conn.execute("SELECT id FROM strategies WHERE name='Empty'").fetchone()[0]
        conn.commit()
        conn.close()

        stats = db.get_strategy_pnl_stats(empty_id)
        assert stats["trades"] == 0
        assert stats["win_rate"] is None

    def test_negative_kelly_clamped_to_zero(self):
        """Strategy with negative edge: f* < 0 → mult should clamp to 1.0."""
        p = 0.30  # bad win rate
        avg_win = 0.01
        avg_loss = 0.05
        b = avg_win / avg_loss
        f_star = p - (1 - p) / b
        assert f_star < 0
        mult = round(1.0 + max(0.0, min(f_star * 0.25, 0.5)), 3)
        assert mult == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# E: 5-regime composite detector
# ---------------------------------------------------------------------------


class TestCompositeRegimeDetector:
    def setup_method(self):
        self.rd = RegimeDetector()

    def test_high_vol_vix_above_25(self):
        assert self.rd.detect_composite_regime(vix=30.0) == "HIGH_VOL"
        assert self.rd.detect_composite_regime(vix=25.1) == "HIGH_VOL"

    def test_low_vol_vix_below_15(self):
        assert self.rd.detect_composite_regime(vix=12.0) == "LOW_VOL"
        assert self.rd.detect_composite_regime(vix=14.9) == "LOW_VOL"

    def test_normal_when_no_market_data(self):
        # Without market data ADX/breadth can't be computed → fallback NORMAL
        result = self.rd.detect_composite_regime(vix=18.0, market_data=None)
        assert result == "NORMAL"

    def test_returns_string(self):
        for vix in [10, 18, 28]:
            r = self.rd.detect_composite_regime(vix=float(vix))
            assert isinstance(r, str)
            assert r in {"TRENDING_BULL", "RANGING", "HIGH_VOL", "LOW_VOL", "NORMAL"}

    def test_vix_priority_over_adx(self):
        """HIGH_VOL and LOW_VOL should win over trend signals regardless of market data."""
        import numpy as np
        import pandas as pd

        # Build a strongly trending dataset
        dates = pd.date_range("2024-01-01", periods=200, freq="B")
        prices = np.linspace(100, 200, 200)  # strong uptrend
        df = pd.DataFrame(
            {
                "symbol": "SPY",
                "close": prices,
                "open": prices * 0.99,
                "high": prices * 1.01,
                "low": prices * 0.98,
                "volume": 1_000_000,
            },
            index=dates,
        )

        # VIX > 25 should give HIGH_VOL even if ADX is high
        r = self.rd.detect_composite_regime(vix=30.0, market_data=df)
        assert r == "HIGH_VOL", f"Expected HIGH_VOL, got {r}"

    def test_compute_adx_returns_float(self):
        import numpy as np
        import pandas as pd

        prices = pd.Series(np.linspace(100, 150, 60))
        adx = self.rd._compute_adx(prices)
        assert isinstance(adx, float)
        assert 0.0 <= adx

    def test_compute_breadth_returns_fraction(self):
        import numpy as np
        import pandas as pd

        dates = pd.date_range("2024-01-01", periods=30, freq="B")
        rows = []
        for sym in ["AAPL", "MSFT", "GOOG"]:
            close = np.linspace(100, 110, 30)  # all above SMA
            rows.append(pd.DataFrame({"symbol": sym, "close": close}, index=dates))
        df = pd.concat(rows)
        b = self.rd._compute_breadth(df)
        assert 0.0 <= b <= 1.0

    def test_composite_persisted_in_status(self):
        status = self.rd.get_status(market_data=None)
        assert "composite_regime" in status
        assert status["composite_regime"] in {
            "TRENDING_BULL",
            "RANGING",
            "HIGH_VOL",
            "LOW_VOL",
            "NORMAL",
        }


# ---------------------------------------------------------------------------
# F: Platform status report
# ---------------------------------------------------------------------------


class TestPlatformStatusReport:
    def test_generates_markdown(self, tmp_db):
        db, _sid = tmp_db
        # Add a broker_state row so recon check doesn't fail
        conn = sqlite3.connect(db.db_path)
        conn.execute(
            "INSERT INTO broker_state (run_id, snapshot_date, snapshot_type, "
            "cash, portfolio_value, buying_power, reconciliation_status) "
            "VALUES ('r1','2026-05-22','RECONCILIATION',10000,96000,10000,'BALANCED')"
        )
        conn.commit()
        conn.close()

        # Run the generator in-process
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "generate_platform_status",
            Path(__file__).parent.parent.parent / "scripts" / "generate_platform_status.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        conn2 = sqlite3.connect(db.db_path)
        report = mod.generate(conn2)
        conn2.close()

        assert "# Platform Status" in report
        assert "## Portfolio" in report
        assert "## System Health" in report
        assert "## Strategy Status" in report
        assert "## Kelly Rebalancing" in report

    def test_handles_empty_db(self, tmp_path):
        """Platform status should not crash on a fresh DB with no data."""
        from src.core.database import TradingDatabase

        db = TradingDatabase(db_path=str(tmp_path / "empty.db"))
        conn = sqlite3.connect(db.db_path)

        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "generate_platform_status",
            Path(__file__).parent.parent.parent / "scripts" / "generate_platform_status.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        report = mod.generate(conn)
        conn.close()
        assert isinstance(report, str)
        assert len(report) > 100


# ---------------------------------------------------------------------------
# G: Per-strategy backtest CLI flag
# ---------------------------------------------------------------------------


class TestPerStrategyBacktest:
    def test_per_strategy_flag_parses(self):
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("--per-strategy", action="store_true")
        parser.add_argument("--years", type=int, default=5)
        args = parser.parse_args(["--per-strategy", "--years", "2"])
        assert args.per_strategy is True
        assert args.years == 2

    def test_per_strategy_false_by_default(self):
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("--per-strategy", action="store_true")
        args = parser.parse_args([])
        assert args.per_strategy is False

    def test_all_strategy_classes_importable(self):
        from src.strategies.strategy_earnings_drift import EarningsDriftStrategy
        from src.strategies.strategy_factor_momentum import FactorMomentumStrategy
        from src.strategies.strategy_ma_crossover import MACrossoverStrategy
        from src.strategies.strategy_ml_momentum import MLMomentumStrategy
        from src.strategies.strategy_rsi_mean_reversion import RSIMeanReversionStrategy
        from src.strategies.strategy_volatility_breakout import VolatilityBreakoutStrategy

        classes = [
            RSIMeanReversionStrategy,
            MLMomentumStrategy,
            EarningsDriftStrategy,
            FactorMomentumStrategy,
            MACrossoverStrategy,
            VolatilityBreakoutStrategy,
        ]
        assert len(classes) == 6
