# Email Approval Workflow Setup Guide

This guide shows you how to set up the email approval workflow, which requires your confirmation before executing any trades.

## Overview

**How It Works:**
1. Bot analyzes the market and generates trade recommendations
2. Bot sends you an email with:
   - Summary of proposed trades
   - Total investment amount
   - Clickable "Approve" and "Reject" buttons
3. You review and click a button
4. Bot executes trades only after you approve

**Safety:** No trades execute without your explicit approval!

---

## Step 1: Configure Email Notifications

### For Gmail Users (Recommended)

1. **Enable 2-Factor Authentication**
   - Go to https://myaccount.google.com/security
   - Enable 2-Step Verification

2. **Generate App Password**
   - Go to https://myaccount.google.com/apppasswords
   - Select "Mail" and "Other (Custom name)"
   - Name it "InvestorBot"
   - Copy the 16-character password

3. **Add to `.env` file:**
   ```bash
   SMTP_SERVER=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USERNAME=your-email@gmail.com
   SMTP_PASSWORD=abcd efgh ijkl mnop  # Your 16-char app password
   ALERT_EMAIL=your-email@gmail.com
   ```

### For Other Email Providers

**Outlook/Hotmail:**
```bash
SMTP_SERVER=smtp-mail.outlook.com
SMTP_PORT=587
SMTP_USERNAME=your-email@outlook.com
SMTP_PASSWORD=your-password
```

**Yahoo:**
```bash
SMTP_SERVER=smtp.mail.yahoo.com
SMTP_PORT=587
SMTP_USERNAME=your-email@yahoo.com
SMTP_PASSWORD=your-app-password
```

---

## Step 2: Start the API Server

The approval workflow requires the API server to be running to handle approval clicks.

**Start the server:**
```bash
python3 main.py
```

**Or run in background:**
```bash
nohup python3 main.py > logs/api.log 2>&1 &
```

**Verify it's running:**
```bash
curl http://localhost:8000/health
```

You should see: `{"status":"healthy"}`

---

## Step 3: Run the Approval Script

### Manual Run

```bash
python3 scripts/auto_invest_with_approval.py \
  --approval-email your-email@gmail.com
```

**What happens:**
1. Bot analyzes market (takes 10-30 seconds)
2. Sends you an email with trade summary
3. Waits for your approval (default: 60 minutes)
4. Executes trades after you approve

### Scheduled Run

Add to crontab to run daily at 10 AM:

```bash
crontab -e
```

Add this line:
```bash
0 10 * * 1-5 cd /Users/shreyaschickerur/CascadeProjects/investor-mimic-bot && /Library/Frameworks/Python.framework/Versions/3.8/bin/python3 scripts/auto_invest_with_approval.py --approval-email your-email@gmail.com >> logs/auto_invest_approval.log 2>&1
```

---

## Step 4: Approve Trades

### Via Email (Easiest)

1. Check your email for "Trade Approval Required"
2. Click the **"Approve"** or **"Reject"** link
3. You'll see a nice web page with trade details
4. Click the green "✓ Approve Trades" button
5. Done! Bot executes immediately

### Via API (Advanced)

If email links don't work, you can approve via command line:

```bash
# Get pending requests
curl http://localhost:8000/api/v1/approvals/

# Approve a specific request
curl -X POST http://localhost:8000/api/v1/approvals/REQUEST_ID/approve

# Reject a specific request
curl -X POST http://localhost:8000/api/v1/approvals/REQUEST_ID/reject
```

---

## Configuration Options

### Custom Approval Timeout

Default is 60 minutes. Change it:

```bash
python3 scripts/auto_invest_with_approval.py \
  --approval-email your@email.com \
  --approval-timeout 120  # 2 hours
```

### Custom Investment Parameters

```bash
python3 scripts/auto_invest_with_approval.py \
  --approval-email your@email.com \
  --min-cash 2000 \           # Need $2,000 to invest
  --max-positions 15 \        # Hold up to 15 stocks
  --cash-buffer-pct 15        # Keep 15% cash buffer
```

### Check Interval

How often to check for approval (default: 30 seconds):

```bash
python3 scripts/auto_invest_with_approval.py \
  --approval-email your@email.com \
  --check-interval 60  # Check every minute
```

---

## Email Example

**Subject:** Trade Approval Required: $5,234.50

**Body:**
```
Investment Approval Required

The bot has identified an investment opportunity and is requesting your approval.

SUMMARY:
--------
Total Investment: $5,234.50
Available Cash: $10,500.00
Cash Buffer: $1,050.00
Number of Trades: 8
Strategy: Conviction Strategy

PROPOSED TRADES:
---------------
  • AAPL: 15.5 shares @ $185.23 = $2,871.07
  • GOOGL: 8.2 shares @ $142.50 = $1,168.50
  • MSFT: 10.3 shares @ $378.90 = $3,902.67
  ... (more trades)

APPROVAL:
---------
This request will expire at: 2025-12-18 11:00:00 UTC

To approve these trades, click:
http://localhost:8000/api/v1/approve/abc123/approve

To reject these trades, click:
http://localhost:8000/api/v1/approve/abc123/reject

Request ID: abc123
```

---

## Troubleshooting

### "Email not configured"

Make sure you have all SMTP settings in `.env`:
- `SMTP_SERVER`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`

### "Failed to send email"

**Gmail users:** Make sure you're using an app password, not your regular password.

**Check credentials:**
```bash
python3 -c "
from config.settings import get_notification_config
config = get_notification_config()
print('Email configured:', config.email_config is not None if config else False)
"
```

### "Approval links don't work"

Make sure the API server is running:
```bash
curl http://localhost:8000/health
```

If not running, start it:
```bash
python3 main.py
```

### "Timeout waiting for approval"

The default timeout is 60 minutes. If you need more time:
```bash
--approval-timeout 180  # 3 hours
```

### "Already invested today"

The bot only invests once per day. To force a re-run:
```bash
rm data/last_investment.txt
```

---

## Security Considerations

### Approval Links

The approval links contain the request ID but no authentication. This means:
- ✅ Anyone with the link can approve/reject
- ⚠️ Don't forward approval emails to others
- ✅ Links expire after the timeout period
- ✅ Each request can only be approved/rejected once

### Production Deployment

For production, you should:
1. Add authentication to approval endpoints
2. Use HTTPS instead of HTTP
3. Deploy API server to a public URL (not localhost)
4. Use environment-specific approval emails

---

## Comparison: With vs Without Approval

### Without Approval (`auto_invest.py`)
- ✅ Fully automated
- ✅ No manual intervention
- ⚠️ Trades execute automatically
- Best for: Hands-off investing

### With Approval (`auto_invest_with_approval.py`)
- ✅ Manual control
- ✅ Review before execution
- ⚠️ Requires checking email
- Best for: Cautious investors, learning phase

---

## Next Steps

1. **Test in paper trading first**
   ```bash
   python3 scripts/auto_invest_with_approval.py \
     --approval-email your@email.com
   ```

2. **Check your email** and try approving a test trade

3. **Monitor for a few cycles** to ensure it works correctly

4. **Switch to live trading** when comfortable

5. **Set up scheduled execution** via cron

---

## FAQ

**Q: Can I approve via email reply?**
A: Not yet, but you can click the links in the email.

**Q: What if I miss the approval window?**
A: The request expires and no trades execute. The bot will try again the next day.

**Q: Can I modify the trades before approving?**
A: No, it's approve or reject. If you want different trades, reject and adjust your strategy parameters.

**Q: How do I see past approval requests?**
A: Check `data/approvals/` directory for JSON files with all requests.

**Q: Can multiple people approve?**
A: Yes, but only the first approval/rejection counts.

---

## Summary

**Setup time:** ~10 minutes

**What you get:**
- ✅ Email notification before every trade
- ✅ Detailed trade summary
- ✅ One-click approval/rejection
- ✅ Complete control over execution
- ✅ Peace of mind

**Perfect for:** Investors who want automation with oversight! 🎯
