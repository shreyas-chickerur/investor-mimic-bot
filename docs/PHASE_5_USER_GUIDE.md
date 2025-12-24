# Phase 5 Paper Trading - Complete User Guide

**Duration:** 14-30 consecutive trading days  
**Start:** December 24, 2025  
**Daily Time:** 5-10 minutes

---

## Day 1: Market Open Execution (One-Time Setup)

**Execute at:** 9:30 AM ET (6:30 AM PST), December 24, 2025

### Step 1: Verify Positions Cleared (2 min)
```bash
python3 -c "
import sys
sys.path.insert(0, 'src')
from broker_reconciler import BrokerReconciler

r = BrokerReconciler()
s = r.get_broker_state()
print(f'Positions: {len(s[\"positions\"])}')
print(f'Cash: \${s[\"cash\"]:,.2f}')

if len(s['positions']) == 0:
    print('\n✅ READY FOR DAY 1')
else:
    print(f'\n⚠️ {len(s[\"positions\"])} positions remain - wait 5 min')
"
```
**Expected:** `Positions: 0`, `Cash: $100,402.61`

### Step 2: Run Day 1 (1 min)
```bash
export ENABLE_BROKER_RECONCILIATION=true
python3 src/multi_strategy_main.py
```
**Watch for:** `✅ Reconciliation PASSED`, `Discrepancies: 0`

### Step 3: Verify Success (1 min)
```bash
python3 -c "
import json
from datetime import datetime
from pathlib import Path

date = datetime.now().strftime('%Y-%m-%d')
json_path = Path(f'artifacts/json/{date}.json')

if json_path.exists():
    with open(json_path) as f:
        data = json.load(f)
    
    recon = data.get('reconciliation_status', 'UNKNOWN')
    discrep = len(data.get('reconciliation_discrepancies', []))
    
    print(f'Reconciliation: {recon}')
    print(f'Discrepancies: {discrep}')
    
    if 'PASS' in recon and discrep == 0:
        print('\n✅ DAY 1 COMPLETE - Phase 5 started!')
"
```

### Step 4: Commit (1 min)
```bash
git add -A
git commit -m "Phase 5 Day 1 Complete"
git push origin main
```

---

## Days 2-30: Daily Execution

**Execute at:** 4:15 PM ET (1:15 PM PST) every trading day

### Daily Command (2-3 min)
```bash
export ENABLE_BROKER_RECONCILIATION=true
python3 src/multi_strategy_main.py
```

**Watch for:**
- ✅ `Reconciliation: PASSED`
- ✅ `Discrepancies: 0`
- ✅ `System State: ACTIVE`
- ✅ `Artifact generated`

### Verify Results (1 min)
```bash
python3 -c "
import json
from datetime import datetime
from pathlib import Path

date = datetime.now().strftime('%Y-%m-%d')
json_path = Path(f'artifacts/json/{date}.json')

if json_path.exists():
    with open(json_path) as f:
        data = json.load(f)
    
    recon = data.get('reconciliation_status', 'UNKNOWN')
    discrep = len(data.get('reconciliation_discrepancies', []))
    signals_gen = len(data.get('generated_signals', []))
    signals_exec = len(data.get('executed_signals', []))
    signals_rej = len(data.get('rejected_signals', []))
    trades = len(data.get('filled_orders', []))
    
    print(f'Date: {date}')
    print(f'Reconciliation: {recon}')
    print(f'Discrepancies: {discrep}')
    print(f'Signals: {signals_gen} gen, {signals_exec} exec, {signals_rej} rej')
    print(f'Trades: {trades}')
    
    if 'PASS' in recon and discrep == 0:
        print('\n✅ Day complete')
    else:
        print('\n❌ Issues detected - see troubleshooting')
"
```

### Commit Results (1 min)
```bash
git add artifacts/ logs/
git commit -m "Phase 5 Day X - $(date +%Y-%m-%d)"
git push origin main
```

---

## Daily Checklist

- [ ] System ran at 4:15 PM ET
- [ ] Reconciliation PASSED (0 discrepancies)
- [ ] Artifact generated (JSON + Markdown)
- [ ] All signals reached terminal state
- [ ] No errors in logs
- [ ] Results committed to git

---

## Troubleshooting

### Reconciliation Failed

**Check discrepancies:**
```bash
tail -100 logs/multi_strategy_*.log | grep -A 20 "RECONCILIATION"
```

**Check broker state:**
```bash
python3 -c "
import sys
sys.path.insert(0, 'src')
from broker_reconciler import BrokerReconciler
r = BrokerReconciler()
s = r.get_broker_state()
print(f'Broker positions: {len(s[\"positions\"])}')
for symbol, pos in s['positions'].items():
    print(f'  {symbol}: {pos[\"qty\"]} shares')
"
```

**If phantom positions exist:**
- Close manually: https://app.alpaca.markets/paper/dashboard/overview
- Log incident in `docs/PHASE_5_INCIDENT_LOG.md`
- Retry execution

### Data Too Old

**Update market data:**
```bash
make update-data
# Wait 2-3 minutes, then retry execution
```

### Silent Signal Drops

**Check if all signals reached terminal state:**
```bash
python3 -c "
import json
from datetime import datetime
from pathlib import Path

date = datetime.now().strftime('%Y-%m-%d')
json_path = Path(f'artifacts/json/{date}.json')

if json_path.exists():
    with open(json_path) as f:
        data = json.load(f)
    
    generated = len(data.get('generated_signals', []))
    executed = len(data.get('executed_signals', []))
    rejected = len(data.get('rejected_signals', []))
    
    if generated != executed + rejected:
        print(f'❌ SILENT DROP: {generated - executed - rejected} signals')
    else:
        print(f'✅ All {generated} signals reached terminal state')
"
```

**If silent drops detected:** Log as critical incident and investigate

---

## Weekly Review

**Every Friday, check progress:**
```bash
python3 scripts/phase5_weekly_review.py
```

---

## Accessing GitHub Actions Artifacts

### View Artifacts
1. Go to: https://github.com/shreyas-chickerur/investor-mimic-bot/actions
2. Click any completed workflow run
3. Scroll to **Artifacts** section
4. Download:
   - `test-logs` - Execution logs
   - `database-snapshot` - Database state
   - `trading-artifacts` - Daily JSON/Markdown files

### Download All Artifacts
```bash
python3 scripts/download_github_artifacts.py
```

This downloads all artifacts from the last 30 days to `artifacts_backup/`

---

## Generate Final Report

**After 14-30 days, generate completion report:**
```bash
python3 scripts/generate_phase5_report.py
```

**Report includes:**
- Total days executed
- Success rate (must be 100%)
- Total trades
- Reconciliation history
- Incident summary
- Performance metrics
- Completion status

**Report location:** `docs/PHASE_5_COMPLETION_REPORT.md`

---

## Success Criteria

Phase 5 is successful if **ALL** of these hold for 14-30 days:

### Operational
- ✅ 100% scheduled days run (no crashes)
- ✅ 0 unresolved reconciliation mismatches
- ✅ 0 silent signal drops
- ✅ 100% artifact generation

### Risk
- ✅ Portfolio heat never exceeds 30%
- ✅ Circuit breaker respected

### Integrity
- ✅ No strategy/parameter changes
- ✅ No manual overrides

---

## Quick Reference

**Daily execution:**
```bash
export ENABLE_BROKER_RECONCILIATION=true && python3 src/multi_strategy_main.py
```

**Check today's status:**
```bash
python3 -c "import json; from pathlib import Path; from datetime import datetime; p = Path(f'artifacts/json/{datetime.now().strftime(\"%Y-%m-%d\")}.json'); print(json.load(open(p))['reconciliation_status'] if p.exists() else 'No artifact')"
```

**View logs:**
```bash
tail -100 logs/multi_strategy_$(date +%Y%m%d)*.log
```

**Check broker:**
```bash
python3 -c "import sys; sys.path.insert(0, 'src'); from broker_reconciler import BrokerReconciler; r = BrokerReconciler(); s = r.get_broker_state(); print(f'Positions: {len(s[\"positions\"])}, Cash: \${s[\"cash\"]:,.2f}')"
```

---

## After Phase 5 Completion

1. Generate final report: `python3 scripts/generate_phase5_report.py`
2. Review completion document: `docs/PHASE_5_COMPLETION_REPORT.md`
3. If all metrics passed → Ready for production
4. If any failures → Document lessons learned and decide next steps
