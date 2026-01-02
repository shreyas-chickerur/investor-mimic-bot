#!/usr/bin/env python3
"""
Universe Provider
Manages symbol universe with support for static, CSV, and dynamic sources
"""
import os
import logging
from typing import List
from pathlib import Path
import pandas as pd

logger = logging.getLogger(__name__)


class UniverseProvider:
    """Provides trading universe from multiple sources"""
    
    DEFAULT_UNIVERSE = [
        'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA', 'NVDA', 'AMD',
        'NFLX', 'DIS', 'PYPL', 'INTC', 'CSCO', 'ADBE', 'CRM', 'ORCL',
        'QCOM', 'TXN', 'AVGO', 'COST', 'SBUX', 'MCD', 'NKE', 'WMT',
        'HD', 'LOW', 'TGT', 'CVS', 'UNH', 'JNJ', 'PFE', 'ABBV',
        'MRK', 'TMO', 'DHR', 'MDT'
    ]
    
    def __init__(self, mode: str = None):
        """
        Initialize universe provider
        
        Args:
            mode: 'static', 'csv', or 'dynamic' (default: from env var)
        """
        self.mode = mode or os.getenv('UNIVERSE_MODE', 'static')
        self.csv_path = os.getenv('UNIVERSE_CSV_PATH', 'config/universe.csv')
        
        logger.info(f"Universe Provider initialized: mode={self.mode}")
    
    def get_universe(self, asof_date: str = None) -> List[str]:
        """
        Get trading universe for a given date
        
        Args:
            asof_date: Date string (YYYY-MM-DD), unused for static/csv modes
            
        Returns:
            List of ticker symbols
        """
        if self.mode == 'static':
            return self._get_static_universe()
        elif self.mode == 'csv':
            return self._get_csv_universe()
        elif self.mode == 'dynamic':
            return self._get_dynamic_universe(asof_date)
        else:
            logger.warning(f"Unknown universe mode '{self.mode}', using static")
            return self._get_static_universe()
    
    def _get_static_universe(self) -> List[str]:
        """Get static universe"""
        logger.info(f"Using static universe: {len(self.DEFAULT_UNIVERSE)} symbols")
        return self.DEFAULT_UNIVERSE.copy()
    
    def _get_csv_universe(self) -> List[str]:
        """Load universe from CSV file"""
        csv_file = Path(self.csv_path)
        
        if not csv_file.exists():
            logger.warning(f"Universe CSV not found: {csv_file}, using static universe")
            return self._get_static_universe()
        
        try:
            df = pd.read_csv(csv_file)
            
            if 'symbol' in df.columns:
                symbols = df['symbol'].dropna().unique().tolist()
            elif 'ticker' in df.columns:
                symbols = df['ticker'].dropna().unique().tolist()
            else:
                symbols = df.iloc[:, 0].dropna().unique().tolist()
            
            logger.info(f"Loaded {len(symbols)} symbols from CSV: {csv_file}")
            return symbols
            
        except Exception as e:
            logger.error(f"Error loading CSV universe: {e}")
            return self._get_static_universe()
    
    def _get_dynamic_universe(self, asof_date: str = None) -> List[str]:
        """
        Get dynamic universe via screener (future implementation)
        
        For now, returns static universe. Future: integrate with screener API
        """
        logger.warning("Dynamic universe not yet implemented, using static")
        return self._get_static_universe()
    
    def validate_universe(self, symbols: List[str]) -> List[str]:
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
            
            if 1 <= len(symbol) <= 5 and symbol.isalnum():
                valid_symbols.append(symbol)
            else:
                logger.warning(f"Invalid symbol filtered out: {symbol}")
        
        logger.info(f"Validated {len(valid_symbols)}/{len(symbols)} symbols")
        return valid_symbols
