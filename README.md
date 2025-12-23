# Investor Mimic Bot

Automated trading system that executes RSI-based mean reversion strategy on Alpaca paper trading.

## Strategy

- **Entry:** RSI < 30 + Volatility < 1.25x rolling median
- **Exit:** Hold for 20 days
- **Position Size:** 10% of capital per trade
- **Max Positions:** 10 concurrent, 2 per symbol

## Quick Start

### Using Makefile (Easiest)

```bash
# 1. Install dependencies
make install

# 2. Configure credentials
cp .env.example .env
# Edit .env with your Alpaca API keys

# 3. Sync database
make sync-db

# 4. Run all strategies
make run

# 5. View dashboard
make dashboard
# Open http://localhost:5000 in browser
```

### All Available Commands
```bash
make help              # Show all commands
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
