# 📧 Daily Digest Email Guide

**Morning Brew Style Investment Digest**

---

## 🎯 Overview

The Daily Digest system sends personalized investment emails to users every morning at 10 AM, featuring:

1. **Market Overview** - Major indices, top headlines
2. **Your Portfolio** - Performance, holdings, personalized recommendations
3. **Holdings News** - News specific to your investments

---

## ✨ Features

### **Market Section**
- 📊 Major indices (S&P 500, NASDAQ, Dow Jones) with daily changes
- 📰 Top 5 market headlines with sentiment analysis
- 🎯 Sector performance overview

### **Portfolio Section**
- 💼 Total portfolio value and gain/loss
- 📈 Top 5 holdings with performance
- 🎯 Today's personalized recommendations (BUY/SELL)
- 📢 News about your specific holdings

### **Email Design**
- Clean, professional Morning Brew style
- Mobile-responsive
- Color-coded sentiment (green = positive, red = negative)
- Succinct and scannable format

---

## 🚀 Setup

### **1. Configure Email Settings**

Add to your `.env` file:

```bash
# SMTP Configuration (Gmail example)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@gmail.com
SMTP_PASSWORD=your_app_password
ALERT_EMAIL=your_email@gmail.com

# API Keys
ALPHA_VANTAGE_API_KEY=your_key
```

**Gmail App Password:**
1. Go to Google Account settings
2. Security → 2-Step Verification → App passwords
3. Generate password for "Mail"
4. Use this as `SMTP_PASSWORD`

### **2. Test Email Send**

```bash
# Send digest manually
make send-digest

# Or directly
python3 scripts/send_daily_digest.py
```

### **3. Schedule Daily Send (10 AM)**

**Option A: Cron Job (Recommended)**

```bash
# Edit crontab
crontab -e

# Add this line (sends at 10 AM daily)
0 10 * * * cd /path/to/investor-mimic-bot && python3 scripts/send_daily_digest.py >> logs/digest.log 2>&1
```

**Option B: System Service**

Create `/etc/systemd/system/daily-digest.service`:

```ini
[Unit]
Description=Daily Investment Digest
After=network.target

[Service]
Type=oneshot
User=your_user
WorkingDirectory=/path/to/investor-mimic-bot
ExecStart=/usr/bin/python3 scripts/send_daily_digest.py
```

Create `/etc/systemd/system/daily-digest.timer`:

```ini
[Unit]
Description=Daily Investment Digest Timer

[Timer]
OnCalendar=*-*-* 10:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

Enable:
```bash
sudo systemctl enable daily-digest.timer
sudo systemctl start daily-digest.timer
```

---

## 📧 Email Content

### **Example Email Structure**

```
┌─────────────────────────────────────┐
│  📈 Daily Investment Digest         │
│  Wednesday, December 18, 2025       │
└─────────────────────────────────────┘

Good morning, John! ☀️

─────────────────────────────────────
📊 Market Overview
─────────────────────────────────────
S&P 500        ↑ 0.45%
NASDAQ         ↑ 0.82%
Dow Jones      ↑ 0.23%

─────────────────────────────────────
📰 Top Headlines
─────────────────────────────────────
• Fed Signals Rate Cut in 2024
  Reuters • Bullish

• Tech Stocks Rally on AI Optimism
  Bloomberg • Bullish

• Oil Prices Surge on Supply Concerns
  CNBC • Neutral

─────────────────────────────────────
💼 Your Portfolio
─────────────────────────────────────
Total Value:     $125,450.00
Total Gain/Loss: +$12,450.00 (+11.02%)

Current Holdings:
AAPL    $45,200    +8.5%
MSFT    $32,100    +12.3%
GOOGL   $28,900    +9.8%

─────────────────────────────────────
🎯 Today's Recommendations
─────────────────────────────────────
🟢 NVDA - BUY
Strong momentum, positive sentiment
Signal Score: 0.85

🔴 XOM - SELL
Weakening fundamentals, negative news
Signal Score: 0.72

─────────────────────────────────────
📢 News About Your Holdings
─────────────────────────────────────
AAPL • Bullish
Apple Announces New AI Features
Strong product lineup expected...

MSFT • Neutral
Microsoft Cloud Revenue Beats Estimates
Azure growth continues...
```

---

## 🔧 Customization

### **Change Send Time**

Edit cron job or timer to different time:
```bash
# 8 AM instead of 10 AM
0 8 * * * cd /path/to/investor-mimic-bot && python3 scripts/send_daily_digest.py
```

### **Customize Content**

Edit `services/monitoring/daily_digest.py`:

```python
# Change number of headlines
headlines = self._get_top_headlines()[:5]  # Change 5 to desired number

# Change number of holdings shown
for holding in holdings[:5]:  # Change 5 to desired number

# Change number of recommendations
LIMIT 5  # Change in SQL query
```

### **Customize Email Design**

Edit `services/monitoring/daily_digest_email_template.py`:

```python
# Change colors
action_color = "#27ae60"  # Green for BUY
action_color = "#e74c3c"  # Red for SELL

# Change fonts
font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI'...

# Change layout
# Modify HTML structure in get_daily_digest_email_html()
```

---

## 📊 Data Sources

### **Market Data**
- Alpha Vantage API (major indices, quotes)
- Rate limit: 5 calls/minute (free tier)

### **News Headlines**
- Alpha Vantage News Sentiment API
- Top market news with sentiment analysis
- Rate limit: 5 calls/minute (free tier)

### **Portfolio Data**
- Database: `holdings` table
- Real-time portfolio values
- Gain/loss calculations

### **Recommendations**
- Database: `trade_recommendations` table
- Generated by ML models
- Signal scores and reasoning

---

## 🔍 Monitoring

### **Check Email Logs**

```bash
# View digest logs
tail -f logs/digest.log

# Check for errors
grep ERROR logs/app.log | grep digest
```

### **Verify Emails Sent**

```sql
-- Check last digest send
SELECT * FROM system_logs 
WHERE event_type = 'daily_digest_sent' 
ORDER BY created_at DESC 
LIMIT 10;
```

### **Test Email Content**

```python
# Generate digest without sending
from services.monitoring.daily_digest import generate_daily_digest

digest = generate_daily_digest("user@example.com")
print(digest)
```

---

## 🐛 Troubleshooting

### **Emails Not Sending**

1. **Check SMTP credentials**
   ```bash
   python3 -c "
   from utils.environment import env
   print(f'SMTP Server: {env.get(\"SMTP_SERVER\")}')
   print(f'SMTP Username: {env.get(\"SMTP_USERNAME\")}')
   print(f'Password set: {bool(env.get(\"SMTP_PASSWORD\"))}')
   "
   ```

2. **Test SMTP connection**
   ```python
   import smtplib
   from utils.environment import env
   
   server = smtplib.SMTP(env.get('SMTP_SERVER'), 587)
   server.starttls()
   server.login(env.get('SMTP_USERNAME'), env.get('SMTP_PASSWORD'))
   print("✓ SMTP connection successful")
   ```

3. **Check Gmail settings**
   - Enable "Less secure app access" OR
   - Use App Password (recommended)
   - Check for blocked sign-in attempts

### **No Market Data**

1. **Check API key**
   ```bash
   python3 -c "
   from utils.environment import env
   print(f'Alpha Vantage Key: {env.get(\"ALPHA_VANTAGE_API_KEY\")[:10]}...')
   "
   ```

2. **Test API connection**
   ```python
   import requests
   from utils.environment import env
   
   url = "https://www.alphavantage.co/query"
   params = {
       "function": "GLOBAL_QUOTE",
       "symbol": "SPY",
       "apikey": env.get("ALPHA_VANTAGE_API_KEY")
   }
   
   response = requests.get(url, params=params)
   print(response.json())
   ```

### **No Portfolio Data**

1. **Check database connection**
   ```bash
   python3 -c "
   from db.connection_pool import get_db_session
   with get_db_session() as s:
       r = s.execute('SELECT COUNT(*) FROM holdings')
       print(f'Holdings count: {r.fetchone()[0]}')
   "
   ```

2. **Verify user email**
   ```sql
   SELECT * FROM investors WHERE email = 'user@example.com';
   ```

---

## 📈 Performance

### **Email Generation Time**
- Market data: ~2-3 seconds
- Portfolio data: ~1 second
- Email generation: <1 second
- **Total: ~5 seconds per user**

### **API Rate Limits**
- Alpha Vantage: 5 calls/minute (free)
- With 10 users: ~2 minutes total
- With 100 users: ~20 minutes total

### **Optimization Tips**
1. Cache market data (same for all users)
2. Batch database queries
3. Use async for API calls
4. Upgrade to paid API tier for more users

---

## ✅ Best Practices

1. **Send at Consistent Time**
   - 10 AM recommended (after market open)
   - Before lunch for maximum engagement

2. **Keep Content Concise**
   - Top 5 headlines only
   - Top 5 holdings only
   - 3-5 recommendations max

3. **Monitor Engagement**
   - Track open rates
   - Monitor click-through rates
   - Adjust content based on feedback

4. **Handle Failures Gracefully**
   - Log all errors
   - Retry failed sends
   - Alert on critical failures

5. **Respect User Preferences**
   - Allow opt-out
   - Customize frequency
   - Personalize content

---

## 🚀 Future Enhancements

- [ ] User preferences (opt-in/out, frequency)
- [ ] A/B testing different formats
- [ ] Click tracking for engagement
- [ ] Mobile app push notifications
- [ ] Weekly summary emails
- [ ] Performance comparison charts
- [ ] Interactive elements (approve trades via email)

---

## 📝 Summary

**Daily Digest Features:**
- ✅ Morning Brew style formatting
- ✅ Market overview with indices
- ✅ Top news headlines
- ✅ Personalized portfolio section
- ✅ Today's recommendations
- ✅ Holdings-specific news
- ✅ Clean, mobile-responsive design
- ✅ Automated daily sending at 10 AM

**Setup Steps:**
1. Configure SMTP settings in `.env`
2. Test with `make send-digest`
3. Schedule with cron or systemd
4. Monitor logs for issues

**The system is ready to send professional daily digests to all users!** 📧

---

*For issues or questions, check logs in `logs/digest.log` or `logs/app.log`*
