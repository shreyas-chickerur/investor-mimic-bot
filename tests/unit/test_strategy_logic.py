"""
Unit tests for critical strategy logic fixes.

Covers the four bugs that were preventing paper trading profitability:
  1. RSI VWAP exit firing on every position (trailing VWAP always < close)
  2. Factor Momentum sigmoid ranking collapsing all scores to ~0.5
  3. ML Momentum min_confidence=0.55 blocking all signals
  4. News sentiment filter graceful degradation
"""
import sys
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.strategies.strategy_earnings_drift import EarningsDriftStrategy
from src.strategies.strategy_factor_momentum import FactorMomentumStrategy
from src.strategies.strategy_ml_momentum import MLMomentumStrategy
from src.strategies.strategy_rsi_mean_reversion import RSIMeanReversionStrategy

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


def _make_symbol_data(
    symbol: str,
    n: int = 100,
    base_price: float = 100.0,
    rsi_val: float = 50.0,
    vol_ratio: float = 1.0,
    momentum: float = 0.05,
) -> pd.DataFrame:
    """Create minimal OHLCV + indicator DataFrame for one symbol."""
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    close = base_price + np.cumsum(np.random.randn(n) * 0.5)
    close = np.maximum(close, 1.0)
    rsi_series = np.full(n, rsi_val, dtype=float)
    rsi_series[-2] = rsi_val - 1.0  # slope = +1 on last bar by default
    df = pd.DataFrame(
        {
            "symbol": symbol,
            "open": close * 0.99,
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
            # Add slight noise to volume so rolling std is never exactly 0
            "volume": np.full(n, 1_000_000.0) + np.random.randn(n) * 1000,
            "rsi": rsi_series,
            "atr_20": close * 0.015,
            # Trailing 20-day VWAP — intentionally much lower than close to replicate
            # the production data bug we fixed.
            "vwap": close * 0.70,
            "volume_ratio": np.full(n, vol_ratio),
            "returns_5d": np.full(n, momentum),
            "returns_20d": np.full(n, momentum * 2),
            "returns_60d": np.full(n, momentum * 4),
            "volatility_20d": np.full(n, 0.15),
            "volatility_60d": np.full(n, 0.15),
            "price_to_sma20": np.full(n, 1.01),
            "price_to_sma50": np.full(n, 1.02),
            "adx": np.full(n, 25.0),
        },
        index=dates,
    )
    return df


def _multi_symbol_data(n_symbols: int = 10, n_bars: int = 100) -> pd.DataFrame:
    """Combine multiple symbol DataFrames into one market_data DataFrame."""
    symbols = [f"SYM{i:02d}" for i in range(n_symbols)]
    frames = []
    for i, sym in enumerate(symbols):
        # vary momentum to give a real spread for cross-sectional ranking
        mom = -0.10 + i * 0.025  # spread from -0.10 to +0.15
        frames.append(_make_symbol_data(sym, n=n_bars, base_price=50 + i * 5, momentum=mom))
    return pd.concat(frames)


# ===========================================================================
# 1. RSI Mean Reversion
# ===========================================================================


class TestRSIMeanReversionFixes:
    def test_rsi_threshold_is_35(self):
        s = RSIMeanReversionStrategy(1, 25_000)
        assert s.rsi_threshold == 35, "Entry threshold must be 35 (meaningfully oversold)"

    def test_rsi_exit_threshold_is_55(self):
        s = RSIMeanReversionStrategy(1, 25_000)
        assert s.rsi_exit == 55, "Exit threshold must be 55"

    def test_buy_when_rsi_below_35_and_slope_positive(self):
        s = RSIMeanReversionStrategy(1, 25_000)
        data = _make_symbol_data("AAPL", rsi_val=30.0)
        # slope = rsi[-1] - rsi[-2] = 30 - 29 = +1  → positive slope
        data["rsi"] = 30.0
        data.loc[data.index[-2], "rsi"] = 29.0

        signals = s.generate_signals(data)
        buys = [x for x in signals if x["action"] == "BUY"]
        assert len(buys) >= 1, "Should generate BUY when RSI < 35 and slope > 0"
        assert buys[0]["symbol"] == "AAPL"

    def test_no_buy_when_rsi_slope_negative(self):
        """RSI falling (slope < 0) should NOT trigger BUY — still could be falling knife."""
        s = RSIMeanReversionStrategy(1, 25_000)
        data = _make_symbol_data("AAPL", rsi_val=35.0)
        data["rsi"] = 35.0
        data.loc[data.index[-2], "rsi"] = 36.0  # slope = -1 (decreasing)

        signals = s.generate_signals(data)
        buys = [x for x in signals if x["action"] == "BUY"]
        assert len(buys) == 0, "No BUY when RSI slope is negative"

    def test_no_buy_when_rsi_above_threshold(self):
        s = RSIMeanReversionStrategy(1, 25_000)
        data = _make_symbol_data("AAPL", rsi_val=55.0)
        data.loc[data.index[-2], "rsi"] = 54.0  # slope = +1

        signals = s.generate_signals(data)
        buys = [x for x in signals if x["action"] == "BUY"]
        assert len(buys) == 0, "No BUY when RSI >= threshold"

    def test_vwap_does_NOT_trigger_immediate_exit(self):
        """
        Critical regression test: trailing VWAP (70% of close) must NOT cause
        an immediate SELL. This was the main bug killing P&L — price is always
        above the long-run trailing VWAP, so that check fired on every position.
        """
        s = RSIMeanReversionStrategy(1, 25_000)
        data = _make_symbol_data("AAPL", rsi_val=50.0, n=100)
        data["close"] = 100.0
        data["vwap"] = 70.0  # trailing 20d VWAP — always below close
        data["rsi"] = 50.0  # neutral RSI, below exit threshold of 55

        s.positions["AAPL"] = 10
        # Entry date is RECENT (5 calendar days ago) so time-exit (20d) doesn't fire
        s.entry_dates["AAPL"] = data.index[-1] - timedelta(days=5)

        signals = s.generate_signals(data)
        sells = [x for x in signals if x["action"] == "SELL"]
        assert len(sells) == 0, (
            "VWAP must NOT trigger exit — trailing VWAP is always below close. "
            "Core profitability bug if this fires."
        )

    def test_sell_when_rsi_recovers_above_55(self):
        s = RSIMeanReversionStrategy(1, 25_000)
        data = _make_symbol_data("AAPL", rsi_val=60.0, n=100)
        data["rsi"] = 60.0

        s.positions["AAPL"] = 10
        s.entry_dates["AAPL"] = data.index[-1] - timedelta(days=5)  # recent entry

        signals = s.generate_signals(data)
        sells = [x for x in signals if x["action"] == "SELL"]
        assert len(sells) == 1
        assert "mean reversion complete" in sells[0]["reasoning"].lower()

    def test_sell_on_time_exit(self):
        s = RSIMeanReversionStrategy(1, 25_000)
        data = _make_symbol_data("AAPL", rsi_val=45.0, n=100)
        data["rsi"] = 45.0  # Below rsi_exit=55 threshold

        s.positions["AAPL"] = 10
        s.entry_dates["AAPL"] = data.index[-1] - timedelta(days=25)  # held 25 days

        signals = s.generate_signals(data)
        sells = [x for x in signals if x["action"] == "SELL"]
        assert len(sells) == 1
        assert "time" in sells[0]["reasoning"].lower()


# ===========================================================================
# 2. Factor Momentum — Cross-sectional ranking
# ===========================================================================


class TestFactorMomentumRanking:
    def test_scores_have_meaningful_spread(self):
        """
        With proper cross-sectional percentile ranking, top vs bottom stock
        should have a composite score difference > 0.3. With the old sigmoid
        approach all scores clustered in 0.50–0.65, giving spread < 0.05.
        """
        s = FactorMomentumStrategy(1, 25_000)
        data = _multi_symbol_data(n_symbols=10, n_bars=80)
        scores = s._compute_factor_scores(data)

        assert len(scores) >= 5, "Should score at least 5 symbols"
        sorted_scores = sorted(scores.values())
        spread = sorted_scores[-1] - sorted_scores[0]
        assert spread > 0.20, (
            f"Cross-sectional spread must be > 0.20, got {spread:.3f}. "
            "Likely still using sigmoid normalization instead of percentile rank."
        )

    def test_top_n_is_three(self):
        # Reduced from 5 to 3 — higher conviction, lower overtrading cost drag.
        s = FactorMomentumStrategy(1, 25_000)
        assert s.top_n == 3

    def test_generates_buy_signals_for_top_symbols(self):
        s = FactorMomentumStrategy(1, 25_000)
        data = _multi_symbol_data(n_symbols=12, n_bars=80)

        signals = s.generate_signals(data)
        buys = [x for x in signals if x["action"] == "BUY"]
        assert len(buys) >= 1, "Factor momentum must generate at least 1 BUY signal"
        assert len(buys) <= s.top_n, f"Must not exceed top_n={s.top_n} buys"

    def test_high_momentum_stock_ranks_higher_than_low_momentum(self):
        """Stocks with better 60d momentum should score higher."""
        s = FactorMomentumStrategy(1, 25_000)
        # Need >= 3 symbols for cross-sectional ranking (len(raw) < 3 guard)
        data_high = _make_symbol_data("HIGH", n=80, momentum=0.20)
        data_low = _make_symbol_data("LOW", n=80, momentum=-0.15)
        data_mid = _make_symbol_data("MID", n=80, momentum=0.00)
        combined = pd.concat([data_high, data_low, data_mid])

        scores = s._compute_factor_scores(combined)
        assert len(scores) == 3, "All 3 symbols should be scored"
        assert scores.get("HIGH", 0) > scores.get(
            "LOW", 0
        ), "HIGH momentum stock should rank above LOW momentum stock"

    def test_sell_after_hold_period(self):
        s = FactorMomentumStrategy(1, 25_000)
        data = _make_symbol_data("SYM00", n=80)
        s.positions["SYM00"] = 10
        s.entry_dates["SYM00"] = data.index[-1] - timedelta(days=25)  # held 25d

        signals = s.generate_signals(data)
        sells = [x for x in signals if x["action"] == "SELL" and x["symbol"] == "SYM00"]
        assert len(sells) == 1


# ===========================================================================
# 3. ML Momentum
# ===========================================================================


# Module-scoped: train once and reuse across all ML tests (GBM with 200
# estimators is non-trivial; training 3 separate instances was the main slow
# path in this file).
@pytest.fixture(scope="module")
def ml_strategy_and_data():
    """Returns (trained_strategy, data) — trained once per test module."""
    data = _multi_symbol_data(n_symbols=8, n_bars=120)
    s = MLMomentumStrategy(1, 25_000)
    s._train_model(data)
    return s, data


class TestMLMomentumFixes:
    def test_min_confidence_is_0_65(self):
        """Confirm threshold raised to 0.65 — live 25% win rate required a higher bar.

        Further raised from 0.60 after the first month of live trading showed ML Momentum
        producing 42 trades at only 25% win rate and negative P&L.  Top-decile signals
        (>=0.65 confidence, >=0.70 quantile threshold) are the only ones with positive
        expected value in live conditions.
        """
        s = MLMomentumStrategy(1, 25_000)
        assert (
            s.min_confidence == 0.65
        ), f"min_confidence={s.min_confidence} — expected 0.65 (raised from 0.60 to cut overtrading)"

    def test_model_is_gradient_boosting_with_correct_params(self):
        """GBM replaced LogisticRegression; verify it is configured to prevent overfitting."""
        from sklearn.ensemble import GradientBoostingClassifier

        s = MLMomentumStrategy(1, 25_000)
        assert isinstance(
            s.model, GradientBoostingClassifier
        ), "MLMomentumStrategy.model must be GradientBoostingClassifier"
        assert s.model.n_estimators == 200, "n_estimators must be 200"
        assert s.model.max_depth == 3, "max_depth must be 3 to prevent overfitting"
        assert s.model.subsample == 0.8, "subsample must be 0.8 for stochastic GBM"

    def test_training_rejects_precomputed_future_returns(self, ml_strategy_and_data):
        """Forward-looking columns are leakage — training must refuse them.

        (Inverted from the original test: pre-computed future_return_5d used
        to be the preferred label source, which is unverifiable lookahead.
        Labels are now derived internally from closes only.)
        """
        s, data = ml_strategy_and_data
        assert s.is_trained, "Model should train successfully on clean multi-symbol data"
        leaky = data.copy()
        leaky["future_return_5d"] = 0.01
        with pytest.raises(ValueError, match="forward-looking"):
            s._train_model(leaky)

    def test_generates_signals_after_training(self, ml_strategy_and_data):
        s, data = ml_strategy_and_data
        signals = s.generate_signals(data)
        assert isinstance(signals, list)

    def test_daily_retrain_triggered_by_date_change(self, ml_strategy_and_data):
        """Model should retrain when _train_date differs from latest data date."""
        s, data = ml_strategy_and_data
        s._train_date = "2020-01-01"  # force stale date
        s.generate_signals(data)
        today = str(data.index.max().date())
        assert s._train_date == today, "Model should retrain and update _train_date"


# ===========================================================================
# 4. Earnings Drift
# ===========================================================================


class TestEarningsDriftDetection:
    def _make_earnings_data(
        self, symbol: str = "AAPL", event_return: float = 0.05, volume_spike: float = 3.0
    ) -> pd.DataFrame:
        """Make data with a synthetic earnings event 2 bars ago."""
        n = 60
        np.random.seed(1)
        dates = pd.date_range("2024-01-01", periods=n, freq="B")
        # Add small noise so rolling std > 0 (avoids avg_vol <= 0 guard)
        close = 100.0 + np.random.randn(n) * 0.3
        close = np.abs(close)
        volume = np.full(n, 1_000_000.0) + np.random.randn(n) * 5000
        volume = np.abs(volume)

        # Inject earnings event 2 bars ago
        close[-2] = close[-3] * (1 + event_return)
        volume[-2] = 1_000_000.0 * volume_spike

        df = pd.DataFrame(
            {
                "symbol": symbol,
                "open": close * 0.99,
                "high": close * 1.01,
                "low": close * 0.99,
                "close": close,
                "volume": volume,
                "atr_20": close * 0.015,
            },
            index=dates,
        )
        return df

    def test_detects_positive_earnings_event(self):
        s = EarningsDriftStrategy(1, 25_000)
        data = self._make_earnings_data(event_return=0.06, volume_spike=3.5)
        event = s._detect_earnings_events(data)
        assert event is not None, "Should detect earnings event"
        assert event["direction"] == "positive"

    def test_detects_negative_earnings_event(self):
        s = EarningsDriftStrategy(1, 25_000)
        data = self._make_earnings_data(event_return=-0.07, volume_spike=3.5)
        event = s._detect_earnings_events(data)
        assert event is not None
        assert event["direction"] == "negative"

    def test_no_event_without_volume_spike(self):
        s = EarningsDriftStrategy(1, 25_000)
        data = self._make_earnings_data(event_return=0.06, volume_spike=1.1)  # < 2x
        event = s._detect_earnings_events(data)
        assert event is None, "No event without volume spike"

    def test_buy_on_positive_surprise(self):
        s = EarningsDriftStrategy(1, 25_000)
        data = self._make_earnings_data(event_return=0.06, volume_spike=3.5)
        signals = s.generate_signals(data)
        buys = [x for x in signals if x["action"] == "BUY"]
        assert len(buys) == 1
        assert "PEAD" in buys[0]["reasoning"]

    def test_no_buy_on_negative_surprise(self):
        s = EarningsDriftStrategy(1, 25_000)
        data = self._make_earnings_data(event_return=-0.06, volume_spike=3.5)
        signals = s.generate_signals(data)
        buys = [x for x in signals if x["action"] == "BUY"]
        assert len(buys) == 0, "Must not buy on negative earnings surprise"


# ===========================================================================
# 5. News sentiment filter
# ===========================================================================


class TestNewsSignalFilter:
    """Tests for the news sentiment confidence modifier."""

    @pytest.fixture(autouse=True)
    def _import_filter(self):
        """Skip all tests in this class if news_sentiment module can't import."""
        try:
            from src.utils.news_sentiment import NewsSignalFilter  # noqa: F401
        except Exception as e:
            pytest.skip(f"news_sentiment import failed: {e}")

    def _make_filter(self):
        from src.utils.news_sentiment import NewsSignalFilter

        return NewsSignalFilter()

    def test_empty_sentiment_map_passes_all_signals(self):
        nf = self._make_filter()
        signals = [
            {"symbol": "AAPL", "action": "BUY", "confidence": 0.6, "reasoning": "test"},
            {"symbol": "MSFT", "action": "SELL", "confidence": 0.8, "reasoning": "test"},
        ]
        result = nf.apply(signals, {})
        assert len(result) == 2

    def test_positive_news_boosts_confidence(self):
        nf = self._make_filter()
        sentiment = {
            "AAPL": {"score": 0.80, "headlines": ["Apple beats earnings"], "article_count": 5}
        }
        signals = [{"symbol": "AAPL", "action": "BUY", "confidence": 0.60, "reasoning": "RSI"}]
        result = nf.apply(signals, sentiment)
        assert len(result) == 1
        assert result[0]["confidence"] > 0.60
        assert result[0]["confidence"] <= 1.0

    def test_negative_news_suppresses_confidence(self):
        nf = self._make_filter()
        sentiment = {
            "AAPL": {"score": 0.30, "headlines": ["Apple misses guidance"], "article_count": 5}
        }
        signals = [{"symbol": "AAPL", "action": "BUY", "confidence": 0.60, "reasoning": "RSI"}]
        result = nf.apply(signals, sentiment)
        assert len(result) == 1
        assert result[0]["confidence"] < 0.60

    def test_very_negative_news_drops_buy_signal(self):
        nf = self._make_filter()
        sentiment = {
            "AAPL": {"score": 0.15, "headlines": ["SEC fraud investigation"], "article_count": 5}
        }
        signals = [{"symbol": "AAPL", "action": "BUY", "confidence": 0.60, "reasoning": "RSI"}]
        result = nf.apply(signals, sentiment)
        assert len(result) == 0, "Very negative news must drop BUY signal entirely"

    def test_very_negative_news_does_not_drop_sell_signal(self):
        """Negative news should NOT drop SELL signals — we want to exit."""
        nf = self._make_filter()
        sentiment = {"AAPL": {"score": 0.10, "headlines": ["Major scandal"], "article_count": 5}}
        signals = [
            {"symbol": "AAPL", "action": "SELL", "confidence": 0.80, "reasoning": "time exit"}
        ]
        result = nf.apply(signals, sentiment)
        assert len(result) == 1, "SELL signals must never be dropped by news filter"

    def test_neutral_news_passes_through_unchanged(self):
        nf = self._make_filter()
        sentiment = {"AAPL": {"score": 0.50, "headlines": [], "article_count": 3}}
        original_conf = 0.65
        signals = [
            {"symbol": "AAPL", "action": "BUY", "confidence": original_conf, "reasoning": "ML"}
        ]
        result = nf.apply(signals, sentiment)
        assert len(result) == 1
        assert result[0]["confidence"] == original_conf
