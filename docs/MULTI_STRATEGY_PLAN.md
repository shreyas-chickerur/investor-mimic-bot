# Multi-Strategy Testing Framework

## Overview

Run 5 different trading strategies concurrently on your Alpaca paper account to find the best performer over 1 month.

---

## 🤖 **5 Proposed Strategies**

### **Strategy 1: RSI Mean Reversion (Current)**
- **Logic:** Buy when RSI < 30, sell after 20 days
- **Indicators:** RSI, volatility
- **Target:** Oversold bounce plays
- **Risk:** Medium

### **Strategy 2: ML Momentum (Scikit-learn)**
- **Logic:** Random Forest predicts next-day returns
- **Features:** RSI, MACD, volume, price momentum
- **Target:** Trend following
- **Risk:** Medium-High

### **Strategy 3: News Sentiment + Technical**
- **Logic:** Combine news sentiment with technical signals
- **Data:** News API + RSI/MACD
- **Target:** Event-driven trades
- **Risk:** Medium

### **Strategy 4: Moving Average Crossover**
- **Logic:** Buy on golden cross (50-day > 200-day MA)
- **Indicators:** SMA 50, SMA 200, volume
- **Target:** Long-term trends
- **Risk:** Low

### **Strategy 5: Volatility Breakout**
- **Logic:** Buy on volume + price breakouts
- **Indicators:** Bollinger Bands, ATR, volume
- **Target:** Momentum breakouts
- **Risk:** High

---

## 📊 **Performance Metrics**

### **Key Statistics:**
1. **Total Return %** - Overall profit/loss
2. **Sharpe Ratio** - Risk-adjusted returns
3. **Max Drawdown** - Largest peak-to-trough decline
4. **Win Rate %** - Percentage of profitable trades
5. **Average Trade Return** - Mean profit per trade
6. **Number of Trades** - Activity level
7. **Profit Factor** - Gross profit / gross loss
8. **Average Hold Time** - Days per position

### **Risk Metrics:**
- Volatility (standard deviation of returns)
- Beta (correlation to market)
- Sortino Ratio (downside risk-adjusted)
- Maximum consecutive losses

---

## 🏗️ **Architecture**

```
┌─────────────────────────────────────────────┐
│         Alpaca Paper Trading Account        │
│              $100,000 Starting              │
└─────────────────────────────────────────────┘
                      │
        ┌─────────────┼─────────────┐
        │             │             │
    Strategy 1    Strategy 2    Strategy 3...
    ($20k each)   ($20k each)   ($20k each)
        │             │             │
        └─────────────┼─────────────┘
                      │
              ┌───────▼────────┐
              │    Database    │
              │  Performance   │
              │    Tracking    │
              └───────┬────────┘
                      │
              ┌───────▼────────┐
              │ Admin Dashboard│
              │  Compare All   │
              └────────────────┘
```

---

## 💾 **Database Schema**

```sql
-- Strategy definitions
CREATE TABLE strategies (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE,
    description TEXT,
    capital_allocation REAL,
    status TEXT,  -- 'active', 'paused', 'completed'
    created_at TEXT
);

-- Strategy performance tracking
CREATE TABLE strategy_performance (
    id INTEGER PRIMARY KEY,
    strategy_id INTEGER,
    date TEXT,
    portfolio_value REAL,
    cash REAL,
    positions_value REAL,
    total_return_pct REAL,
    daily_return_pct REAL,
    num_positions INTEGER,
    num_trades_today INTEGER
);

-- Individual trades per strategy
CREATE TABLE strategy_trades (
    id INTEGER PRIMARY KEY,
    strategy_id INTEGER,
    symbol TEXT,
    action TEXT,  -- 'BUY', 'SELL'
    shares REAL,
    price REAL,
    value REAL,
    order_id TEXT,
    executed_at TEXT,
    exit_price REAL,
    exit_at TEXT,
    profit_loss REAL,
    return_pct REAL
);

-- Strategy signals (what each bot wants to do)
CREATE TABLE strategy_signals (
    id INTEGER PRIMARY KEY,
    strategy_id INTEGER,
    symbol TEXT,
    signal TEXT,  -- 'BUY', 'SELL', 'HOLD'
    confidence REAL,
    reasoning TEXT,
    generated_at TEXT
);
```

---

## 🎯 **Implementation Plan**

### **Phase 1: Framework (Week 1)**
1. Create strategy base class
2. Implement 5 strategies
3. Set up performance tracking database
4. Build strategy runner (executes all 5 daily)

### **Phase 2: Dashboard (Week 1-2)**
1. Build Flask admin dashboard
2. Add performance comparison charts
3. Show real-time metrics
4. Add strategy enable/disable controls

### **Phase 3: Testing (Month 1)**
1. Run all 5 strategies daily
2. Track performance
3. Collect data
4. Compare results

### **Phase 4: Optimization (After Month 1)**
1. Analyze best performer
2. Tune parameters
3. Deploy winning strategy to production

---

## 📈 **Dashboard Features**

### **Main View:**
- Side-by-side comparison table
- Performance charts (line graph over time)
- Current rankings (best to worst)
- Key metrics at a glance

### **Strategy Detail View:**
- Full trade history
- Performance metrics
- Risk analysis
- Signal history

### **Controls:**
- Pause/resume strategies
- Adjust capital allocation
- Export data to CSV
- Manual trade override

---

## 🚀 **Easy Setup**

```bash
# 1. Initialize strategies
python3 scripts/setup_strategies.py

# 2. Start daily runner
python3 scripts/run_all_strategies.py

# 3. View dashboard
python3 src/strategy_dashboard.py
# Open http://localhost:5000
```

---

## 📊 **Example Dashboard**

```
╔══════════════════════════════════════════════════════════════╗
║              STRATEGY PERFORMANCE DASHBOARD                  ║
║                    Day 30 of 30                              ║
╠══════════════════════════════════════════════════════════════╣
║ Strategy              Return    Sharpe   Trades   Win Rate  ║
╠══════════════════════════════════════════════════════════════╣
║ 🥇 ML Momentum        +12.5%    1.82     45       68%       ║
║ 🥈 News Sentiment     +8.3%     1.45     32       62%       ║
║ 🥉 RSI Mean Reversion +6.1%     1.21     28       57%       ║
║ 4️⃣ MA Crossover       +3.2%     0.95     12       50%       ║
║ 5️⃣ Volatility Breakout -2.1%    0.45     38       42%       ║
╚══════════════════════════════════════════════════════════════╝
```

---

## 🎓 **Research-Backed Strategies**

### **Best Practices from Research:**
1. **Momentum** - Proven to work (Jegadeesh & Titman)
2. **Mean Reversion** - Works in short-term (Poterba & Summers)
3. **ML Models** - Random Forest performs well (López de Prado)
4. **News Sentiment** - Alpha from NLP (Tetlock et al.)
5. **Volatility** - Exploitable patterns (Bollerslev)

### **Optimization Tips:**
- Use walk-forward testing
- Avoid overfitting (max 5-7 features)
- Combine signals (ensemble methods)
- Risk management is key (position sizing)

---

## ✅ **Success Criteria**

After 1 month, the winning strategy should have:
- ✅ Positive returns (> 5%)
- ✅ Sharpe ratio > 1.0
- ✅ Max drawdown < 10%
- ✅ Win rate > 55%
- ✅ Consistent performance (not one lucky trade)

---

## 🔄 **Next Steps**

1. Review and approve this plan
2. I'll build the framework (2-3 hours)
3. Implement all 5 strategies
4. Create the dashboard
5. Start testing tomorrow!

**Ready to build this?** 🚀
