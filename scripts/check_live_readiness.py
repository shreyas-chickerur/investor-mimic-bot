#!/usr/bin/env python3
"""
Live-Trading Readiness Gate.

Computes a small set of hard criteria that must ALL pass before paper trading
can be turned off. Designed to be cheap, deterministic, and safe to call from
both the daily email and CLI.

Criteria (intentionally conservative):
    1. Closed trades ............................. >= 30
    2. Win rate .................................. >= 45%
    3. Max drawdown .............................. <= 8%
    4. Profit factor ............................. >= 1.2
    5. Reconciliation clean for last N days ...... >= 14 consecutive days

Returns a dict with each check, the overall verdict, and a single-line summary.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

# Reuse the shared portfolio metrics (Sharpe / drawdown / profit factor)
from performance_tracker import compute_portfolio_metrics  # noqa: E402

REQUIRED_TRADES = 30
MIN_WIN_RATE = 0.45
MAX_ALLOWED_DRAWDOWN = 8.0  # percent (positive number)
MIN_PROFIT_FACTOR = 1.2
REQUIRED_CLEAN_RECON = 14  # consecutive days


def _consecutive_clean_recon_days(db_path: str) -> int:
    """Count consecutive recent days where reconciliation_status was clean."""
    conn = sqlite3.connect(db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT snapshot_date,
                   MAX(CASE WHEN reconciliation_status IN ('PASS','SYNCED','OK')
                            THEN 1 ELSE 0 END) AS clean
            FROM broker_state
            WHERE snapshot_type IN ('RECONCILIATION', 'RECONCILIATION_RETRY',
                                    'END', 'SYNC')
              AND reconciliation_status IS NOT NULL
            GROUP BY snapshot_date
            ORDER BY snapshot_date DESC
        """
        ).fetchall()
    except sqlite3.Error:
        return 0
    finally:
        conn.close()

    streak = 0
    for r in rows:
        if r["clean"]:
            streak += 1
        else:
            break
    return streak


def _check(label: str, value, target, ok: bool, fmt: str = "{}") -> dict:
    return {
        "label": label,
        "value": value,
        "target": target,
        "ok": bool(ok),
        "display": fmt.format(value) if value is not None else "—",
    }


def evaluate_readiness(db_path: str = "trading.db") -> dict:
    metrics = compute_portfolio_metrics(db_path)

    closed = metrics.get("total_trades") or 0
    win_rate = metrics.get("win_rate")
    max_dd = metrics.get("max_drawdown")  # already in percent
    profit_fact = metrics.get("profit_factor")
    clean_streak = _consecutive_clean_recon_days(db_path)

    checks: list[dict] = [
        _check(
            "Closed trades", closed, f">= {REQUIRED_TRADES}", closed >= REQUIRED_TRADES, fmt="{}"
        ),
        _check(
            "Win rate",
            (win_rate or 0) * 100 if win_rate is not None else None,
            f">= {int(MIN_WIN_RATE*100)}%",
            win_rate is not None and win_rate >= MIN_WIN_RATE,
            fmt="{:.1f}%",
        ),
        _check(
            "Max drawdown",
            max_dd,
            f"<= {MAX_ALLOWED_DRAWDOWN:.1f}%",
            max_dd is not None and max_dd <= MAX_ALLOWED_DRAWDOWN,
            fmt="{:.2f}%",
        ),
        _check(
            "Profit factor",
            profit_fact,
            f">= {MIN_PROFIT_FACTOR}",
            profit_fact is not None and profit_fact >= MIN_PROFIT_FACTOR,
            fmt="{:.2f}",
        ),
        _check(
            "Clean reconciliation",
            clean_streak,
            f">= {REQUIRED_CLEAN_RECON} days",
            clean_streak >= REQUIRED_CLEAN_RECON,
            fmt="{} days",
        ),
    ]

    passed = sum(1 for c in checks if c["ok"])
    total = len(checks)
    ready = passed == total

    return {
        "ready": ready,
        "passed": passed,
        "total": total,
        "checks": checks,
        "computed_at": datetime.now().isoformat(timespec="seconds"),
        "summary": (
            "READY to disable paper trading."
            if ready
            else f"NOT READY — {passed}/{total} checks pass."
        ),
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--db", default="trading.db")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    result = evaluate_readiness(args.db)

    if args.json:
        print(json.dumps(result, indent=2))
        return 0 if result["ready"] else 1

    print(result["summary"])
    print(f"  Date: {result['computed_at']}\n")
    for c in result["checks"]:
        mark = "✓" if c["ok"] else "✗"
        print(f"  {mark} {c['label']:<24} {c['display']:<14} (target {c['target']})")
    return 0 if result["ready"] else 1


if __name__ == "__main__":
    sys.exit(main())
