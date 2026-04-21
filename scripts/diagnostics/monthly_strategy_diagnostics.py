#!/usr/bin/env python3
import argparse
import json
import sqlite3
from datetime import datetime
from pathlib import Path


def stage(i: int, total: int, message: str) -> None:
    width = 20
    filled = int(width * i / total)
    bar = "#" * filled + "-" * (width - filled)
    print(f"[{i}/{total}] [{bar}] {message}", flush=True)


def fetch_rows(conn: sqlite3.Connection, query: str, params=()):
    cur = conn.cursor()
    cur.execute(query, params)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def run_report(db_path: str, window_days: int, context_days: int):
    conn = sqlite3.connect(db_path)

    report = {
        "generated_at": datetime.now().isoformat(),
        "db_path": str(Path(db_path).resolve()),
        "window_days": window_days,
        "context_days": context_days,
    }

    stage(1, 6, "Collecting baseline counts")
    report["baseline"] = {
        "sqlite_now": fetch_rows(conn, "select datetime('now') as now")[0]["now"],
        "strategies": fetch_rows(conn, "select count(*) as n from strategies")[0]["n"],
        "signals_window": fetch_rows(
            conn,
            "select count(*) as n from signals where generated_at >= datetime('now', ?)",
            (f"-{window_days} days",),
        )[0]["n"],
        "closed_trades_window": fetch_rows(
            conn,
            "select count(*) as n from trades where executed_at >= datetime('now', ?) and pnl is not null",
            (f"-{window_days} days",),
        )[0]["n"],
        "funnel_rows_window": fetch_rows(
            conn,
            "select count(*) as n from signal_funnel where created_at >= datetime('now', ?)",
            (f"-{window_days} days",),
        )[0]["n"],
        "rejections_window": fetch_rows(
            conn,
            "select count(*) as n from signal_rejections where created_at >= datetime('now', ?)",
            (f"-{window_days} days",),
        )[0]["n"],
    }

    stage(2, 6, f"Computing {window_days}-day trade performance by strategy")
    report["trades_by_strategy_window"] = fetch_rows(
        conn,
        """
        select s.name strategy,
               count(*) closed_trades,
               sum(case when t.pnl > 0 then 1 else 0 end) wins,
               round(100.0 * sum(case when t.pnl > 0 then 1 else 0 end) / nullif(count(*), 0), 1) win_rate,
               round(sum(t.pnl), 2) total_pnl
        from trades t
        join strategies s on s.id = t.strategy_id
        where t.executed_at >= datetime('now', ?)
          and t.pnl is not null
        group by s.name
        order by total_pnl asc
        """,
        (f"-{window_days} days",),
    )

    stage(3, 6, f"Computing {window_days}-day signal and funnel volume")
    report["signals_by_strategy_window"] = fetch_rows(
        conn,
        """
        select s.name strategy,
               count(*) total_signals,
               sum(case when sg.terminal_state='EXECUTED' then 1 else 0 end) executed_signals
        from signals sg
        join strategies s on s.id = sg.strategy_id
        where sg.generated_at >= datetime('now', ?)
        group by s.name
        order by total_signals desc
        """,
        (f"-{window_days} days",),
    )
    report["funnel_by_strategy_window"] = fetch_rows(
        conn,
        """
        select strategy_name,
               sum(raw_signals_count) raw,
               sum(after_regime_count) after_regime,
               sum(after_correlation_count) after_corr,
               sum(after_risk_count) after_risk,
               sum(executed_count) executed
        from signal_funnel
        where created_at >= datetime('now', ?)
        group by strategy_name
        order by raw desc
        """,
        (f"-{window_days} days",),
    )

    stage(4, 6, f"Computing top rejection reasons in last {window_days} days")
    report["top_rejections_window"] = fetch_rows(
        conn,
        """
        select s.name strategy, sr.stage, sr.reason_code, count(*) cnt
        from signal_rejections sr
        join strategies s on s.id = sr.strategy_id
        where sr.created_at >= datetime('now', ?)
        group by s.name, sr.stage, sr.reason_code
        order by cnt desc
        limit 20
        """,
        (f"-{window_days} days",),
    )

    stage(5, 6, f"Computing context window ({context_days} days) for root-cause pattern")
    report["funnel_by_strategy_context"] = fetch_rows(
        conn,
        """
        select strategy_name,
               sum(raw_signals_count) raw,
               sum(after_regime_count) after_regime,
               sum(after_correlation_count) after_corr,
               sum(after_risk_count) after_risk,
               sum(executed_count) executed,
               max(date(created_at)) last_seen
        from signal_funnel
        where created_at >= datetime('now', ?)
        group by strategy_name
        order by raw desc
        """,
        (f"-{context_days} days",),
    )
    report["top_rejections_context"] = fetch_rows(
        conn,
        """
        select s.name strategy, sr.stage, sr.reason_code, count(*) cnt, max(date(sr.created_at)) last_seen
        from signal_rejections sr
        join strategies s on s.id = sr.strategy_id
        where sr.created_at >= datetime('now', ?)
        group by s.name, sr.stage, sr.reason_code
        order by cnt desc
        limit 20
        """,
        (f"-{context_days} days",),
    )

    stage(6, 6, "Collecting last-activity timestamps")
    report["last_activity"] = {
        "last_signal": fetch_rows(conn, "select max(datetime(generated_at)) as ts from signals")[0]["ts"],
        "last_trade": fetch_rows(conn, "select max(datetime(executed_at)) as ts from trades")[0]["ts"],
        "last_funnel": fetch_rows(conn, "select max(datetime(created_at)) as ts from signal_funnel")[0]["ts"],
        "last_rejection": fetch_rows(conn, "select max(datetime(created_at)) as ts from signal_rejections")[0]["ts"],
    }

    conn.close()
    print("[done] Diagnostics complete.", flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description="Run monthly strategy diagnostics with progress output")
    parser.add_argument("--db", default="trading.db", help="Path to SQLite trading DB")
    parser.add_argument("--window-days", type=int, default=30, help="Primary analysis window")
    parser.add_argument("--context-days", type=int, default=120, help="Wider context window")
    parser.add_argument("--out", default="", help="Optional output JSON path")
    args = parser.parse_args()

    report = run_report(args.db, args.window_days, args.context_days)

    print("\n=== BASELINE ===")
    print(json.dumps(report["baseline"], indent=2))
    print("\n=== TRADES (WINDOW) ===")
    print(json.dumps(report["trades_by_strategy_window"], indent=2))
    print("\n=== SIGNALS (WINDOW) ===")
    print(json.dumps(report["signals_by_strategy_window"], indent=2))
    print("\n=== FUNNEL (WINDOW) ===")
    print(json.dumps(report["funnel_by_strategy_window"], indent=2))
    print("\n=== TOP REJECTIONS (WINDOW) ===")
    print(json.dumps(report["top_rejections_window"], indent=2))
    print("\n=== FUNNEL (CONTEXT) ===")
    print(json.dumps(report["funnel_by_strategy_context"], indent=2))
    print("\n=== TOP REJECTIONS (CONTEXT) ===")
    print(json.dumps(report["top_rejections_context"], indent=2))
    print("\n=== LAST ACTIVITY ===")
    print(json.dumps(report["last_activity"], indent=2))

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2))
        print(f"\nSaved report to: {out_path}")


if __name__ == "__main__":
    main()
