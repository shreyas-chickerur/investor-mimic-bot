#!/usr/bin/env python3
"""
Database Sync Script
Synchronizes the local trading database with current Alpaca positions
"""
import os
import sys
from pathlib import Path
from datetime import datetime
import sqlite3

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from dotenv import load_dotenv
load_dotenv()

from alpaca.trading.client import TradingClient

def sync_positions():
    """Sync database with Alpaca positions"""
    
    # Get Alpaca credentials
    api_key = os.getenv('ALPACA_API_KEY')
    secret_key = os.getenv('ALPACA_SECRET_KEY')
    
    if not api_key or not secret_key:
        print("ERROR: Missing Alpaca credentials")
        sys.exit(1)
    
    # Connect to Alpaca
    print("Connecting to Alpaca...")
    trading_client = TradingClient(api_key, secret_key, paper=True)
    
    # Get current positions
    positions = trading_client.get_all_positions()
    print(f"Found {len(positions)} positions in Alpaca")
    
    # Connect to database
    db_path = Path(__file__).parent.parent / 'data' / 'trading_system.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Clear existing open positions
    cursor.execute("UPDATE positions SET status = 'synced_closed' WHERE status = 'open'")
    print(f"Cleared {cursor.rowcount} stale positions from database")
    
    # Import current positions
    today = datetime.now().date().isoformat()
    imported = 0
    
    for pos in positions:
        # Insert as open position
        cursor.execute('''
            INSERT INTO positions (symbol, entry_date, entry_price, shares, position_value, status)
            VALUES (?, ?, ?, ?, ?, 'open')
        ''', (
            pos.symbol,
            today,  # We don't have actual entry date, use today
            float(pos.avg_entry_price),
            int(pos.qty),
            float(pos.market_value),
        ))
        imported += 1
        print(f"  Imported: {pos.symbol} - {pos.qty} shares @ ${pos.avg_entry_price}")
    
    conn.commit()
    conn.close()
    
    print(f"\n✅ Synced {imported} positions to database")
    print(f"Database now matches Alpaca state")

if __name__ == '__main__':
    sync_positions()
