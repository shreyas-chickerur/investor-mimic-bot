"""
Real-Time Price Data Fetcher - Get historical and current prices for technical analysis.
Uses Alpha Vantage and Alpaca APIs.
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pandas as pd
import requests
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

logger = logging.getLogger(__name__)


class PriceDataFetcher:
    """
    Fetch real-time and historical price data for stocks.
    """

    def __init__(
        self,
        alpaca_api_key: Optional[str] = None,
        alpaca_secret_key: Optional[str] = None,
        alpha_vantage_key: Optional[str] = None,
    ):
        """
        Initialize price data fetcher.

        Args:
            alpaca_api_key: Alpaca API key
            alpaca_secret_key: Alpaca secret key
            alpha_vantage_key: Alpha Vantage API key
        """
        self.alpaca_api_key = alpaca_api_key or os.getenv("ALPACA_API_KEY")
        self.alpaca_secret_key = alpaca_secret_key or os.getenv("ALPACA_SECRET_KEY")
        self.alpha_vantage_key = alpha_vantage_key or os.getenv("ALPHA_VANTAGE_API_KEY")

        if self.alpaca_api_key and self.alpaca_secret_key:
            self.alpaca_client = StockHistoricalDataClient(
                self.alpaca_api_key, self.alpaca_secret_key
            )
        else:
            self.alpaca_client = None
            logger.warning("Alpaca credentials not provided")

    def fetch_historical_prices_alpaca(
        self, symbol: str, days: int = 200
    ) -> Optional[pd.DataFrame]:
        """
        Fetch historical prices from Alpaca.

        Args:
            symbol: Stock ticker
            days: Number of days of history

        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume
        """
        if not self.alpaca_client:
            return None

        try:
            end = datetime.now()
            start = end - timedelta(days=days)

            request = StockBarsRequest(
                symbol_or_symbols=symbol, timeframe=TimeFrame.Day, start=start, end=end
            )

            bars = self.alpaca_client.get_stock_bars(request)

            if symbol not in bars:
                logger.warning(f"No data returned for {symbol}")
                return None

            df = bars[symbol].df

            # Rename columns to standard format
            df = df.rename(
                columns={
                    "open": "open",
                    "high": "high",
                    "low": "low",
                    "close": "close",
                    "volume": "volume",
                }
            )

            df = df.reset_index()
            df = df.rename(columns={"timestamp": "date"})

            logger.info(f"Fetched {len(df)} days of price data for {symbol}")
            return df

        except Exception as e:
            logger.error(f"Error fetching Alpaca data for {symbol}: {e}")
            return None

    def fetch_historical_prices_alpha_vantage(
        self, symbol: str, outputsize: str = "compact"
    ) -> Optional[pd.DataFrame]:
        """
        Fetch historical prices from Alpha Vantage.

        Args:
            symbol: Stock ticker
            outputsize: 'compact' (100 days) or 'full' (20+ years)

        Returns:
            DataFrame with columns: date, open, high, low, close, volume
        """
        if not self.alpha_vantage_key:
            return None

        try:
            url = "https://www.alphavantage.co/query"
            params = {
                "function": "TIME_SERIES_DAILY",
                "symbol": symbol,
                "outputsize": outputsize,
                "apikey": self.alpha_vantage_key,
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if "Time Series (Daily)" not in data:
                logger.warning(f"No time series data for {symbol}")
                return None

            time_series = data["Time Series (Daily)"]

            # Convert to DataFrame
            rows = []
            for date_str, values in time_series.items():
                rows.append(
                    {
                        "date": pd.to_datetime(date_str),
                        "open": float(values["1. open"]),
                        "high": float(values["2. high"]),
                        "low": float(values["3. low"]),
                        "close": float(values["4. close"]),
                        "volume": int(values["5. volume"]),
                    }
                )

            df = pd.DataFrame(rows)
            df = df.sort_values("date").reset_index(drop=True)

            logger.info(f"Fetched {len(df)} days of price data for {symbol}")
            return df

        except Exception as e:
            logger.error(f"Error fetching Alpha Vantage data for {symbol}: {e}")
            return None

    def fetch_historical_prices(self, symbol: str, days: int = 200) -> Optional[pd.DataFrame]:
        """
        Fetch historical prices using best available source.

        Args:
            symbol: Stock ticker
            days: Number of days of history

        Returns:
            DataFrame with price data
        """
        # Try Alpaca first (faster, no rate limits for basic usage)
        df = self.fetch_historical_prices_alpaca(symbol, days)

        if df is not None and not df.empty:
            return df

        # Fall back to Alpha Vantage
        outputsize = "full" if days > 100 else "compact"
        df = self.fetch_historical_prices_alpha_vantage(symbol, outputsize)

        if df is not None and not df.empty:
            # Limit to requested days
            df = df.tail(days)
            return df

        logger.warning(f"Could not fetch price data for {symbol}")
        return None

    def fetch_batch_prices(self, symbols: List[str], days: int = 200) -> Dict[str, pd.DataFrame]:
        """
        Fetch historical prices for multiple symbols.

        Args:
            symbols: List of stock tickers
            days: Number of days of history

        Returns:
            Dict mapping symbol to DataFrame
        """
        results = {}

        for symbol in symbols:
            df = self.fetch_historical_prices(symbol, days)
            if df is not None and not df.empty:
                results[symbol] = df

        logger.info(f"Fetched price data for {len(results)}/{len(symbols)} symbols")
        return results

    def get_current_price(self, symbol: str) -> Optional[float]:
        """
        Get current price for a symbol.

        Args:
            symbol: Stock ticker

        Returns:
            Current price or None
        """
        df = self.fetch_historical_prices(symbol, days=1)

        if df is not None and not df.empty:
            return float(df["close"].iloc[-1])

        return None

    def get_current_prices_batch(self, symbols: List[str]) -> Dict[str, float]:
        """
        Get current prices for multiple symbols.

        Args:
            symbols: List of stock tickers

        Returns:
            Dict mapping symbol to current price
        """
        prices = {}

        for symbol in symbols:
            price = self.get_current_price(symbol)
            if price is not None:
                prices[symbol] = price

        return prices
