# Complete Trading System Workflow

**Last Updated:** December 23, 2025  
**Status:** Production-Ready, Phase 4 Complete

---

## System Overview

This is a **multi-strategy portfolio trading system** that:
1. Analyzes 36 S&P 500 stocks daily
2. Uses 5 different trading strategies
3. Applies portfolio-level risk management
4. Executes trades via Alpaca API
5. Sends daily email summaries

---

## Complete Workflow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         DAILY EXECUTION CYCLE                        │
│                        (Runs at market close)                        │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 1: DATA COLLECTION                                             │
├─────────────────────────────────────────────────────────────────────┤
│ • Fetch latest market data for 36 symbols                           │
│ • Calculate technical indicators (RSI, SMA, Bollinger Bands, etc.)  │
│ • Update training_data.csv with new bars                            │
│ • Calculate returns, volatility, volume ratios                      │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 2: REGIME DETECTION                                            │
├─────────────────────────────────────────────────────────────────────┤
│ • Check VIX level (volatility index)                                │
│ • Classify market regime:                                           │
│   - LOW VOLATILITY (VIX < 15): Max heat = 40%                       │
│   - NORMAL (15 ≤ VIX ≤ 25): Max heat = 30%                          │
│   - HIGH VOLATILITY (VIX > 25): Max heat = 20%                      │
│ • Adjust strategy allocation based on regime                        │
│ • Disable certain strategies in high volatility                     │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 3: STRATEGY SIGNAL GENERATION (Parallel)                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│ ┌──────────────────────────────────────────────────────────────┐   │
│ │ Strategy 1: RSI Mean Reversion                               │   │
│ │ • Find oversold stocks (RSI < 30)                            │   │
│ │ • Check for positive RSI slope (avoiding falling knives)     │   │
│ │ • Generate BUY signals                                        │   │
│ │ • Exit when RSI > 70 or 20 days elapsed                      │   │
│ └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│ ┌──────────────────────────────────────────────────────────────┐   │
│ │ Strategy 2: MA Crossover                                     │   │
│ │ • Detect golden cross (SMA20 > SMA50)                        │   │
│ │ • Require volume confirmation                                │   │
│ │ • Generate BUY signals                                        │   │
│ │ • Exit on death cross (SMA20 < SMA50)                        │   │
│ └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│ ┌──────────────────────────────────────────────────────────────┐   │
│ │ Strategy 3: ML Momentum                                      │   │
│ │ • Train Logistic Regression on last 252 days                 │   │
│ │ • Predict probability of positive 5-day return               │   │
│ │ • Generate BUY if probability > 60%                          │   │
│ │ • Exit after 5 days                                          │   │
│ └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│ ┌──────────────────────────────────────────────────────────────┐   │
│ │ Strategy 4: News Sentiment                                   │   │
│ │ • Check momentum (price > SMA20, returns > 0)                │   │
│ │ • Filter by positive sentiment (> 0.3)                       │   │
│ │ • Generate BUY signals                                        │   │
│ │ • Exit when sentiment turns negative or 10 days              │   │
│ └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│ ┌──────────────────────────────────────────────────────────────┐   │
│ │ Strategy 5: Volatility Breakout                              │   │
│ │ • Detect Bollinger Band breakouts                            │   │
│ │ • Require 2 consecutive closes above upper band              │   │
│ │ • Require high volume (> 1.5x average)                       │   │
│ │ • Generate BUY signals                                        │   │
│ │ • Exit when price < SMA20 or 10 days                         │   │
│ └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 4: SIGNAL FILTERING                                            │
├─────────────────────────────────────────────────────────────────────┤
│ • Correlation Filter:                                                │
│   - Check correlation between new signal and existing positions     │
│   - Reject if correlation > 70%                                     │
│   - Prevents over-concentration in correlated stocks                │
│                                                                      │
│ • Duplicate Filter:                                                  │
│   - Remove duplicate signals for same symbol                        │
│   - Keep highest confidence signal                                  │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 5: POSITION SIZING                                             │
├─────────────────────────────────────────────────────────────────────┤
│ For each signal:                                                     │
│ • Calculate ATR (Average True Range) for volatility                 │
│ • Risk per trade = 1% of portfolio value                            │
│ • Shares = (Portfolio × 0.01) / (2 × ATR)                           │
│ • Cap at 10% of portfolio value per position                        │
│ • Adjust for execution costs (slippage + commission)                │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 6: RISK CHECKS (Pre-Execution)                                 │
├─────────────────────────────────────────────────────────────────────┤
│ 1. Cash Check:                                                       │
│    • Verify sufficient cash for trade + costs                       │
│    • Reject if insufficient funds                                   │
│                                                                      │
│ 2. Portfolio Heat Check:                                             │
│    • Current exposure + new position < max heat (30%)               │
│    • Reject if would exceed limit                                   │
│                                                                      │
│ 3. Daily Loss Circuit Breaker:                                      │
│    • Check if daily loss > -2%                                      │
│    • HALT ALL TRADING if triggered                                  │
│                                                                      │
│ 4. Position Limit Check:                                             │
│    • Max 10 positions total                                         │
│    • Max 2 positions per symbol                                     │
│    • Reject if limits exceeded                                      │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 7: TRADE EXECUTION                                             │
├─────────────────────────────────────────────────────────────────────┤
│ For each approved signal:                                            │
│                                                                      │
│ • Calculate execution price with slippage (7.5 bps)                 │
│ • Add commission ($0.005 per share)                                 │
│ • Submit market order to Alpaca API                                 │
│ • Wait for fill confirmation                                        │
│ • Record trade in portfolio                                         │
│ • Update cash balance                                               │
│ • Log execution details                                             │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 8: POSITION MONITORING                                         │
├─────────────────────────────────────────────────────────────────────┤
│ For each existing position:                                          │
│                                                                      │
│ • Check strategy-specific exit conditions:                          │
│   - RSI: Exit if RSI > 70 or 20 days elapsed                        │
│   - MA: Exit on death cross                                         │
│   - ML: Exit after 5 days                                           │
│   - Sentiment: Exit if sentiment < 0 or 10 days                     │
│   - Breakout: Exit if price < SMA20 or 10 days                      │
│                                                                      │
│ • Check catastrophe stop loss (2-3x ATR)                            │
│ • Check profit targets (if applicable)                              │
│ • Generate SELL signals when conditions met                         │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 9: EXIT EXECUTION                                              │
├─────────────────────────────────────────────────────────────────────┤
│ For each exit signal:                                                │
│                                                                      │
│ • Calculate execution price with slippage                           │
│ • Add commission                                                    │
│ • Submit market order to Alpaca API                                 │
│ • Wait for fill confirmation                                        │
│ • Remove position from portfolio                                    │
│ • Update cash balance                                               │
│ • Calculate P&L for closed trade                                    │
│ • Log exit details                                                  │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 10: PERFORMANCE TRACKING                                       │
├─────────────────────────────────────────────────────────────────────┤
│ • Update equity curve                                                │
│ • Calculate daily return                                            │
│ • Update cumulative returns                                         │
│ • Track max drawdown                                                │
│ • Calculate win rate                                                │
│ • Track strategy-level performance                                  │
│ • Log all metrics to database                                       │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 11: REPORTING                                                   │
├─────────────────────────────────────────────────────────────────────┤
│ • Generate daily summary email:                                      │
│   - Portfolio value and daily P&L                                   │
│   - Open positions with current P&L                                 │
│   - Trades executed today                                           │
│   - Strategy performance breakdown                                  │
│   - Risk metrics (heat, drawdown)                                   │
│   - Alerts if any issues                                            │
│                                                                      │
│ • Send email via SMTP                                               │
│ • Log summary to file                                               │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                              [Wait for next day]
```

---

## Key Components Explained

### 1. Data Pipeline
- **Input:** Alpaca API (real-time market data)
- **Storage:** `data/training_data.csv` (historical + new data)
- **Features:** 26 columns including OHLCV, returns, indicators
- **Update:** Daily after market close

### 2. Strategy Engine
- **5 independent strategies** run in parallel
- Each generates signals based on different logic
- No inter-strategy dependencies
- Strategies can be enabled/disabled per regime

### 3. Risk Management (Multi-Layer)

**Layer 1: Position Sizing**
- ATR-based volatility adjustment
- 1% risk per trade
- Max 10% per position

**Layer 2: Portfolio Heat**
- Max 30% of portfolio in positions (normal regime)
- Adjusted by volatility regime
- Prevents over-leverage

**Layer 3: Circuit Breakers**
- Daily loss limit: -2%
- Halts all trading if triggered
- Protects against catastrophic losses

**Layer 4: Correlation Filter**
- Max 70% correlation between positions
- Prevents concentration risk
- Ensures diversification

**Layer 5: Stop Losses**
- Catastrophe stops: 2-3x ATR
- Strategy-specific exits
- Profit targets where applicable

### 4. Execution Pipeline

```
Signal → Position Sizing → Risk Checks → Execution → Tracking
   ↓           ↓              ↓            ↓           ↓
 Filter    Calculate      Verify       Submit      Record
 Dupes      Shares         Cash         Order       Trade
```

### 5. Validation Infrastructure (Phase 4)

**Signal Injection Mode:**
- Injects synthetic signals for testing
- Bypasses strategy generation
- Validates execution pipeline
- Used for CI/CD testing

**Parameter Sweep:**
- Tests multiple parameter sets
- Validates strategy logic
- Ensures robustness
- Validation only (doesn't affect production)

**Volatile Period Testing:**
- Tests system in extreme conditions
- COVID crash, 2022 bear market, 2018 correction
- Validates circuit breakers
- Ensures risk management works

---

## File Organization

### Core Trading System
```
src/
├── portfolio_backtester.py      # Main backtesting engine
├── regime_detector.py           # VIX-based regime detection
├── correlation_filter.py        # Position correlation checks
├── portfolio_risk_manager.py    # Portfolio-level risk management
├── execution_costs.py           # Slippage and commission modeling
└── performance_metrics.py       # Performance tracking
```

### Strategies
```
src/strategies/
├── strategy_rsi_mean_reversion.py
├── strategy_ma_crossover.py
├── strategy_ml_momentum.py
├── strategy_news_sentiment.py
└── strategy_volatility_breakout.py
```

### Validation (Phase 4)
```
src/
├── signal_injection_engine.py   # Synthetic signal generation
└── signal_flow_tracer.py        # Signal lifecycle tracking
```

### Configuration
```
config/
├── config.yaml                  # Production settings
└── validation_config.yaml       # Validation/testing settings
```

### Scripts
```
scripts/
├── run_walkforward_backtest.py  # Main backtest runner
├── run_validation_backtest.py   # Validation testing
├── test_single_strategy.py      # Strategy unit tests
└── debug_single_signal.py       # Execution debugging
```

---

## Production Deployment

### Daily Execution (Automated)
```bash
# Runs at 4:30 PM ET (after market close)
python scripts/run_walkforward_backtest.py

# This will:
# 1. Fetch latest market data
# 2. Generate signals from all strategies
# 3. Execute approved trades via Alpaca
# 4. Send email summary
```

### Manual Testing
```bash
# Test signal generation
python scripts/test_single_strategy.py

# Test execution pipeline
python scripts/debug_single_signal.py

# Run validation tests
python scripts/run_validation_backtest.py
```

### GitHub Actions (CI/CD)
```yaml
# Runs on every push to main
# Tests:
# - Module imports
# - Unit tests
# - Integration tests
# - Signal generation
# - Execution pipeline
# - Validation backtest
```

---

## Data Flow

```
Alpaca API
    ↓
Market Data
    ↓
Technical Indicators
    ↓
Strategy Signals
    ↓
Risk Filtering
    ↓
Position Sizing
    ↓
Execution
    ↓
Portfolio Update
    ↓
Performance Tracking
    ↓
Email Report
```

---

## Error Handling

### Graceful Degradation
- If one strategy fails, others continue
- If data fetch fails, use cached data
- If email fails, log locally

### Circuit Breakers
- Daily loss limit: -2%
- Portfolio heat limit: 30%
- Position limits: 10 max

### Logging
- All trades logged to `logs/`
- Errors logged with stack traces
- Daily summaries archived

---

## Security

### API Keys
- Stored in `.env` file (not in git)
- Loaded via `python-dotenv`
- Never logged or exposed

### Email Credentials
- Stored in `.env` file
- Used only for sending reports
- SMTP over TLS

### Data Privacy
- No PII collected
- Market data only
- Local storage only

---

## Performance Expectations

### Realistic Targets (Based on Phase 4 Testing)
- **Annual Return:** 5-15% (conservative)
- **Max Drawdown:** 10-20%
- **Win Rate:** 45-55%
- **Sharpe Ratio:** 0.5-1.5
- **Trades per month:** 5-15

### Risk Metrics
- **Daily VaR (95%):** ~1.5%
- **Max portfolio heat:** 30%
- **Max position size:** 10%
- **Max daily loss:** -2% (circuit breaker)

---

## Maintenance

### Daily
- Check email summary
- Verify trades executed
- Monitor portfolio heat

### Weekly
- Review strategy performance
- Check for data quality issues
- Verify API connectivity

### Monthly
- Analyze overall performance
- Review risk metrics
- Update documentation if needed

### Quarterly
- Retrain ML models
- Review strategy parameters
- Audit risk management

---

## Troubleshooting

### No Trades Executing
1. Check if circuit breaker triggered (-2% daily loss)
2. Verify portfolio heat not at limit (30%)
3. Check if strategies generating signals
4. Verify sufficient cash available
5. Check correlation filter not rejecting all signals

### Strategies Not Generating Signals
1. Check market conditions (may be normal)
2. Verify data quality (no missing indicators)
3. Check regime detector (strategies may be disabled)
4. Review strategy parameters (may be too strict)

### API Errors
1. Verify API keys in `.env`
2. Check Alpaca account status
3. Verify market hours
4. Check rate limits

---

## Next Steps (Phase 5)

1. **Live Paper Trading**
   - Run system with paper trading account
   - Monitor for 30 days
   - Verify all components work in production

2. **Performance Monitoring**
   - Set up dashboards
   - Track key metrics
   - Alert on anomalies

3. **Optimization** (if needed)
   - Review strategy performance
   - Adjust parameters if justified
   - Document all changes

4. **Production Deployment**
   - Switch to live trading account
   - Start with small capital
   - Scale up gradually

---

## Summary

This is a **complete, production-ready trading system** that:
- ✅ Analyzes 36 stocks daily
- ✅ Uses 5 different strategies
- ✅ Applies comprehensive risk management
- ✅ Executes trades automatically
- ✅ Sends daily reports
- ✅ Has been validated in Phase 4
- ✅ Ready for paper trading

**The system is conservative, well-tested, and designed for long-term stability over short-term gains.**
