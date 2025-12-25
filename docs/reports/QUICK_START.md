# Quick Start Guide

Get the trading system running in the cloud with GitHub Actions.

## Prerequisites

- GitHub account
- Alpaca API account (free paper trading)

## GitHub Actions Setup (Recommended)

### 1. Add GitHub Secrets

Go to your repository: **Settings → Secrets and variables → Actions**

Click **New repository secret** and add:

**Secret 1:**
- Name: `ALPACA_API_KEY`
- Value: Your Alpaca API key

**Secret 2:**
- Name: `ALPACA_SECRET_KEY`
- Value: Your Alpaca secret key

### 2. Push Code to GitHub

```bash
git add .
git commit -m "Setup automated trading system"
git push origin main
```

### 3. Verify Workflow

- Go to: **Actions** tab in your repository
- You should see "Daily Paper Trading" workflow
- It will run automatically weekdays at 10:00 AM ET

### 4. Manual Test (Optional)

- Click **Daily Paper Trading** workflow
- Click **Run workflow** button
- Select branch and click **Run workflow**
- Watch it execute in real-time

## Local Testing (Optional)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure credentials
cp .env.example .env
# Edit .env with your Alpaca API keys

# 3. Run trading system
python3 src/main.py
```

## Verify It's Working

### GitHub Actions
✅ Go to **Actions** tab - see workflow runs  
✅ Click on a run - view detailed logs  
✅ Download artifacts - get trading logs  

### Alpaca Dashboard
✅ Check positions: https://app.alpaca.markets/paper  
✅ View orders and executions  

## What Happens Daily

**10:00 AM ET (Weekdays)** - GitHub Actions triggers automatically:

1. **Setup** - Spins up Ubuntu container
2. **Install** - Installs Python dependencies
3. **Execute** - Runs trading strategy
4. **Scan** - Checks 36 stocks for RSI < 30 signals
5. **Trade** - Submits buy orders to Alpaca
6. **Exit** - Closes positions held for 20+ days
7. **Log** - Saves logs as artifacts (30 days)
8. **Cleanup** - Container shuts down

**Cost:** FREE (GitHub Actions free tier)

## Monitoring

### View Execution History
- Go to **Actions** tab
- See all past runs with timestamps
- Green checkmark = success
- Red X = failure

### View Logs
- Click on any workflow run
- Click **Execute Daily Paper Trading**
- Expand **Run Paper Trading Strategy**
- See full output

### Download Logs
- Scroll to bottom of workflow run
- Under **Artifacts**, download `trading-logs-XXX`

## Troubleshooting

**Workflow not running?**  
- Check GitHub Actions is enabled in Settings
- Verify secrets are set correctly
- Check workflow file syntax

**No signals generated?**  
Normal - strategy only buys during oversold + low volatility conditions.

**Authentication errors?**  
Re-add secrets in GitHub Settings → Secrets and variables → Actions

## Next Steps

See `docs/GUIDE.md` for complete documentation.
