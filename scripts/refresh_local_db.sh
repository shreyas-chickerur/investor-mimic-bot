#!/usr/bin/env bash
# Refresh local trading.db with the latest production snapshot from a
# successful GHA daily_trading.yml run.
#
# The local DB drifts whenever GHA runs (which it does every day on
# main) because the workflow's DB only lives inside the runner. Without
# this, scripts/generate_daily_email.py and any local diagnostics show
# stale state — e.g., on 2026-05-28 the local DB was 30 days behind
# production despite the workflow succeeding daily.
#
# Usage:
#   scripts/refresh_local_db.sh           # pull from most recent successful run
#   scripts/refresh_local_db.sh <run_id>  # pull from a specific run
#
# Requires: gh CLI authenticated to the repo.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

RUN_ID="${1:-}"
if [[ -z "$RUN_ID" ]]; then
  echo "Looking up most recent successful daily_trading.yml run..."
  RUN_ID="$(gh run list --workflow=daily_trading.yml --status=success -L 1 --json databaseId -q '.[0].databaseId')"
  if [[ -z "$RUN_ID" ]]; then
    echo "ERROR: No successful runs found." >&2
    exit 1
  fi
fi

echo "Run ID: $RUN_ID"

STAGING="$(mktemp -d)"
trap 'rm -rf "$STAGING"' EXIT

echo "Downloading trading-database artifact..."
gh run download "$RUN_ID" -n trading-database -D "$STAGING"

if [[ ! -f "$STAGING/trading.db" ]]; then
  echo "ERROR: trading.db not found in artifact." >&2
  exit 1
fi

BACKUP="trading.db.backup_$(date +%Y%m%d_%H%M%S)"
if [[ -f trading.db ]]; then
  cp trading.db "$BACKUP"
  echo "Local DB backed up to $BACKUP"
fi

cp "$STAGING/trading.db" trading.db
echo "Local trading.db replaced with production snapshot from run $RUN_ID"

# Quick state summary so the caller sees what they got.
echo ""
echo "=== Production state ==="
sqlite3 trading.db "SELECT 'positions: ' || COUNT(*) FROM positions WHERE shares != 0;"
sqlite3 trading.db "SELECT 'trades: ' || COUNT(*) || ' (last: ' || MAX(executed_at) || ')' FROM trades;"
sqlite3 trading.db "SELECT 'closed SELLs: ' || COUNT(*) || ', realized P&L: ' || ROUND(SUM(pnl), 2) FROM trades WHERE action='SELL' AND pnl IS NOT NULL;"
