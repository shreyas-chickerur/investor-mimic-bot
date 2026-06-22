#!/usr/bin/env python3
"""
Strategy experiment reviewer — the "did it work?" half of the strategy
changelog. Reads config/strategy_experiments.yaml, and for every experiment
whose review_date has arrived (or all, with --all), evaluates its measurable
success criteria against the recorded result artifacts and assigns a verdict:

  validated     — every criterion met (evidence FOR the change)
  rejected      — results available but a criterion failed (evidence AGAINST)
  inconclusive  — results not yet available / insufficient sample

With --update the verdicts + measured values are written back into the YAML, so
each disposition is traceable to the evidence that produced it. With --db and
--emit-outbox a summary notification is enqueued (the existing email machinery
sends it), so a strategy is never silently abandoned.

Usage:
    python3 scripts/research/review_experiments.py [--all] [--update] \
        [--db trading.db] [--emit-outbox] [--report out.md]
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).parent.parent.parent
REGISTRY = PROJECT_ROOT / "config" / "strategy_experiments.yaml"

_OPS = {
    ">=": lambda a, b: a >= b,
    ">": lambda a, b: a > b,
    "<=": lambda a, b: a <= b,
    "<": lambda a, b: a < b,
    "==": lambda a, b: a == b,
}


def _dotted(obj: dict, path: str) -> Any:
    cur: Any = obj
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def resolve_metric(metric: str, exp: dict, db_path: str | None) -> Any:
    """Resolve a metric to a numeric value, or None if not yet measurable."""
    # Built-in metrics computed by the reviewer.
    if metric == "pairs.passing_count":
        f = PROJECT_ROOT / "data" / "pairs_universe.json"
        if not f.exists():
            return None
        try:
            return len(json.loads(f.read_text()).get("pairs", []))
        except Exception:
            return None
    if metric == "news.distinct_dates":
        if not db_path or not Path(db_path).exists():
            return None
        try:
            con = sqlite3.connect(db_path)
            cur = con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='sentiment_history'"
            )
            if cur.fetchone() is None:
                return 0
            n = con.execute("SELECT COUNT(DISTINCT asof_date) FROM sentiment_history").fetchone()[0]
            con.close()
            return int(n)
        except Exception:
            return None
    # Otherwise: dotted path into the experiment's result_file JSON.
    rf = exp.get("result_file")
    if not rf:
        return None
    p = PROJECT_ROOT / rf
    if not p.exists():
        return None
    try:
        return _dotted(json.loads(p.read_text()), metric)
    except Exception:
        return None


def evaluate(exp: dict, db_path: str | None) -> dict:
    crit_results = []
    all_measurable = True
    all_pass = True
    for c in exp.get("success_criteria", []):
        metric, op, thr = c["metric"], c["op"], c["threshold"]
        val = resolve_metric(metric, exp, db_path)
        if val is None:
            all_measurable = False
            crit_results.append(
                {"metric": metric, "op": op, "threshold": thr, "value": None, "passed": None}
            )
            continue
        passed = _OPS[op](val, thr)
        all_pass = all_pass and passed
        crit_results.append(
            {"metric": metric, "op": op, "threshold": thr, "value": val, "passed": bool(passed)}
        )
    if not all_measurable:
        verdict = "inconclusive"
    elif all_pass:
        verdict = "validated"
    else:
        verdict = "rejected"
    return {"verdict": verdict, "criteria": crit_results, "reviewed_date": date.today().isoformat()}


def _due(exp: dict, force_all: bool) -> bool:
    if exp.get("status") not in (None, "pending"):
        return False
    if force_all:
        return True
    try:
        return datetime.strptime(exp["review_date"], "%Y-%m-%d").date() <= date.today()
    except Exception:
        return False


def format_report(reviews: list[tuple[dict, dict]]) -> str:
    lines = [f"# Strategy experiment review — {date.today().isoformat()}", ""]
    if not reviews:
        lines.append("_No experiments due for review._")
        return "\n".join(lines)
    for exp, ev in reviews:
        emoji = {"validated": "✅", "rejected": "❌", "inconclusive": "⏳"}[ev["verdict"]]
        lines.append(f"## {emoji} {exp['id']} — **{ev['verdict'].upper()}**")
        lines.append(
            f"- strategy: `{exp['strategy']}`  ·  started {exp['date_started']}  ·  review {exp['review_date']}"
        )
        lines.append(f"- hypothesis: {exp.get('hypothesis','').strip()}")
        for c in ev["criteria"]:
            mark = {True: "PASS", False: "FAIL", None: "n/a"}[c["passed"]]
            val = "—" if c["value"] is None else c["value"]
            lines.append(
                f"  - [{mark}] `{c['metric']}` {c['op']} {c['threshold']} (measured: {val})"
            )
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="Review all pending, ignore review_date")
    ap.add_argument("--update", action="store_true", help="Write verdicts back into the registry")
    ap.add_argument("--db", default=None, help="trading.db (for DB-backed metrics + outbox)")
    ap.add_argument("--emit-outbox", action="store_true", help="Enqueue a notification per verdict")
    ap.add_argument("--report", default=None, help="Write the markdown report to this path")
    args = ap.parse_args()

    registry = yaml.safe_load(REGISTRY.read_text())
    experiments = registry.get("experiments", [])

    reviews: list[tuple[dict, dict]] = []
    for exp in experiments:
        if _due(exp, args.all):
            reviews.append((exp, evaluate(exp, args.db)))

    report = format_report(reviews)
    print(report)
    if args.report:
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(report)

    if args.update and reviews:
        for exp, ev in reviews:
            # Only finalise a status when there's a real verdict; leave
            # inconclusive experiments pending so they're re-checked later.
            if ev["verdict"] != "inconclusive":
                exp["status"] = ev["verdict"]
            exp["results"] = ev
        REGISTRY.write_text(yaml.safe_dump(registry, sort_keys=False, width=100))
        print(f"\nUpdated {REGISTRY}")

    if args.emit_outbox and reviews and args.db and Path(args.db).exists():
        try:
            sys.path.insert(0, str(PROJECT_ROOT))
            from src.core.database import TradingDatabase

            db = TradingDatabase(args.db)
            actionable = [r for r in reviews if r[1]["verdict"] != "inconclusive"]
            if actionable:
                subj = f"🧪 Strategy experiment review — {len(actionable)} verdict(s)"
                html = "<pre>" + report.replace("<", "&lt;") + "</pre>"
                db.enqueue_notification("email", "alert", subj, html)
                print("Enqueued review notification to outbox.")
        except Exception as exc:
            print(f"(outbox enqueue skipped: {exc})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
