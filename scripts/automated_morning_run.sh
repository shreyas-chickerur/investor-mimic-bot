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

# Step 1: Sync database with broker state
echo "" | tee -a "$LOG_FILE"
echo "Step 1: Syncing database with broker state..." | tee -a "$LOG_FILE"
python3 scripts/sync_broker_state.py 2>&1 | tee -a "$LOG_FILE"

SYNC_STATUS=$?

if [ $SYNC_STATUS -ne 0 ]; then
    echo "" | tee -a "$LOG_FILE"
    echo "❌ Database sync failed. Aborting automated run." | tee -a "$LOG_FILE"
    exit 1
fi

# Step 2: Run Day 1 with reconciliation
echo "" | tee -a "$LOG_FILE"
echo "Step 2: Running Day 1 execution..." | tee -a "$LOG_FILE"
export ENABLE_BROKER_RECONCILIATION=true
python3 src/execution_engine.py 2>&1 | tee -a "$LOG_FILE"

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
    
    system_health = data.get('system_health', {})
    recon = system_health.get('reconciliation_status', 'UNKNOWN')
    discrep = system_health.get('reconciliation_discrepancies', [])
    discrep_count = len(discrep) if isinstance(discrep, list) else 0
    
    print(f'Reconciliation: {recon}')
    print(f'Discrepancies: {discrep_count}')
    
    if 'PASS' in recon and discrep_count == 0:
        print('\n✅ Execution complete - Reconciliation passed!')
        sys.exit(0)
    else:
        print('\n❌ Reconciliation failed')
        if discrep_count > 0:
            print('Discrepancies:')
            for d in discrep:
                print(f'  - {d}')
        sys.exit(1)
else:
    print(f'❌ No artifact found for {date}')
    sys.exit(1)
" 2>&1 | tee -a "$LOG_FILE"

VERIFY_STATUS=$?

# Final status
if [ $VERIFY_STATUS -eq 0 ]; then
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
