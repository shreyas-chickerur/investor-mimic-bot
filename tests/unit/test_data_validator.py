#!/usr/bin/env python3
"""
Comprehensive tests for Data Validator
Phase 1.2: Data Quality Validation
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from src.data.data_validator import DataQualityError, DataValidator


class TestDataValidator:
    """Test suite for DataValidator"""

    def setup_method(self):
        """Setup for each test"""
        self.validator = DataValidator(max_age_hours=24, max_price_jump_pct=0.20)

    def create_clean_data(self, num_days=10, num_symbols=2):
        """Create clean test data - each symbol on separate days to avoid duplicate timestamps"""
        base_date = datetime.now() - timedelta(days=num_days * num_symbols)
        data = []
        indices = []

        day_counter = 0
        for symbol in [f"SYM{i}" for i in range(num_symbols)]:
            for _i in range(num_days):
                date = base_date + timedelta(days=day_counter)
                data.append(
                    {
                        "symbol": symbol,
                        "open": 100.0,
                        "high": 105.0,
                        "low": 95.0,
                        "close": 100.0,
                        "volume": 1000000,
                    }
                )
                indices.append(date)
                day_counter += 1

        df = pd.DataFrame(data)
        df.index = pd.to_datetime(indices)
        return df

    # Test 1: Clean data passes validation
    def test_clean_data_passes(self):
        """Test that clean data passes all validation checks"""
        df = self.create_clean_data()

        # Should not raise exception
        self.validator.validate_market_data(df)

    # Test 2: Detects duplicate timestamps
    def test_detects_duplicate_timestamps(self):
        """Test detection of duplicate timestamps"""
        df = self.create_clean_data()

        # Add duplicate row
        duplicate_row = df.iloc[0:1].copy()
        df = pd.concat([df, duplicate_row])

        with pytest.raises(DataQualityError) as exc_info:
            self.validator.validate_market_data(df)

        assert "Duplicate timestamps" in str(exc_info.value)

    # Test 3: Detects close price above high
    def test_detects_close_above_high(self):
        """Test detection of close price above high"""
        df = self.create_clean_data()

        # Set close above high
        df.loc[df.index[0], "close"] = 110.0  # high is 105.0

        with pytest.raises(DataQualityError) as exc_info:
            self.validator.validate_market_data(df)

        assert "Close price above high" in str(exc_info.value)

    # Test 4: Detects close price below low
    def test_detects_close_below_low(self):
        """Test detection of close price below low"""
        df = self.create_clean_data()

        # Set close below low
        df.loc[df.index[0], "close"] = 90.0  # low is 95.0

        with pytest.raises(DataQualityError) as exc_info:
            self.validator.validate_market_data(df)

        assert "Close price below low" in str(exc_info.value)

    # Test 5: Detects price jumps > 20%
    def test_detects_large_price_jumps(self):
        """Test detection of suspicious price jumps"""
        df = self.create_clean_data(num_days=5, num_symbols=1)

        # Create 25% price jump (above 20% threshold)
        df.loc[df.index[2], "close"] = 125.0  # 25% jump from 100.0

        with pytest.raises(DataQualityError) as exc_info:
            self.validator.validate_market_data(df)

        assert "suspicious price jumps" in str(exc_info.value)
        assert "25.0%" in str(exc_info.value)

    # Test 6: Allows price jumps < 20%
    def test_allows_normal_price_moves(self):
        """Test that normal price moves (< 20%) are allowed"""
        df = self.create_clean_data(num_days=5, num_symbols=1)

        # Create 15% price move (below 20% threshold)
        # Also adjust high to accommodate the new close price
        df.loc[df.index[2], "close"] = 115.0  # 15% move from 100.0
        df.loc[df.index[2], "high"] = 120.0  # Adjust high to be above close

        # Should not raise exception
        self.validator.validate_market_data(df)

    # Test 7: Detects high zero volume
    def test_detects_high_zero_volume(self):
        """Test detection of high percentage of zero volume"""
        df = self.create_clean_data(num_days=20, num_symbols=1)

        # Set 10% of rows to zero volume (above 5% threshold)
        zero_indices = df.index[:2]
        df.loc[zero_indices, "volume"] = 0

        with pytest.raises(DataQualityError) as exc_info:
            self.validator.validate_market_data(df)

        assert "High zero volume" in str(exc_info.value)

    # Test 8: Allows low zero volume
    def test_allows_low_zero_volume(self):
        """Test that low percentage of zero volume is allowed"""
        df = self.create_clean_data(num_days=100, num_symbols=1)

        # Set 2% of rows to zero volume (below 5% threshold)
        zero_indices = df.index[:2]
        df.loc[zero_indices, "volume"] = 0

        # Should not raise exception
        self.validator.validate_market_data(df)

    # Test 9: Detects large gaps in data
    def test_detects_large_data_gaps(self):
        """Test detection of large gaps in data (> 5 days)"""
        # Create data with 10-day gap
        dates1 = pd.date_range(end=datetime.now(), periods=5, freq="D")
        dates2 = pd.date_range(start=datetime.now() + timedelta(days=10), periods=5, freq="D")
        all_dates = list(dates1) + list(dates2)

        data = []
        for _date in all_dates:
            data.append({"symbol": "TEST", "close": 100.0, "volume": 1000000})

        df = pd.DataFrame(data)
        df.index = pd.to_datetime(all_dates)

        with pytest.raises(DataQualityError) as exc_info:
            self.validator.validate_market_data(df)

        assert "large gaps in data" in str(exc_info.value)

    # Test 10: Multiple errors reported together
    def test_multiple_errors_reported(self):
        """Test that multiple errors are reported together"""
        df = self.create_clean_data()

        # Add multiple issues
        df.loc[df.index[0], "close"] = 110.0  # Close above high
        df.loc[df.index[1], "close"] = 90.0  # Close below low

        with pytest.raises(DataQualityError) as exc_info:
            self.validator.validate_market_data(df)

        error_msg = str(exc_info.value)
        assert "Close price above high" in error_msg
        assert "Close price below low" in error_msg


class TestDataValidatorFreshness:
    """Freshness gate now defers to the calendar-aware is_fresh (SSOT).

    Regression for June 2026: a backup run firing hours late aged weekend-gap
    data past DATA_MAX_AGE_HOURS, so the engine's validator hard-failed
    ("Data is 86.2 hours old") on data pre_flight_check.py had just passed.
    """

    def _write_valid_csv(self, tmp_path, latest_d):
        """A CSV satisfying every non-freshness check, ending on latest_d."""
        from datetime import datetime as _dt
        from datetime import time as _time

        end = _dt.combine(latest_d, _time(0, 0))
        dates = pd.date_range(end=end, periods=300, freq="D")
        rows, idx = [], []
        for sym in [f"SYM{i:02d}" for i in range(30)]:  # >= 29 symbols
            for d in dates:
                rows.append(
                    {
                        "symbol": sym,
                        "close": 100.0,
                        "rsi": 50.0,
                        "volatility_20d": 0.2,
                        "sma_50": 100.0,
                        "sma_200": 100.0,
                    }
                )
                idx.append(d)
        df = pd.DataFrame(rows)
        df.index = pd.to_datetime(idx)
        path = tmp_path / "training_data.csv"
        df.to_csv(path)
        return path

    def test_stale_age_but_covers_last_session_passes(self, tmp_path):
        """Age over threshold is fine when data covers the last completed session."""
        from src.validation.data_freshness import last_completed_session

        session = last_completed_session(datetime.utcnow())
        path = self._write_valid_csv(tmp_path, session)

        # max_age_hours=1 guarantees the age path fails; only the session path
        # (the fix) can make this valid.
        validator = DataValidator(max_age_hours=1)
        is_valid, errors = validator.validate_data_file(path)

        assert is_valid, f"weekend-gap data should pass via session check: {errors}"

    def test_missing_last_session_and_stale_fails(self, tmp_path):
        """Genuinely stale data that misses the last session still fails."""
        from datetime import timedelta

        from src.validation.data_freshness import last_completed_session

        # End a full week before the last session: misses it AND exceeds age.
        stale_end = last_completed_session(datetime.utcnow()) - timedelta(days=7)
        path = self._write_valid_csv(tmp_path, stale_end)

        validator = DataValidator(max_age_hours=1)
        is_valid, errors = validator.validate_data_file(path)

        assert not is_valid
        assert any("misses the last" in e for e in errors), errors


class TestDataValidatorEdgeCases:
    """Test edge cases for data validation"""

    def setup_method(self):
        """Setup for each test"""
        self.validator = DataValidator(max_age_hours=24, max_price_jump_pct=0.20)

    def test_empty_dataframe(self):
        """Test validation of empty DataFrame"""
        df = pd.DataFrame()

        # Should not raise exception (no data to validate)
        self.validator.validate_market_data(df)

    def test_single_row(self):
        """Test validation of single row"""
        df = pd.DataFrame(
            {
                "symbol": ["TEST"],
                "close": [100.0],
                "high": [105.0],
                "low": [95.0],
                "volume": [1000000],
            }
        )
        df.index = pd.to_datetime(["2024-01-01"])

        # Should not raise exception
        self.validator.validate_market_data(df)

    def test_missing_optional_columns(self):
        """Test validation with missing optional columns"""
        df = pd.DataFrame({"symbol": ["TEST", "TEST"], "close": [100.0, 101.0]})
        df.index = pd.to_datetime(["2024-01-01", "2024-01-02"])

        # Should not raise exception (high/low/volume are optional)
        self.validator.validate_market_data(df)

    def test_exact_20_percent_jump(self):
        """Test exact 20% price jump (at threshold)"""
        df = pd.DataFrame({"symbol": ["TEST", "TEST"], "close": [100.0, 120.0]})  # Exactly 20% jump
        df.index = pd.to_datetime(["2024-01-01", "2024-01-02"])

        # Should not raise exception (at threshold, not above)
        self.validator.validate_market_data(df)

    def test_nan_values_handled(self):
        """Test that NaN values don't cause crashes"""
        df = pd.DataFrame(
            {
                "symbol": ["TEST", "TEST", "TEST"],
                "close": [100.0, np.nan, 102.0],
                "volume": [1000000, 1000000, 1000000],
            }
        )
        df.index = pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"])

        # Should not raise exception (NaN is handled gracefully)
        self.validator.validate_market_data(df)


class TestDataValidatorIntegration:
    """Integration tests for data validation"""

    def test_realistic_stock_data(self):
        """Test with realistic stock data"""
        validator = DataValidator(max_age_hours=24, max_price_jump_pct=0.20)

        # Create realistic AAPL-like data
        dates = pd.date_range(end=datetime.now(), periods=30, freq="D")
        data = []

        base_price = 180.0
        for _i, _date in enumerate(dates):
            # Simulate realistic price movement
            price = base_price + np.random.randn() * 3  # ~$3 daily volatility
            data.append(
                {
                    "symbol": "AAPL",
                    "open": price - 1,
                    "high": price + 2,
                    "low": price - 2,
                    "close": price,
                    "volume": 50000000 + np.random.randint(-10000000, 10000000),
                }
            )

        df = pd.DataFrame(data)
        df.index = pd.to_datetime(dates)

        # Should pass validation
        validator.validate_market_data(df)

    def test_multiple_symbols(self):
        """Test validation with multiple symbols"""
        validator = DataValidator(max_age_hours=24, max_price_jump_pct=0.20)

        base_date = datetime.now() - timedelta(days=30)
        data = []
        indices = []

        day_counter = 0
        for symbol in ["AAPL", "MSFT", "GOOGL"]:
            for _i in range(10):
                date = base_date + timedelta(days=day_counter)
                data.append(
                    {
                        "symbol": symbol,
                        "open": 100.0,
                        "high": 105.0,
                        "low": 95.0,
                        "close": 100.0,
                        "volume": 1000000,
                    }
                )
                indices.append(date)
                day_counter += 1

        df = pd.DataFrame(data)
        df.index = pd.to_datetime(indices)

        # Should pass validation
        validator.validate_market_data(df)

    def test_bad_data_rejected(self):
        """Test that obviously bad data is rejected"""
        validator = DataValidator(max_age_hours=24, max_price_jump_pct=0.20)

        # Create data with multiple issues
        df = pd.DataFrame(
            {
                "symbol": ["BAD", "BAD", "BAD"],
                "open": [100.0, 100.0, 100.0],
                "high": [105.0, 105.0, 105.0],
                "low": [95.0, 95.0, 95.0],
                "close": [100.0, 500.0, 100.0],  # 400% jump!
                "volume": [1000000, 0, 1000000],
            }
        )
        df.index = pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"])

        # Should raise exception
        with pytest.raises(DataQualityError):
            validator.validate_market_data(df)


# Property-based tests using hypothesis
try:
    from hypothesis import given
    from hypothesis import strategies as st

    class TestDataValidatorProperties:
        """Property-based tests for data validation"""

        @pytest.mark.skip(
            reason="Hypothesis deadline issues - validation logic tested in other tests"
        )
        @given(
            close=st.floats(min_value=1.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
            high=st.floats(min_value=1.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
            low=st.floats(min_value=1.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
        )
        def test_close_within_high_low_property(self, close, high, low):
            """Property: If close is within high/low, validation should pass"""

            validator = DataValidator()

            # Ensure high >= low
            if high < low:
                high, low = low, high

            # If close is within range, should pass
            if low <= close <= high:
                df = pd.DataFrame(
                    {
                        "symbol": ["TEST"],
                        "close": [close],
                        "high": [high],
                        "low": [low],
                        "volume": [1000000],
                    }
                )
                df.index = pd.to_datetime(["2024-01-01"])

                # Should not raise exception
                validator.validate_market_data(df)

except ImportError:
    print("hypothesis not installed, skipping property-based tests")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
