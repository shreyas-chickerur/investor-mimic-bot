"""
Sell Signal Logic - Determine when to exit positions.
Includes stop loss, take profit, and fundamental deterioration signals.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """Represents an open position."""

    symbol: str
    quantity: float
    entry_price: float
    entry_date: datetime
    current_price: float
    current_value: float
    unrealized_pnl: float
    unrealized_pnl_pct: float


@dataclass
class SellSignal:
    """Represents a sell signal for a position."""

    symbol: str
    reason: str
    urgency: str  # 'high', 'medium', 'low'
    confidence: float
    details: Dict


class SellSignalGenerator:
    """
    Generate sell signals based on multiple criteria.
    """

    def __init__(
        self,
        stop_loss_pct: float = -10.0,
        take_profit_pct: float = 30.0,
        trailing_stop_pct: float = -5.0,
        max_hold_days: int = 365,
    ):
        """
        Initialize sell signal generator.

        Args:
            stop_loss_pct: Stop loss percentage (negative)
            take_profit_pct: Take profit percentage (positive)
            trailing_stop_pct: Trailing stop percentage (negative)
            max_hold_days: Maximum days to hold a position
        """
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.trailing_stop_pct = trailing_stop_pct
        self.max_hold_days = max_hold_days

    def analyze_position(
        self,
        position: Position,
        conviction_score: float = 0.0,
        sentiment_score: float = 0.0,
        technical_score: float = 0.0,
    ) -> Optional[SellSignal]:
        """
        Analyze a position and generate sell signal if needed.

        Args:
            position: Position to analyze
            conviction_score: Current 13F conviction score
            sentiment_score: Current news sentiment
            technical_score: Current technical score

        Returns:
            SellSignal if should sell, None otherwise
        """
        signals = []

        # 1. Stop Loss
        if position.unrealized_pnl_pct <= self.stop_loss_pct:
            signals.append(
                SellSignal(
                    symbol=position.symbol,
                    reason="stop_loss",
                    urgency="high",
                    confidence=1.0,
                    details={
                        "pnl_pct": position.unrealized_pnl_pct,
                        "threshold": self.stop_loss_pct,
                        "message": f"Stop loss triggered: {position.unrealized_pnl_pct:.1f}%",
                    },
                )
            )

        # 2. Take Profit
        if position.unrealized_pnl_pct >= self.take_profit_pct:
            signals.append(
                SellSignal(
                    symbol=position.symbol,
                    reason="take_profit",
                    urgency="medium",
                    confidence=0.9,
                    details={
                        "pnl_pct": position.unrealized_pnl_pct,
                        "threshold": self.take_profit_pct,
                        "message": f"Take profit target reached: {position.unrealized_pnl_pct:.1f}%",
                    },
                )
            )

        # 3. Fundamental Deterioration (conviction dropped)
        if conviction_score < 0.001:  # Institutions exited
            signals.append(
                SellSignal(
                    symbol=position.symbol,
                    reason="conviction_dropped",
                    urgency="high",
                    confidence=0.8,
                    details={
                        "conviction_score": conviction_score,
                        "message": "Top investors have exited this position",
                    },
                )
            )

        # 4. Negative Sentiment Shift
        if sentiment_score < -0.5:
            signals.append(
                SellSignal(
                    symbol=position.symbol,
                    reason="negative_sentiment",
                    urgency="medium",
                    confidence=0.7,
                    details={
                        "sentiment_score": sentiment_score,
                        "message": "Strong negative news sentiment",
                    },
                )
            )

        # 5. Technical Breakdown
        if technical_score < -0.6:
            signals.append(
                SellSignal(
                    symbol=position.symbol,
                    reason="technical_breakdown",
                    urgency="medium",
                    confidence=0.6,
                    details={
                        "technical_score": technical_score,
                        "message": "Technical indicators show weakness",
                    },
                )
            )

        # 6. Max Hold Period
        days_held = (datetime.now() - position.entry_date).days
        if days_held >= self.max_hold_days:
            signals.append(
                SellSignal(
                    symbol=position.symbol,
                    reason="max_hold_period",
                    urgency="low",
                    confidence=0.5,
                    details={
                        "days_held": days_held,
                        "max_days": self.max_hold_days,
                        "message": f"Position held for {days_held} days",
                    },
                )
            )

        # Return highest priority signal
        if signals:
            # Sort by urgency and confidence
            urgency_order = {"high": 3, "medium": 2, "low": 1}
            signals.sort(key=lambda s: (urgency_order[s.urgency], s.confidence), reverse=True)
            return signals[0]

        return None

    def analyze_portfolio(
        self,
        positions: List[Position],
        conviction_scores: Dict[str, float],
        sentiment_scores: Dict[str, float],
        technical_scores: Dict[str, float],
    ) -> List[SellSignal]:
        """
        Analyze entire portfolio and generate sell signals.

        Args:
            positions: List of open positions
            conviction_scores: Current conviction scores
            sentiment_scores: Current sentiment scores
            technical_scores: Current technical scores

        Returns:
            List of sell signals
        """
        sell_signals = []

        for position in positions:
            signal = self.analyze_position(
                position,
                conviction_score=conviction_scores.get(position.symbol, 0.0),
                sentiment_score=sentiment_scores.get(position.symbol, 0.0),
                technical_score=technical_scores.get(position.symbol, 0.0),
            )

            if signal:
                sell_signals.append(signal)

        return sell_signals

    def should_rebalance(
        self,
        positions: List[Position],
        target_weights: Dict[str, float],
        rebalance_threshold: float = 0.05,
    ) -> List[str]:
        """
        Determine if portfolio needs rebalancing.

        Args:
            positions: Current positions
            target_weights: Target allocation weights
            rebalance_threshold: Threshold for rebalancing (5% default)

        Returns:
            List of symbols to sell for rebalancing
        """
        # Calculate current weights
        total_value = sum(p.current_value for p in positions)

        if total_value == 0:
            return []

        current_weights = {p.symbol: p.current_value / total_value for p in positions}

        # Find positions that are overweight
        to_sell = []

        for symbol, current_weight in current_weights.items():
            target_weight = target_weights.get(symbol, 0.0)

            # If significantly overweight or no longer in target
            if current_weight > target_weight + rebalance_threshold:
                to_sell.append(symbol)
            elif target_weight == 0 and current_weight > 0:
                to_sell.append(symbol)

        return to_sell


class PositionTracker:
    """
    Track open positions and their performance.
    """

    def __init__(self, storage_file: str = "data/positions.json"):
        """Initialize position tracker."""
        self.storage_file = storage_file

    def get_open_positions(self) -> List[Position]:
        """
        Get all open positions from Alpaca.

        Returns:
            List of Position objects
        """
        # This would integrate with Alpaca API
        # For now, return empty list
        return []

    def track_position(self, symbol: str, quantity: float, entry_price: float, entry_date: datetime):
        """Record a new position."""
        # Would save to storage

    def close_position(self, symbol: str):
        """Mark a position as closed."""
        # Would update storage

    def get_position_history(self, symbol: str) -> List[Dict]:
        """Get historical performance for a symbol."""
        # Would retrieve from storage
        return []
