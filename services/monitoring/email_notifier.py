"""
Email notification service for alerts and monitoring.

Sends email notifications for critical events, errors, and status updates.
"""

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, List
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

logger = logging.getLogger(__name__)


class EmailConfig(BaseModel):
    """Email configuration."""
    smtp_server: str = Field(..., description="SMTP server address")
    smtp_port: int = Field(default=587, description="SMTP server port")
    smtp_username: str = Field(..., description="SMTP username")
    smtp_password: str = Field(..., description="SMTP password")
    from_email: EmailStr = Field(..., description="Sender email address")
    use_tls: bool = Field(default=True, description="Use TLS encryption")


class EmailNotifier:
    """
    Service for sending email notifications.
    
    Example usage:
        config = EmailConfig(
            smtp_server="smtp.gmail.com",
            smtp_port=587,
            smtp_username="user@gmail.com",
            smtp_password="app_password",
            from_email="user@gmail.com"
        )
        
        notifier = EmailNotifier(config)
        
        notifier.send_alert(
            to_emails=["alerts@example.com"],
            subject="Trading Alert",
            message="Trade execution failed",
            level="ERROR"
        )
    """
    
    def __init__(self, config: EmailConfig):
        """
        Initialize the email notifier.
        
        Args:
            config: Email configuration
        """
        self.config = config
    
    def send_alert(
        self,
        to_emails: List[str],
        subject: str,
        message: str,
        level: str = "INFO",
        details: Optional[dict] = None,
        html: bool = False
    ) -> bool:
        """
        Send an email alert.
        
        Args:
            to_emails: List of recipient email addresses
            subject: Email subject
            message: Email message body
            level: Alert level (INFO, WARNING, ERROR, CRITICAL)
            details: Optional additional details
            html: Whether the message is HTML
            
        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = self.config.from_email
            msg['To'] = ', '.join(to_emails)
            msg['Subject'] = f"[{level}] {subject}"
            msg['Date'] = datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S +0000')
            
            # Build email body
            if html:
                body = message
            else:
                body = self._format_text_email(message, level, details)
            
            # Attach body
            if html:
                msg.attach(MIMEText(body, 'html'))
            else:
                msg.attach(MIMEText(body, 'plain'))
            
            # Send email
            with smtplib.SMTP(self.config.smtp_server, self.config.smtp_port) as server:
                if self.config.use_tls:
                    server.starttls()
                
                server.login(self.config.smtp_username, self.config.smtp_password)
                server.send_message(msg)
            
            logger.info(f"Email alert sent to {', '.join(to_emails)}: {subject}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
            return False
    
    def send_funding_alert(
        self,
        to_emails: List[str],
        status: str,
        amount: Optional[float] = None,
        transfer_id: Optional[str] = None,
        error: Optional[str] = None
    ) -> bool:
        """
        Send a funding workflow alert.
        
        Args:
            to_emails: List of recipient email addresses
            status: Workflow status
            amount: Investment amount
            transfer_id: ACH transfer ID
            error: Error message if failed
            
        Returns:
            True if email sent successfully
        """
        if status == "COMPLETED":
            subject = f"Funding Completed: ${amount:.2f}"
            level = "INFO"
            message = f"""
Funding workflow completed successfully.

Investment Amount: ${amount:.2f}
Transfer ID: {transfer_id}
Status: Funds available for trading

The automated trading workflow can now proceed.
"""
        elif status == "FAILED":
            subject = "Funding Workflow Failed"
            level = "ERROR"
            message = f"""
Funding workflow failed.

Error: {error}
Transfer ID: {transfer_id or 'N/A'}

Please review the logs and take corrective action.
"""
        else:
            subject = f"Funding Status: {status}"
            level = "INFO"
            message = f"""
Funding workflow status update.

Status: {status}
Amount: ${amount:.2f if amount else 'N/A'}
Transfer ID: {transfer_id or 'N/A'}
"""
        
        return self.send_alert(
            to_emails=to_emails,
            subject=subject,
            message=message,
            level=level
        )
    
    def send_trade_alert(
        self,
        to_emails: List[str],
        symbol: str,
        quantity: float,
        price: Optional[float] = None,
        status: str = "FILLED",
        order_id: Optional[str] = None,
        error: Optional[str] = None
    ) -> bool:
        """
        Send a trade execution alert.
        
        Args:
            to_emails: List of recipient email addresses
            symbol: Stock symbol
            quantity: Number of shares
            price: Execution price
            status: Order status
            order_id: Order ID
            error: Error message if failed
            
        Returns:
            True if email sent successfully
        """
        if status == "FILLED":
            subject = f"Trade Executed: {symbol}"
            level = "INFO"
            message = f"""
Trade executed successfully.

Symbol: {symbol}
Quantity: {quantity} shares
Price: ${price:.2f if price else 'N/A'}
Order ID: {order_id}
Total Value: ${(quantity * price):.2f if price else 'N/A'}
"""
        elif status == "FAILED":
            subject = f"Trade Failed: {symbol}"
            level = "ERROR"
            message = f"""
Trade execution failed.

Symbol: {symbol}
Quantity: {quantity} shares
Error: {error}
Order ID: {order_id or 'N/A'}

Please review and retry if necessary.
"""
        else:
            subject = f"Trade Status: {symbol} - {status}"
            level = "INFO"
            message = f"""
Trade status update.

Symbol: {symbol}
Quantity: {quantity} shares
Status: {status}
Order ID: {order_id or 'N/A'}
"""
        
        return self.send_alert(
            to_emails=to_emails,
            subject=subject,
            message=message,
            level=level
        )
    
    def send_system_alert(
        self,
        to_emails: List[str],
        component: str,
        message: str,
        level: str = "ERROR",
        details: Optional[dict] = None
    ) -> bool:
        """
        Send a system-level alert.
        
        Args:
            to_emails: List of recipient email addresses
            component: System component name
            message: Alert message
            level: Alert level
            details: Optional additional details
            
        Returns:
            True if email sent successfully
        """
        subject = f"System Alert: {component}"
        
        return self.send_alert(
            to_emails=to_emails,
            subject=subject,
            message=message,
            level=level,
            details=details
        )
    
    def _format_text_email(
        self,
        message: str,
        level: str,
        details: Optional[dict] = None
    ) -> str:
        """Format a plain text email body."""
        body = f"""
InvestorMimic Bot Alert
{'=' * 50}

Level: {level}
Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}

{message}
"""
        
        if details:
            body += "\n\nAdditional Details:\n"
            body += "-" * 50 + "\n"
            for key, value in details.items():
                body += f"{key}: {value}\n"
        
        body += "\n" + "=" * 50
        body += "\nThis is an automated message from InvestorMimic Bot."
        
        return body
