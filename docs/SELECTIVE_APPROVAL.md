# 🎯 Selective Trade Approval System

**Complete control over individual trade execution**

---

## 📋 Overview

The selective trade approval system allows you to approve or reject each proposed trade individually, giving you complete control over which positions to enter.

### **Key Features**

✅ **Individual Approval** - Approve/reject each trade separately  
✅ **Flexible Control** - Mix approved and rejected trades  
✅ **Selective Execution** - Only approved trades are executed  
✅ **Visual Clarity** - Clear ✓/✗ buttons for each trade  
✅ **Full Tracking** - System tracks status of each trade  

---

## 📧 Email Interface

### **What You'll See**

Each proposed trade has its own action buttons:

```
Symbol | Shares | Price  | Value    | Allocation | Action
-------|--------|--------|----------|------------|--------
GOOGL  | 15.2   | $296   | $4,510   | 7.8%       | [✓] [✗]
UBER   | 45.3   | $128   | $5,821   | 6.5%       | [✓] [✗]
AAPL   | 25.0   | $185   | $4,637   | 5.2%       | [✓] [✗]
MSFT   | 12.5   | $378   | $4,736   | 5.0%       | [✓] [✗]
AMZN   | 8.5    | $178   | $1,514   | 1.7%       | [✓] [✗]
```

### **How to Use**

1. **Review each trade** - Check symbol, quantity, price, value
2. **Click ✓** to approve a trade you want to execute
3. **Click ✗** to reject a trade you don't want
4. **Mix and match** - Approve some, reject others
5. **System executes** only the approved trades

---

## 🔄 How It Works

### **Backend Flow**

```
1. System generates trade recommendations
   ↓
2. Email sent with individual buttons for each trade
   ↓
3. You click ✓ or ✗ for each trade
   ↓
4. API updates trade status (approved=True/False)
   ↓
5. Execution script reads approved trades only
   ↓
6. Only approved trades are executed
```

### **Trade Status Tracking**

Each trade has three possible states:
- **`approved: null`** - Pending (no action taken yet)
- **`approved: true`** - Approved (will be executed)
- **`approved: false`** - Rejected (will not be executed)

---

## 🛠️ Technical Implementation

### **1. Data Model**

```python
class TradeProposal(BaseModel):
    symbol: str
    quantity: float
    estimated_price: Optional[float] = None
    estimated_value: Optional[float] = None
    allocation_pct: Optional[float] = None
    approved: Optional[bool] = None  # Track approval status
```

### **2. API Endpoints**

**Approve Individual Trade:**
```
POST /api/v1/approve/{request_id}/approve-trade/{trade_index}
```

**Reject Individual Trade:**
```
POST /api/v1/approve/{request_id}/reject-trade/{trade_index}
```

**Get Approved Trades:**
```python
manager = TradeApprovalManager()
approved_trades = manager.get_approved_trades(request_id)
```

### **3. Email Template**

Individual buttons generated for each trade:
```python
for i, trade in enumerate(trades):
    approve_url = f"...approve-trade/{i}"
    reject_url = f"...reject-trade/{i}"
    # Generate ✓ and ✗ buttons
```

---

## 📊 Usage Examples

### **Example 1: Approve All**

Click ✓ on all 5 trades → All 5 trades execute

**Result:**
- GOOGL: ✓ Executed
- UBER: ✓ Executed
- AAPL: ✓ Executed
- MSFT: ✓ Executed
- AMZN: ✓ Executed

### **Example 2: Selective Approval**

Click ✓ on GOOGL, AAPL, MSFT  
Click ✗ on UBER, AMZN

**Result:**
- GOOGL: ✓ Executed
- UBER: ✗ Skipped
- AAPL: ✓ Executed
- MSFT: ✓ Executed
- AMZN: ✗ Skipped

### **Example 3: Reject All**

Click ✗ on all 5 trades → No trades execute

**Result:**
- All trades skipped
- Cash remains in account
- No positions opened

---

## 🎯 Use Cases

### **When to Use Selective Approval**

**1. Risk Management**
- Approve only low-volatility stocks
- Skip high-risk positions
- Control total exposure

**2. Sector Diversification**
- Too many tech stocks? Reject some
- Want more diversification? Approve different sectors
- Balance your portfolio manually

**3. Personal Preferences**
- Don't like a specific company? Reject it
- Already own a stock? Skip it
- Have conviction in one? Approve only that

**4. Market Conditions**
- Volatile market? Approve fewer trades
- Confident market? Approve more
- Uncertain? Cherry-pick the best

**5. Capital Constraints**
- Limited cash? Approve top 3 only
- Want to save cash? Reject lower-conviction trades
- Gradual entry? Approve 1-2 at a time

---

## 💡 Best Practices

### **Review Criteria**

**Before approving a trade, consider:**

✅ **Signal Strength** - Is the conviction score high?  
✅ **Volatility** - Can you handle the risk?  
✅ **Allocation** - Is the position size appropriate?  
✅ **Diversification** - Does it fit your portfolio?  
✅ **Personal Knowledge** - Do you know the company?  
✅ **Market Conditions** - Is now a good time?  

### **Approval Strategies**

**Conservative:**
- Approve only top 3 highest conviction
- Skip anything with >25% volatility
- Limit total exposure to 50% of capital

**Moderate:**
- Approve top 5-7 trades
- Skip only highest volatility
- Use 70-80% of capital

**Aggressive:**
- Approve all trades
- Trust the system completely
- Use 85-90% of capital

---

## 🔧 API Usage

### **Python Example**

```python
from services.approval.trade_approval import TradeApprovalManager

manager = TradeApprovalManager()

# Approve specific trades
manager.approve_trade(request_id="abc-123", trade_index=0)  # GOOGL
manager.approve_trade(request_id="abc-123", trade_index=2)  # AAPL
manager.approve_trade(request_id="abc-123", trade_index=3)  # MSFT

# Reject others
manager.reject_trade(request_id="abc-123", trade_index=1)  # UBER
manager.reject_trade(request_id="abc-123", trade_index=4)  # AMZN

# Get approved trades for execution
approved = manager.get_approved_trades(request_id="abc-123")
print(f"Executing {len(approved)} approved trades")
```

### **HTTP Example**

```bash
# Approve GOOGL (index 0)
curl -X POST http://localhost:8000/api/v1/approve/abc-123/approve-trade/0

# Reject UBER (index 1)
curl -X POST http://localhost:8000/api/v1/approve/abc-123/reject-trade/1

# Approve AAPL (index 2)
curl -X POST http://localhost:8000/api/v1/approve/abc-123/approve-trade/2
```

---

## 📈 Execution Logic

### **How Approved Trades Are Executed**

```python
# In execution script
manager = TradeApprovalManager()
approved_trades = manager.get_approved_trades(request_id)

for trade in approved_trades:
    # Only execute approved trades
    execute_trade(
        symbol=trade.symbol,
        quantity=trade.quantity,
        price=trade.estimated_price
    )
```

### **What Happens to Rejected Trades**

- ❌ Not executed
- ❌ No order placed
- ❌ No capital allocated
- ✅ Cash remains available
- ✅ Can be used for other opportunities

---

## 🎉 Benefits

### **Compared to All-or-Nothing Approval**

**Old System:**
- Approve all 10 trades or reject all 10
- No flexibility
- All or nothing

**New System:**
- Approve any combination
- Full flexibility
- Complete control

### **Key Advantages**

1. **Risk Control** - Limit exposure to specific stocks
2. **Flexibility** - Adapt to changing conditions
3. **Confidence** - Only execute what you're comfortable with
4. **Learning** - Start small, scale up as you gain confidence
5. **Customization** - Tailor to your investment style

---

## 🚀 Getting Started

### **1. Receive Email**

Wait for daily email with proposed trades

### **2. Review Trades**

Look at each trade's:
- Symbol and company
- Quantity and price
- Total value
- Allocation percentage

### **3. Make Decisions**

For each trade, decide:
- ✓ Approve if you want to execute
- ✗ Reject if you want to skip

### **4. Click Buttons**

Click the ✓ or ✗ button for each trade

### **5. Confirmation**

System confirms each action and tracks status

### **6. Execution**

Only approved trades are executed automatically

---

## 📝 Summary

**Selective trade approval gives you:**

✅ Individual control over each trade  
✅ Flexibility to approve any combination  
✅ Risk management through selective execution  
✅ Confidence in your investment decisions  
✅ Complete transparency and control  

**The system is now fully functional with selective approval capabilities!** 🎯

Your investment bot respects your choices and only executes the trades you explicitly approve.
