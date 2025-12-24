#!/usr/bin/env python3
"""
Phase 5 Day 1 Verification Script

Verifies that Phase 5 operational validation is working correctly:
1. Broker has 0 positions OR reconciliation passed
2. Database schema is correct
3. Terminal states are complete
4. Trades recorded properly
5. Artifacts exist
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import os
import subprocess
import sqlite3
from datetime import datetime
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient

load_dotenv()

def verify_database_schema():
    """Verify trading.db has correct Phase 5 schema"""
    print("\n" + "="*80)
    print("1. VERIFYING DATABASE SCHEMA")
    print("="*80)
    
    required_tables = [
        'strategies',
        'strategy_performance',
        'signals',
        'trades',
        'positions',
        'broker_state',
        'system_state',
    ]
    
    conn = sqlite3.connect('trading.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]
    
    missing = set(required_tables) - set(tables)
    if missing:
        print(f"❌ FAIL: Missing tables: {missing}")
        conn.close()
        return False
    
    print(f"✅ PASS: All required tables present: {required_tables}")
    
    # Verify trades table has execution cost columns
    cursor.execute("PRAGMA table_info(trades)")
    columns = [row[1] for row in cursor.fetchall()]
    
    required_cols = ['exec_price', 'slippage_cost', 'commission_cost', 'total_cost', 'notional']
    missing_cols = set(required_cols) - set(columns)
    
    if missing_cols:
        print(f"❌ FAIL: trades table missing columns: {missing_cols}")
        conn.close()
        return False
    
    print(f"✅ PASS: trades table has execution cost columns")
    
    # Verify signals table has terminal state columns
    cursor.execute("PRAGMA table_info(signals)")
    columns = [row[1] for row in cursor.fetchall()]
    
    required_cols = ['terminal_state', 'terminal_reason', 'terminal_at', 'asof_date']
    missing_cols = set(required_cols) - set(columns)
    
    if missing_cols:
        print(f"❌ FAIL: signals table missing columns: {missing_cols}")
        conn.close()
        return False
    
    print(f"✅ PASS: signals table has terminal state tracking")
    
    conn.close()
    return True

def run_system(dry_run: bool) -> bool:
    """Run the system in dry-run or real mode."""
    mode = "DRY RUN" if dry_run else "REAL RUN"
    print("\n" + "="*80)
    print(f"2. RUNNING SYSTEM ({mode})")
    print("="*80)

    api_key = os.getenv('ALPACA_API_KEY')
    secret_key = os.getenv('ALPACA_SECRET_KEY')

    if not api_key or not secret_key:
        print("⚠️  WARNING: Alpaca credentials not found, skipping system run")
        return True

    env = os.environ.copy()
    if dry_run:
        env['PHASE5_DRY_RUN'] = 'true'
    else:
        env.pop('PHASE5_DRY_RUN', None)

    cmd = [sys.executable, 'src/multi_strategy_main.py']
    print(f"Running command: {' '.join(cmd)} (PHASE5_DRY_RUN={env.get('PHASE5_DRY_RUN', 'false')})")

    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
        print(f"❌ FAIL: System run failed ({mode})")
        return False

    print(f"✅ PASS: System run completed ({mode})")
    return True


def verify_broker_state():
    """Verify broker has 0 positions or reconciliation passed"""
    print("\n" + "="*80)
    print("4. VERIFYING BROKER STATE")
    print("="*80)
    
    api_key = os.getenv('ALPACA_API_KEY')
    secret_key = os.getenv('ALPACA_SECRET_KEY')
    
    if not api_key or not secret_key:
        print("⚠️  WARNING: Alpaca credentials not found, skipping broker check")
        return True
    
    try:
        client = TradingClient(api_key, secret_key, paper=True)
        account = client.get_account()
        positions = client.get_all_positions()
        
        print(f"Broker Positions: {len(positions)}")
        print(f"Cash: ${float(account.cash):,.2f}")
        print(f"Portfolio Value: ${float(account.portfolio_value):,.2f}")
        
        if len(positions) == 0:
            print("✅ PASS: Broker has 0 positions (clean state)")
            return True
        
        # Check if reconciliation passed
        conn = sqlite3.connect('trading.db')
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT reconciliation_status 
            FROM broker_state 
            ORDER BY created_at DESC 
            LIMIT 1
        """)
        row = cursor.fetchone()
        conn.close()
        
        if row and row[0] == 'PASS':
            print(f"✅ PASS: Reconciliation status = PASS ({len(positions)} positions)")
            return True
        else:
            print(f"❌ FAIL: Broker has {len(positions)} positions but no PASS reconciliation")
            for pos in positions:
                print(f"  - {pos.symbol}: {pos.qty} shares")
            return False
            
    except Exception as e:
        print(f"❌ FAIL: Error checking broker: {e}")
        return False

def verify_terminal_states():
    """Verify all signals have terminal states"""
    print("\n" + "="*80)
    print("5. VERIFYING TERMINAL STATES")
    print("="*80)
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    conn = sqlite3.connect('trading.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM signals WHERE asof_date = ?", (today,))
    total_signals = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT COUNT(*) FROM signals 
        WHERE asof_date = ? AND terminal_state IS NOT NULL
    """, (today,))
    with_terminal = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT COUNT(*) FROM signals 
        WHERE asof_date = ? AND terminal_state IS NULL
    """, (today,))
    without_terminal = cursor.fetchone()[0]
    
    print(f"Total signals today: {total_signals}")
    print(f"With terminal state: {with_terminal}")
    print(f"Without terminal state: {without_terminal}")
    
    if total_signals == 0:
        print("⚠️  WARNING: No signals generated today")
        conn.close()
        return True
    
    if without_terminal > 0:
        print(f"❌ FAIL: {without_terminal} signals missing terminal state")
        
        cursor.execute("""
            SELECT id, symbol, signal_type FROM signals 
            WHERE asof_date = ? AND terminal_state IS NULL
        """, (today,))
        for row in cursor.fetchall():
            print(f"  Signal ID {row[0]}: {row[1]} {row[2]}")
        
        conn.close()
        return False
    
    print("✅ PASS: All signals have terminal states")
    
    # Show terminal state breakdown
    cursor.execute("""
        SELECT terminal_state, COUNT(*) 
        FROM signals 
        WHERE asof_date = ? 
        GROUP BY terminal_state
    """, (today,))
    
    print("\nTerminal state breakdown:")
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]}")
    
    conn.close()
    return True

def verify_trades():
    """Verify trades recorded with execution costs"""
    print("\n" + "="*80)
    print("6. VERIFYING TRADES")
    print("="*80)
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    conn = sqlite3.connect('trading.db')
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT COUNT(*) FROM trades 
        WHERE DATE(executed_at) = ?
    """, (today,))
    trade_count = cursor.fetchone()[0]
    
    print(f"Trades executed today: {trade_count}")
    
    if trade_count == 0:
        print("⚠️  WARNING: No trades executed today")
        conn.close()
        return True
    
    # Verify execution costs are recorded
    cursor.execute("""
        SELECT COUNT(*) FROM trades 
        WHERE DATE(executed_at) = ? 
        AND (exec_price IS NULL OR slippage_cost IS NULL OR commission_cost IS NULL)
    """, (today,))
    missing_costs = cursor.fetchone()[0]
    
    if missing_costs > 0:
        print(f"❌ FAIL: {missing_costs} trades missing execution cost data")
        conn.close()
        return False
    
    print("✅ PASS: All trades have execution costs recorded")
    
    # Show trade summary
    cursor.execute("""
        SELECT symbol, action, shares, exec_price, total_cost, notional
        FROM trades 
        WHERE DATE(executed_at) = ?
        ORDER BY executed_at
    """, (today,))
    
    print("\nTrade summary:")
    for row in cursor.fetchall():
        symbol, action, shares, exec_price, total_cost, notional = row
        print(f"  {action} {shares} {symbol} @ ${exec_price:.2f} (cost: ${total_cost:.2f}, notional: ${notional:.2f})")
    
    conn.close()
    return True

def verify_artifacts():
    """Verify daily artifacts exist"""
    print("\n" + "="*80)
    print("7. VERIFYING ARTIFACTS")
    print("="*80)
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    json_artifact = Path(f'artifacts/json/{today}.json')
    md_artifact = Path(f'artifacts/markdown/{today}.md')
    
    if not json_artifact.exists():
        print(f"❌ FAIL: JSON artifact missing: {json_artifact}")
        return False
    
    print(f"✅ PASS: JSON artifact exists: {json_artifact}")
    
    if not md_artifact.exists():
        print(f"⚠️  WARNING: Markdown artifact missing: {md_artifact}")
    else:
        print(f"✅ PASS: Markdown artifact exists: {md_artifact}")
    
    # Check artifact size
    size = json_artifact.stat().st_size
    if size < 100:
        print(f"❌ FAIL: Artifact suspiciously small ({size} bytes)")
        return False
    
    print(f"✅ PASS: Artifact size: {size} bytes")
    
    return True

def verify_broker_state_snapshot():
    """Verify broker state snapshot was saved"""
    print("\n" + "="*80)
    print("8. VERIFYING BROKER STATE SNAPSHOT")
    print("="*80)
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    conn = sqlite3.connect('trading.db')
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT snapshot_date, cash, portfolio_value, reconciliation_status
        FROM broker_state 
        WHERE snapshot_date = ?
    """, (today,))
    
    row = cursor.fetchone()
    
    if not row:
        print(f"❌ FAIL: No broker state snapshot for {today}")
        conn.close()
        return False
    
    snapshot_date, cash, portfolio_value, recon_status = row
    print(f"✅ PASS: Broker state snapshot exists for {snapshot_date}")
    print(f"  Cash: ${cash:,.2f}")
    print(f"  Portfolio Value: ${portfolio_value:,.2f}")
    print(f"  Reconciliation: {recon_status}")
    
    conn.close()
    return True

def main():
    """Run all verifications"""
    print("\n" + "="*80)
    print("PHASE 5 DAY 1 VERIFICATION")
    print("="*80)
    
    results = []
    
    results.append(("Database Schema", verify_database_schema()))
    results.append(("System Dry Run", run_system(dry_run=True)))
    results.append(("System Real Run", run_system(dry_run=False)))
    results.append(("Broker State", verify_broker_state()))
    results.append(("Terminal States", verify_terminal_states()))
    results.append(("Trades", verify_trades()))
    results.append(("Artifacts", verify_artifacts()))
    results.append(("Broker Snapshot", verify_broker_state_snapshot()))
    
    print("\n" + "="*80)
    print("VERIFICATION SUMMARY")
    print("="*80)
    
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")
    
    all_passed = all(result[1] for result in results)
    
    print("\n" + "="*80)
    if all_passed:
        print("✅ ALL VERIFICATIONS PASSED")
        print("="*80)
        print("\nPhase 5 is operational and ready for Day 1 paper trading.")
        return 0
    else:
        print("❌ SOME VERIFICATIONS FAILED")
        print("="*80)
        print("\nPlease fix the issues above before proceeding.")
        return 1

if __name__ == '__main__':
    sys.exit(main())
