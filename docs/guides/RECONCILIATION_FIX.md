# Reconciliation Fix Guide

## Problem
Morning runs were failing with reconciliation errors showing 4 discrepancies between local database and Alpaca broker state.

## Root Cause
Local database was empty while broker had 2 positions (CVX, TMO), causing:
1. CVX exists in broker but not locally
2. TMO exists in broker but not locally
3. Cash mismatch
4. Portfolio value mismatch

## Solution
Created `scripts/sync_broker_state.py` to sync local database with broker state before each run.

### Updated Morning Run Flow
1. **Sync database** - Fetch broker state and update local database
2. **Run trading** - Execute multi-strategy system
3. **Verify reconciliation** - Check artifact for reconciliation status

### Manual Sync
If reconciliation fails, run:
```bash
# Using the sync script directly
python3 scripts/sync_broker_state.py

# Or using Makefile
make sync-db
```

This will:
- Clear local positions
- Fetch current broker positions
- Update database to match broker
- Verify sync was successful

### Verification
Check reconciliation status:
```bash
python3 -c "
import sys
sys.path.insert(0, 'src')
from broker_reconciler import BrokerReconciler
import sqlite3

reconciler = BrokerReconciler()
broker_state = reconciler.get_broker_state()

conn = sqlite3.connect('trading.db')
cursor = conn.cursor()
cursor.execute('SELECT symbol, shares, avg_price FROM positions')
local_positions = {row[0]: {'qty': int(row[1]), 'avg_price': float(row[2])} for row in cursor.fetchall()}
conn.close()

success, discrepancies = reconciler.reconcile_daily(local_positions, broker_state['cash'])
print(f'Reconciliation: {\"✅ PASS\" if success else \"❌ FAIL\"}')
if discrepancies:
    for d in discrepancies:
        print(f'  - {d}')
"
```

## Changes Made
1. Created `scripts/sync_broker_state.py` - Database sync tool
2. Updated `scripts/automated_morning_run.sh`:
   - Step 1: Sync database instead of just checking positions
   - Step 3: Fixed artifact verification to look in `system_health.reconciliation_discrepancies`
3. Updated `Makefile` - `make sync-db` now uses new sync script
4. Updated documentation:
   - `docs/guides/LIVE_TRADING_RUNBOOK.md` - Reconciliation resolution steps
   - `docs/guides/USAGE_GUIDE.md` - Manual reconciliation and troubleshooting
   - `README.md` - Hard reconciliation gate features

## Related Documentation
- **Runbook:** `docs/guides/LIVE_TRADING_RUNBOOK.md` (Section: Reconciliation Failures)
- **Usage Guide:** `docs/guides/USAGE_GUIDE.md` (Section: Reconciliation Gate & Troubleshooting)
- **Morning Run Script:** `scripts/automated_morning_run.sh`
