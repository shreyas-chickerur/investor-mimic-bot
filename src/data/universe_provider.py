#!/usr/bin/env python3
"""
Universe Provider
Manages symbol universe with support for static, CSV, and dynamic sources
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


class UniverseProvider:
    """Provides trading universe from multiple sources"""

    DEFAULT_UNIVERSE = [
        # Tech / Growth
        "AAPL",
        "MSFT",
        "GOOGL",
        "AMZN",
        "META",
        "TSLA",
        "NVDA",
        "NFLX",
        "ADBE",
        "AVGO",
        "CRM",
        "AMD",
        # Consumer / Retail
        "COST",
        "MCD",
        "NKE",
        "WMT",
        "HD",
        "DIS",
        # Healthcare
        "JNJ",
        "ABBV",
        "MRK",
        "TMO",
        "DHR",
        "ABT",
        "UNH",
        "LLY",
        # Financials
        "MA",
        "JPM",
        "V",
        # Consumer Staples
        "KO",
        "PEP",
        "PG",
        # Energy / Telecom
        "XOM",
        "CVX",
        "VZ",
        # IT Services
        "ACN",
        # --- 2026-06 universe expansion: liquid S&P large caps. 43 mega-caps
        # gave the strategies too few opportunities (4 of 8 emitted zero raw
        # signals on a typical day); breadth feeds signal frequency and
        # deployment. New symbols are backfilled automatically (capped per
        # run) by update_daily_data.py.
        # Tech / Semis / Software
        "ORCL",
        "CSCO",
        "INTC",
        "QCOM",
        "TXN",
        "IBM",
        "NOW",
        "INTU",
        "AMAT",
        "MU",
        "LRCX",
        "KLAC",
        "PANW",
        "ANET",
        "ADI",
        # Financials
        "BAC",
        "WFC",
        "GS",
        "MS",
        "C",
        "SCHW",
        "BLK",
        "AXP",
        "SPGI",
        "COF",
        # Healthcare
        "PFE",
        "BMY",
        "AMGN",
        "GILD",
        "CVS",
        "CI",
        "ISRG",
        "SYK",
        "BSX",
        "MDT",
        "REGN",
        "VRTX",
        "ZTS",
        # Consumer discretionary
        "SBUX",
        "TGT",
        "LOW",
        "TJX",
        "BKNG",
        "CMG",
        "ORLY",
        "ROST",
        "GM",
        "UBER",
        # Consumer staples
        "CL",
        "KMB",
        "MDLZ",
        "MO",
        "PM",
        "GIS",
        # Industrials
        "CAT",
        "DE",
        "BA",
        "GE",
        "HON",
        "UNP",
        "UPS",
        "FDX",
        "LMT",
        "RTX",
        "ETN",
        "EMR",
        "CSX",
        "WM",
        # Energy / Materials / Utilities
        "COP",
        "SLB",
        "EOG",
        "MPC",
        "PSX",
        "LIN",
        "APD",
        "SHW",
        "FCX",
        "NEE",
        "DUK",
        "SO",
        # Communication / Real estate
        "T",
        "TMUS",
        "CMCSA",
        "PLD",
        "AMT",
        # Sector ETFs (used for relative-strength factor computation; excluded from trading)
        "SPY",
        "QQQ",
        "XLK",
        "XLF",
        "XLE",
        "XLV",
        "XLP",
        "XLY",
    ]

    # Symbols used only for factor benchmarking — never traded as positions
    BENCHMARK_SYMBOLS = {"SPY", "QQQ", "XLK", "XLF", "XLE", "XLV", "XLP", "XLY"}

    def __init__(self, mode: str | None = None):
        """
        Initialize universe provider

        Args:
            mode: 'static', 'csv', or 'dynamic' (default: from env var)
        """
        self.mode = mode or os.getenv("UNIVERSE_MODE", "static")
        self.csv_path = os.getenv("UNIVERSE_CSV_PATH", "config/universe.csv")

        logger.info(f"Universe Provider initialized: mode={self.mode}")

    def get_universe(self, asof_date: str | None = None) -> list[str]:
        """
        Get trading universe for a given date

        Args:
            asof_date: Date string (YYYY-MM-DD), unused for static/csv modes

        Returns:
            List of ticker symbols
        """
        if self.mode == "static":
            return self._get_static_universe()
        elif self.mode == "csv":
            return self._get_csv_universe()
        elif self.mode == "dynamic":
            return self._get_dynamic_universe(asof_date)
        else:
            logger.warning(f"Unknown universe mode '{self.mode}', using static")
            return self._get_static_universe()

    def _get_static_universe(self) -> list[str]:
        """Get static universe"""
        logger.info(f"Using static universe: {len(self.DEFAULT_UNIVERSE)} symbols")
        return self.DEFAULT_UNIVERSE.copy()

    def _get_csv_universe(self) -> list[str]:
        """Load universe from CSV file"""
        csv_file = Path(self.csv_path)

        if not csv_file.exists():
            logger.warning(f"Universe CSV not found: {csv_file}, using static universe")
            return self._get_static_universe()

        try:
            df = pd.read_csv(csv_file)

            if "symbol" in df.columns:
                symbols = df["symbol"].dropna().unique().tolist()
            elif "ticker" in df.columns:
                symbols = df["ticker"].dropna().unique().tolist()
            else:
                symbols = df.iloc[:, 0].dropna().unique().tolist()

            logger.info(f"Loaded {len(symbols)} symbols from CSV: {csv_file}")
            return [str(s) for s in symbols]

        except Exception as e:
            logger.error(f"Error loading CSV universe: {e}")
            return self._get_static_universe()

    def _get_dynamic_universe(self, asof_date: str | None = None) -> list[str]:
        """
        Get dynamic universe via screener (future implementation)

        For now, returns static universe. Future: integrate with screener API
        """
        logger.warning("Dynamic universe not yet implemented, using static")
        return self._get_static_universe()

    def validate_universe(self, symbols: list[str]) -> list[str]:
        """
        Validate and clean symbol list

        Args:
            symbols: List of symbols to validate

        Returns:
            Cleaned list of valid symbols
        """
        valid_symbols = []

        for symbol in symbols:
            if not symbol or not isinstance(symbol, str):
                continue

            symbol = symbol.strip().upper()

            if 1 <= len(symbol) <= 6 and all(c.isalnum() or c in ".-" for c in symbol):
                valid_symbols.append(symbol)
            else:
                logger.warning(f"Invalid symbol filtered out: {symbol}")

        logger.info(f"Validated {len(valid_symbols)}/{len(symbols)} symbols")
        return valid_symbols
