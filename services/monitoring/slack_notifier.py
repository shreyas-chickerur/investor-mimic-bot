"""
Slack notification service for alerts and monitoring.

Sends Slack messages for critical events, errors, and status updates.
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional

import httpx
from pydantic import BaseModel, Field, HttpUrl

logger = logging.getLogger(__name__)


class SlackConfig(BaseModel):
    """Slack configuration."""

    webhook_url: HttpUrl = Field(..., description="Slack webhook URL")
    channel: Optional[str] = Field(default=None, description="Default channel (optional)")
    username: str = Field(default="InvestorMimic Bot", description="Bot username")
    icon_emoji: str = Field(default=":robot_face:", description="Bot icon emoji")


class SlackNotifier:
    """
    Service for sending Slack notifications.

    Example usage:
        config = SlackConfig(
            webhook_url="https://hooks.slack.com/services/YOUR/WEBHOOK/URL",
            channel="#alerts",
            username="InvestorMimic Bot"
        )

        notifier = SlackNotifier(config)

        notifier.send_alert(
            message="Trade execution failed",
            level="ERROR",
            details={"symbol": "AAPL", "error": "Insufficient funds"}
        )
    """

    # Emoji mappings for alert levels
    LEVEL_EMOJIS = {
        "INFO": ":information_source:",
        "WARNING": ":warning:",
        "ERROR": ":x:",
        "CRITICAL": ":rotating_light:",
    }

    # Color mappings for alert levels
    LEVEL_COLORS = {
        "INFO": "#36a64f",  # Green
        "WARNING": "#ff9900",  # Orange
        "ERROR": "#ff0000",  # Red
        "CRITICAL": "#8b0000",  # Dark red
    }

    def __init__(self, config: SlackConfig):
        """
        Initialize the Slack notifier.

        Args:
            config: Slack configuration
        """
        self.config = config

    async def send_alert(
        self,
        message: str,
        level: str = "INFO",
        title: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        channel: Optional[str] = None,
    ) -> bool:
        """
        Send a Slack alert.

        Args:
            message: Alert message
            level: Alert level (INFO, WARNING, ERROR, CRITICAL)
            title: Optional title
            details: Optional additional details
            channel: Optional channel override

        Returns:
            True if message sent successfully, False otherwise
        """
        try:
            payload = self._build_payload(message=message, level=level, title=title, details=details, channel=channel)

            async with httpx.AsyncClient() as client:
                response = await client.post(str(self.config.webhook_url), json=payload, timeout=10.0)

                if response.status_code == 200:
                    logger.info(f"Slack alert sent: {title or message[:50]}")
                    return True
                else:
                    logger.error(f"Failed to send Slack alert: {response.status_code} - {response.text}")
                    return False

        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")
            return False

    def send_alert_sync(
        self,
        message: str,
        level: str = "INFO",
        title: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        channel: Optional[str] = None,
    ) -> bool:
        """
        Send a Slack alert synchronously.

        Args:
            message: Alert message
            level: Alert level (INFO, WARNING, ERROR, CRITICAL)
            title: Optional title
            details: Optional additional details
            channel: Optional channel override

        Returns:
            True if message sent successfully, False otherwise
        """
        try:
            import requests

            payload = self._build_payload(message=message, level=level, title=title, details=details, channel=channel)

            response = requests.post(str(self.config.webhook_url), json=payload, timeout=10.0)

            if response.status_code == 200:
                logger.info(f"Slack alert sent: {title or message[:50]}")
                return True
            else:
                logger.error(f"Failed to send Slack alert: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")
            return False

    async def send_funding_alert(
        self,
        status: str,
        amount: Optional[float] = None,
        transfer_id: Optional[str] = None,
        error: Optional[str] = None,
        channel: Optional[str] = None,
    ) -> bool:
        """
        Send a funding workflow alert.

        Args:
            status: Workflow status
            amount: Investment amount
            transfer_id: ACH transfer ID
            error: Error message if failed
            channel: Optional channel override

        Returns:
            True if message sent successfully
        """
        if status == "COMPLETED":
            title = "✅ Funding Completed"
            level = "INFO"
            message = f"Investment of ${amount:.2f} is now available for trading"
            details = {
                "Amount": f"${amount:.2f}",
                "Transfer ID": transfer_id,
                "Status": "Funds settled and ready",
            }
        elif status == "FAILED":
            title = "❌ Funding Failed"
            level = "ERROR"
            message = "Funding workflow encountered an error"
            details = {
                "Error": error,
                "Transfer ID": transfer_id or "N/A",
                "Action Required": "Review logs and retry",
            }
        else:
            title = f"📊 Funding Status: {status}"
            level = "INFO"
            message = "Funding workflow status update"
            details = {
                "Status": status,
                "Amount": f"${amount:.2f}" if amount else "N/A",
                "Transfer ID": transfer_id or "N/A",
            }

        return await self.send_alert(message=message, level=level, title=title, details=details, channel=channel)

    async def send_trade_alert(
        self,
        symbol: str,
        quantity: float,
        price: Optional[float] = None,
        status: str = "FILLED",
        order_id: Optional[str] = None,
        error: Optional[str] = None,
        channel: Optional[str] = None,
    ) -> bool:
        """
        Send a trade execution alert.

        Args:
            symbol: Stock symbol
            quantity: Number of shares
            price: Execution price
            status: Order status
            order_id: Order ID
            error: Error message if failed
            channel: Optional channel override

        Returns:
            True if message sent successfully
        """
        if status == "FILLED":
            title = f"✅ Trade Executed: {symbol}"
            level = "INFO"
            message = f"Successfully bought {quantity} shares of {symbol}"
            details = {
                "Symbol": symbol,
                "Quantity": f"{quantity} shares",
                "Price": f"${price:.2f}" if price else "N/A",
                "Total Value": f"${(quantity * price):.2f}" if price else "N/A",
                "Order ID": order_id,
            }
        elif status == "FAILED":
            title = f"❌ Trade Failed: {symbol}"
            level = "ERROR"
            message = f"Failed to execute trade for {symbol}"
            details = {
                "Symbol": symbol,
                "Quantity": f"{quantity} shares",
                "Error": error,
                "Order ID": order_id or "N/A",
            }
        else:
            title = f"📊 Trade Status: {symbol} - {status}"
            level = "INFO"
            message = f"Trade status update for {symbol}"
            details = {
                "Symbol": symbol,
                "Quantity": f"{quantity} shares",
                "Status": status,
                "Order ID": order_id or "N/A",
            }

        return await self.send_alert(message=message, level=level, title=title, details=details, channel=channel)

    async def send_system_alert(
        self,
        component: str,
        message: str,
        level: str = "ERROR",
        details: Optional[Dict[str, Any]] = None,
        channel: Optional[str] = None,
    ) -> bool:
        """
        Send a system-level alert.

        Args:
            component: System component name
            message: Alert message
            level: Alert level
            details: Optional additional details
            channel: Optional channel override

        Returns:
            True if message sent successfully
        """
        emoji = self.LEVEL_EMOJIS.get(level, ":bell:")
        title = f"{emoji} System Alert: {component}"

        return await self.send_alert(message=message, level=level, title=title, details=details, channel=channel)

    def _build_payload(
        self,
        message: str,
        level: str,
        title: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        channel: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build Slack webhook payload."""
        emoji = self.LEVEL_EMOJIS.get(level, ":bell:")
        color = self.LEVEL_COLORS.get(level, "#808080")

        # Build attachment
        attachment = {
            "color": color,
            "title": title or f"{emoji} {level} Alert",
            "text": message,
            "footer": "InvestorMimic Bot",
            "footer_icon": "https://platform.slack-edge.com/img/default_application_icon.png",
            "ts": int(datetime.utcnow().timestamp()),
        }

        # Add fields for details
        if details:
            fields = []
            for key, value in details.items():
                fields.append({"title": key, "value": str(value), "short": True})
            attachment["fields"] = fields

        # Build payload
        payload = {
            "username": self.config.username,
            "icon_emoji": self.config.icon_emoji,
            "attachments": [attachment],
        }

        # Add channel if specified
        if channel or self.config.channel:
            payload["channel"] = channel or self.config.channel

        return payload
