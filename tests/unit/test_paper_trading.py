"""
Unit Tests for Paper Trading Module

Tests paper trading engine functionality.
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from services.paper_trading import PaperTradingEngine, PaperPosition


class TestPaperTradingEngine:
    """Unit tests for PaperTradingEngine."""

    def test_initialization(self):
        """Test engine initializes with correct capital."""
        engine = PaperTradingEngine(initial_capital=100000)
        assert engine.initial_capital == 100000
        assert engine.cash == 100000
        assert len(engine.positions) == 0
        assert len(engine.trades) == 0

    def test_buy_order_success(self):
        """Test successful buy order."""
        engine = PaperTradingEngine(initial_capital=100000)
        success = engine.place_order("AAPL", "BUY", 100, 150.0)
        
        assert success is True
        assert "AAPL" in engine.positions
        assert engine.positions["AAPL"].quantity == 100
        assert engine.positions["AAPL"].avg_cost == 150.0
        assert engine.cash == 85000  # 100000 - (100 * 150)

    def test_buy_order_insufficient_funds(self):
        """Test buy order with insufficient funds."""
        engine = PaperTradingEngine(initial_capital=1000)
        success = engine.place_order("AAPL", "BUY", 100, 150.0)
        
        assert success is False
        assert "AAPL" not in engine.positions
        assert engine.cash == 1000

    def test_sell_order_success(self):
        """Test successful sell order."""
        engine = PaperTradingEngine(initial_capital=100000)
        engine.place_order("AAPL", "BUY", 100, 150.0)
        success = engine.place_order("AAPL", "SELL", 50, 160.0)
        
        assert success is True
        assert engine.positions["AAPL"].quantity == 50
        assert engine.cash == 93000  # 85000 + (50 * 160)

    def test_sell_order_no_position(self):
        """Test sell order without position."""
        engine = PaperTradingEngine(initial_capital=100000)
        success = engine.place_order("AAPL", "SELL", 50, 160.0)
        
        assert success is False

    def test_sell_order_insufficient_shares(self):
        """Test sell order with insufficient shares."""
        engine = PaperTradingEngine(initial_capital=100000)
        engine.place_order("AAPL", "BUY", 100, 150.0)
        success = engine.place_order("AAPL", "SELL", 150, 160.0)
        
        assert success is False
        assert engine.positions["AAPL"].quantity == 100

    def test_sell_all_shares(self):
        """Test selling all shares removes position."""
        engine = PaperTradingEngine(initial_capital=100000)
        engine.place_order("AAPL", "BUY", 100, 150.0)
        engine.place_order("AAPL", "SELL", 100, 160.0)
        
        assert "AAPL" not in engine.positions

    def test_multiple_buys_average_cost(self):
        """Test multiple buys calculate correct average cost."""
        engine = PaperTradingEngine(initial_capital=100000)
        engine.place_order("AAPL", "BUY", 100, 150.0)
        engine.place_order("AAPL", "BUY", 100, 160.0)
        
        assert engine.positions["AAPL"].quantity == 200
        assert engine.positions["AAPL"].avg_cost == 155.0  # (150 + 160) / 2

    def test_update_prices(self):
        """Test updating position prices."""
        engine = PaperTradingEngine(initial_capital=100000)
        engine.place_order("AAPL", "BUY", 100, 150.0)
        engine.update_prices({"AAPL": 160.0})
        
        assert engine.positions["AAPL"].current_price == 160.0

    def test_portfolio_value(self):
        """Test portfolio value calculation."""
        engine = PaperTradingEngine(initial_capital=100000)
        engine.place_order("AAPL", "BUY", 100, 150.0)
        engine.update_prices({"AAPL": 160.0})
        
        portfolio_value = engine.get_portfolio_value()
        expected = 85000 + (100 * 160.0)  # cash + position value
        assert portfolio_value == expected

    def test_performance_metrics(self):
        """Test performance metrics calculation."""
        engine = PaperTradingEngine(initial_capital=100000)
        engine.place_order("AAPL", "BUY", 100, 150.0)
        engine.update_prices({"AAPL": 160.0})
        
        metrics = engine.get_performance_metrics()
        
        assert "total_value" in metrics
        assert "cash" in metrics
        assert "positions_value" in metrics
        assert "total_return" in metrics
        assert "unrealized_pnl" in metrics
        assert metrics["num_positions"] == 1
        assert metrics["num_trades"] == 1

    def test_positions_summary(self):
        """Test positions summary."""
        engine = PaperTradingEngine(initial_capital=100000)
        engine.place_order("AAPL", "BUY", 100, 150.0)
        engine.update_prices({"AAPL": 160.0})
        
        summary = engine.get_positions_summary()
        
        assert len(summary) == 1
        assert summary[0]["ticker"] == "AAPL"
        assert summary[0]["quantity"] == 100
        assert summary[0]["avg_cost"] == 150.0
        assert summary[0]["current_price"] == 160.0
        assert summary[0]["unrealized_pnl"] == 1000.0  # (160 - 150) * 100


class TestPaperPosition:
    """Unit tests for PaperPosition."""

    def test_position_creation(self):
        """Test position creation."""
        from datetime import datetime
        
        pos = PaperPosition(
            ticker="AAPL", quantity=100, avg_cost=150.0, entry_date=datetime.now(), current_price=150.0
        )
        
        assert pos.ticker == "AAPL"
        assert pos.quantity == 100
        assert pos.avg_cost == 150.0

    def test_market_value(self):
        """Test market value calculation."""
        from datetime import datetime
        
        pos = PaperPosition(
            ticker="AAPL", quantity=100, avg_cost=150.0, entry_date=datetime.now(), current_price=160.0
        )
        
        assert pos.market_value == 16000.0

    def test_cost_basis(self):
        """Test cost basis calculation."""
        from datetime import datetime
        
        pos = PaperPosition(
            ticker="AAPL", quantity=100, avg_cost=150.0, entry_date=datetime.now(), current_price=160.0
        )
        
        assert pos.cost_basis == 15000.0

    def test_unrealized_pnl(self):
        """Test unrealized P&L calculation."""
        from datetime import datetime
        
        pos = PaperPosition(
            ticker="AAPL", quantity=100, avg_cost=150.0, entry_date=datetime.now(), current_price=160.0
        )
        
        assert pos.unrealized_pnl == 1000.0

    def test_unrealized_pnl_pct(self):
        """Test unrealized P&L percentage."""
        from datetime import datetime
        
        pos = PaperPosition(
            ticker="AAPL", quantity=100, avg_cost=150.0, entry_date=datetime.now(), current_price=160.0
        )
        
        assert abs(pos.unrealized_pnl_pct - 0.0667) < 0.001  # ~6.67%


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
