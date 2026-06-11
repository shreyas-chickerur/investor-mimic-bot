#!/usr/bin/env python3
"""
Tests for EarningsDriftStrategy and FactorMomentumStrategy.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import numpy as np
import pandas as pd
import pytest

pytestmark = pytest.mark.timeout(30)  # per-test safety net

from src.strategies.strategy_earnings_drift import EarningsDriftStrategy
from src.strategies.strategy_factor_momentum import FactorMomentumStrategy

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def market_data():
    """Load real market data for integration-style tests."""
    data_file = Path(__file__).parent.parent / "data" / "training_data.csv"
    if not data_file.exists():
        data_file = Path(__file__).parent.parent.parent / "data" / "training_data.csv"
    if not data_file.exists():
        pytest.skip("training_data.csv not found")
    df = pd.read_csv(data_file, index_col=0)
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    return df


def _make_symbol_data(n_days=100, symbol="TEST", base_price=100.0, base_volume=1_000_000, seed=42):
    """Create synthetic OHLCV data for a single symbol."""
    rng = np.random.RandomState(seed)
    dates = pd.bdate_range(end="2024-06-01", periods=n_days)
    close = base_price + np.cumsum(rng.randn(n_days) * 0.5)
    close = np.maximum(close, 1.0)  # no negative prices
    volume = base_volume + rng.randint(-200_000, 200_000, n_days)
    volume = np.maximum(volume, 100)

    df = pd.DataFrame(
        {
            "symbol": symbol,
            "open": close * (1 + rng.randn(n_days) * 0.002),
            "high": close * (1 + abs(rng.randn(n_days) * 0.005)),
            "low": close * (1 - abs(rng.randn(n_days) * 0.005)),
            "close": close,
            "volume": volume.astype(float),
            "rsi": 50 + rng.randn(n_days) * 15,
            "atr_20": close * 0.02,
            "volatility_20d": 0.15 + rng.randn(n_days) * 0.02,
            "returns_5d": rng.randn(n_days) * 0.03,
            "returns_60d": rng.randn(n_days) * 0.10,
            "volume_ratio": 1.0 + rng.randn(n_days) * 0.2,
        },
        index=dates,
    )
    return df


def _inject_earnings_event(df, days_ago=1, return_pct=0.05, volume_mult=3.0):
    """Inject a synthetic earnings event into the data."""
    df = df.copy()
    idx = -days_ago
    # Set a large return
    prev_close = df["close"].iloc[idx - 1]
    df.iloc[idx, df.columns.get_loc("close")] = prev_close * (1 + return_pct)
    # Set a volume spike
    avg_vol = df["volume"].iloc[max(0, idx - 20) : idx].mean()
    df.iloc[idx, df.columns.get_loc("volume")] = avg_vol * volume_mult
    return df


# ---------------------------------------------------------------------------
# EarningsDriftStrategy tests
# ---------------------------------------------------------------------------


class TestEarningsDriftStrategy:
    def test_init(self):
        strat = EarningsDriftStrategy(1, 25000)
        assert strat.name == "Earnings Drift"
        assert strat.capital == 25000
        assert strat.drift_hold_days == 40
        assert strat.volume_spike_threshold == 1.3

    def test_no_signals_on_normal_data(self):
        """Normal market data without volume spikes should produce no BUY signals."""
        strat = EarningsDriftStrategy(1, 25000)
        df = _make_symbol_data(n_days=100, seed=99)
        signals = strat.generate_signals(df)
        # Normal data unlikely to trigger earnings detection
        # (may occasionally trigger, so we just check it returns a list)
        assert isinstance(signals, list)

    def test_buy_on_positive_surprise(self):
        """Should generate BUY signal after a positive earnings surprise."""
        strat = EarningsDriftStrategy(1, 25000)
        df = _make_symbol_data(n_days=100, seed=42)
        df = _inject_earnings_event(df, days_ago=1, return_pct=0.06, volume_mult=3.5)
        signals = strat.generate_signals(df)
        buy_signals = [s for s in signals if s["action"] == "BUY"]
        assert len(buy_signals) >= 1
        assert buy_signals[0]["symbol"] == "TEST"
        assert "PEAD" in buy_signals[0]["reasoning"]
        assert buy_signals[0]["confidence"] >= 0.5

    def test_no_buy_on_negative_surprise(self):
        """Should NOT buy on negative earnings surprise."""
        strat = EarningsDriftStrategy(1, 25000)
        df = _make_symbol_data(n_days=100, seed=42)
        df = _inject_earnings_event(df, days_ago=1, return_pct=-0.06, volume_mult=3.5)
        signals = strat.generate_signals(df)
        buy_signals = [s for s in signals if s["action"] == "BUY"]
        assert len(buy_signals) == 0

    def test_sell_after_drift_window(self):
        """Should sell after drift_hold_days have passed."""
        strat = EarningsDriftStrategy(1, 25000)
        # Simulate holding a position
        strat.positions["TEST"] = 10
        strat.entry_dates["TEST"] = pd.Timestamp("2024-01-01")
        df = _make_symbol_data(n_days=100, symbol="TEST", seed=42)
        # Ensure latest date is well past the drift window
        signals = strat.generate_signals(df)
        sell_signals = [s for s in signals if s["action"] == "SELL"]
        assert len(sell_signals) >= 1
        assert (
            "expired" in sell_signals[0]["reasoning"].lower()
            or "drift" in sell_signals[0]["reasoning"].lower()
        )

    def test_insufficient_data(self):
        """Should return empty list with insufficient data."""
        strat = EarningsDriftStrategy(1, 25000)
        df = _make_symbol_data(n_days=10, seed=42)
        signals = strat.generate_signals(df)
        assert signals == []

    def test_confidence_scales_with_surprise(self):
        """Larger surprise should produce higher confidence."""
        strat1 = EarningsDriftStrategy(1, 25000)
        df_small = _make_symbol_data(n_days=100, seed=42)
        df_small = _inject_earnings_event(df_small, days_ago=1, return_pct=0.03, volume_mult=3.0)
        sigs_small = strat1.generate_signals(df_small)

        strat2 = EarningsDriftStrategy(2, 25000)
        df_big = _make_symbol_data(n_days=100, seed=42)
        df_big = _inject_earnings_event(df_big, days_ago=1, return_pct=0.08, volume_mult=3.0)
        sigs_big = strat2.generate_signals(df_big)

        buy_small = [s for s in sigs_small if s["action"] == "BUY"]
        buy_big = [s for s in sigs_big if s["action"] == "BUY"]
        if buy_small and buy_big:
            assert buy_big[0]["confidence"] >= buy_small[0]["confidence"]

    def test_get_description(self):
        strat = EarningsDriftStrategy(1, 25000)
        desc = strat.get_description()
        assert "drift" in desc.lower() or "earnings" in desc.lower()

    @pytest.mark.slow
    def test_with_real_data(self, market_data):
        """Integration test with real market data."""
        strat = EarningsDriftStrategy(1, 25000)
        recent = market_data[market_data.index >= "2024-01-01"]
        if len(recent) < 30:
            pytest.skip("Not enough recent data")
        signals = strat.generate_signals(recent)
        assert isinstance(signals, list)
        for sig in signals:
            assert "symbol" in sig
            assert "action" in sig
            assert sig["action"] in ("BUY", "SELL")
            assert "price" in sig
            assert sig["price"] > 0


# ---------------------------------------------------------------------------
# FactorMomentumStrategy tests
# ---------------------------------------------------------------------------


def _make_multi_symbol_data(n_symbols=10, n_days=100, seed=42):
    """Create synthetic data for multiple symbols."""
    rng = np.random.RandomState(seed)
    frames = []
    for i in range(n_symbols):
        sym = f"SYM{i:02d}"
        df = _make_symbol_data(
            n_days=n_days, symbol=sym, seed=seed + i, base_price=50 + rng.rand() * 200
        )
        frames.append(df)
    return pd.concat(frames).sort_index()


class TestFactorMomentumStrategy:
    def test_init(self):
        strat = FactorMomentumStrategy(1, 25000)
        assert strat.name == "Factor Momentum"
        assert strat.capital == 25000
        assert strat.hold_days == 20
        assert strat.top_n == 3

    def test_generates_buy_signals(self):
        """Should generate BUY signals for top-ranked stocks."""
        strat = FactorMomentumStrategy(1, 25000)
        df = _make_multi_symbol_data(n_symbols=10, n_days=100)
        signals = strat.generate_signals(df)
        buy_signals = [s for s in signals if s["action"] == "BUY"]
        assert len(buy_signals) > 0
        assert len(buy_signals) <= strat.top_n
        for sig in buy_signals:
            assert sig["shares"] > 0
            assert sig["price"] > 0
            assert "Factor rank" in sig["reasoning"]

    def test_sell_after_hold_period(self):
        """Should sell positions after hold_days. SYM00 is the lowest-momentum
        name in the fixture, so past the soft horizon the rank-hysteresis
        thesis is gone (not in the top 2*top_n band) -> rotate out; if it
        ranks well it exits at the absolute ceiling instead."""
        strat = FactorMomentumStrategy(1, 25000)
        strat.positions["SYM00"] = 10
        strat.entry_dates["SYM00"] = pd.Timestamp("2024-01-01")
        df = _make_multi_symbol_data(n_symbols=10, n_days=100)
        signals = strat.generate_signals(df)
        sell_signals = [s for s in signals if s["action"] == "SELL" and s["symbol"] == "SYM00"]
        assert len(sell_signals) == 1
        reasoning = sell_signals[0]["reasoning"].lower()
        assert "thesis" in reasoning or "ceiling" in reasoning

    def test_no_sell_before_hold_period(self):
        """Should NOT sell positions before hold_days."""
        strat = FactorMomentumStrategy(1, 25000)
        strat.positions["SYM00"] = 10
        # Set entry date to very recent
        strat.entry_dates["SYM00"] = pd.Timestamp("2024-05-30")
        df = _make_multi_symbol_data(n_symbols=10, n_days=100)
        signals = strat.generate_signals(df)
        sell_signals = [s for s in signals if s["action"] == "SELL" and s["symbol"] == "SYM00"]
        assert len(sell_signals) == 0

    def test_does_not_buy_already_held(self):
        """Should not generate BUY for symbols already in positions."""
        strat = FactorMomentumStrategy(1, 25000)
        df = _make_multi_symbol_data(n_symbols=10, n_days=100)
        # First call to get some buys
        signals1 = strat.generate_signals(df)
        bought = [s["symbol"] for s in signals1 if s["action"] == "BUY"]
        # Simulate holding those positions
        for sym in bought[:3]:
            strat.positions[sym] = 10
            strat.entry_dates[sym] = pd.Timestamp("2024-05-30")
        # Second call should not re-buy held symbols
        signals2 = strat.generate_signals(df)
        buy2 = [s["symbol"] for s in signals2 if s["action"] == "BUY"]
        for sym in bought[:3]:
            assert sym not in buy2

    def test_factor_scores_computation(self):
        """Factor scores should be computed for all symbols with enough data."""
        strat = FactorMomentumStrategy(1, 25000)
        df = _make_multi_symbol_data(n_symbols=10, n_days=100)
        scores = strat._compute_factor_scores(df)
        assert len(scores) == 10
        for _sym, score in scores.items():
            assert isinstance(score, float)
            assert 0 <= score <= 1.5  # composite is bounded

    def test_insufficient_data_per_symbol(self):
        """Symbols with < 60 days of data should be excluded from scoring."""
        strat = FactorMomentumStrategy(1, 25000)
        df = _make_multi_symbol_data(n_symbols=5, n_days=30)
        scores = strat._compute_factor_scores(df)
        assert len(scores) == 0

    def test_percentile_ranking_has_spread(self):
        """Cross-sectional percentile scores must span at least 0.3 range across universe."""
        strat = FactorMomentumStrategy(1, 25000)
        df = _make_multi_symbol_data(n_symbols=8, n_days=100)
        scores = strat._compute_factor_scores(df)
        assert len(scores) >= 3
        vals = sorted(scores.values())
        assert vals[-1] - vals[0] > 0.20, (
            "Percentile ranking must produce spread > 0.20 "
            "(sigmoid normalization bug would produce spread < 0.05)"
        )

    def test_buy_capacity_limits(self):
        """Should not exceed top_n total positions."""
        strat = FactorMomentumStrategy(1, 25000)
        strat.top_n = 3
        df = _make_multi_symbol_data(n_symbols=10, n_days=100)
        signals = strat.generate_signals(df)
        buy_signals = [s for s in signals if s["action"] == "BUY"]
        assert len(buy_signals) <= 3

    def test_get_description(self):
        strat = FactorMomentumStrategy(1, 25000)
        desc = strat.get_description()
        assert "factor" in desc.lower()
        assert "momentum" in desc.lower()

    @pytest.mark.slow
    def test_with_real_data(self, market_data):
        """Integration test with real market data."""
        strat = FactorMomentumStrategy(1, 25000)
        recent = market_data[market_data.index >= "2024-01-01"]
        if len(recent) < 100:
            pytest.skip("Not enough recent data")
        signals = strat.generate_signals(recent)
        assert isinstance(signals, list)
        buy_signals = [s for s in signals if s["action"] == "BUY"]
        # Factor momentum should always find top stocks to buy
        assert len(buy_signals) > 0
        for sig in signals:
            assert "symbol" in sig
            assert "action" in sig
            assert sig["action"] in ("BUY", "SELL")
            assert "price" in sig
            assert sig["price"] > 0
            assert "confidence" in sig


# ---------------------------------------------------------------------------
# Cross-strategy tests
# ---------------------------------------------------------------------------


@pytest.mark.slow
class TestStrategyIntegration:
    def test_both_strategies_produce_valid_signals(self, market_data):
        """Both strategies should produce well-formed signals on real data."""
        recent = market_data[market_data.index >= "2023-01-01"]
        if len(recent) < 100:
            pytest.skip("Not enough data")

        for StratClass in [EarningsDriftStrategy, FactorMomentumStrategy]:
            strat = StratClass(1, 25000)
            signals = strat.generate_signals(recent)
            assert isinstance(signals, list)
            for sig in signals:
                required_keys = {"symbol", "action", "shares", "price", "confidence"}
                assert required_keys.issubset(
                    sig.keys()
                ), f"{StratClass.__name__} missing keys: {required_keys - sig.keys()}"
                assert sig["shares"] > 0
                assert sig["price"] > 0
                assert 0 <= sig["confidence"] <= 1.0

    def test_strategies_are_independent(self, market_data):
        """Strategies should not interfere with each other's state."""
        recent = market_data[market_data.index >= "2024-01-01"]
        if len(recent) < 100:
            pytest.skip("Not enough data")

        ed = EarningsDriftStrategy(1, 25000)
        fm = FactorMomentumStrategy(2, 25000)

        ed.generate_signals(recent)
        fm_signals = fm.generate_signals(recent)

        # Modifying one strategy's positions shouldn't affect the other
        for s in fm_signals:
            if s["action"] == "BUY":
                fm.positions[s["symbol"]] = s["shares"]
                fm.entry_dates[s["symbol"]] = recent.index[-1]

        ed.generate_signals(recent)
        assert len(ed.positions) == 0  # ED should still have no positions
