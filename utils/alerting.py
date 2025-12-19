import json
import logging
import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class AlertManager:
    """Manages alerts and notifications for the trading bot"""

    def __init__(
        self,
        smtp_server: str = None,
        smtp_port: int = 587,
        smtp_username: str = None,
        smtp_password: str = None,
        sender_email: str = None,
        admin_emails: List[str] = None,
        alert_history_file: str = "alerts.json",
    ):
        """Initialize the alert manager with SMTP settings"""
        self.smtp_server = smtp_server or os.getenv("SMTP_SERVER")
        self.smtp_port = smtp_port or int(os.getenv("SMTP_PORT", 587))
        self.smtp_username = smtp_username or os.getenv("SMTP_USERNAME")
        self.smtp_password = smtp_password or os.getenv("SMTP_PASSWORD")
        self.sender_email = sender_email or os.getenv("ALERT_SENDER_EMAIL")
        self.admin_emails = admin_emails or json.loads(os.getenv("ALERT_ADMIN_EMAILS", "[]"))
        self.alert_history_file = Path("logs") / alert_history_file
        self.alert_history_file.parent.mkdir(exist_ok=True)

    def _log_alert(self, level: str, message: str, data: dict = None) -> dict:
        """Log an alert to the alert history"""
        alert = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": level,
            "message": message,
            "data": data or {},
        }

        # Append to alert history
        try:
            if self.alert_history_file.exists():
                with open(self.alert_history_file, "r") as f:
                    alerts = json.load(f)
                    if not isinstance(alerts, list):
                        alerts = []
            else:
                alerts = []

            alerts.append(alert)

            # Keep only the last 1000 alerts
            alerts = alerts[-1000:]

            with open(self.alert_history_file, "w") as f:
                json.dump(alerts, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to log alert to history: {e}")

        return alert

    async def send_email(
        self,
        subject: str,
        body: str,
        to_emails: List[str] = None,
        is_html: bool = False,
        priority: str = "normal",
    ) -> bool:
        """Send an email notification if email is properly configured"""
        # Check if email is properly configured
        email_configured = all(
            [
                self.smtp_server,
                self.smtp_port,
                self.smtp_username,
                self.smtp_password,
                self.sender_email,
                to_emails,
            ]
        )

        if not email_configured:
            logger.debug("Email notification skipped: Email not configured or no recipients")
            return False

        if not to_emails:
            to_emails = self.admin_emails

        if not to_emails:
            logger.warning("No recipient emails specified")
            return False

        try:
            # Create message
            msg = MIMEMultipart()
            msg["From"] = self.sender_email
            msg["To"] = ", ".join(to_emails)
            msg["Subject"] = f"[InvestorMimicBot] {subject}"
            msg["X-Priority"] = "1" if priority == "high" else "3"

            # Attach body
            content_type = "html" if is_html else "plain"
            msg.attach(MIMEText(body, content_type, "utf-8"))

            # Connect to SMTP server and send
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)

            logger.info(f"Email sent to {', '.join(to_emails)}: {subject}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email: {e}", exc_info=True)
            return False

    async def alert(
        self,
        message: str,
        level: str = "info",
        data: dict = None,
        send_email: bool = True,
        email_priority: str = "normal",
    ) -> dict:
        """Send an alert with the given level and optional data"""
        level = level.lower()
        valid_levels = ["debug", "info", "warning", "error", "critical"]
        if level not in valid_levels:
            level = "info"

        # Log the alert
        log_method = getattr(logger, level, logger.info)
        log_data = {"alert": True, "level": level, "data": data or {}}
        log_method(message, extra={"data": log_data})

        # Log to alert history
        alert = self._log_alert(level, message, data)

        # Check if we should attempt to send email
        email_enabled = send_email and level in ["warning", "error", "critical"]
        if email_enabled and not all(
            [
                self.smtp_server,
                self.smtp_username,
                self.smtp_password,
                self.sender_email,
                self.admin_emails,
            ]
        ):
            logger.debug("Email alert skipped: Email not fully configured")
            return alert

        # Send email for important alerts if enabled and configured
        if email_enabled:
            email_subject = f"[{level.upper()}] {message[:100]}"
            email_body = f"""
            <h2>InvestorMimicBot Alert</h2>
            <p><strong>Level:</strong> {level.upper()}</p>
            <p><strong>Time:</strong> {alert['timestamp']}</p>
            <p><strong>Message:</strong> {message}</p>
            """

            if data:
                email_body += "<h3>Details:</h3>"
                for key, value in data.items():
                    email_body += f"<p><strong>{key}:</strong> {value}</p>"

            await self.send_email(email_subject, email_body, is_html=True, priority=email_priority)

        return alert


# Global alert manager instance
alert_manager = AlertManager()

# Example usage:
# await alert_manager.alert(
#     "Portfolio rebalance triggered",
#     level="info",
#     data={"reason": "Scheduled weekly rebalance"},
#     send_email=True
# )
