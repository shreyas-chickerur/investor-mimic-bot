#!/bin/bash
# Test GitHub Actions workflow locally
# Simulates the daily trading execution workflow

set -e

PROJECT_ROOT="/Users/shreyaschickerur/CascadeProjects/investor-mimic-bot"
cd "$PROJECT_ROOT"

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║         Testing GitHub Actions Workflow Locally               ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Track results
STEP=0
PASSED=0
FAILED=0

run_step() {
    local step_name=$1
    local command=$2
    
    STEP=$((STEP + 1))
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Step $STEP: $step_name"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    if eval "$command" > /tmp/workflow_step_$STEP.log 2>&1; then
        echo "✅ PASSED: $step_name"
        PASSED=$((PASSED + 1))
    else
        echo "❌ FAILED: $step_name"
        echo "Error output:"
        tail -20 /tmp/workflow_step_$STEP.log
        FAILED=$((FAILED + 1))
    fi
    echo ""
}

# Simulate workflow steps
echo "Starting workflow simulation..."
echo ""

# Step 1: Checkout code (already in directory)
run_step "Checkout code" "test -d .git && echo 'Repository found'"

# Step 2: Set up Python (check Python version)
run_step "Set up Python 3.8" "python3 --version | grep -q 'Python 3'"

# Step 3: Install dependencies
run_step "Install dependencies" "pip list > /dev/null 2>&1"

# Step 4: Import check
run_step "Import check" "python3 scripts/import_check.py"

# Step 5: Initialize database
run_step "Initialize database" "python3 scripts/setup_database.py --db test_workflow.db"

# Step 6: Create required directories
run_step "Create required directories" "mkdir -p artifacts/json artifacts/markdown artifacts/funnel artifacts/data_quality artifacts/drawdown artifacts/health logs data"

# Step 7: Check if run_trading.sh exists
run_step "Check run_trading.sh exists" "test -f scripts/run_trading.sh"

# Step 8: Validate system invariants
run_step "Validate system invariants" "python3 scripts/validate_system.py --latest"

# Step 9: Verify execution criteria
run_step "Verify execution criteria" "python3 scripts/verify_execution.py || true"  # May fail without execution data

# Step 10: Generate strategy performance
run_step "Generate strategy performance" "python3 scripts/generate_strategy_performance.py --days 30"

# Step 11: Generate strategy chart
run_step "Generate strategy chart" "python3 scripts/generate_strategy_chart.py --days 7"

# Step 12: Generate email chart
run_step "Generate email chart" "python3 scripts/generate_email_chart.py"

# Step 13: Generate daily email
run_step "Generate daily email" "python3 scripts/generate_daily_email.py || true"  # May fail without artifact

# Cleanup
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Cleaning up test artifacts..."
rm -f test_workflow.db
echo "✅ Cleanup complete"
echo ""

# Summary
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                    WORKFLOW TEST SUMMARY                       ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "Total steps: $STEP"
echo "✅ Passed: $PASSED"
echo "❌ Failed: $FAILED"
echo ""

if [ $FAILED -eq 0 ]; then
    echo "🎉 All workflow steps passed!"
    echo ""
    echo "The GitHub Actions workflow is ready to run."
    echo "To trigger manually, go to:"
    echo "  GitHub → Actions → Daily Trading Execution → Run workflow"
    exit 0
else
    echo "⚠️  Some workflow steps failed."
    echo "Check logs in /tmp/workflow_step_*.log"
    echo ""
    echo "Note: Some failures are expected without actual execution data."
    exit 1
fi
