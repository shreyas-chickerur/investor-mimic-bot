"""Reproduce what DynamicAllocator sees during a live run, so we can
explain why all 7 active strategies ended up with exactly $11,668 each
(equal split) despite the backtest_sharpe_priors config having
distinguishing values.

Usage: python3 scripts/adhoc/probe_allocator.py
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import yaml  # type: ignore[import-untyped]

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.regime.dynamic_allocator import DynamicAllocator  # noqa: E402


def main() -> None:
    conn = sqlite3.connect(str(ROOT / "trading.db"))
    rows = conn.execute(
        "SELECT id, name FROM strategies WHERE status='active' ORDER BY id"
    ).fetchall()
    ids = [r[0] for r in rows]
    name_by_id = {r[0]: r[1] for r in rows}

    perf: dict[int, list[float]] = {}
    for sid in ids:
        rows = conn.execute(
            "SELECT gross_pnl_pct FROM trade_pnl_detail "
            "WHERE strategy_id=? AND exit_date>=date('now','-60 days')",
            (sid,),
        ).fetchall()
        perf[sid] = [float(r[0]) for r in rows]

    print("=== Live return counts (60d, from trade_pnl_detail) ===")
    for sid in ids:
        print(f"  {name_by_id[sid]:25s} n={len(perf[sid])}")

    cfg = yaml.safe_load((ROOT / "config" / "trading_config.yaml").read_text())
    raw_priors = cfg["strategies"].get("backtest_sharpe_priors", {}) or {}

    ckmap = {v.lower().replace(" ", "_"): k for k, v in name_by_id.items()}
    prior_sharpes: dict[int, float] = {}
    for k, v in raw_priors.items():
        if k in ckmap:
            prior_sharpes[ckmap[k]] = float(v)

    print("\n=== Priors actually wired to strategy IDs ===")
    for sid in ids:
        marker = "" if sid in prior_sharpes else "   <-- NO PRIOR"
        print(f"  {name_by_id[sid]:25s} prior={prior_sharpes.get(sid, '-')}{marker}")

    raw_overrides = cfg["strategies"].get("allocation_overrides", {}) or {}
    per_strategy_max: dict[int, float] = {}
    for k, v in raw_overrides.items():
        if k in ckmap:
            per_strategy_max[ckmap[k]] = float(v)

    print("\n=== Per-strategy max caps wired ===")
    for sid in ids:
        cap = per_strategy_max.get(sid, "(default)")
        print(f"  {name_by_id[sid]:25s} max={cap}")

    alloc = DynamicAllocator(
        total_capital=81676.0,
        max_allocation_pct=0.35,
        min_allocation_pct=0.05,
    )
    result = alloc.calculate_allocations(
        ids,
        perf,
        per_strategy_max=per_strategy_max,
        prior_sharpes=prior_sharpes,
    )

    print("\n=== Allocator output ===")
    total = sum(result.values())
    for sid, cap in result.items():
        pct = (cap / total) * 100 if total else 0
        print(f"  {name_by_id[sid]:25s} ${cap:>10,.0f}  ({pct:5.1f}%)")
    print(f"  {'TOTAL':25s} ${total:>10,.0f}")


if __name__ == "__main__":
    main()
