# Multi-Strategy Quantitative Trading System

**Automated portfolio-level trading system with 5 independent strategies, regime-aware risk management, and broker reconciliation.**

[![Phase 5](https://img.shields.io/badge/Phase-5%20Complete-success)](docs/reports/PHASE_5_FINAL_COMPLETE.md)
[![Paper Trading](https://img.shields.io/badge/Status-Paper%20Trading-blue)](https://app.alpaca.markets/paper/dashboard/overview)
[![Automated](https://img.shields.io/badge/Execution-Automated-green)](.github/workflows/phase5_morning_run.yml)

---

## 📊 Project Overview

This is a **production-ready quantitative trading system** designed for automated paper trading with Alpaca Markets. The system runs 5 independent trading strategies simultaneously, each with its own capital allocation, risk controls, and performance tracking.

### Key Features

- **5 Trading Strategies** - RSI Mean Reversion, ML Momentum, News Sentiment, MA Crossover, Volatility Breakout
- **Portfolio Risk Management** - 30% heat limit, -2% daily loss limit, correlation filtering (>0.7 rejection)
- **Regime Detection** - VIX-based market regime adaptation (NORMAL/HIGH_VOL/CRISIS)
- **Broker Reconciliation** - Automated position/cash verification before every execution
- **Execution Cost Modeling** - Realistic slippage (0.05%) and commission ($1/trade) simulation
- **Live Monitoring** - Real-time web dashboard with strategy performance tracking
- **Automated Execution** - GitHub Actions workflow runs daily at 6:30 AM PST
- **Email Notifications** - Daily digest with trade summaries and failure alerts

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

**Regime Detection (VIX-based):**
- **NORMAL:** VIX < 20 → All strategies active, 30% heat limit
- **HIGH_VOL:** VIX 20-30 → Reduce position sizes, 25% heat limit
- **CRISIS:** VIX > 30 → Defensive mode, 20% heat limit, disable momentum strategies

---

## 🗄️ Database & Artifacts Architecture

### Database Schema (`trading.db`)

**Single source of truth for Phase 5 operational validation.**

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

**Workflow File:** [`.github/workflows/phase5_morning_run.yml`](.github/workflows/phase5_morning_run.yml)

### Monitoring Infrastructure

**Live Dashboard:**
- Flask web server (port 8080)
- Real-time strategy performance
- Auto-refresh every 30 seconds
- Charts: P&L, win rates, trade history

**Email Notifications:**
- Daily digest (blue/orange theme)
- Failure alerts (immediate)
- SMTP via Gmail

---

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
- [Phase 5 Complete](docs/reports/PHASE_5_FINAL_COMPLETE.md) - Latest status
- [Empirical Validation](docs/reports/EMPIRICAL_VALIDATION_REPORT.md) - Backtest results
- [Algorithm Specification](docs/reports/ALGORITHM_SPECIFICATION.md) - Detailed algorithm docs

**Full Documentation Index:** [`docs/README.md`](docs/README.md)

---

## 🚀 Makefile Commands

### Main Commands

```bash
# Setup & Initialization
make init              # Initialize Phase 5 database schema
make fetch-data        # Fetch 15 years of historical data (~18 seconds)

# Daily Execution
make run               # Run Phase 5 daily execution (all 5 strategies)
make verify-positions  # Verify broker positions are cleared

# Monitoring
make dashboard         # Start live dashboard (http://localhost:8080)
make view              # View strategy performance (CLI)
make logs              # View recent trading logs
make positions         # Check current Alpaca positions

# Analysis
make analyze           # Analyze all strategies for signals (dry-run)

# Database Operations
make sync-db           # Sync local database with Alpaca broker
make update-data       # Update market data with latest prices

# Testing
make test              # Run all tests (pytest)
make test-single       # Test single strategy
make test-multi        # Test multi-strategy integration

# Maintenance
make clean             # Clean logs and temporary files
make clean-all         # Deep clean (including databases)
```

### Advanced Workflows

#### Send Test Email (Sample Data)
```bash
python3 scripts/test_email.py
```
Sends email with pre-defined sample data (5 trades, 7 positions, 2 warnings)

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
# Or trigger manually: Actions → phase5_morning_run → Run workflow
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
