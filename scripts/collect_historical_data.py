#!/usr/bin/env python3
"""
Historical Data Collection Script

Collects all necessary historical data for backtesting:
1. Stock prices (2010-2024)
2. 13F filings from database
3. Market data (SPY, VIX)
4. Volume data
"""

import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

import time
from typing import Dict, List, Optional

import pandas as pd
import psycopg2
import requests
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame


class HistoricalDataCollector:
    """
    Collects historical data for backtesting.
    """

    def __init__(self):
        """Initialize data collector."""
        self.alpha_vantage_key = os.getenv("ALPHA_VANTAGE_API_KEY")
        self.db_url = os.getenv("DATABASE_URL", "postgresql://postgres@localhost:5432/investorbot")

        # Alpaca client
        alpaca_key = os.getenv("ALPACA_API_KEY")
        alpaca_secret = os.getenv("ALPACA_SECRET_KEY")
        if alpaca_key and alpaca_secret:
            self.alpaca_client = StockHistoricalDataClient(alpaca_key, alpaca_secret)
        else:
            self.alpaca_client = None

        self.data_dir = Path("historical_data")
        self.data_dir.mkdir(exist_ok=True)

    def get_stock_universe(self) -> List[str]:
        """
        Get list of stocks to backtest.
        Uses stocks from 13F database.
        """
        print("Getting stock universe from 13F database...")

        try:
            conn = psycopg2.connect(self.db_url)
            query = """
                SELECT DISTINCT ticker
                FROM holdings
                WHERE days_old <= 365
                ORDER BY ticker
                LIMIT 100
            """
            df = pd.read_sql(query, conn)
            conn.close()

            symbols = df["ticker"].tolist()
            print(f"  ✓ Found {len(symbols)} symbols from 13F filings")
            return symbols

        except Exception as e:
            print(f"  ⚠ Database error: {e}")
            print("  Using default stock universe...")
            # Default universe of liquid large caps
            return [
                "AAPL",
                "MSFT",
                "GOOGL",
                "AMZN",
                "NVDA",
                "META",
                "TSLA",
                "BRK.B",
                "V",
                "JNJ",
                "WMT",
                "JPM",
                "MA",
                "PG",
                "UNH",
                "HD",
                "DIS",
                "PYPL",
                "NFLX",
                "ADBE",
                "CRM",
                "INTC",
                "CSCO",
                "PFE",
                "ABT",
                "TMO",
                "COST",
                "NKE",
                "MRK",
                "DHR",
                "AVGO",
                "TXN",
                "QCOM",
                "NEE",
                "LLY",
                "MDT",
            ]

    def fetch_alpaca_data(
        self, symbols: List[str], start_date: datetime, end_date: datetime
    ) -> Dict[str, pd.DataFrame]:
        """
        Fetch historical data from Alpaca.

        Args:
            symbols: List of stock symbols
            start_date: Start date
            end_date: End date

        Returns:
            Dictionary of symbol -> DataFrame
        """
        if not self.alpaca_client:
            print("  ⚠ Alpaca client not configured")
            return {}

        print(f"Fetching data from Alpaca for {len(symbols)} symbols...")

        price_data = {}

        # Fetch in batches to avoid rate limits
        batch_size = 10
        for i in range(0, len(symbols), batch_size):
            batch = symbols[i : i + batch_size]

            try:
                request = StockBarsRequest(
                    symbol_or_symbols=batch, timeframe=TimeFrame.Day, start=start_date, end=end_date
                )

                bars = self.alpaca_client.get_stock_bars(request)

                for symbol in batch:
                    if symbol in bars:
                        df = bars[symbol].df
                        price_data[symbol] = df
                        print(f"  ✓ {symbol}: {len(df)} days")

                time.sleep(0.5)  # Rate limiting

            except Exception as e:
                print(f"  ✗ Error fetching batch: {e}")
                continue

        return price_data

    def fetch_alpha_vantage_data(self, symbol: str, outputsize: str = "full") -> Optional[pd.DataFrame]:
        """
        Fetch historical data from Alpha Vantage.

        Args:
            symbol: Stock symbol
            outputsize: 'compact' (100 days) or 'full' (20+ years)

        Returns:
            DataFrame with OHLCV data
        """
        if not self.alpha_vantage_key:
            return None

        url = "https://www.alphavantage.co/query"
        params = {
            "function": "TIME_SERIES_DAILY_ADJUSTED",
            "symbol": symbol,
            "outputsize": outputsize,
            "apikey": self.alpha_vantage_key,
        }

        try:
            response = requests.get(url, params=params, timeout=30)
            data = response.json()

            if "Time Series (Daily)" not in data:
                print(f"  ✗ {symbol}: No data")
                return None

            # Convert to DataFrame
            time_series = data["Time Series (Daily)"]
            df = pd.DataFrame.from_dict(time_series, orient="index")
            df.index = pd.to_datetime(df.index)
            df = df.sort_index()

            # Rename columns
            df.columns = [
                "open",
                "high",
                "low",
                "close",
                "adjusted_close",
                "volume",
                "dividend",
                "split",
            ]
            df = df.astype(float)

            return df[["open", "high", "low", "close", "volume"]]

        except Exception as e:
            print(f"  ✗ {symbol}: {e}")
            return None

    def collect_price_data(
        self, symbols: List[str], start_date: datetime, end_date: datetime
    ) -> Dict[str, pd.DataFrame]:
        """
        Collect price data from available sources.

        Args:
            symbols: List of symbols
            start_date: Start date
            end_date: End date

        Returns:
            Dictionary of symbol -> DataFrame
        """
        print("\n" + "=" * 80)
        print("COLLECTING PRICE DATA")
        print("=" * 80)

        price_data = {}

        # Try Alpaca first (faster for bulk data)
        if self.alpaca_client:
            price_data = self.fetch_alpaca_data(symbols, start_date, end_date)

        # Fill in missing symbols with Alpha Vantage
        missing_symbols = [s for s in symbols if s not in price_data]

        if missing_symbols and self.alpha_vantage_key:
            print(f"\nFetching {len(missing_symbols)} missing symbols from Alpha Vantage...")

            for symbol in missing_symbols[:20]:  # Limit to 20 due to API limits
                df = self.fetch_alpha_vantage_data(symbol)
                if df is not None:
                    # Filter to date range
                    df = df[(df.index >= start_date) & (df.index <= end_date)]
                    price_data[symbol] = df
                    print(f"  ✓ {symbol}: {len(df)} days")

                time.sleep(12)  # Alpha Vantage rate limit: 5 calls/min

        # Save to disk
        print(f"\nSaving price data...")
        for symbol, df in price_data.items():
            filepath = self.data_dir / f"{symbol}_prices.csv"
            df.to_csv(filepath)

        print(f"  ✓ Saved {len(price_data)} symbols to {self.data_dir}")

        return price_data

    def collect_market_data(self, start_date: datetime, end_date: datetime) -> Dict[str, pd.DataFrame]:
        """
        Collect market benchmark data (SPY, VIX).

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            Dictionary with 'spy' and 'vix' DataFrames
        """
        print("\n" + "=" * 80)
        print("COLLECTING MARKET DATA")
        print("=" * 80)

        market_data = {}

        # SPY data
        print("Fetching SPY data...")
        if self.alpaca_client:
            try:
                request = StockBarsRequest(
                    symbol_or_symbols=["SPY"],
                    timeframe=TimeFrame.Day,
                    start=start_date,
                    end=end_date,
                )
                bars = self.alpaca_client.get_stock_bars(request)
                market_data["spy"] = bars["SPY"].df
                print(f"  ✓ SPY: {len(market_data['spy'])} days")
            except Exception as e:
                print(f"  ✗ Error: {e}")

        # VIX data (if available)
        print("Fetching VIX data...")
        if self.alpha_vantage_key:
            vix_df = self.fetch_alpha_vantage_data("^VIX")
            if vix_df is not None:
                vix_df = vix_df[(vix_df.index >= start_date) & (vix_df.index <= end_date)]
                market_data["vix"] = vix_df
                print(f"  ✓ VIX: {len(vix_df)} days")

        # Save
        for name, df in market_data.items():
            filepath = self.data_dir / f"{name}_data.csv"
            df.to_csv(filepath)
            print(f"  ✓ Saved {name} data")

        return market_data

    def collect_13f_data(self) -> pd.DataFrame:
        """
        Collect historical 13F data from database.

        Returns:
            DataFrame with 13F holdings over time
        """
        print("\n" + "=" * 80)
        print("COLLECTING 13F DATA")
        print("=" * 80)

        try:
            conn = psycopg2.connect(self.db_url)

            query = """
                SELECT
                    ticker,
                    security_name,
                    portfolio_weight,
                    days_old,
                    investor_name,
                    filing_date
                FROM holdings
                ORDER BY filing_date DESC
            """

            df = pd.read_sql(query, conn)
            conn.close()

            print(f"  ✓ Loaded {len(df)} 13F holdings")

            # Save
            filepath = self.data_dir / "13f_holdings.csv"
            df.to_csv(filepath, index=False)
            print(f"  ✓ Saved to {filepath}")

            return df

        except Exception as e:
            print(f"  ✗ Database error: {e}")
            return pd.DataFrame()

    def generate_summary_report(
        self,
        price_data: Dict[str, pd.DataFrame],
        market_data: Dict[str, pd.DataFrame],
        holdings_data: pd.DataFrame,
    ):
        """Generate summary report of collected data."""

        print("\n" + "=" * 80)
        print("DATA COLLECTION SUMMARY")
        print("=" * 80)

        print(f"\nPRICE DATA:")
        print(f"  Symbols collected: {len(price_data)}")
        if price_data:
            total_days = sum(len(df) for df in price_data.values())
            avg_days = total_days / len(price_data)
            print(f"  Average days per symbol: {avg_days:.0f}")
            print(f"  Total data points: {total_days:,}")

        print(f"\nMARKET DATA:")
        for name, df in market_data.items():
            print(f"  {name.upper()}: {len(df)} days")

        print(f"\n13F DATA:")
        print(f"  Total holdings: {len(holdings_data)}")
        if not holdings_data.empty:
            print(f"  Unique symbols: {holdings_data['ticker'].nunique()}")
            print(f"  Unique investors: {holdings_data['investor_name'].nunique()}")

        print(f"\nDATA LOCATION:")
        print(f"  {self.data_dir.absolute()}")

        print("\n" + "=" * 80)
        print("✅ DATA COLLECTION COMPLETE!")
        print("=" * 80)


def main():
    """Main execution."""
    print("=" * 80)
    print("HISTORICAL DATA COLLECTION FOR BACKTESTING")
    print("Period: 2010-2024 (Excluding COVID: March-June 2020)")
    print("=" * 80)

    # Initialize collector
    collector = HistoricalDataCollector()

    # Define date range
    start_date = datetime(2010, 1, 1)
    end_date = datetime(2024, 12, 31)

    print(f"\nDate Range: {start_date.date()} to {end_date.date()}")
    print(f"Duration: {(end_date - start_date).days / 365.25:.1f} years")

    # Get stock universe
    symbols = collector.get_stock_universe()

    # Collect price data
    price_data = collector.collect_price_data(symbols, start_date, end_date)

    # Collect market data
    market_data = collector.collect_market_data(start_date, end_date)

    # Collect 13F data
    holdings_data = collector.collect_13f_data()

    # Generate summary
    collector.generate_summary_report(price_data, market_data, holdings_data)

    print("\nNext steps:")
    print("  1. Review collected data in historical_data/")
    print("  2. Run: python3 backtesting/run_comprehensive_backtest.py")
    print("  3. Analyze results and optimize weights")


if __name__ == "__main__":
    main()
