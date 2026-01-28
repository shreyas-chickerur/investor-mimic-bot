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

# Run pre-flight checks without capturing to see errors
echo "Running pre-flight checks..."
python3 scripts/pre_flight_check.py
PREFLIGHT_EXIT=$?

# Check if market was closed (expected skip)
if echo "$PREFLIGHT_OUTPUT" | grep -q "MARKET CLOSED.*expected"; then
    echo "MARKET_CLOSED" > /tmp/run_status.txt
    echo ""
    echo "================================================================================"
    echo "⏸️  RUN SKIPPED - Market closed (expected)"
    echo "================================================================================"
    echo "Finished: $(date)"
    exit 0
fi

# Check exit code for other failures
if [ $PREFLIGHT_EXIT -ne 0 ]; then
    echo "PREFLIGHT_FAILED" > /tmp/run_status.txt
    echo ""
    echo "================================================================================"
    echo "❌ PRE-FLIGHT CHECKS FAILED"
    echo "================================================================================"
    echo "Finished: $(date)"
    exit 1
fi

# Pre-flight passed, execute trading
echo "EXECUTING" > /tmp/run_status.txt
echo ""
echo "================================================================================"
echo "EXECUTING TRADING SYSTEM"
echo "================================================================================"
echo ""

# Run the trading system
python3 src/core/execution_engine.py

EXIT_CODE=$?

echo ""
echo "================================================================================"
if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ TRADING RUN COMPLETED SUCCESSFULLY"
    echo "SUCCESS" > /tmp/run_status.txt
else
    echo "❌ TRADING RUN FAILED (exit code: $EXIT_CODE)"
    echo "EXECUTION_FAILED" > /tmp/run_status.txt
fi
echo "================================================================================"
echo "Finished: $(date)"

exit $EXIT_CODE
