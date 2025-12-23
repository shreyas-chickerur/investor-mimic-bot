# Trading System Algorithm Specification

**Purpose:** This document explains the trading algorithms used in the multi-strategy trading system for external review and improvement suggestions.

---

## System Overview

**Type:** Multi-strategy automated paper trading system  
**Platform:** Alpaca Paper Trading API  
**Execution:** Daily at 10:00 AM ET via GitHub Actions  
**Capital:** $100,000 portfolio split across 5 strategies ($20K each)  
**Universe:** 36 large-cap US stocks (AAPL, MSFT, GOOGL, etc.)

---

## Strategy 1: RSI Mean Reversion

### Core Logic
Buy oversold stocks with low volatility, hold for fixed period.

### Entry Conditions
```python
BUY if:
  1. RSI(14) < 30  (oversold)
  AND
  2. Volatility(20d) < 1.25 × Rolling_Median_Volatility
```

### Exit Conditions
```python
SELL if:
  - Held for 20 days (time-based exit)
```

### Position Sizing
- 10% of strategy capital per trade
- Max 10 positions per strategy
- Max 2 positions per symbol

### Technical Details
- **RSI Calculation:** 14-period Relative Strength Index
- **Volatility:** 20-day rolling standard deviation of returns
- **Volatility Threshold:** Dynamic based on expanding median of all stocks

### Rationale
- RSI < 30 identifies oversold conditions (potential reversal)
- Low volatility filter reduces risk of catching falling knives
- Fixed holding period removes emotion from exit decision

---

## Strategy 2: Moving Average Crossover

### Core Logic
Golden cross (bullish) and death cross (bearish) signals.

### Entry Conditions
```python
BUY if:
  - 50-day MA crosses ABOVE 200-day MA (golden cross)
  AND
  - Not already holding this symbol
```

### Exit Conditions
```python
SELL if:
  - 50-day MA crosses BELOW 200-day MA (death cross)
```

### Position Sizing
- 10% of strategy capital per trade
- Max 10 positions per strategy

### Technical Details
- **Short MA:** 50-day simple moving average
- **Long MA:** 200-day simple moving average
- **Crossover Detection:** Compare current vs previous day values

### Rationale
- Classic trend-following approach
- 50/200 MA crossover is widely watched by institutions
- Captures sustained trends while avoiding whipsaws

---

## Strategy 3: ML Momentum

### Core Logic
Machine learning model predicts 5-day forward returns.

### Entry Conditions
```python
BUY if:
  - Predicted_Return_5d > threshold
  AND
  - Model_Confidence > 0.6
```

### Exit Conditions
```python
SELL if:
  - Held for 5 days
  OR
  - Predicted_Return_5d < 0 (model reversal)
```

### Features Used
- Returns: 1d, 5d, 20d, 60d
- Price ratios: Price/SMA20, Price/SMA50, Price/SMA200
- Volatility: 20d, 60d
- Volume ratio: Volume/SMA20
- RSI(14)

### Model Details
- **Type:** Random Forest Regressor (placeholder - not fully implemented)
- **Target:** 5-day forward return
- **Training:** Rolling window approach

### Rationale
- Captures non-linear patterns traditional indicators miss
- Multiple timeframe features provide context
- Short holding period aligns with prediction horizon

---

## Strategy 4: News Sentiment

### Core Logic
Combine sentiment analysis with technical indicators.

### Entry Conditions
```python
BUY if:
  - News_Sentiment > 0.6 (positive)
  AND
  - RSI < 40 (not overbought)
  AND
  - Volume_Ratio > 1.2 (increased interest)
```

### Exit Conditions
```python
SELL if:
  - News_Sentiment < 0.4 (sentiment deteriorates)
  OR
  - Held for 10 days
```

### Sentiment Calculation
- **Source:** News headlines (placeholder - not fully implemented)
- **Method:** NLP sentiment scoring
- **Aggregation:** Weighted by recency and source credibility

### Rationale
- News drives short-term price movements
- Technical filters prevent buying into overbought conditions
- Volume confirms market interest in the news

---

## Strategy 5: Volatility Breakout

### Core Logic
Buy stocks breaking out of low volatility with volume confirmation.

### Entry Conditions
```python
BUY if:
  - Price > Upper_Bollinger_Band (breakout)
  AND
  - Volatility(20d) < Historical_Median (low vol environment)
  AND
  - Volume > 1.5 × Volume_SMA(20) (volume confirmation)
```

### Exit Conditions
```python
SELL if:
  - Price < Lower_Bollinger_Band (breakdown)
  OR
  - Held for 15 days
```

### Technical Details
- **Bollinger Bands:** 20-period, 2 standard deviations
- **Volume Filter:** 1.5x the 20-day moving average
- **Volatility Check:** Must be below historical median

### Rationale
- Volatility compression often precedes large moves
- Breakouts from low volatility tend to be more sustainable
- Volume confirmation reduces false breakouts

---

## Risk Management

### Position Limits
- **Per Strategy:** Max 10 positions
- **Per Symbol:** Max 2 positions across all strategies
- **Position Size:** 10% of strategy capital

### Cash Management
- Each strategy allocated $20K from $100K portfolio
- Cash reserved before order execution
- Prevents overdraft across strategies
- Prioritizes trades by confidence if insufficient cash

### Data Validation
- **Freshness Check:** Data must be < 24 hours old
- **Completeness:** All required indicators must be present
- **Quality:** < 10% NaN values allowed
- **History:** Minimum 250 days for 200-day MA strategies

### Error Handling
- Failed trades don't stop other strategies
- Email alerts on critical failures
- Graceful degradation if data unavailable

---

## Execution Flow

### Daily Sequence (10:00 AM ET)
1. **Download Previous State**
   - Retrieve databases from previous run
   - Load position history

2. **Data Update**
   - Fetch 300 days of historical data
   - Calculate all technical indicators
   - Validate data quality

3. **Database Sync**
   - Reconcile local DB with Alpaca positions
   - Preserve entry dates
   - Ensure position accuracy

4. **Signal Generation**
   - Each strategy analyzes market independently
   - Generate buy/sell signals
   - Rank by confidence

5. **Trade Execution**
   - Check cash availability
   - Execute top 3 signals per strategy
   - Update positions in real-time

6. **Performance Tracking**
   - Calculate portfolio values
   - Record daily metrics
   - Update P&L per strategy

7. **Notification**
   - Send email summary
   - Upload artifacts to GitHub
   - Log all activity

---

## Current Performance Metrics

### Backtested Results (Historical)
- **RSI Mean Reversion:** +146.7% annual return (on $10K)
- **Other Strategies:** Not fully backtested yet

### Live Performance
- **Portfolio Value:** $100,275.81
- **Cash Available:** $16,992.43
- **Active Positions:** 2 (AVGO, TXN)
- **Total Trades:** 2 executed

---

## Known Limitations

### Strategy Implementation
1. **ML Momentum:** Model not trained, using placeholder logic
2. **News Sentiment:** Sentiment API not integrated, using placeholder
3. **Volatility Breakout:** Bollinger Bands calculation needs verification

### Data Issues
1. **Historical Data:** Only 100 days initially (now fixed to 300)
2. **Real-time Prices:** Using end-of-day data, not intraday
3. **Corporate Actions:** Not adjusted for splits/dividends

### Execution Issues
1. **Slippage:** Not modeled (paper trading uses exact prices)
2. **Market Impact:** Not considered (small position sizes)
3. **Liquidity:** Assumes all orders fill (valid for large-cap stocks)

### System Issues
1. **Position Tracking:** Was broken (now fixed)
2. **Capital Allocation:** Was using cash only (now uses portfolio value)
3. **Exit Logic:** Was missing (now implemented)

---

## Technical Stack

### Data Sources
- **Price Data:** Alpaca API (300 days, daily bars)
- **Indicators:** Calculated locally (pandas/numpy)
- **News:** Not yet integrated

### Execution
- **Broker:** Alpaca Paper Trading API
- **Order Type:** Market orders, day duration
- **Execution Time:** 10:00 AM ET (market open)

### Storage
- **Database:** SQLite (two databases)
  - `trading_system.db` - Legacy single strategy
  - `strategy_performance.db` - Multi-strategy tracking
- **Persistence:** GitHub Actions artifacts (90-day retention)

### Infrastructure
- **Compute:** GitHub Actions (Ubuntu, Python 3.8)
- **Scheduling:** Cron (weekdays at 10 AM ET)
- **Monitoring:** Email notifications + artifacts

---

## Areas for Improvement

### Strategy Enhancements
1. **Dynamic Position Sizing:** Use Kelly Criterion or volatility-based sizing
2. **Stop Losses:** Add protective stops (currently only time-based exits)
3. **Profit Targets:** Take profits at predefined levels
4. **Correlation Filter:** Avoid correlated positions across strategies
5. **Regime Detection:** Adjust strategies based on market regime (bull/bear/sideways)

### Risk Management
1. **Portfolio-Level Stops:** Emergency stop if down X%
2. **Drawdown Limits:** Reduce position sizes after losses
3. **Exposure Limits:** Cap sector/industry concentration
4. **Leverage Control:** Currently 1x, could optimize

### Execution
1. **Limit Orders:** Use limit orders instead of market orders
2. **VWAP Execution:** Split large orders over time
3. **Timing Optimization:** Test different execution times
4. **Partial Fills:** Handle partial order fills

### Data & Features
1. **Alternative Data:** Integrate news, social sentiment, options flow
2. **Fundamental Data:** Add P/E, earnings, revenue growth
3. **Market Microstructure:** Bid-ask spread, order book depth
4. **Cross-Asset Signals:** VIX, bonds, commodities

### Machine Learning
1. **Model Training:** Actually train the ML model (currently placeholder)
2. **Feature Engineering:** Add interaction terms, polynomial features
3. **Ensemble Methods:** Combine multiple models
4. **Online Learning:** Update model with new data

### System Architecture
1. **Database Consolidation:** Merge two databases into one schema
2. **Real-time Execution:** Move from daily to intraday
3. **Backtesting Framework:** Systematic strategy testing
4. **Parameter Optimization:** Grid search for optimal parameters

---

## Questions for Review

1. **Strategy Logic:** Are the entry/exit conditions sound? Any obvious flaws?

2. **Risk Management:** Is 10% position sizing appropriate? Should we use dynamic sizing?

3. **Holding Periods:** Are fixed holding periods (5, 10, 15, 20 days) optimal or should they be dynamic?

4. **Indicator Parameters:** Are the default parameters (RSI 14, MA 50/200, etc.) optimal or should they be optimized?

5. **Strategy Correlation:** How can we ensure strategies are uncorrelated to maximize diversification?

6. **Exit Strategy:** Should we add stop losses and profit targets instead of time-based exits?

7. **Capital Allocation:** Is equal weighting ($20K each) optimal or should we weight by historical performance?

8. **Signal Prioritization:** Currently taking top 3 signals per strategy - is this optimal?

9. **Data Frequency:** Should we move from daily to intraday data for better entries/exits?

10. **Performance Metrics:** What additional metrics should we track beyond P&L?

---

## Request for Feedback

Please review this specification and provide:
- **Critical Flaws:** Any obvious mistakes in the logic
- **Improvement Suggestions:** Specific enhancements to consider
- **Best Practices:** Industry-standard approaches we're missing
- **Risk Concerns:** Potential risks we haven't addressed
- **Optimization Ideas:** Ways to improve returns or reduce risk

Focus on actionable improvements that can be implemented incrementally.
