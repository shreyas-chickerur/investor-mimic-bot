#!/usr/bin/env python3
"""
Strategy Correlation Filter
Prevents over-concentration in correlated positions
"""
import pandas as pd
import numpy as np
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)

class CorrelationFilter:
    """Filters trades based on correlation with existing positions"""
    
    def __init__(self, 
                 correlation_window: int = 60,  # 60-day rolling correlation
                 short_window: int = 20,  # Short-term override window
                 max_correlation: float = 0.7):  # Reject if correlation > 0.7
        """
        Initialize correlation filter
        
        Args:
            correlation_window: Days to use for correlation calculation
            short_window: Short-term window for regime shift detection
            max_correlation: Maximum allowed correlation with existing positions
        """
        self.correlation_window = correlation_window
        self.short_window = short_window
        self.max_correlation = max_correlation
        self.price_history = {}  # {symbol: [prices]}
        
        logger.info(f"Correlation Filter: window={correlation_window}d, "
                   f"short={short_window}d, max_corr={max_correlation}")
    
    def update_price_history(self, symbol: str, prices: pd.Series):
        """Update price history for a symbol"""
        self.price_history[symbol] = prices.tail(self.correlation_window).values
    
    def calculate_correlation(self, symbol1: str, symbol2: str) -> float:
        """
        Calculate correlation between two symbols
        
        Returns:
            Correlation coefficient (-1 to 1)
        """
        if symbol1 not in self.price_history or symbol2 not in self.price_history:
            return 0.0
        
        prices1 = self.price_history[symbol1]
        prices2 = self.price_history[symbol2]
        
        # Need same length
        min_len = min(len(prices1), len(prices2))
        if min_len < 20:  # Need at least 20 days
            return 0.0
        
        prices1 = prices1[-min_len:]
        prices2 = prices2[-min_len:]
        
        # Calculate returns
        returns1 = np.diff(prices1) / prices1[:-1]
        returns2 = np.diff(prices2) / prices2[:-1]
        
        # Calculate correlation
        if len(returns1) > 0 and len(returns2) > 0:
            corr = np.corrcoef(returns1, returns2)[0, 1]
            return corr if not np.isnan(corr) else 0.0
        
        return 0.0
    
    def calculate_correlation_multi_window(self, symbol1: str, symbol2: str) -> tuple:
        """
        Calculate correlation on both long and short windows
        
        Returns:
            (long_window_corr, short_window_corr)
        """
        if symbol1 not in self.price_history or symbol2 not in self.price_history:
            return 0.0, 0.0
        
        prices1 = self.price_history[symbol1]
        prices2 = self.price_history[symbol2]
        
        # Long window correlation
        min_len = min(len(prices1), len(prices2))
        if min_len >= self.correlation_window:
            p1_long = prices1[-self.correlation_window:]
            p2_long = prices2[-self.correlation_window:]
            returns1_long = np.diff(p1_long) / p1_long[:-1]
            returns2_long = np.diff(p2_long) / p2_long[:-1]
            long_corr = np.corrcoef(returns1_long, returns2_long)[0, 1] if len(returns1_long) > 0 else 0.0
            long_corr = long_corr if not np.isnan(long_corr) else 0.0
        else:
            long_corr = 0.0
        
        # Short window correlation (regime shift detection)
        if min_len >= self.short_window:
            p1_short = prices1[-self.short_window:]
            p2_short = prices2[-self.short_window:]
            returns1_short = np.diff(p1_short) / p1_short[:-1]
            returns2_short = np.diff(p2_short) / p2_short[:-1]
            short_corr = np.corrcoef(returns1_short, returns2_short)[0, 1] if len(returns1_short) > 0 else 0.0
            short_corr = short_corr if not np.isnan(short_corr) else 0.0
        else:
            short_corr = 0.0
        
        return long_corr, short_corr
    
    def check_correlation(self, new_symbol: str, existing_symbols: List[str]) -> tuple:
        """
        Check if new symbol is too correlated with existing positions
        Uses both long and short windows to catch regime shifts
        
        Args:
            new_symbol: Symbol to check
            existing_symbols: List of currently held symbols
            
        Returns:
            (is_acceptable, max_correlation_found, correlated_symbol)
        """
        if not existing_symbols:
            return True, 0.0, None
        
        max_corr = 0.0
        max_corr_symbol = None
        
        for existing_symbol in existing_symbols:
            long_corr, short_corr = self.calculate_correlation_multi_window(new_symbol, existing_symbol)
            
            # Track maximum correlation
            if abs(long_corr) > abs(max_corr):
                max_corr = long_corr
                max_corr_symbol = existing_symbol
            
            # Reject if EITHER window exceeds threshold (catches regime shifts)
            if abs(long_corr) > self.max_correlation or abs(short_corr) > self.max_correlation:
                logger.warning(f"Rejecting {new_symbol}: correlation with {existing_symbol} "
                             f"(60d: {long_corr:.2f}, 20d: {short_corr:.2f}) exceeds {self.max_correlation}")
                return False, max(abs(long_corr), abs(short_corr)), existing_symbol
        
        return True, max_corr, max_corr_symbol
    
    def filter_signals(self, 
                      signals: List[Dict],
                      existing_positions: Dict[str, int],
                      market_data: pd.DataFrame) -> List[Dict]:
        """
        Filter signals based on correlation with existing positions
        
        Args:
            signals: List of trading signals
            existing_positions: Dict of {symbol: shares}
            market_data: DataFrame with price history
            
        Returns:
            Filtered list of signals
        """
        # Update price history
        for symbol in market_data['symbol'].unique():
            symbol_data = market_data[market_data['symbol'] == symbol]
            self.update_price_history(symbol, symbol_data['close'])
        
        # Filter signals
        filtered_signals = []
        existing_symbols = list(existing_positions.keys())
        
        for signal in signals:
            if signal.get('action') != 'BUY':
                # Don't filter sell signals
                filtered_signals.append(signal)
                continue
            
            symbol = signal.get('symbol')
            is_acceptable, max_corr, corr_symbol = self.check_correlation(symbol, existing_symbols)
            
            if is_acceptable:
                filtered_signals.append(signal)
                logger.info(f"Accepted {symbol}: max correlation {max_corr:.2f} "
                          f"with {corr_symbol if corr_symbol else 'none'}")
            else:
                logger.info(f"Filtered {symbol}: too correlated with {corr_symbol}")
        
        return filtered_signals
