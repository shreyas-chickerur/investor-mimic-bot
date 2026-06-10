#!/usr/bin/env python3
"""
build_run_health.py — single source of truth for a run's health.

Consolidates the run status file, expectation results, guardrail results,
reconciliation state, signal funnel, and order activity into ONE
machine-readable artifact (run_health.json) and ONE run_history DB row.

Why: diagnosing the June 2026 outage meant stitching together five artifacts
and the workflow log. After this, `make diagnose` (or any Claude Code
session) reads run_health.json / run_history and knows in seconds what
failed, how severe it was, and whether it is RECURRING (same check failed in
the last 3 runs — escalated into email subjects via $GITHUB_OUTPUT).

Usage:
  python3 scripts/diagnostics/build_run_health.py \
      --db trading.db \
      --status-file /tmp/run_status.txt \
      --expectations artifacts/diagnostics/expect_check.json \
      --guardrails artifacts/diagnostics/post_run_guardrails.json \
      --recon-status PASS --sync-ok '' --drift-resolved '' \
      --out artifacts/run_health.json
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

SCHEMA_VERSION = 1
RECURRENCE_WINDOW = 3  # same check failing this many consecutive runs = recurring


# ---------------------------------------------------------------------------
# Collectors
# ---------------------------------------------------------------------------


def read_status(status_file: str) -> str:
    p = Path(status_file)
    if not p.exists():
        return "UNKNOWN"
    return p.read_text().strip() or "UNKNOWN"


def read_json(path: str) -> dict | None:
    p = Path(path)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text())
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def collect_db_facts(db_path: str) -> dict:
    facts: dict = {
        "run_id": None,
        "portfolio_value": None,
        "reconciliation_status": None,
        "funnel": {},
        "orders": {},
        "errors_today": 0,
    }
    if not Path(db_path).exists():
        return facts
    conn = sqlite3.connect(db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT run_id, portfolio_value FROM broker_state "
            "WHERE snapshot_type != 'SYNC' AND run_id != 'AUTO_SYNC' "
            "ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        if row is None:
            row = conn.execute(
                "SELECT run_id, portfolio_value FROM broker_state "
                "ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
        if row:
            facts["run_id"] = row["run_id"]
            facts["portfolio_value"] = row["portfolio_value"]

        if facts["run_id"]:
            recon = conn.execute(
                "SELECT reconciliation_status FROM broker_state "
                "WHERE run_id=? AND snapshot_type IN ('RECONCILIATION', 'RECONCILIATION_RETRY') "
                "ORDER BY created_at DESC, id DESC LIMIT 1",
                (facts["run_id"],),
            ).fetchone()
            facts["reconciliation_status"] = recon[0] if recon else None

            facts["funnel"] = {
                r["strategy_id"]: {
                    "raw": r["raw_signals_count"],
                    "executed": r["executed_count"],
                }
                for r in conn.execute(
                    "SELECT strategy_id, raw_signals_count, executed_count "
                    "FROM signal_funnel WHERE run_id=?",
                    (facts["run_id"],),
                ).fetchall()
            }

        today = datetime.now().strftime("%Y-%m-%d")
        order_rows = conn.execute(
            "SELECT status, COUNT(*) AS n FROM order_intents "
            "WHERE created_at LIKE ? GROUP BY status",
            (f"{today}%",),
        ).fetchall()
        facts["orders"] = {r["status"]: r["n"] for r in order_rows}

        try:
            facts["errors_today"] = conn.execute(
                "SELECT COUNT(*) FROM error_log WHERE created_at LIKE ?",
                (f"{today}%",),
            ).fetchone()[0]
        except sqlite3.OperationalError:
            pass  # error_log table may not exist on older DBs
    finally:
        conn.close()
    return facts


# ---------------------------------------------------------------------------
# Health computation
# ---------------------------------------------------------------------------


def build_checks(
    status: str,
    expectations: dict | None,
    guardrails: dict | None,
    db_facts: dict,
    recon_status_arg: str,
    drift_resolved: str,
) -> list[dict]:
    checks: list[dict] = []

    if status == "MARKET_CLOSED":
        checks.append(
            {
                "name": "run_status",
                "source": "gate",
                "passed": True,
                "severity": "critical",
                "detail": "market closed — expected skip",
            }
        )
        return checks

    checks.append(
        {
            "name": "run_status",
            "source": "gate",
            "passed": status == "SUCCESS",
            "severity": "critical",
            "detail": f"run status is {status}",
        }
    )

    if expectations:
        for r in expectations.get("results", []):
            checks.append(
                {
                    "name": f"expect:{r['label']}",
                    "source": "expectation",
                    "passed": bool(r["passed"]),
                    "severity": r.get("severity", "medium"),
                    "detail": r.get("detail", ""),
                }
            )
    else:
        checks.append(
            {
                "name": "expectations_report_present",
                "source": "expectation",
                "passed": False,
                "severity": "high",
                "detail": "expect_check.json missing — expectation step did not run",
            }
        )

    if guardrails:
        crit = guardrails.get("critical_failures", [])
        checks.append(
            {
                "name": "guardrails_clean",
                "source": "guardrail",
                "passed": not crit,
                "severity": "critical",
                "detail": "; ".join(str(c) for c in crit) or "all guardrails passed",
            }
        )
    else:
        checks.append(
            {
                "name": "guardrails_report_present",
                "source": "guardrail",
                "passed": False,
                "severity": "critical",
                "detail": "post_run_guardrails.json missing while trading executed",
            }
        )

    recon = recon_status_arg or db_facts.get("reconciliation_status") or "UNKNOWN"
    recon_ok = recon != "FAIL" or drift_resolved == "true"
    checks.append(
        {
            "name": "reconciliation",
            "source": "reconciliation",
            "passed": recon_ok,
            "severity": "critical",  # unresolved drift halts trust in all positions
            "detail": f"status={recon}, drift_resolved={drift_resolved or 'n/a'}",
        }
    )

    return checks


def compute_overall(checks: list[dict]) -> str:
    """RED = a critical check failed (gate goes red). YELLOW = high/medium
    failures worth attention but the run is fundamentally sound. GREEN = clean."""
    failed = [c for c in checks if not c["passed"]]
    if any(c["severity"] == "critical" for c in failed):
        return "RED"
    if failed:
        return "YELLOW"
    return "GREEN"


def detect_recurrences(db_path: str, failed_names: list[str]) -> list[str]:
    """Check names that also failed in each of the last RECURRENCE_WINDOW-1 runs."""
    if not failed_names or not Path(db_path).exists():
        return []
    conn = sqlite3.connect(db_path, timeout=10)
    try:
        rows = conn.execute(
            "SELECT failed_checks_json FROM run_history ORDER BY id DESC LIMIT ?",
            (RECURRENCE_WINDOW - 1,),
        ).fetchall()
    finally:
        conn.close()
    if len(rows) < RECURRENCE_WINDOW - 1:
        return []
    prior_failures = [set(json.loads(r[0] or "[]")) for r in rows]
    return [name for name in failed_names if all(name in prev for prev in prior_failures)]


def persist_run_history(db_path: str, report: dict) -> None:
    conn = sqlite3.connect(db_path, timeout=10)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO run_history "
            "(run_id, run_date, overall, status, failed_checks_json, "
            " portfolio_value, n_orders, data_freshness_hours) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                report["run_id"] or f"unknown_{report['date']}",
                report["date"],
                report["overall"],
                report["status"],
                json.dumps([c["name"] for c in report["checks"] if not c["passed"]]),
                report["portfolio_value"],
                sum(report["orders"].values()) if report["orders"] else 0,
                report["data_freshness_hours"],
            ),
        )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description="Build consolidated run health report")
    ap.add_argument("--db", default="trading.db")
    ap.add_argument("--status-file", default="/tmp/run_status.txt")
    ap.add_argument("--expectations", default="artifacts/diagnostics/expect_check.json")
    ap.add_argument("--guardrails", default="artifacts/diagnostics/post_run_guardrails.json")
    ap.add_argument("--data-file", default="data/training_data.csv")
    ap.add_argument("--recon-status", default="")
    ap.add_argument("--drift-resolved", default="")
    ap.add_argument("--out", default="artifacts/run_health.json")
    args = ap.parse_args()

    status = read_status(args.status_file)
    expectations = read_json(args.expectations)
    guardrails = read_json(args.guardrails)
    db_facts = collect_db_facts(args.db)

    data_age_hours = None
    data_file = Path(args.data_file)
    if data_file.exists():
        data_age_hours = round(
            (datetime.now() - datetime.fromtimestamp(data_file.stat().st_mtime)).total_seconds()
            / 3600,
            1,
        )

    checks = build_checks(
        status, expectations, guardrails, db_facts, args.recon_status, args.drift_resolved
    )
    overall = compute_overall(checks)
    failed_names = [c["name"] for c in checks if not c["passed"]]
    recurring = detect_recurrences(args.db, failed_names)

    report = {
        "schema_version": SCHEMA_VERSION,
        "run_id": db_facts["run_id"],
        "date": datetime.now().strftime("%Y-%m-%d"),
        "generated_at": datetime.now().isoformat(),
        "overall": overall,
        "status": status,
        "checks": checks,
        "funnel": db_facts["funnel"],
        "orders": db_facts["orders"],
        "errors_today": db_facts["errors_today"],
        "portfolio_value": db_facts["portfolio_value"],
        "data_freshness_hours": data_age_hours,
        "escalation": {"recurring": recurring},
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2))

    try:
        persist_run_history(args.db, report)
    except Exception as exc:
        print(f"[warn] could not persist run_history: {exc}", file=sys.stderr)

    # Surface recurrence to the workflow for email-subject escalation
    gh_output = os.environ.get("GITHUB_OUTPUT")
    if gh_output:
        with open(gh_output, "a") as f:
            f.write(f"overall={overall}\n")
            f.write(f"recurring={'true' if recurring else 'false'}\n")
            f.write(f"recurring_checks={','.join(recurring)}\n")

    icon = {"GREEN": "✅", "YELLOW": "🟡", "RED": "❌"}[overall]
    print(f"{icon} Run health: {overall} (status={status}, run_id={report['run_id']})")
    for c in checks:
        mark = "✓" if c["passed"] else "✗"
        print(f"  {mark} [{c['severity']:<8}] {c['name']}: {c['detail']}")
    if recurring:
        print(f"\n🔁 RECURRING failures (≥{RECURRENCE_WINDOW} consecutive runs): {recurring}")
    print(f"\nSaved: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
