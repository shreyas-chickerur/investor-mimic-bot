"""
Paper Trading Mode

Simulates real trades without risking capital, tracking hypothetical portfolio performance.
"""

from typing import Dict, List, Optional
from datetime import datetime
from decimal import Decimal
from dataclasses import dataclass, field
from utils.enhanced_logging import get_logger
from utils.validators import trade_validator
from db.connection_pool import get_db_session

logger = get_logger(__name__)


@dataclass
class PaperPosition:
    """Represents a paper trading position."""
    ticker: str
    quantity: float
    avg_cost: float
    entry_date: datetime
    current_price: float = 0.0
    
    @property
    def market_value(self) -> float:
        return self.quantity * self.current_price
    
    @property
    def cost_basis(self) -> float:
        return self.quantity * self.avg_cost
    
    @property
    def unrealized_pnl(self) -> float:
        return self.market_value - self.cost_basis
    
    @property
    def unrealized_pnl_pct(self) -> float:
        return (self.unrealized_pnl / self.cost_basis) if self.cost_basis > 0 else 0.0


@dataclass
class PaperTrade:
    """Represents a paper trade."""
    ticker: str
    action: str
    quantity: float
    price: float
    timestamp: datetime
    commission: float = 0.0
    
    @property
    def total_value(self) -> float:
        return self.quantity * self.price + self.commission


class PaperTradingEngine:
    """Paper trading engine for simulated trading."""
    
    def __init__(self, initial_capital: float = 100000.0):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions: Dict[str, PaperPosition] = {}
        self.trades: List[PaperTrade] = []
        self.daily_values: List[Dict] = []
        
        logger.info(f"Paper trading initialized with ${initial_capital:,.2f}")
    
    def place_order(
        self,
        ticker: str,
        action: str,
        quantity: float,
        price: float,
        commission: float = 0.0
    ) -> bool:
        """
        Place a paper trade order.
        
        Args:
            ticker: Stock ticker
            action: 'BUY' or 'SELL'
            quantity: Number of shares
            price: Price per share
            commission: Trading commission
            
        Returns:
            True if order successful, False otherwise
        """
        try:
            # Validate trade
            validated = trade_validator.validate_trade(ticker, action, quantity, price)
            
            if action == 'BUY':
                return self._execute_buy(
                    validated['ticker'],
                    validated['quantity'],
                    validated['price'],
                    commission
                )
            else:
                return self._execute_sell(
                    validated['ticker'],
                    validated['quantity'],
                    validated['price'],
                    commission
                )
        
        except Exception as e:
            logger.error(f"Paper trade failed: {e}", error=e)
            return False
    
    def _execute_buy(self, ticker: str, quantity: float, price: float, commission: float) -> bool:
        """Execute paper buy order."""
        total_cost = quantity * price + commission
        
        if total_cost > self.cash:
            logger.warning(f"Insufficient cash for {ticker}: need ${total_cost:,.2f}, have ${self.cash:,.2f}")
            return False
        
        # Update cash
        self.cash -= total_cost
        
        # Update or create position
        if ticker in self.positions:
            pos = self.positions[ticker]
            new_quantity = pos.quantity + quantity
            new_avg_cost = (pos.cost_basis + quantity * price) / new_quantity
            pos.quantity = new_quantity
            pos.avg_cost = new_avg_cost
        else:
            self.positions[ticker] = PaperPosition(
                ticker=ticker,
                quantity=quantity,
                avg_cost=price,
                entry_date=datetime.now(),
                current_price=price
            )
        
        # Record trade
        trade = PaperTrade(
            ticker=ticker,
            action='BUY',
            quantity=quantity,
            price=price,
            timestamp=datetime.now(),
            commission=commission
        )
        self.trades.append(trade)
        
        # Log to database
        self._log_trade_to_db(trade)
        
        logger.info(f"Paper BUY: {quantity} {ticker} @ ${price:.2f}")
        return True
    
    def _execute_sell(self, ticker: str, quantity: float, price: float, commission: float) -> bool:
        """Execute paper sell order."""
        if ticker not in self.positions:
            logger.warning(f"No position in {ticker} to sell")
            return False
        
        pos = self.positions[ticker]
        if quantity > pos.quantity:
            logger.warning(f"Insufficient shares: trying to sell {quantity}, have {pos.quantity}")
            return False
        
        # Calculate proceeds
        proceeds = quantity * price - commission
        self.cash += proceeds
        
        # Update position
        pos.quantity -= quantity
        if pos.quantity == 0:
            del self.positions[ticker]
        
        # Record trade
        trade = PaperTrade(
            ticker=ticker,
            action='SELL',
            quantity=quantity,
            price=price,
            timestamp=datetime.now(),
            commission=commission
        )
        self.trades.append(trade)
        
        # Log to database
        self._log_trade_to_db(trade)
        
        logger.info(f"Paper SELL: {quantity} {ticker} @ ${price:.2f}")
        return True
    
    def update_prices(self, prices: Dict[str, float]):
        """Update current prices for all positions."""
        for ticker, price in prices.items():
            if ticker in self.positions:
                self.positions[ticker].current_price = price
    
    def get_portfolio_value(self) -> float:
        """Calculate total portfolio value."""
        positions_value = sum(pos.market_value for pos in self.positions.values())
        return self.cash + positions_value
    
    def get_performance_metrics(self) -> Dict:
        """Calculate performance metrics."""
        total_value = self.get_portfolio_value()
        total_return = (total_value - self.initial_capital) / self.initial_capital
        
        positions_value = sum(pos.market_value for pos in self.positions.values())
        total_unrealized_pnl = sum(pos.unrealized_pnl for pos in self.positions.values())
        
        return {
            'total_value': total_value,
            'cash': self.cash,
            'positions_value': positions_value,
            'total_return': total_return,
            'total_return_pct': total_return * 100,
            'unrealized_pnl': total_unrealized_pnl,
            'num_positions': len(self.positions),
            'num_trades': len(self.trades)
        }
    
    def get_positions_summary(self) -> List[Dict]:
        """Get summary of all positions."""
        return [
            {
                'ticker': pos.ticker,
                'quantity': pos.quantity,
                'avg_cost': pos.avg_cost,
                'current_price': pos.current_price,
                'market_value': pos.market_value,
                'unrealized_pnl': pos.unrealized_pnl,
                'unrealized_pnl_pct': pos.unrealized_pnl_pct * 100,
                'entry_date': pos.entry_date.isoformat()
            }
            for pos in self.positions.values()
        ]
    
    def _log_trade_to_db(self, trade: PaperTrade):
        """Log paper trade to database."""
        try:
            with get_db_session() as session:
                session.execute(
                    """
                    INSERT INTO trade_history 
                    (ticker, action, quantity, price, total_value, commission, trade_date, status, notes)
                    VALUES (:ticker, :action, :quantity, :price, :total_value, :commission, :trade_date, :status, :notes)
                    """,
                    {
                        'ticker': trade.ticker,
                        'action': trade.action,
                        'quantity': trade.quantity,
                        'price': trade.price,
                        'total_value': trade.total_value,
                        'commission': trade.commission,
                        'trade_date': trade.timestamp,
                        'status': 'paper_trade',
                        'notes': 'Simulated paper trade'
                    }
                )
        except Exception as e:
            logger.error(f"Failed to log paper trade to DB: {e}")
    
    def record_daily_snapshot(self):
        """Record daily portfolio snapshot."""
        metrics = self.get_performance_metrics()
        snapshot = {
            'date': datetime.now().date(),
            'total_value': metrics['total_value'],
            'cash': metrics['cash'],
            'positions_value': metrics['positions_value'],
            'total_return': metrics['total_return'],
            'num_positions': metrics['num_positions']
        }
        self.daily_values.append(snapshot)
        
        # Log to database
        try:
            with get_db_session() as session:
                session.execute(
                    """
                    INSERT INTO performance_metrics 
                    (date, portfolio_value, cash_balance, total_value, daily_return, cumulative_return)
                    VALUES (:date, :portfolio_value, :cash_balance, :total_value, :daily_return, :cumulative_return)
                    ON CONFLICT (date) DO UPDATE SET
                        portfolio_value = EXCLUDED.portfolio_value,
                        cash_balance = EXCLUDED.cash_balance,
                        total_value = EXCLUDED.total_value,
                        cumulative_return = EXCLUDED.cumulative_return
                    """,
                    {
                        'date': snapshot['date'],
                        'portfolio_value': snapshot['positions_value'],
                        'cash_balance': snapshot['cash'],
                        'total_value': snapshot['total_value'],
                        'daily_return': 0.0,  # Calculate from previous day
                        'cumulative_return': snapshot['total_return']
                    }
                )
        except Exception as e:
            logger.error(f"Failed to log daily snapshot: {e}")


# Global paper trading engine
_paper_engine = None


def get_paper_engine(initial_capital: float = 100000.0) -> PaperTradingEngine:
    """Get global paper trading engine."""
    global _paper_engine
    if _paper_engine is None:
        _paper_engine = PaperTradingEngine(initial_capital)
    return _paper_engine
