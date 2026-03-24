#!/usr/bin/env python3
"""
Test individual strategies to verify signal generation against real data.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd
import pytest

pytestmark = pytest.mark.slow  # loads training_data.csv for all tests

from src.strategies.strategy_rsi_mean_reversion import RSIMeanReversionStrategy
from src.strategies.strategy_ma_crossover import MACrossoverStrategy
from src.strategies.strategy_volatility_breakout import VolatilityBreakoutStrategy
from src.strategies.strategy_earnings_drift import EarningsDriftStrategy
from src.strategies.strategy_factor_momentum import FactorMomentumStrategy

@pytest.fixture(scope="module")
def market_data():
    """Load market data for testing"""
    # Try tests/data first, then project root data/
    data_file = Path(__file__).parent.parent / 'data' / 'training_data.csv'
    if not data_file.exists():
        data_file = Path(__file__).parent.parent.parent / 'data' / 'training_data.csv'
    if not data_file.exists():
        pytest.skip("training_data.csv not found")
    df = pd.read_csv(data_file, index_col=0)
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    return df

STRATEGY_CLASSES = [
    ("RSI Mean Reversion", RSIMeanReversionStrategy),
    ("MA Crossover", MACrossoverStrategy),
    ("Volatility Breakout", VolatilityBreakoutStrategy),
    ("Earnings Drift", EarningsDriftStrategy),
    ("Factor Momentum", FactorMomentumStrategy),
]

@pytest.mark.parametrize("name,strategy_class", STRATEGY_CLASSES)
def test_strategy_generates_signals(name, strategy_class, market_data):
    """Each strategy should return a list of signals on real data."""
    strategy = strategy_class(1, 20000)
    recent_data = market_data.groupby("symbol", group_keys=False).tail(1000)
    signals = strategy.generate_signals(recent_data)
    assert isinstance(signals, list)

@pytest.mark.parametrize("name,strategy_class", STRATEGY_CLASSES)
def test_signal_structure(name, strategy_class, market_data):
    """Signals should have required keys with valid types."""
    strategy = strategy_class(1, 20000)
    recent_data = market_data.groupby("symbol", group_keys=False).tail(1000)
    signals = strategy.generate_signals(recent_data)
    for sig in signals:
        assert 'symbol' in sig
        assert 'action' in sig
        assert sig['action'] in ('BUY', 'SELL')
        assert 'price' in sig
        assert sig['price'] > 0
        assert 'confidence' in sig
        assert 0 <= sig['confidence'] <= 1
