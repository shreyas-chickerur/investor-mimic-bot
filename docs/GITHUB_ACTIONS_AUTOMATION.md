# GitHub Actions Automation for Phase 5

**Automated morning execution via GitHub Actions - No local machine required**

---

## Overview

GitHub Actions will automatically run Phase 5 Day 1 execution at 6:30 AM PST (14:30 UTC) every day.

**Benefits:**
- ✅ No need to keep your computer on
- ✅ No need to be awake
- ✅ Runs in the cloud
- ✅ Automatic artifact storage
- ✅ Automatic git commits

---

## Setup (One-Time)

### Step 1: Verify Secrets Are Set

GitHub secrets should already be configured. Verify:

1. Go to: https://github.com/shreyas-chickerur/investor-mimic-bot/settings/secrets/actions
2. Confirm these secrets exist:
   - `ALPACA_API_KEY`
   - `ALPACA_SECRET_KEY`

If missing, add them:
- Click "New repository secret"
- Name: `ALPACA_API_KEY`
- Value: Your Alpaca API key
- Repeat for `ALPACA_SECRET_KEY`

### Step 2: Enable Workflow

The workflow is already committed to `.github/workflows/phase5_morning_run.yml`

It will automatically run at 6:30 AM PST daily.

---

## What It Does

The GitHub Actions workflow:

1. **Checks out code** from main branch
2. **Sets up Python 3.8** environment
3. **Installs dependencies** from requirements.txt
4. **Initializes database** with required tables
5. **Verifies positions cleared** (aborts if not)
6. **Runs Day 1 execution** with reconciliation enabled
7. **Verifies success** (reconciliation passed, 0 discrepancies)
8. **Uploads artifacts** (JSON, Markdown, logs) - retained 30 days
9. **Commits results** to main branch

---

## Schedule

**Runs daily at:** 6:30 AM PST (14:30 UTC)

**Timezone conversion:**
- 6:30 AM PST = 9:30 AM EST = 14:30 UTC

**Cron expression:** `30 14 * * *`

---

## Manual Trigger

You can manually trigger the workflow anytime:

1. Go to: https://github.com/shreyas-chickerur/investor-mimic-bot/actions
2. Click "Phase 5 Morning Execution" workflow
3. Click "Run workflow" button
4. Select branch: `main`
5. Click "Run workflow"

---

## Monitor Execution

### View Workflow Runs

1. Go to: https://github.com/shreyas-chickerur/investor-mimic-bot/actions
2. Click "Phase 5 Morning Execution"
3. See all runs with status (success/failure)

### View Logs

1. Click on a specific run
2. Click "morning-execution" job
3. Expand each step to see detailed logs

### Download Artifacts

1. Click on a completed run
2. Scroll to "Artifacts" section
3. Download `phase5-day1-artifacts`
4. Contains: `artifacts/` and `logs/` folders

---

## What Happens If...

### Positions Not Cleared

**Workflow will:**
- Abort at Step 1
- Mark run as failed
- Log warning: "X positions remain - aborting"
- Not run execution
- Not commit anything

**What to do:**
- Wait for positions to clear (usually within minutes after market open)
- Manually trigger workflow again
- Or wait for next scheduled run

### Reconciliation Fails

**Workflow will:**
- Complete execution
- Mark run as failed at Step 3
- Upload artifacts (for debugging)
- Not commit results

**What to do:**
- Check logs for discrepancies
- Fix issues manually
- Re-run workflow

### Execution Succeeds

**Workflow will:**
- Mark run as successful
- Upload artifacts
- Commit results to main branch
- Push to GitHub

**You'll see:**
- New commit: "Phase 5 Day 1 Complete (Automated via GitHub Actions)"
- Artifacts in `artifacts/` folder
- Logs in `logs/` folder

---

## Notifications

### Email Notifications

GitHub sends email notifications for:
- ✅ Workflow success
- ❌ Workflow failure

**Configure:**
1. GitHub Settings → Notifications
2. Enable "Actions" notifications

### Slack/Discord (Optional)

Add notification step to workflow:

```yaml
- name: Notify Slack
  if: always()
  uses: 8398a7/action-slack@v3
  with:
    status: ${{ job.status }}
    webhook_url: ${{ secrets.SLACK_WEBHOOK }}
```

---

## Daily Execution (Days 2-30)

For daily execution at 1:15 PM PST (4:15 PM ET), create another workflow:

**File:** `.github/workflows/phase5_daily_run.yml`

**Cron:** `15 21 * * *` (1:15 PM PST = 21:15 UTC)

**Same steps as morning run, but:**
- No position verification (not needed after Day 1)
- Just run execution + verify + commit

---

## Troubleshooting

### Workflow Not Running

**Check:**
1. Workflow file exists: `.github/workflows/phase5_morning_run.yml`
2. Workflow is enabled (not disabled in Actions settings)
3. Repository has Actions enabled

**Fix:**
- Go to Actions tab
- Enable workflows if disabled

### Secrets Not Found

**Error:** `You must supply a method of authentication`

**Fix:**
1. Verify secrets exist in repository settings
2. Check secret names match exactly: `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`
3. Re-add secrets if needed

### Git Push Failed

**Error:** `failed to push some refs`

**Cause:** Local changes conflict with remote

**Fix:**
- Workflow will skip commit if no changes
- Or pull changes locally first

### Artifacts Not Generated

**Check:**
1. Execution completed successfully
2. `artifacts/` folder exists
3. Artifact upload step succeeded

**Debug:**
- Check workflow logs for errors
- Verify `multi_strategy_main.py` generates artifacts

---

## Cost

**GitHub Actions free tier:**
- 2,000 minutes/month for private repos
- Unlimited for public repos

**This workflow uses:**
- ~5 minutes per run
- 30 days × 5 min = 150 minutes/month

**Well within free tier!** ✅

---

## Disable Automation

To stop automated runs:

1. Go to: https://github.com/shreyas-chickerur/investor-mimic-bot/actions
2. Click "Phase 5 Morning Execution"
3. Click "..." menu → "Disable workflow"

Or delete the workflow file:
```bash
git rm .github/workflows/phase5_morning_run.yml
git commit -m "Disable automated morning run"
git push
```

---

## Re-enable Automation

1. Go to Actions tab
2. Click "Phase 5 Morning Execution"
3. Click "Enable workflow"

---

## Summary

**Setup:** One-time (verify secrets)  
**Runs:** Automatically at 6:30 AM PST daily  
**Monitors:** GitHub Actions tab  
**Artifacts:** Auto-uploaded, 30-day retention  
**Cost:** Free (within GitHub Actions limits)

**You can sleep in - GitHub handles everything!** 🛌✅

---

## Quick Links

- **Actions:** https://github.com/shreyas-chickerur/investor-mimic-bot/actions
- **Secrets:** https://github.com/shreyas-chickerur/investor-mimic-bot/settings/secrets/actions
- **Workflow file:** `.github/workflows/phase5_morning_run.yml`
