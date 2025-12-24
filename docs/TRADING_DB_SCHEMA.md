# Trading Database Schema (Phase 5)

**Database:** `trading.db`  
**Purpose:** Single source of truth for Phase 5 paper trading operational validation  
**Created:** 2024-12-24  

---

## Tables

### 1. `strategies`

Stores trading strategy definitions.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Strategy ID |
| `name` | TEXT | UNIQUE NOT NULL | Strategy name |
| `description` | TEXT | | Strategy description |
| `capital_allocation` | REAL | NOT NULL | Capital allocated |
| `initial_capital` | REAL | NOT NULL | Starting capital |
| `status` | TEXT | DEFAULT 'active' | Status (active/inactive) |
| `created_at` | TEXT | DEFAULT CURRENT_TIMESTAMP | Creation timestamp |

---

### 2. `signals`

Trading signals with terminal state tracking.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Signal ID |
| `strategy_id` | INTEGER | NOT NULL, FK → strategies.id | Strategy that generated signal |
| `symbol` | TEXT | NOT NULL | Stock symbol |
| `signal_type` | TEXT | NOT NULL | Signal type (BUY/SELL) |
| `confidence` | REAL | | Signal confidence (0-1) |
| `reasoning` | TEXT | | Why signal was generated |
| `asof_date` | TEXT | NOT NULL | Date signal was generated |
| `generated_at` | TEXT | DEFAULT CURRENT_TIMESTAMP | Timestamp generated |
| `terminal_state` | TEXT | | Terminal state (EXECUTED, REJECTED, FILTERED, etc.) |
| `terminal_reason` | TEXT | | Why signal reached terminal state |
| `terminal_at` | TEXT | | When terminal state was reached |

**Critical:** Every signal MUST reach exactly one terminal state.

---

### 3. `trades`

Executed trades with full cost breakdown.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Trade ID |
| `strategy_id` | INTEGER | NOT NULL, FK → strategies.id | Strategy that executed trade |
| `signal_id` | INTEGER | FK → signals.id | Signal that triggered trade (if any) |
| `symbol` | TEXT | NOT NULL | Stock symbol |
| `action` | TEXT | NOT NULL | BUY or SELL |
| `shares` | REAL | NOT NULL | Number of shares |
| `requested_price` | REAL | NOT NULL | Price requested |
| `exec_price` | REAL | NOT NULL | Actual execution price (with slippage) |
| `slippage_cost` | REAL | DEFAULT 0 | Slippage cost ($) |
| `commission_cost` | REAL | DEFAULT 0 | Commission cost ($) |
| `total_cost` | REAL | DEFAULT 0 | Total transaction cost ($) |
| `notional` | REAL | NOT NULL | Total notional value |
| `order_id` | TEXT | | Broker order ID |
| `executed_at` | TEXT | NOT NULL | Execution timestamp |
| `pnl` | REAL | | Realized P&L (for closed positions) |

**Notional Calculation:**
- BUY: `notional = exec_price * shares + total_cost`
- SELL: `notional = exec_price * shares - total_cost`

---

### 4. `positions`

Current open positions.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Position ID |
| `strategy_id` | INTEGER | NOT NULL, FK → strategies.id | Strategy holding position |
| `symbol` | TEXT | NOT NULL | Stock symbol |
| `shares` | REAL | NOT NULL | Number of shares |
| `avg_price` | REAL | NOT NULL | Average entry price |
| `current_price` | REAL | | Current market price |
| `market_value` | REAL | | Current market value |
| `unrealized_pnl` | REAL | | Unrealized P&L |
| `last_updated` | TEXT | NOT NULL | Last update timestamp |

**Constraint:** UNIQUE(strategy_id, symbol)

---

### 5. `broker_state`

Daily broker state snapshots for reconciliation.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Snapshot ID |
| `snapshot_date` | TEXT | NOT NULL | Date of snapshot |
| `cash` | REAL | NOT NULL | Cash balance |
| `portfolio_value` | REAL | NOT NULL | Total portfolio value |
| `buying_power` | REAL | NOT NULL | Buying power |
| `positions_json` | TEXT | | Positions as JSON |
| `reconciliation_status` | TEXT | | PASS or FAIL |
| `discrepancies_json` | TEXT | | Discrepancies as JSON |
| `created_at` | TEXT | DEFAULT CURRENT_TIMESTAMP | Creation timestamp |

---

### 6. `system_state`

System-wide state tracking.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `key` | TEXT | PRIMARY KEY | State key |
| `value` | TEXT | | State value |
| `timestamp` | DATETIME | DEFAULT CURRENT_TIMESTAMP | Last updated |

---

## Critical Invariants

1. **Signal Terminal States:** Every signal in `signals` table MUST have `terminal_state` set after processing
2. **Trade Costs:** All trades MUST record `exec_price`, `slippage_cost`, `commission_cost`, and `total_cost`
3. **Position Consistency:** Positions in `positions` table MUST match broker positions (verified by reconciliation)
4. **Broker State:** Daily `broker_state` snapshot MUST be saved before reconciliation
5. **Single Source of Truth:** All Phase 5 components read/write to this database only

---

## Indices

None currently. Add if query performance becomes an issue.

---

## Migration from Legacy

Legacy `strategy_performance.db` schema has been retired. All Phase 5 code uses `trading.db` with this schema.

**Backup:** Old database backed up to `trading.db.backup.YYYYMMDD_HHMMSS`
