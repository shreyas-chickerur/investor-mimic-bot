# Investor Mimic Bot

Automated trading system that executes RSI-based mean reversion strategy on Alpaca paper trading.

## Strategy

- **Entry:** RSI < 30 + Volatility < 1.25x rolling median
- **Exit:** Hold for 20 days
- **Position Size:** 10% of capital per trade
- **Max Positions:** 10 concurrent, 2 per symbol

## Quick Start

### GitHub Actions (Recommended - Runs in Cloud)

1. **Add GitHub Secrets:**
   - Go to: Settings → Secrets and variables → Actions
   - Add `ALPACA_API_KEY` and `ALPACA_SECRET_KEY`

2. **Enable Workflow:**
   - Push code to GitHub
   - Workflow runs automatically weekdays at 10 AM ET

3. **Manual Trigger (Optional):**
   - Go to Actions → Daily Paper Trading → Run workflow

### Local Testing

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure credentials
cp .env.example .env
# Edit .env with your Alpaca API keys

# 3. Run trading system
python3 src/main.py
```

## What It Does

✅ Scans 36 stocks daily for oversold conditions  
✅ Executes buy orders when signals are generated  
✅ Automatically closes positions after 20 days  
✅ Tracks all trades in local database  
✅ Logs all activity for monitoring  

## Monitoring

```bash
# View logs
tail -f logs/trading.log

# Check positions
sqlite3 data/trading_system.db "SELECT * FROM positions WHERE status='open'"

# Or check Alpaca dashboard
https://app.alpaca.markets/paper/dashboard/overview
```

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
