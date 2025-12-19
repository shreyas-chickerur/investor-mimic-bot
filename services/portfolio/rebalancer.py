"""
Portfolio Rebalancing System

Maintains optimal portfolio allocation by rebalancing positions that drift
from target weights. Prevents concentration risk and maintains diversification.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple


logger = logging.getLogger(__name__)


@dataclass
class RebalanceConfig:
    """Rebalancing configuration."""

    max_position_pct: float = 0.12  # 12% max per position
    min_position_pct: float = 0.03  # 3% min per position
    rebalance_threshold: float = 0.02  # 2% drift triggers rebalance
    rebalance_frequency_days: int = 7  # Weekly rebalancing
    full_rebalance_days: int = 30  # Monthly full rebalance
    event_driven_threshold: float = 0.20  # 20% move triggers rebalance


@dataclass
class PortfolioPosition:
    """Portfolio position."""

    symbol: str
    quantity: float
    current_price: float
    current_value: float
    target_weight: float
    current_weight: float
    drift: float  # Difference from target

    @property
    def needs_rebalance(self) -> bool:
        """Does this position need rebalancing?"""
        return abs(self.drift) > 0.02  # 2% threshold


class PortfolioRebalancer:
    """
    Manages portfolio rebalancing to maintain optimal allocation.
    """

    def __init__(self, config: Optional[RebalanceConfig] = None):
        """
        Initialize rebalancer.

        Args:
            config: Rebalancing configuration
        """
        self.config = config or RebalanceConfig()
        self.last_rebalance: Optional[datetime] = None
        self.last_full_rebalance: Optional[datetime] = None
        self.rebalance_history: List[Dict] = []

    def calculate_portfolio_weights(
        self, positions: Dict[str, Dict], total_value: float
    ) -> Dict[str, PortfolioPosition]:
        """
        Calculate current and target weights for all positions.

        Args:
            positions: Dictionary of symbol -> position info
                      {symbol: {'quantity': float, 'price': float, 'target_weight': float}}
            total_value: Total portfolio value

        Returns:
            Dictionary of symbol -> PortfolioPosition
        """
        portfolio_positions = {}

        for symbol, pos in positions.items():
            quantity = pos["quantity"]
            price = pos["price"]
            target_weight = pos.get("target_weight", 0.0)

            current_value = quantity * price
            current_weight = current_value / total_value if total_value > 0 else 0
            drift = current_weight - target_weight

            portfolio_positions[symbol] = PortfolioPosition(
                symbol=symbol,
                quantity=quantity,
                current_price=price,
                current_value=current_value,
                target_weight=target_weight,
                current_weight=current_weight,
                drift=drift,
            )

        return portfolio_positions

    def identify_rebalance_needs(
        self, portfolio_positions: Dict[str, PortfolioPosition]
    ) -> Tuple[List[str], List[str], List[str]]:
        """
        Identify positions that need rebalancing.

        Args:
            portfolio_positions: Dictionary of positions

        Returns:
            Tuple of (oversized, undersized, within_range)
        """
        oversized = []
        undersized = []
        within_range = []

        for symbol, pos in portfolio_positions.items():
            # Check if oversized
            if pos.current_weight > self.config.max_position_pct:
                oversized.append(symbol)
            # Check if undersized
            elif pos.current_weight < self.config.min_position_pct and pos.target_weight > 0:
                undersized.append(symbol)
            # Check drift threshold
            elif abs(pos.drift) > self.config.rebalance_threshold:
                if pos.drift > 0:
                    oversized.append(symbol)
                else:
                    undersized.append(symbol)
            else:
                within_range.append(symbol)

        return oversized, undersized, within_range

    def calculate_rebalance_trades(
        self, portfolio_positions: Dict[str, PortfolioPosition], total_value: float
    ) -> List[Dict]:
        """
        Calculate trades needed to rebalance portfolio.

        Args:
            portfolio_positions: Dictionary of positions
            total_value: Total portfolio value

        Returns:
            List of trade dictionaries
        """
        trades = []

        for symbol, pos in portfolio_positions.items():
            # Calculate target value
            target_value = total_value * pos.target_weight
            current_value = pos.current_value

            # Calculate value difference
            value_diff = target_value - current_value

            # Skip if difference is too small
            if abs(value_diff) < total_value * 0.01:  # Less than 1% of portfolio
                continue

            # Calculate quantity to trade
            quantity_diff = value_diff / pos.current_price

            if quantity_diff > 0:
                # Need to buy
                trades.append(
                    {
                        "symbol": symbol,
                        "action": "BUY",
                        "quantity": abs(quantity_diff),
                        "current_weight": pos.current_weight,
                        "target_weight": pos.target_weight,
                        "drift": pos.drift,
                        "value": abs(value_diff),
                    }
                )
            elif quantity_diff < 0:
                # Need to sell
                trades.append(
                    {
                        "symbol": symbol,
                        "action": "SELL",
                        "quantity": abs(quantity_diff),
                        "current_weight": pos.current_weight,
                        "target_weight": pos.target_weight,
                        "drift": pos.drift,
                        "value": abs(value_diff),
                    }
                )

        return trades

    def should_rebalance(
        self, portfolio_positions: Dict[str, PortfolioPosition], force: bool = False
    ) -> Tuple[bool, str]:
        """
        Determine if portfolio should be rebalanced.

        Args:
            portfolio_positions: Dictionary of positions
            force: Force rebalance regardless of schedule

        Returns:
            Tuple of (should_rebalance, reason)
        """
        now = datetime.now()

        # Force rebalance
        if force:
            return True, "FORCED"

        # Check for event-driven rebalance (large moves)
        for pos in portfolio_positions.values():
            if abs(pos.drift) > self.config.event_driven_threshold:
                return True, f"EVENT_DRIVEN ({pos.symbol} drift: {pos.drift:+.1%})"

        # Check for oversized positions
        oversized, undersized, _ = self.identify_rebalance_needs(portfolio_positions)
        if oversized:
            return True, f"OVERSIZED_POSITIONS ({', '.join(oversized)})"

        # Check scheduled rebalance
        if self.last_rebalance:
            days_since = (now - self.last_rebalance).days
            if days_since >= self.config.rebalance_frequency_days:
                return True, "SCHEDULED_WEEKLY"
        else:
            return True, "INITIAL_REBALANCE"

        # Check full rebalance schedule
        if self.last_full_rebalance:
            days_since = (now - self.last_full_rebalance).days
            if days_since >= self.config.full_rebalance_days:
                return True, "SCHEDULED_MONTHLY"

        return False, "NO_REBALANCE_NEEDED"

    def execute_rebalance(
        self,
        portfolio_positions: Dict[str, PortfolioPosition],
        total_value: float,
        dry_run: bool = False,
    ) -> Dict:
        """
        Execute portfolio rebalance.

        Args:
            portfolio_positions: Dictionary of positions
            total_value: Total portfolio value
            dry_run: If True, only calculate trades without executing

        Returns:
            Rebalance summary
        """
        # Calculate trades
        trades = self.calculate_rebalance_trades(portfolio_positions, total_value)

        # Identify position categories
        oversized, undersized, within_range = self.identify_rebalance_needs(portfolio_positions)

        summary = {
            "timestamp": datetime.now(),
            "total_value": total_value,
            "num_positions": len(portfolio_positions),
            "oversized_positions": oversized,
            "undersized_positions": undersized,
            "within_range_positions": within_range,
            "trades": trades,
            "num_trades": len(trades),
            "total_trade_value": sum(t["value"] for t in trades),
            "dry_run": dry_run,
        }

        if not dry_run:
            self.last_rebalance = datetime.now()
            if len(trades) > len(portfolio_positions) * 0.5:  # More than 50% of positions
                self.last_full_rebalance = datetime.now()
            self.rebalance_history.append(summary)

        logger.info(
            f"Rebalance {'simulation' if dry_run else 'executed'}: {len(trades)} trades, ${summary['total_trade_value']:,.2f} total value"
        )

        return summary

    def get_rebalance_report(self, portfolio_positions: Dict[str, PortfolioPosition], total_value: float) -> str:
        """
        Generate human-readable rebalance report.

        Args:
            portfolio_positions: Dictionary of positions
            total_value: Total portfolio value

        Returns:
            Report string
        """
        oversized, undersized, within_range = self.identify_rebalance_needs(portfolio_positions)
        trades = self.calculate_rebalance_trades(portfolio_positions, total_value)

        report = f"""
PORTFOLIO REBALANCE REPORT
{'=' * 60}

Portfolio Value: ${total_value:,.2f}
Total Positions: {len(portfolio_positions)}

POSITION STATUS:
  Oversized (need to reduce):  {len(oversized)}
  Undersized (need to add):    {len(undersized)}
  Within range:                {len(within_range)}

"""

        if oversized:
            report += "OVERSIZED POSITIONS:\n"
            for symbol in oversized:
                pos = portfolio_positions[symbol]
                report += (
                    f"  {symbol}: {pos.current_weight:.1%} (target: {pos.target_weight:.1%}, drift: {pos.drift:+.1%})\n"
                )
            report += "\n"

        if undersized:
            report += "UNDERSIZED POSITIONS:\n"
            for symbol in undersized:
                pos = portfolio_positions[symbol]
                report += (
                    f"  {symbol}: {pos.current_weight:.1%} (target: {pos.target_weight:.1%}, drift: {pos.drift:+.1%})\n"
                )
            report += "\n"

        if trades:
            report += f"RECOMMENDED TRADES ({len(trades)}):\n"
            for trade in trades:
                report += (
                    f"  {trade['action']:4s} {trade['quantity']:8.2f} {trade['symbol']:6s} (${trade['value']:,.2f})\n"
                )
            report += f"\nTotal Trade Value: ${sum(t['value'] for t in trades):,.2f}\n"
        else:
            report += "NO TRADES NEEDED - Portfolio is balanced\n"

        return report

    def get_rebalance_history(self, limit: int = 10) -> List[Dict]:
        """Get recent rebalance history."""
        return self.rebalance_history[-limit:]


class SmartRebalancer(PortfolioRebalancer):
    """
    Smart rebalancer with tax-loss harvesting and transaction cost awareness.
    """

    def __init__(
        self,
        config: Optional[RebalanceConfig] = None,
        transaction_cost_pct: float = 0.001,  # 0.1% transaction cost
    ):
        super().__init__(config)
        self.transaction_cost_pct = transaction_cost_pct

    def calculate_tax_aware_trades(
        self,
        portfolio_positions: Dict[str, PortfolioPosition],
        total_value: float,
        cost_basis: Dict[str, float],
    ) -> List[Dict]:
        """
        Calculate trades with tax-loss harvesting.

        Args:
            portfolio_positions: Dictionary of positions
            total_value: Total portfolio value
            cost_basis: Dictionary of symbol -> cost basis

        Returns:
            List of tax-aware trades
        """
        trades = self.calculate_rebalance_trades(portfolio_positions, total_value)

        # Prioritize selling losers (tax-loss harvesting)
        for trade in trades:
            symbol = trade["symbol"]
            if trade["action"] == "SELL" and symbol in cost_basis:
                current_price = portfolio_positions[symbol].current_price
                pnl = current_price - cost_basis[symbol]
                trade["pnl"] = pnl
                trade["is_loss"] = pnl < 0
                trade["priority"] = "HIGH" if pnl < 0 else "NORMAL"

        # Sort: losses first (tax harvesting), then by value
        trades.sort(key=lambda x: (x.get("priority", "NORMAL") != "HIGH", -x["value"]))

        return trades

    def optimize_for_transaction_costs(self, trades: List[Dict], min_trade_value: float = 100.0) -> List[Dict]:
        """
        Filter out trades where transaction costs exceed benefit.

        Args:
            trades: List of trades
            min_trade_value: Minimum trade value to execute

        Returns:
            Filtered list of trades
        """
        optimized_trades = []

        for trade in trades:
            trade_value = trade["value"]
            transaction_cost = trade_value * self.transaction_cost_pct

            # Only execute if trade value exceeds minimum and cost is reasonable
            if trade_value >= min_trade_value and transaction_cost < trade_value * 0.1:
                trade["transaction_cost"] = transaction_cost
                optimized_trades.append(trade)
            else:
                logger.debug(f"Skipping small trade: {trade['symbol']} ${trade_value:.2f}")

        return optimized_trades
