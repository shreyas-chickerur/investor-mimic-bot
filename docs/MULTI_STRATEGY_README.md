# Multi-Strategy Testing Framework

## 🎯 Overview

Test 5 different trading strategies concurrently on your Alpaca paper account to find the best performer over 1 month.

**Total Capital:** $100,000 (Paper Trading)  
**Per Strategy:** $20,000  
**Duration:** 30 days  
**Goal:** Find the winning strategy

---

## 🤖 The 5 Strategies

### 1. RSI Mean Reversion
- **Logic:** Buy when RSI < 30 (oversold), sell after 20 days
- **Risk:** Medium
- **Best For:** Range-bound markets

### 2. ML Momentum
- **Logic:** Random Forest predicts returns from technical features
- **Risk:** Medium-High
- **Best For:** Trending markets

### 3. News Sentiment
- **Logic:** Combines news sentiment with technical indicators
- **Risk:** Medium
- **Best For:** Event-driven opportunities

### 4. Moving Average Crossover
- **Logic:** Buy on golden cross (50/200 MA), sell on death cross
- **Risk:** Low
- **Best For:** Long-term trends

### 5. Volatility Breakout
- **Logic:** Buy on Bollinger Band breakouts with high volume
- **Risk:** High
- **Best For:** Volatile markets

---

## 🚀 Quick Start (Tomorrow Morning)

### Step 1: Setup (One-Time)
```bash
python3 scripts/setup_strategies.py
```

This initializes:
- 5 strategies in database
- $20k capital allocation per strategy
- Performance tracking tables

### Step 2: Run Daily
```bash
python3 scripts/run_strategies_daily.py
```

This executes:
- Fetches market data from Alpaca
- Generates signals for all 5 strategies
- Executes trades on paper account
- Records performance

### Step 3: View Dashboard
```bash
python3 src/strategy_dashboard.py
```

Then open: **http://localhost:5000**

---

## 📊 Dashboard Features

### Main View
- **Rankings:** See which strategy is winning
- **Performance Chart:** Visual comparison
- **Key Metrics:** Return %, trades, positions
- **Real-time Updates:** Auto-refresh every 60 seconds

### Metrics Tracked
1. **Total Return %** - Overall profit/loss
2. **Portfolio Value** - Current value
3. **Number of Trades** - Activity level
4. **Active Positions** - Current holdings
5. **Win Rate** - % profitable trades (coming soon)
6. **Sharpe Ratio** - Risk-adjusted returns (coming soon)

---

## 📅 Daily Workflow

### Morning (9:00 AM)
1. System fetches latest market data
2. Each strategy analyzes data independently
3. Signals generated for all 5 strategies
4. Trades executed on Alpaca paper account
5. Performance recorded in database

### Anytime
- Open dashboard to check rankings
- See which strategy is performing best
- Review trade history
- Monitor positions

### After 30 Days
- Compare final results
- Deploy winning strategy to production
- Optimize parameters based on learnings

---

## 🗄️ Database Structure

### Tables
- `strategies` - Strategy definitions
- `strategy_performance` - Daily snapshots
- `strategy_trades` - All trades
- `strategy_signals` - Generated signals

### Location
`data/strategy_performance.db`

---

## 📈 Performance Metrics

### What to Look For

**After 1 Week:**
- Which strategies are generating signals?
- Are trades executing properly?
- Any obvious issues?

**After 2 Weeks:**
- Early performance trends
- Win rates emerging
- Risk levels appropriate?

**After 1 Month:**
- Clear winner identified
- Statistical significance
- Ready for production deployment

### Success Criteria
- ✅ Positive returns (> 5%)
- ✅ Consistent performance
- ✅ Reasonable trade frequency
- ✅ Manageable risk (drawdown < 10%)

---

## 🔧 Configuration

### Capital Allocation
Edit in `scripts/setup_strategies.py`:
```python
runner.initialize_strategies(total_capital=100000)
```

### Trading Universe
Edit in `src/strategy_runner.py`:
```python
symbols = ['AAPL', 'MSFT', 'GOOGL', ...]  # Add/remove symbols
```

### Strategy Parameters
Each strategy file has configurable parameters:
- `src/strategies/strategy_rsi_mean_reversion.py`
- `src/strategies/strategy_ml_momentum.py`
- etc.

---

## 🐛 Troubleshooting

### Dashboard won't load
```bash
# Check if server is running
ps aux | grep strategy_dashboard

# Restart dashboard
python3 src/strategy_dashboard.py
```

### No signals generated
- Check market data is loading
- Verify strategy logic is correct
- Review logs in terminal

### Trades not executing
- Verify Alpaca credentials in .env
- Check paper trading account status
- Review Alpaca API limits

---

## 📝 Files Created

### Core Framework
- `src/strategy_base.py` - Base class for all strategies
- `src/strategy_database.py` - Performance tracking database
- `src/strategy_runner.py` - Executes all strategies

### Strategies
- `src/strategies/strategy_rsi_mean_reversion.py`
- `src/strategies/strategy_ml_momentum.py`
- `src/strategies/strategy_news_sentiment.py`
- `src/strategies/strategy_ma_crossover.py`
- `src/strategies/strategy_volatility_breakout.py`

### Dashboard
- `src/strategy_dashboard.py` - Web interface

### Scripts
- `scripts/setup_strategies.py` - One-time setup
- `scripts/run_strategies_daily.py` - Daily execution

---

## 🎓 Next Steps

### Tomorrow Morning
1. Run setup: `python3 scripts/setup_strategies.py`
2. Execute first run: `python3 scripts/run_strategies_daily.py`
3. Open dashboard: `python3 src/strategy_dashboard.py`
4. Watch the competition begin!

### This Week
- Run daily (manually or via cron)
- Monitor dashboard
- Verify trades executing correctly

### After 1 Month
- Analyze results
- Choose winning strategy
- Deploy to production
- Optimize parameters

---

## 💡 Tips

1. **Be Patient** - 30 days needed for statistical significance
2. **Monitor Daily** - Check dashboard regularly
3. **Don't Interfere** - Let strategies run independently
4. **Document Learnings** - Note what works and what doesn't
5. **Iterate** - Use insights to improve strategies

---

## ✅ Ready to Start!

Everything is built and ready. Tomorrow morning:

```bash
# 1. Setup (one-time)
python3 scripts/setup_strategies.py

# 2. Run strategies
python3 scripts/run_strategies_daily.py

# 3. View dashboard
python3 src/strategy_dashboard.py
```

**Good luck finding your winning strategy!** 🚀
