# Phase 5 Pipeline Proof

**Date:** 2024-12-24  
**Purpose:** Document the live execution order and module invocation for Phase 5 operational validation  

---

## Execution Flow

### 1. **Initialization** (`MultiStrategyRunner.__init__`)

**Order:**
1. Initialize Phase5Database (`trading.db`)
2. Set `asof_date` for signal tracking
3. Connect to Alpaca Trading Client
4. Get initial account state (portfolio value, cash)
5. Initialize professional-grade modules:
   - `EmailNotifier` - Email alerts and summaries
   - `DataValidator` - Market data validation
   - `CashManager` - Cash allocation tracking
   - `PortfolioRiskManager` - Heat limits and circuit breakers
   - `CorrelationFilter` - Signal correlation filtering
   - `RegimeDetector` - Market regime detection
   - `DynamicAllocator` - Strategy capital allocation
   - `ExecutionCostModel` - Slippage and commission calculation
   - `PerformanceMetrics` - Trade performance tracking
   - `BrokerReconciler` - Broker vs local state reconciliation
   - `DailyArtifactWriter` - JSON/Markdown artifact generation

**Database Tables Created:**
- `strategies` - Strategy definitions
- `signals` - Trading signals with terminal states
- `trades` - Executed trades with full cost breakdown
- `positions` - Current open positions
- `broker_state` - Daily broker snapshots
- `system_state` - System-wide state

---

### 2. **Account State Refresh** (`main()` - Start)

**Module:** `_refresh_account_state()`

**Actions:**
- Query Alpaca for fresh account data
- Update `portfolio_value`
- Update `cash_available`
- Log refreshed state

**Critical:** Ensures we start with accurate broker state

---

### 3. **Data Validation** (`load_market_data()`)

**Module:** `DataValidator`

**Actions:**
1. Check if `data/training_data.csv` exists
2. Validate data freshness
3. Validate required columns
4. Validate data completeness
5. Auto-update if enabled and validation fails

**Output:** Validated DataFrame with last 100 days of market data

---

### 4. **Strategy Initialization** (`initialize_strategies()`)

**Actions:**
1. Calculate equal capital allocation per strategy
2. Create or load 5 strategies from database:
   - RSI Mean Reversion
   - ML Momentum
   - News Sentiment
   - MA Crossover
   - Volatility Breakout
3. Load existing positions from `positions` table
4. Initialize strategy instances with capital

**Database Writes:**
- `strategies` table (if new)

---

### 5. **Regime Detection** (`run_all_strategies()`)

**Module:** `RegimeDetector`

**Actions:**
1. Calculate VIX from market data
2. Classify volatility regime (LOW/NORMAL/HIGH/EXTREME)
3. Determine max portfolio heat based on regime
4. Return regime adjustments

**Output:** Regime adjustments dict with `max_portfolio_heat`, `vix`, `volatility_regime`

---

### 6. **Daily Loss Limit Check**

**Module:** `PortfolioRiskManager`

**Actions:**
- Check if daily loss exceeds limit
- Halt trading if limit breached

**Circuit Breaker:** Trading stops if triggered

---

### 7. **Broker Reconciliation** (if enabled)

**Module:** `BrokerReconciler`

**Actions:**
1. **Refresh account state** (CRITICAL)
2. Build local positions from `positions` table
3. Query Alpaca for broker positions
4. Compare local vs broker:
   - Position quantities
   - Cash balances
5. Generate discrepancy list
6. **HALT trading if reconciliation fails**

**Database Reads:**
- `positions` table

**Output:** `reconciliation_status` (PASS/FAIL), `discrepancies` list

---

### 8. **Signal Generation** (per strategy)

**Module:** Strategy classes (RSI, ML, News, MA, Volatility)

**Actions:**
1. Calculate technical indicators
2. Apply strategy logic
3. Generate buy/sell signals
4. Assign confidence scores

**Database Writes:**
- `signals` table with `asof_date`, `strategy_id`, `symbol`, `signal_type`, `confidence`, `reasoning`

**Output:** List of signals with `signal_id` attached

---

### 9. **Correlation Filtering**

**Module:** `CorrelationFilter`

**Actions:**
1. Get combined positions across all strategies
2. Filter signals to avoid correlated positions
3. Reduce concentration risk

**Terminal States Updated:**
- Filtered signals → `FILTERED` with reason

---

### 10. **Trade Execution** (per strategy)

**Module:** `_execute_strategy_trades()`

**Order per signal:**

1. **Calculate Execution Costs**
   - Module: `ExecutionCostModel`
   - Calculate `exec_price`, `slippage_cost`, `commission_cost`, `total_cost`

2. **Cash Reservation**
   - Module: `CashManager`
   - Reserve cash for trade
   - **Terminal State:** `REJECTED` if insufficient cash

3. **Portfolio Heat Check**
   - Module: `PortfolioRiskManager`
   - Check if adding position exceeds heat limit
   - Uses **current_exposure** (updated per trade)
   - **Terminal State:** `FILTERED` if heat limit exceeded

4. **Submit Order to Broker**
   - Module: Alpaca `TradingClient`
   - Submit market order
   - Receive `order_id`

5. **Update Strategy State**
   - Add/remove position from strategy
   - Update capital
   - Update exposure (CRITICAL: propagates to next strategy)

6. **Database Writes**
   - `trades` table: Full execution details
     - `strategy_id`, `signal_id`, `symbol`, `action`, `shares`
     - `requested_price`, `exec_price`, `slippage_cost`, `commission_cost`, `total_cost`, `notional`
     - `order_id`, `executed_at`
   - `positions` table: Update or create position
     - `strategy_id`, `symbol`, `shares`, `avg_price`, `current_price`, `market_value`, `unrealized_pnl`
   - `signals` table: Update terminal state
     - **Terminal State:** `EXECUTED` with `trade_id`

7. **Track Executed Trade**
   - Add to `executed_trades` list for email

**Error Handling:**
- Any exception → **Terminal State:** `REJECTED` with error message

---

### 11. **Account State Refresh** (`main()` - After Execution)

**Module:** `_refresh_account_state()`

**Actions:**
- Query Alpaca for post-execution account data
- Update `portfolio_value`
- Update `cash_available`

**Critical:** Ensures accurate state before reporting

---

### 12. **Performance Metrics**

**Module:** `PerformanceMetrics`

**Actions:**
- Calculate daily P&L
- Calculate cumulative P&L
- Calculate drawdown
- Track max drawdown

---

### 13. **Order Status Verification**

**Module:** `verify_order_statuses()`

**Actions:**
1. Query Alpaca for each `order_id`
2. Classify orders:
   - `filled` → `confirmed_fills`
   - `canceled/rejected/expired` → `rejected_orders`
   - Other → `pending_orders`

**Output:** Confirmed fill count

---

### 14. **Broker State Snapshot**

**Database Writes:**
- `broker_state` table:
  - `snapshot_date`, `cash`, `portfolio_value`, `buying_power`
  - `positions_json` (all broker positions)
  - `reconciliation_status`, `discrepancies_json`

**Critical:** Creates audit trail for reconciliation

---

### 15. **Daily Artifact Generation**

**Module:** `DailyArtifactWriter`

**Actions:**
1. Collect all execution data:
   - VIX and regime
   - Raw signals by strategy
   - Executed signals
   - Placed/filled/rejected orders
   - Portfolio heat, P&L, drawdown
   - Open positions
   - Runtime, data freshness
   - Errors, warnings
   - Reconciliation status
2. Write JSON artifact: `artifacts/json/YYYY-MM-DD.json`
3. Write Markdown artifact: `artifacts/markdown/YYYY-MM-DD.md`

**Output:** Permanent record of day's execution

---

### 16. **Email Notification**

**Module:** `EmailNotifier`

**Actions:**
1. Collect trade summary
2. Collect position data
3. Generate HTML email with:
   - Trade list
   - Portfolio metrics
   - Errors (if any)
4. Send via SMTP

---

## Terminal State Tracking

**Every signal MUST reach exactly one terminal state:**

| Terminal State | Reason |
|----------------|--------|
| `EXECUTED` | Trade successfully executed |
| `REJECTED` | Insufficient cash, execution error |
| `FILTERED` | Correlation filter, portfolio heat limit |

**Verification:**
```sql
SELECT COUNT(*) FROM signals WHERE asof_date = 'YYYY-MM-DD' AND terminal_state IS NULL;
-- Must return 0
```

---

## Critical Invariants

1. **Single Source of Truth:** All data in `trading.db`
2. **Terminal States:** Every signal has `terminal_state` set
3. **Execution Costs:** All trades record `exec_price`, `slippage_cost`, `commission_cost`
4. **Portfolio Heat:** Exposure updated after each trade, propagates to next strategy
5. **Account Refresh:** Called at start, before reconciliation, after execution
6. **Broker State:** Snapshot saved daily with reconciliation status
7. **Positions Sync:** `positions` table matches broker positions (verified by reconciliation)

---

## Module Invocation Summary

```
1. Phase5Database.__init__()
2. _refresh_account_state() [START]
3. DataValidator.validate_data_file()
4. initialize_strategies()
5. RegimeDetector.get_regime_adjustments()
6. PortfolioRiskManager.check_daily_loss_limit()
7. _refresh_account_state() [BEFORE RECONCILIATION]
8. BrokerReconciler.reconcile_daily()
9. Strategy.generate_signals() [x5]
10. CorrelationFilter.filter_signals() [x5]
11. ExecutionCostModel.calculate_execution_price() [per trade]
12. CashManager.reserve_cash() [per trade]
13. PortfolioRiskManager.can_add_position() [per trade]
14. TradingClient.submit_order() [per trade]
15. Phase5Database.log_trade() [per trade]
16. Phase5Database.update_position() [per trade]
17. Phase5Database.update_signal_terminal_state() [per signal]
18. _refresh_account_state() [AFTER EXECUTION]
19. PerformanceMetrics.add_trade() [per trade]
20. verify_order_statuses()
21. Phase5Database.save_broker_state()
22. DailyArtifactWriter.write_daily_artifact()
23. EmailNotifier.send_daily_summary()
```

---

## Verification Commands

```bash
# Check terminal states
python3 scripts/verify_phase5_day1.py

# Check database
sqlite3 trading.db "SELECT COUNT(*) FROM signals WHERE terminal_state IS NULL;"

# Check trades
sqlite3 trading.db "SELECT * FROM trades WHERE DATE(executed_at) = date('now');"

# Check broker state
sqlite3 trading.db "SELECT * FROM broker_state ORDER BY created_at DESC LIMIT 1;"
```
