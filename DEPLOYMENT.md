# Automated Deployment Guide

This guide sets up **automated daily execution** of the paper trading system on GitHub Actions (free, runs on GitHub's servers).

---

## 🎯 What This Does

- **Runs automatically** every weekday at 10:00 AM ET (after market open)
- **No computer needed** - runs on GitHub's servers
- **Free** - GitHub Actions provides 2,000 minutes/month free
- **Logs saved** - Trading logs stored for 30 days
- **Manual trigger** - Can run anytime via GitHub UI

---

## 📋 Setup Steps (10 minutes)

### Step 1: Add GitHub Secrets

Your Alpaca credentials need to be stored securely in GitHub.

**Option A: Using GitHub CLI (Recommended)**
```bash
# Install GitHub CLI if needed
# Mac: brew install gh
# Linux: https://github.com/cli/cli#installation

# Login
gh auth login

# Add secrets
echo "PK7ZJKOYNMMWAULRJGFSBLZL54" | gh secret set ALPACA_API_KEY
echo "4LtTZQw5wGrXLz7Eu7DGoGEc5uwfzuxbkaWgXFiFtemo" | gh secret set ALPACA_SECRET_KEY
```

**Option B: Using GitHub Web Interface**
1. Go to: https://github.com/shreyas-chickerur/investor-mimic-bot/settings/secrets/actions
2. Click **New repository secret**
3. Add:
   - Name: `ALPACA_API_KEY`
   - Value: `PK7ZJKOYNMMWAULRJGFSBLZL54`
4. Click **Add secret**
5. Repeat for:
   - Name: `ALPACA_SECRET_KEY`
   - Value: `4LtTZQw5wGrXLz7Eu7DGoGEc5uwfzuxbkaWgXFiFtemo`

### Step 2: Push Workflows to GitHub

```bash
cd /Users/shreyaschickerur/CascadeProjects/investor-mimic-bot

# Add workflow files
git add .github/workflows/

# Commit
git commit -m "feat: add automated daily trading workflow"

# Push
git push origin feature/web-dashboard
```

### Step 3: Enable GitHub Actions

1. Go to: https://github.com/shreyas-chickerur/investor-mimic-bot/actions
2. If prompted, click **I understand my workflows, go ahead and enable them**

### Step 4: Test Manual Run

1. Go to: https://github.com/shreyas-chickerur/investor-mimic-bot/actions
2. Click **Daily Paper Trading** workflow
3. Click **Run workflow** dropdown
4. Click **Run workflow** button
5. Wait ~2 minutes
6. Click on the running workflow to see logs

---

## ✅ Verification

After running, you should see:
- ✅ Workflow completes successfully
- ✅ Logs show signals generated
- ✅ Orders submitted to Alpaca
- ✅ Check Alpaca dashboard: https://app.alpaca.markets/paper

---

## 📅 Schedule

The workflow runs automatically:
- **When:** 10:00 AM ET (3:00 PM UTC)
- **Days:** Monday - Friday (market days)
- **What it does:**
  1. Fetches latest market data
  2. Generates buy/sell signals
  3. Executes trades via Alpaca
  4. Saves logs

---

## 🔧 Customization

### Change Schedule

Edit `.github/workflows/daily-trading.yml`:

```yaml
schedule:
  # Current: 10:00 AM ET (3:00 PM UTC)
  - cron: '0 15 * * 1-5'
  
  # Examples:
  # 9:45 AM ET (2:45 PM UTC) - right after market open
  - cron: '45 14 * * 1-5'
  
  # 3:30 PM ET (8:30 PM UTC) - before market close
  - cron: '30 20 * * 1-5'
```

### Run Multiple Times Per Day

```yaml
schedule:
  # Morning run at 10 AM ET
  - cron: '0 15 * * 1-5'
  # Afternoon run at 2 PM ET
  - cron: '0 19 * * 1-5'
```

---

## 📊 Monitoring

### View Execution History
1. Go to: https://github.com/shreyas-chickerur/investor-mimic-bot/actions
2. Click **Daily Paper Trading**
3. See all past runs with timestamps

### View Logs
1. Click on any workflow run
2. Click **Execute Daily Paper Trading**
3. Expand **Run Paper Trading Strategy**
4. See full output including signals and trades

### Download Logs
1. Scroll to bottom of workflow run
2. Under **Artifacts**, download `trading-logs-XXX`

---

## 🚨 Troubleshooting

### Workflow Not Running
- Check GitHub Actions is enabled
- Verify secrets are set correctly
- Check cron schedule matches your timezone

### Authentication Errors
```bash
# Re-add secrets
gh secret set ALPACA_API_KEY
gh secret set ALPACA_SECRET_KEY
```

### No Signals Generated
- This is normal - strategy only buys when RSI < 30
- Check Alpaca dashboard for existing positions
- Review logs to see market conditions

---

## 💰 Cost

**GitHub Actions:** FREE
- 2,000 minutes/month included
- Each run takes ~2 minutes
- 22 trading days/month × 2 min = 44 minutes/month
- **Well within free tier**

---

## 🎯 Next Steps

1. ✅ Set up GitHub secrets
2. ✅ Push workflows
3. ✅ Test manual run
4. ✅ Verify in Alpaca dashboard
5. 📅 Let it run automatically daily
6. 📊 Monitor performance weekly

After 1-3 months of profitable paper trading, consider switching to live trading!

---

## 📝 Manual Override

You can always run manually:
```bash
# On your laptop
python3 bin/alpaca_paper_trading.py

# Or trigger via GitHub
# Go to Actions → Daily Paper Trading → Run workflow
```

---

**Your trading system is now fully automated and server-independent!** 🚀
