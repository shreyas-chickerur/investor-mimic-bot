# System Architecture

**Investor Mimic Bot - Multi-Strategy Trading System**

---

## Overview

A portfolio-level, multi-strategy trading system with professional-grade risk management, regime detection, and automated execution. Designed for $1,000+ capital with conservative risk controls.

---

## System Components

### 1. Core (`src/core/`)

**`database.py`** - TradingDatabase
- SQLite-based persistence layer
- Tables: strategies, trades, positions, signals, performance_metrics, regime_history
- Run-level tracking for backtesting and live trading
- Thread-safe operations

**`strategy_base.py`** - TradingStrategy (Abstract Base Class)
- Base class for all trading strategies
- Position tracking, capital management
- Trade history and performance metrics
- Abstract `generate_signals()` method

**`execution_engine.py`** - MultiStrategyRunner
- Orchestrates all 5 strategies
- Portfolio-level coordination
- Integrates all risk controls and filters
- Execution timing: 4:15 PM ET (avoids lookahead bias)

---

### 2. Strategies (`src/strategies/`)

**`strategy_rsi_mean_reversion.py`** - RSIMeanReversionStrategy
- Entry: RSI < 30 (oversold) AND RSI slope > 0 (turning up)
- Exit: RSI > 50 OR price >= VWAP OR 20 days held
- Allocation: 20% of portfolio

**`strategy_ma_crossover.py`** - MACrossoverStrategy
- Entry: Fast MA (20) crosses above Slow MA (50)
- Exit: Fast MA crosses below Slow MA
- Volume confirmation required
- Allocation: 20% of portfolio

**`strategy_ml_momentum.py`** - MLMomentumStrategy
- Logistic regression classifier (not regressor)
- Features: RSI, momentum, volume, volatility
- Entry: Probability > 60%
- Exit: 5 days or probability < 40%
- Allocation: 20% of portfolio

**`strategy_volatility_breakout.py`** - VolatilityBreakoutStrategy
- Entry: Price breaks above Bollinger Band + volume surge
- Exit: Price returns to middle band or 7 days
- Allocation: 20% of portfolio

**`strategy_news_sentiment.py`** - NewsSentimentStrategy
- News-based momentum (placeholder for future implementation)
- Allocation: 20% of portfolio

---

### 3. Risk Management (`src/risk/`)

**`portfolio_risk_manager.py`** - PortfolioRiskManager
- **Portfolio heat limit**: 30% max exposure
- **Daily loss limit**: -2% halts trading
- **Correlation tracking**: 60-day rolling window
- **Position sizing**: ATR-based, 1% portfolio risk per trade

**`correlation_filter.py`** - CorrelationFilter
- Rejects positions with correlation > 0.70
- 60-day rolling correlation window
- 20-day short window for regime shifts
- Reduces tail risk and concentration

**`stop_loss_manager.py`** - StopLossManager
- Catastrophic stops only: 2.5x ATR
- Not tight stops (avoid whipsaws)
- Tail protection, not active management

**`drawdown_stop_manager.py`** - DrawdownStopManager
- **8% drawdown**: Halt new entries, 10-day cooldown
- **10% drawdown**: Panic mode, flatten all positions, 20-day cooldown
- Automated health checks before resume
- 50% sizing ramp-up after cooldown

**`broker_reconciler.py`** - BrokerReconciler
- Daily reconciliation: Database vs. Alpaca positions
- Tolerance: $10 cash, $0.50 price, 0 shares quantity
- Pauses trading on mismatch
- Email alerts on failure

---

### 4. Regime Detection (`src/regime/`)

**`regime_detector.py`** - RegimeDetector
- Detects market regime: Trend vs. Chop, High vs. Low Volatility
- Uses VIX, ADX, rolling volatility
- Strategies adapt to regime (e.g., disable MA Crossover in chop)

**`dynamic_allocator.py`** - DynamicAllocator
- Adjusts strategy weights based on rolling performance
- Caps single strategy dominance at 35%
- Rebalances monthly based on Sharpe/Calmar ratios

---

### 5. Data Management (`src/data/`)

**`data_fetcher.py`** - AlpacaDataFetcher
- Fetches daily OHLCV from Alpaca API
- Calculates technical indicators: RSI, SMA, ATR, Bollinger Bands, VWAP

**`data_validator.py`** - DataValidator
- Validates OHLCV data quality
- Checks for missing dates, invalid prices, zero volume
- Rejects bad data before strategy execution

**`universe_provider.py`** - UniverseProvider
- Provides list of tradable stocks (36 large-cap US stocks)
- Filters by liquidity, market cap, sector diversity

**`data_quality_checker.py`** - DataQualityChecker
- Pre-execution data quality checks
- Ensures sufficient lookback periods
- Validates indicator calculations

---

### 6. Integration (`src/integration/`)

**`dry_run_wrapper.py`** - DryRunWrapper
- Simulates trades without actual execution
- Logs intended trades for testing
- Useful for paper trading validation

**`cash_manager.py`** - CashManager
- Tracks available cash for trading
- Reserves cash for open orders
- Prevents over-allocation

**`pending_signals_manager.py`** - PendingSignalsManager
- Manages signals that couldn't be executed immediately
- Signal decay: 3 days default
- Retries on next execution cycle

**`strategy_runner.py`** - StrategyRunner
- Executes individual strategy logic
- Coordinates with risk controls
- Logs signal funnel (generated → filtered → executed)

**`strategy_database.py`** - StrategyDatabase
- Strategy-specific database operations
- Performance tracking per strategy
- Trade attribution

**`portfolio_backtester.py`** - PortfolioBacktester
- Walk-forward backtesting framework
- 2-year train, 6-month test, 6-month step
- Portfolio-level metrics (not per-strategy)

---

### 7. Monitoring (`src/monitoring/`)

**`pnl_calculator.py`** - PnLCalculator
- Real-time P&L calculation
- Daily, weekly, monthly aggregation
- Strategy-level attribution

**`signal_funnel_tracker.py`** - SignalFunnelTracker
- Tracks signal flow: Generated → Correlation Filter → Risk Filter → Executed
- Identifies bottlenecks (e.g., too many rejections)

**`strategy_health_scorer.py`** - StrategyHealthScorer
- Scores strategy health: Win rate, Sharpe, drawdown
- Flags underperforming strategies
- Triggers allocation adjustments

**`artifact_writer.py`** - DailyArtifactWriter
- Writes daily reports to `artifacts/` directory
- JSON format: trades, positions, P&L, risk metrics
- Timestamped for historical review

---

### 8. Utilities (`src/utils/`)

**`config_loader.py`** - ConfigLoader (Singleton)
- Loads `config/trading_config.yaml`
- Dot notation access: `config.get('risk.max_portfolio_heat')`
- Reload capability for live updates

**`email_notifier.py`** - EmailNotifier
- Sends email alerts for critical events
- SMTP configuration via `.env`
- Alert levels: INFO, WARNING, CRITICAL

**`execution_costs.py`** - ExecutionCostModel
- Models slippage (0.05%) and commissions ($0)
- Adjusts expected P&L for realistic backtesting

**`kill_switch_service.py`** - KillSwitchService
- Emergency stop mechanism
- Triggered by external signal or manual intervention
- Halts all trading immediately

**`structured_logger.py`** - StructuredLogger
- JSON-formatted logs for easy parsing
- Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
- Separate log files per module

**`signal_tracer.py`** - SignalFlowTracer
- Traces signal lifecycle from generation to terminal state
- Ensures every signal reaches exactly one terminal state
- Validates no signals are lost or duplicated

**`window_boundary_guardrail.py`** - Window Boundary Guardrail
- Prevents trading at window boundaries (e.g., start/end of backtest)
- Ensures clean entry/exit from trading periods

---

## Data Flow

```
1. Data Fetching (4:00 PM ET)
   ↓
2. Data Validation
   ↓
3. Regime Detection
   ↓
4. Strategy Signal Generation (5 strategies in parallel)
   ↓
5. Signal Aggregation
   ↓
6. Correlation Filter (reject correlated positions)
   ↓
7. Portfolio Risk Manager (check heat, daily loss)
   ↓
8. Position Sizing (ATR-based, 1% risk)
   ↓
9. Execution Cost Model (adjust for slippage)
   ↓
10. Broker Reconciliation (pre-execution check)
    ↓
11. Trade Execution (4:15 PM ET)
    ↓
12. Position Tracking & P&L Update
    ↓
13. Performance Metrics & Artifacts
    ↓
14. Drawdown Check (post-execution)
    ↓
15. Email Alerts (if needed)
```

---

## Execution Timing

**4:00 PM ET**: Market close, data available  
**4:00-4:10 PM ET**: Data fetching, validation, indicator calculation  
**4:10-4:15 PM ET**: Signal generation, risk filtering, position sizing  
**4:15 PM ET**: Trade execution (market-on-close orders)  
**4:15-4:30 PM ET**: Reconciliation, P&L update, artifacts, alerts  

**Why 4:15 PM?** Avoids lookahead bias (using today's close to trade today). Trades execute at next day's open/close.

---

## Risk Control Hierarchy

1. **Kill Switch** (manual emergency stop)
2. **Drawdown Stops** (8% halt, 10% panic)
3. **Daily Loss Limit** (-2% halts trading)
4. **Portfolio Heat Limit** (30% max exposure)
5. **Correlation Filter** (>0.70 rejected)
6. **Position Sizing** (1% risk per trade)
7. **Stop Losses** (2.5x ATR catastrophic stops)

Each layer is independent and can halt trading. Multiple layers provide defense-in-depth.

---

## Configuration System

**`config/trading_config.yaml`** - Central configuration file

Sections:
- **risk**: Portfolio heat, daily loss, correlation thresholds
- **position_sizing**: ATR-based sizing, max position size
- **execution**: Timing, order types, slippage
- **regime**: VIX thresholds, ADX thresholds
- **strategies**: Per-strategy parameters (RSI levels, MA periods, etc.)
- **data**: Universe, lookback periods, indicators
- **monitoring**: Alert thresholds, artifact settings
- **backtesting**: Walk-forward parameters
- **paper_trading**: Dry-run settings
- **database**: SQLite configuration

All modules load config via `get_config()` singleton. No hardcoded values.

---

## Database Schema

**strategies** - Strategy metadata (id, name, capital, allocation)  
**trades** - All executed trades (entry/exit, P&L, strategy_id)  
**positions** - Current open positions (symbol, shares, entry_price, strategy_id)  
**signals** - Generated signals (symbol, action, confidence, terminal_state)  
**performance_metrics** - Daily metrics (portfolio_value, drawdown, heat, sharpe)  
**regime_history** - Regime changes over time (regime_type, vix_level, timestamp)  
**reconciliation_log** - Broker reconciliation results (status, mismatches, timestamp)  

---

## Testing Strategy

**Unit Tests** (`tests/`)
- 257 tests, 85% pass rate
- 100% coverage required on critical modules:
  - Risk management
  - Drawdown stops
  - Broker reconciliation
  - Signal tracing

**Integration Tests**
- Paper trading: 2 weeks minimum
- End-to-end signal flow
- Broker API integration

**Backtesting**
- Walk-forward: 2-year train, 6-month test
- Stress tests: 2008, 2020, 2022
- Realistic metrics validation (Sharpe 0.8-1.3, DD 10-20%)

---

## Deployment Modes

**1. Backtesting** (`TRADING_MODE=backtest`)
- Historical data only
- No API calls
- Fast execution
- Portfolio-level metrics

**2. Paper Trading** (`TRADING_MODE=paper`)
- Alpaca paper trading API
- Real-time data
- Simulated execution
- Validate before live

**3. Dry Run** (`DRY_RUN=true`)
- Live data, no execution
- Logs intended trades
- Final validation step

**4. Live Trading** (`TRADING_MODE=live`, `DRY_RUN=false`)
- Real money, real execution
- Full risk controls active
- Daily monitoring required

---

## Performance Expectations

**Realistic Targets:**
- Annual Return: 10-25%
- Sharpe Ratio: 0.8-1.3
- Max Drawdown: 10-20%
- Win Rate: 45-55%
- Time in Market: 40-60%

**Red Flags:**
- Sharpe >2.0 (likely leakage)
- Max DD <5% (unrealistic)
- Win rate >65% (suspicious)
- Smooth equity curve (check bias)

---

## Known Limitations

1. **No intraday trading** - Daily bars only, end-of-day execution
2. **No leverage** - Cash account, 1x buying power
3. **No options/futures** - Stocks only
4. **No short selling** - Long-only strategies
5. **Limited universe** - 36 large-cap US stocks
6. **Survivorship bias** - Historical data may exclude delisted stocks
7. **Slippage model** - Static 0.05%, not adaptive
8. **News sentiment** - Placeholder, not fully implemented

---

## Security Considerations

- API keys stored in `.env` (never committed)
- Database local only (not exposed)
- Logs sanitized (no sensitive data)
- Email credentials secure
- No remote access by default
- Backup strategy for database

---

## Maintenance

**Daily**: Logs review, reconciliation check  
**Weekly**: Strategy performance review, risk metrics  
**Monthly**: Full backtest refresh, parameter review  
**Quarterly**: Dependency updates, security patches  
**Annually**: Full system audit, architecture review

---

## Future Enhancements

1. **Regime-adaptive risk limits** (low VIX: 40% heat, high VIX: 20% heat)
2. **Dynamic correlation window** (20-day override during regime shifts)
3. **Execution cost scaling** (by ATR and volume percentile)
4. **News sentiment implementation** (currently placeholder)
5. **Multi-timeframe analysis** (weekly/monthly trends)
6. **Machine learning enhancements** (feature engineering, model selection)
7. **Portfolio optimization** (mean-variance, risk parity)
8. **Tax-loss harvesting** (for taxable accounts)

---

**This architecture is designed for:**
- Modularity (easy to add/remove strategies)
- Testability (every component unit-tested)
- Safety (multiple layers of risk control)
- Observability (comprehensive logging and monitoring)
- Maintainability (clear separation of concerns)
