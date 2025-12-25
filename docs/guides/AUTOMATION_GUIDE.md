# Automation Guide - Run Strategies Daily Automatically

## 🎯 Overview

You have **two options** to automate the daily workflow:

1. **Cron Job (Local Mac)** - Runs on your computer
2. **GitHub Actions (Cloud)** - Runs in the cloud (recommended)

---

## ⚙️ **Option 1: Cron Job (Local Mac)**

### **Setup (One-Time)**

```bash
./scripts/setup_cron.sh
```

This creates a cron job that runs **every weekday at 9:00 AM**.

### **What It Does**
- ✅ Runs `automated_morning_workflow.py` automatically
- ✅ Executes all 5 strategies
- ✅ Places trades on paper account
- ✅ Sends summary email
- ✅ Logs output to `logs/cron.log`

### **Requirements**
- ⚠️ Your Mac must be on and awake at 9 AM
- ⚠️ Terminal must have Full Disk Access (System Preferences → Security → Privacy)

### **View Logs**
```bash
tail -f logs/cron.log
```

### **View Cron Jobs**
```bash
crontab -l
```

### **Remove Cron Job**
```bash
crontab -e
# Delete the line with 'automated_morning_workflow.py'
```

### **Pros**
- ✅ Simple setup
- ✅ Runs locally
- ✅ No cloud dependencies

### **Cons**
- ❌ Computer must be on
- ❌ Won't run if Mac is asleep
- ❌ Manual if you're traveling

---

## ☁️ **Option 2: GitHub Actions (Recommended)**

### **Setup (One-Time)**

#### **Step 1: Add Secrets to GitHub**

Go to your repository on GitHub:
```
Settings → Secrets and variables → Actions → New repository secret
```

Add these secrets:
```
ALPACA_API_KEY=PK7ZJKOYNMMWAULRJGFSBLZL54
ALPACA_SECRET_KEY=4LtTZQw5wGrXLz7Eu7DGoGEc5uwfzuxbkaWgXFiFtemo
EMAIL_USERNAME=schickerur2020@gmail.com
EMAIL_PASSWORD=guigmczeokncwpin
EMAIL_TO=schickerur2020@gmail.com
```

#### **Step 2: Push Workflow File**

The workflow file is already created at:
`.github/workflows/multi-strategy-daily.yml`

Just commit and push:
```bash
git add .github/workflows/multi-strategy-daily.yml
git commit -m "Add automated daily workflow"
git push
```

#### **Step 3: Enable Actions**

On GitHub:
```
Actions tab → Enable workflows
```

### **What It Does**
- ✅ Runs **every weekday at 9:00 AM ET** automatically
- ✅ Executes all 5 strategies in the cloud
- ✅ Places trades on paper account
- ✅ Sends summary email to you
- ✅ Saves database to GitHub
- ✅ Works even if your computer is off

### **Schedule**
```yaml
cron: '0 14 * * 1-5'  # 9 AM ET = 2 PM UTC, Mon-Fri
```

### **Manual Trigger**
You can also trigger manually:
```
GitHub → Actions → Multi-Strategy Daily Execution → Run workflow
```

### **View Logs**
```
GitHub → Actions → Click on workflow run → View logs
```

### **Pros**
- ✅ Runs in the cloud (always available)
- ✅ Computer can be off
- ✅ Works while traveling
- ✅ Free on GitHub
- ✅ Automatic database backups
- ✅ Complete execution logs

### **Cons**
- ❌ Requires GitHub setup
- ❌ Slightly more complex

---

## 🔄 **Complete Automation Flow**

### **Every Weekday at 9:00 AM:**

```
1. GitHub Actions triggers (or cron job)
   ↓
2. Fetch market data from Alpaca
   ↓
3. Run all 5 strategies
   ↓
4. Generate trading signals
   ↓
5. Execute trades on paper account
   ↓
6. Record performance in database
   ↓
7. Send summary email to you
   ↓
8. Save database (GitHub) or log (cron)
   ↓
9. Done! Check email and dashboard
```

### **You Receive:**
- 📧 Daily summary email with rankings
- 📊 Updated dashboard (view anytime)
- 📈 Performance tracking in database

### **You Do:**
- ✅ Nothing! It's fully automated
- 📊 Check dashboard when you want
- 📧 Read summary emails

---

## 📊 **Monitoring**

### **Check Dashboard Anytime**
```bash
./START_DASHBOARD.sh
```
Opens at http://localhost:5000

### **View Logs**

**Cron:**
```bash
tail -f logs/cron.log
```

**GitHub Actions:**
```
GitHub → Actions → View workflow runs
```

### **Check Email**
- Daily summary email
- Strategy rankings
- Performance updates

---

## 🐛 **Troubleshooting**

### **Cron Job Not Running**

**Check if cron job exists:**
```bash
crontab -l | grep automated_morning_workflow
```

**Check logs:**
```bash
cat logs/cron.log
```

**Common issues:**
- Mac was asleep at 9 AM
- Terminal doesn't have Full Disk Access
- Python path incorrect

**Fix:**
```bash
# Re-run setup
./scripts/setup_cron.sh
```

### **GitHub Actions Not Running**

**Check workflow status:**
```
GitHub → Actions → View runs
```

**Common issues:**
- Secrets not configured
- Workflow not enabled
- Schedule time zone confusion

**Fix:**
- Verify secrets in GitHub Settings
- Enable workflows in Actions tab
- Trigger manually to test

---

## 🎯 **Recommendation**

### **Best Setup: GitHub Actions**

**Why:**
- ✅ Works 24/7 in the cloud
- ✅ Computer can be off
- ✅ Automatic backups
- ✅ Complete logs
- ✅ Free

**Setup time:** 5 minutes

### **Alternative: Cron Job**

**When to use:**
- You prefer local execution
- Don't want to use GitHub
- Want simpler setup

**Setup time:** 1 minute

---

## ✅ **Quick Setup Commands**

### **For Cron (Local):**
```bash
./scripts/setup_cron.sh
```

### **For GitHub Actions (Cloud):**
```bash
# 1. Add secrets on GitHub (one-time)
# 2. Push workflow file
git add .github/workflows/multi-strategy-daily.yml
git commit -m "Add automated workflow"
git push

# 3. Enable Actions on GitHub
# Done!
```

---

## 📅 **After Setup**

### **Daily (Automatic):**
- 9:00 AM: Workflow runs
- 9:05 AM: Email arrives
- Anytime: Check dashboard

### **Weekly (Optional):**
- Review performance
- Check rankings
- Adjust if needed

### **Monthly:**
- Analyze results
- Choose winning strategy
- Deploy to production

---

## 🚀 **Ready to Automate**

Choose your option and run the setup:

**Option 1 (Local):**
```bash
./scripts/setup_cron.sh
```

**Option 2 (Cloud - Recommended):**
1. Add secrets to GitHub
2. Push workflow file
3. Enable Actions

**Then relax - everything runs automatically!** 🎯
