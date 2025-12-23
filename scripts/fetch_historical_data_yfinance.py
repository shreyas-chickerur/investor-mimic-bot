#!/usr/bin/env python3
"""
Fetch Extended Historical Data using yfinance (FREE)
Downloads 15 years of historical data for all 36 stocks

yfinance is free and provides full historical data without API limits
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Install yfinance if needed
try:
    import yfinance as yf
except ImportError:
    logger.info("Installing yfinance...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "yfinance"])
    import yfinance as yf

# 36 large-cap stocks
STOCK_SYMBOLS = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'BRK-B',
    'UNH', 'JNJ', 'JPM', 'V', 'PG', 'MA', 'HD', 'CVX',
    'MRK', 'ABBV', 'PEP', 'KO', 'AVGO', 'COST', 'WMT', 'MCD',
    'CSCO', 'ACN', 'LLY', 'TMO', 'DHR', 'ABT', 'NKE', 'DIS',
    'VZ', 'ADBE', 'NFLX', 'CRM'
]

class YFinanceDataFetcher:
    """Fetch extended historical data using yfinance (free)"""
    
    def __init__(self, years: int = 15):
        self.years = years
        logger.info(f"YFinance fetcher initialized: {years} years of data")
    
    def fetch_stock_data(self, symbol: str) -> pd.DataFrame:
        """Fetch historical data for a symbol"""
        logger.info(f"Fetching {symbol}...")
        
        try:
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=self.years * 365)
            
            # Fetch data
            ticker = yf.Ticker(symbol)
            df = ticker.history(start=start_date, end=end_date, interval='1d')
            
            if len(df) == 0:
                logger.warning(f"  {symbol}: No data returned")
                return None
            
            # Rename columns to match our format
            df = df.reset_index()
            df = df.rename(columns={
                'Date': 'date',
                'Open': 'open',
                'High': 'high',
                'Low': 'low',
                'Close': 'close',
                'Volume': 'volume'
            })
            
            # Add symbol column
            df['symbol'] = symbol
            
            # Keep only needed columns
            df = df[['date', 'symbol', 'open', 'high', 'low', 'close', 'volume']]
            
            # Add adjusted_close (same as close for now)
            df['adjusted_close'] = df['close']
            
            logger.info(f"  {symbol}: {len(df)} days ({df['date'].min().date()} to {df['date'].max().date()})")
            
            return df
            
        except Exception as e:
            logger.error(f"Error fetching {symbol}: {e}")
            return None
    
    def fetch_all_stocks(self) -> pd.DataFrame:
        """Fetch data for all stocks"""
        logger.info(f"Fetching {len(STOCK_SYMBOLS)} stocks...")
        
        all_data = []
        
        for i, symbol in enumerate(STOCK_SYMBOLS, 1):
            logger.info(f"\n[{i}/{len(STOCK_SYMBOLS)}] {symbol}")
            
            df = self.fetch_stock_data(symbol)
            
            if df is not None and len(df) > 0:
                all_data.append(df)
        
        if not all_data:
            raise ValueError("No data fetched for any symbol")
        
        # Combine all data
        combined = pd.concat(all_data, ignore_index=True)
        combined = combined.sort_values(['date', 'symbol'])
        
        logger.info(f"\nTotal records: {len(combined):,}")
        logger.info(f"Date range: {combined['date'].min().date()} to {combined['date'].max().date()}")
        logger.info(f"Symbols: {combined['symbol'].nunique()}")
        
        return combined
    
    def calculate_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate all required technical indicators"""
        logger.info("Calculating technical indicators...")
        
        df = df.copy()
        df = df.sort_values(['symbol', 'date'])
        
        for symbol in df['symbol'].unique():
            mask = df['symbol'] == symbol
            symbol_data = df[mask].copy()
            
            # RSI
            delta = symbol_data['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            symbol_data['rsi'] = 100 - (100 / (1 + rs))
            
            # RSI slope
            symbol_data['rsi_slope'] = symbol_data['rsi'].diff()
            
            # Moving averages
            symbol_data['sma_20'] = symbol_data['close'].rolling(window=20).mean()
            symbol_data['sma_50'] = symbol_data['close'].rolling(window=50).mean()
            symbol_data['sma_100'] = symbol_data['close'].rolling(window=100).mean()
            symbol_data['sma_200'] = symbol_data['close'].rolling(window=200).mean()
            
            # Bollinger Bands
            symbol_data['bb_middle'] = symbol_data['close'].rolling(window=20).mean()
            bb_std = symbol_data['close'].rolling(window=20).std()
            symbol_data['bb_upper'] = symbol_data['bb_middle'] + (bb_std * 2)
            symbol_data['bb_lower'] = symbol_data['bb_middle'] - (bb_std * 2)
            
            # ATR
            high_low = symbol_data['high'] - symbol_data['low']
            high_close = abs(symbol_data['high'] - symbol_data['close'].shift())
            low_close = abs(symbol_data['low'] - symbol_data['close'].shift())
            tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            symbol_data['atr_20'] = tr.rolling(window=20).mean()
            
            # VWAP (daily reset)
            symbol_data['vwap'] = (symbol_data['close'] * symbol_data['volume']).cumsum() / symbol_data['volume'].cumsum()
            
            # ADX (simplified)
            plus_dm = symbol_data['high'].diff()
            minus_dm = -symbol_data['low'].diff()
            plus_dm[plus_dm < 0] = 0
            minus_dm[minus_dm < 0] = 0
            tr_smooth = tr.rolling(window=14).mean()
            plus_di = 100 * (plus_dm.rolling(window=14).mean() / tr_smooth)
            minus_di = 100 * (minus_dm.rolling(window=14).mean() / tr_smooth)
            dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
            symbol_data['adx'] = dx.rolling(window=14).mean()
            
            # Update main dataframe
            df.loc[mask, symbol_data.columns] = symbol_data
        
        logger.info("Technical indicators calculated")
        return df
    
    def save_data(self, df: pd.DataFrame, output_path: str = 'data/extended_historical_data.csv'):
        """Save data to CSV"""
        output_file = Path(output_path)
        output_file.parent.mkdir(exist_ok=True)
        
        df.to_csv(output_file, index=False)
        logger.info(f"Data saved to {output_file}")
        logger.info(f"File size: {output_file.stat().st_size / 1024 / 1024:.2f} MB")

def main():
    """Fetch extended historical data"""
    logger.info("="*80)
    logger.info("EXTENDED HISTORICAL DATA FETCH (yfinance)")
    logger.info("="*80)
    
    # Initialize fetcher
    fetcher = YFinanceDataFetcher(years=15)
    
    # Fetch all stock data
    logger.info("\nFetching stock data...")
    df = fetcher.fetch_all_stocks()
    
    # Calculate technical indicators
    df = fetcher.calculate_technical_indicators(df)
    
    # Save
    fetcher.save_data(df)
    
    logger.info("\n" + "="*80)
    logger.info("DATA FETCH COMPLETE")
    logger.info("="*80)
    
    # Summary
    print(f"\nSummary:")
    print(f"  Records: {len(df):,}")
    print(f"  Symbols: {df['symbol'].nunique()}")
    print(f"  Date range: {df['date'].min().date()} to {df['date'].max().date()}")
    print(f"  Years: {(df['date'].max() - df['date'].min()).days / 365.25:.1f}")
    print(f"\nData ready for walk-forward backtesting!")

if __name__ == '__main__':
    main()
