#!/usr/bin/env python3
"""
Alpha-vs-SPY edge analysis.

The go-live question is not "is the portfolio up?" — it is 75% parked in the
SPY cash-sweep, so it will always roughly track SPY. The question is whether
the ALPHA SLEEVE (everything the strategies actually pick, i.e. the book minus
the SPY sweep) earns its keep versus simply holding that capital in SPY, after
costs.

This script answers that from the trading DB alone:

  * Realized P&L per strategy from trade_pnl_detail, split into ACTIVE vs
    DISABLED (wind-down) using the `disabled:` flags in trading_config.yaml, so
    the read isn't polluted by strategies evidence already retired. Stop-loss
    exits (recorded without a strategy_name) are bucketed separately but counted
    against the active sleeve, since that's whose positions they closed.
  * The SPY sweep position is used as the pure-beta benchmark: its own % return
    IS SPY's return over the sweep's life, needing no external price feed.
  * Total portfolio return over the window from START snapshots.

It intentionally does NOT annualize or compute Sharpe: with a two-digit closed-
trade count that would be false precision. The output is a dollar-and-percent
attribution plus an explicit, sample-size-aware verdict.

Usage:
    python3 scripts/adhoc/alpha_vs_spy.py --db path/to/trading.db [--since 2026-07-02]

--since defaults to 2026-07-02, the date real fills began (PR #60 switched
entries to DAY marketable limits; pre-fix OPG "fills" were largely phantom).
"""
from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_SINCE = "2026-07-02"  # PR #60: entries became real DAY-limit fills


def _norm(name: str) -> str:
    """Lowercase and strip separators so 'News Sentiment' == 'news_sentiment'."""
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


def _disabled_norm_names() -> set[str]:
    """Normalized names of strategies flagged disabled in trading_config.yaml."""
    try:
        import yaml

        cfg = yaml.safe_load((REPO_ROOT / "config" / "trading_config.yaml").read_text())
    except Exception as exc:  # noqa: BLE001
        print(f"WARN: could not read trading_config.yaml ({exc}); assuming none disabled")
        return set()
    strategies = cfg.get("strategies", {})
    return {
        _norm(key)
        for key, val in strategies.items()
        if isinstance(val, dict) and val.get("disabled") is True
    }


def _fmt(x: float) -> str:
    return f"${x:,.2f}"


def analyze(db_path: str, since: str) -> dict:
    disabled = _disabled_norm_names()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        # --- Realized P&L, per strategy, since the window start, ex-sweep ---
        rows = conn.execute(
            """
            SELECT strategy_name, gross_pnl
            FROM trade_pnl_detail
            WHERE symbol != 'SPY'
              AND COALESCE(strategy_name, '') != 'BROKER_SYNC'
              AND exit_date >= ?
            """,
            (since,),
        ).fetchall()

        buckets = {"ACTIVE": [0.0, 0], "DISABLED": [0.0, 0], "STOPLOSS": [0.0, 0]}
        per_strategy: dict[str, list[float]] = {}
        for r in rows:
            name = r["strategy_name"] or ""
            pnl = r["gross_pnl"] or 0.0
            if not name.strip():
                bucket = "STOPLOSS"  # active-strategy stop, recorded without a name
            elif _norm(name) in disabled:
                bucket = "DISABLED"
            else:
                bucket = "ACTIVE"
            buckets[bucket][0] += pnl
            buckets[bucket][1] += 1
            key = name.strip() or "(stop-loss, unattributed)"
            per_strategy.setdefault(key, [0.0, 0])
            per_strategy[key][0] += pnl
            per_strategy[key][1] += 1

        # --- Open unrealized: alpha sleeve vs SPY sweep ---
        sweep = conn.execute(
            "SELECT shares, avg_price, current_price, unrealized_pnl, market_value "
            "FROM positions WHERE symbol = 'SPY'"
        ).fetchone()
        alpha_unreal = conn.execute(
            "SELECT COALESCE(SUM(unrealized_pnl),0) u, COALESCE(SUM(market_value),0) mv, COUNT(*) n "
            "FROM positions WHERE symbol != 'SPY'"
        ).fetchone()

        # --- Portfolio equity over the window (START snapshots) ---
        pv_start = conn.execute(
            "SELECT portfolio_value FROM broker_state "
            "WHERE snapshot_type='START' AND portfolio_value IS NOT NULL AND snapshot_date >= ? "
            "ORDER BY snapshot_date ASC LIMIT 1",
            (since,),
        ).fetchone()
        pv_end = conn.execute(
            "SELECT portfolio_value FROM broker_state "
            "WHERE snapshot_type='START' AND portfolio_value IS NOT NULL "
            "ORDER BY snapshot_date DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()

    active_realized = buckets["ACTIVE"][0]
    disabled_realized = buckets["DISABLED"][0]
    stoploss_realized = buckets["STOPLOSS"][0]
    # Stop-losses closed active-strategy positions, so the honest "are the
    # strategies we still run making money?" number folds them into ACTIVE.
    active_net = active_realized + stoploss_realized

    spy_pct = None
    if sweep and sweep["avg_price"] and sweep["shares"]:
        cost_basis = sweep["avg_price"] * sweep["shares"]
        spy_pct = (sweep["unrealized_pnl"] / cost_basis * 100) if cost_basis else None

    port_pct = None
    if pv_start and pv_end and pv_start["portfolio_value"]:
        port_pct = (pv_end["portfolio_value"] / pv_start["portfolio_value"] - 1) * 100

    return {
        "since": since,
        "buckets": buckets,
        "per_strategy": per_strategy,
        "active_net": active_net,
        "disabled_realized": disabled_realized,
        "alpha_unreal": dict(alpha_unreal) if alpha_unreal else {},
        "sweep": dict(sweep) if sweep else {},
        "spy_pct": spy_pct,
        "port_pct": port_pct,
        "n_active_trades": buckets["ACTIVE"][1] + buckets["STOPLOSS"][1],
    }


def render(a: dict) -> str:
    out = []
    out.append("=" * 72)
    out.append(f"ALPHA-vs-SPY EDGE ANALYSIS   (window: since {a['since']})")
    out.append("=" * 72)

    out.append("\nRealized P&L by strategy (ex-SPY sweep):")
    for name, (pnl, n) in sorted(a["per_strategy"].items(), key=lambda kv: -kv[1][0]):
        out.append(f"  {name:<32} {n:>3} trades   {_fmt(pnl):>12}")

    out.append("\nSleeve buckets (realized):")
    out.append(
        f"  ACTIVE strategies (incl. their stop-losses): {_fmt(a['active_net'])} "
        f"over {a['n_active_trades']} trades"
    )
    out.append(f"  DISABLED strategies (wind-down):             {_fmt(a['disabled_realized'])}")

    au = a["alpha_unreal"]
    out.append("\nOpen book (unrealized):")
    out.append(
        f"  Alpha sleeve: {int(au.get('n', 0))} positions, "
        f"mkt {_fmt(au.get('mv', 0))}, unrealized {_fmt(au.get('u', 0))}"
    )
    sw = a["sweep"]
    if sw:
        out.append(
            f"  SPY sweep:    {sw.get('shares')} sh @ {sw.get('avg_price'):.2f}, "
            f"unrealized {_fmt(sw.get('unrealized_pnl', 0))}"
        )

    out.append("\nBenchmark (window return):")
    out.append(
        f"  Total portfolio: {a['port_pct']:.2f}%"
        if a["port_pct"] is not None
        else "  Total portfolio: n/a"
    )
    out.append(
        f"  SPY (sweep = pure beta): {a['spy_pct']:.2f}%  [over the sweep's life, not the exact window]"
        if a["spy_pct"] is not None
        else "  SPY: n/a"
    )

    # --- Verdict ---
    out.append("\n" + "-" * 72)
    out.append("VERDICT")
    out.append("-" * 72)
    n = a["n_active_trades"]
    verdict = []
    if a["active_net"] > 0:
        verdict.append(
            f"Active strategies are net POSITIVE on realized P&L ({_fmt(a['active_net'])}) "
            f"in the real-fill era."
        )
    else:
        verdict.append(
            f"Active strategies are roughly BREAK-EVEN / NEGATIVE on realized P&L "
            f"({_fmt(a['active_net'])}) once their stop-losses are counted."
        )
    if a["port_pct"] is not None and a["spy_pct"] is not None:
        if a["port_pct"] > a["spy_pct"]:
            verdict.append(
                "The portfolio outpaced SPY over the window, but it holds cash + a "
                "sub-100% SPY weight, so most of that gap is LOWER BETA, not demonstrated alpha."
            )
    verdict.append(
        f"Sample is {n} active closed trades — far below the ~30 needed for any "
        f"statistical confidence. Treat this as directional, not conclusive."
    )
    for v in verdict:
        out.append("  • " + v)
    out.append("")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description="Alpha-vs-SPY edge analysis")
    ap.add_argument("--db", required=True, help="Path to trading.db")
    ap.add_argument(
        "--since", default=DEFAULT_SINCE, help=f"Window start (default {DEFAULT_SINCE})"
    )
    args = ap.parse_args()
    if not Path(args.db).exists():
        print(f"DB not found: {args.db}", file=sys.stderr)
        sys.exit(2)
    print(render(analyze(args.db, args.since)))


if __name__ == "__main__":
    main()
