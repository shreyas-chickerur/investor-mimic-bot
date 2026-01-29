# Signal Generation Monitoring & Prevention Guide

## Overview

This guide explains the comprehensive signal generation monitoring system that ensures trading strategies work reliably and prevents silent failures.

## Problem Statement

**Issue:** Trading strategies may fail to generate signals due to:
- Stale market data (not updated daily)
- Missing or incomplete data
- Data quality issues (NaN values, missing columns)
- Silent failures in strategy logic
- Environment differences between local and production

**Impact:** No trades executed, missed opportunities, unclear diagnostics

## Solution Architecture

### 1. Enhanced Logging System

**Location:** `src/core/execution_engine.py`

**What it does:**
- Logs every strategy call with data statistics
- Shows signal counts for each strategy
- Displays sample signals (first 3) with reasoning
- Helps diagnose why signals aren't appearing

**Example output:**
```
Calling RSI Mean Reversion.generate_signals() with 2958 rows, 29 symbols
RSI Mean Reversion generated 3 raw signals
  - BUY AAPL: RSI 32.5 < 30, slope 20.44 > 0 (turning up)
  - BUY ADBE: RSI 31.0 < 30, slope 4.46 > 0 (turning up)
  - BUY BRK.B: RSI 28.5 < 30, slope 6.27 > 0 (turning up)
```

### 2. Daily Data Update Script

**Location:** `scripts/update_daily_data.py`

**Purpose:** Fetch latest market data daily to keep training_data.csv fresh

**Usage:**
```bash
python3 scripts/update_daily_data.py
```

**Features:**
- Fetches latest 5 days of data for all symbols
- Calculates all technical indicators (RSI, SMA, BB, ATR, etc.)
- Merges with existing data
- Keeps last 2 years to prevent file bloat
- Rate-limited for free Alpha Vantage API (12s between requests)

**When to run:**
- Daily before market open (automated in workflow)
- After adding new symbols to universe
- When data becomes stale (>3 days old)

### 3. Signal Generation Test Script

**Location:** `scripts/test_signal_generation.py`

**Purpose:** Verify all strategies can generate signals with current data

**Usage:**
```bash
python3 scripts/test_signal_generation.py
```

**What it checks:**
- Data file exists and loads correctly
- Data quality (age, completeness, required columns)
- Each strategy's signal generation
- Shows sample signals and reasoning
- Provides data quality metrics

**Example output:**
```
=== SIGNAL GENERATION TEST ===
Loaded 114,206 rows for 29 symbols
Data age: 2 days

RSI Mean Reversion: 3 signals ✅ OK
ML Momentum: 0 signals ✅ OK
...
Total signals: 3
✅ TEST PASSED - Strategies are generating signals
```

### 4. Signal Health Monitor

**Location:** `scripts/monitor_signal_health.py`

**Purpose:** Automated health checks for signal generation system

**Usage:**
```bash
python3 scripts/monitor_signal_health.py
```

**Checks performed:**
1. Data file exists
2. Data freshness (warns if >3 days old)
3. Symbol completeness (29 symbols expected)
4. Required columns present
5. NaN value detection
6. Market condition analysis (RSI levels)

**Integrated into workflow:** Runs before trading execution

### 5. Data Freshness Validation

**Location:** `src/core/execution_engine.py` (in `load_market_data()`)

**What it does:**
- Automatically checks data age when loading
- Warns if data is >3 days old
- Suggests running update script
- Prevents silent failures from stale data

**Example warning:**
```
⚠️  DATA IS STALE: 5 days old (latest: 2026-01-23)
⚠️  Consider running: python3 scripts/update_daily_data.py
```

## Workflow Integration

The daily trading workflow now includes:

```yaml
- name: Check signal generation health
  run: |
    echo "=== Signal Generation Health Check ==="
    python3 scripts/monitor_signal_health.py || echo "Health check completed with warnings"
```

This runs **before** trading execution to catch issues early.

## Prevention Checklist

### Daily (Automated)
- ✅ Health check runs in workflow
- ✅ Data freshness validated
- ✅ Enhanced logging tracks signal generation

### Weekly (Manual)
- [ ] Review workflow logs for signal patterns
- [ ] Check if strategies are generating expected signals
- [ ] Verify data update script is working

### Monthly (Manual)
- [ ] Run local signal generation test
- [ ] Review strategy performance
- [ ] Update universe if needed

### When Issues Occur

**No signals generated:**
1. Check data freshness: `python3 scripts/monitor_signal_health.py`
2. Test locally: `python3 scripts/test_signal_generation.py`
3. Update data: `python3 scripts/update_daily_data.py`
4. Review workflow logs for detailed diagnostics

**Stale data warning:**
1. Run: `python3 scripts/update_daily_data.py`
2. Verify Alpha Vantage API key is set
3. Check API rate limits

**Strategy-specific issues:**
1. Review enhanced logs in workflow
2. Test strategy locally with current data
3. Check strategy parameters in config

## Monitoring Dashboard

### Key Metrics to Watch

1. **Signal Count Trend**
   - Track signals per strategy over time
   - Alert if all strategies show 0 signals for >3 days

2. **Data Freshness**
   - Monitor data age in workflow logs
   - Alert if >3 days old

3. **Strategy Health**
   - RSI Mean Reversion: Should generate signals when market is oversold
   - ML Momentum: Depends on model confidence
   - Volatility Breakout: Requires high volume + price breakouts

### Expected Behavior

**Normal:**
- 0-5 signals per day is typical
- Some days have no signals (market conditions don't meet criteria)
- RSI strategy most active during market corrections

**Warning Signs:**
- 0 signals for >5 consecutive trading days
- Data age >3 days
- Missing symbols in data
- NaN values in critical columns

**Critical Issues:**
- Data file not found
- All strategies failing to generate signals
- Workflow errors in signal generation step

## Troubleshooting Guide

### Issue: No signals in workflow but signals locally

**Diagnosis:**
```bash
# Compare local vs workflow data
python3 scripts/test_signal_generation.py

# Check workflow logs for:
# - Data loading errors
# - Strategy initialization errors
# - Signal filtering/rejection
```

**Solution:**
- Ensure data file is committed to repo
- Check environment variables in workflow
- Review correlation filter settings

### Issue: Stale data

**Diagnosis:**
```bash
python3 scripts/monitor_signal_health.py
```

**Solution:**
```bash
# Update data manually
python3 scripts/update_daily_data.py

# Or add to cron/workflow for daily updates
```

### Issue: Data quality problems

**Diagnosis:**
```bash
# Check for NaN values, missing columns
python3 scripts/monitor_signal_health.py

# Inspect data directly
python3 -c "
import pandas as pd
df = pd.read_csv('data/training_data.csv')
print(df.info())
print(df.isnull().sum())
"
```

**Solution:**
- Re-fetch data: `python3 scripts/update_daily_data.py`
- Check Alpha Vantage API status
- Verify technical indicator calculations

## Best Practices

1. **Always test locally before deploying**
   ```bash
   python3 scripts/test_signal_generation.py
   ```

2. **Monitor workflow logs regularly**
   - Check for enhanced logging output
   - Review signal counts per strategy
   - Watch for warnings

3. **Keep data fresh**
   - Run update script daily (automated in workflow)
   - Monitor data age warnings
   - Set up alerts for stale data

4. **Document changes**
   - Update this guide when adding new strategies
   - Document expected signal patterns
   - Track configuration changes

5. **Test after changes**
   - Run test script after strategy modifications
   - Verify signals still generate correctly
   - Check workflow execution

## API Keys Required

- `ALPHA_VANTAGE_API_KEY`: For fetching market data
- `ALPACA_API_KEY`: For broker integration
- `ALPACA_SECRET_KEY`: For broker integration

## File Locations

- **Data:** `data/training_data.csv` (47MB, committed to repo)
- **Scripts:** `scripts/update_daily_data.py`, `scripts/test_signal_generation.py`, `scripts/monitor_signal_health.py`
- **Logs:** Enhanced logging in `src/core/execution_engine.py`
- **Workflow:** `.github/workflows/daily_trading.yml`

## Support

If issues persist:
1. Review this guide
2. Check workflow logs for detailed diagnostics
3. Run local tests to isolate the problem
4. Verify API keys and environment variables
5. Check data file integrity

## Version History

- **v1.0** (2026-01-28): Initial comprehensive monitoring system
  - Enhanced logging
  - Daily data update script
  - Signal generation test script
  - Health monitoring
  - Data freshness validation
  - Workflow integration
