#!/usr/bin/env python3
"""
Catastrophe Stop Loss Manager
Implements 2-3x ATR stop losses for tail protection
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.database import TradingDatabase

logger = logging.getLogger(__name__)


class StopLossManager:
    """Manages catastrophe stop losses based on ATR.

    Supports:
      * Per-call multiplier override (regime-aware stops).
      * Ratchet trailing: lock-in to entry once +1×ATR, lock to entry+1×ATR
        once +2×ATR. Stops only ever move UP.
      * DB persistence: stop levels survive across daily GHA runs.
    """

    def __init__(
        self,
        atr_multiplier: float = 2.5,
        breakeven_atr: float = 1.0,
        lock_atr: float = 2.0,
        db: TradingDatabase | None = None,
    ):
        self.atr_multiplier = atr_multiplier
        self.breakeven_atr = breakeven_atr
        self.lock_atr = lock_atr
        self.db = db
        self.stop_levels: dict[str, float] = {}
        self.entry_prices: dict[str, float] = {}
        self.entry_atrs: dict[str, float] = {}
        # "long" (stop below entry, triggers on fall) or "short" (stop above
        # entry, triggers on rise). Shorts get a catastrophe stop only — no
        # trailing/ratchet in v1, since pairs trades exit on spread reversion.
        self.directions: dict[str, str] = {}

        if self.db is not None:
            self._load_from_db()

        logger.info(
            "Stop Loss Manager: %.1fx ATR base, ratchet @ +%.1f×ATR → entry, "
            "+%.1f×ATR → entry+1×ATR",
            atr_multiplier,
            breakeven_atr,
            lock_atr,
        )

    def _load_from_db(self) -> None:
        """Restore persisted stop levels from the database on startup."""
        try:
            rows = self.db.load_all_stop_losses()  # type: ignore[union-attr]
            for symbol, data in rows.items():
                self.stop_levels[symbol] = data["stop_price"]
                self.entry_prices[symbol] = data["entry_price"]
                self.entry_atrs[symbol] = data["entry_atr"]
                self.directions[symbol] = data.get("direction", "long")
            if rows:
                logger.info("Restored %d stop-loss levels from DB: %s", len(rows), list(rows))
        except Exception as e:
            logger.warning("Could not load stop losses from DB: %s", e)

    def _persist(self, symbol: str) -> None:
        """Save current stop-loss state for a symbol to the database."""
        if self.db is None:
            return
        try:
            self.db.save_stop_loss(
                symbol,
                self.stop_levels[symbol],
                self.entry_prices[symbol],
                self.entry_atrs.get(symbol, 0.0),
                self.directions.get(symbol, "long"),
            )
        except Exception as e:
            logger.warning("Could not persist stop loss for %s: %s", symbol, e)

    def set_stop_loss(
        self,
        symbol: str,
        entry_price: float,
        atr: float,
        multiplier: float | None = None,
        direction: str = "long",
    ):
        """Set initial stop. ``multiplier`` overrides the default for regime sensitivity.

        ``direction="short"`` places the stop ABOVE entry (loss = price rising),
        capped at entry*1.50 to mirror the long-side 50% floor.
        """
        if not (entry_price and entry_price > 0):
            logger.warning(
                "Cannot set stop loss for %s: invalid entry_price=%s", symbol, entry_price
            )
            return
        if not (atr and atr > 0):
            # Fallback: 7% of entry price keeps positions protected even without ATR data.
            atr = entry_price * 0.07
            logger.warning(
                "No ATR for %s — using 7%% fallback stop (ATR=%.2f from entry=%.2f)",
                symbol,
                atr,
                entry_price,
            )
        mult = multiplier if multiplier is not None else self.atr_multiplier
        if direction == "short":
            # Cap at +50% so a missing/garbage ATR can't disable the stop entirely
            stop_price = min(entry_price + (mult * atr), entry_price * 1.50)
        else:
            # Floor at 50% of entry so we never place a stop near $0 (would be rejected by broker)
            stop_price = max(entry_price - (mult * atr), entry_price * 0.50)
        self.stop_levels[symbol] = stop_price
        self.entry_prices[symbol] = entry_price
        self.entry_atrs[symbol] = atr
        self.directions[symbol] = direction
        self._persist(symbol)
        logger.info(
            f"Stop loss set for {symbol} ({direction}): ${stop_price:.2f} "
            f"({mult:.1f}x ATR from ${entry_price:.2f})"
        )

    def get_direction(self, symbol: str) -> str:
        """Direction of the tracked stop for a symbol ('long' when unknown)."""
        return self.directions.get(symbol, "long")

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
        direction = self.directions.get(symbol, "long")

        hit = current_price >= stop_price if direction == "short" else current_price <= stop_price
        if hit:
            logger.warning(
                f"STOP LOSS HIT ({direction}): {symbol} at ${current_price:.2f} "
                f"(stop: ${stop_price:.2f})"
            )
            return True

        return False

    def remove_stop_loss(self, symbol: str):
        """Remove stop loss tracking for a symbol."""
        self.stop_levels.pop(symbol, None)
        self.entry_prices.pop(symbol, None)
        self.entry_atrs.pop(symbol, None)
        self.directions.pop(symbol, None)
        if self.db is not None:
            try:
                self.db.delete_stop_loss(symbol)
            except Exception as e:
                logger.warning("Could not delete stop loss for %s from DB: %s", symbol, e)
        logger.debug(f"Stop loss removed for {symbol}")

    def prune_orphan_stops(self, held_symbols: set[str]) -> list[str]:
        """Drop tracked stops for symbols no longer held.

        Stops are normally removed when a position closes, but a run that aborts
        before the exit phase (e.g. a failed pre-flight) leaves the stop_loss_state
        row behind. Over time these accumulate (June 2026: 18 stored stops vs 4
        held positions). They are harmless to firing — check_stop_losses iterates
        actual positions — but they bloat the table and mislead diagnostics, so
        prune them at startup against the live position set.
        """
        orphans = [s for s in list(self.stop_levels) if s not in held_symbols]
        for symbol in orphans:
            self.remove_stop_loss(symbol)
        if orphans:
            logger.info(
                "Pruned %d orphan stop-loss level(s) with no matching position: %s",
                len(orphans),
                orphans,
            )
        return orphans

    def get_stop_price(self, symbol: str) -> float:
        """Get stop price for a symbol"""
        return self.stop_levels.get(symbol, 0.0)

    def update_trailing_stop(self, symbol: str, current_price: float, atr: float):
        """Legacy chandelier trailing — stop = price − mult×ATR. Stops only move up.

        Long-only: shorts keep their catastrophe stop (raising it would loosen
        protection, lowering it is a different mechanism not implemented in v1).
        """
        if self.directions.get(symbol, "long") == "short":
            return
        if symbol not in self.stop_levels or not atr or atr <= 0:
            return
        new_stop = max(current_price - (self.atr_multiplier * atr), 0.01)
        if new_stop > self.stop_levels[symbol]:
            self.stop_levels[symbol] = new_stop
            self._persist(symbol)
            logger.info(f"Trailing stop updated for {symbol}: ${new_stop:.2f}")

    def update_ratchet_stop(self, symbol: str, current_price: float, atr: float):
        """Ratchet stop based on open profit measured in ATR units.

        * +breakeven_atr (default 1×ATR) of profit → stop ratchets up to entry.
        * +lock_atr     (default 2×ATR) of profit → stop ratchets up to entry + 1×ATR.
        Stops never move down. Falls back to chandelier trailing for further gains.
        Long-only: shorts keep their catastrophe stop (see update_trailing_stop).
        """
        if self.directions.get(symbol, "long") == "short":
            return
        if symbol not in self.stop_levels or not atr or atr <= 0:
            return
        entry = self.entry_prices.get(symbol)
        if entry is None:
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
            self._persist(symbol)
            logger.info(
                f"Ratchet stop for {symbol}: ${new_stop:.2f} "
                f"(entry ${entry:.2f}, profit {open_profit:+.2f} = {open_profit/atr:.1f}×ATR)"
            )

    def audit_and_repair_stops(
        self,
        open_positions: list[dict],
        current_prices: dict[str, float],
        fallback_stop_pct: float = 0.07,
    ) -> list[str]:
        """Verify every open position has an active stop.  For any orphan (no stop
        in stop_levels), create a fallback stop using the current ATR stored on the
        position, or ``avg_price * (1 - fallback_stop_pct)`` if ATR is unavailable.

        Returns a list of symbols where a fallback stop was synthesised.
        """
        repaired: list[str] = []
        for pos in open_positions:
            symbol = pos.get("symbol", "")
            if not symbol or symbol in self.stop_levels:
                continue

            avg_price = float(pos.get("avg_price") or pos.get("entry_price") or 0)
            atr = float(pos.get("atr") or 0)
            current_price = current_prices.get(symbol, avg_price)
            direction = "short" if float(pos.get("shares") or 0) < 0 else "long"

            if avg_price <= 0:
                logger.warning(
                    "Stop-loss audit: %s has no avg_price — cannot create fallback stop", symbol
                )
                continue

            if direction == "short":
                if atr > 0:
                    stop_price = min(current_price + self.atr_multiplier * atr, avg_price * 1.50)
                else:
                    stop_price = avg_price * (1 + fallback_stop_pct)
            elif atr > 0:
                stop_price = max(current_price - self.atr_multiplier * atr, avg_price * 0.50)
            else:
                stop_price = avg_price * (1 - fallback_stop_pct)

            stop_price = max(stop_price, 0.01)
            self.stop_levels[symbol] = stop_price
            self.entry_prices[symbol] = avg_price
            self.entry_atrs[symbol] = atr
            self.directions[symbol] = direction
            self._persist(symbol)
            repaired.append(symbol)
            logger.warning(
                "Stop-loss audit: synthesised fallback stop for %s (%s) at $%.2f "
                "(avg_price=%.2f, atr=%.4f)",
                symbol,
                direction,
                stop_price,
                avg_price,
                atr,
            )

        if repaired:
            logger.warning(
                "Stop-loss audit complete: %d position(s) were missing stops and have been "
                "assigned fallback levels: %s",
                len(repaired),
                repaired,
            )
        else:
            logger.info(
                "Stop-loss audit: all %d open positions have active stops", len(open_positions)
            )
        return repaired
