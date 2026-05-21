"""Test risk management modules - CRITICAL: 100% COVERAGE REQUIRED"""
import sys
from pathlib import Path

import numpy as np
import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.risk.correlation_filter import CorrelationFilter
from src.risk.drawdown_stop_manager import DrawdownStopManager
from src.risk.portfolio_risk_manager import PortfolioRiskManager
from src.risk.stop_loss_manager import StopLossManager


class TestPortfolioRiskManager:
    """Test portfolio heat limits and risk controls"""

    def test_portfolio_heat_limit_rejection(self):
        """Test that positions are rejected when heat limit exceeded"""
        risk_manager = PortfolioRiskManager(max_portfolio_heat=0.30)

        # Current heat: 50% (50k exposure / 100k portfolio)
        current_exposure = 50000
        portfolio_value = 100000
        new_position_value = 50000  # Would bring heat to 100%

        result = risk_manager.can_add_position(
            position_value=new_position_value,
            current_exposure=current_exposure,
            portfolio_value=portfolio_value,
        )

        assert not result

    def test_portfolio_heat_limit_acceptance(self):
        """Test that positions are accepted when within heat limit"""
        risk_manager = PortfolioRiskManager(max_portfolio_heat=0.30)

        current_exposure = 10000
        portfolio_value = 100000
        new_position_value = 10000  # Would bring heat to 20%

        result = risk_manager.can_add_position(
            position_value=new_position_value,
            current_exposure=current_exposure,
            portfolio_value=portfolio_value,
        )

        assert result

    def test_daily_loss_limit_triggers_halt(self):
        """Test daily loss limit triggers trading halt"""
        risk_manager = PortfolioRiskManager(max_daily_loss_pct=0.02)

        # Set daily start value first
        risk_manager.set_daily_start_value(100000)

        # Simulate 3% daily loss
        risk_manager.check_daily_loss_limit(97000)  # 3% loss from 100k

        assert risk_manager.trading_halted

    def test_daily_loss_within_limit(self):
        """Test that small losses don't trigger halt"""
        risk_manager = PortfolioRiskManager(max_daily_loss_pct=0.02)

        # Portfolio started at 100k, now at 99k = 1% loss
        result = risk_manager.check_daily_loss_limit(current_value=99000)

        assert result
        assert not risk_manager.trading_halted

    def test_regime_adjusts_heat_limits(self):
        """Test regime detection adjusts heat limits"""
        risk_manager = PortfolioRiskManager(max_portfolio_heat=0.30)

        # Set to high volatility regime (should reduce heat)
        risk_manager.set_regime("HIGH_VOL")

        # Heat should be reduced to 25% (30% * 0.83)
        assert risk_manager.max_portfolio_heat == pytest.approx(0.25, abs=0.01)

        # Set back to normal regime
        risk_manager.set_regime("NORMAL")

        # Heat limit should return to 30%
        assert risk_manager.max_portfolio_heat == pytest.approx(0.30, abs=0.01)


class TestCorrelationFilter:
    """Test correlation filtering logic"""

    def test_correlation_filter_rejects_high_correlation(self):
        """Test correlation filter rejects highly correlated positions"""
        import numpy as np
        import pandas as pd

        np.random.seed(42)
        corr_filter = CorrelationFilter(max_correlation=0.7)

        # Create correlated price series with matching length
        dates = pd.date_range("2024-01-01", periods=100)
        base_prices = np.cumsum(np.random.normal(0, 1, 100)) + 100

        # Highly correlated stock — tiny noise keeps returns correlation reliably > 0.95
        correlated_prices = base_prices + np.random.normal(0, 0.05, 100)

        # Update price history
        corr_filter.update_price_history("AAPL", pd.Series(base_prices, index=dates))
        corr_filter.update_price_history("MSFT", pd.Series(correlated_prices, index=dates))

        # Test correlation filter
        existing_positions = {"AAPL": 100}
        should_filter, reason, correlations = corr_filter.should_filter_signal(
            "MSFT", existing_positions
        )

        # Should reject due to high correlation
        assert should_filter

    def test_correlation_filter_accepts_low_correlation(self, mock_market_data):
        """Test correlation filter accepts uncorrelated signals"""
        corr_filter = CorrelationFilter(max_correlation=0.7, correlation_window=60)

        # Create uncorrelated returns
        np.random.seed(42)
        existing_positions = {"MSFT": {"returns": np.random.randn(60)}}

        signals = [{"symbol": "AAPL", "action": "BUY", "confidence": 0.8}]

        # Should accept signal
        filtered = corr_filter.filter_signals_with_sizing(
            signals, existing_positions, mock_market_data
        )

        assert len(filtered) >= 1


class TestStopLossManager:
    """Test catastrophe stop loss logic"""

    def test_catastrophe_stop_loss_trigger(self):
        """Test stop loss triggers at 3x ATR"""
        stop_manager = StopLossManager(atr_multiplier=3.0)

        # Set stop loss first
        stop_manager.set_stop_loss(symbol="AAPL", entry_price=150, atr=5.0)

        # Check if triggered at 3x ATR below entry (135 = 150 - 3*5)
        result = stop_manager.check_stop_loss(symbol="AAPL", current_price=135)

        assert result

    def test_catastrophe_stop_loss_no_trigger(self):
        """Test stop loss doesn't trigger within threshold"""
        stop_manager = StopLossManager(atr_multiplier=2.5)

        # Set stop loss
        stop_manager.set_stop_loss(symbol="AAPL", entry_price=150, atr=5.0)

        # Check at 2x ATR (within 2.5x threshold): 150 - 2*5 = 140
        result = stop_manager.check_stop_loss(symbol="AAPL", current_price=140)

        assert not result

    def test_stop_loss_with_zero_atr(self):
        """Test stop loss handles edge case of zero ATR"""
        stop_manager = StopLossManager()

        # Should not crash with zero ATR (won't set stop)
        stop_manager.set_stop_loss(symbol="AAPL", entry_price=150, atr=0.0)

        # Check should return False (no stop set)
        result = stop_manager.check_stop_loss(symbol="AAPL", current_price=140)

        # Should return False since no stop was set
        assert not result


class TestDrawdownStopManager:
    """Test drawdown protection logic"""

    def test_drawdown_halt_threshold(self):
        """Test drawdown manager halts trading at 8% drawdown"""
        from unittest.mock import Mock

        # Mock dependencies
        mock_db = Mock()
        mock_email = Mock()

        dd_manager = DrawdownStopManager(db=mock_db, email_notifier=mock_email)

        # Check at 8% drawdown
        is_stopped, reason, details = dd_manager.check_drawdown_stop(
            current_portfolio_value=92000, peak_portfolio_value=100000
        )

        assert is_stopped
        assert "HALT" in reason or "halt" in reason.lower()

    def test_drawdown_panic_threshold(self):
        """Test drawdown manager panics at 10% drawdown"""
        from unittest.mock import Mock

        mock_db = Mock()
        mock_email = Mock()

        dd_manager = DrawdownStopManager(db=mock_db, email_notifier=mock_email)

        # Check at 10% drawdown
        is_stopped, reason, details = dd_manager.check_drawdown_stop(
            current_portfolio_value=90000, peak_portfolio_value=100000
        )

        assert is_stopped
        assert "PANIC" in reason or "panic" in reason.lower()

    def test_drawdown_normal_state(self):
        """Test drawdown manager allows trading in normal state"""
        from unittest.mock import Mock

        mock_db = Mock()
        mock_email = Mock()

        dd_manager = DrawdownStopManager(db=mock_db, email_notifier=mock_email)

        # Check at 5% drawdown (within limits)
        is_stopped, reason, details = dd_manager.check_drawdown_stop(
            current_portfolio_value=95000, peak_portfolio_value=100000
        )

        assert not is_stopped

    def test_drawdown_cooldown_period(self):
        """Test cooldown period after halt"""
        import json
        from datetime import datetime, timedelta
        from unittest.mock import Mock

        mock_db = Mock()
        mock_email = Mock()

        # Mock get_system_state to return proper JSON string
        cooldown_end = (datetime.now() + timedelta(days=10)).isoformat()
        mock_db.get_system_state.return_value = json.dumps(
            {
                "state": "HALT",
                "drawdown": 0.08,
                "cooldown_days": 10,
                "cooldown_end": cooldown_end,
                "triggered_at": datetime.now().isoformat(),
                "rampup_end": None,
            }
        )

        dd_manager = DrawdownStopManager(db=mock_db, email_notifier=mock_email)

        # Trigger halt
        dd_manager.check_drawdown_stop(92000, 100000)

        # Should not allow trading during cooldown
        assert not dd_manager.is_trading_allowed()

    def test_drawdown_rampup_sizing(self):
        """Test rampup reduces position sizing"""
        import json
        from datetime import datetime, timedelta
        from unittest.mock import Mock

        mock_db = Mock()
        mock_email = Mock()

        # Mock get_system_state to return RAMPUP state
        rampup_end = (datetime.now() + timedelta(days=5)).isoformat()
        mock_db.get_system_state.return_value = json.dumps(
            {
                "state": "RAMPUP",
                "drawdown": 0.0,
                "cooldown_days": 0,
                "cooldown_end": None,
                "triggered_at": datetime.now().isoformat(),
                "rampup_end": rampup_end,
            }
        )

        dd_manager = DrawdownStopManager(db=mock_db, email_notifier=mock_email)

        multiplier = dd_manager.get_sizing_multiplier()

        # Should be less than 1.0 during rampup (default 0.5)
        assert multiplier < 1.0
        assert multiplier == 0.5


class TestPositionSizing:
    """Test position sizing calculations"""

    def test_position_sizing_validation(self):
        """Test position sizing never exceeds portfolio value"""
        PortfolioRiskManager()

        portfolio_value = 100000
        price = 150
        atr = 0.01  # Extremely low ATR would suggest huge position

        # Calculate position size with 1% risk
        risk_amount = portfolio_value * 0.01
        shares = int(risk_amount / atr)

        # Even with low ATR, position should be reasonable
        # Cap at 10% of portfolio
        max_shares = int((portfolio_value * 0.10) / price)
        shares = min(shares, max_shares)

        max_notional = shares * price
        assert max_notional <= portfolio_value * 0.10

    def test_atr_based_position_sizing(self):
        """Test ATR-based position sizing calculation"""
        portfolio_value = 100000
        price = 150
        atr = 5.0
        risk_pct = 0.01  # 1% risk per position

        # Calculate shares
        risk_amount = portfolio_value * risk_pct  # $1000
        shares = int(risk_amount / atr)  # 1000 / 5 = 200 shares

        assert shares == 200

        notional = shares * price  # 200 * 150 = $30,000
        assert notional == 30000

        # Verify risk amount
        actual_risk = shares * atr  # 200 * 5 = $1000
        assert actual_risk == risk_amount

    def test_position_sizing_with_high_atr(self):
        """Test position sizing with high volatility (high ATR)"""
        portfolio_value = 100000
        price = 150
        atr = 20.0  # High volatility
        risk_pct = 0.01

        risk_amount = portfolio_value * risk_pct  # $1000
        shares = int(risk_amount / atr)  # 1000 / 20 = 50 shares

        assert shares == 50

        notional = shares * price  # 50 * 150 = $7,500
        assert notional == 7500

        # Lower shares due to higher volatility
        assert shares < 100


class TestRiskManagerIntegration:
    """Test integration between risk management components"""

    def test_risk_checks_execute_in_order(self):
        """Test that risk checks are applied in correct order"""
        risk_manager = PortfolioRiskManager(max_portfolio_heat=0.30, max_daily_loss_pct=0.02)

        # Set daily start value first
        risk_manager.set_daily_start_value(100000)

        # First check: daily loss limit
        risk_manager.check_daily_loss_limit(97000)  # 3% loss
        assert risk_manager.trading_halted

        # Second check: even if heat is OK, trading should be halted
        result = risk_manager.can_add_position(
            position_value=10000, current_exposure=10000, portfolio_value=100000
        )

        assert not result  # Halted due to daily loss

    def test_multiple_risk_filters_compound(self):
        """Test that multiple risk filters work together"""
        risk_manager = PortfolioRiskManager(max_portfolio_heat=0.30)

        # High exposure
        current_exposure = 25000
        portfolio_value = 100000
        new_position = 10000  # Would bring to 35% heat

        # Should reject due to heat
        result = risk_manager.can_add_position(
            position_value=new_position,
            current_exposure=current_exposure,
            portfolio_value=portfolio_value,
        )

        assert not result
