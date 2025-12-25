# GitHub Actions Setup for Phase 5 Operational Validation

This guide explains how to set up automated daily trading runs and weekly rollups using GitHub Actions.

---

## Overview

Two workflows are configured:
1. **Daily Trading** (`.github/workflows/daily-trading.yml`) - Runs Mon-Fri at 1 PM PT / 4 PM ET
2. **Weekly Rollup** (`.github/workflows/weekly-rollup.yml`) - Runs Sundays at 2 PM PT / 5 PM ET

---

## Setup Instructions

### 1. Add Alpaca Credentials as GitHub Secrets

1. Go to your GitHub repository
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Add these secrets:

| Name | Value |
|------|-------|
| `ALPACA_API_KEY` | Your Alpaca API key |
| `ALPACA_SECRET_KEY` | Your Alpaca secret key |

### 2. Enable GitHub Actions

1. Go to **Actions** tab in your repository
2. If prompted, click **I understand my workflows, go ahead and enable them**
3. Verify both workflows appear:
   - "Phase 5 Daily Operational Validation"
   - "Phase 5 Weekly Rollup"

### 3. Manual Test Run (Recommended)

Before relying on scheduled runs, test manually:

1. Go to **Actions** tab
2. Click **Phase 5 Daily Operational Validation**
3. Click **Run workflow** → **Run workflow**
4. Wait for completion (~2-5 minutes)
5. Check the summary and logs

---

## What Happens Automatically

### Daily (Mon-Fri at 1 PM PT)

1. **Runs trading system** with:
   - `ALPACA_PAPER=true`
   - `ENABLE_BROKER_RECONCILIATION=true`
   - `PHASE5_SIGNAL_INJECTION=false`

2. **Verifies invariants**:
   - Runs `check_phase5_invariants.py --latest`
   - Must show 6/6 PASS

3. **Verifies Day 1 criteria**:
   - Runs `verify_phase5_day1.py`
   - Checks all validation requirements

4. **Extracts metrics**:
   - Run ID
   - Broker snapshots
   - Signal termination rates
   - Trade counts

5. **Uploads artifacts**:
   - `trading.db` (persistent across runs)
   - Daily JSON/markdown artifacts
   - Retention: 90 days

6. **Creates summary**:
   - Visible in Actions run summary
   - Shows run ID, signals, trades, status

### Weekly (Sundays at 2 PM PT)

1. **Generates rollup report**:
   - Last 7 days summary
   - Reconciliation pass/fail counts
   - Signal statistics
   - Trade statistics

2. **Checks validation progress**:
   - Total successful days
   - Days remaining to 14-day minimum
   - Completion status

3. **Creates summary**:
   - Validation progress
   - Next steps
   - Completion status

---

## Monitoring

### Check Daily Run Status

1. Go to **Actions** tab
2. Click latest **Phase 5 Daily Operational Validation** run
3. Check:
   - ✅ Green checkmark = Success
   - ❌ Red X = Failure (investigate logs)
   - Summary shows run ID, signals, trades

### Check Weekly Rollup

1. Go to **Actions** tab
2. Click latest **Phase 5 Weekly Rollup** run
3. Check:
   - Successful days count
   - Failed days count
   - Progress toward 14-30 day goal

### Download Artifacts

1. Go to any completed run
2. Scroll to **Artifacts** section
3. Download:
   - `trading-database` (latest trading.db)
   - `daily-artifacts-XXX` (JSON/markdown files)

---

## Troubleshooting

### Workflow Fails

1. Click the failed run
2. Expand failed step
3. Check error message
4. Common issues:
   - **Secrets not set**: Add ALPACA_API_KEY and ALPACA_SECRET_KEY
   - **Invariants fail**: Check logs for which invariant failed
   - **Database error**: Download artifact and inspect locally

### Invariants Fail

If `check_phase5_invariants.py` shows failures:

1. Download `trading-database` artifact
2. Run locally:
   ```bash
   python3 scripts/check_phase5_invariants.py --latest
   ```
3. Investigate specific failure
4. Fix issue before next run

### Reconciliation Fails

If reconciliation shows FAIL:

1. Download `trading-database` artifact
2. Check discrepancies:
   ```bash
   RUN_ID=$(sqlite3 trading.db "SELECT run_id FROM broker_state ORDER BY created_at DESC LIMIT 1;")
   sqlite3 trading.db "SELECT discrepancies_json FROM broker_state WHERE run_id='$RUN_ID' AND snapshot_type='RECONCILIATION';"
   ```
3. Resolve discrepancies
4. May need to pause validation until fixed

---

## Manual Runs

You can trigger runs manually anytime:

1. Go to **Actions** tab
2. Select workflow (Daily or Weekly)
3. Click **Run workflow**
4. Select branch (usually `main`)
5. Click **Run workflow**

Useful for:
- Testing after changes
- Running on non-scheduled days
- Catching up after failures

---

## Notifications

### Email Notifications (Default)

GitHub sends email notifications for:
- Workflow failures
- First failure after success
- Success after failure

Configure in: **Settings** → **Notifications** → **Actions**

### Slack/Discord (Optional)

Add notification steps to workflows:

```yaml
- name: Notify Slack
  if: failure()
  uses: slackapi/slack-github-action@v1
  with:
    webhook-url: ${{ secrets.SLACK_WEBHOOK }}
    payload: |
      {
        "text": "Phase 5 validation failed: ${{ github.run_id }}"
      }
```

---

## Database Persistence

The `trading.db` file persists across runs via artifacts:

1. **Download** at start of each run (if exists)
2. **Upload** at end of each run
3. **Retention**: 90 days

This ensures:
- Historical data accumulates
- Weekly rollups work correctly
- Validation day count is accurate

---

## Validation Completion

When you reach 14-30 successful days:

1. **Weekly rollup** will show completion status
2. **Download** final `trading-database` artifact
3. **Generate** final validation report
4. **Document** results in `docs/PHASE_5_VALIDATION_COMPLETE.md`
5. **Disable** or reduce frequency of workflows if desired

---

## Cost Considerations

GitHub Actions free tier:
- **Public repos**: Unlimited minutes
- **Private repos**: 2,000 minutes/month

Each run uses ~2-5 minutes:
- Daily runs: ~5 min × 20 days/month = 100 min/month
- Weekly runs: ~2 min × 4 weeks = 8 min/month
- **Total**: ~108 min/month (well within free tier)

---

## Security Notes

1. **Secrets are encrypted** and not visible in logs
2. **Paper trading only** - no real money at risk
3. **Database artifacts** are private to repository
4. **API keys** never exposed in workflow files
5. **Artifacts auto-delete** after 90 days

---

## Next Steps

1. ✅ Add Alpaca secrets to repository
2. ✅ Enable GitHub Actions
3. ✅ Run manual test
4. ✅ Verify first daily run succeeds
5. ✅ Monitor weekly rollups
6. ✅ Complete 14-30 day validation period

**Current Status:** Ready to automate
