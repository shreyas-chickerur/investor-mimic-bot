# Comprehensive Code Review - Critical Issues Found

**Date:** December 23, 2025  
**Reviewer:** Cascade AI  
**Scope:** Complete system architecture and implementation

---

## 🚨 CRITICAL ISSUES

### 1. **Capital Allocation Logic is Broken**

**Location:** `src/multi_strategy_main.py:65`

```python
capital_per_strategy = self.total_capital / 5
```

**Problem:**
- Divides TOTAL cash by 5, giving each strategy 1/5 of available cash
- But `self.total_capital` is the CASH available, not total capital
- If you have $18,745 cash and 4 positions worth $81,495, each strategy gets $3,749
- **This means strategies are severely undercapitalized**

**Impact:**
- Strategies can only buy tiny positions
- System thinks it has $100K but allocates based on $18K
- Performance tracking is completely wrong

**Fix Needed:**
```python
# Should use portfolio value, not just cash
account = self.trading_client.get_account()
total_portfolio = float(account.portfolio_value)
capital_per_strategy = total_portfolio / 5  # $20K each if $100K total
```

---

### 2. **Strategy Positions Never Update**

**Location:** `src/strategies/strategy_rsi_mean_reversion.py:43`

```python
if rsi < self.rsi_threshold and symbol not in self.positions:
```

**Problem:**
- `self.positions` is a dictionary that's NEVER updated after trades execute
- Strategies don't know what they own
- Will keep generating buy signals for stocks already owned
- Sell signals never trigger (positions dict is always empty)

**Impact:**
- Duplicate positions in same symbol
- No exit logic works
- Strategies violate their own rules

**Fix Needed:**
- Update `self.positions` after each trade execution
- Load positions from database on initialization
- Sync positions with Alpaca

---

### 3. **Two Separate Trading Systems Running**

**Files:**
- `src/main.py` - Single RSI strategy
- `src/multi_strategy_main.py` - Multi-strategy system

**Problem:**
- Both systems exist and can run independently
- Both write to same database (`trading_system.db`)
- No coordination between them
- GitHub Actions runs `multi_strategy_main.py` but local might run `main.py`

**Impact:**
- Database corruption
- Conflicting trades
- Unclear which system is "production"

**Fix Needed:**
- Delete `src/main.py` or clearly mark as deprecated
- Use only one execution path

---

### 4. **Database Schema Mismatch**

**Problem:**
- `trading_system.db` has schema for single strategy
- `strategy_performance.db` has schema for multi-strategy
- Both databases exist but aren't connected
- Performance tracking in one DB, positions in another

**Tables in trading_system.db:**
- positions
- signals  
- performance

**Tables in strategy_performance.db:**
- strategies
- strategy_performance
- strategy_trades
- strategy_signals

**Impact:**
- Data fragmentation
- Can't correlate positions with strategy performance
- Dashboard shows wrong data

**Fix Needed:**
- Consolidate into single database
- Add strategy_id foreign key to positions table
- Migrate all data to unified schema

---

### 5. **Market Data Has No RSI/Volatility for Strategies**

**Location:** `src/multi_strategy_main.py:147`

```python
signals = strategy.generate_signals(market_data)
```

**Problem:**
- Loads `training_data.csv` which has RSI/volatility columns
- But strategies expect to CALCULATE their own indicators
- MA Crossover strategy calculates MAs on the fly
- RSI strategy expects 'rsi' column to exist in data

**In strategy_rsi_mean_reversion.py:36:**
```python
if pd.isna(symbol_data.get('rsi')):
    continue
```

**Impact:**
- Some strategies work (if data has indicators)
- Some strategies fail (if they calculate on the fly)
- Inconsistent behavior

**Fix Needed:**
- Either: Pre-calculate ALL indicators in data
- Or: Have ALL strategies calculate their own
- Don't mix approaches

---

### 6. **update_data.py Only Fetches 100 Days**

**Location:** `scripts/update_data.py:63`

```python
start_date = end_date - timedelta(days=100)
```

**Problem:**
- Only fetches 100 calendar days (~70 trading days)
- MA Crossover strategy needs 200 days for 200-day MA
- Strategy will NEVER generate signals (insufficient data)

**Impact:**
- MA Crossover strategy is permanently broken
- Any strategy needing >100 days of data won't work

**Fix Needed:**
```python
start_date = end_date - timedelta(days=300)  # At least 200 trading days
```

---

### 7. **Sync Database Loses Entry Dates**

**Location:** `scripts/sync_database.py:58`

```python
today,  # We don't have actual entry date, use today
```

**Problem:**
- When syncing positions from Alpaca, uses TODAY as entry date
- Loses actual entry date information
- Can't calculate hold period
- Can't determine when to exit

**Impact:**
- Exit logic broken (thinks all positions entered today)
- Performance tracking wrong (wrong hold periods)
- Can't implement time-based exits

**Fix Needed:**
- Store entry dates in Alpaca order metadata
- Or maintain separate tracking database
- Don't overwrite entry dates on sync

---

### 8. **No Exit Logic in Multi-Strategy System**

**Location:** `src/multi_strategy_main.py:132-176`

**Problem:**
- `run_all_strategies()` only executes BUY signals
- Never checks for SELL signals
- Strategies generate sell signals but they're ignored
- Positions held forever

**Code only handles:**
```python
if action == 'BUY' and shares > 0:
    # execute buy
```

**No code for:**
```python
if action == 'SELL':
    # execute sell
```

**Impact:**
- Positions never close
- Capital locked up indefinitely
- Strategy logic incomplete

**Fix Needed:**
- Add sell order execution
- Handle both BUY and SELL actions
- Implement exit logic

---

### 9. **Performance Calculation Uses Wrong Prices**

**Location:** `src/multi_strategy_main.py:169`

```python
current_prices = market_data.groupby('symbol')['close'].last().to_dict()
```

**Problem:**
- Uses prices from `training_data.csv` (could be days old)
- Not real-time prices from Alpaca
- Performance metrics based on stale data

**Impact:**
- Inaccurate portfolio values
- Wrong return calculations
- Misleading dashboard

**Fix Needed:**
- Fetch current prices from Alpaca API
- Use real-time market data for valuations

---

### 10. **Capital Depletion Not Tracked**

**Location:** `src/multi_strategy_main.py:65`

**Problem:**
- Each strategy allocated capital once at start
- Capital never decreases when trades execute
- Strategies don't know how much cash they've used
- Can "spend" same capital multiple times

**Example:**
- Strategy allocated $20K
- Buys $15K of stock
- Still thinks it has $20K available
- Can buy another $20K (overdraft)

**Impact:**
- Over-leveraging
- Strategies exceed their allocation
- System can go negative cash

**Fix Needed:**
- Track cash vs invested per strategy
- Update available capital after each trade
- Prevent overdraft

---

### 11. **Duplicate Symbol Tracking Broken**

**Location:** `src/trading_system.py:206-208`

```python
current_symbol_positions = len(self.positions[self.positions['symbol'] == symbol])
pending_symbol_trades = sum(1 for t in executed_trades if t['symbol'] == symbol)
```

**Problem:**
- Checks positions in `trading_system.db`
- But multi-strategy trades go to `strategy_performance.db`
- Different databases = can't prevent duplicates across strategies
- Multiple strategies can buy same symbol

**Impact:**
- Concentration risk
- Multiple strategies buying AAPL simultaneously
- Exceeds intended position limits

**Fix Needed:**
- Unified position tracking across all strategies
- Global symbol limit enforcement

---

### 12. **GitHub Actions Artifact Download May Fail**

**Location:** `.github/workflows/daily-trading.yml:35-42`

```yaml
- name: Download previous databases
  continue-on-error: true
  uses: dawidd6/action-download-artifact@v2
```

**Problem:**
- Uses third-party action (dawidd6)
- Not official GitHub action
- Could break if maintainer abandons it
- `continue-on-error: true` masks failures

**Impact:**
- Silent failures
- Databases not persisted
- Data loss between runs

**Fix Needed:**
- Use official GitHub cache action
- Or use GitHub Releases for database storage
- Don't silently continue on error

---

### 13. **No Transaction Atomicity**

**Location:** `src/multi_strategy_main.py:178-222`

**Problem:**
- Submits order to Alpaca
- Then logs to database
- If database write fails, order executed but not tracked
- If order fails, database might still log it

**Impact:**
- Orphaned orders
- Database out of sync with reality
- Accounting errors

**Fix Needed:**
- Use try/except/finally properly
- Rollback database on Alpaca failure
- Ensure atomicity

---

### 14. **Strategy Base Class Has No Position Management**

**Location:** `src/strategy_base.py:20`

```python
self.positions = {}  # {symbol: shares}
```

**Problem:**
- Positions dict initialized empty
- Never populated from database
- Never updated after trades
- Each strategy thinks it owns nothing

**Impact:**
- All position-based logic broken
- Strategies don't know their state
- Can't make informed decisions

**Fix Needed:**
- Load positions from database on init
- Update after every trade
- Sync with Alpaca periodically

---

### 15. **Logging Creates Files That Don't Exist**

**Location:** `src/multi_strategy_main.py:35`

```python
logging.FileHandler('logs/multi_strategy.log'),
```

**Problem:**
- Assumes `logs/` directory exists
- Fails if directory doesn't exist
- No error handling

**Impact:**
- Crashes on first run
- No logs captured
- Silent failures

**Fix Needed:**
```python
Path('logs').mkdir(exist_ok=True)
logging.FileHandler('logs/multi_strategy.log')
```

---

## 🔧 ARCHITECTURAL ISSUES

### 16. **No Separation of Concerns**

**Problem:**
- `multi_strategy_main.py` does everything:
  - Data loading
  - Strategy execution
  - Order execution
  - Database operations
  - Reporting
- 300 lines of mixed responsibilities

**Fix Needed:**
- Separate classes for each concern
- DataLoader, OrderExecutor, Reporter, etc.

---

### 17. **No Error Recovery**

**Problem:**
- If one strategy fails, entire run stops
- No retry logic
- No graceful degradation

**Fix Needed:**
- Wrap each strategy in try/except
- Continue with other strategies if one fails
- Log errors but don't crash

---

### 18. **Hard-Coded Values Everywhere**

**Examples:**
- `capital_per_strategy = self.total_capital / 5` (hard-coded 5)
- `signals[:3]` (hard-coded top 3)
- `position_size=0.10` (hard-coded 10%)
- `max_positions=10` (hard-coded)

**Fix Needed:**
- Configuration file
- Environment variables
- Make system configurable

---

### 19. **No Input Validation**

**Problem:**
- No validation of market data
- No validation of signals
- No validation of order parameters
- Assumes everything is correct

**Fix Needed:**
- Validate data before use
- Check for NaN, negative values, etc.
- Fail fast with clear errors

---

### 20. **Inconsistent Date Handling**

**Problem:**
- Sometimes uses `datetime` objects
- Sometimes uses strings
- Sometimes uses pandas Timestamp
- No standardization

**Fix Needed:**
- Pick one date type
- Convert at boundaries
- Use consistently throughout

---

## 📊 DATA ISSUES

### 21. **training_data.csv Structure Unclear**

**Problem:**
- Has 80K+ rows for 36 symbols
- ~2,243 rows per symbol
- But only fetching 100 days (70 trading days)
- Where did the 2,243 days come from?

**Fix Needed:**
- Document data structure
- Explain date range
- Clean up old data

---

### 22. **No Data Validation**

**Problem:**
- Loads CSV without checking:
  - Missing columns
  - Data types
  - Date ranges
  - NaN values

**Fix Needed:**
- Schema validation
- Data quality checks
- Fail with clear error if data is bad

---

## 🎯 SUMMARY

**Total Critical Issues:** 22

**Severity Breakdown:**
- **Blocker (System Won't Work):** 8
  - Capital allocation
  - Position tracking
  - No exit logic
  - Database mismatch
  - Insufficient data for strategies
  
- **Major (Wrong Results):** 10
  - Performance calculations
  - Duplicate positions
  - Entry date loss
  - Capital depletion
  
- **Minor (Technical Debt):** 4
  - Logging
  - Hard-coded values
  - Error handling

**Recommendation:**
The system needs significant refactoring before it can be trusted for live trading. The multi-strategy implementation is fundamentally broken and will not work as intended.

**Priority Fixes:**
1. Fix capital allocation (use portfolio value, not cash)
2. Implement position tracking (update after trades)
3. Add exit logic (handle SELL signals)
4. Consolidate databases (single source of truth)
5. Fix data fetching (get enough history)
6. Implement proper state management

**Estimated Effort:** 2-3 days of focused development
