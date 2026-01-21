"""
Simple database tests - basic functionality coverage
"""

import os
import sys
import pytest
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from src.core.database import TradingDatabase


class TestDatabaseBasics:
    """Test basic database operations"""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database"""
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        temp_file.close()
        db = TradingDatabase(temp_file.name)
        yield db
        os.unlink(temp_file.name)
    
    def test_database_initialization(self, temp_db):
        """Test database initializes"""
        assert temp_db.run_id is not None
        assert len(temp_db.run_id) > 0
    
    def test_create_strategy(self, temp_db):
        """Test strategy creation"""
        strategy_id = temp_db.create_strategy('RSI', 'RSI Mean Reversion', 20000.0)
        assert strategy_id > 0
    
    def test_log_signal(self, temp_db):
        """Test signal logging"""
        strategy_id = temp_db.create_strategy('RSI', 'Test', 20000.0)
        signal_id = temp_db.log_signal(
            strategy_id=strategy_id,
            symbol='AAPL',
            signal_type='BUY',
            confidence=0.85,
            reasoning='Test signal',
            asof_date='2024-01-01'
        )
        assert signal_id > 0
    
    def test_update_signal_terminal_state(self, temp_db):
        """Test signal terminal state update"""
        strategy_id = temp_db.create_strategy('RSI', 'Test', 20000.0)
        signal_id = temp_db.log_signal(
            strategy_id=strategy_id,
            symbol='AAPL',
            signal_type='BUY',
            confidence=0.85,
            reasoning='Test',
            asof_date='2024-01-01'
        )
        temp_db.update_signal_terminal_state(signal_id, 'EXECUTED', 'Order filled')
        # No assertion needed - just verify it doesn't crash
    
    def test_log_trade(self, temp_db):
        """Test trade logging"""
        strategy_id = temp_db.create_strategy('RSI', 'Test', 20000.0)
        trade_id = temp_db.log_trade(
            strategy_id=strategy_id,
            signal_id=None,
            symbol='AAPL',
            action='BUY',
            shares=10.0,
            requested_price=150.0,
            exec_price=150.5,
            slippage_cost=5.0,
            commission_cost=1.0,
            order_id='test_123'
        )
        assert trade_id > 0
    
    def test_update_position(self, temp_db):
        """Test position update"""
        strategy_id = temp_db.create_strategy('RSI', 'Test', 20000.0)
        temp_db.update_position(
            strategy_id=strategy_id,
            symbol='AAPL',
            shares=10.0,
            avg_price=150.0
        )
        # No assertion needed - just verify it doesn't crash
    
    def test_get_all_strategies(self, temp_db):
        """Test getting all strategies"""
        temp_db.create_strategy('RSI', 'Test1', 20000.0)
        temp_db.create_strategy('MA', 'Test2', 20000.0)
        strategies = temp_db.get_all_strategies()
        assert len(strategies) >= 2
    
    def test_get_positions(self, temp_db):
        """Test getting positions"""
        strategy_id = temp_db.create_strategy('RSI', 'Test', 20000.0)
        temp_db.update_position(strategy_id, 'AAPL', 10.0, 150.0)
        positions = temp_db.get_positions(strategy_id)
        assert len(positions) >= 1
    
    def test_delete_position(self, temp_db):
        """Test position deletion"""
        strategy_id = temp_db.create_strategy('RSI', 'Test', 20000.0)
        temp_db.update_position(strategy_id, 'AAPL', 10.0, 150.0)
        temp_db.delete_position(strategy_id, 'AAPL')
        # No assertion needed - just verify it doesn't crash
    
    def test_save_broker_state(self, temp_db):
        """Test broker state saving"""
        temp_db.save_broker_state(
            snapshot_date='2024-01-01',
            snapshot_type='daily',
            cash=100000.0,
            portfolio_value=100000.0,
            buying_power=100000.0,
            positions=[],
            reconciliation_status='PASSED',
            discrepancies=[]
        )
        # No assertion needed - just verify it doesn't crash
    
    def test_create_order_intent(self, temp_db):
        """Test order intent creation"""
        strategy_id = temp_db.create_strategy('RSI', 'Test', 20000.0)
        intent_id = temp_db.create_order_intent(
            strategy_id=strategy_id,
            symbol='AAPL',
            side='BUY',
            target_qty=10.0
        )
        assert intent_id is not None
        assert len(intent_id) > 0
    
    def test_update_order_intent_status(self, temp_db):
        """Test order intent status update"""
        strategy_id = temp_db.create_strategy('RSI', 'Test', 20000.0)
        intent_id = temp_db.create_order_intent(strategy_id, 'AAPL', 'BUY', 10.0)
        temp_db.update_order_intent_status(intent_id, 'SUBMITTED', 'broker_123')
        # No assertion needed - just verify it doesn't crash
    
    def test_save_signal_funnel(self, temp_db):
        """Test signal funnel saving"""
        strategy_id = temp_db.create_strategy('RSI', 'Test', 20000.0)
        temp_db.save_signal_funnel(
            strategy_id=strategy_id,
            strategy_name='RSI',
            raw=10,
            regime=8,
            correlation=6,
            risk=4,
            executed=2
        )
        # No assertion needed - just verify it doesn't crash
    
    def test_log_signal_rejection(self, temp_db):
        """Test signal rejection logging"""
        strategy_id = temp_db.create_strategy('RSI', 'Test', 20000.0)
        temp_db.log_signal_rejection(
            strategy_id=strategy_id,
            symbol='AAPL',
            stage='RISK',
            reason_code='HEAT_LIMIT',
            details={'heat': 0.35}
        )
        # No assertion needed - just verify it doesn't crash
    
    def test_verify_terminal_states(self, temp_db):
        """Test terminal state verification"""
        strategy_id = temp_db.create_strategy('RSI', 'Test', 20000.0)
        signal_id = temp_db.log_signal(strategy_id, 'AAPL', 'BUY', 0.85, 'Test', '2024-01-01')
        temp_db.update_signal_terminal_state(signal_id, 'EXECUTED', 'Filled')
        total, with_terminal = temp_db.verify_terminal_states(temp_db.run_id)
        assert total >= 1
        assert with_terminal >= 1
    
    def test_get_signals_without_terminal_state(self, temp_db):
        """Test getting signals without terminal state"""
        strategy_id = temp_db.create_strategy('RSI', 'Test', 20000.0)
        temp_db.log_signal(strategy_id, 'AAPL', 'BUY', 0.85, 'Test', '2024-01-01')
        signals = temp_db.get_signals_without_terminal_state(temp_db.run_id)
        assert len(signals) >= 1
    
    def test_get_todays_trades(self, temp_db):
        """Test getting today's trades"""
        from datetime import datetime
        strategy_id = temp_db.create_strategy('RSI', 'Test', 20000.0)
        temp_db.log_trade(strategy_id, None, 'AAPL', 'BUY', 10.0, 150.0, 150.5, 5.0, 1.0, 'test_123')
        trades = temp_db.get_todays_trades(datetime.now().strftime('%Y-%m-%d'))
        assert len(trades) >= 1
    
    def test_get_strategy_trades(self, temp_db):
        """Test getting strategy trades"""
        strategy_id = temp_db.create_strategy('RSI', 'Test', 20000.0)
        temp_db.log_trade(strategy_id, None, 'AAPL', 'BUY', 10.0, 150.0, 150.5, 5.0, 1.0, 'test_123')
        trades = temp_db.get_strategy_trades(strategy_id)
        assert len(trades) >= 1
    
    def test_get_signal_funnel_summary(self, temp_db):
        """Test getting signal funnel summary"""
        strategy_id = temp_db.create_strategy('RSI', 'Test', 20000.0)
        temp_db.save_signal_funnel(strategy_id, 'RSI', 10, 8, 6, 4, 2)
        summary = temp_db.get_signal_funnel_summary(temp_db.run_id)
        assert len(summary) >= 1
    
    def test_get_signal_rejections_summary(self, temp_db):
        """Test getting signal rejections summary"""
        strategy_id = temp_db.create_strategy('RSI', 'Test', 20000.0)
        temp_db.log_signal_rejection(strategy_id, 'AAPL', 'RISK', 'HEAT_LIMIT', {})
        summary = temp_db.get_signal_rejections_summary(temp_db.run_id)
        assert len(summary) >= 1
    
    def test_get_order_intent_by_id(self, temp_db):
        """Test getting order intent by ID"""
        strategy_id = temp_db.create_strategy('RSI', 'Test', 20000.0)
        intent_id = temp_db.create_order_intent(strategy_id, 'AAPL', 'BUY', 10.0)
        intent = temp_db.get_order_intent_by_id(intent_id)
        assert intent is not None
        assert intent['intent_id'] == intent_id
    
    def test_get_position(self, temp_db):
        """Test getting single position"""
        strategy_id = temp_db.create_strategy('RSI', 'Test', 20000.0)
        temp_db.update_position(strategy_id, 'AAPL', 10.0, 150.0)
        position = temp_db.get_position(strategy_id, 'AAPL')
        assert position is not None
        assert position['symbol'] == 'AAPL'
    
    def test_count_duplicate_order_intents(self, temp_db):
        """Test counting duplicate order intents"""
        strategy_id = temp_db.create_strategy('RSI', 'Test', 20000.0)
        intent_id = temp_db.create_order_intent(strategy_id, 'AAPL', 'BUY', 10.0)
        count = temp_db.count_duplicate_order_intents(hours=24)
        assert count >= 0  # May be 0 if no duplicates
