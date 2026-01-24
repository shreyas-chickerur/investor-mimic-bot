#!/usr/bin/env python3
"""
Sync Local Database with Broker State

Fetches current broker state and updates local database to match.
Use this to resolve reconciliation failures or initialize database.
"""
import sys
import os
import sqlite3
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.risk.broker_reconciler import BrokerReconciler
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def sync_broker_to_database(db_path='trading.db'):
    """
    Sync broker state to local database
    
    - Clears local positions
    - Fetches broker positions and adds them
    - Updates portfolio state
    """
    logger.info("="*80)
    logger.info("SYNCING LOCAL DATABASE WITH BROKER STATE")
    logger.info("="*80)
    
    # Get broker state
    reconciler = BrokerReconciler()
    broker_state = reconciler.get_broker_state()
    
    if not broker_state:
        logger.error("❌ Failed to fetch broker state")
        return False
    
    logger.info(f"\nBroker State:")
    logger.info(f"  Positions: {len(broker_state['positions'])}")
    logger.info(f"  Cash: ${broker_state['cash']:,.2f}")
    logger.info(f"  Portfolio Value: ${broker_state['portfolio_value']:,.2f}")
    
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Clear existing positions
        cursor.execute("DELETE FROM positions")
        logger.info(f"\n✅ Cleared local positions")
        
        # Add broker positions
        # First ensure we have a default strategy
        cursor.execute("SELECT id FROM strategies WHERE name = 'BROKER_SYNC' LIMIT 1")
        result = cursor.fetchone()
        if result:
            strategy_id = result[0]
        else:
            cursor.execute("""
                INSERT INTO strategies (name, description, capital_allocation, initial_capital, status)
                VALUES ('BROKER_SYNC', 'Positions synced from broker', 1.0, ?, 'active')
            """, (broker_state['portfolio_value'],))
            strategy_id = cursor.lastrowid
            logger.info(f"✅ Created BROKER_SYNC strategy (id={strategy_id})")
        
        # Insert broker positions
        for symbol, pos_data in broker_state['positions'].items():
            cursor.execute("""
                INSERT INTO positions (
                    strategy_id, symbol, shares, avg_price, 
                    current_price, market_value, unrealized_pnl, last_updated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                strategy_id,
                symbol,
                pos_data['qty'],
                pos_data['avg_price'],
                pos_data['avg_price'],  # Use avg_price as current for now
                pos_data['market_value'],
                pos_data['unrealized_pl'],
                datetime.now().isoformat()
            ))
            logger.info(f"  ✅ Added {symbol}: {pos_data['qty']} shares @ ${pos_data['avg_price']:.2f}")
        
        # Update broker_state snapshot
        cursor.execute("""
            INSERT INTO broker_state (
                run_id, snapshot_date, snapshot_type, cash, portfolio_value,
                buying_power, positions_json, reconciliation_status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            'MANUAL_SYNC',
            datetime.now().strftime('%Y-%m-%d'),
            'SYNC',
            broker_state['cash'],
            broker_state['portfolio_value'],
            broker_state['buying_power'],
            str(broker_state['positions']),
            'SYNCED',
            datetime.now().isoformat()
        ))
        
        conn.commit()
        logger.info(f"\n✅ Database synced successfully")
        logger.info(f"  Positions: {len(broker_state['positions'])}")
        logger.info(f"  Cash: ${broker_state['cash']:,.2f}")
        logger.info(f"  Portfolio Value: ${broker_state['portfolio_value']:,.2f}")
        
        # Verify sync
        cursor.execute("SELECT COUNT(*) FROM positions")
        local_count = cursor.fetchone()[0]
        
        if local_count == len(broker_state['positions']):
            logger.info(f"\n✅ VERIFICATION PASSED - {local_count} positions in sync")
            return True
        else:
            logger.error(f"\n❌ VERIFICATION FAILED - Local: {local_count}, Broker: {len(broker_state['positions'])}")
            return False
            
    except Exception as e:
        logger.error(f"\n❌ Sync failed: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    success = sync_broker_to_database()
    sys.exit(0 if success else 1)
