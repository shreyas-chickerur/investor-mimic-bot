#!/usr/bin/env python3
"""
Fetch Extended Historical Data
Downloads 10+ years of historical data for all 36 stocks using Alpha Vantage

CONFIGURATION:
- Minimum 10 years (3650 days)
- Preferred 15 years (5475 days)
- Daily OHLCV bars
- Same 36 large-cap US stocks
"""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import pandas as pd
import time
from datetime import datetime, timedelta
import logging
import requests

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 36 large-cap stocks (same as current universe)
STOCK_SYMBOLS = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'BRK.B',
    'UNH', 'JNJ', 'JPM', 'V', 'PG', 'MA', 'HD', 'CVX',
    'MRK', 'ABBV', 'PEP', 'KO', 'AVGO', 'COST', 'WMT', 'MCD',
    'CSCO', 'ACN', 'LLY', 'TMO', 'DHR', 'ABT', 'NKE', 'DIS',
    'VZ', 'ADBE', 'NFLX', 'CRM'
]

class ExtendedDataFetcher:
    """Fetch extended historical data"""
    
    def __init__(self, api_key: str = None, years: int = 15):
        """
        Initialize fetcher
        
        Args:
            api_key: Alpha Vantage API key
            years: Years of history to fetch (default 15)
        """
        self.api_key = api_key or os.getenv('ALPHA_VANTAGE_API_KEY')
        if not self.api_key:
            raise ValueError("ALPHA_VANTAGE_API_KEY not set")
        
        self.years = years
        self.base_url = "https://www.alphavantage.co/query"
        
        logger.info(f"Fetcher initialized: {years} years of data")
    
    def fetch_stock_data(self, symbol: str) -> pd.DataFrame:
        """
        Fetch full historical data for a symbol
        
        Args:
            symbol: Stock symbol
            
        Returns:
            DataFrame with OHLCV data
        """
        logger.info(f"Fetching {symbol}...")
        
        params = {
            'function': 'TIME_SERIES_DAILY_ADJUSTED',
            'symbol': symbol,
            'outputsize': 'full',  # Get full history
            'apikey': self.api_key
        }
        
        try:
            response = requests.get(self.base_url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if 'Time Series (Daily)' not in data:
                if 'Note' in data:
                    logger.warning(f"{symbol}: API rate limit hit")
                    return None
                elif 'Error Message' in data:
                    logger.error(f"{symbol}: {data['Error Message']}")
                    return None
                else:
                    logger.error(f"{symbol}: Unexpected response format")
                    return None
            
            # Parse time series
            ts_data = data['Time Series (Daily)']
            
            records = []
            for date_str, values in ts_data.items():
                records.append({
                    'date': date_str,
                    'symbol': symbol,
                    'open': float(values['1. open']),
                    'high': float(values['2. high']),
                    'low': float(values['3. low']),
                    'close': float(values['4. close']),
                    'adjusted_close': float(values['5. adjusted close']),
                    'volume': int(values['6. volume'])
                })
            
            df = pd.DataFrame(records)
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date')
            
            # Filter to requested years
            cutoff_date = datetime.now() - timedelta(days=self.years * 365)
            df = df[df['date'] >= cutoff_date]
            
            logger.info(f"  {symbol}: {len(df)} days ({df['date'].min().date()} to {df['date'].max().date()})")
            
            return df
            
        except Exception as e:
            logger.error(f"Error fetching {symbol}: {e}")
            return None
    
    def fetch_all_stocks(self, delay_seconds: int = 12) -> pd.DataFrame:
        """
        Fetch data for all stocks
        
        Args:
            delay_seconds: Delay between API calls (Alpha Vantage limit: 5 calls/min)
            
        Returns:
            Combined DataFrame
        """
        logger.info(f"Fetching {len(STOCK_SYMBOLS)} stocks with {delay_seconds}s delay...")
        logger.info(f"Estimated time: {len(STOCK_SYMBOLS) * delay_seconds / 60:.1f} minutes")
        
        all_data = []
        
        for i, symbol in enumerate(STOCK_SYMBOLS, 1):
            logger.info(f"\n[{i}/{len(STOCK_SYMBOLS)}] {symbol}")
            
            df = self.fetch_stock_data(symbol)
            
            if df is not None and len(df) > 0:
                all_data.append(df)
            
            # Delay to respect API limits
            if i < len(STOCK_SYMBOLS):
                logger.info(f"Waiting {delay_seconds}s...")
                time.sleep(delay_seconds)
        
        if not all_data:
            raise ValueError("No data fetched for any symbol")
        
        # Combine all data
        combined = pd.concat(all_data, ignore_index=True)
        combined = combined.sort_values(['date', 'symbol'])
        
        logger.info(f"\nTotal records: {len(combined)}")
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
            
            # VWAP (daily)
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
    logger.info("EXTENDED HISTORICAL DATA FETCH")
    logger.info("="*80)
    
    # Initialize fetcher
    fetcher = ExtendedDataFetcher(years=15)
    
    # Fetch all stock data
    logger.info("\nFetching stock data...")
    df = fetcher.fetch_all_stocks(delay_seconds=12)
    
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
