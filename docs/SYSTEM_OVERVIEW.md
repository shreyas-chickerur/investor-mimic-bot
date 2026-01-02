# Multi-Strategy Quantitative Trading System

**Status:** Production-ready, actively trading on Alpaca Paper Trading  
**Last Updated:** January 1, 2026

---

## What This System Does

Fully automated quantitative trading system that executes 4 independent strategies daily on Alpaca Markets. Runs at 6:30 AM PST via GitHub Actions, generates signals, executes trades, manages risk, and sends email notifications.

**Current Performance:**
- **Capital:** ~$100,000 paper trading account
- **Strategies:** 4 active (RSI Mean Reversion, MA Crossover, Momentum, ML Momentum)
- **Execution:** Automated daily via GitHub Actions
- **Trade Frequency Target:** 2-5 trades/week

---

## System Capabilities

### Core Features
- **Multi-strategy execution** - 4 independent strategies with separate capital allocation
- **Automated daily trading** - GitHub Actions runs at 6:30 AM PST weekdays
- **Professional risk management** - Portfolio heat limits, daily loss circuit breaker, correlation filtering
- **Regime-adaptive** - Adjusts risk based on VIX volatility levels
- **Production-ready infrastructure** - Kill switches, reconciliation gates, idempotent orders, signal funnel tracking

### Risk Controls
- Portfolio heat limits (20-40% based on regime)
- Daily loss circuit breaker (-2% halts trading)
- Correlation filter (rejects signals >0.7 correlated with existing positions)
- 3x ATR catastrophe stop losses
- Broker reconciliation before every trade

### Data & Execution
- 15 years historical data (2010-2025, 32 large-cap US stocks)
- Volatility-adjusted position sizing (ATR-based)
- Execution cost modeling (slippage + commission)
- Real-time broker state synchronization

---

## Quick Start

### Prerequisites
- GitHub account
- Alpaca API account (free paper trading)

### Setup (5 minutes)

1. **Add GitHub Secrets** (Settings → Secrets and variables → Actions):
   - `ALPACA_API_KEY` - Your Alpaca API key
   - `ALPACA_SECRET_KEY` - Your Alpaca secret key
   - `ALPHA_VANTAGE_API_KEY` - Data API key
   - `EMAIL_USERNAME` - Gmail for notifications (optional)
   - `EMAIL_PASSWORD` - Gmail app password (optional)
   - `EMAIL_TO` - Recipient email (optional)

2. **Push to GitHub:**
   ```bash
   git push origin main
   ```

3. **Verify:** Go to Actions tab, see "Daily Paper Trading" workflow running

### What Happens Daily

**6:30 AM PST (Weekdays)** - GitHub Actions triggers:
1. Fetch market data from Alpha Vantage
2. Check stop losses (3x ATR catastrophe stops)
3. Run broker reconciliation (halt if mismatch)
4. Generate signals from 4 strategies
5. Filter by correlation and risk limits
6. Execute top 3 signals per strategy
7. Send email digest with results
8. Upload database and logs as artifacts

---

## System Architecture

### Execution Flow
```
GitHub Actions (Cloud)
    ↓
1. Fetch Market Data → Alpha Vantage API
2. Load Database → SQLite (from previous run)
3. Check Stop Losses → 3x ATR exits
4. Broker Reconciliation → Alpaca API (MANDATORY GATE)
5. Kill Switch Check → Manual/automatic circuit breakers
6. Generate Signals → 4 strategies independently
7. Filter Signals → Correlation + risk checks
8. Execute Trades → Top 3 per strategy
9. Update Database → Positions, trades, metrics
10. Send Email → Daily digest with funnel analysis
11. Upload Artifacts → Database, logs (90-day retention)
```

### Key Components

**Execution Engine** (`src/execution_engine.py`)
- Orchestrates entire daily workflow
- Manages strategy lifecycle and trade execution
- Coordinates all risk management modules

**Strategies** (`src/strategies/`)
- RSI Mean Reversion - Buy oversold stocks turning upward
- MA Crossover - 20/100 MA with ADX trend confirmation
- Momentum - 20-day momentum with volume confirmation
- ML Momentum - Logistic regression classifier

**Risk Management**
- `portfolio_risk_manager.py` - Portfolio heat, daily loss limits
- `correlation_filter.py` - Dual-window correlation (60d + 20d)
- `regime_detector.py` - VIX-based market regime classification
- `stop_loss_manager.py` - 3x ATR catastrophe stops

**Production Features**
- `kill_switch_service.py` - Manual/automatic circuit breakers
- `signal_funnel_tracker.py` - Track signals through pipeline stages
- `broker_reconciler.py` - Mandatory reconciliation before trading
- `structured_logger.py` - JSON event logging

**Database** (`src/database.py`)
- SQLite with comprehensive schema
- Tables: strategies, signals, trades, positions, broker_state, signal_funnel, order_intents
- Persisted via GitHub Actions artifacts (90-day retention)

---

## Performance Expectations

### Realistic Targets (Expert-Validated)
| Metric | Target Range | Warning Signs |
|--------|--------------|---------------|
| **Sharpe Ratio** | 0.8 - 1.3 | >2.0 = likely leakage |
| **Max Drawdown** | 10% - 20% | <5% = unrealistic |
| **Annual Return** | 10% - 25% | >50% = unlikely without leverage |
| **Win Rate** | 45% - 55% | >65% = suspicious |

### Backtest Results (15 years, 2010-2025)
| Strategy | Total Return | Trades | Status |
|----------|--------------|--------|--------|
| MA Crossover | +155% | 662 | ✅ Active |
| Momentum | +152% | 4,330 | ✅ Active |
| RSI Mean Reversion | +124% | 2,229 | ✅ Active |
| ML Momentum | +107% | 17,812 | ✅ Active |

**Note:** Backtest results include survivorship bias and may not reflect live performance.

---

## Monitoring & Alerts

### Email Notifications
Daily digest includes:
- **Signal Funnel Analysis** - Track signals through each stage (raw → regime → correlation → risk → executed)
- **"Why No Trade?"** - Explains top blockers with examples
- **Trade Summary** - All executed trades with details
- **Portfolio Metrics** - Value, cash, heat, P&L
- **Strategy Performance** - Per-strategy metrics
- **Current Positions** - All open positions

### Critical Alerts
Automatic email alerts for:
- Reconciliation failures (trading blocked)
- Daily drawdown >15%
- No trades for >7 days
- Kill switch activation
- Database integrity issues

### Manual Monitoring
```bash
# Check latest run
gh run list --workflow=daily_trading.yml --limit 1

# Download database
gh run download <run_id> --name trading-database

# View signals
sqlite3 trading.db "SELECT * FROM signal_funnel ORDER BY created_at DESC LIMIT 5;"

# Check trades
sqlite3 trading.db "SELECT * FROM trades ORDER BY executed_at DESC LIMIT 10;"
```

---

## Configuration

### Environment Variables

**Required:**
- `ALPACA_API_KEY` - Broker API key
- `ALPACA_SECRET_KEY` - Broker secret
- `ALPACA_PAPER=true` - Always paper trading

**Optional:**
- `TRADING_DISABLED=false` - Global kill switch
- `STRATEGY_DISABLED_LIST=` - Comma-separated strategy names to disable
- `UNIVERSE_MODE=static` - Universe source (static|csv|dynamic)
- `MAX_PORTFOLIO_HEAT=0.30` - Portfolio exposure limit
- `MAX_DAILY_LOSS_PCT=0.02` - Daily loss circuit breaker
- `ENABLE_BROKER_RECONCILIATION=true` - Mandatory reconciliation gate
- `STRUCTURED_LOGGING=false` - JSON event logging

---

## Production Readiness Features

### Milestone 1: Visibility & Safety ✅
- **Signal Funnel Tracking** - Track signals through 5 stages with rejection reasons
- **Kill Switches** - Manual (`TRADING_DISABLED=true`) and automatic (reconciliation fail, excessive drawdown)
- **Idempotent Orders** - Deterministic intent IDs prevent duplicate orders on retries
- **Hard Reconciliation Gate** - Blocks trading on broker/DB mismatch
- **Enhanced Email** - Funnel summary and "Why No Trade" reports

### Milestone 2: Trade Frequency ✅
- **Universe Expansion** - Support for 150+ symbols via CSV
- **Correlation Attenuation** - Size scaling (0.5-0.8 corr = 100%→25% size) instead of binary reject
- **Pending Signals** - 3-day decay window for blocked-but-valid signals

### Milestone 3: Production Polish ✅
- **Typed Configuration** - Pydantic-based validation
- **Structured Logging** - JSON event logs for observability
- **Operations Runbook** - Emergency procedures and troubleshooting guide

---

## Known Limitations

1. **Paper trading only** - Not yet validated for live capital
2. **Daily execution** - No intraday trading
3. **Limited universe** - 32-36 stocks (expandable to 150+ via CSV)
4. **Survivorship bias** - Historical data contains only stocks that survived
5. **No sector limits** - Could over-concentrate in one sector
6. **Static execution costs** - Fixed slippage/commission (could scale by ATR/volume)

---

## Next Steps

### Immediate (Week 1)
- Monitor trade frequency with relaxed parameters
- Verify funnel tracking in daily emails
- Test kill switches and reconciliation gate

### Short-term (Month 1)
- Expand universe to 150+ symbols (set `UNIVERSE_MODE=csv`)
- Complete walk-forward validation
- Build performance dashboard

### Long-term (Quarter 1)
- Paper trading validation (2-4 weeks minimum)
- Stress test analysis (2008, 2020, 2022 periods)
- Live trading readiness assessment

---

## Support & Documentation

- **Usage Guide:** `docs/guides/USAGE_GUIDE.md` - Detailed how-to for all features
- **Architecture:** `docs/reference/ARCHITECTURE.md` - Technical implementation details
- **Runbook:** `docs/guides/RUNBOOK.md` - Emergency procedures and troubleshooting
- **Implementation Guide:** `docs/guides/PRODUCTION_READINESS_IMPLEMENTATION.md` - Production features spec

---

**System Status:** Production-ready for paper trading, actively monitoring performance
