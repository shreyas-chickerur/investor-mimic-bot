"""
Maximize coverage - comprehensive tests for all uncovered modules
Target: Push coverage as high as possible by testing actual working APIs
"""

import os
import sys
import pytest
import tempfile
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


# ============================================================================
# PNL CALCULATOR - 88 lines (requires db mock)
# ============================================================================

class TestPnLCalculatorMaximize:
    """Maximize coverage of pnl_calculator.py"""
    
    @pytest.fixture
    def mock_db(self):
        """Create mock database"""
        db = Mock()
        db.db_path = ':memory:'
        
        # Mock connection
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = []
        mock_cursor.fetchone.return_value = [0.0]
        mock_conn.cursor.return_value = mock_cursor
        db._get_connection = Mock(return_value=mock_conn)
        
        return db
    
    def test_init_and_load_positions(self, mock_db):
        from src.monitoring.pnl_calculator import PnLCalculator
        calc = PnLCalculator(mock_db)
        assert calc.db == mock_db
    
    def test_calculate_buy_trade(self, mock_db):
        from src.monitoring.pnl_calculator import PnLCalculator
        calc = PnLCalculator(mock_db)
        pnl, explanation = calc.calculate_trade_pnl(1, 'AAPL', 'BUY', 10, 150.0, 5.0)
        assert pnl == 0.0
        assert 'BUY' in explanation
    
    def test_calculate_sell_trade_with_position(self, mock_db):
        from src.monitoring.pnl_calculator import PnLCalculator
        calc = PnLCalculator(mock_db)
        # First buy
        calc.calculate_trade_pnl(1, 'AAPL', 'BUY', 10, 150.0, 0.0)
        # Then sell
        pnl, explanation = calc.calculate_trade_pnl(1, 'AAPL', 'SELL', 10, 160.0, 5.0)
        assert pnl > 0  # Should be profitable
        assert 'SELL' in explanation
    
    def test_calculate_sell_without_position(self, mock_db):
        from src.monitoring.pnl_calculator import PnLCalculator
        calc = PnLCalculator(mock_db)
        pnl, explanation = calc.calculate_trade_pnl(1, 'AAPL', 'SELL', 10, 160.0, 0.0)
        assert pnl == 0.0
        assert 'No open position' in explanation
    
    def test_get_unrealized_pnl_with_position(self, mock_db):
        from src.monitoring.pnl_calculator import PnLCalculator
        calc = PnLCalculator(mock_db)
        calc.calculate_trade_pnl(1, 'AAPL', 'BUY', 10, 150.0, 0.0)
        upnl, details = calc.get_unrealized_pnl(1, 'AAPL', 160.0)
        assert upnl == 100.0  # (160-150)*10
        assert details['shares'] == 10
    
    def test_get_unrealized_pnl_no_position(self, mock_db):
        from src.monitoring.pnl_calculator import PnLCalculator
        calc = PnLCalculator(mock_db)
        upnl, details = calc.get_unrealized_pnl(1, 'AAPL', 160.0)
        assert upnl == 0.0
        assert details['shares'] == 0
    
    def test_get_strategy_pnl_summary(self, mock_db):
        from src.monitoring.pnl_calculator import PnLCalculator
        calc = PnLCalculator(mock_db)
        calc.calculate_trade_pnl(1, 'AAPL', 'BUY', 10, 150.0, 0.0)
        summary = calc.get_strategy_pnl_summary(1, {'AAPL': 160.0})
        assert 'realized_pnl' in summary
        assert 'unrealized_pnl' in summary
        assert 'total_pnl' in summary
    
    def test_fifo_lot_matching(self, mock_db):
        from src.monitoring.pnl_calculator import PnLCalculator
        calc = PnLCalculator(mock_db)
        # Buy at different prices
        calc.calculate_trade_pnl(1, 'AAPL', 'BUY', 5, 100.0, 0.0)
        calc.calculate_trade_pnl(1, 'AAPL', 'BUY', 5, 110.0, 0.0)
        # Sell should use FIFO (first lot at 100)
        pnl, _ = calc.calculate_trade_pnl(1, 'AAPL', 'SELL', 5, 120.0, 0.0)
        assert pnl == 100.0  # (120-100)*5


# ============================================================================
# PENDING SIGNALS MANAGER - 65 lines (requires db mock)
# ============================================================================

class TestPendingSignalsManagerMaximize:
    """Maximize coverage of pending_signals_manager.py"""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database"""
        from src.core.database import TradingDatabase
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db = TradingDatabase(f.name)
            yield db
            os.unlink(f.name)
    
    def test_init_creates_table(self, temp_db):
        from src.integration.pending_signals_manager import PendingSignalsManager
        manager = PendingSignalsManager(temp_db, decay_days=3)
        assert manager.db == temp_db
        assert manager.decay_days == 3
    
    def test_add_pending_signal(self, temp_db):
        from src.integration.pending_signals_manager import PendingSignalsManager
        manager = PendingSignalsManager(temp_db)
        strategy_id = temp_db.create_strategy('RSI', 'Test', 10000.0)
        manager.add_pending_signal(strategy_id, 'AAPL', {'action': 'BUY'}, 'correlation_blocked')
    
    def test_get_pending_signals_empty(self, temp_db):
        from src.integration.pending_signals_manager import PendingSignalsManager
        manager = PendingSignalsManager(temp_db)
        pending = manager.get_pending_signals()
        assert pending == []
    
    def test_get_pending_signals_with_data(self, temp_db):
        from src.integration.pending_signals_manager import PendingSignalsManager
        manager = PendingSignalsManager(temp_db)
        strategy_id = temp_db.create_strategy('RSI', 'Test', 10000.0)
        manager.add_pending_signal(strategy_id, 'AAPL', {'action': 'BUY'}, 'test_reason')
        pending = manager.get_pending_signals()
        assert len(pending) > 0
    
    def test_get_pending_signals_by_strategy(self, temp_db):
        from src.integration.pending_signals_manager import PendingSignalsManager
        manager = PendingSignalsManager(temp_db)
        strategy_id = temp_db.create_strategy('RSI', 'Test', 10000.0)
        manager.add_pending_signal(strategy_id, 'AAPL', {'action': 'BUY'}, 'test')
        pending = manager.get_pending_signals(strategy_id=strategy_id)
        assert len(pending) > 0
    
    def test_update_pending_status(self, temp_db):
        from src.integration.pending_signals_manager import PendingSignalsManager
        manager = PendingSignalsManager(temp_db)
        strategy_id = temp_db.create_strategy('RSI', 'Test', 10000.0)
        manager.add_pending_signal(strategy_id, 'AAPL', {'action': 'BUY'}, 'test')
        pending = manager.get_pending_signals()
        if pending:
            manager.update_pending_status(pending[0]['id'], 'EXECUTED')
    
    def test_cleanup_expired(self, temp_db):
        from src.integration.pending_signals_manager import PendingSignalsManager
        manager = PendingSignalsManager(temp_db, decay_days=0)
        strategy_id = temp_db.create_strategy('RSI', 'Test', 10000.0)
        manager.add_pending_signal(strategy_id, 'AAPL', {'action': 'BUY'}, 'test')
        manager.cleanup_expired()


# ============================================================================
# CASH MANAGER - 56 lines
# ============================================================================

class TestCashManagerMaximize:
    """Maximize coverage of cash_manager.py"""
    
    def test_init_equal_allocation(self):
        from src.integration.cash_manager import CashManager
        manager = CashManager(100000.0, 5)
        assert manager.total_cash == 100000.0
        assert manager.allocated_cash[1] == 20000.0
        assert manager.reserved_cash == 0
    
    def test_check_available_cash(self):
        from src.integration.cash_manager import CashManager
        manager = CashManager(100000.0, 5)
        assert manager.check_available_cash(1, 10000.0) == True
        assert manager.check_available_cash(1, 30000.0) == False
    
    def test_reserve_and_release_cash(self):
        from src.integration.cash_manager import CashManager
        manager = CashManager(100000.0, 5)
        assert manager.reserve_cash(1, 10000.0) == True
        assert manager.allocated_cash[1] == 10000.0
        manager.release_cash(1, 5000.0)
        assert manager.allocated_cash[1] == 15000.0
    
    def test_set_allocations(self):
        from src.integration.cash_manager import CashManager
        manager = CashManager(100000.0, 5)
        new_alloc = {1: 30000.0, 2: 25000.0, 3: 20000.0, 4: 15000.0, 5: 10000.0}
        manager.set_allocations(new_alloc)
        assert manager.allocated_cash[1] == 30000.0
    
    def test_set_allocations_with_exposures(self):
        from src.integration.cash_manager import CashManager
        manager = CashManager(100000.0, 5)
        alloc = {1: 30000.0, 2: 25000.0, 3: 20000.0, 4: 15000.0, 5: 10000.0}
        exposures = {1: 5000.0, 2: 3000.0, 3: 2000.0, 4: 1000.0, 5: 500.0}
        manager.set_allocations(alloc, exposures)
    
    def test_get_status(self):
        from src.integration.cash_manager import CashManager
        manager = CashManager(100000.0, 5)
        status = manager.get_status()
        assert 'total_cash' in status
        assert 'reserved_cash' in status
    
    def test_prioritize_trades(self):
        from src.integration.cash_manager import CashManager
        manager = CashManager(100000.0, 5)
        trades = [
            {'strategy_id': 1, 'cost': 5000.0, 'confidence': 0.9},
            {'strategy_id': 2, 'cost': 15000.0, 'confidence': 0.8}
        ]
        approved = manager.prioritize_trades(trades)
        assert isinstance(approved, list)


# ============================================================================
# UNIVERSE PROVIDER - 56 lines
# ============================================================================

class TestUniverseProviderMaximize:
    """Maximize coverage of universe_provider.py"""
    
    def test_get_universe(self):
        from src.data.universe_provider import UniverseProvider
        provider = UniverseProvider()
        universe = provider.get_universe()
        assert isinstance(universe, list)
        assert len(universe) > 0
        assert all(isinstance(s, str) for s in universe)


# ============================================================================
# EXECUTION COSTS - Additional comprehensive tests
# ============================================================================

class TestExecutionCostsAdditional:
    """Additional execution costs tests"""
    
    def test_different_slippage_levels(self):
        from src.utils.execution_costs import ExecutionCostModel
        model_low = ExecutionCostModel(slippage_bps=5.0)
        model_high = ExecutionCostModel(slippage_bps=15.0)
        
        _, slip_low, _, _ = model_low.calculate_execution_price(100.0, 'BUY', 100)
        _, slip_high, _, _ = model_high.calculate_execution_price(100.0, 'BUY', 100)
        
        assert slip_high > slip_low
    
    def test_commission_scaling(self):
        from src.utils.execution_costs import ExecutionCostModel
        model = ExecutionCostModel(commission_per_share=0.01)
        
        _, _, comm_small, _ = model.calculate_execution_price(100.0, 'BUY', 10)
        _, _, comm_large, _ = model.calculate_execution_price(100.0, 'BUY', 100)
        
        assert comm_large == 10 * comm_small


# ============================================================================
# DATA FETCHERS - 337 lines total
# ============================================================================

class TestDataFetchersMaximize:
    """Maximize coverage of data fetchers"""
    
    @patch.dict(os.environ, {'ALPACA_API_KEY': 'test', 'ALPACA_SECRET_KEY': 'test'})
    def test_alpaca_fetcher(self):
        from src.data.alpaca_data_fetcher import AlpacaDataFetcher
        fetcher = AlpacaDataFetcher()
        assert fetcher is not None
    
    @patch.dict(os.environ, {'ALPHA_VANTAGE_API_KEY': 'test'})
    def test_alpha_vantage_fetcher(self):
        from src.data.alpha_vantage_fetcher import AlphaVantageFetcher
        fetcher = AlphaVantageFetcher()
        assert fetcher is not None
    
    @patch.dict(os.environ, {'ALPHA_VANTAGE_API_KEY': 'test'})
    def test_vix_fetcher(self):
        from src.data.vix_data_fetcher import VIXDataFetcher
        fetcher = VIXDataFetcher()
        assert fetcher is not None


# ============================================================================
# EMAIL NOTIFIER - 126 lines
# ============================================================================

class TestEmailNotifierMaximize:
    """Maximize coverage of email_notifier.py"""
    
    @patch.dict(os.environ, {
        'EMAIL_SENDER': 'test@test.com',
        'EMAIL_PASSWORD': 'pass',
        'EMAIL_RECIPIENT': 'recipient@test.com',
        'EMAIL_ENABLED': 'false'
    })
    def test_email_notifier_init(self):
        from src.utils.email_notifier import EmailNotifier
        notifier = EmailNotifier()
        assert notifier is not None
    
    @patch.dict(os.environ, {
        'EMAIL_SENDER': 'test@test.com',
        'EMAIL_PASSWORD': 'pass',
        'EMAIL_RECIPIENT': 'recipient@test.com',
        'EMAIL_ENABLED': 'false'
    })
    def test_send_alert(self):
        from src.utils.email_notifier import EmailNotifier
        notifier = EmailNotifier()
        notifier.send_alert('Test', 'Body')


# ============================================================================
# PORTFOLIO BACKTESTER - 255 lines
# ============================================================================

class TestPortfolioBacktesterMaximize:
    """Maximize coverage of portfolio_backtester.py"""
    
    def test_init(self):
        from src.integration.portfolio_backtester import PortfolioBacktester
        backtester = PortfolioBacktester()
        assert backtester is not None


# ============================================================================
# CONFIG MODULES - config_loader.py
# ============================================================================

class TestConfigModulesMaximize:
    """Maximize coverage of config modules"""

    def test_config_loader_import(self):
        from src.utils.config_loader import ConfigLoader
        loader = ConfigLoader()
        assert loader is not None
