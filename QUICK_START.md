# Quick Start Guide - Tomorrow Morning

## 🚀 **OPTION 1: Multi-Strategy Testing (Automated)**

Run 5 strategies automatically, get summary email:

```bash
# Run this command tomorrow morning
python3 scripts/automated_morning_workflow.py
```

**What happens:**
- ✅ All 5 strategies execute automatically
- ✅ Trades placed on paper account
- ✅ Summary email sent to your inbox
- ✅ No manual approval needed

**View results:**
```bash
./START_DASHBOARD.sh
# Opens at http://localhost:5000
```

---

## 📧 **OPTION 2: Manual Approval Workflow**

Get email, manually approve/reject trades:

```bash
# Send approval email
python3 scripts/test_morning_workflow.py
```

**What happens:**
- ✅ Email sent with proposed trades
- ⏸️ You click link and approve/reject
- ✅ Approved trades execute
- ✅ Confirmation email sent after submission

**Approval server (must be running):**
```bash
python3 src/approval_server.py
```

---

## 📊 **Admin Dashboard**

View all 5 strategies competing:

```bash
./START_DASHBOARD.sh
```

**Or:**
```bash
python3 src/strategy_dashboard.py
```

**Then open:** http://localhost:5000

**Shows:**
- 🏆 Strategy rankings
- 📈 Performance charts
- 💰 Portfolio values
- 📊 Return percentages
- 🔢 Trade counts

---

## ⚙️ **What's Configured**

### Email Settings (`.env`)
```
EMAIL_USERNAME=schickerur2020@gmail.com
EMAIL_PASSWORD=guigmczeokncwpin
EMAIL_TO=schickerur2020@gmail.com
```

### Strategies Initialized
1. RSI Mean Reversion - $20,000
2. ML Momentum - $20,000
3. News Sentiment - $20,000
4. MA Crossover - $20,000
5. Volatility Breakout - $20,000

### Databases
- Strategy performance: `data/strategy_performance.db`
- Trading system: `data/trading_system.db`

---

## 📅 **Recommended: Daily Schedule**

### Every Morning (Automated)
```bash
python3 scripts/automated_morning_workflow.py
```

### Anytime (Check Results)
```bash
./START_DASHBOARD.sh
```

---

## ✅ **Summary**

**Tomorrow morning, just run ONE command:**

```bash
python3 scripts/automated_morning_workflow.py
```

**This will:**
1. ✅ Run all 5 strategies
2. ✅ Execute trades automatically
3. ✅ Send you summary email
4. ✅ Track performance in database

**Then check dashboard anytime:**
```bash
./START_DASHBOARD.sh
```

**That's it! No manual work needed.** 🎯
