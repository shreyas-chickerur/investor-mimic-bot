#!/usr/bin/env python3
"""
post_run_expect.py — after-run expectation checks.

Reads trading.db and verifies the conditions that should hold after every
successful trading run. Emails a structured alert when any expectation fails,
and writes a machine-readable report to artifacts/diagnostics/expect_check.json.

Exit codes:
  0  all expectations met
  1  one or more critical expectations failed
  2  one or more high-severity expectations failed (critical all passed)

Run:
  python3 scripts/post_run_expect.py --db trading.db
  python3 scripts/post_run_expect.py --db trading.db --out /tmp/expect.json
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _q1(conn: sqlite3.Connection, sql: str, params=()) -> dict:
    conn.row_factory = sqlite3.Row
    row = conn.execute(sql, params).fetchone()
    return dict(row) if row else {}


def _qall(conn: sqlite3.Connection, sql: str, params=()) -> list[dict]:
    conn.row_factory = sqlite3.Row
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------


def check_run_completed(conn: sqlite3.Connection, today: str) -> tuple[bool, str]:
    """Most recent run finished with SUCCESS, not HALTED or FAILED."""
    row = _q1(
        conn,
        "SELECT run_id, stage, status, updated_at FROM run_state ORDER BY updated_at DESC LIMIT 1",
    )
    if not row:
        return False, "No run_state rows found — DB may be empty or corrupt"
    status = row.get("status", "")
    run_id = row.get("run_id", "?")
    if status == "SUCCESS":
        return True, f"Run {run_id} completed successfully"
    return False, f"Run {run_id} ended with status={status} (expected SUCCESS)"


def check_kill_switch_not_fired(conn: sqlite3.Connection, today: str) -> tuple[bool, str]:
    """Most recent run was NOT halted by the kill switch."""
    row = _q1(
        conn,
        "SELECT run_id, stage, status FROM run_state ORDER BY updated_at DESC LIMIT 1",
    )
    if row.get("stage") == "KILL_SWITCH":
        return False, (
            f"Kill switch fired for run {row.get('run_id')} — "
            "check drawdown level and consecutive_failures count"
        )
    return True, "Kill switch did not fire"


def check_reconciliation(conn: sqlite3.Connection, today: str) -> tuple[bool, str]:
    """Latest reconciliation snapshot shows PASS."""
    row = _q1(
        conn,
        """
        SELECT reconciliation_status, run_id, created_at
        FROM broker_state
        WHERE snapshot_type IN ('RECONCILIATION', 'RECONCILIATION_RETRY', 'END')
        ORDER BY created_at DESC LIMIT 1
        """,
    )
    if not row:
        return False, "No reconciliation snapshot found — trading may have been halted before recon"
    status = row.get("reconciliation_status", "UNKNOWN")
    if status == "PASS":
        return True, f"Reconciliation PASS (run {row.get('run_id')})"
    return False, f"Reconciliation {status} for run {row.get('run_id')} at {row.get('created_at')}"


def check_portfolio_value(conn: sqlite3.Connection, today: str) -> tuple[bool, str]:
    """Portfolio value is above $90k (sanity check — flags catastrophic loss)."""
    row = _q1(
        conn,
        "SELECT portfolio_value, cash FROM broker_state ORDER BY created_at DESC LIMIT 1",
    )
    if not row:
        return False, "No broker_state row found"
    val = float(row.get("portfolio_value") or 0)
    if val >= 90_000:
        return True, f"Portfolio value ${val:,.2f}"
    return False, f"Portfolio value ${val:,.2f} is below $90k — review for unexpected large loss"


def check_drawdown(conn: sqlite3.Connection, today: str) -> tuple[bool, str]:
    """Max drawdown stored in system_state is < 5% (percent units, e.g. 4.9)."""
    row = _q1(conn, "SELECT value FROM system_state WHERE key='max_drawdown'")
    if not row:
        return True, "max_drawdown not yet set (first run)"
    try:
        dd = float(row["value"])
    except (ValueError, TypeError):
        return False, f"max_drawdown value in DB is not numeric: {row['value']!r}"
    if dd < 5.0:
        return True, f"Max drawdown {dd:.2f}% is within the 5% kill-switch threshold"
    return False, (
        f"Max drawdown {dd:.2f}% exceeds 5% — kill switch should have fired. "
        "If it didn't, check kill_switch_service.py"
    )


def check_signals_generated(conn: sqlite3.Connection, today: str) -> tuple[bool, str]:
    """Latest run generated at least 1 signal (strategies are running)."""
    row = _q1(
        conn,
        """
        SELECT sf.run_id, SUM(sf.raw_signals_count) AS total
        FROM signal_funnel sf
        JOIN (SELECT run_id AS latest_run FROM broker_state ORDER BY created_at DESC LIMIT 1) latest
          ON sf.run_id = latest.latest_run
        """,
    )
    total = int(row.get("total") or 0)
    run_id = row.get("run_id", "?")
    if total > 0:
        return True, f"Run {run_id}: {total} raw signal(s) generated"
    return False, (
        f"Run {run_id}: 0 signals generated — strategies may all be in WATCHING state "
        "or market data is stale"
    )


def check_snapshot_fresh(conn: sqlite3.Connection, today: str) -> tuple[bool, str]:
    """daily_portfolio_snapshot was updated today."""
    row = _q1(
        conn,
        "SELECT snapshot_date, portfolio_value FROM daily_portfolio_snapshot "
        "ORDER BY snapshot_date DESC LIMIT 1",
    )
    if not row:
        return False, "No daily_portfolio_snapshot rows — snapshot was never logged"
    snap_date = row.get("snapshot_date", "")
    if snap_date == today:
        return True, f"Portfolio snapshot recorded for {today}"
    return False, (
        f"Latest snapshot is from {snap_date}, not today ({today}) — "
        "runner_main artifact block may have crashed"
    )


def check_no_critical_errors(conn: sqlite3.Connection, today: str) -> tuple[bool, str]:
    """No critical errors logged in the last 24 hours."""
    try:
        row = _q1(
            conn,
            "SELECT COUNT(*) AS c FROM error_log WHERE occurred_at >= datetime('now','-24 hours')",
        )
        count = int(row.get("c") or 0)
        if count == 0:
            return True, "No errors in error_log in the last 24 hours"
        return False, f"{count} error(s) logged in error_log — check artifacts/error_log"
    except sqlite3.OperationalError:
        return True, "error_log table absent — no errors recorded"


def check_consecutive_failures(conn: sqlite3.Connection, today: str) -> tuple[bool, str]:
    """Consecutive failed/halted runs < 3 (kill switch threshold)."""
    rows = _qall(
        conn,
        "SELECT status FROM run_state ORDER BY updated_at DESC LIMIT 5",
    )
    streak = 0
    for r in rows:
        if r["status"] in ("FAILED", "HALTED"):
            streak += 1
        else:
            break
    if streak == 0:
        return True, "No consecutive failures"
    if streak < 3:
        return False, (
            f"{streak} consecutive HALTED/FAILED run(s) — "
            f"1 more will trigger the kill switch (threshold=3)"
        )
    return False, (
        f"{streak} consecutive failures — kill switch should have fired on the 3rd. "
        "Check get_consecutive_failed_runs logic."
    )


# ---------------------------------------------------------------------------
# Expectation registry  (severity: "critical" | "high" | "medium")
# ---------------------------------------------------------------------------

EXPECTATIONS = [
    ("Run completed (not HALTED/FAILED)", check_run_completed, "critical"),
    ("Kill switch did not fire", check_kill_switch_not_fired, "critical"),
    ("Reconciliation passed", check_reconciliation, "high"),
    ("Portfolio value > $90k", check_portfolio_value, "critical"),
    ("Max drawdown < 5%", check_drawdown, "critical"),
    ("Signals generated (strategies active)", check_signals_generated, "medium"),
    ("Daily snapshot recorded", check_snapshot_fresh, "high"),
    ("No critical errors today", check_no_critical_errors, "medium"),
    ("Consecutive failures < 3", check_consecutive_failures, "high"),
]


# ---------------------------------------------------------------------------
# Report builder
# ---------------------------------------------------------------------------


def run_checks(db_path: str) -> dict:
    today = date.today().isoformat()
    conn = sqlite3.connect(db_path, timeout=10)

    results = []
    for label, fn, severity in EXPECTATIONS:
        try:
            passed, detail = fn(conn, today)
        except Exception as exc:
            passed = False
            detail = f"Check threw an exception: {exc}"
        results.append(
            {
                "label": label,
                "passed": passed,
                "detail": detail,
                "severity": severity,
            }
        )

    conn.close()

    critical_failures = [r for r in results if not r["passed"] and r["severity"] == "critical"]
    high_failures = [r for r in results if not r["passed"] and r["severity"] == "high"]
    medium_failures = [r for r in results if not r["passed"] and r["severity"] == "medium"]
    all_failures = [r for r in results if not r["passed"]]

    return {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "trading_date": today,
        "passed": len([r for r in results if r["passed"]]),
        "total": len(results),
        "all_ok": len(all_failures) == 0,
        "critical_failures": len(critical_failures),
        "high_failures": len(high_failures),
        "medium_failures": len(medium_failures),
        "results": results,
    }


def format_report(report: dict) -> str:
    """Plain-text summary formatted for pasting to Claude."""
    lines = [
        f"=== POST-RUN EXPECTATION CHECK  {report['trading_date']} ===",
        f"Passed: {report['passed']}/{report['total']}",
        "",
    ]
    failures = [r for r in report["results"] if not r["passed"]]
    if not failures:
        lines.append("✅ ALL EXPECTATIONS MET — run completed as expected")
    else:
        lines.append(f"❌ {len(failures)} EXPECTATION(S) FAILED:")
        for r in failures:
            lines.append(f"  [{r['severity'].upper()}] {r['label']}")
            lines.append(f"         {r['detail']}")
    lines.append("")
    lines.append("--- All checks ---")
    for r in report["results"]:
        icon = "✓" if r["passed"] else "✗"
        lines.append(f"  {icon} [{r['severity']:<8}] {r['label']}")
        if not r["passed"]:
            lines.append(f"           → {r['detail']}")
    return "\n".join(lines)


def send_alert(report: dict) -> None:
    """Send HTML alert email if any expectations failed."""
    failures = [r for r in report["results"] if not r["passed"]]
    if not failures:
        return

    try:
        from src.utils.email_notifier import EmailNotifier, _bullet_list, _kv_rows, build_alert_html

        severity_color = "#dc3545"  # red for critical, orange for high
        if not any(r["severity"] == "critical" for r in failures):
            severity_color = "#e65100"

        rows_html = _kv_rows(
            [
                ("Date", report["trading_date"]),
                ("Passed", f"{report['passed']}/{report['total']} checks"),
                ("Critical failures", str(report["critical_failures"])),
                ("High failures", str(report["high_failures"])),
            ]
        )
        failure_list = _bullet_list(
            [
                f"<strong>[{r['severity'].upper()}]</strong> {r['label']}: {r['detail']}"
                for r in failures
            ]
        )
        body = (
            rows_html
            + "<h4 style='margin:16px 0 6px;color:#555'>What failed</h4>"
            + failure_list
            + "<p style='color:#555;font-size:13px;margin:12px 0 0'>"
            "Run <code>python3 scripts/read_snapshot.py</code> locally or check "
            "the GHA artifacts for full diagnostics.</p>"
        )
        html = build_alert_html(
            f"⚠️ Post-run check: {len(failures)} expectation(s) failed",
            body,
            accent_color=severity_color,
        )
        notifier = EmailNotifier()
        if not notifier.enabled:
            print("[warn] email credentials not configured — alert not sent", file=sys.stderr)
            return
        notifier.send_alert(f"⚠️ Trading run expectations failed ({report['trading_date']})", html)
        print("Alert email sent")
    except Exception as exc:
        print(f"[warn] could not send alert email: {exc}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description="Post-run expectation checks")
    ap.add_argument("--db", default="trading.db", help="Path to trading.db")
    ap.add_argument(
        "--out",
        default="artifacts/diagnostics/expect_check.json",
        help="Output JSON path",
    )
    ap.add_argument("--no-email", action="store_true", help="Skip alert email")
    args = ap.parse_args()

    if not Path(args.db).exists():
        print(f"ERROR: {args.db} not found", file=sys.stderr)
        return 1

    report = run_checks(args.db)

    # Print human-readable summary (easy to paste to Claude)
    print(format_report(report))

    # Save machine-readable JSON for GHA artifacts
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2))
    print(f"\nSaved: {out_path}")

    # Send alert if anything failed
    if not args.no_email and not report["all_ok"]:
        send_alert(report)

    # Exit codes: 0=all ok, 1=critical failure, 2=high failure only
    if report["critical_failures"] > 0:
        return 1
    if report["high_failures"] > 0:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
