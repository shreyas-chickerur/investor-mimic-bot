# Code Consolidation Plan

**Current State:** 26 Python files in `src/` directory  
**Goal:** Consolidate into logical groupings for better maintainability

---

## Current File Structure Analysis

### Core Trading System (8 files)
- `main.py` - Entry point
- `multi_strategy_main.py` - Main trading orchestrator
- `trading_system.py` - Trading system class
- `strategy_runner.py` - Strategy execution
- `trade_executor.py` - Trade execution
- `cash_manager.py` - Cash management
- `stop_loss_manager.py` - Stop loss tracking
- `config.py` - Configuration loader

### Data & Market (3 files)
- `alpaca_data_fetcher.py` - Alpaca API integration
- `vix_data_fetcher.py` - VIX data fetching
- `data_validator.py` - Data quality checks

### Risk Management (4 files)
- `portfolio_risk_manager.py` - Portfolio-level risk
- `correlation_filter.py` - Correlation checks
- `execution_costs.py` - Cost modeling
- `regime_detector.py` - Market regime detection

### Strategy System (2 files + 5 strategy files)
- `strategy_base.py` - Base strategy class
- `dynamic_allocator.py` - Dynamic allocation
- `strategies/` folder with 5 strategy implementations

### Backtesting & Validation (3 files)
- `portfolio_backtester.py` - Backtesting engine
- `signal_injection_engine.py` - Validation testing
- `signal_flow_tracer.py` - Signal tracking

### Monitoring & Reporting (4 files)
- `performance_metrics.py` - Performance tracking
- `email_notifier.py` - Email reports
- `dashboard_server.py` - Web dashboard
- `strategy_dashboard.py` - Strategy monitoring

### Data Storage & Security (2 files)
- `strategy_database.py` - Database operations
- `security.py` - Security & authentication

---

## Proposed Consolidation

### Option 1: Functional Grouping (Recommended)

```
src/
├── core/
│   ├── __init__.py
│   ├── trading_engine.py          # Combines: trading_system.py, strategy_runner.py, trade_executor.py
│   ├── portfolio_manager.py       # Combines: cash_manager.py, stop_loss_manager.py
│   └── config.py                  # Keep as-is
│
├── data/
│   ├── __init__.py
│   ├── market_data.py             # Combines: alpaca_data_fetcher.py, vix_data_fetcher.py
│   └── validators.py              # Rename: data_validator.py
│
├── risk/
│   ├── __init__.py
│   └── risk_management.py         # Combines: portfolio_risk_manager.py, correlation_filter.py,
│                                  #           execution_costs.py, regime_detector.py
│
├── strategies/
│   ├── __init__.py
│   ├── base.py                    # Rename: strategy_base.py
│   ├── allocator.py               # Rename: dynamic_allocator.py
│   ├── rsi_mean_reversion.py     # Keep as-is
│   ├── ma_crossover.py            # Keep as-is
│   ├── ml_momentum.py             # Keep as-is
│   ├── news_sentiment.py          # Keep as-is
│   └── volatility_breakout.py     # Keep as-is
│
├── backtesting/
│   ├── __init__.py
│   ├── backtest_engine.py         # Rename: portfolio_backtester.py
│   ├── signal_injection.py        # Rename: signal_injection_engine.py
│   └── signal_tracer.py           # Rename: signal_flow_tracer.py
│
├── monitoring/
│   ├── __init__.py
│   ├── metrics.py                 # Rename: performance_metrics.py
│   ├── notifications.py           # Rename: email_notifier.py
│   └── dashboards.py              # Combines: dashboard_server.py, strategy_dashboard.py
│
├── infrastructure/
│   ├── __init__.py
│   ├── database.py                # Rename: strategy_database.py
│   └── security.py                # Keep as-is
│
└── main.py                        # Keep as entry point
```

**Result:** 26 files → 20 files (23% reduction)

---

### Option 2: Aggressive Consolidation

```
src/
├── trading_core.py                # Combines: trading_system.py, strategy_runner.py,
│                                  #           trade_executor.py, cash_manager.py,
│                                  #           stop_loss_manager.py
│
├── market_data.py                 # Combines: alpaca_data_fetcher.py, vix_data_fetcher.py,
│                                  #           data_validator.py
│
├── risk_management.py             # Combines: portfolio_risk_manager.py, correlation_filter.py,
│                                  #           execution_costs.py, regime_detector.py
│
├── strategies/
│   ├── __init__.py
│   ├── base.py
│   ├── allocator.py
│   └── [5 strategy files]
│
├── backtesting.py                 # Combines: portfolio_backtester.py, signal_injection_engine.py,
│                                  #           signal_flow_tracer.py
│
├── monitoring.py                  # Combines: performance_metrics.py, email_notifier.py,
│                                  #           dashboard_server.py, strategy_dashboard.py
│
├── infrastructure.py              # Combines: strategy_database.py, security.py
│
├── config.py
└── main.py
```

**Result:** 26 files → 15 files (42% reduction)

---

## Recommendation: Option 1 (Functional Grouping)

**Reasons:**
1. **Better organization** - Clear separation of concerns
2. **Easier maintenance** - Each module has single responsibility
3. **Better testing** - Can test each module independently
4. **Not too aggressive** - Doesn't create massive files
5. **Clear imports** - Easy to understand dependencies

**Implementation:**
- Keep strategies separate (they're already well-organized)
- Group related functionality (data, risk, monitoring)
- Maintain clear module boundaries
- Use `__init__.py` for clean imports

---

## Files That Should NOT Be Consolidated

1. **Strategy files** - Each strategy is independent
2. **main.py** - Entry point should be simple
3. **config.py** - Configuration should be separate
4. **security.py** - Security should be isolated

---

## Benefits of Consolidation

### Before (Current)
```python
from portfolio_risk_manager import PortfolioRiskManager
from correlation_filter import CorrelationFilter
from execution_costs import ExecutionCostModel
from regime_detector import RegimeDetector
```

### After (Consolidated)
```python
from risk.risk_management import (
    PortfolioRiskManager,
    CorrelationFilter,
    ExecutionCostModel,
    RegimeDetector
)
```

**Or even simpler:**
```python
from risk import RiskManager  # Single class with all functionality
```

---

## Implementation Priority

### Phase 1: Low-Risk Consolidations
1. ✅ Combine dashboards (dashboard_server.py + strategy_dashboard.py)
2. ✅ Combine data fetchers (alpaca + vix)
3. ✅ Rename files for clarity

### Phase 2: Medium-Risk Consolidations
4. Combine risk management files
5. Combine monitoring files
6. Organize into folders

### Phase 3: High-Risk Consolidations (Optional)
7. Combine core trading files
8. Refactor imports across codebase
9. Update all scripts

---

## Testing Strategy

After each consolidation:
1. Run all unit tests
2. Run integration tests
3. Test signal generation
4. Test execution pipeline
5. Run validation backtest

**No consolidation should break existing functionality.**

---

## Current Status

**NOT YET IMPLEMENTED** - This is the plan.

**Recommendation:** Implement Phase 1 consolidations only, as they are:
- Low risk
- High benefit
- Easy to test
- Won't break existing code

**Phase 2 and 3 can wait until after Phase 5 (live paper trading).**
