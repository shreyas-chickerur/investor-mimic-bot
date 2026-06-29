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
        self._env_patch = patch.dict(
            os.environ, {"SENDER_EMAIL": "", "SENDER_PASSWORD": "", "RECIPIENT_EMAIL": ""}
        )
        self._env_patch.start()
        self.notifier = EmailNotifier()

    def tearDown(self):
        self._env_patch.stop()

    def test_send_alert_method_exists(self):
        """Test that send_alert method exists"""
        self.assertTrue(hasattr(self.notifier, "send_alert"))
        self.assertTrue(callable(self.notifier.send_alert))

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
        self.assertIn("subject", params)
        self.assertIn("message", params)

    def test_legacy_daily_summary_sender_removed(self):
        """Legacy summary sender should be removed after email-path unification."""
        self.assertFalse(hasattr(self.notifier, "send_daily_summary"))


if __name__ == "__main__":
    unittest.main()


class TestEmailArchive(unittest.TestCase):
    """The on-send archive must capture mail locally without ever blocking send."""

    def test_archive_writes_gitignored_html_with_subject(self):
        import tempfile

        from src.utils.email_notifier import archive_email

        with tempfile.TemporaryDirectory() as d:
            path = archive_email("⚠️ Recon Warning: SPY/UNH", "<html><body>hi</body></html>", d)
            self.assertIsNotNone(path)
            self.assertTrue(path.endswith(".html"))
            content = Path(path).read_text(encoding="utf-8")
            self.assertIn("Recon Warning", content)  # subject preserved in header comment
            self.assertIn("<body>hi</body>", content)

    def test_send_email_archives_on_success(self):
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            env = {
                "SENDER_EMAIL": "a@b.com",
                "SENDER_PASSWORD": "x",  # pragma: allowlist secret
                "RECIPIENT_EMAIL": "c@d.com",
                "EMAIL_ARCHIVE_DIR": d,
            }
            with patch.dict(os.environ, env):
                notifier = EmailNotifier()
                with patch("src.utils.email_notifier.smtplib.SMTP") as smtp:
                    smtp.return_value.__enter__.return_value = smtp.return_value
                    notifier._send_email("Daily Digest", "<html>x</html>", is_html=True)
            written = list(Path(d).glob("*.html"))
            self.assertEqual(len(written), 1)
            self.assertIn("Daily-Digest", written[0].name)

    def test_archive_failure_never_raises(self):
        # Point at a path that cannot be created (a file used as a directory).
        import tempfile

        from src.utils.email_notifier import archive_email

        with tempfile.NamedTemporaryFile() as f:
            result = archive_email("subj", "<html>x</html>", os.path.join(f.name, "nope"))
            self.assertIsNone(result)
