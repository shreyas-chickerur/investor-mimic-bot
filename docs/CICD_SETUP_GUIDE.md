# 🚀 CI/CD Pipeline Setup Guide - Investor Mimic Bot

**Comprehensive Project Documentation for CI/CD Implementation**

This document provides all necessary information to set up a complete CI/CD pipeline for the Investor Mimic Bot project.

---

## 📋 Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture & Technology Stack](#architecture--technology-stack)
3. [Project Structure](#project-structure)
4. [Dependencies & Requirements](#dependencies--requirements)
5. [Environment Configuration](#environment-configuration)
6. [Testing Strategy](#testing-strategy)
7. [Build & Deployment Process](#build--deployment-process)
8. [Current CI/CD Setup](#current-cicd-setup)
9. [CI/CD Pipeline Requirements](#cicd-pipeline-requirements)
10. [Security & Secrets Management](#security--secrets-management)
11. [Monitoring & Alerts](#monitoring--alerts)

---

## 📖 Project Overview

**Project Name:** Investor Mimic Bot  
**Type:** AI-Powered Investment System  
**Language:** Python 3.8+  
**Repository:** https://github.com/shreyas-chickerur/investor-mimic-bot

### Purpose
Automated investment system that analyzes stocks using 8 factors (13F filings, news sentiment, insider trading, technical indicators, etc.) and provides trade recommendations with an interactive approval workflow.

### Key Features
- 8-factor analysis engine
- Paper trading mode for safe testing
- Real-time data fetching (Alpaca API, Alpha Vantage)
- ML-based factor weight optimization
- Email approval workflow
- Risk management (stop-loss, position sizing)
- Database-backed (PostgreSQL)

---

## 🏗️ Architecture & Technology Stack

### Backend
- **Language:** Python 3.8
- **Framework:** FastAPI (for API endpoints)
- **Database:** PostgreSQL 13+
- **Cache:** Redis (optional, falls back to memory)
- **ML Libraries:** scikit-learn, pandas, numpy

### External APIs
- **Alpaca Markets API** - Trading and market data
- **Alpha Vantage API** - News sentiment and quotes
- **SEC EDGAR** - 13F filings data

### Infrastructure
- **Async Processing:** asyncio, aiohttp
- **Connection Pooling:** SQLAlchemy with QueuePool
- **Rate Limiting:** Token bucket algorithm
- **Caching:** Redis + in-memory fallback
- **Monitoring:** psutil, custom metrics
- **Logging:** Structured logging with DB persistence

---

## 📁 Project Structure

```
investor-mimic-bot/
├── .github/
│   └── workflows/
│       ├── ci.yml              # Current CI workflow
│       └── deploy.yml          # Current deployment workflow
├── backtesting/
│   ├── backtest_engine.py
│   └── run_optimized_backtest.py
├── config/
│   ├── environments/
│   │   ├── .env.development
│   │   ├── .env.staging
│   │   └── .env.production
│   ├── investors.py
│   └── settings.py             # Pydantic settings
├── db/
│   ├── base.py
│   ├── connection_pool.py
│   └── models.py
├── docs/
│   ├── SYSTEM_OVERVIEW.md
│   ├── FUTURE_ENHANCEMENTS.md
│   └── FINAL_IMPLEMENTATION_SUMMARY.md
├── logs/                       # Log files (gitignored)
├── ml/
│   ├── adaptive_learning_engine.py
│   └── ensemble_models.py
├── scripts/
│   ├── cli.py                  # CLI tool
│   ├── main.py                 # Main entry point
│   └── setup_cron.sh
├── services/
│   ├── approval/
│   ├── execution/
│   ├── market/
│   ├── news/
│   ├── portfolio/
│   ├── risk/
│   ├── sec/
│   ├── strategy/
│   ├── technical/
│   └── paper_trading.py
├── sql/
│   └── migrations/
│       └── 001_add_indexes.sql
├── tests/
│   ├── test_integration.py
│   ├── test_advanced_features.py
│   └── test_approval_integration.py
├── utils/
│   ├── api_client.py
│   ├── async_data_fetcher.py
│   ├── cache.py
│   ├── data_quality.py
│   ├── enhanced_logging.py
│   ├── environment.py
│   ├── error_handler.py
│   ├── health_check.py
│   ├── monitoring.py
│   ├── notifications.py
│   ├── profiling.py
│   ├── rate_limiter.py
│   └── validators.py
├── .env.example
├── .gitignore
├── Makefile
├── README.md
├── requirements.txt
├── requirements-dev.txt
└── pyproject.toml
```

---

## 📦 Dependencies & Requirements

### Python Version
- **Required:** Python 3.8+
- **Recommended:** Python 3.8 (tested and verified)

### Core Dependencies (requirements.txt)
```
alpaca-py>=0.8.2
requests>=2.31.0
pandas>=2.0.0
numpy>=1.24.0
scikit-learn>=1.3.0
sqlalchemy>=2.0.0
psycopg2-binary>=2.9.0
redis>=4.5.0
aiohttp>=3.8.0
fastapi>=0.100.0
uvicorn>=0.23.0
pydantic>=2.0.0
python-dotenv>=1.0.0
click>=8.1.0
```

### Development Dependencies (requirements-dev.txt)
```
pytest>=7.4.0
pytest-cov>=4.1.0
pytest-asyncio>=0.21.0
black>=23.7.0
flake8>=6.1.0
mypy>=1.5.0
pre-commit>=3.3.0
```

### System Dependencies
- PostgreSQL 13+
- Redis 6+ (optional)
- Git

---

## 🔧 Environment Configuration

### Environment Variables Required

#### Trading APIs (Required)
```bash
ALPACA_API_KEY=your_api_key
ALPACA_SECRET_KEY=your_secret_key
ALPACA_PAPER=True                    # True for paper trading, False for live
ALPACA_BASE_URL=https://paper-api.alpaca.markets
```

#### Database (Required)
```bash
DATABASE_URL=postgresql://user:password@host:5432/dbname
```

#### Optional Services
```bash
# Alpha Vantage (for news sentiment)
ALPHA_VANTAGE_API_KEY=your_key

# Email Notifications
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@gmail.com
SMTP_PASSWORD=your_password
ALERT_EMAIL=alerts@example.com

# Slack Notifications
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...

# Twilio SMS
TWILIO_ACCOUNT_SID=your_sid
TWILIO_AUTH_TOKEN=your_token
TWILIO_PHONE_NUMBER=+1234567890

# Telegram
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=your_chat_id

# Redis Cache
REDIS_URL=redis://localhost:6379/0
```

#### Application Settings
```bash
ENVIRONMENT=development              # development, staging, production
LOG_LEVEL=INFO
PAPER_TRADING=True
MAX_POSITIONS=10
REBALANCE_FREQUENCY=10
SIGNAL_THRESHOLD=0.6
STOP_LOSS_PCT=0.20
```

### Environment Files
- `.env.development` - Development environment
- `.env.staging` - Staging environment
- `.env.production` - Production environment

---

## 🧪 Testing Strategy

### Test Types

#### 1. Unit Tests
- Location: `tests/`
- Framework: pytest
- Coverage target: 80%+

#### 2. Integration Tests
- File: `tests/test_integration.py`
- Tests: Cache, validation, paper trading, database, end-to-end workflows

#### 3. Linting & Code Quality
- **Black:** Code formatting (line length: 120)
- **Flake8:** Linting (max line length: 120, ignore E203, W503)
- **Mypy:** Type checking (optional, not enforced yet)

### Test Commands

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=services --cov=backtesting --cov=ml --cov-report=xml

# Run specific test file
pytest tests/test_integration.py -v

# Run linting
black --check services/ scripts/ backtesting/ ml/ tests/ --line-length=120
flake8 services/ scripts/ backtesting/ ml/ --max-line-length=120 --ignore=E203,W503

# Run type checking (optional)
mypy services/ ml/ utils/
```

### Makefile Commands
```bash
make install          # Install dependencies
make test             # Run tests
make lint             # Run linting
make format           # Format code
make run-daily        # Run daily workflow
make backtest-optimized  # Run backtest
```

---

## 🚀 Build & Deployment Process

### Build Steps

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set Up Environment**
   ```bash
   cp config/environments/.env.{environment} .env
   ```

3. **Initialize Database**
   ```bash
   psql -U postgres -d investorbot < sql/migrations/001_add_indexes.sql
   ```

4. **Verify Configuration**
   ```bash
   python scripts/cli.py validate-config
   ```

5. **Run Tests**
   ```bash
   pytest tests/ -v
   ```

### Deployment Environments

#### Development
- **Purpose:** Local development and testing
- **Database:** Local PostgreSQL
- **Trading:** Paper trading only
- **Branch:** Any feature branch

#### Staging
- **Purpose:** Pre-production testing
- **Database:** Staging PostgreSQL instance
- **Trading:** Paper trading only
- **Branch:** develop

#### Production
- **Purpose:** Live trading (use with caution)
- **Database:** Production PostgreSQL instance
- **Trading:** Can be live or paper (configured via ALPACA_PAPER)
- **Branch:** main

### Deployment Process

1. **Code pushed to branch**
2. **CI runs tests and linting**
3. **If tests pass:**
   - Development: Auto-deploy to dev environment
   - Staging: Auto-deploy to staging on merge to develop
   - Production: Manual approval required, deploy on merge to main

4. **Post-deployment:**
   - Run health checks
   - Verify database connectivity
   - Check API connections
   - Monitor logs

---

## 🔄 Current CI/CD Setup

### GitHub Actions Workflows

#### CI Workflow (`.github/workflows/ci.yml`)
**Triggers:** Push to main/develop, Pull requests

**Steps:**
1. Checkout code
2. Set up Python 3.8
3. Cache dependencies
4. Install dependencies
5. Run linting (black, flake8)
6. Run tests with coverage
7. Upload coverage to Codecov

**Services:**
- PostgreSQL (for integration tests)

#### Deploy Workflow (`.github/workflows/deploy.yml`)
**Triggers:** Push to main, Tags (v*)

**Steps:**
1. Checkout code
2. Set up Python 3.8
3. Install dependencies
4. Run tests
5. Build Docker image (placeholder)
6. Deploy to production (placeholder)

---

## 🎯 CI/CD Pipeline Requirements

### What the Pipeline Should Do

#### On Every Push/PR:
1. ✅ Install dependencies
2. ✅ Run linting (black, flake8)
3. ✅ Run type checking (mypy - optional)
4. ✅ Run unit tests
5. ✅ Run integration tests
6. ✅ Generate coverage report
7. ✅ Check code quality metrics

#### On Merge to Develop (Staging):
1. ✅ All CI checks pass
2. ✅ Build application
3. ✅ Deploy to staging environment
4. ✅ Run smoke tests
5. ✅ Notify team (Slack/Email)

#### On Merge to Main (Production):
1. ✅ All CI checks pass
2. ✅ Require manual approval
3. ✅ Build application
4. ✅ Run database migrations
5. ✅ Deploy to production
6. ✅ Run health checks
7. ✅ Monitor for errors
8. ✅ Notify team

#### Scheduled Jobs:
1. ✅ Daily data fetch (13F filings)
2. ✅ Daily backtest validation
3. ✅ Weekly dependency updates
4. ✅ Monthly security scans

### Pipeline Features Needed

#### Build & Test
- [x] Parallel test execution
- [x] Test result caching
- [x] Coverage reporting
- [ ] Performance benchmarking
- [ ] Security scanning (Snyk, Bandit)

#### Deployment
- [ ] Blue-green deployment
- [ ] Rollback capability
- [ ] Database migration automation
- [ ] Environment-specific configurations
- [ ] Secrets management (AWS Secrets Manager, Vault)

#### Monitoring
- [ ] Deployment notifications
- [ ] Error tracking (Sentry)
- [ ] Performance monitoring
- [ ] Log aggregation
- [ ] Health check endpoints

---

## 🔐 Security & Secrets Management

### Secrets Required

#### GitHub Secrets (for CI/CD)
```
ALPACA_API_KEY
ALPACA_SECRET_KEY
DATABASE_URL_DEV
DATABASE_URL_STAGING
DATABASE_URL_PROD
ALPHA_VANTAGE_API_KEY
SMTP_PASSWORD
SLACK_WEBHOOK_URL
CODECOV_TOKEN (optional)
```

### Security Best Practices

1. **Never commit secrets to repository**
   - Use `.env` files (gitignored)
   - Use GitHub Secrets for CI/CD
   - Use environment-specific secret managers

2. **API Key Rotation**
   - Rotate keys quarterly
   - Use separate keys for dev/staging/prod

3. **Database Security**
   - Use strong passwords
   - Enable SSL connections
   - Restrict network access
   - Regular backups

4. **Code Security**
   - Run security scans (Bandit)
   - Keep dependencies updated
   - Review dependency vulnerabilities

---

## 📊 Monitoring & Alerts

### Health Checks

#### Endpoint: `/health`
Returns system health status:
```json
{
  "status": "healthy",
  "components": {
    "database": {"status": "healthy"},
    "cache": {"status": "healthy"},
    "apis": {"status": "healthy"}
  }
}
```

#### CLI Command
```bash
python scripts/cli.py status
```

### Monitoring Metrics

1. **System Health**
   - CPU usage
   - Memory usage
   - Disk usage
   - Database connections

2. **Application Metrics**
   - API response times
   - Cache hit rate
   - Trade execution success rate
   - Factor score calculations

3. **Business Metrics**
   - Portfolio value
   - Daily P&L
   - Number of positions
   - Trade frequency

### Alert Channels

- **Slack:** Real-time notifications
- **Email:** Daily summaries, critical alerts
- **SMS:** Critical failures only
- **Telegram:** Trade confirmations

---

## 🛠️ CI/CD Implementation Checklist

### Phase 1: Basic CI/CD
- [x] GitHub Actions workflows created
- [x] Automated testing on PR
- [x] Code quality checks (linting)
- [ ] Coverage reporting integrated
- [ ] Branch protection rules

### Phase 2: Deployment Automation
- [ ] Staging environment setup
- [ ] Production environment setup
- [ ] Automated deployment to staging
- [ ] Manual approval for production
- [ ] Rollback mechanism

### Phase 3: Advanced Features
- [ ] Database migration automation
- [ ] Blue-green deployment
- [ ] Canary releases
- [ ] Performance testing
- [ ] Security scanning

### Phase 4: Monitoring & Observability
- [ ] Error tracking (Sentry)
- [ ] Log aggregation (ELK, CloudWatch)
- [ ] Performance monitoring (Datadog, New Relic)
- [ ] Custom dashboards
- [ ] Alert rules configured

---

## 📝 Additional Notes

### Important Considerations

1. **Paper Trading First**
   - Always test in paper trading mode
   - Validate all changes thoroughly
   - Monitor for at least 1 week before live trading

2. **Database Migrations**
   - Always backup before migrations
   - Test migrations in staging first
   - Have rollback scripts ready

3. **API Rate Limits**
   - Alpaca: 200 requests/minute
   - Alpha Vantage: 5 requests/minute (free tier)
   - Implement rate limiting and caching

4. **Scheduled Jobs**
   - Daily workflow: 9:30 AM ET (market open)
   - Data fetch: 6:00 PM ET (after market close)
   - Backtest validation: Weekly on Sunday

### Useful Commands

```bash
# CLI Tool
python scripts/cli.py status              # System status
python scripts/cli.py validate-config     # Validate configuration
python scripts/cli.py backtest            # Run backtest
python scripts/cli.py init                # Interactive setup

# Makefile
make install                              # Install dependencies
make test                                 # Run tests
make lint                                 # Run linting
make format                               # Format code
make run-daily                            # Run daily workflow
make backtest-optimized                   # Run optimized backtest
```

---

## 🔗 Resources

- **Repository:** https://github.com/shreyas-chickerur/investor-mimic-bot
- **Documentation:** `docs/SYSTEM_OVERVIEW.md`
- **Future Enhancements:** `docs/FUTURE_ENHANCEMENTS.md`
- **API Documentation:** `docs/API.md` (if exists)

---

## ✅ Summary for CI/CD Implementation

**Project Type:** Python 3.8 application with PostgreSQL database  
**Testing:** pytest with coverage, black/flake8 for linting  
**Environments:** Development, Staging, Production  
**Deployment:** GitHub Actions → Staging (auto) → Production (manual approval)  
**Monitoring:** Health checks, system metrics, custom alerts  
**Security:** GitHub Secrets, environment-specific configs, API key rotation

**Key Files:**
- `.github/workflows/ci.yml` - Current CI workflow
- `.github/workflows/deploy.yml` - Current deployment workflow
- `Makefile` - Build commands
- `requirements.txt` - Dependencies
- `tests/` - Test suite

**This document provides everything needed to create a comprehensive CI/CD pipeline for the Investor Mimic Bot project.**

---

*Document Created: December 18, 2025*  
*For: CI/CD Pipeline Implementation*  
*Repository: https://github.com/shreyas-chickerur/investor-mimic-bot*
