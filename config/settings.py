"""Application settings and configuration."""

import os
from decimal import Decimal
from typing import Optional

from pydantic import BaseSettings, Field, PostgresDsn, validator


class Settings(BaseSettings):
    """Application settings with environment variable overrides."""

    # Application
    APP_NAME: str = "InvestorMimic Bot"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    DEBUG: bool = False
    ENVIRONMENT: str = "production"
    SECRET_KEY: str = Field(..., env="SECRET_KEY")

    # Database
    DATABASE_URL: PostgresDsn = Field(
        "postgresql+asyncpg://postgres:postgres@localhost:5432/investorbot", env="DATABASE_URL"
    )

    # Alpaca API
    ALPACA_API_KEY: str = Field(..., env="ALPACA_API_KEY")
    ALPACA_SECRET_KEY: str = Field(..., env="ALPACA_SECRET_KEY")
    ALPACA_PAPER: bool = Field(True, env="ALPACA_PAPER")
    ALPACA_BASE_URL: str = Field("https://paper-api.alpaca.markets", env="ALPACA_BASE_URL")

    # Alpaca Broker (optional - will auto-fetch if not provided)
    ALPACA_ACCOUNT_ID: Optional[str] = Field(None, env="ALPACA_ACCOUNT_ID")
    ALPACA_BANK_ID: Optional[str] = Field(None, env="ALPACA_BANK_ID")

    # Trading Settings
    PAPER_TRADING: bool = Field(True, env="PAPER_TRADING")
    MAX_POSITIONS: int = Field(10, env="MAX_POSITIONS")
    REBALANCE_FREQUENCY: int = Field(10, env="REBALANCE_FREQUENCY")  # days
    SIGNAL_THRESHOLD: float = Field(0.6, env="SIGNAL_THRESHOLD")
    STOP_LOSS_PCT: float = Field(0.20, env="STOP_LOSS_PCT")
    MAX_POSITION_SIZE: float = Field(0.15, env="MAX_POSITION_SIZE")  # % of portfolio
    TRANSACTION_COST: float = Field(0.001, env="TRANSACTION_COST")  # 0.1%
    SLIPPAGE: float = Field(0.0005, env="SLIPPAGE")  # 0.05%

    # CORS
    ALLOWED_ORIGINS: str = Field(
        "http://localhost:3000,http://localhost:8000", env="ALLOWED_ORIGINS"
    )

    # Logging
    LOG_LEVEL: str = Field("INFO", env="LOG_LEVEL")
    LOG_FILE: str = Field("logs/app.log", env="LOG_FILE")
    LOG_MAX_SIZE: int = Field(10, env="LOG_MAX_SIZE")  # MB
    LOG_BACKUP_COUNT: int = Field(5, env="LOG_BACKUP_COUNT")

    # Funding Configuration
    DEFAULT_ALLOCATION_PERCENT: float = Field(25.0, ge=0, le=100, env="DEFAULT_ALLOCATION_PERCENT")
    MIN_INVESTMENT_AMOUNT: Decimal = Field(Decimal("100.00"), gt=0, env="MIN_INVESTMENT_AMOUNT")
    CASH_BUFFER_AMOUNT: Decimal = Field(Decimal("1000.00"), ge=0, env="CASH_BUFFER_AMOUNT")

    # Plaid Configuration (optional)
    PLAID_CLIENT_ID: Optional[str] = Field(None, env="PLAID_CLIENT_ID")
    PLAID_SECRET: Optional[str] = Field(None, env="PLAID_SECRET")
    PLAID_ENV: str = Field("sandbox", env="PLAID_ENV")  # sandbox, development, or production

    # Email Notifications (optional)
    SMTP_SERVER: Optional[str] = Field(None, env="SMTP_SERVER")
    SMTP_PORT: Optional[int] = Field(None, env="SMTP_PORT")
    SMTP_USERNAME: Optional[str] = Field(None, env="SMTP_USERNAME")
    SMTP_PASSWORD: Optional[str] = Field(None, env="SMTP_PASSWORD")
    ALERT_EMAIL: Optional[str] = Field(None, env="ALERT_EMAIL")

    # Slack Webhook (optional)
    SLACK_WEBHOOK_URL: Optional[str] = Field(None, env="SLACK_WEBHOOK_URL")
    SLACK_CHANNEL: Optional[str] = Field("#alerts", env="SLACK_CHANNEL")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

        @classmethod
        def parse_env_var(cls, field_name: str, raw_val: str):
            """Parse environment variables based on field type."""
            if field_name == "ALLOWED_ORIGINS":
                return [origin.strip() for origin in raw_val.split(",") if origin.strip()]
            return cls.json_loads(raw_val)  # type: ignore

    @validator("ALLOWED_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v):
        """Parse ALLOWED_ORIGINS from comma-separated string."""
        if isinstance(v, str):
            # Return as string, will be parsed by FastAPI middleware
            return v
        return v

    @validator("MIN_INVESTMENT_AMOUNT", "CASH_BUFFER_AMOUNT", pre=True)
    def parse_decimal(cls, v):
        """Parse string values to Decimal."""
        if isinstance(v, str):
            return Decimal(v)
        return v


# Create settings instance
settings = Settings()


def get_alpaca_account_id() -> Optional[str]:
    """
    Get Alpaca account ID from settings or fetch via API.

    Returns:
        Account ID or None if not available
    """
    if settings.ALPACA_ACCOUNT_ID:
        return settings.ALPACA_ACCOUNT_ID

    # Try to fetch via API
    try:
        from utils.alpaca_helpers import get_alpaca_account_id

        account_id = get_alpaca_account_id(
            api_key=settings.ALPACA_API_KEY,
            secret_key=settings.ALPACA_SECRET_KEY,
            sandbox=settings.ALPACA_PAPER,
        )
        return account_id
    except Exception as e:
        import logging

        logging.warning(f"Could not auto-fetch Alpaca account ID: {e}")
        return None


def get_alpaca_bank_id() -> Optional[str]:
    """
    Get Alpaca bank ID from settings or fetch via API.

    Returns:
        Bank ID or None if not available
    """
    if settings.ALPACA_BANK_ID:
        return settings.ALPACA_BANK_ID

    # Try to fetch via API
    try:
        from utils.alpaca_helpers import get_alpaca_bank_id

        bank_id = get_alpaca_bank_id(
            api_key=settings.ALPACA_API_KEY,
            secret_key=settings.ALPACA_SECRET_KEY,
            sandbox=settings.ALPACA_PAPER,
        )
        return bank_id
    except Exception as e:
        import logging

        logging.warning(f"Could not auto-fetch Alpaca bank ID: {e}")
        return None


def get_notification_config():
    """
    Get notification configuration from settings.

    Returns:
        NotificationConfig if any notification channels are configured, None otherwise
    """
    from services.monitoring.email_notifier import EmailConfig
    from services.monitoring.notification_manager import NotificationChannel, NotificationConfig
    from services.monitoring.slack_notifier import SlackConfig

    email_config = None
    slack_config = None

    # Configure email if settings are present
    if all([settings.SMTP_SERVER, settings.SMTP_USERNAME, settings.SMTP_PASSWORD]):
        email_config = EmailConfig(
            smtp_server=settings.SMTP_SERVER,
            smtp_port=settings.SMTP_PORT or 587,
            smtp_username=settings.SMTP_USERNAME,
            smtp_password=settings.SMTP_PASSWORD,
            from_email=settings.SMTP_USERNAME,
        )

    # Configure Slack if webhook URL is present
    if settings.SLACK_WEBHOOK_URL:
        slack_config = SlackConfig(
            webhook_url=settings.SLACK_WEBHOOK_URL, channel=settings.SLACK_CHANNEL
        )

    # Return None if no channels configured
    if not email_config and not slack_config:
        return None

    # Parse alert emails
    alert_emails = []
    if settings.ALERT_EMAIL:
        alert_emails = [email.strip() for email in settings.ALERT_EMAIL.split(",")]

    return NotificationConfig(
        email_config=email_config,
        slack_config=slack_config,
        alert_emails=alert_emails,
        slack_channel=settings.SLACK_CHANNEL,
        default_channel=NotificationChannel.BOTH,
        info_channel=NotificationChannel.SLACK,
        warning_channel=NotificationChannel.BOTH,
        error_channel=NotificationChannel.BOTH,
        critical_channel=NotificationChannel.BOTH,
    )
