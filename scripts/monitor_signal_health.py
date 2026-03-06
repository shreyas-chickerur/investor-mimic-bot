#!/usr/bin/env python3
"""
Signal Generation Health Monitor
Checks if strategies are generating signals and alerts if there's an issue
"""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import logging
from datetime import datetime, timedelta
from src.data.universe_provider import UniverseProvider

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_signal_health():
    """Check if signal generation is healthy"""
    
    logger.info("="*80)
    logger.info("SIGNAL GENERATION HEALTH CHECK")
    logger.info("="*80)
    
    issues = []
    warnings = []
    
    # 1. Check if data file exists
    data_file = Path('data/training_data.csv')
    if not data_file.exists():
        issues.append("Data file not found at data/training_data.csv")
        logger.error("❌ Data file not found")
        return False, issues, warnings
    
    logger.info("✅ Data file exists")
    
    # 2. Check data freshness
    df = pd.read_csv(data_file)
    df['date'] = pd.to_datetime(df['date'])
    latest_date = df['date'].max()
    data_age_days = (pd.Timestamp.now() - latest_date).days
    
    logger.info(f"Data age: {data_age_days} days (latest: {latest_date.date()})")
    
    if data_age_days > 7:
        issues.append(f"Data is very stale: {data_age_days} days old")
        logger.error(f"❌ Data is {data_age_days} days old - needs update")
    elif data_age_days > 3:
        warnings.append(f"Data is somewhat stale: {data_age_days} days old")
        logger.warning(f"⚠️  Data is {data_age_days} days old - consider updating")
    else:
        logger.info("✅ Data is fresh")
    
    # 3. Check data completeness
    expected_symbols = len(UniverseProvider().get_universe())
    actual_symbols = df['symbol'].nunique()
    
    if actual_symbols < expected_symbols:
        issues.append(f"Missing symbols: {actual_symbols}/{expected_symbols}")
        logger.error(f"❌ Only {actual_symbols}/{expected_symbols} symbols in data")
    else:
        logger.info(f"✅ All {actual_symbols} symbols present")
    
    # 4. Check for required columns
    required_cols = ['symbol', 'close', 'volume', 'rsi', 'sma_20', 'sma_50', 'atr_20']
    missing_cols = [col for col in required_cols if col not in df.columns]
    
    if missing_cols:
        issues.append(f"Missing columns: {missing_cols}")
        logger.error(f"❌ Missing required columns: {missing_cols}")
    else:
        logger.info("✅ All required columns present")
    
    # 5. Check for NaN values in critical columns
    df_latest = df.groupby('symbol').tail(1)
    for col in ['rsi', 'close', 'volume']:
        if col in df_latest.columns:
            nan_count = df_latest[col].isna().sum()
            if nan_count > 0:
                warnings.append(f"{nan_count} symbols have NaN in {col}")
                logger.warning(f"⚠️  {nan_count} symbols have NaN in {col}")
    
    # 6. Check if any symbols meet RSI criteria
    if 'rsi' in df_latest.columns:
        rsi_low = len(df_latest[df_latest['rsi'] < 40])
        logger.info(f"Symbols with RSI < 40: {rsi_low}")
        
        if rsi_low == 0:
            warnings.append("No symbols with RSI < 40 - signals unlikely")
            logger.warning("⚠️  No symbols with RSI < 40 - RSI strategy unlikely to generate signals")
    
    # Summary
    logger.info("\n" + "="*80)
    logger.info("HEALTH CHECK SUMMARY")
    logger.info("="*80)
    
    if issues:
        logger.error(f"\n❌ CRITICAL ISSUES ({len(issues)}):")
        for issue in issues:
            logger.error(f"  - {issue}")
    
    if warnings:
        logger.warning(f"\n⚠️  WARNINGS ({len(warnings)}):")
        for warning in warnings:
            logger.warning(f"  - {warning}")
    
    if not issues and not warnings:
        logger.info("\n✅ ALL CHECKS PASSED - Signal generation should work normally")
    
    return len(issues) == 0, issues, warnings

def main():
    """Main execution"""
    healthy, issues, warnings = check_signal_health()
    
    if not healthy:
        logger.error("\n" + "="*80)
        logger.error("❌ SIGNAL GENERATION HEALTH CHECK FAILED")
        logger.error("="*80)
        logger.error("\nRecommended actions:")
        logger.error("  1. Run: python3 scripts/update_daily_data.py")
        logger.error("  2. Check data file integrity")
        logger.error("  3. Verify API keys are set")
        sys.exit(1)
    else:
        logger.info("\n" + "="*80)
        logger.info("✅ SIGNAL GENERATION HEALTH CHECK PASSED")
        logger.info("="*80)
        sys.exit(0)

if __name__ == '__main__':
    main()
