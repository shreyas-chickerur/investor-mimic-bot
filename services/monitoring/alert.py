"""Alerting module for the application."""

import asyncio
import logging
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class AlertLevel(str, Enum):
    """Enum for different alert levels."""

    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class Alert(BaseModel):
    """Alert model for system notifications."""

    level: AlertLevel
    message: str
    component: str
    details: Optional[Dict[str, Any]] = None

    async def send(self):
        """Send the alert to configured destinations."""
        log_msg = f"[{self.level}] {self.component}: {self.message}"
        if self.details:
            log_msg += f" | Details: {self.details}"

        if self.level in [AlertLevel.ERROR, AlertLevel.CRITICAL]:
            logger.error(log_msg)
        elif self.level == AlertLevel.WARNING:
            logger.warning(log_msg)
        else:
            logger.info(log_msg)

        # Send via notification manager if available
        try:
            from services.monitoring.notification_manager import get_notification_manager

            manager = get_notification_manager()
            if manager:
                await manager.send_alert(self)
        except Exception as e:
            logger.debug(f"Could not send notification: {e}")


async def send_alert(alert: Alert):
    """Helper function to send alerts.

    Args:
        alert: The alert to send
    """
    await alert.send()


def send_alert_sync(level: AlertLevel, message: str, component: str, details: Optional[Dict[str, Any]] = None):
    """Synchronous helper function to send alerts (for non-async contexts).

    Args:
        level: The severity level of the alert
        message: The alert message
        component: The component generating the alert
        details: Optional additional details as a dictionary
    """
    alert = Alert(level=level, message=message, component=component, details=details)

    # Log immediately
    log_msg = f"[{alert.level}] {alert.component}: {alert.message}"
    if alert.details:
        log_msg += f" | Details: {alert.details}"

    if alert.level in [AlertLevel.ERROR, AlertLevel.CRITICAL]:
        logger.error(log_msg)
    elif alert.level == AlertLevel.WARNING:
        logger.warning(log_msg)
    else:
        logger.info(log_msg)

    # Try to send via notification manager
    try:
        from services.monitoring.notification_manager import get_notification_manager

        manager = get_notification_manager()
        if manager:
            # Run async send in event loop
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Create task if loop is already running
                    asyncio.create_task(manager.send_alert(alert))
                else:
                    # Run in new event loop
                    loop.run_until_complete(manager.send_alert(alert))
            except RuntimeError:
                # No event loop, create one
                asyncio.run(manager.send_alert(alert))
    except Exception as e:
        logger.debug(f"Could not send notification: {e}")
