# Phase 5 Implementation Plan - Paper Trading

**Date:** December 23, 2025  
**Status:** Planning  
**Duration:** 14-30 trading days

---

## Objective

Validate live operability, safety, and observability under real market conditions **WITHOUT** modifying strategy logic.

---

## Core Constraints (STRICT)

❌ **FORBIDDEN:**
- Strategy parameter changes
- Allocation logic changes
- Risk limit changes
- Tuning based on paper performance
- Skipping days due to "bad conditions"

✅ **ALLOWED ONLY:**
- Execution bug fixes
- Reconciliation error fixes
- Logging/observability improvements
- Operational failure fixes

---

## Implementation Components

### 1. Broker Reconciliation System (CRITICAL)

**File:** `src/broker_reconciliation.py`

**Requirements:**
- Daily automatic reconciliation
- Check: Positions (symbol, qty, avg price)
- Check: Cash balance
- Check: Orders (no phantom/duplicated/stuck)
- Check: Trades (local P&L matches broker fills)

**Failure Behavior:**
- Enter PAUSED state immediately
- Block all new trades
- Log and email alert
- Resume only after reconciliation success

**Implementation:**
```python
class BrokerReconciliation:
    def reconcile_daily():
        # Compare local state vs Alpaca
        # Return: (success, discrepancies)
        pass
    
    def enter_paused_state():
        # Block trading
        # Send alerts
        pass
```

---

### 2. Daily Execution Artifact Generator

**File:** `src/daily_artifact_generator.py`

**Artifact Contents:**
- Date
- Market Regime (VIX level, classification)
- Signals (raw, rejected with reasons, executed)
- Trades (placed, filled, rejected)
- Risk (heat, P&L, drawdown, circuit breaker state)
- Positions (open, unrealized P&L, exposure)
- System Health (runtime, errors, data freshness)

**Storage:**
- Location: `artifacts/YYYY-MM-DD.json`
- Format: Machine-readable JSON
- Retention: Permanent

**Implementation:**
```python
class DailyArtifactGenerator:
    def generate_artifact(date, data):
        # Compile all required data
        # Save to artifacts/YYYY-MM-DD.json
        pass
```

---

### 3. Live Signal Flow Integrity

**File:** `src/signal_flow_logger.py`

**Terminal States (MANDATORY):**
- EXECUTED
- REJECTED_BY_CORRELATION
- REJECTED_BY_HEAT
- REJECTED_BY_CIRCUIT_BREAKER
- REJECTED_BY_SIZING (0 shares)
- REJECTED_BY_BROKER

**Requirements:**
- Every signal must reach exactly one terminal state
- No silent drops allowed
- Full traceability

**Implementation:**
```python
class SignalFlowLogger:
    def log_signal_outcome(signal, terminal_state, reason):
        # Log with timestamp, signal details, outcome
        pass
```

---

### 4. Zero-Trade Day Handling

**File:** `src/zero_trade_handler.py`

**Requirements:**
- Explicitly log reason:
  - "No signals generated"
  - "Signals rejected by risk"
  - "System paused"
- Confirm:
  - P&L unchanged
  - No fees applied
  - Positions unchanged

**Implementation:**
```python
class ZeroTradeHandler:
    def log_zero_trade_day(date, reason):
        # Document why no trades occurred
        # Verify state unchanged
        pass
```

---

### 5. Regime Transition Validation

**File:** `src/regime_transition_monitor.py`

**Requirements:**
- Detect VIX threshold crossing
- Log regime change
- Monitor portfolio heat adjustment
- Track strategy enable/disable
- Check for exposure spikes

**Must Observe Live:**
- At least one regime transition during Phase 5
- Cannot be simulated

**Implementation:**
```python
class RegimeTransitionMonitor:
    def detect_transition(current_vix, previous_vix):
        # Check if regime changed
        # Log all adjustments
        pass
```

---

### 6. Circuit Breaker Observation

**File:** `src/circuit_breaker_monitor.py`

**Requirements:**
- Passive observation (not forced)
- If triggered:
  - Trading halts immediately
  - No new trades that day
  - Event logged with timestamp
  - Resume logic follows documented rules
- If not triggered: Record as "not observed"

**Implementation:**
```python
class CircuitBreakerMonitor:
    def observe_circuit_breaker(triggered, reason):
        # Log event
        # Confirm halt behavior
        pass
```

---

### 7. Daily Metrics Tracking

**File:** `src/daily_metrics_tracker.py`

**Metrics Required:**

**Performance:**
- Daily return
- Cumulative return
- Win rate
- Profit factor
- Rolling Sharpe
- Max drawdown

**Risk:**
- Portfolio heat
- Exposure concentration
- Correlation levels
- Strategy allocation weights

**Operational:**
- Order rejection rate
- Execution slippage vs expected
- Runtime stability

**Implementation:**
```python
class DailyMetricsTracker:
    def calculate_daily_metrics(date, trades, positions):
        # Calculate all required metrics
        # Append to PHASE_5_METRICS.csv
        pass
```

---

### 8. Phase 5 Deliverables

**Files to Generate:**

1. **`docs/PHASE_5_PAPER_TRADING_REPORT.md`**
   - Timeline summary
   - Daily trade counts
   - Regime distribution
   - P&L summary
   - Risk events
   - Operational issues
   - Honest assessment

2. **`docs/PHASE_5_INCIDENT_LOG.md`**
   - Reconciliation issues
   - Broker rejections
   - System pauses
   - Anomalies

3. **`artifacts/PHASE_5_METRICS.csv`**
   - One row per trading day
   - All metrics

---

## Success Criteria (ALL REQUIRED)

### Operational Stability
- [  ] System runs every scheduled day
- [  ] No unresolved broker mismatches
- [  ] No silent signal loss
- [  ] No unintended trades

### Risk Discipline
- [  ] Portfolio heat never exceeds limits
- [  ] Circuit breakers respected
- [  ] No exposure spikes on regime changes

### Observability
- [  ] Daily artifacts generated 100% of days
- [  ] Every trade traceable end-to-end
- [  ] Every rejection has a reason

### Integrity
- [  ] No parameter changes
- [  ] No strategy tuning
- [  ] No manual overrides

### Honesty
- [  ] Negative performance reported unchanged
- [  ] Zero-trade periods documented clearly

---

## Implementation Timeline

### Week 1: Infrastructure Setup
- Day 1-2: Broker reconciliation system
- Day 3-4: Daily artifact generator
- Day 5: Signal flow integrity logging

### Week 2: Monitoring & Validation
- Day 6-7: Zero-trade and regime transition handling
- Day 8-9: Metrics tracking and circuit breaker monitoring
- Day 10: Testing and validation

### Week 3-5: Live Paper Trading
- 14-30 consecutive trading days
- Daily monitoring and artifact generation
- No modifications to strategy logic

### Week 6: Analysis & Reporting
- Generate Phase 5 deliverables
- Compile incident log
- Create final report

---

## Exit Decision

**Valid Outcomes:**
- ✅ Operationally sound → proceed to extended paper or capital scaling
- ⚠️ Operational issues → fix and re-run Phase 5
- ❌ System unstable → halt progression

**No partial pass allowed.**

---

## Next Steps

1. Create all required Python modules
2. Integrate with existing system
3. Test reconciliation logic
4. Set up artifact storage
5. Begin 14-30 day paper trading period

---

**Phase 5 is an audit, not an experiment.**  
**Trustworthiness matters more than P&L.**
