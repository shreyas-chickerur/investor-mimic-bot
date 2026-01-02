#!/usr/bin/env python3
"""
Comprehensive Logging and Alert System

Logs all critical events: transfers, trades, errors, performance
Ensures you're never blind to system activity
"""

import logging
import json
from datetime import datetime
from pathlib import Path
import sqlite3
from typing import Dict, Any, Optional

class TradingLogger:
    """Centralized logging for all trading activities"""
    
    def __init__(self, log_dir='logs', db_path='data/trading_system.db'):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        self.db_path = db_path
        
        # Set up file logging
        self._setup_file_logging()
        
        # Set up database logging
        self._setup_database_logging()
    
    def _setup_file_logging(self):
        """Configure file-based logging"""
        # Main log file
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.log_dir / 'trading.log'),
                logging.StreamHandler()
            ]
        )
        
        # Separate loggers for different categories
        self.trade_logger = self._create_logger('trades', 'trades.log')
        self.error_logger = self._create_logger('errors', 'errors.log')
        self.performance_logger = self._create_logger('performance', 'performance.log')
        self.transfer_logger = self._create_logger('transfers', 'transfers.log')
        self.alert_logger = self._create_logger('alerts', 'alerts.log')
    
    def _create_logger(self, name: str, filename: str) -> logging.Logger:
        """Create a specialized logger"""
        logger = logging.getLogger(name)
        logger.setLevel(logging.INFO)
        
        handler = logging.FileHandler(self.log_dir / filename)
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        ))
        logger.addHandler(handler)
        
        return logger
    
    def _setup_database_logging(self):
        """Create database tables for structured logging"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Activity log table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                category TEXT NOT NULL,
                event_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                message TEXT NOT NULL,
                details TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Trade log table (detailed)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trade_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                action TEXT NOT NULL,
                symbol TEXT NOT NULL,
                shares INTEGER,
                price REAL,
                value REAL,
                order_id TEXT,
                status TEXT,
                reason TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Error log table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS error_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                error_type TEXT NOT NULL,
                error_message TEXT NOT NULL,
                stack_trace TEXT,
                context TEXT,
                severity TEXT NOT NULL,
                resolved BOOLEAN DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Performance snapshots
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS performance_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                portfolio_value REAL,
                cash REAL,
                positions_value REAL,
                num_positions INTEGER,
                daily_return REAL,
                cumulative_return REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def log_trade(self, action: str, symbol: str, shares: int, price: float, 
                  order_id: Optional[str] = None, status: str = 'SUCCESS', 
                  reason: Optional[str] = None):
        """Log a trade execution"""
        timestamp = datetime.now().isoformat()
        value = shares * price
        
        # File log
        self.trade_logger.info(
            f"{action} {shares} shares of {symbol} @ ${price:.2f} "
            f"(${value:.2f}) - {status}"
        )
        
        # Database log
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO trade_log 
            (timestamp, action, symbol, shares, price, value, order_id, status, reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (timestamp, action, symbol, shares, price, value, order_id, status, reason))
        
        cursor.execute('''
            INSERT INTO activity_log 
            (timestamp, category, event_type, severity, message, details)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            timestamp, 'TRADE', action, 'INFO',
            f"{action} {shares} shares of {symbol}",
            json.dumps({'price': price, 'value': value, 'order_id': order_id})
        ))
        
        conn.commit()
        conn.close()
        
        # Alert if significant trade
        if value > 1000:
            self._send_alert(
                'LARGE_TRADE',
                f"Large {action}: {shares} shares of {symbol} (${value:.2f})",
                'INFO'
            )
    
    def log_transfer(self, transfer_type: str, amount: float, 
                    from_account: str, to_account: str, reason: str):
        """Log account transfers"""
        timestamp = datetime.now().isoformat()
        
        # File log
        self.transfer_logger.info(
            f"{transfer_type}: ${amount:.2f} from {from_account} to {to_account} - {reason}"
        )
        
        # Database log
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO activity_log 
            (timestamp, category, event_type, severity, message, details)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            timestamp, 'TRANSFER', transfer_type, 'INFO',
            f"Transfer ${amount:.2f}",
            json.dumps({
                'amount': amount,
                'from': from_account,
                'to': to_account,
                'reason': reason
            })
        ))
        conn.commit()
        conn.close()
    
    def log_error(self, error_type: str, error_message: str, 
                  stack_trace: Optional[str] = None, 
                  context: Optional[Dict] = None, 
                  severity: str = 'ERROR'):
        """Log errors with full context"""
        timestamp = datetime.now().isoformat()
        
        # File log
        self.error_logger.error(
            f"{error_type}: {error_message}\n"
            f"Context: {json.dumps(context) if context else 'None'}\n"
            f"Stack: {stack_trace if stack_trace else 'None'}"
        )
        
        # Database log
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO error_log 
            (timestamp, error_type, error_message, stack_trace, context, severity)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            timestamp, error_type, error_message, 
            stack_trace, json.dumps(context) if context else None, 
            severity
        ))
        
        cursor.execute('''
            INSERT INTO activity_log 
            (timestamp, category, event_type, severity, message, details)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            timestamp, 'ERROR', error_type, severity,
            error_message,
            json.dumps(context) if context else None
        ))
        
        conn.commit()
        conn.close()
        
        # Alert on critical errors
        if severity in ['CRITICAL', 'ERROR']:
            self._send_alert(
                'ERROR',
                f"{error_type}: {error_message}",
                severity
            )
    
    def log_performance(self, portfolio_value: float, cash: float, 
                       positions_value: float, num_positions: int,
                       daily_return: float = 0.0, cumulative_return: float = 0.0):
        """Log performance snapshot"""
        timestamp = datetime.now().isoformat()
        
        # File log
        self.performance_logger.info(
            f"Portfolio: ${portfolio_value:.2f} | Cash: ${cash:.2f} | "
            f"Positions: ${positions_value:.2f} ({num_positions}) | "
            f"Daily: {daily_return:+.2f}% | Cumulative: {cumulative_return:+.2f}%"
        )
        
        # Database log
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO performance_snapshots 
            (timestamp, portfolio_value, cash, positions_value, num_positions, 
             daily_return, cumulative_return)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (timestamp, portfolio_value, cash, positions_value, num_positions,
              daily_return, cumulative_return))
        
        cursor.execute('''
            INSERT INTO activity_log 
            (timestamp, category, event_type, severity, message, details)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            timestamp, 'PERFORMANCE', 'SNAPSHOT', 'INFO',
            f"Portfolio: ${portfolio_value:.2f}",
            json.dumps({
                'cash': cash,
                'positions_value': positions_value,
                'num_positions': num_positions,
                'daily_return': daily_return,
                'cumulative_return': cumulative_return
            })
        ))
        
        conn.commit()
        conn.close()
        
        # Alert on significant changes
        if abs(daily_return) > 5.0:
            self._send_alert(
                'LARGE_MOVE',
                f"Daily return: {daily_return:+.2f}%",
                'WARNING' if abs(daily_return) > 10 else 'INFO'
            )
    
    def _send_alert(self, alert_type: str, message: str, severity: str):
        """Send alert (logged for email notification)"""
        timestamp = datetime.now().isoformat()
        
        # File log for alerts
        self.alert_logger.warning(f"[{severity}] {alert_type}: {message}")
        
        # Database log
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO activity_log 
            (timestamp, category, event_type, severity, message)
            VALUES (?, ?, ?, ?, ?)
        ''', (timestamp, 'ALERT', alert_type, severity, message))
        conn.commit()
        conn.close()
    
    def get_recent_activity(self, hours: int = 24, limit: int = 100):
        """Get recent activity for monitoring"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT timestamp, category, event_type, severity, message, details
            FROM activity_log
            WHERE datetime(timestamp) > datetime('now', '-' || ? || ' hours')
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (hours, limit))
        
        activities = cursor.fetchall()
        conn.close()
        
        return [
            {
                'timestamp': row[0],
                'category': row[1],
                'event_type': row[2],
                'severity': row[3],
                'message': row[4],
                'details': json.loads(row[5]) if row[5] else None
            }
            for row in activities
        ]
    
    def get_unresolved_errors(self):
        """Get all unresolved errors"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT timestamp, error_type, error_message, severity, context
            FROM error_log
            WHERE resolved = 0
            ORDER BY timestamp DESC
        ''')
        
        errors = cursor.fetchall()
        conn.close()
        
        return [
            {
                'timestamp': row[0],
                'error_type': row[1],
                'error_message': row[2],
                'severity': row[3],
                'context': json.loads(row[4]) if row[4] else None
            }
            for row in errors
        ]
    
    def generate_daily_summary(self):
        """Generate daily summary for email"""
        activities = self.get_recent_activity(hours=24)
        
        summary = {
            'trades': [a for a in activities if a['category'] == 'TRADE'],
            'errors': [a for a in activities if a['category'] == 'ERROR'],
            'alerts': [a for a in activities if a['category'] == 'ALERT'],
            'performance': [a for a in activities if a['category'] == 'PERFORMANCE'],
        }
        
        return summary

# Global logger instance
_logger = None

def get_logger():
    """Get or create global logger instance"""
    global _logger
    if _logger is None:
        _logger = TradingLogger()
    return _logger
