#!/usr/bin/env python3
"""
Alpha Vantage Data Fetcher
Fetches historical stock data using Alpha Vantage API
"""
from __future__ import annotations

import os
import time
import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class AlphaVantageFetcher:
    """Fetches stock data from Alpha Vantage API"""
    
    BASE_URL = "https://www.alphavantage.co/query"
    
    def __init__(self, api_key: Optional[str] = None, premium: bool = True):
        """
        Initialize Alpha Vantage fetcher
        
        Args:
            api_key: Alpha Vantage API key (defaults to env var)
            premium: Whether using premium API (higher rate limits)
        """
        self.api_key = api_key or os.getenv('ALPHA_VANTAGE_API_KEY')
        if not self.api_key:
            raise ValueError("Alpha Vantage API key not found")
        
        self.premium = premium
        # Premium: 75 calls/min, 1200 calls/day
        # Free: 5 calls/min, 500 calls/day
        self.calls_per_minute = 75 if premium else 5
        self.delay_seconds = 60.0 / self.calls_per_minute
        
        self.last_call_time = 0
        self.call_count = 0
    
    def _rate_limit(self):
        """Enforce rate limiting"""
        elapsed = time.time() - self.last_call_time
        if elapsed < self.delay_seconds:
            sleep_time = self.delay_seconds - elapsed
            time.sleep(sleep_time)
        self.last_call_time = time.time()
        self.call_count += 1
    
    def fetch_daily_data(self, symbol: str, outputsize: str = 'full') -> Optional[pd.DataFrame]:
        """
        Fetch daily OHLCV data for a symbol
        
        Args:
            symbol: Stock symbol
            outputsize: 'compact' (100 days) or 'full' (20+ years)
        
        Returns:
            DataFrame with columns: date, open, high, low, close, volume
        """
        self._rate_limit()
        
        params = {
            'function': 'TIME_SERIES_DAILY_ADJUSTED',
            'symbol': symbol,
            'outputsize': outputsize,
            'apikey': self.api_key
        }
        
        try:
            response = requests.get(self.BASE_URL, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            # Check for errors
            if 'Error Message' in data:
                logger.error(f"Alpha Vantage error for {symbol}: {data['Error Message']}")
                return None
            
            if 'Note' in data:
                logger.warning(f"Alpha Vantage rate limit note: {data['Note']}")
                time.sleep(60)  # Wait a minute if rate limited
                return None
            
            if 'Time Series (Daily)' not in data:
                logger.error(f"No time series data for {symbol}: {data}")
                return None
            
            # Parse time series
            time_series = data['Time Series (Daily)']
            
            rows = []
            for date_str, values in time_series.items():
                rows.append({
                    'date': pd.to_datetime(date_str),
                    'open': float(values['1. open']),
                    'high': float(values['2. high']),
                    'low': float(values['3. low']),
                    'close': float(values['4. close']),
                    'volume': int(values['6. volume']),
                    'symbol': symbol
                })
            
            df = pd.DataFrame(rows)
            df = df.sort_values('date').reset_index(drop=True)
            
            logger.info(f"Fetched {len(df)} days for {symbol} (latest: {df['date'].max().date()})")
            return df
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed for {symbol}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error fetching {symbol}: {e}")
            return None
    
    def fetch_multiple_symbols(self, symbols: List[str], outputsize: str = 'full') -> pd.DataFrame:
        """
        Fetch data for multiple symbols
        
        Args:
            symbols: List of stock symbols
            outputsize: 'compact' or 'full'
        
        Returns:
            Combined DataFrame with all symbols
        """
        all_data = []
        total = len(symbols)
        
        print(f"\nFetching {total} symbols from Alpha Vantage (Premium API)")
        print(f"Rate limit: {self.calls_per_minute} calls/min (~{self.delay_seconds:.1f}s per call)")
        print(f"Estimated time: {(total * self.delay_seconds / 60):.1f} minutes\n")
        
        for i, symbol in enumerate(symbols, 1):
            print(f"[{i}/{total}] Fetching {symbol}...", end=' ', flush=True)
            
            df = self.fetch_daily_data(symbol, outputsize)
            
            if df is not None and len(df) > 0:
                all_data.append(df)
                print(f"✓ {len(df)} days")
            else:
                print(f"✗ Failed")
            
            # Progress update every 10 symbols
            if i % 10 == 0:
                elapsed_min = (self.call_count * self.delay_seconds) / 60
                remaining = total - i
                eta_min = (remaining * self.delay_seconds) / 60
                print(f"  Progress: {i}/{total} ({i/total*100:.1f}%) | Elapsed: {elapsed_min:.1f}m | ETA: {eta_min:.1f}m")
        
        if not all_data:
            raise ValueError("No data fetched for any symbols")
        
        combined = pd.concat(all_data, ignore_index=True)
        print(f"\n✅ Fetched {len(combined)} total rows for {len(all_data)} symbols")
        print(f"Date range: {combined['date'].min().date()} to {combined['date'].max().date()}")
        
        return combined
    
    def fetch_recent_data(self, symbols: List[str], days: int = 30) -> pd.DataFrame:
        """
        Fetch only recent data (last N days) using compact output
        
        Args:
            symbols: List of stock symbols
            days: Number of recent days to fetch (max 100 for compact)
        
        Returns:
            DataFrame with recent data
        """
        if days > 100:
            logger.warning(f"Requested {days} days but compact output limited to 100, using full")
            outputsize = 'full'
        else:
            outputsize = 'compact'
        
        df = self.fetch_multiple_symbols(symbols, outputsize=outputsize)
        
        # Filter to recent days
        cutoff_date = datetime.now() - timedelta(days=days)
        df = df[df['date'] >= cutoff_date].copy()
        
        return df
    
    def update_existing_data(self, existing_csv: str, symbols: List[str]) -> pd.DataFrame:
        """
        Update existing CSV with only new data since last date
        
        Args:
            existing_csv: Path to existing training_data.csv
            symbols: List of symbols to update
        
        Returns:
            Updated DataFrame
        """
        # Load existing data
        existing_df = pd.read_csv(existing_csv, index_col=0, parse_dates=True)
        existing_df = existing_df.reset_index()
        existing_df = existing_df.rename(columns={'index': 'date', existing_df.index.name: 'date'})
        
        # Find latest date in existing data
        latest_date = existing_df['date'].max()
        days_old = (datetime.now() - latest_date).days
        
        print(f"Existing data latest date: {latest_date.date()} ({days_old} days old)")
        
        if days_old <= 1:
            print("Data is current, no update needed")
            return existing_df
        
        # Fetch recent data (use compact for efficiency)
        print(f"Fetching last {min(days_old + 5, 100)} days...")
        new_df = self.fetch_recent_data(symbols, days=min(days_old + 5, 100))
        
        # Filter to only dates after existing data
        new_df = new_df[new_df['date'] > latest_date].copy()
        
        if len(new_df) == 0:
            print("No new data available")
            return existing_df
        
        print(f"Found {len(new_df)} new rows")
        
        # Combine old and new
        combined = pd.concat([existing_df, new_df], ignore_index=True)
        combined = combined.sort_values(['symbol', 'date']).reset_index(drop=True)
        
        # Remove duplicates
        combined = combined.drop_duplicates(subset=['symbol', 'date'], keep='last')
        
        print(f"Combined dataset: {len(combined)} rows")
        print(f"Date range: {combined['date'].min().date()} to {combined['date'].max().date()}")
        
        return combined


    def fetch_earnings_calendar(self, symbols: Optional[List[str]] = None,
                                horizon: str = '3month',
                                save_path: Optional[str] = None) -> pd.DataFrame:
        """Fetch upcoming earnings dates from Alpha Vantage EARNINGS_CALENDAR endpoint.

        This is a single CSV download (one API call), not per-symbol.

        Args:
            symbols: Filter to only these symbols. None = return all.
            horizon: '3month' (default) or '6month' or '12month'.
            save_path: If set, save filtered DataFrame to this CSV path.

        Returns:
            DataFrame with columns: symbol, name, reportDate, fiscalDateEnding,
            estimate, currency.  reportDate is a date string 'YYYY-MM-DD'.
        """
        self._rate_limit()
        params = {
            'function': 'EARNINGS_CALENDAR',
            'horizon': horizon,
            'apikey': self.api_key,
        }
        try:
            resp = requests.get(self.BASE_URL, params=params, timeout=30, stream=True)
            resp.raise_for_status()

            # Response is a CSV stream
            from io import StringIO
            df = pd.read_csv(StringIO(resp.text))
            df.columns = [c.strip() for c in df.columns]

            # Normalise the reportDate column name (AV sometimes ships 'reportDate')
            if 'reportDate' not in df.columns and 'report_date' in df.columns:
                df = df.rename(columns={'report_date': 'reportDate'})

            if 'symbol' not in df.columns or 'reportDate' not in df.columns:
                logger.error("Unexpected EARNINGS_CALENDAR schema: %s", list(df.columns))
                return pd.DataFrame()

            df['reportDate'] = pd.to_datetime(df['reportDate'], errors='coerce')
            df = df.dropna(subset=['reportDate'])

            if symbols:
                df = df[df['symbol'].isin(symbols)].copy()

            logger.info("Earnings calendar: %d upcoming events for %d symbols",
                        len(df), df['symbol'].nunique())

            if save_path:
                df.to_csv(save_path, index=False)
                logger.info("Saved earnings calendar to %s", save_path)

            return df

        except Exception as exc:
            logger.error("Failed to fetch earnings calendar: %s", exc)
            return pd.DataFrame()


def test_fetcher():
    """Test the Alpha Vantage fetcher"""
    fetcher = AlphaVantageFetcher(premium=True)
    
    # Test single symbol
    print("Testing single symbol fetch...")
    df = fetcher.fetch_daily_data('AAPL', outputsize='compact')
    
    if df is not None:
        print(f"✓ Fetched {len(df)} days for AAPL")
        print(df.head())
        print(df.tail())
    else:
        print("✗ Failed to fetch AAPL")


if __name__ == '__main__':
    test_fetcher()
