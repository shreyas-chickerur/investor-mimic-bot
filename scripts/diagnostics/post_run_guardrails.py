#!/usr/bin/env python3
"""Post-run guardrails to prevent silent liveness and accounting failures."""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Dict, List


CANONICAL_STRATEGIES = [
    "RSI Mean Reversion",
    "ML Momentum",
    "Earnings Drift",
    "Factor Momentum",
]


def stage(i: int, total: int, message: str) -> None:
    width = 18
    filled = int(width * i / total)
    bar = "#" * filled + "-" * (width - filled)
    print(f"[{i}/{total}] [{bar}] {message}", flush=True)


def read_status(status_file: Path) -> str:
    if not status_file.exists():
        return "UNKNOWN"
    return status_file.read_text().strip()


def query_rows(conn: sqlite3.Connection, sql: str, params=()) -> List[Dict]:
    cur = conn.cursor()
    cur.execute(sql, params)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate post-run liveness and funnel invariants")
    parser.add_argument("--db", default="trading.db")
    parser.add_argument("--status-file", default="/tmp/run_status.txt")
    parser.add_argument("--max-idle-hours", type=int, default=48)
    parser.add_argument("--out", default="artifacts/diagnostics/post_run_guardrails.json")
    args = parser.parse_args()

    status = read_status(Path(args.status_file))
    if status == "MARKET_CLOSED":
        print("[guardrails] MARKET_CLOSED status detected; skipping liveness assertions.")
        return 0

    conn = sqlite3.connect(args.db)

    report: Dict = {
        "status": status,
        "critical_failures": [],
        "warnings": [],
        "latest_run_id": None,
    }

    stage(1, 4, "Loading latest run context")
    run_rows = query_rows(
        conn,
        "select run_id, max(created_at) as last_seen from broker_state group by run_id order by last_seen desc limit 1",
    )
    if not run_rows:
        report["critical_failures"].append("No broker_state rows found; trading run likely did not persist")
    else:
        report["latest_run_id"] = run_rows[0]["run_id"]

    stage(2, 4, "Checking canonical strategy funnel presence")
    if report["latest_run_id"]:
        funnel_rows = query_rows(
            conn,
            """
            select strategy_name, raw_signals_count, after_regime_count,
                   after_correlation_count, after_risk_count, executed_count
            from signal_funnel where run_id = ?
            """,
            (report["latest_run_id"],),
        )
        by_name = {r["strategy_name"]: r for r in funnel_rows}
        missing = [s for s in CANONICAL_STRATEGIES if s not in by_name]
        if missing:
            report["critical_failures"].append(
                f"Missing signal_funnel rows for canonical strategies: {missing}"
            )
        report["funnel_rows"] = funnel_rows

    stage(3, 4, "Validating funnel monotonic invariants")
    for row in report.get("funnel_rows", []):
        raw = int(row["raw_signals_count"] or 0)
        regime = int(row["after_regime_count"] or 0)
        corr = int(row["after_correlation_count"] or 0)
        risk = int(row["after_risk_count"] or 0)
        executed = int(row["executed_count"] or 0)
        if not (raw >= regime >= corr >= risk >= executed >= 0):
            report["critical_failures"].append(
                f"Funnel invariant violation for {row['strategy_name']}: "
                f"raw={raw}, regime={regime}, corr={corr}, risk={risk}, executed={executed}"
            )

    stage(4, 4, "Checking dominant rejection patterns (30d warning)")
    rej_rows = query_rows(
        conn,
        """
        select stage, reason_code, count(*) as cnt
        from signal_rejections
        where created_at >= datetime('now', '-30 days')
        group by stage, reason_code
        order by cnt desc
        """,
    )
    total_rej = sum(int(r["cnt"]) for r in rej_rows)
    if total_rej >= 10 and rej_rows:
        top = rej_rows[0]
        ratio = int(top["cnt"]) / total_rej
        if ratio >= 0.70:
            report["warnings"].append(
                f"Rejections are dominated by {top['stage']}:{top['reason_code']} "
                f"({top['cnt']}/{total_rej}, {ratio:.0%})"
            )

    conn.close()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2))

    print(json.dumps(report, indent=2), flush=True)
    print(f"Saved guardrail report: {out_path}", flush=True)

    if report["critical_failures"]:
        print("[guardrails] CRITICAL FAILURES DETECTED", flush=True)
        return 1

    print("[guardrails] All critical checks passed", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
