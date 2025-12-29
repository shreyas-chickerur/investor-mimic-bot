#!/usr/bin/env python3
"""
Check Broker State Script

Displays current broker state before execution.
Supports multi-day positions - does NOT force closure.
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / 'src'))

load_dotenv()

from broker_reconciler import BrokerReconciler

def check_broker_state():
    """Check and display current broker state"""
    reconciler = BrokerReconciler()
    state = reconciler.get_broker_state()
    
    print("=" * 60)
    print("BROKER STATE CHECK")
    print("=" * 60)
    print(f"Positions: {len(state['positions'])}")
    print(f"Cash: ${state['cash']:,.2f}")
    print(f"Portfolio Value: ${state['portfolio_value']:,.2f}")
    
    if state['positions']:
        print("\nOpen Positions:")
        for symbol, data in state['positions'].items():
            print(f"  {symbol}: {data['qty']} shares @ ${data['avg_price']:.2f}")
            print(f"    Market Value: ${data['market_value']:,.2f}")
            print(f"    Unrealized P&L: ${data['unrealized_pl']:,.2f}")
    
    print("\n✅ Broker state retrieved - ready for execution")
    print("=" * 60)
    return True

if __name__ == "__main__":
    try:
        check_broker_state()
        sys.exit(0)
    except Exception as e:
        print(f"❌ Error checking broker state: {e}")
        sys.exit(1)
