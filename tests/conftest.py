"""
Shared pytest fixtures for all tests.

All market-data fixtures use the same column schema as training_data.csv so
that strategies work against them without KeyError exceptions.
"""
import logging
import lzma
import os
import tempfile
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


@pytest.fixture(autouse=True, scope="session")
def _ensure_training_data():
    """Inflate the committed market-data snapshot when data/training_data.csv
    is absent (CI checkouts — the live file is gitignored and artifact-managed).

    Local working copies that already have the live file are never touched.
    The snapshot is the full production dataset with numerics rounded to 4dp
    (sub-cent prices, 1bp returns) so the slow/functional suites — including
    the DRY_RUN engine canary — exercise the real pipeline in CI.
    """
    repo_root = Path(__file__).parent.parent
    target = repo_root / "data" / "training_data.csv"
    snapshot = repo_root / "tests" / "fixtures" / "market_data_snapshot.csv.xz"
    if not target.exists() and snapshot.exists():
        target.parent.mkdir(exist_ok=True)
        target.write_bytes(lzma.decompress(snapshot.read_bytes()))


@pytest.fixture(autouse=True, scope="session")
def _isolate_file_handlers():
    """Remove FileHandlers from all loggers before the test session runs.

    Modules like update_daily_data and execution_engine call logging.basicConfig()
    at import time, which can attach FileHandlers that write to the production
    multi_strategy.log or api.log. Removing them prevents test runs from
    contaminating production log files.
    """
    root = logging.getLogger()
    file_handlers = [h for h in root.handlers if isinstance(h, logging.FileHandler)]
    for h in file_handlers:
        root.removeHandler(h)
        h.close()
    # Also scrub any named loggers that already have file handlers
    for _name, logger in logging.Logger.manager.loggerDict.items():
        if isinstance(logger, logging.Logger):
            fhs = [h for h in logger.handlers if isinstance(h, logging.FileHandler)]
            for h in fhs:
                logger.removeHandler(h)
                h.close()
    yield


# ---------------------------------------------------------------------------
# Market data helpers
# ---------------------------------------------------------------------------


def _make_ohlcv(
    symbol: str, n: int = 100, base_price: float = 150.0, rsi_val: float = 50.0
) -> pd.DataFrame:
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

    return pd.DataFrame(
        {
            "symbol": symbol,
            "open": close * 0.99,
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
            "volume": np.full(n, 1_500_000.0) + np.random.randn(n) * 2000,
            "rsi": rsi_series,
            "rsi_slope": np.zeros(n),
            "atr_20": close * 0.015,
            # Trailing 20-day VWAP — always below close in uptrends.
            # Do NOT use price >= vwap as an exit condition (this was the core bug).
            "vwap": close * 0.70,
            "volume_ratio": np.full(n, 1.0),
            "returns_1d": np.full(n, 0.001),
            "returns_5d": np.full(n, 0.01),
            "returns_20d": np.full(n, 0.02),
            "returns_60d": np.full(n, 0.05),
            "volatility_20d": np.full(n, 0.15),
            "volatility_60d": np.full(n, 0.15),
            "price_to_sma20": np.full(n, 1.01),
            "price_to_sma50": np.full(n, 1.02),
            "price_to_sma200": np.full(n, 1.05),
            "sma_20": close * 0.99,
            "sma_50": close * 0.98,
            "adx": np.full(n, 25.0),
            "future_return_5d": future_rets,
            "future_return_20d": future_rets * 2,
        },
        index=dates,
    )


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
            {"symbol": "MSFT", "shares": 50, "avg_price": 300},
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
