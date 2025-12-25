# Email Notification System

## Overview

The trading system sends automated email notifications to keep you informed about daily trading activity, critical alerts, and system errors. All emails are sent via SMTP (Gmail by default) and formatted in HTML for easy reading.

## Configuration

### Required Environment Variables

Add these to your `.env` file:

```bash
# Email Configuration
SENDER_EMAIL=your-email@gmail.com
SENDER_PASSWORD=your-app-password  # Gmail App Password, not regular password
RECIPIENT_EMAIL=where-to-receive@email.com

# Optional (defaults shown)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
```

### Gmail App Password Setup

1. Enable 2-Factor Authentication on your Gmail account
2. Go to Google Account → Security → 2-Step Verification → App passwords
3. Generate a new app password for "Mail"
4. Use this 16-character password (not your regular Gmail password)

### Disabling Emails

If email credentials are not configured, the system will:
- Log warnings instead of sending emails
- Continue operating normally
- Store all data in logs for manual review

---

## Email Types

### 1. Daily Trading Summary 📊

**Sent:** After every successful trading day execution  
**Frequency:** Once per day (after market close execution)

**Contains:**
- **Portfolio Overview**
  - Total portfolio value
  - Available cash balance
  
- **Trades Executed**
  - Count of buys and sells
  - Detailed table with:
    - Action (BUY/SELL)
    - Symbol
    - Number of shares
    - Execution price
    - Strategy that generated the signal
  
- **Current Positions**
  - Top 10 positions by value
  - Entry price vs current price
  - Unrealized P&L for each position
  
- **Warnings/Errors** (if any)
  - Data validation issues
  - Rejected signals
  - Risk management interventions

**Subject Line:**  
`📊 Daily Trading Summary - YYYY-MM-DD`

---

### 2. Broker Reconciliation Failure 🚨

**Sent:** When local database doesn't match Alpaca broker state  
**Frequency:** Immediately when mismatch detected (before trading)

**Triggers:**
- Position quantity mismatch (>1 share difference)
- Position price mismatch (>1% difference)
- Cash balance mismatch (>$10 difference)
- Extra positions in broker not tracked locally
- Missing positions in broker that should exist

**System Response:**
- Enters **PAUSED** state
- Blocks all trading until resolved
- Sends critical alert email
- Logs detailed discrepancies

**Contains:**
- List of specific discrepancies
- Current broker state
- Current local database state
- Reconciliation timestamp
- Instructions for resolution
- Warning not to trade manually

**Subject Line:**  
`🚨 ALERT: Trading System Paused - Reconciliation Failure`

**Resolution Required:**
1. Review GitHub Actions logs
2. Check Alpaca dashboard
3. Identify source of discrepancy
4. Run `make verify-positions` to check status
5. System auto-resumes after successful reconciliation

---

### 3. System Error Alerts 🚨

**Sent:** When critical errors occur during execution  
**Frequency:** Immediately when error detected

**Common Triggers:**
- Failed to load market data from Alpaca
- Database connection failures
- Unhandled exceptions during execution
- API rate limit errors
- Network connectivity issues

**Contains:**
- Error message summary
- Full stack trace (for debugging)
- Timestamp of error
- Link to GitHub Actions logs
- Recommended actions

**Subject Line:**  
`🚨 Trading System Error - YYYY-MM-DD`

---

## Email Delivery

### Timing
- **Daily Summary:** Sent after 4:15 PM ET execution completes (~4:20 PM ET)
- **Reconciliation Alerts:** Sent immediately when mismatch detected
- **Error Alerts:** Sent immediately when error occurs

### Reliability
- Emails are sent synchronously (execution waits for confirmation)
- Failed email sends are logged but don't block trading
- SMTP errors are caught and logged for debugging

### Testing
Run the test suite to verify email configuration:
```bash
make test
# Look for: tests/test_email_alert.py
```

---

## Monitoring Best Practices

### Daily Routine
1. **Check Daily Summary** - Review trades and positions each evening
2. **Monitor P&L** - Track unrealized gains/losses
3. **Review Warnings** - Address any data quality issues

### Alert Response
1. **Reconciliation Failures** - Investigate immediately, system is paused
2. **System Errors** - Check logs, may require manual intervention
3. **Repeated Errors** - May indicate API issues or configuration problems

### What to Watch For
- ✅ Consistent daily summaries = system running smoothly
- ⚠️ Missing daily summary = execution may have failed
- 🚨 Reconciliation alerts = immediate attention required
- 🚨 Repeated error alerts = systemic issue needs fixing

---

## Troubleshooting

### Not Receiving Emails

**Check Configuration:**
```bash
make check-secrets
```

**Common Issues:**
1. Gmail App Password not set (using regular password)
2. 2FA not enabled on Gmail account
3. SMTP blocked by firewall
4. Incorrect recipient email address
5. Emails going to spam folder

**Debug Steps:**
1. Check logs: `make logs`
2. Verify environment variables are loaded
3. Test SMTP connection manually
4. Check Gmail "Less secure app access" settings (deprecated)
5. Verify App Password is 16 characters, no spaces

### Emails Going to Spam

**Whitelist the sender:**
1. Add sender email to contacts
2. Mark as "Not Spam" in Gmail
3. Create filter to always inbox

**Check email content:**
- HTML emails may trigger spam filters
- Ensure sender domain matches SMTP server

---

## Sample Emails

See `docs/sample_emails/` for example email templates:
- `daily_summary_sample.html` - Normal trading day
- `reconciliation_alert_sample.html` - Broker mismatch
- `error_alert_sample.html` - System error

---

## Security Notes

⚠️ **Never commit email credentials to Git**
- Use `.env` file (already in `.gitignore`)
- Use GitHub Secrets for CI/CD
- Rotate App Passwords periodically

⚠️ **Email contains sensitive information**
- Portfolio values
- Trading activity
- Position details
- Use secure email provider
- Enable 2FA on email account

---

## Implementation Details

**Source Code:**
- `src/email_notifier.py` - Email notification class
- `src/multi_strategy_main.py` - Daily summary integration
- `src/broker_reconciler.py` - Reconciliation alerts
- `tests/test_email_alert.py` - Email tests

**Dependencies:**
- `smtplib` - SMTP protocol (Python standard library)
- `email.mime` - Email formatting (Python standard library)

**No external packages required** - uses Python standard library only.
