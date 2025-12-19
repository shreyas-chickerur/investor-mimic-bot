"""
Rate Limiter for API Calls

Implements token bucket algorithm for rate limiting.
"""

import time
from typing import Dict, Optional
from threading import Lock
from utils.environment import env


class RateLimiter:
    """Token bucket rate limiter."""

    def __init__(self, calls_per_window: int = None, window_seconds: int = 60):
        """
        Initialize rate limiter.

        Args:
            calls_per_window: Maximum calls per window (from env if None)
            window_seconds: Time window in seconds
        """
        self.calls_per_window = calls_per_window or env.api_rate_limit
        self.window_seconds = window_seconds
        self.buckets: Dict[str, Dict] = {}
        self.lock = Lock()

    def acquire(self, key: str = "default") -> bool:
        """
        Acquire a token for the given key.

        Args:
            key: Rate limit key (e.g., API name)

        Returns:
            True if token acquired, False if rate limited
        """
        with self.lock:
            now = time.time()

            if key not in self.buckets:
                self.buckets[key] = {"tokens": self.calls_per_window, "last_update": now}

            bucket = self.buckets[key]

            # Refill tokens based on time passed
            time_passed = now - bucket["last_update"]
            tokens_to_add = (time_passed / self.window_seconds) * self.calls_per_window
            bucket["tokens"] = min(self.calls_per_window, bucket["tokens"] + tokens_to_add)
            bucket["last_update"] = now

            # Try to consume a token
            if bucket["tokens"] >= 1:
                bucket["tokens"] -= 1
                return True

            return False

    def wait_if_needed(self, key: str = "default", max_wait: float = 60.0) -> bool:
        """
        Wait until a token is available.

        Args:
            key: Rate limit key
            max_wait: Maximum time to wait in seconds

        Returns:
            True if token acquired, False if timeout
        """
        start_time = time.time()

        while time.time() - start_time < max_wait:
            if self.acquire(key):
                return True
            time.sleep(0.1)

        return False

    def reset(self, key: Optional[str] = None):
        """Reset rate limiter for key or all keys."""
        with self.lock:
            if key:
                self.buckets.pop(key, None)
            else:
                self.buckets.clear()


# Global rate limiter instance
rate_limiter = RateLimiter()
