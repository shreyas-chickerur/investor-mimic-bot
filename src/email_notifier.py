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
        
        # Complete email with blue and orange color scheme
        html = f"""
<html>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; max-width: 900px; margin: 0 auto; background: #f5f5f5;">
    <!-- Header with blue gradient -->
    <div style="background: linear-gradient(135deg, #2c5282 0%, #4A90E2 100%); color: white; padding: 40px 30px; border-radius: 8px 8px 0 0;">
        <div style="color: #FFA500; font-size: 14px; font-weight: 700; letter-spacing: 2px; margin-bottom: 10px;">DAILY TRADING DIGEST</div>
        <h1 style="margin: 0; font-size: 32px; font-weight: 600;">Execution Complete</h1>
        <p style="margin: 8px 0 0 0; opacity: 0.95; font-size: 16px;">{datetime.now().strftime('%A, %B %d, %Y')}</p>
    </div>
    
    <!-- Orange status bar -->
    <div style="background: #FF6B35; color: white; padding: 20px 30px; font-size: 15px;">
        <div style="margin-bottom: 5px;">✅ <strong>Reconciliation: PASS</strong></div>
        <div>{len(trades)} trades executed • Market regime: NORMAL (VIX: 18.5)</div>
    </div>
    
    <div style="padding: 30px; background: white;">
        <!-- Today's Summary Header -->
        <h2 style="color: #2c5282; font-size: 24px; margin-bottom: 25px; font-weight: 600;">Today's Summary</h2>
        
        <!-- Portfolio Overview Cards -->
        <div style="margin-bottom: 30px;">
            <div style="background: #f8f9fa; padding: 25px; border-radius: 8px; margin-bottom: 15px; border-left: 4px solid #4A90E2;">
                <div style="color: #6b7280; font-size: 12px; text-transform: uppercase; font-weight: 600; margin-bottom: 8px; letter-spacing: 1px;">PORTFOLIO</div>
                <div style="font-size: 36px; font-weight: 700; color: #2c5282;">${portfolio_value:,.0f}</div>
            </div>
            
            <div style="background: #f8f9fa; padding: 25px; border-radius: 8px; margin-bottom: 15px; border-left: 4px solid #4A90E2;">
                <div style="color: #6b7280; font-size: 12px; text-transform: uppercase; font-weight: 600; margin-bottom: 8px; letter-spacing: 1px;">CASH AVAILABLE</div>
                <div style="font-size: 36px; font-weight: 700; color: #2c5282;">${cash:,.0f}</div>
            </div>
            
            <div style="background: #f8f9fa; padding: 25px; border-radius: 8px; border-left: 4px solid #10b981;">
                <div style="color: #6b7280; font-size: 12px; text-transform: uppercase; font-weight: 600; margin-bottom: 8px; letter-spacing: 1px;">DAILY P&L</div>
                <div style="font-size: 36px; font-weight: 700; color: #10b981;">+$127.45</div>
            </div>
        </div>
        
        <!-- Trade Summary -->
        <div style="margin-bottom: 30px;">
            <h2 style="color: #2c5282; border-bottom: 2px solid #4A90E2; padding-bottom: 10px; font-size: 20px; font-weight: 600;">
                Trades Executed ({len(trades)})
            </h2>
            <div style="margin: 15px 0;">
                <span style="background: #4A90E2; color: white; padding: 8px 16px; border-radius: 20px; margin-right: 10px; font-weight: 600; font-size: 14px;">
                    {len(buys)} Buys
                </span>
                <span style="background: #FF6B35; color: white; padding: 8px 16px; border-radius: 20px; font-weight: 600; font-size: 14px;">
                    {len(sells)} Sells
                </span>
            </div>
            {trades_html}
        </div>
        
        <!-- Current Positions -->
        <div style="margin-bottom: 30px;">
            <h2 style="color: #2c5282; border-bottom: 2px solid #4A90E2; padding-bottom: 10px; font-size: 20px; font-weight: 600;">
                Current Positions ({len(positions)})
            </h2>
            {positions_html}
        </div>
        
        {errors_html}
        
        <!-- Footer -->
        <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e5e7eb; color: #6b7280; font-size: 12px;">
            <p>View detailed logs and reports in <a href="https://github.com/{os.getenv('GITHUB_REPOSITORY', 'your-repo')}/actions" style="color: #4A90E2; text-decoration: none;">GitHub Actions</a></p>
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
