# Trading Database Schema (Phase 5)

**Database:** `trading.db`  
**Purpose:** Single source of truth for Phase 5 paper trading operational validation  
**Date:** 2024-12-24  
**Schema Version:** 1.0

---

## Complete Table List

```
broker_state
positions
signals
sqlite_sequence (internal)
strategies
system_state
trades
```

---

## Table Definitions

### 1. `strategies`

Strategy definitions and capital allocation.

| Column | Type | NotNull | Default | PK | Description |
|--------|------|---------|---------|-------|-------------|
| `id` | INTEGER | No | | Yes | Strategy ID (auto-increment) |
| `name` | TEXT | Yes | | No | Strategy name (UNIQUE) |
| `description` | TEXT | No | | No | Strategy description |
| `capital_allocation` | REAL | Yes | | No | Capital allocated to strategy |
| `initial_capital` | REAL | Yes | | No | Starting capital |
| `status` | TEXT | No | 'active' | No | Status (active/inactive) |
| `created_at` | TEXT | No | CURRENT_TIMESTAMP | No | Creation timestamp |

**Constraints:**
- UNIQUE(name)

**Foreign Keys:** None

**Current Rows:** 0

---

### 2. `signals`

Trading signals with terminal state tracking. **CRITICAL:** Every signal MUST reach exactly one terminal state.

| Column | Type | NotNull | Default | PK | Description |
|--------|------|---------|---------|-------|-------------|
| `id` | INTEGER | No | | Yes | Signal ID (auto-increment) |
| `strategy_id` | INTEGER | Yes | | No | Strategy that generated signal |
| `symbol` | TEXT | Yes | | No | Stock symbol |
| `signal_type` | TEXT | Yes | | No | Signal type (BUY/SELL) |
| `confidence` | REAL | No | | No | Signal confidence (0-1) |
| `reasoning` | TEXT | No | | No | Why signal was generated |
| `asof_date` | TEXT | Yes | | No | Date signal was generated (YYYY-MM-DD) |
| `generated_at` | TEXT | No | CURRENT_TIMESTAMP | No | Timestamp generated |
| `terminal_state` | TEXT | No | | No | Terminal state (EXECUTED/REJECTED/FILTERED) |
| `terminal_reason` | TEXT | No | | No | Why signal reached terminal state |
| `terminal_at` | TEXT | No | | No | When terminal state was reached |

**Constraints:** None

**Foreign Keys:**
- `strategy_id` → `strategies.id`

**Current Rows:** 0

**Terminal States:**
- `EXECUTED` - Trade successfully submitted to broker
- `REJECTED` - Insufficient cash, execution error, reconciliation failure
- `FILTERED` - Correlation filter, portfolio heat limit
- `REJECTED_BY_RECONCILIATION` - Reconciliation failed before execution

**INVARIANT:** Every signal with `asof_date = today` MUST have `terminal_state IS NOT NULL` by end of run.

---

### 3. `trades`

Executed trades with full cost breakdown. Records actual execution details.

| Column | Type | NotNull | Default | PK | Description |
|--------|------|---------|---------|-------|-------------|
| `id` | INTEGER | No | | Yes | Trade ID (auto-increment) |
| `strategy_id` | INTEGER | Yes | | No | Strategy that executed trade |
| `signal_id` | INTEGER | No | | No | Signal that triggered trade |
| `symbol` | TEXT | Yes | | No | Stock symbol |
| `action` | TEXT | Yes | | No | BUY or SELL |
| `shares` | REAL | Yes | | No | Number of shares |
| `requested_price` | REAL | Yes | | No | Price requested |
| `exec_price` | REAL | Yes | | No | Actual execution price (with slippage) |
| `slippage_cost` | REAL | No | 0 | No | Slippage cost ($) |
| `commission_cost` | REAL | No | 0 | No | Commission cost ($) |
| `total_cost` | REAL | No | 0 | No | Total transaction cost ($) |
| `notional` | REAL | Yes | | No | Total notional value |
| `order_id` | TEXT | No | | No | Broker order ID |
| `executed_at` | TEXT | Yes | | No | Execution timestamp |
| `pnl` | REAL | No | | No | Realized P&L (for closed positions) |

**Constraints:** None

**Foreign Keys:**
- `strategy_id` → `strategies.id`
- `signal_id` → `signals.id`

**Current Rows:** 0

**Notional Calculation:**
- BUY: `notional = exec_price * shares + total_cost`
- SELL: `notional = exec_price * shares - total_cost`

**INVARIANT:** If reconciliation failed, `trades` table MUST be empty for that run.

---

### 4. `positions`

Current open positions. Updated after each trade execution.

| Column | Type | NotNull | Default | PK | Description |
|--------|------|---------|---------|-------|-------------|
| `id` | INTEGER | No | | Yes | Position ID (auto-increment) |
| `strategy_id` | INTEGER | Yes | | No | Strategy holding position |
| `symbol` | TEXT | Yes | | No | Stock symbol |
| `shares` | REAL | Yes | | No | Number of shares |
| `avg_price` | REAL | Yes | | No | Average entry price |
| `current_price` | REAL | No | | No | Current market price |
| `market_value` | REAL | No | | No | Current market value |
| `unrealized_pnl` | REAL | No | | No | Unrealized P&L |
| `last_updated` | TEXT | Yes | | No | Last update timestamp |

**Constraints:**
- UNIQUE(strategy_id, symbol)

**Foreign Keys:**
- `strategy_id` → `strategies.id`

**Current Rows:** 0

**INVARIANT:** Positions in this table MUST match broker positions (verified by reconciliation).

---

### 5. `broker_state`

Daily broker state snapshots for reconciliation audit trail.

| Column | Type | NotNull | Default | PK | Description |
|--------|------|---------|---------|-------|-------------|
| `id` | INTEGER | No | | Yes | Snapshot ID (auto-increment) |
| `snapshot_date` | TEXT | Yes | | No | Date of snapshot (YYYY-MM-DD) |
| `cash` | REAL | Yes | | No | Cash balance |
| `portfolio_value` | REAL | Yes | | No | Total portfolio value |
| `buying_power` | REAL | Yes | | No | Buying power |
| `positions_json` | TEXT | No | | No | Positions as JSON array |
| `reconciliation_status` | TEXT | No | | No | PASS or FAIL |
| `discrepancies_json` | TEXT | No | | No | Discrepancies as JSON array |
| `created_at` | TEXT | No | CURRENT_TIMESTAMP | No | Creation timestamp |

**Constraints:** None

**Foreign Keys:** None

**Current Rows:** 0

**INVARIANT:** At least one snapshot MUST exist per run with `snapshot_date = today`.

---

### 6. `system_state`

System-wide state tracking (key-value store).

| Column | Type | NotNull | Default | PK | Description |
|--------|------|---------|---------|-------|-------------|
| `key` | TEXT | No | | Yes | State key (PRIMARY KEY) |
| `value` | TEXT | No | | No | State value |
| `timestamp` | DATETIME | No | CURRENT_TIMESTAMP | No | Last updated |

**Constraints:**
- PRIMARY KEY(key)

**Foreign Keys:** None

**Current Rows:** 0

**Usage:** Stores system-wide flags like `PHASE_5_INITIAL_STATE_RESET`.

---

## Missing: run_id Column

**CRITICAL ISSUE:** No `run_id` column exists in any table. This prevents:
- Tracking which signals/trades/snapshots belong to the same execution
- Verifying invariants per run
- Auditing historical runs

**REQUIRED:** Add `run_id TEXT NOT NULL` to:
- `signals`
- `trades`
- `broker_state`

**Format:** `run_id = YYYYMMDD_HHMMSS_<random_suffix>` (e.g., `20241224_153000_a7f3`)

---

## Critical Invariants (Phase 5)

These MUST be enforced by verification script:

### A. Signal-Terminal State Count Match
```sql
-- For a given run_id:
SELECT COUNT(*) FROM signals WHERE run_id = ?;
-- MUST EQUAL
SELECT COUNT(*) FROM signals WHERE run_id = ? AND terminal_state IS NOT NULL;
```

### B. No Signal Without Terminal State
```sql
-- MUST return 0:
SELECT COUNT(*) FROM signals 
WHERE run_id = ? AND terminal_state IS NULL;
```

### C. No Signal With Multiple Terminal States
**Enforced by schema:** `terminal_state` is a single column, not a separate table.

### D. Reconciliation Failure → No Trades
```sql
-- If reconciliation_status = 'FAIL':
SELECT COUNT(*) FROM trades WHERE run_id = ?;
-- MUST return 0
```

### E. Dry-Run → No Broker Orders
**Enforced by code:** Dry-run mode does not call `trading_client.submit_order()`.
- Trades table MUST be empty in dry-run
- OR trades must have `order_id = 'DRYRUN'` (if we choose to log dry-run trades)

### F. Broker State Snapshots
```sql
-- MUST have at least 1 snapshot per run:
SELECT COUNT(*) FROM broker_state WHERE run_id = ?;
-- MUST return >= 1
```

**Recommended:** 3 snapshots per run:
1. Start (before execution)
2. Reconciliation point (if enabled)
3. End (after execution)

---

## Schema Migration Required

**Current State:** Schema exists but lacks `run_id` tracking.

**Required Changes:**
1. Add `run_id TEXT NOT NULL` to `signals`, `trades`, `broker_state`
2. Add index on `run_id` for performance
3. Update `Phase5Database` to accept and persist `run_id`
4. Update `multi_strategy_main.py` to generate and pass `run_id`

**Migration Script:** TBD (will be idempotent)

---

## Verification Commands

```bash
# Check schema
sqlite3 trading.db ".schema"

# Check for signals without terminal states
sqlite3 trading.db "SELECT COUNT(*) FROM signals WHERE terminal_state IS NULL;"

# Check today's trades
sqlite3 trading.db "SELECT * FROM trades WHERE DATE(executed_at) = date('now');"

# Check broker state snapshots
sqlite3 trading.db "SELECT * FROM broker_state ORDER BY created_at DESC LIMIT 3;"

# Verify invariants
python3 scripts/check_phase5_invariants.py --run-id <run_id>
```

---

## Notes

- **Survivorship Bias:** Acknowledged, cannot be fully removed from historical data
- **Lookahead Bias:** Eliminated by 4:15 PM ET execution timing
- **Schema Version:** 1.0 (2024-12-24)
- **Next Review:** After first production run with `run_id` tracking
