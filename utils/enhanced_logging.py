"""
Enhanced Logging System

Provides structured logging with context, performance tracking, and database persistence.
"""

import logging
import sys
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path
import json
from utils.environment import env


class StructuredLogger:
    """Enhanced logger with structured output and database persistence."""

    def __init__(self, name: str, log_to_db: bool = True):
        self.name = name
        self.logger = logging.getLogger(name)
        self.log_to_db = log_to_db
        self._setup_logger()

    def _setup_logger(self):
        """Configure logger with appropriate handlers."""
        self.logger.setLevel(getattr(logging, env.log_level))

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        console_handler.setFormatter(console_formatter)

        # File handler
        log_file = env.get("LOG_FILE", "logs/app.log")
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s"
        )
        file_handler.setFormatter(file_formatter)

        # Add handlers if not already added
        if not self.logger.handlers:
            self.logger.addHandler(console_handler)
            self.logger.addHandler(file_handler)

    def _log_to_database(self, level: str, message: str, extra: Optional[Dict] = None):
        """Log to database for persistence and analysis."""
        if not self.log_to_db:
            return

        try:
            from db.base import get_db_session

            with get_db_session() as session:
                log_entry = {
                    "level": level,
                    "message": message,
                    "module": self.name,
                    "function": extra.get("function") if extra else None,
                    "error_details": json.dumps(extra) if extra else None,
                    "created_at": datetime.now(),
                }

                # Insert into system_logs table
                session.execute(
                    """
                    INSERT INTO system_logs (level, message, module, function, error_details, created_at)
                    VALUES (:level, :message, :module, :function, :error_details, :created_at)
                    """,
                    log_entry,
                )
                session.commit()
        except Exception as e:
            # Don't fail if database logging fails
            self.logger.warning(f"Failed to log to database: {e}")

    def debug(self, message: str, **kwargs):
        """Log debug message."""
        self.logger.debug(message, extra=kwargs)

    def info(self, message: str, **kwargs):
        """Log info message."""
        self.logger.info(message, extra=kwargs)
        self._log_to_database("INFO", message, kwargs)

    def warning(self, message: str, **kwargs):
        """Log warning message."""
        self.logger.warning(message, extra=kwargs)
        self._log_to_database("WARNING", message, kwargs)

    def error(self, message: str, error: Optional[Exception] = None, **kwargs):
        """Log error message."""
        if error:
            kwargs["error_type"] = type(error).__name__
            kwargs["error_message"] = str(error)

        self.logger.error(message, extra=kwargs)
        self._log_to_database("ERROR", message, kwargs)

    def critical(self, message: str, error: Optional[Exception] = None, **kwargs):
        """Log critical message."""
        if error:
            kwargs["error_type"] = type(error).__name__
            kwargs["error_message"] = str(error)

        self.logger.critical(message, extra=kwargs)
        self._log_to_database("CRITICAL", message, kwargs)

    def log_trade(self, action: str, ticker: str, quantity: float, price: float, **kwargs):
        """Log trade execution."""
        message = f"Trade: {action} {quantity} {ticker} @ ${price}"
        kwargs.update({"action": action, "ticker": ticker, "quantity": quantity, "price": price})
        self.info(message, **kwargs)

    def log_performance(self, metric: str, value: float, **kwargs):
        """Log performance metric."""
        message = f"Performance: {metric} = {value}"
        kwargs.update({"metric": metric, "value": value})
        self.info(message, **kwargs)


def get_logger(name: str) -> StructuredLogger:
    """Get a structured logger instance."""
    return StructuredLogger(name)


# Create default logger
default_logger = get_logger("investor_mimic_bot")
