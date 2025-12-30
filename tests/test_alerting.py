#!/usr/bin/env python3
"""
Comprehensive tests for Critical Alerting System
Phase 1.3: Critical Alerting
"""
import pytest
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import sqlite3

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / 'src'))

from alerting import CriticalAlertSystem, AlertLevel


class TestCriticalAlertSystem:
    """Test suite for CriticalAlertSystem"""
    
    def setup_method(self):
        """Setup for each test"""
        # Create in-memory database for testing
        self.db_path = ":memory:"
        self.setup_test_database()
        
        # Mock environment variables
        os.environ['SENDER_EMAIL'] = 'test@example.com'
        os.environ['SENDER_PASSWORD'] = 'test_password'
        os.environ['RECIPIENT_EMAIL'] = 'recipient@example.com'
        
        # Create alert system with mocked email
        with patch('email_notifier.EmailNotifier'):
            self.alert_system = CriticalAlertSystem(self.db_path)
            self.alert_system.email_notifier = Mock()
            self.alert_system.email_notifier.send_email = Mock(return_value=True)
    
    def setup_test_database(self):
        """Create test database with schema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create tables
        cursor.execute('''
            CREATE TABLE trades (
                id INTEGER PRIMARY KEY,
                signal_id INTEGER,
                executed_at TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE signals (
                id INTEGER PRIMARY KEY,
                terminal_state TEXT,
                generated_at TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE positions (
                id INTEGER PRIMARY KEY,
                shares REAL
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def get_mock_db(self):
        """Get mock database object with fresh connection"""
        db = Mock()
        # Create new connection with tables each time
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY,
                signal_id INTEGER,
                executed_at TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY,
                terminal_state TEXT,
                generated_at TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY,
                shares REAL
            )
        ''')
        conn.commit()
        db.get_connection = Mock(return_value=conn)
        return db
    
    # Test 1: Drawdown alert triggers at threshold
    def test_drawdown_alert_triggers_at_threshold(self):
        """Test that drawdown alert triggers when threshold exceeded"""
        current_value = 85000.0
        peak_value = 100000.0
        # Drawdown = 15% (at threshold)
        
        result = self.alert_system.check_drawdown_alert(current_value, peak_value)
        
        assert result == True
        assert self.alert_system.email_notifier.send_email.called
    
    # Test 2: Drawdown alert doesn't trigger below threshold
    def test_drawdown_alert_not_triggered_below_threshold(self):
        """Test that drawdown alert doesn't trigger below threshold"""
        current_value = 90000.0
        peak_value = 100000.0
        # Drawdown = 10% (below 15% threshold)
        
        result = self.alert_system.check_drawdown_alert(current_value, peak_value)
        
        assert result == False
        assert not self.alert_system.email_notifier.send_email.called
    
    # Test 3: No trade alert triggers after 7 days
    def test_no_trade_alert_triggers_after_7_days(self):
        """Test that no-trade alert triggers after threshold days"""
        db = self.get_mock_db()
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # Insert trade from 8 days ago
        old_date = (datetime.now() - timedelta(days=8)).isoformat()
        cursor.execute("INSERT INTO trades (executed_at) VALUES (?)", (old_date,))
        conn.commit()
        
        result = self.alert_system.check_no_trade_alert(db)
        
        assert result == True
        assert self.alert_system.email_notifier.send_email.called
    
    # Test 4: No trade alert doesn't trigger within threshold
    def test_no_trade_alert_not_triggered_within_threshold(self):
        """Test that no-trade alert doesn't trigger within threshold"""
        db = self.get_mock_db()
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # Insert trade from 3 days ago
        recent_date = (datetime.now() - timedelta(days=3)).isoformat()
        cursor.execute("INSERT INTO trades (executed_at) VALUES (?)", (recent_date,))
        conn.commit()
        
        result = self.alert_system.check_no_trade_alert(db)
        
        assert result == False
        assert not self.alert_system.email_notifier.send_email.called
    
    # Test 5: Reconciliation alert triggers on FAIL
    def test_reconciliation_alert_triggers_on_fail(self):
        """Test that reconciliation alert triggers on FAIL status"""
        discrepancies = [
            "Position mismatch: AAPL (local: 10, broker: 5)",
            "Cash mismatch: $1000 difference"
        ]
        
        result = self.alert_system.check_reconciliation_alert("FAIL", discrepancies)
        
        assert result == True
        assert self.alert_system.email_notifier.send_email.called
        
        # Check that discrepancies are in the alert
        call_args = self.alert_system.email_notifier.send_email.call_args
        assert "AAPL" in str(call_args)
    
    # Test 6: Reconciliation alert doesn't trigger on PASS
    def test_reconciliation_alert_not_triggered_on_pass(self):
        """Test that reconciliation alert doesn't trigger on PASS status"""
        result = self.alert_system.check_reconciliation_alert("PASS", [])
        
        assert result == False
        assert not self.alert_system.email_notifier.send_email.called
    
    # Test 7: Database integrity detects orphaned trades
    def test_database_integrity_detects_orphaned_trades(self):
        """Test detection of orphaned trades"""
        db = self.get_mock_db()
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # Insert trade with non-existent signal_id
        cursor.execute("INSERT INTO trades (signal_id, executed_at) VALUES (?, ?)",
                      (999, datetime.now().isoformat()))
        conn.commit()
        
        result = self.alert_system.check_database_integrity(db)
        
        assert result == True
        assert self.alert_system.email_notifier.send_email.called
    
    # Test 8: Database integrity detects non-terminal signals
    def test_database_integrity_detects_non_terminal_signals(self):
        """Test detection of signals without terminal state"""
        db = self.get_mock_db()
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # Insert old signal without terminal state
        old_date = (datetime.now() - timedelta(days=2)).isoformat()
        cursor.execute("INSERT INTO signals (terminal_state, generated_at) VALUES (?, ?)",
                      (None, old_date))
        conn.commit()
        
        result = self.alert_system.check_database_integrity(db)
        
        assert result == True
        assert self.alert_system.email_notifier.send_email.called
    
    # Test 9: Database integrity detects negative positions
    def test_database_integrity_detects_negative_positions(self):
        """Test detection of negative position shares"""
        db = self.get_mock_db()
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # Insert position with negative shares
        cursor.execute("INSERT INTO positions (shares) VALUES (?)", (-10.0,))
        conn.commit()
        
        result = self.alert_system.check_database_integrity(db)
        
        assert result == True
        assert self.alert_system.email_notifier.send_email.called
    
    # Test 10: Database integrity passes with clean data
    def test_database_integrity_passes_with_clean_data(self):
        """Test that integrity check passes with clean data"""
        db = self.get_mock_db()
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # Insert valid signal and trade
        cursor.execute("INSERT INTO signals (id, terminal_state, generated_at) VALUES (?, ?, ?)",
                      (1, 'EXECUTED', datetime.now().isoformat()))
        cursor.execute("INSERT INTO trades (signal_id, executed_at) VALUES (?, ?)",
                      (1, datetime.now().isoformat()))
        cursor.execute("INSERT INTO positions (shares) VALUES (?)", (10.0,))
        conn.commit()
        
        result = self.alert_system.check_database_integrity(db)
        
        assert result == False
        assert not self.alert_system.email_notifier.send_email.called
    
    # Test 11: Alert levels are correct
    def test_alert_levels(self):
        """Test that different alert levels are used correctly"""
        # Critical alert for drawdown
        self.alert_system.check_drawdown_alert(80000.0, 100000.0)
        call_args = self.alert_system.email_notifier.send_email.call_args
        assert "CRITICAL" in str(call_args)
        
        # Reset mock
        self.alert_system.email_notifier.send_email.reset_mock()
        
        # Warning alert for no trades
        db = self.get_mock_db()
        conn = db.get_connection()
        cursor = conn.cursor()
        old_date = (datetime.now() - timedelta(days=8)).isoformat()
        cursor.execute("INSERT INTO trades (executed_at) VALUES (?)", (old_date,))
        conn.commit()
        
        self.alert_system.check_no_trade_alert(db)
        call_args = self.alert_system.email_notifier.send_email.call_args
        assert "WARNING" in str(call_args)
    
    # Test 12: Run all checks executes all checks
    def test_run_all_checks_executes_all(self):
        """Test that run_all_checks executes all checks"""
        db = self.get_mock_db()
        
        results = self.alert_system.run_all_checks(
            db=db,
            current_portfolio_value=100000.0,
            peak_portfolio_value=100000.0,
            reconciliation_status="PASS",
            discrepancies=[]
        )
        
        assert 'drawdown_alert' in results
        assert 'no_trade_alert' in results
        assert 'reconciliation_alert' in results
        assert 'database_integrity_alert' in results
    
    # Test 13: Multiple alerts can trigger simultaneously
    def test_multiple_alerts_trigger_simultaneously(self):
        """Test that multiple alerts can trigger at once"""
        db = self.get_mock_db()
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # Set up conditions for multiple alerts
        # 1. Old trade (no-trade alert)
        old_date = (datetime.now() - timedelta(days=8)).isoformat()
        cursor.execute("INSERT INTO trades (executed_at) VALUES (?)", (old_date,))
        
        # 2. Orphaned trade (integrity alert)
        cursor.execute("INSERT INTO trades (signal_id, executed_at) VALUES (?, ?)",
                      (999, datetime.now().isoformat()))
        conn.commit()
        
        results = self.alert_system.run_all_checks(
            db=db,
            current_portfolio_value=80000.0,  # 20% drawdown
            peak_portfolio_value=100000.0,
            reconciliation_status="FAIL",
            discrepancies=["Test discrepancy"]
        )
        
        # Should have multiple alerts
        alerts_triggered = sum(results.values())
        assert alerts_triggered >= 3  # drawdown, reconciliation, integrity


class TestAlertSystemIntegration:
    """Integration tests for alert system"""
    
    def test_twilio_graceful_degradation(self):
        """Test that system works without Twilio configured"""
        # Don't set Twilio env vars
        for var in ['TWILIO_ACCOUNT_SID', 'TWILIO_AUTH_TOKEN', 'TWILIO_PHONE_FROM', 'TWILIO_PHONE_TO']:
            if var in os.environ:
                del os.environ[var]
        
        with patch('email_notifier.EmailNotifier'):
            alert_system = CriticalAlertSystem(":memory:")
            
            # Should initialize without Twilio
            assert alert_system.twilio_enabled == False
            assert alert_system.email_notifier is not None
    
    def test_email_graceful_degradation(self):
        """Test that system works without email configured"""
        # Clear email env vars
        for var in ['SENDER_EMAIL', 'SENDER_PASSWORD', 'RECIPIENT_EMAIL']:
            if var in os.environ:
                del os.environ[var]
        
        with patch('email_notifier.EmailNotifier') as mock_email:
            mock_email.return_value.enabled = False
            alert_system = CriticalAlertSystem(":memory:")
            
            # Should initialize without email
            assert alert_system.email_notifier is not None
    
    def test_configurable_thresholds(self):
        """Test that alert thresholds are configurable"""
        os.environ['ALERT_DRAWDOWN_THRESHOLD'] = '0.20'  # 20%
        os.environ['ALERT_NO_TRADE_DAYS'] = '14'  # 14 days
        
        with patch('email_notifier.EmailNotifier'):
            alert_system = CriticalAlertSystem(":memory:")
            
            assert alert_system.drawdown_threshold == 0.20
            assert alert_system.no_trade_days == 14


class TestAlertSystemEdgeCases:
    """Test edge cases for alert system"""
    
    def test_zero_peak_portfolio_value(self):
        """Test handling of zero peak portfolio value"""
        with patch('email_notifier.EmailNotifier'):
            alert_system = CriticalAlertSystem(":memory:")
            alert_system.email_notifier = Mock()
            
            result = alert_system.check_drawdown_alert(100000.0, 0.0)
            
            # Should not trigger alert with zero peak
            assert result == False
    
    def test_no_trades_in_database(self):
        """Test handling when no trades exist"""
        with patch('email_notifier.EmailNotifier'):
            alert_system = CriticalAlertSystem(":memory:")
            alert_system.email_notifier = Mock()
            
            db = Mock()
            conn = sqlite3.connect(":memory:")
            cursor = conn.cursor()
            cursor.execute("CREATE TABLE trades (id INTEGER PRIMARY KEY, executed_at TEXT)")
            conn.commit()
            db.get_connection = Mock(return_value=conn)
            
            result = alert_system.check_no_trade_alert(db)
            
            # Should not trigger alert if no trades exist
            assert result == False
    
    def test_database_error_handling(self):
        """Test handling of database errors"""
        with patch('email_notifier.EmailNotifier'):
            alert_system = CriticalAlertSystem(":memory:")
            alert_system.email_notifier = Mock()
            alert_system.email_notifier.send_email = Mock(return_value=True)
            
            # Mock database that raises error
            db = Mock()
            db.get_connection = Mock(side_effect=Exception("Database error"))
            
            result = alert_system.check_database_integrity(db)
            
            # Should send alert about the check failure
            assert result == True
            assert alert_system.email_notifier.send_email.called


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
