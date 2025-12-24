# Investor Mimic Bot

Multi-strategy quantitative trading system with portfolio-level risk management and automated execution.

## Phase 5: Automated Paper Trading

Fully automated daily execution with email notifications and live monitoring dashboard.

### Features

- **5 Trading Strategies**: RSI Mean Reversion, ML Momentum, News Sentiment, MA Crossover, Volatility Breakout
- **Portfolio Risk Management**: Heat limits (30%), daily loss limits (-2%), correlation filtering
- **Regime Detection**: VIX-based market regime adaptation
- **Broker Reconciliation**: Automated position verification with Alpaca
- **Execution Cost Modeling**: Realistic slippage and commission simulation
- **Live Dashboard**: Real-time strategy performance monitoring
- **Automated Execution**: GitHub Actions workflow runs daily at 6:30 AM PST
- **Email Notifications**: Daily digest with trade summaries and failure alerts

---

## Quick Start

### 1. Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys:
# - ALPACA_API_KEY
# - ALPACA_SECRET_KEY
# - ALPHA_VANTAGE_API_KEY (premium)
# - EMAIL credentials (optional)

# Initialize database
make init
```

### 2. Fetch Market Data

```bash
# Fetch 15 years of historical data (~18 seconds with premium API)
make fetch-data
```

### 3. Run Execution

```bash
# Run Phase 5 daily execution
make run
```

### 4. Monitor Performance

```bash
# Start live dashboard at http://localhost:8080
make dashboard

# Stop dashboard
make stop-dashboard
```

---

## Live Monitoring Dashboard

Access real-time strategy performance at **http://localhost:8080**

**Features:**
- Strategy P&L cards with win rates
- Performance charts over time
- Execution history with reconciliation status
- Auto-refresh every 30 seconds

**Start Dashboard:**
```bash
make dashboard
```

---

## Automated Execution (GitHub Actions)

### Schedule
- **Runs:** Every weekday at 6:30 AM PST
- **Duration:** 14-30 days of paper trading
- **No manual intervention required**

### Workflow Steps
1. Initialize database
2. Fetch fresh market data (~18s)
3. Verify positions cleared
4. Execute all 5 strategies
5. Verify reconciliation
6. Upload artifacts (30-day retention)
7. Send email digest

### Setup GitHub Secrets

Add these secrets at: https://github.com/YOUR_USERNAME/investor-mimic-bot/settings/secrets/actions

**Required:**
- `ALPACA_API_KEY`
- `ALPACA_SECRET_KEY`
- `ALPHA_VANTAGE_API_KEY`

**Optional (for email notifications):**
- `EMAIL_USERNAME` (Gmail address)
- `EMAIL_PASSWORD` (Gmail app password)
- `EMAIL_TO` (recipient email)

---

## Email Notifications

### Daily Digest (Success)
Sent every morning after successful execution:
- Reconciliation status
- Market regime (VIX level)
- All trades executed (symbol, shares, price, strategy)
- Portfolio risk metrics (heat, P&L)
- System health (runtime, errors, warnings)
- Links to artifacts and dashboard

### Failure Alerts
Sent immediately if any step fails:
- Error details
- Direct link to workflow logs
- Artifact name for debugging

---

## Available Commands

```bash
# Setup & Initialization
make init              # Initialize database for Phase 5
make fetch-data        # Fetch market data (premium API, ~18s)

# Execution
make run               # Run Phase 5 daily execution
make verify-positions  # Verify broker positions are cleared

# Monitoring
make dashboard         # Start live monitoring dashboard (port 8080)
make stop-dashboard    # Stop dashboard server

# Maintenance
make run               # Run all 5 strategies
make dashboard         # Web dashboard
make analyze           # Analyze signals
make view              # CLI performance
make logs              # View logs
make test              # Run tests
```

See `docs/MAKEFILE_GUIDE.md` for complete command reference.

### GitHub Actions (Cloud Deployment)

1. **Add GitHub Secrets:**
   - Go to: Settings → Secrets and variables → Actions
   - Add `ALPACA_API_KEY` and `ALPACA_SECRET_KEY`

2. **Enable Workflow:**
   - Push code to GitHub
   - Runs automatically weekdays at 10 AM ET

**Data Freshness Guarantees:**
- ✅ Market data updated every run (0 minutes stale)
- ✅ Database synced with Alpaca before trading
- ✅ Performance history persisted via artifacts
- ✅ See `docs/DATABASE_PERSISTENCE.md` for details

## What It Does

✅ Runs 5 independent trading strategies simultaneously  
✅ Each strategy has separate capital allocation and tracking  
✅ Scans 36 stocks daily across all strategies  
✅ Executes trades based on strategy-specific signals  
✅ Tracks performance individually for each strategy  
✅ Comprehensive dashboard for monitoring all strategies  

## The 5 Strategies

1. **RSI Mean Reversion** - Buy oversold stocks (RSI < 30) with low volatility
2. **MA Crossover** - Golden cross trend following (50/200 MA)
3. **Momentum** - Machine learning momentum prediction
4. **News Sentiment** - Sentiment analysis + technical indicators
5. **Volatility Breakout** - Bollinger Band breakouts with volume

Each strategy operates independently with $20K capital allocation.

## Monitoring

### Web Dashboard (Recommended)
```bash
make dashboard
# Opens http://localhost:5000
```
- Real-time performance tracking
- All 5 strategies in one view
- Auto-refreshes every 30 seconds
- Beautiful, easy-to-read interface

### Command Line
```bash
make view              # Strategy performance
make logs              # Recent logs
make positions         # Current positions
```

### Alpaca Dashboard
https://app.alpaca.markets/paper/dashboard/overview

## Documentation

See `docs/GUIDE.md` for complete documentation including:
- Configuration options
- Troubleshooting
- Performance metrics
- Security best practices

## Project Structure

```
investor-mimic-bot/
├── src/
│   ├── main.py              # Main trading execution
│   ├── trading_system.py    # Core strategy logic
│   └── strategies/          # Strategy implementations
├── scripts/
│   ├── sync_database.py     # Sync with Alpaca
│   └── update_data.py       # Update market data
├── data/
│   ├── training_data.csv    # Historical data
│   └── trading_system.db    # Position tracking
└── logs/                    # Execution logs
```

## Deployment

**GitHub Actions** - Automated cloud execution
- Runs weekdays at 10:00 AM ET
- No computer needed
- Free tier (2,000 minutes/month)
- Logs saved for 30 days

**Monitor:** https://github.com/YOUR_USERNAME/investor-mimic-bot/actions

## Status

✅ **Active** - Configured for GitHub Actions  
✅ Workflow ready for cloud deployment  
✅ 4 positions currently held  
✅ All systems operational
