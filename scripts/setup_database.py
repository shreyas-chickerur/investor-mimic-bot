#!/usr/bin/env python3
"""
Initialize trading database for CI/CD and fresh installations

Creates all required tables and initial state for the trading system.
Safe to run multiple times (idempotent).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import sqlite3
from strategy_database import StrategyDatabase


def init_database(db_path='trading.db'):
    """
    Initialize the trading database with all required tables and schemas.
    
    Args:
        db_path: Path to the database file
    """
    print(f'Initializing database: {db_path}')
    
    # Initialize via StrategyDatabase (creates strategies table)
    db = StrategyDatabase(db_path)
    print('✅ Strategies table created')
    
    # Create additional tables
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Trades table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy_id INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            action TEXT NOT NULL,
            shares INTEGER NOT NULL,
            price REAL NOT NULL,
            date TEXT NOT NULL,
            total_cost REAL,
            FOREIGN KEY (strategy_id) REFERENCES strategies(id)
        )
    ''')
    print('✅ Trades table created')
    
    # System state table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS system_state (
            key TEXT PRIMARY KEY,
            value TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    print('✅ System state table created')
    
    # Positions table (for tracking current positions)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy_id INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            shares INTEGER NOT NULL,
            avg_price REAL NOT NULL,
            last_updated TEXT NOT NULL,
            FOREIGN KEY (strategy_id) REFERENCES strategies(id),
            UNIQUE(strategy_id, symbol)
        )
    ''')
    print('✅ Positions table created')
    
    conn.commit()
    conn.close()
    
    print(f'\n✅ Database initialized successfully: {db_path}')
    print('   All tables created and ready for use')
    
    return True


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Initialize trading database')
    parser.add_argument('--db', default='trading.db', help='Database file path')
    args = parser.parse_args()
    
    success = init_database(args.db)
    sys.exit(0 if success else 1)
