# Deployment Guide

## Overview

The trading system can be deployed in two modes:
1. **Local Development** - Run on your local machine with approval server
2. **Production (GitHub Actions)** - Automated daily execution with email notifications

---

## 🏠 Local Development Setup

### Current Setup (What You're Using Now)

**Components:**
- Flask approval server running locally (`http://localhost:8000`)
- Email workflow with database sync
- Manual approval via web interface

**How It Works:**
```bash
# 1. Start the approval server
python3 src/approval_server.py

# 2. Send test email
python3 scripts/test_morning_workflow.py

# 3. Click link in email → Approve/reject → Trades execute
```

**Pros:**
- ✅ Full control and testing
- ✅ See everything in real-time
- ✅ Easy debugging

**Cons:**
- ❌ Server must be running when you click email links
- ❌ Computer must be on
- ❌ Not automated

---

## ☁️ Production Deployment (GitHub Actions)

### Option 1: Email-Only Workflow (Recommended for Now)

**How It Works:**
1. GitHub Actions runs daily at scheduled time (e.g., 9:00 AM ET)
2. System generates trading signals
3. Email sent with proposed trades
4. **Email contains approve/reject buttons that submit directly to GitHub**
5. No server needed - everything via email

**Implementation:**
```yaml
# .github/workflows/daily-trading.yml
name: Daily Trading

on:
  schedule:
    - cron: '0 14 * * 1-5'  # 9:00 AM ET, weekdays only
  workflow_dispatch:  # Manual trigger

jobs:
  trade:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.8'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run trading workflow
        env:
          ALPACA_API_KEY: ${{ secrets.ALPACA_API_KEY }}
          ALPACA_SECRET_KEY: ${{ secrets.ALPACA_SECRET_KEY }}
          EMAIL_USERNAME: ${{ secrets.EMAIL_USERNAME }}
          EMAIL_PASSWORD: ${{ secrets.EMAIL_PASSWORD }}
          EMAIL_TO: ${{ secrets.EMAIL_TO }}
        run: python3 scripts/test_morning_workflow.py
```

**Pros:**
- ✅ Fully automated
- ✅ No server to maintain
- ✅ Runs even when computer is off
- ✅ Free on GitHub

**Cons:**
- ❌ No web-based approval page (email buttons only)
- ❌ Less interactive UI

### Option 2: Cloud-Hosted Approval Server

**Deployment Options:**

#### A. Railway.app (Easiest)
```bash
# 1. Install Railway CLI
npm install -g @railway/cli

# 2. Login and deploy
railway login
railway init
railway up

# 3. Set environment variables in Railway dashboard
```

**Cost:** ~$5/month for hobby plan

#### B. Heroku
```bash
# 1. Create Procfile
echo "web: python3 src/approval_server.py" > Procfile

# 2. Deploy
heroku create investor-approval
git push heroku main
```

**Cost:** ~$7/month for basic dyno

#### C. AWS Lambda + API Gateway
- More complex setup
- Pay per request (very cheap for low volume)
- Requires serverless framework

**Pros:**
- ✅ Full web interface
- ✅ Always available
- ✅ Professional deployment

**Cons:**
- ❌ Costs money
- ❌ More complex setup
- ❌ Need to manage hosting

---

## 🚀 Recommended Deployment Strategy

### Phase 1: Current Setup (You Are Here)
- Local approval server for testing
- Manual email workflow
- Verify everything works

### Phase 2: GitHub Actions + Email Buttons
- Automate daily email sending
- Simple approve/reject via email links
- No server needed
- **This is the easiest production setup**

### Phase 3: Cloud Deployment (Optional)
- Deploy approval server to Railway/Heroku
- Full web interface
- Professional setup

---

## 📋 GitHub Actions Setup (Step-by-Step)

### 1. Add Secrets to GitHub

Go to: `Settings → Secrets and variables → Actions → New repository secret`

Add these secrets:
```
ALPACA_API_KEY=your_key_here
ALPACA_SECRET_KEY=your_secret_here
EMAIL_USERNAME=schickerur2020@gmail.com
EMAIL_PASSWORD=guigmczeokncwpin
EMAIL_TO=schickerur2020@gmail.com
```

### 2. Update Workflow File

The workflow file already exists at `.github/workflows/daily-trading.yml`

**Current schedule:** Runs daily, but needs approval workflow

**What needs to change:**
- Currently set to `AUTO_TRADE=true` (executes immediately)
- Change to `AUTO_TRADE=false` for manual approval

### 3. Email-Based Approval (No Server Needed)

**Option A: GitHub Issues API**
- Approve/reject buttons create GitHub issues
- Workflow monitors issues and executes trades
- No server needed!

**Option B: GitHub Workflow Dispatch**
- Email contains links to trigger workflows
- Workflows execute approved trades
- Simple and free

---

## ⚙️ Configuration

### For Local Development:
```bash
# .env
ALPACA_API_KEY=your_key
ALPACA_SECRET_KEY=your_secret
EMAIL_USERNAME=your_email@gmail.com
EMAIL_PASSWORD=your_app_password
EMAIL_TO=your_email@gmail.com
APPROVAL_BASE_URL=http://localhost:8000/approve
AUTO_TRADE=false
```

### For GitHub Actions:
```bash
# Set in GitHub Secrets (no .env file needed)
# Secrets are automatically available as environment variables
```

---

## 🔒 Security Considerations

### Local Development:
- ✅ Credentials in `.env` (gitignored)
- ✅ Server only accessible locally
- ✅ One-time approval tokens

### GitHub Actions:
- ✅ Secrets encrypted by GitHub
- ✅ Never exposed in logs
- ✅ Audit trail in Actions history

### Cloud Deployment:
- ✅ Environment variables in hosting platform
- ✅ HTTPS encryption
- ✅ Professional security

---

## 📊 Monitoring

### Local:
- Server logs in terminal
- Database in `data/trading_system.db`
- Email confirmations

### GitHub Actions:
- Workflow run history
- Logs for each execution
- Email notifications on failure

---

## 🎯 Next Steps

**For Your Current Setup:**
1. ✅ Local server works perfectly
2. ✅ Email workflow complete
3. ✅ Approval page functional
4. ✅ Database tracking everything

**To Go Production:**
1. Test morning workflow: `python3 scripts/test_morning_workflow.py`
2. Verify email approval flow works end-to-end
3. Decide: Email-only or cloud server?
4. Set up GitHub Actions with chosen approach
5. Test with manual workflow trigger
6. Enable daily schedule

**Recommendation:** Start with GitHub Actions + email-only workflow. It's free, automated, and requires no server maintenance. You can always add a cloud server later if you want the full web interface.

---

## ❓ FAQ

**Q: Will GitHub Actions work without a server?**
A: Yes! The workflow runs in GitHub's cloud. You only need a server if you want the web-based approval interface.

**Q: What if I'm not available when the email arrives?**
A: Approval requests expire after 24 hours. You can adjust this or set up multiple approval recipients.

**Q: Can I test before going live?**
A: Yes! Use `workflow_dispatch` to manually trigger the workflow anytime.

**Q: What about database persistence?**
A: For GitHub Actions, use GitHub's artifact storage or a cloud database like Supabase (free tier available).

**Q: Is it safe to store credentials in GitHub?**
A: Yes, GitHub Secrets are encrypted and never exposed in logs or to other users.
