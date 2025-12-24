# Phase 5 Daily Execution Guide (Days 2-30)

**Duration:** 14-30 consecutive trading days  
**Start Date:** December 24, 2025 (Day 1)  
**Daily Execution Time:** 4:15 PM ET (1:15 PM PST)

---

## Daily Execution Steps (Every Trading Day)

### Step 1: Pre-Execution Check (1 minute)

**Verify market is closed:**
```bash
# Market closes at 4:00 PM ET
# Wait until 4:15 PM ET to ensure all data is final
date
```

**Check system status:**
```bash
cd /Users/shreyaschickerur/CascadeProjects/investor-mimic-bot
git pull origin main  # Get any updates
```

---

### Step 2: Run Daily Execution (2-3 minutes)

**Execute the trading system:**
```bash
export ENABLE_BROKER_RECONCILIATION=true
python3 src/multi_strategy_main.py
```

**Watch for these critical outputs:**
- ✅ `Reconciliation: PASSED`
- ✅ `Discrepancies: 0`
- ✅ `System State: ACTIVE (not paused)`
- ✅ `Artifact generated: artifacts/json/YYYY-MM-DD.json`

**If you see:**
- ❌ `Reconciliation: FAILED` → Go to **Troubleshooting** section
- ❌ `System State: PAUSED` → Go to **Troubleshooting** section
- ❌ Any errors → Check logs and troubleshoot

---

### Step 3: Verify Daily Artifact (1 minute)

**Check artifact was generated:**
```bash
python3 -c "
import json
from datetime import datetime
from pathlib import Path

date = datetime.now().strftime('%Y-%m-%d')
json_path = Path(f'artifacts/json/{date}.json')
md_path = Path(f'artifacts/markdown/{date}.md')

print(f'Date: {date}')
print(f'JSON artifact: {\"✅\" if json_path.exists() else \"❌\"} {json_path}')
print(f'Markdown artifact: {\"✅\" if md_path.exists() else \"❌\"} {md_path}')

if json_path.exists():
    with open(json_path) as f:
        data = json.load(f)
    
    print(f'\nReconciliation: {data.get(\"reconciliation_status\", \"UNKNOWN\")}')
    print(f'Discrepancies: {len(data.get(\"reconciliation_discrepancies\", []))}')
    print(f'Signals Generated: {len(data.get(\"generated_signals\", []))}')
    print(f'Signals Executed: {len(data.get(\"executed_signals\", []))}')
    print(f'Signals Rejected: {len(data.get(\"rejected_signals\", []))}')
    print(f'Trades: {len(data.get(\"filled_orders\", []))}')
    print(f'System Health: {data.get(\"system_health\", {})}')
"
```

**Expected output:**
```
Date: 2025-12-XX
JSON artifact: ✅ artifacts/json/2025-12-XX.json
Markdown artifact: ✅ artifacts/markdown/2025-12-XX.md

Reconciliation: PASSED
Discrepancies: 0
Signals Generated: [varies]
Signals Executed: [varies]
Signals Rejected: [varies]
Trades: [varies]
System Health: {'runtime_seconds': X, 'error_count': 0, ...}
```

---

### Step 4: Daily Metrics Check (1 minute)

**Verify success criteria:**
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
    
    # Check operational metrics
    recon_status = data.get('reconciliation_status', '')
    recon_discrep = len(data.get('reconciliation_discrepancies', []))
    
    # Check for silent drops
    generated = len(data.get('generated_signals', []))
    executed = len(data.get('executed_signals', []))
    rejected = len(data.get('rejected_signals', []))
    terminal_states = executed + rejected
    
    # Check risk metrics
    risk = data.get('risk', {})
    portfolio_heat = risk.get('portfolio_heat', 0)
    circuit_breaker = risk.get('circuit_breaker_state', 'UNKNOWN')
    
    print('='*60)
    print('DAILY METRICS CHECK')
    print('='*60)
    
    # Operational
    print(f'\n✅ OPERATIONAL:')
    print(f'   Reconciliation: {\"PASS\" if \"PASS\" in recon_status else \"FAIL\"}')
    print(f'   Discrepancies: {recon_discrep} (must be 0)')
    print(f'   Silent drops: {generated - terminal_states} (must be 0)')
    
    # Risk
    print(f'\n✅ RISK:')
    print(f'   Portfolio heat: {portfolio_heat:.1f}% (max 30%)')
    print(f'   Circuit breaker: {circuit_breaker}')
    
    # Integrity
    print(f'\n✅ INTEGRITY:')
    print(f'   No parameter changes: YES (manual verification)')
    print(f'   No manual overrides: YES (manual verification)')
    
    # Summary
    all_pass = (
        'PASS' in recon_status and 
        recon_discrep == 0 and 
        generated == terminal_states and
        portfolio_heat <= 30.0
    )
    
    print(f'\n{\"✅\" if all_pass else \"❌\"} Day {date}: {\"SUCCESS\" if all_pass else \"ISSUES DETECTED\"}')
else:
    print(f'❌ No artifact found for {date}')
"
```

---

### Step 5: Commit Daily Results (1 minute)

**Commit the day's artifacts and logs:**
```bash
git add artifacts/ logs/
git commit -m "Phase 5 Day X - $(date +%Y-%m-%d)

Reconciliation: PASSED
Discrepancies: 0
Signals: X generated, X executed, X rejected
Trades: X
System: ACTIVE"

git push origin main
```

---

## Daily Monitoring Checklist

Use this checklist **every day**:

- [ ] System ran at 4:15 PM ET
- [ ] Reconciliation PASSED (0 discrepancies)
- [ ] Daily artifact generated (JSON + Markdown)
- [ ] All signals reached terminal state (no silent drops)
- [ ] Portfolio heat within limits (≤30%)
- [ ] Circuit breaker INACTIVE (or appropriately triggered)
- [ ] No unintended trades
- [ ] No errors in logs
- [ ] Results committed to git

---

## Phase 5 Success Criteria (Must Hold Every Day)

### Operational Stability
- ✅ System runs successfully every trading day
- ✅ 0 unresolved reconciliation mismatches
- ✅ 0 silent signal drops
- ✅ 100% artifact generation

### Risk Discipline
- ✅ Portfolio heat never exceeds regime cap (30%)
- ✅ Circuit breaker respected
- ✅ No exposure spikes

### Integrity
- ✅ No strategy changes
- ✅ No parameter tuning
- ✅ No allocation logic changes
- ✅ No risk limit changes
- ✅ No manual overrides

---

## Troubleshooting

### Issue: Reconciliation Failed

**Symptoms:**
- `Reconciliation: FAILED`
- `Discrepancies: X` (where X > 0)
- `System State: PAUSED`

**Steps:**
1. **Check discrepancies:**
   ```bash
   tail -100 logs/multi_strategy_*.log | grep -A 20 "RECONCILIATION"
   ```

2. **If broker has phantom positions:**
   ```bash
   # Check broker state
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
   
   # Close phantom positions manually via Alpaca web interface
   # https://app.alpaca.markets/paper/dashboard/overview
   ```

3. **If local DB has phantom state:**
   ```bash
   # Check local database
   python3 -c "
   import sys
   sys.path.insert(0, 'src')
   from strategy_database import StrategyDatabase
   db = StrategyDatabase()
   strategies = db.get_all_strategies()
   for strat in strategies:
       trades = db.get_strategy_trades(strat['id'])
       print(f'{strat[\"name\"]}: {len(trades)} trades')
   "
   
   # If mismatch, log incident and investigate
   ```

4. **Log incident:**
   ```bash
   # Add to docs/PHASE_5_INCIDENT_LOG.md
   # Document: date, issue, root cause, resolution, impact
   ```

5. **Retry after fix:**
   ```bash
   export ENABLE_BROKER_RECONCILIATION=true
   python3 src/multi_strategy_main.py
   ```

---

### Issue: Data Validation Failed

**Symptoms:**
- `Data validation failed: Data is X hours old`
- System exits before execution

**Steps:**
1. **Update market data:**
   ```bash
   make update-data
   # Or: python3 scripts/fetch_extended_historical_data.py
   ```

2. **Wait for completion** (2-3 minutes)

3. **Retry execution:**
   ```bash
   export ENABLE_BROKER_RECONCILIATION=true
   python3 src/multi_strategy_main.py
   ```

---

### Issue: Silent Signal Drops

**Symptoms:**
- Signals generated but no terminal state logged
- `generated_signals` count > (`executed_signals` + `rejected_signals`)

**Steps:**
1. **Check signal flow logs:**
   ```bash
   tail -200 logs/multi_strategy_*.log | grep -E "(GENERATED|EXECUTED|REJECTED)"
   ```

2. **Verify terminal state enforcement:**
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
       
       generated = data.get('generated_signals', [])
       executed = data.get('executed_signals', [])
       rejected = data.get('rejected_signals', [])
       
       print(f'Generated: {len(generated)}')
       print(f'Executed: {len(executed)}')
       print(f'Rejected: {len(rejected)}')
       print(f'Terminal states: {len(executed) + len(rejected)}')
       
       if len(generated) != len(executed) + len(rejected):
           print(f'\n❌ SILENT DROP DETECTED')
           print(f'   Missing: {len(generated) - len(executed) - len(rejected)} signals')
   "
   ```

3. **Log incident** (this is a critical issue)

4. **Investigate code** (signal flow tracer may have bug)

---

### Issue: Circuit Breaker Triggered

**Symptoms:**
- `Circuit breaker: ACTIVE`
- Trading blocked for the day

**Steps:**
1. **This is expected behavior** - circuit breaker protects against excessive losses

2. **Verify trigger was legitimate:**
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
       
       risk = data.get('risk', {})
       print(f'Daily P&L: {risk.get(\"daily_pnl\", 0):.2f}')
       print(f'Drawdown: {risk.get(\"drawdown\", 0):.2f}%')
       print(f'Circuit breaker: {risk.get(\"circuit_breaker_state\")}')
   "
   ```

3. **Log in incident log** (document trigger reason)

4. **Continue next day** (circuit breaker resets daily)

---

## Weekly Review (Every Friday)

**Review Phase 5 progress:**
```bash
python3 -c "
import json
from pathlib import Path
from datetime import datetime, timedelta

print('='*60)
print('PHASE 5 WEEKLY REVIEW')
print('='*60)

# Get last 7 days of artifacts
days_checked = 0
days_passed = 0
total_trades = 0

for i in range(7):
    date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
    json_path = Path(f'artifacts/json/{date}.json')
    
    if json_path.exists():
        days_checked += 1
        with open(json_path) as f:
            data = json.load(f)
        
        recon_status = data.get('reconciliation_status', '')
        recon_discrep = len(data.get('reconciliation_discrepancies', []))
        trades = len(data.get('filled_orders', []))
        
        if 'PASS' in recon_status and recon_discrep == 0:
            days_passed += 1
        
        total_trades += trades
        
        print(f'{date}: {\"✅\" if \"PASS\" in recon_status else \"❌\"} Recon, {trades} trades')

print(f'\nWeek Summary:')
print(f'  Days checked: {days_checked}')
print(f'  Days passed: {days_passed}')
print(f'  Success rate: {days_passed/days_checked*100:.1f}%')
print(f'  Total trades: {total_trades}')
print(f'\nPhase 5 requires: 100% success rate for 14-30 days')
"
```

---

## Phase 5 Completion

**After 14-30 consecutive successful days:**

1. **Generate final report:**
   ```bash
   python3 scripts/generate_phase5_report.py
   ```

2. **Create completion document:**
   ```bash
   # Create docs/PHASE_5_COMPLETION.md
   # Include: duration, success metrics, incidents, lessons learned
   ```

3. **Commit final results:**
   ```bash
   git add -A
   git commit -m "Phase 5 Complete - X days of validated paper trading"
   git push origin main
   ```

4. **Ready for production** (if all metrics passed)

---

## Quick Reference

**Daily command:**
```bash
export ENABLE_BROKER_RECONCILIATION=true && python3 src/multi_strategy_main.py
```

**Check today's results:**
```bash
python3 -c "import json; from pathlib import Path; from datetime import datetime; p = Path(f'artifacts/json/{datetime.now().strftime(\"%Y-%m-%d\")}.json'); print(json.load(open(p))['reconciliation_status'] if p.exists() else 'No artifact')"
```

**View logs:**
```bash
tail -100 logs/multi_strategy_$(date +%Y%m%d)*.log
```

**Check broker state:**
```bash
python3 -c "import sys; sys.path.insert(0, 'src'); from broker_reconciler import BrokerReconciler; r = BrokerReconciler(); s = r.get_broker_state(); print(f'Positions: {len(s[\"positions\"])}, Cash: \${s[\"cash\"]:,.2f}')"
```

---

**Phase 5 Duration:** 14-30 consecutive trading days  
**Daily Time Commitment:** ~5-10 minutes  
**Success Criteria:** 100% operational stability, 0 reconciliation failures, full observability
