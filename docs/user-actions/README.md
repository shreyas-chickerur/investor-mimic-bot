# User Action Items & Setup Guides

This folder contains all documentation for setup, configuration, and action items you need to complete.

---

## Getting Started

**Start here:** [USER_ACTION_ITEMS.md](USER_ACTION_ITEMS.md)

This is your complete checklist organized into 7 iterative phases:
1. Environment Setup (15 min)
2. Database Setup (10 min)
3. GitHub CI/CD Setup (10 min)
4. Initial Data Collection (3-6 hours)
5. Component Testing (30 min)
6. Automation Setup (15 min)
7. End-to-End Testing (1 hour)

---

## Setup Guides

### System Setup
- **[USER_ACTION_ITEMS.md](USER_ACTION_ITEMS.md)** - Complete setup checklist (START HERE)
- **[WEB_DASHBOARD_SETUP_GUIDE.md](WEB_DASHBOARD_SETUP_GUIDE.md)** - Web dashboard setup and deployment

### GitHub & CI/CD
- **[GITHUB_BRANCH_PROTECTION_SETUP.md](GITHUB_BRANCH_PROTECTION_SETUP.md)** - Configure branch protection and automated testing

### System Analysis
- **[SYSTEM_ANALYSIS_AND_GAPS.md](SYSTEM_ANALYSIS_AND_GAPS.md)** - Complete system analysis, gaps, and optimization recommendations

---

## Quick Reference

### Required API Keys
- Alpha Vantage (free) - News and earnings data
- Alpaca (already have) - Trading
- Gmail App Password - Email notifications
- JWT Secret - Authentication

### Database Migrations
```bash
psql -U postgres -d investorbot < sql/migrations/002_ml_training_schema.sql
psql -U postgres -d investorbot < sql/migrations/003_user_management_schema.sql
```

### Testing Commands
```bash
make test        # Run all tests
make lint        # Run linting
make test-unit   # Unit tests only
```

### Automation
```bash
# Daily digest (10 AM)
0 10 * * * cd /path/to/investor-mimic-bot && python3 scripts/send_daily_digest.py

# ML retraining (Weekly, Sunday 2 AM)
0 2 * * 0 cd /path/to/investor-mimic-bot && python3 ml/continuous_learning_engine.py

# Data collection (Daily, 6 AM)
0 6 * * * cd /path/to/investor-mimic-bot && python3 scripts/automated_ml_pipeline.py
```

---

## Checklist Status

Track your progress:

**Phase 1 - Environment**
- [ ] Dependencies installed
- [ ] .env file configured
- [ ] JWT secret generated
- [ ] Database connection tested

**Phase 2 - Database**
- [ ] Migration 002 run
- [ ] Migration 003 run
- [ ] Tables verified

**Phase 3 - GitHub**
- [ ] Branch protection configured
- [ ] CI workflow tested

**Phase 4 - Data Collection**
- [ ] 13F data collected
- [ ] Price history collected
- [ ] Training data generated
- [ ] ML model trained

**Phase 5 - Testing**
- [ ] Authentication tested
- [ ] Daily digest tested
- [ ] Causality tested
- [ ] All unit tests passing

**Phase 6 - Automation**
- [ ] Daily digest scheduled
- [ ] ML retraining scheduled
- [ ] Data collection scheduled

**Phase 7 - Production**
- [ ] End-to-end test passed
- [ ] Production checklist complete
- [ ] System monitoring active

---

## Support

**Feature Documentation:** See [../features/](../features/) folder
**System Overview:** See [../SYSTEM_OVERVIEW.md](../SYSTEM_OVERVIEW.md)
**Testing Guide:** See [../TESTING_GUIDE.md](../TESTING_GUIDE.md)

---

**Total Setup Time:** 5-8 hours (most can run overnight)
**Approach:** Complete each phase → Test → Move to next phase
**Result:** Production-ready system
