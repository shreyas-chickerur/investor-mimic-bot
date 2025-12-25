# GitHub Actions Setup Checklist

Complete this checklist before relying on automated Phase 5 validation runs.

---

## ✅ 1. GitHub Secrets Configuration

Go to: **Repository → Settings → Secrets and variables → Actions**

### Required Secrets

| Secret Name | Value | Status |
|-------------|-------|--------|
| `ALPACA_API_KEY` | Your Alpaca API key | ⬜ Not set |
| `ALPACA_SECRET_KEY` | Your Alpaca secret key | ⬜ Not set |

### Verification

After adding secrets, run this check:
1. Go to **Actions** tab
2. Select **Phase 5 Daily Operational Validation**
3. Click **Run workflow** → **Run workflow**
4. Check if it completes successfully

---

## ✅ 2. Environment Variables (Auto-Configured)

These are hardcoded in the workflow files - **no action needed**:

| Variable | Value | Location |
|----------|-------|----------|
| `ALPACA_PAPER` | `true` | `.github/workflows/phase5-daily-validation.yml:66` |
| `ALPACA_LIVE_ENABLED` | `false` | `.github/workflows/phase5-daily-validation.yml:67` |
| `ENABLE_BROKER_RECONCILIATION` | `true` | `.github/workflows/phase5-daily-validation.yml:68` |
| `PHASE5_SIGNAL_INJECTION` | `false` | `.github/workflows/phase5-daily-validation.yml:69` |

---

## ✅ 3. Email/Notifications

### GitHub Actions Default Notifications

GitHub automatically sends emails for:
- ✅ Workflow failures
- ✅ First failure after success
- ✅ Success after failure

**Configure:** Settings → Notifications → Actions

### SMTP Email (Optional - Not Required)

The system has `EmailNotifier` code but it's **NOT wired into GitHub Actions**.

If you want email notifications from the trading system itself:
1. Add these secrets:
   - `SMTP_SERVER`
   - `SMTP_PORT`
   - `SENDER_EMAIL`
   - `SENDER_PASSWORD`
   - `RECIPIENT_EMAIL`
2. Add them to workflow env vars

**Recommendation:** Skip SMTP for now. GitHub Actions notifications are sufficient.

---

## ✅ 4. Dependencies & Runtime Environment

### Python Version

- **Workflow:** Python 3.8 (`.github/workflows/phase5-daily-validation.yml:11`)
- **Your Local:** Python 3.8.3 ✅ **Match**

### Dependencies

**Workflow installs:** `pip install -r requirements.txt`

**Required packages in `requirements.txt`:**
- ✅ `alpaca-py==0.11.0`
- ✅ `pandas==2.0.3`
- ✅ `python-dotenv==1.0.0`
- ✅ `scikit-learn==1.3.2`
- ✅ `numpy==1.24.4`
- ✅ `requests==2.31.0`

**sqlite3:** Included in Python standard library ✅

### Required Files/Directories

**Workflow creates:**
- ✅ `artifacts/json/`
- ✅ `artifacts/markdown/`
- ✅ `logs/`

**Must exist in repo:**
- ✅ `src/multi_strategy_main.py`
- ✅ `scripts/check_phase5_invariants.py`
- ✅ `scripts/verify_phase5_day1.py`
- ✅ `requirements.txt`

**Data files:**
- `data/training_data.csv` - **Not required** (system fetches data via Alpaca API)
- `trading.db` - **Created automatically** on first run

---

## ✅ 5. Database Persistence

### How It Works

1. **Download** `trading.db` artifact at start (if exists)
2. **Run** trading system (updates database)
3. **Upload** `trading.db` artifact at end

**Retention:** 90 days

### Verification

After first run:
1. Go to completed workflow run
2. Scroll to **Artifacts** section
3. Verify `trading-database` artifact exists
4. Download and inspect locally (optional)

### What This Enables

- ✅ Historical data accumulates across runs
- ✅ Weekly rollups show correct day counts
- ✅ Validation progress tracked accurately (X/14-30 days)

---

## ✅ 6. Cron Schedule Verification

### Daily Validation

**Workflow:** `.github/workflows/phase5-daily-validation.yml`

```yaml
schedule:
  - cron: '0 21 * * 1-5'  # 9 PM UTC Mon-Fri
```

**Converts to:**
- **PST (Winter):** 1 PM PT
- **PDT (Summer):** 2 PM PT

**Market closes:** 4 PM ET / 1 PM PT

✅ **Runs after market close** (safe for end-of-day execution)

### Weekly Rollup

**Workflow:** `.github/workflows/weekly-rollup.yml`

```yaml
schedule:
  - cron: '0 22 * * 0'  # 10 PM UTC Sundays
```

**Converts to:**
- **PST (Winter):** 2 PM PT Sunday
- **PDT (Summer):** 3 PM PT Sunday

✅ **Runs on weekends** (no market conflict)

### Manual Trigger

Both workflows support `workflow_dispatch` - you can trigger manually anytime:
1. Go to **Actions** tab
2. Select workflow
3. Click **Run workflow**

---

## ✅ 7. Safety Guardrails

### Automated Checks in Workflow

**Before trading system runs:**

1. **Paper Trading Verification**
   ```bash
   if [ "$ALPACA_PAPER" != "true" ]; then
     echo "❌ FATAL: ALPACA_PAPER must be 'true'"
     exit 1
   fi
   ```

2. **Signal Injection Disabled**
   ```bash
   if [ "$PHASE5_SIGNAL_INJECTION" != "false" ]; then
     echo "❌ FATAL: Must be 'false' for operational validation"
     exit 1
   fi
   ```

3. **Live Trading Disabled**
   ```yaml
   ALPACA_LIVE_ENABLED: 'false'
   ```

### Code-Level Checks

**In `src/multi_strategy_main.py`:**

```python
self.paper_mode = os.getenv('ALPACA_PAPER', 'true').lower() == 'true'
live_enabled = os.getenv('ALPACA_LIVE_ENABLED', 'false').lower() == 'true'

if not self.paper_mode and not live_enabled:
    raise ValueError("Live trading disabled")
```

✅ **Multi-layer protection** against accidental live trading

---

## ✅ 8. First Run Test

### Manual Test (Recommended)

Before relying on scheduled runs:

1. **Add secrets** (Step 1)
2. Go to **Actions** tab
3. Click **Phase 5 Daily Operational Validation**
4. Click **Run workflow** → **Run workflow**
5. Wait 2-5 minutes
6. **Verify:**
   - ✅ Status: Green checkmark
   - ✅ Summary shows: Run ID, signals, trades
   - ✅ Logs show: 6/6 invariants passing
   - ✅ Artifact uploaded: `trading-database`

### If It Fails

Check logs for:
- **Missing secrets:** Add ALPACA_API_KEY and ALPACA_SECRET_KEY
- **Import errors:** Verify requirements.txt has all packages
- **Database errors:** Check if trading.db was created
- **Invariant failures:** Review which invariant failed

---

## ✅ 9. Monitoring Setup

### Daily Monitoring (Passive)

GitHub sends email notifications automatically:
- ✅ Enabled by default
- ✅ Configure: Settings → Notifications → Actions
- ✅ Receive emails on: Failures, first failure after success

### Weekly Check (Active)

Every Sunday, review:
1. Go to **Actions** tab
2. Click latest **Phase 5 Weekly Rollup** run
3. Check summary:
   - Successful days: X/14-30
   - Failed days: 0 (should be zero)
   - Progress status

### Download Artifacts (Optional)

Anytime:
1. Go to any completed run
2. Scroll to **Artifacts**
3. Download:
   - `trading-database` (latest trading.db)
   - `daily-artifacts-XXX` (JSON/markdown files)

---

## ✅ 10. Completion Criteria

### When Validation is Complete

**Weekly rollup will show:**
```
✅ Validation complete! Ready for production.
```

**This happens when:**
- 14-30 consecutive successful days
- Zero reconciliation failures
- Zero invariant violations
- 100% signal termination rate

### Next Steps After Completion

1. Download final `trading-database` artifact
2. Generate final validation report
3. Document results in `docs/PHASE_5_VALIDATION_COMPLETE.md`
4. Optionally disable or reduce workflow frequency

---

## Summary Checklist

- [ ] Add `ALPACA_API_KEY` secret
- [ ] Add `ALPACA_SECRET_KEY` secret
- [ ] Run manual test workflow
- [ ] Verify first run succeeds
- [ ] Verify artifact uploaded
- [ ] Enable GitHub Actions email notifications
- [ ] Wait for first scheduled run (next weekday 1 PM PT)
- [ ] Check weekly rollup (next Sunday 2 PM PT)
- [ ] Monitor for 14-30 days
- [ ] Download final artifacts when complete

---

## Quick Reference

**Add secrets:** Repo → Settings → Secrets and variables → Actions  
**Manual run:** Actions → Phase 5 Daily Operational Validation → Run workflow  
**Check status:** Actions → Latest run → Summary  
**Download DB:** Actions → Run → Artifacts → trading-database  
**Weekly stats:** Actions → Phase 5 Weekly Rollup → Latest run

---

**Status:** Ready for automation  
**Next:** Add secrets and run first test
