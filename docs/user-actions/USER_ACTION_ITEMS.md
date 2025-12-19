# User Action Items - Complete Checklist

Everything you need to do to complete the system setup and deployment.

**UPDATED**: Dec 18, 2025 - Includes all changes through web dashboard, CI/CD, and system analysis

**APPROACH**: Iterative testing - complete each phase, test, then move to next phase

---

## Quick Start Checklist

**Phase 1 - Environment Setup** (15 minutes)
- [ ] Install missing Python dependencies
- [ ] Set up API keys in .env
- [ ] Generate JWT secret
- [ ] Verify database connection

**Phase 2 - Database Setup** (10 minutes)
- [ ] Run migration 002 (ML schema)
- [ ] Run migration 003 (User management)
- [ ] Verify tables created

**Phase 3 - GitHub Setup** (10 minutes)
- [ ] Configure branch protection
- [ ] Test CI workflow
- [ ] Verify PR process

**Phase 4 - Initial Data Collection** (3-6 hours, can run overnight)
- [ ] Collect 13F data
- [ ] Collect price history
- [ ] Generate training data
- [ ] Train initial ML model

**Phase 5 - Testing** (30 minutes)
- [ ] Test authentication system
- [ ] Test daily digest generation
- [ ] Test causality analysis
- [ ] Run all unit tests

**Phase 6 - Automation** (15 minutes)
- [ ] Schedule daily digest cron job
- [ ] Schedule ML retraining
- [ ] Schedule data collection

**Phase 7 - End-to-End Testing** (1 hour)
- [ ] Complete workflow test
- [ ] Verify all integrations
- [ ] Production readiness check

**Phase 8 - Code Quality & Cleanup** (1-2 hours)
- [ ] Run Black formatting on all Python files
- [ ] Address Flake8 linting issues (497 issues to fix)
- [ ] Remove unused imports
- [ ] Fix code quality warnings
- [ ] Verify CI/CD passes all checks

**Phase 9 - Frontend Development** (Optional, 1-2 weeks)
- [ ] Decide on frontend approach (build now vs later)
- [ ] If building: Initialize Next.js project
- [ ] If building: Create authentication pages
- [ ] If building: Build dashboard components
- [ ] If building: Integrate with backend API
- [ ] If building: Deploy to Vercel

---

## CRITICAL: API Keys & Credentials

### Required Immediately

**1. Alpha Vantage API Key** (Already have)
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

## PHASE 1: Environment Setup (15 minutes)

### Step 1.1: Install Updated Python Dependencies

**IMPORTANT**: New dependencies were added after initial document creation.

```bash
cd /path/to/investor-mimic-bot
pip install -r requirements.txt
```

**New dependencies added:**
- `psutil==5.9.6` - System monitoring (fixes CI error)
- `scikit-learn==1.3.2` - ML models
- `redis==5.0.1` - Caching layer
- `bcrypt==4.1.2` - Password hashing
- `pyjwt==2.8.0` - JWT authentication
- `python-multipart==0.0.6` - FastAPI file uploads

**Verify installation:**
```bash
python3 -c "import psutil; import sklearn; import redis; import bcrypt; import jwt; print('All dependencies installed successfully')"
```

### Step 1.2: Create/Update .env File

Create `.env` file in project root with all credentials:

```bash
# Alpaca (Already have)
ALPACA_API_KEY=your_key
ALPACA_SECRET_KEY=your_secret
ALPACA_PAPER=True

# Database (Already have)
DATABASE_URL=postgresql://user:pass@host:port/investorbot

# Alpha Vantage (Required - get from https://www.alphavantage.co/support/#api-key)
ALPHA_VANTAGE_API_KEY=your_key

# Email SMTP (Required - Gmail app password)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@gmail.com
SMTP_PASSWORD=your_app_password
ALERT_EMAIL=your_email@gmail.com

# JWT Secret (Required - generate with: openssl rand -hex 32)
JWT_SECRET_KEY=your_generated_secret_key_here
FRONTEND_URL=http://localhost:3000

# Optional APIs (Recommended)
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

### Step 1.3: Generate JWT Secret Key

```bash
openssl rand -hex 32
```

Copy the output and add to `.env` as `JWT_SECRET_KEY`

### Step 1.4: Test Database Connection

```bash
python3 -c "
from db.connection_pool import get_db_session
with get_db_session() as session:
    result = session.execute('SELECT 1')
    print('✓ Database connection successful')
"
```

**✓ Phase 1 Complete - Environment is set up**

---

## PHASE 2: Database Migrations (10 minutes)

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

### Step 2.3: Verify Migrations
```bash
psql -U postgres -d investorbot -c "\dt"
```

Should show all new tables (30+ tables total).

**Test specific tables:**
```bash
psql -U postgres -d investorbot -c "SELECT COUNT(*) FROM users;"
psql -U postgres -d investorbot -c "SELECT COUNT(*) FROM training_data;"
```

**✓ Phase 2 Complete - Database schema is ready**

---

## PHASE 3: GitHub CI/CD Setup (10 minutes)

### Step 3.1: Configure Branch Protection

**IMPORTANT**: This was added after initial document. Required for automated testing on PRs.

1. **Go to repository settings:**
   ```
   https://github.com/shreyas-chickerur/investor-mimic-bot/settings/branches
   ```

2. **Click "Add rule"**

3. **Branch name pattern:** `main`

4. **Check these boxes:**
   - ✅ Require a pull request before merging
     - Set required approvals: `1`
     - ✅ Dismiss stale approvals when new commits pushed
   - ✅ Require status checks to pass before merging
     - ✅ Require branches to be up to date
     - Search and select: `test` (CI job name)
   - ✅ Require conversation resolution before merging
   - ✅ Include administrators

5. **Click "Create"**

### Step 3.2: Test CI Workflow

Create a test PR to verify CI works:

```bash
git checkout main
git pull
git checkout -b test/ci-verification
echo "# CI Test" >> README.md
git add README.md
git commit -m "test: verify CI workflow"
git push -u origin test/ci-verification
```

Then:
1. Go to GitHub and create PR
2. Watch CI run automatically (~2-5 minutes)
3. Verify all checks pass:
   - ✅ Run linting (Black)
   - ✅ Run linting (Flake8)
   - ✅ Run unit tests
4. Close the test PR (don't merge)
5. Delete the test branch

### Step 3.3: Verify CI Configuration

**Check workflow file:**
```bash
cat .github/workflows/ci.yml
```

**Should include:**
- Triggers on PR to main/develop
- Black formatting check (required)
- Flake8 linting (required)
- Unit tests (required)
- Integration tests (optional)
- Functional tests (optional)

**✓ Phase 3 Complete - CI/CD is configured**

---

## PHASE 4: Initial Data Collection (3-6 hours, run overnight)

### Step 4.1: Collect Historical 13F Data (3-5 hours)
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

### Step 4.1: Collect Historical 13F Data (3-5 hours)
```bash
python3 scripts/load_13f_data.py
```

### Step 4.2: Collect Historical Price Data (1-2 hours)
```bash
python3 scripts/collect_historical_data.py
```

### Step 4.3: Collect News and Fundamentals (30 minutes)
```bash
python3 -c "
from ml.data_collection_pipeline import collect_comprehensive_data
tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'NVDA', 'JPM', 'V', 'WMT']
collect_comprehensive_data(tickers, years=3)
"
```

### Step 4.4: Generate Training Data (1-2 hours)
```bash
python3 -c "
from ml.feature_engineering_pipeline import generate_training_data
tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'NVDA', 'JPM', 'V', 'WMT']
generate_training_data(tickers, years=3)
"
```

### Step 4.5: Train Initial ML Model (30-60 minutes)
```bash
python3 ml/continuous_learning_engine.py
```

### Step 4.6: Verify Data Collection

```bash
psql -U postgres -d investorbot -c "SELECT COUNT(*) FROM holdings;"
psql -U postgres -d investorbot -c "SELECT COUNT(*) FROM price_history;"
psql -U postgres -d investorbot -c "SELECT COUNT(*) FROM training_data;"
psql -U postgres -d investorbot -c "SELECT COUNT(*) FROM model_metrics;"
```

**Expected results:**
- holdings: 1000+ rows
- price_history: 10,000+ rows
- training_data: 10,000+ rows
- model_metrics: 1+ rows

**✓ Phase 4 Complete - Initial data collected and model trained**

---

## PHASE 5: Component Testing (30 minutes)

### Step 5.1: Test Authentication System

```bash
python3 -c "
from api.auth import AuthService
auth = AuthService()
user = auth.register_user('test@example.com', 'password123', 'Test User')
print(f'✓ User created: {user}')
login = auth.login_user('test@example.com', 'password123')
print(f'✓ Login successful: {login[\"access_token\"][:20]}...')
"
```

### Step 5.2: Test Daily Digest Generation

```bash
python3 -c "
from services.monitoring.daily_digest import generate_daily_digest
digest = generate_daily_digest('test@example.com')
print(f'✓ Digest generated with {len(digest.get(\"portfolio_section\", {}).get(\"recommendations\", []))} recommendations')
"
```

### Step 5.3: Test Causality Analysis

```bash
python3 -c "
from services.analysis.stock_causality_analyzer import analyze_stock_recommendation
result = analyze_stock_recommendation('AAPL', 'BUY', 0.85)
print(f'✓ Found {result[\"total_events\"]} events')
print(f'✓ Causal chain has {len(result[\"causal_chain\"])} steps')
"
```

### Step 5.4: Run All Unit Tests

```bash
make test
```

Should see: **58/58 tests passing**

### Step 5.5: Test Linting

```bash
make lint
```

Should pass with no errors.

**✓ Phase 5 Complete - All components tested**

---

## PHASE 6: Automation Setup (15 minutes)

### Step 6.1: Schedule Daily Digest Email (10 AM daily)

**Option A: Cron Job (Recommended)**
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

### Step 6.2: Schedule ML Retraining (Weekly - Sunday 2 AM)

Add to crontab:
```
0 2 * * 0 cd /path/to/investor-mimic-bot && python3 ml/continuous_learning_engine.py >> logs/ml_training.log 2>&1
```

### Step 6.3: Schedule Data Collection (Daily - 6 AM)

Add to crontab:
```
0 6 * * * cd /path/to/investor-mimic-bot && python3 scripts/automated_ml_pipeline.py >> logs/data_collection.log 2>&1
```

### Step 6.4: Verify Cron Jobs

```bash
crontab -l
```

Should show all three scheduled tasks.

**Test cron job manually:**
```bash
cd /path/to/investor-mimic-bot && python3 scripts/send_daily_digest.py
```

**✓ Phase 6 Complete - Automation is configured**

---

## PHASE 7: End-to-End Testing (1 hour)

### Step 7.1: Complete Workflow Test

**Test the entire recommendation pipeline:**

```bash
python3 -c "
print('=== COMPLETE WORKFLOW TEST ===')
print()

# 1. Check database has data
from db.connection_pool import get_db_session
with get_db_session() as session:
    holdings = session.execute('SELECT COUNT(*) FROM holdings').fetchone()[0]
    prices = session.execute('SELECT COUNT(*) FROM price_history').fetchone()[0]
    training = session.execute('SELECT COUNT(*) FROM training_data').fetchone()[0]
    print(f'✓ Database: {holdings} holdings, {prices} prices, {training} training samples')

# 2. Test ML model
from ml.continuous_learning_engine import ContinuousLearningEngine
engine = ContinuousLearningEngine()
X, y = engine.create_training_dataset(lookback_days=365)
print(f'✓ ML Model: {len(X)} samples, {len(X.columns)} features')

# 3. Test authentication
from api.auth import AuthService
auth = AuthService()
try:
    user = auth.register_user('workflow@test.com', 'test123', 'Workflow Test')
    print(f'✓ Auth: User created')
except:
    print(f'✓ Auth: User already exists')

# 4. Test causality analysis
from services.analysis.stock_causality_analyzer import analyze_stock_recommendation
result = analyze_stock_recommendation('AAPL', 'BUY', 0.85)
print(f'✓ Causality: {result[\"total_events\"]} events, {len(result[\"causal_chain\"])} steps')

# 5. Test digest generation
from services.monitoring.daily_digest import generate_daily_digest
digest = generate_daily_digest('workflow@test.com')
recs = len(digest.get('portfolio_section', {}).get('recommendations', []))
print(f'✓ Digest: Generated with {recs} recommendations')

print()
print('=== ALL SYSTEMS OPERATIONAL ===')
"
```

### Step 7.2: Test All Unit Tests

```bash
make test
```

**Expected:** 58/58 tests passing

### Step 7.3: Test Linting

```bash
make lint
```

**Expected:** No errors

### Step 7.4: Test CI/CD Pipeline

Create a test PR:

```bash
git checkout -b test/end-to-end-verification
echo "# End-to-End Test" >> README.md
git add README.md
git commit -m "test: end-to-end verification"
git push -u origin test/end-to-end-verification
```

Verify on GitHub:
1. Create PR
2. All CI checks pass
3. Merge button is enabled
4. Close PR without merging

### Step 7.5: Production Readiness Checklist

**Environment:**
- [ ] All API keys configured in .env
- [ ] JWT secret generated and set
- [ ] Database migrations run successfully
- [ ] All dependencies installed

**Data:**
- [ ] 13F data collected (1000+ holdings)
- [ ] Price history collected (10,000+ rows)
- [ ] Training data generated (10,000+ samples)
- [ ] ML model trained (model_metrics has rows)

**Testing:**
- [ ] All 58 unit tests passing
- [ ] Linting passes with no errors
- [ ] CI/CD pipeline working
- [ ] Authentication system tested
- [ ] Daily digest generation tested
- [ ] Causality analysis tested

**Automation:**
- [ ] Daily digest cron job scheduled
- [ ] ML retraining cron job scheduled
- [ ] Data collection cron job scheduled

**GitHub:**
- [ ] Branch protection configured
- [ ] CI workflow tested
- [ ] PR process verified

### Step 7.6: Monitor First 24 Hours

**Check logs regularly:**
```bash
# Daily digest log
tail -f logs/digest.log

# Application log
tail -f logs/app.log

# Data collection log
tail -f logs/data_collection.log
```

**Verify cron jobs run:**
```bash
grep CRON /var/log/syslog | tail -20
```

**Check database growth:**
```bash
psql -U postgres -d investorbot -c "SELECT 
  'holdings' as table_name, COUNT(*) as count FROM holdings
UNION ALL SELECT 'price_history', COUNT(*) FROM price_history
UNION ALL SELECT 'training_data', COUNT(*) FROM training_data;"
```

**✓ Phase 7 Complete - System is production ready!**

---

## PHASE 8: Code Quality & Cleanup (1-2 hours)

### Step 8.1: Run Black Formatting

**IMPORTANT**: Always run before committing to avoid CI failures.

```bash
python3 -m black services/ scripts/ backtesting/ ml/ tests/ utils/ api/ --line-length=120
```

**Expected**: "All done! ✨ 🍰 ✨"

### Step 8.2: Check Flake8 Linting

```bash
python3 -m flake8 services/ scripts/ backtesting/ ml/ utils/ api/ --max-line-length=120 --ignore=E203,W503 --count
```

**Current status**: 497 issues (mostly unused imports)

### Step 8.3: Fix Major Linting Issues

**Priority fixes:**
1. Remove unused imports
2. Fix undefined names (F821 errors)
3. Fix f-strings missing placeholders
4. Remove trailing whitespace
5. Fix lines too long (>120 characters)

**Example fixes:**
```bash
# Remove unused import
# Before: from typing import List, Dict, Optional
# After: from typing import Dict  # Only keep what's used

# Fix undefined name
# Before: def get_items() -> List[str]:
# After: from typing import List
#        def get_items() -> List[str]:
```

### Step 8.4: Verify CI/CD Passes

Create test PR to verify:
```bash
git checkout -b test/code-quality-check
echo "# Code Quality Check" >> README.md
git add README.md
git commit -m "test: verify code quality checks pass"
git push -u origin test/code-quality-check
```

Verify on GitHub:
- ✅ Black formatting passes
- ✅ Flake8 linting passes
- ✅ Unit tests pass (58 tests)

**✓ Phase 8 Complete - Code quality improved**

---

## PHASE 9: Frontend Development (Optional, 1-2 weeks)

### Decision Point: Build Frontend Now or Later?

**Option A: Build Now (Recommended if you want full system)**
- Complete user experience
- Visual portfolio tracking
- Interactive recommendations
- Real-time updates
- Time: 1-2 weeks

**Option B: Build Later (Recommended if you want to test backend first)**
- Focus on backend functionality
- Test with command-line tools
- Add frontend when backend is stable
- Time: Can defer indefinitely

### If Building Frontend Now:

#### Step 9.1: Initialize Next.js Project

```bash
cd /path/to/investor-mimic-bot
npx create-next-app@latest frontend --typescript --tailwind --app --no-src-dir
cd frontend
npm install
```

#### Step 9.2: Install Additional Dependencies

```bash
npm install @radix-ui/react-* lucide-react recharts swr next-auth
npm install -D @types/node @types/react
```

#### Step 9.3: Set Up Authentication

- Configure NextAuth.js
- Create login/register pages
- Set up JWT token handling
- Test authentication flow

#### Step 9.4: Build Dashboard Pages

- Dashboard home (portfolio overview)
- Portfolio view (holdings, charts)
- Recommendations (with flow charts)
- Settings (profile, API keys)
- Trade history

#### Step 9.5: Integrate with Backend

- Set up API client
- Connect to FastAPI backend
- Test all endpoints
- Handle errors gracefully

#### Step 9.6: Deploy Frontend

```bash
npm run build
vercel deploy
```

**✓ Phase 9 Complete - Frontend deployed**

---

## Post-Deployment Monitoring

### Daily Checks
- [ ] Check logs/app.log for errors
- [ ] Check logs/digest.log for email send status
- [ ] Verify daily digest email received
- [ ] Check Alpaca account balance
- [ ] Review any failed trades

### Weekly Checks
- [ ] Review ML model performance (model_metrics table)
- [ ] Check trade_performance for win rate
- [ ] Review database size and cleanup old data
- [ ] Check system resource usage
- [ ] Verify all cron jobs ran successfully

### Monthly Checks
- [ ] Review overall strategy performance
- [ ] Analyze user activity (when dashboard live)
- [ ] Update dependencies: `pip list --outdated`
- [ ] Review and rotate API keys if needed
- [ ] Check backup integrity
- [ ] Run security audit
- [ ] Review and address Flake8 linting issues
- [ ] Update documentation with new features
- [ ] Review CHANGELOG.md and update
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
