"""
Comprehensive Backtesting Engine

Tests the investment strategy on historical data (2010-2024, excluding COVID).
Compares predicted performance vs actual returns and generates detailed analytics.
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class BacktestConfig:
    """Backtesting configuration."""

    start_date: datetime
    end_date: datetime
    initial_capital: float = 100000.0
    exclude_periods: List[Tuple[datetime, datetime]] = None  # COVID, etc.
    rebalance_frequency: str = "weekly"  # weekly, monthly
    transaction_cost_pct: float = 0.001  # 0.1% per trade
    slippage_pct: float = 0.0005  # 0.05% slippage
    max_positions: int = 20

    def __post_init__(self):
        if self.exclude_periods is None:
            # Exclude COVID period (March 2020 - June 2020)
            self.exclude_periods = [(datetime(2020, 3, 1), datetime(2020, 6, 30))]


@dataclass
class Trade:
    """Individual trade record."""

    date: datetime
    symbol: str
    action: str  # BUY, SELL
    quantity: float
    price: float
    value: float
    commission: float
    reason: str  # ENTRY, EXIT, REBALANCE, STOP_LOSS


@dataclass
class Position:
    """Portfolio position."""

    symbol: str
    quantity: float
    entry_price: float
    entry_date: datetime
    current_price: float
    current_value: float
    unrealized_pnl: float
    unrealized_pnl_pct: float


@dataclass
class BacktestResult:
    """Backtesting results."""

    config: BacktestConfig
    trades: List[Trade]
    daily_portfolio_values: pd.Series
    daily_returns: pd.Series
    positions_history: List[Dict]

    # Performance metrics
    total_return: float
    annualized_return: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float

    # Comparison metrics
    spy_return: float
    alpha: float
    beta: float

    # Trade statistics
    total_trades: int
    winning_trades: int
    losing_trades: int
    avg_win: float
    avg_loss: float
    avg_hold_period: float


class BacktestEngine:
    """
    Comprehensive backtesting engine for strategy validation.
    """

    def __init__(self, config: BacktestConfig):
        """
        Initialize backtest engine.

        Args:
            config: Backtesting configuration
        """
        self.config = config
        self.cash = config.initial_capital
        self.positions: Dict[str, Position] = {}
        self.trades: List[Trade] = []
        self.portfolio_values: List[Tuple[datetime, float]] = []
        self.positions_history: List[Dict] = []

    def is_excluded_period(self, date: datetime) -> bool:
        """Check if date falls in excluded period."""
        for start, end in self.config.exclude_periods:
            if start <= date <= end:
                return True
        return False

    def calculate_portfolio_value(self, current_prices: Dict[str, float]) -> float:
        """Calculate total portfolio value."""
        positions_value = sum(
            pos.quantity * current_prices.get(pos.symbol, pos.current_price) for pos in self.positions.values()
        )
        return self.cash + positions_value

    def execute_trade(
        self,
        date: datetime,
        symbol: str,
        action: str,
        quantity: float,
        price: float,
        reason: str = "SIGNAL",
    ) -> Optional[Trade]:
        """
        Execute a trade with transaction costs.

        Args:
            date: Trade date
            symbol: Stock symbol
            action: BUY or SELL
            quantity: Number of shares
            price: Execution price
            reason: Trade reason

        Returns:
            Trade object or None if failed
        """
        # Apply slippage
        if action == "BUY":
            execution_price = price * (1 + self.config.slippage_pct)
        else:
            execution_price = price * (1 - self.config.slippage_pct)

        value = quantity * execution_price
        commission = value * self.config.transaction_cost_pct

        if action == "BUY":
            total_cost = value + commission
            if total_cost > self.cash:
                logger.warning(f"Insufficient cash for {symbol}: need ${total_cost:.2f}, have ${self.cash:.2f}")
                return None

            self.cash -= total_cost

            if symbol in self.positions:
                # Add to existing position
                pos = self.positions[symbol]
                new_quantity = pos.quantity + quantity
                new_entry_price = ((pos.quantity * pos.entry_price) + (quantity * execution_price)) / new_quantity
                pos.quantity = new_quantity
                pos.entry_price = new_entry_price
            else:
                # New position
                self.positions[symbol] = Position(
                    symbol=symbol,
                    quantity=quantity,
                    entry_price=execution_price,
                    entry_date=date,
                    current_price=execution_price,
                    current_value=value,
                    unrealized_pnl=0.0,
                    unrealized_pnl_pct=0.0,
                )

        elif action == "SELL":
            if symbol not in self.positions:
                logger.warning(f"Cannot sell {symbol}: no position")
                return None

            pos = self.positions[symbol]
            if quantity > pos.quantity:
                quantity = pos.quantity  # Sell all available

            self.cash += value - commission
            pos.quantity -= quantity

            if pos.quantity <= 0:
                del self.positions[symbol]

        # Record trade
        trade = Trade(
            date=date,
            symbol=symbol,
            action=action,
            quantity=quantity,
            price=execution_price,
            value=value,
            commission=commission,
            reason=reason,
        )
        self.trades.append(trade)

        return trade

    def update_positions(self, date: datetime, current_prices: Dict[str, float]):
        """Update position values with current prices."""
        for symbol, pos in self.positions.items():
            if symbol in current_prices:
                pos.current_price = current_prices[symbol]
                pos.current_value = pos.quantity * pos.current_price
                pos.unrealized_pnl = pos.current_value - (pos.quantity * pos.entry_price)
                pos.unrealized_pnl_pct = (pos.unrealized_pnl / (pos.quantity * pos.entry_price)) * 100

    def record_portfolio_state(self, date: datetime, current_prices: Dict[str, float]):
        """Record current portfolio state."""
        self.update_positions(date, current_prices)
        portfolio_value = self.calculate_portfolio_value(current_prices)
        self.portfolio_values.append((date, portfolio_value))

        # Record positions snapshot
        self.positions_history.append(
            {
                "date": date,
                "cash": self.cash,
                "positions": {
                    symbol: {
                        "quantity": pos.quantity,
                        "price": pos.current_price,
                        "value": pos.current_value,
                        "pnl_pct": pos.unrealized_pnl_pct,
                    }
                    for symbol, pos in self.positions.items()
                },
                "total_value": portfolio_value,
            }
        )

    def calculate_metrics(self, spy_returns: pd.Series) -> Dict:
        """Calculate performance metrics."""
        # Convert to DataFrame
        df = pd.DataFrame(self.portfolio_values, columns=["date", "value"])
        df.set_index("date", inplace=True)
        df["returns"] = df["value"].pct_change()

        # Total return
        total_return = (df["value"].iloc[-1] - self.config.initial_capital) / self.config.initial_capital

        # Annualized return
        days = (df.index[-1] - df.index[0]).days
        years = days / 365.25
        annualized_return = (1 + total_return) ** (1 / years) - 1

        # Sharpe ratio (assuming 2% risk-free rate)
        risk_free_rate = 0.02
        excess_returns = df["returns"] - (risk_free_rate / 252)
        sharpe_ratio = np.sqrt(252) * excess_returns.mean() / df["returns"].std()

        # Sortino ratio (downside deviation)
        downside_returns = df["returns"][df["returns"] < 0]
        downside_std = downside_returns.std()
        sortino_ratio = np.sqrt(252) * excess_returns.mean() / downside_std if downside_std > 0 else 0

        # Maximum drawdown
        cumulative = (1 + df["returns"]).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = drawdown.min()

        # Trade statistics
        winning_trades = [t for t in self.trades if self._is_winning_trade(t)]
        losing_trades = [t for t in self.trades if self._is_losing_trade(t)]

        win_rate = len(winning_trades) / len(self.trades) if self.trades else 0

        avg_win = np.mean([self._trade_pnl(t) for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([abs(self._trade_pnl(t)) for t in losing_trades]) if losing_trades else 0

        profit_factor = (
            (sum([self._trade_pnl(t) for t in winning_trades]) / sum([abs(self._trade_pnl(t)) for t in losing_trades]))
            if losing_trades
            else 0
        )

        # Alpha and Beta vs SPY
        aligned_returns = df["returns"].align(spy_returns, join="inner")[0]
        aligned_spy = df["returns"].align(spy_returns, join="inner")[1]

        if len(aligned_returns) > 0:
            covariance = np.cov(aligned_returns, aligned_spy)[0][1]
            spy_variance = np.var(aligned_spy)
            beta = covariance / spy_variance if spy_variance > 0 else 1.0
            alpha = annualized_return - (risk_free_rate + beta * (spy_returns.mean() * 252 - risk_free_rate))
        else:
            beta = 1.0
            alpha = 0.0

        return {
            "total_return": total_return,
            "annualized_return": annualized_return,
            "sharpe_ratio": sharpe_ratio,
            "sortino_ratio": sortino_ratio,
            "max_drawdown": max_drawdown,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "total_trades": len(self.trades),
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "alpha": alpha,
            "beta": beta,
            "daily_returns": df["returns"],
        }

    def _is_winning_trade(self, trade: Trade) -> bool:
        """Check if trade was profitable."""
        # Simplified - would need to match buy/sell pairs
        return trade.action == "SELL" and self._trade_pnl(trade) > 0

    def _is_losing_trade(self, trade: Trade) -> bool:
        """Check if trade was a loss."""
        return trade.action == "SELL" and self._trade_pnl(trade) < 0

    def _trade_pnl(self, trade: Trade) -> float:
        """Calculate trade P&L (simplified)."""
        # This is simplified - in reality would need to track entry/exit pairs
        if trade.action == "SELL":
            # Estimate P&L based on average entry price
            return trade.value * 0.1  # Placeholder
        return 0.0

    def generate_report(self, metrics: Dict, spy_return: float) -> str:
        """Generate backtest report."""
        report = f"""
{'=' * 80}
BACKTEST RESULTS
{'=' * 80}

PERIOD: {self.config.start_date.strftime('%Y-%m-%d')} to {self.config.end_date.strftime('%Y-%m-%d')}
INITIAL CAPITAL: ${self.config.initial_capital:,.2f}
FINAL VALUE: ${self.portfolio_values[-1][1]:,.2f}

PERFORMANCE METRICS:
  Total Return:        {metrics['total_return']:+.2%}
  Annualized Return:   {metrics['annualized_return']:+.2%}
  Sharpe Ratio:        {metrics['sharpe_ratio']:.2f}
  Sortino Ratio:       {metrics['sortino_ratio']:.2f}
  Maximum Drawdown:    {metrics['max_drawdown']:.2%}

COMPARISON VS SPY:
  SPY Return:          {spy_return:+.2%}
  Alpha:               {metrics['alpha']:+.2%}
  Beta:                {metrics['beta']:.2f}
  Outperformance:      {metrics['total_return'] - spy_return:+.2%}

TRADE STATISTICS:
  Total Trades:        {metrics['total_trades']}
  Winning Trades:      {metrics['winning_trades']} ({metrics['win_rate']:.1%})
  Losing Trades:       {metrics['losing_trades']}
  Profit Factor:       {metrics['profit_factor']:.2f}
  Avg Win:             ${metrics['avg_win']:,.2f}
  Avg Loss:            ${metrics['avg_loss']:,.2f}

{'=' * 80}
"""
        return report

    def save_results(self, output_dir: Path, metrics: Dict):
        """Save backtest results to files."""
        output_dir.mkdir(parents=True, exist_ok=True)

        # Save trades
        trades_df = pd.DataFrame(
            [
                {
                    "date": t.date,
                    "symbol": t.symbol,
                    "action": t.action,
                    "quantity": t.quantity,
                    "price": t.price,
                    "value": t.value,
                    "commission": t.commission,
                    "reason": t.reason,
                }
                for t in self.trades
            ]
        )
        trades_df.to_csv(output_dir / "trades.csv", index=False)

        # Save portfolio values
        portfolio_df = pd.DataFrame(self.portfolio_values, columns=["date", "value"])
        portfolio_df.to_csv(output_dir / "portfolio_values.csv", index=False)

        # Save metrics
        with open(output_dir / "metrics.json", "w") as f:
            # Convert non-serializable types
            serializable_metrics = {
                k: float(v) if isinstance(v, (np.floating, np.integer)) else v
                for k, v in metrics.items()
                if k != "daily_returns"
            }
            json.dump(serializable_metrics, f, indent=2)

        logger.info(f"Backtest results saved to {output_dir}")
