# Investor Mimic Bot

**4-strategy quantitative trading system with regime-aware risk, news sentiment, and broker reconciliation.**

[![Paper Trading](https://img.shields.io/badge/Status-Paper%20Trading-blue)](https://app.alpaca.markets/paper/dashboard/overview)
[![Automated](https://img.shields.io/badge/Execution-Automated-green)](.github/workflows/daily_trading.yml)

---

## What This Does

Automated quantitative trading system running **4 independent strategies** on **36 large-cap US stocks**:

| Strategy | Edge | Hold Period |
|---|---|---|
| **RSI Mean Reversion** | Buy RSI < 40 + turning up, sell RSI > 55 | Up to 20 days |
| **ML Momentum** | LogisticRegression on 12 OHLCV+indicator features, P(5d gain) > 52% | 5 days |
| **Earnings Drift (PEAD)** | Buys volume-spike + abnormal-return events (positive earnings proxy) | 40 days |
| **Factor Momentum** | Cross-sectional rank by momentum/quality/reversion/volume percentiles, top 5 | 20 days |

**News Sentiment Layer** (via yfinance + VADER): boosts confidence on positive headlines, suppresses on negative, drops BUY signals on very negative news — applied to all 4 strategies.

- Executes **daily at 4:15 PM ET** via GitHub Actions
- **16 years of historical data** (2010–present)
- Portfolio-level risk: correlation filter, 50% heat cap, 2.5× ATR stop losses
- Regime detection using realized volatility proxy
- Broker reconciliation before every run
- Daily email digest with signal reasoning chains

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   GITHUB ACTIONS (Cloud)                     │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Daily Workflow (4:15 PM ET, Mon-Fri)                  │ │
│  │  1. Fetch Market Data (Alpha Vantage)                  │ │
│  │  2. Reconcile Broker (Alpaca positions + cash)         │ │
│  │  3. Generate Signals (5 strategies × 32 symbols)       │ │
│  │  4. Filter Signals (correlation, risk, regime)         │ │
│  │  5. Execute Trades (paper trading)                     │ │
│  │  6. Upload Artifacts (JSON + logs)                     │ │
│  │  7. Send Email Digest                                  │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                  LOCAL DEVELOPMENT                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Makefile   │  │  Dashboard   │  │  Backtesting │      │
│  │  Commands    │  │  (Streamlit) │  │  Framework   │      │
│  │  • setup     │  │  localhost:  │  │  • Walk-fwd  │      │
│  │  • test      │  │    8501      │  │  • Metrics   │      │
│  │  • run       │  │              │  │  • Reports   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                DATA & PERSISTENCE LAYER                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  trading.db  │  │  Artifacts   │  │  Alpaca API  │      │
│  │  • Signals   │  │  • Daily     │  │  • Positions │      │
│  │  • Trades    │  │    JSON      │  │  • Orders    │      │
│  │  • Positions │  │  • Markdown  │  │  • Market    │      │
│  │  • Broker    │  │  • 90-day    │  │    Data      │      │
│  │    State     │  │    retention │  │              │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

---

## Quick Start

### 1. Setup Environment

```bash
# Install dependencies
make install

# Create .env file from template
cp .env.example .env

# Add your API keys to .env:
# - ALPACA_API_KEY
# - ALPACA_SECRET_KEY
# - ALPHA_VANTAGE_API_KEY
```

### 2. Initialize System

```bash
# Initialize database
make init

# Fetch historical data (15 years)
make fetch-data

# Verify setup
make check-health
```

### 3. Run Trading System

```bash
# Run all strategies (paper trading)
make run

# View performance
make dashboard

# Check results
make report
```

---

## Makefile Commands

All commands are run via `make <command>`. Run `make help` to see all available commands.

### Setup & Installation
- `make install` - Install Python dependencies
- `make init` - Initialize database schema
- `make setup` - Full setup (install + init + fetch-data)
- `make check-health` - Verify system health

### Development
- `make run` - Execute trading system
- `make run-dry` - Dry run (no actual trades)
- `make dashboard` - Launch Streamlit dashboard
- `make logs` - View recent logs
- `make shell` - Open Python shell with imports

### Testing
- `make test` - Run all tests
- `make test-unit` - Run unit tests only
- `make test-integration` - Run integration tests
- `make test-component` - Run component tests
- `make test-functional` - Run functional tests
- `make test-coverage` - Run tests with coverage report
- `make test-watch` - Run tests in watch mode

### Data Management
- `make fetch-data` - Fetch historical market data
- `make update-data` - Update market data
- `make sync-broker` - Sync database with broker
- `make clean-data` - Clean cached data

### Analysis & Reporting
- `make report` - Generate performance report
- `make analyze` - Analyze signals (no trading)
- `make backtest` - Run backtest validation
- `make metrics` - Show portfolio metrics

### Validation & Debugging
- `make validate` - Validate system invariants
- `make verify` - Verify execution criteria
- `make check-broker` - Check broker state
- `make debug-signal` - Debug signal flow
- `make import-check` - Verify imports

### Maintenance
- `make clean` - Clean temporary files
- `make clean-all` - Deep clean (including DB)
- `make format` - Format code with black
- `make lint` - Lint code with flake8
- `make type-check` - Type check with mypy

---

## Project Structure

```
investor-mimic-bot/
├── .github/workflows/     # GitHub Actions CI/CD
├── artifacts/             # Daily execution artifacts
├── config/                # Configuration files
├── dashboard/             # Streamlit dashboard
├── data/                  # Market data cache
├── scripts/               # Utility scripts
├── src/                   # Core trading system
│   ├── core/             # Core engine & base classes
│   ├── data/             # Data fetchers & validators
│   ├── integration/      # Strategy runner & executor
│   ├── monitoring/       # Dashboard & metrics
│   ├── regime/           # Regime detection & allocation
│   ├── risk/             # Risk management & reconciliation
│   └── strategies/       # Trading strategies
├── tests/                 # Test suite (organized by type)
│   ├── unit/             # Unit tests
│   ├── integration/      # Integration tests
│   ├── component/        # Component tests
│   └── functional/       # Functional tests
├── .env                   # Environment variables (local)
├── .env.example           # Environment template
├── Makefile               # Command shortcuts
├── README.md              # This file
├── requirements.txt       # Python dependencies
└── trading.db             # SQLite database
```

---

## Trading Strategies

### 1. RSI Mean Reversion
- **Entry**: RSI < 40, RSI slope > 0 (turning up)
- **Exit**: RSI > 60 OR price ≥ VWAP OR 20 days
- **Indicators**: RSI(14), VWAP, ATR
- **Status**: ✅ Active, generating 3+ signals/day

### 2. MA Crossover (Trend Following)
- **Entry**: 20 MA crosses above 50 MA, ADX > 20
- **Exit**: 20 MA crosses below 50 MA
- **Indicators**: SMA(20/50), ADX
- **Status**: ✅ Active, awaits crossover conditions

### 3. ML Momentum
- **Entry**: Logistic regression predicts positive return (>55% confidence)
- **Exit**: Model predicts negative OR 5 days
- **Indicators**: RSI, 20-day return, volume ratio
- **Status**: ⚠️ Active but conservative (0 signals currently)

### 4. Volatility Breakout
- **Entry**: Price breaks above volatility bands
- **Exit**: Volatility conditions reverse
- **Indicators**: ATR, Bollinger Bands
- **Status**: ✅ Active, awaits breakout conditions

### 5. News Sentiment
- **Entry**: Positive news sentiment + technical confirmation
- **Exit**: Negative sentiment OR technical exit
- **Indicators**: News API, sentiment scores
- **Status**: ⚠️ Disabled (NEWS_API_KEY not configured)

---

## Risk Management

### Portfolio-Level Controls
- **Heat Limit**: 50% max exposure (regime-dependent: 50%/40%/30%)
- **Daily Loss Limit**: -5% circuit breaker
- **Correlation Filter**: Reject if >0.8 with existing positions (60-day + 20-day windows)
- **Position Sizing**: ATR-based, volatility-adjusted
- **Stop Losses**: 2.5x ATR catastrophe stops on all positions
- **Data Quality**: Blocks symbols with >10% NaN, stale data >72h, or price outliers

### Regime Detection (VIX-based)
- **LOW_VOL** (VIX < 15): All strategies active, 50% heat
- **NORMAL** (VIX 15-25): Standard mode, 40% heat
- **HIGH_VOL** (VIX > 25): Defensive mode, 30% heat, reduced sizing

### Broker Reconciliation
- Runs before every execution
- Compares database vs Alpaca positions/cash
- Blocks trading on any mismatch >1%
- Automatic sync available via `make sync-broker`

---

## Testing

Tests are organized by type in the `tests/` directory:

### Unit Tests (`tests/unit/`)
Test individual functions and classes in isolation.

```bash
make test-unit
```

### Integration Tests (`tests/integration/`)
Test interactions between multiple components.

```bash
make test-integration
```

### Component Tests (`tests/component/`)
Test complete subsystems (strategies, risk management, etc.).

```bash
make test-component
```

### Functional Tests (`tests/functional/`)
Test end-to-end workflows and user scenarios.

```bash
make test-functional
```

### Coverage
```bash
make test-coverage  # Generate HTML coverage report
```

---

## Environment Variables

Required in `.env` file:

```bash
# Alpaca API (Required)
ALPACA_API_KEY=your_api_key
ALPACA_SECRET_KEY=your_secret_key
ALPACA_BASE_URL=https://paper-api.alpaca.markets

# Alpha Vantage (Required for data)
ALPHA_VANTAGE_API_KEY=your_api_key

# Email Notifications (Optional)
SENDER_EMAIL=your-email@gmail.com
SENDER_PASSWORD=your-gmail-app-password
RECIPIENT_EMAIL=recipient@email.com

# Trading Controls (Optional)
TRADING_DISABLED=false
DRY_RUN=false
ENABLE_BROKER_RECONCILIATION=true
```

---

## GitHub Actions Setup

The system runs automatically via GitHub Actions with 2 workflows:

### 1. Daily Trading Execution
- **Schedule**: Mon-Fri at 4:15 PM ET (21:15 UTC)
- **Purpose**: Execute trading strategies
- **Manual trigger**: Actions tab → Daily Trading Execution → Run workflow

### 2. Daily Performance Monitoring
- **Schedule**: Mon-Fri at 5:00 PM ET (22:00 UTC)
- **Purpose**: Monitor system health and alert on failures
- **Checks**: Signals generated, trades executed, portfolio utilization, strategy performance, data freshness
- **Alerts**: Email sent only on failures (no daily spam)

### Required GitHub Secrets

Add these at Settings → Secrets → Actions:

**Trading (Required):**
- `ALPACA_API_KEY`
- `ALPACA_SECRET_KEY`
- `ALPHA_VANTAGE_API_KEY`

**Monitoring Alerts (Optional):**
- `EMAIL_USERNAME` - Gmail address
- `EMAIL_PASSWORD` - Gmail app password
- `ALERT_EMAIL` - Where to send failure alerts

---

## License

MIT
