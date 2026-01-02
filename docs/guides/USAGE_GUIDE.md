# Usage Guide - Multi-Strategy Trading System

**Last Updated:** January 1, 2026

Complete guide to using all features of the trading system.

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Running the System](#running-the-system)
3. [Configuration](#configuration)
4. [Monitoring & Alerts](#monitoring--alerts)
5. [Database Operations](#database-operations)
6. [Production Features](#production-features)
7. [Troubleshooting](#troubleshooting)

---

## Getting Started

### Prerequisites

1. **GitHub Account** - For GitHub Actions automation
2. **Alpaca Account** - Free paper trading account at [alpaca.markets](https://alpaca.markets)
3. **Alpha Vantage API Key** - Free tier at [alphavantage.co](https://www.alphavantage.co)
4. **Gmail Account** (Optional) - For email notifications

### Initial Setup

**1. Configure GitHub Secrets**

Go to: Repository → Settings → Secrets and variables → Actions

Add the following secrets:

| Secret Name | Description | Required |
|-------------|-------------|----------|
| `ALPACA_API_KEY` | Your Alpaca API key | ✅ Yes |
| `ALPACA_SECRET_KEY` | Your Alpaca secret key | ✅ Yes |
| `ALPHA_VANTAGE_API_KEY` | Data API key | ✅ Yes |
| `EMAIL_USERNAME` | Gmail address | ⚠️ Optional |
| `EMAIL_PASSWORD` | Gmail app password | ⚠️ Optional |
| `EMAIL_TO` | Recipient email | ⚠️ Optional |

**2. Push Code to GitHub**

```bash
git add .
git commit -m "Initial setup"
git push origin main
```

**3. Verify Workflow**

- Go to **Actions** tab
- See "Daily Paper Trading" workflow
- Click **Run workflow** to test manually

---

## Running the System

### Automated Execution (Production)

**Schedule:** Runs automatically at 6:30 AM PST weekdays

The GitHub Actions workflow handles everything:
- Fetches market data
- Runs all strategies
- Executes trades
- Sends email digest
- Uploads artifacts

**No manual intervention required.**

### Manual Execution

**Via GitHub Actions:**
1. Go to **Actions** tab
2. Click **Daily Paper Trading**
3. Click **Run workflow**
4. Select branch (usually `main`)
5. Click **Run workflow** button

**Locally (for testing):**

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export ALPACA_API_KEY="your_key"
export ALPACA_SECRET_KEY="your_secret"
export ALPACA_PAPER=true

# Run system
python src/execution_engine.py
```

### Using Makefile Commands

```bash
# Update market data
make update-data

# Run trading system
make run

# View positions
make positions

# Check broker state
make check-broker

# Sync database with broker
make sync-db

# Validate system
make validate

# Run tests
make test

# View logs
make logs

# Clean artifacts
make clean
```

---

## Configuration

### Environment Variables

**Trading Controls:**

```bash
# Global kill switch
TRADING_DISABLED=false

# Disable specific strategies (comma-separated)
STRATEGY_DISABLED_LIST=

# Example: Disable ML Momentum and News Sentiment
STRATEGY_DISABLED_LIST="ML Momentum,News Sentiment"
```

**Universe Configuration:**

```bash
# Universe mode: static, csv, or dynamic
UNIVERSE_MODE=static

# Path to CSV file (if using csv mode)
UNIVERSE_CSV_PATH=config/universe.csv
```

**Risk Parameters:**

```bash
# Maximum portfolio exposure (0.0 to 1.0)
MAX_PORTFOLIO_HEAT=0.30

# Daily loss circuit breaker (0.0 to 0.10)
MAX_DAILY_LOSS_PCT=0.02

# Correlation threshold (0.0 to 1.0)
MAX_CORRELATION=0.7
```

**Data Validation:**

```bash
# Maximum data age in hours
DATA_MAX_AGE_HOURS=24

# Auto-update data if stale
AUTO_UPDATE_DATA=false
```

**Reconciliation:**

```bash
# Enable broker reconciliation (mandatory gate)
ENABLE_BROKER_RECONCILIATION=true

# Reconciliation tolerance percentage
RECONCILIATION_TOLERANCE_PCT=0.01
```

**Logging:**

```bash
# Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL=INFO

# Enable structured JSON logging
STRUCTURED_LOGGING=false
```

### Expanding Universe

**Option 1: Use CSV Mode**

1. Create/edit `config/universe.csv`:
```csv
symbol,sector,market_cap
AAPL,Technology,Large
MSFT,Technology,Large
GOOGL,Technology,Large
...
```

2. Set environment variable:
```bash
UNIVERSE_MODE=csv
```

3. System will load symbols from CSV

**Option 2: Modify Static Universe**

Edit `src/universe_provider.py`:
```python
DEFAULT_UNIVERSE = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META',
    # Add your symbols here
]
```

---

## Monitoring & Alerts

### Daily Email Digest

**Sections Included:**

1. **Signal Funnel Analysis**
   - Table showing signal counts through each stage
   - Per-strategy breakdown: raw → regime → correlation → risk → executed

2. **"Why No Trade?" Report**
   - Explains top blockers if no trades executed
   - Shows example symbols and rejection reasons

3. **Trade Summary**
   - All executed trades with details
   - Buy/sell counts and totals

4. **Portfolio Metrics**
   - Current value, cash, buying power
   - Portfolio heat percentage
   - Daily P&L

5. **Strategy Performance**
   - Per-strategy metrics
   - Win rate, profit factor, trade counts

6. **Current Positions**
   - All open positions
   - Entry price, current price, unrealized P&L

### Critical Alerts

**Automatic email alerts sent for:**

- **Reconciliation Failure** - Broker/DB mismatch, trading blocked
- **Kill Switch Activation** - Manual or automatic halt
- **Excessive Drawdown** - Daily loss >15%
- **No Trades** - No trades for >7 days
- **Database Issues** - Integrity problems

### Viewing Logs

**GitHub Actions Logs:**
1. Go to **Actions** tab
2. Click on workflow run
3. Click **Execute Daily Paper Trading**
4. Expand **Run Paper Trading Strategy**

**Download Logs:**
1. Scroll to bottom of workflow run
2. Under **Artifacts**, download `trading-logs-XXX`

**Structured Event Logs:**

If `STRUCTURED_LOGGING=true`, JSON logs saved to:
```
logs/events/events_{run_id}.jsonl
```

Each line is a JSON object:
```json
{
  "timestamp": "2026-01-01T14:30:00",
  "run_id": "20260101_143000",
  "event_type": "SIGNAL_GENERATED",
  "strategy_id": 1,
  "symbol": "AAPL",
  "stage": "GENERATION",
  "data": {
    "action": "BUY",
    "confidence": 0.75,
    "reasoning": "RSI < 30 and turning upward"
  }
}
```

---

## Database Operations

### Accessing Database

**Download from GitHub Actions:**
```bash
# Get latest run ID
gh run list --workflow=daily_trading.yml --limit 1

# Download database
gh run download <run_id> --name trading-database

# Extract
unzip trading-database.zip
```

**Query Database:**
```bash
# Open SQLite shell
sqlite3 trading.db

# Or use Python
python -c "import sqlite3; conn = sqlite3.connect('trading.db'); cursor = conn.cursor(); cursor.execute('SELECT * FROM strategies'); print(cursor.fetchall())"
```

### Common Queries

**View Signal Funnel:**
```sql
SELECT 
    strategy_name,
    raw_signals_count as raw,
    after_regime_count as regime,
    after_correlation_count as correlation,
    after_risk_count as risk,
    executed_count as executed
FROM signal_funnel
WHERE run_id = (SELECT run_id FROM signal_funnel ORDER BY created_at DESC LIMIT 1)
ORDER BY strategy_id;
```

**View Signal Rejections:**
```sql
SELECT 
    stage,
    reason_code,
    COUNT(*) as count,
    GROUP_CONCAT(symbol, ', ') as symbols
FROM signal_rejections
WHERE run_id = (SELECT run_id FROM signal_rejections ORDER BY created_at DESC LIMIT 1)
GROUP BY stage, reason_code
ORDER BY count DESC;
```

**View Recent Trades:**
```sql
SELECT 
    executed_at,
    symbol,
    action,
    shares,
    exec_price,
    total_cost
FROM trades
ORDER BY executed_at DESC
LIMIT 10;
```

**View Order Intents:**
```sql
SELECT 
    intent_id,
    symbol,
    side,
    target_qty,
    status,
    broker_order_id
FROM order_intents
WHERE run_id = (SELECT run_id FROM order_intents ORDER BY created_at DESC LIMIT 1)
ORDER BY created_at DESC;
```

**Check for Duplicate Intents:**
```sql
SELECT 
    intent_id,
    COUNT(*) as count
FROM order_intents
GROUP BY intent_id
HAVING count > 1;
```

### Database Maintenance

**Backup Database:**
```bash
cp trading.db trading.db.backup.$(date +%Y%m%d)
```

**Vacuum Database:**
```bash
sqlite3 trading.db "VACUUM;"
```

**Check Integrity:**
```bash
sqlite3 trading.db "PRAGMA integrity_check;"
```

---

## Production Features

### Kill Switches

**Manual Kill Switch:**

```bash
# Halt all trading
export TRADING_DISABLED=true

# Or add to GitHub Secrets
# Name: TRADING_DISABLED
# Value: true
```

**Disable Specific Strategies:**

```bash
# Disable one strategy
export STRATEGY_DISABLED_LIST="ML Momentum"

# Disable multiple strategies
export STRATEGY_DISABLED_LIST="ML Momentum,News Sentiment"
```

**Check Kill Switch Status:**

```python
from src.kill_switch_service import KillSwitchService
from src.database import TradingDatabase
from src.email_notifier import EmailNotifier

db = TradingDatabase()
notifier = EmailNotifier()
kill_switch = KillSwitchService(db, notifier)

status = kill_switch.get_status()
print(f"Is killed: {status['is_killed']}")
print(f"Reasons: {status['kill_reasons']}")
print(f"Disabled strategies: {status['disabled_strategies']}")
```

**Automatic Kill Conditions:**

System automatically halts trading when:
- Reconciliation fails (broker/DB mismatch)
- Daily drawdown exceeds 5%
- 3+ consecutive run failures
- Order rejection rate >50% with ≥5 rejected orders

### Signal Funnel Tracking

**View Funnel in Email:**

Daily email includes funnel table:
```
Strategy              Raw  Regime  Correlation  Risk  Executed
RSI Mean Reversion    12   9       4            2     1
ML Momentum           8    8       5            3     2
```

**Query Funnel Data:**

```python
from src.database import TradingDatabase

db = TradingDatabase(run_id='20260101_143000')

# Get funnel summary
funnel = db.get_signal_funnel_summary()
for row in funnel:
    print(f"{row['strategy_name']}: {row['raw_signals_count']} → {row['executed_count']}")

# Get rejection summary
rejections = db.get_signal_rejections_summary(limit=10)
for row in rejections:
    print(f"{row['stage']} - {row['reason_code']}: {row['count']} signals")
    print(f"  Symbols: {row['symbols']}")
```

### Idempotent Order Placement

**How It Works:**

1. System generates deterministic `intent_id` for each order:
   ```
   intent_id = hash(run_id + strategy_id + symbol + side + qty + hour_bucket)
   ```

2. Before submitting order, checks if intent already exists
3. If intent status is SUBMITTED/ACKED/FILLED, skips order
4. Prevents duplicate orders on GitHub Actions retries

**Check Order Intents:**

```python
from src.database import TradingDatabase

db = TradingDatabase()

# Check for duplicate intent
intent_id = db.check_duplicate_order_intent(
    strategy_id=1,
    symbol='AAPL',
    side='BUY',
    target_qty=10
)

if intent_id:
    print(f"Order intent already exists: {intent_id}")
    intent = db.get_order_intent_by_id(intent_id)
    print(f"Status: {intent['status']}")
```

### Reconciliation Gate

**How It Works:**

1. Before trading, system compares:
   - Local DB positions vs Alpaca positions
   - Local cash balance vs Alpaca cash

2. If mismatch exceeds 1% tolerance:
   - Trading is blocked
   - Critical alert email sent
   - Discrepancies logged

3. Trading only proceeds if reconciliation passes

**Manual Reconciliation:**

```bash
# Check broker state
python scripts/check_broker_state.py

# Sync database with broker (overwrites DB)
python scripts/sync_database.py --force

# Verify reconciliation
python scripts/verify_execution.py
```

**View Reconciliation History:**

```sql
SELECT 
    snapshot_date,
    snapshot_type,
    reconciliation_status,
    cash,
    portfolio_value
FROM broker_state
ORDER BY created_at DESC
LIMIT 10;
```

### Correlation Attenuation

**How It Works:**

Instead of binary rejection at 0.7 correlation:
- corr ≤ 0.5: 100% size (no attenuation)
- 0.5 < corr ≤ 0.8: Linear scale 100% → 25%
- corr > 0.8: Reject (0% size)

**Example:**
- Signal for MSFT with 0.6 correlation to existing AAPL position
- Size multiplier: 0.8 (80% of normal size)
- If normal size is 100 shares, executes 80 shares

**Check Correlation:**

```python
from src.correlation_filter import CorrelationFilter

corr_filter = CorrelationFilter()

# Calculate size multiplier
multiplier, reason = corr_filter.calculate_size_multiplier(correlation=0.65)
print(f"Multiplier: {multiplier:.2f} ({reason})")
# Output: Multiplier: 0.67 (attenuated_correlation_0.65)
```

### Pending Signals

**How It Works:**

1. Signal blocked by correlation/risk today
2. System persists signal to `pending_signals` table
3. Re-evaluates signal for next 3 days
4. If positions change and signal becomes valid, executes
5. Expires after 3 days

**View Pending Signals:**

```python
from src.pending_signals_manager import PendingSignalsManager
from src.database import TradingDatabase

db = TradingDatabase()
pending_mgr = PendingSignalsManager(db, decay_days=3)

# Get all pending signals
pending = pending_mgr.get_pending_signals()
for sig in pending:
    print(f"{sig['symbol']}: Blocked by {sig['blocked_reason']}")
    print(f"  Expires: {sig['expires_at']}")
    print(f"  Retry count: {sig['retry_count']}")

# Cleanup expired
pending_mgr.cleanup_expired()
```

---

## Troubleshooting

### No Trades Executing

**Diagnosis:**

1. Check signal funnel in email or database
2. Identify which stage is blocking signals

**Common Issues:**

**No Raw Signals:**
- Market conditions don't meet strategy criteria
- Check if market was open (holidays)
- Verify data is up-to-date

**Blocked by Regime:**
- Strategy disabled for current market regime
- Check VIX level and regime thresholds

**Blocked by Correlation:**
- All signals too correlated with existing positions
- Consider expanding universe or relaxing threshold

**Blocked by Risk/Cash:**
- Portfolio heat limit reached (30%)
- Insufficient cash available
- Daily loss limit triggered (-2%)

**Solutions:**

```bash
# Expand universe
UNIVERSE_MODE=csv  # Use 150+ symbols

# Relax correlation threshold
MAX_CORRELATION=0.75  # From 0.7

# Increase heat limit (carefully)
MAX_PORTFOLIO_HEAT=0.35  # From 0.30
```

### Reconciliation Failures

**Symptoms:**
- Email alert: "Reconciliation Failure - Trading Blocked"
- No trades executed

**Diagnosis:**

```bash
# Check broker state
python scripts/check_broker_state.py

# View discrepancies in database
sqlite3 trading.db "SELECT * FROM broker_state WHERE reconciliation_status='FAIL' ORDER BY created_at DESC LIMIT 1;"
```

**Common Causes:**

1. **Manual trade via Alpaca dashboard** - Position exists in broker but not DB
2. **Position closed outside system** - DB has position, broker doesn't
3. **Partial fills** - Quantity mismatch

**Solutions:**

```bash
# Sync database to broker state (overwrites DB)
python scripts/sync_database.py --force

# Verify sync worked
python scripts/verify_execution.py
```

### GitHub Actions Failures

**Check Workflow Status:**
```bash
gh run list --workflow=daily_trading.yml --limit 5
```

**Common Issues:**

**API Rate Limits:**
- Alpha Vantage: 5 calls/minute
- Solution: Add delays or upgrade API tier

**Missing Secrets:**
- Verify all required secrets are set
- Check secret names match exactly

**Database Corruption:**
- Download and inspect database
- Restore from backup if needed

**Python Errors:**
- Check logs for stack trace
- Verify all dependencies installed

### Kill Switch Activated

**Check Status:**

```bash
# View environment variables
env | grep -E "(TRADING_DISABLED|STRATEGY_DISABLED)"

# Or check GitHub Secrets
```

**Deactivate:**

```bash
# Remove or set to false
export TRADING_DISABLED=false
export STRATEGY_DISABLED_LIST=

# Or update GitHub Secrets
```

### Data Issues

**Stale Data:**

```bash
# Check data age
ls -lh data/training_data.csv

# Update data
make update-data

# Or set auto-update
AUTO_UPDATE_DATA=true
```

**Missing Indicators:**

```bash
# Re-run data update with full indicator calculation
python scripts/update_data.py --force
```

**Data Quality:**

```bash
# Validate data
python scripts/validate_system.py

# Check for missing values
python -c "import pandas as pd; df = pd.read_csv('data/training_data.csv'); print(df.isnull().sum())"
```

---

## Advanced Usage

### Custom Strategies

**Create New Strategy:**

1. Create file in `src/strategies/`:
```python
from strategy_base import StrategyBase

class MyCustomStrategy(StrategyBase):
    def __init__(self, strategy_id, name, capital, universe):
        super().__init__(strategy_id, name, capital, universe)
    
    def generate_signals(self, market_data):
        signals = []
        # Your logic here
        return signals
```

2. Register in `src/execution_engine.py`:
```python
from strategies.my_custom_strategy import MyCustomStrategy

def initialize_strategies(self):
    strategies = [
        # Existing strategies...
        MyCustomStrategy(
            strategy_id=5,
            name="My Custom Strategy",
            capital=self.portfolio_value / 5,
            universe=self.universe
        )
    ]
    return strategies
```

### Custom Risk Rules

**Modify Risk Manager:**

Edit `src/portfolio_risk_manager.py`:
```python
def can_add_position(self, trade_value, current_exposure, portfolio_value):
    # Add custom logic
    if self.is_high_volatility_regime:
        max_heat = 0.20  # More conservative
    else:
        max_heat = self.max_portfolio_heat
    
    new_exposure = current_exposure + trade_value
    return (new_exposure / portfolio_value) <= max_heat
```

### Custom Alerts

**Add Alert Conditions:**

Edit `src/alerting.py`:
```python
def check_custom_condition(self):
    # Your condition
    if some_condition:
        self.send_alert(
            subject="Custom Alert",
            message="Your custom message"
        )
```

---

## Best Practices

### Before Going Live

1. **Paper trade for 2-4 weeks minimum**
2. **Monitor daily emails closely**
3. **Verify funnel tracking shows expected behavior**
4. **Test kill switches work**
5. **Confirm reconciliation catches mismatches**
6. **Review all rejection reasons**
7. **Validate performance matches expectations**

### Regular Maintenance

**Daily:**
- Review email digest
- Check for alerts
- Verify trades executed as expected

**Weekly:**
- Review signal rejection patterns
- Check strategy performance
- Verify data quality

**Monthly:**
- Analyze funnel trends
- Review correlation filter effectiveness
- Audit order intent logs
- Database cleanup (old logs)

### Monitoring Checklist

- [ ] Email received with daily summary
- [ ] Signal funnel shows reasonable counts
- [ ] No kill switch alerts
- [ ] Reconciliation status: PASS
- [ ] Portfolio heat <30%
- [ ] Daily P&L within expected range
- [ ] No duplicate order intents

---

## Getting Help

### Documentation

- **System Overview:** `docs/SYSTEM_OVERVIEW.md`
- **Architecture:** `docs/reference/ARCHITECTURE.md`
- **Runbook:** `docs/guides/RUNBOOK.md`
- **Implementation Guide:** `docs/guides/PRODUCTION_READINESS_IMPLEMENTATION.md`

### Useful Commands

```bash
# View all available commands
make help

# Check system status
make status

# View recent logs
make logs

# Validate system
make validate

# Run tests
make test

# Clean up
make clean
```

### Common SQL Queries

See `docs/guides/RUNBOOK.md` Appendix for comprehensive list of useful SQL commands.

---

**For emergency procedures, see:** `docs/guides/RUNBOOK.md`  
**For technical details, see:** `docs/reference/ARCHITECTURE.md`
