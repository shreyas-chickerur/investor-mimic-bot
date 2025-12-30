#!/usr/bin/env python3
"""
Alternative Historical Data Fetcher using pandas_datareader
Downloads 10+ years of OHLCV data for walk-forward validation
"""
import os
import sys
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Stock universe (36 large-cap stocks)
STOCK_UNIVERSE = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'BRK-B',
    'JPM', 'JNJ', 'V', 'PG', 'XOM', 'UNH', 'MA', 'HD',
    'CVX', 'MRK', 'ABBV', 'PEP', 'KO', 'AVGO', 'COST', 'LLY',
    'WMT', 'MCD', 'DIS', 'CSCO', 'ADBE', 'NFLX', 'CRM', 'INTC',
    'AMD', 'QCOM', 'TXN', 'ORCL'
]

def fetch_with_pandas_datareader(symbols, start_date, end_date, output_file):
    """
    Fetch historical data using pandas_datareader (Yahoo Finance)
    """
    try:
        import pandas_datareader as pdr
    except ImportError:
        logger.error("pandas_datareader not installed. Run: pip install pandas-datareader")
        return None, []
    
    logger.info(f"Fetching data for {len(symbols)} symbols from {start_date} to {end_date}")
    
    all_data = []
    failed_symbols = []
    
    for i, symbol in enumerate(symbols, 1):
        try:
            logger.info(f"[{i}/{len(symbols)}] Fetching {symbol}...")
            
            # Download data from Yahoo Finance via pandas_datareader
            df = pdr.get_data_yahoo(symbol, start=start_date, end=end_date)
            
            if df.empty:
                logger.warning(f"No data for {symbol}")
                failed_symbols.append(symbol)
                continue
            
            # Reset index to get date as column
            df = df.reset_index()
            
            # Add symbol column
            df['symbol'] = symbol
            
            # Rename columns to match our format
            df = df.rename(columns={
                'Date': 'date',
                'Open': 'open',
                'High': 'high',
                'Low': 'low',
                'Close': 'close',
                'Volume': 'volume',
                'Adj Close': 'adj_close'
            })
            
            # Select only needed columns
            df = df[['date', 'symbol', 'open', 'high', 'low', 'close', 'volume']]
            
            all_data.append(df)
            logger.info(f"  ✓ {symbol}: {len(df)} rows")
            
        except Exception as e:
            logger.error(f"  ✗ {symbol}: {e}")
            failed_symbols.append(symbol)
    
    if not all_data:
        raise ValueError("No data fetched for any symbol")
    
    # Combine all data
    combined_df = pd.concat(all_data, ignore_index=True)
    
    # Sort by date and symbol
    combined_df = combined_df.sort_values(['date', 'symbol'])
    
    # Save to CSV
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    combined_df.to_csv(output_path, index=False)
    
    logger.info(f"\n{'='*60}")
    logger.info(f"Data saved to: {output_path}")
    logger.info(f"Total rows: {len(combined_df):,}")
    logger.info(f"Symbols: {combined_df['symbol'].nunique()}")
    logger.info(f"Date range: {combined_df['date'].min()} to {combined_df['date'].max()}")
    logger.info(f"Failed symbols: {failed_symbols if failed_symbols else 'None'}")
    logger.info(f"{'='*60}\n")
    
    return combined_df, failed_symbols


def fetch_vix_data(start_date, end_date, output_file):
    """
    Fetch VIX data for regime detection
    """
    try:
        import pandas_datareader as pdr
    except ImportError:
        logger.error("pandas_datareader not installed")
        return None
    
    logger.info(f"Fetching VIX data from {start_date} to {end_date}")
    
    try:
        df = pdr.get_data_yahoo("^VIX", start=start_date, end=end_date)
        
        if df.empty:
            raise ValueError("No VIX data fetched")
        
        df = df.reset_index()
        df = df.rename(columns={
            'Date': 'date',
            'Close': 'vix_close'
        })
        
        df = df[['date', 'vix_close']]
        
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False)
        
        logger.info(f"VIX data saved to: {output_path}")
        logger.info(f"Total rows: {len(df):,}")
        logger.info(f"Date range: {df['date'].min()} to {df['date'].max()}")
        
        return df
        
    except Exception as e:
        logger.error(f"Failed to fetch VIX data: {e}")
        return None


def main():
    """Fetch all historical data for backtesting"""
    
    # Calculate date range (15 years of data)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=15*365)
    
    start_str = start_date.strftime('%Y-%m-%d')
    end_str = end_date.strftime('%Y-%m-%d')
    
    logger.info("="*60)
    logger.info("HISTORICAL DATA FETCHER (pandas_datareader)")
    logger.info("="*60)
    logger.info(f"Date range: {start_str} to {end_str}")
    logger.info(f"Symbols: {len(STOCK_UNIVERSE)}")
    logger.info("="*60 + "\n")
    
    # Fetch stock data
    stock_file = 'data/backtest_data.csv'
    stock_data, failed = fetch_with_pandas_datareader(
        STOCK_UNIVERSE, 
        start_str, 
        end_str, 
        stock_file
    )
    
    # Fetch VIX data
    vix_file = 'data/backtest_vix.csv'
    vix_data = fetch_vix_data(start_str, end_str, vix_file)
    
    logger.info("\n✅ Historical data fetch complete!")
    logger.info(f"Stock data: {stock_file}")
    logger.info(f"VIX data: {vix_file}")
    
    if failed:
        logger.warning(f"\n⚠️  Failed to fetch data for: {', '.join(failed)}")
        logger.warning("Backtesting will proceed with available symbols")


if __name__ == '__main__':
    main()
