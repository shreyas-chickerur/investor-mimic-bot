#!/usr/bin/env python3
"""
End-to-End Morning Workflow Test
Simulates what happens when the system runs in the morning
"""
import sys
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from email_workflow import send_approval_email_workflow

print("=" * 80)
print("MORNING WORKFLOW SIMULATION")
print("=" * 80)
print(f"\n📅 Date: {datetime.now().strftime('%A, %B %d, %Y')}")
print(f"⏰ Time: {datetime.now().strftime('%I:%M %p ET')}")
print("\n" + "=" * 80)
print("SIMULATING DAILY TRADING WORKFLOW")
print("=" * 80)

print("\n🌅 MORNING SEQUENCE:")
print("   1. GitHub Actions triggers at scheduled time (e.g., 9:00 AM ET)")
print("   2. System fetches latest data from Alpaca")
print("   3. Trading signals generated based on your strategy")
print("   4. Data synced to database")
print("   5. Email sent with approval request")
print("   6. You review and approve/reject trades")
print("   7. Approved trades execute on Alpaca")
print()

# Simulate trading signals (in production, these come from your trading system)
print("📊 Generating sample trading signals...")
proposed_trades = [
    {
        'symbol': 'AAPL',
        'shares': 10,
        'price': 185.50,
        'value': 1855.00,
        'action': 'BUY',
        'reasoning': {
            'rsi': 28.5,
            'volatility': '1.15x',
            'score': 0.85,
            'signal': 'Strong buy signal - oversold conditions'
        }
    },
    {
        'symbol': 'GOOGL',
        'shares': 15,
        'price': 140.75,
        'value': 2111.25,
        'action': 'BUY',
        'reasoning': {
            'rsi': 27.8,
            'volatility': '1.18x',
            'score': 0.88,
            'signal': 'Buy signal - momentum building'
        }
    }
]

print(f"✅ Generated {len(proposed_trades)} trading signals")
for trade in proposed_trades:
    print(f"   - {trade['symbol']}: {trade['action']} {trade['shares']} shares @ ${trade['price']:.2f}")

print("\n" + "=" * 80)
print("EXECUTING COMPLETE WORKFLOW")
print("=" * 80)

# Run the complete workflow
results = send_approval_email_workflow(proposed_trades)

print("\n" + "=" * 80)
print("MORNING WORKFLOW RESULTS")
print("=" * 80)

if results['email_sent']:
    print("\n✅ WORKFLOW COMPLETED SUCCESSFULLY")
    print(f"\n📧 Email sent to your inbox")
    print(f"   Request ID: {results['request_id']}")
    print(f"   Trades: {len(proposed_trades)}")
    
    print("\n📋 WHAT HAPPENS NEXT:")
    print("   1. Check your email inbox")
    print("   2. Review the daily digest and proposed trades")
    print("   3. Click 'Review & Approve Trades'")
    print("   4. Make your decisions on the approval page")
    print("   5. Submit your decisions")
    print("   6. Approved trades execute immediately on Alpaca")
    print("   7. You receive confirmation with results")
    
    print("\n⏱️  TIMELINE:")
    print("   - Email sent: Now")
    print("   - You review: Anytime today")
    print("   - Trades execute: When you approve")
    print("   - Request expires: 24 hours")
    
    print("\n🔒 SECURITY:")
    print("   - Approval link is one-time use")
    print("   - Secure token authentication")
    print("   - All decisions logged in database")
    print("   - Complete audit trail maintained")
    
else:
    print("\n❌ WORKFLOW FAILED")
    if results['errors']:
        print("\nErrors:")
        for error in results['errors']:
            print(f"   - {error}")

print("\n" + "=" * 80)
print("END OF MORNING WORKFLOW SIMULATION")
print("=" * 80)
print()
