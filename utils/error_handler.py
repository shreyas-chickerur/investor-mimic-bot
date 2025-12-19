"""
Centralized Error Handling

Provides consistent error handling across the system.
"""

import logging
import traceback
from functools import wraps
from typing import Any, Callable

from utils.monitoring import monitor


class SystemError(Exception):
    """Base exception for system errors."""


class APIError(SystemError):
    """API-related errors."""


class DatabaseError(SystemError):
    """Database-related errors."""


class ValidationError(SystemError):
    """Data validation errors."""


class ConfigurationError(SystemError):
    """Configuration errors."""


def handle_errors(default_return: Any = None, raise_on_error: bool = False, log_level: str = "error"):
    """
    Decorator for consistent error handling.

    Args:
        default_return: Value to return on error
        raise_on_error: Whether to re-raise the exception
        log_level: Logging level for errors
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Log the error
                logger = logging.getLogger(func.__module__)
                log_func = getattr(logger, log_level, logger.error)

                error_msg = f"Error in {func.__name__}: {str(e)}"
                log_func(error_msg)
                log_func(traceback.format_exc())

                # Record in monitoring
                monitor.create_alert(
                    "error",
                    error_msg,
                    {
                        "function": func.__name__,
                        "module": func.__module__,
                        "error_type": type(e).__name__,
                        "traceback": traceback.format_exc(),
                    },
                )

                if raise_on_error:
                    raise

                return default_return

        return wrapper

    return decorator


def retry_on_failure(
    max_attempts: int = 3,
    delay_seconds: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: tuple = (Exception,),
):
    """
    Decorator to retry function on failure.

    Args:
        max_attempts: Maximum number of attempts
        delay_seconds: Initial delay between attempts
        backoff_factor: Multiplier for delay on each retry
        exceptions: Tuple of exceptions to catch
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            import time

            last_exception = None
            current_delay = delay_seconds

            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt < max_attempts - 1:
                        logger = logging.getLogger(func.__module__)
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_attempts} failed for {func.__name__}: {str(e)}. "
                            f"Retrying in {current_delay}s..."
                        )
                        time.sleep(current_delay)
                        current_delay *= backoff_factor
                    else:
                        logger.error(f"All {max_attempts} attempts failed for {func.__name__}")

            # All attempts failed
            if last_exception:
                raise last_exception

        return wrapper

    return decorator


class ErrorContext:
    """Context manager for error handling."""

    def __init__(self, operation: str, raise_on_error: bool = True, log_errors: bool = True):
        self.operation = operation
        self.raise_on_error = raise_on_error
        self.log_errors = log_errors
        self.logger = logging.getLogger(__name__)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            error_msg = f"Error during {self.operation}: {str(exc_val)}"

            if self.log_errors:
                self.logger.error(error_msg)
                self.logger.error(traceback.format_exc())

            monitor.create_alert(
                "error",
                error_msg,
                {
                    "operation": self.operation,
                    "error_type": exc_type.__name__,
                    "traceback": traceback.format_exc(),
                },
            )

            if not self.raise_on_error:
                return True  # Suppress exception

        return False  # Propagate exception if raise_on_error=True


def validate_input(validator: Callable[[Any], bool], error_message: str):
    """
    Decorator to validate function inputs.

    Args:
        validator: Function that returns True if input is valid
        error_message: Error message if validation fails
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not validator(*args, **kwargs):
                raise ValidationError(f"{func.__name__}: {error_message}")
            return func(*args, **kwargs)

        return wrapper

    return decorator
