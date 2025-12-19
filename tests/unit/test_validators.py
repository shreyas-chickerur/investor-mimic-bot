"""
Unit Tests for Validators Module

Tests data validation functionality.
"""

import sys
from datetime import date, datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.validators import FactorScoreValidator, TradeValidator, ValidationError, Validator


class TestValidator:
    """Unit tests for Validator class."""

    def test_validate_ticker_valid(self):
        """Test valid ticker validation."""
        result = Validator.validate_ticker("AAPL")
        assert result == "AAPL"

    def test_validate_ticker_lowercase(self):
        """Test ticker is converted to uppercase."""
        result = Validator.validate_ticker("aapl")
        assert result == "AAPL"

    def test_validate_ticker_invalid_format(self):
        """Test invalid ticker format."""
        with pytest.raises(ValidationError):
            Validator.validate_ticker("INVALID123")

    def test_validate_ticker_empty(self):
        """Test empty ticker."""
        with pytest.raises(ValidationError):
            Validator.validate_ticker("")

    def test_validate_quantity_valid(self):
        """Test valid quantity."""
        result = Validator.validate_quantity(100)
        assert result == 100.0

    def test_validate_quantity_negative(self):
        """Test negative quantity."""
        with pytest.raises(ValidationError):
            Validator.validate_quantity(-100)

    def test_validate_quantity_zero(self):
        """Test zero quantity."""
        with pytest.raises(ValidationError):
            Validator.validate_quantity(0)

    def test_validate_price_valid(self):
        """Test valid price."""
        result = Validator.validate_price(150.50)
        assert result == 150.50

    def test_validate_price_negative(self):
        """Test negative price."""
        with pytest.raises(ValidationError):
            Validator.validate_price(-150.50)

    def test_validate_date_from_string(self):
        """Test date validation from string."""
        result = Validator.validate_date("2024-01-01")
        assert result == date(2024, 1, 1)

    def test_validate_date_from_datetime(self):
        """Test date validation from datetime."""
        dt = datetime(2024, 1, 1, 12, 0, 0)
        result = Validator.validate_date(dt)
        assert result == date(2024, 1, 1)

    def test_validate_email_valid(self):
        """Test valid email."""
        result = Validator.validate_email("test@example.com")
        assert result == "test@example.com"

    def test_validate_email_invalid(self):
        """Test invalid email."""
        with pytest.raises(ValidationError):
            Validator.validate_email("invalid-email")

    def test_validate_percentage_valid(self):
        """Test valid percentage."""
        result = Validator.validate_percentage(50.0)
        assert result == 50.0

    def test_validate_percentage_out_of_range(self):
        """Test percentage out of range."""
        with pytest.raises(ValidationError):
            Validator.validate_percentage(150.0)

    def test_validate_score_valid(self):
        """Test valid score (0-1)."""
        result = Validator.validate_score(0.75)
        assert result == 0.75

    def test_validate_score_out_of_range(self):
        """Test score out of range."""
        with pytest.raises(ValidationError):
            Validator.validate_score(1.5)


class TestTradeValidator:
    """Unit tests for TradeValidator class."""

    def test_validate_trade_valid(self):
        """Test valid trade validation."""
        result = TradeValidator.validate_trade("AAPL", "BUY", 100, 150.0)
        assert result["ticker"] == "AAPL"
        assert result["action"] == "BUY"
        assert result["quantity"] == 100.0
        assert result["price"] == 150.0
        assert result["total_value"] == 15000.0

    def test_validate_action_buy(self):
        """Test BUY action validation."""
        result = TradeValidator.validate_action("buy")
        assert result == "BUY"

    def test_validate_action_sell(self):
        """Test SELL action validation."""
        result = TradeValidator.validate_action("sell")
        assert result == "SELL"

    def test_validate_action_invalid(self):
        """Test invalid action."""
        with pytest.raises(ValidationError):
            TradeValidator.validate_action("HOLD")

    def test_validate_portfolio_allocation_valid(self):
        """Test valid portfolio allocation."""
        positions = {"AAPL": 0.3, "MSFT": 0.3, "GOOGL": 0.4}
        result = TradeValidator.validate_portfolio_allocation(positions)
        assert result == positions

    def test_validate_portfolio_allocation_invalid_sum(self):
        """Test portfolio allocation that doesn't sum to 100%."""
        positions = {"AAPL": 0.3, "MSFT": 0.3}
        with pytest.raises(ValidationError):
            TradeValidator.validate_portfolio_allocation(positions)


class TestFactorScoreValidator:
    """Unit tests for FactorScoreValidator class."""

    def test_validate_factor_scores_valid(self):
        """Test valid factor scores."""
        scores = {
            "conviction": 0.8,
            "news": 0.7,
            "insider": 0.6,
            "technical": 0.75,
            "moving_avg": 0.65,
            "volume": 0.7,
            "relative_strength": 0.8,
            "earnings": 0.75,
        }
        result = FactorScoreValidator.validate_factor_scores(scores)
        assert result == scores

    def test_validate_factor_scores_missing_factor(self):
        """Test factor scores with missing factor."""
        scores = {
            "conviction": 0.8,
            "news": 0.7,
            # Missing other factors
        }
        with pytest.raises(ValidationError):
            FactorScoreValidator.validate_factor_scores(scores)

    def test_validate_factor_scores_invalid_value(self):
        """Test factor scores with invalid value."""
        scores = {
            "conviction": 1.5,  # Invalid
            "news": 0.7,
            "insider": 0.6,
            "technical": 0.75,
            "moving_avg": 0.65,
            "volume": 0.7,
            "relative_strength": 0.8,
            "earnings": 0.75,
        }
        with pytest.raises(ValidationError):
            FactorScoreValidator.validate_factor_scores(scores)

    def test_validate_composite_score(self):
        """Test composite score calculation."""
        scores = {
            "conviction": 0.8,
            "news": 0.7,
            "insider": 0.6,
            "technical": 0.75,
            "moving_avg": 0.65,
            "volume": 0.7,
            "relative_strength": 0.8,
            "earnings": 0.75,
        }
        weights = {
            "conviction": 0.2,
            "news": 0.15,
            "insider": 0.1,
            "technical": 0.15,
            "moving_avg": 0.1,
            "volume": 0.1,
            "relative_strength": 0.1,
            "earnings": 0.1,
        }
        result = FactorScoreValidator.validate_composite_score(scores, weights)
        assert 0 <= result <= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
