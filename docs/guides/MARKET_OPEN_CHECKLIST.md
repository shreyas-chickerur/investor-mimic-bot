# Market Open Checklist - Phase 5 Day 1

**Execute at:** 9:30 AM ET, December 24, 2025  
**Purpose:** Complete fresh start and begin Phase 5 Day 1

---

## Pre-Market (Before 9:30 AM ET)

### ✅ Already Complete
- [x] Database reset (0 trades, PHASE_5_INITIAL_STATE_RESET = TRUE)
- [x] Email alerts fixed (send_alert method added)
- [x] Terminal state enforcement ready
- [x] Sell orders submitted for all 11 positions

### ⏳ Waiting for Market Open
- [ ] Positions to settle (11 sell orders accepted, waiting for fills)
- [ ] Cash to update to ~$100,402.61

---

## At Market Open (9:30 AM ET)

### Step 1: Verify Positions Cleared (2 minutes)

**Run this command:**
```bash
python3 -c "
import sys
sys.path.insert(0, 'src')
from broker_reconciler import BrokerReconciler

r = BrokerReconciler()
s = r.get_broker_state()
print(f'Positions: {len(s[\"positions\"])}')
print(f'Cash: \${s[\"cash\"]:,.2f}')
print(f'Portfolio Value: \${s[\"portfolio_value\"]:,.2f}')

if len(s['positions']) == 0:
    print('\n✅ READY FOR DAY 1')
else:
    print(f'\n⚠️  {len(s[\"positions\"])} positions remain')
    for symbol, pos in s['positions'].items():
        print(f'  {symbol}: {pos[\"qty\"]} shares')
"
```

**Expected output:**
```
Positions: 0
Cash: $100,402.61
Portfolio Value: $100,402.61

✅ READY FOR DAY 1
```

**If positions still show:**
- Wait 5 more minutes (orders may still be settling)
- Check Alpaca web interface: https://app.alpaca.markets/paper/dashboard/overview
- If positions persist, manually close via web interface

---

### Step 2: Run Day 1 Execution (1 minute)

**Once positions = 0, run:**
```bash
export ENABLE_BROKER_RECONCILIATION=true
python3 src/execution_engine.py
```

**Watch for:**
- `✅ Reconciliation PASSED`
- `Discrepancies: 0`
- `System State: ACTIVE (not paused)`
- `Artifact generated: artifacts/json/2025-12-24.json`

---

### Step 3: Verify Day 1 Success (1 minute)

**Run this verification:**
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
    
    recon_status = data.get('reconciliation_status', 'UNKNOWN')
    recon_discrep = len(data.get('reconciliation_discrepancies', []))
    
    print(f'Date: {date}')
    print(f'Reconciliation: {recon_status}')
    print(f'Discrepancies: {recon_discrep}')
    print(f'Signals Generated: {len(data.get(\"generated_signals\", []))}')
    print(f'Trades: {len(data.get(\"filled_orders\", []))}')
    
    if 'PASS' in recon_status and recon_discrep == 0:
        print('\n✅ DAY 1 COMPLETE')
        print('✅ Phase 5 officially started')
    else:
        print(f'\n❌ Issue detected')
else:
    print(f'❌ No artifact for {date}')
"
```

**Expected output:**
```
Date: 2025-12-24
Reconciliation: PASSED
Discrepancies: 0
Signals Generated: [varies]
Trades: [varies]

✅ DAY 1 COMPLETE
✅ Phase 5 officially started
```

---

### Step 4: Update Documentation (1 minute)

**Update incident log:**
```bash
# Add resolution note to Incident #003
echo "
**Resolution Update (Market Open):**
- Positions cleared at market open (9:30 AM ET Dec 24)
- Day 1 executed successfully
- Reconciliation passed (0 discrepancies)
" >> docs/PHASE_5_INCIDENT_LOG.md
```

**Commit the Day 1 results:**
```bash
git add -A
git commit -m "Phase 5 Day 1 - Market Open Execution Complete

- Positions cleared at market open
- Reconciliation: PASSED (0 discrepancies)
- Day 1 artifact generated
- Phase 5 officially started"
git push origin main
```

---

## Success Criteria

✅ **Broker State:**
- Positions: 0
- Cash: ~$100,402.61
- Portfolio Value: ~$100,402.61

✅ **Reconciliation:**
- Status: PASSED
- Discrepancies: 0
- System: ACTIVE (not paused)

✅ **Artifacts:**
- JSON: `artifacts/json/2025-12-24.json` exists
- Markdown: `artifacts/markdown/2025-12-24.md` exists

✅ **System Health:**
- No errors
- Terminal states enforced
- No silent signal drops

---

## If Something Goes Wrong

### Issue: Positions still showing after 10 minutes
**Solution:**
1. Check Alpaca web interface for order status
2. Manually close any remaining positions
3. Wait 2 minutes and retry Step 1

### Issue: Reconciliation fails
**Solution:**
1. Check discrepancy list in logs
2. If broker has phantom positions → close them manually
3. If database has phantom state → run database reset again
4. Retry Day 1 execution

### Issue: Data validation fails
**Solution:**
1. Update market data: `make update-data`
2. Wait for data refresh to complete
3. Retry Day 1 execution

### Issue: No artifact generated
**Solution:**
1. Check logs for errors: `tail -100 logs/phase5_day1_final.log`
2. Fix any errors
3. Retry Day 1 execution

---

## After Day 1 Complete

### Daily Execution Schedule
- **Time:** 4:15 PM ET (after market close)
- **Command:** `export ENABLE_BROKER_RECONCILIATION=true && python3 src/execution_engine.py`
- **Duration:** 14-30 consecutive trading days

### Daily Monitoring
1. Check reconciliation status (must pass every day)
2. Review daily artifact (`artifacts/json/YYYY-MM-DD.json`)
3. Verify terminal states (no silent drops)
4. Log any incidents in `docs/PHASE_5_INCIDENT_LOG.md`

### Phase 5 Rules (STRICT)
- ❌ NO strategy changes
- ❌ NO parameter tuning
- ❌ NO allocation logic changes
- ❌ NO risk limit changes
- ❌ NO reconciliation disabling
- ✅ Log all incidents honestly
- ✅ Keep reconciliation enabled
- ✅ Generate artifacts daily

---

## Timeline

**Now (12:47 AM PST):** Waiting for market open  
**9:30 AM ET (6:30 AM PST):** Execute checklist  
**9:35 AM ET:** Day 1 complete  
**4:15 PM ET:** Day 2 execution  
**Next 14-30 days:** Daily execution and monitoring

---

## Quick Reference Commands

**Check broker state:**
```bash
python3 -c "import sys; sys.path.insert(0, 'src'); from broker_reconciler import BrokerReconciler; r = BrokerReconciler(); s = r.get_broker_state(); print(f'Positions: {len(s[\"positions\"])}, Cash: \${s[\"cash\"]:,.2f}')"
```

**Run Day 1:**
```bash
export ENABLE_BROKER_RECONCILIATION=true && python3 src/execution_engine.py
```

**Check Day 1 results:**
```bash
python3 -c "import json; from pathlib import Path; from datetime import datetime; p = Path(f'artifacts/json/{datetime.now().strftime(\"%Y-%m-%d\")}.json'); print(json.load(open(p))['reconciliation_status'] if p.exists() else 'No artifact')"
```

---

**Total time needed at market open: ~5 minutes**
