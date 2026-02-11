"""Pytest fixtures for testing"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import tempfile
import os

@pytest.fixture
def mock_market_data():
    """Generate realistic mock market data"""
    dates = pd.date_range(end=datetime.now(), periods=100)
    data = pd.DataFrame({
        'symbol': ['AAPL'] * 100,
        'close': 150 + np.random.randn(100).cumsum(),
        'volume': np.random.randint(1000000, 5000000, 100),
        'rsi': 30 + np.random.randn(100) * 15,
        'atr': 5 + np.abs(np.random.randn(100) * 0.5),
        'macd': np.random.randn(100),
        'bb_upper': 155 + np.random.randn(100),
        'bb_lower': 145 + np.random.randn(100),
        'vwap': 150 + np.random.randn(100) * 2,
    }, index=dates)
    return data

@pytest.fixture
def mock_portfolio():
    """Mock portfolio with positions"""
    return {
        'cash': 50000,
        'portfolio_value': 100000,
        'positions': [
            {'symbol': 'AAPL', 'shares': 100, 'avg_price': 150},
            {'symbol': 'MSFT', 'shares': 50, 'avg_price': 300}
        ]
    }

@pytest.fixture
def mock_env_vars(monkeypatch):
    """Set up mock environment variables"""
    monkeypatch.setenv('ALPACA_API_KEY', 'test_key')
    monkeypatch.setenv('ALPACA_SECRET_KEY', 'test_secret')
    monkeypatch.setenv('ALPACA_PAPER', 'true')
    monkeypatch.setenv('DATA_MAX_AGE_HOURS', '72')
