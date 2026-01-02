#!/bin/bash
# Automated Morning Execution Script for Phase 5 Day 1
# Runs at 6:30 AM PST (9:30 AM ET) to execute Day 1 after positions clear.
# Logs all output for review.

# Configuration
PROJECT_DIR="/Users/shreyaschickerur/CascadeProjects/investor-mimic-bot"
LOG_DIR="$PROJECT_DIR/logs"
DATE=$(date +%Y-%m-%d)
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="$LOG_DIR/automated_run_$TIMESTAMP.log"

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# Start logging
echo "========================================" | tee -a "$LOG_FILE"
echo "Automated Morning Run - $DATE" | tee -a "$LOG_FILE"
echo "Started at: $(date)" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"

# Change to project directory
cd "$PROJECT_DIR" || exit 1

# Load environment variables from .env file
echo "" | tee -a "$LOG_FILE"
echo "Loading environment variables..." | tee -a "$LOG_FILE"
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
    echo "✅ Environment loaded from .env" | tee -a "$LOG_FILE"
else
    echo "❌ .env file not found!" | tee -a "$LOG_FILE"
    exit 1
fi

# Verify credentials are set
if [ -z "$ALPACA_API_KEY" ] || [ -z "$ALPACA_SECRET_KEY" ]; then
    echo "❌ Alpaca credentials not found in environment!" | tee -a "$LOG_FILE"
    exit 1
fi
echo "✅ Alpaca credentials verified" | tee -a "$LOG_FILE"

# Step 1: Verify positions cleared
echo "" | tee -a "$LOG_FILE"
echo "Step 1: Verifying broker positions cleared..." | tee -a "$LOG_FILE"
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
    sys.exit(0)
else:
    print(f'\n⚠️ {len(s[\"positions\"])} positions remain - aborting')
    sys.exit(1)
" 2>&1 | tee -a "$LOG_FILE"

POSITIONS_CHECK=$?

if [ $POSITIONS_CHECK -ne 0 ]; then
    echo "" | tee -a "$LOG_FILE"
    echo "❌ Positions not cleared. Aborting automated run." | tee -a "$LOG_FILE"
    echo "Please check manually and run when ready." | tee -a "$LOG_FILE"
    exit 1
fi

# Step 2: Run Day 1 with reconciliation
echo "" | tee -a "$LOG_FILE"
echo "Step 2: Running Day 1 execution..." | tee -a "$LOG_FILE"
export ENABLE_BROKER_RECONCILIATION=true
python3 src/multi_strategy_main.py 2>&1 | tee -a "$LOG_FILE"

RUN_STATUS=$?

# Step 3: Verify success
echo "" | tee -a "$LOG_FILE"
echo "Step 3: Verifying execution success..." | tee -a "$LOG_FILE"
python3 -c "
import json
from datetime import datetime
from pathlib import Path
import sys

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
        sys.exit(0)
    else:
        print('\n❌ Reconciliation failed')
        sys.exit(1)
else:
    print(f'❌ No artifact found for {date}')
    sys.exit(1)
" 2>&1 | tee -a "$LOG_FILE"

VERIFY_STATUS=$?

# Step 4: Commit results if successful
if [ $VERIFY_STATUS -eq 0 ]; then
    echo "" | tee -a "$LOG_FILE"
    echo "Step 4: Committing results..." | tee -a "$LOG_FILE"
    git add -A
    git commit -m "Phase 5 Day 1 Complete (Automated)" 2>&1 | tee -a "$LOG_FILE"
    git push origin main 2>&1 | tee -a "$LOG_FILE"
    
    echo "" | tee -a "$LOG_FILE"
    echo "✅ Automated morning run completed successfully!" | tee -a "$LOG_FILE"
else
    echo "" | tee -a "$LOG_FILE"
    echo "❌ Automated morning run failed. Check logs." | tee -a "$LOG_FILE"
fi

# Summary
echo "" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"
echo "Completed at: $(date)" | tee -a "$LOG_FILE"
echo "Log file: $LOG_FILE" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"

exit $VERIFY_STATUS
