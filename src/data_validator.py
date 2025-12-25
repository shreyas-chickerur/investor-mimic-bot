#!/usr/bin/env python3
"""
Data Validation System
Ensures data quality before trading
"""
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import logging
from dateutil import tz
from pandas.tseries.holiday import USFederalHolidayCalendar
from pandas.tseries.offsets import CustomBusinessDay

logger = logging.getLogger(__name__)

class DataValidator:
    """Validates market data quality"""
    
    def __init__(self, max_age_hours: int = 24):
        self.max_age_hours = max_age_hours
        self._holiday_calendar = USFederalHolidayCalendar()
        self._business_day = CustomBusinessDay(calendar=self._holiday_calendar)

    def _is_holiday(self, date: datetime.date) -> bool:
        holidays = self._holiday_calendar.holidays(start=date, end=date)
        return not holidays.empty

    def _previous_business_day(self, date: datetime.date) -> datetime.date:
        return (pd.Timestamp(date) - self._business_day).date()

    def _expected_latest_date(self, now: datetime) -> datetime.date:
        """Determine the expected latest trading date based on market time."""
        today = now.date()
        if now.weekday() >= 5 or self._is_holiday(today):
            return self._previous_business_day(today)

        market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
        if now >= market_close:
            return today

        return self._previous_business_day(today)
    
    def validate_data_file(self, data_path: Path):
        """
        Validate training data file
        
        Returns:
            (is_valid, errors)
        """
        errors = []
        
        # Check file exists
        if not data_path.exists():
            errors.append(f"Data file not found: {data_path}")
            return False, errors
        
        try:
            # Load data
            df = pd.read_csv(data_path, index_col=0)
            df.index = pd.to_datetime(df.index)
            
            # Check data freshness
            latest_date = df.index.max()
            now_utc = datetime.utcnow()
            market_now = datetime.now(tz=tz.gettz("America/New_York"))
            expected_latest_date = self._expected_latest_date(market_now)
            age_hours = (now_utc - latest_date).total_seconds() / 3600
            
            if latest_date.date() < expected_latest_date and age_hours > self.max_age_hours:
                errors.append(
                    "Data is "
                    f"{age_hours:.1f} hours old (max: {self.max_age_hours}); "
                    f"expected at least {expected_latest_date}"
                )
            
            # Check required columns
            required_cols = ['symbol', 'close', 'rsi', 'volatility_20d', 'sma_50', 'sma_200']
            missing_cols = [col for col in required_cols if col not in df.columns]
            
            if missing_cols:
                errors.append(f"Missing required columns: {missing_cols}")
            
            # Check data quality
            if df['close'].isna().sum() > len(df) * 0.1:
                errors.append(f"High percentage of NaN values in close prices: {df['close'].isna().sum() / len(df) * 100:.1f}%")
            
            # Check sufficient data for strategies
            days_available = (df.index.max() - df.index.min()).days
            if days_available < 250:  # ~200 trading days
                errors.append(f"Insufficient data for 200-day MA: only {days_available} days")
            
            # Check number of symbols
            num_symbols = df['symbol'].nunique()
            if num_symbols < 30:
                errors.append(f"Too few symbols: {num_symbols} (expected 36)")
            
            # Log validation results
            if errors:
                logger.warning(f"Data validation failed: {errors}")
                return False, errors
            else:
                logger.info(f"Data validation passed: {len(df)} rows, {num_symbols} symbols, {age_hours:.1f} hours old")
                return True, []
                
        except Exception as e:
            errors.append(f"Error validating data: {str(e)}")
            logger.error(f"Data validation error: {e}")
            return False, errors
    
    def validate_before_trading(self, data_path: Path) -> bool:
        """
        Validate data and raise exception if invalid
        
        Returns:
            True if valid
        
        Raises:
            ValueError if invalid
        """
        is_valid, errors = self.validate_data_file(data_path)
        
        if not is_valid:
            error_msg = "Data validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
            raise ValueError(error_msg)
        
        return True

def validate_data(data_path: Path, max_age_hours: int = 24):
    """Convenience function to validate data"""
    validator = DataValidator(max_age_hours)
    return validator.validate_data_file(data_path)
