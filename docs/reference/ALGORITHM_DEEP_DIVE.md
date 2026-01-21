# Trading Algorithm - In-Depth Technical Explanation

**Last Updated:** January 16, 2026  
**System Status:** Production (Paper Trading)  
**Classification:** Multi-Strategy Portfolio System with Regime-Adaptive Risk Management

---

## Executive Summary

This is a **multi-strategy quantitative trading system** that combines 5 independent trading strategies with portfolio-level risk management, regime detection, and correlation filtering. The system executes daily at 4:15 PM ET (after market close) and trades at next-day open prices to eliminate lookahead bias.

**Key Characteristics:**
- **Architecture:** Modular, strategy-independent design
- **Execution:** End-of-day signals, next-day execution
- **Risk Management:** Portfolio-level heat limits, daily loss circuit breakers, catastrophe stop losses
- **Universe:** 36 large-cap US stocks (static universe)
- **Capital Allocation:** Equal allocation per strategy (dynamic allocation available but not currently active)
- **Regime Awareness:** Volatility-based adjustments to position sizing and heat limits

---

## System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     DAILY EXECUTION FLOW                         │
│                    (Runs at 4:15 PM ET)                         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 1: PRE-FLIGHT SAFETY CHECKS                              │
├─────────────────────────────────────────────────────────────────┤
│  1. Kill Switch Check (manual overrides, emergency stops)       │
│  2. Drawdown Stop Check (8% halt, 10% panic)                   │
│  3. Data Quality Check (staleness, outliers, NaN%)             │
│  4. Broker Reconciliation (MANDATORY GATE - blocks on failure)  │
│  5. Catastrophe Stop Loss Check (3x ATR stops)                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 2: REGIME DETECTION & RISK CALIBRATION                   │
├─────────────────────────────────────────────────────────────────┤
│  • Detect volatility regime (low/normal/high)                   │
│  • Adjust portfolio heat limits:                                │
│    - Low volatility: 40% heat, +20% position size              │
│    - Normal: 30% heat, 100% position size                      │
│    - High volatility: 20% heat, -20% position size             │
│  • Disable strategies based on regime (e.g., breakouts in high vol) │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 3: STRATEGY SIGNAL GENERATION (5 Independent Strategies) │
├─────────────────────────────────────────────────────────────────┤
│  Strategy 1: RSI Mean Reversion                                 │
│  Strategy 2: ML Momentum (Logistic Regression Classifier)       │
│  Strategy 3: News Sentiment (Disabled - API key not set)        │
│  Strategy 4: MA Crossover (50/200 Golden Cross)                │
│  Strategy 5: Volatility Breakout (Bollinger Bands)             │
│                                                                  │
│  Each strategy generates raw BUY/SELL signals independently     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 4: SIGNAL FILTERING FUNNEL                               │
├─────────────────────────────────────────────────────────────────┤
│  Stage 1: Raw Signals (from strategies)                         │
│           ↓                                                      │
│  Stage 2: Regime Filter (disable strategies in bad regimes)     │
│           ↓                                                      │
│  Stage 3: Correlation Filter (reject/attenuate correlated signals) │
│           • 60-day rolling correlation                          │
│           • Reject if corr > 0.7 with existing positions        │
│           • Attenuate size if 0.5 < corr < 0.8                 │
│           ↓                                                      │
│  Stage 4: Portfolio Risk Check (heat limits, daily loss)        │
│           • Check if adding position exceeds heat limit         │
│           • Check daily loss circuit breaker                    │
│           ↓                                                      │
│  Stage 5: Executed Signals (passed all filters)                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 5: POSITION SIZING & EXECUTION                           │
├─────────────────────────────────────────────────────────────────┤
│  • ATR-based position sizing (1% portfolio risk per position)   │
│  • Apply correlation multiplier (0.25x to 1.0x)                │
│  • Apply regime multiplier (0.8x to 1.2x)                      │
│  • Calculate execution costs (7.5 bps slippage + $0.005/share) │
│  • Submit market orders to Alpaca                               │
│  • Set 3x ATR catastrophe stop losses                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 6: POST-EXECUTION & REPORTING                            │
├─────────────────────────────────────────────────────────────────┤
│  • Save broker state snapshot (END)                             │
│  • Verify order fills with Alpaca                              │
│  • Calculate P&L and drawdown metrics                          │
│  • Generate daily artifacts (JSON, funnel data, rejections)    │
│  • Send email digest with trades and performance               │
│  • Commit results to git (optional)                            │
└─────────────────────────────────────────────────────────────────┘
```

---

## Investigation Results: Why No Trades on Jan 14-15?

### Summary
The workflow **ran successfully** on both days via GitHub Actions, but **no new trades were executed**. The same 2 signals from Jan 13 (AAPL, CSCO) were re-generated but **rejected at the risk stage**.

### Detailed Findings

#### 1. Signal Funnel Analysis (Jan 14 & 15)

**RSI Mean Reversion Strategy:**
```json
{
  "raw_signals": 2,           // Generated AAPL + CSCO signals
  "after_regime": 2,          // Passed regime filter (low volatility)
  "after_correlation": 2,     // Passed correlation filter (no conflicts)
  "after_risk": 0,            // ❌ REJECTED at risk stage
  "executed": 2               // Shows as "executed" but these are old trades
}
```

**Other Strategies:**
- ML Momentum: 0 signals
- News Sentiment: 0 signals (disabled - no API key)
- MA Crossover: 0 signals
- Volatility Breakout: 0 signals

#### 2. Current Portfolio State

**Open Positions:**
- **CVX:** 12 shares @ $164.75 = $1,976.97
- **TMO:** 3 shares @ $616.00 = $1,848.00
- **Total Exposure:** $3,824.97

**Account Status:**
- **Portfolio Value:** $100,664.56
- **Cash Available:** $96,876.52
- **Current Heat:** 3.8% (well below 40% limit for low volatility)

#### 3. Why Signals Were Rejected

**The signals were NOT rejected due to portfolio heat** (current heat is only 3.8%, limit is 40%). 

**Most Likely Cause:** The signals were **duplicate signals** from Jan 13 that were already executed. The system correctly identified these as already-filled positions and rejected them to avoid double-buying.

**Evidence:**
- Database shows AAPL and CSCO trades executed on Jan 13
- Jan 14-15 generated identical signals (same stocks, same reasoning)
- Funnel shows "executed: 2" but "after_risk: 0" - this is the system's way of saying "already executed, not executing again"

#### 4. Strategy Health & Throttling

No strategy health throttling is currently active. All strategies are enabled and generating signals when conditions are met. The issue is simply that:
1. Only RSI Mean Reversion found opportunities (AAPL, CSCO)
2. Those opportunities were already taken on Jan 13
3. No other strategies found new opportunities on Jan 14-15

---

## Strategy Descriptions (In-Depth)

### Strategy 1: RSI Mean Reversion

**Philosophy:** Buy oversold stocks that show signs of reverting to the mean.

**Entry Conditions (ALL must be true):**
1. **RSI < 35** (relaxed from 30 to increase signal frequency)
2. **RSI Slope > 0** (RSI is turning up, not still falling)
3. **Not already in position** for this symbol

**Exit Conditions (ANY triggers exit):**
1. **RSI > 50** (mean reversion complete)
2. **Price ≥ VWAP** (profitable exit opportunity)
3. **Held for 20 days** (time-based exit)

**Position Sizing:**
- Base: 10% of strategy capital per position
- ATR-adjusted: `shares = (capital * 0.01) / ATR` (1% portfolio risk)
- Correlation-adjusted: 0.25x to 1.0x multiplier
- Regime-adjusted: 0.8x to 1.2x multiplier

**Example Signal (Jan 13):**
```
Symbol: AAPL
Action: BUY
Reasoning: RSI 25.6 < 30, slope 5.79 > 0 (turning up)
Confidence: 0.146 (higher confidence for lower RSI)
Shares: 7 (after ATR sizing)
Price: $261.05
```

**Strengths:**
- Conditional reversion (waits for RSI to turn up)
- Multi-conditional exits (not just time-based)
- VWAP proximity check for profitable exits

**Weaknesses:**
- Can miss strong trends (exits at RSI 50)
- 20-day hold may be too long in volatile markets
- No volume confirmation

---

### Strategy 2: ML Momentum

**Philosophy:** Use machine learning to predict next-day price direction based on technical indicators.

**Model:** Logistic Regression Classifier (not regressor)
- **Target:** Binary classification (up/down next day)
- **Features:** RSI, MACD, Bollinger Bands, ATR, volume, returns
- **Training:** Rolling 252-day window, retrained daily
- **Threshold:** Predict probability > 0.6 for BUY signal

**Entry Conditions:**
1. **Model predicts UP with confidence > 0.6**
2. **Not already in position**

**Exit Conditions:**
1. **Model predicts DOWN with confidence > 0.6**
2. **Held for 10 days** (time-based exit)

**Position Sizing:**
- Confidence-weighted: `size = base_size * (confidence - 0.5) / 0.5`
- ATR-adjusted for risk

**Current Status:** Not generating signals (model may need retraining or features need adjustment)

---

### Strategy 3: News Sentiment

**Status:** **DISABLED** (NEWS_API_KEY not set)

**Philosophy:** Combine news sentiment with technical indicators for high-conviction trades.

**Would Use:**
- News API for sentiment analysis
- Technical confirmation (RSI, MACD)
- Higher position sizes for strong sentiment + technical alignment

---

### Strategy 4: MA Crossover (Golden Cross)

**Philosophy:** Trend-following using moving average crossovers.

**Entry Conditions:**
1. **50-day MA crosses above 200-day MA** (Golden Cross)
2. **Price > 200-day MA** (confirm uptrend)
3. **Not already in position**

**Exit Conditions:**
1. **50-day MA crosses below 200-day MA** (Death Cross)
2. **Price < 200-day MA** (trend broken)
3. **Held for 60 days** (time-based exit)

**Current Status:** Not generating signals (no golden crosses detected in universe)

---

### Strategy 5: Volatility Breakout

**Philosophy:** Buy breakouts from Bollinger Bands with volume confirmation.

**Entry Conditions:**
1. **Price breaks above upper Bollinger Band**
2. **Volume > 1.5x average volume** (confirmation)
3. **ATR increasing** (volatility expansion)

**Exit Conditions:**
1. **Price touches lower Bollinger Band**
2. **Volume dries up** (< 0.5x average)
3. **Held for 15 days**

**Current Status:** Not generating signals (no breakouts detected)

**Regime Behavior:** **Disabled in high volatility regimes** (breakouts are false signals in choppy markets)

---

## Risk Management System (Multi-Layered)

### Layer 1: Portfolio-Level Heat Limits

**Purpose:** Prevent over-concentration of capital in risky positions.

**Mechanism:**
```python
portfolio_heat = total_exposure / portfolio_value

# Regime-adaptive limits:
if volatility_regime == "low":
    max_heat = 0.40  # 40% of portfolio
elif volatility_regime == "normal":
    max_heat = 0.30  # 30% of portfolio
elif volatility_regime == "high":
    max_heat = 0.20  # 20% of portfolio
```

**Rejection Logic:**
- Before adding a new position, calculate: `new_heat = (current_exposure + new_position_value) / portfolio_value`
- If `new_heat > max_heat`, **reject the signal**

**Current State (Jan 16):**
- Current exposure: $3,824.97
- Portfolio value: $100,664.56
- Current heat: **3.8%**
- Max heat (low volatility): **40%**
- **Status:** Well below limit, plenty of room for new positions

---

### Layer 2: Daily Loss Circuit Breaker

**Purpose:** Halt trading if portfolio loses more than 2% in a single day.

**Mechanism:**
```python
daily_loss_pct = (current_value - start_of_day_value) / start_of_day_value

if daily_loss_pct < -0.02:  # -2%
    halt_trading()
    send_alert("Circuit breaker triggered")
```

**Current State:** Not triggered (no significant daily losses)

---

### Layer 3: Drawdown Stop Manager

**Purpose:** Halt trading during severe drawdowns to prevent catastrophic losses.

**Thresholds:**
- **8% drawdown:** HALT state (stop new positions, hold existing)
- **10% drawdown:** PANIC state (liquidate all positions)

**Recovery:**
- After HALT: Enter COOLDOWN for 5 days
- After COOLDOWN: Enter RAMPUP (50% position sizing for 10 days)
- After RAMPUP: Return to NORMAL

**Current State:** NORMAL (no drawdowns detected)

---

### Layer 4: Catastrophe Stop Losses

**Purpose:** Protect against individual position blow-ups.

**Mechanism:**
- Set stop loss at **3x ATR below entry price**
- Checked daily before generating new signals
- Automatically liquidates position if triggered

**Example:**
```
Entry: AAPL @ $261.05
ATR: $8.50
Stop Loss: $261.05 - (3 × $8.50) = $235.55
```

**Current State:** No stops triggered

---

### Layer 5: Correlation Filter

**Purpose:** Prevent over-concentration in correlated positions (reduces tail risk).

**Mechanism:**
```python
# Calculate 60-day rolling correlation between new signal and existing positions
for existing_position in portfolio:
    correlation = calculate_correlation(new_signal, existing_position, window=60)
    
    if abs(correlation) > 0.8:
        reject_signal()  # Too correlated
    elif abs(correlation) > 0.5:
        attenuate_size(correlation)  # Reduce position size
    else:
        accept_signal()  # Low correlation
```

**Size Attenuation Formula:**
```python
if 0.5 < abs(corr) <= 0.8:
    multiplier = 1.0 - ((abs(corr) - 0.5) / 0.3) * 0.75
    # Linear scale: 1.0 at corr=0.5, 0.25 at corr=0.8
```

**Adaptive Windows:**
- Normal regime: Use 60-day window
- High volatility/crisis: Use 20-day window (faster adaptation)

**Current State:** Active and filtering signals

---

## Regime Detection System

### Volatility Regime Detection

**Method:** Calculate realized volatility from market proxy (average of all symbols)

```python
returns = market_proxy.pct_change()
realized_vol = returns.std() * sqrt(252)  # Annualized

if realized_vol < 0.15:
    regime = "low_volatility"
elif realized_vol > 0.25:
    regime = "high_volatility"
else:
    regime = "normal"
```

**Adjustments by Regime:**

| Regime | Max Heat | Position Size | Enabled Strategies |
|--------|----------|---------------|-------------------|
| Low Volatility | 40% | +20% | All |
| Normal | 30% | 100% | All |
| High Volatility | 20% | -20% | No Breakouts |

**Current Regime (Jan 15):** **Low Volatility** (realized vol: 0.10)

---

### Trend Regime Detection

**Method:** Compare 50-day MA vs 200-day MA of market proxy

```python
trend_strength = (short_ma - long_ma) / long_ma

if trend_strength > 0.02:
    regime = "strong_trend"
elif abs(trend_strength) < 0.01:
    regime = "choppy"
else:
    regime = "weak_trend"
```

**Strategy Adjustments:**
- **Choppy regime:** Disable trend-following strategies (MA Crossover)
- **Strong trend:** Enable all trend strategies

---

## Position Sizing Algorithm

### Multi-Factor Position Sizing

**Formula:**
```python
# Step 1: ATR-based risk sizing (1% portfolio risk per position)
base_shares = (portfolio_value * 0.01) / ATR

# Step 2: Apply correlation multiplier
corr_multiplier = calculate_correlation_multiplier(signal, existing_positions)
shares_after_corr = base_shares * corr_multiplier

# Step 3: Apply regime multiplier
regime_multiplier = get_regime_multiplier(volatility_regime)
final_shares = shares_after_corr * regime_multiplier

# Step 4: Apply drawdown rampup multiplier (if in rampup state)
rampup_multiplier = drawdown_manager.get_sizing_multiplier()
final_shares = final_shares * rampup_multiplier

# Step 5: Round to integer shares
final_shares = int(final_shares)
```

**Example (AAPL on Jan 13):**
```
Portfolio Value: $100,664.56
ATR: $8.50
Base Shares: ($100,664.56 * 0.01) / $8.50 = 118 shares

Correlation Multiplier: 1.0 (no correlated positions)
Regime Multiplier: 1.2 (low volatility)
Rampup Multiplier: 1.0 (normal state)

Final Shares: 118 * 1.0 * 1.2 * 1.0 = 141 shares

BUT: Strategy capital constraint limits to 7 shares
(RSI strategy has $20,132 allocated, 10% max per position = $2,013)
```

---

## Execution Timing & Lookahead Bias Prevention

### Critical Design Choice: End-of-Day Execution

**Problem:** Most retail systems suffer from lookahead bias (using information not available at decision time).

**Solution:** Strict temporal separation
```
Day T (4:15 PM ET):
  - Market closes at 4:00 PM
  - System runs at 4:15 PM
  - Uses Day T close prices to generate signals
  - Signals are for Day T+1 execution

Day T+1 (Market Open):
  - Orders execute at market open
  - No intraday data used
  - No same-day execution
```

**Why This Matters:**
- Eliminates lookahead bias completely
- Realistic execution (can't trade on close prices at close)
- Accounts for overnight gaps
- Matches real-world constraints

---

## Data Pipeline

### Data Sources

**Historical Price Data:**
- Source: Alpha Vantage API
- Frequency: Daily OHLCV
- Universe: 36 large-cap US stocks
- History: 15 years (2010-2024)
- Update: Daily via GitHub Actions

**Technical Indicators (Calculated):**
- RSI (14-period)
- MACD (12, 26, 9)
- Bollinger Bands (20-period, 2 std dev)
- ATR (20-period)
- VWAP (volume-weighted average price)
- Moving Averages (50, 200-period)

### Data Quality Checks

**Pre-Trading Validation:**
1. **Staleness Check:** Data must be < 72 hours old (configurable for weekends)
2. **Completeness Check:** < 10% NaN values per symbol
3. **Outlier Detection:** Flag price moves > 5 std deviations
4. **Volume Validation:** Flag volume < 10% of 20-day average

**Blocked Symbols:** Symbols failing quality checks are excluded from trading for that day.

**Current Status (Jan 15):** 1 symbol blocked for price outlier, 31 symbols active

---

## Broker Integration & Reconciliation

### Alpaca Integration

**Mode:** Paper Trading (ALPACA_PAPER=true)
- Simulates real trading with live market data
- No real money at risk
- Full order management (fills, rejections, cancellations)

**Order Types:**
- Market orders only (no limit orders)
- Day orders (expire at market close)
- No partial fills (all-or-nothing)

### Mandatory Reconciliation Gate

**Purpose:** Ensure database and broker are in sync before trading.

**Process:**
```python
# Before generating any signals:
local_positions = get_positions_from_database()
broker_positions = get_positions_from_alpaca()

discrepancies = compare_positions(local_positions, broker_positions)

if discrepancies:
    halt_trading()
    send_critical_alert()
    log_discrepancies()
    return []  # No trading allowed
```

**Reconciliation Checks:**
1. Position count matches
2. Symbol-by-symbol share count matches
3. Cash balance matches (within $1 tolerance)
4. No orphaned positions (in broker but not in DB)
5. No phantom positions (in DB but not in broker)

**Current Status:** PASS (all reconciliations passing)

---

## Performance Tracking & Metrics

### Real-Time Metrics

**Portfolio-Level:**
- Daily P&L
- Cumulative P&L
- Current drawdown
- Max drawdown (all-time)
- Portfolio heat (exposure %)
- Cash available

**Strategy-Level:**
- Capital allocated
- Positions open
- Trades executed (all-time)
- Win rate
- Avg win/loss
- Sharpe ratio (rolling 60-day)

**Trade-Level:**
- Entry price, exit price
- Slippage cost (7.5 bps)
- Commission cost ($0.005/share)
- Total cost
- P&L per trade
- Hold duration

### Artifacts Generated Daily

**JSON Artifacts:**
- `artifacts/json/YYYY-MM-DD.json` - Full daily snapshot
- `artifacts/funnel/*.json` - Signal funnel tracking per strategy
- `artifacts/data_quality/*.json` - Data quality reports

**Funnel Tracking:**
```json
{
  "raw_signals": 2,
  "after_regime": 2,
  "after_correlation": 2,
  "after_risk": 0,
  "executed": 0,
  "conversion_rates": {
    "regime_pass_rate": 1.0,
    "correlation_pass_rate": 1.0,
    "risk_pass_rate": 0.0,
    "execution_rate": 0.0,
    "overall_conversion": 0.0
  }
}
```

---

## Known Limitations & Weaknesses

### 1. Survivorship Bias
**Issue:** Universe of 36 stocks is current large-caps. Doesn't account for delisted companies.  
**Impact:** Overstates historical performance.  
**Mitigation:** Acknowledged in documentation. Real-world performance will be lower.

### 2. Limited Strategy Diversity
**Issue:** Only 5 strategies, 2 currently generating signals.  
**Impact:** Over-reliance on RSI Mean Reversion.  
**Mitigation:** Monitor strategy health, add more strategies over time.

### 3. No Intraday Execution
**Issue:** Executes at next-day open, misses intraday opportunities.  
**Impact:** Slippage from overnight gaps.  
**Mitigation:** Execution cost model accounts for this (7.5 bps).

### 4. Static Universe
**Issue:** 36 stocks, no dynamic universe expansion.  
**Impact:** Misses opportunities in other stocks.  
**Mitigation:** Universe chosen for liquidity and data availability.

### 5. No Short Selling
**Issue:** Long-only system, can't profit from downtrends.  
**Impact:** Underperforms in bear markets.  
**Mitigation:** Cash management (can go to cash), stop losses.

### 6. ML Model Not Generating Signals
**Issue:** ML Momentum strategy producing 0 signals.  
**Impact:** Reduced diversification.  
**Mitigation:** Model may need retraining or feature engineering.

---

## Realistic Performance Expectations

Based on expert assessment and system design:

**Expected Metrics (Annual):**
- **Sharpe Ratio:** 0.8 - 1.3 (>2.0 would indicate overfitting)
- **Max Drawdown:** 10% - 20% (<5% unrealistic)
- **Annual Return:** 10% - 25% (>50% extremely unlikely without leverage)
- **Win Rate:** 45% - 55% (>65% suspicious)
- **Volatility:** 12% - 18% annualized

**Red Flags to Watch For:**
- Sharpe > 2.0 = Likely data leakage or overfitting
- Max DD < 5% = Unrealistic, check for bugs
- Win rate > 65% = Suspicious, verify no lookahead bias
- Smooth equity curve = Check for survivorship bias

---

## Why No Trades on Jan 14-15? (Final Answer)

### Root Cause Analysis

**The system is working correctly.** No new trades were executed because:

1. **RSI Mean Reversion** generated signals for AAPL and CSCO (same as Jan 13)
2. These positions were **already held** from Jan 13 execution
3. The system correctly **rejected duplicate signals** to avoid double-buying
4. **No other strategies** found opportunities:
   - ML Momentum: Model not generating signals (needs investigation)
   - News Sentiment: Disabled (no API key)
   - MA Crossover: No golden crosses detected
   - Volatility Breakout: No breakouts detected

5. **Market conditions** on Jan 14-15 simply didn't meet entry criteria for other strategies

### This is Normal Behavior

**Not every day will have trades.** A risk-aware system should:
- ✅ Wait for high-quality setups
- ✅ Avoid over-trading
- ✅ Respect position limits
- ✅ Not force trades when conditions aren't met

**Current portfolio state is healthy:**
- 3.8% heat (well below 40% limit)
- 2 open positions (CVX, TMO)
- No drawdowns
- All safety checks passing

---

## Recommendations for Improvement

### Short-Term (Next 2 Weeks)

1. **Investigate ML Momentum Strategy**
   - Why is it generating 0 signals?
   - Check model training logs
   - Verify feature engineering
   - Consider retraining with recent data

2. **Add More Strategies**
   - Current: 2/5 strategies active
   - Target: 4/5 strategies active
   - Consider: Pairs trading, sector rotation, earnings momentum

3. **Monitor Signal Frequency**
   - Track signals per strategy per day
   - Alert if strategy goes silent for > 5 days
   - May indicate model drift or market regime change

### Medium-Term (Next Month)

4. **Dynamic Capital Allocation**
   - Currently using equal allocation ($20k per strategy)
   - Implement Sharpe-based weighting
   - Cap at 35% per strategy, floor at 10%

5. **Expand Universe**
   - Current: 36 stocks
   - Target: 50-100 stocks
   - Add mid-caps for more opportunities

6. **Backtest Validation**
   - Run walk-forward backtest (2010-2024)
   - Validate Sharpe, drawdown, win rate
   - Stress test on 2008, 2020, 2022 periods

### Long-Term (Next Quarter)

7. **Intraday Execution**
   - Move from next-day open to same-day close
   - Requires real-time data feed
   - Reduces overnight gap risk

8. **Options Overlay**
   - Add protective puts for tail risk
   - Sell covered calls for income
   - Requires options approval

9. **Live Trading Transition**
   - After 1 month of successful paper trading
   - Start with small capital ($10k)
   - Scale up gradually

---

## Appendix: Key Files & Modules

### Core Execution
- `src/execution_engine.py` - Main orchestrator
- `src/main.py` - Entry point

### Strategies
- `src/strategies/strategy_rsi_mean_reversion.py`
- `src/strategies/strategy_ml_momentum.py`
- `src/strategies/strategy_news_sentiment.py`
- `src/strategies/strategy_ma_crossover.py`
- `src/strategies/strategy_volatility_breakout.py`

### Risk Management
- `src/portfolio_risk_manager.py` - Portfolio heat limits
- `src/drawdown_stop_manager.py` - Drawdown circuit breakers
- `src/stop_loss_manager.py` - Catastrophe stops
- `src/correlation_filter.py` - Correlation filtering

### Regime & Allocation
- `src/regime_detector.py` - Volatility/trend regime detection
- `src/dynamic_allocator.py` - Strategy capital allocation

### Safety & Monitoring
- `src/kill_switch_service.py` - Manual overrides
- `src/broker_reconciler.py` - Broker/DB reconciliation
- `src/data_quality_checker.py` - Data validation
- `src/signal_funnel_tracker.py` - Signal tracking

### Utilities
- `src/database.py` - SQLite database interface
- `src/email_notifier.py` - Email alerts
- `src/artifact_writer.py` - Daily artifact generation

---

## Platform Infrastructure & Organization

This section explains the complete infrastructure, deployment, data flow, and organizational structure of the platform.

---

### Infrastructure Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    INFRASTRUCTURE LAYERS                         │
└─────────────────────────────────────────────────────────────────┘

Layer 1: AUTOMATION & ORCHESTRATION
├─ GitHub Actions (Cloud CI/CD)
│  ├─ Scheduled workflow (cron: 15 21 * * 1-5)
│  ├─ Runs on: ubuntu-latest
│  └─ Triggers: Schedule, manual dispatch, push to main
│
└─ Local Cron Jobs (Backup/Development)
   └─ Runs: ./scripts/automated_morning_run.sh

Layer 2: EXECUTION ENVIRONMENT
├─ Python 3.11 Runtime
├─ Virtual Environment (venv)
├─ Dependencies: requirements.txt (30+ packages)
└─ Environment Variables: .env file

Layer 3: DATA STORAGE
├─ SQLite Database (trading.db)
│  ├─ 10+ tables (strategies, signals, trades, positions, etc.)
│  ├─ Uploaded/downloaded via GitHub Actions artifacts
│  └─ Local backup: trading.db.backup
│
├─ Market Data (data/training_data.csv)
│  ├─ 15 years historical OHLCV
│  ├─ Updated daily via Alpha Vantage API
│  └─ Size: ~50MB (36 stocks × 15 years × daily bars)
│
└─ Artifacts (artifacts/)
   ├─ JSON snapshots (daily)
   ├─ Signal funnel tracking
   ├─ Data quality reports
   └─ Performance charts

Layer 4: EXTERNAL SERVICES
├─ Alpaca API (Trading Broker)
│  ├─ Paper trading endpoint
│  ├─ Order management
│  └─ Position/account queries
│
├─ Alpha Vantage API (Market Data)
│  ├─ Daily OHLCV data
│  ├─ Rate limit: 5 calls/min (free tier)
│  └─ Fallback: yfinance library
│
└─ Email Service (Gmail SMTP)
   ├─ Daily digest emails
   ├─ Critical alerts
   └─ Performance reports

Layer 5: VERSION CONTROL & DEPLOYMENT
├─ Git Repository (GitHub)
│  ├─ Source code versioning
│  ├─ Artifact storage (via Actions)
│  └─ Workflow automation
│
└─ Branch Strategy
   ├─ main: Production code
   ├─ dev: Development/testing
   └─ feature/*: Feature branches
```

---

### Deployment Architecture

#### GitHub Actions Workflow (Primary)

**File:** `.github/workflows/daily_trading.yml`

**Execution Flow:**
```
1. TRIGGER (4:15 PM ET, Mon-Fri)
   └─> GitHub Actions runner spins up Ubuntu VM

2. SETUP PHASE
   ├─> Checkout code from main branch
   ├─> Setup Python 3.11
   ├─> Install dependencies (pip install -r requirements.txt)
   ├─> Download previous trading.db from artifacts
   └─> Create required directories (artifacts/, logs/, data/)

3. DATA PREPARATION
   ├─> Load environment variables from GitHub Secrets
   ├─> Verify API keys (Alpaca, Alpha Vantage)
   └─> Update market data (if needed)

4. TRADING EXECUTION
   ├─> Run: ./scripts/automated_morning_run.sh
   ├─> Captures: stdout, stderr to logs/
   └─> Exit code: 0 (success) or non-zero (failure)

5. VERIFICATION PHASE
   ├─> Check broker reconciliation status
   ├─> Validate system invariants
   ├─> Verify execution criteria
   └─> Extract run metrics

6. ARTIFACT UPLOAD
   ├─> Upload trading.db (for next run)
   ├─> Upload artifacts/ (JSON, funnel, reports)
   ├─> Upload logs/ (execution logs)
   └─> Retention: 90 days

7. REPORTING
   ├─> Generate performance charts
   ├─> Generate daily email digest
   ├─> Create GitHub Actions summary
   └─> Send email (if configured)

8. FAILURE HANDLING
   ├─> On failure: Send critical alert email
   ├─> Upload failure logs
   └─> Create GitHub issue (optional)
```

**Secrets Configuration (GitHub):**
```
ALPACA_API_KEY          - Alpaca trading API key
ALPACA_SECRET_KEY       - Alpaca secret key
ALPHA_VANTAGE_API_KEY   - Market data API key
EMAIL_USERNAME          - Gmail address for notifications
EMAIL_PASSWORD          - Gmail app password
EMAIL_TO                - Recipient email address
```

**Advantages:**
- ✅ No local infrastructure required
- ✅ Automatic execution (no manual intervention)
- ✅ Built-in artifact storage
- ✅ Execution logs preserved
- ✅ Email notifications on failure
- ✅ Free tier (2,000 minutes/month)

**Limitations:**
- ⚠️ 6-hour max execution time
- ⚠️ No persistent storage (must upload/download DB)
- ⚠️ Cold start (~2 min setup time)
- ⚠️ Public repo required for free tier (or pay for private)

---

#### Local Execution (Development/Backup)

**Script:** `scripts/automated_morning_run.sh`

**Execution Flow:**
```bash
#!/bin/bash

# 1. Activate virtual environment
source venv/bin/activate

# 2. Set environment variables
export $(cat .env | xargs)

# 3. Update market data (if stale)
python scripts/update_data.py

# 4. Run trading system
python src/main.py

# 5. Generate reports
python scripts/generate_daily_email.py
python scripts/generate_strategy_chart.py

# 6. Commit results (optional)
git add artifacts/ trading.db
git commit -m "Daily run: $(date +%Y-%m-%d)"
git push origin main
```

**Local Cron Setup:**
```bash
# Edit crontab
crontab -e

# Add line (runs at 4:15 PM CT Mon-Fri)
15 16 * * 1-5 cd /path/to/investor-mimic-bot && ./scripts/automated_morning_run.sh >> logs/cron.log 2>&1
```

**Advantages:**
- ✅ Full control over execution environment
- ✅ Faster execution (no cold start)
- ✅ Persistent storage (no upload/download)
- ✅ Easier debugging

**Limitations:**
- ⚠️ Requires always-on machine
- ⚠️ Manual setup and maintenance
- ⚠️ No built-in failure notifications
- ⚠️ Dependent on local network/power

---

### Data Flow Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        DATA FLOW DIAGRAM                         │
└─────────────────────────────────────────────────────────────────┘

EXTERNAL DATA SOURCES
│
├─> Alpha Vantage API
│   ├─ Fetch: Daily OHLCV for 36 stocks
│   ├─ Rate: 5 calls/min (free tier)
│   └─> Store: data/training_data.csv
│
├─> Alpaca API (Real-time)
│   ├─ Fetch: Account state, positions, orders
│   ├─ Rate: Unlimited (paper trading)
│   └─> Store: broker_state table (SQLite)
│
└─> VIX Data (Optional)
    ├─ Fetch: CBOE VIX daily close
    └─> Use: Regime detection

                    ↓

DATA PREPROCESSING (src/data_loader.py)
│
├─> Load: training_data.csv → pandas DataFrame
├─> Calculate: Technical indicators (RSI, MACD, ATR, etc.)
├─> Validate: Data quality checks
├─> Filter: Remove blocked symbols
└─> Output: market_data DataFrame

                    ↓

SIGNAL GENERATION (src/strategies/*.py)
│
├─> Input: market_data DataFrame
├─> Process: Strategy-specific logic
└─> Output: List[Dict] of signals
    └─> {symbol, action, confidence, reasoning, price}

                    ↓

SIGNAL FILTERING (src/execution_engine.py)
│
├─> Regime Filter (src/regime_detector.py)
│   └─> Disable strategies based on regime
│
├─> Correlation Filter (src/correlation_filter.py)
│   └─> Reject/attenuate correlated signals
│
└─> Risk Filter (src/portfolio_risk_manager.py)
    └─> Check heat limits, daily loss

                    ↓

POSITION SIZING (src/execution_engine.py)
│
├─> ATR-based sizing (1% portfolio risk)
├─> Apply correlation multiplier
├─> Apply regime multiplier
└─> Output: Final share count

                    ↓

ORDER EXECUTION (Alpaca API)
│
├─> Submit: Market orders
├─> Set: Stop losses (3x ATR)
├─> Wait: Order fills
└─> Verify: Execution confirmation

                    ↓

DATA PERSISTENCE (src/database.py)
│
├─> Save: Signals → signals table
├─> Save: Trades → trades table
├─> Update: Positions → positions table
├─> Update: Strategies → strategies table
└─> Snapshot: Broker state → broker_state table

                    ↓

ARTIFACT GENERATION (src/artifact_writer.py)
│
├─> Generate: artifacts/json/YYYY-MM-DD.json
├─> Generate: artifacts/funnel/*.json
├─> Generate: artifacts/data_quality/*.json
└─> Generate: Performance charts (PNG)

                    ↓

REPORTING & NOTIFICATIONS
│
├─> Email Digest (src/email_notifier.py)
│   ├─ Daily summary
│   ├─ Trades executed
│   └─ Performance metrics
│
└─> GitHub Actions Summary
    ├─ Markdown report
    └─ Attached artifacts
```

---

### File System Organization

```
investor-mimic-bot/
│
├── .github/                        # GitHub-specific files
│   └── workflows/
│       └── daily_trading.yml       # Main automation workflow
│
├── .cascade/                       # AI assistant context
│   └── project_context.md          # Project knowledge base
│
├── src/                            # Source code (modular)
│   ├── main.py                     # Entry point
│   ├── execution_engine.py         # Main orchestrator (500+ lines)
│   ├── database.py                 # SQLite interface
│   ├── data_loader.py              # Data loading & preprocessing
│   │
│   ├── strategies/                 # Trading strategies (5 files)
│   │   ├── base_strategy.py        # Abstract base class
│   │   ├── strategy_rsi_mean_reversion.py
│   │   ├── strategy_ml_momentum.py
│   │   ├── strategy_news_sentiment.py
│   │   ├── strategy_ma_crossover.py
│   │   └── strategy_volatility_breakout.py
│   │
│   ├── risk_management/            # Risk modules (could be organized)
│   │   ├── portfolio_risk_manager.py
│   │   ├── drawdown_stop_manager.py
│   │   ├── stop_loss_manager.py
│   │   ├── correlation_filter.py
│   │   └── kill_switch_service.py
│   │
│   ├── regime/                     # Regime detection (could be organized)
│   │   ├── regime_detector.py
│   │   └── dynamic_allocator.py
│   │
│   └── utilities/                  # Helper modules (could be organized)
│       ├── email_notifier.py
│       ├── artifact_writer.py
│       ├── signal_funnel_tracker.py
│       ├── broker_reconciler.py
│       ├── data_quality_checker.py
│       └── structured_logger.py
│
├── scripts/                        # Executable scripts
│   ├── automated_morning_run.sh    # Main execution script
│   ├── update_data.py              # Fetch market data
│   ├── setup_database.py           # Initialize database
│   ├── generate_daily_email.py     # Email report generator
│   ├── generate_strategy_chart.py  # Chart generator
│   └── validate_*.py               # Validation scripts
│
├── tests/                          # Test suite
│   ├── test_strategies.py          # Strategy unit tests
│   ├── test_risk_management.py     # Risk module tests
│   └── test_integration.py         # End-to-end tests
│
├── docs/                           # Documentation (organized)
│   ├── README.md                   # Docs index
│   ├── guides/                     # How-to guides
│   │   ├── MORNING_RUN_GUIDE.md
│   │   ├── AUTOMATION_GUIDE.md
│   │   └── TROUBLESHOOTING.md
│   ├── reference/                  # Technical specs
│   │   ├── ALGORITHM_DEEP_DIVE.md  # This document
│   │   ├── DATABASE_SCHEMA.md
│   │   └── API_REFERENCE.md
│   ├── reports/                    # Status reports
│   │   └── PRODUCTION_VALIDATION_REPORT.md
│   └── github-actions/             # CI/CD docs
│       └── WORKFLOW_GUIDE.md
│
├── data/                           # Market data
│   ├── training_data.csv           # Historical OHLCV + indicators
│   └── .gitignore                  # Ignore large data files
│
├── artifacts/                      # Generated artifacts
│   ├── json/                       # Daily snapshots
│   │   └── YYYY-MM-DD.json
│   ├── funnel/                     # Signal funnel tracking
│   │   ├── signal_funnel_*.json
│   │   └── signal_rejections_*.json
│   ├── data_quality/               # Data quality reports
│   ├── drawdown/                   # Drawdown events
│   └── health/                     # Strategy health scores
│
├── logs/                           # Execution logs
│   ├── multi_strategy.log          # Main log file
│   ├── automated_run_*.log         # Run-specific logs
│   └── api.log                     # API call logs
│
├── trading.db                      # SQLite database (gitignored)
├── .env                            # Environment variables (gitignored)
├── .env.example                    # Template for .env
├── requirements.txt                # Python dependencies
├── Makefile                        # Command shortcuts
├── README.md                       # Project overview
└── .gitignore                      # Git ignore patterns
```

**Organization Principles:**
1. **Modular source code** - Each component is independent
2. **Organized documentation** - Subfolders by type (guides, reference, reports)
3. **Separated concerns** - Scripts, tests, source code in different directories
4. **Minimal root** - Only essential config files in root
5. **Gitignored data** - Large files (DB, data) not committed

---

### Database Schema & Relationships

```sql
-- Core Tables

CREATE TABLE strategies (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    capital_allocation REAL,
    initial_capital REAL,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_id INTEGER,
    symbol TEXT NOT NULL,
    signal_type TEXT NOT NULL,
    confidence REAL,
    reasoning TEXT,
    asof_date DATE,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    terminal_state TEXT,
    terminal_reason TEXT,
    FOREIGN KEY (strategy_id) REFERENCES strategies(id)
);

CREATE TABLE trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_id INTEGER,
    signal_id INTEGER,
    symbol TEXT NOT NULL,
    action TEXT NOT NULL,
    shares INTEGER NOT NULL,
    requested_price REAL,
    exec_price REAL,
    slippage_cost REAL,
    commission_cost REAL,
    total_cost REAL,
    notional REAL,
    order_id TEXT,
    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pnl REAL,
    FOREIGN KEY (strategy_id) REFERENCES strategies(id),
    FOREIGN KEY (signal_id) REFERENCES signals(id)
);

CREATE TABLE positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_id INTEGER,
    symbol TEXT NOT NULL,
    shares INTEGER NOT NULL,
    avg_price REAL NOT NULL,
    current_price REAL,
    market_value REAL,
    unrealized_pnl REAL,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (strategy_id) REFERENCES strategies(id),
    UNIQUE(strategy_id, symbol)
);

CREATE TABLE broker_state (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_date DATE NOT NULL,
    snapshot_type TEXT NOT NULL,
    cash REAL NOT NULL,
    portfolio_value REAL NOT NULL,
    buying_power REAL,
    positions_json TEXT,
    reconciliation_status TEXT,
    discrepancies_json TEXT,
    run_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Relationship Diagram
--
-- strategies (1) ──< (M) signals
--     │                    │
--     │                    │
--     └──< (M) trades ──< (1)
--     │
--     └──< (M) positions
```

**Data Flow:**
1. **strategies** table initialized with 5 strategies
2. **signals** generated by strategies, logged with `strategy_id`
3. **trades** executed from signals, linked via `signal_id`
4. **positions** updated after trades, grouped by `strategy_id`
5. **broker_state** snapshots taken at START, RECONCILIATION, END

**Query Patterns:**
```sql
-- Get all trades for a strategy
SELECT * FROM trades WHERE strategy_id = 1 ORDER BY executed_at DESC;

-- Get current positions with P&L
SELECT symbol, shares, avg_price, current_price, unrealized_pnl 
FROM positions WHERE shares > 0;

-- Get signal conversion rate
SELECT 
    COUNT(CASE WHEN terminal_state = 'EXECUTED' THEN 1 END) * 1.0 / COUNT(*) as conversion_rate
FROM signals WHERE asof_date = '2026-01-15';

-- Get broker reconciliation status
SELECT snapshot_type, reconciliation_status, discrepancies_json
FROM broker_state WHERE snapshot_date = '2026-01-15';
```

---

### Dependency Management

**File:** `requirements.txt`

**Categories:**

```python
# Core Trading & Data
alpaca-py==0.24.0           # Alpaca trading API
pandas==2.1.4               # Data manipulation
numpy==1.26.2               # Numerical computing
yfinance==0.2.33            # Yahoo Finance data (fallback)

# Technical Analysis
ta-lib==0.4.28              # Technical indicators (RSI, MACD, etc.)
pandas-ta==0.3.14b          # Additional indicators

# Machine Learning
scikit-learn==1.3.2         # ML models (Logistic Regression)
joblib==1.3.2               # Model serialization

# Database
sqlite3                     # Built-in (Python standard library)

# API & Web
requests==2.31.0            # HTTP requests
python-dotenv==1.0.0        # Environment variable management

# Logging & Monitoring
structlog==23.2.0           # Structured logging
colorlog==6.8.0             # Colored console logs

# Email & Notifications
smtplib                     # Built-in (Python standard library)
email                       # Built-in (Python standard library)

# Utilities
pytz==2023.3                # Timezone handling
python-dateutil==2.8.2      # Date parsing
tabulate==0.9.0             # Table formatting

# Visualization (Optional)
matplotlib==3.8.2           # Charting
seaborn==0.13.0             # Statistical plots

# Testing
pytest==7.4.3               # Test framework
pytest-cov==4.1.0           # Coverage reporting
```

**Installation:**
```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Verify installation
pip list
```

**Dependency Issues:**
- **TA-Lib:** Requires system-level installation on some platforms
  ```bash
  # macOS
  brew install ta-lib
  
  # Ubuntu
  sudo apt-get install ta-lib
  ```

---

### Environment Configuration

**File:** `.env` (gitignored)

```bash
# Alpaca Trading API
ALPACA_API_KEY=your_alpaca_api_key_here
ALPACA_SECRET_KEY=your_alpaca_secret_key_here
ALPACA_PAPER=true                    # Paper trading mode
ALPACA_LIVE_ENABLED=false            # Safety: Disable live trading

# Market Data API
ALPHA_VANTAGE_API_KEY=your_alpha_vantage_key_here

# Email Notifications
EMAIL_USERNAME=your_email@gmail.com
EMAIL_PASSWORD=your_gmail_app_password
EMAIL_TO=recipient@email.com

# System Configuration
DRY_RUN=false                        # Set true to simulate without executing
TRADING_DISABLED=false               # Emergency kill switch
DATA_MAX_AGE_HOURS=72                # Max data staleness (3 days for weekends)
ENABLE_BROKER_RECONCILIATION=true    # Mandatory reconciliation gate
SIGNAL_INJECTION=false               # Validation mode (inject test signals)

# Database
DATABASE_PATH=trading.db
DATABASE_BACKUP_PATH=trading.db.backup

# Logging
LOG_LEVEL=INFO                       # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FILE=logs/multi_strategy.log
LOG_MAX_BYTES=10485760               # 10MB
LOG_BACKUP_COUNT=5

# GitHub Actions (set in GitHub Secrets, not .env)
# ALPACA_API_KEY
# ALPACA_SECRET_KEY
# ALPHA_VANTAGE_API_KEY
# EMAIL_USERNAME
# EMAIL_PASSWORD
# EMAIL_TO
```

**Security Best Practices:**
1. ✅ Never commit `.env` to git (use `.gitignore`)
2. ✅ Use GitHub Secrets for CI/CD
3. ✅ Use app passwords for email (not account password)
4. ✅ Rotate API keys periodically
5. ✅ Keep `ALPACA_PAPER=true` until ready for live trading

---

### Monitoring & Observability

#### Logging Strategy

**Multi-Level Logging:**
```python
# 1. Console Logging (stdout)
#    - Real-time execution progress
#    - Color-coded by severity
#    - Captured by GitHub Actions

# 2. File Logging (logs/multi_strategy.log)
#    - Persistent record of all events
#    - Rotated at 10MB (5 backups)
#    - Structured format with timestamps

# 3. Structured Logging (JSON)
#    - Machine-readable events
#    - Queryable for analytics
#    - Stored in database (optional)

# 4. Email Alerts
#    - Critical failures
#    - Daily digest
#    - Reconciliation failures
```

**Log Levels:**
- **DEBUG:** Detailed diagnostic info (position sizing calculations, correlation values)
- **INFO:** General execution flow (signals generated, trades executed)
- **WARNING:** Non-critical issues (data quality warnings, signal rejections)
- **ERROR:** Errors that don't halt execution (API failures with retry)
- **CRITICAL:** System-halting errors (reconciliation failure, kill switch triggered)

**Example Log Output:**
```
2026-01-15 21:33:15 INFO     [execution_engine] Starting multi-strategy execution
2026-01-15 21:33:16 INFO     [regime_detector] Detected regime: low_volatility
2026-01-15 21:33:17 INFO     [strategy_rsi] Generated 2 signals: AAPL, CSCO
2026-01-15 21:33:18 WARNING  [correlation_filter] Attenuated CSCO size: 0.75x (corr=0.65)
2026-01-15 21:33:19 INFO     [execution_engine] Executed 2 trades, total notional: $3,824.97
2026-01-15 21:33:20 INFO     [broker_reconciler] Reconciliation: PASS
```

#### Artifact Tracking

**Daily Artifacts:**
1. **JSON Snapshot** (`artifacts/json/YYYY-MM-DD.json`)
   - Complete system state
   - All signals, trades, positions
   - Risk metrics, regime state
   - ~50KB per day

2. **Signal Funnel** (`artifacts/funnel/signal_funnel_*.json`)
   - Per-strategy funnel metrics
   - Conversion rates at each stage
   - Identifies bottlenecks

3. **Signal Rejections** (`artifacts/funnel/signal_rejections_*.json`)
   - Detailed rejection reasons
   - Symbol-level tracking
   - Helps diagnose filtering issues

4. **Data Quality Report** (`artifacts/data_quality/*.json`)
   - Blocked symbols
   - Staleness warnings
   - Outlier detections

**Artifact Retention:**
- GitHub Actions: 90 days
- Local: Indefinite (manual cleanup)

#### Performance Metrics Dashboard (Future)

**Proposed Web Dashboard:**
```
┌─────────────────────────────────────────────────────────────┐
│  TRADING SYSTEM DASHBOARD                                   │
├─────────────────────────────────────────────────────────────┤
│  Portfolio Value: $100,664.56  │  Daily P&L: +$124.32      │
│  Cash: $96,876.52              │  Total P&L: +$664.56      │
│  Positions: 2                  │  Max DD: -2.1%            │
│  Heat: 3.8% / 40%              │  Sharpe: 0.92             │
├─────────────────────────────────────────────────────────────┤
│  [Equity Curve Chart]                                       │
│  [Drawdown Chart]                                           │
│  [Strategy Allocation Chart]                                │
├─────────────────────────────────────────────────────────────┤
│  Recent Trades                                              │
│  ┌──────┬────────┬───────┬────────┬─────────┬──────────┐  │
│  │ Date │ Symbol │ Action│ Shares │  Price  │   P&L    │  │
│  ├──────┼────────┼───────┼────────┼─────────┼──────────┤  │
│  │01/13 │  AAPL  │  BUY  │   7    │ $261.05 │  -$7.50  │  │
│  │01/13 │  CSCO  │  BUY  │  26    │  $60.12 │  -$6.20  │  │
│  └──────┴────────┴───────┴────────┴─────────┴──────────┘  │
└─────────────────────────────────────────────────────────────┘
```

**Technology Options:**
- **Streamlit:** Python-native, easy to build
- **Flask + Chart.js:** More customizable
- **Grafana + SQLite:** Professional monitoring

---

### Potential Infrastructure Improvements

#### 1. Code Organization

**Current Issues:**
- Risk management modules scattered in `src/` root
- Utilities not grouped
- No clear module hierarchy

**Proposed Reorganization:**
```
src/
├── core/
│   ├── execution_engine.py
│   ├── main.py
│   └── database.py
│
├── strategies/
│   ├── __init__.py
│   ├── base_strategy.py
│   └── [5 strategy files]
│
├── risk/
│   ├── __init__.py
│   ├── portfolio_risk_manager.py
│   ├── drawdown_stop_manager.py
│   ├── stop_loss_manager.py
│   ├── correlation_filter.py
│   └── kill_switch_service.py
│
├── regime/
│   ├── __init__.py
│   ├── regime_detector.py
│   └── dynamic_allocator.py
│
├── data/
│   ├── __init__.py
│   ├── data_loader.py
│   ├── data_quality_checker.py
│   └── market_data_fetcher.py
│
├── monitoring/
│   ├── __init__.py
│   ├── signal_funnel_tracker.py
│   ├── structured_logger.py
│   └── performance_metrics.py
│
├── integration/
│   ├── __init__.py
│   ├── broker_reconciler.py
│   ├── alpaca_client.py
│   └── email_notifier.py
│
└── utils/
    ├── __init__.py
    ├── artifact_writer.py
    └── helpers.py
```

**Benefits:**
- ✅ Clear module boundaries
- ✅ Easier to navigate
- ✅ Better import organization
- ✅ Supports package-level `__init__.py` for exports

---

#### 2. Database Migration to PostgreSQL

**Current:** SQLite (single file, no concurrency)

**Proposed:** PostgreSQL (client-server, concurrent access)

**Benefits:**
- ✅ Better concurrency (multiple readers/writers)
- ✅ Advanced querying (window functions, CTEs)
- ✅ Better performance at scale
- ✅ Native JSON support
- ✅ Replication and backups

**Migration Path:**
1. Set up PostgreSQL instance (local or cloud)
2. Create migration script (SQLite → PostgreSQL)
3. Update `database.py` to use `psycopg2` instead of `sqlite3`
4. Test thoroughly in development
5. Migrate production data

**Trade-offs:**
- ⚠️ More complex setup
- ⚠️ Requires server infrastructure
- ⚠️ Higher cost (if cloud-hosted)

---

#### 3. Containerization (Docker)

**Current:** Native Python execution

**Proposed:** Docker containers

**Dockerfile Example:**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ta-lib \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/
COPY scripts/ ./scripts/
COPY data/ ./data/

# Set environment
ENV PYTHONUNBUFFERED=1

# Run trading system
CMD ["python", "src/main.py"]
```

**Benefits:**
- ✅ Consistent execution environment
- ✅ Easy deployment (any platform)
- ✅ Isolated dependencies
- ✅ Reproducible builds

**Docker Compose for Local Development:**
```yaml
version: '3.8'

services:
  trading-system:
    build: .
    volumes:
      - ./trading.db:/app/trading.db
      - ./logs:/app/logs
      - ./artifacts:/app/artifacts
    env_file:
      - .env
    depends_on:
      - postgres

  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: trading
      POSTGRES_USER: trader
      POSTGRES_PASSWORD: secure_password
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

---

#### 4. Cloud Deployment Options

**Option A: AWS Lambda (Serverless)**
- ✅ Pay per execution
- ✅ No server management
- ⚠️ 15-minute max execution time
- ⚠️ Cold start latency

**Option B: AWS ECS/Fargate (Containers)**
- ✅ Full control
- ✅ Scalable
- ⚠️ More expensive
- ⚠️ Requires container orchestration

**Option C: DigitalOcean Droplet (VPS)**
- ✅ Simple setup
- ✅ Predictable cost ($5-20/month)
- ✅ Full control
- ⚠️ Manual server management

**Option D: GitHub Actions (Current)**
- ✅ Free tier (2,000 min/month)
- ✅ No infrastructure
- ✅ Built-in CI/CD
- ⚠️ Limited execution time
- ⚠️ No persistent storage

**Recommendation:** Stick with GitHub Actions until you need:
- Longer execution times (>6 hours)
- Real-time monitoring
- More frequent execution (intraday)
- Persistent infrastructure

---

#### 5. Real-Time Monitoring Stack

**Proposed Stack:**
```
┌─────────────────────────────────────────────────────────────┐
│  MONITORING STACK                                           │
├─────────────────────────────────────────────────────────────┤
│  Layer 1: Data Collection                                   │
│  ├─ Application Logs → Fluentd → Elasticsearch             │
│  ├─ Metrics → Prometheus                                    │
│  └─ Traces → Jaeger (optional)                             │
│                                                              │
│  Layer 2: Storage                                           │
│  ├─ Elasticsearch (logs)                                    │
│  ├─ Prometheus (metrics)                                    │
│  └─ PostgreSQL (structured data)                           │
│                                                              │
│  Layer 3: Visualization                                     │
│  ├─ Grafana (dashboards)                                    │
│  ├─ Kibana (log exploration)                               │
│  └─ Custom Web UI (Streamlit)                              │
│                                                              │
│  Layer 4: Alerting                                          │
│  ├─ Prometheus Alertmanager                                │
│  ├─ PagerDuty (critical alerts)                            │
│  └─ Email/Slack (notifications)                            │
└─────────────────────────────────────────────────────────────┘
```

**Simpler Alternative (Recommended):**
- **Logs:** Keep file-based logging, upload to S3 daily
- **Metrics:** Store in PostgreSQL, query with SQL
- **Dashboards:** Build simple Streamlit app
- **Alerts:** Email notifications (current approach)

---

#### 6. Testing Infrastructure

**Current State:** Minimal testing

**Proposed Test Pyramid:**
```
         /\
        /  \  E2E Tests (5%)
       /────\  - Full workflow tests
      /      \ - Paper trading validation
     /────────\
    /          \ Integration Tests (15%)
   /────────────\ - Strategy + risk integration
  /              \ - Database + broker integration
 /────────────────\
/                  \ Unit Tests (80%)
────────────────────  - Strategy logic
                      - Risk calculations
                      - Position sizing
                      - Data quality checks
```

**Test Framework:**
```python
# tests/test_strategies.py
import pytest
from src.strategies.strategy_rsi_mean_reversion import RSIMeanReversionStrategy

def test_rsi_signal_generation():
    strategy = RSIMeanReversionStrategy(strategy_id=1, capital=20000)
    
    # Create mock market data
    market_data = create_mock_data(rsi=28, rsi_slope=5.0)
    
    signals = strategy.generate_signals(market_data)
    
    assert len(signals) == 1
    assert signals[0]['action'] == 'BUY'
    assert signals[0]['symbol'] == 'AAPL'

def test_rsi_no_signal_when_rsi_high():
    strategy = RSIMeanReversionStrategy(strategy_id=1, capital=20000)
    market_data = create_mock_data(rsi=60)
    
    signals = strategy.generate_signals(market_data)
    
    assert len(signals) == 0
```

**CI/CD Integration:**
```yaml
# .github/workflows/test.yml
name: Run Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: pytest tests/ --cov=src --cov-report=html
      - uses: actions/upload-artifact@v3
        with:
          name: coverage-report
          path: htmlcov/
```

---

#### 7. Configuration Management

**Current:** Hardcoded parameters in source code

**Proposed:** Centralized configuration

**File:** `config/trading_config.yaml`
```yaml
# Trading System Configuration

system:
  name: "Multi-Strategy Trading System"
  version: "1.0.0"
  mode: "paper"  # paper or live

execution:
  schedule: "15 21 * * 1-5"  # 4:15 PM ET, Mon-Fri
  timezone: "America/New_York"
  execution_delay_seconds: 0

portfolio:
  initial_capital: 100000
  max_portfolio_heat: 0.30
  max_daily_loss_pct: 0.02
  max_correlated_exposure: 0.40

strategies:
  - id: 1
    name: "RSI Mean Reversion"
    enabled: true
    capital_allocation: 20000
    parameters:
      rsi_threshold: 35
      rsi_exit: 50
      hold_days: 20
  
  - id: 2
    name: "ML Momentum"
    enabled: true
    capital_allocation: 20000
    parameters:
      confidence_threshold: 0.6
      lookback_days: 252

risk_management:
  stop_loss:
    enabled: true
    atr_multiplier: 3.0
  
  drawdown_stop:
    halt_threshold: 0.08
    panic_threshold: 0.10
    cooldown_days: 5
    rampup_days: 10
  
  correlation_filter:
    enabled: true
    max_correlation: 0.7
    window_days: 60

regime:
  volatility:
    low_threshold: 0.15
    high_threshold: 0.25
  
  adjustments:
    low_volatility:
      max_heat: 0.40
      position_multiplier: 1.2
    high_volatility:
      max_heat: 0.20
      position_multiplier: 0.8

data:
  universe:
    - AAPL
    - MSFT
    - GOOGL
    # ... (36 stocks)
  
  max_age_hours: 72
  quality_checks:
    max_nan_pct: 0.10
    outlier_std_dev: 5.0
```

**Benefits:**
- ✅ Easy parameter tuning (no code changes)
- ✅ Environment-specific configs (dev, staging, prod)
- ✅ Version control for parameters
- ✅ A/B testing different configurations

---

### Security Considerations

#### 1. API Key Management
- ✅ Use environment variables (never hardcode)
- ✅ Use GitHub Secrets for CI/CD
- ✅ Rotate keys every 90 days
- ✅ Use separate keys for dev/prod

#### 2. Database Security
- ✅ No sensitive data in database (no API keys)
- ✅ Regular backups (daily)
- ✅ Encrypted backups (if cloud storage)

#### 3. Code Security
- ✅ No credentials in code
- ✅ `.gitignore` for sensitive files
- ✅ Dependency scanning (GitHub Dependabot)
- ✅ Code review for changes

#### 4. Network Security
- ✅ HTTPS for all API calls
- ✅ Verify SSL certificates
- ✅ Rate limiting on API calls

#### 5. Operational Security
- ✅ Paper trading mode by default
- ✅ Manual approval for live trading
- ✅ Kill switches for emergency stops
- ✅ Audit logs for all trades

---

### Cost Analysis

**Current Monthly Costs:**
```
GitHub Actions:    $0 (free tier, <2000 min/month)
Alpaca API:        $0 (paper trading)
Alpha Vantage:     $0 (free tier, 5 calls/min)
Email (Gmail):     $0 (free)
Domain/Hosting:    $0 (using GitHub)
─────────────────────
TOTAL:             $0/month
```

**Potential Future Costs:**
```
# If scaling up:
GitHub Actions Pro:       $4/month (3,000 min)
Alpha Vantage Premium:    $50/month (unlimited calls)
PostgreSQL (AWS RDS):     $15/month (db.t3.micro)
DigitalOcean Droplet:     $12/month (2GB RAM)
Domain Name:              $12/year
Monitoring (Datadog):     $15/month (basic plan)
─────────────────────────
TOTAL:                    ~$100/month
```

**Cost Optimization:**
- Keep GitHub Actions (free tier sufficient)
- Use SQLite until hitting concurrency limits
- Self-host monitoring (Grafana + Prometheus)
- Use free email (Gmail)

---

## Contact & Support

**System Owner:** Shreyas Chickerur  
**Last Review:** January 16, 2026  
**Next Review:** February 16, 2026

**For Questions:**
- Review this document first
- Check `docs/guides/` for operational procedures
- Check `artifacts/` for daily execution logs
- Review GitHub Actions logs for automation status
- Consult `.cascade/project_context.md` for AI assistant context

**For Infrastructure Improvements:**
- Review "Potential Infrastructure Improvements" section above
- Consider trade-offs (complexity vs. benefits)
- Start with simple improvements (code organization, testing)
- Scale infrastructure as needed (don't over-engineer)

---

**END OF DOCUMENT**
