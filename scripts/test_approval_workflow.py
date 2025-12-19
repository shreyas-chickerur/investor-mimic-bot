#!/usr/bin/env python3
"""
Simple test of the approval workflow.
This bypasses complex imports and just tests the core functionality.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

print("=" * 80)
print("TESTING APPROVAL WORKFLOW")
print("=" * 80)
print()

# Test 1: Email configuration
print("1. Testing email configuration...")
smtp_server = os.getenv("SMTP_SERVER")
smtp_username = os.getenv("SMTP_USERNAME")
alert_email = os.getenv("ALERT_EMAIL")

if all([smtp_server, smtp_username, alert_email]):
    print(f"   ✓ Email configured: {alert_email}")
else:
    print("   ✗ Email not configured")
    sys.exit(1)

# Test 2: Database connection
print("\n2. Testing database connection...")
try:
    import psycopg2

    conn = psycopg2.connect("postgresql://postgres@localhost:5432/investorbot")
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM holdings")
    count = cur.fetchone()[0]
    print(f"   ✓ Database connected: {count:,} holdings loaded")
    conn.close()
except Exception as e:
    print(f"   ✗ Database error: {e}")
    sys.exit(1)

# Test 3: Alpaca connection
print("\n3. Testing Alpaca connection...")
try:
    from alpaca.trading.client import TradingClient

    api_key = os.getenv("ALPACA_API_KEY")
    secret_key = os.getenv("ALPACA_SECRET_KEY")

    client = TradingClient(api_key, secret_key, paper=True)
    account = client.get_account()
    print(f"   ✓ Alpaca connected: ${float(account.buying_power):,.2f} buying power")
except Exception as e:
    print(f"   ✗ Alpaca error: {e}")
    sys.exit(1)

# Test 4: Send test approval email
print("\n4. Sending test approval email...")
try:
    from services.approval.trade_approval import TradeApprovalManager
    from services.monitoring.email_notifier import EmailConfig, EmailNotifier

    email_config = EmailConfig(
        smtp_server=smtp_server,
        smtp_port=int(os.getenv("SMTP_PORT", "587")),
        smtp_username=smtp_username,
        smtp_password=os.getenv("SMTP_PASSWORD"),
        from_email=smtp_username,
    )

    notifier = EmailNotifier(email_config)
    manager = TradeApprovalManager()

    # Create a test approval request
    test_trades = [
        {
            "symbol": "AAPL",
            "quantity": 10.5,
            "estimated_price": 185.50,
            "estimated_value": 1947.75,
            "allocation_pct": 40.0,
        },
        {
            "symbol": "GOOGL",
            "quantity": 5.2,
            "estimated_price": 142.30,
            "estimated_value": 739.96,
            "allocation_pct": 15.0,
        },
        {
            "symbol": "MSFT",
            "quantity": 12.8,
            "estimated_price": 378.90,
            "estimated_value": 4849.92,
            "allocation_pct": 45.0,
        },
    ]

    request = manager.create_approval_request(
        trades=test_trades,
        total_investment=7537.63,
        available_cash=10000.00,
        cash_buffer=1000.00,
        expiry_hours=24,
    )

    print(f"   ✓ Created approval request: {request.request_id}")

    # Send email
    success = notifier.send_alert(
        to_emails=[alert_email],
        subject=f"TEST: Trade Approval Required - ${request.total_investment:,.2f}",
        message=f"""
This is a TEST of the approval workflow.

SUMMARY:
--------
Total Investment: ${request.total_investment:,.2f}
Available Cash: ${request.available_cash:,.2f}
Cash Buffer: ${request.cash_buffer:,.2f}
Number of Trades: {len(request.trades)}

PROPOSED TRADES:
---------------
  • AAPL: 10.5 shares @ $185.50 = $1,947.75
  • GOOGL: 5.2 shares @ $142.30 = $739.96
  • MSFT: 12.8 shares @ $378.90 = $4,849.92

APPROVAL:
---------
To approve (for testing), visit:
http://localhost:8000/api/v1/approve/{request.request_id}/approve

To reject (for testing), visit:
http://localhost:8000/api/v1/approve/{request.request_id}/reject

Request ID: {request.request_id}

This is a TEST - no actual trades will be executed.
""",
        level="INFO",
    )

    if success:
        print(f"   ✓ Test email sent to {alert_email}")
        print(f"\n   Check your email and click the approval link!")
        print(f"   Approval URL: http://localhost:8000/api/v1/approve/{request.request_id}/approve")
    else:
        print("   ✗ Failed to send email")
        sys.exit(1)

except Exception as e:
    print(f"   ✗ Error: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 80)
print("✅ ALL TESTS PASSED!")
print("=" * 80)
print()
print("Next steps:")
print("1. Check your email at:", alert_email)
print("2. Click the approval link in the email")
print("3. Verify the approval page loads correctly")
print()
print("The system is ready for automated investing!")
