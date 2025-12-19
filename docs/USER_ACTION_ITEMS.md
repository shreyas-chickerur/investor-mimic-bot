# User Action Items - Complete Checklist

Everything you need to do to complete the system setup and deployment.

---

## CRITICAL: API Keys & Credentials

### Required Immediately

**1. Alpha Vantage API Key** (FREE - Required)
- Sign up: https://www.alphavantage.co/support/#api-key
- Free tier: 5 API calls per minute, 500 per day
- Used for: News sentiment, earnings data, fundamentals
- Add to `.env`: `ALPHA_VANTAGE_API_KEY=your_key`

**2. Alpaca API Keys** (Already have)
- Verify in `.env`:
  - `ALPACA_API_KEY=your_key`
  - `ALPACA_SECRET_KEY=your_secret`
  - `ALPACA_PAPER=True` (for testing)

**3. Database Credentials** (Already have)
- Verify in `.env`: `DATABASE_URL=postgresql://user:pass@host:port/db`

**4. JWT Secret Key** (NEW - Required for web dashboard)
- Generate strong secret: `openssl rand -hex 32`
- Add to `.env`: `JWT_SECRET_KEY=your_generated_secret`

**5. Email SMTP Credentials** (Required for daily digest)
- Gmail example:
  - Go to Google Account → Security → 2-Step Verification → App passwords
  - Generate app password
  - Add to `.env`:
    ```
    SMTP_SERVER=smtp.gmail.com
    SMTP_PORT=587
    SMTP_USERNAME=your_email@gmail.com
    SMTP_PASSWORD=your_app_password
    ALERT_EMAIL=your_email@gmail.com
    ```

### Optional (Recommended for Better Data)

**6. Finnhub API Key** (FREE)
- Sign up: https://finnhub.io/register
- Free tier: 60 API calls per minute
- Used for: Additional news sources
- Add to `.env`: `FINNHUB_API_KEY=your_key`

**7. NewsAPI Key** (FREE)
- Sign up: https://newsapi.org/register
- Free tier: 100 requests per day
- Used for: News aggregation
- Add to `.env`: `NEWSAPI_KEY=your_key`

**8. Financial Modeling Prep** ($14/month - Optional)
- Sign up: https://financialmodelingprep.com/developer/docs/
- Comprehensive fundamentals data
- Add to `.env`: `FMP_API_KEY=your_key`

---

## Database Migrations (MUST RUN)

Run these in order:

### 1. ML Training Schema
```bash
psql -U postgres -d investorbot < sql/migrations/002_ml_training_schema.sql
```

Creates tables for:
- investor_performance
- news_articles
- social_sentiment
- fundamentals
- technical_indicators (extended)
- training_data
- model_predictions
- model_metrics
- data_collection_status
- model_retraining_schedule

### 2. User Management Schema
```bash
psql -U postgres -d investorbot < sql/migrations/003_user_management_schema.sql
```

Creates tables for:
- users
- user_settings
- user_sessions
- user_activity
- trade_performance
- portfolio_snapshots
- strategy_performance
- user_notifications
- api_usage
- user_preferences
- user_watchlists
- watchlist_items
- user_feedback
- system_announcements

### Verify Migrations
```bash
psql -U postgres -d investorbot -c "\dt"
```

Should show all new tables.

---

## Configuration Files

### 1. Update .env File

Complete `.env` should have:
```bash
# Alpaca
ALPACA_API_KEY=your_key
ALPACA_SECRET_KEY=your_secret
ALPACA_PAPER=True

# Database
DATABASE_URL=postgresql://user:pass@host:port/investorbot

# Alpha Vantage (Required)
ALPHA_VANTAGE_API_KEY=your_key

# Email (Required for daily digest)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@gmail.com
SMTP_PASSWORD=your_app_password
ALERT_EMAIL=your_email@gmail.com

# JWT (Required for web dashboard)
JWT_SECRET_KEY=your_generated_secret
FRONTEND_URL=http://localhost:3000

# Optional APIs
FINNHUB_API_KEY=your_key
NEWSAPI_KEY=your_key
FMP_API_KEY=your_key

# Slack (Optional)
SLACK_WEBHOOK_URL=your_webhook

# Twilio (Optional)
TWILIO_ACCOUNT_SID=your_sid
TWILIO_AUTH_TOKEN=your_token
TWILIO_FROM_NUMBER=your_number
```

### 2. Verify Python Dependencies

```bash
pip install -r requirements.txt
```

If missing any:
```bash
pip install fastapi uvicorn pyjwt bcrypt python-multipart
```

---

## Initial Data Collection

### 1. Collect Historical 13F Data (3-5 hours)
```bash
python3 scripts/load_13f_data.py
```

### 2. Collect Historical Price Data (1-2 hours)
```bash
python3 scripts/collect_historical_data.py
```

### 3. Collect News and Fundamentals (30 minutes)
```bash
python3 -c "
from ml.data_collection_pipeline import collect_comprehensive_data
tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'NVDA', 'JPM', 'V', 'WMT']
collect_comprehensive_data(tickers, years=3)
"
```

### 4. Generate Training Data (1-2 hours)
```bash
python3 -c "
from ml.feature_engineering_pipeline import generate_training_data
tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'NVDA', 'JPM', 'V', 'WMT']
generate_training_data(tickers, years=3)
"
```

### 5. Train Initial ML Model (30-60 minutes)
```bash
python3 ml/continuous_learning_engine.py
```

---

## Schedule Automated Tasks

### 1. Daily Digest Email (10 AM daily)

**Option A: Cron Job**
```bash
crontab -e
```

Add:
```
0 10 * * * cd /path/to/investor-mimic-bot && python3 scripts/send_daily_digest.py >> logs/digest.log 2>&1
```

**Option B: Systemd Timer**

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

### 2. ML Retraining (Weekly - Sunday 2 AM)

Add to crontab:
```
0 2 * * 0 cd /path/to/investor-mimic-bot && python3 ml/continuous_learning_engine.py >> logs/ml_training.log 2>&1
```

### 3. Data Collection (Daily - 6 AM)

Add to crontab:
```
0 6 * * * cd /path/to/investor-mimic-bot && python3 scripts/automated_ml_pipeline.py >> logs/data_collection.log 2>&1
```

---

## Testing Steps

### 1. Test Authentication System
```bash
python3 -c "
from api.auth import AuthService
auth = AuthService()
user = auth.register_user('test@example.com', 'password123', 'Test User')
print(f'User created: {user}')
login = auth.login_user('test@example.com', 'password123')
print(f'Login successful: {login[\"access_token\"][:20]}...')
"
```

### 2. Test Daily Digest Generation
```bash
python3 scripts/send_daily_digest.py
```

Check `logs/digest.log` for errors.

### 3. Test Causality Analysis
```bash
python3 -c "
from services.analysis.stock_causality_analyzer import analyze_stock_recommendation
result = analyze_stock_recommendation('AAPL', 'BUY', 0.85)
print(f'Found {result[\"total_events\"]} events')
print(f'Causal chain has {len(result[\"causal_chain\"])} steps')
"
```

### 4. Test ML Pipeline
```bash
python3 -c "
from ml.continuous_learning_engine import ContinuousLearningEngine
engine = ContinuousLearningEngine()
X, y = engine.create_training_dataset(lookback_days=365)
print(f'Training data: {len(X)} samples, {len(X.columns)} features')
"
```

### 5. Run All Unit Tests
```bash
make test
```

### 6. Run Linting
```bash
make lint
```

### 7. Test Alpaca Connection
```bash
python3 scripts/test_alpaca_connectivity.py
```

---

## Deployment Steps

### 1. Set Up Production Environment

Create `.env.production`:
```bash
ENVIRONMENT=production
ALPACA_PAPER=False  # CAREFUL: Real money!
# ... other production settings
```

### 2. Set Up Monitoring

**Sentry (Error Tracking)**
```bash
pip install sentry-sdk
```

Add to `.env`:
```bash
SENTRY_DSN=your_sentry_dsn
```

**Health Checks**
```bash
# Add to crontab - check every 5 minutes
*/5 * * * * curl -f http://localhost:8000/health || echo "API down" | mail -s "Alert" your@email.com
```

### 3. Set Up Backups

**Database Backups (Daily)**
```bash
# Add to crontab
0 3 * * * pg_dump investorbot > /backups/investorbot_$(date +\%Y\%m\%d).sql
```

**Keep last 30 days**
```bash
0 4 * * * find /backups -name "investorbot_*.sql" -mtime +30 -delete
```

---

## Web Dashboard Setup (When Ready)

### 1. Install Node.js and npm
```bash
# macOS
brew install node

# Verify
node --version
npm --version
```

### 2. Initialize Frontend (I'll create this when you're ready)
```bash
cd frontend
npm install
npm run dev
```

### 3. Deploy Frontend to Vercel
```bash
npm install -g vercel
vercel login
vercel deploy
```

---

## Monitoring & Maintenance

### Daily Checks
- [ ] Check `logs/app.log` for errors
- [ ] Check `logs/digest.log` for email send status
- [ ] Verify daily digest email received
- [ ] Check Alpaca account balance
- [ ] Review any failed trades

### Weekly Checks
- [ ] Review ML model performance
- [ ] Check `model_metrics` table for accuracy
- [ ] Review `trade_performance` for win rate
- [ ] Check database size and cleanup old data
- [ ] Review system resource usage

### Monthly Checks
- [ ] Review overall strategy performance
- [ ] Analyze user activity (when dashboard live)
- [ ] Update dependencies: `pip list --outdated`
- [ ] Review and rotate API keys if needed
- [ ] Check backup integrity

---

## Troubleshooting

### Issue: API Rate Limits

**Alpha Vantage (5 calls/min)**
- Spread out calls
- Cache aggressively
- Consider paid tier ($50/month for 75 calls/min)

**Solution**: Implemented rate limiting in code

### Issue: Database Connection Pool Exhausted

Check connections:
```bash
psql -U postgres -d investorbot -c "SELECT count(*) FROM pg_stat_activity;"
```

Increase pool size in `db/connection_pool.py`

### Issue: Email Not Sending

Test SMTP:
```bash
python3 -c "
import smtplib
from utils.environment import env
server = smtplib.SMTP(env.get('SMTP_SERVER'), 587)
server.starttls()
server.login(env.get('SMTP_USERNAME'), env.get('SMTP_PASSWORD'))
print('SMTP connection successful')
"
```

### Issue: ML Model Not Training

Check training data:
```bash
psql -U postgres -d investorbot -c "SELECT COUNT(*) FROM training_data;"
```

Need at least 10,000 samples.

---

## Security Checklist

- [ ] Change default JWT_SECRET_KEY
- [ ] Use strong database password
- [ ] Enable SSL for database connection
- [ ] Set up firewall rules
- [ ] Enable 2FA on all accounts (Alpaca, email, etc.)
- [ ] Encrypt Alpaca API keys in database
- [ ] Set up rate limiting on API endpoints
- [ ] Regular security audits
- [ ] Keep dependencies updated
- [ ] Monitor for suspicious activity

---

## Performance Optimization

### Database Indexes
Already created in migrations, but verify:
```bash
psql -U postgres -d investorbot -c "\di"
```

### Redis Caching (Optional but Recommended)
```bash
# Install Redis
brew install redis

# Start Redis
redis-server

# Add to .env
REDIS_URL=redis://localhost:6379
```

### Database Vacuum (Monthly)
```bash
psql -U postgres -d investorbot -c "VACUUM ANALYZE;"
```

---

## Cost Tracking

### Current Costs
- Alpha Vantage: $0 (free tier)
- Alpaca: $0 (paper trading)
- Database: $0 (local) or $15-50/month (hosted)
- Email: $0 (Gmail)

### Optional Upgrades
- Alpha Vantage Premium: $50/month
- Financial Modeling Prep: $14/month
- Polygon.io: $29/month
- Sentry: $26/month
- Vercel Pro: $20/month

**Total: $0-139/month depending on needs**

---

## Support & Resources

### Documentation
- All docs in `docs/` folder
- Architecture guides
- API documentation
- Testing guides

### Logs
- `logs/app.log` - Main application log
- `logs/digest.log` - Email digest log
- `logs/ml_training.log` - ML training log
- `logs/api_error.log` - API errors

### Database Queries

**Check system health**:
```sql
SELECT * FROM data_collection_status ORDER BY last_collection_time DESC;
SELECT * FROM model_metrics WHERE is_production = TRUE;
SELECT COUNT(*) FROM training_data;
SELECT COUNT(*) FROM users;
```

---

## Summary Checklist

### Immediate (Required)
- [ ] Get Alpha Vantage API key
- [ ] Set up Gmail app password for SMTP
- [ ] Generate JWT secret key
- [ ] Run database migrations (002 and 003)
- [ ] Update .env file with all credentials
- [ ] Collect initial historical data
- [ ] Train initial ML model
- [ ] Test daily digest email
- [ ] Schedule cron jobs

### Soon (Recommended)
- [ ] Get Finnhub API key
- [ ] Set up database backups
- [ ] Set up monitoring/alerts
- [ ] Test all system components
- [ ] Review and optimize performance
- [ ] Set up production environment

### Later (Optional)
- [ ] Build web dashboard frontend
- [ ] Set up Redis caching
- [ ] Upgrade to paid API tiers
- [ ] Add more data sources
- [ ] Implement A/B testing
- [ ] Add mobile app

---

**Once you complete the "Immediate" checklist, the system will be fully operational!**

Let me know when you've completed these items and I'll proceed with comprehensive testing and optimization.
