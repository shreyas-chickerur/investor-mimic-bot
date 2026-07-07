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
        ORDER BY id DESC LIMIT 1
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
        "SELECT portfolio_value, cash FROM broker_state ORDER BY id DESC LIMIT 1",
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


def check_unfilled_opg_rate(conn: sqlite3.Connection, today: str) -> tuple[bool, str]:
    """Yesterday's optimistically-FILLED OPG orders that never actually filled.

    The pre-run broker sync sweeps phantom positions (local-not-at-broker) and
    records the count in system_state. A handful is normal on gap days; a
    burst means the 1% limit buffer is too tight or signals chase gaps.
    """
    row = _q1(conn, "SELECT value FROM system_state WHERE key='unfilled_opg_swept'")
    if not row:
        return True, "no unfilled-OPG sweep data yet"
    try:
        payload = json.loads(row["value"])
        count = int(payload.get("count", 0))
        symbols = payload.get("symbols", [])
        swept_date = payload.get("date", "?")
    except (ValueError, TypeError, KeyError) as exc:
        return True, f"unfilled-OPG payload unreadable ({exc})"
    if count >= 5:
        return False, (
            f"{count} unfilled OPG order(s) swept on {swept_date}: {symbols} — "
            "the 1% limit-on-open buffer may be too tight for current gaps"
        )
    return True, f"{count} unfilled OPG order(s) swept on {swept_date}"


def check_sweep_deploying(conn: sqlite3.Connection, today: str) -> tuple[bool, str]:
    """The cash sweep must actually deploy — its orders must reach the broker.

    The sweep parks idle cash in the index sleeve so cash does not sit at 0%.
    When its orders fail to fill (broker_expired), the DB records an optimistic
    fill that the next run trues up — so reconciliation self-heals and the run
    stays GREEN while cash silently never deploys. That hid a two-week sweep
    outage in June 2026 (OPG orders expired in the opening cross every day).

    This looks at the sweep's most recent *settled* BUY intents (prior days,
    excluding today's not-yet-trued optimistic fill). If the last 3 all expired
    at the broker, the sweep is not deploying and must escalate.
    """
    rows = _qall(
        conn,
        """
        SELECT oi.status, oi.error_code, date(oi.created_at) AS d
        FROM order_intents oi
        JOIN strategies s ON s.id = oi.strategy_id
        WHERE s.name = 'Cash Sweep' AND oi.side = 'BUY' AND date(oi.created_at) < ?
        ORDER BY oi.created_at DESC
        LIMIT 3
        """,
        (today,),
    )
    if len(rows) < 3:
        return True, "not enough settled sweep orders yet"
    expired = [
        r for r in rows if r.get("error_code") == "broker_expired" or r["status"] == "FAILED"
    ]
    if len(expired) == len(rows):
        days = ", ".join(r["d"] for r in rows)
        return False, (
            f"Cash sweep has not deployed: the last {len(rows)} settled sweep BUY "
            f"orders all expired at the broker ({days}). Cash is sitting idle — "
            "check the sweep limit/time-in-force (DAY marketable limit expected)"
        )
    return True, f"sweep deploying ({len(rows) - len(expired)}/{len(rows)} recent orders filled)"


def check_order_fill_rate(conn: sqlite3.Connection, today: str) -> tuple[bool, str]:
    """Platform-wide order fill rate must be healthy — the bot must actually trade.

    OPG limit/market-on-open orders expired in the opening auction cross ~87% of
    the time (126 FAILED vs 19 FILLED buys, 2026-05-20 → 2026-07-02): the
    strategies almost never held positions, paper mode booked optimistic fills,
    and the digest reported phantom trades while the account drifted with SPY
    beta. Fixed by switching all entries/exits to DAY marketable limits
    (see execution failure 2026-07-02).

    Looks at settled BUY intents over the last 10 trading days (excluding
    today's not-yet-trued optimistic fills). Fails if fewer than half filled.
    Immediately after the DAY fix deploys, historical FAILED rows dominate the
    window and this will read RED for a few days — that is correct, it reflects
    reality until real fills accrue.
    """
    rows = _qall(
        conn,
        """
        SELECT status FROM order_intents
        WHERE side = 'BUY' AND status IN ('FILLED', 'FAILED')
          AND date(created_at) < ?
          AND date(created_at) >= date(?, '-14 days')
        ORDER BY created_at DESC
        """,
        (today, today),
    )
    if len(rows) < 5:
        return True, f"not enough settled orders to judge fill rate ({len(rows)})"
    filled = sum(1 for r in rows if r["status"] == "FILLED")
    rate = filled / len(rows)
    if rate < 0.5:
        return False, (
            f"Order fill rate {rate:.0%} ({filled}/{len(rows)} settled buys filled) "
            "over the last 14 days — orders are expiring unfilled. Entries/exits "
            "must use DAY marketable limits, not OPG (auction-only)"
        )
    return True, f"Order fill rate {rate:.0%} ({filled}/{len(rows)} settled buys filled, 14d)"


def check_review_not_overdue(conn: sqlite3.Connection, today: str) -> tuple[bool, str]:
    """Probation caps and parameter plateaus must be revisited quarterly.

    Reads backtesting.next_review_date from trading_config.yaml; once the
    date passes, every run goes YELLOW until the evidence run is done and
    the date is bumped (procedure: docs/research/EVIDENCE_RUNBOOK.md).
    """
    try:
        from src.utils.config_loader import get_config

        due = str(get_config().get("backtesting.next_review_date", "") or "")
    except Exception as exc:
        return True, f"review date unreadable ({exc}) — skipping"
    if not due:
        return True, "no next_review_date configured"
    if today >= due:
        return False, (
            f"Quarterly strategy re-validation was due {due} — run the evidence "
            "pipeline (docs/research/EVIDENCE_RUNBOOK.md) and bump next_review_date"
        )
    return True, f"Next strategy re-validation due {due}"


def check_signals_generated(conn: sqlite3.Connection, today: str) -> tuple[bool, str]:
    """Latest run generated at least 1 signal (strategies are running)."""
    # Latest *trading run* — SYNC rows carry run_id='AUTO_SYNC' which never
    # appears in signal_funnel, and ordering must be by id: legacy rows mix
    # 'YYYY-MM-DDTHH:MM:SS' and 'YYYY-MM-DD HH:MM:SS' created_at formats.
    row = _q1(
        conn,
        """
        SELECT sf.run_id, SUM(sf.raw_signals_count) AS total
        FROM signal_funnel sf
        JOIN (SELECT run_id AS latest_run FROM broker_state
              WHERE snapshot_type != 'SYNC'
              ORDER BY id DESC LIMIT 1) latest
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
    ("Quarterly strategy re-validation not overdue", check_review_not_overdue, "medium"),
    ("Unfilled-OPG rate acceptable", check_unfilled_opg_rate, "medium"),
    ("Cash sweep is deploying", check_sweep_deploying, "high"),
    ("Order fill rate healthy", check_order_fill_rate, "high"),
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


def send_alert(report: dict, db_path: str = "trading.db") -> None:
    """Queue an HTML alert for critical/high expectation failures.

    Alert policy (user decision 2026-06-10): medium-severity failures stay in
    the JSON artifact and daily digest only — a standalone email per quiet-day
    "0 signals" check was pure noise. Delivery goes through the notification
    outbox so this script has no SMTP side effects (the workflow's outbox
    processor sends it).
    """
    failures = [
        r for r in report["results"] if not r["passed"] and r["severity"] in ("critical", "high")
    ]
    if not failures:
        medium = [r for r in report["results"] if not r["passed"]]
        if medium:
            print(f"{len(medium)} medium-severity failure(s) — recorded in JSON, no email")
        return

    try:
        from src.utils.email_notifier import _bullet_list, _kv_rows, build_alert_html

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
        from src.core.database import TradingDatabase

        db = TradingDatabase(db_path=db_path)
        db.enqueue_notification(
            "email",
            "alert",
            f"⚠️ Trading run expectations failed ({report['trading_date']})",
            html,
        )
        print("Alert queued to notification outbox")
    except Exception as exc:
        print(f"[warn] could not queue alert email: {exc}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Exit-code contract
# ---------------------------------------------------------------------------

# Exit-code contract (consumed by daily_trading.yml's "Post-run expectation
# check" step, which fails the job on 1 but NOT on 2):
#   0 = all expectations met
#   1 = one or more CRITICAL expectations failed → the run is untrustworthy,
#       fail the workflow job
#   2 = only HIGH/medium expectations failed (all critical passed) → surfaced
#       as an alert email + YELLOW in run_health, but must NOT fail the job
#       (e.g. fill rate reading low for a few days right after a fix deploys)
EXIT_ALL_OK = 0
EXIT_CRITICAL = 1
EXIT_HIGH_ONLY = 2


def exit_code_from_report(report: dict) -> int:
    """Map a run_checks() report to the process exit code (see contract above)."""
    if report.get("critical_failures", 0) > 0:
        return EXIT_CRITICAL
    if report.get("high_failures", 0) > 0:
        return EXIT_HIGH_ONLY
    return EXIT_ALL_OK


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

    # Queue alert for critical/high failures (medium = JSON + digest only)
    if not args.no_email and not report["all_ok"]:
        send_alert(report, db_path=args.db)

    return exit_code_from_report(report)


if __name__ == "__main__":
    raise SystemExit(main())
