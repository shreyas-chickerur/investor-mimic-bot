"""
Data Quality Checks

Validates data quality to prevent bad trades from bad data.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from utils.enhanced_logging import get_logger
from utils.monitoring import monitor

logger = get_logger(__name__)


class DataQualityChecker:
    """Comprehensive data quality validation."""
    
    def __init__(self):
        self.quality_metrics = []
    
    def check_missing_data(self, df: pd.DataFrame, required_columns: List[str]) -> Tuple[bool, str]:
        """Check for missing required columns or data."""
        # Check columns exist
        missing_cols = [col for col in required_columns if col not in df.columns]
        if missing_cols:
            return False, f"Missing columns: {missing_cols}"
        
        # Check for null values
        null_counts = df[required_columns].isnull().sum()
        if null_counts.any():
            null_cols = null_counts[null_counts > 0].to_dict()
            return False, f"Null values found: {null_cols}"
        
        return True, "No missing data"
    
    def check_outliers(
        self,
        data: pd.Series,
        method: str = 'iqr',
        threshold: float = 3.0
    ) -> Tuple[bool, List[int]]:
        """
        Detect outliers in data.
        
        Args:
            data: Data series to check
            method: 'iqr' or 'zscore'
            threshold: Threshold for outlier detection
            
        Returns:
            (is_clean, outlier_indices)
        """
        if method == 'iqr':
            Q1 = data.quantile(0.25)
            Q3 = data.quantile(0.75)
            IQR = Q3 - Q1
            lower_bound = Q1 - threshold * IQR
            upper_bound = Q3 + threshold * IQR
            outliers = data[(data < lower_bound) | (data > upper_bound)]
        else:  # zscore
            z_scores = np.abs((data - data.mean()) / data.std())
            outliers = data[z_scores > threshold]
        
        outlier_indices = outliers.index.tolist()
        is_clean = len(outlier_indices) == 0
        
        if not is_clean:
            logger.warning(f"Found {len(outlier_indices)} outliers in data")
        
        return is_clean, outlier_indices
    
    def check_data_staleness(
        self,
        timestamp: datetime,
        max_age_hours: int = 24
    ) -> Tuple[bool, str]:
        """Check if data is too old."""
        age = datetime.now() - timestamp
        max_age = timedelta(hours=max_age_hours)
        
        if age > max_age:
            return False, f"Data is {age.total_seconds()/3600:.1f} hours old (max: {max_age_hours})"
        
        return True, f"Data is fresh ({age.total_seconds()/3600:.1f} hours old)"
    
    def check_price_consistency(
        self,
        prices: Dict[str, float],
        historical_prices: Dict[str, List[float]]
    ) -> Tuple[bool, List[str]]:
        """Check if current prices are consistent with historical data."""
        suspicious_tickers = []
        
        for ticker, current_price in prices.items():
            if ticker not in historical_prices:
                continue
            
            hist = historical_prices[ticker]
            if len(hist) < 5:
                continue
            
            # Check if price is within reasonable range
            mean_price = np.mean(hist)
            std_price = np.std(hist)
            
            # Price shouldn't deviate more than 5 standard deviations
            if abs(current_price - mean_price) > 5 * std_price:
                suspicious_tickers.append(ticker)
                logger.warning(
                    f"{ticker}: Current price ${current_price:.2f} is suspicious "
                    f"(mean: ${mean_price:.2f}, std: ${std_price:.2f})"
                )
        
        is_consistent = len(suspicious_tickers) == 0
        return is_consistent, suspicious_tickers
    
    def check_volume_anomaly(
        self,
        current_volume: int,
        avg_volume: float,
        threshold: float = 5.0
    ) -> Tuple[bool, str]:
        """Check for unusual volume."""
        if avg_volume == 0:
            return True, "No historical volume data"
        
        ratio = current_volume / avg_volume
        
        if ratio > threshold:
            return False, f"Volume {ratio:.1f}x higher than average"
        elif ratio < 1/threshold:
            return False, f"Volume {ratio:.1f}x lower than average"
        
        return True, "Volume is normal"
    
    def validate_factor_scores(self, scores: Dict[str, float]) -> Tuple[bool, List[str]]:
        """Validate factor scores are in valid range."""
        invalid_factors = []
        
        for factor, score in scores.items():
            if not (0 <= score <= 1):
                invalid_factors.append(f"{factor}={score:.3f}")
                logger.error(f"Invalid factor score: {factor}={score:.3f}")
        
        is_valid = len(invalid_factors) == 0
        return is_valid, invalid_factors
    
    def check_data_completeness(
        self,
        data: pd.DataFrame,
        expected_rows: int,
        tolerance: float = 0.1
    ) -> Tuple[bool, str]:
        """Check if we have enough data."""
        actual_rows = len(data)
        min_required = int(expected_rows * (1 - tolerance))
        
        if actual_rows < min_required:
            return False, f"Insufficient data: {actual_rows}/{expected_rows} rows"
        
        return True, f"Data complete: {actual_rows}/{expected_rows} rows"
    
    def run_full_quality_check(
        self,
        data: Dict[str, any],
        config: Dict[str, any]
    ) -> Tuple[bool, List[str]]:
        """
        Run comprehensive quality checks on data.
        
        Args:
            data: Dictionary containing all data to validate
            config: Configuration for quality checks
            
        Returns:
            (passed, issues)
        """
        issues = []
        
        # Check prices
        if 'prices' in data:
            for ticker, price in data['prices'].items():
                if price <= 0:
                    issues.append(f"{ticker}: Invalid price ${price}")
                elif price > 100000:
                    issues.append(f"{ticker}: Suspiciously high price ${price}")
        
        # Check factor scores
        if 'factor_scores' in data:
            for ticker, scores in data['factor_scores'].items():
                is_valid, invalid = self.validate_factor_scores(scores)
                if not is_valid:
                    issues.append(f"{ticker}: Invalid scores {invalid}")
        
        # Check timestamps
        if 'timestamp' in data:
            is_fresh, msg = self.check_data_staleness(
                data['timestamp'],
                config.get('max_age_hours', 24)
            )
            if not is_fresh:
                issues.append(f"Stale data: {msg}")
        
        # Record metrics
        passed = len(issues) == 0
        monitor.record_metric('data_quality_checks', 1 if passed else 0)
        
        if not passed:
            monitor.create_alert(
                'warning',
                f"Data quality issues detected: {len(issues)} problems",
                {'issues': issues}
            )
            logger.warning(f"Data quality check failed: {issues}")
        else:
            logger.info("Data quality check passed")
        
        return passed, issues


# Global checker instance
_quality_checker = None


def get_quality_checker() -> DataQualityChecker:
    """Get global quality checker instance."""
    global _quality_checker
    if _quality_checker is None:
        _quality_checker = DataQualityChecker()
    return _quality_checker


def validate_data(data: Dict, config: Dict = None) -> Tuple[bool, List[str]]:
    """
    Convenience function to validate data quality.
    
    Usage:
        passed, issues = validate_data(data)
        if not passed:
            logger.error(f"Data quality issues: {issues}")
    """
    checker = get_quality_checker()
    return checker.run_full_quality_check(data, config or {})
