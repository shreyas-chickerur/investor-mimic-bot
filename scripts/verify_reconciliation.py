#!/usr/bin/env python3
"""
Verify reconciliation status between local database and broker
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.database import TradingDatabase
from src.risk.broker_reconciler import BrokerReconciler
from alpaca.trading.client import TradingClient


def main():
    db = TradingDatabase('trading.db')
    
    api_key = os.getenv('ALPACA_API_KEY')
    secret_key = os.getenv('ALPACA_SECRET_KEY')
    paper_mode = os.getenv('ALPACA_PAPER', 'true').lower() == 'true'
    
    if not api_key or not secret_key:
        print("❌ Error: ALPACA_API_KEY and ALPACA_SECRET_KEY must be set")
        sys.exit(1)
    
    client = TradingClient(api_key, secret_key, paper=paper_mode)
    reconciler = BrokerReconciler(db, client)
    
    print("Running reconciliation check...")
    result = reconciler.reconcile()
    
    print(f"\nReconciliation status: {result['status']}")
    
    if result['status'] == 'PASS':
        print("✅ Reconciliation PASSED - database is in sync with broker")
        sys.exit(0)
    else:
        print(f"❌ Reconciliation FAILED - {len(result['discrepancies'])} discrepancies found:")
        for disc in result['discrepancies']:
            print(f"  - {disc}")
        sys.exit(1)


if __name__ == '__main__':
    main()
