#!/usr/bin/env python3
"""
Unit Tests for Broker Reconciliation System

Tests reconciliation logic, PAUSED state, and mismatch detection.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import unittest
from unittest.mock import Mock, patch, MagicMock
from broker_reconciler import BrokerReconciler, ReconciliationMismatch


class TestBrokerReconciler(unittest.TestCase):
    """Test broker reconciliation system"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_email = Mock()
        
        # Mock Alpaca client
        with patch('broker_reconciler.TradingClient'):
            self.reconciler = BrokerReconciler(email_notifier=self.mock_email)
            self.reconciler.client = Mock()
    
    def test_perfect_reconciliation(self):
        """Test reconciliation with perfect match"""
        # Setup: Local and broker states match
        local_positions = {
            'AAPL': {'qty': 10, 'avg_price': 150.00},
            'MSFT': {'qty': 5, 'avg_price': 300.00}
        }
        local_cash = 50000.00
        
        # Mock broker responses
        mock_positions = [
            Mock(symbol='AAPL', qty='10', avg_entry_price='150.00'),
            Mock(symbol='MSFT', qty='5', avg_entry_price='300.00')
        ]
        mock_account = Mock(cash='50000.00', buying_power='50000.00')
        
        self.reconciler.client.get_all_positions.return_value = mock_positions
        self.reconciler.client.get_account.return_value = mock_account
        
        # Execute
        success, discrepancies = self.reconciler.reconcile_daily(local_positions, local_cash)
        
        # Assert
        self.assertTrue(success)
        self.assertEqual(len(discrepancies), 0)
        self.assertFalse(self.reconciler.is_paused)
    
    def test_position_quantity_mismatch(self):
        """Test detection of position quantity mismatch"""
        local_positions = {
            'AAPL': {'qty': 10, 'avg_price': 150.00}
        }
        local_cash = 50000.00
        
        # Broker has different quantity
        mock_positions = [
            Mock(symbol='AAPL', qty='15', avg_entry_price='150.00')  # Mismatch!
        ]
        mock_account = Mock(cash='50000.00', buying_power='50000.00')
        
        self.reconciler.client.get_all_positions.return_value = mock_positions
        self.reconciler.client.get_account.return_value = mock_account
        
        # Execute
        success, discrepancies = self.reconciler.reconcile_daily(local_positions, local_cash)
        
        # Assert
        self.assertFalse(success)
        self.assertGreater(len(discrepancies), 0)
        self.assertTrue(self.reconciler.is_paused)
        self.assertIn('Quantity mismatch', discrepancies[0])
    
    def test_position_price_mismatch(self):
        """Test detection of position price mismatch"""
        local_positions = {
            'AAPL': {'qty': 10, 'avg_price': 150.00}
        }
        local_cash = 50000.00
        
        # Broker has significantly different price (>1% tolerance)
        mock_positions = [
            Mock(symbol='AAPL', qty='10', avg_entry_price='160.00')  # 6.7% diff
        ]
        mock_account = Mock(cash='50000.00', buying_power='50000.00')
        
        self.reconciler.client.get_all_positions.return_value = mock_positions
        self.reconciler.client.get_account.return_value = mock_account
        
        # Execute
        success, discrepancies = self.reconciler.reconcile_daily(local_positions, local_cash)
        
        # Assert
        self.assertFalse(success)
        self.assertGreater(len(discrepancies), 0)
        self.assertTrue(self.reconciler.is_paused)
        self.assertIn('Price mismatch', discrepancies[0])
    
    def test_cash_mismatch(self):
        """Test detection of cash balance mismatch"""
        local_positions = {}
        local_cash = 50000.00
        
        # Broker has different cash (>1% tolerance)
        mock_positions = []
        mock_account = Mock(cash='45000.00', buying_power='45000.00')  # 10% diff
        
        self.reconciler.client.get_all_positions.return_value = mock_positions
        self.reconciler.client.get_account.return_value = mock_account
        
        # Execute
        success, discrepancies = self.reconciler.reconcile_daily(local_positions, local_cash)
        
        # Assert
        self.assertFalse(success)
        self.assertGreater(len(discrepancies), 0)
        self.assertTrue(self.reconciler.is_paused)
        self.assertIn('Cash mismatch', discrepancies[0])
    
    def test_phantom_position_detection(self):
        """Test detection of phantom positions (broker but not local)"""
        local_positions = {
            'AAPL': {'qty': 10, 'avg_price': 150.00}
        }
        local_cash = 50000.00
        
        # Broker has extra position
        mock_positions = [
            Mock(symbol='AAPL', qty='10', avg_entry_price='150.00'),
            Mock(symbol='TSLA', qty='5', avg_entry_price='200.00')  # Phantom!
        ]
        mock_account = Mock(cash='50000.00', buying_power='50000.00')
        
        self.reconciler.client.get_all_positions.return_value = mock_positions
        self.reconciler.client.get_account.return_value = mock_account
        
        # Execute
        success, discrepancies = self.reconciler.reconcile_daily(local_positions, local_cash)
        
        # Assert
        self.assertFalse(success)
        self.assertGreater(len(discrepancies), 0)
        self.assertTrue(self.reconciler.is_paused)
        # Should have both "exists in broker but not locally" and phantom position messages
        self.assertTrue(any('TSLA' in disc for disc in discrepancies))
    
    def test_missing_position_detection(self):
        """Test detection of missing positions (local but not broker)"""
        local_positions = {
            'AAPL': {'qty': 10, 'avg_price': 150.00},
            'MSFT': {'qty': 5, 'avg_price': 300.00}
        }
        local_cash = 50000.00
        
        # Broker missing MSFT
        mock_positions = [
            Mock(symbol='AAPL', qty='10', avg_entry_price='150.00')
        ]
        mock_account = Mock(cash='50000.00', buying_power='50000.00')
        
        self.reconciler.client.get_all_positions.return_value = mock_positions
        self.reconciler.client.get_account.return_value = mock_account
        
        # Execute
        success, discrepancies = self.reconciler.reconcile_daily(local_positions, local_cash)
        
        # Assert
        self.assertFalse(success)
        self.assertGreater(len(discrepancies), 0)
        self.assertTrue(self.reconciler.is_paused)
        self.assertTrue(any('MSFT' in disc and 'exists locally but not in broker' in disc for disc in discrepancies))
    
    def test_paused_state_blocks_trading(self):
        """Test that PAUSED state is properly set and queryable"""
        # Force a mismatch
        local_positions = {'AAPL': {'qty': 10, 'avg_price': 150.00}}
        local_cash = 50000.00
        
        mock_positions = [Mock(symbol='AAPL', qty='15', avg_entry_price='150.00')]
        mock_account = Mock(cash='50000.00', buying_power='50000.00')
        
        self.reconciler.client.get_all_positions.return_value = mock_positions
        self.reconciler.client.get_account.return_value = mock_account
        
        # Execute
        success, discrepancies = self.reconciler.reconcile_daily(local_positions, local_cash)
        
        # Check PAUSED state
        is_paused, details = self.reconciler.check_if_paused()
        
        self.assertTrue(is_paused)
        self.assertEqual(details, discrepancies)
        self.assertGreater(len(details), 0)
    
    def test_email_alert_on_mismatch(self):
        """Test that email alert is sent on reconciliation failure"""
        local_positions = {'AAPL': {'qty': 10, 'avg_price': 150.00}}
        local_cash = 50000.00
        
        # Force mismatch
        mock_positions = [Mock(symbol='AAPL', qty='15', avg_entry_price='150.00')]
        mock_account = Mock(cash='50000.00', buying_power='50000.00')
        
        self.reconciler.client.get_all_positions.return_value = mock_positions
        self.reconciler.client.get_account.return_value = mock_account
        
        # Execute
        success, discrepancies = self.reconciler.reconcile_daily(local_positions, local_cash)
        
        # Assert email was sent
        self.mock_email.send_alert.assert_called_once()
        call_args = self.mock_email.send_alert.call_args[0]
        self.assertIn('PAUSED', call_args[0])  # Subject
        self.assertIn('Reconciliation', call_args[0])
    
    def test_force_resume(self):
        """Test force resume functionality"""
        # Enter paused state
        self.reconciler.is_paused = True
        self.reconciler.mismatch_details = ['Test mismatch']
        
        # Force resume
        self.reconciler.force_resume()
        
        # Assert
        self.assertFalse(self.reconciler.is_paused)
        self.assertEqual(len(self.reconciler.mismatch_details), 0)
    
    def test_price_tolerance(self):
        """Test that small price differences within 1% tolerance are accepted"""
        local_positions = {
            'AAPL': {'qty': 10, 'avg_price': 150.00}
        }
        local_cash = 50000.00
        
        # Broker has slightly different price (0.5% diff - within tolerance)
        mock_positions = [
            Mock(symbol='AAPL', qty='10', avg_entry_price='150.75')
        ]
        mock_account = Mock(cash='50000.00', buying_power='50000.00')
        
        self.reconciler.client.get_all_positions.return_value = mock_positions
        self.reconciler.client.get_account.return_value = mock_account
        
        # Execute
        success, discrepancies = self.reconciler.reconcile_daily(local_positions, local_cash)
        
        # Assert - should pass despite small difference
        self.assertTrue(success)
        self.assertEqual(len(discrepancies), 0)
    
    def test_cash_tolerance(self):
        """Test that small cash differences within 1% tolerance are accepted"""
        local_positions = {}
        local_cash = 50000.00
        
        # Broker has slightly different cash (0.5% diff - within tolerance)
        mock_positions = []
        mock_account = Mock(cash='50250.00', buying_power='50250.00')
        
        self.reconciler.client.get_all_positions.return_value = mock_positions
        self.reconciler.client.get_account.return_value = mock_account
        
        # Execute
        success, discrepancies = self.reconciler.reconcile_daily(local_positions, local_cash)
        
        # Assert - should pass despite small difference
        self.assertTrue(success)
        self.assertEqual(len(discrepancies), 0)


if __name__ == '__main__':
    unittest.main()
