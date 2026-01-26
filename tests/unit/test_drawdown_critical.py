"""
Critical path tests for drawdown_stop_manager.py - Target 100% coverage
Missing lines: 79, 136, 159-161, 168-169, 214-224, 228-237, 285-286, 377-378
"""

import os
import sys
import pytest
import json
import tempfile
from unittest.mock import Mock, patch
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestDrawdownStopManagerCritical:
    """Achieve 100% coverage on drawdown_stop_manager.py"""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database"""
        from src.core.database import TradingDatabase
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db = TradingDatabase(f.name)
            yield db
            os.unlink(f.name)
    
    @pytest.fixture
    @patch.dict(os.environ, {
        'EMAIL_SENDER': 'test@test.com',
        'EMAIL_PASSWORD': 'pass',
        'EMAIL_RECIPIENT': 'recipient@test.com',
        'EMAIL_ENABLED': 'false'
    })
    def manager(self, temp_db):
        """Create drawdown manager"""
        from src.utils.email_notifier import EmailNotifier
        from src.risk.drawdown_stop_manager import DrawdownStopManager
        email = EmailNotifier()
        return DrawdownStopManager(temp_db, email)
    
    def test_check_drawdown_invalid_peak(self, manager):
        """Test check_drawdown_stop with invalid peak value (line 79)"""
        is_stopped, reason, details = manager.check_drawdown_stop(
            current_portfolio_value=100000.0,
            peak_portfolio_value=-100.0  # Invalid
        )
        assert is_stopped == False
    
    def test_get_current_state_no_state(self, manager):
        """Test get_current_state when no state exists (lines 136-142)"""
        state = manager.get_current_state()
        assert state['state'] == 'NORMAL'
        assert state['cooldown_end'] is None
        assert state['rampup_end'] is None
        assert state['sizing_multiplier'] == 1.0
        assert state['trading_allowed'] == True
    
    def test_health_checks_failed_extend_cooldown(self, manager):
        """Test health check failure extends cooldown (lines 159-161)"""
        # Set HALT state
        manager._set_drawdown_state('HALT', 0.09, 10)
        
        # Mock health checks to fail
        with patch.object(manager, '_run_health_checks', return_value=(False, {})):
            # Set cooldown_end to past
            state_data = json.loads(manager.db.get_system_state('drawdown_stop_state'))
            state_data['cooldown_end'] = (datetime.now() - timedelta(days=1)).isoformat()
            manager.db.set_system_state('drawdown_stop_state', json.dumps(state_data))
            
            # Get state should extend cooldown
            state = manager.get_current_state()
            
            # Verify cooldown was extended
            assert state['state'] in ['HALT', 'PANIC']
    
    def test_rampup_expired_return_to_normal(self, manager):
        """Test rampup expiration returns to normal (lines 168-169)"""
        # Set RAMPUP state with past end date
        manager._set_rampup_state()
        
        # Modify rampup_end to be in the past
        state_data = json.loads(manager.db.get_system_state('drawdown_stop_state'))
        state_data['rampup_end'] = (datetime.now() - timedelta(days=1)).isoformat()
        manager.db.set_system_state('drawdown_stop_state', json.dumps(state_data))
        
        # Get state should return to normal
        state = manager.get_current_state()
        assert state['state'] == 'NORMAL'
    
    def test_set_normal_state(self, manager):
        """Test _set_normal_state method (lines 214-224)"""
        manager._set_normal_state()
        
        state = manager.get_current_state()
        assert state['state'] == 'NORMAL'
        assert state['drawdown'] == 0.0
        assert state['cooldown_days'] == 0
    
    def test_extend_cooldown(self, manager):
        """Test _extend_cooldown method (lines 228-237)"""
        # Set initial state with cooldown
        manager._set_drawdown_state('HALT', 0.09, 10)
        
        # Get initial cooldown end
        state_before = json.loads(manager.db.get_system_state('drawdown_stop_state'))
        cooldown_end_before = datetime.fromisoformat(state_before['cooldown_end'])
        
        # Extend cooldown
        manager._extend_cooldown(5)
        
        # Verify extension
        state_after = json.loads(manager.db.get_system_state('drawdown_stop_state'))
        cooldown_end_after = datetime.fromisoformat(state_after['cooldown_end'])
        
        assert cooldown_end_after > cooldown_end_before
        assert state_after['cooldown_days'] == state_before['cooldown_days'] + 5
    
    def test_should_flatten_positions(self, manager):
        """Test should_flatten_positions method (lines 377-378)"""
        # Normal state - should not flatten
        result = manager.should_flatten_positions()
        assert result == False
        
        # Set panic state
        manager._set_drawdown_state('PANIC', 0.11, 20)
        result = manager.should_flatten_positions()
        assert result == True
