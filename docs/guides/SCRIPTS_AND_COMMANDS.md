# Scripts and Commands Reference

**Auto-generated documentation for all scripts and Make commands**

Last updated: 2025-12-24 01:34:13

---

## Make Commands

### Data Management
- **`make update-data`** - No description

### Testing
- **`make test`** - Testing
- **`make test-single`** - No description

### Execution
- **`make run`** - Main execution

### Database

### Utilities
- **`make clean`** - Cleanup

---

## Scripts Directory

### Data Scripts
**`scripts/fetch_historical_data.py`**
- Fetch Extended Historical Data

**`scripts/fetch_historical_data_yfinance.py`**
- Fetch Extended Historical Data using yfinance (FREE)

**`scripts/setup_database.py`**
- Initialize trading database for CI/CD and fresh installations

**`scripts/sync_database.py`**
- Database Sync Script

**`scripts/update_data.py`**
- Quick Data Update Script

### Phase 5 Scripts
**`scripts/fresh_start_phase5.py`**
- Phase 5 Fresh Start Script

**`scripts/generate_phase5_report.py`**
- Generate Phase 5 Completion Report

**`scripts/phase5_weekly_review.py`**
- Phase 5 Weekly Review Script

### Testing Scripts
**`scripts/debug_single_signal.py`**
- Deep-dive debugging: Trace a single signal through the entire execution pipeline

**`scripts/run_simple_backtest.py`**
- Simple backtest runner - focuses on getting trades to execute

**`scripts/run_validation_backtest.py`**
- Phase 4 Validation Backtest Runner

**`scripts/run_walkforward_backtest.py`**
- Walk-Forward Backtest Runner

**`scripts/stress_test_periods.py`**
- Stress Test Framework

**`scripts/test_backtest_minimal.py`**
- Minimal backtest test to trace signal flow

**`scripts/test_single_strategy.py`**
- Test individual strategies to verify signal generation

### Other Scripts
**`scripts/add_missing_indicators.py`**
- Add missing technical indicators to training data

**`scripts/download_github_artifacts.py`**
- Download all GitHub Actions artifacts for Phase 5

**`scripts/generate_docs.py`**
- Auto-generate SCRIPTS_AND_COMMANDS.md documentation

**`scripts/generate_validation_plots.py`**
- Validation Plot Generation

**`scripts/analyze_signals.py`**
- Multi-Strategy Analysis - Check all 5 strategies for signals

**`scripts/view_performance.py`**
- View Multi-Strategy Performance Dashboard

---

## Auto-Discovery System

This documentation auto-updates by scanning:
1. **Makefile** - Extracts all targets and descriptions
2. **scripts/** - Lists all .py files with docstrings
3. **src/** - Documents main execution files

To regenerate this documentation:
```bash
python3 scripts/generate_docs.py
```

---

## Adding New Scripts

When adding a new script:
1. Add a docstring at the top explaining what it does
2. Run `python3 scripts/generate_docs.py` to update this file
3. Commit both the script and updated documentation

Example docstring format:
```python
#!/usr/bin/env python3
"""
Brief description of what this script does

Longer explanation if needed.
Usage: python3 scripts/my_script.py [args]
"""
```

---

## Quick Reference

**Daily execution (Phase 5):**
```bash
export ENABLE_BROKER_RECONCILIATION=true
python3 src/execution_engine.py
```

**Update market data:**
```bash
make update-data
```

**Initialize database:**
```bash
python3 scripts/setup_database.py
```

**Weekly review:**
```bash
python3 scripts/phase5_weekly_review.py
```

**Generate final report:**
```bash
python3 scripts/generate_phase5_report.py
```

**Download CI/CD artifacts:**
```bash
python3 scripts/download_github_artifacts.py
```

**Regenerate this documentation:**
```bash
python3 scripts/generate_docs.py
```
