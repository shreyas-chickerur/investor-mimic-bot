# Market Open Quick Start - Phase 5 Day 1

**Execute at:** 9:30 AM ET (6:30 AM PST), December 24, 2025  
**Total time:** ~5 minutes

---

## Step 1: Verify Positions Cleared (2 min)

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

---

## Step 2: Run Day 1 (1 min)

```bash
export ENABLE_BROKER_RECONCILIATION=true
python3 src/multi_strategy_main.py
```

**Watch for:** `✅ Reconciliation PASSED`, `Discrepancies: 0`

---

## Step 3: Verify Success (1 min)

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

---

## Step 4: Commit (1 min)

```bash
git add -A
git commit -m "Phase 5 Day 1 Complete"
git push origin main
```

---

## Done! ✅

**Next run:** 4:15 PM ET today (Day 2)

**Daily command:**
```bash
export ENABLE_BROKER_RECONCILIATION=true && python3 src/multi_strategy_main.py
```

---

## If Issues

**Positions still showing:**
- Wait 5 more minutes, retry Step 1
- Or close manually: https://app.alpaca.markets/paper/dashboard/overview

**Reconciliation fails:**
- Check logs for discrepancies
- Close any phantom positions manually
- Retry Step 2

**Data too old:**
```bash
make update-data
# Wait for completion, then retry Step 2
```
