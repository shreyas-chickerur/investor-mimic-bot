# Trading Strategy Flowcharts

Complete visual guide to how each strategy generates signals.

---

## 1. RSI Mean Reversion Strategy

### Purpose
Identify oversold stocks that are turning up, avoiding "falling knives"

### Flowchart
```
START
  ↓
Load Historical Data (20+ days for RSI)
  ↓
For Each Symbol:
  ↓
Calculate RSI (14-period)
  ↓
Is RSI < 30? ────NO───→ Skip Symbol
  ↓ YES
Calculate RSI Slope (current - previous)
  ↓
Is RSI Slope > 0? ────NO───→ Skip Symbol
  ↓ YES                      (Avoiding falling knife)
Check if already holding position
  ↓
Already holding? ────YES───→ Skip Symbol
  ↓ NO
Calculate Position Size (ATR-based, 1% risk)
  ↓
GENERATE BUY SIGNAL
  ↓
Hold for 20 days or until:
  - RSI > 70 (overbought) OR
  - 5% profit target OR
  - 3% stop loss
  ↓
GENERATE SELL SIGNAL
  ↓
END
```

### Key Parameters
- **RSI Threshold:** 30 (oversold)
- **RSI Exit:** 70 (overbought)
- **Hold Period:** 20 days
- **Profit Target:** 5%
- **Stop Loss:** 3%

### Example
```
Day 1: AVGO RSI = 15.43 (oversold)
Day 2: AVGO RSI = 22.56 (slope = +7.13) ✅ BUY SIGNAL
Hold for 20 days or until RSI > 70
Day 15: AVGO RSI = 72 ✅ SELL SIGNAL
```

---

## 2. MA Crossover Strategy

### Purpose
Capture momentum when short-term trend crosses above long-term trend

### Flowchart
```
START
  ↓
Load Historical Data (200+ days for SMA200)
  ↓
For Each Symbol:
  ↓
Calculate SMA20 (20-day moving average)
  ↓
Calculate SMA50 (50-day moving average)
  ↓
Previous: SMA20 < SMA50? ────NO───→ Check for Sell
  ↓ YES
Current: SMA20 > SMA50? ────NO───→ Skip Symbol
  ↓ YES                            (No crossover)
Golden Cross Detected!
  ↓
Check Volume Confirmation
  ↓
Volume > 20-day avg? ────NO───→ Skip Symbol
  ↓ YES
Check if already holding position
  ↓
Already holding? ────YES───→ Skip Symbol
  ↓ NO
Calculate Position Size (ATR-based, 1% risk)
  ↓
GENERATE BUY SIGNAL
  ↓
Hold until Death Cross:
  - SMA20 crosses below SMA50
  ↓
GENERATE SELL SIGNAL
  ↓
END
```

### Key Parameters
- **Short MA:** 20 days
- **Long MA:** 50 days
- **Volume Confirmation:** Required
- **Exit:** Death cross (SMA20 < SMA50)

### Example
```
Day 1: AAPL SMA20 = 149.50, SMA50 = 150.00 (below)
Day 2: AAPL SMA20 = 150.25, SMA50 = 150.00 (above) ✅ GOLDEN CROSS
       Volume = 80M (avg = 70M) ✅ BUY SIGNAL
Hold until death cross
Day 45: AAPL SMA20 = 148.00, SMA50 = 149.00 ✅ SELL SIGNAL
```

---

## 3. ML Momentum Strategy

### Purpose
Use machine learning to predict positive returns based on technical features

### Flowchart
```
START
  ↓
Load Historical Data (60+ days for features)
  ↓
Training Phase (if not trained):
  ↓
Extract Features:
  - Returns (1d, 5d, 20d, 60d)
  - Price to SMA ratios
  - Volatility (20d, 60d)
  - Volume ratio
  - RSI
  ↓
Create Labels (future 5-day return > 0)
  ↓
Train Logistic Regression Model
  ↓
Save Model & Scaler
  ↓
Prediction Phase:
  ↓
For Each Symbol:
  ↓
Extract Current Features
  ↓
Scale Features (using saved scaler)
  ↓
Predict Probability of Positive Return
  ↓
Probability > 60%? ────NO───→ Skip Symbol
  ↓ YES
Check if already holding position
  ↓
Already holding? ────YES───→ Skip Symbol
  ↓ NO
Calculate Position Size (ATR-based, 1% risk)
  ↓
GENERATE BUY SIGNAL
  ↓
Hold for 5 days
  ↓
GENERATE SELL SIGNAL
  ↓
END
```

### Key Parameters
- **Model:** Logistic Regression
- **Min Probability:** 60%
- **Hold Period:** 5 days
- **Features:** 9 technical indicators
- **Training:** Rolling window (last 252 days)

### Example
```
Training: Use last 252 days of data
Features: [returns_1d=0.02, returns_5d=0.05, rsi=55, ...]
Model predicts: P(positive return) = 0.73 ✅ BUY SIGNAL
Hold for 5 days
Day 5: Auto-exit ✅ SELL SIGNAL
```

---

## 4. News Sentiment Strategy

### Purpose
Use sentiment as a filter for momentum signals (not standalone)

### Flowchart
```
START
  ↓
Load Historical Data
  ↓
For Each Symbol:
  ↓
Check Momentum Signal:
  - Price > SMA20 AND
  - Returns_5d > 0
  ↓
Momentum positive? ────NO───→ Skip Symbol
  ↓ YES
Fetch News Sentiment (if available)
  ↓
Sentiment Score > 0.3? ────NO───→ Skip Symbol
  ↓ YES                          (Negative/neutral news)
Check if already holding position
  ↓
Already holding? ────YES───→ Skip Symbol
  ↓ NO
Calculate Position Size (ATR-based, 1% risk)
  ↓
GENERATE BUY SIGNAL
  ↓
Hold for 10 days or until:
  - Sentiment turns negative OR
  - Price < SMA20
  ↓
GENERATE SELL SIGNAL
  ↓
END
```

### Key Parameters
- **Sentiment Threshold:** 0.3 (positive)
- **Momentum Filter:** Price > SMA20 AND Returns_5d > 0
- **Hold Period:** 10 days
- **Exit:** Sentiment < 0 OR Price < SMA20

### Example
```
Day 1: MSFT Price = $350 (SMA20 = $340) ✅ Above MA
       Returns_5d = +2.5% ✅ Positive momentum
       Sentiment = 0.65 ✅ Positive news
       ✅ BUY SIGNAL
Hold for 10 days or until conditions break
Day 7: Sentiment = -0.2 ✅ SELL SIGNAL
```

---

## 5. Volatility Breakout Strategy

### Purpose
Capture explosive moves when price breaks above volatility bands with confirmation

### Flowchart
```
START
  ↓
Load Historical Data (20+ days for Bollinger Bands)
  ↓
For Each Symbol:
  ↓
Calculate Bollinger Bands (20-day, 2 std dev)
  - Upper Band
  - Middle Band (SMA20)
  - Lower Band
  ↓
Previous Close < Upper Band? ────NO───→ Skip Symbol
  ↓ YES
Current Close > Upper Band? ────NO───→ Skip Symbol
  ↓ YES
Breakout Detected!
  ↓
Check False Breakout Protection:
  ↓
2 consecutive closes > Upper Band? ────NO───→ Skip Symbol
  ↓ YES
Check Volume Confirmation
  ↓
Volume > 1.5x avg? ────NO───→ Skip Symbol
  ↓ YES
Check if already holding position
  ↓
Already holding? ────YES───→ Skip Symbol
  ↓ NO
Calculate Position Size (ATR-based, 1% risk)
  ↓
GENERATE BUY SIGNAL
  ↓
Hold until:
  - Price < Middle Band (SMA20) OR
  - 10 days elapsed
  ↓
GENERATE SELL SIGNAL
  ↓
END
```

### Key Parameters
- **Bollinger Bands:** 20-day, 2 std dev
- **Confirmation:** 2 consecutive closes above upper band
- **Volume:** > 1.5x average
- **Hold Period:** 10 days max
- **Exit:** Price < SMA20

### Example
```
Day 1: NVDA Close = $495 (Upper Band = $500) ✅ Below
Day 2: NVDA Close = $505 (Upper Band = $500) ✅ Above (1st day)
Day 3: NVDA Close = $510 (Upper Band = $500) ✅ Above (2nd day)
       Volume = 120M (avg = 70M, 1.71x) ✅ High volume
       ✅ BUY SIGNAL
Hold until price < SMA20 or 10 days
Day 8: NVDA Close = $485 (SMA20 = $490) ✅ SELL SIGNAL
```

---

## Strategy Comparison Matrix

| Strategy | Signal Type | Hold Period | Risk Level | Market Condition |
|----------|-------------|-------------|------------|------------------|
| RSI Mean Reversion | Counter-trend | 20 days | Medium | Volatile/Oversold |
| MA Crossover | Trend-following | Until death cross | Low | Trending |
| ML Momentum | Predictive | 5 days | Medium | Any |
| News Sentiment | Momentum + Filter | 10 days | Medium | News-driven |
| Volatility Breakout | Breakout | 10 days | High | High volatility |

---

## Signal Generation Priority

When multiple strategies generate signals for the same symbol:

```
1. Check Correlation Filter
   ↓
2. If correlated signals > 70%, reject lower confidence
   ↓
3. Check Portfolio Heat (max 30%)
   ↓
4. If heat limit reached, reject all new signals
   ↓
5. Execute highest confidence signal first
   ↓
6. Update portfolio heat
   ↓
7. Process next signal
```

---

## Risk Management Integration

All strategies integrate with portfolio-level risk management:

```
Signal Generated
  ↓
Calculate Position Size (ATR-based, 1% portfolio risk)
  ↓
Check Cash Available
  ↓
Check Portfolio Heat (current + new < 30%)
  ↓
Check Daily Loss Limit (< -2%)
  ↓
Check Correlation with Existing Positions (< 70%)
  ↓
Apply Execution Costs (7.5 bps slippage + $0.005/share)
  ↓
Execute Trade
  ↓
Monitor for Exit Conditions
  ↓
Apply Catastrophe Stop Loss (2-3x ATR)
```

---

## Data Requirements

| Strategy | Min History | Key Indicators | Data Frequency |
|----------|-------------|----------------|----------------|
| RSI Mean Reversion | 20 days | RSI, VWAP | Daily |
| MA Crossover | 200 days | SMA20, SMA50, Volume | Daily |
| ML Momentum | 252 days | 9 features | Daily |
| News Sentiment | 20 days | Sentiment, SMA20 | Daily |
| Volatility Breakout | 20 days | Bollinger Bands, Volume | Daily |

---

## Exit Conditions Summary

| Strategy | Normal Exit | Stop Loss | Profit Target |
|----------|-------------|-----------|---------------|
| RSI Mean Reversion | RSI > 70 or 20 days | -3% | +5% |
| MA Crossover | Death cross | 2-3x ATR | None |
| ML Momentum | 5 days | 2-3x ATR | None |
| News Sentiment | Sentiment < 0 or 10 days | 2-3x ATR | None |
| Volatility Breakout | Price < SMA20 or 10 days | 2-3x ATR | None |

All strategies also subject to portfolio-level circuit breaker: -2% daily loss limit.
