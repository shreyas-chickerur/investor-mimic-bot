# System Architecture & Technical Reference

**Last Updated:** January 1, 2026

---

## Table of Contents

1. [System Components](#system-components)
2. [File Structure](#file-structure)
3. [Module Reference](#module-reference)
4. [Database Schema](#database-schema)
5. [Data Flow](#data-flow)
6. [Strategy Implementation](#strategy-implementation)
7. [Risk Management](#risk-management)
8. [Production Features](#production-features)

---

## System Components

### Core Execution Layer

**`src/execution_engine.py`** - Main orchestrator (1,200+ lines)
- Initializes all strategies and risk modules
- Runs daily execution workflow
- Manages broker reconciliation
- Coordinates signal generation and trade execution
- Handles stop losses and kill switches

**Key Methods:**
- `__init__()` - Initialize all modules (strategies, risk managers, notifiers)
- `run_all_strategies(market_data)` - Main execution loop
- `check_stop_losses(market_data)` - Check 3x ATR stops before trading
- `_execute_strategy_trades(strategy, signals, exposure, portfolio_value)` - Execute trades with idempotency
- `_build_local_positions()` - Build position snapshot for reconciliation

**Usage:**
```python
from execution_engine import MultiStrategyRunner

# Initialize with run ID
runner = MultiStrategyRunner(run_id="20260101_143000")

# Load market data
market_data = pd.read_csv('data/training_data.csv')

# Execute all strategies
signals = runner.run_all_strategies(market_data)
```

---

### Strategy Layer

**`src/strategy_base.py`** - Abstract base class for all strategies
- Defines common interface for all strategies
- Implements volatility-adjusted position sizing (ATR-based)
- Manages strategy capital and positions
- Tracks entry dates for time-based exits

**Key Methods:**
- `generate_signals(market_data)` - Abstract method, must be implemented by subclasses
- `calculate_position_size(symbol, price, atr, capital)` - ATR-based sizing targeting 1% portfolio risk
- `add_position(symbol, shares)` - Track new position
- `remove_position(symbol)` - Remove closed position
- `update_capital(amount)` - Adjust available capital

**Usage:**
```python
from strategy_base import StrategyBase

class MyStrategy(StrategyBase):
    def generate_signals(self, market_data):
        signals = []
        # Your signal generation logic
        for symbol in self.universe:
            # Calculate indicators
            # Generate signal
            signal = {
                'symbol': symbol,
                'action': 'BUY',
                'confidence': 0.75,
                'reasoning': 'Custom logic',
                'price': current_price,
                'atr': atr_value
            }
            signals.append(signal)
        return signals
```

**Strategy Implementations:**

**`src/strategies/strategy_rsi_mean_reversion.py`**
- **Entry:** RSI < 35 AND RSI slope > 0 AND near VWAP (within 5%)
- **Exit:** RSI > 50 OR price >= VWAP OR held 20 days
- **Logic:** Conditional reversion, avoids falling knives

**`src/strategies/strategy_ma_crossover.py`**
- **Entry:** 20 MA crosses above 100 MA AND ADX > 20
- **Exit:** 20 MA crosses below 100 MA
- **Logic:** Trend-following with strength confirmation

**`src/strategies/strategy_momentum.py`**
- **Entry:** 20-day momentum > threshold with volume confirmation
- **Exit:** Time-based (hold period)
- **Logic:** Captures sustained price movements

**`src/strategies/strategy_ml_momentum.py`**
- **Entry:** Logistic regression predicts P(return_5d > 0) > 60%
- **Exit:** 5 days OR model reversal
- **Logic:** ML classifier for probability-based signals
- **Features:** Returns (1d, 5d, 20d), price ratios, RSI, volatility, volume

---

### Risk Management Layer

**`src/portfolio_risk_manager.py`** - Portfolio-level risk controls
- Monitors total portfolio exposure (heat)
- Enforces daily loss circuit breaker
- Regime-dependent risk adjustments

**Key Methods:**
- `set_daily_start_value(value)` - Set starting portfolio value for daily loss calculation
- `check_daily_loss_limit(current_value)` - Returns False if daily loss exceeds -2%
- `can_add_position(trade_value, current_exposure, portfolio_value)` - Checks if new position fits within heat limit
- `get_current_heat(current_exposure, portfolio_value)` - Calculate current portfolio heat percentage

**Usage:**
```python
from portfolio_risk_manager import PortfolioRiskManager

risk_mgr = PortfolioRiskManager()
risk_mgr.set_daily_start_value(100000)

# Check daily loss limit
if not risk_mgr.check_daily_loss_limit(current_value=98500):
    print("Daily loss limit exceeded, halt trading")

# Check if can add position
if risk_mgr.can_add_position(trade_value=5000, current_exposure=25000, portfolio_value=100000):
    print("Position approved")
```

**`src/correlation_filter.py`** - Prevents correlated positions
- Calculates 60-day and 20-day rolling correlations
- Dual-window detection catches regime shifts
- Size attenuation mode: scales position size based on correlation

**Key Methods:**
- `update_price_history(symbol, prices)` - Add price data for correlation calculation
- `calculate_correlation(symbol1, symbol2)` - Returns correlation coefficient
- `check_correlation(symbol, existing_symbols)` - Returns (is_acceptable, max_corr, corr_symbol)
- `filter_signals_with_sizing(signals, existing_positions, market_data)` - Returns signals with size_multiplier field
- `calculate_size_multiplier(correlation)` - Returns (multiplier, reason) for correlation attenuation

**Correlation Attenuation Rules:**
- corr ≤ 0.5: 100% size (no attenuation)
- 0.5 < corr ≤ 0.8: Linear scale 100% → 25%
- corr > 0.8: Reject (0% size)

**Usage:**
```python
from correlation_filter import CorrelationFilter

corr_filter = CorrelationFilter(max_correlation=0.7)

# Update price history
for symbol in universe:
    prices = market_data[market_data['symbol'] == symbol]['close']
    corr_filter.update_price_history(symbol, prices)

# Filter signals with size attenuation
filtered_signals = corr_filter.filter_signals_with_sizing(
    signals=raw_signals,
    existing_positions={'AAPL': 100, 'MSFT': 50},
    market_data=market_data
)

# Each signal now has 'size_multiplier' field (0.25 to 1.0)
```

**`src/regime_detector.py`** - VIX-based market regime detection
- Classifies market into LOW_VOLATILITY, NORMAL, HIGH_VOLATILITY, CRISIS
- Adjusts risk parameters based on regime

**Key Methods:**
- `detect_regime(vix_level, market_data)` - Returns regime classification
- `get_regime_adjustments(vix_level, market_data)` - Returns dict with adjusted parameters
- `should_enable_strategy(strategy_name, regime_adjustments)` - Returns True if strategy should run

**Regime Rules:**
- VIX < 15: Low volatility → 40% heat, 1.2x positions
- VIX > 25: High volatility → 20% heat, 0.8x positions, disable breakouts
- Normal: 30% heat, 1.0x positions

**`src/stop_loss_manager.py`** - Catastrophe stop losses
- 3x ATR stops (tail protection only)
- Per-position tracking
- Automatic execution before signal generation

**Key Methods:**
- `set_stop_loss(symbol, entry_price, atr)` - Set stop at entry_price - (3 * atr)
- `check_stop_loss(symbol, current_price)` - Returns True if stop triggered
- `get_stop_price(symbol)` - Returns stop loss price
- `remove_stop_loss(symbol)` - Remove tracking after exit

---

### Production Features Layer

**`src/kill_switch_service.py`** - Circuit breakers
- Manual switches via environment variables
- Automatic triggers on critical conditions

**Key Methods:**
- `check_all_switches(context)` - Returns True if trading should proceed
- `is_strategy_enabled(strategy_name)` - Check if specific strategy is enabled
- `get_status()` - Returns kill switch status dict

**Manual Switches:**
- `TRADING_DISABLED=true` - Global halt
- `STRATEGY_DISABLED_LIST=strategy1,strategy2` - Selective disable

**Automatic Conditions:**
- Reconciliation failure
- Daily drawdown >5%
- Consecutive failures ≥3
- Order rejection rate >50% with ≥5 rejected

**Usage:**
```python
from kill_switch_service import KillSwitchService

kill_switch = KillSwitchService(db, email_notifier)

context = {
    'reconciliation_status': 'PASS',
    'daily_drawdown': 0.015,
    'consecutive_failures': 0,
    'rejected_orders_count': 0,
    'total_orders': 5
}

if kill_switch.check_all_switches(context):
    print("Trading allowed")
else:
    print(f"Trading halted: {kill_switch.kill_reasons}")
```

**`src/signal_funnel_tracker.py`** - Signal pipeline tracking
- Tracks signals through 5 stages: raw → regime → correlation → risk → executed
- Logs rejection reasons with details
- Generates "Why No Trade" reports

**Key Methods:**
- `record_raw_signals(strategy_id, count)` - Track initial signal count
- `record_after_regime(strategy_id, count)` - After regime filter
- `record_after_correlation(strategy_id, count)` - After correlation filter
- `record_after_risk(strategy_id, count)` - After risk checks
- `record_executed(strategy_id, count)` - Final executed count
- `log_rejection(strategy_id, symbol, stage, reason_code, details, signal_id)` - Log why signal was rejected
- `save_to_database(strategy_id, strategy_name)` - Persist funnel data
- `get_why_no_trade_report(strategy_id, strategy_name)` - Generate report for email

**Usage:**
```python
from signal_funnel_tracker import SignalFunnelTracker

tracker = SignalFunnelTracker(db)

# Track through pipeline
tracker.record_raw_signals(strategy_id=1, count=12)
tracker.record_after_regime(strategy_id=1, count=9)
tracker.record_after_correlation(strategy_id=1, count=4)
tracker.record_after_risk(strategy_id=1, count=2)
tracker.record_executed(strategy_id=1, count=1)

# Log rejection
tracker.log_rejection(
    strategy_id=1,
    symbol='AAPL',
    stage='CORRELATION',
    reason_code='high_correlation',
    details={'correlation': 0.85, 'with_symbol': 'MSFT'}
)

# Save and generate report
tracker.save_to_database(strategy_id=1, strategy_name='RSI Mean Reversion')
report = tracker.get_why_no_trade_report(strategy_id=1, strategy_name='RSI Mean Reversion')
```

**`src/broker_reconciler.py`** - Mandatory reconciliation gate
- Compares local DB positions with broker positions
- Blocks trading on any mismatch beyond tolerance
- Generates reconciliation reports

**Key Methods:**
- `reconcile_daily(local_positions, local_cash)` - Returns (success, discrepancies)
- `_compare_positions(local_positions, broker_positions)` - Detailed position comparison
- `_compare_cash(local_cash, broker_cash)` - Cash balance comparison

**`src/structured_logger.py`** - JSON event logging
- Logs events to `logs/events/events_{run_id}.jsonl`
- One JSON object per line for easy parsing

**Event Types:**
- SIGNAL_GENERATED, SIGNAL_REJECTED
- ORDER_INTENT_CREATED, ORDER_SUBMITTED, ORDER_FILLED, ORDER_REJECTED
- RECONCILIATION_CHECK, KILL_SWITCH_TRIGGERED
- STRATEGY_DISABLED, RISK_LIMIT_HIT, ERROR

**Usage:**
```python
from structured_logger import StructuredLogger

logger = StructuredLogger(run_id='20260101_143000')

# Log signal generation
logger.log_signal_generated(
    strategy_id=1,
    symbol='AAPL',
    action='BUY',
    confidence=0.75,
    reasoning='RSI < 30 and turning upward'
)

# Log rejection
logger.log_signal_rejected(
    strategy_id=1,
    symbol='MSFT',
    stage='CORRELATION',
    reason_code='high_correlation',
    details={'correlation': 0.85}
)
```

---

### Database Layer

**`src/database.py`** - SQLite database interface

**Core Tables:**
- `strategies` - Strategy metadata (id, name, description, capital)
- `signals` - All generated signals with terminal states
- `trades` - Executed trades with costs
- `positions` - Current positions per strategy
- `broker_state` - Broker snapshots (START, RECONCILIATION, END)
- `system_state` - Key-value system state

**Production Tables:**
- `signal_funnel` - Funnel counts per run (raw → executed)
- `signal_rejections` - Per-signal rejection reasons
- `order_intents` - Idempotency tracking with deterministic IDs
- `pending_signals` - Blocked signals with decay window

**Key Methods:**
- `create_strategy(name, description, capital)` - Create or get strategy
- `log_signal(strategy_id, symbol, signal_type, confidence, reasoning, asof_date)` - Log signal
- `update_signal_terminal_state(signal_id, terminal_state, reason)` - Mark signal outcome
- `log_trade(strategy_id, signal_id, symbol, action, shares, ...)` - Log executed trade
- `update_position(strategy_id, symbol, shares, avg_price, current_price)` - Update position
- `save_signal_funnel(strategy_id, strategy_name, raw, regime, correlation, risk, executed)` - Save funnel data
- `log_signal_rejection(strategy_id, symbol, stage, reason_code, details, signal_id)` - Log rejection
- `create_order_intent(strategy_id, symbol, side, target_qty)` - Generate deterministic intent ID
- `update_order_intent_status(intent_id, status, broker_order_id, error)` - Track order lifecycle
- `check_duplicate_order_intent(strategy_id, symbol, side, target_qty)` - Check for duplicates

**Order Intent ID Generation:**
```python
# Deterministic hash: run_id + strategy_id + symbol + side + qty + hour_bucket
timestamp_bucket = datetime.now().strftime('%Y%m%d_%H')
intent_string = f"{run_id}_{strategy_id}_{symbol}_{side}_{target_qty}_{timestamp_bucket}"
intent_id = hashlib.sha256(intent_string.encode()).hexdigest()[:16]
```

---

### Utility Modules

**`src/cash_manager.py`** - Per-strategy cash allocation
- Reserves cash before trades
- Prevents overdraft across strategies

**`src/execution_costs.py`** - Realistic cost modeling
- Slippage: 7.5 basis points (0.075%)
- Commission: $0.005 per share
- Returns execution price including costs

**`src/performance_metrics.py`** - Comprehensive metrics
- Sharpe, Sortino, Calmar ratios
- Max drawdown, win rate, profit factor
- Average win/loss, hold time

**`src/email_notifier.py`** - Email notifications
- Daily digest with funnel analysis
- Critical alerts
- HTML formatting

**`src/data_validator.py`** - Data quality checks
- Freshness validation (<24 hours)
- Completeness checks
- Quality thresholds

**`src/universe_provider.py`** - Symbol universe management
- Static mode: 36 default symbols
- CSV mode: Load from `config/universe.csv` (150+ symbols)
- Dynamic mode: Future screener integration

**`src/pending_signals_manager.py`** - Signal decay window
- Persist blocked-but-valid signals
- Re-evaluate for 3 days
- Automatic cleanup of expired signals

**`src/config_typed.py`** - Pydantic configuration
- Strong typing with validation
- Environment variable loading
- Production readiness checks

---

## Database Schema

### Core Schema

```sql
-- Strategies
CREATE TABLE strategies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    capital_allocation REAL,
    initial_capital REAL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Signals
CREATE TABLE signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    strategy_id INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    signal_type TEXT NOT NULL,
    confidence REAL,
    reasoning TEXT,
    asof_date TEXT,
    generated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    terminal_state TEXT,
    terminal_reason TEXT,
    terminal_at TEXT,
    FOREIGN KEY (strategy_id) REFERENCES strategies(id)
);

-- Trades
CREATE TABLE trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    strategy_id INTEGER NOT NULL,
    signal_id INTEGER,
    symbol TEXT NOT NULL,
    action TEXT NOT NULL,
    shares REAL NOT NULL,
    requested_price REAL,
    exec_price REAL,
    slippage_cost REAL,
    commission_cost REAL,
    total_cost REAL,
    notional REAL,
    order_id TEXT,
    executed_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (strategy_id) REFERENCES strategies(id),
    FOREIGN KEY (signal_id) REFERENCES signals(id)
);

-- Positions
CREATE TABLE positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_id INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    shares REAL NOT NULL,
    avg_price REAL,
    current_price REAL,
    market_value REAL,
    unrealized_pnl REAL,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (strategy_id) REFERENCES strategies(id),
    UNIQUE(strategy_id, symbol)
);
```

### Production Schema

```sql
-- Signal Funnel
CREATE TABLE signal_funnel (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    strategy_id INTEGER NOT NULL,
    strategy_name TEXT NOT NULL,
    raw_signals_count INTEGER DEFAULT 0,
    after_regime_count INTEGER DEFAULT 0,
    after_correlation_count INTEGER DEFAULT 0,
    after_risk_count INTEGER DEFAULT 0,
    executed_count INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (strategy_id) REFERENCES strategies(id)
);

-- Signal Rejections
CREATE TABLE signal_rejections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    signal_id INTEGER,
    strategy_id INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    stage TEXT NOT NULL,
    reason_code TEXT NOT NULL,
    details_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (signal_id) REFERENCES signals(id),
    FOREIGN KEY (strategy_id) REFERENCES strategies(id)
);

-- Order Intents (Idempotency)
CREATE TABLE order_intents (
    intent_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    strategy_id INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    target_qty REAL NOT NULL,
    status TEXT NOT NULL,
    broker_order_id TEXT,
    error_code TEXT,
    error_message TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    submitted_at TEXT,
    acked_at TEXT,
    filled_at TEXT,
    FOREIGN KEY (strategy_id) REFERENCES strategies(id)
);

-- Pending Signals
CREATE TABLE pending_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_id INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    signal_data_json TEXT NOT NULL,
    blocked_reason TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    retry_count INTEGER DEFAULT 0,
    last_retry_at TEXT,
    status TEXT DEFAULT 'PENDING',
    FOREIGN KEY (strategy_id) REFERENCES strategies(id)
);
```

---

## Data Flow

### Daily Execution Flow

```
1. GitHub Actions Trigger (6:30 AM PST)
   ↓
2. Fetch Market Data (Alpha Vantage API)
   - 300 days historical OHLCV
   - Calculate technical indicators (RSI, ATR, ADX, VWAP, etc.)
   ↓
3. Initialize Execution Engine
   - Load database from previous run
   - Initialize all strategies
   - Initialize risk managers
   - Initialize production modules
   ↓
4. Kill Switch Check
   - Check manual switches (TRADING_DISABLED, STRATEGY_DISABLED_LIST)
   - Check automatic conditions (reconciliation, drawdown, failures)
   - HALT if any switch triggered
   ↓
5. Stop Loss Check
   - Check all positions against 3x ATR stops
   - Execute stop loss exits if triggered
   ↓
6. Broker Reconciliation (MANDATORY GATE)
   - Compare local DB positions with Alpaca positions
   - Compare cash balances
   - HALT if mismatch beyond 1% tolerance
   ↓
7. Daily Loss Check
   - Calculate daily P&L
   - HALT if loss exceeds -2%
   ↓
8. Signal Generation (Per Strategy)
   - Generate raw signals
   - Track: FUNNEL STAGE 1 (raw count)
   ↓
9. Regime Filter
   - Check if strategy enabled for current regime
   - Track: FUNNEL STAGE 2 (after regime)
   ↓
10. Correlation Filter
   - Calculate correlations with existing positions
   - Apply size attenuation (0.5-0.8 corr)
   - Reject if correlation > 0.8
   - Track: FUNNEL STAGE 3 (after correlation)
   ↓
11. Log Signals to Database
   - Create signal records
   - Assign signal IDs
   ↓
12. Risk & Cash Checks
   - Check portfolio heat limit
   - Check available cash
   - Track: FUNNEL STAGE 4 (after risk)
   ↓
13. Order Intent Creation (Idempotency)
   - Generate deterministic intent_id
   - Check for duplicate intents
   - Skip if already submitted
   ↓
14. Trade Execution
   - Apply size multiplier from correlation attenuation
   - Calculate execution costs
   - Submit market orders to Alpaca
   - Update intent status
   - Track: FUNNEL STAGE 5 (executed)
   ↓
15. Update Database
   - Log trades
   - Update positions
   - Save funnel data
   - Log rejections
   ↓
16. Generate Reports
   - Signal funnel summary
   - "Why No Trade" reports
   - Performance metrics
   ↓
17. Send Email Digest
   - Funnel analysis
   - Trade summary
   - Portfolio metrics
   - Current positions
   ↓
18. Upload Artifacts
   - Database (trading.db)
   - Logs (multi_strategy.log)
   - Event logs (events_{run_id}.jsonl)
   - 90-day retention
```

---

## Technical Stack

**Languages:**
- Python 3.8
- Bash (scripts)
- YAML (GitHub Actions)

**Core Libraries:**
- `pandas` - Data manipulation
- `numpy` - Numerical computing
- `scikit-learn` - ML models
- `matplotlib` - Plotting
- `alpaca-py` - Broker API
- `pydantic` - Configuration validation
- `sqlite3` - Database

**Infrastructure:**
- GitHub Actions - Automation
- SQLite - Database
- Gmail SMTP - Notifications
- Alpaca Markets - Broker

---

## Performance Considerations

### Execution Time
- Typical run: 1-2 minutes
- Data fetch: 10-20 seconds
- Signal generation: 5-10 seconds per strategy
- Trade execution: 1-2 seconds per trade

### Memory Usage
- Historical data: ~50 MB
- Database: ~5 MB
- Peak memory: ~200 MB

### Scalability
- Current: 32-36 symbols, 4 strategies
- CSV mode: 150+ symbols supported
- Bottleneck: API rate limits (Alpha Vantage: 5 calls/minute)

---

## Security

**Secrets Management:**
- All credentials stored as GitHub Secrets
- Never committed to repository
- Loaded as environment variables at runtime

**API Keys:**
- Alpaca API key/secret (broker)
- Alpha Vantage API key (data)
- Gmail credentials (notifications)

**Database:**
- SQLite file persisted as GitHub Actions artifact
- 90-day retention
- No sensitive data stored

---

**For detailed usage instructions, see:** `docs/guides/USAGE_GUIDE.md`  
**For operational procedures, see:** `docs/guides/RUNBOOK.md`
