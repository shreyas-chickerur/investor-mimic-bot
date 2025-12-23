# Trading System Improvement Tracker

**Based on:** ChatGPT Expert Review (December 23, 2025)  
**Status:** Implementation in progress

---

## Overview

This document tracks the implementation of expert-recommended improvements to elevate the system from "retail bot" to "junior quant system" quality.

**Assessment:** "Well past toy bot level, approaching junior quant system design territory"

---

## Critical Issues (Fix First)

### ✅ Issue 1: Execution Timing Lookahead Bias - FIXED
**Problem:** Running at 10:00 AM ET with daily bars creates lookahead bias risk  
**Impact:** Inflated backtest results, will fail live  
**Priority:** CRITICAL

**Solution Options:**
1. Run after market close (4:15 PM ET) ✅ **CHOSEN**
2. Explicitly fetch previous day only
3. Switch to intraday bars (30m/1h)

**Implementation:**
- [x] Update GitHub Actions cron to 21:15 UTC (4:15 PM ET)
- [x] Ensure data fetching uses previous trading day only
- [x] Add validation to prevent same-day data usage
- [ ] Test with paper trading

**Files modified:**
- `.github/workflows/daily-trading.yml` - Changed cron to 4:15 PM ET
- `scripts/update_data.py` - Added logic to use previous day if before 4 PM

---

### ✅ Issue 2: RSI Exit Logic Too Naive - FIXED
**Problem:** Fixed 20-day exit holds losers too long, exits winners too early  
**Impact:** Poor expectancy, missed profits  
**Priority:** CRITICAL

**Current:**
```python
SELL if: Held for 20 days
```

**Improved:**
```python
SELL if:
  - RSI > 50 (mean reversion complete) OR
  - Price >= VWAP (profitable exit) OR
  - Held for 20 days (fallback)
```

**Implementation:**
- [x] Add VWAP calculation to data pipeline
- [x] Update RSI strategy exit logic
- [x] Add RSI slope filter for entries (avoid falling knives)
- [x] Add distance from VWAP filter for entries
- [ ] Backtest improvement

**Files modified:**
- `src/strategies/strategy_rsi_mean_reversion.py` - Improved entry/exit logic
- `scripts/update_data.py` - Added VWAP, RSI slope, ATR, ADX calculations

---

### ⏳ Issue 3: Backtest Results Inflated - IN PROGRESS
**Problem:** +146% annual return doesn't account for slippage, costs, biases  
**Impact:** Unrealistic expectations  
**Priority:** HIGH

**Missing:**
- Slippage (5-10 bps per trade)
- Transaction costs ($0.005/share)
- Max drawdown tracking
- Win rate metrics
- Survivorship bias check

**Implementation:**
- [x] Create slippage model (7.5 bps)
- [x] Create commission cost model ($0.005/share)
- [x] Create comprehensive metrics tracker
- [ ] Integrate into execution flow
- [ ] Track max drawdown
- [ ] Calculate win rate
- [ ] Document realistic expectations

**Files created:**
- `src/execution_costs.py` - Slippage and commission modeling
- `src/performance_metrics.py` - Comprehensive metrics (Sharpe, Sortino, Calmar, etc.)

**Files to modify:**
- `src/multi_strategy_main.py` - Integrate cost model and metrics

---

## High-ROI Improvements

### ✅ Improvement 1: Volatility-Adjusted Position Sizing - COMPLETE
**Current:** Fixed 10% per trade  
**Implemented:** Position Size ∝ 1 / ATR(20)

**Target:** 1% portfolio volatility per position

**Benefits:**
- Improved Sharpe ratio
- Better risk-adjusted returns
- Automatic position scaling

**Implementation:**
- [x] Add ATR calculation to data pipeline
- [x] Create volatility-based sizing function
- [x] Update all strategies to use new sizing
- [ ] Backtest improvement

**Files modified:**
- `scripts/update_data.py` (added ATR)
- `src/strategy_base.py` (updated calculate_position_size)
- All 5 strategy files (integrated ATR sizing)

---

### ✅ Improvement 2: Portfolio-Level Risk Controls - COMPLETE
**Current:** Per-strategy rules only  
**Implemented:** Portfolio risk manager

**Added:**
- Max portfolio heat (≤ 30% capital exposed)
- Max correlated exposure
- Max daily loss (-2% → no new trades)

**Implementation:**
- [x] Create portfolio risk manager
- [x] Add exposure tracking
- [x] Add daily loss circuit breaker
- [ ] Integrate with execution flow (next step)

**Files created:**
- `src/portfolio_risk_manager.py`

**Files to modify:**
- `src/multi_strategy_main.py` (integration pending)

---

### ✅ Improvement 3: Strategy Correlation Filter - COMPLETE
**Problem:** Strategies not independent (RSI, Volatility, MA all momentum-based)  
**Solution:** Reject trades if correlation > 0.7 with existing positions

**Implementation:**
- [x] Calculate 60-day rolling correlation
- [x] Add correlation check before trade execution
- [x] Track correlation metrics
- [ ] Test impact on diversification (integration pending)

**Files created:**
- `src/correlation_filter.py`

**Files to modify:**
- `src/multi_strategy_main.py` (integration pending)

---

### ⏳ Improvement 4: Expected Value Signal Scoring
**Current:** "Top 3 signals" by vague confidence  
**Better:** Score = (Expected Return) / (Expected Volatility)

**Implementation:**
- [ ] Calculate historical avg return per signal type
- [ ] Use ATR for volatility estimate
- [ ] Rank signals by EV score
- [ ] Replace top-3 with top-EV

**Files to modify:**
- All strategy files (add EV calculation)
- `src/multi_strategy_main.py` (update prioritization)

---

## Strategy-Specific Improvements

### 📊 Strategy 1: RSI Mean Reversion

**Current Issues:**
- RSI < 30 is crowded
- Catches falling knives

**Improvements:**
- [ ] Add RSI slope filter (must be turning upward)
- [ ] Add distance from VWAP filter
- [ ] Improve exit logic (already covered above)

**Files to modify:**
- `src/strategies/strategy_rsi_mean_reversion.py`

---

### 📊 Strategy 2: MA Crossover

**Current Issues:**
- 50/200 is very slow
- Performs poorly on individual stocks

**Improvements:**
- [ ] Change to 20/100 or EMA-based
- [ ] Add ADX > 20 trend strength filter
- [ ] Consider disabling for individual stocks

**Files to modify:**
- `src/strategies/strategy_ma_crossover.py`
- `scripts/update_data.py` (add ADX)

---

### 📊 Strategy 3: ML Momentum

**Current Issues:**
- Random Forest Regressor suboptimal
- No walk-forward validation

**Improvements:**
- [ ] Change to classifier: P(return_5d > 0)
- [ ] Use Logistic Regression baseline
- [ ] Add XGBoost classifier
- [ ] Implement walk-forward validation
- [ ] Add earnings date purging

**Files to modify:**
- `src/strategies/strategy_ml_momentum.py`
- New: `src/ml_models/`

---

### 📊 Strategy 4: News Sentiment

**Current Issues:**
- Sentiment as trigger is risky
- Latency and headline bias

**Improvements:**
- [ ] Use sentiment as filter, not trigger
- [ ] Require momentum signal AND sentiment confirmation
- [ ] Add sentiment staleness check

**Files to modify:**
- `src/strategies/strategy_news_sentiment.py`

---

### 📊 Strategy 5: Volatility Breakout

**Current Issues:**
- No false breakout protection

**Improvements:**
- [ ] Require close > upper band for 2 consecutive bars
- [ ] OR close > band AND body > 60% of candle
- [ ] Add volume persistence check

**Files to modify:**
- `src/strategies/strategy_volatility_breakout.py`

---

## System Architecture Enhancements

### 🏗️ Enhancement 1: Strategy Weighting by Performance
**Current:** Equal $20K allocation  
**Better:** Weight ∝ Sharpe Ratio (capped), rebalance monthly

**Implementation:**
- [ ] Calculate Sharpe ratio per strategy
- [ ] Implement dynamic allocation
- [ ] Add monthly rebalancing
- [ ] Cap max allocation (e.g., 40%)

**Status:** Not started

---

### 🏗️ Enhancement 2: Regime Detection
**High Value:** Can double Sharpe ratio

**Add:**
- Volatility regime (VIX)
- Trend regime (SPY 200MA)

**Rules:**
- Disable mean reversion in strong trends
- Disable breakouts in low-vol chop

**Implementation:**
- [ ] Add VIX data fetching
- [ ] Add SPY 200MA calculation
- [ ] Create regime classifier
- [ ] Add strategy enable/disable logic

**Status:** Not started

---

### 🏗️ Enhancement 3: Unified Event-Driven Engine
**Future:** Replace daily loop with proper architecture

**Layers:**
1. Signal generation
2. Portfolio construction
3. Execution layer
4. Risk layer

**Status:** Future work

---

## Metrics to Add Immediately

### 📈 Current Metrics
- ✅ Portfolio value
- ✅ Cash available
- ✅ Number of trades
- ✅ P&L

### 📈 Missing Critical Metrics
- [ ] Max drawdown
- [ ] Calmar ratio
- [ ] Win rate
- [ ] Avg win / avg loss
- [ ] Time in market
- [ ] Turnover
- [ ] Exposure by sector
- [ ] Sharpe ratio
- [ ] Sortino ratio

**Implementation:**
- [ ] Create comprehensive metrics tracker
- [ ] Add to daily email summary
- [ ] Store in database
- [ ] Create metrics dashboard

**Files to create:**
- `src/performance_metrics.py`

---

## Implementation Progress

### Phase 1: Critical Fixes ✅ COMPLETE
- [x] Fix execution timing (4:15 PM ET)
- [x] Improve RSI exits (conditional exits)
- [x] Add slippage/costs infrastructure
- [x] Add basic metrics infrastructure

**Completed:** December 23, 2025

---

### Phase 2: High-ROI Improvements ✅ COMPLETE
- [x] Volatility-adjusted sizing (ATR-based)
- [x] Portfolio risk controls (heat, daily loss)
- [x] Correlation filter (60-day rolling)
- [x] All strategies integrated

**Completed:** December 23, 2025

---

### Phase 3: Strategy Improvements ✅ COMPLETE
- [x] RSI: Slope filter, VWAP exits
- [x] MA Crossover: 20/100 MAs, ADX filter
- [x] ML Momentum: Logistic classifier
- [x] News Sentiment: Filter not trigger
- [x] Volatility Breakout: False breakout protection

**Completed:** December 23, 2025

---

### Phase 4: Architecture (Future)
- [ ] Strategy weighting
- [ ] Regime detection
- [ ] Event-driven engine

**Target:** TBD

---

## Testing & Validation

### Before Each Change
- [ ] Unit tests for new functions
- [ ] Integration tests
- [ ] Backtest comparison (before/after)
- [ ] Paper trading validation

### After All Changes
- [ ] Full system backtest
- [ ] Walk-forward validation
- [ ] Out-of-sample testing
- [ ] Live paper trading for 2 weeks

---

## Success Metrics

### System Quality Indicators
- **Sharpe Ratio:** Target > 1.5 (currently unknown)
- **Max Drawdown:** Target < 15%
- **Win Rate:** Target > 55%
- **Calmar Ratio:** Target > 2.0

### Code Quality
- All functions documented
- >80% test coverage
- No critical bugs
- Clean architecture

---

## Notes & Decisions

### Decision Log

**2025-12-23:** Chose to run after market close (4:15 PM ET) instead of 10 AM to avoid lookahead bias

**2025-12-23:** Will implement volatility-based sizing before Kelly Criterion (simpler, more robust)

**2025-12-23:** Prioritizing portfolio-level risk controls over individual strategy improvements

---

## Questions for Future Review

1. Should we disable underperforming strategies automatically?
2. What's the optimal rebalancing frequency?
3. Should we add options data for volatility signals?
4. How to handle earnings announcements systematically?
5. Should we move to intraday execution eventually?

---

## Resources & References

- Original system: `ALGORITHM_SPECIFICATION.md`
- ChatGPT review: Saved in project notes
- Industry standards: Quantopian lectures, QuantConnect docs

---

**Last Updated:** December 23, 2025  
**Next Review:** After Phase 1 completion
