#!/usr/bin/env python3
"""
read_snapshot.py — human-readable summary of web/public/data/latest.json
or web/public/data/mock/latest.json

Usage:
  python3 scripts/read_snapshot.py            # real snapshot
  python3 scripts/read_snapshot.py --mock     # mock snapshot
  python3 scripts/read_snapshot.py --json     # dump raw JSON
  python3 scripts/read_snapshot.py --field portfolio.totalValue
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _fmt(v, prefix="$"):
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{prefix}{v:,.2f}" if prefix else f"{v:.4f}"
    return str(v)


def read_snapshot(path: Path) -> dict:
    data: dict = json.loads(path.read_text())
    return data


def summarise(d: dict) -> str:
    lines = []
    meta = d["meta"]
    p = d["portfolio"]
    lines += [
        f"=== SNAPSHOT: {meta['tradingDate']}  run={meta['runId']} ===",
        "",
        "--- PORTFOLIO ---",
        f"  Value        : {_fmt(p['totalValue'])}   Cash: {_fmt(p['cash'])}",
        f"  Today        : {p['todayChangePct']:+.2f}%  ({_fmt(p['todayChangeUsd'])})",
        f"  All-Time P&L : {_fmt(p['allTimePnlUsd'])}  ({p['allTimePnlPct']:+.2f}%)",
        f"  Positions    : {p['positionsCount']}  ({p['exposurePct']:.1f}% deployed)",
        f"  Sharpe       : {p['sharpe'] or '—'}",
        f"  Max DD       : {p['maxDrawdownPct'] or '—'}%",
        f"  Win Rate     : {p['winRatePct'] or '—'}%  (≥20 trades required)",
        f"  Closed Trades: {p['closedTradesCount']}",
        f"  Regime       : {p['regime']}",
        "",
        "--- STRATEGIES ---",
    ]
    for s in d["strategies"]:
        ret = f"{s['returnPct']:+.2f}%" if s["returnPct"] is not None else "—"
        sr = f"{s['sharpe']:.2f}" if s["sharpe"] is not None else "—"
        win = f"{s['winRatePct']:.0f}%" if s["winRatePct"] is not None else "—"
        lines.append(
            f"  {s['name']:<22} {s['status']:<10} "
            f"ret={ret:<8} sr={sr:<6} win={win:<6} trades={s['tradesCount']:<4} health={s['healthScore']}"
        )

    lines += ["", "--- POSITIONS ---"]
    if d["positions"]:
        for pos in d["positions"]:
            pl = pos["unrealizedPlUsd"]
            lines.append(
                f"  {pos['symbol']:<6} ({pos['strategy']:<22})  "
                f"{pos['shares']} sh  val={_fmt(pos['value'])}  "
                f"pl={_fmt(pl) if pl is not None else '—'}  "
                f"sentiment={pos['sentimentLabel']}"
            )
    else:
        lines.append("  (none)")

    lines += ["", "--- CLOSED TRADES (last 10) ---"]
    for t in d["trades"][:10]:
        pl = t["realizedPlUsd"]
        lines.append(
            f"  {t['date']}  {t['symbol']:<5}  {t['strategy']:<22}  "
            f"entry={_fmt(t['entry'])}  exit={_fmt(t['exit'])}  "
            f"pl={_fmt(pl)}  ({t['realizedPlPct']:+.2f}%)  reason={t['exitReason']}"
        )
    if not d["trades"]:
        lines.append("  (none)")

    sig = d["signals"]
    lines += ["", "--- SIGNAL FUNNEL (latest run) ---"]
    for f in sig["funnel"]:
        lines.append(f"  {f['stage']:<35} {f['count']:>5}  {f['note']}")

    lines += ["", "--- ANALYTICS ---"]
    a = d["analytics"]
    lines.append(
        "  Monthly returns: "
        + ", ".join(f"{m['month']} {m['returnPct']:+.2f}%" for m in a["monthlyReturns"])
    )
    if a["bestMonth"]:
        lines.append(
            f"  Best month : {a['bestMonth']['month']}  {a['bestMonth']['returnPct']:+.2f}%"
        )
    if a["worstMonth"]:
        lines.append(
            f"  Worst month: {a['worstMonth']['month']}  {a['worstMonth']['returnPct']:+.2f}%"
        )
    dd_max = max((abs(pt["ddPct"] or 0) for pt in a["drawdown"]), default=0)
    lines.append(f"  Peak drawdown: {dd_max:.2f}%")
    lines.append(f"  Rolling Sharpe points: {len(a['rollingSharpe'])}")
    lines.append(f"  Backtest vs Live: {len(a['backtestVsLive'])} strategies")

    health = d["health"]
    lines += ["", "--- SYSTEM HEALTH ---"]
    for m in health["markers"]:
        ok_str = "✓" if (m.get("ok") or m.get("neutral") or m.get("autoResolved")) else "✗"
        lines.append(f"  {ok_str}  {m['label']:<28}  {m['detail']}")

    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mock", action="store_true", help="Use mock snapshot")
    ap.add_argument("--json", action="store_true", help="Dump raw JSON")
    ap.add_argument("--field", help="Dot-path to extract, e.g. portfolio.totalValue")
    args = ap.parse_args()

    base = Path(__file__).parent.parent / "web/public/data"
    path = (base / "mock" / "latest.json") if args.mock else (base / "latest.json")

    if not path.exists():
        print(f"ERROR: {path} not found")
        return

    d = read_snapshot(path)

    if args.json:
        print(json.dumps(d, indent=2))
        return

    if args.field:
        obj = d
        for key in args.field.split("."):
            if isinstance(obj, dict):
                obj = obj.get(key)
            elif isinstance(obj, list):
                try:
                    obj = obj[int(key)]
                except (ValueError, IndexError):
                    obj = None
            else:
                obj = None
        print(json.dumps(obj, indent=2))
        return

    print(summarise(d))


if __name__ == "__main__":
    main()
