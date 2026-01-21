# Quick Start Guide - Multi-Strategy Trading System

**Last Updated:** January 2026  
**Version:** 2.0 (Post-Phase 2 & 3 Updates)

Complete guide for using the modernized trading system with YAML configuration, modular architecture, and real-time dashboard.

---

## Table of Contents

1. [Installation & Setup](#installation--setup)
2. [Running the System](#running-the-system)
3. [Configuration (NEW)](#configuration-new)
4. [Monitoring Dashboard (NEW)](#monitoring-dashboard-new)
5. [Daily Operations](#daily-operations)
6. [Adjusting Parameters](#adjusting-parameters)
7. [Emergency Procedures](#emergency-procedures)
8. [Common Tasks](#common-tasks)

---

## Installation & Setup

### Prerequisites

```bash
# Python 3.8+
python3 --version

# Git
git --version
```

### Initial Setup

**1. Clone Repository:**
```bash
git clone https://github.com/yourusername/investor-mimic-bot.git
cd investor-mimic-bot
```

**2. Install Dependencies:**
```bash
pip install -r requirements.txt
```

**3. Configure Environment:**
```bash
# Create .env file
cp .env.example .env

# Edit .env with your credentials
nano .env
```

**Required in `.env`:**
```bash
# Alpaca API (get from alpaca.markets)
ALPACA_API_KEY=your_key_here
ALPACA_SECRET_KEY=your_secret_here
ALPACA_BASE_URL=https://paper-api.alpaca.markets  # Paper trading
# ALPACA_BASE_URL=https://api.alpaca.markets      # Live trading

# Trading mode
TRADING_MODE=paper  # or 'live'
DRY_RUN=false       # Set to true for simulation

# Email alerts (optional)
EMAIL_USERNAME=your_email@gmail.com
EMAIL_PASSWORD=your_app_password
EMAIL_TO=recipient@email.com
```

**4. Verify Installation:**
```bash
# Run tests
pytest tests/ -v

# Check imports
python -c "from src.core.execution_engine import MultiStrategyRunner; print('✅ OK')"

# Load config
python -c "from src.utils.config_loader import get_config; c = get_config(); print('✅ Config loaded')"
```

---

## Running the System

### Basic Execution

**Paper Trading (Recommended First):**
```bash
# Ensure paper trading mode
export TRADING_MODE=paper
export ALPACA_BASE_URL=https://paper-api.alpaca.markets

# Run system
python src/core/execution_engine.py
```

**Dry Run (No Actual Trades):**
```bash
# Simulates trades without execution
export DRY_RUN=true
python src/core/execution_engine.py
```

**Live Trading (After Testing):**
```bash
# ⚠️ REAL MONEY - Complete pre-live checklist first!
export TRADING_MODE=live
export ALPACA_BASE_URL=https://api.alpaca.markets
export DRY_RUN=false

python src/core/execution_engine.py
```

### Scheduled Execution

**Using Cron (Linux/Mac):**
```bash
# Edit crontab
crontab -e

# Add line (runs at 4:15 PM ET weekdays)
15 16 * * 1-5 cd /path/to/investor-mimic-bot && python src/core/execution_engine.py >> logs/cron.log 2>&1
```

**Using Task Scheduler (Windows):**
- Create task to run `python src/core/execution_engine.py`
- Schedule for 4:15 PM ET weekdays
- Set working directory to project root

---

## Configuration (NEW)

### Central Configuration File

**All parameters now in:** `config/trading_config.yaml`

**Structure:**
```yaml
risk:
  max_portfolio_heat: 0.30          # Maximum portfolio exposure
  max_daily_loss_pct: 0.02          # Daily loss circuit breaker
  correlation_threshold: 0.70        # Reject correlated positions
  correlation_window: 60             # Days for correlation calculation
  drawdown_halt_threshold: 0.08     # 8% drawdown halts trading
  drawdown_panic_threshold: 0.10    # 10% drawdown flattens all

position_sizing:
  base_risk_per_trade: 0.01         # 1% portfolio risk per trade
  max_position_pct: 0.10            # Max 10% in single position
  atr_multiplier: 2.5               # Stop loss distance

execution:
  execution_time: "16:15"           # 4:15 PM ET
  order_type: "market"              # Market orders
  slippage_pct: 0.0005             # 0.05% slippage

strategies:
  rsi_mean_reversion:
    enabled: true
    allocation: 0.20                # 20% of portfolio
    rsi_period: 14
    rsi_oversold: 30
    rsi_overbought: 70
    
  ma_crossover:
    enabled: true
    allocation: 0.20
    fast_ma: 20
    slow_ma: 50
    volume_confirmation: true
    
  ml_momentum:
    enabled: true
    allocation: 0.20
    lookback_days: 60
    min_confidence: 0.60
    
  volatility_breakout:
    enabled: true
    allocation: 0.20
    atr_period: 14
    breakout_multiplier: 2.0
```

### How to Change Parameters

**Example: Adjust RSI Threshold**

1. Open config file:
```bash
nano config/trading_config.yaml
```

2. Find and edit:
```yaml
strategies:
  rsi_mean_reversion:
    rsi_oversold: 35  # Changed from 30
```

3. Save and restart system:
```bash
python src/core/execution_engine.py
```

**That's it!** No code changes needed.

### Common Adjustments

**More Conservative (Lower Risk):**
```yaml
risk:
  max_portfolio_heat: 0.20          # From 0.30
  max_daily_loss_pct: 0.01          # From 0.02
  correlation_threshold: 0.60        # From 0.70
```

**More Aggressive (Higher Risk):**
```yaml
risk:
  max_portfolio_heat: 0.40          # From 0.30
  max_daily_loss_pct: 0.03          # From 0.02
  correlation_threshold: 0.80        # From 0.70
```

**Disable a Strategy:**
```yaml
strategies:
  ml_momentum:
    enabled: false                   # Disables ML Momentum
```

---

## Monitoring Dashboard (NEW)

### Launch Dashboard

```bash
# Install dashboard dependencies (if not already)
pip install streamlit plotly

# Launch dashboard
cd dashboard
streamlit run app.py

# Or use the provided script
./run.sh
```

**Access:** http://localhost:8501

### Dashboard Features

**1. Portfolio Overview**
- Current portfolio value
- Total P&L (daily, weekly, monthly)
- Current drawdown percentage
- Portfolio heat (exposure)

**2. Open Positions**
- All current positions
- Entry price vs current price
- Unrealized P&L per position
- Days held
- Strategy attribution

**3. Recent Trades**
- Last 20 trades
- Entry/exit details
- Realized P&L
- Win/loss indicator
- Strategy that generated trade

**4. Strategy Performance**
- Per-strategy metrics
- Win rate, profit factor
- Sharpe ratio
- Number of trades
- Average P&L per trade

**5. Risk Metrics**
- Portfolio heat over time
- Drawdown history
- Correlation matrix
- Daily loss tracking

**6. Equity Curve**
- Interactive Plotly chart
- Portfolio value over time
- Drawdown visualization
- Benchmark comparison (optional)

### Auto-Refresh

Dashboard automatically refreshes every 60 seconds to show latest data from database.

---

## Daily Operations

### Pre-Market Routine (11 minutes)

**1. System Health Check (5 min)**
```bash
# Check logs for errors
tail -100 logs/trading_system.log
grep -i "error\|exception" logs/trading_system.log | tail -20

# Verify system completed last run
ps aux | grep python | grep trading
```

**2. Broker Reconciliation (2 min)**
```bash
# Run reconciliation
python src/risk/broker_reconciler.py

# Expected: "✅ Reconciliation PASSED"
```

**3. Circuit Breaker Check (1 min)**
```bash
# Open dashboard and check for alerts
# Or query database:
python -c "from src.core.database import TradingDatabase; \
db = TradingDatabase('trading.db'); \
cursor = db.conn.execute('SELECT * FROM circuit_breaker_status ORDER BY timestamp DESC LIMIT 1'); \
print(cursor.fetchone())"
```

**4. Position Review (2 min)**
```bash
# Open dashboard → "Open Positions" tab
# Or query:
python -c "from src.core.database import TradingDatabase; \
import pandas as pd; \
db = TradingDatabase('trading.db'); \
positions = pd.read_sql('SELECT * FROM positions WHERE exit_date IS NULL', db.conn); \
print(positions[['symbol', 'shares', 'entry_price', 'strategy_id']])"
```

**5. Cash Balance (1 min)**
```bash
# Check Alpaca dashboard
# Or via API:
python -c "from alpaca.trading.client import TradingClient; \
import os; \
client = TradingClient(os.getenv('ALPACA_API_KEY'), os.getenv('ALPACA_SECRET_KEY')); \
account = client.get_account(); \
print(f'Cash: ${float(account.cash):.2f}'); \
print(f'Portfolio Value: ${float(account.portfolio_value):.2f}')"
```

### Post-Market Routine (18 minutes)

**1. Trade Review (5 min)**
```bash
# Open dashboard → "Recent Trades" tab
# Verify all intended trades executed
```

**2. Artifact Review (3 min)**
```bash
# View today's artifact
cat artifacts/daily_report_$(date +%Y%m%d).json | python -m json.tool | head -50
```

**3. P&L Verification (2 min)**
```bash
# Dashboard P&L vs Alpaca dashboard
# Should match within $10
```

**4. Strategy Performance (3 min)**
```bash
# Dashboard → "Strategy Performance" tab
# Check for any strategy with consistent losses
```

**5. Drawdown Monitoring (2 min)**
```bash
# Dashboard → "Risk Metrics" tab
# Alert if drawdown > 5%
```

**6. Rejected Signals (3 min)**
```bash
# Check why signals were rejected
python -c "from src.core.database import TradingDatabase; \
import pandas as pd; \
from datetime import datetime; \
db = TradingDatabase('trading.db'); \
today = datetime.now().strftime('%Y-%m-%d'); \
rejected = pd.read_sql(f\"SELECT terminal_state, COUNT(*) as count FROM signals WHERE asof_date = '{today}' AND terminal_state != 'executed' GROUP BY terminal_state\", db.conn); \
print(rejected)"
```

---

## Adjusting Parameters

### Risk Parameters

**Increase/Decrease Portfolio Heat:**
```yaml
# config/trading_config.yaml
risk:
  max_portfolio_heat: 0.35  # Increased from 0.30
```

**Adjust Daily Loss Limit:**
```yaml
risk:
  max_daily_loss_pct: 0.015  # Decreased from 0.02 (more conservative)
```

**Change Correlation Threshold:**
```yaml
risk:
  correlation_threshold: 0.75  # Increased from 0.70 (less strict)
```

### Strategy Parameters

**Adjust RSI Strategy:**
```yaml
strategies:
  rsi_mean_reversion:
    rsi_oversold: 35        # Less aggressive entry
    rsi_overbought: 65      # Earlier exit
```

**Adjust MA Crossover:**
```yaml
strategies:
  ma_crossover:
    fast_ma: 10             # Faster signals
    slow_ma: 30             # Faster signals
```

**Adjust ML Momentum:**
```yaml
strategies:
  ml_momentum:
    min_confidence: 0.65    # Higher confidence required
```

### Position Sizing

**Increase Position Sizes:**
```yaml
position_sizing:
  base_risk_per_trade: 0.015  # From 0.01 (1.5% risk per trade)
  max_position_pct: 0.15      # From 0.10 (15% max position)
```

**After Changing Config:**
1. Save `config/trading_config.yaml`
2. Restart system: `python src/core/execution_engine.py`
3. Verify changes: `python -c "from src.utils.config_loader import get_config; c = get_config(); print(c.get('risk.max_portfolio_heat'))"`

---

## Emergency Procedures

### 8% Drawdown Hit (Halt Mode)

**What Happens:**
- System automatically halts new entries
- Existing positions remain open
- 10-day cooldown period begins
- Email alert sent

**Your Actions:**
1. Review cause of drawdown (market crash? strategy failure?)
2. Check dashboard for losing positions
3. Monitor for 10 trading days
4. System auto-resumes after cooldown if conditions met

**Manual Resume (if needed):**
```bash
python -c "from src.risk.drawdown_stop_manager import DrawdownStopManager; \
from src.core.database import TradingDatabase; \
db = TradingDatabase('trading.db'); \
mgr = DrawdownStopManager(db, None); \
mgr.force_resume()"
```

### 10% Drawdown Hit (PANIC MODE)

**What Happens:**
- System automatically flattens ALL positions
- Trading halted completely
- 20-day cooldown period begins
- Email alert sent (CRITICAL)

**Your Actions:**
1. **DO NOT PANIC** - System protected your capital
2. Full system audit required
3. Review all strategies, risk controls, data quality
4. Determine root cause before resuming
5. Consider reducing risk parameters before resuming

**Manual Resume (only after fixes):**
```bash
# Only after thorough investigation and fixes
python -c "from src.risk.drawdown_stop_manager import DrawdownStopManager; \
from src.core.database import TradingDatabase; \
db = TradingDatabase('trading.db'); \
mgr = DrawdownStopManager(db, None); \
mgr.force_resume()"
```

### Reconciliation Failure

**What Happens:**
- Trading paused immediately
- Email alert sent
- Discrepancy between database and broker

**Your Actions:**
1. Run verbose reconciliation:
```bash
python src/risk/broker_reconciler.py --verbose
```

2. Compare positions:
```bash
# Database positions
sqlite3 trading.db "SELECT * FROM positions WHERE exit_date IS NULL"

# Alpaca positions (check dashboard)
```

3. Identify discrepancy:
   - Manual trade placed outside system?
   - System error during execution?
   - Database corruption?

4. Fix issue (update database or fix system)

5. Force resume:
```bash
python -c "from src.risk.broker_reconciler import BrokerReconciler; \
from src.core.database import TradingDatabase; \
db = TradingDatabase('trading.db'); \
rec = BrokerReconciler(db, None); \
rec.force_resume()"
```

### Emergency Flatten All Positions

**If you need to exit everything immediately:**
```bash
python -c "from alpaca.trading.client import TradingClient; \
import os; \
client = TradingClient(os.getenv('ALPACA_API_KEY'), os.getenv('ALPACA_SECRET_KEY')); \
client.close_all_positions(cancel_orders=True); \
print('✅ All positions closed')"
```

---

## Common Tasks

### View Current Positions

**Via Dashboard:**
- Open dashboard → "Open Positions" tab

**Via Command Line:**
```bash
python -c "from src.core.database import TradingDatabase; \
import pandas as pd; \
db = TradingDatabase('trading.db'); \
positions = pd.read_sql('SELECT * FROM positions WHERE exit_date IS NULL', db.conn); \
print(positions)"
```

### View Recent Trades

**Via Dashboard:**
- Open dashboard → "Recent Trades" tab

**Via Command Line:**
```bash
python -c "from src.core.database import TradingDatabase; \
import pandas as pd; \
db = TradingDatabase('trading.db'); \
trades = pd.read_sql('SELECT * FROM trades ORDER BY entry_date DESC LIMIT 20', db.conn); \
print(trades[['symbol', 'action', 'shares', 'price', 'pnl']])"
```

### Check Portfolio Value

**Via Dashboard:**
- Open dashboard → "Portfolio Overview"

**Via Command Line:**
```bash
python -c "from alpaca.trading.client import TradingClient; \
import os; \
client = TradingClient(os.getenv('ALPACA_API_KEY'), os.getenv('ALPACA_SECRET_KEY')); \
account = client.get_account(); \
print(f'Portfolio Value: ${float(account.portfolio_value):.2f}'); \
print(f'P&L Today: ${float(account.todays_return):.2f}')"
```

### Calculate Current Drawdown

**Via Dashboard:**
- Open dashboard → "Risk Metrics" → Drawdown chart

**Via Command Line:**
```bash
python -c "from src.core.database import TradingDatabase; \
db = TradingDatabase('trading.db'); \
cursor = db.conn.execute('SELECT portfolio_value FROM performance_metrics ORDER BY date DESC LIMIT 1'); \
current = cursor.fetchone()[0]; \
cursor = db.conn.execute('SELECT MAX(portfolio_value) FROM performance_metrics'); \
peak = cursor.fetchone()[0]; \
drawdown = (peak - current) / peak; \
print(f'Current Drawdown: {drawdown:.2%}'); \
print(f'Peak: ${peak:.2f}, Current: ${current:.2f}')"
```

### Backup Database

```bash
# Create backup
cp trading.db backups/trading_$(date +%Y%m%d).db

# Verify backup
sqlite3 backups/trading_$(date +%Y%m%d).db "PRAGMA integrity_check;"
```

### Restore from Backup

```bash
# Restore database
cp backups/trading_20260115.db trading.db

# Verify integrity
sqlite3 trading.db "PRAGMA integrity_check;"
```

### Run Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_risk_management.py -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html
```

### Update Data

```bash
# If using Alpha Vantage or other data source
python scripts/update_data.py

# Or implement your own data update script
```

---

## Troubleshooting

### System Not Starting

**Check imports:**
```bash
python -c "from src.core.execution_engine import MultiStrategyRunner; print('✅ OK')"
```

**Check config:**
```bash
python -c "from src.utils.config_loader import get_config; c = get_config(); print('✅ Config OK')"
```

**Check logs:**
```bash
tail -100 logs/trading_system.log
```

### No Trades Executing

**Check signal funnel:**
```bash
# Open dashboard and review rejected signals
# Or check database for rejection reasons
```

**Common causes:**
- All signals rejected by correlation filter
- Portfolio heat limit reached
- Daily loss limit triggered
- Circuit breaker active

**Solutions:**
- Adjust correlation threshold in config
- Increase portfolio heat limit (carefully)
- Wait for cooldown period to expire

### Dashboard Not Loading

**Check if Streamlit installed:**
```bash
pip install streamlit plotly pandas
```

**Launch with verbose output:**
```bash
cd dashboard
streamlit run app.py --logger.level=debug
```

**Check database exists:**
```bash
ls -lh trading.db
```

---

## Best Practices

### Before Going Live

1. ✅ Complete pre-live checklist (`docs/guides/PRE_LIVE_CHECKLIST.md`)
2. ✅ Paper trade for 2+ weeks
3. ✅ Review all config parameters
4. ✅ Test emergency procedures
5. ✅ Verify monitoring works
6. ✅ Set up email alerts
7. ✅ Understand all risk controls

### Daily Discipline

1. ✅ Follow pre-market routine (11 min)
2. ✅ Follow post-market routine (18 min)
3. ✅ Review dashboard daily
4. ✅ Check for email alerts
5. ✅ Monitor drawdown

### Weekly Review

1. ✅ Strategy performance review
2. ✅ Risk metrics review
3. ✅ Rejected signals analysis
4. ✅ Data quality check

### Monthly Review

1. ✅ Full backtest refresh
2. ✅ Parameter review (if needed)
3. ✅ Database maintenance
4. ✅ Dependency updates

---

## Quick Reference

### Key Files

- **Config:** `config/trading_config.yaml`
- **Main Script:** `src/core/execution_engine.py`
- **Dashboard:** `dashboard/app.py`
- **Database:** `trading.db`
- **Logs:** `logs/trading_system.log`
- **Artifacts:** `artifacts/daily_report_*.json`

### Key Commands

```bash
# Run system
python src/core/execution_engine.py

# Launch dashboard
cd dashboard && streamlit run app.py

# Run reconciliation
python src/risk/broker_reconciler.py

# Run tests
pytest tests/ -v

# Backup database
cp trading.db backups/trading_$(date +%Y%m%d).db
```

### Key Metrics

- **Portfolio Heat:** Current exposure / Portfolio value (target: <30%)
- **Drawdown:** (Peak - Current) / Peak (alert: >5%, halt: >8%, panic: >10%)
- **Daily Loss:** Today's P&L / Starting value (limit: -2%)
- **Correlation:** Between positions (reject: >0.70)

---

## Getting Help

### Documentation

- **Pre-Live Checklist:** `docs/guides/PRE_LIVE_CHECKLIST.md`
- **System Architecture:** `docs/reference/SYSTEM_ARCHITECTURE.md`
- **Operational Procedures:** `docs/guides/OPERATIONAL_PROCEDURES.md`
- **Full Usage Guide:** `docs/guides/USAGE_GUIDE.md`

### Support

- Check logs: `logs/trading_system.log`
- Review dashboard for issues
- Consult operational procedures for emergencies
- Test in paper trading first

---

**Remember:** This is real money. Monitor daily, follow procedures, never skip the pre-live checklist. When in doubt, halt trading and investigate.
