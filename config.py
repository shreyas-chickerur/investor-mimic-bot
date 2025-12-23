#!/usr/bin/env python3
"""
Configuration Management
Centralized configuration for the trading system
"""

# Strategy Configuration
NUM_STRATEGIES = 5
CAPITAL_ALLOCATION_METHOD = 'equal'  # 'equal' or 'weighted'

# Position Sizing
DEFAULT_POSITION_SIZE = 0.10  # 10% per trade
MAX_POSITIONS_PER_STRATEGY = 10
MAX_POSITIONS_PER_SYMBOL = 2

# Signal Execution
MAX_SIGNALS_PER_STRATEGY = 3  # Top N signals to execute per run

# Data Configuration
DATA_LOOKBACK_DAYS = 300  # Days of historical data to fetch
DATA_UPDATE_ON_RUN = True  # Update data before each run

# RSI Strategy Parameters
RSI_THRESHOLD = 30
RSI_HOLD_DAYS = 20
RSI_VOLATILITY_MULTIPLIER = 1.25

# MA Crossover Parameters
MA_SHORT_WINDOW = 50
MA_LONG_WINDOW = 200

# Volatility Breakout Parameters
VOLATILITY_THRESHOLD = 1.5
VOLUME_THRESHOLD = 1.5

# Database Configuration
USE_SINGLE_DATABASE = True  # Use consolidated database schema
DATABASE_PATH = 'data/trading_system.db'
STRATEGY_DB_PATH = 'data/strategy_performance.db'

# Logging Configuration
LOG_LEVEL = 'INFO'
LOG_TO_FILE = True
LOG_TO_CONSOLE = True

# API Configuration
ALPACA_PAPER_TRADING = True
ALPACA_TIMEOUT_SECONDS = 30

# Risk Management
MAX_PORTFOLIO_LEVERAGE = 1.0  # No leverage
EMERGENCY_STOP_LOSS_PCT = 0.50  # Stop all trading if down 50%

# Symbols to Trade
SYMBOLS = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA', 'NVDA', 'AMD',
    'NFLX', 'DIS', 'PYPL', 'INTC', 'CSCO', 'ADBE', 'CRM', 'ORCL',
    'QCOM', 'TXN', 'AVGO', 'COST', 'SBUX', 'MCD', 'NKE', 'WMT',
    'HD', 'LOW', 'TGT', 'CVS', 'UNH', 'JNJ', 'PFE', 'ABBV',
    'MRK', 'TMO', 'DHR', 'MDT'
]
