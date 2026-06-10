#!/usr/bin/env python3
"""
diagnose.py — one-command triage for the trading platform.

Designed so a future operator (human or Claude Code) can answer "is the
platform healthy, and if not, what exactly broke and is it recurring?" in
under a minute, without spelunking workflow logs.

Usage:
  python3 scripts/diagnose.py                  # local trading.db / tmp dir
  python3 scripts/diagnose.py --fetch          # pull latest run's DB + health artifacts via gh
  python3 scripts/diagnose.py --db path/to.db  # explicit DB
  make diagnose                                # alias for --fetch

What it checks, in order:
  1. GHA run conclusions for daily_trading.yml — including the 0-second
     "workflow file unparseable" signature that caused the June 2026 outage.
  2. run_history (last 14 runs): one line per run with overall + failed checks.
  3. The latest non-GREEN run: each failed check with detail AND a
     ready-to-paste sqlite3 query for digging deeper.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
from pathlib import Path

REPO = "shreyas-chickerur/investor-mimic-bot"
FETCH_DIR = Path("tmp/diagnose")

# Ready-to-paste deep-dive queries per failed check name (or prefix)
DIG_QUERIES = {
    "reconciliation": (
        'sqlite3 {db} "SELECT snapshot_type, reconciliation_status, discrepancies_json '
        'FROM broker_state ORDER BY created_at DESC LIMIT 6;"'
    ),
    "run_status": (
        'sqlite3 {db} "SELECT run_id, stage, status, error_message FROM run_state '
        'ORDER BY updated_at DESC LIMIT 5;"'
    ),
    "guardrails_clean": (
        'sqlite3 {db} "SELECT strategy_id, raw_signals_count, executed_count '
        'FROM signal_funnel ORDER BY id DESC LIMIT 16;"'
    ),
    "expect:Kill switch did not fire": (
        'sqlite3 {db} "SELECT key, value FROM system_state WHERE key IN '
        "('max_drawdown','peak_portfolio_value','cumulative_pnl');\""
    ),
    "expect:Signals generated (strategies active)": (
        'sqlite3 {db} "SELECT strategy_id, stage, reason_code, COUNT(*) FROM signal_rejections '
        'GROUP BY strategy_id, stage, reason_code ORDER BY COUNT(*) DESC LIMIT 12;"'
    ),
}


def _gh(args: list[str]) -> str:
    return subprocess.run(["gh"] + args, capture_output=True, text=True, timeout=120).stdout.strip()


def check_workflow_runs() -> None:
    """Spot the outage signatures in recent daily_trading runs."""
    print("── GitHub Actions: daily_trading.yml (last 7 runs) " + "─" * 28)
    try:
        out = _gh(
            [
                "run",
                "list",
                "--repo",
                REPO,
                "--workflow",
                "daily_trading.yml",
                "--limit",
                "7",
                "--json",
                "conclusion,createdAt,event,displayTitle,databaseId",
            ]
        )
        runs = json.loads(out) if out else []
    except Exception as exc:
        print(f"  (gh CLI unavailable: {exc})")
        return

    if not runs:
        print("  No runs found")
        return

    unparseable = False
    for r in runs:
        title = r["displayTitle"][:50]
        flag = ""
        # GitHub names a run after the workflow FILE PATH when it cannot
        # parse the file — and the run fails in ~0s. That means the schedule/
        # dispatch is silently dead until the YAML is fixed.
        if ".github/workflows" in r["displayTitle"] and r["conclusion"] == "failure":
            flag = "  ⚠️ WORKFLOW FILE UNPARSEABLE"
            unparseable = True
        print(
            f"  {r['createdAt'][:16]}  {r['event']:<18} {r['conclusion'] or 'running':<9} {title}{flag}"
        )

    if unparseable:
        print(
            "\n  🚨 WORKFLOW FILE UNPARSEABLE — dispatches are being REJECTED.\n"
            "     Fix: run `actionlint .github/workflows/daily_trading.yml` and\n"
            "     `git log -p .github/workflows/daily_trading.yml` to find the bad commit."
        )


def fetch_artifacts() -> Path | None:
    """Download the latest run's run-health + trading-database artifacts."""
    FETCH_DIR.mkdir(parents=True, exist_ok=True)
    try:
        out = _gh(
            [
                "run",
                "list",
                "--repo",
                REPO,
                "--workflow",
                "daily_trading.yml",
                "--limit",
                "5",
                "--json",
                "databaseId,conclusion",
            ]
        )
        runs = json.loads(out) if out else []
        for r in runs:
            run_id = str(r["databaseId"])
            res = subprocess.run(
                [
                    "gh",
                    "run",
                    "download",
                    run_id,
                    "--repo",
                    REPO,
                    "-n",
                    "trading-database",
                    "-D",
                    str(FETCH_DIR),
                ],
                capture_output=True,
                text=True,
                timeout=180,
            )
            if res.returncode == 0:
                subprocess.run(
                    [
                        "gh",
                        "run",
                        "download",
                        run_id,
                        "--repo",
                        REPO,
                        "-n",
                        "run-health",
                        "-D",
                        str(FETCH_DIR),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                print(f"  Fetched artifacts from run {run_id} → {FETCH_DIR}/")
                return FETCH_DIR / "trading.db"
        print("  Could not download artifacts from recent runs")
    except Exception as exc:
        print(f"  (artifact fetch failed: {exc})")
    return None


def show_run_history(db_path: Path) -> str | None:
    """Last-14-runs table. Returns run_id of the latest non-GREEN run."""
    print("\n── run_history (last 14 runs) " + "─" * 49)
    if not db_path.exists():
        print(f"  {db_path} not found — pass --db or use --fetch")
        return None
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT run_id, run_date, overall, status, failed_checks_json, "
            "portfolio_value, n_orders FROM run_history ORDER BY id DESC LIMIT 14"
        ).fetchall()
    except sqlite3.OperationalError:
        print("  run_history table not present (pre-2026-06-11 DB)")
        return None
    finally:
        conn.close()

    if not rows:
        print("  (empty — first run after deployment will populate it)")
        return None

    latest_bad = None
    for r in rows:
        icon = {"GREEN": "✅", "YELLOW": "🟡", "RED": "❌"}.get(r["overall"], "❓")
        failed = json.loads(r["failed_checks_json"] or "[]")
        pv = f"${r['portfolio_value']:,.0f}" if r["portfolio_value"] else "—"
        print(
            f"  {icon} {r['run_date']}  {r['overall']:<6} {r['status'] or '?':<16} "
            f"pv={pv:<10} orders={r['n_orders'] or 0:<3} "
            f"{('failed: ' + ', '.join(failed[:3])) if failed else ''}"
        )
        if r["overall"] != "GREEN" and latest_bad is None:
            latest_bad = r["run_id"]
    return latest_bad


def show_failure_detail(db_path: Path, health_json: Path) -> None:
    report = None
    if health_json.exists():
        try:
            report = json.loads(health_json.read_text())
        except Exception:
            pass
    if not report:
        return
    failed = [c for c in report.get("checks", []) if not c["passed"]]
    if not failed:
        return

    print(
        f"\n── Latest run failures ({report.get('date')}, overall={report.get('overall')}) "
        + "─" * 20
    )
    for c in failed:
        print(f"  ✗ [{c['severity']}] {c['name']}")
        print(f"      {c['detail']}")
        for key, query in DIG_QUERIES.items():
            if c["name"] == key or c["name"].startswith(key):
                print(f"      dig deeper: {query.format(db=db_path)}")
                break
    recurring = report.get("escalation", {}).get("recurring", [])
    if recurring:
        print(f"\n  🔁 RECURRING (≥3 consecutive runs): {recurring}")
        print("     This is a systemic issue, not a transient blip — check the")
        print("     CLAUDE.md runbook section for this check name.")


def main() -> int:
    ap = argparse.ArgumentParser(description="Trading platform triage")
    ap.add_argument("--db", default="trading.db", help="Path to trading.db")
    ap.add_argument(
        "--fetch", action="store_true", help="Download latest run's artifacts via gh CLI"
    )
    ap.add_argument("--no-gha", action="store_true", help="Skip GitHub Actions checks")
    args = ap.parse_args()

    print("=" * 80)
    print("PLATFORM DIAGNOSIS")
    print("=" * 80)

    if not args.no_gha:
        check_workflow_runs()

    db_path = Path(args.db)
    health_json = Path("artifacts/run_health.json")
    if args.fetch:
        fetched = fetch_artifacts()
        if fetched and fetched.exists():
            db_path = fetched
            candidate = FETCH_DIR / "run_health.json"
            if candidate.exists():
                health_json = candidate

    show_run_history(db_path)
    show_failure_detail(db_path, health_json)

    print("\nNext steps: see CLAUDE.md → 'Runbook' for failure-mode playbooks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
