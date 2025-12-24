# Scripts and Commands Reference

**Auto-generated documentation for all scripts and Make commands**

Last updated: Auto-updates on each run

---

## Make Commands

### Data Management
- **`make update-data`** - Download latest market data for all symbols (runs `fetch_extended_historical_data.py`)
- **`make clean-data`** - Remove all downloaded market data files

### Testing
- **`make test`** - Run all tests (unit + integration)
- **`make test-single`** - Run single strategy test for quick validation

### Execution
- **`make run`** - Execute the trading system (multi-strategy)
- **`make dry-run`** - Run system in dry-run mode (no broker orders)

### Database
- **`make init-db`** - Initialize trading database with all required tables
- **`make reset-db`** - Reset database to clean state (WARNING: deletes all data)

### Utilities
- **`make clean`** - Remove temporary files and caches
- **`make help`** - Show all available Make commands

---

## Scripts Directory

### Data Scripts
**`scripts/fetch_extended_historical_data.py`**
- Downloads historical market data for all configured symbols
- Updates: `data/SYMBOL.csv` files
- Auto-runs: Via `make update-data`
- Usage: `python3 scripts/fetch_extended_historical_data.py`

### Database Scripts
**`scripts/init_database.py`**
- Initializes trading database with all required tables
- Creates: strategies, trades, system_state, positions tables
- Safe to run multiple times (idempotent)
- Usage: `python3 scripts/init_database.py [--db PATH]`
- Auto-runs: In GitHub Actions before tests

### Phase 5 Scripts
**`scripts/fresh_start_phase5.py`**
- Closes all broker positions and resets database for Phase 5
- Steps: Close positions → Reset DB → Verify reconciliation
- Usage: `python3 scripts/fresh_start_phase5.py`
- When: One-time at Phase 5 start

**`scripts/phase5_weekly_review.py`**
- Analyzes last 7 days of Phase 5 execution
- Shows: Success rate, signals, trades, failed days
- Usage: `python3 scripts/phase5_weekly_review.py`
- When: Every Friday during Phase 5

**`scripts/generate_phase5_report.py`**
- Generates comprehensive Phase 5 completion report
- Analyzes: All days, success criteria, incidents, statistics
- Output: `docs/PHASE_5_COMPLETION_REPORT.md`
- Usage: `python3 scripts/generate_phase5_report.py`
- When: After 14-30 days of Phase 5

**`scripts/download_github_artifacts.py`**
- Downloads all GitHub Actions artifacts (last 30 days)
- Requires: GitHub CLI (`brew install gh`, `gh auth login`)
- Downloads to: `artifacts_backup/TIMESTAMP/`
- Usage: `python3 scripts/download_github_artifacts.py`
- When: To backup or analyze CI/CD artifacts

### Testing Scripts
**`scripts/test_single_strategy.py`**
- Tests a single strategy in isolation
- Quick validation for strategy logic
- Usage: `python3 scripts/test_single_strategy.py`

**`scripts/debug_single_signal.py`**
- Debug execution pipeline for a single signal
- Traces signal through all stages
- Usage: `python3 scripts/debug_single_signal.py`

**`scripts/run_validation_backtest.py`**
- Runs validation backtest to ensure trades execute
- Quick smoke test for system functionality
- Usage: `python3 scripts/run_validation_backtest.py`

---

## Source Files (src/)

### Main Execution
**`src/multi_strategy_main.py`**
- Main entry point for trading system
- Orchestrates: Data loading, signal generation, execution, reconciliation
- Usage: `python3 src/multi_strategy_main.py`
- Environment: Set `ENABLE_BROKER_RECONCILIATION=true` for production

### Core Components
**`src/portfolio_backtester.py`**
- Portfolio-level backtesting engine
- Manages: Multiple strategies, capital allocation, position tracking

**`src/strategy_database.py`**
- Database interface for strategy performance tracking
- Tables: strategies, trades, performance, signals

**`src/broker_reconciler.py`**
- Reconciles local state with broker state
- Ensures: Data integrity, no phantom positions/trades
- Critical: Must pass with 0 discrepancies

**`src/cash_manager.py`**
- Manages cash allocation across strategies
- Tracks: Available cash, reserved cash, per-strategy budgets

**`src/email_notifier.py`**
- Sends email notifications for critical events
- Methods: `send_daily_summary()`, `send_alert()`

**`src/signal_flow_tracer.py`**
- Traces signals through execution pipeline
- Ensures: All signals reach terminal state (no silent drops)

**`src/signal_flow_tracer_extended.py`**
- Extended signal flow tracing with terminal state enforcement
- Phase 5 requirement: Exactly one terminal state per signal

**`src/dry_run_executor.py`**
- Executes trades in dry-run mode (no broker orders)
- For: Testing and validation without real trades

### Strategy Files
**`src/strategies/strategy_rsi_mean_reversion.py`**
- RSI-based mean reversion strategy
- Signals: Buy oversold, sell overbought

**`src/strategies/strategy_ml_momentum.py`**
- Machine learning momentum strategy
- Model: Logistic regression with feature engineering

**`src/strategies/strategy_news_sentiment.py`**
- News sentiment-based trading strategy
- Uses: NewsAPI or heuristic fallback

**`src/strategies/strategy_ma_crossover.py`**
- Moving average crossover strategy
- Signals: Golden cross (buy), death cross (sell)

**`src/strategies/strategy_volatility_breakout.py`**
- Volatility breakout strategy
- Signals: Price breaks out of volatility bands

---

## Auto-Discovery System

This documentation auto-updates by scanning:
1. **Makefile** - Extracts all targets and descriptions
2. **scripts/** - Lists all .py files with docstrings
3. **src/** - Documents main execution files

To regenerate this documentation:
```bash
python3 scripts/generate_docs.py
```

---

## Adding New Scripts

When adding a new script:
1. Add a docstring at the top explaining what it does
2. Run `python3 scripts/generate_docs.py` to update this file
3. Commit both the script and updated documentation

Example docstring format:
```python
#!/usr/bin/env python3
"""
Brief description of what this script does

Longer explanation if needed.
Usage: python3 scripts/my_script.py [args]
"""
```

---

## Quick Reference

**Daily execution (Phase 5):**
```bash
export ENABLE_BROKER_RECONCILIATION=true
python3 src/multi_strategy_main.py
```

**Update market data:**
```bash
make update-data
```

**Initialize database:**
```bash
python3 scripts/init_database.py
```

**Weekly review:**
```bash
python3 scripts/phase5_weekly_review.py
```

**Generate final report:**
```bash
python3 scripts/generate_phase5_report.py
```

**Download CI/CD artifacts:**
```bash
python3 scripts/download_github_artifacts.py
```
