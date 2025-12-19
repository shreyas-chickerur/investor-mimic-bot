"""
Performance Tracker - Track portfolio performance, returns, and metrics.
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class PortfolioSnapshot:
    """Snapshot of portfolio at a point in time."""

    date: datetime
    total_value: Decimal
    cash: Decimal
    positions_value: Decimal
    positions: Dict[str, Dict]  # symbol -> {quantity, value, price}


@dataclass
class PerformanceMetrics:
    """Performance metrics for a time period."""

    start_date: datetime
    end_date: datetime
    start_value: Decimal
    end_value: Decimal
    total_return: float
    total_return_pct: float
    annualized_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    num_trades: int
    profitable_trades: int


class PerformanceTracker:
    """
    Track and analyze portfolio performance over time.
    """

    def __init__(self, storage_dir: str = "data/performance"):
        """
        Initialize performance tracker.

        Args:
            storage_dir: Directory to store performance data
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.snapshots_file = self.storage_dir / "snapshots.json"
        self.trades_file = self.storage_dir / "trades.json"

        self.snapshots: List[PortfolioSnapshot] = []
        self.trades: List[Dict] = []

        self._load_data()

    def _load_data(self):
        """Load historical data from storage."""
        try:
            if self.snapshots_file.exists():
                with open(self.snapshots_file, "r") as f:
                    data = json.load(f)
                    self.snapshots = [
                        PortfolioSnapshot(
                            date=datetime.fromisoformat(s["date"]),
                            total_value=Decimal(str(s["total_value"])),
                            cash=Decimal(str(s["cash"])),
                            positions_value=Decimal(str(s["positions_value"])),
                            positions=s["positions"],
                        )
                        for s in data
                    ]

            if self.trades_file.exists():
                with open(self.trades_file, "r") as f:
                    self.trades = json.load(f)

            logger.info(f"Loaded {len(self.snapshots)} snapshots and {len(self.trades)} trades")

        except Exception as e:
            logger.error(f"Error loading performance data: {e}")

    def _save_data(self):
        """Save data to storage."""
        try:
            # Save snapshots
            snapshots_data = [
                {
                    "date": s.date.isoformat(),
                    "total_value": str(s.total_value),
                    "cash": str(s.cash),
                    "positions_value": str(s.positions_value),
                    "positions": s.positions,
                }
                for s in self.snapshots
            ]

            with open(self.snapshots_file, "w") as f:
                json.dump(snapshots_data, f, indent=2)

            # Save trades
            with open(self.trades_file, "w") as f:
                json.dump(self.trades, f, indent=2)

        except Exception as e:
            logger.error(f"Error saving performance data: {e}")

    def record_snapshot(self, total_value: Decimal, cash: Decimal, positions: Dict[str, Dict]):
        """
        Record a portfolio snapshot.

        Args:
            total_value: Total portfolio value
            cash: Cash balance
            positions: Dict of positions {symbol: {quantity, value, price}}
        """
        positions_value = sum(Decimal(str(p["value"])) for p in positions.values())

        snapshot = PortfolioSnapshot(
            date=datetime.now(),
            total_value=total_value,
            cash=cash,
            positions_value=positions_value,
            positions=positions,
        )

        self.snapshots.append(snapshot)
        self._save_data()

        logger.info(f"Recorded snapshot: ${total_value:,.2f}")

    def record_trade(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        total_value: float,
        timestamp: Optional[datetime] = None,
    ):
        """
        Record a trade execution.

        Args:
            symbol: Stock symbol
            side: 'buy' or 'sell'
            quantity: Number of shares
            price: Price per share
            total_value: Total trade value
            timestamp: Trade timestamp
        """
        trade = {
            "timestamp": (timestamp or datetime.now()).isoformat(),
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price": price,
            "total_value": total_value,
        }

        self.trades.append(trade)
        self._save_data()

        logger.info(f"Recorded trade: {side} {quantity} {symbol} @ ${price:.2f}")

    def calculate_metrics(
        self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None
    ) -> Optional[PerformanceMetrics]:
        """
        Calculate performance metrics for a time period.

        Args:
            start_date: Start date (default: first snapshot)
            end_date: End date (default: last snapshot)

        Returns:
            PerformanceMetrics or None
        """
        if len(self.snapshots) < 2:
            logger.warning("Need at least 2 snapshots to calculate metrics")
            return None

        # Filter snapshots by date range
        filtered = self.snapshots
        if start_date:
            filtered = [s for s in filtered if s.date >= start_date]
        if end_date:
            filtered = [s for s in filtered if s.date <= end_date]

        if len(filtered) < 2:
            return None

        start_snapshot = filtered[0]
        end_snapshot = filtered[-1]

        # Calculate returns
        start_value = float(start_snapshot.total_value)
        end_value = float(end_snapshot.total_value)

        total_return = end_value - start_value
        total_return_pct = (total_return / start_value) * 100

        # Annualized return
        days = (end_snapshot.date - start_snapshot.date).days
        years = days / 365.25
        annualized_return = ((end_value / start_value) ** (1 / years) - 1) * 100 if years > 0 else 0

        # Calculate Sharpe ratio (simplified - assumes risk-free rate of 2%)
        returns = []
        for i in range(1, len(filtered)):
            prev_val = float(filtered[i - 1].total_value)
            curr_val = float(filtered[i].total_value)
            daily_return = (curr_val - prev_val) / prev_val
            returns.append(daily_return)

        if returns:
            avg_return = sum(returns) / len(returns)
            std_return = (sum((r - avg_return) ** 2 for r in returns) / len(returns)) ** 0.5
            sharpe_ratio = (
                (avg_return - 0.02 / 252) / std_return * (252**0.5) if std_return > 0 else 0
            )
        else:
            sharpe_ratio = 0

        # Calculate max drawdown
        peak = start_value
        max_dd = 0
        for snapshot in filtered:
            value = float(snapshot.total_value)
            if value > peak:
                peak = value
            drawdown = (peak - value) / peak
            if drawdown > max_dd:
                max_dd = drawdown

        # Calculate win rate from trades
        period_trades = [
            t
            for t in self.trades
            if start_snapshot.date <= datetime.fromisoformat(t["timestamp"]) <= end_snapshot.date
        ]

        # Match buy/sell pairs to calculate wins
        profitable = 0
        total_closed = 0

        # Simplified: count sells that are higher than average buy price
        buys_by_symbol = {}
        for trade in period_trades:
            symbol = trade["symbol"]
            if trade["side"] == "buy":
                if symbol not in buys_by_symbol:
                    buys_by_symbol[symbol] = []
                buys_by_symbol[symbol].append(trade["price"])
            elif trade["side"] == "sell":
                if symbol in buys_by_symbol and buys_by_symbol[symbol]:
                    avg_buy = sum(buys_by_symbol[symbol]) / len(buys_by_symbol[symbol])
                    if trade["price"] > avg_buy:
                        profitable += 1
                    total_closed += 1

        win_rate = (profitable / total_closed * 100) if total_closed > 0 else 0

        return PerformanceMetrics(
            start_date=start_snapshot.date,
            end_date=end_snapshot.date,
            start_value=start_snapshot.total_value,
            end_value=end_snapshot.total_value,
            total_return=total_return,
            total_return_pct=total_return_pct,
            annualized_return=annualized_return,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_dd * 100,
            win_rate=win_rate,
            num_trades=len(period_trades),
            profitable_trades=profitable,
        )

    def get_performance_summary(self) -> Dict:
        """
        Get a summary of performance metrics.

        Returns:
            Dict with performance summary
        """
        if not self.snapshots:
            return {"error": "No performance data available"}

        # Overall metrics
        overall = self.calculate_metrics()

        # Last 30 days
        thirty_days_ago = datetime.now() - timedelta(days=30)
        last_30 = self.calculate_metrics(start_date=thirty_days_ago)

        # Last 7 days
        seven_days_ago = datetime.now() - timedelta(days=7)
        last_7 = self.calculate_metrics(start_date=seven_days_ago)

        latest = self.snapshots[-1]

        summary = {
            "current_value": float(latest.total_value),
            "cash": float(latest.cash),
            "positions_value": float(latest.positions_value),
            "num_positions": len(latest.positions),
            "last_updated": latest.date.isoformat(),
            "overall": self._metrics_to_dict(overall) if overall else None,
            "last_30_days": self._metrics_to_dict(last_30) if last_30 else None,
            "last_7_days": self._metrics_to_dict(last_7) if last_7 else None,
            "total_trades": len(self.trades),
        }

        return summary

    def _metrics_to_dict(self, metrics: PerformanceMetrics) -> Dict:
        """Convert PerformanceMetrics to dict."""
        return {
            "start_date": metrics.start_date.isoformat(),
            "end_date": metrics.end_date.isoformat(),
            "start_value": float(metrics.start_value),
            "end_value": float(metrics.end_value),
            "total_return": metrics.total_return,
            "total_return_pct": metrics.total_return_pct,
            "annualized_return": metrics.annualized_return,
            "sharpe_ratio": metrics.sharpe_ratio,
            "max_drawdown": metrics.max_drawdown,
            "win_rate": metrics.win_rate,
            "num_trades": metrics.num_trades,
            "profitable_trades": metrics.profitable_trades,
        }

    def export_to_csv(self, output_file: str):
        """
        Export performance data to CSV.

        Args:
            output_file: Output CSV file path
        """
        if not self.snapshots:
            logger.warning("No data to export")
            return

        data = []
        for snapshot in self.snapshots:
            data.append(
                {
                    "date": snapshot.date.isoformat(),
                    "total_value": float(snapshot.total_value),
                    "cash": float(snapshot.cash),
                    "positions_value": float(snapshot.positions_value),
                    "num_positions": len(snapshot.positions),
                }
            )

        df = pd.DataFrame(data)
        df.to_csv(output_file, index=False)

        logger.info(f"Exported performance data to {output_file}")
