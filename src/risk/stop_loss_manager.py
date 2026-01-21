#!/usr/bin/env python3
"""
Catastrophe Stop Loss Manager
Implements 2-3x ATR stop losses for tail protection
"""
import logging
from typing import Dict

logger = logging.getLogger(__name__)

class StopLossManager:
    """Manages catastrophe stop losses based on ATR"""
    
    def __init__(self, atr_multiplier: float = 2.5):
        """
        Initialize stop loss manager
        
        Args:
            atr_multiplier: Multiplier for ATR (2-3x recommended)
        """
        self.atr_multiplier = atr_multiplier
        self.stop_levels = {}  # {symbol: stop_price}
        
        logger.info(f"Stop Loss Manager: {atr_multiplier}x ATR catastrophe stops")
    
    def set_stop_loss(self, symbol: str, entry_price: float, atr: float):
        """
        Set stop loss for a position
        
        Args:
            symbol: Stock symbol
            entry_price: Entry price
            atr: Average True Range (20-day)
        """
        if atr and atr > 0:
            stop_price = entry_price - (self.atr_multiplier * atr)
            self.stop_levels[symbol] = stop_price
            logger.info(f"Stop loss set for {symbol}: ${stop_price:.2f} "
                       f"({self.atr_multiplier}x ATR from ${entry_price:.2f})")
        else:
            logger.warning(f"No ATR available for {symbol}, no stop loss set")
    
    def check_stop_loss(self, symbol: str, current_price: float) -> bool:
        """
        Check if stop loss has been hit
        
        Args:
            symbol: Stock symbol
            current_price: Current price
            
        Returns:
            True if stop loss hit, False otherwise
        """
        if symbol not in self.stop_levels:
            return False
        
        stop_price = self.stop_levels[symbol]
        
        if current_price <= stop_price:
            logger.warning(f"STOP LOSS HIT: {symbol} at ${current_price:.2f} "
                          f"(stop: ${stop_price:.2f})")
            return True
        
        return False
    
    def remove_stop_loss(self, symbol: str):
        """Remove stop loss for a symbol"""
        if symbol in self.stop_levels:
            del self.stop_levels[symbol]
            logger.debug(f"Stop loss removed for {symbol}")
    
    def get_stop_price(self, symbol: str) -> float:
        """Get stop price for a symbol"""
        return self.stop_levels.get(symbol, 0.0)
    
    def update_trailing_stop(self, symbol: str, current_price: float, atr: float):
        """
        Update trailing stop loss (optional enhancement)
        
        Only moves stop up, never down
        """
        if symbol not in self.stop_levels or not atr or atr <= 0:
            return
        
        new_stop = current_price - (self.atr_multiplier * atr)
        current_stop = self.stop_levels[symbol]
        
        if new_stop > current_stop:
            self.stop_levels[symbol] = new_stop
            logger.info(f"Trailing stop updated for {symbol}: ${new_stop:.2f}")
