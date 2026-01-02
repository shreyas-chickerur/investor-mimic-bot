#!/bin/bash
# Automated trading run with pre-flight checks
# Safe for GitHub Actions and cron jobs

set -e  # Exit on error

echo "================================================================================"
echo "AUTOMATED TRADING RUN"
echo "================================================================================"
echo "Started: $(date)"
echo ""

# Navigate to project root
cd "$(dirname "$0")/.."

# Set default environment variables if not set
export DATA_VALIDATOR_MAX_AGE_HOURS="${DATA_VALIDATOR_MAX_AGE_HOURS:-96}"
export ALPACA_PAPER="${ALPACA_PAPER:-true}"
export DRY_RUN="${DRY_RUN:-false}"

echo "Configuration:"
echo "  DRY_RUN: $DRY_RUN"
echo "  ALPACA_PAPER: $ALPACA_PAPER"
echo "  DATA_VALIDATOR_MAX_AGE_HOURS: $DATA_VALIDATOR_MAX_AGE_HOURS"
echo ""

# Run pre-flight checks
echo "Running pre-flight checks..."
python3 scripts/pre_flight_check.py

# Check exit code
if [ $? -eq 0 ]; then
    echo ""
    echo "================================================================================"
    echo "EXECUTING TRADING SYSTEM"
    echo "================================================================================"
    echo ""
    
    # Run the trading system
    python3 src/execution_engine.py
    
    EXIT_CODE=$?
    
    echo ""
    echo "================================================================================"
    if [ $EXIT_CODE -eq 0 ]; then
        echo "✅ TRADING RUN COMPLETED SUCCESSFULLY"
    else
        echo "❌ TRADING RUN FAILED (exit code: $EXIT_CODE)"
    fi
    echo "================================================================================"
    echo "Finished: $(date)"
    
    exit $EXIT_CODE
else
    echo ""
    echo "================================================================================"
    echo "⏸️  TRADING RUN SKIPPED (pre-flight checks failed)"
    echo "================================================================================"
    echo "Finished: $(date)"
    
    # Exit 0 so GitHub Actions doesn't mark as failed
    # (skipping on weekends/holidays is expected behavior)
    exit 0
fi
