#!/usr/bin/env python3
"""
Test New Workflow
Simplified email + Comprehensive approval page
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from email_template_simple import generate_simple_approval_email
from approval_page_comprehensive import generate_comprehensive_approval_page
from alpaca_data_fetcher import AlpacaDataFetcher

print("=" * 80)
print("NEW WORKFLOW TEST - SIMPLIFIED EMAIL + COMPREHENSIVE APPROVAL PAGE")
print("=" * 80)

try:
    # Fetch real data from Alpaca
    print("\n🔄 Fetching real data from Alpaca...")
    fetcher = AlpacaDataFetcher()
    
    account_info = fetcher.get_account_info()
    current_holdings = fetcher.get_current_positions()
    market_data = fetcher.get_market_indices()
    
    print(f"✅ Portfolio: ${account_info['portfolio_value']:,.2f}")
    print(f"✅ Cash: ${account_info['cash']:,.2f}")
    print(f"✅ Holdings: {len(current_holdings)} positions")
    
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
        },
        {
            'symbol': 'GOOGL',
            'shares': 15,
            'price': 140.75,
            'value': 2111.25,
            'action': 'BUY',
            'reasoning': {'rsi': 27.8, 'volatility': '1.18x', 'score': 0.88}
        },
        {
            'symbol': 'NVDA',
            'shares': 5,
            'price': 495.00,
            'value': 2475.00,
            'action': 'BUY',
            'reasoning': {'rsi': 26.5, 'volatility': '1.22x', 'score': 0.90}
        }
    ]
    
    # Generate simplified email
    print("\n📧 Generating simplified email (daily digest)...")
    email_html = generate_simple_approval_email(
        trades=proposed_trades,
        portfolio_value=account_info['portfolio_value'],
        cash=account_info['cash'],
        approval_url="http://localhost:8000/approve",
        request_id="approval_new_workflow_test",
        market_data=market_data,
        current_holdings=current_holdings
    )
    
    email_file = Path('new_workflow_email.html')
    with open(email_file, 'w') as f:
        f.write(email_html)
    print(f"✅ Simplified email saved: {email_file.absolute()}")
    
    # Generate comprehensive approval page
    print("\n📋 Generating comprehensive approval page...")
    approval_html = generate_comprehensive_approval_page(
        trades=proposed_trades,
        portfolio_value=account_info['portfolio_value'],
        cash=account_info['cash'],
        request_id="approval_new_workflow_test",
        market_data=market_data,
        current_holdings=current_holdings,
        holdings_news=[]  # Would be populated from database
    )
    
    approval_file = Path('new_workflow_approval.html')
    with open(approval_file, 'w') as f:
        f.write(approval_html)
    print(f"✅ Comprehensive approval page saved: {approval_file.absolute()}")
    
    print("\n" + "=" * 80)
    print("✅ NEW WORKFLOW GENERATED")
    print("=" * 80)
    
    print("\n📧 SIMPLIFIED EMAIL:")
    print("  • Quick daily digest format")
    print("  • Portfolio summary (4 metrics)")
    print("  • Market overview")
    print("  • Trade list (compact)")
    print("  • Call-to-action button")
    print("  • Fast to read and scan")
    
    print("\n📋 COMPREHENSIVE APPROVAL PAGE:")
    print("  • Executive summary")
    print("  • Market overview (detailed)")
    print("  • Your current holdings")
    print("  • News about your holdings")
    print("  • Each trade with full analysis")
    print("  • News-based causal flowcharts")
    print("  • Approve/Reject for each trade")
    print("  • Bulk action buttons")
    
    print("\n🔄 WORKFLOW:")
    print("  1. Receive simplified email (quick scan)")
    print("  2. Click 'Review Trades' button")
    print("  3. Comprehensive page opens (informed decision)")
    print("  4. Review all details, news, analysis")
    print("  5. Approve/reject trades")
    print("  6. Submit decisions")
    
    print("\nTo view:")
    print(f"  Email: open {email_file.absolute()}")
    print(f"  Approval: open {approval_file.absolute()}")
    
    # Open both files
    import subprocess
    subprocess.run(['open', str(email_file)])
    subprocess.run(['open', str(approval_file)])
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    print(traceback.format_exc())
