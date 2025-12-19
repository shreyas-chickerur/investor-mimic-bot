"""
Caching Layer with Redis Support

Provides in-memory and Redis caching for API responses and computed data.
"""

import hashlib
import pickle
from functools import wraps
from typing import Any, Callable, Optional

from utils.enhanced_logging import get_logger

logger = get_logger(__name__)

try:
    import redis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("Redis not available, using in-memory cache only")


class Cache:
    """Unified caching interface supporting both in-memory and Redis."""

    def __init__(self, redis_url: Optional[str] = None):
        self.memory_cache = {}
        self.redis_client = None

        if REDIS_AVAILABLE and redis_url:
            try:
                self.redis_client = redis.from_url(redis_url, decode_responses=False)
                self.redis_client.ping()
                logger.info("Redis cache connected")
            except Exception as e:
                logger.warning(f"Redis connection failed, using memory cache: {e}")

    def _make_key(self, key: str, prefix: str = "") -> str:
        """Create cache key with optional prefix."""
        full_key = f"{prefix}:{key}" if prefix else key
        return hashlib.md5(full_key.encode()).hexdigest()

    def get(self, key: str, prefix: str = "") -> Optional[Any]:
        """Get value from cache."""
        cache_key = self._make_key(key, prefix)

        # Try Redis first
        if self.redis_client:
            try:
                value = self.redis_client.get(cache_key)
                if value:
                    return pickle.loads(value)
            except Exception as e:
                logger.error(f"Redis get error: {e}")

        # Fall back to memory cache
        return self.memory_cache.get(cache_key)

    def set(self, key: str, value: Any, ttl: int = 300, prefix: str = "") -> bool:
        """Set value in cache with TTL in seconds."""
        cache_key = self._make_key(key, prefix)

        # Try Redis first
        if self.redis_client:
            try:
                serialized = pickle.dumps(value)
                self.redis_client.setex(cache_key, ttl, serialized)
                return True
            except Exception as e:
                logger.error(f"Redis set error: {e}")

        # Fall back to memory cache
        self.memory_cache[cache_key] = value
        return True

    def delete(self, key: str, prefix: str = "") -> bool:
        """Delete value from cache."""
        cache_key = self._make_key(key, prefix)

        if self.redis_client:
            try:
                self.redis_client.delete(cache_key)
            except Exception as e:
                logger.error(f"Redis delete error: {e}")

        self.memory_cache.pop(cache_key, None)
        return True

    def clear(self, prefix: Optional[str] = None) -> bool:
        """Clear cache, optionally by prefix."""
        if prefix and self.redis_client:
            try:
                pattern = f"{prefix}:*"
                keys = self.redis_client.keys(pattern)
                if keys:
                    self.redis_client.delete(*keys)
            except Exception as e:
                logger.error(f"Redis clear error: {e}")
        elif not prefix:
            if self.redis_client:
                try:
                    self.redis_client.flushdb()
                except Exception as e:
                    logger.error(f"Redis flush error: {e}")
            self.memory_cache.clear()

        return True


# Global cache instance
_cache = None


def get_cache() -> Cache:
    """Get global cache instance."""
    global _cache
    if _cache is None:
        from utils.environment import env

        redis_url = env.get("REDIS_URL")
        _cache = Cache(redis_url)
    return _cache


def cached(ttl: int = 300, prefix: str = ""):
    """
    Decorator to cache function results.

    Args:
        ttl: Time to live in seconds
        prefix: Cache key prefix
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Create cache key from function name and arguments
            key_parts = [func.__name__]
            key_parts.extend(str(arg) for arg in args)
            key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
            cache_key = ":".join(key_parts)

            # Try to get from cache
            cache = get_cache()
            cached_value = cache.get(cache_key, prefix)

            if cached_value is not None:
                logger.debug(f"Cache hit: {func.__name__}")
                return cached_value

            # Compute and cache
            logger.debug(f"Cache miss: {func.__name__}")
            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl, prefix)

            return result

        return wrapper

    return decorator


# Convenience decorators for common use cases
def cache_stock_price(ttl: int = 300):
    """Cache stock price data."""
    return cached(ttl=ttl, prefix="price")


def cache_factor_score(ttl: int = 900):
    """Cache factor scores (15 min)."""
    return cached(ttl=ttl, prefix="factor")


def cache_13f_data(ttl: int = 86400):
    """Cache 13F data (24 hours)."""
    return cached(ttl=ttl, prefix="13f")


def cache_news(ttl: int = 3600):
    """Cache news data (1 hour)."""
    return cached(ttl=ttl, prefix="news")
