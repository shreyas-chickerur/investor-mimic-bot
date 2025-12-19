"""
Multi-Channel Notification System

Supports Slack, SMS (Twilio), Telegram, and Push notifications.
"""

from enum import Enum
from typing import Dict, List, Optional

import requests

from utils.enhanced_logging import get_logger
from utils.environment import env

logger = get_logger(__name__)


class NotificationChannel(Enum):
    """Notification channel types."""

    SLACK = "slack"
    SMS = "sms"
    TELEGRAM = "telegram"
    PUSH = "push"
    EMAIL = "email"


class NotificationPriority(Enum):
    """Notification priority levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class NotificationManager:
    """Manages multi-channel notifications."""

    def __init__(self):
        self.slack_webhook = env.get("SLACK_WEBHOOK_URL")
        self.twilio_sid = env.get("TWILIO_ACCOUNT_SID")
        self.twilio_token = env.get("TWILIO_AUTH_TOKEN")
        self.twilio_from = env.get("TWILIO_PHONE_NUMBER")
        self.telegram_token = env.get("TELEGRAM_BOT_TOKEN")
        self.telegram_chat_id = env.get("TELEGRAM_CHAT_ID")

    def send_notification(
        self,
        message: str,
        channel: NotificationChannel = NotificationChannel.SLACK,
        priority: NotificationPriority = NotificationPriority.MEDIUM,
        **kwargs,
    ) -> bool:
        """
        Send notification via specified channel.

        Args:
            message: Notification message
            channel: Notification channel
            priority: Message priority
            **kwargs: Additional channel-specific parameters

        Returns:
            True if sent successfully
        """
        try:
            if channel == NotificationChannel.SLACK:
                return self._send_slack(message, priority, **kwargs)
            elif channel == NotificationChannel.SMS:
                return self._send_sms(message, **kwargs)
            elif channel == NotificationChannel.TELEGRAM:
                return self._send_telegram(message, **kwargs)
            elif channel == NotificationChannel.EMAIL:
                return self._send_email(message, **kwargs)
            else:
                logger.warning(f"Unsupported notification channel: {channel}")
                return False
        except Exception as e:
            logger.error(f"Failed to send {channel.value} notification: {e}", error=e)
            return False

    def _send_slack(self, message: str, priority: NotificationPriority, **kwargs) -> bool:
        """Send Slack notification."""
        if not self.slack_webhook:
            logger.debug("Slack webhook not configured")
            return False

        # Format message with priority
        emoji = {
            NotificationPriority.LOW: ":information_source:",
            NotificationPriority.MEDIUM: ":warning:",
            NotificationPriority.HIGH: ":rotating_light:",
            NotificationPriority.CRITICAL: ":fire:",
        }.get(priority, ":bell:")

        payload = {"text": f"{emoji} {message}", "username": "Investor Mimic Bot", **kwargs}

        response = requests.post(self.slack_webhook, json=payload, timeout=10)
        response.raise_for_status()

        logger.info(f"Slack notification sent: {message[:50]}...")
        return True

    def _send_sms(self, message: str, to_number: Optional[str] = None, **kwargs) -> bool:
        """Send SMS via Twilio."""
        if not all([self.twilio_sid, self.twilio_token, self.twilio_from]):
            logger.debug("Twilio not configured")
            return False

        if not to_number:
            to_number = env.get("ALERT_PHONE_NUMBER")
            if not to_number:
                logger.warning("No phone number specified for SMS")
                return False

        try:
            from twilio.rest import Client

            client = Client(self.twilio_sid, self.twilio_token)

            client.messages.create(body=message, from_=self.twilio_from, to=to_number)

            logger.info(f"SMS sent to {to_number}: {message[:50]}...")
            return True
        except ImportError:
            logger.warning("Twilio library not installed. Install with: pip install twilio")
            return False

    def _send_telegram(self, message: str, **kwargs) -> bool:
        """Send Telegram notification."""
        if not all([self.telegram_token, self.telegram_chat_id]):
            logger.debug("Telegram not configured")
            return False

        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        payload = {
            "chat_id": self.telegram_chat_id,
            "text": message,
            "parse_mode": "Markdown",
            **kwargs,
        }

        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()

        logger.info(f"Telegram notification sent: {message[:50]}...")
        return True

    def _send_email(self, message: str, subject: Optional[str] = None, **kwargs) -> bool:
        """Send email notification."""
        # Use existing email system
        try:
            from services.approval.email_sender import send_email

            to_email = kwargs.get("to_email") or env.get("ALERT_EMAIL")
            if not to_email:
                logger.warning("No email address specified")
                return False

            send_email(
                to_email=to_email, subject=subject or "Investor Mimic Bot Alert", body=message
            )

            logger.info(f"Email sent to {to_email}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email: {e}", error=e)
            return False

    def send_trade_alert(
        self, ticker: str, action: str, quantity: float, price: float, channels: list = None
    ) -> Dict[str, bool]:
        """
        Send trade alert to multiple channels.

        Args:
            ticker: Stock ticker
            action: BUY or SELL
            quantity: Number of shares
            price: Price per share
            channels: List of channels to notify

        Returns:
            Dictionary of channel: success status
        """
        message = f"🔔 Trade Alert: {action} {quantity} {ticker} @ ${price:.2f}"

        if channels is None:
            channels = [NotificationChannel.SLACK, NotificationChannel.EMAIL]

        results = {}
        for channel in channels:
            results[channel.value] = self.send_notification(
                message, channel=channel, priority=NotificationPriority.HIGH
            )

        return results

    def send_system_alert(
        self, message: str, priority: NotificationPriority = NotificationPriority.MEDIUM
    ) -> Dict[str, bool]:
        """Send system alert to all configured channels."""
        channels = []

        if self.slack_webhook:
            channels.append(NotificationChannel.SLACK)
        if self.telegram_token:
            channels.append(NotificationChannel.TELEGRAM)

        # Critical alerts also go via SMS
        if priority == NotificationPriority.CRITICAL and self.twilio_sid:
            channels.append(NotificationChannel.SMS)

        results = {}
        for channel in channels:
            results[channel.value] = self.send_notification(
                message, channel=channel, priority=priority
            )

        return results


# Global notification manager
_notifier = None


def get_notifier() -> NotificationManager:
    """Get global notification manager."""
    global _notifier
    if _notifier is None:
        _notifier = NotificationManager()
    return _notifier


def notify(
    message: str,
    channel: NotificationChannel = NotificationChannel.SLACK,
    priority: NotificationPriority = NotificationPriority.MEDIUM,
) -> bool:
    """
    Convenience function to send notification.

    Usage:
        from utils.notifications import notify, NotificationChannel

        notify("Trade executed", channel=NotificationChannel.SLACK)
    """
    notifier = get_notifier()
    return notifier.send_notification(message, channel, priority)
