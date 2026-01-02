#!/usr/bin/env python3
"""
Trading Database Adapter
Single source of truth for paper trading operational validation
"""
import sqlite3
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import json
import random
import string


class TradingDatabase:
    """Database adapter for trading system with proper schema"""
    
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
        """Initialize trading database schema"""
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
        
        # Create indexes for common queries (Phase 3.1 optimization)
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_signals_run_id ON signals(run_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_signals_symbol ON signals(symbol)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_signals_terminal_state ON signals(terminal_state)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_signals_generated_at ON signals(generated_at)')
        
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
                entry_price REAL,
                entry_date TEXT,
                atr REAL,
                stop_loss_price REAL,
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
        
        # Signal funnel tracking (portfolio-level per run)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS signal_funnel (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                strategy_id INTEGER NOT NULL,
                strategy_name TEXT NOT NULL,
                raw_signals_count INTEGER DEFAULT 0,
                after_regime_count INTEGER DEFAULT 0,
                after_correlation_count INTEGER DEFAULT 0,
                after_risk_count INTEGER DEFAULT 0,
                executed_count INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (strategy_id) REFERENCES strategies(id)
            )
        ''')
        
        # Signal rejection reasons (per-signal detail)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS signal_rejections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                signal_id INTEGER,
                strategy_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                stage TEXT NOT NULL,
                reason_code TEXT NOT NULL,
                details_json TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (signal_id) REFERENCES signals(id),
                FOREIGN KEY (strategy_id) REFERENCES strategies(id)
            )
        ''')
        
        # Order intents (idempotency tracking)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS order_intents (
                intent_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                strategy_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                target_qty REAL NOT NULL,
                status TEXT NOT NULL,
                broker_order_id TEXT,
                error_code TEXT,
                error_message TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                submitted_at TEXT,
                acked_at TEXT,
                filled_at TEXT,
                FOREIGN KEY (strategy_id) REFERENCES strategies(id)
            )
        ''')
        
        # Add indexes for performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_signal_funnel_run_id ON signal_funnel(run_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_signal_rejections_run_id ON signal_rejections(run_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_signal_rejections_stage ON signal_rejections(stage)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_order_intents_run_id ON order_intents(run_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_order_intents_status ON order_intents(status)')
        
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
                  slippage_cost: float, commission_cost: float, order_id: str, pnl: Optional[float] = None) -> int:
        """Log a trade with execution costs and P&L"""
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
             slippage_cost, commission_cost, total_cost, notional, order_id, executed_at, pnl)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (self.run_id, strategy_id, signal_id, symbol, action, shares, requested_price, exec_price,
              slippage_cost, commission_cost, total_cost, notional, order_id,
              datetime.now().isoformat(), pnl))
        
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
        # Performance snapshots not yet implemented
        # Return empty list to avoid breaking dynamic allocation
        return []
    
    def get_latest_performance(self, strategy_id: int) -> Dict:
        """Get latest performance snapshot (stub - returns None for now)"""
        # Performance snapshots not yet implemented
        return None
    
    def record_daily_performance(self, strategy_id: int, **kwargs):
        """Record daily performance (stub - not yet implemented)"""
        # Daily performance snapshots not yet implemented
        # This is a no-op to maintain compatibility
        pass
    
    def save_signal_funnel(self, strategy_id: int, strategy_name: str, 
                           raw: int, regime: int, correlation: int, risk: int, executed: int):
        """Save signal funnel counts for a strategy"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO signal_funnel 
            (run_id, strategy_id, strategy_name, raw_signals_count, after_regime_count,
             after_correlation_count, after_risk_count, executed_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (self.run_id, strategy_id, strategy_name, raw, regime, correlation, risk, executed))
        conn.commit()
        conn.close()
    
    def log_signal_rejection(self, strategy_id: int, symbol: str, stage: str, 
                             reason_code: str, details: dict = None, signal_id: int = None):
        """Log why a signal was rejected"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO signal_rejections 
            (run_id, signal_id, strategy_id, symbol, stage, reason_code, details_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (self.run_id, signal_id, strategy_id, symbol, stage, reason_code, 
              json.dumps(details) if details else None))
        conn.commit()
        conn.close()
    
    def create_order_intent(self, strategy_id: int, symbol: str, side: str, 
                           target_qty: float) -> str:
        """Create order intent with deterministic ID"""
        import hashlib
        timestamp_bucket = datetime.now().strftime('%Y%m%d_%H')
        intent_string = f"{self.run_id}_{strategy_id}_{symbol}_{side}_{target_qty}_{timestamp_bucket}"
        intent_id = hashlib.sha256(intent_string.encode()).hexdigest()[:16]
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT intent_id, status FROM order_intents WHERE intent_id = ?', (intent_id,))
        existing = cursor.fetchone()
        
        if existing:
            conn.close()
            return existing[0]
        
        cursor.execute('''
            INSERT INTO order_intents 
            (intent_id, run_id, strategy_id, symbol, side, target_qty, status)
            VALUES (?, ?, ?, ?, ?, ?, 'CREATED')
        ''', (intent_id, self.run_id, strategy_id, symbol, side, target_qty))
        conn.commit()
        conn.close()
        
        return intent_id
    
    def update_order_intent_status(self, intent_id: str, status: str, 
                                   broker_order_id: str = None, error: str = None):
        """Update order intent status"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        timestamp_field = {
            'SUBMITTED': 'submitted_at',
            'ACKED': 'acked_at',
            'FILLED': 'filled_at'
        }.get(status)
        
        if timestamp_field:
            cursor.execute(f'''
                UPDATE order_intents 
                SET status = ?, broker_order_id = ?, {timestamp_field} = ?
                WHERE intent_id = ?
            ''', (status, broker_order_id, datetime.now().isoformat(), intent_id))
        else:
            cursor.execute('''
                UPDATE order_intents 
                SET status = ?, broker_order_id = ?, error_message = ?
                WHERE intent_id = ?
            ''', (status, broker_order_id, error, intent_id))
        
        conn.commit()
        conn.close()
    
    def get_signal_funnel_summary(self, run_id: str = None) -> List[Dict]:
        """Get funnel summary for email reporting"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        rid = run_id or self.run_id
        cursor.execute('SELECT * FROM signal_funnel WHERE run_id = ?', (rid,))
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_signal_rejections_summary(self, run_id: str = None, limit: int = 10) -> List[Dict]:
        """Get top rejection reasons for email reporting"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        rid = run_id or self.run_id
        cursor.execute('''
            SELECT stage, reason_code, COUNT(*) as count, 
                   GROUP_CONCAT(symbol, ', ') as symbols
            FROM signal_rejections 
            WHERE run_id = ?
            GROUP BY stage, reason_code
            ORDER BY count DESC
            LIMIT ?
        ''', (rid, limit))
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_order_intent_by_id(self, intent_id: str) -> Optional[Dict]:
        """Get order intent by ID"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM order_intents WHERE intent_id = ?', (intent_id,))
        row = cursor.fetchone()
        conn.close()
        
        return dict(row) if row else None
    
    def check_duplicate_order_intent(self, strategy_id: int, symbol: str, 
                                    side: str, target_qty: float) -> Optional[str]:
        """
        Check if an order intent already exists for this exact order.
        
        Returns intent_id if duplicate found, None otherwise.
        """
        intent_id = self.create_order_intent(strategy_id, symbol, side, target_qty)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT intent_id, status FROM order_intents
            WHERE intent_id = ?
        ''', (intent_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result and result[1] in ['SUBMITTED', 'ACKED', 'FILLED']:
            return result[0]
        
        return None
    
    def count_duplicate_order_intents(self, hours: int = 24) -> int:
        """
        Count duplicate order intents in the last N hours.
        
        Args:
            hours: Number of hours to look back
        
        Returns:
            Count of duplicate intents
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cutoff_time = (datetime.now() - timedelta(hours=hours)).isoformat()
        
        cursor.execute('''
            SELECT intent_id, COUNT(*) as count
            FROM order_intents
            WHERE created_at >= ?
            GROUP BY intent_id
            HAVING count > 1
        ''', (cutoff_time,))
        
        duplicates = cursor.fetchall()
        conn.close()
        
        return len(duplicates)
    
    def get_system_state(self, key: str) -> Optional[str]:
        """
        Get system state value by key.
        
        Args:
            key: State key
        
        Returns:
            State value or None if not found
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT value FROM system_state
            WHERE key = ?
        ''', (key,))
        
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result else None
    
    def set_system_state(self, key: str, value: str):
        """
        Set system state value.
        
        Args:
            key: State key
            value: State value
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO system_state (key, value, timestamp)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        ''', (key, value))
        
        conn.commit()
        conn.close()


# Backward compatibility alias
Phase5Database = TradingDatabase
