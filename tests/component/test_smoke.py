"""
Smoke tests — verify the full pipeline initialises and runs against synthetic data
without a live broker connection.

These are intentionally narrow: they test that the wiring between components
is correct (no import errors, no AttributeError on early exit paths, no schema
migration crashes) rather than trading logic.  Strategy unit tests cover signal
correctness; these tests cover the integration seams.
"""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _synthetic_market_data(symbols=None, n_days=60) -> pd.DataFrame:
    """Return a synthetic OHLCV + indicators DataFrame for smoke testing."""
    if symbols is None:
        symbols = ["AAPL", "MSFT", "SPY", "GOOGL", "AMZN"]

    rng = np.random.default_rng(42)
    dates = pd.bdate_range(end=datetime.now().date(), periods=n_days)
    rows = []
    for sym in symbols:
        price = 100.0
        for _dt in dates:
            change = rng.normal(0, 0.01)
            price = max(10.0, price * (1 + change))
            volume = int(rng.integers(1_000_000, 5_000_000))
            rows.append(
                {
                    "symbol": sym,
                    "open": price * (1 + rng.uniform(-0.005, 0.005)),
                    "high": price * (1 + rng.uniform(0, 0.01)),
                    "low": price * (1 - rng.uniform(0, 0.01)),
                    "close": price,
                    "adjusted_close": price,
                    "volume": volume,
                    "rsi": rng.uniform(30, 70),
                    "atr_20": price * 0.015,
                    "sma_20": price * rng.uniform(0.97, 1.03),
                    "sma_50": price * rng.uniform(0.95, 1.05),
                    "sma_100": price * rng.uniform(0.90, 1.10),
                    "sma_200": price * rng.uniform(0.85, 1.15),
                    "volume_ratio": rng.uniform(0.8, 1.5),
                    "returns_5d": rng.uniform(-0.05, 0.05),
                    "returns_20d": rng.uniform(-0.10, 0.10),
                    "returns_60d": rng.uniform(-0.15, 0.15),
                    "volatility_20d": rng.uniform(0.10, 0.30),
                    "volatility_60d": rng.uniform(0.10, 0.30),
                    "price_to_sma20": rng.uniform(0.95, 1.05),
                    "price_to_sma50": rng.uniform(0.92, 1.08),
                    "adx": rng.uniform(15, 35),
                    "vwap": price * rng.uniform(0.98, 1.02),
                    "bb_upper": price * 1.02,
                    "bb_lower": price * 0.98,
                    "bb_middle": price,
                    "future_return_5d": rng.uniform(-0.05, 0.05),
                }
            )
    df = pd.DataFrame(rows)
    df.index = pd.DatetimeIndex([r for sym in symbols for r in dates])
    df.index.name = "date"
    return df


def _mock_alpaca_account(portfolio_value=100_000.0):
    acc = MagicMock()
    acc.portfolio_value = portfolio_value
    acc.cash = portfolio_value * 0.20
    acc.buying_power = portfolio_value * 0.20
    return acc


# ---------------------------------------------------------------------------
# Strategy smoke tests — every strategy generates signals without crashing
# ---------------------------------------------------------------------------


class TestStrategiesSmoke:
    def test_rsi_generates_signals(self):
        from src.strategies.strategy_rsi_mean_reversion import RSIMeanReversionStrategy

        strat = RSIMeanReversionStrategy(strategy_id=1, capital=10_000)
        data = _synthetic_market_data()
        signals = strat.generate_signals(data)
        assert isinstance(signals, list)

    def test_ml_momentum_generates_signals(self):
        from src.strategies.strategy_ml_momentum import MLMomentumStrategy

        strat = MLMomentumStrategy(strategy_id=2, capital=10_000)
        data = _synthetic_market_data(n_days=80)
        signals = strat.generate_signals(data)
        assert isinstance(signals, list)

    def test_earnings_drift_generates_signals(self):
        from src.strategies.strategy_earnings_drift import EarningsDriftStrategy

        strat = EarningsDriftStrategy(strategy_id=3, capital=10_000)
        data = _synthetic_market_data()
        signals = strat.generate_signals(data)
        assert isinstance(signals, list)

    def test_factor_momentum_generates_signals(self):
        from src.strategies.strategy_factor_momentum import FactorMomentumStrategy

        strat = FactorMomentumStrategy(strategy_id=4, capital=10_000)
        data = _synthetic_market_data()
        signals = strat.generate_signals(data)
        assert isinstance(signals, list)

    def test_ma_crossover_generates_signals(self):
        from src.strategies.strategy_ma_crossover import MACrossoverStrategy

        strat = MACrossoverStrategy(strategy_id=5, capital=10_000)
        data = _synthetic_market_data()
        signals = strat.generate_signals(data)
        assert isinstance(signals, list)

    def test_volatility_breakout_generates_signals(self):
        from src.strategies.strategy_volatility_breakout import VolatilityBreakoutStrategy

        strat = VolatilityBreakoutStrategy(strategy_id=6, capital=10_000)
        data = _synthetic_market_data()
        signals = strat.generate_signals(data)
        assert isinstance(signals, list)

    def test_news_sentiment_generates_signals(self):
        from src.strategies.strategy_news_sentiment import NewsSentimentStrategy

        strat = NewsSentimentStrategy(strategy_id=7, capital=10_000)
        data = _synthetic_market_data()
        # Patch the underlying news provider to avoid real network calls
        with patch("src.strategies.strategy_news_sentiment.NewsSentimentProvider") as mock_p:
            mock_p.return_value.get_sentiment.return_value = {}
            mock_p.return_value.get_usage_summary.return_value = {}
            signals = strat.generate_signals(data)
        assert isinstance(signals, list)


# ---------------------------------------------------------------------------
# Database smoke tests — schema migration runs cleanly
# ---------------------------------------------------------------------------


class TestDatabaseSmoke:
    def test_init_and_schema(self, tmp_path):
        from src.core.database import TradingDatabase

        TradingDatabase(db_path=str(tmp_path / "smoke.db"))
        # Verify critical tables exist
        import sqlite3

        with sqlite3.connect(str(tmp_path / "smoke.db")) as conn:
            tables = {
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        for expected in [
            "trades",
            "positions",
            "order_intents",
            "tax_lots",
            "trade_pnl_detail",
            "signal_funnel",
        ]:
            assert expected in tables, f"Missing table: {expected}"

    def test_tax_lot_recording(self, tmp_path):
        from src.core.database import TradingDatabase

        db = TradingDatabase(db_path=str(tmp_path / "tax.db"))
        db.record_tax_lot(
            strategy_id=1,
            symbol="AAPL",
            buy_date="2026-01-02",
            buy_price=150.0,
            quantity=10.0,
        )
        result = db.fifo_match_sell(
            strategy_id=1, symbol="AAPL", sell_quantity=5.0, sell_price=160.0
        )
        assert result in ("STCG", "LTCG", "MIXED")

    def test_wash_sale_detection(self, tmp_path):
        from src.core.database import TradingDatabase

        db = TradingDatabase(db_path=str(tmp_path / "wash.db"))
        # No recent loss sale — should return False
        assert not db.was_sold_at_loss_recently("AAPL", strategy_id=1, days=30)


# ---------------------------------------------------------------------------
# Kill switch smoke test — fires and returns gracefully
# ---------------------------------------------------------------------------


class TestKillSwitchSmoke:
    def test_drawdown_kill_fires(self):
        from src.utils.kill_switch_service import KillSwitchService

        db = MagicMock()
        db.get_consecutive_failed_runs.return_value = 0
        email = MagicMock()
        ks = KillSwitchService(db, email)
        ctx = {
            "reconciliation_status": "PASS",
            "daily_drawdown": 0.06,  # 6% > 5% threshold
            "consecutive_failures": 0,
            "rejected_orders_count": 0,
            "total_orders": 1,
        }
        result = ks.check_all_switches(ctx)
        assert result is False
        assert ks.is_killed

    def test_healthy_context_passes(self):
        from src.utils.kill_switch_service import KillSwitchService

        db = MagicMock()
        email = MagicMock()
        ks = KillSwitchService(db, email)
        ctx = {
            "reconciliation_status": "PASS",
            "daily_drawdown": 0.02,
            "consecutive_failures": 0,
            "rejected_orders_count": 0,
            "total_orders": 5,
        }
        assert ks.check_all_switches(ctx) is True


# ---------------------------------------------------------------------------
# Stop-loss manager smoke test
# ---------------------------------------------------------------------------


class TestStopLossManagerSmoke:
    def test_audit_repairs_orphan(self, tmp_path):
        from src.risk.stop_loss_manager import StopLossManager

        mgr = StopLossManager(atr_multiplier=2.5)
        positions = [{"symbol": "AAPL", "avg_price": 150.0, "atr": 2.0, "shares": 10}]
        prices = {"AAPL": 155.0}
        repaired = mgr.audit_and_repair_stops(positions, prices)
        assert "AAPL" in repaired
        assert "AAPL" in mgr.stop_levels
        assert mgr.stop_levels["AAPL"] < 155.0
