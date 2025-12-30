# Multi-Strategy Quantitative Trading System

**Automated portfolio-level trading system with 5 independent strategies, regime-aware risk management, and broker reconciliation.**

[![Paper Trading](https://img.shields.io/badge/Status-Paper%20Trading-blue)](https://app.alpaca.markets/paper/dashboard/overview)
[![Automated](https://img.shields.io/badge/Execution-Automated-green)](.github/workflows/daily_trading.yml)
[![Validated](https://img.shields.io/badge/System-Validated-success)](docs/reports/EMPIRICAL_VALIDATION_REPORT.md)

---

## 📊 Project Overview

This is a **production-ready quantitative trading system** designed for automated paper trading with Alpaca Markets. The system runs 5 independent trading strategies simultaneously, each with its own capital allocation, risk controls, and performance tracking.

### Key Features

- **5 Trading Strategies** - RSI Mean Reversion, ML Momentum, News Sentiment, MA Crossover, Volatility Breakout
- **Portfolio Risk Management** - 30% heat limit, -2% daily loss limit, correlation filtering (>0.7 rejection)
- **Regime Detection** - VIX-based market regime adaptation (NORMAL/HIGH_VOL/CRISIS)
- **Broker Reconciliation** - Automated position/cash verification before every execution
- **Execution Cost Modeling** - Realistic slippage (0.05%) and commission ($1/trade) simulation
- **Strategy Performance Tracking** - Per-strategy metrics, rankings, and visual analytics
- **Web Dashboard UI** - Beautiful interactive dashboard with charts and performance tables
- **Automated Execution** - GitHub Actions workflow runs daily at 6:30 AM PST
- **Email Notifications** - Daily digest with trade summaries, weekly visual reports (Mon/Wed/Fri)

### System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    GitHub Actions (Cloud)                    │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Daily Workflow (6:30 AM PST)                         │  │
│  │ 1. Fetch Market Data → 2. Reconcile Broker          │  │
│  │ 3. Generate Signals → 4. Execute Trades             │  │
│  │ 5. Upload Artifacts → 6. Send Email Digest          │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                   Local Development                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ Make Commands│  │  Dashboard   │  │  Backtesting │     │
│  │ • make run   │  │ localhost:   │  │ • Validation │     │
│  │ • make test  │  │   8080       │  │ • Walk-fwd   │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                  Data & Persistence Layer                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ trading.db   │  │ Artifacts    │  │ Alpaca API   │     │
│  │ • Strategies │  │ • Daily JSON │  │ • Positions  │     │
│  │ • Signals    │  │ • Markdown   │  │ • Orders     │     │
│  │ • Trades     │  │ • 30-day     │  │ • Market     │     │
│  │ • Snapshots  │  │   retention  │  │   Data       │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔄 Daily Workflow

### Automated Execution Flow

```
1. Pre-Execution Checks (6:30 AM PST)
   ├─ Fetch latest market data (Alpha Vantage)
   ├─ Calculate technical indicators (RSI, VWAP, ATR, ADX)
   └─ Verify broker reconciliation (positions + cash)

2. Signal Generation
   ├─ Each strategy analyzes 36 large-cap stocks
   ├─ Generate BUY/SELL signals with confidence scores
   └─ Log all signals to database with reasoning

3. Risk Filtering
   ├─ Correlation filter (reject if >0.7 with existing positions)
   ├─ Portfolio heat check (reject if would exceed 30%)
   ├─ Daily loss limit check (pause if down >2%)
   └─ Regime-based adjustments (VIX thresholds)

4. Position Sizing
   ├─ ATR-based volatility sizing (1% portfolio risk per trade)
   ├─ Cash availability check
   └─ Apply execution costs (slippage + commission)

5. Trade Execution
   ├─ Submit orders to Alpaca (paper trading)
   ├─ Record trades with full cost breakdown
   └─ Update terminal states (EXECUTED/REJECTED/FILTERED)

6. Post-Execution
   ├─ Take broker snapshot (START + END)
   ├─ Verify all signals have terminal states
   ├─ Generate daily artifact (JSON + Markdown)
   ├─ Upload to GitHub (30-day retention)
   └─ Send email digest with summary
```

### Broker Reconciliation

**Critical Safety Feature** - Runs before every execution:

- Compares local database vs Alpaca broker state
- Checks: position quantities, average prices, cash balance
- Tolerances: ±1 share, ±1% price, ±$10 cash
- **On mismatch:** System enters PAUSED state, sends alert email, blocks trading
- **On success:** Execution proceeds normally

---

## 📈 Trading Strategies & Indicators

### Strategy Portfolio

| Strategy | Capital | Entry Logic | Exit Logic | Indicators |
|----------|---------|-------------|------------|------------|
| **RSI Mean Reversion** | $20K | RSI < 30, RSI slope positive, near VWAP | RSI > 50 OR 20 days | RSI(14), VWAP, ATR |
| **ML Momentum** | $20K | ML classifier predicts up, volume > avg | ML predicts down OR 15 days | Logistic regression, volume |
| **News Sentiment** | $20K | Positive sentiment + RSI < 40 | Negative sentiment OR 10 days | News API, RSI |
| **MA Crossover** | $20K | 50 MA crosses above 200 MA, ADX > 25 | 50 MA crosses below 200 MA | SMA(50/200), ADX |
| **Volatility Breakout** | $20K | Price breaks upper Bollinger, volume spike | Price crosses middle Bollinger | Bollinger Bands, volume |

### Technical Indicators

**Calculated daily for all 36 stocks:**

- **RSI (14-day)** - Relative Strength Index for overbought/oversold
- **VWAP** - Volume-Weighted Average Price for intraday reference
- **ATR (20-day)** - Average True Range for volatility measurement
- **ADX** - Average Directional Index for trend strength
- **SMA (50/200)** - Simple Moving Averages for trend identification
- **Bollinger Bands (20, 2σ)** - Volatility bands for breakout detection

### Risk Management

**Portfolio-Level Controls:**
- **Heat Limit:** 30% max portfolio exposure (sum of position values / portfolio value)
- **Daily Loss Limit:** -2% max drawdown from daily start value
- **Correlation Filter:** Reject signals if correlation >0.7 with existing positions (60-day rolling)
- **Position Sizing:** ATR-based, 1% portfolio risk per trade
- **Execution Costs:** 0.05% slippage + $1 commission per trade

**Catastrophe Stop Losses:**
- 3x ATR stop losses on all positions
- Automatic execution when stops are hit
- Prevents single position from causing >25% loss
- Set automatically when positions are opened
- Removed automatically when positions are closed
- Full audit trail in logs and database

**Regime Detection (VIX-based):**
- **NORMAL:** VIX < 20 → All strategies active, 30% heat limit
- **HIGH_VOL:** VIX 20-30 → Reduce position sizes, 25% heat limit
- **CRISIS:** VIX > 30 → Defensive mode, 20% heat limit, disable momentum strategies

---

## 🗄️ Database & Artifacts Architecture

### Database Schema (`trading.db`)

**Single source of truth for operational trading validation.**

#### Core Tables

**`strategies`** - Strategy definitions and capital allocation
```sql
id, name, description, capital_allocation, initial_capital, status, created_at
```

**`signals`** - Trading signals with terminal state tracking
```sql
id, strategy_id, symbol, signal_type, confidence, reasoning, 
asof_date, generated_at, terminal_state, terminal_reason, terminal_at
```
- **Terminal States:** EXECUTED, REJECTED, FILTERED, REJECTED_BY_RECONCILIATION
- **Invariant:** Every signal must reach exactly one terminal state

**`trades`** - Executed trades with full cost breakdown
```sql
id, strategy_id, signal_id, symbol, action, shares, 
requested_price, exec_price, slippage_cost, commission_cost, 
total_cost, pnl, executed_at, run_id
```

**`positions`** - Current open positions
```sql
id, strategy_id, symbol, shares, entry_price, entry_date, 
current_price, unrealized_pnl, status
```

**`broker_state`** - Broker reconciliation snapshots
```sql
id, run_id, snapshot_type (START/END/RECONCILIATION), 
timestamp, positions_json, cash, portfolio_value
```

**`system_state`** - System-level state tracking
```sql
id, run_id, execution_date, start_time, end_time, 
portfolio_value_start, portfolio_value_end, daily_pnl, 
regime_type, regime_vix, status
```

#### How Database & Artifacts Work Together

**Database (`trading.db`):**
- Persistent SQLite database
- Tracks all trades, positions, signals across runs
- Enables historical analysis and performance tracking
- Used for broker reconciliation and state management

**Artifacts (JSON + Markdown):**
- Generated after each execution
- Uploaded to GitHub Actions (30-day retention)
- Portable snapshots of each day's execution
- Contains: signals, trades, positions, regime, reconciliation status
- Used for debugging, auditing, and reporting

**Workflow:**
```
1. Read from trading.db (load previous state)
2. Execute strategies (generate signals, execute trades)
3. Write to trading.db (update positions, record trades)
4. Generate artifact from trading.db (daily snapshot)
5. Upload artifact to GitHub (persistence + audit trail)
```

**Schema Documentation:** See [`docs/reference/TRADING_DB_SCHEMA.md`](docs/reference/TRADING_DB_SCHEMA.md)

---

## 🏗️ Infrastructure

### Local Development

**Requirements:**
- Python 3.8+
- SQLite3
- Alpaca Paper Trading Account
- Alpha Vantage API Key (premium for 15-year historical data)

**Environment Variables (`.env`):**
```bash
# Alpaca API (Required)
ALPACA_API_KEY=your_api_key
ALPACA_SECRET_KEY=your_secret_key
ALPACA_BASE_URL=https://paper-api.alpaca.markets

# Alpha Vantage (Required for data fetching)
ALPHA_VANTAGE_API_KEY=your_api_key

# Email Notifications (Optional)
SENDER_EMAIL=your-email@gmail.com
SENDER_PASSWORD=your-gmail-app-password
RECIPIENT_EMAIL=recipient@email.com
```

### GitHub Actions (Cloud)

**Automated Execution:**
- Runs on GitHub's infrastructure (free tier: 2,000 minutes/month)
- Scheduled via cron: `30 14 * * 1-5` (6:30 AM PST, weekdays only)
- No local computer needed
- Logs retained for 30 days

**Required GitHub Secrets:**
- `ALPACA_API_KEY`
- `ALPACA_SECRET_KEY`
- `ALPHA_VANTAGE_API_KEY`
- `SENDER_EMAIL` (optional)
- `SENDER_PASSWORD` (optional)
- `RECIPIENT_EMAIL` (optional)

**Workflow File:** [`.github/workflows/daily_trading.yml`](.github/workflows/daily_trading.yml)

### Monitoring Infrastructure

**Strategy Performance Dashboard:**
- Modern web UI with interactive charts (Chart.js)
- Real-time performance metrics and rankings
- Visual analytics: cumulative P&L, win rates, Sharpe ratios
- Access via: `python3 scripts/serve_dashboard.py` → http://localhost:8080/dashboard/strategy_performance.html

**Email Notifications:**
- **Daily digest** (every day): Portfolio metrics, trades, strategy performance table
- **Weekly visual reports** (Mon/Wed/Fri): Embedded strategy charts and trend analysis
- **Failure alerts**: Immediate notifications for workflow failures
- Beautiful HTML emails with blue/orange theme
- SMTP via Gmail

---

## 📁 Project Structure

### Key Directories

```
investor-mimic-bot/
├── .github/workflows/       # GitHub Actions workflows
│   └── daily_trading.yml    # Daily automated execution (6:30 AM PST)
├── artifacts/               # Daily execution artifacts (JSON + Markdown)
│   ├── json/               # Daily artifact JSON files
│   └── markdown/           # Daily markdown summaries
├── config/                 # Configuration files
├── dashboard/              # Web dashboard UI
│   └── strategy_performance.html  # Strategy performance dashboard
├── data/                   # Market data and training data
├── docs/                   # Documentation
│   ├── guides/            # Setup and usage guides
│   ├── reference/         # Technical reference docs
│   ├── reports/           # Validation and status reports
│   └── README.md          # Documentation index
├── examples/               # Sample data and mock templates
│   ├── send_sample_email.py      # Sample email generator
│   ├── sample_data/              # Sample artifacts
│   └── README.md                 # Examples documentation
├── scripts/                # Utility and execution scripts
│   ├── setup_database.py         # Database initialization
│   ├── fetch_historical_data.py  # Market data fetching
│   ├── check_broker_state.py     # Broker state verification
│   ├── generate_strategy_performance.py  # Strategy analysis
│   ├── generate_strategy_chart.py        # Chart generation
│   ├── generate_daily_email.py           # Email generation
│   ├── serve_dashboard.py                # Dashboard server
│   ├── validate_system.py                # System validation
│   ├── verify_execution.py               # Execution verification
│   ├── analyze_signals.py                # Signal analysis
│   ├── sync_database.py                  # Database sync
│   ├── update_data.py                    # Data updates
│   └── view_performance.py               # Performance viewer
├── src/                    # Core trading system code
│   ├── execution_engine.py       # Main execution engine
│   ├── broker_reconciler.py      # Broker reconciliation
│   ├── portfolio_risk_manager.py # Risk management
│   ├── regime_detector.py        # Market regime detection
│   ├── email_notifier.py         # Email notifications
│   ├── database.py               # Database interface
│   └── strategies/               # Trading strategies
│       ├── strategy_rsi_mean_reversion.py
│       ├── strategy_ml_momentum.py
│       ├── strategy_news_sentiment.py
│       ├── strategy_ma_crossover.py
│       └── strategy_volatility_breakout.py
├── tests/                  # Test suite
├── .env                    # Environment variables (local)
├── .env.example            # Environment template
├── Makefile                # Common commands
├── README.md               # This file
├── requirements.txt        # Python dependencies
└── trading.db              # SQLite database
```

### Key Files

**Configuration:**
- `.env` - Local environment variables (API keys, credentials)
- `.env.example` - Template for environment setup
- `requirements.txt` - Python package dependencies
- `Makefile` - Common command shortcuts

**Database:**
- `trading.db` - SQLite database (strategies, signals, trades, positions)

**Workflows:**
- `.github/workflows/daily_trading.yml` - Automated daily execution

## 📚 Documentation

### Quick Links

**Getting Started:**
- [General Guide](docs/guides/GUIDE.md) - Complete system overview
- [Makefile Commands](docs/guides/MAKEFILE_GUIDE.md) - All available commands
- [Market Open Checklist](docs/guides/MARKET_OPEN_CHECKLIST.md) - Pre-trading checklist

**Setup & Configuration:**
- [GitHub Secrets Setup](docs/guides/ADD_GITHUB_SECRETS.md) - Configure CI/CD
- [Automation Guide](docs/guides/AUTOMATION_GUIDE.md) - Setup automated workflows

**Technical Reference:**
- [Database Schema](docs/reference/TRADING_DB_SCHEMA.md) - Complete schema documentation
- [Strategy Flowcharts](docs/reference/STRATEGY_FLOWCHARTS.md) - Visual strategy logic
- [Email Notifications](docs/reference/EMAIL_NOTIFICATIONS.md) - Email system details
- [Known Limitations](docs/reference/KNOWN_LIMITATIONS.md) - System constraints

**GitHub Actions:**
- [Setup Guide](docs/github-actions/GITHUB_ACTIONS_SETUP.md) - Initial setup
- [Checklist](docs/github-actions/GITHUB_ACTIONS_CHECKLIST.md) - Pre-deployment checklist
- [Automation](docs/github-actions/GITHUB_ACTIONS_AUTOMATION.md) - Workflow details

**Reports & Validation:**
- [System Status](docs/reports/SYSTEM_STATUS.md) - Latest status
- [Empirical Validation](docs/reports/EMPIRICAL_VALIDATION_REPORT.md) - Backtest results
- [Algorithm Specification](docs/reports/ALGORITHM_SPECIFICATION.md) - Detailed algorithm docs

**Examples:**
- [Examples README](examples/README.md) - Sample data and mock templates

**Full Documentation Index:** [`docs/README.md`](docs/README.md)

---

## 🚀 Makefile Commands

### Setup & Initialization

#### `make init`
**Purpose:** Initialize database schema with all required tables

**Before running:**
- Ensure `.env` file exists with required credentials
- No prior setup needed

**Command:**
```bash
make init
```

**After running:**
- `trading.db` file created in project root
- All tables (strategies, signals, trades, positions, etc.) initialized
- Verify: `ls -lh trading.db` should show the database file

---

#### `make fetch-data`
**Purpose:** Fetch 15 years of historical market data for all 36 stocks

**Before running:**
- Run `make init` first
- Ensure `ALPHA_VANTAGE_API_KEY` is set in `.env`
- Premium API key recommended for faster fetching

**Command:**
```bash
make fetch-data
```

**After running:**
- Takes ~18 seconds with premium API
- Market data stored in `trading.db`
- Verify: `sqlite3 trading.db "SELECT COUNT(*) FROM market_data;"`

---

### Daily Execution

#### `make run`
**Purpose:** Execute all 5 trading strategies with live broker integration

**Before running:**
- Run `make init` and `make fetch-data` first
- Ensure `ALPACA_API_KEY` and `ALPACA_SECRET_KEY` are set
- Check broker state: `make check-broker`
- Verify market data is current: `make update-data`

**Command:**
```bash
make run
```

**After running:**
- Trades executed and recorded in database
- Artifacts generated in `artifacts/json/` and `artifacts/markdown/`
- Check results: `make view` or `make perf-report`
- Review logs: `make logs`

---

#### `make verify-positions`
**Purpose:** Verify all broker positions are cleared (for testing)

**Before running:**
- Ensure Alpaca credentials are set

**Command:**
```bash
make verify-positions
```

**After running:**
- Exits with code 0 if no positions
- Exits with code 1 if positions exist
- Use before running tests or validation

---

### Strategy Performance Analysis

#### `make perf-report`
**Purpose:** Generate comprehensive 30-day strategy performance report

**Before running:**
- Requires trades in database (run `make run` first)
- No prerequisites for first-time use (will show "No trades")

**Command:**
```bash
make perf-report
```

**After running:**
- Report printed to console
- Data saved to `/tmp/strategy_performance.json`
- Shows: P&L, win rates, Sharpe ratios, profit factors

---

#### `make perf-chart`
**Purpose:** Generate visual performance charts (7-day cumulative P&L and win rates)

**Before running:**
- Requires trades in database
- Install matplotlib if not present

**Command:**
```bash
make perf-chart
```

**After running:**
- Chart saved to `/tmp/strategy_chart.html`
- Embedded base64 image ready for email
- Open in browser to view

---

#### `make perf-dashboard`
**Purpose:** Start interactive web dashboard for strategy performance

**Before running:**
- Ensure port 8080 is available
- Run `make perf-report` first to generate data

**Command:**
```bash
make perf-dashboard
```

**After running:**
- Server starts on http://localhost:8080
- Open http://localhost:8080/dashboard/strategy_performance.html
- Press Ctrl+C to stop server

---

### Email & Notifications

#### `make email-daily`
**Purpose:** Generate daily email digest (standard format)

**Before running:**
- Requires today's artifact: run `make run` first
- Artifact must exist in `artifacts/json/YYYY-MM-DD.json`

**Command:**
```bash
make email-daily
```

**After running:**
- Email HTML generated at `/tmp/daily_email.html`
- Open in browser to preview
- Contains: portfolio metrics, trades, positions, strategy performance

---

#### `make email-weekly`
**Purpose:** Generate weekly email with embedded performance charts

**Before running:**
- Run `make perf-chart` first to generate charts
- Requires today's artifact

**Command:**
```bash
make email-weekly
```

**After running:**
- Email HTML with charts at `/tmp/daily_email.html`
- Includes 7-day performance visualizations
- Larger file size due to embedded images

---

#### `make email-sample`
**Purpose:** Generate sample email with mock data (for testing)

**Before running:**
- No prerequisites - uses mock data

**Command:**
```bash
make email-sample
```

**After running:**
- Sample email at `/tmp/sample_email.html`
- Shows example format with realistic data
- Use to preview email design

---

### System Validation

#### `make validate`
**Purpose:** Validate system invariants and data integrity

**Before running:**
- Requires database with execution data
- Run after `make run`

**Command:**
```bash
make validate
```

**After running:**
- Checks 6 system invariants
- Reports PASS/FAIL for each
- Review output for any failures

---

#### `make verify-system`
**Purpose:** Verify execution criteria and reconciliation

**Before running:**
- Requires completed execution
- Database must have latest run data

**Command:**
```bash
make verify-system
```

**After running:**
- Verifies signals have terminal states
- Checks reconciliation passed
- Confirms artifact generation

---

#### `make check-broker`
**Purpose:** Display current broker state (positions, cash, portfolio value)

**Before running:**
- Ensure Alpaca credentials are set
- No other prerequisites

**Command:**
```bash
make check-broker
```

**After running:**
- Shows current positions and cash
- Displays portfolio value
- Use before/after trading to verify state

---

#### `make import-check`
**Purpose:** Verify all Python modules load correctly

**Before running:**
- Run after any code changes
- Ensures dependencies are installed

**Command:**
```bash
make import-check
```

**After running:**
- Reports success or import errors
- Fix any missing dependencies before running system

---

### Analysis & Debugging

#### `make analyze`
**Purpose:** Analyze all strategies for signals (dry-run, no trading)

**Before running:**
- Requires market data: `make fetch-data` or `make update-data`
- No trades will be executed

**Command:**
```bash
make analyze
```

**After running:**
- Shows signals each strategy would generate
- Use to test strategy logic without trading
- Review signal quality before live execution

---

#### `make debug-signal`
**Purpose:** Debug single signal flow with detailed tracing

**Before running:**
- Requires specific signal to debug
- May need to modify script for target signal

**Command:**
```bash
make debug-signal
```

**After running:**
- Detailed trace of signal lifecycle
- Shows why signal was accepted/rejected
- Use for troubleshooting signal issues

---

#### `make backtest`
**Purpose:** Run validation backtest on historical data

**Before running:**
- Requires historical data: `make fetch-data`
- Takes several minutes to complete

**Command:**
```bash
make backtest
```

**After running:**
- Backtest results in console
- Performance metrics calculated
- Use to validate strategy performance

---

### Monitoring

#### `make view`
**Purpose:** View strategy performance dashboard (CLI)

**Before running:**
- Requires database with trade history
- Run `make run` first for meaningful data

**Command:**
```bash
make view
```

**After running:**
- Shows performance summary for all strategies
- Displays recent trades and signals
- Use regularly to monitor system health

---

#### `make logs`
**Purpose:** View recent trading logs (last 50 lines)

**Before running:**
- Logs must exist in `logs/multi_strategy.log`
- Run `make run` to generate logs

**Command:**
```bash
make logs
```

**After running:**
- Shows last 50 log lines
- Use to debug issues or verify execution
- Full logs in `logs/multi_strategy.log`

---

#### `make positions`
**Purpose:** Check current Alpaca positions

**Before running:**
- Ensure Alpaca credentials are set

**Command:**
```bash
make positions
```

**After running:**
- Lists all open positions
- Shows symbol, quantity, entry price
- Use to verify broker state

---

### Database & Data

#### `make sync-db`
**Purpose:** Sync local database with Alpaca broker state

**Before running:**
- Ensure Alpaca credentials are set
- Database must exist: `make init`

**Command:**
```bash
make sync-db
```

**After running:**
- Local positions updated from broker
- Cash balance synchronized
- Use after manual broker changes

---

#### `make update-data`
**Purpose:** Update market data with latest prices

**Before running:**
- Requires `ALPHA_VANTAGE_API_KEY`
- Database must exist

**Command:**
```bash
make update-data
```

**After running:**
- Latest market data fetched
- Database updated with new prices
- Run before `make run` for current data

---

### Testing

#### `make test`
**Purpose:** Run all tests (pytest)

**Before running:**
- Install pytest: `pip install pytest`
- No other prerequisites

**Command:**
```bash
make test
```

**After running:**
- All tests executed
- Shows pass/fail for each test
- Fix any failures before deployment

---

#### `make test-single`
**Purpose:** Test single strategy execution

**Before running:**
- Database and market data required

**Command:**
```bash
make test-single
```

**After running:**
- Single strategy tested in isolation
- Use to debug strategy-specific issues

---

#### `make test-multi`
**Purpose:** Test multi-strategy integration

**Before running:**
- Database and market data required

**Command:**
```bash
make test-multi
```

**After running:**
- Tests all strategies working together
- Verifies portfolio-level risk management

---

### Maintenance

#### `make clean`
**Purpose:** Clean logs and temporary files

**Before running:**
- No prerequisites
- Safe to run anytime

**Command:**
```bash
make clean
```

**After running:**
- Logs cleared from `logs/`
- Python cache files removed
- Temporary files deleted

---

#### `make clean-all`
**Purpose:** Deep clean including databases (⚠️ DESTRUCTIVE)

**Before running:**
- ⚠️ **WARNING:** Deletes all databases
- Backup `trading.db` if needed

**Command:**
```bash
make clean-all
```

**After running:**
- All databases deleted
- Logs and cache cleared
- Run `make init` to reinitialize

---

### Quick Reference

**First-time setup:**
```bash
make init          # Initialize database
make fetch-data    # Get historical data
make check-broker  # Verify broker connection
```

**Daily workflow:**
```bash
make check-broker  # Check current state
make update-data   # Get latest prices
make run           # Execute strategies
make view          # View results
```

**Performance analysis:**
```bash
make perf-report      # Generate report
make perf-chart       # Create charts
make perf-dashboard   # View dashboard
```

**Troubleshooting:**
```bash
make import-check  # Verify imports
make logs          # Check logs
make validate      # Verify system health
```

### Advanced Workflows

#### Strategy Performance Analysis
```bash
# Generate 30-day performance report
make perf-report

# Generate 7-day performance charts
make perf-chart

# Start interactive performance dashboard
make perf-dashboard
# Then open: http://localhost:8080/dashboard/strategy_performance.html
```

**Dashboard Features:**
- Real-time stats cards (total trades, P&L, win rate, top strategy)
- Interactive charts (cumulative P&L bar chart, win rate doughnut chart)
- Detailed performance table with color-coded metrics
- Top performer highlighting
- Responsive design for mobile/desktop

#### Database & System Management
```bash
# Initialize database schema
make init

# Sync database with broker
make sync-db

# Update market data
make update-data

# Fetch historical data
make fetch-data

# Validate system invariants
make validate

# Verify execution criteria
make verify-system

# Check broker state
make check-broker

# Import check (verify all modules load)
make import-check
```

#### Email & Notifications
```bash
# Generate daily email digest
make email-daily

# Generate weekly email with visuals (Mon/Wed/Fri style)
make email-weekly

# Generate performance chart for email
make email-chart

# Send sample email (mock data)
make email-sample

# Send sample email with visuals
make email-sample-visual
```

#### Analysis & Debugging
```bash
# Analyze all strategies for signals (dry-run)
make analyze

# Debug single signal flow
make debug-signal

# View strategy performance (CLI)
make view

# Run validation backtest
make backtest
```

#### Send Test Email (Current Data)
```bash
# First run execution to generate real data
make run

# Then send email with actual data
python3 -c "
import sys
sys.path.insert(0, 'src')
from email_notifier import EmailNotifier
from broker_reconciler import BrokerReconciler

notifier = EmailNotifier()
reconciler = BrokerReconciler()
broker_state = reconciler.get_broker_state()

# Load trades from database
import sqlite3
conn = sqlite3.connect('trading.db')
trades = conn.execute('SELECT * FROM trades WHERE DATE(executed_at) = DATE(\"now\")').fetchall()
conn.close()

notifier.send_daily_summary(
    trades=[dict(t) for t in trades],
    positions=broker_state['positions'],
    portfolio_value=broker_state['portfolio_value'],
    cash=broker_state['cash']
)
"
```

#### Dashboard with Sample Data
```bash
# Dashboard always uses current trading.db data
# To use sample data, first populate database with test data
python3 tests/test_backtest_minimal.py
make dashboard
```

#### Dashboard with Current Data
```bash
# Run execution first to populate with real data
make run
make dashboard
```

#### Backtesting

**Simple Backtest (Single Strategy):**
```bash
python3 scripts/run_simple_backtest.py
```

**Validation Backtest (Signal Injection):**
```bash
python3 scripts/run_validation_backtest.py
```

**Walk-Forward Backtest (Portfolio-Level):**
```bash
python3 scripts/run_walkforward_backtest.py
```

**Stress Test (Specific Periods):**
```bash
python3 scripts/stress_test_periods.py
```

#### Admin Dashboard (Compare Approaches)
```bash
# Start Flask dashboard server
python3 dashboard/app.py

# Open browser to http://localhost:8080
# Features:
# - Strategy performance comparison
# - Daily P&L charts
# - Execution history with reconciliation status
# - Auto-refresh every 30 seconds
```

---

## 🛠️ First-Time Setup

### Prerequisites

1. **Python 3.8+**
   ```bash
   python3 --version
   ```

2. **Alpaca Paper Trading Account**
   - Sign up: https://alpaca.markets
   - Get API keys from dashboard

3. **Alpha Vantage API Key**
   - Sign up: https://www.alphavantage.co/support/#api-key
   - Premium tier recommended for 15-year historical data

### Local Setup

```bash
# 1. Clone repository
git clone https://github.com/YOUR_USERNAME/investor-mimic-bot.git
cd investor-mimic-bot

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
nano .env  # Edit with your API keys

# Required:
# ALPACA_API_KEY=your_key
# ALPACA_SECRET_KEY=your_secret
# ALPHA_VANTAGE_API_KEY=your_key

# Optional (for email notifications):
# SENDER_EMAIL=your-email@gmail.com
# SENDER_PASSWORD=your-gmail-app-password
# RECIPIENT_EMAIL=recipient@email.com

# 4. Initialize database
make init

# 5. Fetch historical data (~18 seconds with premium API)
make fetch-data

# 6. Verify setup
make test

# 7. Run first execution
make run

# 8. Start dashboard
make dashboard
# Open http://localhost:8080
```

### GitHub Actions Setup

```bash
# 1. Push code to GitHub
git add .
git commit -m "Initial commit"
git push origin main

# 2. Add GitHub Secrets
# Go to: https://github.com/YOUR_USERNAME/investor-mimic-bot/settings/secrets/actions
# Add:
# - ALPACA_API_KEY
# - ALPACA_SECRET_KEY
# - ALPHA_VANTAGE_API_KEY
# - SENDER_EMAIL (optional)
# - SENDER_PASSWORD (optional)
# - RECIPIENT_EMAIL (optional)

# 3. Enable workflow
# Go to: https://github.com/YOUR_USERNAME/investor-mimic-bot/actions
# Enable workflows if prompted

# 4. Workflow will run automatically weekdays at 6:30 AM PST
# Or trigger manually: Actions → daily_trading → Run workflow
```

### Verification

```bash
# Check database was created
ls -lh trading.db

# Check data was fetched
sqlite3 trading.db "SELECT COUNT(*) FROM market_data;"

# Check strategies were initialized
sqlite3 trading.db "SELECT name, capital_allocation FROM strategies;"

# Run validation
python3 scripts/validate_system.py --latest
python3 scripts/verify_execution.py

# View first execution results
make view
```

---

## 📊 Status

✅ **Phase 5 Complete** - Production-ready for paper trading  
✅ **Automated Execution** - GitHub Actions configured  
✅ **Broker Reconciliation** - Safety checks active  
✅ **Email Notifications** - Daily digest + failure alerts  
✅ **Live Dashboard** - Real-time monitoring  
✅ **Empirically Validated** - Walk-forward backtesting complete

**Next Steps:**
1. Monitor paper trading performance (14-30 days)
2. Review daily artifacts and email digests
3. Validate system stability and risk controls
4. Consider live trading after successful paper trading period

---

## 📞 Support

**Issues or Questions:**
- Check [Known Limitations](docs/reference/KNOWN_LIMITATIONS.md)
- Review [Troubleshooting Guide](docs/guides/GUIDE.md#troubleshooting)
- See [GitHub Actions Logs](https://github.com/YOUR_USERNAME/investor-mimic-bot/actions)

**Monitoring:**
- **Alpaca Dashboard:** https://app.alpaca.markets/paper/dashboard/overview
- **GitHub Actions:** https://github.com/YOUR_USERNAME/investor-mimic-bot/actions
- **Local Dashboard:** http://localhost:8080 (after `make dashboard`)

---

## 📄 License

This project is for educational and research purposes only. Not financial advice.
