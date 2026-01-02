"""
Data Quality & Staleness Checker

Detects and blocks trading on:
- Stale data (configurable threshold, default 72 hours)
- Missing required indicators
- Data quality issues (excessive NaN, outliers)

Generates data_quality_report.json per run.
"""

import os
import json
import logging
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Set, Tuple

logger = logging.getLogger(__name__)


class DataQualityChecker:
    """
    Checks data quality and staleness before trading.
    
    Blocks affected symbols with DATA_QUALITY rejection reasons.
    Never trades on suspect data.
    """
    
    def __init__(self, artifacts_dir='artifacts/data_quality'):
        """
        Initialize data quality checker.
        
        Args:
            artifacts_dir: Directory for quality report artifacts
        """
        self.artifacts_dir = artifacts_dir
        
        # Staleness threshold (hours)
        self.staleness_threshold_hours = int(os.getenv('DATA_STALENESS_HOURS', '72'))
        
        # Quality thresholds
        self.max_nan_pct = float(os.getenv('MAX_NAN_PCT', '0.10'))  # 10% max NaN
        self.min_history_days = int(os.getenv('MIN_HISTORY_DAYS', '250'))  # For 200-day MA
        
        # Required indicators
        self.required_indicators = [
            'close', 'rsi', 'sma_20', 'sma_50', 'sma_100', 
            'atr', 'volatility_20d'
        ]
        
        # Create artifacts directory
        os.makedirs(self.artifacts_dir, exist_ok=True)
        
        logger.info(f"DataQualityChecker initialized: staleness={self.staleness_threshold_hours}h, "
                   f"max_nan={self.max_nan_pct:.1%}")
    
    def check_data_quality(self, market_data: pd.DataFrame, 
                          asof_date: datetime) -> Tuple[Set[str], Dict]:
        """
        Check data quality and identify symbols to block.
        
        Args:
            market_data: Market data DataFrame
            asof_date: As-of date for the run
        
        Returns:
            Tuple of (blocked_symbols, quality_report)
        """
        blocked_symbols = set()
        quality_report = {
            'asof_date': asof_date.isoformat(),
            'staleness_threshold_hours': self.staleness_threshold_hours,
            'symbols_checked': 0,
            'symbols_blocked': 0,
            'issues': {},
            'timestamp': datetime.now().isoformat()
        }
        
        if market_data.empty:
            logger.error("Market data is empty!")
            quality_report['issues']['EMPTY_DATA'] = {
                'severity': 'CRITICAL',
                'message': 'Market data DataFrame is empty',
                'symbols': []
            }
            # Save report and return - block all trading
            self._save_quality_report(quality_report)
            return set(), quality_report
        
        # Get unique symbols
        if 'symbol' not in market_data.columns:
            logger.error("Market data missing 'symbol' column!")
            quality_report['issues']['MISSING_SYMBOL_COLUMN'] = {
                'severity': 'CRITICAL',
                'message': 'Market data missing symbol column',
                'symbols': []
            }
            self._save_quality_report(quality_report)
            return set(), quality_report
        
        symbols = market_data['symbol'].unique()
        quality_report['symbols_checked'] = len(symbols)
        
        # Check each symbol
        for symbol in symbols:
            symbol_data = market_data[market_data['symbol'] == symbol].copy()
            
            # Check 1: Staleness
            stale, stale_reason = self._check_staleness(symbol_data, asof_date)
            if stale:
                blocked_symbols.add(symbol)
                self._add_issue(quality_report, 'STALE_DATA', symbol, stale_reason)
                continue
            
            # Check 2: Missing indicators
            missing, missing_reason = self._check_missing_indicators(symbol_data)
            if missing:
                blocked_symbols.add(symbol)
                self._add_issue(quality_report, 'MISSING_INDICATORS', symbol, missing_reason)
                continue
            
            # Check 3: Excessive NaN values
            excessive_nan, nan_reason = self._check_nan_values(symbol_data)
            if excessive_nan:
                blocked_symbols.add(symbol)
                self._add_issue(quality_report, 'EXCESSIVE_NAN', symbol, nan_reason)
                continue
            
            # Check 4: Insufficient history
            insufficient, history_reason = self._check_history_length(symbol_data)
            if insufficient:
                blocked_symbols.add(symbol)
                self._add_issue(quality_report, 'INSUFFICIENT_HISTORY', symbol, history_reason)
                continue
            
            # Check 5: Price outliers (sanity check)
            outlier, outlier_reason = self._check_price_outliers(symbol_data)
            if outlier:
                blocked_symbols.add(symbol)
                self._add_issue(quality_report, 'PRICE_OUTLIER', symbol, outlier_reason)
                continue
        
        quality_report['symbols_blocked'] = len(blocked_symbols)
        
        # Log summary
        if blocked_symbols:
            logger.warning(f"Data quality check: {len(blocked_symbols)}/{len(symbols)} symbols blocked")
            for issue_type, issue_data in quality_report['issues'].items():
                logger.warning(f"  {issue_type}: {len(issue_data['symbols'])} symbols")
        else:
            logger.info(f"Data quality check: All {len(symbols)} symbols passed")
        
        # Save report
        self._save_quality_report(quality_report)
        
        return blocked_symbols, quality_report
    
    def _check_staleness(self, symbol_data: pd.DataFrame, 
                        asof_date: datetime) -> Tuple[bool, str]:
        """Check if data is stale."""
        if symbol_data.empty:
            return True, "No data available"
        
        # Get most recent date in data
        if 'date' in symbol_data.columns:
            symbol_data['date'] = pd.to_datetime(symbol_data['date'])
            most_recent = symbol_data['date'].max()
        elif symbol_data.index.name == 'date':
            most_recent = pd.to_datetime(symbol_data.index.max())
        else:
            # Can't determine date, assume stale
            return True, "Cannot determine data date"
        
        # Calculate age
        age_hours = (asof_date - most_recent).total_seconds() / 3600
        
        if age_hours > self.staleness_threshold_hours:
            return True, f"Data age {age_hours:.1f}h exceeds threshold {self.staleness_threshold_hours}h"
        
        return False, ""
    
    def _check_missing_indicators(self, symbol_data: pd.DataFrame) -> Tuple[bool, str]:
        """Check for missing required indicators."""
        missing = []
        
        for indicator in self.required_indicators:
            if indicator not in symbol_data.columns:
                missing.append(indicator)
        
        if missing:
            return True, f"Missing indicators: {', '.join(missing)}"
        
        return False, ""
    
    def _check_nan_values(self, symbol_data: pd.DataFrame) -> Tuple[bool, str]:
        """Check for excessive NaN values."""
        total_rows = len(symbol_data)
        if total_rows == 0:
            return True, "No data rows"
        
        # Check each required indicator
        for indicator in self.required_indicators:
            if indicator in symbol_data.columns:
                nan_count = symbol_data[indicator].isna().sum()
                nan_pct = nan_count / total_rows
                
                if nan_pct > self.max_nan_pct:
                    return True, f"{indicator} has {nan_pct:.1%} NaN (threshold: {self.max_nan_pct:.1%})"
        
        return False, ""
    
    def _check_history_length(self, symbol_data: pd.DataFrame) -> Tuple[bool, str]:
        """Check if sufficient history available."""
        history_days = len(symbol_data)
        
        if history_days < self.min_history_days:
            return True, f"Only {history_days} days of history (need {self.min_history_days})"
        
        return False, ""
    
    def _check_price_outliers(self, symbol_data: pd.DataFrame) -> Tuple[bool, str]:
        """Check for price outliers (sanity check)."""
        if 'close' not in symbol_data.columns:
            return False, ""
        
        prices = symbol_data['close'].dropna()
        
        if len(prices) == 0:
            return True, "No valid prices"
        
        # Check for zero or negative prices
        if (prices <= 0).any():
            return True, "Zero or negative prices detected"
        
        # Check for extreme price jumps (>50% in one day)
        if len(prices) > 1:
            returns = prices.pct_change().dropna()
            if (returns.abs() > 0.50).any():
                max_jump = returns.abs().max()
                return True, f"Extreme price jump detected: {max_jump:.1%}"
        
        return False, ""
    
    def _add_issue(self, quality_report: Dict, issue_type: str, 
                   symbol: str, reason: str):
        """Add issue to quality report."""
        if issue_type not in quality_report['issues']:
            quality_report['issues'][issue_type] = {
                'severity': 'HIGH',
                'message': reason,
                'symbols': []
            }
        
        quality_report['issues'][issue_type]['symbols'].append({
            'symbol': symbol,
            'reason': reason
        })
    
    def _save_quality_report(self, quality_report: Dict):
        """Save data quality report artifact."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"data_quality_report_{timestamp}.json"
        filepath = os.path.join(self.artifacts_dir, filename)
        
        with open(filepath, 'w') as f:
            json.dump(quality_report, f, indent=2)
        
        logger.info(f"Saved data quality report: {filepath}")
    
    def get_blocked_symbols_summary(self, quality_report: Dict) -> str:
        """
        Generate human-readable summary of blocked symbols.
        
        Args:
            quality_report: Quality report dict
        
        Returns:
            Summary string for email/logs
        """
        if not quality_report.get('issues'):
            return "No data quality issues detected."
        
        lines = [f"Data Quality Issues: {quality_report['symbols_blocked']} symbols blocked\n"]
        
        for issue_type, issue_data in quality_report['issues'].items():
            symbol_count = len(issue_data['symbols'])
            lines.append(f"\n{issue_type} ({symbol_count} symbols):")
            
            # Show first 5 symbols as examples
            for symbol_info in issue_data['symbols'][:5]:
                lines.append(f"  • {symbol_info['symbol']}: {symbol_info['reason']}")
            
            if symbol_count > 5:
                lines.append(f"  ... and {symbol_count - 5} more")
        
        return '\n'.join(lines)
