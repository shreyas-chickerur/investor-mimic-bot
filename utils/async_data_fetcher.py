"""
Async Data Fetcher for Parallel Processing

Enables concurrent data fetching for multiple stocks, dramatically improving performance.
"""

import asyncio
from typing import List, Dict, Any, Optional, Callable
import aiohttp
from concurrent.futures import ThreadPoolExecutor
from utils.enhanced_logging import get_logger
from utils.cache import cache_stock_price
from utils.rate_limiter import rate_limiter

logger = get_logger(__name__)


class AsyncDataFetcher:
    """Asynchronous data fetcher for parallel operations."""
    
    def __init__(self, max_concurrent: int = 10):
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    async def fetch_url(
        self,
        url: str,
        params: Optional[Dict] = None,
        headers: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Fetch data from URL asynchronously."""
        async with self.semaphore:
            try:
                async with self.session.get(url, params=params, headers=headers, timeout=30) as response:
                    response.raise_for_status()
                    return await response.json()
            except Exception as e:
                logger.error(f"Async fetch error for {url}: {e}")
                return {}
    
    async def fetch_stock_data(self, ticker: str, data_fetcher: Callable) -> Dict[str, Any]:
        """Fetch data for a single stock."""
        async with self.semaphore:
            # Run synchronous function in thread pool
            loop = asyncio.get_event_loop()
            try:
                with ThreadPoolExecutor() as executor:
                    result = await loop.run_in_executor(executor, data_fetcher, ticker)
                return {'ticker': ticker, 'data': result, 'success': True}
            except Exception as e:
                logger.error(f"Error fetching {ticker}: {e}")
                return {'ticker': ticker, 'data': None, 'success': False, 'error': str(e)}
    
    async def fetch_multiple_stocks(
        self,
        tickers: List[str],
        data_fetcher: Callable
    ) -> List[Dict[str, Any]]:
        """Fetch data for multiple stocks in parallel."""
        tasks = [self.fetch_stock_data(ticker, data_fetcher) for ticker in tickers]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions
        valid_results = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Task failed: {result}")
            else:
                valid_results.append(result)
        
        return valid_results
    
    async def fetch_batch(
        self,
        items: List[Any],
        fetch_func: Callable,
        batch_size: int = 50
    ) -> List[Dict[str, Any]]:
        """Fetch items in batches to avoid overwhelming APIs."""
        all_results = []
        
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            logger.info(f"Processing batch {i//batch_size + 1}/{(len(items) + batch_size - 1)//batch_size}")
            
            tasks = [fetch_func(item) for item in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            valid_results = [r for r in batch_results if not isinstance(r, Exception)]
            all_results.extend(valid_results)
            
            # Small delay between batches
            await asyncio.sleep(0.5)
        
        return all_results


def run_async(coro):
    """Helper to run async function from sync code."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(coro)


async def fetch_all_stock_prices(tickers: List[str], price_fetcher: Callable) -> Dict[str, Any]:
    """
    Fetch prices for all stocks in parallel.
    
    Args:
        tickers: List of stock tickers
        price_fetcher: Function to fetch price for single ticker
        
    Returns:
        Dictionary mapping ticker to price data
    """
    async with AsyncDataFetcher(max_concurrent=10) as fetcher:
        results = await fetcher.fetch_multiple_stocks(tickers, price_fetcher)
    
    # Convert to dictionary
    price_data = {}
    for result in results:
        if result['success'] and result['data']:
            price_data[result['ticker']] = result['data']
    
    logger.info(f"Fetched prices for {len(price_data)}/{len(tickers)} stocks")
    return price_data


async def fetch_all_factor_scores(tickers: List[str], score_calculator: Callable) -> Dict[str, Dict[str, float]]:
    """
    Calculate factor scores for all stocks in parallel.
    
    Args:
        tickers: List of stock tickers
        score_calculator: Function to calculate scores for single ticker
        
    Returns:
        Dictionary mapping ticker to factor scores
    """
    async with AsyncDataFetcher(max_concurrent=20) as fetcher:
        results = await fetcher.fetch_multiple_stocks(tickers, score_calculator)
    
    # Convert to dictionary
    scores = {}
    for result in results:
        if result['success'] and result['data']:
            scores[result['ticker']] = result['data']
    
    logger.info(f"Calculated scores for {len(scores)}/{len(tickers)} stocks")
    return scores


# Convenience functions for sync code
def fetch_prices_parallel(tickers: List[str], price_fetcher: Callable) -> Dict[str, Any]:
    """Synchronous wrapper for parallel price fetching."""
    return run_async(fetch_all_stock_prices(tickers, price_fetcher))


def calculate_scores_parallel(tickers: List[str], score_calculator: Callable) -> Dict[str, Dict[str, float]]:
    """Synchronous wrapper for parallel score calculation."""
    return run_async(fetch_all_factor_scores(tickers, score_calculator))
