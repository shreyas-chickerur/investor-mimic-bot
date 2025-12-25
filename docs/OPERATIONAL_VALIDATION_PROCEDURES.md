# Phase 5 Operational Validation - Daily Procedures

**Duration:** 14-30 consecutive trading days  
**Start Date:** 2025-12-25 (Day 1 after controlled test)  
**Status:** Ready to begin

---

## Daily Workflow

### 1. Daily Run (Natural Signals Only)

```bash
export ALPACA_PAPER=true
export ENABLE_BROKER_RECONCILIATION=true
export PHASE5_SIGNAL_INJECTION=false  # Keep OFF for entire 14-30 days

python3 src/multi_strategy_main.py
```

### 2. Verify Invariants (Immediately After)

```bash
python3 scripts/check_phase5_invariants.py --latest
python3 scripts/verify_phase5_day1.py
```

**Required:** Both must pass for the day to count.

### 3. Quick Spot Checks (Optional but Recommended)

**Get latest run_id:**
```bash
RUN_ID=$(sqlite3 trading.db "SELECT run_id FROM broker_state ORDER BY created_at DESC LIMIT 1;")
echo "RUN_ID=$RUN_ID"
```

**Confirm snapshots + reconciliation:**
```bash
sqlite3 trading.db "SELECT snapshot_type, reconciliation_status FROM broker_state WHERE run_id='$RUN_ID' ORDER BY created_at;"
```
Expected: `START|SKIPPED`, `RECONCILIATION|PASS`, `END|PASS`

**Confirm all signals terminalized:**
```bash
sqlite3 trading.db "SELECT COUNT(*) AS total, SUM(CASE WHEN terminal_state IS NOT NULL THEN 1 ELSE 0 END) AS terminalized FROM signals WHERE run_id='$RUN_ID';"
```
Expected: `total` = `terminalized`

**Terminal state breakdown:**
```bash
sqlite3 trading.db "SELECT terminal_state, terminal_reason, COUNT(*) FROM signals WHERE run_id='$RUN_ID' GROUP BY terminal_state, terminal_reason;"
```

**Check trades (if any):**
```bash
sqlite3 trading.db "SELECT id, signal_id, symbol, action, shares, requested_price, exec_price, total_cost, notional, order_id FROM trades WHERE run_id='$RUN_ID';"
```

---

## Weekly Rollup (Every 7 Days)

```bash
sqlite3 -header -column trading.db "
SELECT
  snapshot_date AS day,
  COUNT(DISTINCT run_id) AS runs,
  SUM(CASE WHEN reconciliation_status='PASS' THEN 1 ELSE 0 END) AS recon_pass,
  SUM(CASE WHEN reconciliation_status='FAIL' THEN 1 ELSE 0 END) AS recon_fail
FROM broker_state
WHERE snapshot_type='END'
  AND snapshot_date >= date('now','-7 days')
GROUP BY snapshot_date
ORDER BY snapshot_date;"
```

**Expected:** All days show `recon_pass=1`, `recon_fail=0`

---

## Success Criteria

### Daily Requirements
- ✅ `check_phase5_invariants.py --latest` shows 6/6 PASS
- ✅ `verify_phase5_day1.py` shows all checks PASS
- ✅ Reconciliation status = PASS (not FAIL)
- ✅ All signals have terminal states
- ✅ All 3 broker snapshots present (START, RECONCILIATION, END)

### Overall Requirements (14-30 Days)
- ✅ 14-30 consecutive trading days
- ✅ Zero reconciliation failures
- ✅ Zero invariant violations
- ✅ 100% signal termination rate
- ✅ Complete audit trail every day

---

## Important Notes

1. **Keep injection OFF:** `PHASE5_SIGNAL_INJECTION=false` for entire validation period
2. **0-signal days are OK:** Natural signals may not trigger every day
3. **If invariants fail:** Stop and investigate before continuing
4. **If reconciliation fails:** Critical issue - must be resolved before continuing

---

## Troubleshooting

### If Invariants Fail
Paste the full output of:
```bash
python3 scripts/check_phase5_invariants.py --latest
```

### If verify_phase5_day1.py Fails
Paste the full output of:
```bash
python3 scripts/verify_phase5_day1.py
```

### If Reconciliation Fails
Check discrepancies:
```bash
RUN_ID=$(sqlite3 trading.db "SELECT run_id FROM broker_state ORDER BY created_at DESC LIMIT 1;")
sqlite3 trading.db "SELECT discrepancies_json FROM broker_state WHERE run_id='$RUN_ID' AND snapshot_type='RECONCILIATION';"
```

---

## Daily Log Template

```
Date: YYYY-MM-DD
Run ID: <from query>
Invariants: 6/6 PASS / X/6 FAIL
verify_phase5_day1: PASS / FAIL
Reconciliation: PASS / FAIL
Signals: X total, X terminalized
Trades: X executed
Notes: <any observations>
```

---

## Completion

After 14-30 consecutive successful days:
1. Document final results
2. Calculate success metrics (recon pass rate, signal termination rate, etc.)
3. Mark Phase 5 operational validation as COMPLETE
4. System ready for production deployment

**Current Status:** Day 0 (Controlled test complete, ready to begin Day 1)
