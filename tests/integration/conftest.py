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
def test_database(tmp_path):
    """Create temporary test database"""
    import sys
    from pathlib import Path
    
    # Add src to path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    
    from src.database import Database
    
    db_path = tmp_path / "test.db"
    db = Database(str(db_path))
    
    # Initialize schema
    db.execute("""
        CREATE TABLE IF NOT EXISTS strategies (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            capital_allocation REAL,
            initial_capital REAL,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    db.execute("""
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy_id INTEGER,
            symbol TEXT NOT NULL,
            signal_type TEXT NOT NULL,
            confidence REAL,
            reasoning TEXT,
            asof_date DATE,
            generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            terminal_state TEXT,
            terminal_reason TEXT,
            FOREIGN KEY (strategy_id) REFERENCES strategies(id)
        )
    """)
    
    db.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy_id INTEGER,
            signal_id INTEGER,
            symbol TEXT NOT NULL,
            action TEXT NOT NULL,
            shares INTEGER NOT NULL,
            requested_price REAL,
            exec_price REAL,
            slippage_cost REAL,
            commission_cost REAL,
            total_cost REAL,
            notional REAL,
            order_id TEXT,
            executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            pnl REAL,
            FOREIGN KEY (strategy_id) REFERENCES strategies(id),
            FOREIGN KEY (signal_id) REFERENCES signals(id)
        )
    """)
    
    db.execute("""
        CREATE TABLE IF NOT EXISTS positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy_id INTEGER,
            symbol TEXT NOT NULL,
            shares INTEGER NOT NULL,
            avg_price REAL NOT NULL,
            current_price REAL,
            market_value REAL,
            unrealized_pnl REAL,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (strategy_id) REFERENCES strategies(id),
            UNIQUE(strategy_id, symbol)
        )
    """)
    
    db.execute("""
        CREATE TABLE IF NOT EXISTS broker_state (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_date DATE NOT NULL,
            snapshot_type TEXT NOT NULL,
            cash REAL NOT NULL,
            portfolio_value REAL NOT NULL,
            buying_power REAL,
            positions_json TEXT,
            reconciliation_status TEXT,
            discrepancies_json TEXT,
            run_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    return str(db_path)

@pytest.fixture
def mock_env_vars(monkeypatch):
    """Set up mock environment variables"""
    monkeypatch.setenv('ALPACA_API_KEY', 'test_key')
    monkeypatch.setenv('ALPACA_SECRET_KEY', 'test_secret')
    monkeypatch.setenv('ALPACA_PAPER', 'true')
    monkeypatch.setenv('DATA_MAX_AGE_HOURS', '72')
