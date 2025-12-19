"""
Stop-Loss and Take-Profit Manager

Automated exit strategy to protect capital and lock in profits.
Prevents catastrophic losses and ensures disciplined profit-taking.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class StopLossConfig:
    """Stop-loss configuration."""

    hard_stop_pct: float = 0.10  # -10% hard stop
    trailing_stop_pct: float = 0.08  # -8% trailing stop from peak
    atr_multiplier: float = 2.0  # 2x ATR for volatility-adjusted stop
    use_trailing: bool = True
    use_volatility_adjusted: bool = True


@dataclass
class TakeProfitConfig:
    """Take-profit configuration."""

    target_1_pct: float = 0.15  # +15% first target
    target_1_size: float = 0.50  # Take 50% off at target 1
    target_2_pct: float = 0.30  # +30% second target
    target_2_size: float = 0.25  # Take 25% off at target 2
    trail_remaining: bool = True  # Trail remaining 25%


@dataclass
class Position:
    """Position tracking."""

    symbol: str
    entry_price: float
    current_price: float
    quantity: float
    entry_date: datetime
    peak_price: float  # Highest price since entry
    stop_price: float  # Current stop-loss price
    target_1_hit: bool = False
    target_2_hit: bool = False
    remaining_quantity: float = None  # After partial exits

    def __post_init__(self):
        if self.remaining_quantity is None:
            self.remaining_quantity = self.quantity

    @property
    def current_pnl_pct(self) -> float:
        """Current profit/loss percentage."""
        return ((self.current_price - self.entry_price) / self.entry_price) * 100

    @property
    def peak_pnl_pct(self) -> float:
        """Peak profit percentage."""
        return ((self.peak_price - self.entry_price) / self.entry_price) * 100


class StopLossManager:
    """
    Manages stop-losses and take-profits for all positions.
    """

    def __init__(
        self,
        stop_config: Optional[StopLossConfig] = None,
        profit_config: Optional[TakeProfitConfig] = None,
    ):
        """
        Initialize stop-loss manager.

        Args:
            stop_config: Stop-loss configuration
            profit_config: Take-profit configuration
        """
        self.stop_config = stop_config or StopLossConfig()
        self.profit_config = profit_config or TakeProfitConfig()
        self.positions: Dict[str, Position] = {}

    def add_position(
        self,
        symbol: str,
        entry_price: float,
        quantity: float,
        entry_date: Optional[datetime] = None,
        atr: Optional[float] = None,
    ) -> Position:
        """
        Add a new position to track.

        Args:
            symbol: Stock symbol
            entry_price: Entry price
            quantity: Position size
            entry_date: Entry date
            atr: Average True Range for volatility-adjusted stop

        Returns:
            Position object
        """
        if entry_date is None:
            entry_date = datetime.now()

        # Calculate initial stop price
        stop_price = self._calculate_initial_stop(entry_price, atr)

        position = Position(
            symbol=symbol,
            entry_price=entry_price,
            current_price=entry_price,
            quantity=quantity,
            entry_date=entry_date,
            peak_price=entry_price,
            stop_price=stop_price,
        )

        self.positions[symbol] = position

        logger.info(f"Added position: {symbol} @ ${entry_price:.2f}, stop @ ${stop_price:.2f}")

        return position

    def _calculate_initial_stop(self, entry_price: float, atr: Optional[float] = None) -> float:
        """Calculate initial stop-loss price."""
        # Hard stop
        hard_stop = entry_price * (1 - self.stop_config.hard_stop_pct)

        # Volatility-adjusted stop (if ATR available)
        if atr and self.stop_config.use_volatility_adjusted:
            vol_stop = entry_price - (atr * self.stop_config.atr_multiplier)
            # Use the tighter of the two stops
            return max(hard_stop, vol_stop)

        return hard_stop

    def update_position(
        self, symbol: str, current_price: float
    ) -> Tuple[bool, Optional[str], Optional[float]]:
        """
        Update position with current price and check for exits.

        Args:
            symbol: Stock symbol
            current_price: Current market price

        Returns:
            Tuple of (should_exit, reason, exit_quantity)
        """
        if symbol not in self.positions:
            logger.warning(f"Position {symbol} not found")
            return False, None, None

        position = self.positions[symbol]
        position.current_price = current_price

        # Update peak price
        if current_price > position.peak_price:
            position.peak_price = current_price

            # Update trailing stop
            if self.stop_config.use_trailing:
                new_stop = position.peak_price * (1 - self.stop_config.trailing_stop_pct)
                position.stop_price = max(position.stop_price, new_stop)

        # Check stop-loss
        if current_price <= position.stop_price:
            logger.info(
                f"Stop-loss hit for {symbol}: ${current_price:.2f} <= ${position.stop_price:.2f}"
            )
            return True, "STOP_LOSS", position.remaining_quantity

        # Check take-profit targets
        pnl_pct = position.current_pnl_pct

        # Target 1
        if not position.target_1_hit and pnl_pct >= self.profit_config.target_1_pct * 100:
            exit_qty = position.quantity * self.profit_config.target_1_size
            position.target_1_hit = True
            position.remaining_quantity -= exit_qty
            logger.info(
                f"Target 1 hit for {symbol}: Taking {self.profit_config.target_1_size:.0%} off"
            )
            return True, "TAKE_PROFIT_1", exit_qty

        # Target 2
        if (
            position.target_1_hit
            and not position.target_2_hit
            and pnl_pct >= self.profit_config.target_2_pct * 100
        ):
            exit_qty = position.quantity * self.profit_config.target_2_size
            position.target_2_hit = True
            position.remaining_quantity -= exit_qty
            logger.info(
                f"Target 2 hit for {symbol}: Taking {self.profit_config.target_2_size:.0%} off"
            )
            return True, "TAKE_PROFIT_2", exit_qty

        return False, None, None

    def get_position_status(self, symbol: str) -> Optional[Dict]:
        """Get current status of a position."""
        if symbol not in self.positions:
            return None

        position = self.positions[symbol]

        return {
            "symbol": symbol,
            "entry_price": position.entry_price,
            "current_price": position.current_price,
            "quantity": position.quantity,
            "remaining_quantity": position.remaining_quantity,
            "current_pnl_pct": position.current_pnl_pct,
            "peak_pnl_pct": position.peak_pnl_pct,
            "stop_price": position.stop_price,
            "target_1_hit": position.target_1_hit,
            "target_2_hit": position.target_2_hit,
            "days_held": (datetime.now() - position.entry_date).days,
        }

    def remove_position(self, symbol: str):
        """Remove a position from tracking."""
        if symbol in self.positions:
            del self.positions[symbol]
            logger.info(f"Removed position: {symbol}")

    def get_all_positions(self) -> List[Dict]:
        """Get status of all positions."""
        return [self.get_position_status(symbol) for symbol in self.positions.keys()]

    def check_all_positions(self, current_prices: Dict[str, float]) -> List[Tuple[str, str, float]]:
        """
        Check all positions for exit signals.

        Args:
            current_prices: Dictionary of symbol -> current price

        Returns:
            List of (symbol, reason, quantity) tuples for positions to exit
        """
        exits = []

        for symbol, price in current_prices.items():
            if symbol in self.positions:
                should_exit, reason, quantity = self.update_position(symbol, price)
                if should_exit:
                    exits.append((symbol, reason, quantity))

        return exits


class AdvancedStopLossManager(StopLossManager):
    """
    Advanced stop-loss manager with additional features.
    """

    def calculate_atr(self, prices: pd.Series, period: int = 14) -> float:
        """
        Calculate Average True Range for volatility-adjusted stops.

        Args:
            prices: Series of prices
            period: ATR period

        Returns:
            ATR value
        """
        if len(prices) < period + 1:
            return prices.std()  # Fallback to standard deviation

        # Calculate True Range
        high = prices.rolling(window=2).max()
        low = prices.rolling(window=2).min()
        tr = high - low

        # Calculate ATR
        atr = tr.rolling(window=period).mean().iloc[-1]

        return atr if not np.isnan(atr) else prices.std()

    def adjust_stop_for_volatility(self, symbol: str, recent_prices: pd.Series):
        """
        Adjust stop-loss based on recent volatility.

        Args:
            symbol: Stock symbol
            recent_prices: Recent price series
        """
        if symbol not in self.positions:
            return

        position = self.positions[symbol]
        atr = self.calculate_atr(recent_prices)

        # Recalculate stop with current ATR
        vol_stop = position.current_price - (atr * self.stop_config.atr_multiplier)

        # Only tighten the stop, never loosen it
        if vol_stop > position.stop_price:
            position.stop_price = vol_stop
            logger.info(f"Adjusted stop for {symbol} to ${vol_stop:.2f} (ATR: ${atr:.2f})")

    def get_exit_summary(self) -> Dict:
        """Get summary of all exits."""
        summary = {
            "total_positions": len(self.positions),
            "positions_with_target_1": sum(1 for p in self.positions.values() if p.target_1_hit),
            "positions_with_target_2": sum(1 for p in self.positions.values() if p.target_2_hit),
            "avg_pnl_pct": np.mean([p.current_pnl_pct for p in self.positions.values()])
            if self.positions
            else 0,
            "avg_peak_pnl_pct": np.mean([p.peak_pnl_pct for p in self.positions.values()])
            if self.positions
            else 0,
        }

        return summary
