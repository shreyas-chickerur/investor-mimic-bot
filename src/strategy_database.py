#!/usr/bin/env python3
"""
Strategy Performance Database
Tracks all strategies, trades, and performance metrics
"""
import sqlite3
from typing import List, Dict, Optional
from datetime import datetime
import json


class StrategyDatabase:
    """Database for multi-strategy performance tracking"""
    
    def __init__(self, db_path='data/strategy_performance.db'):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Initialize database tables"""
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
        
        # Individual trades
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
        
        conn.commit()
        conn.close()
    
    def create_strategy(self, name: str, description: str, capital: float) -> int:
        """Create a new strategy"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO strategies (name, description, capital_allocation, initial_capital)
            VALUES (?, ?, ?, ?)
        ''', (name, description, capital, capital))
        
        strategy_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return strategy_id
    
    def get_all_strategies(self) -> List[Dict]:
        """Get all strategies"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM strategies ORDER BY id')
        rows = cursor.fetchall()
        conn.close()
        
        return [
            {
                'id': row[0],
                'name': row[1],
                'description': row[2],
                'capital_allocation': row[3],
                'initial_capital': row[4],
                'status': row[5],
                'created_at': row[6]
            }
            for row in rows
        ]
    
    def save_performance(self, strategy_id: int, metrics: Dict):
        """Save daily performance snapshot"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO strategy_performance 
            (strategy_id, date, portfolio_value, cash, positions_value, 
             total_return_pct, num_positions, num_trades_today)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            strategy_id,
            datetime.now().strftime('%Y-%m-%d'),
            metrics['portfolio_value'],
            metrics['cash'],
            metrics['positions_value'],
            metrics['return_pct'],
            metrics['num_positions'],
            metrics.get('trades_today', 0)
        ))
        
        conn.commit()
        conn.close()
    
    def save_trade(self, strategy_id: int, trade: Dict):
        """Save a trade"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO strategy_trades 
            (strategy_id, symbol, action, shares, price, value, order_id, executed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            strategy_id,
            trade['symbol'],
            trade['action'],
            trade['shares'],
            trade['price'],
            trade['value'],
            trade.get('order_id'),
            trade.get('executed_at', datetime.now().isoformat())
        ))
        
        conn.commit()
        conn.close()
    
    def save_signal(self, strategy_id: int, signal: Dict):
        """Save a trading signal"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO strategy_signals 
            (strategy_id, symbol, signal, confidence, reasoning)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            strategy_id,
            signal['symbol'],
            signal['action'],
            signal.get('confidence', 0.0),
            signal.get('reasoning', '')
        ))
        
        conn.commit()
        conn.close()
    
    def log_signal(self, strategy_id: int, symbol: str, signal: str, confidence: float, reasoning: str):
        """Log a trading signal"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO strategy_signals 
            (strategy_id, symbol, signal, confidence, reasoning)
            VALUES (?, ?, ?, ?, ?)
        ''', (strategy_id, symbol, signal, confidence, reasoning))
        
        conn.commit()
        conn.close()
    
    def log_trade(self, strategy_id: int, symbol: str, action: str, shares: float, 
                  price: float, value: float, order_id: str):
        """Log a trade execution"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO strategy_trades 
            (strategy_id, symbol, action, shares, price, value, order_id, executed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (int(strategy_id), str(symbol), str(action), float(shares), 
              float(price), float(value), str(order_id) if order_id else None, 
              datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
    
    def record_daily_performance(self, strategy_id: int, portfolio_value: float, 
                                cash: float, positions_value: float, return_pct: float, 
                                num_positions: int):
        """Record daily performance snapshot"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO strategy_performance 
            (strategy_id, date, portfolio_value, cash, positions_value, 
             total_return_pct, num_positions, num_trades_today)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0)
        ''', (strategy_id, datetime.now().strftime('%Y-%m-%d'), 
              portfolio_value, cash, positions_value, return_pct, num_positions))
        
        conn.commit()
        conn.close()
    
    def get_latest_performance(self, strategy_id: int) -> Optional[Dict]:
        """Get latest performance for a strategy"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM strategy_performance 
            WHERE strategy_id = ? 
            ORDER BY date DESC LIMIT 1
        ''', (strategy_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'portfolio_value': row[3],
                'cash': row[4],
                'positions_value': row[5],
                'total_return_pct': row[6],
                'num_positions': row[8]
            }
        return None
    
    def get_strategy_performance(self, strategy_id: int, days: int = 30) -> List[Dict]:
        """Get performance history for a strategy"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT date, portfolio_value, total_return_pct, num_positions
            FROM strategy_performance
            WHERE strategy_id = ?
            ORDER BY date DESC
            LIMIT ?
        ''', (strategy_id, days))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [
            {
                'date': row[0],
                'portfolio_value': row[1],
                'return_pct': row[2],
                'num_positions': row[3]
            }
            for row in rows
        ]
    
    def get_strategy_trades(self, strategy_id: int, limit: Optional[int] = None) -> List[Dict]:
        """Get trade history for a strategy"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if limit is None:
            cursor.execute('''
                SELECT symbol, action, shares, price, value, executed_at, profit_loss, return_pct
                FROM strategy_trades
                WHERE strategy_id = ?
                ORDER BY executed_at DESC
            ''', (strategy_id,))
        else:
            cursor.execute('''
                SELECT symbol, action, shares, price, value, executed_at, profit_loss, return_pct
                FROM strategy_trades
                WHERE strategy_id = ?
                ORDER BY executed_at DESC
                LIMIT ?
            ''', (strategy_id, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [
            {
                'symbol': row[0],
                'action': row[1],
                'shares': row[2],
                'price': row[3],
                'value': row[4],
                'executed_at': row[5],
                'profit_loss': row[6],
                'return_pct': row[7]
            }
            for row in rows
        ]
    
    def get_comparison_data(self) -> List[Dict]:
        """Get latest performance data for all strategies"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                s.id,
                s.name,
                s.initial_capital,
                p.portfolio_value,
                p.total_return_pct,
                p.num_positions,
                (SELECT COUNT(*) FROM strategy_trades WHERE strategy_id = s.id) as total_trades
            FROM strategies s
            LEFT JOIN (
                SELECT strategy_id, portfolio_value, total_return_pct, num_positions
                FROM strategy_performance
                WHERE (strategy_id, date) IN (
                    SELECT strategy_id, MAX(date)
                    FROM strategy_performance
                    GROUP BY strategy_id
                )
            ) p ON s.id = p.strategy_id
            WHERE s.status = 'active'
            ORDER BY p.total_return_pct DESC
        ''')
        
        rows = cursor.fetchall()
        conn.close()
        
        return [
            {
                'id': row[0],
                'name': row[1],
                'initial_capital': row[2],
                'portfolio_value': row[3] or row[2],
                'return_pct': row[4] or 0.0,
                'num_positions': row[5] or 0,
                'total_trades': row[6]
            }
            for row in rows
        ]
