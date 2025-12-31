# Backtest Files Cleanup Analysis

**Generated:** December 30, 2025

## Current Backtest Files

### Active Files (Keep)

1. **`scripts/run_multi_strategy_backtest.py`** ✅ **KEEP**
   - **Purpose:** Comprehensive multi-strategy comparison backtest
   - **Features:** Tests all 5 strategies independently, generates comparison reports
   - **Status:** Active, primary backtest tool
   - **Output:** Comparative performance metrics, rankings, improvement recommendations

2. **`scripts/run_validation_backtest.py`** ✅ **KEEP**
   - **Purpose:** Phase 4 validation with signal injection and parameter sweeps
   - **Features:** Signal injection mode, parameter sweep, volatile period testing
   - **Status:** Active, validation tool
   - **Output:** Validation reports, signal flow traces

3. **`scripts/clean_data.py`** ✅ **KEEP**
   - **Purpose:** Data cleaning and imputation
   - **Features:** Forward-fill missing values, generate cleaning reports
   - **Status:** Active, data preparation tool
   - **Output:** `data/training_data_clean.csv`, cleaning reports

### Redundant Files (Remove)

4. **`scripts/fetch_backtest_data.py`** ❌ **REMOVE**
   - **Reason:** Uses yfinance which has dependency conflicts
   - **Status:** Non-functional due to Python package conflicts
   - **Replacement:** Data already collected via Alpha Vantage
   - **Action:** Delete - no longer needed

5. **`scripts/fetch_backtest_data_alternative.py`** ❌ **REMOVE**
   - **Reason:** Uses pandas_datareader which is blocked by Yahoo Finance
   - **Status:** Non-functional, Yahoo blocks requests
   - **Replacement:** Data already collected via Alpha Vantage
   - **Action:** Delete - no longer needed

6. **`scripts/run_backtest.py`** ❌ **REMOVE**
   - **Reason:** Superseded by `run_multi_strategy_backtest.py`
   - **Status:** Uses database trades (limited data), incomplete implementation
   - **Replacement:** `run_multi_strategy_backtest.py` provides full strategy simulation
   - **Action:** Delete - replaced by better implementation

7. **`scripts/run_full_backtest_simulation.py`** ❌ **REMOVE**
   - **Reason:** Single-strategy only, superseded by multi-strategy version
   - **Status:** Tests only one momentum strategy
   - **Replacement:** `run_multi_strategy_backtest.py` tests all 5 strategies
   - **Action:** Delete - replaced by comprehensive multi-strategy backtest

## Cleanup Actions

### Files to Delete

```bash
# Remove redundant backtest files
rm scripts/fetch_backtest_data.py
rm scripts/fetch_backtest_data_alternative.py
rm scripts/run_backtest.py
rm scripts/run_full_backtest_simulation.py
```

### Files to Keep

- `scripts/run_multi_strategy_backtest.py` - Primary backtest tool
- `scripts/run_validation_backtest.py` - Validation and testing
- `scripts/clean_data.py` - Data preparation

## Rationale

### Why Remove Data Fetchers?

1. **Dependency Conflicts:** `yfinance` has greenlet/gevent conflicts on Python 3.8
2. **API Blocks:** Yahoo Finance blocks pandas_datareader requests
3. **Data Already Available:** 15 years of data collected via Alpha Vantage
4. **No Future Need:** Data is static snapshot, no need to re-fetch

### Why Remove Old Backtest Scripts?

1. **Functionality:** Old scripts test single strategy or use limited database trades
2. **Completeness:** Multi-strategy backtest provides comprehensive comparison
3. **Maintenance:** Reduces code duplication and maintenance burden
4. **Clarity:** Single source of truth for backtesting

## Post-Cleanup Structure

### Backtest Workflow

```
1. Data Preparation
   └── scripts/clean_data.py
       └── Output: data/training_data_clean.csv

2. Strategy Backtesting
   └── scripts/run_multi_strategy_backtest.py
       └── Output: artifacts/backtest/multi_strategy_comparison.md
       └── Output: artifacts/backtest/strategy_comparison.png

3. Validation Testing
   └── scripts/run_validation_backtest.py
       └── Output: Validation reports and traces
```

### Makefile Commands

Update Makefile to reflect cleanup:

```makefile
# Remove old commands
# make fetch-backtest-data (REMOVE)
# make run-backtest (REMOVE)

# Keep active commands
make clean-data              # Clean and impute missing values
make backtest-multi-strategy # Run comprehensive multi-strategy backtest
make validate-backtest       # Run validation tests
```

## Impact Assessment

### Before Cleanup
- **6 backtest files** (4 redundant, 2 active)
- **Confusion:** Multiple ways to run backtests
- **Maintenance:** 4 files to maintain

### After Cleanup
- **3 backtest files** (all active)
- **Clarity:** Clear purpose for each file
- **Maintenance:** Only 3 files to maintain

### Risk Assessment
- **Low Risk:** Removed files are non-functional or superseded
- **No Data Loss:** All data preserved in `data/training_data_clean.csv`
- **Reversible:** Files tracked in git history if needed

## Validation Checklist

Before cleanup:
- ✅ Multi-strategy backtest tested and working
- ✅ Validation backtest tested and working
- ✅ Data cleaning tested and working
- ✅ All outputs verified
- ✅ Git history preserved

After cleanup:
- [ ] Verify all backtest commands work
- [ ] Update Makefile
- [ ] Update README documentation
- [ ] Commit cleanup changes

---

**Cleanup Status:** Ready to execute  
**Approval Required:** Yes  
**Reversible:** Yes (via git history)
