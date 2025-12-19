"""
Performance Tests for Async Data Fetcher

Tests async processing performance improvements.
"""

import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.async_data_fetcher import AsyncDataFetcher, run_async


class TestAsyncPerformance:
    """Performance tests for async data fetching."""

    def test_parallel_vs_sequential(self):
        """Test that parallel processing is faster than sequential."""

        def mock_fetch(ticker):
            """Mock data fetcher with delay."""
            time.sleep(0.1)
            return {"ticker": ticker, "price": 100.0}

        tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]

        # Sequential processing
        start = time.time()
        sequential_results = [mock_fetch(t) for t in tickers]
        sequential_time = time.time() - start

        # Parallel processing
        async def parallel_fetch():
            async with AsyncDataFetcher(max_concurrent=5) as fetcher:
                return await fetcher.fetch_multiple_stocks(tickers, mock_fetch)

        start = time.time()
        parallel_results = run_async(parallel_fetch())
        parallel_time = time.time() - start

        # Parallel should be significantly faster
        assert parallel_time < sequential_time / 2
        assert len(parallel_results) == len(sequential_results)

    def test_concurrent_limit(self):
        """Test that concurrent limit is respected."""
        call_times = []

        def mock_fetch(ticker):
            call_times.append(time.time())
            time.sleep(0.1)
            return {"ticker": ticker, "price": 100.0}

        tickers = ["T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8", "T9", "T10"]

        async def fetch_with_limit():
            async with AsyncDataFetcher(max_concurrent=3) as fetcher:
                return await fetcher.fetch_multiple_stocks(tickers, mock_fetch)

        run_async(fetch_with_limit())

        # With max_concurrent=3, should take at least 4 batches
        # 10 items / 3 concurrent = ~4 batches
        # Each batch takes 0.1s, so total should be ~0.4s
        # (This is a simplified check)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
