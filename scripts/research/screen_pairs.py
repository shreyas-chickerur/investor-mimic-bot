#!/usr/bin/env python3
"""
Pairs universe screener — replaces the 5 hand-picked pairs with a data-driven
search, and aligns the force-exit horizon to each pair's measured half-life.

Why this exists (EXP-2026-06-22-pairs-universe-screen, see
docs/research/STRATEGY_CHANGELOG.md): the original 5 hardcoded pairs all failed
the gates — the one cointegrated pair (V/MA) mean-reverts over ~100 days while
the strategy force-exited at 20. Two research-backed fixes:

  1. Search the WHOLE universe for cointegrated pairs, restricted to
     SAME-SECTOR candidates so the cointegration has an economic basis and we
     control the multiple-comparisons false-positive rate (testing every
     C(n,2) pair at 5% would surface ~1-in-20 spurious pairs). Selection uses
     the stricter 1% Engle-Granger critical value.
  2. Set each pair's max-hold to a MULTIPLE of its half-life (HOLD_MULT), so a
     fast-reverting pair is actually given time to revert before the force-exit.
     "If the half-life is 20 days, a 5-day window won't capture the reversion"
     — half-life sets the lookback/hold, not an arbitrary constant.

Output: data/pairs_universe.json — the production strategy loads this (falling
back to its built-in defaults when the file is absent).

Usage:
    python3 scripts/research/screen_pairs.py [--data data/extended_historical_data.csv]
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))  # sibling scripts (validate_pairs)
sys.path.insert(0, str(Path(__file__).parent.parent.parent))  # project root (src.*)

from validate_pairs import (  # noqa: E402
    EG_CRITICAL,
    engle_granger_tstat,
    simulate_pair,
    spread_half_life,
)

from src.data.sector_map import sector_of  # noqa: E402

# Selection gates (intentionally stricter than the per-pair validator):
MIN_OVERLAP_ROWS = 504  # ≥ ~2y of overlapping history
HALF_LIFE_MAX = 15.0  # so 3× hold stays ≤ ~45d (practical capital horizon)
HOLD_MULT = 3.0  # force-exit at ~3 half-lives (research: a few half-lives)
MAX_HOLD_CAP = 45
MAX_HOLD_FLOOR = 10
MIN_TRADES = 10
MIN_PF = 1.1
EG_SELECT = EG_CRITICAL["1%"]  # -3.90: stricter than 5% to absorb multiple testing

OUTPUT_PATH = Path("data/pairs_universe.json")


def _aligned_max_hold(half_life: float) -> int:
    return int(min(MAX_HOLD_CAP, max(MAX_HOLD_FLOOR, round(HOLD_MULT * half_life))))


def screen(data_path: str) -> dict:
    df = pd.read_csv(data_path, index_col=0)
    df.index = pd.to_datetime(df.index)
    df.sort_index(inplace=True)

    closes = {sym: g["close"] for sym, g in df.groupby("symbol") if len(g) >= MIN_OVERLAP_ROWS}
    symbols = sorted(closes)

    # Same-sector candidate pairs only.
    candidates: list[tuple[str, str]] = []
    for a, b in itertools.combinations(symbols, 2):
        sa, sb = sector_of(a), sector_of(b)
        if sa is not None and sa == sb:
            candidates.append((a, b))

    print(
        f"{len(symbols)} symbols with ≥{MIN_OVERLAP_ROWS} rows → "
        f"{len(candidates)} same-sector candidate pairs"
    )
    print(
        f"\n{'pair':<14}{'sector':<10}{'EG t':>7}{'half':>7}{'hold':>6}"
        f"{'trades':>7}{'PF':>6}{'verdict':>9}"
    )
    print("-" * 72)

    selected: list[dict] = []
    evaluated = 0
    for a, b in candidates:
        ca, cb = closes[a].align(closes[b], join="inner")
        if len(ca) < MIN_OVERLAP_ROWS:
            continue
        evaluated += 1
        log_a, log_b = np.log(ca), np.log(cb)
        tstat = engle_granger_tstat(log_a, log_b)
        hl = spread_half_life(log_a, log_b)
        if tstat is None or hl is None or hl <= 0:
            continue
        coint = tstat < EG_SELECT
        if not coint or hl > HALF_LIFE_MAX:
            continue
        # Orient num/den so the simulated long-leg is the lagging name; try both
        # and keep the more profitable orientation under the aligned hold.
        hold = _aligned_max_hold(hl)
        sim_ab = simulate_pair(ca, cb, max_hold=hold)
        sim_ba = simulate_pair(cb, ca, max_hold=hold)
        num, den, sim = (
            (a, b, sim_ab)
            if (sim_ab.get("profit_factor") or 0) >= (sim_ba.get("profit_factor") or 0)
            else (b, a, sim_ba)
        )
        pf = sim.get("profit_factor") or 0
        passes = sim["n_trades"] >= MIN_TRADES and pf >= MIN_PF
        verdict = "SELECT" if passes else "fail"
        print(
            f"{num+'/'+den:<14}{(sector_of(num) or '')[:9]:<10}"
            f"{tstat:>7.2f}{hl:>7.1f}{hold:>6}{sim['n_trades']:>7}"
            f"{pf:>6.2f}{verdict:>9}"
        )
        if passes:
            selected.append(
                {
                    "num": num,
                    "den": den,
                    "sector": sector_of(num),
                    "eg_tstat": round(tstat, 2),
                    "half_life_days": round(hl, 1),
                    "max_hold_days": hold,
                    "profit_factor": pf,
                    "n_trades": sim["n_trades"],
                    "win_rate_pct": sim.get("win_rate_pct"),
                }
            )

    selected.sort(key=lambda r: r["profit_factor"], reverse=True)
    result = {
        "generated_from": data_path,
        "candidates_evaluated": evaluated,
        "gates": {
            "eg_tstat_max": EG_SELECT,
            "half_life_max": HALF_LIFE_MAX,
            "hold_mult": HOLD_MULT,
            "min_trades": MIN_TRADES,
            "min_profit_factor": MIN_PF,
        },
        "pairs": selected,
    }
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description="Screen the universe for tradeable pairs")
    ap.add_argument("--data", default="data/extended_historical_data.csv")
    ap.add_argument("--output", default=str(OUTPUT_PATH))
    args = ap.parse_args()

    result = screen(args.data)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2))
    n = len(result["pairs"])
    print(f"\n{n} pair(s) pass all gates → wrote {out}")
    if n:
        print(
            "Selected:",
            ", ".join(
                f"{p['num']}/{p['den']}(hl={p['half_life_days']}d,"
                f"hold={p['max_hold_days']}d,PF={p['profit_factor']})"
                for p in result["pairs"]
            ),
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
