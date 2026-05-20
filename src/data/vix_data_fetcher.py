#!/usr/bin/env python3
"""
VIX Data Fetcher
Fetches real VIX data from Yahoo Finance or Alpha Vantage
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta

import pandas as pd
import requests

logger = logging.getLogger(__name__)

_YAHOO_VIX_URL = "https://query1.finance.yahoo.com/v8/finance/chart/%5EVIX"
_CACHE_TTL_SECONDS = 3600
_DEFAULT_VIX = 18.0


class VIXDataFetcher:
    """Fetches VIX data from public sources"""

    def __init__(self, source: str = "yahoo"):
        """
        Initialize VIX data fetcher

        Args:
            source: Preferred data source ('yahoo' or 'alphavantage').
                    Yahoo is always tried first; Alpha Vantage is the fallback.
        """
        self.source = source
        self.cache: dict = {}
        self.cache_time: datetime | None = None

    def get_current_vix(self) -> float:
        """
        Get current VIX level

        Returns:
            Current VIX value
        """
        # Check cache (refresh every hour)
        if (
            self.cache_time
            and (datetime.now() - self.cache_time).total_seconds() < _CACHE_TTL_SECONDS
        ):
            if "vix" in self.cache:
                return self.cache["vix"]

        vix: float | None = None

        # Always try Yahoo first; fall back to Alpha Vantage regardless of source setting
        try:
            vix = self._fetch_from_yahoo()
        except Exception as e:
            logger.warning(f"Yahoo VIX fetch failed, trying Alpha Vantage fallback: {e}")

        if vix is None:
            try:
                vix = self._fetch_from_alphavantage()
            except Exception as e:
                logger.error(f"Alpha Vantage VIX fetch also failed: {e}")

        if vix is None:
            logger.warning(f"All VIX sources failed; using default {_DEFAULT_VIX}")
            vix = _DEFAULT_VIX

        self.cache["vix"] = vix
        self.cache_time = datetime.now()
        logger.info(f"VIX fetched: {vix:.2f}")
        return vix

    def _fetch_from_yahoo(self) -> float:
        """
        Fetch VIX from Yahoo Finance with retry on rate-limit (429).
        """
        params = {"interval": "1d", "range": "1d"}
        headers = {"User-Agent": "Mozilla/5.0 (compatible; TradingBot/1.0)"}

        for attempt, backoff in enumerate([0, 2, 4], start=1):
            if backoff:
                time.sleep(backoff)
            try:
                response = requests.get(_YAHOO_VIX_URL, params=params, headers=headers, timeout=10)
                if response.status_code == 429:
                    logger.warning(f"Yahoo VIX rate-limited (attempt {attempt}/3)")
                    continue
                response.raise_for_status()

                data = response.json()
                if "chart" in data and "result" in data["chart"]:
                    result = data["chart"]["result"][0]
                    if "meta" in result and "regularMarketPrice" in result["meta"]:
                        return float(result["meta"]["regularMarketPrice"])

                raise ValueError("Could not parse VIX data from Yahoo")

            except requests.exceptions.HTTPError as e:
                if attempt < 3:
                    logger.warning(f"Yahoo VIX HTTP error on attempt {attempt}: {e}")
                    continue
                raise

        raise RuntimeError("Yahoo VIX fetch failed after 3 attempts (rate-limited)")

    def _fetch_from_alphavantage(self) -> float:
        """
        Fetch VIX from Alpha Vantage

        Requires ALPHA_VANTAGE_API_KEY environment variable
        """
        import os

        api_key = os.getenv("ALPHA_VANTAGE_API_KEY")
        if not api_key:
            raise ValueError("ALPHA_VANTAGE_API_KEY not set")

        try:
            url = "https://www.alphavantage.co/query"
            params = {"function": "GLOBAL_QUOTE", "symbol": "VIX", "apikey": api_key}

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()

            if "Global Quote" in data and "05. price" in data["Global Quote"]:
                vix = data["Global Quote"]["05. price"]
                return float(vix)

            raise ValueError("Could not parse VIX data from Alpha Vantage")

        except Exception as e:
            logger.error(f"Alpha Vantage VIX fetch failed: {e}")
            raise

    def get_vix_history(self, days: int = 30) -> pd.DataFrame:
        """
        Get historical VIX data

        Args:
            days: Number of days of history

        Returns:
            DataFrame with VIX history
        """
        try:
            if self.source == "yahoo":
                return self._fetch_history_yahoo(days)
            else:
                return self._fetch_history_alphavantage(days)
        except Exception as e:
            logger.error(f"Error fetching VIX history: {e}")
            # Return empty DataFrame
            return pd.DataFrame()

    def _fetch_history_yahoo(self, days: int) -> pd.DataFrame:
        """Fetch VIX history from Yahoo"""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)

            # Convert to Unix timestamps
            start_ts = int(start_date.timestamp())
            end_ts = int(end_date.timestamp())

            url = "https://query1.finance.yahoo.com/v8/finance/chart/%5EVIX"
            params = {"period1": start_ts, "period2": end_ts, "interval": "1d"}
            headers = {"User-Agent": "Mozilla/5.0 (compatible; TradingBot/1.0)"}
            response = requests.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()

            data = response.json()

            if "chart" in data and "result" in data["chart"]:
                result = data["chart"]["result"][0]
                timestamps = result["timestamp"]
                closes = result["indicators"]["quote"][0]["close"]

                df = pd.DataFrame({"date": pd.to_datetime(timestamps, unit="s"), "vix": closes})
                df = df.set_index("date")

                return df

            raise ValueError("Could not parse VIX history")

        except Exception as e:
            logger.error(f"Yahoo VIX history fetch failed: {e}")
            raise

    def _fetch_history_alphavantage(self, days: int) -> pd.DataFrame:
        """Fetch VIX history from Alpha Vantage"""
        import os

        api_key = os.getenv("ALPHA_VANTAGE_API_KEY")
        if not api_key:
            raise ValueError("ALPHA_VANTAGE_API_KEY not set")

        try:
            url = "https://www.alphavantage.co/query"
            params = {
                "function": "TIME_SERIES_DAILY",
                "symbol": "VIX",
                "apikey": api_key,
                "outputsize": "compact",  # Last 100 days
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()

            if "Time Series (Daily)" in data:
                ts_data = data["Time Series (Daily)"]

                dates = []
                vix_values = []

                for date_str, values in ts_data.items():
                    dates.append(pd.to_datetime(date_str))
                    vix_values.append(float(values["4. close"]))

                df = pd.DataFrame({"date": dates, "vix": vix_values})
                df = df.set_index("date").sort_index()

                # Filter to requested days
                cutoff = datetime.now() - timedelta(days=days)
                df = df[df.index >= cutoff]

                return df

            raise ValueError("Could not parse VIX history")

        except Exception as e:
            logger.error(f"Alpha Vantage VIX history fetch failed: {e}")
            raise
