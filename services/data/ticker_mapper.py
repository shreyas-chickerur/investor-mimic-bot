"""
Ticker Mapper - Convert between CUSIP, ticker symbols, and company names.
Uses OpenFIGI API and database lookups.
"""

import logging
import os
from typing import Dict, List, Optional, Set

import psycopg2
import requests
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)


class TickerMapper:
    """
    Map between CUSIP, ticker symbols, and company names.
    """

    def __init__(self, openfigi_api_key: Optional[str] = None, db_url: Optional[str] = None):
        """
        Initialize ticker mapper.

        Args:
            openfigi_api_key: OpenFIGI API key
            db_url: Database URL for local cache
        """
        self.openfigi_api_key = openfigi_api_key or os.getenv("OPENFIGI_API_KEY")
        self.db_url = db_url or os.getenv("DATABASE_URL", "").replace("postgresql+asyncpg://", "postgresql://")

        # In-memory cache
        self.cusip_to_ticker_cache: Dict[str, str] = {}
        self.ticker_to_cusip_cache: Dict[str, str] = {}

        # Load from database
        self._load_from_database()

    def _load_from_database(self):
        """Load ticker mappings from database."""
        if not self.db_url:
            return

        try:
            conn = psycopg2.connect(self.db_url)
            cur = conn.cursor(cursor_factory=RealDictCursor)

            # Load from securities table
            cur.execute(
                """
                SELECT cusip, ticker 
                FROM securities 
                WHERE ticker IS NOT NULL AND ticker != ''
                AND cusip IS NOT NULL AND cusip != ''
            """
            )

            rows = cur.fetchall()
            for row in rows:
                cusip = row["cusip"]
                ticker = row["ticker"]
                self.cusip_to_ticker_cache[cusip] = ticker
                self.ticker_to_cusip_cache[ticker] = cusip

            logger.info(f"Loaded {len(self.cusip_to_ticker_cache)} ticker mappings from database")

            cur.close()
            conn.close()

        except Exception as e:
            logger.warning(f"Could not load from database: {e}")

    def cusip_to_ticker(self, cusip: str) -> Optional[str]:
        """
        Convert CUSIP to ticker symbol.

        Args:
            cusip: CUSIP identifier

        Returns:
            Ticker symbol or None
        """
        # Check cache first
        if cusip in self.cusip_to_ticker_cache:
            return self.cusip_to_ticker_cache[cusip]

        # Try OpenFIGI API
        if self.openfigi_api_key:
            ticker = self._lookup_openfigi(cusip, "cusip")
            if ticker:
                self.cusip_to_ticker_cache[cusip] = ticker
                self.ticker_to_cusip_cache[ticker] = cusip
                return ticker

        return None

    def ticker_to_cusip(self, ticker: str) -> Optional[str]:
        """
        Convert ticker symbol to CUSIP.

        Args:
            ticker: Stock ticker

        Returns:
            CUSIP or None
        """
        # Check cache first
        if ticker in self.ticker_to_cusip_cache:
            return self.ticker_to_cusip_cache[ticker]

        # Try OpenFIGI API
        if self.openfigi_api_key:
            cusip = self._lookup_openfigi(ticker, "ticker")
            if cusip:
                self.ticker_to_cusip_cache[ticker] = cusip
                self.cusip_to_ticker_cache[cusip] = ticker
                return cusip

        return None

    def _lookup_openfigi(self, identifier: str, id_type: str) -> Optional[str]:
        """
        Lookup identifier using OpenFIGI API.

        Args:
            identifier: CUSIP or ticker
            id_type: 'cusip' or 'ticker'

        Returns:
            Mapped identifier or None
        """
        try:
            url = "https://api.openfigi.com/v3/mapping"

            headers = {"Content-Type": "application/json"}

            if self.openfigi_api_key:
                headers["X-OPENFIGI-APIKEY"] = self.openfigi_api_key

            if id_type == "cusip":
                payload = [{"idType": "ID_CUSIP", "idValue": identifier, "exchCode": "US"}]
            else:  # ticker
                payload = [{"idType": "TICKER", "idValue": identifier, "exchCode": "US"}]

            response = requests.post(url, json=payload, headers=headers, timeout=10)
            response.raise_for_status()

            data = response.json()

            if data and len(data) > 0 and "data" in data[0]:
                result = data[0]["data"][0]

                if id_type == "cusip":
                    return result.get("ticker")
                else:
                    return result.get("compositeFIGI")  # Can be used as CUSIP proxy

            return None

        except Exception as e:
            logger.debug(f"OpenFIGI lookup failed for {identifier}: {e}")
            return None

    def batch_cusip_to_ticker(self, cusips: List[str]) -> Dict[str, str]:
        """
        Convert multiple CUSIPs to tickers.

        Args:
            cusips: List of CUSIPs

        Returns:
            Dict mapping CUSIP to ticker
        """
        results = {}

        for cusip in cusips:
            ticker = self.cusip_to_ticker(cusip)
            if ticker:
                results[cusip] = ticker

        return results

    def batch_ticker_to_cusip(self, tickers: List[str]) -> Dict[str, str]:
        """
        Convert multiple tickers to CUSIPs.

        Args:
            tickers: List of tickers

        Returns:
            Dict mapping ticker to CUSIP
        """
        results = {}

        for ticker in tickers:
            cusip = self.ticker_to_cusip(ticker)
            if cusip:
                results[ticker] = cusip

        return results

    def normalize_symbols(self, symbols: List[str]) -> Set[str]:
        """
        Normalize a list of symbols (mix of CUSIPs and tickers) to tickers only.

        Args:
            symbols: List of CUSIPs and/or tickers

        Returns:
            Set of ticker symbols
        """
        tickers = set()

        for symbol in symbols:
            # If it looks like a CUSIP (9 alphanumeric), try to convert
            if len(symbol) == 9 and symbol.isalnum():
                ticker = self.cusip_to_ticker(symbol)
                if ticker:
                    tickers.add(ticker)
                else:
                    # Keep as-is if conversion fails
                    tickers.add(symbol)
            else:
                # Assume it's already a ticker
                tickers.add(symbol)

        return tickers

    def save_mapping(self, cusip: str, ticker: str):
        """
        Save a mapping to the database.

        Args:
            cusip: CUSIP identifier
            ticker: Ticker symbol
        """
        if not self.db_url:
            return

        try:
            conn = psycopg2.connect(self.db_url)
            cur = conn.cursor()

            # Update securities table
            cur.execute(
                """
                INSERT INTO securities (cusip, ticker)
                VALUES (%s, %s)
                ON CONFLICT (cusip) DO UPDATE SET ticker = EXCLUDED.ticker
            """,
                (cusip, ticker),
            )

            conn.commit()
            cur.close()
            conn.close()

            # Update cache
            self.cusip_to_ticker_cache[cusip] = ticker
            self.ticker_to_cusip_cache[ticker] = cusip

        except Exception as e:
            logger.error(f"Error saving mapping: {e}")
