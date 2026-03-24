#!/usr/bin/env python3
"""
Test email alert functionality
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import os
import unittest
from unittest.mock import patch
from src.utils.email_notifier import EmailNotifier


class TestEmailAlert(unittest.TestCase):
    """Test email alert method"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Force credentials absent so EmailNotifier.enabled=False (no live SMTP)
        self._env_patch = patch.dict(os.environ, {
            'SENDER_EMAIL': '', 'SENDER_PASSWORD': '', 'RECIPIENT_EMAIL': ''
        })
        self._env_patch.start()
        self.notifier = EmailNotifier()

    def tearDown(self):
        self._env_patch.stop()
    
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

    def test_daily_summary_includes_reasoning_flowchart_section(self):
        """Daily summary should render reasoning flowchart cards when provided."""
        email_html = self.notifier._build_summary_email(
            trades=[],
            positions=[],
            portfolio_value=100000.0,
            cash=25000.0,
            errors=None,
            signal_reasoning_chains=[
                {
                    'strategy': 'News Sentiment',
                    'symbol': 'AAPL',
                    'action': 'BUY',
                    'flowchart': 'Event A -> Event B -> Price dropped -> Signal generated (BUY)',
                    'executed': True,
                }
            ],
        )

        self.assertIn('Signal Reasoning Flowcharts', email_html)
        self.assertIn('News Sentiment', email_html)
        self.assertIn('AAPL', email_html)
        self.assertIn('Event A -&gt; Event B -&gt; Price dropped -&gt; Signal generated (BUY)', email_html)

    def test_daily_summary_escapes_flowchart_html_content(self):
        """Flowchart content should be HTML escaped for safety."""
        email_html = self.notifier._build_summary_email(
            trades=[],
            positions=[],
            portfolio_value=100000.0,
            cash=25000.0,
            errors=None,
            signal_reasoning_chains=[
                {
                    'strategy': 'News Sentiment',
                    'symbol': 'TSLA',
                    'action': 'SELL',
                    'flowchart': '<script>alert(1)</script> -> negative news -> Signal generated (SELL)',
                    'executed': False,
                }
            ],
        )

        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;', email_html)
        self.assertNotIn('<script>alert(1)</script>', email_html)


if __name__ == '__main__':
    unittest.main()
