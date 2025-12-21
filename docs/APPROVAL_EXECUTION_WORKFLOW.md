# Approval to Execution Workflow

## Overview

The system now implements a complete approval-to-execution workflow where user decisions directly control which trades execute on Alpaca.

---

## 🔄 Complete Workflow

### **1. Signal Generation (Automated)**
```
Daily workflow runs → Trading signals generated → Checks AUTO_TRADE config
```

### **2. Manual Approval Required (AUTO_TRADE=false)**
```
System creates approval request → Sends email → User receives notification
```

### **3. User Reviews (Manual)**
```
User clicks "Review Trades" → Comprehensive approval page opens
User reviews each trade individually → Selects Approve ✓ or Reject ✗
```

### **4. Trade Execution (Automated)**
```
User clicks "Submit Decisions" → System processes form
Approved trades → Execute on Alpaca immediately
Rejected trades → Skipped, no execution
```

---

## ✅ What Gets Executed

**Only approved trades execute on Alpaca:**

| User Decision | Action |
|---------------|--------|
| **Approve ✓** | Trade executes on Alpaca immediately |
| **Reject ✗** | Trade is skipped, no execution |

**Example:**
- 4 trades proposed
- User approves 3, rejects 1
- **Result:** Only 3 trades execute on Alpaca

---

## 🎯 Key Features

### **1. Manual Review Required**
- ✅ No bulk "Approve All" button
- ✅ No sticky decision section
- ✅ User must scroll through all trades
- ✅ Forces deliberate decision-making

### **2. Direct Alpaca Execution**
- ✅ Approved trades execute immediately
- ✅ Market orders submitted to Alpaca
- ✅ Order IDs returned for tracking
- ✅ Failed trades logged with errors

### **3. Complete Audit Trail**
- ✅ All decisions logged to database
- ✅ Execution results recorded
- ✅ Order IDs stored
- ✅ Timestamps for everything

---

## 📊 Execution Results

After submitting decisions, the system returns:

```python
{
    'approved': [list of approved trades],
    'rejected': [list of rejected trades],
    'executed': [
        {
            'trade': {...},
            'order_id': 'abc123',
            'status': 'accepted'
        }
    ],
    'failed': [
        {
            'trade': {...},
            'error': 'Insufficient buying power'
        }
    ],
    'summary': {
        'total_trades': 4,
        'approved': 3,
        'rejected': 1,
        'executed': 3,
        'failed': 0,
        'timestamp': '2025-12-20T18:00:00'
    }
}
```

---

## 🔧 Technical Implementation

### **Approval Handler** (`src/approval_handler.py`)
```python
def process_approval_decisions(request_id, decisions):
    # Get pending request
    request = get_pending_request(request_id)
    
    # Execute approved trades on Alpaca
    executor = TradeExecutor()
    results = executor.execute_approved_trades(decisions, trades)
    
    # Log results
    executor.log_execution_results(results, request_id)
    
    return results
```

### **Trade Executor** (`src/trade_executor.py`)
```python
def execute_approved_trades(approval_decisions, trades):
    for i, trade in enumerate(trades):
        decision = approval_decisions.get(f'trade_{i}')
        
        if decision == 'approve':
            # Execute on Alpaca
            result = _execute_single_trade(trade)
            
            if result['success']:
                executed.append(result)
            else:
                failed.append(result)
        else:
            rejected.append(trade)
    
    return results
```

### **Single Trade Execution**
```python
def _execute_single_trade(trade):
    # Create market order
    order_data = MarketOrderRequest(
        symbol=trade['symbol'],
        qty=trade['shares'],
        side=OrderSide.BUY,  # or SELL
        time_in_force=TimeInForce.DAY
    )
    
    # Submit to Alpaca
    order = trading_client.submit_order(order_data)
    
    return {
        'success': True,
        'order_id': order.id,
        'status': order.status
    }
```

---

## 📝 Example Flow

### **Scenario: 4 Proposed Trades**

**Email Received:**
```
4 trades pending approval
Total investment: $9,443.25
```

**User Reviews on Approval Page:**
- AAPL: 10 shares @ $185.50 → **Approve ✓**
- MSFT: 8 shares @ $375.25 → **Approve ✓**
- GOOGL: 15 shares @ $140.75 → **Reject ✗** (too risky)
- NVDA: 5 shares @ $495.00 → **Approve ✓**

**User Clicks "Submit Decisions"**

**System Executes:**
```
✅ EXECUTED: AAPL - 10 shares - Order ID: abc123
✅ EXECUTED: MSFT - 8 shares - Order ID: def456
⏭️  REJECTED: GOOGL - 15 shares
✅ EXECUTED: NVDA - 5 shares - Order ID: ghi789

📊 EXECUTION SUMMARY:
   Total Trades: 4
   Approved: 3
   Rejected: 1
   Successfully Executed: 3
   Failed: 0
```

**Result on Alpaca:**
- 3 new positions opened (AAPL, MSFT, NVDA)
- GOOGL not purchased
- Total investment: $7,332.00 (instead of $9,443.25)

---

## 🛡️ Safety Features

### **1. One-Time Use Tokens**
- Approval links work only once
- Prevents duplicate submissions
- Expires after 24 hours

### **2. Request Validation**
- Verifies request exists
- Checks not already processed
- Validates all form data

### **3. Error Handling**
- Failed trades logged
- Errors reported to user
- No partial executions

### **4. Audit Trail**
- Every decision logged
- Execution results stored
- Order IDs tracked
- Timestamps recorded

---

## 🔍 Monitoring & Verification

### **Check Execution Results:**
```python
from approval_handler import ApprovalHandler

handler = ApprovalHandler()
status = handler.get_approval_status(request_id)
# Returns: 'pending', 'processed', or 'not_found'
```

### **View Alpaca Orders:**
```python
from alpaca.trading.client import TradingClient

client = TradingClient(api_key, secret_key, paper=True)
orders = client.get_orders()

for order in orders:
    print(f"{order.symbol}: {order.qty} shares - {order.status}")
```

### **Check Positions:**
```python
positions = client.get_all_positions()

for position in positions:
    print(f"{position.symbol}: {position.qty} shares @ ${position.current_price}")
```

---

## ⚙️ Configuration

### **Enable Manual Approval:**
```bash
# .env
AUTO_TRADE=false  # Requires manual approval
```

### **Enable Automatic Trading:**
```bash
# .env
AUTO_TRADE=true  # Executes immediately, no approval
```

---

## 📊 Database Tables

### **pending_approvals**
```sql
CREATE TABLE pending_approvals (
    request_id TEXT PRIMARY KEY,
    created_at TEXT,
    trades_json TEXT,
    portfolio_value REAL,
    cash REAL,
    status TEXT,  -- 'pending', 'processed'
    approved_at TEXT,
    decisions_json TEXT
);
```

### **Query Example:**
```sql
SELECT * FROM pending_approvals 
WHERE status = 'processed' 
ORDER BY approved_at DESC 
LIMIT 10;
```

---

## ✅ Summary

**The approval-to-execution workflow ensures:**

1. ✅ User reviews every trade manually
2. ✅ Only approved trades execute on Alpaca
3. ✅ Rejected trades are skipped
4. ✅ Complete audit trail maintained
5. ✅ Execution results logged
6. ✅ Order IDs tracked
7. ✅ Errors handled gracefully

**Your decisions directly control what trades execute on your Alpaca account!** 🎯
