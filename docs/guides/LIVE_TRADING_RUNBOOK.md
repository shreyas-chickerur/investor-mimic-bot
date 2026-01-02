# Live Trading Operations Runbook

**Purpose:** Emergency procedures and operational guidance for $1,000 live capital trading system  
**Last Updated:** January 1, 2026

---

## Table of Contents

1. [Emergency Procedures](#emergency-procedures)
2. [Drawdown Stop System](#drawdown-stop-system)
3. [Kill Switches](#kill-switches)
4. [Data Quality Issues](#data-quality-issues)
5. [Reconciliation Failures](#reconciliation-failures)
6. [Recovery Procedures](#recovery-procedures)
7. [Monitoring & Alerts](#monitoring--alerts)
8. [Configuration Reference](#configuration-reference)

---

## Emergency Procedures

### IMMEDIATE HALT - All Trading

**When to use:** Critical system failure, unexpected behavior, or manual intervention needed.

```bash
# Set global kill switch
export TRADING_DISABLED=true

# Or update GitHub Secret
# Name: TRADING_DISABLED
# Value: true
```

**Effect:** All new entries blocked immediately. Existing positions continue to be managed (exits, stops).

**To Resume:**
```bash
export TRADING_DISABLED=false
```

---

### PANIC BUTTON - Flatten All Positions

**When to use:** 10%+ drawdown or critical market event requiring immediate exit.

**Automatic Trigger:** System automatically triggers at 10% drawdown if `FLATTEN_ON_PANIC=true`

**Manual Trigger:**
1. Set `TRADING_DISABLED=true`
2. Manually close all positions via Alpaca dashboard
3. Wait for cooldown period (20 trading days)
4. Run health checks before resuming

---

## Drawdown Stop System

### Overview

**Purpose:** Protect $1,000 capital from catastrophic losses with automated cooldown/resume protocol.

**Thresholds:**
- **8% Drawdown:** HALT - Block new entries, 10-day cooldown
- **10% Drawdown:** PANIC - Block new entries + flatten positions (optional), 20-day cooldown

### How It Works

```
Normal Trading
    ↓
Portfolio drops 8% from peak
    ↓
HALT STATE TRIGGERED
    ↓
- All new entries blocked
- Existing positions managed normally
- Email alert sent
- 10-day cooldown starts
    ↓
After 10 trading days
    ↓
AUTOMATED HEALTH CHECKS
    ↓
├─ PASS → Enter RAMPUP mode (50% sizing for 5 days)
└─ FAIL → Extend cooldown by 5 days, retry
    ↓
After 5 days of rampup
    ↓
RETURN TO NORMAL (100% sizing)
```

### Checking Current State

```bash
# Query database
sqlite3 trading.db "SELECT value FROM system_state WHERE key='drawdown_stop_state';"

# Or check logs
grep "drawdown" logs/multi_strategy.log
```

**State Values:**
- `NORMAL` - Full trading, 100% sizing
- `HALT` - No new entries, cooldown active
- `PANIC` - No new entries, positions flattened (if enabled)
- `RAMPUP` - New entries allowed, 50% sizing

### Manual Override

**Force Resume (Use with caution):**
```python
from src.database import TradingDatabase
import json

db = TradingDatabase()
state_data = {
    'state': 'NORMAL',
    'drawdown': 0.0,
    'cooldown_days': 0,
    'cooldown_end': None,
    'triggered_at': datetime.now().isoformat(),
    'rampup_end': None
}
db.set_system_state('drawdown_stop_state', json.dumps(state_data))
```

**⚠️ WARNING:** Only override if you understand the risks. System is designed to protect capital.

### Health Checks

**Automated checks before resume:**
1. **Reconciliation:** Last reconciliation status = PASS
2. **Data Quality:** Data updated within 72 hours
3. **No Duplicate Intents:** No duplicate orders in last 24 hours
4. **Strategies Enabled:** At least 1 strategy enabled

**View Health Check Results:**
```bash
ls -lt artifacts/drawdown/health_check_*.json | head -1
cat artifacts/drawdown/health_check_*.json
```

### Configuration

```bash
# Drawdown thresholds
DRAWDOWN_HALT_THRESHOLD=0.08      # 8% (default)
DRAWDOWN_PANIC_THRESHOLD=0.10     # 10% (default)

# Cooldown periods (trading days)
HALT_COOLDOWN_DAYS=10             # Default
PANIC_COOLDOWN_DAYS=20            # Default

# Resume protocol
RAMPUP_SIZING_PCT=0.50            # 50% sizing during rampup
RAMPUP_DAYS=5                     # Days of rampup

# Flatten on panic
FLATTEN_ON_PANIC=true             # Flatten all positions at 10%
```

---

## Kill Switches

### Manual Kill Switches

**Global Disable:**
```bash
TRADING_DISABLED=true
```

**Disable Specific Strategies:**
```bash
STRATEGY_DISABLED_LIST="ML Momentum,News Sentiment"
```

**Check Status:**
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
```

### Automatic Kill Switches

**System automatically halts trading when:**

1. **Reconciliation Failure**
   - Broker positions don't match database
   - Triggers: CRITICAL alert
   - Action: Block all new entries until reconciliation passes

2. **Duplicate Intent Detection**
   - Same order intent created multiple times
   - Triggers: CRITICAL alert
   - Action: Block trading, investigate idempotency issue

3. **Excessive Order Rejections**
   - >50% of orders rejected with ≥5 rejected
   - Triggers: WARNING alert
   - Action: Block trading, review order logic

4. **Consecutive Run Failures**
   - ≥3 consecutive execution failures
   - Triggers: CRITICAL alert
   - Action: Block trading, investigate system issues

**View Kill Switch Log:**
```bash
grep "KILL_SWITCH" logs/events/events_*.jsonl
```

---

## Data Quality Issues

### Stale Data Detection

**Threshold:** Data older than 72 hours (configurable)

**When Detected:**
- Affected symbols blocked from trading
- `DATA_QUALITY` rejection reason logged
- `data_quality_report.json` artifact generated

**Check Data Age:**
```bash
# View latest data quality report
ls -lt artifacts/data_quality/data_quality_report_*.json | head -1
cat artifacts/data_quality/data_quality_report_*.json
```

**Resolution:**
```bash
# Update market data
python scripts/update_data.py

# Or set auto-update
AUTO_UPDATE_DATA=true
```

### Data Quality Issues

**System blocks symbols with:**
- Stale data (>72 hours old)
- Missing required indicators
- Excessive NaN values (>10%)
- Insufficient history (<250 days)
- Price outliers (>50% single-day jump)

**View Blocked Symbols:**
```python
import json

with open('artifacts/data_quality/data_quality_report_latest.json') as f:
    report = json.load(f)

for issue_type, issue_data in report['issues'].items():
    print(f"\n{issue_type}:")
    for symbol_info in issue_data['symbols']:
        print(f"  {symbol_info['symbol']}: {symbol_info['reason']}")
```

### Configuration

```bash
# Staleness threshold (hours)
DATA_STALENESS_HOURS=72

# Quality thresholds
MAX_NAN_PCT=0.10                  # 10% max NaN
MIN_HISTORY_DAYS=250              # For 200-day MA
```

---

## Reconciliation Failures

### What Is Reconciliation?

**Purpose:** Verify database positions match broker positions before every trading session.

**Hard Gate:** Trading is **blocked** if reconciliation fails (mismatch beyond tolerance).

### Common Causes

1. **Manual Trade via Alpaca Dashboard**
   - Position exists in broker but not in database
   - **Fix:** Sync database to broker state

2. **Position Closed Outside System**
   - Database has position, broker doesn't
   - **Fix:** Sync database to broker state

3. **Partial Fills**
   - Quantity mismatch between database and broker
   - **Fix:** Update database with actual filled quantity

4. **Cash Balance Mismatch**
   - Database cash doesn't match broker cash
   - **Fix:** Sync database to broker state

### Resolution Steps

**Step 1: Check Discrepancies**
```bash
# View latest reconciliation
sqlite3 trading.db "SELECT * FROM broker_state WHERE snapshot_type='RECONCILIATION' ORDER BY created_at DESC LIMIT 1;"
```

**Step 2: Sync Database to Broker (Overwrites DB)**
```bash
python scripts/sync_database.py --force
```

**⚠️ WARNING:** This overwrites database with broker state. Any pending signals/intents will be lost.

**Step 3: Verify Sync**
```bash
python scripts/verify_execution.py
```

**Step 4: Resume Trading**

Reconciliation will automatically pass on next run if sync was successful.

### Configuration

```bash
# Reconciliation tolerance
RECONCILIATION_TOLERANCE_PCT=0.01  # 1% tolerance

# Enable/disable (should always be true for live)
ENABLE_BROKER_RECONCILIATION=true
```

---

## Recovery Procedures

### After Drawdown Stop

**Scenario:** System triggered 8% halt, cooldown period complete.

**Steps:**
1. Wait for cooldown period (10 trading days for halt, 20 for panic)
2. System automatically runs health checks
3. If health checks pass:
   - System enters RAMPUP mode (50% sizing)
   - Trade for 5 days at reduced sizing
   - Automatically returns to normal sizing
4. If health checks fail:
   - Cooldown extended by 5 days
   - Review and fix issues
   - Retry health checks

**Manual Health Check:**
```python
from src.drawdown_stop_manager import DrawdownStopManager
from src.database import TradingDatabase
from src.email_notifier import EmailNotifier

db = TradingDatabase()
notifier = EmailNotifier()
manager = DrawdownStopManager(db, notifier)

can_resume, checks = manager._run_health_checks()
print(f"Can resume: {can_resume}")
print(f"Checks: {checks}")
```

### After Kill Switch Activation

**Scenario:** Automatic kill switch triggered (reconciliation, duplicates, etc.)

**Steps:**
1. Identify root cause from logs/alerts
2. Fix underlying issue
3. Clear kill switch condition:
   - Reconciliation: Sync database
   - Duplicates: Investigate idempotency logic
   - Rejections: Review order logic
   - Failures: Fix system errors
4. Verify fix with DRY_RUN mode
5. Resume trading

### After Data Quality Issues

**Scenario:** Symbols blocked due to stale/bad data.

**Steps:**
1. Update market data: `python scripts/update_data.py`
2. Verify data quality: Check `data_quality_report.json`
3. If issues persist:
   - Check Alpha Vantage API status
   - Verify API key/quota
   - Consider alternative data source
4. Resume trading (blocked symbols will be unblocked if data is good)

---

## Monitoring & Alerts

### Daily Monitoring Checklist

**Every Trading Day:**
- [ ] Check email digest received
- [ ] Review signal funnel (any trades executed?)
- [ ] Check drawdown level (current vs peak)
- [ ] Verify reconciliation status (PASS)
- [ ] Review data quality report (any blocked symbols?)
- [ ] Check kill switch status (any active?)
- [ ] Review strategy health scores (any CRITICAL?)

### Weekly Monitoring Checklist

**Every Week:**
- [ ] Review strategy health summary
- [ ] Check artifact directories for anomalies
- [ ] Verify database integrity
- [ ] Review rejection patterns
- [ ] Check for duplicate order intents
- [ ] Analyze "Why No Trade" reports
- [ ] Review drawdown history

### Alert Types

**CRITICAL Alerts (Immediate Action Required):**
- Drawdown ≥8% (HALT triggered)
- Drawdown ≥10% (PANIC triggered)
- Reconciliation failure
- Duplicate order intents detected
- Kill switch activated

**WARNING Alerts (Review Soon):**
- Strategy health score <60
- High rejection rate (>80%)
- No trades for >7 days
- Data quality issues

**INFO Alerts (Informational):**
- Daily digest
- Weekly health summary
- Successful reconciliation
- Normal operations

### Viewing Artifacts

**Signal Funnel:**
```bash
ls -lt artifacts/funnel/signal_funnel_*.json | head -5
cat artifacts/funnel/signal_funnel_*.json | jq .
```

**Signal Rejections:**
```bash
ls -lt artifacts/funnel/signal_rejections_*.json | head -5
cat artifacts/funnel/signal_rejections_*.json | jq .
```

**Why No Trade:**
```bash
ls -lt artifacts/funnel/why_no_trade_summary_*.json | head -5
cat artifacts/funnel/why_no_trade_summary_*.json | jq .
```

**Data Quality:**
```bash
ls -lt artifacts/data_quality/data_quality_report_*.json | head -5
cat artifacts/data_quality/data_quality_report_*.json | jq .
```

**Drawdown Events:**
```bash
ls -lt artifacts/drawdown/*.json
cat artifacts/drawdown/halt_*.json | jq .
```

**Strategy Health:**
```bash
ls -lt artifacts/health/strategy_health_summary_*.json | head -5
cat artifacts/health/strategy_health_summary_*.json | jq .
```

---

## Configuration Reference

### Environment Variables

**Trading Controls:**
```bash
TRADING_DISABLED=false                    # Global kill switch
STRATEGY_DISABLED_LIST=                   # Comma-separated strategy names
DRY_RUN=false                            # Safe mode (no broker writes)
```

**Drawdown Stop:**
```bash
DRAWDOWN_HALT_THRESHOLD=0.08             # 8% halt threshold
DRAWDOWN_PANIC_THRESHOLD=0.10            # 10% panic threshold
HALT_COOLDOWN_DAYS=10                    # Halt cooldown period
PANIC_COOLDOWN_DAYS=20                   # Panic cooldown period
RAMPUP_SIZING_PCT=0.50                   # 50% sizing during rampup
RAMPUP_DAYS=5                            # Rampup duration
FLATTEN_ON_PANIC=true                    # Flatten positions at 10%
```

**Data Quality:**
```bash
DATA_STALENESS_HOURS=72                  # Stale data threshold
MAX_NAN_PCT=0.10                         # Max NaN percentage
MIN_HISTORY_DAYS=250                     # Min history required
```

**Risk Management:**
```bash
MAX_PORTFOLIO_HEAT=0.30                  # 30% max exposure
MAX_DAILY_LOSS_PCT=0.02                  # 2% daily loss limit
MAX_CORRELATION=0.7                      # Correlation threshold
```

**Reconciliation:**
```bash
ENABLE_BROKER_RECONCILIATION=true        # Mandatory gate
RECONCILIATION_TOLERANCE_PCT=0.01        # 1% tolerance
```

**Health Scoring:**
```bash
HEALTH_SHORT_WINDOW=7                    # 7-day window
HEALTH_LONG_WINDOW=30                    # 30-day window
MIN_TRADES_FOR_HEALTH=5                  # Min trades for scoring
MAX_REJECTION_RATE=0.80                  # 80% max rejection rate
MIN_EXPECTANCY=0.0                       # Break-even minimum
```

---

## Common Scenarios

### Scenario 1: System Halted at 8% Drawdown

**What Happened:**
- Portfolio dropped from $1,000 to $920 (8% drawdown)
- System automatically triggered HALT state
- Email alert sent
- 10-day cooldown started

**What To Do:**
1. **Review why drawdown occurred:**
   - Check recent trades
   - Review market conditions
   - Analyze strategy performance
2. **Wait for cooldown (10 trading days)**
3. **System will automatically:**
   - Run health checks after cooldown
   - Resume at 50% sizing if checks pass
   - Return to normal after 5 days
4. **Monitor closely during rampup**

**What NOT To Do:**
- Don't manually override unless absolutely necessary
- Don't panic and close all positions (unless 10% reached)
- Don't disable drawdown stop system

### Scenario 2: No Trades for 7 Days

**What Happened:**
- System running normally
- No trades executed for 7+ days
- Email alert received

**What To Do:**
1. **Check signal funnel artifacts:**
   ```bash
   cat artifacts/funnel/why_no_trade_summary_*.json
   ```
2. **Identify blocker:**
   - No raw signals? Check strategy logic
   - Regime filter? Check VIX levels
   - Correlation filter? Check existing positions
   - Risk limits? Check portfolio heat
3. **Review data quality:**
   ```bash
   cat artifacts/data_quality/data_quality_report_*.json
   ```
4. **Consider adjustments:**
   - Expand universe (CSV mode)
   - Relax correlation threshold (carefully)
   - Review strategy parameters

### Scenario 3: Reconciliation Failure

**What Happened:**
- Database positions don't match broker
- Trading blocked
- CRITICAL alert sent

**What To Do:**
1. **Identify discrepancy:**
   ```bash
   sqlite3 trading.db "SELECT discrepancies FROM broker_state WHERE reconciliation_status='FAIL' ORDER BY created_at DESC LIMIT 1;"
   ```
2. **Common causes:**
   - Manual trade via Alpaca dashboard
   - Position closed outside system
   - Partial fill not recorded
3. **Fix:**
   ```bash
   python scripts/sync_database.py --force
   ```
4. **Verify:**
   ```bash
   python scripts/verify_execution.py
   ```
5. **Resume:** Next run will pass reconciliation

### Scenario 4: DRY_RUN Testing

**What To Do:**
1. **Enable DRY_RUN mode:**
   ```bash
   export DRY_RUN=true
   ```
2. **Run system:**
   ```bash
   python src/execution_engine.py
   ```
3. **Review logs:**
   - All logic executes normally
   - No actual broker writes
   - "[DRY_RUN]" prefix in logs
4. **Check artifacts generated:**
   - Signal funnel
   - Rejections
   - Data quality
   - All reports
5. **Disable DRY_RUN when ready:**
   ```bash
   export DRY_RUN=false
   ```

---

## Support & Escalation

### Self-Service Diagnostics

**Check System Health:**
```bash
# Run validation
python scripts/validate_system.py

# Check database integrity
sqlite3 trading.db "PRAGMA integrity_check;"

# View recent errors
grep ERROR logs/multi_strategy.log | tail -20
```

**Review Structured Logs:**
```bash
# View event log
cat logs/events/events_*.jsonl | jq 'select(.event_type=="ERROR")'

# Count events by type
cat logs/events/events_*.jsonl | jq -r '.event_type' | sort | uniq -c
```

### When To Escalate

**Immediate Escalation:**
- System completely non-functional
- Database corruption
- Unexpected capital loss >5%
- Security breach suspected

**Review Within 24 Hours:**
- Persistent reconciliation failures
- Repeated kill switch activations
- Strategy health scores all CRITICAL
- Data quality issues not resolving

---

**Remember:** System is designed to protect capital. Trust the safety mechanisms. Manual overrides should be rare and well-considered.
