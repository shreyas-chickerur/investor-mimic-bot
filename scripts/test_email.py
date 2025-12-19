#!/usr/bin/env python3
"""
Test email notification configuration.

This script sends a test email to verify your SMTP settings are correct.
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from services.monitoring.email_notifier import EmailConfig, EmailNotifier


def main():
    print("=" * 80)
    print("EMAIL CONFIGURATION TEST")
    print("=" * 80)
    print()

    # Get email config from environment
    print("Loading configuration from .env...")
    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port = os.getenv("SMTP_PORT", "587")
    smtp_username = os.getenv("SMTP_USERNAME")
    smtp_password = os.getenv("SMTP_PASSWORD")
    alert_email = os.getenv("ALERT_EMAIL")

    if not all([smtp_server, smtp_username, smtp_password, alert_email]):
        print("❌ Missing email configuration")
        print()
        print("Please configure these in your .env file:")
        print("  SMTP_SERVER=smtp.gmail.com")
        print("  SMTP_PORT=587")
        print("  SMTP_USERNAME=your-email@gmail.com")
        print("  SMTP_PASSWORD=your-app-password")
        print("  ALERT_EMAIL=your-email@gmail.com")
        sys.exit(1)

    print("✓ Configuration loaded")
    print()
    print(f"SMTP Server: {smtp_server}")
    print(f"SMTP Port: {smtp_port}")
    print(f"Username: {smtp_username}")
    print(f"Alert Email: {alert_email}")
    print()

    # Create email config
    try:
        email_config = EmailConfig(
            smtp_server=smtp_server,
            smtp_port=int(smtp_port),
            smtp_username=smtp_username,
            smtp_password=smtp_password,
            from_email=smtp_username,
        )
    except Exception as e:
        print(f"❌ Failed to create email config: {e}")
        sys.exit(1)

    # Create email notifier
    print("Initializing email notifier...")
    notifier = EmailNotifier(email_config)
    print("✓ Notifier initialized")
    print()

    # Send test email
    print("Sending test email...")
    print(f"To: {alert_email}")
    print()

    success = notifier.send_alert(
        to_emails=[alert_email],
        subject="Test Email from InvestorMimic Bot",
        message="""
This is a test email to verify your email configuration is working correctly.

If you received this email, your SMTP settings are configured properly!

You can now use the email approval workflow for automated trading.

Next steps:
1. Start the API server: python3 main.py
2. Run the approval script: python3 scripts/auto_invest_with_approval.py --approval-email schickerur2020@gmail.com

Happy investing! 🚀
""",
        level="INFO",
    )

    print()
    if success:
        print("=" * 80)
        print("✅ SUCCESS! Test email sent successfully")
        print("=" * 80)
        print()
        print("Check your inbox at:", alert_email)
        print()
        print("If you don't see it:")
        print("  1. Check your spam folder")
        print("  2. Wait a minute (email can be delayed)")
        print("  3. Verify your app password is correct")
        print()
    else:
        print("=" * 80)
        print("❌ FAILED to send test email")
        print("=" * 80)
        print()
        print("Common issues:")
        print("  1. Incorrect app password (must be 16 characters from Google)")
        print("  2. 2FA not enabled on Gmail account")
        print("  3. App password not generated correctly")
        print()
        print("To fix:")
        print("  1. Go to https://myaccount.google.com/apppasswords")
        print("  2. Generate a new app password for 'Mail'")
        print("  3. Update SMTP_PASSWORD in your .env file")
        print()
        sys.exit(1)


if __name__ == "__main__":
    main()
