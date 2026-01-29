#!/usr/bin/env python3
"""
Daily Data Update Script
Fetches latest market data and appends to training_data.csv
Ensures data is always fresh for trading strategies
"""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

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

# Import universe from config
from src.data.universe_provider import UniverseProvider

class DailyDataUpdater:
    """Update training data with latest market data"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv('ALPHA_VANTAGE_API_KEY')
        if not self.api_key:
            raise ValueError("ALPHA_VANTAGE_API_KEY not set")
        
        self.base_url = "https://www.alphavantage.co/query"
        self.universe = UniverseProvider().get_universe()
        logger.info(f"Initialized updater for {len(self.universe)} symbols")
    
    def fetch_latest_data(self, symbol: str, days: int = 5) -> pd.DataFrame:
        """
        Fetch latest data for a symbol
        
        Args:
            symbol: Stock symbol
            days: Number of days to fetch (default 5 to ensure we get latest)
            
        Returns:
            DataFrame with latest OHLCV data
        """
        params = {
            'function': 'TIME_SERIES_DAILY_ADJUSTED',
            'symbol': symbol,
            'outputsize': 'compact',  # Last 100 days
            'apikey': self.api_key
        }
        
        try:
            response = requests.get(self.base_url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if 'Time Series (Daily)' not in data:
                logger.warning(f"{symbol}: No data - {data.get('Note', data.get('Error Message', 'Unknown error'))}")
                return None
            
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
            
            # Get only the latest days
            cutoff = datetime.now() - timedelta(days=days)
            df = df[df['date'] >= cutoff]
            
            return df
            
        except Exception as e:
            logger.error(f"Error fetching {symbol}: {e}")
            return None
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate technical indicators for new data"""
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
            
            # Volatility
            returns = symbol_data['close'].pct_change()
            symbol_data['volatility_20d'] = returns.rolling(window=20).std()
            
            # VWAP
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
            
            df.loc[mask, symbol_data.columns] = symbol_data
        
        return df
    
    def update_training_data(self, data_file: str = 'data/training_data.csv'):
        """Update training data with latest market data"""
        data_path = Path(data_file)
        
        # Load existing data
        if data_path.exists():
            logger.info(f"Loading existing data from {data_path}")
            existing_df = pd.read_csv(data_path)
            existing_df['date'] = pd.to_datetime(existing_df['date'])
            latest_date = existing_df['date'].max()
            logger.info(f"  Existing data: {len(existing_df)} rows, latest date: {latest_date.date()}")
        else:
            logger.warning(f"No existing data found at {data_path}")
            existing_df = None
            latest_date = None
        
        # Fetch latest data for all symbols
        logger.info(f"\nFetching latest data for {len(self.universe)} symbols...")
        new_data = []
        failed = []
        
        for i, symbol in enumerate(self.universe, 1):
            logger.info(f"[{i}/{len(self.universe)}] {symbol}")
            
            df = self.fetch_latest_data(symbol, days=5)
            
            if df is not None and len(df) > 0:
                new_data.append(df)
            else:
                failed.append(symbol)
            
            # Rate limiting: 5 requests per minute for free tier
            if i < len(self.universe):
                time.sleep(12)  # 12 seconds between requests
        
        if failed:
            logger.warning(f"Failed to fetch {len(failed)} symbols: {failed}")
        
        if not new_data:
            logger.error("No new data fetched!")
            return False
        
        # Combine new data
        new_df = pd.concat(new_data, ignore_index=True)
        new_df = new_df.sort_values(['date', 'symbol'])
        
        logger.info(f"\nNew data fetched: {len(new_df)} rows")
        logger.info(f"  Date range: {new_df['date'].min().date()} to {new_df['date'].max().date()}")
        logger.info(f"  Symbols: {new_df['symbol'].nunique()}")
        
        # Merge with existing data
        if existing_df is not None:
            # Remove overlapping dates from existing data
            existing_df = existing_df[existing_df['date'] < new_df['date'].min()]
            
            # Combine
            combined_df = pd.concat([existing_df, new_df], ignore_index=True)
            combined_df = combined_df.sort_values(['date', 'symbol'])
            
            # Keep last 2 years of data to prevent file from growing too large
            cutoff_date = datetime.now() - timedelta(days=730)
            combined_df = combined_df[combined_df['date'] >= cutoff_date]
            
            logger.info(f"\nCombined data: {len(combined_df)} rows")
            logger.info(f"  Date range: {combined_df['date'].min().date()} to {combined_df['date'].max().date()}")
        else:
            combined_df = new_df
        
        # Calculate indicators for the combined dataset
        logger.info("\nCalculating technical indicators...")
        combined_df = self.calculate_indicators(combined_df)
        
        # Save
        data_path.parent.mkdir(exist_ok=True)
        combined_df.to_csv(data_path, index=False)
        logger.info(f"\n✅ Data saved to {data_path}")
        logger.info(f"  File size: {data_path.stat().st_size / 1024 / 1024:.2f} MB")
        logger.info(f"  Total rows: {len(combined_df):,}")
        logger.info(f"  Latest date: {combined_df['date'].max().date()}")
        
        return True

def main():
    """Main execution"""
    logger.info("="*80)
    logger.info("DAILY DATA UPDATE")
    logger.info("="*80)
    
    updater = DailyDataUpdater()
    success = updater.update_training_data()
    
    if success:
        logger.info("\n" + "="*80)
        logger.info("✅ DATA UPDATE COMPLETE")
        logger.info("="*80)
        sys.exit(0)
    else:
        logger.error("\n" + "="*80)
        logger.error("❌ DATA UPDATE FAILED")
        logger.error("="*80)
        sys.exit(1)

if __name__ == '__main__':
    main()
