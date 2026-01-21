# Project Context & Conversation History

**Project:** Investor Mimic Bot (Multi-Strategy Quantitative Trading System)  
**Owner:** Shreyas Chickerur  
**Last Updated:** January 16, 2026  
**Status:** Production (Paper Trading via GitHub Actions)

---

## Project Overview

A multi-strategy quantitative trading system that executes daily at 4:15 PM ET via GitHub Actions. The system combines 5 independent trading strategies with portfolio-level risk management, regime detection, and correlation filtering.

**Key Stats:**
- **Universe:** 36 large-cap US stocks
- **Capital:** ~$100k (paper trading)
- **Strategies:** 5 (2 currently active)
- **Execution:** Daily at 4:15 PM ET (after market close)
- **Platform:** Alpaca (paper trading mode)

---

## System Architecture Summary

### Execution Flow
1. **Pre-flight checks:** Kill switches, drawdown stops, data quality, broker reconciliation
2. **Regime detection:** Volatility/trend regime, adjust heat limits
3. **Signal generation:** 5 independent strategies generate signals
4. **Signal filtering:** Regime filter → Correlation filter → Risk filter
5. **Position sizing:** ATR-based with correlation/regime adjustments
6. **Execution:** Submit orders to Alpaca, set stop losses
7. **Post-execution:** Verify fills, calculate P&L, generate artifacts, send email

### 5 Trading Strategies
1. **RSI Mean Reversion** ✅ Active - Buy RSI<35 with positive slope, exit at RSI>50 or VWAP
2. **ML Momentum** ⚠️ Not generating signals - Logistic regression classifier
3. **News Sentiment** ❌ Disabled - No API key
4. **MA Crossover** ⚠️ No signals - Golden cross (50/200 MA)
5. **Volatility Breakout** ⚠️ No signals - Bollinger Band breakouts

### Risk Management (5 Layers)
1. Portfolio heat limits (20-40% based on regime)
2. Daily loss circuit breaker (-2%)
3. Drawdown stop manager (8% halt, 10% panic)
4. Catastrophe stop losses (3x ATR)
5. Correlation filter (reject if >0.7, attenuate if >0.5)

---

## Current System State (Jan 16, 2026)

### Portfolio
- **Value:** $100,664.56
- **Cash:** $96,876.52
- **Positions:** 2 (CVX: 12 shares, TMO: 3 shares)
- **Exposure:** $3,824.97 (3.8% heat)
- **Regime:** Low volatility (40% heat limit)

### Recent Activity
- **Jan 13:** Bought AAPL (7 shares) + CSCO (26 shares) via RSI strategy
- **Jan 14-15:** No new trades (same signals rejected as duplicates)
- **Reconciliation:** PASS (all checks passing)

### Known Issues
1. **ML Momentum:** Generating 0 signals (needs investigation)
2. **Strategy diversity:** Only 2/5 strategies active
3. **Signal frequency:** Low (only RSI finding opportunities)

---

## Key Design Decisions & Rationale

### 1. End-of-Day Execution (4:15 PM ET)
**Decision:** Generate signals after market close, execute next day at open  
**Rationale:** Eliminates lookahead bias, realistic execution constraints  
**Trade-off:** Overnight gap risk (mitigated by execution cost model)

### 2. Equal Capital Allocation
**Decision:** $20k per strategy (equal weighting)  
**Rationale:** Insufficient data for dynamic allocation yet  
**Future:** Implement Sharpe-based weighting after 60+ days

### 3. Correlation Filter (60-day window)
**Decision:** Reject signals with >0.7 correlation to existing positions  
**Rationale:** Reduces tail risk, prevents over-concentration  
**Expert feedback:** Add 20-day override for regime shifts (not yet implemented)

### 4. Regime-Adaptive Heat Limits
**Decision:** 40% (low vol), 30% (normal), 20% (high vol)  
**Rationale:** Increase exposure in calm markets, reduce in volatile markets  
**Expert feedback:** This is ahead of most retail systems

### 5. Mandatory Broker Reconciliation
**Decision:** Hard gate - block trading if DB/broker mismatch  
**Rationale:** Prevent phantom positions, ensure data integrity  
**Implementation:** Checks before every trading session

### 6. ATR-Based Position Sizing
**Decision:** 1% portfolio risk per position  
**Rationale:** Industry standard, controls risk per trade  
**Formula:** `shares = (portfolio * 0.01) / ATR`

### 7. 3x ATR Catastrophe Stops
**Decision:** Set stop loss 3 ATR below entry  
**Rationale:** Tail protection without getting stopped out by noise  
**Expert feedback:** 2-3x ATR is appropriate for daily timeframe

---

## Expert Feedback & Assessments

### ChatGPT Quant Expert Assessment (After Phase 1-3)
**Rating:** "Well-designed junior quant system with professional risk architecture"

**Strengths Identified:**
- Execution timing eliminates lookahead bias
- RSI strategy is "legit" (conditional reversion, multi-exit)
- Volatility-based position sizing is industry standard
- Portfolio-level risk controls (not just per-strategy)
- Correlation filter ahead of most retail systems
- ML strategy correctly uses classifier (not regressor)

**Weaknesses Identified:**
- Incomplete integration (now fixed)
- Lack of validated backtests (in progress)
- Correlation filter rigidity during regime shifts
- Static execution costs (should scale by ATR/volume)

**Realistic Performance Expectations:**
- Sharpe: 0.8-1.3 (>2.0 = overfitting)
- Max drawdown: 10-20% (<5% = unrealistic)
- Annual return: 10-25% (>50% = unlikely)
- Win rate: 45-55% (>65% = suspicious)

**Next Steps Recommended:**
1. Walk-forward portfolio backtesting (mandatory)
2. Regime detection (implemented)
3. Dynamic strategy weighting (not yet implemented)
4. Stop losses (implemented - 3x ATR)

---

## Development History & Phases

### Phase 1: Core Strategy Implementation
- Implemented 5 strategies with independent tracking
- Database schema for trades, signals, positions
- Basic execution engine

### Phase 2: Risk Management
- Portfolio-level heat limits
- Daily loss circuit breaker
- Correlation filter
- ATR-based position sizing

### Phase 3: Production Readiness
- Broker reconciliation (mandatory gate)
- Kill switches
- Drawdown stop manager
- Data quality checks
- Signal funnel tracking
- Email notifications

### Phase 4: Regime Detection
- Volatility regime detection (low/normal/high)
- Trend regime detection (strong/weak/choppy)
- Adaptive heat limits and position sizing
- Strategy enable/disable based on regime

### Phase 5: Validation & Monitoring (Current)
- GitHub Actions automation (daily at 4:15 PM ET)
- Artifact generation (JSON, funnel, rejections)
- Performance tracking
- Paper trading validation

### Future Phases (Planned)
- Phase 6: Backtest validation (walk-forward)
- Phase 7: Dynamic allocation (Sharpe-based)
- Phase 8: Universe expansion (36 → 100 stocks)
- Phase 9: Live trading transition (small capital)

---

## File Organization & Structure

### Root Directory (Minimal)
- `.env` - Credentials (gitignored)
- `requirements.txt` - Python dependencies
- `README.md` - Project overview
- `.gitignore` - Ignore patterns
- `Makefile` - Command shortcuts
- `trading.db` - SQLite database

### Source Code (`src/`)
- `main.py` - Entry point
- `execution_engine.py` - Main orchestrator
- `database.py` - Database interface
- `strategies/` - 5 strategy implementations
- Risk management modules (15+ files)
- Utilities (email, artifacts, logging)

### Documentation (`docs/`)
- `guides/` - How-to guides, operational procedures
- `reference/` - Technical specs, architecture
- `reports/` - Status reports, validation results
- `github-actions/` - CI/CD documentation

### Scripts (`scripts/`)
- `automated_morning_run.sh` - Main execution script
- `update_data.py` - Fetch market data
- `generate_*.py` - Report generation
- `validate_*.py` - Validation scripts

### Tests (`tests/`)
- Unit tests for strategies
- Integration tests for execution flow
- Manual test scripts

### Artifacts (`artifacts/`)
- `json/` - Daily snapshots
- `funnel/` - Signal funnel tracking
- `data_quality/` - Data quality reports
- `drawdown/` - Drawdown events
- `health/` - Strategy health scores

### Data (`data/`)
- `training_data.csv` - Historical OHLCV + indicators
- Updated daily via Alpha Vantage API

---

## User Preferences & Guidelines

### File Organization
- **Root:** Only essential config files
- **Documentation:** All markdown in `docs/` subfolders
- **Tests:** All tests in `tests/`
- **Scripts:** All scripts in `scripts/`
- **Source:** All code in `src/`
- **Never:** Create loose files in root

### Documentation Style
- **Minimal & focused:** Only create docs that provide holistic value
- **No clutter:** Avoid excessive markdown files
- **Organized:** Use `docs/` subfolders (guides, reference, reports)
- **Purpose:** Features, instructions, system explanations

### Code Style
- **Modular:** Keep components separate, don't merge into single files
- **No comments:** Don't add/delete comments unless asked
- **Consolidate:** Merge similar functionality into one file
- **Web dashboards:** Prefer over CLI tools for monitoring

### Automation
- **Makefiles:** Use for easy command execution
- **GitHub Actions:** Daily automation at 4:15 PM ET
- **Email notifications:** Daily digest with trades and performance

---

## Common Questions & Answers

### Q: Why no trades on some days?
**A:** This is normal. The system waits for quality setups rather than forcing trades. Reasons:
- No stocks meet strategy criteria
- Signals rejected by correlation filter
- Portfolio heat limits reached
- Duplicate signals (already holding position)

### Q: Why is ML Momentum generating 0 signals?
**A:** Needs investigation. Possible causes:
- Model needs retraining with recent data
- Feature engineering issues
- Prediction threshold too high (>0.6)
- Market conditions don't match training data

### Q: How is lookahead bias prevented?
**A:** Strict temporal separation:
- Day T (4:15 PM): Generate signals using Day T close prices
- Day T+1 (open): Execute orders at market open
- No same-day execution, no intraday data

### Q: What's the difference between paper and live trading?
**A:** Paper trading:
- Simulates real trading with live market data
- No real money at risk
- Full order management (fills, rejections)
- Same code as live trading
- Used for validation before going live

### Q: How do I check if the workflow is running?
**A:** 
```bash
gh run list --workflow=daily_trading.yml --limit 5
```
Or check GitHub Actions tab in repository.

### Q: Where are the daily results?
**A:**
- `artifacts/json/YYYY-MM-DD.json` - Full snapshot
- `artifacts/funnel/` - Signal funnel tracking
- Email digest (sent daily)
- GitHub Actions summary

### Q: How do I manually run the workflow?
**A:**
```bash
# Via GitHub Actions (workflow_dispatch)
gh workflow run daily_trading.yml

# Or locally
./scripts/automated_morning_run.sh
```

---

## Technical Debt & Known Issues

### High Priority
1. **ML Momentum not generating signals** - Investigate model, features, threshold
2. **Low strategy diversity** - Only 2/5 strategies active
3. **No backtesting validation** - Need walk-forward backtest

### Medium Priority
4. **Static execution costs** - Should scale by ATR and volume
5. **Correlation filter rigidity** - Add 20-day override for regime shifts
6. **No dynamic allocation** - Still using equal weighting
7. **Limited universe** - Only 36 stocks

### Low Priority
8. **No short selling** - Long-only system
9. **No intraday execution** - Next-day open only
10. **No options overlay** - No tail protection via puts

---

## Environment Variables

```bash
# Alpaca API (Required)
ALPACA_API_KEY=your_key
ALPACA_SECRET_KEY=your_secret
ALPACA_PAPER=true
ALPACA_LIVE_ENABLED=false

# Alpha Vantage (Required for data updates)
ALPHA_VANTAGE_API_KEY=your_key

# Email Notifications (Optional)
EMAIL_USERNAME=your_email
EMAIL_PASSWORD=your_app_password
EMAIL_TO=recipient_email

# System Configuration
DRY_RUN=false
TRADING_DISABLED=false
DATA_MAX_AGE_HOURS=72
ENABLE_BROKER_RECONCILIATION=true
SIGNAL_INJECTION=false
```

---

## Database Schema (Key Tables)

### `strategies`
- `id`, `name`, `description`, `capital_allocation`, `initial_capital`, `status`

### `signals`
- `id`, `strategy_id`, `symbol`, `signal_type`, `confidence`, `reasoning`, `asof_date`, `generated_at`, `terminal_state`, `terminal_reason`

### `trades`
- `id`, `strategy_id`, `signal_id`, `symbol`, `action`, `shares`, `requested_price`, `exec_price`, `slippage_cost`, `commission_cost`, `notional`, `order_id`, `executed_at`, `pnl`

### `positions`
- `id`, `strategy_id`, `symbol`, `shares`, `avg_price`, `current_price`, `market_value`, `unrealized_pnl`, `last_updated`

### `broker_state`
- `id`, `snapshot_date`, `snapshot_type`, `cash`, `portfolio_value`, `buying_power`, `positions_json`, `reconciliation_status`, `discrepancies_json`, `run_id`

---

## Key Metrics & Thresholds

### Risk Limits
- **Portfolio heat:** 20-40% (regime-dependent)
- **Daily loss:** -2% (circuit breaker)
- **Drawdown halt:** -8%
- **Drawdown panic:** -10%
- **Correlation threshold:** 0.7 (reject), 0.5 (attenuate)
- **Stop loss:** 3x ATR below entry

### Position Sizing
- **Base risk:** 1% portfolio per position
- **Max position:** 10% of strategy capital
- **Regime multiplier:** 0.8x to 1.2x
- **Correlation multiplier:** 0.25x to 1.0x

### Data Quality
- **Max staleness:** 72 hours
- **Max NaN:** 10% per symbol
- **Outlier threshold:** 5 std deviations
- **Min volume:** 10% of 20-day average

### Strategy Parameters
- **RSI threshold:** 35 (entry), 50 (exit)
- **RSI hold:** 20 days max
- **ML confidence:** 0.6 (entry/exit)
- **MA periods:** 50, 200 (golden cross)
- **Bollinger Bands:** 20-period, 2 std dev

---

## Useful Commands

### Run Trading System
```bash
make run                    # Run locally
make test                   # Run tests
make validate              # Validate system
```

### Check Status
```bash
gh run list --workflow=daily_trading.yml
gh run view <run_id>
sqlite3 trading.db "SELECT * FROM broker_state ORDER BY created_at DESC LIMIT 1;"
```

### Data Management
```bash
python scripts/update_data.py          # Update market data
python scripts/setup_database.py       # Initialize database
```

### Generate Reports
```bash
python scripts/generate_strategy_performance.py --days 30
python scripts/generate_strategy_chart.py --days 7
python scripts/generate_daily_email.py
```

---

## Recent Conversations & Context

### Jan 16, 2026 - Investigation: Why No Trades on Jan 14-15?

**User Question:** "Can you check over the past 3 days how many stocks were bought or sold?"

**Findings:**
- **Jan 13:** 4 trades (2 AAPL, 2 CSCO) - duplicates from two runs
- **Jan 14-15:** 0 new trades
- **Reason:** Same signals (AAPL, CSCO) generated but rejected as duplicates
- **Workflow status:** Running successfully via GitHub Actions
- **System health:** All checks passing, 3.8% heat (well below 40% limit)

**User Request:** "Why were there no signals over the past 2 days?"

**Investigation:**
1. Checked funnel artifacts - signals rejected at risk stage
2. Reviewed portfolio positions - CVX, TMO held
3. Analyzed strategy health - no throttling active
4. **Conclusion:** System working correctly, no new opportunities found

**User Request:** "Can you explain IN DEPTH how the algorithm works?"

**Response:** Created comprehensive documentation at `docs/reference/ALGORITHM_DEEP_DIVE.md` covering:
- System architecture (6 phases)
- All 5 strategies (detailed)
- Risk management (5 layers)
- Regime detection
- Position sizing algorithm
- Execution timing
- Data pipeline
- Known limitations
- Realistic expectations
- Recommendations

---

## Next Steps & Roadmap

### Immediate (This Week)
- [ ] Investigate ML Momentum strategy (why 0 signals?)
- [ ] Monitor signal frequency (alert if strategy silent >5 days)
- [ ] Review strategy health scoring

### Short-Term (Next 2 Weeks)
- [ ] Add signal frequency monitoring
- [ ] Consider adding new strategies (pairs trading, sector rotation)
- [ ] Implement dynamic allocation (Sharpe-based)

### Medium-Term (Next Month)
- [ ] Run walk-forward backtest (2010-2024)
- [ ] Expand universe (36 → 50-100 stocks)
- [ ] Add 20-day correlation override for regime shifts

### Long-Term (Next Quarter)
- [ ] Transition to intraday execution
- [ ] Add options overlay (protective puts)
- [ ] Begin live trading with small capital ($10k)

---

## References & Documentation

### Key Documents
- `README.md` - Project overview and quick start
- `docs/reference/ALGORITHM_DEEP_DIVE.md` - Comprehensive algorithm explanation
- `docs/guides/MORNING_RUN_GUIDE.md` - Daily execution guide
- `docs/guides/AUTOMATION_GUIDE.md` - GitHub Actions setup
- `docs/reports/PRODUCTION_VALIDATION_REPORT.md` - Validation results

### External Resources
- Alpaca API: https://alpaca.markets/docs/
- Alpha Vantage API: https://www.alphavantage.co/documentation/

---

**Last Updated:** January 16, 2026  
**Next Review:** February 16, 2026

---

## Notes for Future AI Assistants

When helping with this project:

1. **Always check this file first** for context and recent decisions
2. **Respect the modular architecture** - don't merge files
3. **Follow file organization rules** - docs in docs/, tests in tests/, etc.
4. **Check GitHub Actions logs** for automation status
5. **Review artifacts/** for daily execution data
6. **Consult ALGORITHM_DEEP_DIVE.md** for technical details
7. **Remember:** Not every day will have trades (this is normal)
8. **Be conservative** with performance expectations (Sharpe 0.8-1.3, not 2.0+)
9. **Validate before changing** - this is a production system
10. **Document decisions** - update this file with major changes

**Common Pitfalls to Avoid:**
- Don't assume lack of trades = system failure
- Don't optimize for better backtest results (overfitting)
- Don't add complexity without validation
- Don't merge modular components
- Don't create loose files in root directory
- Don't tune parameters to improve Sharpe (data leakage)

**When in Doubt:**
- Check the code in `src/`
- Review recent artifacts in `artifacts/json/`
- Check GitHub Actions logs
- Consult this context file
- Ask the user for clarification
