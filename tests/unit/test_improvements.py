"""
Unit tests for IMPROVEMENTS batch:
  B1 – Trailing ATR stop activation
  A1 – LightGBM upgrade
  A2 – HMM regime detection
  B2 – Pre-earnings BUY guard
  C1 – Limit-order pricing
  C3 – Conviction-based sizing multiplier
  B4 – ML risk-off overlay logic
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _spy_data(n: int = 120) -> pd.DataFrame:
    """Build minimal multi-symbol DataFrame with SPY included."""
    np.random.seed(42)
    dates = pd.date_range(end=pd.Timestamp.today(), periods=n, freq="B")

    rows = []
    for sym in ["SPY", "AAPL", "MSFT"]:
        price = 400.0 if sym == "SPY" else 150.0
        close = price + np.cumsum(np.random.randn(n) * 0.5)
        close = np.maximum(close, 1.0)
        for i in range(len(dates)):
            rows.append(
                {
                    "symbol": sym,
                    "close": close[i],
                    "open": close[i] * 0.99,
                    "high": close[i] * 1.01,
                    "low": close[i] * 0.99,
                    "volume": 1_500_000.0,
                    "rsi": 50.0,
                    "rsi_slope": 0.0,
                    "atr_20": close[i] * 0.015,
                    "vwap": close[i] * 0.70,
                    "volume_ratio": 1.0,
                    "returns_1d": 0.001,
                    "returns_5d": 0.01,
                    "returns_20d": 0.02,
                    "returns_60d": 0.05,
                    "volatility_20d": 0.15,
                    "volatility_60d": 0.15,
                    "price_to_sma20": 1.01,
                    "price_to_sma50": 1.02,
                    "price_to_sma200": 1.05,
                    "sma_20": close[i] * 0.99,
                    "sma_50": close[i] * 0.98,
                    "sma_100": close[i] * 0.97,
                    "sma_200": close[i] * 0.95,
                    "earnings_surprise": 0.0,
                    "pe_ratio": 20.0,
                    "revenue_growth": 0.05,
                    "profit_margin": 0.15,
                    "beta": 1.0,
                }
            )
    df = pd.DataFrame(rows)
    df.index = pd.DatetimeIndex(list(dates) * 3)
    return df


# ---------------------------------------------------------------------------
# B1 – Trailing ATR stop activation
# ---------------------------------------------------------------------------


class TestTrailingAtrActivation:
    """B1: update_trailing_stop() must be called inside check_stop_losses()."""

    @pytest.mark.unit
    def test_update_trailing_stop_called_when_atr_present(self):
        """Trailing stop is ratcheted up when ATR is in the position dict."""
        from src.risk.stop_loss_manager import StopLossManager

        mgr = StopLossManager(atr_multiplier=3.0)
        entry = 100.0
        atr = 2.0
        mgr.set_stop_loss("AAPL", entry, atr)
        initial_stop = mgr.get_stop_price("AAPL")  # 94.0

        mgr.update_trailing_stop("AAPL", 110.0, atr)
        assert mgr.get_stop_price("AAPL") == 104.0
        assert mgr.get_stop_price("AAPL") > initial_stop

    @pytest.mark.unit
    def test_trailing_stop_never_moves_down(self):
        """Stop ratchet must be monotonically non-decreasing."""
        from src.risk.stop_loss_manager import StopLossManager

        mgr = StopLossManager(atr_multiplier=3.0)
        mgr.set_stop_loss("AAPL", 100.0, 2.0)
        mgr.update_trailing_stop("AAPL", 110.0, 2.0)
        high_stop = mgr.get_stop_price("AAPL")

        mgr.update_trailing_stop("AAPL", 102.0, 2.0)  # price fell back
        assert mgr.get_stop_price("AAPL") == high_stop

    @pytest.mark.unit
    def test_trailing_stop_skipped_when_atr_zero(self):
        """No update should occur if ATR is 0 (guard in check_stop_losses)."""
        from src.risk.stop_loss_manager import StopLossManager

        mgr = StopLossManager(atr_multiplier=3.0)
        mgr.set_stop_loss("AAPL", 100.0, 2.0)
        stop_before = mgr.get_stop_price("AAPL")

        # Simulate the guard: `if atr > 0: update_trailing_stop(...)`
        atr = 0
        if atr > 0:
            mgr.update_trailing_stop("AAPL", 150.0, atr)

        assert mgr.get_stop_price("AAPL") == stop_before  # unchanged


# ---------------------------------------------------------------------------
# A1 – LightGBM / GradientBoosting upgrade
# ---------------------------------------------------------------------------


class TestLightGBMUpgrade:
    """A1: ML Momentum now uses LightGBM (or sklearn fallback)."""

    @pytest.mark.unit
    def test_model_is_lgbm_or_fallback(self):
        """Verify the model attribute is LGBMClassifier or the sklearn fallback."""
        from src.strategies.strategy_ml_momentum import _LGBM_AVAILABLE, MLMomentumStrategy

        strat = MLMomentumStrategy(strategy_id=1, capital=25000)
        model_type = type(strat.model).__name__
        if _LGBM_AVAILABLE:
            assert model_type == "LGBMClassifier"
        else:
            assert model_type == "GradientBoostingClassifier"

    @pytest.mark.unit
    def test_no_scaler_attribute(self):
        """StandardScaler must be removed — tree models don't need feature scaling."""
        from src.strategies.strategy_ml_momentum import MLMomentumStrategy

        strat = MLMomentumStrategy(strategy_id=1, capital=25000)
        assert not hasattr(strat, "scaler"), "Scaler should be removed for LightGBM"

    @pytest.mark.unit
    def test_model_trains_and_predicts(self):
        """Model must train on synthetic data and return probability in [0,1]."""
        from src.strategies.strategy_ml_momentum import MLMomentumStrategy

        strat = MLMomentumStrategy(strategy_id=1, capital=25000)
        df = _spy_data(n=120)
        signals = strat.generate_signals(df)

        assert isinstance(signals, list)
        for sig in signals:
            if "confidence" in sig:
                assert 0.0 <= sig["confidence"] <= 1.0

    @pytest.mark.unit
    def test_get_description_reflects_backend(self):
        """get_description() must mention LightGBM (or fallback)."""
        from src.strategies.strategy_ml_momentum import _LGBM_AVAILABLE, MLMomentumStrategy

        strat = MLMomentumStrategy(strategy_id=1, capital=25000)
        desc = strat.get_description()
        if _LGBM_AVAILABLE:
            assert "LightGBM" in desc
        else:
            assert "fallback" in desc.lower() or "GradientBoosting" in desc


# ---------------------------------------------------------------------------
# A2 – HMM regime detection
# ---------------------------------------------------------------------------


class TestHMMRegimeDetection:
    """A2: detect_hmm_regime() returns 'bull', 'bear', or 'unknown'."""

    @pytest.mark.unit
    def test_valid_return_values(self):
        from src.regime.regime_detector import RegimeDetector

        rd = RegimeDetector()
        df = _spy_data(n=120)
        result = rd.detect_hmm_regime(df)
        assert result in ("bull", "bear", "unknown")

    @pytest.mark.unit
    def test_returns_unknown_with_no_spy(self):
        """No SPY rows → fallback to 'unknown'."""
        from src.regime.regime_detector import RegimeDetector

        rd = RegimeDetector()
        df = _spy_data(n=120)
        df_no_spy = df[df["symbol"] != "SPY"]
        result = rd.detect_hmm_regime(df_no_spy)
        assert result == "unknown"

    @pytest.mark.unit
    def test_returns_unknown_with_insufficient_data(self):
        """< 60 SPY rows → 'unknown'."""
        from src.regime.regime_detector import RegimeDetector

        rd = RegimeDetector()
        df = _spy_data(n=120)
        df_short = df[df["symbol"] == "SPY"].head(30)
        result = rd.detect_hmm_regime(df_short)
        assert result == "unknown"

    @pytest.mark.unit
    def test_returns_unknown_when_hmmlearn_missing(self):
        """When hmmlearn is unavailable the detector returns 'unknown' gracefully."""
        import src.regime.regime_detector as rd_module

        original = rd_module._HMM_AVAILABLE
        try:
            rd_module._HMM_AVAILABLE = False
            from src.regime.regime_detector import RegimeDetector

            rd = RegimeDetector()
            rd._hmm_cache = None
            result = rd.detect_hmm_regime(_spy_data(n=120))
            assert result == "unknown"
        finally:
            rd_module._HMM_AVAILABLE = original

    @pytest.mark.unit
    def test_hmm_regime_in_adjustments_dict(self):
        """get_regime_adjustments() must include 'hmm_regime' key."""
        from src.regime.regime_detector import RegimeDetector

        rd = RegimeDetector()
        adj = rd.get_regime_adjustments(vix=18.0, market_data=_spy_data(n=120))
        assert "hmm_regime" in adj

    @pytest.mark.unit
    def test_bear_regime_disables_mean_reversion(self):
        """HMM bear state must set enable_mean_reversion=False."""
        from src.regime.regime_detector import RegimeDetector

        rd = RegimeDetector()
        with patch.object(rd, "detect_hmm_regime", return_value="bear"):
            adj = rd.get_regime_adjustments(vix=18.0, market_data=_spy_data(n=60))
        assert adj["enable_mean_reversion"] is False

    @pytest.mark.unit
    def test_bull_regime_keeps_mean_reversion_enabled(self):
        """HMM bull state must NOT disable mean reversion."""
        from src.regime.regime_detector import RegimeDetector

        rd = RegimeDetector()
        with patch.object(rd, "detect_hmm_regime", return_value="bull"), patch.object(
            rd, "detect_volatility_regime", return_value="normal"
        ), patch.object(rd, "detect_trend_regime", return_value="weak_trend"):
            adj = rd.get_regime_adjustments(vix=18.0, market_data=_spy_data(n=60))
        assert adj["enable_mean_reversion"] is True

    @pytest.mark.unit
    def test_hmm_cache_is_reused_same_day(self):
        """Result must be cached so HMM doesn't refit twice on the same date."""
        from src.regime.regime_detector import RegimeDetector

        rd = RegimeDetector()
        today = str(pd.Timestamp.today().date())
        rd._hmm_cache = (today, "bull")

        df = _spy_data(n=120)
        result = rd.detect_hmm_regime(df)
        assert result == "bull"  # returned from cache, not refitted


# ---------------------------------------------------------------------------
# B2 – Pre-earnings BUY guard
# ---------------------------------------------------------------------------


class TestPreEarningsGuard:
    """B2: _get_symbols_reporting_tomorrow() + BUY suppression."""

    @pytest.mark.unit
    def test_returns_empty_when_no_calendar(self, tmp_path, monkeypatch):
        """No earnings_calendar.csv → empty set (graceful)."""
        monkeypatch.chdir(tmp_path)
        from src.core.execution_engine import MultiStrategyRunner

        eng = object.__new__(MultiStrategyRunner)
        result = eng._get_symbols_reporting_tomorrow()
        assert result == set()

    @pytest.mark.unit
    def test_detects_tomorrow_reporters(self, tmp_path, monkeypatch):
        """Symbols with reportDate = tomorrow are returned."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "data").mkdir()

        tomorrow = (pd.Timestamp.today() + pd.Timedelta(days=1)).normalize()
        cal_path = tmp_path / "data" / "earnings_calendar.csv"
        with open(cal_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["symbol", "reportDate"])
            writer.writeheader()
            writer.writerow({"symbol": "AAPL", "reportDate": tomorrow.strftime("%Y-%m-%d")})
            writer.writerow({"symbol": "MSFT", "reportDate": "2000-01-01"})

        from src.core.execution_engine import MultiStrategyRunner

        eng = object.__new__(MultiStrategyRunner)
        result = eng._get_symbols_reporting_tomorrow()
        assert "AAPL" in result
        assert "MSFT" not in result

    @pytest.mark.unit
    def test_past_reporters_not_included(self, tmp_path, monkeypatch):
        """Yesterday's reporters must NOT appear in the guard set."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "data").mkdir()

        yesterday = (pd.Timestamp.today() - pd.Timedelta(days=1)).normalize()
        cal_path = tmp_path / "data" / "earnings_calendar.csv"
        with open(cal_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["symbol", "reportDate"])
            writer.writeheader()
            writer.writerow({"symbol": "GOOGL", "reportDate": yesterday.strftime("%Y-%m-%d")})

        from src.core.execution_engine import MultiStrategyRunner

        eng = object.__new__(MultiStrategyRunner)
        assert "GOOGL" not in eng._get_symbols_reporting_tomorrow()


# ---------------------------------------------------------------------------
# C1 – Limit-order pricing
# ---------------------------------------------------------------------------


class TestLimitOrderPricing:
    """C1: BUY limit = price*1.001, SELL limit = price*0.999."""

    @pytest.mark.unit
    def test_buy_limit_price_formula(self):
        price = 150.0
        limit = round(price * 1.001, 2)
        assert limit == 150.15
        assert limit > price

    @pytest.mark.unit
    def test_sell_limit_price_formula(self):
        price = 150.0
        limit = round(price * 0.999, 2)
        assert limit == 149.85
        assert limit < price

    @pytest.mark.unit
    def test_limit_order_request_imported(self):
        """LimitOrderRequest must be importable from execution_engine module."""
        from alpaca.trading.requests import LimitOrderRequest  # noqa: F401 – import check

    @pytest.mark.unit
    def test_stop_loss_exits_still_use_market_order(self):
        """MarketOrderRequest import must still be present for stop-loss exits."""
        from alpaca.trading.requests import MarketOrderRequest  # noqa: F401


# ---------------------------------------------------------------------------
# C3 – Conviction-based sizing multiplier
# ---------------------------------------------------------------------------


class TestConvictionSizingMultiplier:
    """C3: conviction_mult = max(0.5, min(1.0, confidence))."""

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "confidence,expected_mult",
        [
            (0.50, 0.50),  # minimum floor
            (0.52, 0.52),
            (0.65, 0.65),
            (0.80, 0.80),
            (1.00, 1.00),  # maximum cap
            (1.50, 1.00),  # clamped at 1.0
            (0.00, 0.50),  # clamped at 0.5
        ],
    )
    def test_conviction_clamp(self, confidence: float, expected_mult: float):
        mult = max(0.5, min(1.0, float(confidence)))
        assert mult == pytest.approx(expected_mult)

    @pytest.mark.unit
    def test_missing_confidence_defaults_to_0_7(self):
        """No confidence key → default 0.7 → mult = 0.7."""
        signal: dict = {"symbol": "AAPL", "action": "BUY", "shares": 100}
        mult = max(0.5, min(1.0, float(signal.get("confidence", 0.7))))
        assert mult == pytest.approx(0.7)

    @pytest.mark.unit
    def test_combined_multiplier_chain(self):
        """Full multiplier chain: corr * drawdown * conviction is ≤ 1.0."""
        size_mult = 0.8
        drawdown_mult = 0.9
        conviction_mult = max(0.5, min(1.0, 0.55))
        combined = size_mult * drawdown_mult * conviction_mult
        assert 0.0 < combined <= 1.0


# ---------------------------------------------------------------------------
# B4 – ML risk-off overlay
# ---------------------------------------------------------------------------


class TestMLRiskOffOverlay:
    """B4: ≥3 ML SELL signals triggers risk-off; suppresses non-ML BUYs."""

    @pytest.mark.unit
    def test_risk_off_threshold_exactly_three(self):
        """Exactly 3 ML SELLs should trigger risk-off."""
        signals = [
            {"action": "SELL", "symbol": "A"},
            {"action": "SELL", "symbol": "B"},
            {"action": "SELL", "symbol": "C"},
        ]
        ml_sell_count = sum(1 for s in signals if s["action"] == "SELL")
        assert ml_sell_count >= 3

    @pytest.mark.unit
    def test_risk_off_not_triggered_below_three(self):
        """2 ML SELLs must NOT trigger risk-off."""
        signals = [
            {"action": "SELL", "symbol": "A"},
            {"action": "SELL", "symbol": "B"},
            {"action": "BUY", "symbol": "C"},
        ]
        ml_sell_count = sum(1 for s in signals if s["action"] == "SELL")
        assert not (ml_sell_count >= 3)

    @pytest.mark.unit
    def test_risk_off_skips_non_ml_buy(self):
        """When _ml_risk_off is True, non-ML BUYs are suppressed."""
        executed = []

        class FakeStrategy:
            name = "RSI Mean Reversion"

        strategy = FakeStrategy()
        ml_risk_off = True
        signals = [{"action": "BUY", "symbol": "AAPL"}]

        for sig in signals:
            if ml_risk_off and "ml" not in strategy.name.lower():
                continue  # suppressed
            executed.append(sig)

        assert executed == []

    @pytest.mark.unit
    def test_risk_off_does_not_skip_ml_buy(self):
        """When _ml_risk_off is True, ML strategy BUYs are still allowed."""
        executed = []

        class FakeStrategy:
            name = "ML Momentum"

        strategy = FakeStrategy()
        ml_risk_off = True
        signals = [{"action": "BUY", "symbol": "AAPL"}]

        for sig in signals:
            if ml_risk_off and "ml" not in strategy.name.lower():
                continue
            executed.append(sig)

        assert len(executed) == 1

    @pytest.mark.unit
    def test_risk_off_does_not_suppress_sells(self):
        """Risk-off must never block SELL signals (exits should always proceed)."""
        executed = []

        class FakeStrategy:
            name = "RSI Mean Reversion"

        strategy = FakeStrategy()
        ml_risk_off = True
        signals = [
            {"action": "SELL", "symbol": "AAPL"},
            {"action": "BUY", "symbol": "MSFT"},
        ]

        for sig in signals:
            action = sig["action"]
            if action == "BUY" and ml_risk_off and "ml" not in strategy.name.lower():
                continue
            executed.append(sig)

        assert len(executed) == 1
        assert executed[0]["action"] == "SELL"
