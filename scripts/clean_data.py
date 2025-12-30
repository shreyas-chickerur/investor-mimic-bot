#!/usr/bin/env python3
"""
Data Cleaning Script
Handles missing values in historical data using appropriate imputation methods
"""
import pandas as pd
import numpy as np
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def clean_training_data(input_file='data/training_data.csv', output_file='data/training_data_clean.csv'):
    """
    Clean training data by handling missing values appropriately
    
    Strategy:
    1. OHLCV data: Forward-fill (use last known price)
    2. Technical indicators: Forward-fill then backward-fill for start
    3. Volume: Forward-fill (use last known volume)
    """
    logger.info(f"Loading data from {input_file}")
    df = pd.read_csv(input_file)
    
    # Convert date to datetime if needed
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'])
    
    logger.info(f"Original data: {len(df):,} rows, {df.isnull().sum().sum()} missing values")
    
    # Separate by symbol for proper forward-fill
    cleaned_dfs = []
    
    for symbol in sorted(df['symbol'].unique()):
        symbol_df = df[df['symbol'] == symbol].copy()
        symbol_df = symbol_df.sort_values('date')
        
        # Count missing before
        missing_before = symbol_df.isnull().sum().sum()
        
        # 1. OHLCV columns - forward fill (use last known price)
        ohlcv_cols = ['open', 'high', 'low', 'close', 'adjusted_close', 'volume']
        for col in ohlcv_cols:
            if col in symbol_df.columns:
                symbol_df[col] = symbol_df[col].fillna(method='ffill')
                # If still NaN at start, backfill
                symbol_df[col] = symbol_df[col].fillna(method='bfill')
        
        # 2. Technical indicators - forward fill then backfill
        indicator_cols = ['rsi', 'rsi_slope', 'sma_20', 'sma_50', 'sma_100', 'sma_200',
                         'bb_middle', 'bb_upper', 'bb_lower', 'atr_20', 'volatility_20d',
                         'vwap', 'adx']
        
        for col in indicator_cols:
            if col in symbol_df.columns:
                # Forward fill
                symbol_df[col] = symbol_df[col].fillna(method='ffill')
                # Backfill for early periods
                symbol_df[col] = symbol_df[col].fillna(method='bfill')
                # If still NaN, use neutral values
                if col == 'rsi':
                    symbol_df[col] = symbol_df[col].fillna(50)  # Neutral RSI
                elif col == 'rsi_slope':
                    symbol_df[col] = symbol_df[col].fillna(0)   # No slope
                elif 'sma' in col or 'bb' in col or 'vwap' in col:
                    # Use close price as fallback for price-based indicators
                    symbol_df[col] = symbol_df[col].fillna(symbol_df['close'])
                elif col in ['atr_20', 'volatility_20d']:
                    # Use median volatility as fallback
                    median_val = symbol_df[col].median()
                    symbol_df[col] = symbol_df[col].fillna(median_val)
                elif col == 'adx':
                    symbol_df[col] = symbol_df[col].fillna(25)  # Neutral ADX
        
        missing_after = symbol_df.isnull().sum().sum()
        logger.info(f"  {symbol}: {missing_before} → {missing_after} missing values")
        
        cleaned_dfs.append(symbol_df)
    
    # Combine all symbols
    df_clean = pd.concat(cleaned_dfs, ignore_index=True)
    
    logger.info(f"\nCleaned data: {len(df_clean):,} rows, {df_clean.isnull().sum().sum()} missing values")
    
    # Save cleaned data
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df_clean.to_csv(output_path, index=False)
    
    logger.info(f"✅ Cleaned data saved to: {output_path}")
    
    # Generate cleaning report
    report = f"""# Data Cleaning Report

**Generated:** {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}

## Summary

- **Input File:** {input_file}
- **Output File:** {output_file}
- **Total Rows:** {len(df_clean):,}
- **Symbols:** {df_clean['symbol'].nunique()}
- **Missing Values Before:** {df.isnull().sum().sum():,}
- **Missing Values After:** {df_clean.isnull().sum().sum():,}

## Cleaning Methods Applied

### OHLCV Data
- **Method:** Forward-fill (use last known price)
- **Fallback:** Backward-fill for start of series
- **Columns:** open, high, low, close, adjusted_close, volume

### Technical Indicators

#### Price-based Indicators (SMA, Bollinger Bands, VWAP)
- **Method:** Forward-fill → Backward-fill → Use close price
- **Rationale:** Price-based indicators should track actual prices

#### RSI (Relative Strength Index)
- **Method:** Forward-fill → Backward-fill → 50 (neutral)
- **Rationale:** RSI of 50 indicates neutral momentum

#### RSI Slope
- **Method:** Forward-fill → Backward-fill → 0 (no change)
- **Rationale:** Zero slope indicates no momentum change

#### Volatility Indicators (ATR, Volatility)
- **Method:** Forward-fill → Backward-fill → Median value
- **Rationale:** Use historical median as reasonable estimate

#### ADX (Average Directional Index)
- **Method:** Forward-fill → Backward-fill → 25 (neutral)
- **Rationale:** ADX of 25 indicates moderate trend strength

## Validation

### Missing Values by Column (After Cleaning)
"""
    
    for col in df_clean.columns:
        missing = df_clean[col].isnull().sum()
        if missing > 0:
            report += f"- **{col}:** {missing:,} ({missing/len(df_clean)*100:.2f}%)\n"
    
    if df_clean.isnull().sum().sum() == 0:
        report += "\n✅ **No missing values remaining!**\n"
    
    report += f"""
## Impact on Backtesting

### Benefits
1. **Complete Data:** All strategies can use full dataset
2. **No NaN Errors:** Eliminates runtime errors from missing data
3. **Consistent Signals:** All indicators available for all periods

### Limitations
1. **Early Period Accuracy:** First 200 days use imputed values for 200-day SMA
2. **Survivorship Bias:** Still present (only current large-caps included)
3. **Imputation Assumptions:** Forward-fill assumes price continuity

### Recommendations
- Strategies should still validate data availability
- Consider excluding first 200 days from backtest
- Monitor for unrealistic indicator values

---

**Cleaning Script:** `scripts/clean_data.py`  
**Original Data:** `data/training_data.csv`  
**Cleaned Data:** `data/training_data_clean.csv`
"""
    
    # Save report
    report_path = Path('artifacts/data_cleaning_report.md')
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, 'w') as f:
        f.write(report)
    
    logger.info(f"✅ Cleaning report saved to: {report_path}")
    
    return df_clean


def main():
    """Clean training data"""
    logger.info("="*60)
    logger.info("DATA CLEANING")
    logger.info("="*60)
    
    clean_training_data()
    
    logger.info("\n🎉 Data cleaning complete!")
    logger.info("📊 Files created:")
    logger.info("   - data/training_data_clean.csv")
    logger.info("   - artifacts/data_cleaning_report.md")


if __name__ == '__main__':
    main()
