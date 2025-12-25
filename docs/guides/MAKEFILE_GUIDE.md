# Makefile Command Reference

Complete guide to all available commands for the Multi-Strategy Trading System.

---

## 🚀 Main Commands

### `make run`
Run all 5 trading strategies simultaneously.
```bash
make run
```
- Executes multi-strategy system
- Scans 36 stocks across all strategies
- Places trades based on signals
- Logs all activity

### `make dashboard`
Open the web-based monitoring dashboard.
```bash
make dashboard
```
- Starts Flask server on http://localhost:5000
- Real-time strategy performance
- Auto-refreshes every 30 seconds
- Shows trades, positions, and returns

### `make analyze`
Analyze all strategies for current signals.
```bash
make analyze
```
- Scans market for opportunities
- Shows signals from all 5 strategies
- Displays top candidates
- No trades executed (analysis only)

---

## 📈 Monitoring Commands

### `make view`
View strategy performance in terminal.
```bash
make view
```
- CLI-based performance dashboard
- Shows all 5 strategies
- Individual P&L and metrics
- Recent trades and signals

### `make logs`
View recent trading logs.
```bash
make logs
```
- Shows last 50 log entries
- Trading execution details
- Error messages if any

### `make positions`
Check current Alpaca positions.
```bash
make positions
```
- Lists all open positions
- Shows shares and entry prices
- Direct from Alpaca API

---

## 🔧 Setup & Maintenance

### `make install`
Install all dependencies.
```bash
make install
```
- Installs Python packages from requirements.txt
- One-time setup command

### `make sync-db`
Sync database with Alpaca positions.
```bash
make sync-db
```
- Reconciles local database with Alpaca
- Fixes any discrepancies
- Run if positions don't match

### `make update-data`
Update market data.
```bash
make update-data
```
- Fetches latest stock data
- Updates training_data.csv
- Run if data is stale

---

## 🧪 Testing Commands

### `make test`
Run all tests.
```bash
make test
```
- Runs pytest on all test files
- Comprehensive test suite
- Shows pass/fail results

### `make test-single`
Test single RSI strategy.
```bash
make test-single
```
- Tests core trading system
- Validates signal generation
- Quick sanity check

### `make test-multi`
Test multi-strategy system.
```bash
make test-multi
```
- Tests all 5 strategies
- Alpaca integration tests
- Full system validation

---

## 🧹 Cleanup Commands

### `make clean`
Clean logs and temporary files.
```bash
make clean
```
- Removes log files
- Deletes Python cache
- Keeps databases intact

### `make clean-all`
Deep clean including databases.
```bash
make clean-all
```
- Removes all logs
- Deletes databases
- Fresh start (use with caution)

---

## 🔐 Helper Commands

### `make check-secrets`
Verify API credentials are set.
```bash
make check-secrets
```
- Checks .env file
- Validates Alpaca keys
- Shows what's missing

### `make quickstart`
Show quick start guide.
```bash
make quickstart
```
- Displays setup steps
- Helpful for first-time users

---

## 📊 Development Commands

### `make run-single`
Run only the RSI strategy (legacy).
```bash
make run-single
```
- Single strategy mode
- For testing/debugging
- Uses src/main.py

### `make dev-dashboard`
Start dashboard in development mode.
```bash
make dev-dashboard
```
- Flask debug mode enabled
- Auto-reloads on code changes
- For development only

---

## 💡 Common Workflows

### First Time Setup
```bash
make install          # Install dependencies
make sync-db          # Sync with Alpaca
make run              # Run strategies
make dashboard        # View results
```

### Daily Monitoring
```bash
make dashboard        # Open web dashboard
# Or
make view            # CLI dashboard
```

### Before Trading
```bash
make analyze         # Check for signals
make positions       # Verify current positions
make run            # Execute trades
```

### Troubleshooting
```bash
make logs           # Check for errors
make sync-db        # Fix database issues
make check-secrets  # Verify credentials
```

---

## 🎯 Tips

1. **Use `make help`** - Shows all available commands
2. **Dashboard is best** - Web interface easier than CLI
3. **Sync regularly** - Run `make sync-db` if positions look wrong
4. **Check logs** - `make logs` shows what happened
5. **Test first** - Use `make analyze` before `make run`

---

## 📝 Notes

- All commands run from project root
- Requires `.env` file with Alpaca credentials
- Dashboard runs on port 5000
- Logs saved in `logs/` directory
- Databases in `data/` directory
