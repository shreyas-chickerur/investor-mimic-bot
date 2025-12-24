#!/usr/bin/env python3
"""
Test email alert functionality
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import unittest
from email_notifier import EmailNotifier


class TestEmailAlert(unittest.TestCase):
    """Test email alert method"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.notifier = EmailNotifier()
    
    def test_send_alert_method_exists(self):
        """Test that send_alert method exists"""
        self.assertTrue(hasattr(self.notifier, 'send_alert'))
        self.assertTrue(callable(getattr(self.notifier, 'send_alert')))
    
    def test_send_alert_with_disabled_email(self):
        """Test send_alert when email is disabled (should not raise error)"""
        # This should not raise an error even if email is disabled
        try:
            self.notifier.send_alert("Test Alert", "This is a test message")
        except Exception as e:
            self.fail(f"send_alert raised exception: {e}")
    
    def test_send_alert_signature(self):
        """Test send_alert has correct signature"""
        import inspect
        sig = inspect.signature(self.notifier.send_alert)
        params = list(sig.parameters.keys())
        
        # Should have 'subject' and 'message' parameters
        self.assertIn('subject', params)
        self.assertIn('message', params)


if __name__ == '__main__':
    unittest.main()
