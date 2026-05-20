#!/usr/bin/env python3
"""
Catastrophe Stop Loss Manager
Implements 2-3x ATR stop losses for tail protection
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class StopLossManager:
    """Manages catastrophe stop losses based on ATR.

    Supports:
      * Per-call multiplier override (regime-aware stops).
      * Ratchet trailing: lock-in to entry once +1×ATR, lock to entry+1×ATR
        once +2×ATR. Stops only ever move UP.
    """

    def __init__(
        self,
        atr_multiplier: float = 2.5,
        breakeven_atr: float = 1.0,
        lock_atr: float = 2.0,
    ):
        self.atr_multiplier = atr_multiplier
        self.breakeven_atr = breakeven_atr
        self.lock_atr = lock_atr
        self.stop_levels: dict[str, float] = {}
        self.entry_prices: dict[str, float] = {}
        self.entry_atrs: dict[str, float] = {}
        logger.info(
            "Stop Loss Manager: %.1fx ATR base, ratchet @ +%.1f×ATR → entry, "
            "+%.1f×ATR → entry+1×ATR",
            atr_multiplier,
            breakeven_atr,
            lock_atr,
        )

    def set_stop_loss(
        self,
        symbol: str,
        entry_price: float,
        atr: float,
        multiplier: float | None = None,
    ):
        """Set initial stop. ``multiplier`` overrides the default for regime sensitivity."""
        if not (atr and atr > 0):
            logger.warning(f"No ATR available for {symbol}, no stop loss set")
            return
        mult = multiplier if multiplier is not None else self.atr_multiplier
        stop_price = max(entry_price - (mult * atr), 0.01)  # floor at $0.01
        self.stop_levels[symbol] = stop_price
        self.entry_prices[symbol] = entry_price
        self.entry_atrs[symbol] = atr
        logger.info(
            f"Stop loss set for {symbol}: ${stop_price:.2f} "
            f"({mult:.1f}x ATR from ${entry_price:.2f})"
        )

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
            logger.warning(
                f"STOP LOSS HIT: {symbol} at ${current_price:.2f} " f"(stop: ${stop_price:.2f})"
            )
            return True

        return False

    def remove_stop_loss(self, symbol: str):
        """Remove stop loss tracking for a symbol."""
        self.stop_levels.pop(symbol, None)
        self.entry_prices.pop(symbol, None)
        self.entry_atrs.pop(symbol, None)
        logger.debug(f"Stop loss removed for {symbol}")

    def get_stop_price(self, symbol: str) -> float:
        """Get stop price for a symbol"""
        return self.stop_levels.get(symbol, 0.0)

    def update_trailing_stop(self, symbol: str, current_price: float, atr: float):
        """Legacy chandelier trailing — stop = price − mult×ATR. Stops only move up."""
        if symbol not in self.stop_levels or not atr or atr <= 0:
            return
        new_stop = max(current_price - (self.atr_multiplier * atr), 0.01)
        if new_stop > self.stop_levels[symbol]:
            self.stop_levels[symbol] = new_stop
            logger.info(f"Trailing stop updated for {symbol}: ${new_stop:.2f}")

    def update_ratchet_stop(self, symbol: str, current_price: float, atr: float):
        """Ratchet stop based on open profit measured in ATR units.

        * +breakeven_atr (default 1×ATR) of profit → stop ratchets up to entry.
        * +lock_atr     (default 2×ATR) of profit → stop ratchets up to entry + 1×ATR.
        Stops never move down. Falls back to chandelier trailing for further gains.
        """
        if symbol not in self.stop_levels or not atr or atr <= 0:
            return
        entry = self.entry_prices.get(symbol)
        if not entry:
            return self.update_trailing_stop(symbol, current_price, atr)

        open_profit = current_price - entry
        current_stop = self.stop_levels[symbol]
        new_stop = current_stop

        # Tier 2: lock in 1×ATR of profit
        if open_profit >= self.lock_atr * atr:
            new_stop = max(new_stop, entry + atr)
        # Tier 1: ratchet to breakeven
        elif open_profit >= self.breakeven_atr * atr:
            new_stop = max(new_stop, entry)

        # Above tier 2, also let chandelier extend further
        chandelier = max(current_price - (self.atr_multiplier * atr), 0.01)
        new_stop = max(new_stop, chandelier) if open_profit >= self.lock_atr * atr else new_stop

        if new_stop > current_stop:
            self.stop_levels[symbol] = new_stop
            logger.info(
                f"Ratchet stop for {symbol}: ${new_stop:.2f} "
                f"(entry ${entry:.2f}, profit {open_profit:+.2f} = {open_profit/atr:.1f}×ATR)"
            )
