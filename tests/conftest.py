"""
Shared pytest fixtures for all tests.

All market-data fixtures use the same column schema as training_data.csv so
that strategies work against them without KeyError exceptions.
"""
import os
import tempfile

import numpy as np
import pandas as pd
import pytest
from datetime import datetime, timedelta


# ---------------------------------------------------------------------------
# Market data helpers
# ---------------------------------------------------------------------------

def _make_ohlcv(symbol: str, n: int = 100, base_price: float = 150.0,
                rsi_val: float = 50.0) -> pd.DataFrame:
    """
    Build a minimal but realistic market DataFrame matching the
    training_data.csv schema (same columns production strategies read).
    """
    np.random.seed(0)
    dates = pd.date_range(end=datetime.now(), periods=n, freq="B")
    close = base_price + np.cumsum(np.random.randn(n) * 0.5)
    close = np.maximum(close, 1.0)

    rsi_series = np.full(n, rsi_val, dtype=float)
    rsi_series[-2] = rsi_val - 1.0  # default slope = +1

    # Alternate future returns so ML model gets both classes
    future_rets = np.where(np.arange(n) % 2 == 0, 0.01, -0.01)

    return pd.DataFrame({
        "symbol":           symbol,
        "open":             close * 0.99,
        "high":             close * 1.01,
        "low":              close * 0.99,
        "close":            close,
        "volume":           np.full(n, 1_500_000.0) + np.random.randn(n) * 2000,
        "rsi":              rsi_series,
        "rsi_slope":        np.zeros(n),
        "atr_20":           close * 0.015,
        # Trailing 20-day VWAP — always below close in uptrends.
        # Do NOT use price >= vwap as an exit condition (this was the core bug).
        "vwap":             close * 0.70,
        "volume_ratio":     np.full(n, 1.0),
        "returns_1d":       np.full(n, 0.001),
        "returns_5d":       np.full(n, 0.01),
        "returns_20d":      np.full(n, 0.02),
        "returns_60d":      np.full(n, 0.05),
        "volatility_20d":   np.full(n, 0.15),
        "volatility_60d":   np.full(n, 0.15),
        "price_to_sma20":   np.full(n, 1.01),
        "price_to_sma50":   np.full(n, 1.02),
        "price_to_sma200":  np.full(n, 1.05),
        "sma_20":           close * 0.99,
        "sma_50":           close * 0.98,
        "adx":              np.full(n, 25.0),
        "future_return_5d": future_rets,
        "future_return_20d": future_rets * 2,
    }, index=dates)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_market_data():
    """Single-symbol AAPL market data (100 bars, RSI neutral)."""
    return _make_ohlcv("AAPL", n=100, base_price=150.0, rsi_val=50.0)


@pytest.fixture
def mock_market_data_oversold():
    """Single-symbol data with RSI < 40 and positive slope — RSI buy conditions met."""
    df = _make_ohlcv("AAPL", n=100, base_price=150.0, rsi_val=36.0)
    df["rsi"] = 36.0
    df.loc[df.index[-2], "rsi"] = 35.0  # slope = +1
    return df


@pytest.fixture
def mock_multi_symbol_data():
    """10-symbol market DataFrame with varied momentum for cross-sectional ranking."""
    np.random.seed(1)
    frames = []
    for i in range(10):
        sym = f"SYM{i:02d}"
        mom = -0.10 + i * 0.025  # -0.10 … +0.125
        df = _make_ohlcv(sym, n=80, base_price=50 + i * 5)
        df["returns_60d"] = mom
        df["returns_5d"] = mom * 0.5
        frames.append(df)
    return pd.concat(frames)


@pytest.fixture
def mock_portfolio():
    """Simple portfolio dict matching PortfolioRiskManager expectations."""
    return {
        "cash": 50_000,
        "portfolio_value": 100_000,
        "positions": [
            {"symbol": "AAPL", "shares": 100, "avg_price": 150},
            {"symbol": "MSFT", "shares": 50,  "avg_price": 300},
        ],
    }


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Minimal environment for unit tests that import config."""
    monkeypatch.setenv("ALPACA_API_KEY", "test_key")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "test_secret")
    monkeypatch.setenv("ALPACA_PAPER", "true")
    monkeypatch.setenv("DATA_MAX_AGE_HOURS", "72")
    monkeypatch.setenv("DRY_RUN", "true")


@pytest.fixture
def tmp_db_path():
    """Return a path to a temporary SQLite database that is cleaned up after the test."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    yield path
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass
