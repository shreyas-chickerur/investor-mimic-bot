#!/usr/bin/env python3
"""
Database Schema Extensions for News-Based Trading
Adds support for market data, news, and causal chains
"""
import sqlite3
from pathlib import Path
from typing import List, Dict, Optional
import json
from datetime import datetime


class TradingDatabase:
    """Extended database with news and causal chain support"""
    
    def __init__(self, db_path='data/trading_system.db'):
        self.db_path = db_path
        self._setup_extended_schema()
    
    def _setup_extended_schema(self):
        """Create extended tables for news-based trading"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Market data table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS market_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                index_name TEXT NOT NULL,
                value TEXT,
                change REAL,
                change_pct REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Stock news table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stock_news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                title TEXT NOT NULL,
                summary TEXT,
                sentiment TEXT,
                source TEXT,
                published_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Causal chains table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS causal_chains (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                trade_date TEXT NOT NULL,
                chain_json TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Current holdings with extended info
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS current_holdings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL UNIQUE,
                shares REAL NOT NULL,
                avg_price REAL NOT NULL,
                current_price REAL,
                last_updated TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Approval tokens table (one-time use)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS approval_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT NOT NULL,
                token TEXT UNIQUE NOT NULL,
                used BOOLEAN DEFAULT 0,
                expires_at TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Trade executions table (Alpaca order tracking)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trade_executions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                shares REAL NOT NULL,
                action TEXT NOT NULL,
                decision TEXT NOT NULL,
                order_id TEXT,
                status TEXT,
                executed_price REAL,
                executed_at TEXT,
                error TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Alpaca account snapshots table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS account_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                portfolio_value REAL NOT NULL,
                cash REAL NOT NULL,
                equity REAL NOT NULL,
                buying_power REAL NOT NULL,
                snapshot_date TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # User-friendly error messages table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS error_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                error_pattern TEXT NOT NULL UNIQUE,
                user_friendly_message TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        
        # Populate default error messages
        self._populate_default_error_messages()
    
    def save_market_data(self, market_data: Dict):
        """Save market overview data"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        date = datetime.now().strftime('%Y-%m-%d')
        
        for index_name, data in market_data.items():
            cursor.execute('''
                INSERT INTO market_data (date, index_name, value, change, change_pct)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                date,
                index_name,
                data.get('value', ''),
                data.get('change', 0),
                data.get('change_pct', 0)
            ))
        
        conn.commit()
        conn.close()
    
    def get_latest_market_data(self) -> Dict:
        """Get most recent market data"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT index_name, value, change, change_pct
            FROM market_data
            WHERE date = (SELECT MAX(date) FROM market_data)
        ''')
        
        rows = cursor.fetchall()
        conn.close()
        
        market_data = {}
        for row in rows:
            market_data[row[0]] = {
                'value': row[1],
                'change': row[2],
                'change_pct': row[3]
            }
        
        return market_data
    
    def save_stock_news(self, symbol: str, title: str, summary: str, sentiment: str, source: str = 'API'):
        """Save news about a stock"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO stock_news (symbol, title, summary, sentiment, source, published_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            symbol,
            title,
            summary,
            sentiment,
            source,
            datetime.now().isoformat()
        ))
        
        conn.commit()
        conn.close()
    
    def get_holdings_news(self, limit: int = 5) -> List[Dict]:
        """Get recent news for current holdings"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT sn.symbol, sn.title, sn.summary, sn.sentiment
            FROM stock_news sn
            INNER JOIN current_holdings ch ON sn.symbol = ch.symbol
            ORDER BY sn.created_at DESC
            LIMIT ?
        ''', (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [
            {
                'ticker': row[0],
                'title': row[1],
                'summary': row[2],
                'sentiment': row[3]
            }
            for row in rows
        ]
    
    def save_causal_chain(self, symbol: str, causal_chain: List[Dict]):
        """Save causal chain for a trade"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO causal_chains (symbol, trade_date, chain_json)
            VALUES (?, ?, ?)
        ''', (
            symbol,
            datetime.now().strftime('%Y-%m-%d'),
            json.dumps(causal_chain)
        ))
        
        conn.commit()
        conn.close()
    
    def get_causal_chain(self, symbol: str) -> Optional[List[Dict]]:
        """Get most recent causal chain for a symbol"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT chain_json
            FROM causal_chains
            WHERE symbol = ?
            ORDER BY created_at DESC
            LIMIT 1
        ''', (symbol,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return json.loads(row[0])
        return None
    
    def update_holding(self, symbol: str, shares: float, avg_price: float, current_price: float):
        """Update or insert current holding"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO current_holdings (symbol, shares, avg_price, current_price, last_updated)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(symbol) DO UPDATE SET
                shares = excluded.shares,
                avg_price = excluded.avg_price,
                current_price = excluded.current_price,
                last_updated = excluded.last_updated
        ''', (
            symbol,
            shares,
            avg_price,
            current_price,
            datetime.now().isoformat()
        ))
        
        conn.commit()
        conn.close()
    
    def get_current_holdings(self) -> List[Dict]:
        """Get all current holdings"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT symbol, shares, avg_price, current_price
            FROM current_holdings
            WHERE shares > 0
            ORDER BY symbol
        ''')
        
        rows = cursor.fetchall()
        conn.close()
        
        return [
            {
                'symbol': row[0],
                'shares': row[1],
                'avg_price': row[2],
                'current_price': row[3] or row[2]
            }
            for row in rows
        ]
    
    def save_account_snapshot(self, portfolio_value: float, cash: float, equity: float, buying_power: float):
        """Save Alpaca account snapshot"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO account_snapshots (portfolio_value, cash, equity, buying_power, snapshot_date)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            portfolio_value,
            cash,
            equity,
            buying_power,
            datetime.now().strftime('%Y-%m-%d')
        ))
        
        conn.commit()
        conn.close()
    
    def save_trade_execution(self, request_id: str, symbol: str, shares: float, action: str, 
                            decision: str, order_id: str = None, status: str = None, 
                            executed_price: float = None, error: str = None):
        """Save trade execution result"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Convert None to empty string for TEXT fields to avoid binding errors
        cursor.execute('''
            INSERT INTO trade_executions 
            (request_id, symbol, shares, action, decision, order_id, status, executed_price, executed_at, error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            request_id,
            symbol,
            shares,
            action,
            decision,
            str(order_id) if order_id else None,
            str(status) if status else None,
            executed_price,
            datetime.now().isoformat() if order_id else None,
            str(error) if error else None
        ))
        
        conn.commit()
        conn.close()
    
    def get_trade_executions(self, request_id: str = None, limit: int = 100) -> List[Dict]:
        """Get trade execution history"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if request_id:
            cursor.execute('''
                SELECT symbol, shares, action, decision, order_id, status, executed_price, executed_at, error
                FROM trade_executions
                WHERE request_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            ''', (request_id, limit))
        else:
            cursor.execute('''
                SELECT symbol, shares, action, decision, order_id, status, executed_price, executed_at, error
                FROM trade_executions
                ORDER BY created_at DESC
                LIMIT ?
            ''', (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [
            {
                'symbol': row[0],
                'shares': row[1],
                'action': row[2],
                'decision': row[3],
                'order_id': row[4],
                'status': row[5],
                'executed_price': row[6],
                'executed_at': row[7],
                'error': row[8]
            }
            for row in rows
        ]
    
    def _populate_default_error_messages(self):
        """Populate default user-friendly error messages"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        default_messages = [
            ('wash trade', 'Cannot execute - you have a conflicting order for this stock'),
            ('insufficient', 'Not enough cash available'),
            ('not found', 'Stock symbol not found'),
            ('market closed', 'Market is currently closed'),
            ('buying power', 'Insufficient buying power'),
            ('rejected', 'Order was rejected by the broker'),
            ('timeout', 'Request timed out - please try again'),
            ('connection', 'Connection error - please check your internet'),
        ]
        
        for pattern, message in default_messages:
            try:
                cursor.execute('''
                    INSERT OR IGNORE INTO error_messages (error_pattern, user_friendly_message)
                    VALUES (?, ?)
                ''', (pattern, message))
            except:
                pass
        
        conn.commit()
        conn.close()
    
    def get_user_friendly_message(self, error_text: str) -> str:
        """Get user-friendly message for an error"""
        if not error_text:
            return '-'
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT error_pattern, user_friendly_message FROM error_messages')
        patterns = cursor.fetchall()
        conn.close()
        
        error_lower = error_text.lower()
        for pattern, message in patterns:
            if pattern.lower() in error_lower:
                return message
        
        return 'Trade could not be executed - please check your Alpaca account'
    
    def get_email_data(self, proposed_trades: List[Dict]) -> Dict:
        """
        Get all data needed for approval email
        Populates from database dynamically
        """
        # Get market data
        market_data = self.get_latest_market_data()
        
        # Get current holdings
        current_holdings = self.get_current_holdings()
        
        # Get news about holdings
        holdings_news = self.get_holdings_news(limit=5)
        
        # Get or generate causal chains for proposed trades
        for trade in proposed_trades:
            symbol = trade['symbol']
            causal_chain = self.get_causal_chain(symbol)
            if causal_chain:
                trade['causal_chain'] = causal_chain
        
        return {
            'market_data': market_data,
            'current_holdings': current_holdings,
            'holdings_news': holdings_news,
            'trades': proposed_trades
        }
