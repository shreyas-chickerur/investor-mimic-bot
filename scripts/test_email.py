#!/usr/bin/env python3
"""
Send a test daily trading summary email with sample data
"""
import sys
import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from email_notifier import EmailNotifier

def send_test_summary():
    """Send test daily summary with realistic sample data"""
    
    notifier = EmailNotifier()
    
    if not notifier.enabled:
        print("❌ Email not configured. Please set environment variables:")
        print("   - SENDER_EMAIL")
        print("   - SENDER_PASSWORD")
        print("   - RECIPIENT_EMAIL")
        return
    
    # Sample trades
    sample_trades = [
        {
            'action': 'BUY',
            'symbol': 'AAPL',
            'shares': 15,
            'price': 195.50,
            'strategy': 'RSI Mean Reversion'
        },
        {
            'action': 'BUY',
            'symbol': 'MSFT',
            'shares': 10,
            'price': 378.25,
            'strategy': 'ML Momentum'
        },
        {
            'action': 'BUY',
            'symbol': 'GOOGL',
            'shares': 8,
            'price': 142.80,
            'strategy': 'News Sentiment'
        },
        {
            'action': 'SELL',
            'symbol': 'TSLA',
            'shares': 12,
            'price': 248.50,
            'strategy': 'RSI Mean Reversion (Exit)'
        },
        {
            'action': 'SELL',
            'symbol': 'NVDA',
            'shares': 5,
            'price': 495.75,
            'strategy': 'ML Momentum (Exit)'
        }
    ]
    
    # Sample positions
    sample_positions = [
        {
            'symbol': 'AAPL',
            'shares': 15,
            'entry_price': 195.50,
            'current_price': 197.25
        },
        {
            'symbol': 'MSFT',
            'shares': 10,
            'entry_price': 378.25,
            'current_price': 380.50
        },
        {
            'symbol': 'GOOGL',
            'shares': 8,
            'entry_price': 142.80,
            'current_price': 143.10
        },
        {
            'symbol': 'META',
            'shares': 20,
            'entry_price': 355.00,
            'current_price': 358.75
        },
        {
            'symbol': 'AMZN',
            'shares': 12,
            'entry_price': 178.50,
            'current_price': 176.80
        },
        {
            'symbol': 'JPM',
            'shares': 25,
            'entry_price': 198.20,
            'current_price': 199.50
        },
        {
            'symbol': 'V',
            'shares': 18,
            'entry_price': 285.40,
            'current_price': 287.90
        }
    ]
    
    # Sample errors/warnings
    sample_errors = [
        "Signal rejected: NFLX - Correlation with existing positions too high (0.78)",
        "Risk limit: Portfolio heat at 28% (max 30%)"
    ]
    
    # Portfolio values
    portfolio_value = 102450.75
    cash = 12340.25
    
    print("📧 Sending test daily summary email...")
    print(f"   To: {notifier.recipient_email}")
    print(f"   Trades: {len(sample_trades)}")
    print(f"   Positions: {len(sample_positions)}")
    print(f"   Warnings: {len(sample_errors)}")
    
    try:
        notifier.send_daily_summary(
            trades=sample_trades,
            positions=sample_positions,
            portfolio_value=portfolio_value,
            cash=cash,
            errors=sample_errors
        )
        print("✅ Test email sent successfully!")
        print("\nCheck your inbox and review the email format.")
        print("Provide feedback on what you'd like to change.")
        
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        print("\nTroubleshooting:")
        print("1. Check your .env file has correct credentials")
        print("2. Verify Gmail App Password (not regular password)")
        print("3. Ensure 2FA is enabled on Gmail")
        print("4. Check SMTP settings")

if __name__ == '__main__':
    send_test_summary()
