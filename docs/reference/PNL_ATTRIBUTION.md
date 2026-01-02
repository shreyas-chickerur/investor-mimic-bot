# P&L Attribution System

**Status:** ✅ Implemented  
**Date:** January 1, 2026

---

## Overview

The system now has **proper P&L (Profit & Loss) attribution** that tracks which strategy generated which profits or losses. This uses FIFO (First In First Out) lot tracking to accurately calculate realized P&L when positions are closed.

---

## How It Works

### 1. **Position Tracking (FIFO Lots)**

When a strategy buys shares, they're added as "lots":
```python
# Example: RSI Mean Reversion buys 10 AAPL @ $185.50
Lot 1: 10 shares @ $185.50 (entry date: 2026-01-03)
```

If the same strategy buys more later:
```python
# Later: RSI Mean Reversion buys 5 more AAPL @ $190.00
Lot 1: 10 shares @ $185.50
Lot 2: 5 shares @ $190.00
```

### 2. **P&L Calculation on Sells (FIFO)**

When selling, the system uses **FIFO** (oldest lots first):

**Example: Sell 12 shares @ $192.00**
```
Lot 1: 10 shares @ $185.50 → $192.00 = +$65.00 (10 × $6.50)
Lot 2: 2 shares @ $190.00 → $192.00 = +$4.00 (2 × $2.00)
Remaining: Lot 2 has 3 shares @ $190.00 left

Total Realized P&L: $69.00 (minus costs)
```

### 3. **Per-Strategy Attribution**

Each trade is linked to its strategy via `strategy_id`:
- **RSI Mean Reversion** (strategy_id=1) tracks its own positions
- **ML Momentum** (strategy_id=2) tracks its own positions
- **Each strategy's P&L is independent**

---

## Database Schema

### Trades Table (Enhanced)
```sql
CREATE TABLE trades (
    id INTEGER PRIMARY KEY,
    strategy_id INTEGER NOT NULL,  -- Links to strategy
    symbol TEXT NOT NULL,
    action TEXT NOT NULL,           -- 'BUY' or 'SELL'
    shares REAL NOT NULL,
    exec_price REAL NOT NULL,
    pnl REAL,                       -- ✅ NOW POPULATED
    executed_at TEXT NOT NULL,
    FOREIGN KEY (strategy_id) REFERENCES strategies(id)
)
```

**Before:** `pnl` column was NULL  
**After:** `pnl` is calculated and stored for every trade

---

## Implementation Details

### PnLCalculator Class

**Location:** `src/pnl_calculator.py`

**Key Methods:**

1. **`calculate_trade_pnl()`** - Calculate P&L for each trade
   - BUY: Adds to open lots (P&L = $0)
   - SELL: Matches against open lots using FIFO (P&L = realized gain/loss)

2. **`get_unrealized_pnl()`** - Calculate unrealized P&L for open positions
   - Uses current market price vs. cost basis

3. **`get_strategy_pnl_summary()`** - Get complete P&L for a strategy
   - Realized P&L (from closed trades)
   - Unrealized P&L (from open positions)
   - Total P&L = Realized + Unrealized

### Integration Points

**Execution Engine (`src/execution_engine.py`):**

```python
# When executing a trade:
pnl, explanation = self.pnl_calculator.calculate_trade_pnl(
    strategy.strategy_id,
    symbol,
    action,  # 'BUY' or 'SELL'
    shares,
    exec_price,
    total_costs
)

# Store P&L in database
self.db.log_trade(..., pnl=pnl)
```

**Logs show P&L explanation:**
```
P&L: SELL: 10@$185.50→$192.00 = +$65.00; 2@$190.00→$192.00 = +$4.00 | Total: +$69.00
```

---

## Querying P&L Per Strategy

### Get Realized P&L for a Strategy
```sql
SELECT 
    s.name as strategy,
    SUM(t.pnl) as realized_pnl,
    COUNT(*) as trades
FROM trades t
JOIN strategies s ON t.strategy_id = s.id
WHERE t.pnl IS NOT NULL
GROUP BY s.name
ORDER BY realized_pnl DESC;
```

### Get Today's P&L by Strategy
```sql
SELECT 
    s.name as strategy,
    SUM(t.pnl) as daily_pnl,
    COUNT(*) as trades
FROM trades t
JOIN strategies s ON t.strategy_id = s.id
WHERE DATE(t.executed_at) = DATE('now')
  AND t.pnl IS NOT NULL
GROUP BY s.name;
```

### Get Strategy Performance Over Time
```sql
SELECT 
    s.name as strategy,
    DATE(t.executed_at) as date,
    SUM(t.pnl) as daily_pnl,
    SUM(SUM(t.pnl)) OVER (
        PARTITION BY s.name 
        ORDER BY DATE(t.executed_at)
    ) as cumulative_pnl
FROM trades t
JOIN strategies s ON t.strategy_id = s.id
WHERE t.pnl IS NOT NULL
GROUP BY s.name, DATE(t.executed_at)
ORDER BY s.name, date;
```

---

## Email Reports

The daily email digest now includes **accurate per-strategy P&L**:

```
Strategy Performance (Today)
┌─────────────────────┬────────┬──────────┬──────────┬───────────┐
│ Strategy            │ Trades │ Win Rate │ Avg P&L  │ Total P&L │
├─────────────────────┼────────┼──────────┼──────────┼───────────┤
│ RSI Mean Reversion  │   5    │  60.0%   │  $25.50  │  +$127.50 │
│ ML Momentum         │   4    │  75.0%   │  $22.31  │   +$89.25 │
│ MA Crossover        │   3    │  66.7%   │  $15.27  │   +$45.80 │
│ News Sentiment      │   2    │  50.0%   │  -$6.20  │   -$12.40 │
└─────────────────────┴────────┴──────────┴──────────┴───────────┘
```

---

## Example Scenario

### Day 1: RSI Mean Reversion
- BUY 10 AAPL @ $185.50 → P&L: $0 (opening position)
- BUY 5 MSFT @ $375.00 → P&L: $0 (opening position)

### Day 2: RSI Mean Reversion
- SELL 10 AAPL @ $192.00 → P&L: +$65.00 (10 × $6.50 gain)
- Strategy's Total P&L: +$65.00

### Day 3: ML Momentum (Different Strategy)
- BUY 10 AAPL @ $190.00 → P&L: $0 (ML's own position)
- SELL 10 AAPL @ $195.00 → P&L: +$50.00 (10 × $5.00 gain)
- ML Momentum's Total P&L: +$50.00

**Result:**
- RSI Mean Reversion: +$65.00
- ML Momentum: +$50.00
- **Each strategy's P&L is tracked independently**

---

## Benefits

1. **Accurate Attribution** - Know exactly which strategy is profitable
2. **Performance Analysis** - Compare strategies objectively
3. **Risk Management** - Identify underperforming strategies
4. **Accountability** - Each strategy's track record is clear
5. **Tax Reporting** - Realized P&L properly calculated using FIFO

---

## Verification

### Check P&L is Being Calculated
```bash
sqlite3 trading.db "SELECT COUNT(*) as trades_with_pnl FROM trades WHERE pnl IS NOT NULL;"
```

Should show non-zero count after trades execute.

### View Recent P&L
```bash
sqlite3 trading.db "
SELECT 
    s.name,
    t.symbol,
    t.action,
    t.shares,
    t.exec_price,
    t.pnl
FROM trades t
JOIN strategies s ON t.strategy_id = s.id
ORDER BY t.executed_at DESC
LIMIT 10;
"
```

---

## Technical Notes

- **FIFO Method:** Required for US tax reporting
- **Lot Tracking:** Handles partial position closes correctly
- **Cost Basis:** Includes slippage and commissions
- **Unrealized P&L:** Calculated separately for open positions
- **Thread Safety:** Uses database transactions for consistency

---

**Status:** ✅ Fully implemented and integrated into execution engine  
**Next Run:** January 3, 2026 - P&L will be properly tracked and attributed
