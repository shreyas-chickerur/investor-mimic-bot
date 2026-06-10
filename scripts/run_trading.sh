#!/bin/bash
# Automated trading run with pre-flight checks
# Safe for GitHub Actions and cron jobs

# Note: Do NOT use set -e here - we handle exit codes manually

echo "================================================================================"
echo "AUTOMATED TRADING RUN"
echo "================================================================================"
echo "Started: $(date)"
echo ""

# Navigate to project root
cd "$(dirname "$0")/.."

# Status file protocol: STARTED -> MARKET_CLOSED | PREFLIGHT_FAILED |
# EXECUTING -> SUCCESS | EXECUTION_FAILED. Written FIRST so a crash anywhere
# in this script still leaves a status behind — a missing file (UNKNOWN in
# the workflow) now unambiguously means this script never ran, and the final
# health gate fails on anything that isn't SUCCESS or MARKET_CLOSED.
# RUN_STATUS_FILE is overridable for tests.
RUN_STATUS_FILE="${RUN_STATUS_FILE:-/tmp/run_status.txt}"
echo "STARTED" > "$RUN_STATUS_FILE"

# Set default environment variables if not set.
# DATA_VALIDATOR_MAX_AGE_HOURS derives from the single workflow-level
# DATA_MAX_AGE_HOURS knob when present, so staleness has ONE threshold.
export DATA_VALIDATOR_MAX_AGE_HOURS="${DATA_VALIDATOR_MAX_AGE_HOURS:-${DATA_MAX_AGE_HOURS:-80}}"
export ALPACA_PAPER="${ALPACA_PAPER:-true}"
export DRY_RUN="${DRY_RUN:-false}"

echo "Configuration:"
echo "  DRY_RUN: $DRY_RUN"
echo "  ALPACA_PAPER: $ALPACA_PAPER"
echo "  DATA_VALIDATOR_MAX_AGE_HOURS: $DATA_VALIDATOR_MAX_AGE_HOURS"
echo ""

# Run pre-flight checks and capture output
echo "Running pre-flight checks..."
PREFLIGHT_OUTPUT=$(python3 scripts/pre_flight_check.py 2>&1)
PREFLIGHT_EXIT=$?
echo "$PREFLIGHT_OUTPUT"

# Check if market was closed (expected skip)
if echo "$PREFLIGHT_OUTPUT" | grep -q "MARKET CLOSED\|Market closed"; then
    echo "MARKET_CLOSED" > "$RUN_STATUS_FILE"
    echo ""
    echo "================================================================================"
    echo "⏸️  RUN SKIPPED - Market closed (expected)"
    echo "================================================================================"
    echo "Finished: $(date)"
    exit 0
fi

# Check exit code for other failures
if [ $PREFLIGHT_EXIT -ne 0 ]; then
    echo "PREFLIGHT_FAILED" > "$RUN_STATUS_FILE"
    echo ""
    echo "================================================================================"
    echo "❌ PRE-FLIGHT CHECKS FAILED"
    echo "================================================================================"
    echo "Finished: $(date)"
    exit 1
fi

# Pre-flight passed, execute trading
echo "EXECUTING" > "$RUN_STATUS_FILE"
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
    echo "SUCCESS" > "$RUN_STATUS_FILE"
else
    echo "❌ TRADING RUN FAILED (exit code: $EXIT_CODE)"
    echo "EXECUTION_FAILED" > "$RUN_STATUS_FILE"
fi
echo "================================================================================"
echo "Finished: $(date)"

exit $EXIT_CODE
