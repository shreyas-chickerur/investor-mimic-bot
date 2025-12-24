#!/usr/bin/env python3
"""
Email Notification System
Sends daily trading summaries and error alerts
"""
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

class EmailNotifier:
    """Handles email notifications for trading system"""
    
    def __init__(self):
        self.smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.sender_email = os.getenv('SENDER_EMAIL')
        self.sender_password = os.getenv('SENDER_PASSWORD')
        self.recipient_email = os.getenv('RECIPIENT_EMAIL')
        
        if not all([self.sender_email, self.sender_password, self.recipient_email]):
            logger.warning("Email credentials not configured - notifications disabled")
            self.enabled = False
        else:
            self.enabled = True
    
    def send_alert(self, subject: str, message: str):
        """Send critical alert email (for reconciliation failures, etc.)"""
        
        if not self.enabled:
            logger.warning("Email notifications disabled - alert not sent")
            return
        
        alert_subject = f"🚨 ALERT: {subject}"
        self._send_email(alert_subject, message)
    
    def send_daily_summary(self, 
                          trades: List[Dict],
                          positions: List[Dict],
                          portfolio_value: float,
                          cash: float,
                          errors: List[str] = None):
        """Send daily trading summary email"""
        
        if not self.enabled:
            logger.info("Email notifications disabled - skipping")
            return
        
        subject = f"📊 Daily Trading Summary - {datetime.now().strftime('%Y-%m-%d')}"
        
        # Build email body
        body = self._build_summary_email(trades, positions, portfolio_value, cash, errors)
        
        self._send_email(subject, body)
    
    def send_error_alert(self, error_message: str, details: str = ""):
        """Send error alert email"""
        
        if not self.enabled:
            logger.error(f"Email disabled, error not sent: {error_message}")
            return
        
        subject = f"🚨 Trading System Error - {datetime.now().strftime('%Y-%m-%d')}"
        
        body = f"""
<html>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <div style="background: #dc3545; color: white; padding: 20px; border-radius: 8px 8px 0 0;">
        <h1 style="margin: 0;">🚨 Error Alert</h1>
    </div>
    
    <div style="padding: 20px; background: #f8f9fa; border: 1px solid #dee2e6;">
        <h2 style="color: #dc3545;">Error Occurred</h2>
        <p style="font-size: 16px; color: #333;">{error_message}</p>
        
        {f'<div style="background: white; padding: 15px; border-left: 4px solid #dc3545; margin-top: 15px;"><pre style="margin: 0; white-space: pre-wrap;">{details}</pre></div>' if details else ''}
        
        <p style="margin-top: 20px; color: #666;">
            <strong>Time:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}<br>
            <strong>Action Required:</strong> Check GitHub Actions logs for details
        </p>
    </div>
</body>
</html>
"""
        
        self._send_email(subject, body, is_html=True)
    
    def _build_summary_email(self, trades, positions, portfolio_value, cash, errors):
        """Build HTML email body for daily summary"""
        
        # Count trades by action
        buys = [t for t in trades if t.get('action') == 'BUY']
        sells = [t for t in trades if t.get('action') == 'SELL']
        
        # Build trades table
        trades_html = ""
        if trades:
            trades_html = "<table style='width: 100%; border-collapse: collapse; margin-top: 10px;'>"
            trades_html += "<tr style='background: #f8f9fa; border-bottom: 2px solid #dee2e6;'>"
            trades_html += "<th style='padding: 10px; text-align: left;'>Action</th>"
            trades_html += "<th style='padding: 10px; text-align: left;'>Symbol</th>"
            trades_html += "<th style='padding: 10px; text-align: right;'>Shares</th>"
            trades_html += "<th style='padding: 10px; text-align: right;'>Price</th>"
            trades_html += "<th style='padding: 10px; text-align: left;'>Strategy</th>"
            trades_html += "</tr>"
            
            for trade in trades:
                action_color = '#28a745' if trade.get('action') == 'BUY' else '#dc3545'
                trades_html += f"<tr style='border-bottom: 1px solid #dee2e6;'>"
                trades_html += f"<td style='padding: 10px; color: {action_color}; font-weight: bold;'>{trade.get('action', 'N/A')}</td>"
                trades_html += f"<td style='padding: 10px;'>{trade.get('symbol', 'N/A')}</td>"
                trades_html += f"<td style='padding: 10px; text-align: right;'>{trade.get('shares', 0)}</td>"
                trades_html += f"<td style='padding: 10px; text-align: right;'>${trade.get('price', 0):.2f}</td>"
                trades_html += f"<td style='padding: 10px;'>{trade.get('strategy', 'N/A')}</td>"
                trades_html += "</tr>"
            
            trades_html += "</table>"
        else:
            trades_html = "<p style='color: #666; font-style: italic;'>No trades executed today</p>"
        
        # Build positions table
        positions_html = ""
        if positions:
            positions_html = "<table style='width: 100%; border-collapse: collapse; margin-top: 10px;'>"
            positions_html += "<tr style='background: #f8f9fa; border-bottom: 2px solid #dee2e6;'>"
            positions_html += "<th style='padding: 10px; text-align: left;'>Symbol</th>"
            positions_html += "<th style='padding: 10px; text-align: right;'>Shares</th>"
            positions_html += "<th style='padding: 10px; text-align: right;'>Entry Price</th>"
            positions_html += "<th style='padding: 10px; text-align: right;'>Current Price</th>"
            positions_html += "<th style='padding: 10px; text-align: right;'>P&L</th>"
            positions_html += "</tr>"
            
            for pos in positions[:10]:  # Top 10 positions
                pnl = (pos.get('current_price', 0) - pos.get('entry_price', 0)) * pos.get('shares', 0)
                pnl_color = '#28a745' if pnl >= 0 else '#dc3545'
                
                positions_html += f"<tr style='border-bottom: 1px solid #dee2e6;'>"
                positions_html += f"<td style='padding: 10px;'>{pos.get('symbol', 'N/A')}</td>"
                positions_html += f"<td style='padding: 10px; text-align: right;'>{pos.get('shares', 0)}</td>"
                positions_html += f"<td style='padding: 10px; text-align: right;'>${pos.get('entry_price', 0):.2f}</td>"
                positions_html += f"<td style='padding: 10px; text-align: right;'>${pos.get('current_price', 0):.2f}</td>"
                positions_html += f"<td style='padding: 10px; text-align: right; color: {pnl_color}; font-weight: bold;'>${pnl:+.2f}</td>"
                positions_html += "</tr>"
            
            positions_html += "</table>"
        else:
            positions_html = "<p style='color: #666; font-style: italic;'>No open positions</p>"
        
        # Build errors section
        errors_html = ""
        if errors:
            errors_html = f"""
            <div style="background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin-top: 20px;">
                <h3 style="color: #856404; margin-top: 0;">⚠️ Warnings/Errors</h3>
                <ul style="margin: 0; padding-left: 20px;">
                    {''.join(f'<li style="color: #856404;">{error}</li>' for error in errors)}
                </ul>
            </div>
            """
        
        # Complete email
        html = f"""
<html>
<body style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; background: #f8f9fa;">
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 8px 8px 0 0;">
        <h1 style="margin: 0;">📊 Daily Trading Summary</h1>
        <p style="margin: 5px 0 0 0; opacity: 0.9;">{datetime.now().strftime('%A, %B %d, %Y')}</p>
    </div>
    
    <div style="padding: 30px; background: white;">
        <!-- Portfolio Overview -->
        <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px; margin-bottom: 30px;">
            <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; border-left: 4px solid #667eea;">
                <div style="color: #666; font-size: 12px; text-transform: uppercase; margin-bottom: 5px;">Portfolio Value</div>
                <div style="font-size: 28px; font-weight: bold; color: #2d3748;">${portfolio_value:,.2f}</div>
            </div>
            <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; border-left: 4px solid #48bb78;">
                <div style="color: #666; font-size: 12px; text-transform: uppercase; margin-bottom: 5px;">Cash Available</div>
                <div style="font-size: 28px; font-weight: bold; color: #2d3748;">${cash:,.2f}</div>
            </div>
        </div>
        
        <!-- Trade Summary -->
        <div style="margin-bottom: 30px;">
            <h2 style="color: #2d3748; border-bottom: 2px solid #e2e8f0; padding-bottom: 10px;">
                Trades Executed ({len(trades)})
            </h2>
            <div style="margin: 15px 0;">
                <span style="background: #c6f6d5; color: #22543d; padding: 5px 15px; border-radius: 20px; margin-right: 10px;">
                    {len(buys)} Buys
                </span>
                <span style="background: #fed7d7; color: #742a2a; padding: 5px 15px; border-radius: 20px;">
                    {len(sells)} Sells
                </span>
            </div>
            {trades_html}
        </div>
        
        <!-- Current Positions -->
        <div style="margin-bottom: 30px;">
            <h2 style="color: #2d3748; border-bottom: 2px solid #e2e8f0; padding-bottom: 10px;">
                Current Positions ({len(positions)})
            </h2>
            {positions_html}
        </div>
        
        {errors_html}
        
        <!-- Footer -->
        <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e2e8f0; color: #666; font-size: 12px;">
            <p>View detailed logs and reports in <a href="https://github.com/{os.getenv('GITHUB_REPOSITORY', 'your-repo')}/actions" style="color: #667eea;">GitHub Actions</a></p>
            <p style="margin-top: 10px;">This is an automated message from your trading system.</p>
        </div>
    </div>
</body>
</html>
"""
        
        return html
    
    def _send_email(self, subject: str, body: str, is_html: bool = True):
        """Send email via SMTP"""
        
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.sender_email
            msg['To'] = self.recipient_email
            
            if is_html:
                msg.attach(MIMEText(body, 'html'))
            else:
                msg.attach(MIMEText(body, 'plain'))
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)
            
            logger.info(f"Email sent successfully: {subject}")
            
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            raise

def send_daily_summary(**kwargs):
    """Convenience function to send daily summary"""
    notifier = EmailNotifier()
    notifier.send_daily_summary(**kwargs)

def send_error_alert(error_message: str, details: str = ""):
    """Convenience function to send error alert"""
    notifier = EmailNotifier()
    notifier.send_error_alert(error_message, details)
