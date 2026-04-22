#!/usr/bin/env python3
"""
Email Notification System
Sends critical alert emails.

Daily digest emails are generated and sent via scripts/generate_daily_email.py
in workflow execution.
"""
from __future__ import annotations

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
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

def send_error_alert(error_message: str, details: str = ""):
    """Convenience function to send error alert"""
    notifier = EmailNotifier()
    notifier.send_error_alert(error_message, details)
