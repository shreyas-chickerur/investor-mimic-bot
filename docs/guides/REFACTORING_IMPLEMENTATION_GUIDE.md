# System Refactoring Implementation Guide

**Based on:** Claude's comprehensive infrastructure review  
**Date:** January 16, 2026  
**Status:** Ready to implement

---

## Overview

This guide implements Claude's recommendations for production-ready infrastructure. The refactoring is divided into 3 phases:

- **Phase 1:** Critical fixes before live trading (testing, validation, error handling)
- **Phase 2:** High-impact improvements (code organization, config management, monitoring)
- **Phase 3:** Pre-live trading checklist and documentation

**Estimated Time:** 2-3 weeks  
**Current Progress:** Tests created (2/50 files), Ready to continue

---

## Implementation Status

### ✅ Completed
- [x] Test infrastructure (conftest.py)
- [x] Risk management tests (test_risk_management.py)
- [x] Implementation guide (this document)

### 🔄 In Progress
- [ ] Strategy tests
- [ ] Broker reconciliation tests
- [ ] Integration tests

### ⏳ Pending
- [ ] Input validation in execution_engine.py
- [ ] Pre-live validation script
- [ ] Code reorganization (git mv commands)
- [ ] YAML configuration system
- [ ] Streamlit dashboard
- [ ] GitHub Actions test workflow
- [ ] Pre-live checklist

---

## Phase 1: Critical Fixes (Week 1)

### 1.1 Testing Infrastructure ⚠️ PARTIALLY COMPLETE

**Files Created:**
- ✅ `tests/conftest.py` - Pytest fixtures
- ✅ `tests/test_risk_management.py` - Risk module tests (100% coverage target)
- ⏳ `tests/test_strategies.py` - Strategy logic tests
- ⏳ `tests/test_broker_reconciliation.py` - Reconciliation tests
- ⏳ `tests/test_integration.py` - End-to-end tests

**Next Steps:**
```bash
# Continue creating test files from Claude's guide
# Then run tests
pytest tests/ --cov=src --cov-report=html --cov-report=term
open htmlcov/index.html  # Review coverage
```

**Target Coverage:**
- Risk management: 100%
- Position sizing: 100%
- Broker reconciliation: 100%
- Strategy logic: 80%
- Overall: 60%

### 1.2 Input Validation & Error Handling

**Files to Modify:**
- `src/execution_engine.py` - Add `_validate_inputs()` method
- `src/portfolio_risk_manager.py` - Add input validation to all methods

**Key Changes:**
- Validate market data (not empty, required columns, NaN limits)
- Check data freshness (< 72 hours old)
- Verify environment variables set
- Validate portfolio value > 0
- Add comprehensive error messages
- Send critical alerts on validation failures

### 1.3 Pre-Live Validation Script

**File to Create:**
- `scripts/validate_before_live.py` - 10-point validation checklist

**Checks:**
1. Test coverage >= 60%
2. Broker reconciliation working
3. Stop losses enabled
4. Drawdown protection configured
5. Email notifications working
6. Paper trading results (>30 trades, >40% win rate)
7. Data quality acceptable
8. Risk limits reasonable
9. Database schema complete
10. API keys configured

**Usage:**
```bash
python scripts/validate_before_live.py
# Must return exit code 0 before going live
```

---

## Phase 2: High-Impact Improvements (Week 2)

### 2.1 Code Reorganization into Submodules

**Current Structure:**
```
src/
├── execution_engine.py
├── portfolio_risk_manager.py
├── regime_detector.py
├── strategies/
└── ... (15+ files in root)
```

**New Structure:**
```
src/
├── core/          # execution_engine, main, database
├── risk/          # portfolio_risk_manager, stop_loss, etc.
├── regime/        # regime_detector, dynamic_allocator
├── data/          # data_loader, data_quality_checker
├── monitoring/    # signal_funnel_tracker, structured_logger
├── integration/   # broker_reconciler, email_notifier
├── utils/         # artifact_writer, config_loader
└── strategies/    # (keep as-is)
```

**Implementation:**
```bash
# Create directories
mkdir -p src/{core,risk,regime,data,monitoring,integration,utils}

# Move files (preserves git history)
git mv src/execution_engine.py src/core/
git mv src/main.py src/core/
git mv src/database.py src/core/

git mv src/portfolio_risk_manager.py src/risk/
git mv src/drawdown_stop_manager.py src/risk/
git mv src/stop_loss_manager.py src/risk/
git mv src/correlation_filter.py src/risk/
git mv src/kill_switch_service.py src/risk/

git mv src/regime_detector.py src/regime/
git mv src/dynamic_allocator.py src/regime/

git mv src/data_loader.py src/data/
git mv src/data_quality_checker.py src/data/

git mv src/signal_funnel_tracker.py src/monitoring/
git mv src/structured_logger.py src/monitoring/

git mv src/broker_reconciler.py src/integration/
git mv src/email_notifier.py src/integration/

git mv src/artifact_writer.py src/utils/

# Create __init__.py files (see Claude's guide for contents)
# Update all imports to use absolute paths (src.core.database, etc.)
```

**Verification:**
```bash
python scripts/verify_reorganization.py
pytest tests/  # All tests should still pass
```

### 2.2 YAML Configuration Management

**Files to Create:**
- `config/trading_config.yaml` - Centralized configuration
- `src/utils/config_loader.py` - Config loading utility

**Benefits:**
- No hardcoded parameters in code
- Easy parameter tuning without code changes
- Environment-specific configs (dev/staging/prod)
- Version control for parameters

**Usage:**
```python
from src.utils.config_loader import ConfigLoader

config = ConfigLoader()
rsi_threshold = config.get('strategies.rsi_mean_reversion.params.rsi_threshold')
max_heat = config.get('risk.portfolio.heat_limits.normal')
```

**Add to requirements.txt:**
```
PyYAML==6.0.1
```

### 2.3 Streamlit Monitoring Dashboard

**Files to Create:**
- `dashboard/app.py` - Main dashboard
- `dashboard/requirements.txt` - Dashboard dependencies
- `dashboard/run.sh` - Launch script

**Features:**
- Portfolio overview (value, P&L, heat, positions)
- Equity curve chart
- Recent trades table
- Current positions table
- Strategy performance metrics
- Recent signals log

**Usage:**
```bash
cd dashboard
pip install -r requirements.txt
./run.sh
# Open http://localhost:8501
```

---

## Phase 3: Pre-Live Trading Checklist

**File to Create:**
- `docs/PRE_LIVE_CHECKLIST.md` - Comprehensive checklist

**Sections:**
1. Critical Requirements (must complete)
2. Risk Configuration Review
3. Strategy Review
4. Operational Readiness
5. Final Safety Checks
6. Post-Launch Monitoring (first 2 weeks)

**Key Items:**
- [ ] All validation checks passing
- [ ] Test coverage >= 60%
- [ ] 30+ paper trades with >= 40% win rate
- [ ] Stop losses enabled
- [ ] Email notifications working
- [ ] Start with small capital ($5k-$10k)
- [ ] Daily monitoring plan established

---

## Testing After Implementation

```bash
# Run all tests with coverage
pytest tests/ -v --cov=src --cov-report=html --cov-report=term

# Check coverage report
open htmlcov/index.html

# Verify imports after reorganization
python scripts/verify_reorganization.py

# Test config loading
python -c "from src.utils.config_loader import ConfigLoader; c = ConfigLoader(); print(c.get('risk.portfolio.heat_limits.normal'))"

# Run pre-live validation
python scripts/validate_before_live.py
```

---

## GitHub Actions Integration

**File to Create:**
- `.github/workflows/test.yml` - Automated testing on push/PR

**Triggers:**
- Push to main or dev branches
- Pull requests to main

**Steps:**
1. Checkout code
2. Setup Python 3.11
3. Install system dependencies (ta-lib)
4. Install Python dependencies
5. Run tests with coverage
6. Upload coverage report
7. Fail if coverage < 60%

---

## What NOT to Do (Per Claude's Analysis)

❌ **Skip These (Unnecessary at Current Scale):**
1. PostgreSQL migration - SQLite is fine
2. Docker containerization - Adds complexity without benefit
3. Cloud infrastructure migration - GitHub Actions sufficient
4. Grafana/Prometheus - Streamlit dashboard is enough
5. Microservices architecture - Monolith is appropriate
6. Real-time execution - End-of-day is correct approach
7. Advanced MLOps - Current ML is simple enough
8. Caching layer - Data refreshes daily
9. Speed optimizations - Runtime < 5 min is fine
10. Custom monitoring - Logs + Streamlit + email sufficient

---

## Implementation Timeline

### Week 1: Critical Fixes
- **Days 1-2:** Complete test suite (all test files)
- **Days 3-4:** Add input validation and error handling
- **Day 5:** Create and test pre-live validation script

### Week 2: High-Impact Improvements
- **Days 1-2:** Code reorganization (git mv + import updates)
- **Days 3-4:** YAML configuration system
- **Day 5:** Streamlit dashboard

### Week 3: Validation & Documentation
- **Days 1-2:** GitHub Actions workflow
- **Days 3-4:** Pre-live checklist and documentation
- **Day 5:** Final validation and testing

---

## Success Criteria

Before marking complete:
- ✅ Test coverage >= 60% overall
- ✅ Risk modules at 100% coverage
- ✅ All tests passing
- ✅ Code reorganized into submodules
- ✅ YAML config system working
- ✅ Dashboard displaying correct data
- ✅ Pre-live validation script passing
- ✅ GitHub Actions tests passing
- ✅ Documentation complete

---

## Next Steps for You

1. **Review this guide** - Understand the full scope
2. **Continue Phase 1.1** - Create remaining test files:
   - `tests/test_strategies.py`
   - `tests/test_broker_reconciliation.py`
   - `tests/test_integration.py`
3. **Run tests** - `pytest tests/ --cov=src`
4. **Proceed to Phase 1.2** - Add input validation
5. **Track progress** - Update this guide as you complete items

---

## Getting Help

If you encounter issues:
1. Check test output for specific failures
2. Review Claude's original guide (in your consultation prompt)
3. Verify imports are correct after reorganization
4. Ensure all dependencies installed (`pip install -r requirements.txt`)
5. Check that database schema is initialized

---

## Notes

- All code follows existing patterns in your codebase
- Import statements use absolute imports (`from src.core.database import Database`)
- Config system allows easy parameter tuning without code changes
- Test coverage focuses on critical areas (risk management, position sizing)
- Dashboard provides visibility without heavy infrastructure
- Validation script catches issues before they affect real money

**Remember:** This is production infrastructure for real money. Take time to do it right.
