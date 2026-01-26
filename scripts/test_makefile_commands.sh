#!/bin/bash
# Comprehensive test script for all Makefile commands
# Tests each command as a user would run them

set -e  # Exit on error

PROJECT_ROOT="/Users/shreyaschickerur/CascadeProjects/investor-mimic-bot"
cd "$PROJECT_ROOT"

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║        Testing All Makefile Commands                          ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Track results
PASSED=0
FAILED=0
SKIPPED=0

test_command() {
    local cmd=$1
    local description=$2
    local should_skip=$3
    
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Testing: make $cmd"
    echo "Description: $description"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    if [ "$should_skip" = "skip" ]; then
        echo "⏭️  SKIPPED (requires user interaction or long runtime)"
        SKIPPED=$((SKIPPED + 1))
        echo ""
        return
    fi
    
    if make $cmd > /tmp/make_test_$cmd.log 2>&1; then
        echo "✅ PASSED"
        PASSED=$((PASSED + 1))
    else
        echo "❌ FAILED"
        echo "Error output:"
        tail -20 /tmp/make_test_$cmd.log
        FAILED=$((FAILED + 1))
    fi
    echo ""
}

# ============================================================================
# SETUP & INSTALLATION
# ============================================================================
echo "📦 SETUP & INSTALLATION"
echo ""

test_command "help" "Display help menu" ""
test_command "import-check" "Verify all imports" ""
test_command "check-health" "System health check" ""

# ============================================================================
# TESTING
# ============================================================================
echo "🧪 TESTING"
echo ""

test_command "test-unit" "Run unit tests" ""
test_command "test-component" "Run component tests" ""
test_command "test-integration" "Run integration tests" ""
test_command "test-functional" "Run functional tests" "skip"  # May require broker access

# ============================================================================
# DATA MANAGEMENT
# ============================================================================
echo "📊 DATA MANAGEMENT"
echo ""

test_command "clean-data" "Clean cached data" ""

# ============================================================================
# ANALYSIS & REPORTING
# ============================================================================
echo "📈 ANALYSIS & REPORTING"
echo ""

test_command "report" "Generate performance report" ""
test_command "metrics" "Show portfolio metrics" ""

# ============================================================================
# VALIDATION & DEBUGGING
# ============================================================================
echo "✅ VALIDATION & DEBUGGING"
echo ""

test_command "validate" "Validate system invariants" ""
test_command "verify" "Verify execution criteria" ""

# ============================================================================
# MAINTENANCE
# ============================================================================
echo "🧹 MAINTENANCE"
echo ""

test_command "clean-cache" "Clean Python cache" ""
test_command "clean" "Clean temporary files" ""

# ============================================================================
# SUMMARY
# ============================================================================
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                    TEST SUMMARY                                ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "✅ PASSED:  $PASSED"
echo "❌ FAILED:  $FAILED"
echo "⏭️  SKIPPED: $SKIPPED"
echo ""

TOTAL=$((PASSED + FAILED + SKIPPED))
echo "Total commands tested: $TOTAL"
echo ""

if [ $FAILED -eq 0 ]; then
    echo "🎉 All testable commands passed!"
    exit 0
else
    echo "⚠️  Some commands failed. Check logs in /tmp/make_test_*.log"
    exit 1
fi
