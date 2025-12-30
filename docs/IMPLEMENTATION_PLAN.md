# Implementation Plan - Critical Improvements
**Based on Claude UI Review Feedback**  
**Created:** December 29, 2025  
**Approach:** Incremental implementation with testing at each phase

---

## 🎯 Philosophy

**Core Principles:**
1. **Incremental** - One feature at a time, fully tested before moving on
2. **Branch-based** - Each feature gets its own branch, no direct pushes to main
3. **Test-first** - Write tests before implementation where possible
4. **Validate** - Run full system validation after each merge
5. **Document** - Update docs as we go, not after

**Development Workflow:**
```
1. Create feature branch
2. Implement feature
3. Write/update tests
4. Run test suite
5. Manual validation
6. Update documentation
7. Code review (self-review checklist)
8. Merge to main
9. Full system test
10. Monitor for 24-48 hours before next feature
```

---

## 📋 Implementation Phases

### **Phase 1: Critical Safety Features (Week 1-2)**
*Priority: CRITICAL - These prevent catastrophic losses*

#### 1.1 Catastrophe Stop Losses
**Branch:** `feature/catastrophe-stops`  
**Estimated Time:** 4-6 hours  
**Risk Level:** Low (pure addition, no changes to existing logic)

**Implementation Steps:**
1. Add stop loss configuration to execution engine
2. Implement `check_catastrophe_stops()` function
3. Integrate into position monitoring loop
4. Add database column for stop loss prices
5. Write unit tests for stop loss logic
6. Write integration test for stop loss execution
7. Add logging for stop loss triggers
8. Update documentation

**Testing Checklist:**
- [ ] Unit test: Stop triggers at exactly 3x ATR below entry
- [ ] Unit test: Stop doesn't trigger at 2.9x ATR
- [ ] Integration test: Stop executes actual sell order
- [ ] Integration test: Stop updates database correctly
- [ ] Manual test: Run with mock position at stop loss level
- [ ] Validation: Check logs show stop loss evaluation

**Files to Modify:**
- `src/execution_engine.py` - Add stop loss checking
- `src/database.py` - Add stop_loss_price column to positions table
- `tests/test_execution_engine.py` - Add stop loss tests
- `README.md` - Document stop loss feature

**Acceptance Criteria:**
- Stop loss triggers correctly in tests
- Database tracks stop loss prices
- Logs show stop loss evaluations
- No impact on existing functionality

---

#### 1.2 Data Quality Validation
**Branch:** `feature/data-quality-validation`  
**Estimated Time:** 6-8 hours  
**Risk Level:** Medium (could reject valid data if too strict)

**Implementation Steps:**
1. Create `src/data_validator.py` module
2. Implement validation checks:
   - Missing days detection
   - Duplicate timestamps
   - Price jump detection (>20%)
   - Zero volume detection
   - OHLC consistency (close within high/low)
3. Integrate into `update_data.py`
4. Add validation to market data queries
5. Create custom `DataQualityError` exception
6. Write comprehensive tests
7. Add validation reporting to logs
8. Update documentation

**Testing Checklist:**
- [ ] Unit test: Detects missing days (gap > 3 days)
- [ ] Unit test: Detects duplicate timestamps
- [ ] Unit test: Detects price jumps > 20%
- [ ] Unit test: Detects zero volume
- [ ] Unit test: Detects close outside high/low
- [ ] Integration test: Rejects bad data from Alpha Vantage
- [ ] Integration test: Accepts clean data
- [ ] Manual test: Run with known bad data file
- [ ] Validation: Check error messages are clear

**Files to Create:**
- `src/data_validator.py` - New validation module
- `tests/test_data_validator.py` - Validation tests
- `tests/fixtures/bad_data.csv` - Test data with errors

**Files to Modify:**
- `scripts/update_data.py` - Add validation calls
- `src/execution_engine.py` - Validate data before use
- `README.md` - Document data quality checks

**Acceptance Criteria:**
- All validation checks work correctly
- Bad data is rejected with clear error messages
- Good data passes validation
- System logs validation results
- No false positives on clean data

---

#### 1.3 Critical Alerting System
**Branch:** `feature/critical-alerts`  
**Estimated Time:** 6-8 hours  
**Risk Level:** Low (monitoring only, no trading logic changes)

**Implementation Steps:**
1. Install Twilio for SMS alerts
2. Create `src/alerting.py` module
3. Implement alert checks:
   - Drawdown > 15%
   - No trades in 7 days
   - Broker reconciliation failure
   - Database integrity issues
4. Add email + SMS notification
5. Create alert configuration in `.env`
6. Write tests for alert triggers
7. Add alert history to database
8. Update documentation

**Testing Checklist:**
- [ ] Unit test: Drawdown alert triggers at 15.1%
- [ ] Unit test: No-trade alert triggers after 7 days
- [ ] Unit test: Reconciliation failure alert triggers
- [ ] Integration test: Email sends correctly
- [ ] Integration test: SMS sends correctly (if configured)
- [ ] Manual test: Trigger each alert type
- [ ] Validation: Check alert history in database

**Files to Create:**
- `src/alerting.py` - New alerting module
- `tests/test_alerting.py` - Alert tests

**Files to Modify:**
- `src/execution_engine.py` - Add alert checks
- `src/broker_reconciler.py` - Trigger alerts on failure
- `requirements.txt` - Add twilio
- `.env.example` - Add alert configuration
- `README.md` - Document alerting system

**Acceptance Criteria:**
- All alert conditions trigger correctly
- Emails send successfully
- SMS sends successfully (if configured)
- Alert history tracked in database
- No false alarms during normal operation

---

### **Phase 2: Risk Management Enhancements (Week 3-4)**
*Priority: HIGH - Improves risk controls*

#### 2.1 Adaptive Correlation Filter
**Branch:** `feature/adaptive-correlation`  
**Estimated Time:** 4-6 hours  
**Risk Level:** Medium (changes existing filter logic)

**Implementation Steps:**
1. Modify correlation filter to accept window parameter
2. Add `adaptive_correlation_window()` function
3. Integrate with regime detector
4. Update correlation calculation logic
5. Write tests for different regimes
6. Add logging for window selection
7. Update documentation

**Testing Checklist:**
- [ ] Unit test: Returns 60 days in NORMAL regime
- [ ] Unit test: Returns 40 days in HIGH_VOL regime
- [ ] Unit test: Returns 20 days in CRISIS regime
- [ ] Integration test: Filter uses correct window
- [ ] Backtest: Compare old vs new filter performance
- [ ] Manual test: Run with different regimes
- [ ] Validation: Check correlation calculations

**Files to Modify:**
- `src/execution_engine.py` - Update correlation filter
- `src/regime_detector.py` - Add window selection
- `tests/test_execution_engine.py` - Add correlation tests
- `README.md` - Document adaptive correlation

**Acceptance Criteria:**
- Correlation window adapts to regime
- Filter still rejects correlated positions
- No regression in existing functionality
- Logs show window selection reasoning

---

#### 2.2 Regime-Dependent Heat Limits
**Branch:** `feature/regime-heat-limits`  
**Estimated Time:** 4-6 hours  
**Risk Level:** Medium (changes position sizing)

**Implementation Steps:**
1. Add `REGIME_HEAT_LIMITS` configuration
2. Modify heat limit calculation
3. Add drawdown-based reduction
4. Update position sizing logic
5. Write tests for different scenarios
6. Add logging for heat limit adjustments
7. Update documentation

**Testing Checklist:**
- [ ] Unit test: 40% heat in NORMAL regime
- [ ] Unit test: 25% heat in HIGH_VOL regime
- [ ] Unit test: 15% heat in CRISIS regime
- [ ] Unit test: 50% reduction at 10% drawdown
- [ ] Integration test: Position sizing respects limits
- [ ] Manual test: Run with different regimes
- [ ] Validation: Check heat calculations

**Files to Modify:**
- `src/execution_engine.py` - Update heat limits
- `src/regime_detector.py` - Add heat limit logic
- `tests/test_execution_engine.py` - Add heat tests
- `README.md` - Document regime-dependent limits

**Acceptance Criteria:**
- Heat limits adjust correctly by regime
- Drawdown reduction works
- Position sizing respects new limits
- Logs show limit adjustments

---

#### 2.3 Per-Strategy Risk Limits
**Branch:** `feature/strategy-risk-limits`  
**Estimated Time:** 6-8 hours  
**Risk Level:** Medium (adds new rejection criteria)

**Implementation Steps:**
1. Add strategy-level configuration
2. Implement `MAX_STRATEGY_ALLOCATION` check
3. Implement `MAX_STRATEGY_POSITIONS` check
4. Add strategy exposure tracking
5. Update signal rejection logic
6. Write comprehensive tests
7. Add logging for strategy limits
8. Update documentation

**Testing Checklist:**
- [ ] Unit test: Rejects when strategy > 35% of portfolio
- [ ] Unit test: Rejects when strategy has 6 positions
- [ ] Unit test: Allows when under limits
- [ ] Integration test: Limits enforced during execution
- [ ] Manual test: Run with strategy at limit
- [ ] Validation: Check strategy exposure calculations

**Files to Modify:**
- `src/execution_engine.py` - Add strategy limits
- `src/database.py` - Add strategy exposure queries
- `tests/test_execution_engine.py` - Add limit tests
- `README.md` - Document strategy limits

**Acceptance Criteria:**
- Strategy allocation limited to 35%
- Strategy positions limited to 5
- Limits enforced correctly
- Logs show limit checks

---

#### 2.4 Time-Based Exits
**Branch:** `feature/time-based-exits`  
**Estimated Time:** 4-6 hours  
**Risk Level:** Low (adds new exit criteria)

**Implementation Steps:**
1. Add `MAX_HOLD_DAYS` configuration per strategy
2. Implement `check_time_stop()` function
3. Integrate into position monitoring
4. Add time-based exit tracking
5. Write tests for each strategy
6. Add logging for time exits
7. Update documentation

**Testing Checklist:**
- [ ] Unit test: RSI exits after 30 days
- [ ] Unit test: ML Momentum exits after 45 days
- [ ] Unit test: News Sentiment exits after 10 days
- [ ] Integration test: Time exits execute correctly
- [ ] Manual test: Run with old positions
- [ ] Validation: Check exit timing

**Files to Modify:**
- `src/execution_engine.py` - Add time-based exits
- `src/database.py` - Track hold duration
- `tests/test_execution_engine.py` - Add time exit tests
- `README.md` - Document time-based exits

**Acceptance Criteria:**
- Each strategy has appropriate max hold period
- Time exits trigger correctly
- Database tracks hold duration
- Logs show time exit reasoning

---

### **Phase 3: Data & Performance (Week 5-6)**
*Priority: HIGH - Foundation for backtesting*

#### 3.1 Database Optimization
**Branch:** `feature/database-optimization`  
**Estimated Time:** 4-6 hours  
**Risk Level:** Low (performance improvement only)

**Implementation Steps:**
1. Add indexes to database schema
2. Enable WAL mode for SQLite
3. Implement connection pooling
4. Add batch insert operations
5. Write performance benchmarks
6. Test query performance
7. Update documentation

**Testing Checklist:**
- [ ] Benchmark: Query performance before/after
- [ ] Unit test: Batch inserts work correctly
- [ ] Integration test: No data corruption
- [ ] Manual test: Run full execution cycle
- [ ] Validation: Check query times in logs

**Files to Modify:**
- `src/database.py` - Add indexes and optimizations
- `scripts/setup_database.py` - Add indexes to schema
- `tests/test_database.py` - Add performance tests
- `README.md` - Document optimizations

**Acceptance Criteria:**
- Indexes created successfully
- Query performance improved
- No data corruption
- Batch operations work correctly

---

#### 3.2 Market Data Caching
**Branch:** `feature/market-data-caching`  
**Estimated Time:** 4-6 hours  
**Risk Level:** Low (performance improvement only)

**Implementation Steps:**
1. Add LRU cache to market data queries
2. Implement cache invalidation logic
3. Add cache statistics tracking
4. Write tests for cache behavior
5. Add cache clearing to daily workflow
6. Update documentation

**Testing Checklist:**
- [ ] Unit test: Cache returns same data
- [ ] Unit test: Cache clears correctly
- [ ] Integration test: Reduces API calls
- [ ] Manual test: Run with cache enabled
- [ ] Validation: Check cache hit rate

**Files to Modify:**
- `scripts/update_data.py` - Add caching
- `src/execution_engine.py` - Use cached data
- `tests/test_update_data.py` - Add cache tests
- `README.md` - Document caching

**Acceptance Criteria:**
- Cache reduces API calls
- Cache invalidation works
- No stale data issues
- Cache statistics tracked

---

#### 3.3 Enhanced Testing Suite
**Branch:** `feature/enhanced-testing`  
**Estimated Time:** 8-12 hours  
**Risk Level:** Low (testing only)

**Implementation Steps:**
1. Write critical path tests (position sizing, stops, filters)
2. Add integration tests for full execution cycle
3. Add property-based tests with hypothesis
4. Create test fixtures for common scenarios
5. Add performance benchmarks
6. Increase coverage to 60%+
7. Update documentation

**Testing Checklist:**
- [ ] All critical paths have tests
- [ ] Integration tests pass
- [ ] Property-based tests pass
- [ ] Coverage report shows 60%+
- [ ] All tests run in CI
- [ ] Documentation updated

**Files to Create:**
- `tests/test_critical_paths.py` - Critical path tests
- `tests/test_integration.py` - Integration tests
- `tests/fixtures/` - Test fixtures directory

**Files to Modify:**
- All test files - Increase coverage
- `.github/workflows/` - Add test workflow
- `README.md` - Document testing approach

**Acceptance Criteria:**
- Test coverage > 60%
- All critical paths tested
- Integration tests pass
- CI runs all tests

---

### **Phase 4: Walk-Forward Backtesting (Week 7-10)**
*Priority: CRITICAL - Validates strategy performance*

#### 4.1 Backtesting Infrastructure
**Branch:** `feature/backtest-infrastructure`  
**Estimated Time:** 12-16 hours  
**Risk Level:** High (complex, new system)

**Implementation Steps:**
1. Install vectorbt or backtrader
2. Create `src/backtester.py` module
3. Implement walk-forward framework:
   - 2-year training window
   - 6-month test window
   - 1-month step size
4. Add portfolio-level backtesting
5. Implement all risk controls in backtest
6. Add execution cost modeling
7. Write tests for backtest logic
8. Update documentation

**Testing Checklist:**
- [ ] Unit test: Window sliding works correctly
- [ ] Unit test: Train/test split is correct
- [ ] Integration test: Backtest runs end-to-end
- [ ] Validation: No lookahead bias
- [ ] Validation: All filters applied
- [ ] Validation: Costs included
- [ ] Manual test: Run on known data

**Files to Create:**
- `src/backtester.py` - Backtesting engine
- `scripts/run_backtest.py` - Backtest runner
- `tests/test_backtester.py` - Backtest tests

**Files to Modify:**
- `requirements.txt` - Add backtesting libraries
- `Makefile` - Add backtest command
- `README.md` - Document backtesting

**Acceptance Criteria:**
- Walk-forward framework works
- No lookahead bias
- All risk controls applied
- Execution costs included
- Results reproducible

---

#### 4.2 Survivorship Bias Fix
**Branch:** `feature/survivorship-bias-fix`  
**Estimated Time:** 8-12 hours  
**Risk Level:** Medium (requires historical data)

**Implementation Steps:**
1. Obtain S&P 500 historical constituents data
2. Create point-in-time universe function
3. Update backtesting to use historical universe
4. Add universe tracking to database
5. Write tests for universe selection
6. Compare results with/without fix
7. Update documentation

**Testing Checklist:**
- [ ] Unit test: Universe changes over time
- [ ] Unit test: No future constituents in past
- [ ] Integration test: Backtest uses correct universe
- [ ] Validation: Compare biased vs unbiased results
- [ ] Manual test: Check universe at specific dates

**Files to Create:**
- `data/sp500_historical_constituents.csv` - Historical data
- `src/universe_manager.py` - Universe management

**Files to Modify:**
- `src/backtester.py` - Use point-in-time universe
- `tests/test_backtester.py` - Add universe tests
- `README.md` - Document survivorship bias fix

**Acceptance Criteria:**
- Historical universe data loaded
- Point-in-time universe works
- Backtest uses correct universe
- Results show impact of fix

---

#### 4.3 ML Feature Leakage Check
**Branch:** `feature/ml-leakage-check`  
**Estimated Time:** 6-8 hours  
**Risk Level:** High (could invalidate ML strategy)

**Implementation Steps:**
1. Audit all ML features for leakage
2. Add `.shift(1)` to all features
3. Verify target variable doesn't leak
4. Add leakage detection tests
5. Retrain model with fixed features
6. Compare performance before/after
7. Update documentation

**Testing Checklist:**
- [ ] Unit test: All features shifted correctly
- [ ] Unit test: Target doesn't use future data
- [ ] Integration test: Model trains correctly
- [ ] Validation: Accuracy drops to realistic level (51-54%)
- [ ] Manual test: Check feature timestamps

**Files to Modify:**
- `src/strategies/strategy_ml_momentum.py` - Fix features
- `tests/test_ml_momentum.py` - Add leakage tests
- `README.md` - Document feature engineering

**Acceptance Criteria:**
- No feature leakage detected
- Model accuracy realistic (51-54%)
- Features properly shifted
- Tests prevent future leakage

---

#### 4.4 Comprehensive Backtest Execution
**Branch:** `feature/comprehensive-backtest`  
**Estimated Time:** 8-12 hours  
**Risk Level:** Medium (analysis and reporting)

**Implementation Steps:**
1. Run walk-forward backtest (2018-2024)
2. Generate performance metrics:
   - CAGR, Sharpe, Sortino, Calmar
   - Max drawdown, drawdown duration
   - Win rate, profit factor
   - Rolling 12-month Sharpe
3. Create stress test analysis:
   - 2020 COVID crash
   - 2022 bear market
4. Generate plots:
   - Equity curve
   - Drawdown curve
   - Rolling Sharpe
   - Strategy allocation over time
5. Write comprehensive report
6. Update documentation

**Testing Checklist:**
- [ ] Backtest completes successfully
- [ ] All metrics calculated correctly
- [ ] Plots generated correctly
- [ ] Stress tests show realistic behavior
- [ ] Report is comprehensive
- [ ] Results are reproducible

**Files to Create:**
- `docs/reports/BACKTEST_RESULTS.md` - Results report
- `docs/reports/plots/` - Generated plots

**Files to Modify:**
- `docs/reports/EMPIRICAL_VALIDATION_REPORT.md` - Update with results
- `README.md` - Add backtest results summary

**Acceptance Criteria:**
- Backtest runs successfully
- Results are realistic (Sharpe 0.8-1.3)
- Stress tests show reasonable behavior
- Report is comprehensive and honest
- No red flags (Sharpe >2, DD <5%, etc.)

---

### **Phase 5: Production Readiness (Week 11-12)**
*Priority: MEDIUM - Final polish*

#### 5.1 Monitoring Dashboard Enhancements
**Branch:** `feature/monitoring-enhancements`  
**Estimated Time:** 6-8 hours  
**Risk Level:** Low (UI improvements only)

**Implementation Steps:**
1. Add real-time drawdown display
2. Add alert history view
3. Add stop loss tracking
4. Add regime indicator
5. Add performance metrics
6. Update dashboard styling
7. Update documentation

**Acceptance Criteria:**
- Dashboard shows all key metrics
- Real-time updates work
- UI is intuitive
- Mobile responsive

---

#### 5.2 Documentation Finalization
**Branch:** `feature/documentation-finalization`  
**Estimated Time:** 6-8 hours  
**Risk Level:** Low (documentation only)

**Implementation Steps:**
1. Update all documentation with new features
2. Add troubleshooting guide
3. Add FAQ section
4. Add deployment checklist
5. Add disaster recovery procedures
6. Review and update all guides
7. Add video tutorials (optional)

**Acceptance Criteria:**
- All features documented
- Documentation is accurate
- Guides are comprehensive
- No broken links

---

#### 5.3 Final System Validation
**Branch:** `feature/final-validation`  
**Estimated Time:** 8-12 hours  
**Risk Level:** Low (validation only)

**Implementation Steps:**
1. Run full test suite
2. Run complete backtest
3. Run 2 weeks paper trading
4. Verify all alerts work
5. Verify all monitoring works
6. Verify all documentation accurate
7. Create pre-live checklist
8. Final code review

**Acceptance Criteria:**
- All tests pass
- Backtest results realistic
- Paper trading successful
- Alerts working
- Documentation complete
- System ready for live trading decision

---

## 📊 Success Metrics

### Phase 1 (Safety)
- ✅ Catastrophe stops implemented and tested
- ✅ Data quality validation catches bad data
- ✅ Critical alerts send successfully
- ✅ No regressions in existing functionality

### Phase 2 (Risk Management)
- ✅ Adaptive correlation filter working
- ✅ Regime-dependent heat limits working
- ✅ Per-strategy limits enforced
- ✅ Time-based exits working
- ✅ All risk controls tested

### Phase 3 (Performance)
- ✅ Database queries 2x faster
- ✅ Market data caching reduces API calls
- ✅ Test coverage > 60%
- ✅ All critical paths tested

### Phase 4 (Backtesting)
- ✅ Walk-forward backtest complete
- ✅ Survivorship bias fixed
- ✅ ML feature leakage eliminated
- ✅ Results are realistic (Sharpe 0.8-1.3)
- ✅ Stress tests show reasonable behavior

### Phase 5 (Production)
- ✅ Monitoring dashboard enhanced
- ✅ Documentation complete
- ✅ System fully validated
- ✅ Ready for live trading decision

---

## 🚦 Decision Gates

### Gate 1: After Phase 1
**Question:** Are catastrophic risks mitigated?
- Catastrophe stops working?
- Data quality validation working?
- Critical alerts working?

**If NO:** Fix issues before proceeding  
**If YES:** Proceed to Phase 2

### Gate 2: After Phase 2
**Question:** Are risk controls adequate?
- All risk limits working?
- No positions exceed limits?
- Regime detection working?

**If NO:** Fix issues before proceeding  
**If YES:** Proceed to Phase 3

### Gate 3: After Phase 3
**Question:** Is system performant and tested?
- Test coverage > 60%?
- Database performance acceptable?
- All critical paths tested?

**If NO:** Add more tests before proceeding  
**If YES:** Proceed to Phase 4

### Gate 4: After Phase 4
**Question:** Are backtest results realistic?
- Sharpe ratio 0.8-1.3?
- Max drawdown 10-20%?
- No red flags?
- Stress tests reasonable?

**If NO:** Investigate issues, may need strategy changes  
**If YES:** Proceed to Phase 5

### Gate 5: After Phase 5
**Question:** Is system ready for live trading?
- All features working?
- Documentation complete?
- Paper trading successful?
- Comfortable with results?

**If NO:** Continue paper trading  
**If YES:** Consider small live deployment ($10k)

---

## 🛠️ Development Tools

### Required Installations
```bash
# Backtesting
pip install vectorbt
pip install backtrader

# Monitoring
pip install twilio
pip install sentry-sdk

# Testing
pip install hypothesis
pip install pytest-benchmark
pip install pytest-cov

# Performance
pip install line_profiler
pip install memory_profiler
```

### Git Workflow
```bash
# Start new feature
git checkout main
git pull origin main
git checkout -b feature/feature-name

# Work on feature
git add .
git commit -m "Descriptive message"

# Before merging
git checkout main
git pull origin main
git checkout feature/feature-name
git rebase main

# Run tests
make test
make validate

# Merge to main
git checkout main
git merge feature/feature-name
git push origin main

# Monitor for 24-48 hours before next feature
```

### Testing Commands
```bash
# Run all tests
make test

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_execution_engine.py

# Run with verbose output
pytest -v

# Run performance benchmarks
pytest --benchmark-only
```

---

## 📅 Timeline Summary

**Total Estimated Time:** 10-12 weeks (part-time, 10-15 hours/week)

**Week 1-2:** Phase 1 - Critical Safety Features  
**Week 3-4:** Phase 2 - Risk Management Enhancements  
**Week 5-6:** Phase 3 - Data & Performance  
**Week 7-10:** Phase 4 - Walk-Forward Backtesting  
**Week 11-12:** Phase 5 - Production Readiness

**Aggressive Timeline:** 8 weeks (risky, not recommended)  
**Recommended Timeline:** 10-12 weeks (prudent)  
**Conservative Timeline:** 16 weeks (ideal for thorough testing)

---

## 🎯 Next Steps

1. **Review this plan** - Discuss any concerns or adjustments
2. **Set up development environment** - Install required tools
3. **Create first branch** - `feature/catastrophe-stops`
4. **Start Phase 1.1** - Implement catastrophe stop losses
5. **Test thoroughly** - Don't rush, test each feature completely
6. **Monitor continuously** - Watch for any issues after each merge

---

## 💡 Important Reminders

1. **Don't skip testing** - Each feature must be thoroughly tested
2. **Don't rush** - Better to take 12 weeks and do it right than 8 weeks and have bugs
3. **Monitor after merges** - Watch system for 24-48 hours after each merge
4. **Document as you go** - Don't leave documentation for later
5. **Ask questions** - If something is unclear, discuss before implementing
6. **Stay incremental** - One feature at a time, no exceptions
7. **Be honest about results** - If backtest shows poor performance, that's valuable information

---

## 🔗 Resources

**Learning:**
- "Advances in Financial Machine Learning" by Marcos López de Prado
- "Quantitative Trading" by Ernest Chan
- "The Deflated Sharpe Ratio" paper (Bailey & López de Prado)

**Tools:**
- vectorbt documentation: https://vectorbt.dev/
- backtrader documentation: https://www.backtrader.com/
- pytest documentation: https://docs.pytest.org/

**Community:**
- QuantConnect forums
- /r/algotrading subreddit
- Quantitative Finance Stack Exchange

---

**Ready to start? Let's discuss Phase 1.1 (Catastrophe Stops) first!**
