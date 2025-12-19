"""
Unified notification manager for all alerting channels.

Manages email and Slack notifications with configurable routing.
"""

import logging
from typing import Optional, Dict, Any, List
from enum import Enum

from pydantic import BaseModel, Field

from services.monitoring.email_notifier import EmailNotifier, EmailConfig
from services.monitoring.slack_notifier import SlackNotifier, SlackConfig
from services.monitoring.alert import Alert, AlertLevel

logger = logging.getLogger(__name__)


class NotificationChannel(str, Enum):
    """Available notification channels."""
    EMAIL = "email"
    SLACK = "slack"
    BOTH = "both"


class NotificationConfig(BaseModel):
    """Configuration for notification manager."""
    email_config: Optional[EmailConfig] = None
    slack_config: Optional[SlackConfig] = None
    default_channel: NotificationChannel = Field(default=NotificationChannel.BOTH)
    alert_emails: List[str] = Field(default_factory=list, description="Email addresses for alerts")
    slack_channel: Optional[str] = Field(default=None, description="Default Slack channel")
    
    # Alert level routing
    info_channel: NotificationChannel = Field(default=NotificationChannel.SLACK)
    warning_channel: NotificationChannel = Field(default=NotificationChannel.BOTH)
    error_channel: NotificationChannel = Field(default=NotificationChannel.BOTH)
    critical_channel: NotificationChannel = Field(default=NotificationChannel.BOTH)


class NotificationManager:
    """
    Unified notification manager for all alerting channels.
    
    Example usage:
        config = NotificationConfig(
            email_config=EmailConfig(...),
            slack_config=SlackConfig(...),
            alert_emails=["alerts@example.com"],
            slack_channel="#alerts"
        )
        
        manager = NotificationManager(config)
        
        # Send alert through appropriate channels
        await manager.send_alert(Alert(
            level=AlertLevel.ERROR,
            message="Trade execution failed",
            component="trading",
            details={"symbol": "AAPL"}
        ))
    """
    
    def __init__(self, config: NotificationConfig):
        """
        Initialize the notification manager.
        
        Args:
            config: Notification configuration
        """
        self.config = config
        
        # Initialize notifiers
        self.email_notifier = None
        self.slack_notifier = None
        
        if config.email_config:
            self.email_notifier = EmailNotifier(config.email_config)
            logger.info("Email notifier initialized")
        
        if config.slack_config:
            self.slack_notifier = SlackNotifier(config.slack_config)
            logger.info("Slack notifier initialized")
        
        if not self.email_notifier and not self.slack_notifier:
            logger.warning("No notification channels configured")
    
    async def send_alert(
        self,
        alert: Alert,
        channel: Optional[NotificationChannel] = None
    ) -> bool:
        """
        Send an alert through appropriate channels.
        
        Args:
            alert: Alert to send
            channel: Optional channel override
            
        Returns:
            True if at least one notification succeeded
        """
        # Determine which channel to use
        if channel is None:
            channel = self._get_channel_for_level(alert.level)
        
        success = False
        
        # Send via email
        if channel in [NotificationChannel.EMAIL, NotificationChannel.BOTH]:
            if self.email_notifier and self.config.alert_emails:
                email_success = self.email_notifier.send_alert(
                    to_emails=self.config.alert_emails,
                    subject=f"{alert.component}: {alert.message}",
                    message=alert.message,
                    level=alert.level.value,
                    details=alert.details
                )
                success = success or email_success
            else:
                logger.debug("Email notifier not configured or no recipients")
        
        # Send via Slack
        if channel in [NotificationChannel.SLACK, NotificationChannel.BOTH]:
            if self.slack_notifier:
                slack_success = await self.slack_notifier.send_alert(
                    message=alert.message,
                    level=alert.level.value,
                    title=f"{alert.component}",
                    details=alert.details,
                    channel=self.config.slack_channel
                )
                success = success or slack_success
            else:
                logger.debug("Slack notifier not configured")
        
        return success
    
    async def send_funding_alert(
        self,
        status: str,
        amount: Optional[float] = None,
        transfer_id: Optional[str] = None,
        error: Optional[str] = None,
        channel: Optional[NotificationChannel] = None
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
            True if at least one notification succeeded
        """
        if channel is None:
            channel = self.config.error_channel if status == "FAILED" else self.config.info_channel
        
        success = False
        
        # Send via email
        if channel in [NotificationChannel.EMAIL, NotificationChannel.BOTH]:
            if self.email_notifier and self.config.alert_emails:
                email_success = self.email_notifier.send_funding_alert(
                    to_emails=self.config.alert_emails,
                    status=status,
                    amount=amount,
                    transfer_id=transfer_id,
                    error=error
                )
                success = success or email_success
        
        # Send via Slack
        if channel in [NotificationChannel.SLACK, NotificationChannel.BOTH]:
            if self.slack_notifier:
                slack_success = await self.slack_notifier.send_funding_alert(
                    status=status,
                    amount=amount,
                    transfer_id=transfer_id,
                    error=error,
                    channel=self.config.slack_channel
                )
                success = success or slack_success
        
        return success
    
    async def send_trade_alert(
        self,
        symbol: str,
        quantity: float,
        price: Optional[float] = None,
        status: str = "FILLED",
        order_id: Optional[str] = None,
        error: Optional[str] = None,
        channel: Optional[NotificationChannel] = None
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
            True if at least one notification succeeded
        """
        if channel is None:
            channel = self.config.error_channel if status == "FAILED" else self.config.info_channel
        
        success = False
        
        # Send via email
        if channel in [NotificationChannel.EMAIL, NotificationChannel.BOTH]:
            if self.email_notifier and self.config.alert_emails:
                email_success = self.email_notifier.send_trade_alert(
                    to_emails=self.config.alert_emails,
                    symbol=symbol,
                    quantity=quantity,
                    price=price,
                    status=status,
                    order_id=order_id,
                    error=error
                )
                success = success or email_success
        
        # Send via Slack
        if channel in [NotificationChannel.SLACK, NotificationChannel.BOTH]:
            if self.slack_notifier:
                slack_success = await self.slack_notifier.send_trade_alert(
                    symbol=symbol,
                    quantity=quantity,
                    price=price,
                    status=status,
                    order_id=order_id,
                    error=error,
                    channel=self.config.slack_channel
                )
                success = success or slack_success
        
        return success
    
    async def send_system_alert(
        self,
        component: str,
        message: str,
        level: str = "ERROR",
        details: Optional[Dict[str, Any]] = None,
        channel: Optional[NotificationChannel] = None
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
            True if at least one notification succeeded
        """
        if channel is None:
            channel = self._get_channel_for_level(AlertLevel(level))
        
        success = False
        
        # Send via email
        if channel in [NotificationChannel.EMAIL, NotificationChannel.BOTH]:
            if self.email_notifier and self.config.alert_emails:
                email_success = self.email_notifier.send_system_alert(
                    to_emails=self.config.alert_emails,
                    component=component,
                    message=message,
                    level=level,
                    details=details
                )
                success = success or email_success
        
        # Send via Slack
        if channel in [NotificationChannel.SLACK, NotificationChannel.BOTH]:
            if self.slack_notifier:
                slack_success = await self.slack_notifier.send_system_alert(
                    component=component,
                    message=message,
                    level=level,
                    details=details,
                    channel=self.config.slack_channel
                )
                success = success or slack_success
        
        return success
    
    def _get_channel_for_level(self, level: AlertLevel) -> NotificationChannel:
        """Get the appropriate notification channel for an alert level."""
        if level == AlertLevel.INFO:
            return self.config.info_channel
        elif level == AlertLevel.WARNING:
            return self.config.warning_channel
        elif level == AlertLevel.ERROR:
            return self.config.error_channel
        elif level == AlertLevel.CRITICAL:
            return self.config.critical_channel
        else:
            return self.config.default_channel


# Global notification manager instance
_notification_manager: Optional[NotificationManager] = None


def initialize_notification_manager(config: NotificationConfig):
    """Initialize the global notification manager."""
    global _notification_manager
    _notification_manager = NotificationManager(config)
    logger.info("Notification manager initialized")


def get_notification_manager() -> Optional[NotificationManager]:
    """Get the global notification manager instance."""
    return _notification_manager


async def send_notification(
    alert: Alert,
    channel: Optional[NotificationChannel] = None
) -> bool:
    """
    Send a notification using the global notification manager.
    
    Args:
        alert: Alert to send
        channel: Optional channel override
        
    Returns:
        True if notification sent successfully
    """
    manager = get_notification_manager()
    if manager:
        return await manager.send_alert(alert, channel)
    else:
        logger.warning("Notification manager not initialized")
        return False
