#!/usr/bin/env python3
"""
Test Approval Page with Real Data
Shows what the trade review page would look like
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from email_template import generate_approval_page_html
from alpaca_data_fetcher import AlpacaDataFetcher

print("=" * 80)
print("APPROVAL PAGE PREVIEW - TRADE REVIEW INTERFACE")
print("=" * 80)

try:
    # Initialize Alpaca fetcher
    print("\n🔄 Fetching real data from Alpaca...")
    fetcher = AlpacaDataFetcher()
    
    # Get account info
    account_info = fetcher.get_account_info()
    print(f"✅ Portfolio: ${account_info['portfolio_value']:,.2f}")
    print(f"✅ Cash: ${account_info['cash']:,.2f}")
    
    # Sample proposed trades (these would come from signal generation)
    proposed_trades = [
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
        },
        {
            'symbol': 'GOOGL',
            'shares': 15,
            'price': 140.75,
            'value': 2111.25,
            'action': 'BUY'
        },
        {
            'symbol': 'NVDA',
            'shares': 5,
            'price': 495.00,
            'value': 2475.00,
            'action': 'BUY'
        }
    ]
    
    print(f"✅ Proposed trades: {len(proposed_trades)}")
    
    # Generate approval page HTML
    print("\n📋 Generating approval page...")
    approval_page_html = generate_approval_page_html(
        trades=proposed_trades,
        portfolio_value=account_info['portfolio_value'],
        cash=account_info['cash'],
        request_id="approval_real_page_test"
    )
    
    # Save approval page
    page_file = Path('real_approval_page.html')
    with open(page_file, 'w') as f:
        f.write(approval_page_html)
    
    print(f"✅ Approval page saved to: {page_file.absolute()}")
    
    print("\n" + "=" * 80)
    print("✅ APPROVAL PAGE GENERATED")
    print("=" * 80)
    print("\nThis is the page you would see when clicking 'Review Trades' in the email.")
    print("\nFeatures:")
    print("  • Your real portfolio value and cash")
    print("  • All proposed trades with details")
    print("  • Approve/Reject radio buttons for each trade")
    print("  • Approve All / Reject All buttons")
    print("  • Submit button to process decisions")
    print("\nTo view:")
    print(f"  open {page_file.absolute()}")
    
    # Open the file
    import subprocess
    subprocess.run(['open', str(page_file)])
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    print(traceback.format_exc())
