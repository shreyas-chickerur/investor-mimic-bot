# Makefile Command Reference

Complete guide to all available commands for the Multi-Strategy Trading System. Each command includes prerequisites, usage, and expected outcomes.

---

## 🚀 Main Commands

### `make run`
**Purpose:** Execute all 5 trading strategies with live broker integration

**Before running:**
- Run `make init` and `make fetch-data` first
- Ensure `ALPACA_API_KEY` and `ALPACA_SECRET_KEY` are set in `.env`
- Check broker state: `make check-broker`
- Verify market data is current: `make update-data`

**Command:**
```bash
make run
```

**After running:**
- Trades executed and recorded in database
- Artifacts generated in `artifacts/json/` and `artifacts/markdown/`
- Check results: `make view` or `make perf-report`
- Review logs: `make logs`

---

### `make dashboard`
**Purpose:** Open the web-based monitoring dashboard

**Before running:**
- Ensure port 5000 is available
- Database should have execution data for meaningful display

**Command:**
```bash
make dashboard
```

**After running:**
- Server starts on http://localhost:5000
- Real-time strategy performance displayed
- Auto-refreshes every 30 seconds
- Press Ctrl+C to stop server

---

### `make analyze`
**Purpose:** Analyze all strategies for signals (dry-run, no trading)

**Before running:**
- Requires market data: `make fetch-data` or `make update-data`
- No trades will be executed

**Command:**
```bash
make analyze
```

**After running:**
- Shows signals each strategy would generate
- Use to test strategy logic without trading
- Review signal quality before live execution

---

## 📈 Monitoring Commands

### `make view`
**Purpose:** View strategy performance dashboard (CLI)

**Before running:**
- Requires database with trade history
- Run `make run` first for meaningful data

**Command:**
```bash
make view
```

**After running:**
- Shows performance summary for all strategies
- Displays recent trades and signals
- Use regularly to monitor system health

---

### `make logs`
**Purpose:** View recent trading logs (last 50 lines)

**Before running:**
- Logs must exist in `logs/multi_strategy.log`
- Run `make run` to generate logs

**Command:**
```bash
make logs
```

**After running:**
- Shows last 50 log lines
- Use to debug issues or verify execution
- Full logs in `logs/multi_strategy.log`

---

### `make positions`
**Purpose:** Check current Alpaca positions

**Before running:**
- Ensure Alpaca credentials are set in `.env`

**Command:**
```bash
make positions
```

**After running:**
- Lists all open positions
- Shows symbol, quantity, entry price
- Use to verify broker state

---

## 🔧 Setup & Maintenance

### `make init`
**Purpose:** Initialize database schema with all required tables

**Before running:**
- Ensure `.env` file exists with required credentials
- No prior setup needed

**Command:**
```bash
make init
```

**After running:**
- `trading.db` file created in project root
- All tables (strategies, signals, trades, positions, etc.) initialized
- Verify: `ls -lh trading.db` should show the database file

---

### `make fetch-data`
**Purpose:** Fetch 15 years of historical market data for all 36 stocks

**Before running:**
- Run `make init` first
- Ensure `ALPHA_VANTAGE_API_KEY` is set in `.env`
- Premium API key recommended for faster fetching

**Command:**
```bash
make fetch-data
```

**After running:**
- Takes ~18 seconds with premium API
- Market data stored in `trading.db`
- Verify: `sqlite3 trading.db "SELECT COUNT(*) FROM market_data;"`

---

### `make sync-db`
**Purpose:** Sync local database with Alpaca broker state

**Before running:**
- Ensure Alpaca credentials are set
- Database must exist: `make init`

**Command:**
```bash
make sync-db
```

**After running:**
- Local positions updated from broker
- Cash balance synchronized
- Use after manual broker changes

---

### `make update-data`
**Purpose:** Update market data with latest prices

**Before running:**
- Requires `ALPHA_VANTAGE_API_KEY`
- Database must exist

**Command:**
```bash
make update-data
```

**After running:**
- Latest market data fetched
- Database updated with new prices
- Run before `make run` for current data

---

## 🧪 Testing Commands

### `make test`
**Purpose:** Run all tests (pytest)

**Before running:**
- Install pytest: `pip install pytest`
- No other prerequisites

**Command:**
```bash
make test
```

**After running:**
- All tests executed
- Shows pass/fail for each test
- Fix any failures before deployment

---

### `make test-single`
**Purpose:** Test single strategy execution

**Before running:**
- Database and market data required

**Command:**
```bash
make test-single
```

**After running:**
- Single strategy tested in isolation
- Use to debug strategy-specific issues

---

### `make test-multi`
**Purpose:** Test multi-strategy integration

**Before running:**
- Database and market data required

**Command:**
```bash
make test-multi
```

**After running:**
- Tests all strategies working together
- Verifies portfolio-level risk management

---

## 🧹 Cleanup Commands

### `make clean`
**Purpose:** Clean logs and temporary files

**Before running:**
- No prerequisites
- Safe to run anytime

**Command:**
```bash
make clean
```

**After running:**
- Logs cleared from `logs/`
- Python cache files removed
- Temporary files deleted

---

### `make clean-all`
**Purpose:** Deep clean including databases (⚠️ DESTRUCTIVE)

**Before running:**
- ⚠️ **WARNING:** Deletes all databases
- Backup `trading.db` if needed

**Command:**
```bash
make clean-all
```

**After running:**
- All databases deleted
- Logs and cache cleared
- Run `make init` to reinitialize

---

## ✅ System Validation Commands

### `make validate`
**Purpose:** Validate system invariants and data integrity

**Before running:**
- Requires database with execution data
- Run after `make run`

**Command:**
```bash
make validate
```

**After running:**
- Checks 6 system invariants
- Reports PASS/FAIL for each
- Review output for any failures

---

### `make verify-system`
**Purpose:** Verify execution criteria and reconciliation

**Before running:**
- Requires completed execution
- Database must have latest run data

**Command:**
```bash
make verify-system
```

**After running:**
- Verifies signals have terminal states
- Checks reconciliation passed
- Confirms artifact generation

---

### `make check-broker`
**Purpose:** Display current broker state (positions, cash, portfolio value)

**Before running:**
- Ensure Alpaca credentials are set
- No other prerequisites

**Command:**
```bash
make check-broker
```

**After running:**
- Shows current positions and cash
- Displays portfolio value
- Use before/after trading to verify state

---

### `make import-check`
**Purpose:** Verify all Python modules load correctly

**Before running:**
- Run after any code changes
- Ensures dependencies are installed

**Command:**
```bash
make import-check
```

**After running:**
- Reports success or import errors
- Fix any missing dependencies before running system

---

## 📊 Strategy Performance Commands

### `make perf-report`
**Purpose:** Generate comprehensive 30-day strategy performance report

**Before running:**
- Requires trades in database (run `make run` first)
- No prerequisites for first-time use (will show "No trades")

**Command:**
```bash
make perf-report
```

**After running:**
- Report printed to console
- Data saved to `/tmp/strategy_performance.json`
- Shows: P&L, win rates, Sharpe ratios, profit factors

---

### `make perf-chart`
**Purpose:** Generate visual performance charts (7-day cumulative P&L and win rates)

**Before running:**
- Requires trades in database
- Install matplotlib if not present

**Command:**
```bash
make perf-chart
```

**After running:**
- Chart saved to `/tmp/strategy_chart.html`
- Embedded base64 image ready for email
- Open in browser to view

---

### `make perf-dashboard`
**Purpose:** Start interactive web dashboard for strategy performance

**Before running:**
- Ensure port 8080 is available
- Run `make perf-report` first to generate data

**Command:**
```bash
make perf-dashboard
```

**After running:**
- Server starts on http://localhost:8080
- Open http://localhost:8080/dashboard/strategy_performance.html
- Press Ctrl+C to stop server

---

## 📧 Email & Notification Commands

### `make email-daily`
**Purpose:** Generate daily email digest (standard format)

**Before running:**
- Requires today's artifact: run `make run` first
- Artifact must exist in `artifacts/json/YYYY-MM-DD.json`

**Command:**
```bash
make email-daily
```

**After running:**
- Email HTML generated at `/tmp/daily_email.html`
- Open in browser to preview
- Contains: portfolio metrics, trades, positions, strategy performance

---

### `make email-weekly`
**Purpose:** Generate weekly email with embedded performance charts

**Before running:**
- Run `make perf-chart` first to generate charts
- Requires today's artifact

**Command:**
```bash
make email-weekly
```

**After running:**
- Email HTML with charts at `/tmp/daily_email.html`
- Includes 7-day performance visualizations
- Larger file size due to embedded images

---

### `make email-sample`
**Purpose:** Generate sample email with mock data (for testing)

**Before running:**
- No prerequisites - uses mock data

**Command:**
```bash
make email-sample
```

**After running:**
- Sample email at `/tmp/sample_email.html`
- Shows example format with realistic data
- Use to preview email design

---

## 🐛 Analysis & Debugging Commands

### `make debug-signal`
**Purpose:** Debug single signal flow with detailed tracing

**Before running:**
- Requires specific signal to debug
- May need to modify script for target signal

**Command:**
```bash
make debug-signal
```

**After running:**
- Detailed trace of signal lifecycle
- Shows why signal was accepted/rejected
- Use for troubleshooting signal issues

---

### `make backtest`
**Purpose:** Run validation backtest on historical data

**Before running:**
- Requires historical data: `make fetch-data`
- Takes several minutes to complete

**Command:**
```bash
make backtest
```

**After running:**
- Backtest results in console
- Performance metrics calculated
- Use to validate strategy performance

---

## 💡 Common Workflows

### First-time Setup
```bash
make init          # Initialize database
make fetch-data    # Get historical data (15 years, ~18 seconds)
make check-broker  # Verify broker connection
```

### Daily Workflow
```bash
make check-broker  # Check current state
make update-data   # Get latest prices
make run           # Execute strategies
make view          # View results
```

### Performance Analysis
```bash
make perf-report      # Generate 30-day report
make perf-chart       # Create charts
make perf-dashboard   # View interactive dashboard
```

### Email Generation
```bash
make run              # Execute trades first
make perf-chart       # Generate charts
make email-weekly     # Generate email with visuals
# Open /tmp/daily_email.html to preview
```

### Troubleshooting
```bash
make import-check  # Verify imports
make logs          # Check logs
make validate      # Verify system health
make check-broker  # Verify broker state
```

### Testing Before Live Trading
```bash
make analyze       # Dry-run signal analysis
make email-sample  # Preview email format
make test          # Run all tests
```

---

## 🎯 Tips

1. **Use `make help`** - Shows all available commands with categories
2. **Check prerequisites** - Each command lists what's needed before running
3. **Review outputs** - Each command tells you what to check after running
4. **Start simple** - Use `make init`, `make fetch-data`, then `make run`
5. **Monitor regularly** - Use `make view` or `make perf-dashboard` daily
6. **Test first** - Use `make analyze` before `make run` to see signals
7. **Backup data** - Before `make clean-all`, backup `trading.db`

---

## 📝 Notes

- All commands run from project root directory
- Requires `.env` file with Alpaca and Alpha Vantage credentials
- Main dashboard runs on port 5000, performance dashboard on port 8080
- Logs saved in `logs/` directory
- Database: `trading.db` in project root
- Artifacts saved in `artifacts/json/` and `artifacts/markdown/`
- Email previews saved to `/tmp/` directory

---

## 🔗 Related Documentation

- [Main README](../../README.md) - Complete system documentation
- [Quick Start Guide](QUICK_START.md) - Getting started tutorial
- [Scripts Reference](SCRIPTS_AND_COMMANDS.md) - Direct script usage
- [GitHub Actions Setup](../github-actions/GITHUB_ACTIONS_SETUP.md) - Automated execution
