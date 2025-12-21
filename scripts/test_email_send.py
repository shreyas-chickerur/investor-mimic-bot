#!/usr/bin/env python3
"""
Test Email Send with Sample Data
Triggers actual email sending and verifies database storage
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from email_template_simple import generate_simple_approval_email
from approval_handler import ApprovalHandler
from database_schema import TradingDatabase
from alpaca_data_fetcher import AlpacaDataFetcher
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv

load_dotenv()

print("=" * 80)
print("EMAIL SEND TEST - COMPLETE WORKFLOW WITH DATABASE STORAGE")
print("=" * 80)

try:
    # Initialize database
    print("\n📊 Initializing database...")
    db = TradingDatabase()
    print("✅ Database initialized")
    
    # Fetch real data from Alpaca
    print("\n🔄 Fetching real data from Alpaca...")
    fetcher = AlpacaDataFetcher()
    
    account_info = fetcher.get_account_info()
    current_holdings = fetcher.get_current_positions()
    market_data = fetcher.get_market_indices()
    
    print(f"✅ Portfolio: ${account_info['portfolio_value']:,.2f}")
    print(f"✅ Cash: ${account_info['cash']:,.2f}")
    print(f"✅ Holdings: {len(current_holdings)} positions")
    
    # Store market data in database
    print("\n💾 Storing market data in database...")
    db.save_market_data(market_data)
    print("✅ Market data stored")
    
    # Store holdings in database
    print("\n💾 Storing holdings in database...")
    for holding in current_holdings:
        db.update_holding(
            symbol=holding['symbol'],
            shares=holding['shares'],
            avg_price=holding['avg_price'],
            current_price=holding['current_price']
        )
    print(f"✅ {len(current_holdings)} holdings stored")
    
    # Sample proposed trades
    proposed_trades = [
        {
            'symbol': 'AAPL',
            'shares': 10,
            'price': 185.50,
            'value': 1855.00,
            'action': 'BUY',
            'reasoning': {'rsi': 28.5, 'volatility': '1.15x', 'score': 0.85}
        },
        {
            'symbol': 'MSFT',
            'shares': 8,
            'price': 375.25,
            'value': 3002.00,
            'action': 'BUY',
            'reasoning': {'rsi': 29.2, 'volatility': '1.20x', 'score': 0.82}
        }
    ]
    
    # Create approval request in database
    print("\n💾 Creating approval request in database...")
    handler = ApprovalHandler()
    request_id = handler.create_approval_request(
        trades=proposed_trades,
        portfolio_value=account_info['portfolio_value'],
        cash=account_info['cash']
    )
    print(f"✅ Approval request created: {request_id}")
    
    # Generate approval token
    print("\n🔐 Generating secure approval token...")
    from security import get_security_manager
    security = get_security_manager()
    approval_token = security.create_approval_token(request_id)
    print(f"✅ Token created: {approval_token[:16]}...")
    
    # Generate email HTML
    print("\n📧 Generating email HTML...")
    approval_url = os.getenv('APPROVAL_BASE_URL', 'http://localhost:8000/approve')
    
    email_html = generate_simple_approval_email(
        trades=proposed_trades,
        portfolio_value=account_info['portfolio_value'],
        cash=account_info['cash'],
        approval_url=approval_url,
        request_id=request_id,
        market_data=market_data,
        current_holdings=current_holdings
    )
    print("✅ Email HTML generated")
    
    # Send email
    print("\n📤 Sending email...")
    email_username = os.getenv('EMAIL_USERNAME')
    email_password = os.getenv('EMAIL_PASSWORD')
    email_to = os.getenv('EMAIL_TO')
    
    if not email_username or not email_password or not email_to:
        print("⚠️  Email credentials not configured in .env")
        print("   Set EMAIL_USERNAME, EMAIL_PASSWORD, EMAIL_TO to send actual email")
        print("   Skipping email send, but database storage is complete")
    else:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"🔔 Trade Approval Required - {len(proposed_trades)} trades pending"
        msg['From'] = email_username
        msg['To'] = email_to
        
        html_part = MIMEText(email_html, 'html')
        msg.attach(html_part)
        
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(email_username, email_password)
            server.send_message(msg)
        
        print(f"✅ Email sent to {email_to}")
    
    # Verify database storage
    print("\n🔍 Verifying database storage...")
    
    # Check approval request
    pending_request = handler.get_pending_request(request_id)
    if pending_request:
        print(f"✅ Approval request stored: {request_id}")
        print(f"   Status: {pending_request['status']}")
        print(f"   Trades: {len(pending_request['trades'])}")
    
    # Check market data
    stored_market_data = db.get_latest_market_data()
    if stored_market_data:
        print(f"✅ Market data stored: {len(stored_market_data)} indices")
    
    # Check holdings
    stored_holdings = db.get_current_holdings()
    if stored_holdings:
        print(f"✅ Holdings stored: {len(stored_holdings)} positions")
    
    # Check approval token
    token_status = security.validate_approval_token(approval_token)
    if token_status:
        print(f"✅ Approval token valid and stored")
    
    print("\n" + "=" * 80)
    print("✅ EMAIL WORKFLOW TEST COMPLETE")
    print("=" * 80)
    
    print("\n📊 DATABASE STORAGE SUMMARY:")
    print(f"   ✅ Approval request: {request_id}")
    print(f"   ✅ Market data: {len(stored_market_data)} indices")
    print(f"   ✅ Holdings: {len(stored_holdings)} positions")
    print(f"   ✅ Proposed trades: {len(proposed_trades)}")
    print(f"   ✅ Approval token: {approval_token[:16]}...")
    
    print("\n📧 EMAIL STATUS:")
    if email_username and email_password and email_to:
        print(f"   ✅ Email sent to: {email_to}")
    else:
        print("   ⚠️  Email not sent (credentials not configured)")
    
    print("\n🔄 NEXT STEPS:")
    print("   1. Check your email inbox")
    print("   2. Click 'Review Trades' button")
    print("   3. Approve/reject trades")
    print("   4. Submit decisions")
    print("   5. Approved trades will execute on Alpaca")
    print("   6. All decisions stored in database")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    print(traceback.format_exc())
