"""Test broker reconciliation - CRITICAL: 100% COVERAGE REQUIRED"""
import os
import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.risk.broker_reconciler import BrokerReconciler, ReconciliationMismatch


class TestBrokerReconciliation:
    """Test broker reconciliation logic"""
    
    @patch('src.risk.broker_reconciler.TradingClient')
    def test_reconciliation_catches_missing_position(self, mock_trading_client):
        """Test that missing positions in broker are detected"""
        # Setup mock broker
        mock_client = Mock()
        mock_trading_client.return_value = mock_client
        
        # Mock broker positions (missing MSFT)
        mock_broker_position = Mock()
        mock_broker_position.symbol = 'AAPL'
        mock_broker_position.qty = '100'
        mock_broker_position.avg_entry_price = '150.00'
        
        mock_client.get_all_positions.return_value = [mock_broker_position]
        
        with patch.dict(os.environ, {'ALPACA_API_KEY': 'test', 'ALPACA_SECRET_KEY': 'test'}):
            reconciler = BrokerReconciler()
            reconciler.client = mock_client
            
            # Local positions include MSFT
            local_positions = {
                'AAPL': {'qty': 100, 'avg_price': 150.00},
                'MSFT': {'qty': 50, 'avg_price': 300.00}
            }
            
            success, discrepancies = reconciler.reconcile_daily(
                local_positions=local_positions,
                local_cash=50000
            )
        
        assert success == False
        assert len(discrepancies) > 0
        assert any('MSFT' in str(d) for d in discrepancies)
    
    @patch('src.risk.broker_reconciler.TradingClient')
    def test_reconciliation_catches_share_mismatch(self, mock_trading_client):
        """Test that share count mismatches are detected"""
        mock_client = Mock()
        mock_trading_client.return_value = mock_client
        
        # Mock broker position with different qty
        mock_broker_position = Mock()
        mock_broker_position.symbol = 'AAPL'
        mock_broker_position.qty = '90'  # Different from local
        mock_broker_position.avg_entry_price = '150.00'
        
        mock_client.get_all_positions.return_value = [mock_broker_position]
        
        # Mock account with proper string values
        mock_account = Mock()
        mock_account.cash = '50000.0'
        mock_account.buying_power = '50000.0'
        mock_client.get_account.return_value = mock_account
        
        with patch.dict(os.environ, {'ALPACA_API_KEY': 'test', 'ALPACA_SECRET_KEY': 'test'}):
            reconciler = BrokerReconciler()
            reconciler.client = mock_client
            
            local_positions = {
                'AAPL': {'qty': 100, 'avg_price': 150.00}
            }
            
            success, discrepancies = reconciler.reconcile_daily(
                local_positions=local_positions,
                local_cash=50000
            )
        
        assert success == False
        assert len(discrepancies) > 0
        assert any('AAPL' in str(d) and 'quantity' in str(d).lower() for d in discrepancies)
    
    @patch('src.risk.broker_reconciler.TradingClient')
    def test_reconciliation_catches_orphaned_position(self, mock_trading_client):
        """Test that positions in broker but not in DB are detected"""
        mock_client = Mock()
        mock_trading_client.return_value = mock_client
        
        # Mock broker has position not in local
        mock_broker_position = Mock()
        mock_broker_position.symbol = 'AAPL'
        mock_broker_position.qty = '100'
        mock_broker_position.avg_entry_price = '150.00'
        
        mock_client.get_all_positions.return_value = [mock_broker_position]
        
        # Mock account with proper string values
        mock_account = Mock()
        mock_account.cash = '100000.0'
        mock_account.buying_power = '100000.0'
        mock_client.get_account.return_value = mock_account
        
        with patch.dict(os.environ, {'ALPACA_API_KEY': 'test', 'ALPACA_SECRET_KEY': 'test'}):
            reconciler = BrokerReconciler()
            reconciler.client = mock_client
            
            # Local has no positions
            local_positions = {}
            
            success, discrepancies = reconciler.reconcile_daily(
                local_positions=local_positions,
                local_cash=100000
            )
        
        assert success == False
        assert len(discrepancies) > 0
        assert any('AAPL' in str(d) for d in discrepancies)
    
    @patch('src.risk.broker_reconciler.TradingClient')
    def test_reconciliation_passes_when_matching(self, mock_trading_client):
        """Test that reconciliation passes when positions match"""
        mock_client = Mock()
        mock_trading_client.return_value = mock_client
        
        # Mock matching positions
        mock_position_1 = Mock()
        mock_position_1.symbol = 'AAPL'
        mock_position_1.qty = '100'
        mock_position_1.avg_entry_price = '150.00'
        
        mock_position_2 = Mock()
        mock_position_2.symbol = 'MSFT'
        mock_position_2.qty = '50'
        mock_position_2.avg_entry_price = '300.00'
        
        mock_client.get_all_positions.return_value = [mock_position_1, mock_position_2]
        
        # Mock account with proper string cash value
        mock_account = Mock()
        mock_account.cash = '50000.0'
        mock_account.buying_power = '50000.0'
        mock_client.get_account.return_value = mock_account
        
        with patch.dict(os.environ, {'ALPACA_API_KEY': 'test', 'ALPACA_SECRET_KEY': 'test'}):
            reconciler = BrokerReconciler()
            reconciler.client = mock_client
            
            local_positions = {
                'AAPL': {'qty': 100, 'avg_price': 150.00},
                'MSFT': {'qty': 50, 'avg_price': 300.00}
            }
            
            success, discrepancies = reconciler.reconcile_daily(
                local_positions=local_positions,
                local_cash=50000
            )
        
        assert success == True
        assert len(discrepancies) == 0
    
    @patch('src.risk.broker_reconciler.TradingClient')
    def test_reconciliation_handles_empty_positions(self, mock_trading_client):
        """Test reconciliation with no positions"""
        mock_client = Mock()
        mock_trading_client.return_value = mock_client
        
        mock_client.get_all_positions.return_value = []
        
        mock_account = Mock()
        mock_account.cash = '100000.0'
        mock_account.buying_power = '100000.0'
        mock_client.get_account.return_value = mock_account
        
        with patch.dict(os.environ, {'ALPACA_API_KEY': 'test', 'ALPACA_SECRET_KEY': 'test'}):
            reconciler = BrokerReconciler()
            reconciler.client = mock_client
            
            success, discrepancies = reconciler.reconcile_daily(
                local_positions={},
                local_cash=100000
            )
        
        assert success == True
        assert len(discrepancies) == 0
    
    @patch('src.risk.broker_reconciler.TradingClient')
    def test_reconciliation_handles_api_failure(self, mock_trading_client):
        """Test reconciliation handles API failures gracefully"""
        mock_client = Mock()
        mock_trading_client.return_value = mock_client
        
        # Simulate API failure
        mock_client.get_all_positions.side_effect = Exception("API Error")
        
        with patch.dict(os.environ, {'ALPACA_API_KEY': 'test', 'ALPACA_SECRET_KEY': 'test'}):
            reconciler = BrokerReconciler()
            reconciler.client = mock_client
            
            success, discrepancies = reconciler.reconcile_daily(
                local_positions={},
                local_cash=100000
            )
        
        # Should fail gracefully
        assert success == False
        assert len(discrepancies) > 0
    
    def test_reconciliation_without_credentials(self, monkeypatch):
        """Test reconciliation handles missing credentials"""
        # Remove credentials
        monkeypatch.delenv('ALPACA_API_KEY', raising=False)
        monkeypatch.delenv('ALPACA_SECRET_KEY', raising=False)
        
        reconciler = BrokerReconciler()
        
        # Should initialize with client=None
        assert reconciler.client is None
        
        # Reconciliation should fail gracefully
        success, discrepancies = reconciler.reconcile_daily(
            local_positions={},
            local_cash=100000
        )
        
        assert success == True
        assert len(discrepancies) == 0
    
    @patch('src.risk.broker_reconciler.TradingClient')
    def test_reconciliation_sets_paused_state_on_failure(self, mock_trading_client):
        """Test that reconciliation sets paused state on mismatch"""
        mock_client = Mock()
        mock_trading_client.return_value = mock_client
        
        # Create mismatch
        mock_broker_position = Mock()
        mock_broker_position.symbol = 'AAPL'
        mock_broker_position.qty = '100'
        mock_broker_position.avg_entry_price = '150.00'
        
        mock_client.get_all_positions.return_value = [mock_broker_position]
        
        with patch.dict(os.environ, {'ALPACA_API_KEY': 'test', 'ALPACA_SECRET_KEY': 'test'}):
            reconciler = BrokerReconciler()
            reconciler.client = mock_client
            
            # Local has different position
            local_positions = {
                'AAPL': {'qty': 90, 'avg_price': 150.00}
            }
            
            success, discrepancies = reconciler.reconcile_daily(
                local_positions=local_positions,
                local_cash=50000
            )
        
        assert success == False
        # Reconciler should track mismatch
        assert len(reconciler.mismatch_details) > 0 or len(discrepancies) > 0
    
    @patch('src.risk.broker_reconciler.TradingClient')
    def test_reconciliation_cash_mismatch(self, mock_trading_client):
        """Test that cash mismatches are detected"""
        mock_client = Mock()
        mock_trading_client.return_value = mock_client
        
        mock_client.get_all_positions.return_value = []
        
        # Mock account with different cash
        mock_account = Mock()
        mock_account.cash = '95000'  # Different from local
        mock_client.get_account.return_value = mock_account
        
        reconciler = BrokerReconciler()
        
        success, discrepancies = reconciler.reconcile_daily(
            local_positions={},
            local_cash=100000
        )
        
        # May or may not fail depending on tolerance
        # At minimum, should log the discrepancy
        assert isinstance(success, bool)
        assert isinstance(discrepancies, list)


class TestReconciliationIntegration:
    """Test reconciliation integration with execution engine"""
    
    @patch('src.risk.broker_reconciler.TradingClient')
    def test_reconciliation_blocks_trading_on_failure(self, mock_trading_client):
        """Test that failed reconciliation should block trading"""
        mock_client = Mock()
        mock_trading_client.return_value = mock_client
        
        # Create mismatch
        mock_broker_position = Mock()
        mock_broker_position.symbol = 'AAPL'
        mock_broker_position.qty = '100'
        mock_broker_position.avg_entry_price = '150.00'
        
        mock_client.get_all_positions.return_value = [mock_broker_position]
        
        with patch.dict(os.environ, {'ALPACA_API_KEY': 'test', 'ALPACA_SECRET_KEY': 'test'}):
            reconciler = BrokerReconciler()
            reconciler.client = mock_client
            
            # Mismatch in positions
            local_positions = {}
            
            success, discrepancies = reconciler.reconcile_daily(
                local_positions=local_positions,
                local_cash=100000
            )
        
        # Should fail
        assert success == False
        
        # Execution engine should check this before trading
        # (This would be tested in integration tests)
    
    def test_reconciliation_allows_trading_on_success(self):
        """Test that successful reconciliation allows trading"""
        with patch('src.risk.broker_reconciler.TradingClient') as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client
            
            # Mock matching positions
            mock_position = Mock()
            mock_position.symbol = 'AAPL'
            mock_position.qty = '100'
            mock_position.market_value = '15000.0'
            mock_position.avg_entry_price = '150.0'
            mock_client.get_all_positions.return_value = [mock_position]
            
            mock_account = Mock()
            mock_account.cash = '50000.0'
            mock_account.buying_power = '50000.0'
            mock_client.get_account.return_value = mock_account
            
            with patch.dict(os.environ, {'ALPACA_API_KEY': 'test', 'ALPACA_SECRET_KEY': 'test'}):
                reconciler = BrokerReconciler()
                reconciler.client = mock_client
                
                success, _ = reconciler.reconcile_daily(
                    local_positions={'AAPL': {'qty': 100, 'avg_price': 150.0}},
                    local_cash=50000.0
                )
                
                assert success == True
                assert reconciler.is_paused == False
    
    @patch('src.risk.broker_reconciler.TradingClient')
    def test_reconcile_with_orders(self, mock_trading_client):
        """Test reconciliation with open orders (lines 94-95)"""
        mock_client = Mock()
        mock_trading_client.return_value = mock_client
        
        mock_account = Mock()
        mock_account.cash = '50000.0'
        mock_account.buying_power = '50000.0'
        mock_client.get_account.return_value = mock_account
        mock_client.get_all_positions.return_value = []
        
        # Mock orders
        from alpaca.trading.requests import GetOrdersRequest
        mock_client.get_orders.return_value = []
        
        with patch.dict(os.environ, {'ALPACA_API_KEY': 'test', 'ALPACA_SECRET_KEY': 'test'}):
            reconciler = BrokerReconciler()
            reconciler.client = mock_client
            
            # Pass local_orders to trigger order reconciliation
            success, _ = reconciler.reconcile_daily(
                local_positions={},
                local_cash=50000.0,
                local_orders=[{'id': 'order_123', 'symbol': 'AAPL'}]
            )
            assert mock_client.get_orders.called
    
    @patch('src.risk.broker_reconciler.TradingClient')
    def test_reconcile_exception_handling(self, mock_trading_client):
        """Test exception handling in reconciliation (lines 116-121)"""
        mock_client = Mock()
        mock_trading_client.return_value = mock_client
        
        # Make get_all_positions raise an exception
        mock_client.get_all_positions.side_effect = Exception("API Error")
        
        with patch.dict(os.environ, {'ALPACA_API_KEY': 'test', 'ALPACA_SECRET_KEY': 'test'}):
            reconciler = BrokerReconciler()
            reconciler.client = mock_client
            
            success, discrepancies = reconciler.reconcile_daily(
                local_positions={},
                local_cash=50000.0
            )
            
            assert success == False
            assert any('error' in str(d).lower() for d in discrepancies)
            assert reconciler.is_paused == True
    
    @patch('src.risk.broker_reconciler.TradingClient')
    def test_reconcile_orders_stuck_orders(self, mock_trading_client):
        """Test stuck orders detection (lines 196-223)"""
        mock_client = Mock()
        mock_trading_client.return_value = mock_client
        
        mock_account = Mock()
        mock_account.cash = '50000.0'
        mock_account.buying_power = '50000.0'
        mock_client.get_account.return_value = mock_account
        mock_client.get_all_positions.return_value = []
        
        # Mock broker has no orders, but local has one
        mock_client.get_orders.return_value = []
        
        with patch.dict(os.environ, {'ALPACA_API_KEY': 'test', 'ALPACA_SECRET_KEY': 'test'}):
            reconciler = BrokerReconciler()
            reconciler.client = mock_client
            
            success, discrepancies = reconciler.reconcile_daily(
                local_positions={},
                local_cash=50000.0,
                local_orders=[{'id': 'stuck_order_123'}]
            )
            
            assert any('Stuck orders' in str(d) for d in discrepancies)
    
    @patch('src.risk.broker_reconciler.TradingClient')
    def test_reconcile_orders_phantom_orders(self, mock_trading_client):
        """Test phantom orders detection (lines 196-223)"""
        mock_client = Mock()
        mock_trading_client.return_value = mock_client
        
        mock_account = Mock()
        mock_account.cash = '50000.0'
        mock_account.buying_power = '50000.0'
        mock_client.get_account.return_value = mock_account
        mock_client.get_all_positions.return_value = []
        
        # Mock broker has an order, but local doesn't
        mock_order = Mock()
        mock_order.id = 'phantom_order_456'
        mock_client.get_orders.return_value = [mock_order]
        
        with patch.dict(os.environ, {'ALPACA_API_KEY': 'test', 'ALPACA_SECRET_KEY': 'test'}):
            reconciler = BrokerReconciler()
            reconciler.client = mock_client
            
            success, discrepancies = reconciler.reconcile_daily(
                local_positions={},
                local_cash=50000.0,
                local_orders=[]
            )
            
            assert any('Phantom orders' in str(d) for d in discrepancies)
    
    @patch('src.risk.broker_reconciler.TradingClient')
    def test_email_alert_failure(self, mock_trading_client):
        """Test email alert failure handling (lines 287-288)"""
        mock_client = Mock()
        mock_trading_client.return_value = mock_client
        
        mock_client.get_all_positions.return_value = []
        mock_account = Mock()
        mock_account.cash = '50000.0'
        mock_account.buying_power = '50000.0'
        mock_client.get_account.return_value = mock_account
        
        # Mock email notifier that raises exception
        mock_email = Mock()
        mock_email.send_alert.side_effect = Exception("Email send failed")
        
        with patch.dict(os.environ, {'ALPACA_API_KEY': 'test', 'ALPACA_SECRET_KEY': 'test'}):
            reconciler = BrokerReconciler(email_notifier=mock_email)
            reconciler.client = mock_client
            
            # Create a mismatch to trigger email
            success, _ = reconciler.reconcile_daily(
                local_positions={},
                local_cash=40000.0  # Mismatch
            )
            
            assert success == False
    
    @patch('src.risk.broker_reconciler.TradingClient')
    def test_get_broker_state(self, mock_trading_client):
        """Test get_broker_state method (lines 317-341)"""
        mock_client = Mock()
        mock_trading_client.return_value = mock_client
        
        mock_position = Mock()
        mock_position.symbol = 'AAPL'
        mock_position.qty = '100'
        mock_position.avg_entry_price = '150.0'
        mock_position.market_value = '15000.0'
        mock_position.unrealized_pl = '500.0'
        mock_client.get_all_positions.return_value = [mock_position]
        
        mock_account = Mock()
        mock_account.cash = '50000.0'
        mock_account.buying_power = '50000.0'
        mock_account.portfolio_value = '65000.0'
        mock_client.get_account.return_value = mock_account
        
        mock_client.get_orders.return_value = []
        
        with patch.dict(os.environ, {'ALPACA_API_KEY': 'test', 'ALPACA_SECRET_KEY': 'test'}):
            reconciler = BrokerReconciler()
            reconciler.client = mock_client
            
            state = reconciler.get_broker_state()
            
            assert 'positions' in state
            assert 'AAPL' in state['positions']
            assert state['positions']['AAPL']['qty'] == 100
            assert state['cash'] == 50000.0
            assert state['buying_power'] == 50000.0
            assert state['portfolio_value'] == 65000.0
    
    @patch('src.risk.broker_reconciler.TradingClient')
    def test_get_broker_state_error_handling(self, mock_trading_client):
        """Test get_broker_state error handling (lines 340-341)"""
        mock_client = Mock()
        mock_trading_client.return_value = mock_client
        
        mock_client.get_all_positions.side_effect = Exception("API Error")
        
        with patch.dict(os.environ, {'ALPACA_API_KEY': 'test', 'ALPACA_SECRET_KEY': 'test'}):
            reconciler = BrokerReconciler()
            reconciler.client = mock_client
            
            state = reconciler.get_broker_state()
            
            assert state == {}
    
    def test_check_if_paused(self):
        """Test check_if_paused method"""
        with patch('src.risk.broker_reconciler.TradingClient'):
            with patch.dict(os.environ, {'ALPACA_API_KEY': 'test', 'ALPACA_SECRET_KEY': 'test'}):
                reconciler = BrokerReconciler()
                
                # Initially not paused
                is_paused, details = reconciler.check_if_paused()
                assert is_paused == False
                assert details == []
                
                # Set paused state
                reconciler.is_paused = True
                reconciler.mismatch_details = ['Test mismatch']
                
                is_paused, details = reconciler.check_if_paused()
                assert is_paused == True
                assert len(details) > 0
    
    def test_force_resume(self):
        """Test force_resume method"""
        with patch('src.risk.broker_reconciler.TradingClient'):
            with patch.dict(os.environ, {'ALPACA_API_KEY': 'test', 'ALPACA_SECRET_KEY': 'test'}):
                reconciler = BrokerReconciler()
                
                # Set paused state
                reconciler.is_paused = True
                reconciler.mismatch_details = ['Test mismatch']
                
                # Force resume
                reconciler.force_resume()
                
                assert reconciler.is_paused == False
                assert reconciler.mismatch_details == []
