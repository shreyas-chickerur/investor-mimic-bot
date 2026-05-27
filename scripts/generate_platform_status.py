#!/usr/bin/env python3
"""Generate artifacts/platform_status.md — a snapshot of system health and strategy state.

Run once per daily GHA workflow. Output is uploaded as part of daily-artifacts.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

DB_PATH = os.getenv("DB_PATH", "trading.db")
OUT_PATH = Path("artifacts/platform_status.md")

KELLY_MIN_TRADES = 20


def _q(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list:
    conn.row_factory = sqlite3.Row
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def _scalar(conn: sqlite3.Connection, sql: str, params: tuple = (), default=None):
    row = conn.execute(sql, params).fetchone()
    return row[0] if row else default


def _regime_label(conn: sqlite3.Connection) -> str:
    raw = _scalar(conn, "SELECT value FROM system_state WHERE key = 'regime'")
    if not raw:
        return "UNKNOWN"
    try:
        d = json.loads(raw)
        return d.get("composite_regime") or d.get("classification") or "UNKNOWN"
    except Exception:
        return "UNKNOWN"


def _vix(conn: sqlite3.Connection) -> str:
    raw = _scalar(conn, "SELECT value FROM system_state WHERE key = 'regime'")
    if not raw:
        return "—"
    try:
        d = json.loads(raw)
        v = d.get("vix")
        return f"{v:.1f}" if v else "—"
    except Exception:
        return "—"


def _recon_status(conn: sqlite3.Connection) -> str:
    row = conn.execute(
        "SELECT reconciliation_status FROM broker_state "
        "WHERE snapshot_type IN ('RECONCILIATION','RECONCILIATION_RETRY') "
        "ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    return row[0] if row else "UNKNOWN"


def _strategies(conn: sqlite3.Connection) -> list[dict]:
    return _q(conn, "SELECT id, name, status, capital_allocation FROM strategies ORDER BY id")


def _pnl_stats(conn: sqlite3.Connection, strategy_id: int) -> dict:
    rows = _q(
        conn,
        "SELECT gross_pnl, gross_pnl_pct, is_winner FROM trade_pnl_detail WHERE strategy_id = ?",
        (strategy_id,),
    )
    if not rows:
        return {"trades": 0}
    wins = [r for r in rows if r["is_winner"] == 1]
    losses = [r for r in rows if r["is_winner"] == 0]
    avg_win = sum(r["gross_pnl_pct"] for r in wins) / len(wins) if wins else 0.0
    avg_loss = abs(sum(r["gross_pnl_pct"] for r in losses) / len(losses)) if losses else 1e-9
    win_rate = len(wins) / len(rows)
    # Quarter-Kelly
    b = avg_win / avg_loss
    f_star = win_rate - (1 - win_rate) / b
    kelly_mult = round(1.0 + max(0.0, min(f_star * 0.25, 0.5)), 3)
    return {
        "trades": len(rows),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": win_rate,
        "avg_win_pct": avg_win,
        "avg_loss_pct": avg_loss,
        "kelly_mult": kelly_mult if len(rows) >= KELLY_MIN_TRADES else None,
        "total_pnl": sum(r["gross_pnl"] for r in rows),
    }


def _health_score(conn: sqlite3.Connection, strategy_id: int) -> int | None:
    row = conn.execute(
        "SELECT value FROM system_state WHERE key = ?",
        (f"health_score_{strategy_id}",),
    ).fetchone()
    if row:
        try:
            return int(row[0])
        except Exception:
            pass
    return None


def _open_positions(conn: sqlite3.Connection, strategy_id: int) -> int:
    row = conn.execute(
        "SELECT COUNT(*) FROM positions WHERE strategy_id = ? AND shares > 0",
        (strategy_id,),
    ).fetchone()
    return row[0] if row else 0


def _portfolio_snapshot(conn: sqlite3.Connection) -> dict | None:
    row = conn.execute(
        "SELECT portfolio_value, cash, daily_pnl, daily_pnl_pct, cumulative_pnl, drawdown_pct, "
        "num_open_positions, vix, regime, snapshot_date "
        "FROM daily_portfolio_snapshot ORDER BY snapshot_date DESC LIMIT 1"
    ).fetchone()
    if row:
        return dict(
            zip(
                [
                    "portfolio_value",
                    "cash",
                    "daily_pnl",
                    "daily_pnl_pct",
                    "cumulative_pnl",
                    "drawdown_pct",
                    "num_open_positions",
                    "vix",
                    "regime",
                    "snapshot_date",
                ],
                row,
            )
        )
    return None


def _data_age_hours(conn: sqlite3.Connection) -> float | None:
    raw = _scalar(conn, "SELECT value FROM system_state WHERE key = 'data_last_updated'")
    if not raw:
        return None
    try:
        ts = datetime.fromisoformat(raw)
        return (datetime.now() - ts).total_seconds() / 3600
    except Exception:
        return None


def _circuit_breaker(conn: sqlite3.Connection) -> bool:
    raw = _scalar(conn, "SELECT value FROM system_state WHERE key = 'circuit_breaker_active'")
    return (raw or "false").lower() not in ("true", "1")


def _run_number() -> str:
    return os.getenv("RUN_NUMBER", "—")


def generate(conn: sqlite3.Connection) -> str:
    now = datetime.now()
    snap = _portfolio_snapshot(conn)
    regime = _regime_label(conn)
    vix_val = _vix(conn)
    recon = _recon_status(conn)
    strategies = _strategies(conn)

    lines: list[str] = []
    lines.append(f"# Platform Status — {now.strftime('%Y-%m-%d %H:%M ET')}")
    lines.append(f"\n> Run #{_run_number()} &nbsp;·&nbsp; Generated automatically by GHA")
    lines.append("")

    # Portfolio summary
    lines.append("## Portfolio")
    if snap:
        pv = snap.get("portfolio_value") or 0
        cash = snap.get("cash") or 0
        dpnl = snap.get("daily_pnl") or 0
        dpnl_pct = snap.get("daily_pnl_pct") or 0
        cpnl = snap.get("cumulative_pnl") or 0
        dd = snap.get("drawdown_pct") or 0
        n_pos = snap.get("num_open_positions") or 0
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| Portfolio Value | ${pv:,.2f} |")
        lines.append(f"| Cash | ${cash:,.2f} |")
        sign = "+" if dpnl >= 0 else ""
        lines.append(f"| Today's P&L | {sign}${dpnl:,.2f} ({sign}{dpnl_pct:.2%}) |")
        lines.append(f"| All-Time P&L | ${cpnl:+,.2f} |")
        lines.append(f"| Max Drawdown | {dd:.2%} |")
        lines.append(f"| Open Positions | {n_pos} |")
        lines.append(f"| Regime | **{regime}** |")
        lines.append(f"| VIX | {vix_val} |")
    else:
        lines.append("_No portfolio snapshot available yet._")
    lines.append("")

    # System health markers
    lines.append("## System Health")
    data_age = _data_age_hours(conn)
    cb_clear = _circuit_breaker(conn)

    health_markers = [
        ("Broker reconciled", recon in ("PASS", "SYNCED"), f"Status: {recon}"),
        (
            "Data fresh",
            data_age is not None and data_age < 48,
            f"{data_age:.1f}h ago" if data_age is not None else "age unknown",
        ),
        ("Circuit breaker clear", cb_clear, "OK" if cb_clear else "TRIPPED"),
        ("Regime detected", regime != "UNKNOWN", regime),
    ]
    for label, ok, detail in health_markers:
        icon = "✅" if ok else "❌"
        lines.append(f"- {icon} **{label}**: {detail}")
    lines.append("")

    # Strategy table
    lines.append("## Strategy Status")
    lines.append("")
    lines.append("| Strategy | Status | Capital | Positions | Trades | Win Rate | Kelly |")
    lines.append("|----------|--------|---------|-----------|--------|----------|-------|")
    for s in strategies:
        sid = s["id"]
        stats = _pnl_stats(conn, sid)
        n_pos = _open_positions(conn, sid)
        capital = s.get("capital_allocation") or 0
        n_trades = stats.get("trades", 0)
        if n_trades >= 1:
            wr = f"{stats['win_rate']:.0%}"
        else:
            wr = "—"
        kelly = (
            f"{stats['kelly_mult']:.3f}×"
            if stats.get("kelly_mult")
            else f"gated (<{KELLY_MIN_TRADES})"
        )
        status_icon = "🟢" if s.get("status") == "active" else "⚪"
        lines.append(
            f"| {s['name']} | {status_icon} {s.get('status','?')} "
            f"| ${capital:,.0f} | {n_pos} | {n_trades} | {wr} | {kelly} |"
        )
    lines.append("")

    # Regime-based strategy weighting note
    lines.append("## Regime → Strategy Weighting")
    lines.append(f"\nCurrent composite regime: **{regime}**\n")
    regime_notes = {
        "TRENDING_BULL": "ML Momentum and MA Crossover up-weighted (+0.20). RSI Mean Reversion down-weighted (−0.15).",
        "RANGING": "RSI Mean Reversion up-weighted (+0.20). ML Momentum and MA Crossover down-weighted (−0.15).",
        "HIGH_VOL": "RSI Mean Reversion up-weighted (+0.15). Volatility Breakout down-weighted (−0.15).",
        "LOW_VOL": "ML Momentum up-weighted (+0.15). MA Crossover and Volatility Breakout up-weighted (+0.10).",
        "NORMAL": "No regime-specific adjustments — health and Sharpe weights dominate.",
    }
    lines.append(regime_notes.get(regime, "Regime unknown — neutral weights applied."))
    lines.append("")

    # Kelly status
    lines.append("## Kelly Rebalancing")
    lines.append(
        f"\nActivates at **{KELLY_MIN_TRADES} closed trades per strategy** (quarter-Kelly, 0.25×).\n"
    )
    gated = [
        s["name"]
        for s in strategies
        if _pnl_stats(conn, s["id"]).get("trades", 0) < KELLY_MIN_TRADES
    ]
    active = [
        s["name"]
        for s in strategies
        if _pnl_stats(conn, s["id"]).get("trades", 0) >= KELLY_MIN_TRADES
    ]
    lines.append(f"- **Active (have data)**: {', '.join(active) if active else 'none yet'}")
    lines.append(f"- **Gated (need more trades)**: {', '.join(gated) if gated else 'none'}")
    lines.append("")

    # Footer
    lines.append("---")
    lines.append(
        f"_Auto-generated by `generate_platform_status.py` at {now.isoformat(timespec='seconds')}_"
    )

    return "\n".join(lines)


def main() -> None:
    if not Path(DB_PATH).exists():
        print(f"⚠️  {DB_PATH} not found — skipping platform status generation")
        return

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        report = generate(conn)
    finally:
        conn.close()

    OUT_PATH.write_text(report)
    print(f"✅ Platform status written to {OUT_PATH}")
    print(report[:500])


if __name__ == "__main__":
    main()
