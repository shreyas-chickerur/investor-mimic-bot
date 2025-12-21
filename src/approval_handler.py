#!/usr/bin/env python3
"""
Trade Approval Handler
Manages approval workflow and stores pending trades
"""
import json
import sqlite3
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from config import TradingConfig
from email_template import generate_approval_email


class ApprovalHandler:
    """Handles trade approval workflow"""
    
    def __init__(self, db_path='data/trading_system.db'):
        self.db_path = db_path
        self._setup_database()
    
    def _setup_database(self):
        """Create approval tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pending_approvals (
                request_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                trades_json TEXT NOT NULL,
                portfolio_value REAL,
                cash REAL,
                status TEXT DEFAULT 'pending',
                approved_at TEXT,
                decisions_json TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def create_approval_request(
        self,
        trades: List[Dict],
        portfolio_value: float,
        cash: float
    ) -> str:
        """
        Create a new approval request
        
        Args:
            trades: List of proposed trades
            portfolio_value: Current portfolio value
            cash: Available cash
        
        Returns:
            request_id: Unique request ID
        """
        request_id = f"approval_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO pending_approvals 
            (request_id, created_at, trades_json, portfolio_value, cash, status)
            VALUES (?, ?, ?, ?, ?, 'pending')
        ''', (
            request_id,
            datetime.now().isoformat(),
            json.dumps(trades),
            portfolio_value,
            cash
        ))
        
        conn.commit()
        conn.close()
        
        return request_id
    
    def send_approval_email(
        self,
        request_id: str,
        trades: List[Dict],
        portfolio_value: float,
        cash: float
    ) -> bool:
        """
        Send approval email to user
        
        Args:
            request_id: Approval request ID
            trades: List of proposed trades
            portfolio_value: Current portfolio value
            cash: Available cash
        
        Returns:
            bool: True if email sent successfully
        """
        try:
            # Generate approval URL
            approval_url = f"{TradingConfig.APPROVAL_BASE_URL}/approve"
            
            # Generate email HTML
            email_html = generate_approval_email(
                trades=trades,
                portfolio_value=portfolio_value,
                cash=cash,
                approval_url=approval_url,
                request_id=request_id
            )
            
            # Create email
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"🔔 Trade Approval Required - {len(trades)} trades pending"
            msg['From'] = TradingConfig.EMAIL_USERNAME
            msg['To'] = TradingConfig.EMAIL_TO
            
            # Attach HTML
            html_part = MIMEText(email_html, 'html')
            msg.attach(html_part)
            
            # Send email
            with smtplib.SMTP('smtp.gmail.com', 587) as server:
                server.starttls()
                server.login(TradingConfig.EMAIL_USERNAME, TradingConfig.EMAIL_PASSWORD)
                server.send_message(msg)
            
            print(f"✅ Approval email sent to {TradingConfig.EMAIL_TO}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to send approval email: {e}")
            return False
    
    def get_pending_request(self, request_id: str) -> Optional[Dict]:
        """Get pending approval request"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT request_id, created_at, trades_json, portfolio_value, cash, status
            FROM pending_approvals
            WHERE request_id = ? AND status = 'pending'
        ''', (request_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return {
            'request_id': row[0],
            'created_at': row[1],
            'trades': json.loads(row[2]),
            'portfolio_value': row[3],
            'cash': row[4],
            'status': row[5]
        }
    
    def process_approval_decisions(
        self,
        request_id: str,
        decisions: Dict[str, str]
    ) -> Dict:
        """
        Process approval decisions and execute approved trades on Alpaca
        
        Args:
            request_id: Approval request ID
            decisions: Dict mapping trade index to 'approve' or 'reject'
        
        Returns:
            Dict with execution results
        """
        # Get pending request
        request = self.get_pending_request(request_id)
        if not request:
            return {'error': 'Request not found or already processed'}
        
        trades = request['trades']
        
        # Execute approved trades on Alpaca
        from trade_executor import TradeExecutor
        
        executor = TradeExecutor()
        execution_results = executor.execute_approved_trades(decisions, trades, request_id)
        
        # Log execution results
        executor.log_execution_results(execution_results, request_id)
        
        # Save account snapshot after execution
        from database_schema import TradingDatabase
        from alpaca_data_fetcher import AlpacaDataFetcher
        
        try:
            fetcher = AlpacaDataFetcher()
            account_info = fetcher.get_account_info()
            
            db = TradingDatabase()
            db.save_account_snapshot(
                portfolio_value=account_info['portfolio_value'],
                cash=account_info['cash'],
                equity=account_info['equity'],
                buying_power=account_info['buying_power']
            )
        except Exception as e:
            print(f"Warning: Could not save account snapshot: {e}")
        
        # Update database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE pending_approvals
            SET status = 'processed',
                approved_at = ?,
                decisions_json = ?
            WHERE request_id = ?
        ''', (
            datetime.now().isoformat(),
            json.dumps(decisions),
            request_id
        ))
        
        conn.commit()
        conn.close()
        
        # Return execution results
        return execution_results
    
    def get_approval_status(self, request_id: str) -> str:
        """Get status of approval request"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT status FROM pending_approvals WHERE request_id = ?
        ''', (request_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        return row[0] if row else 'not_found'
    
    def cleanup_old_requests(self, days: int = 7):
        """Clean up old approval requests"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            DELETE FROM pending_approvals
            WHERE datetime(created_at) < datetime('now', '-' || ? || ' days')
        ''', (days,))
        
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        
        return deleted
