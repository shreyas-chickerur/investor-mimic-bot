#!/usr/bin/env python3
"""
Pending Signals Manager
Persists blocked-but-valid signals and re-evaluates them over N days
"""
import logging
from typing import List, Dict
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)


class PendingSignalsManager:
    """Manages pending signals with decay window"""
    
    def __init__(self, db, decay_days: int = 3):
        """
        Initialize pending signals manager
        
        Args:
            db: Database instance
            decay_days: Number of days to keep pending signals
        """
        self.db = db
        self.decay_days = decay_days
        self._ensure_table_exists()
    
    def _ensure_table_exists(self):
        """Create pending_signals table if not exists"""
        import sqlite3
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pending_signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                signal_data_json TEXT NOT NULL,
                blocked_reason TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                retry_count INTEGER DEFAULT 0,
                last_retry_at TEXT,
                status TEXT DEFAULT 'PENDING',
                FOREIGN KEY (strategy_id) REFERENCES strategies(id)
            )
        ''')
        
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_pending_signals_status ON pending_signals(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_pending_signals_expires ON pending_signals(expires_at)')
        
        conn.commit()
        conn.close()
    
    def add_pending_signal(self, strategy_id: int, symbol: str, 
                          signal_data: Dict, blocked_reason: str):
        """Add a signal to pending queue"""
        import sqlite3
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        
        created_at = datetime.now()
        expires_at = created_at + timedelta(days=self.decay_days)
        
        cursor.execute('''
            INSERT INTO pending_signals 
            (strategy_id, symbol, signal_data_json, blocked_reason, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (strategy_id, symbol, json.dumps(signal_data), blocked_reason,
              created_at.isoformat(), expires_at.isoformat()))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Added pending signal: {symbol} (reason: {blocked_reason}, expires: {expires_at.date()})")
    
    def get_pending_signals(self, strategy_id: int = None) -> List[Dict]:
        """Get all active pending signals"""
        import sqlite3
        conn = sqlite3.connect(self.db.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        
        if strategy_id:
            cursor.execute('''
                SELECT * FROM pending_signals 
                WHERE status = 'PENDING' AND expires_at > ?
                AND strategy_id = ?
                ORDER BY created_at
            ''', (now, strategy_id))
        else:
            cursor.execute('''
                SELECT * FROM pending_signals 
                WHERE status = 'PENDING' AND expires_at > ?
                ORDER BY created_at
            ''', (now,))
        
        rows = cursor.fetchall()
        conn.close()
        
        pending = []
        for row in rows:
            signal_dict = dict(row)
            signal_dict['signal_data'] = json.loads(signal_dict['signal_data_json'])
            pending.append(signal_dict)
        
        return pending
    
    def update_pending_status(self, pending_id: int, status: str):
        """Update status of pending signal"""
        import sqlite3
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE pending_signals 
            SET status = ?, last_retry_at = ?, retry_count = retry_count + 1
            WHERE id = ?
        ''', (status, datetime.now().isoformat(), pending_id))
        
        conn.commit()
        conn.close()
    
    def cleanup_expired(self):
        """Remove expired pending signals"""
        import sqlite3
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        
        cursor.execute('''
            UPDATE pending_signals 
            SET status = 'EXPIRED'
            WHERE status = 'PENDING' AND expires_at <= ?
        ''', (now,))
        
        expired_count = cursor.rowcount
        conn.commit()
        conn.close()
        
        if expired_count > 0:
            logger.info(f"Expired {expired_count} pending signals")
