#!/usr/bin/env python3
"""
Test Complete Workflow with Data Sync
Demonstrates the improved architecture with database sync before email
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from email_workflow import send_approval_email_workflow

print("=" * 80)
print("COMPLETE WORKFLOW TEST - WITH DATABASE SYNC")
print("=" * 80)
print("\nThis workflow:")
print("  1. Syncs all Alpaca data to database")
print("  2. Uses database as single source of truth")
print("  3. Generates and sends email")
print()

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

# Run complete workflow
results = send_approval_email_workflow(proposed_trades)

# Print results
print("\n" + "=" * 80)
print("WORKFLOW RESULTS")
print("=" * 80)
print(f"Data sync: {'✅ Success' if results['sync_success'] else '❌ Failed'}")
print(f"Email sent: {'✅ Success' if results['email_sent'] else '❌ Failed'}")
print(f"Request ID: {results['request_id']}")

if results['errors']:
    print(f"\nErrors: {len(results['errors'])}")
    for error in results['errors']:
        print(f"  ❌ {error}")

print()

if results['email_sent']:
    print("✅ Check your email inbox!")
    exit(0)
else:
    print("❌ Email not sent - check errors above")
    exit(1)
