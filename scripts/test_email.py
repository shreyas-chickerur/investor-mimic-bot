#!/usr/bin/env python3
"""
Test Email Workflow
Generates sample email and saves to HTML file for preview
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from email_template_enhanced import generate_professional_approval_email
from email_template import generate_approval_page_html

# Sample trade data with reasoning
sample_trades = [
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
    },
    {
        'symbol': 'GOOGL',
        'shares': 15,
        'price': 140.75,
        'value': 2111.25,
        'reasoning': {'rsi': 27.8, 'volatility': '1.18x', 'score': 0.88}
    },
    {
        'symbol': 'NVDA',
        'shares': 5,
        'price': 495.00,
        'value': 2475.00,
        'reasoning': {'rsi': 26.5, 'volatility': '1.22x', 'score': 0.90}
    }
]

# Sample market data
market_data = {
    "S&P 500": {"value": "4,783.45", "change": 23.45, "change_pct": 0.49},
    "NASDAQ": {"value": "15,095.14", "change": -15.23, "change_pct": -0.10},
    "DOW": {"value": "37,545.33", "change": 45.67, "change_pct": 0.12}
}

# Sample current holdings
current_holdings = [
    {'symbol': 'TSLA', 'shares': 12, 'avg_price': 245.00, 'current_price': 252.30},
    {'symbol': 'AMD', 'shares': 25, 'avg_price': 142.50, 'current_price': 138.75},
    {'symbol': 'META', 'shares': 8, 'avg_price': 485.00, 'current_price': 498.20}
]

# Sample holdings news
holdings_news = [
    {
        'ticker': 'TSLA',
        'title': 'Tesla Announces New Battery Technology Breakthrough',
        'summary': 'Company reveals 30% improvement in energy density, potentially reducing costs and extending range for electric vehicles.',
        'sentiment': 'Bullish'
    },
    {
        'ticker': 'AMD',
        'title': 'AMD Faces Increased Competition in AI Chip Market',
        'summary': 'Analysts note growing pressure from competitors in the data center GPU segment, though long-term outlook remains positive.',
        'sentiment': 'Neutral'
    }
]

portfolio_value = 50000.00
cash = 40556.75
approval_url = "http://localhost:8000/approve"
request_id = "approval_20251220_test"

print("=" * 80)
print("ENHANCED PROFESSIONAL EMAIL WORKFLOW TEST")
print("=" * 80)

# Generate professional approval email
print("\n1. Generating professional financial-style email HTML...")
email_html = generate_professional_approval_email(
    trades=sample_trades,
    portfolio_value=portfolio_value,
    cash=cash,
    approval_url=approval_url,
    request_id=request_id,
    market_data=market_data,
    holdings_news=holdings_news,
    current_holdings=current_holdings
)

# Save email to file
email_file = Path('test_approval_email.html')
with open(email_file, 'w') as f:
    f.write(email_html)

print(f"✅ Email saved to: {email_file.absolute()}")

# Generate approval page
print("\n2. Generating approval page HTML...")
approval_page_html = generate_approval_page_html(
    trades=sample_trades,
    portfolio_value=portfolio_value,
    cash=cash,
    request_id=request_id
)

# Save approval page to file
page_file = Path('test_approval_page.html')
with open(page_file, 'w') as f:
    f.write(approval_page_html)

print(f"✅ Approval page saved to: {page_file.absolute()}")

print("\n" + "=" * 80)
print("✅ TEST COMPLETE")
print("=" * 80)
print("\nTo view the email:")
print(f"  open {email_file.absolute()}")
print("\nTo view the approval page:")
print(f"  open {page_file.absolute()}")
print("\nSample data used:")
print(f"  - {len(sample_trades)} trades")
print(f"  - Total investment: ${sum(t['value'] for t in sample_trades):,.2f}")
print(f"  - Portfolio value: ${portfolio_value:,.2f}")
print(f"  - Available cash: ${cash:,.2f}")
