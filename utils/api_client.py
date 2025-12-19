"""
API Client with Retry Logic and Rate Limiting

Provides resilient API calls with exponential backoff and rate limiting.
"""

import time
from functools import wraps
from typing import Any, Callable, Dict, Optional

import requests

from utils.enhanced_logging import get_logger
from utils.error_handler import APIError, retry_on_failure
from utils.rate_limiter import rate_limiter

logger = get_logger(__name__)


class APIClient:
    """Base API client with retry and rate limiting."""

    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        rate_limit_key: str = "default",
        timeout: int = 30,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.rate_limit_key = rate_limit_key
        self.timeout = timeout
        self.session = requests.Session()

        if api_key:
            self.session.headers.update({"Authorization": f"Bearer {api_key}"})

    @retry_on_failure(max_attempts=3, delay_seconds=1.0, backoff_factor=2.0)
    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        data: Optional[Dict] = None,
        headers: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Make HTTP request with retry logic."""
        # Wait for rate limit
        if not rate_limiter.wait_if_needed(self.rate_limit_key, max_wait=60.0):
            raise APIError(f"Rate limit exceeded for {self.rate_limit_key}")

        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        try:
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                json=data,
                headers=headers,
                timeout=self.timeout,
            )

            response.raise_for_status()

            logger.debug(f"API request successful: {method} {url}")

            return response.json() if response.content else {}

        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error: {e}", error=e)
            raise APIError(f"HTTP {e.response.status_code}: {e.response.text}")

        except requests.exceptions.Timeout as e:
            logger.error(f"Request timeout: {url}", error=e)
            raise APIError(f"Request timeout after {self.timeout}s")

        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {url}", error=e)
            raise APIError(f"Request failed: {str(e)}")

    def get(self, endpoint: str, params: Optional[Dict] = None, **kwargs) -> Dict[str, Any]:
        """Make GET request."""
        return self._make_request("GET", endpoint, params=params, **kwargs)

    def post(self, endpoint: str, data: Optional[Dict] = None, **kwargs) -> Dict[str, Any]:
        """Make POST request."""
        return self._make_request("POST", endpoint, data=data, **kwargs)

    def put(self, endpoint: str, data: Optional[Dict] = None, **kwargs) -> Dict[str, Any]:
        """Make PUT request."""
        return self._make_request("PUT", endpoint, data=data, **kwargs)

    def delete(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make DELETE request."""
        return self._make_request("DELETE", endpoint, **kwargs)


class AlpacaClient(APIClient):
    """Alpaca API client with specific methods."""

    def __init__(self, api_key: str, secret_key: str, paper: bool = True):
        base_url = "https://paper-api.alpaca.markets" if paper else "https://api.alpaca.markets"
        super().__init__(base_url, rate_limit_key="alpaca")

        self.session.headers.update({"APCA-API-KEY-ID": api_key, "APCA-API-SECRET-KEY": secret_key})

    def get_account(self) -> Dict[str, Any]:
        """Get account information."""
        return self.get("/v2/account")

    def get_positions(self) -> list:
        """Get current positions."""
        return self.get("/v2/positions")

    def place_order(
        self,
        symbol: str,
        qty: float,
        side: str,
        order_type: str = "market",
        time_in_force: str = "day",
    ) -> Dict[str, Any]:
        """Place an order."""
        data = {
            "symbol": symbol,
            "qty": qty,
            "side": side.lower(),
            "type": order_type,
            "time_in_force": time_in_force,
        }
        return self.post("/v2/orders", data=data)


class AlphaVantageClient(APIClient):
    """Alpha Vantage API client."""

    def __init__(self, api_key: str):
        super().__init__("https://www.alphavantage.co", api_key=api_key, rate_limit_key="alpha_vantage")

    def get_quote(self, symbol: str) -> Dict[str, Any]:
        """Get real-time quote."""
        params = {"function": "GLOBAL_QUOTE", "symbol": symbol, "apikey": self.api_key}
        return self.get("/query", params=params)

    def get_news_sentiment(self, tickers: str) -> Dict[str, Any]:
        """Get news sentiment."""
        params = {"function": "NEWS_SENTIMENT", "tickers": tickers, "apikey": self.api_key}
        return self.get("/query", params=params)

    def get_daily_prices(self, symbol: str, outputsize: str = "compact") -> Dict[str, Any]:
        """Get daily price data."""
        params = {
            "function": "TIME_SERIES_DAILY_ADJUSTED",
            "symbol": symbol,
            "outputsize": outputsize,
            "apikey": self.api_key,
        }
        return self.get("/query", params=params)


def with_api_retry(max_attempts: int = 3):
    """Decorator for API calls with retry logic."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            delay = 1.0

            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except APIError as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        logger.warning(
                            f"API call failed (attempt {attempt + 1}/{max_attempts}): {str(e)}. "
                            f"Retrying in {delay}s..."
                        )
                        time.sleep(delay)
                        delay *= 2

            logger.error(f"API call failed after {max_attempts} attempts")
            raise last_exception

        return wrapper

    return decorator
