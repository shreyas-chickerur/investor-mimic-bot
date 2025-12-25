# Project Structure

**Multi-Strategy Quantitative Trading System**

Organized by function, not by phase. Clean, maintainable, and easy to navigate.

---

## 📁 Root Directory

```
investor-mimic-bot/
├── README.md              # Comprehensive project documentation
├── requirements.txt       # Python dependencies
├── .env                   # Environment variables (API keys)
├── .gitignore            # Git ignore patterns
├── Makefile              # Command shortcuts
├── trading.db            # SQLite database (trading data)
├── market_data.db        # SQLite database (market data)
├── src/                  # Source code
├── scripts/              # Utility scripts
├── tests/                # Test suite
├── docs/                 # Documentation
├── data/                 # Training data
├── logs/                 # Execution logs
├── artifacts/            # Daily execution artifacts
├── backtest_results/     # Backtesting outputs
├── config/               # Configuration files
├── patches/              # Code patches
└── .github/workflows/    # CI/CD automation
```

---

## 💻 Source Code (`src/`)

### Core Trading Engine
- **`execution_engine.py`** - Main execution orchestrator (was `multi_strategy_main.py`)
- **`trade_executor.py`** - Trade execution logic
- **`broker_reconciler.py`** - Broker state reconciliation
- **`portfolio_risk_manager.py`** - Portfolio-level risk controls
- **`cash_manager.py`** - Cash management
- **`execution_costs.py`** - Slippage and commission modeling
- **`correlation_filter.py`** - Position correlation filtering
- **`dynamic_allocator.py`** - Dynamic capital allocation
- **`regime_detector.py`** - Market regime detection (VIX-based)
- **`stop_loss_manager.py`** - Stop loss management
- **`window_boundary_guardrail.py`** - Window boundary protection

### Data Management
- **`alpaca_data_fetcher.py`** - Alpaca market data fetching
- **`vix_data_fetcher.py`** - VIX data fetching
- **`data_validator.py`** - Data quality validation
- **`news_sentiment.py`** - News sentiment analysis

### Database
- **`database.py`** - Database operations (was `phase5_database.py`)
- **`strategy_database.py`** - Strategy-specific database operations

### Utilities
- **`email_notifier.py`** - Email notifications
- **`artifact_writer.py`** - Daily artifact generation (was `daily_artifact_writer.py`)
- **`performance_metrics.py`** - Performance calculations
- **`signal_tracer.py`** - Signal flow tracing (was `signal_flow_tracer.py`)
- **`signal_tracer_extended.py`** - Terminal state enforcement
- **`signal_injection_engine.py`** - Signal injection for testing
- **`dry_run_executor.py`** - Dry run execution mode

### Strategies
- **`strategies/`** - Strategy implementations
  - `strategy_rsi_mean_reversion.py`
  - `strategy_ml_momentum.py`
  - `strategy_news_sentiment.py`
  - `strategy_ma_crossover.py`
  - `strategy_volatility_breakout.py`
- **`strategy_base.py`** - Base strategy class
- **`strategy_runner.py`** - Strategy execution runner
- **`strategy_dashboard.py`** - Strategy dashboard

### Other
- **`config.py`** - Configuration management
- **`main.py`** - Single strategy runner (deprecated)
- **`dashboard_server.py`** - Web dashboard server
- **`portfolio_backtester.py`** - Portfolio backtesting
- **`trading_system.py`** - Trading system core
- **`security.py`** - Security utilities

---

## 🔧 Scripts (`scripts/`)

### Setup & Data
- **`setup_database.py`** - Initialize database (was `init_database.py`)
- **`fetch_historical_data.py`** - Fetch historical data (was `fetch_extended_historical_data.py`)
- **`update_data.py`** - Update market data
- **`sync_database.py`** - Sync with broker

### Analysis & Monitoring
- **`analyze_signals.py`** - Analyze signals (was `multi_strategy_analysis.py`)
- **`view_performance.py`** - View performance (was `view_strategy_performance.py`)

### Validation
- **`validate_system.py`** - System validation (was `check_phase5_invariants.py`)
- **`verify_execution.py`** - Execution verification (was `verify_phase5_day1.py`)

### Backtesting
- **`run_simple_backtest.py`** - Simple backtest
- **`run_validation_backtest.py`** - Validation backtest
- **`run_walkforward_backtest.py`** - Walk-forward backtest
- **`stress_test_periods.py`** - Stress testing

### Reporting
- **`generate_report.py`** - Generate reports (was `generate_phase5_report.py`)
- **`weekly_review.py`** - Weekly review (was `phase5_weekly_review.py`)
- **`generate_validation_plots.py`** - Generate plots

### Utilities
- **`test_email.py`** - Test email (was `send_test_email.py`)
- **`generate_email_chart.py`** - Generate email charts
- **`debug_single_signal.py`** - Debug signals
- **`download_github_artifacts.py`** - Download artifacts
- **`setup_cron_fixed.sh`** - Setup cron job

---

## 🧪 Tests (`tests/`)

- **`test_alpaca_integration.py`** - Alpaca API integration tests
- **`test_broker_reconciler.py`** - Broker reconciliation tests
- **`test_email_alert.py`** - Email notification tests
- **`test_end_to_end.py`** - End-to-end system tests
- **`test_integration.py`** - Integration tests
- **`test_terminal_states.py`** - Terminal state tests
- **`test_trading_system.py`** - Trading system tests
- **`test_single_strategy.py`** - Single strategy tests
- **`test_backtest_minimal.py`** - Minimal backtest tests
- **`production_readiness_check.py`** - Production readiness

---

## 📚 Documentation (`docs/`)

### Structure
```
docs/
├── README.md              # Documentation index
├── PROJECT_STRUCTURE.md   # This file
├── guides/                # How-to guides
├── reference/             # Technical reference
├── reports/               # Current reports
└── history/               # Historical documentation
```

### Guides (`docs/guides/`)
- `GUIDE.md` - Complete system guide
- `AUTOMATION_GUIDE.md` - Automation setup
- `ADD_GITHUB_SECRETS.md` - GitHub secrets configuration
- `MAKEFILE_GUIDE.md` - Makefile commands
- `MARKET_OPEN_CHECKLIST.md` - Pre-market checklist
- `MARKET_OPEN_QUICK_START.md` - Quick start
- `SCRIPTS_AND_COMMANDS.md` - Scripts reference

### Reference (`docs/reference/`)
- `TRADING_DB_SCHEMA.md` - Database schema
- `DATABASE_PERSISTENCE.md` - Database persistence
- `STRATEGY_FLOWCHARTS.md` - Strategy flowcharts
- `EMAIL_NOTIFICATIONS.md` - Email system
- `SECURITY_PY_EXPLANATION.md` - Security module
- `KNOWN_LIMITATIONS.md` - System limitations

### Reports (`docs/reports/`)
- `ALGORITHM_SPECIFICATION.md` - Algorithm specs
- `COMPLETE_SYSTEM_DOCUMENTATION.md` - Complete docs
- `EMPIRICAL_VALIDATION_REPORT.md` - Validation results
- `VERIFICATION_REPORT.md` - System verification
- `FINAL_IMPLEMENTATION_REPORT.md` - Implementation details
- `EXPERT_FEEDBACK_ROUND2.md` - Expert feedback
- `IMPROVEMENT_TRACKER.md` - Improvements
- `SYSTEM_UPDATE_FOR_REVIEW.md` - System updates
- `QUICK_START.md` - Quick start guide

### History (`docs/history/`)
- `implementation/` - Phase-specific implementation docs
- `development/` - Development notes and handoffs
- `reviews/` - Code reviews and fixes

---

## 🤖 CI/CD (`.github/workflows/`)

### Active Workflows
- **`phase5_morning_run.yml`** - Daily execution (6:30 AM PST)
- **`phase5-daily-validation.yml`** - Daily validation
- **`test.yml`** - CI testing

### Removed Workflows
- `daily-trading.yml` (unused)
- `daily-trading-clean.yml` (empty)
- `weekly-rollup.yml` (unused)

---

## 📊 Database Schema

### Tables
- **`strategies`** - Strategy definitions
- **`signals`** - Trading signals with terminal states
- **`trades`** - Executed trades
- **`positions`** - Current positions
- **`broker_state`** - Broker reconciliation snapshots
- **`system_state`** - System-level state

See `docs/reference/TRADING_DB_SCHEMA.md` for complete schema.

---

## 🚀 Key Commands

### Daily Operations
```bash
make run            # Run trading execution
make dashboard      # Start web dashboard
make view           # View performance
make logs           # View logs
```

### Setup
```bash
make init           # Initialize database
make fetch-data     # Fetch historical data
make sync-db        # Sync with broker
```

### Validation
```bash
python3 scripts/validate_system.py --latest
python3 scripts/verify_execution.py
```

### Testing
```bash
make test           # Run all tests
```

---

## 📝 Naming Conventions

### Files
- **Descriptive, functional names** (not phase-based)
- **snake_case** for Python files
- **UPPERCASE** for markdown documentation

### Removed Phase-Specific Naming
- ❌ `phase5_database.py` → ✅ `database.py`
- ❌ `multi_strategy_main.py` → ✅ `execution_engine.py`
- ❌ `check_phase5_invariants.py` → ✅ `validate_system.py`
- ❌ `verify_phase5_day1.py` → ✅ `verify_execution.py`
- ❌ `send_test_email.py` → ✅ `test_email.py`

---

## 🎯 Design Principles

1. **Functional Organization** - Organized by what it does, not when it was built
2. **Single Responsibility** - Each file has one clear purpose
3. **Modular Design** - Components are independent and reusable
4. **Clear Naming** - Names describe function, not history
5. **Minimal Root** - Only essential files in root directory
6. **Documented** - Every major component has documentation

---

## 📈 Project Status

✅ **Phase 1:** Documentation organized into functional subfolders  
✅ **Phase 2:** Scripts renamed to be generic (no phase references)  
✅ **Phase 3:** Source files renamed to be generic and descriptive  
✅ **All Tests Passing:** 80 tests, 0 errors  
✅ **Production Ready:** Automated execution via GitHub Actions

---

## 🔗 Quick Links

- **Main README:** [`README.md`](../README.md)
- **Documentation Index:** [`docs/README.md`](README.md)
- **Scripts Reference:** [`scripts/README.md`](../scripts/README.md)
- **Database Schema:** [`docs/reference/TRADING_DB_SCHEMA.md`](reference/TRADING_DB_SCHEMA.md)
- **System Guide:** [`docs/guides/GUIDE.md`](guides/GUIDE.md)
