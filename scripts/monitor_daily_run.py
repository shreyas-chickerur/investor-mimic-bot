#!/usr/bin/env python3
"""
Daily run monitor: downloads the latest GHA trading-database artifact,
checks the four tracked metrics, and prints a machine-readable JSON verdict
so the autonomous cron agent knows what (if anything) to fix.

Exit codes:
  0 — all green, no action needed
  1 — warnings surfaced (agent should investigate)
  2 — error fetching artifact or DB

Metrics tracked (matches the "what to watch" list from 2026-06-29):
  1. dual_momentum_signals   — has Dual Momentum generated ANY signals since
                               its 300-day data-window fix landed?
  2. alpha_deployment_pct    — what fraction of portfolio is in alpha (non-sweep)
                               positions? Target > 10%.
  3. rsi_signals_trend       — is RSI signal count per day trending up after
                               the rsi_entry_threshold 35→38 widening?
  4. phantom_pnl_cleaned     — are there still trade_pnl_detail rows with
                               entry_price <= 0?

Usage:
  python3 scripts/monitor_daily_run.py [--db path/to/trading.db]
  # Without --db: downloads the latest 'trading-database' artifact via gh CLI.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# Artifact download
# ---------------------------------------------------------------------------


def download_latest_artifact(dest_dir: Path) -> Path | None:
    """Download trading-database artifact from the latest successful daily run."""
    try:
        # Find latest successful run
        result = subprocess.run(
            [
                "gh",
                "run",
                "list",
                "--workflow",
                "daily_trading.yml",
                "--status",
                "success",
                "--limit",
                "1",
                "--json",
                "databaseId",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        runs = json.loads(result.stdout)
        if not runs:
            print("ERROR: no successful daily runs found", file=sys.stderr)
            return None
        run_id = runs[0]["databaseId"]

        subprocess.run(
            ["gh", "run", "download", str(run_id), "-n", "trading-database", "-D", str(dest_dir)],
            capture_output=True,
            text=True,
            check=True,
        )
        db_candidates = list(dest_dir.glob("**/*.db"))
        if not db_candidates:
            print("ERROR: no .db file found in downloaded artifact", file=sys.stderr)
            return None
        return db_candidates[0]
    except subprocess.CalledProcessError as e:
        print(f"ERROR downloading artifact: {e.stderr}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# Metric checks
# ---------------------------------------------------------------------------


def check_dual_momentum_signals(cur: sqlite3.Cursor) -> dict:
    """Has Dual Momentum generated any signals since 2026-06-29 (data-window fix)?"""
    fix_date = "2026-06-29"
    cur.execute(
        """
        SELECT COUNT(*) FROM signals s
        JOIN strategies st ON s.strategy_id = st.id
        WHERE LOWER(st.name) LIKE '%dual%'
          AND s.generated_at >= ?
        """,
        (fix_date,),
    )
    count = cur.fetchone()[0]

    # Also check last 7 days specifically
    week_ago = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")
    cur.execute(
        """
        SELECT COUNT(*) FROM signals s
        JOIN strategies st ON s.strategy_id = st.id
        WHERE LOWER(st.name) LIKE '%dual%'
          AND s.generated_at >= ?
        """,
        (week_ago,),
    )
    last_7d = cur.fetchone()[0]

    status = "green" if count > 0 else "red"
    return {
        "metric": "dual_momentum_signals",
        "status": status,
        "signals_since_fix": count,
        "signals_last_7d": last_7d,
        "note": (
            "Dual Momentum generating signals normally"
            if count > 0
            else "ZERO signals since 300-day data-window fix — investigate strategy or data"
        ),
    }


def check_alpha_deployment(cur: sqlite3.Cursor) -> dict:
    """What % of portfolio is in alpha (non-sweep, non-BROKER_SYNC) positions?"""
    # Latest portfolio value from broker_state
    cur.execute("SELECT portfolio_value FROM broker_state ORDER BY created_at DESC LIMIT 1")
    row = cur.fetchone()
    portfolio_value = float(row[0]) if row else 0.0

    # Alpha positions = positions excluding Cash Sweep and BROKER_SYNC
    cur.execute(
        """
        SELECT SUM(p.market_value) FROM positions p
        JOIN strategies s ON p.strategy_id = s.id
        WHERE s.name NOT IN ('Cash Sweep', 'BROKER_SYNC')
          AND p.shares != 0
        """
    )
    alpha_row = cur.fetchone()
    alpha_value = float(alpha_row[0] or 0)

    alpha_pct = (alpha_value / portfolio_value * 100) if portfolio_value > 0 else 0.0
    status = "green" if alpha_pct >= 10 else ("yellow" if alpha_pct >= 5 else "red")

    return {
        "metric": "alpha_deployment_pct",
        "status": status,
        "alpha_value": round(alpha_value, 0),
        "portfolio_value": round(portfolio_value, 0),
        "alpha_pct": round(alpha_pct, 1),
        "note": (
            f"Alpha deployment {alpha_pct:.1f}% — target ≥10%"
            + (" ✓" if status == "green" else " ⚠ underdeployed")
        ),
    }


def check_rsi_signals_trend(cur: sqlite3.Cursor) -> dict:
    """Is the RSI daily signal count trending up after threshold widening (2026-06-29)?"""
    fix_date = "2026-06-29"

    # Count RSI signals per calendar day for the last 14 days
    cur.execute(
        """
        SELECT DATE(s.generated_at) as day, COUNT(*) as n
        FROM signals s
        JOIN strategies st ON s.strategy_id = st.id
        WHERE LOWER(st.name) LIKE '%rsi%'
          AND s.generated_at >= DATE('now', '-14 days')
        GROUP BY day ORDER BY day
        """,
    )
    rows = cur.fetchall()
    daily = {r[0]: r[1] for r in rows}

    # Split into before/after fix
    before = [v for d, v in daily.items() if d < fix_date]
    after = [v for d, v in daily.items() if d >= fix_date]

    avg_before = sum(before) / len(before) if before else 0
    avg_after = sum(after) / len(after) if after else 0

    improving = avg_after >= avg_before or not before
    status = "green" if improving else "yellow"

    return {
        "metric": "rsi_signals_trend",
        "status": status,
        "avg_signals_per_day_before_fix": round(avg_before, 1),
        "avg_signals_per_day_after_fix": round(avg_after, 1),
        "daily_breakdown": daily,
        "note": (
            f"RSI signals: {avg_before:.1f}/day before fix → {avg_after:.1f}/day after"
            + (" (improving ✓)" if improving else " (not improving ⚠)")
        ),
    }


def check_phantom_pnl(cur: sqlite3.Cursor) -> dict:
    """Are there still trade_pnl_detail rows with entry_price <= 0?"""
    cur.execute("SELECT COUNT(*) FROM trade_pnl_detail WHERE entry_price <= 0")
    count = cur.fetchone()[0]
    status = "green" if count == 0 else "red"
    return {
        "metric": "phantom_pnl_cleaned",
        "status": status,
        "zero_basis_rows": count,
        "note": (
            "Phantom P&L rows fully purged ✓"
            if count == 0
            else f"{count} zero-basis row(s) remain — DB migration may not have run yet"
        ),
    }


def check_signal_rejection_breakdown(cur: sqlite3.Cursor) -> dict:
    """Top rejection reasons for the last 7 days — surfaces new bottlenecks."""
    cur.execute(
        """
        SELECT reason_code, COUNT(*) as n
        FROM signal_rejections
        WHERE created_at >= DATE('now', '-7 days')
        GROUP BY reason_code
        ORDER BY n DESC
        LIMIT 10
        """
    )
    rows = cur.fetchall()
    breakdown = {str(r[0]): r[1] for r in rows}
    top = rows[0] if rows else (None, 0)

    # Flag if a single rejection reason dominates (>40% of all rejections)
    total = sum(r[1] for r in rows)
    dominant = total > 0 and top[1] / total > 0.4

    return {
        "metric": "rejection_breakdown_7d",
        "status": "yellow" if dominant else "green",
        "total_rejections": total,
        "breakdown": breakdown,
        "note": (
            f"Top rejection: {top[0]} ({top[1]}/{total})"
            + (" — DOMINANT bottleneck ⚠" if dominant else "")
            if total > 0
            else "No signal rejections in last 7 days"
        ),
    }


def check_run_streak(cur: sqlite3.Cursor) -> dict:
    """How many of the last 5 runs were GREEN/YELLOW vs RED?"""
    cur.execute(
        """
        SELECT run_date, overall, status
        FROM run_history
        ORDER BY id DESC LIMIT 5
        """
    )
    rows = cur.fetchall()
    failed = [(r[0], r[1], r[2]) for r in rows if r[1] not in ("GREEN", "YELLOW")]
    status = "green" if not failed else ("yellow" if len(failed) < 3 else "red")
    return {
        "metric": "run_streak",
        "status": status,
        "last_5_runs": [{"date": r[0], "overall": r[1], "status": r[2]} for r in rows],
        "failed_runs": failed,
        "note": (
            "Last 5 runs all GREEN/YELLOW ✓"
            if not failed
            else f"{len(failed)} of last 5 runs were RED — {failed}"
        ),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", help="Path to local trading.db (skip artifact download)")
    args = parser.parse_args()

    if args.db:
        db_path = Path(args.db)
    else:
        tmp = Path(tempfile.mkdtemp(prefix="monitor_"))
        print(f"Downloading latest trading-database artifact to {tmp} …", file=sys.stderr)
        db_path = download_latest_artifact(tmp)
        if not db_path:
            sys.exit(2)

    print(f"Using DB: {db_path}", file=sys.stderr)

    conn = sqlite3.connect(str(db_path), timeout=10)
    cur = conn.cursor()

    results = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "db_path": str(db_path),
        "checks": [],
    }

    for check_fn in [
        check_dual_momentum_signals,
        check_alpha_deployment,
        check_rsi_signals_trend,
        check_phantom_pnl,
        check_signal_rejection_breakdown,
        check_run_streak,
    ]:
        try:
            result = check_fn(cur)
            results["checks"].append(result)
        except Exception as e:
            results["checks"].append(
                {
                    "metric": check_fn.__name__,
                    "status": "error",
                    "note": str(e),
                }
            )

    conn.close()

    overall = "green"
    for c in results["checks"]:
        s = c.get("status", "green")
        if s == "red":
            overall = "red"
        elif s in ("yellow", "error") and overall == "green":
            overall = "yellow"
    results["overall"] = overall

    print(json.dumps(results, indent=2))

    sys.exit(0 if overall == "green" else 1)


if __name__ == "__main__":
    main()
