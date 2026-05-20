#!/usr/bin/env python3
"""
Paper Trading Validation Report

Reads trade_pnl_detail and daily_portfolio_snapshot from the live DB
and prints a comprehensive metrics summary for the paper trading period.

Metrics captured (per the validation spec):
  Return   : Cumulative P&L, daily P&L, implied CAGR
  Risk     : Max drawdown, worst daily loss, current drawdown
  Trading  : Win rate, avg win/loss %, profit factor, avg hold days
  Stability: Consecutive wins/losses, per-strategy breakdown
  Regime   : Trade distribution across VIX/regime buckets

Run: python3 scripts/paper_trading_report.py [--days 30]
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import sqlite3

_DB_PATH = Path(__file__).parent.parent / "trading.db"


def _pct(val: float) -> str:
    return f"{val * 100:+.2f}%"


def _money(val: float) -> str:
    return f"${val:+,.2f}"


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row is not None


def run_report(days: int = 30) -> None:
    if not _DB_PATH.exists():
        print(f"DB not found: {_DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row

    since = (datetime.now().date() - __import__("datetime").timedelta(days=days)).isoformat()

    # ── Trade P&L detail ──────────────────────────────────────────────────────
    trades = conn.execute(
        "SELECT * FROM trade_pnl_detail WHERE exit_date >= ? ORDER BY exit_date", (since,)
    ).fetchall()

    # ── Daily snapshots ────────────────────────────────────────────────────────
    snaps = conn.execute(
        "SELECT * FROM daily_portfolio_snapshot WHERE snapshot_date >= ? ORDER BY snapshot_date",
        (since,),
    ).fetchall()

    # ── Signal funnel summary ──────────────────────────────────────────────────
    funnel = conn.execute(
        """
        SELECT strategy_name,
               SUM(raw_signals_count)     AS raw,
               SUM(after_regime_count)    AS after_regime,
               SUM(after_correlation_count) AS after_corr,
               SUM(executed_count)        AS executed
        FROM signal_funnel
        WHERE created_at >= ?
        GROUP BY strategy_name
    """,
        (since,),
    ).fetchall()

    # ── Signal rejections ─────────────────────────────────────────────────────
    rejections = conn.execute(
        """
        SELECT stage, reason_code, COUNT(*) AS cnt
        FROM signal_rejections
        WHERE created_at >= ?
        GROUP BY stage, reason_code
        ORDER BY cnt DESC
        LIMIT 20
    """,
        (since,),
    ).fetchall()

    # ── Open positions ────────────────────────────────────────────────────────
    open_positions = (
        conn.execute(
            """
        SELECT p.symbol, s.name AS strategy_name, p.shares,
               p.entry_price, p.current_price, p.unrealized_pnl
        FROM positions p
        LEFT JOIN strategies s ON s.id = p.strategy_id
        ORDER BY p.unrealized_pnl
    """
        ).fetchall()
        if _table_exists(conn, "positions")
        else []
    )

    # ── Heat usage (cash deployed vs limit) ───────────────────────────────────
    latest_snap = snaps[-1] if snaps else None

    # ── SPY gate — most recent regime row ─────────────────────────────────────
    # spy_price / spy_sma50 columns added by future migrations; gracefully absent
    snap_cols = {row[1] for row in conn.execute("PRAGMA table_info(daily_portfolio_snapshot)")}
    if "spy_price" in snap_cols and "spy_sma50" in snap_cols:
        spy_regime = conn.execute(
            """
            SELECT snapshot_date, regime, spy_price, spy_sma50
            FROM daily_portfolio_snapshot
            ORDER BY snapshot_date DESC
            LIMIT 1
        """
        ).fetchone()
    else:
        spy_regime = (
            conn.execute(
                """
            SELECT snapshot_date, regime, NULL AS spy_price, NULL AS spy_sma50
            FROM daily_portfolio_snapshot
            ORDER BY snapshot_date DESC
            LIMIT 1
        """
            ).fetchone()
            if _table_exists(conn, "daily_portfolio_snapshot")
            else None
        )

    conn.close()

    # ── Header ────────────────────────────────────────────────────────────────
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"\n{'=' * 70}")
    print(f"  PAPER TRADING VALIDATION REPORT  |  Last {days} days  |  {now}")
    print(f"{'=' * 70}\n")

    # ── Portfolio snapshots ────────────────────────────────────────────────────
    print("── PORTFOLIO SNAPSHOTS ──────────────────────────────────────────────")
    if snaps:
        first_val = snaps[0]["portfolio_value"]
        last_val = snaps[-1]["portfolio_value"]
        peak_val = max(s["portfolio_value"] for s in snaps)
        max_dd = min((s["drawdown_pct"] or 0.0) for s in snaps)
        daily_pnls = [(s["daily_pnl_pct"] or 0.0) for s in snaps]
        worst_day = min(daily_pnls)
        best_day = max(daily_pnls)
        trading_days = len(snaps)
        cum_pnl = last_val - first_val
        implied_cagr = (
            ((last_val / first_val) ** (252 / max(trading_days, 1)) - 1) if first_val > 0 else 0.0
        )

        print(
            f"  Period          : {snaps[0]['snapshot_date']} → {snaps[-1]['snapshot_date']}  ({trading_days} trading days)"
        )
        print(f"  Start value     : ${first_val:,.2f}")
        print(f"  Current value   : ${last_val:,.2f}  (cum P&L {_money(cum_pnl)})")
        print(f"  Peak value      : ${peak_val:,.2f}")
        print(f"  Implied CAGR    : {_pct(implied_cagr)}")
        print(f"  Max drawdown    : {_pct(max_dd)}")
        print(f"  Worst day       : {_pct(worst_day)}")
        print(f"  Best day        : {_pct(best_day)}")

        print(
            f"\n  {'Date':<12} {'Value':>10} {'Daily P&L':>10} {'Drawdown':>10} {'Regime':<20} {'VIX':>6}"
        )
        print(f"  {'-' * 72}")
        for s in snaps[-10:]:  # last 10 rows
            regime = (s["regime"] or "unknown")[:18]
            vix = f"{s['vix']:.1f}" if s["vix"] else "   -"
            dpnl = _pct(s["daily_pnl_pct"] or 0.0)
            dd = _pct(s["drawdown_pct"] or 0.0)
            print(
                f"  {s['snapshot_date']:<12} ${s['portfolio_value']:>9,.2f} {dpnl:>10} {dd:>10} {regime:<20} {vix:>6}"
            )
    else:
        print("  No snapshot data yet (first run after code deployment will populate this).")

    # ── Trade P&L ─────────────────────────────────────────────────────────────
    print(f"\n── CLOSED TRADE P&L ({len(trades)} trades, last {days} days) ───────────────────")
    if trades:
        wins = [t for t in trades if t["is_winner"] == 1]
        losses = [t for t in trades if t["is_winner"] == 0]
        gross_wins = sum(t["gross_pnl"] for t in wins)
        gross_losses = abs(sum(t["gross_pnl"] for t in losses)) or 1e-9
        pf = gross_wins / gross_losses
        wr = len(wins) / len(trades)
        avg_w = sum(t["gross_pnl_pct"] for t in wins) / len(wins) if wins else 0.0
        avg_l = sum(t["gross_pnl_pct"] for t in losses) / len(losses) if losses else 0.0
        hold_days_list = [t["hold_days"] for t in trades if t["hold_days"] is not None]
        avg_hold = sum(hold_days_list) / len(hold_days_list) if hold_days_list else None

        print(f"  Win rate        : {wr:.1%}  ({len(wins)}W / {len(losses)}L)")
        print(f"  Profit factor   : {pf:.2f}  (>1.0 = profitable, >1.5 = good)")
        print(f"  Avg win         : {_pct(avg_w)}")
        print(f"  Avg loss        : {_pct(avg_l)}")
        print(
            f"  Win/Loss ratio  : {abs(avg_w / avg_l):.2f}x" if avg_l else "  Win/Loss ratio  : ∞"
        )
        print(f"  Gross wins      : {_money(gross_wins)}")
        print(f"  Gross losses    : {_money(-gross_losses)}")
        print(f"  Net P&L         : {_money(gross_wins - gross_losses)}")
        print(f"  Avg hold days   : {avg_hold:.1f}d" if avg_hold else "  Avg hold days   : —")

        # Consecutive streak
        results = [t["is_winner"] for t in trades]
        max_win_streak = max_loss_streak = cur = 0
        for r in results:
            cur = (cur + 1) if r else 0
            max_win_streak = max(max_win_streak, cur)
        cur = 0
        for r in results:
            cur = (cur + 1) if not r else 0
            max_loss_streak = max(max_loss_streak, cur)
        print(f"  Max win streak  : {max_win_streak}")
        print(f"  Max loss streak : {max_loss_streak}")

        # Validation flags
        print("\n  ── VALIDATION FLAGS ──")
        flags = []
        if wr > 0.65:
            flags.append("⚠️  Win rate >65% — suspicious, check for lookahead bias")
        if pf > 3.0:
            flags.append("⚠️  Profit factor >3 — likely overfitting or tiny sample")
        if len(trades) < 10:
            flags.append("ℹ️  < 10 closed trades — metrics not yet statistically meaningful")
        if not flags:
            flags.append("✅  No red flags detected")
        for f in flags:
            print(f"  {f}")

        # Per-strategy breakdown
        from collections import defaultdict

        by_strat: dict = defaultdict(list)
        for t in trades:
            by_strat[t["strategy_name"] or "Unknown"].append(t)
        print("\n  ── PER-STRATEGY BREAKDOWN ──")
        print(f"  {'Strategy':<28} {'Trades':>6} {'WR':>6} {'PF':>6} {'Net P&L':>10}")
        print(f"  {'-' * 60}")
        for strat, strat_trades in sorted(by_strat.items()):
            sw = [x for x in strat_trades if x["is_winner"] == 1]
            sl = [x for x in strat_trades if x["is_winner"] == 0]
            sgw = sum(x["gross_pnl"] for x in sw)
            sgl = abs(sum(x["gross_pnl"] for x in sl)) or 1e-9
            swr = len(sw) / len(strat_trades)
            spf = sgw / sgl
            net = sgw - sgl
            print(f"  {strat:<28} {len(strat_trades):>6} {swr:>6.1%} {spf:>6.2f} {_money(net):>10}")
    else:
        print("  No closed trades yet — positions are still open or no trades have been taken.")

    # ── Signal funnel ─────────────────────────────────────────────────────────
    print(f"\n── SIGNAL FUNNEL (last {days} days) ─────────────────────────────────────")
    if funnel:
        print(f"  {'Strategy':<28} {'Raw':>5} {'Regime':>7} {'Corr':>6} {'Exec':>6} {'Fill%':>7}")
        print(f"  {'-' * 62}")
        for row in funnel:
            fill_pct = (row["executed"] / row["raw"] * 100) if row["raw"] else 0
            print(
                f"  {row['strategy_name']:<28} {row['raw']:>5} {row['after_regime']:>7} {row['after_corr']:>6} {row['executed']:>6} {fill_pct:>6.1f}%"
            )
    else:
        print("  No funnel data yet.")

    # ── Top rejection reasons ─────────────────────────────────────────────────
    print(f"\n── TOP SIGNAL REJECTIONS (last {days} days) ──────────────────────────────")
    if rejections:
        print(f"  {'Stage':<15} {'Reason':<25} {'Count':>6}")
        print(f"  {'-' * 50}")
        for r in rejections:
            print(f"  {r['stage']:<15} {r['reason_code']:<25} {r['cnt']:>6}")
    else:
        print("  No rejection data yet.")

    # ── Regime gate status ────────────────────────────────────────────────────
    print("\n── REGIME GATE STATUS ───────────────────────────────────────────────────")
    if spy_regime and spy_regime["spy_price"] and spy_regime["spy_sma50"]:
        spy_px = spy_regime["spy_price"]
        sma50 = spy_regime["spy_sma50"]
        gate = "OPEN (regime normal)" if spy_px >= sma50 else "CLOSED (SPY below SMA50)"
        gate_sym = "✅" if spy_px >= sma50 else "🚫"
        spy_suppressed = sum(
            r["cnt"] for r in rejections if "regime" in (r["reason_code"] or "").lower()
        )
        print(f"  {gate_sym} Gate: {gate}")
        print(f"  SPY ${spy_px:.2f}  vs  SMA50 ${sma50:.2f}  ({spy_px - sma50:+.2f})")
        if spy_suppressed:
            print(f"  ⚠️  {spy_suppressed} signal(s) suppressed by regime filter this period")
    else:
        print("  No SPY/SMA50 data stored yet (added to snapshot after first run with new schema).")

    # ── Open positions & unrealized P&L ──────────────────────────────────────
    print("\n── OPEN POSITIONS ───────────────────────────────────────────────────────")
    if open_positions:
        total_unrealized = sum(p["unrealized_pnl"] or 0 for p in open_positions)
        print(
            f"  {'Symbol':<8} {'Strategy':<22} {'Shares':>6}  {'Entry':>8}  {'Current':>8}  {'Unreal P&L':>11}"
        )
        print(f"  {'-' * 72}")
        for p in open_positions:
            ep = p["entry_price"] or 0
            cp = p["current_price"] or 0
            upnl = p["unrealized_pnl"] or 0
            strat = p["strategy_name"] or ""
            print(
                f"  {p['symbol']:<8} {strat:<22} {p['shares']:>6}  ${ep:>7.2f}  ${cp:>7.2f}  {_money(upnl):>11}"
            )
        print(f"  {'':>52}  {'─' * 11}")
        print(f"  {'Total unrealized':>52}  {_money(total_unrealized):>11}")
    else:
        print("  No open positions tracked in DB yet.")

    # ── Heat usage ────────────────────────────────────────────────────────────
    if latest_snap and latest_snap["portfolio_value"]:
        cash_col = dict(latest_snap).get("cash")
        if cash_col is not None:
            print("\n── CAPITAL DEPLOYMENT ───────────────────────────────────────────────────")
            total = latest_snap["portfolio_value"]
            cash = cash_col
            deployed = total - cash
            print(f"  Total portfolio : ${total:>10,.2f}")
            print(f"  Cash            : ${cash:>10,.2f}  ({100*cash/total:.1f}%)")
            print(f"  Deployed (heat) : ${deployed:>10,.2f}  ({100*deployed/total:.1f}%)")
            heat_rejections = sum(
                r["cnt"]
                for r in rejections
                if "heat" in (r["reason_code"] or "").lower()
                or "cash" in (r["reason_code"] or "").lower()
            )
            if heat_rejections:
                print(
                    f"  ⚠️  {heat_rejections} signal(s) blocked by cash/heat limit — consider raising heat ceiling if win rate holds"
                )

    print(f"\n{'=' * 70}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Paper trading validation report")
    parser.add_argument("--days", type=int, default=30, help="Look-back window in days")
    args = parser.parse_args()
    run_report(days=args.days)
