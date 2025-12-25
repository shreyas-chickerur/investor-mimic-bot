# Scripts Directory

Utility scripts for the trading system. Use `make` commands when available for easier execution.

## Setup & Data Management

**`setup_database.py`** - Initialize database schema
- Usage: `make init` or `python3 scripts/setup_database.py --db trading.db`
- Creates all required tables for trading system

**`fetch_historical_data.py`** - Fetch historical market data
- Usage: `make fetch-data`
- Fetches 15 years of OHLCV data using Alpha Vantage API
- Requires premium API key

**`update_data.py`** - Update market data with latest prices
- Usage: `make update-data`
- Adds technical indicators (RSI, VWAP, ATR, ADX)

**`sync_database.py`** - Sync local database with broker
- Usage: `make sync-db`
- Reconciles positions and cash balances with Alpaca

---

## Analysis & Monitoring

**`analyze_signals.py`** - Analyze all strategies for signals
- Usage: `make analyze`
- Dry-run analysis without executing trades

**`view_performance.py`** - View strategy performance metrics
- Usage: `make view`
- CLI dashboard with P&L, win rates, trade counts

---

## Validation & Verification

**`validate_system.py`** - Validate system invariants
- Usage: `python3 scripts/validate_system.py --latest`
- Checks database integrity and execution correctness
- Validates signal terminal states, broker snapshots, costs

**`import_check.py`** - Lightweight import check
- Usage: `python3 scripts/import_check.py`
- Verifies core modules and workflow scripts import cleanly

**`verify_execution.py`** - Verify execution criteria
- Usage: `python3 scripts/verify_execution.py`
- Validates execution meets acceptance criteria
- Checks trades, reconciliation, terminal states

---

## Backtesting

**`run_simple_backtest.py`** - Quick single-strategy backtest
- Simple historical simulation for testing

**`run_validation_backtest.py`** - Validation backtest with signal injection
- Tests system with known signals and parameters

**`run_walkforward_backtest.py`** - Walk-forward portfolio backtest
- Full portfolio-level backtest with rolling windows

**`stress_test_periods.py`** - Stress test specific market periods
- Tests system during crisis periods (2008, 2020, 2022)

---

## Reporting

**`generate_report.py`** - Generate system report
- Usage: `python3 scripts/generate_report.py`
- Creates comprehensive report after validation period

**`weekly_review.py`** - Weekly performance review
- Usage: `python3 scripts/weekly_review.py`
- Checks success rate, P&L trends, failures

**`generate_validation_plots.py`** - Generate validation plots
- Creates equity curves, drawdown charts, allocation plots

---

## Email & Utilities

**`test_email.py`** - Send test email
- Usage: `python3 scripts/test_email.py`
- Tests email configuration with sample data

**`generate_email_chart.py`** - Generate performance chart for emails
- Used by workflows for daily digest emails

**`debug_single_signal.py`** - Debug individual signal processing
- Traces signal through entire execution pipeline

**`download_github_artifacts.py`** - Download artifacts from GitHub Actions
- Retrieves daily JSON artifacts for analysis

**`setup_cron_fixed.sh`** - Setup local cron job
- Configures cron for daily execution at 4:15 PM ET

---

## Quick Reference

### Daily Workflow
```bash
make update-data    # Fetch latest market data
make run            # Execute trading strategies
make view           # Check performance
```

### Setup
```bash
make init           # Initialize database
make fetch-data     # Fetch historical data (one-time)
make sync-db        # Sync with broker
```

### Validation
```bash
python3 scripts/validate_system.py --latest
python3 scripts/verify_execution.py
```

### Testing
```bash
make test                                    # Run all tests
python3 scripts/test_email.py               # Test email
python3 scripts/run_simple_backtest.py      # Quick backtest
```
