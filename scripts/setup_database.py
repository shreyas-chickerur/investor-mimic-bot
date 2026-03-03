#!/usr/bin/env python3
"""
Initialize trading database for CI/CD and fresh installations

Creates all required tables and initial state for the trading system.
Safe to run multiple times (idempotent).
"""
import sys
import sqlite3
from pathlib import Path


def init_database(db_path='trading.db'):
    """
    Initialize the trading database with all required tables and schemas.
    
    Args:
        db_path: Path to the database file
    """
    print(f'Initializing database: {db_path}')
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Strategies table (from StrategyDatabase)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS strategies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            capital_allocation REAL NOT NULL,
            initial_capital REAL NOT NULL,
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    print('✅ Strategies table created')
    
    # Daily performance snapshots
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS strategy_performance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            portfolio_value REAL NOT NULL,
            cash REAL NOT NULL,
            positions_value REAL NOT NULL,
            total_return_pct REAL NOT NULL,
            daily_return_pct REAL,
            num_positions INTEGER,
            num_trades_today INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (strategy_id) REFERENCES strategies(id)
        )
    ''')
    
    # Individual trades (from StrategyDatabase)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS strategy_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy_id INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            action TEXT NOT NULL,
            shares REAL NOT NULL,
            price REAL NOT NULL,
            value REAL NOT NULL,
            order_id TEXT,
            executed_at TEXT NOT NULL,
            exit_price REAL,
            exit_at TEXT,
            profit_loss REAL,
            return_pct REAL,
            hold_days INTEGER,
            FOREIGN KEY (strategy_id) REFERENCES strategies(id)
        )
    ''')
    
    # Trading signals
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS strategy_signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy_id INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            signal TEXT NOT NULL,
            confidence REAL,
            reasoning TEXT,
            generated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (strategy_id) REFERENCES strategies(id)
        )
    ''')
    
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
    # Schema must match database.py TradingDatabase.update_position()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy_id INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            shares REAL NOT NULL,
            avg_price REAL,
            current_price REAL,
            market_value REAL,
            unrealized_pnl REAL,
            stop_loss_price REAL,
            entry_date TEXT,
            last_updated TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
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
