#!/usr/bin/env python3
"""
Test Real Email with Actual Alpaca Data
Shows what the email would look like today with real positions
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from email_template_enhanced import generate_professional_approval_email
from alpaca_data_fetcher import AlpacaDataFetcher

print("=" * 80)
print("REAL EMAIL PREVIEW - TODAY'S DATA FROM ALPACA")
print("=" * 80)

try:
    # Initialize Alpaca fetcher
    print("\n🔄 Connecting to Alpaca API...")
    fetcher = AlpacaDataFetcher()
    
    # Get account info
    print("📊 Fetching account information...")
    account_info = fetcher.get_account_info()
    print(f"   Portfolio Value: ${account_info['portfolio_value']:,.2f}")
    print(f"   Cash: ${account_info['cash']:,.2f}")
    print(f"   Equity: ${account_info['equity']:,.2f}")
    
    # Get current positions
    print("\n📈 Fetching current positions...")
    current_holdings = fetcher.get_current_positions()
    print(f"   Found {len(current_holdings)} positions:")
    for holding in current_holdings:
        print(f"   - {holding['symbol']}: {holding['shares']} shares @ ${holding['current_price']:.2f} ({holding['unrealized_plpc']:+.2f}%)")
    
    # Get market data
    print("\n📊 Fetching market indices...")
    market_data = fetcher.get_market_indices()
    for index, data in market_data.items():
        print(f"   {index}: {data['value']} ({data['change_pct']:+.2f}%)")
    
    # Sample proposed trades (these would come from signal generation)
    print("\n💡 Using sample proposed trades for demonstration...")
    proposed_trades = [
        {
            'symbol': 'AAPL',
            'shares': 10,
            'price': 185.50,
            'value': 1855.00,
            'reasoning': {'rsi': 28.5, 'volatility': '1.15x', 'score': 0.85}
        },
        {
            'symbol': 'MSFT',
            'shares': 8,
            'price': 375.25,
            'value': 3002.00,
            'reasoning': {'rsi': 29.2, 'volatility': '1.20x', 'score': 0.82}
        }
    ]
    
    # Get complete email data
    print("\n🔄 Fetching complete email data...")
    email_data = fetcher.get_complete_email_data(proposed_trades)
    
    # Generate email
    print("\n📧 Generating professional email HTML...")
    email_html = generate_professional_approval_email(
        trades=email_data['trades'],
        portfolio_value=email_data['portfolio_value'],
        cash=email_data['cash'],
        approval_url="http://localhost:8000/approve",
        request_id=f"approval_real_{Path(__file__).stem}",
        market_data=email_data['market_data'],
        holdings_news=email_data.get('holdings_news', []),
        current_holdings=email_data['current_holdings']
    )
    
    # Save email
    email_file = Path('real_approval_email_today.html')
    with open(email_file, 'w') as f:
        f.write(email_html)
    
    print(f"\n✅ Email saved to: {email_file.absolute()}")
    print("\n" + "=" * 80)
    print("✅ SUCCESS - REAL EMAIL GENERATED WITH TODAY'S ALPACA DATA")
    print("=" * 80)
    print("\nEmail contains:")
    print(f"  • Your actual {len(current_holdings)} positions from Alpaca")
    print(f"  • Real portfolio value: ${account_info['portfolio_value']:,.2f}")
    print(f"  • Real cash balance: ${account_info['cash']:,.2f}")
    print(f"  • Current market indices")
    print(f"  • {len(proposed_trades)} proposed trades with causal analysis")
    print("\nTo view:")
    print(f"  open {email_file.absolute()}")
    
    # Open the file
    import subprocess
    subprocess.run(['open', str(email_file)])
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    print("\nMake sure:")
    print("  1. ALPACA_API_KEY and ALPACA_SECRET_KEY are set in .env")
    print("  2. You have an active Alpaca paper trading account")
    print("  3. alpaca-py is installed: pip install alpaca-py")
    import traceback
    print("\nFull error:")
    print(traceback.format_exc())
