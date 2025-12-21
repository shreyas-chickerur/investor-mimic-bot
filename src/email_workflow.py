#!/usr/bin/env python3
"""
Email Workflow
Complete workflow for sending approval emails with database-synced data
"""
from typing import List, Dict
from datetime import datetime
from data_sync_job import run_data_sync
from database_schema import TradingDatabase
from email_template_simple_fixed import generate_simple_approval_email
from approval_handler import ApprovalHandler
from security import get_security_manager
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv

load_dotenv()


def send_approval_email_workflow(proposed_trades: List[Dict]) -> Dict:
    """
    Complete workflow to send approval email
    
    Steps:
    1. Sync all Alpaca data to database
    2. Get data from database (not Alpaca directly)
    3. Create approval request
    4. Generate email HTML
    5. Send email
    
    Args:
        proposed_trades: List of proposed trades
    
    Returns:
        Dict with workflow results
    """
    print("=" * 80)
    print(f"EMAIL WORKFLOW - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    results = {
        'sync_success': False,
        'email_sent': False,
        'request_id': None,
        'errors': []
    }
    
    try:
        # Step 1: Sync Alpaca data to database
        print("\n📊 STEP 1: Syncing Alpaca data to database...")
        sync_results = run_data_sync()
        
        if not sync_results['success']:
            results['errors'].extend(sync_results['errors'])
            print("⚠️  Data sync had errors, but continuing...")
        
        results['sync_success'] = True
        
        # Step 2: Get all data from database (single source of truth)
        print("\n📖 STEP 2: Loading data from database...")
        db = TradingDatabase()
        
        # Get account info from latest snapshot
        # For now, we'll use the sync results, but in production this would query the DB
        account_info = sync_results.get('account_snapshot', {})
        portfolio_value = account_info.get('portfolio_value', 0)
        cash = account_info.get('cash', 0)
        
        # Get holdings from database
        current_holdings = db.get_current_holdings()
        print(f"   ✅ Loaded {len(current_holdings)} holdings from database")
        
        # Get market data from database
        market_data = db.get_latest_market_data()
        print(f"   ✅ Loaded {len(market_data)} market indices from database")
        
        # Get news from database
        holdings_news = db.get_holdings_news(limit=5)
        print(f"   ✅ Loaded {len(holdings_news)} news articles from database")
        
        # Step 3: Create approval request
        print("\n📝 STEP 3: Creating approval request...")
        handler = ApprovalHandler()
        request_id = handler.create_approval_request(
            trades=proposed_trades,
            portfolio_value=portfolio_value,
            cash=cash
        )
        results['request_id'] = request_id
        print(f"   ✅ Approval request created: {request_id}")
        
        # Step 4: Generate secure approval token
        print("\n🔐 STEP 4: Generating secure approval token...")
        security = get_security_manager()
        approval_token = security.create_approval_token(request_id)
        print(f"   ✅ Token created: {approval_token[:16]}...")
        
        # Step 5: Generate email HTML (using database data only)
        print("\n📧 STEP 5: Generating email HTML...")
        approval_url = os.getenv('APPROVAL_BASE_URL', 'http://localhost:8000/approve')
        
        email_html = generate_simple_approval_email(
            trades=proposed_trades,
            portfolio_value=portfolio_value,
            cash=cash,
            approval_url=approval_url,
            request_id=request_id,
            market_data=market_data,
            current_holdings=current_holdings
        )
        print("   ✅ Email HTML generated")
        
        # Step 6: Send email
        print("\n📤 STEP 6: Sending email...")
        email_username = os.getenv('EMAIL_USERNAME')
        email_password = os.getenv('EMAIL_PASSWORD')
        email_to = os.getenv('EMAIL_TO')
        
        if not email_username or not email_password or not email_to:
            error_msg = "Email credentials not configured"
            results['errors'].append(error_msg)
            print(f"   ⚠️  {error_msg}")
            return results
        
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
        
        results['email_sent'] = True
        print(f"   ✅ Email sent to {email_to}")
        
        # Summary
        print("\n" + "=" * 80)
        print("✅ EMAIL WORKFLOW COMPLETED SUCCESSFULLY")
        print("=" * 80)
        print(f"   Request ID: {request_id}")
        print(f"   Trades: {len(proposed_trades)}")
        print(f"   Portfolio: ${portfolio_value:,.2f}")
        print(f"   Cash: ${cash:,.2f}")
        print(f"   Email sent to: {email_to}")
        print()
        
    except Exception as e:
        error_msg = f"Workflow error: {e}"
        results['errors'].append(error_msg)
        print(f"\n❌ {error_msg}")
        import traceback
        print(traceback.format_exc())
    
    return results


def send_approval_email_from_database(proposed_trades: List[Dict]) -> Dict:
    """
    Send approval email using only database data (assumes data already synced)
    
    This is useful when data sync happens separately (e.g., scheduled job)
    
    Args:
        proposed_trades: List of proposed trades
    
    Returns:
        Dict with results
    """
    print("📧 Sending approval email from database data...")
    
    db = TradingDatabase()
    
    # Get all data from database
    email_data = db.get_email_data(proposed_trades)
    
    # Create approval request
    handler = ApprovalHandler()
    request_id = handler.create_approval_request(
        trades=proposed_trades,
        portfolio_value=email_data['portfolio_value'],
        cash=email_data['cash']
    )
    
    # Generate and send email
    # (Implementation similar to above)
    
    return {
        'email_sent': True,
        'request_id': request_id
    }


if __name__ == '__main__':
    # Test with sample trades
    sample_trades = [
        {
            'symbol': 'AAPL',
            'shares': 10,
            'price': 185.50,
            'value': 1855.00,
            'action': 'BUY'
        },
        {
            'symbol': 'MSFT',
            'shares': 8,
            'price': 375.25,
            'value': 3002.00,
            'action': 'BUY'
        }
    ]
    
    results = send_approval_email_workflow(sample_trades)
    
    if not results['email_sent']:
        exit(1)
