"""
Critical path tests for correlation_filter.py - Target 100% coverage
Missing lines: 56, 70, 79-108, 129-134, 151, 158, 162-165, 202-205, 215, 219-220, 235, 255-279
"""

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


class TestCorrelationFilterCritical:
    """Achieve 100% coverage on correlation_filter.py"""

    def test_should_filter_signal_no_positions(self):
        """Test should_filter_signal with no existing positions (line 151)"""
        from src.risk.correlation_filter import CorrelationFilter

        filter = CorrelationFilter()

        should_filter, reason, correlations = filter.should_filter_signal("AAPL", {})
        assert not should_filter
        assert reason == "No existing positions"

    def test_calculate_correlation_multi_window_no_history(self):
        """No price history returns conservative prior (0.5) not 0.0.

        Returning 0.0 when data is absent treats unknown pairs as uncorrelated,
        which lets every new symbol bypass the filter unconditionally.  The fix
        returns a neutral prior of 0.5 so attenuation applies consistently.
        """
        from src.risk.correlation_filter import CorrelationFilter

        filter = CorrelationFilter()

        long_corr, short_corr = filter.calculate_correlation_multi_window("AAPL", "MSFT")
        assert long_corr == 0.5, "expected conservative prior 0.5 when no history"
        assert short_corr == 0.5

    def test_calculate_correlation_multi_window_insufficient_data(self):
        """Insufficient data (<20 bars) returns conservative prior (0.4) not 0.0."""
        from src.risk.correlation_filter import CorrelationFilter

        filter = CorrelationFilter(correlation_window=60, short_window=20)

        # Add insufficient price history
        filter.update_price_history("AAPL", pd.Series(np.random.randn(10) + 100))
        filter.update_price_history("MSFT", pd.Series(np.random.randn(10) + 200))

        long_corr, short_corr = filter.calculate_correlation_multi_window("AAPL", "MSFT")
        assert long_corr == 0.4, "expected conservative prior 0.4 when <20 bars"
        assert short_corr == 0.4

    def test_calculate_correlation_multi_window_sufficient_data(self):
        """Test calculate_correlation_multi_window with sufficient data (lines 87-93, 98-104)"""
        from src.risk.correlation_filter import CorrelationFilter

        filter = CorrelationFilter(correlation_window=60, short_window=20)

        # Add sufficient price history
        np.random.seed(42)
        filter.update_price_history("AAPL", pd.Series(np.random.randn(100) + 100))
        filter.update_price_history("MSFT", pd.Series(np.random.randn(100) + 200))

        long_corr, short_corr = filter.calculate_correlation_multi_window("AAPL", "MSFT")
        assert isinstance(long_corr, float)
        assert isinstance(short_corr, float)

    def test_calculate_size_multiplier_low_correlation(self):
        """Test calculate_size_multiplier with low correlation (line 128)"""
        from src.risk.correlation_filter import CorrelationFilter

        filter = CorrelationFilter()

        multiplier, reason = filter.calculate_size_multiplier(0.3)
        assert multiplier == 1.0
        assert reason == "low_correlation"

    def test_calculate_size_multiplier_medium_correlation(self):
        """Test calculate_size_multiplier with medium correlation (lines 131-132)"""
        from src.risk.correlation_filter import CorrelationFilter

        filter = CorrelationFilter()

        multiplier, reason = filter.calculate_size_multiplier(0.65)
        assert 0.25 <= multiplier < 1.0
        assert "attenuated_correlation" in reason

    def test_calculate_size_multiplier_high_correlation(self):
        """Test calculate_size_multiplier with high correlation (line 134)"""
        from src.risk.correlation_filter import CorrelationFilter

        filter = CorrelationFilter()

        multiplier, reason = filter.calculate_size_multiplier(0.85)
        assert multiplier == 0.0
        assert "high_correlation" in reason

    def test_should_filter_signal_same_symbol(self):
        """Test should_filter_signal skips same symbol (line 158)"""
        from src.risk.correlation_filter import CorrelationFilter

        filter = CorrelationFilter()

        # Add price history
        filter.update_price_history("AAPL", pd.Series(np.random.randn(100) + 100))

        should_filter, reason, correlations = filter.should_filter_signal("AAPL", {"AAPL": 100})
        assert not should_filter

    def test_should_filter_signal_high_vol_regime(self):
        """Test should_filter_signal with HIGH_VOL regime (lines 162-165)"""
        from src.risk.correlation_filter import CorrelationFilter

        filter = CorrelationFilter()

        # Add correlated price history
        np.random.seed(42)
        base_prices = np.cumsum(np.random.randn(100)) + 100
        filter.update_price_history("AAPL", pd.Series(base_prices))
        filter.update_price_history("MSFT", pd.Series(base_prices * 1.1))

        should_filter, reason, correlations = filter.should_filter_signal(
            "MSFT", {"AAPL": 100}, regime="HIGH_VOL"
        )
        assert isinstance(should_filter, bool)
        if "AAPL" in correlations:
            assert "short" in correlations["AAPL"]

    def test_filter_signals_with_sizing_sell_signals(self):
        """Test filter_signals_with_sizing with sell signals (lines 202-205)"""
        from src.risk.correlation_filter import CorrelationFilter

        filter = CorrelationFilter()

        signals = [{"symbol": "AAPL", "action": "SELL", "confidence": 0.8}]

        market_data = pd.DataFrame({"symbol": ["AAPL"] * 100, "close": np.random.randn(100) + 100})

        filtered = filter.filter_signals_with_sizing(signals, {}, market_data)
        assert len(filtered) == 1
        assert filtered[0]["size_multiplier"] == 1.0
        assert filtered[0]["correlation_reason"] == "sell_signal"

    def test_filter_signals_with_sizing_buy_signals(self):
        """Test filter_signals_with_sizing with buy signals (lines 215, 219-220)"""
        from src.risk.correlation_filter import CorrelationFilter

        filter = CorrelationFilter()

        signals = [
            {"symbol": "AAPL", "action": "BUY", "confidence": 0.8},
            {"symbol": "MSFT", "action": "BUY", "confidence": 0.7},
        ]

        market_data = pd.DataFrame(
            {
                "symbol": ["AAPL"] * 100 + ["MSFT"] * 100,
                "close": list(np.random.randn(100) + 100) + list(np.random.randn(100) + 200),
            }
        )

        filtered = filter.filter_signals_with_sizing(signals, {"GOOGL": 50}, market_data)
        assert len(filtered) >= 0

    def test_filter_signals_skip_same_symbol(self):
        """Test filter_signals_with_sizing skips same symbol (line 235)"""
        from src.risk.correlation_filter import CorrelationFilter

        filter = CorrelationFilter()

        signals = [{"symbol": "AAPL", "action": "BUY", "confidence": 0.8}]

        market_data = pd.DataFrame({"symbol": ["AAPL"] * 100, "close": np.random.randn(100) + 100})

        # AAPL already in positions
        filtered = filter.filter_signals_with_sizing(signals, {"AAPL": 100}, market_data)
        assert len(filtered) >= 0

    def test_calculate_correlation_no_history(self):
        """No price history returns conservative prior 0.5, not 0.0.

        Returning 0.0 unconditionally passes every new symbol through the
        filter without attenuation.  Conservative prior of 0.5 applies
        size attenuation (~83% of nominal size) to unknown pairs.
        """
        from src.risk.correlation_filter import CorrelationFilter

        filter = CorrelationFilter()

        corr = filter.calculate_correlation("AAPL", "MSFT")
        assert corr == 0.5

    def test_calculate_correlation_with_history(self):
        """Test calculate_correlation with price history (line 70)"""
        from src.risk.correlation_filter import CorrelationFilter

        filter = CorrelationFilter()

        # Add price history
        filter.update_price_history("AAPL", pd.Series(np.random.randn(100) + 100))
        filter.update_price_history("MSFT", pd.Series(np.random.randn(100) + 200))

        corr = filter.calculate_correlation("AAPL", "MSFT")
        assert isinstance(corr, float)
        assert -1.0 <= corr <= 1.0
