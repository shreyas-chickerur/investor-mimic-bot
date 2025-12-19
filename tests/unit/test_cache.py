"""
Unit Tests for Cache Module

Tests the caching functionality in isolation.
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.cache import Cache, cached


class TestCache:
    """Unit tests for Cache class."""

    def test_cache_initialization(self):
        """Test cache initializes correctly."""
        cache = Cache()
        assert cache is not None
        assert cache.memory_cache == {}

    def test_set_and_get(self):
        """Test basic set and get operations."""
        cache = Cache()
        cache.set("test_key", "test_value", ttl=60)
        result = cache.get("test_key")
        assert result == "test_value"

    def test_get_nonexistent_key(self):
        """Test getting a key that doesn't exist."""
        cache = Cache()
        result = cache.get("nonexistent")
        assert result is None

    def test_delete(self):
        """Test cache deletion."""
        cache = Cache()
        cache.set("test_key", "test_value", ttl=60)
        cache.delete("test_key")
        result = cache.get("test_key")
        assert result is None

    def test_clear(self):
        """Test clearing entire cache."""
        cache = Cache()
        cache.set("key1", "value1", ttl=60)
        cache.set("key2", "value2", ttl=60)
        cache.clear()
        assert cache.get("key1") is None
        assert cache.get("key2") is None

    def test_prefix_isolation(self):
        """Test that prefixes isolate cache entries."""
        cache = Cache()
        cache.set("key", "value1", ttl=60, prefix="prefix1")
        cache.set("key", "value2", ttl=60, prefix="prefix2")

        result1 = cache.get("key", prefix="prefix1")
        result2 = cache.get("key", prefix="prefix2")

        assert result1 == "value1"
        assert result2 == "value2"

    def test_cached_decorator(self):
        """Test cached decorator functionality."""
        call_count = [0]

        @cached(ttl=60, prefix="test")
        def expensive_function(x):
            call_count[0] += 1
            return x * 2

        # First call - should execute
        result1 = expensive_function(5)
        assert result1 == 10
        assert call_count[0] == 1

        # Second call - should use cache
        result2 = expensive_function(5)
        assert result2 == 10
        assert call_count[0] == 1  # Should not increment

    def test_cached_decorator_different_args(self):
        """Test cached decorator with different arguments."""
        call_count = [0]

        @cached(ttl=60)
        def add(a, b):
            call_count[0] += 1
            return a + b

        result1 = add(1, 2)
        result2 = add(1, 2)
        result3 = add(2, 3)

        assert result1 == 3
        assert result2 == 3
        assert result3 == 5
        assert call_count[0] == 2  # Only 2 unique calls


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
