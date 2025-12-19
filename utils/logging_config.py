import json
import logging
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

# Ensure logs directory exists
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)


# Structured log formatter for JSON logs
class StructuredFormatter(logging.Formatter):
    def _json_serialize(self, obj):
        """JSON serializer for objects not serializable by default"""
        if hasattr(obj, "isoformat"):
            return obj.isoformat() + "Z" if obj.tzinfo is None else obj.isoformat()
        elif hasattr(obj, "__dict__"):
            return {k: self._json_serialize(v) for k, v in obj.__dict__.items() if not k.startswith("_")}
        elif hasattr(obj, "__str__"):
            return str(obj)
        return obj

    def format(self, record):
        log_record = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add any extra attributes
        if hasattr(record, "data"):
            try:
                # Try to serialize the data
                serialized_data = {}
                for k, v in record.data.items():
                    try:
                        # Try to serialize the value
                        json.dumps({k: v}, default=str)
                        serialized_data[k] = v
                    except (TypeError, ValueError):
                        # If serialization fails, convert to string
                        serialized_data[k] = str(v)
                log_record.update(serialized_data)
            except Exception as e:
                log_record["data_error"] = f"Failed to serialize log data: {str(e)}"

        try:
            return json.dumps(log_record, default=self._json_serialize, ensure_ascii=False)
        except (TypeError, ValueError) as e:
            # If we still can't serialize, return a minimal error message
            error_record = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "level": "ERROR",
                "message": f"Failed to format log record: {str(e)}",
                "original_message": record.getMessage(),
            }
            return json.dumps(error_record, ensure_ascii=False)


def get_console_handler():
    """Get console handler for logging to stdout"""
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    return handler


def get_file_handler(log_file: str, max_mb: int = 10, backup_count: int = 5):
    """Get rotating file handler for logging to files"""
    handler = RotatingFileHandler(
        LOG_DIR / log_file,
        maxBytes=max_mb * 1024 * 1024,  # MB to bytes
        backupCount=backup_count,
        encoding="utf8",
    )
    handler.setLevel(logging.DEBUG)
    formatter = StructuredFormatter()
    handler.setFormatter(formatter)
    return handler


def setup_logger(name: str, log_file: Optional[str] = None, level: int = logging.INFO):
    """Set up a logger with both console and file handlers"""
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Don't propagate to parent loggers
    logger.propagate = False

    # Clear any existing handlers
    if logger.hasHandlers():
        logger.handlers.clear()

    # Add console handler
    logger.addHandler(get_console_handler())

    # Add file handler if log file is specified
    if log_file:
        logger.addHandler(get_file_handler(log_file))

    return logger


# Configure root logger
def configure_root_logger():
    """Configure the root logger with default settings"""
    # Set up root logger to capture all logs
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Clear any existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Add handlers
    root_logger.addHandler(get_console_handler())
    root_logger.addHandler(get_file_handler("bot.log"))

    # Suppress noisy logs from dependencies
    for logger_name in ["urllib3", "asyncio", "httpx"]:
        logging.getLogger(logger_name).setLevel(logging.WARNING)


# Initialize root logger when module is imported
configure_root_logger()

# Example usage:
# logger = setup_logger(__name__, "trading_bot.log")
# logger.info("This is an info message")
# logger.error("An error occurred", extra={"data": {"key": "value"}})
