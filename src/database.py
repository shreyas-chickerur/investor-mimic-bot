#!/usr/bin/env python3
"""
Phase 5 Database Adapter
Single source of truth for Phase 5 paper trading operational validation
"""
import sqlite3
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import json
import random
import string


class Phase5Database:
    """Database adapter for Phase 5 with proper schema"""
    
    def __init__(self, db_path='trading.db', run_id=None):
        self.db_path = db_path
        self.run_id = run_id or self._generate_run_id()
        self._init_database()
    
    def _generate_run_id(self) -> str:
        """Generate unique run_id: YYYYMMDD_HHMMSS_<random_suffix>"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
        return f"{timestamp}_{suffix}"
    
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
                run_id TEXT NOT NULL,
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
        
        # Add index on run_id for performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_signals_run_id ON signals(run_id)')
        
        # Trades table with execution costs
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
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
        
        # Add index on run_id for performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_trades_run_id ON trades(run_id)')
        
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
                run_id TEXT NOT NULL,
                snapshot_date TEXT NOT NULL,
                snapshot_type TEXT NOT NULL,
                cash REAL NOT NULL,
                portfolio_value REAL NOT NULL,
                buying_power REAL NOT NULL,
                positions_json TEXT,
                reconciliation_status TEXT,
                discrepancies_json TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Add index on run_id for performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_broker_state_run_id ON broker_state(run_id)')
        
        # System state
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS system_state (
                key TEXT PRIMARY KEY,
                value TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
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
            (run_id, strategy_id, symbol, signal_type, confidence, reasoning, asof_date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (self.run_id, strategy_id, symbol, signal_type, confidence, reasoning, asof_date))
        
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
            (run_id, strategy_id, signal_id, symbol, action, shares, requested_price, exec_price,
             slippage_cost, commission_cost, total_cost, notional, order_id, executed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (self.run_id, strategy_id, signal_id, symbol, action, shares, requested_price, exec_price,
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
    
    def save_broker_state(self, snapshot_date: str, snapshot_type: str, cash: float, 
                         portfolio_value: float, buying_power: float, positions: List[Dict],
                         reconciliation_status: str, discrepancies: List[str]):
        """Save broker state snapshot
        
        Args:
            snapshot_type: 'START', 'RECONCILIATION', or 'END'
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO broker_state 
            (run_id, snapshot_date, snapshot_type, cash, portfolio_value, buying_power, 
             positions_json, reconciliation_status, discrepancies_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (self.run_id, snapshot_date, snapshot_type, cash, portfolio_value, buying_power,
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

    def get_position(self, strategy_id: int, symbol: str) -> Optional[Dict]:
        """Get a single position for a strategy and symbol."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            'SELECT * FROM positions WHERE strategy_id = ? AND symbol = ?',
            (strategy_id, symbol)
        )
        row = cursor.fetchone()
        conn.close()

        return dict(row) if row else None
    
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
    
    def get_signals_without_terminal_state(self, run_id: Optional[str] = None) -> List[Dict]:
        """Get signals that haven't reached terminal state for a run"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        rid = run_id or self.run_id
        cursor.execute('''
            SELECT * FROM signals 
            WHERE run_id = ? AND terminal_state IS NULL
        ''', (rid,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def verify_terminal_states(self, run_id: Optional[str] = None) -> Tuple[int, int]:
        """Verify all signals have terminal states. Returns (total, with_terminal)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        rid = run_id or self.run_id
        cursor.execute('SELECT COUNT(*) FROM signals WHERE run_id = ?', (rid,))
        total = cursor.fetchone()[0]
        
        cursor.execute('''
            SELECT COUNT(*) FROM signals 
            WHERE run_id = ? AND terminal_state IS NOT NULL
        ''', (rid,))
        with_terminal = cursor.fetchone()[0]
        
        conn.close()
        
        return (total, with_terminal)
    
    def get_strategy_trades(self, strategy_id: int) -> List[Dict]:
        """Get all trades for a strategy"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM trades 
            WHERE strategy_id = ?
            ORDER BY executed_at DESC
        ''', (strategy_id,))
        
        rows = cursor.fetchall()
        conn.close()

        trades = [dict(row) for row in rows]
        for trade in trades:
            if trade.get('price') is None:
                trade['price'] = trade.get('exec_price') or trade.get('requested_price') or 0.0

        return trades
    
    def get_strategy_performance(self, strategy_id: int, days: int = 30) -> List[Dict]:
        """Get strategy performance history (stub - returns empty for now)"""
        # Phase 5 doesn't track performance snapshots yet
        # Return empty list to avoid breaking dynamic allocation
        return []
    
    def get_latest_performance(self, strategy_id: int) -> Dict:
        """Get latest performance snapshot (stub - returns None for now)"""
        # Phase 5 doesn't track performance snapshots yet
        return None
    
    def record_daily_performance(self, strategy_id: int, **kwargs):
        """Record daily performance (stub - Phase 5 doesn't track this yet)"""
        # Phase 5 doesn't track daily performance snapshots
        # This is a no-op to maintain compatibility
        pass
