#!/usr/bin/env python3
"""
Phase 5 Fresh Start Script

Executes Option 1 (Fresh Start):
1. Close all broker positions
2. Reset local database
3. Verify reconciliation passes
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import os
import time
import sqlite3
from alpaca.trading.client import TradingClient
from broker_reconciler import BrokerReconciler
from email_notifier import EmailNotifier

def main():
    print('='*80)
    print('PHASE 5 FRESH START')
    print('='*80)
    
    # Step 1: Close all broker positions
    print('\nSTEP 1: Closing all broker positions...')
    api_key = os.getenv('ALPACA_API_KEY')
    secret_key = os.getenv('ALPACA_SECRET_KEY')
    
    if not api_key or not secret_key:
        print('❌ ERROR: Alpaca credentials not found')
        print('Please set ALPACA_API_KEY and ALPACA_SECRET_KEY environment variables')
        return False
    
    client = TradingClient(api_key, secret_key, paper=True)
    
    # Get all positions
    positions = client.get_all_positions()
    print(f'Current positions: {len(positions)}')
    
    if len(positions) > 0:
        print(f'Closing {len(positions)} positions...')
        for pos in positions:
            print(f'  Closing {pos.symbol}: {pos.qty} shares')
            try:
                client.close_position(pos.symbol)
                print(f'    ✅ Closed')
            except Exception as e:
                print(f'    ❌ Error: {e}')
        
        # Wait for orders to settle
        time.sleep(3)
    
    # Verify all closed
    positions_after = client.get_all_positions()
    if len(positions_after) > 0:
        print(f'⚠️  WARNING: {len(positions_after)} positions remain')
        for pos in positions_after:
            print(f'  {pos.symbol}: {pos.qty} shares')
        return False
    
    account = client.get_account()
    print(f'✅ All positions closed')
    print(f'   Cash: ${float(account.cash):,.2f}')
    print(f'   Portfolio Value: ${float(account.portfolio_value):,.2f}')
    
    # Step 2: Reset local database
    print('\nSTEP 2: Resetting local database...')
    db_path = Path(__file__).parent.parent / 'trading.db'
    
    if not db_path.exists():
        print('⚠️  Database does not exist - will be created fresh')
    else:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Get table info
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print(f'Found {len(tables)} tables: {[t[0] for t in tables]}')
        
        # Clear trades if table exists
        try:
            cursor.execute('SELECT COUNT(*) FROM trades')
            trade_count = cursor.fetchone()[0]
            print(f'Found {trade_count} trades')
            
            cursor.execute('DELETE FROM trades')
            conn.commit()
            print(f'✅ Deleted {trade_count} trades')
        except sqlite3.OperationalError:
            print('⚠️  No trades table found')
        
        # Mark Phase 5 reset
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS system_state (
                key TEXT PRIMARY KEY,
                value TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            INSERT OR REPLACE INTO system_state (key, value)
            VALUES ('PHASE_5_INITIAL_STATE_RESET', 'TRUE')
        ''')
        conn.commit()
        print('✅ Marked PHASE_5_INITIAL_STATE_RESET = TRUE')
        
        conn.close()
    
    # Step 3: Verify reconciliation
    print('\nSTEP 3: Verifying reconciliation...')
    email_notifier = EmailNotifier()
    reconciler = BrokerReconciler(email_notifier=email_notifier)
    
    # Get broker state
    broker_state = reconciler.get_broker_state()
    print(f'Broker state:')
    print(f'  Positions: {len(broker_state["positions"])}')
    print(f'  Cash: ${broker_state["cash"]:,.2f}')
    
    # Run reconciliation with empty local state
    local_positions = {}
    local_cash = broker_state['cash']
    
    success, discrepancies = reconciler.reconcile_daily(
        local_positions=local_positions,
        local_cash=local_cash
    )
    
    if success and len(discrepancies) == 0:
        print('✅ Reconciliation PASSED (0 discrepancies)')
        print('\n' + '='*80)
        print('✅ FRESH START COMPLETE')
        print('='*80)
        print('System is ready for Phase 5 paper trading')
        return True
    else:
        print(f'❌ Reconciliation FAILED ({len(discrepancies)} discrepancies)')
        for disc in discrepancies:
            print(f'  - {disc}')
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
