# Morning Run Guide

**Quick reference for automated daily trading runs**

---

## 🚀 Quick Start

### Local Testing

```bash
# Test the pre-flight check
python3 scripts/pre_flight_check.py

# Run full automated trading (with checks)
./scripts/run_trading.sh
```

### Manual Run

```bash
# Set environment
export ALPACA_PAPER=true
export DRY_RUN=false
export DATA_VALIDATOR_MAX_AGE_HOURS=96

# Run
python3 src/execution_engine.py
```

---

## 🔍 What the Pre-Flight Check Does

The system automatically checks:

1. **Market Open** - Skips weekends and major holidays
2. **Data Freshness** - Ensures data is <96 hours old (4 days)
3. **Auto-Update** - Attempts to fetch fresh data if stale
4. **Database** - Verifies database is accessible
5. **Safety Systems** - Checks kill switches and modes

**If any check fails:** Trading run is skipped (exit 0 for GitHub Actions)

---

## 📅 Expected Behavior

### Trading Days (Mon-Fri, not holidays)
```
✅ Market open
✅ Data fresh or updated
✅ Database accessible
✅ Safety systems OK
→ Trading executes normally
```

### Weekends
```
⏸️  Market closed: Weekend
→ Trading skipped (not an error)
```

### Holidays
```
⏸️  Market closed: Holiday
→ Trading skipped (not an error)
```

### Stale Data (can't update)
```
⚠️  Data stale: 5.2 days old
❌ Data update failed
→ Trading skipped if >7 days old
→ Trading proceeds if <7 days old
```

---

## ⚙️ Configuration

### Environment Variables

```bash
# Data staleness threshold (hours)
DATA_VALIDATOR_MAX_AGE_HOURS=96    # 4 days (default)

# Trading mode
ALPACA_PAPER=true                   # Paper trading (default)
DRY_RUN=false                       # Actual execution (default)

# Safety
TRADING_DISABLED=false              # Global kill switch
ENABLE_BROKER_RECONCILIATION=true   # Mandatory gate
```

### For GitHub Actions

Set in `.github/workflows/daily_trading.yml`:
```yaml
env:
  DATA_VALIDATOR_MAX_AGE_HOURS: '96'
  ALPACA_PAPER: 'true'
  DRY_RUN: 'false'
```

---

## 🐛 Troubleshooting

### Issue: Pre-flight check fails on data

**Symptom:**
```
❌ Data too stale to proceed safely
```

**Solutions:**
1. Wait for next trading day (data will update)
2. Manually update: `python3 scripts/update_data.py`
3. Increase threshold: `export DATA_VALIDATOR_MAX_AGE_HOURS=168` (7 days)

### Issue: Market closed but should be open

**Check:**
```python
python3 scripts/pre_flight_check.py
```

**Update holidays list** in `scripts/pre_flight_check.py` if needed.

### Issue: Database not accessible

**Fix:**
```bash
# Reinitialize database
python3 scripts/setup_database.py --db trading.db
```

### Issue: Kill switch active

**Check:**
```bash
echo $TRADING_DISABLED
```

**Disable:**
```bash
export TRADING_DISABLED=false
```

---

## 📊 Monitoring Morning Runs

### Check Logs

```bash
# View latest log
tail -100 logs/multi_strategy.log

# Check for errors
grep ERROR logs/multi_strategy.log

# Check pre-flight results
grep "PRE-FLIGHT" logs/multi_strategy.log
```

### Check Artifacts

```bash
# List today's artifacts
find artifacts/ -name "*$(date +%Y%m%d)*"

# View funnel
cat artifacts/funnel/signal_funnel_*.json | python3 -m json.tool

# View data quality
cat artifacts/data_quality/data_quality_report_*.json | python3 -m json.tool
```

### Check Database

```bash
# Recent runs
sqlite3 trading.db "SELECT run_id, created_at FROM broker_state ORDER BY created_at DESC LIMIT 5;"

# Today's trades
sqlite3 trading.db "SELECT * FROM trades WHERE DATE(executed_at) = DATE('now');"

# Drawdown state
sqlite3 trading.db "SELECT value FROM system_state WHERE key='drawdown_stop_state';"
```

---

## 🔄 GitHub Actions Workflow

### Schedule
- **Time:** 6:30 AM PST (14:30 UTC) daily
- **Runs:** Monday-Sunday (pre-flight check handles weekends/holidays)

### What Happens
1. Download previous database
2. Initialize/update database
3. Create artifact directories
4. **Run pre-flight check** ← NEW
5. **Auto-update data if needed** ← NEW
6. Execute trading (if checks pass)
7. Verify reconciliation
8. Upload database & artifacts
9. Send email digest

### Manual Trigger
```bash
# Via GitHub UI: Actions → Daily Trading Execution → Run workflow
```

---

## ✅ Success Indicators

**Pre-flight check passed:**
```
✅ ALL CHECKS PASSED - Safe to proceed with trading run
```

**Trading completed:**
```
✅ TRADING RUN COMPLETED SUCCESSFULLY
```

**Artifacts generated:**
```
artifacts/funnel/signal_funnel_*.json
artifacts/funnel/signal_rejections_*.json
artifacts/data_quality/data_quality_report_*.json
```

**Email received:**
- Subject: "📊 Daily Trading Digest"
- Contains: Signal funnel, trades, positions, metrics

---

## 🎯 Best Practices

### Daily Monitoring (2 minutes)
1. Check email digest
2. Verify no critical errors
3. Review drawdown level
4. Check for kill switch activations

### Weekly Review (15 minutes)
1. Review strategy health summary (Mondays)
2. Check rejection patterns
3. Verify no duplicate intents
4. Review data quality trends

### Monthly Audit (30 minutes)
1. Review all artifacts
2. Check database integrity
3. Analyze performance metrics
4. Update holiday list if needed

---

## 📞 Quick Commands

```bash
# Test pre-flight check
python3 scripts/pre_flight_check.py

# Run full automated flow
./scripts/run_trading.sh

# Check system status
python3 -c "from src.database import TradingDatabase; db = TradingDatabase(); print(db.get_system_state('drawdown_stop_state'))"

# View latest run
sqlite3 trading.db "SELECT * FROM broker_state ORDER BY created_at DESC LIMIT 1;"

# Check artifacts
ls -lt artifacts/funnel/ | head -5
```

---

## 🚨 Emergency Procedures

### Stop All Trading
```bash
export TRADING_DISABLED=true
# Or set GitHub Secret: TRADING_DISABLED=true
```

### Force Data Update
```bash
python3 scripts/update_data.py
```

### Reset Drawdown State
```python
from src.database import TradingDatabase
import json
db = TradingDatabase()
state = {'state': 'NORMAL', 'drawdown': 0.0, 'cooldown_days': 0, 'cooldown_end': None, 'triggered_at': None, 'rampup_end': None}
db.set_system_state('drawdown_stop_state', json.dumps(state))
```

---

**Last Updated:** January 1, 2026  
**Status:** Production ready with automated pre-flight checks
