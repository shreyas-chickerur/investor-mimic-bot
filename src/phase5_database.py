#!/usr/bin/env python3
"""
Phase 5 Database Adapter
Single source of truth for Phase 5 paper trading operational validation
"""
import sqlite3
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import json


class Phase5Database:
    """Database adapter for Phase 5 with proper schema"""
    
    def __init__(self, db_path='trading.db'):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Initialize Phase 5 database schema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Strategies table
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
        
        # Signals table with asof_date and terminal state tracking
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                signal_type TEXT NOT NULL,
                confidence REAL,
                reasoning TEXT,
                asof_date TEXT NOT NULL,
                generated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                terminal_state TEXT,
                terminal_reason TEXT,
                terminal_at TEXT,
                FOREIGN KEY (strategy_id) REFERENCES strategies(id)
            )
        ''')
        
        # Trades table with execution costs
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_id INTEGER NOT NULL,
                signal_id INTEGER,
                symbol TEXT NOT NULL,
                action TEXT NOT NULL,
                shares REAL NOT NULL,
                requested_price REAL NOT NULL,
                exec_price REAL NOT NULL,
                slippage_cost REAL DEFAULT 0,
                commission_cost REAL DEFAULT 0,
                total_cost REAL DEFAULT 0,
                notional REAL NOT NULL,
                order_id TEXT,
                executed_at TEXT NOT NULL,
                pnl REAL,
                FOREIGN KEY (strategy_id) REFERENCES strategies(id),
                FOREIGN KEY (signal_id) REFERENCES signals(id)
            )
        ''')
        
        # Positions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                shares REAL NOT NULL,
                avg_price REAL NOT NULL,
                current_price REAL,
                market_value REAL,
                unrealized_pnl REAL,
                last_updated TEXT NOT NULL,
                FOREIGN KEY (strategy_id) REFERENCES strategies(id),
                UNIQUE(strategy_id, symbol)
            )
        ''')
        
        # Broker state snapshots
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS broker_state (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_date TEXT NOT NULL,
                cash REAL NOT NULL,
                portfolio_value REAL NOT NULL,
                buying_power REAL NOT NULL,
                positions_json TEXT,
                reconciliation_status TEXT,
                discrepancies_json TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # System state
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS system_state (
                key TEXT PRIMARY KEY,
                value TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Strategy performance snapshots (optional but required by runner)
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

        self._ensure_trade_columns(cursor)
        
        conn.commit()
        conn.close()

    def _ensure_trade_columns(self, cursor: sqlite3.Cursor):
        """Ensure trades table has required execution cost columns."""
        cursor.execute("PRAGMA table_info(trades)")
        existing = {row[1] for row in cursor.fetchall()}

        required_columns = {
            'requested_price': 'REAL NOT NULL DEFAULT 0',
            'exec_price': 'REAL NOT NULL DEFAULT 0',
            'slippage_cost': 'REAL DEFAULT 0',
            'commission_cost': 'REAL DEFAULT 0',
            'total_cost': 'REAL DEFAULT 0',
            'notional': 'REAL NOT NULL DEFAULT 0'
        }

        for column, definition in required_columns.items():
            if column not in existing:
                cursor.execute(f"ALTER TABLE trades ADD COLUMN {column} {definition}")
    
    def create_strategy(self, name: str, description: str, capital: float) -> int:
        """Create or get strategy"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Try to get existing
        cursor.execute('SELECT id FROM strategies WHERE name = ?', (name,))
        row = cursor.fetchone()
        
        if row:
            strategy_id = row[0]
        else:
            cursor.execute('''
                INSERT INTO strategies (name, description, capital_allocation, initial_capital)
                VALUES (?, ?, ?, ?)
            ''', (name, description, capital, capital))
            strategy_id = cursor.lastrowid
            conn.commit()
        
        conn.close()
        return strategy_id
    
    def log_signal(self, strategy_id: int, symbol: str, signal_type: str, 
                   confidence: float, reasoning: str, asof_date: str) -> int:
        """Log a trading signal"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO signals 
            (strategy_id, symbol, signal_type, confidence, reasoning, asof_date)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (strategy_id, symbol, signal_type, confidence, reasoning, asof_date))
        
        signal_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return signal_id
    
    def update_signal_terminal_state(self, signal_id: int, terminal_state: str, reason: str):
        """Update signal with terminal state"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE signals 
            SET terminal_state = ?, terminal_reason = ?, terminal_at = ?
            WHERE id = ?
        ''', (terminal_state, reason, datetime.now().isoformat(), signal_id))
        
        conn.commit()
        conn.close()
    
    def log_trade(self, strategy_id: int, signal_id: Optional[int], symbol: str, 
                  action: str, shares: float, requested_price: float, exec_price: float,
                  slippage_cost: float, commission_cost: float, order_id: str) -> int:
        """Log a trade with execution costs"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        total_cost = slippage_cost + commission_cost
        
        # Calculate notional
        if action == 'BUY':
            notional = exec_price * shares + total_cost
        else:  # SELL
            notional = exec_price * shares - total_cost
        
        cursor.execute('''
            INSERT INTO trades 
            (strategy_id, signal_id, symbol, action, shares, requested_price, exec_price,
             slippage_cost, commission_cost, total_cost, notional, order_id, executed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (strategy_id, signal_id, symbol, action, shares, requested_price, exec_price,
              slippage_cost, commission_cost, total_cost, notional, order_id,
              datetime.now().isoformat()))
        
        trade_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return trade_id
    
    def update_position(self, strategy_id: int, symbol: str, shares: float, 
                       avg_price: float, current_price: Optional[float] = None):
        """Update or create position"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        market_value = shares * current_price if current_price else shares * avg_price
        unrealized_pnl = (current_price - avg_price) * shares if current_price else 0
        
        cursor.execute('''
            INSERT INTO positions 
            (strategy_id, symbol, shares, avg_price, current_price, market_value, 
             unrealized_pnl, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(strategy_id, symbol) DO UPDATE SET
                shares = excluded.shares,
                avg_price = excluded.avg_price,
                current_price = excluded.current_price,
                market_value = excluded.market_value,
                unrealized_pnl = excluded.unrealized_pnl,
                last_updated = excluded.last_updated
        ''', (strategy_id, symbol, shares, avg_price, current_price, market_value,
              unrealized_pnl, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
    
    def delete_position(self, strategy_id: int, symbol: str):
        """Delete a position (when fully closed)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM positions WHERE strategy_id = ? AND symbol = ?',
                      (strategy_id, symbol))
        
        conn.commit()
        conn.close()
    
    def save_broker_state(self, snapshot_date: str, cash: float, portfolio_value: float,
                         buying_power: float, positions: List[Dict],
                         reconciliation_status: str, discrepancies: List[str]):
        """Save broker state snapshot"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO broker_state 
            (snapshot_date, cash, portfolio_value, buying_power, positions_json,
             reconciliation_status, discrepancies_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (snapshot_date, cash, portfolio_value, buying_power,
              json.dumps(positions), reconciliation_status, json.dumps(discrepancies)))
        
        conn.commit()
        conn.close()
    
    def get_all_strategies(self) -> List[Dict]:
        """Get all strategies"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM strategies WHERE status = "active" ORDER BY id')
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_positions(self, strategy_id: Optional[int] = None) -> List[Dict]:
        """Get positions"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if strategy_id:
            cursor.execute('SELECT * FROM positions WHERE strategy_id = ?', (strategy_id,))
        else:
            cursor.execute('SELECT * FROM positions')
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]

    def get_strategy_trades(self, strategy_id: int) -> List[Dict]:
        """Get trades for a strategy."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, strategy_id, signal_id, symbol, action, shares,
                   exec_price AS price, requested_price, exec_price,
                   slippage_cost, commission_cost, total_cost, notional,
                   order_id, executed_at, pnl
            FROM trades
            WHERE strategy_id = ?
            ORDER BY executed_at
        ''', (strategy_id,))

        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def record_daily_performance(self, strategy_id: int, portfolio_value: float,
                                 cash: float, positions_value: float, return_pct: float,
                                 num_positions: int):
        """Record daily performance snapshot."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO strategy_performance
            (strategy_id, date, portfolio_value, cash, positions_value,
             total_return_pct, num_positions, num_trades_today)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0)
        ''', (
            strategy_id,
            datetime.now().strftime('%Y-%m-%d'),
            portfolio_value,
            cash,
            positions_value,
            return_pct,
            num_positions
        ))

        conn.commit()
        conn.close()

    def get_latest_performance(self, strategy_id: int) -> Optional[Dict]:
        """Get the latest performance record for a strategy."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM strategy_performance
            WHERE strategy_id = ?
            ORDER BY date DESC, created_at DESC
            LIMIT 1
        ''', (strategy_id,))

        row = cursor.fetchone()
        conn.close()

        return dict(row) if row else None

    def get_strategy_performance(self, strategy_id: int, days: int = 60) -> List[Dict]:
        """Get recent performance records for a strategy."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM strategy_performance
            WHERE strategy_id = ?
            ORDER BY date DESC, created_at DESC
            LIMIT ?
        ''', (strategy_id, days))

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]
    
    def get_todays_trades(self, date: str) -> List[Dict]:
        """Get trades for a specific date"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT t.*, s.name as strategy_name
            FROM trades t
            JOIN strategies s ON t.strategy_id = s.id
            WHERE DATE(t.executed_at) = ?
            ORDER BY t.executed_at
        ''', (date,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_signals_without_terminal_state(self, asof_date: str) -> List[Dict]:
        """Get signals that haven't reached terminal state"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM signals 
            WHERE asof_date = ? AND terminal_state IS NULL
        ''', (asof_date,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def verify_terminal_states(self, asof_date: str) -> Tuple[int, int]:
        """Verify all signals have terminal states. Returns (total, with_terminal)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM signals WHERE asof_date = ?', (asof_date,))
        total = cursor.fetchone()[0]
        
        cursor.execute('''
            SELECT COUNT(*) FROM signals 
            WHERE asof_date = ? AND terminal_state IS NOT NULL
        ''', (asof_date,))
        with_terminal = cursor.fetchone()[0]
        
        conn.close()
        
        return (total, with_terminal)
