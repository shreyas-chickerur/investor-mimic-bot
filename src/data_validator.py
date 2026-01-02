#!/usr/bin/env python3
"""
Data Validation System
Ensures data quality before trading

Phase 1.2: Enhanced with comprehensive data quality checks
- Missing days detection
- Duplicate timestamps
- Price jump detection (>20%)
- Zero volume detection
- OHLC consistency checks
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import logging
import os
from typing import Tuple, List
from dateutil import tz
from pandas.tseries.holiday import USFederalHolidayCalendar
from pandas.tseries.offsets import CustomBusinessDay

logger = logging.getLogger(__name__)


class DataQualityError(Exception):
    """Raised when data quality checks fail"""
    pass

class DataValidator:
    """
    Validates market data quality with comprehensive checks
    
    Checks performed:
    - Data freshness (max age)
    - Missing days (gaps > 3 trading days)
    - Duplicate timestamps
    - Price jumps > 20% (likely data errors)
    - Zero volume (stale data)
    - OHLC consistency (close within high/low range)
    - Required columns present
    - Sufficient historical data
    """
    
    def __init__(self, max_age_hours: int = 24, max_price_jump_pct: float = 0.20):
        self.max_age_hours = max_age_hours
        self.max_price_jump_pct = max_price_jump_pct
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
    
    def validate_data_file(self, data_path: Path) -> Tuple[bool, List[str]]:
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
            
            # Check data freshness - configurable threshold
            latest_date = df.index.max()
            now_utc = datetime.utcnow()
            market_now = datetime.now(tz=tz.gettz("America/New_York"))
            expected_latest_date = self._expected_latest_date(market_now)
            age_hours = (now_utc - latest_date).total_seconds() / 3600
            
            max_age_hours = int(os.getenv('DATA_VALIDATOR_MAX_AGE_HOURS', '96'))
            if latest_date.date() < expected_latest_date and age_hours > max_age_hours:
                expected_date = (datetime.now() - timedelta(hours=max_age_hours)).strftime('%Y-%m-%d')
                errors.append(
                    "Data is "
                    f"{age_hours:.1f} hours old (max: {max_age_hours}); "
                    f"expected at least {expected_date}"
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
    
    def validate_market_data(self, df: pd.DataFrame) -> None:
        """
        Comprehensive validation of market data DataFrame
        
        Args:
            df: DataFrame with OHLCV data and timestamp index
            
        Raises:
            DataQualityError: If any validation check fails
        """
        errors = []
        
        # Check 1: Duplicate timestamps
        if df.index.duplicated().any():
            duplicates = df[df.index.duplicated(keep=False)].index.unique()
            errors.append(f"Duplicate timestamps found: {len(duplicates)} dates")
        
        # Check 2: OHLC consistency (close must be within high/low range)
        if 'high' in df.columns and 'low' in df.columns and 'close' in df.columns:
            invalid_close_high = (df['close'] > df['high']).sum()
            invalid_close_low = (df['close'] < df['low']).sum()
            
            if invalid_close_high > 0:
                errors.append(f"Close price above high: {invalid_close_high} rows")
            if invalid_close_low > 0:
                errors.append(f"Close price below low: {invalid_close_low} rows")
        
        # Check 3: Price jumps > 20% (likely data errors)
        if 'close' in df.columns and 'symbol' in df.columns:
            for symbol in df['symbol'].unique():
                symbol_data = df[df['symbol'] == symbol].sort_index()
                if len(symbol_data) > 1:
                    returns = symbol_data['close'].pct_change()
                    suspicious_jumps = (abs(returns) > self.max_price_jump_pct).sum()
                    
                    if suspicious_jumps > 0:
                        max_jump = abs(returns).max()
                        errors.append(
                            f"{symbol}: {suspicious_jumps} suspicious price jumps "
                            f"(max: {max_jump*100:.1f}%, threshold: {self.max_price_jump_pct*100:.0f}%)"
                        )
        
        # Check 4: Zero volume (stale data)
        if 'volume' in df.columns:
            zero_volume = (df['volume'] == 0).sum()
            if zero_volume > 0:
                zero_pct = zero_volume / len(df) * 100
                if zero_pct > 5:  # More than 5% zero volume is suspicious
                    errors.append(f"High zero volume: {zero_volume} rows ({zero_pct:.1f}%)")
        
        # Check 5: Missing days (gaps > 3 trading days)
        if 'symbol' in df.columns:
            for symbol in df['symbol'].unique():
                symbol_data = df[df['symbol'] == symbol].sort_index()
                if len(symbol_data) > 1:
                    date_diffs = symbol_data.index.to_series().diff()
                    # More than 5 days gap (accounting for weekends) is suspicious
                    large_gaps = (date_diffs > pd.Timedelta(days=5)).sum()
                    
                    if large_gaps > 0:
                        max_gap = date_diffs.max().days
                        errors.append(
                            f"{symbol}: {large_gaps} large gaps in data "
                            f"(max gap: {max_gap} days)"
                        )
        
        # Raise exception if any errors found
        if errors:
            error_msg = "Data quality validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
            logger.error(error_msg)
            raise DataQualityError(error_msg)
        
        logger.info(f"Data quality validation passed: {len(df)} rows validated")
    
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
