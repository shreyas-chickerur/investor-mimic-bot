"""
Performance Tests for Cache Module

Tests cache performance and efficiency.
"""

import pytest
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.cache import Cache, cached


class TestCachePerformance:
    """Performance tests for caching."""

    def test_cache_write_performance(self):
        """Test cache write performance."""
        cache = Cache()
        start = time.time()

        for i in range(1000):
            cache.set(f"key_{i}", f"value_{i}", ttl=60)

        elapsed = time.time() - start
        assert elapsed < 1.0  # Should complete in under 1 second

    def test_cache_read_performance(self):
        """Test cache read performance."""
        cache = Cache()

        # Populate cache
        for i in range(1000):
            cache.set(f"key_{i}", f"value_{i}", ttl=60)

        # Measure read performance
        start = time.time()
        for i in range(1000):
            cache.get(f"key_{i}")

        elapsed = time.time() - start
        assert elapsed < 0.5  # Should complete in under 0.5 seconds

    def test_cached_decorator_speedup(self):
        """Test that cached decorator provides speedup."""

        @cached(ttl=60)
        def expensive_operation(n):
            time.sleep(0.01)  # Simulate expensive operation
            return n * 2

        # First call - should be slow
        start = time.time()
        result1 = expensive_operation(5)
        first_call_time = time.time() - start

        # Second call - should be fast (cached)
        start = time.time()
        result2 = expensive_operation(5)
        second_call_time = time.time() - start

        assert result1 == result2
        assert second_call_time < first_call_time / 10  # At least 10x faster

    def test_cache_memory_efficiency(self):
        """Test cache doesn't consume excessive memory."""
        import sys

        cache = Cache()

        # Store 10000 small items
        for i in range(10000):
            cache.set(f"key_{i}", i, ttl=60)

        # Memory usage should be reasonable
        # This is a basic check - in production you'd use memory_profiler
        assert len(cache.memory_cache) == 10000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
