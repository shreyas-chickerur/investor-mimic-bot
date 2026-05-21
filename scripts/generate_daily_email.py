#!/usr/bin/env python3
"""
Daily Trading Digest — premium, editorial, beginner-friendly evening read.

Design goals:
  * Feels like Morning Brew or The Hustle, not a brokerage dashboard.
  * Every technical term has a plain-English explainer nearby.
  * Strategy status is front-and-center — beginner investors need context.
  * Warnings and alerts are unmissable.
  * Rich visual hierarchy: big numbers, color-coded sections, sparklines.

Usage:
    python3 scripts/generate_daily_email.py [--include-visuals] [--send]
"""
from __future__ import annotations

import argparse
import base64
import html as html_lib
import io
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ── Palette ───────────────────────────────────────────────────────────────────
# Light theme only — dark email templates get inverted by Gmail/Outlook.
PAGE_BG = "#f4f6fb"  # Cool off-white page background
CARD = "#ffffff"  # White card surface
CARD_ALT = "#f0f4fb"  # Subtle alternate fill
BORDER = "#e2e8f4"  # Cool blue-gray hairline
BORDER_MED = "#c8d4e8"  # Stronger border for emphasis

INK = "#0d1117"  # Primary near-black
INK_DIM = "#4a5568"  # Secondary text
INK_MUTE = "#94a3b8"  # Muted / labels

# Semantic colors — each with bg tint, border, foreground
GREEN = "#059669"
GREEN_BG = "#ecfdf5"
GREEN_BORDER = "#6ee7b7"
GREEN_DARK = "#065f46"

RED = "#dc2626"
RED_BG = "#fef2f2"
RED_BORDER = "#fca5a5"
RED_DARK = "#7f1d1d"

AMBER = "#d97706"
AMBER_BG = "#fffbeb"
AMBER_BORDER = "#fcd34d"
AMBER_DARK = "#78350f"

BLUE = "#2563eb"
BLUE_BG = "#eff6ff"
BLUE_BORDER = "#93c5fd"
BLUE_DARK = "#1e3a8a"

PURPLE = "#7c3aed"
PURPLE_BG = "#f5f3ff"
PURPLE_BORDER = "#c4b5fd"
PURPLE_DARK = "#4c1d95"

SLATE = "#64748b"
SLATE_BG = "#f8fafc"
SLATE_BORDER = "#cbd5e1"

# Strategy brand colors (ink, bg, border)
STRAT_BRAND: dict[str, tuple[str, str, str]] = {
    "RSI Mean Reversion": ("#0369a1", "#e0f2fe", "#7dd3fc"),
    "ML Momentum": ("#7c3aed", "#f5f3ff", "#c4b5fd"),
    "Earnings Drift": ("#d97706", "#fffbeb", "#fcd34d"),
    "Factor Momentum": ("#64748b", "#f8fafc", "#cbd5e1"),
}

FONT = (
    'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, '
    '"Helvetica Neue", Arial, sans-serif'
)
DISPLAY = 'Fraunces, "DM Serif Display", "Playfair Display", Georgia, serif'
MONO = '"SF Mono", "JetBrains Mono", "Roboto Mono", Menlo, Consolas, monospace'

STRATEGY_EXPLAINERS: dict[str, str] = {
    "RSI Mean Reversion": (
        "Buys stocks that have fallen sharply and look 'oversold' — like a rubber band "
        "stretched too far. RSI below 30 signals it may snap back up."
    ),
    "ML Momentum": (
        "A machine-learning model trained on 12 price and volume signals predicts "
        "which stocks are likely to rise over the next 5 days. Only acts on high-confidence signals."
    ),
    "Earnings Drift": (
        "After a company reports better-than-expected earnings, its stock often keeps "
        "drifting higher for weeks. This strategy rides that momentum."
    ),
    "Factor Momentum": (
        "Ranks every stock by a mix of momentum and quality scores, then buys the top-ranked. "
        "Currently paused — our backtests didn't find a reliable edge here."
    ),
}


# ── DB helpers ────────────────────────────────────────────────────────────────
def _conn(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _q(db: sqlite3.Connection, sql: str, *args) -> list[dict]:
    try:
        return [dict(r) for r in db.execute(sql, args).fetchall()]
    except sqlite3.Error:
        return []


def _q1(db: sqlite3.Connection, sql: str, *args) -> dict:
    rows = _q(db, sql, *args)
    return rows[0] if rows else {}


# ── Data fetchers ─────────────────────────────────────────────────────────────
def get_latest_snapshot(db) -> dict:
    return _q1(
        db,
        """
        SELECT portfolio_value, cash, reconciliation_status, snapshot_date
        FROM broker_state
        WHERE snapshot_type IN ('RECONCILIATION','RECONCILIATION_RETRY','END','SYNC','START')
        ORDER BY created_at DESC, id DESC LIMIT 1
        """,
    )


def get_equity_curve(db, days: int = 30) -> list[dict]:
    return _q(
        db,
        """
        SELECT snapshot_date AS date, MAX(portfolio_value) AS total
        FROM broker_state
        WHERE snapshot_type IN ('START','END')
          AND snapshot_date >= date('now', ?)
        GROUP BY snapshot_date
        ORDER BY snapshot_date
        """,
        f"-{days} days",
    )


def get_today_trades(db) -> list[dict]:
    return _q(
        db,
        """
        SELECT t.symbol, t.action, t.shares, t.exec_price, t.notional,
               t.pnl, t.executed_at, s.name AS strat
        FROM trades t JOIN strategies s ON t.strategy_id = s.id
        WHERE DATE(t.executed_at) = DATE('now') AND s.name != 'BROKER_SYNC'
        ORDER BY t.executed_at
        """,
    )


def get_open_positions(db) -> list[dict]:
    return _q(
        db,
        """
        SELECT p.symbol, p.shares, p.avg_price, p.current_price,
               p.unrealized_pnl, p.entry_date, p.entry_price,
               p.stop_loss_price, s.name AS strat,
               CAST(julianday('now') - julianday(COALESCE(p.entry_date, date('now')))
                    AS INTEGER) AS days_held
        FROM positions p JOIN strategies s ON p.strategy_id = s.id
        WHERE p.shares > 0 AND s.name != 'BROKER_SYNC'
        ORDER BY p.unrealized_pnl DESC
        """,
    )


def get_signal_reasons(db, symbols: list[str]) -> dict[tuple[str, str], dict]:
    if not symbols:
        return {}
    placeholders = ",".join("?" for _ in symbols)
    rows = _q(
        db,
        f"""
        SELECT sg.symbol, sg.signal_type, sg.reasoning, sg.confidence,
               sg.generated_at, s.name AS strat
        FROM signals sg JOIN strategies s ON sg.strategy_id = s.id
        WHERE sg.symbol IN ({placeholders})
          AND sg.generated_at >= datetime('now', '-2 days')
        ORDER BY sg.generated_at DESC
        """,
        *symbols,
    )
    out: dict[tuple[str, str], dict] = {}
    for r in rows:
        action = (
            "BUY" if (r.get("signal_type") or "").upper() in ("BUY", "LONG", "ENTRY") else "SELL"
        )
        key = (r["symbol"], action)
        out.setdefault(key, r)
    return out


def get_latest_run_id(db) -> str | None:
    rows = _q(
        db,
        """
        SELECT run_id FROM broker_state
        WHERE snapshot_type != 'SYNC' AND run_id != 'AUTO_SYNC'
        ORDER BY created_at DESC LIMIT 1
        """,
    )
    return rows[0]["run_id"] if rows else None


def get_rejection_summary(db, run_id: str | None) -> list[dict]:
    if not run_id:
        return []
    return _q(
        db,
        """
        SELECT stage, reason_code, COUNT(*) AS cnt
        FROM signal_rejections WHERE run_id = ?
        GROUP BY stage, reason_code
        ORDER BY cnt DESC LIMIT 5
        """,
        run_id,
    )


def get_zero_trade_streak(db) -> int:
    rows = _q(
        db,
        """
        SELECT DATE(snapshot_date) AS day,
               (SELECT COUNT(*) FROM trades t
                WHERE DATE(t.executed_at) = DATE(bs.snapshot_date)
                  AND t.strategy_id IN (SELECT id FROM strategies WHERE name != 'BROKER_SYNC')
               ) AS trade_count
        FROM broker_state bs
        WHERE snapshot_type IN ('RECONCILIATION','RECONCILIATION_RETRY','EXECUTION')
          AND run_id != 'AUTO_SYNC'
        GROUP BY DATE(snapshot_date)
        ORDER BY day DESC LIMIT 10
        """,
    )
    streak = 0
    for r in rows:
        if int(r.get("trade_count") or 0) == 0:
            streak += 1
        else:
            break
    return streak


def get_aggregate_pnl(db) -> dict:
    return _q1(
        db,
        """
        SELECT COUNT(*)                                    AS closed,
               SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END)  AS wins,
               SUM(COALESCE(pnl,0))                       AS total_pnl,
               SUM(CASE WHEN DATE(executed_at)=DATE('now')
                        THEN COALESCE(pnl,0) ELSE 0 END)  AS today_realized
        FROM trades WHERE pnl IS NOT NULL
        """,
    )


def get_strategy_statuses(db) -> list[dict]:
    return _q(
        db,
        """
        SELECT id, name, status, capital_allocation,
               (SELECT COUNT(*) FROM positions p
                WHERE p.strategy_id = strategies.id AND p.shares > 0) AS open_count,
               (SELECT COALESCE(SUM(unrealized_pnl),0) FROM positions p
                WHERE p.strategy_id = strategies.id AND p.shares > 0) AS unrealized_total
        FROM strategies
        WHERE name != 'BROKER_SYNC'
        ORDER BY id
        """,
    )


def get_system_alerts(db, recon_status: str, zero_streak: int) -> list[dict]:
    alerts = []
    # Frozen / non-active strategies
    strats = _q(db, "SELECT name, status FROM strategies WHERE name != 'BROKER_SYNC'")
    for s in strats:
        if (s.get("status") or "active").lower() not in ("active", ""):
            alerts.append(
                {
                    "level": "warning",
                    "icon": "⏸",
                    "msg": f"{s['name']} strategy is {s['status']}",
                }
            )
    # Reconciliation issues
    recon_upper = (recon_status or "").upper()
    if "FAIL" in recon_upper or "MISMATCH" in recon_upper or "ERROR" in recon_upper:
        alerts.append(
            {
                "level": "critical",
                "icon": "⚠️",
                "msg": f"Account sync issue detected — {recon_status}. System will retry automatically.",
            }
        )
    # Long zero-trade streak
    if zero_streak >= 5:
        alerts.append(
            {
                "level": "info",
                "icon": "💤",
                "msg": f"{zero_streak} days in a row with no trades. Markets may be range-bound; "
                "the system is being selective.",
            }
        )
    # Disabled Factor Momentum (always note it so user understands)
    # Factor Momentum is noted in strategy dashboard, not as an alert
    return alerts


def get_fill_quality_summary(db) -> dict:
    return _q1(
        db,
        """
        SELECT AVG(ABS(deviation_bps)) AS avg_dev,
               MAX(ABS(deviation_bps)) AS max_dev,
               COUNT(*) AS fill_count
        FROM fill_quality WHERE DATE(recorded_at) = DATE('now')
        """,
    )


# ── Price chart helpers ───────────────────────────────────────────────────────
_CHART_CACHE: dict[str, str] = {}


def _load_price_history() -> dict[str, list[tuple[str, float]]] | None:
    csv_path = PROJECT_ROOT / "data" / "training_data.csv"
    if not csv_path.exists():
        return None
    try:
        import pandas as pd

        df = pd.read_csv(csv_path, usecols=["date", "symbol", "close"])
    except Exception:
        return None
    df = df.dropna(subset=["close"])
    by_sym: dict[str, list[tuple[str, float]]] = {}
    for sym, sub in df.groupby("symbol"):
        sub = sub.sort_values("date").tail(45)
        by_sym[sym] = list(zip(sub["date"].astype(str), sub["close"].astype(float)))
    return by_sym


_PRICE_HISTORY: dict[str, list[tuple[str, float]]] | None = None


def _sym_history(symbol: str) -> list[tuple[str, float]]:
    global _PRICE_HISTORY
    if _PRICE_HISTORY is None:
        _PRICE_HISTORY = _load_price_history() or {}
    return _PRICE_HISTORY.get(symbol, [])


def render_sparkline(symbol: str, entry_price: float | None = None) -> str:
    cache_key = f"{symbol}:{entry_price}"
    if cache_key in _CHART_CACHE:
        return _CHART_CACHE[cache_key]
    history = _sym_history(symbol)
    if len(history) < 5:
        _CHART_CACHE[cache_key] = ""
        return ""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        _CHART_CACHE[cache_key] = ""
        return ""
    closes = [c for _, c in history]
    is_up = closes[-1] >= closes[0]
    line_color = GREEN if is_up else RED
    fig, ax = plt.subplots(figsize=(3.6, 1.0), dpi=140)
    fig.patch.set_facecolor(CARD)
    ax.set_facecolor(CARD)
    ax.plot(range(len(closes)), closes, color=line_color, linewidth=1.8)
    ax.fill_between(range(len(closes)), closes, min(closes), color=line_color, alpha=0.10)
    if entry_price and min(closes) <= entry_price <= max(closes):
        ax.axhline(entry_price, color=INK_DIM, linewidth=0.8, linestyle=(0, (3, 4)))
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.margins(x=0.01, y=0.18)
    plt.tight_layout(pad=0.1)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor=CARD, edgecolor="none")
    plt.close(fig)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    _CHART_CACHE[cache_key] = b64
    return b64


def render_equity_sparkline(equity: list[dict]) -> str:
    cache_key = f"__equity__:{len(equity)}:{equity[-1]['total'] if equity else 0}"
    if cache_key in _CHART_CACHE:
        return _CHART_CACHE[cache_key]
    values = [float(p.get("total") or 0) for p in equity if p.get("total") is not None]
    if len(values) < 3:
        _CHART_CACHE[cache_key] = ""
        return ""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        _CHART_CACHE[cache_key] = ""
        return ""
    is_up = values[-1] >= values[0]
    line_color = GREEN if is_up else RED

    fig, ax = plt.subplots(figsize=(7.2, 1.6), dpi=140)
    fig.patch.set_facecolor("#e8f4fd")
    ax.set_facecolor("#e8f4fd")
    ax.plot(range(len(values)), values, color=line_color, linewidth=2.2)
    ax.fill_between(range(len(values)), values, min(values), color=line_color, alpha=0.15)
    ax.axhline(values[0], color=INK_DIM, linewidth=0.8, linestyle=(0, (4, 5)))
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.margins(x=0.005, y=0.20)
    plt.tight_layout(pad=0.05)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor="#e8f4fd", edgecolor="none")
    plt.close(fig)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    _CHART_CACHE[cache_key] = b64
    return b64


# ── Reason inference ──────────────────────────────────────────────────────────
def _short_strategy(name: str) -> str:
    return {
        "RSI Mean Reversion": "RSI Bounce",
        "ML Momentum": "AI Model",
        "Earnings Drift": "Earnings Play",
        "Factor Momentum": "Factor Rank",
    }.get(name or "", name or "")


def _infer_buy_reason(strategy: str, signal_reasoning: str) -> str:
    import re

    r = (signal_reasoning or "").lower()
    m = re.search(r"rsi[^a-z0-9]?(\d{1,2}(?:\.\d+)?)", r)
    if "rsi" in r and m:
        return f"RSI hit {m.group(1)} — stock is oversold and may bounce"
    if "rsi" in r:
        return "RSI signaled the stock is oversold — potential reversal"
    m = re.search(r"p\(up\)\s*[=:]?\s*([\d.]+)", r)
    if m:
        return f"AI model: {int(float(m.group(1)) * 100)}% probability of rising next 5 days"
    m = re.search(r"confidence[^0-9]*([\d.]+)", r)
    if m and float(m.group(1)) <= 1.0:
        return f"AI confidence score: {int(float(m.group(1)) * 100)}%"
    m = re.search(r"volume[_\s]*ratio[=:\s]*([\d.]+)", r)
    if m:
        return f"Volume spiked {float(m.group(1)):.1f}× above average — post-earnings momentum"
    m = re.search(r"top\s*(\d+)\s*/\s*(\d+)", r)
    if m:
        return f"Ranked #{m.group(1)} of {m.group(2)} stocks by momentum + quality score"
    return f"{_short_strategy(strategy)} entry triggered"


def _infer_sell_reason(
    strategy: str,
    signal_reasoning: str,
    pnl: float | None,
    pnl_pct: float | None,
    days_held: int | None,
) -> str:
    r = (signal_reasoning or "").lower()
    pct_str = f"{pnl_pct:+.1f}%" if pnl_pct is not None else None
    d = days_held
    if "stop" in r and "loss" in r:
        return (
            f"Stop-loss triggered — exited to limit downside ({pct_str} in {d}d)"
            if pct_str
            else "Stop-loss triggered"
        )
    if "profit target" in r or ("profit" in r and "target" in r):
        return (
            f"Hit our profit target — locked in gains ({pct_str} in {d}d)"
            if pct_str
            else "Profit target reached"
        )
    if "rsi" in r and any(w in r for w in [">", "recovery", "reversion", "complete"]):
        return (
            f"RSI recovered — stock bounced as expected ({pct_str})"
            if pct_str
            else "RSI recovered — reversion complete"
        )
    if any(w in r for w in ["rebalance", "held", "expired", "window", "drift"]):
        if pct_str and d is not None:
            return f"Planned {d}-day hold completed — closed at {pct_str}"
        if pct_str:
            return f"Planned exit — closed at {pct_str}"
    if pct_str and d is not None:
        return f"Closed after {d} days at {pct_str}"
    if pct_str:
        return f"Closed at {pct_str}"
    return f"{_short_strategy(strategy)} exit"


# ── Formatting helpers ────────────────────────────────────────────────────────
def fmt_money(v: float | None, sign: bool = False) -> str:
    if v is None:
        return "—"
    s = "+" if (sign and v >= 0) else ""
    return f"{s}${abs(v):,.2f}" if v < 0 and not sign else f"{s}${v:,.2f}"


def fmt_pct(v: float | None, digits: int = 1) -> str:
    if v is None:
        return "—"
    sign = "+" if v >= 0 else ""
    return f"{sign}{v:.{digits}f}%"


def pnl_color(v: float | None) -> str:
    if v is None or v == 0:
        return INK_DIM
    return GREEN if v > 0 else RED


def pnl_bg(v: float | None) -> str:
    if v is None or v == 0:
        return CARD_ALT
    return GREEN_BG if v > 0 else RED_BG


# ── Section: Hero ─────────────────────────────────────────────────────────────
def build_hero(
    pv: float,
    today_pnl: float,
    today_pct: float,
    date_str: str,
    equity: list[dict] | None = None,
) -> str:
    is_up = today_pnl >= 0
    arrow = "▲" if is_up else "▼"

    if today_pct >= 1.5:
        vibe = "Strong green day — the system delivered."
    elif today_pct >= 0.3:
        vibe = "Quiet gains. Slow and steady."
    elif today_pct > -0.3:
        vibe = "Flat tape. Markets were indecisive."
    elif today_pct > -1.5:
        vibe = "Tape leaned heavy today."
    else:
        vibe = "Rough session — losses taken in stride."

    chart_html = ""
    if equity and len(equity) >= 3:
        b64 = render_equity_sparkline(equity)
        if b64:
            window = len(equity)
            first = float(equity[0].get("total") or 0)
            last = float(equity[-1].get("total") or 0)
            window_pnl = last - first
            window_pct = (window_pnl / first * 100) if first else 0.0
            wcol = GREEN if window_pnl >= 0 else RED
            chart_html = f"""
      <div style="margin-top:20px;background:#e8f4fd;border-radius:10px;padding:4px 0 0;">
        <img src="data:image/png;base64,{b64}"
             style="display:block;width:100%;height:auto;border-radius:10px;" />
        <div style="display:flex;justify-content:space-between;
                    padding:8px 12px 10px;font-family:{FONT};
                    font-size:11px;color:#4a6580;font-weight:600;letter-spacing:0.03em;">
          <span>{window}-session window</span>
          <span style="color:{wcol};font-weight:700;">
            {'▲' if window_pnl >= 0 else '▼'} ${abs(window_pnl):,.2f} &nbsp;
            {window_pct:+.2f}%
          </span>
        </div>
      </div>"""

    return f"""
<div style="background:linear-gradient(160deg,#1e3a5f 0%,#0d2340 60%,#162b45 100%);
            padding:36px 32px 32px;border-radius:0 0 24px 24px;">

  <!-- Wordmark + date -->
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:28px;">
    <div style="font-family:{FONT};font-size:11px;font-weight:800;letter-spacing:0.28em;
                color:#7eb8e8;text-transform:uppercase;">Investor&nbsp;Mimic</div>
    <div style="font-family:{FONT};font-size:11px;color:#7eb8e8;letter-spacing:0.06em;
                font-weight:600;">{html_lib.escape(date_str)}</div>
  </div>

  <!-- Vibe line -->
  <div style="font-family:{DISPLAY};font-style:italic;font-size:18px;
              color:#a8cce8;line-height:1.3;margin-bottom:18px;
              letter-spacing:-0.01em;">{vibe}</div>

  <!-- Big number -->
  <div style="font-family:{DISPLAY};font-size:64px;font-weight:900;
              letter-spacing:-0.04em;color:#ffffff;line-height:1;
              margin-bottom:16px;">${pv:,.2f}</div>

  <!-- Today chip -->
  <div style="display:inline-flex;align-items:center;gap:8px;">
    <span style="display:inline-block;background:{'rgba(16,185,129,0.18)' if is_up else 'rgba(220,38,38,0.18)'};
                 color:{'#6ee7b7' if is_up else '#fca5a5'};
                 border:1.5px solid {'rgba(16,185,129,0.4)' if is_up else 'rgba(220,38,38,0.4)'};
                 font-family:{FONT};font-size:15px;font-weight:800;
                 padding:8px 18px;border-radius:999px;letter-spacing:-0.01em;">
      {arrow} ${abs(today_pnl):,.2f}
      <span style="opacity:0.80;font-weight:600;margin-left:8px;">{today_pct:+.2f}%</span>
    </span>
    <span style="font-family:{FONT};font-size:11px;color:#7eb8e8;
                 font-weight:600;letter-spacing:0.08em;text-transform:uppercase;">today</span>
  </div>

  {chart_html}
</div>
"""


# ── Section: Alert Banner ─────────────────────────────────────────────────────
def build_alert_banner(alerts: list[dict]) -> str:
    if not alerts:
        return ""
    has_critical = any(a.get("level") == "critical" for a in alerts)
    bg = RED_BG if has_critical else AMBER_BG
    border = RED_BORDER if has_critical else AMBER_BORDER
    ink = RED_DARK if has_critical else AMBER_DARK

    items = "".join(
        f"""<div style="display:flex;align-items:flex-start;gap:10px;
                        padding:10px 0;border-top:1px solid {border};">
              <span style="font-size:16px;flex-shrink:0;">{a.get('icon','⚠️')}</span>
              <span style="font-family:{FONT};font-size:13px;color:{ink};
                           font-weight:500;line-height:1.5;">{html_lib.escape(a['msg'])}</span>
            </div>"""
        for a in alerts
    )

    headline = "Action Needed" if has_critical else "Heads Up"
    return f"""
<div style="margin:16px 24px 0;background:{bg};border:1.5px solid {border};
            border-radius:16px;padding:18px 22px;">
  <div style="font-family:{FONT};font-size:10px;font-weight:800;letter-spacing:0.22em;
              color:{ink};text-transform:uppercase;margin-bottom:4px;">{headline}</div>
  {items}
</div>
"""


# ── Section: KPI Strip ────────────────────────────────────────────────────────
def build_kpi_strip(
    today_realized: float,
    total_pnl: float,
    win_rate: float | None,
    wins: int,
    losses: int,
    open_count: int,
) -> str:
    wr_str = f"{int(round(win_rate * 100))}%" if win_rate is not None else "—"
    wr_sub = f"{wins} wins · {losses} losses" if win_rate is not None else "No closed trades yet"
    wr_col = (
        GREEN
        if (win_rate and win_rate >= 0.5)
        else (RED if (win_rate and win_rate < 0.4) else AMBER)
    )

    def _card(
        label: str,
        value: str,
        val_col: str,
        sub: str,
        bg: str,
        border: str,
        lbl_col: str,
        tip: str = "",
    ) -> str:
        tip_html = (
            (
                f'<div style="font-family:{FONT};font-size:10px;color:{INK_MUTE};'
                f'margin-top:8px;line-height:1.4;font-weight:400;">{tip}</div>'
            )
            if tip
            else ""
        )
        return f"""
<td style="padding:20px 18px;background:{bg};border:1.5px solid {border};
           border-radius:16px;vertical-align:top;width:25%;">
  <div style="font-family:{FONT};font-size:9px;font-weight:800;letter-spacing:0.22em;
              color:{lbl_col};text-transform:uppercase;margin-bottom:10px;">{label}</div>
  <div style="font-family:{DISPLAY};font-size:28px;font-weight:900;letter-spacing:-0.03em;
              color:{val_col};line-height:1;">{value}</div>
  <div style="font-family:{FONT};font-size:11px;color:{INK_DIM};
              margin-top:6px;font-weight:500;">{sub}</div>
  {tip_html}
</td>"""

    today_bg = GREEN_BG if today_realized > 0 else (RED_BG if today_realized < 0 else CARD_ALT)
    today_border = (
        GREEN_BORDER if today_realized > 0 else (RED_BORDER if today_realized < 0 else BORDER)
    )
    today_lbl = GREEN_DARK if today_realized > 0 else (RED_DARK if today_realized < 0 else INK_MUTE)

    total_bg = GREEN_BG if total_pnl > 0 else (RED_BG if total_pnl < 0 else CARD_ALT)
    total_border = GREEN_BORDER if total_pnl > 0 else (RED_BORDER if total_pnl < 0 else BORDER)
    total_lbl = GREEN_DARK if total_pnl > 0 else (RED_DARK if total_pnl < 0 else INK_MUTE)

    return f"""
<div style="padding:20px 24px 4px;">
  <table style="width:100%;border-collapse:separate;border-spacing:10px 0;">
    <tr>
      {_card("Today's P&L", fmt_money(today_realized, sign=True),
             pnl_color(today_realized), "realized gains &amp; losses",
             today_bg, today_border, today_lbl,
             "Money actually made or lost from trades that closed today.")}
      {_card("All-Time P&L", fmt_money(total_pnl, sign=True),
             pnl_color(total_pnl), "since inception",
             total_bg, total_border, total_lbl,
             "Total profit or loss across every closed trade ever.")}
      {_card("Win Rate", wr_str, wr_col, wr_sub,
             AMBER_BG, AMBER_BORDER, AMBER_DARK,
             "% of closed trades that made money. Above 50% is profitable.")}
      {_card("Open Positions", str(open_count), BLUE, "stocks held right now",
             BLUE_BG, BLUE_BORDER, BLUE_DARK,
             "Stocks the system currently owns but hasn't sold yet.")}
    </tr>
  </table>
</div>
"""


# ── Section: Strategy Dashboard ───────────────────────────────────────────────
def build_strategy_dashboard(strategy_rows: list[dict]) -> str:
    if not strategy_rows:
        return ""

    # Mark Factor Momentum as disabled from config (regardless of DB status)
    disabled_names = {"Factor Momentum"}

    cards = []
    for row in strategy_rows:
        name = row.get("name") or ""
        open_count = int(row.get("open_count") or 0)
        unr = float(row.get("unrealized_total") or 0)
        db_status = (row.get("status") or "active").lower()

        is_disabled = name in disabled_names
        is_active = not is_disabled and db_status in ("active", "")

        ink, bg, border = STRAT_BRAND.get(name, (SLATE, SLATE_BG, SLATE_BORDER))

        if is_disabled:
            status_html = """
<span style="display:inline-block;background:#f1f5f9;color:#64748b;
             border:1px solid #cbd5e1;font-size:9px;font-weight:800;
             letter-spacing:0.18em;padding:3px 10px;border-radius:999px;">
  ⏸ PAUSED
</span>"""
        elif is_active:
            status_html = f"""
<span style="display:inline-block;background:{GREEN_BG};color:{GREEN_DARK};
             border:1px solid {GREEN_BORDER};font-size:9px;font-weight:800;
             letter-spacing:0.18em;padding:3px 10px;border-radius:999px;">
  ● ACTIVE
</span>"""
        else:
            status_html = f"""
<span style="display:inline-block;background:{AMBER_BG};color:{AMBER_DARK};
             border:1px solid {AMBER_BORDER};font-size:9px;font-weight:800;
             letter-spacing:0.18em;padding:3px 10px;border-radius:999px;">
  ⚠ {db_status.upper()}
</span>"""

        positions_line = (
            f"{open_count} position{'s' if open_count != 1 else ''} open"
            if is_active
            else "No positions"
        )
        unr_line = ""
        if is_active and open_count > 0:
            unr_col = GREEN_DARK if unr >= 0 else RED_DARK
            unr_bg = GREEN_BG if unr >= 0 else RED_BG
            unr_border = GREEN_BORDER if unr >= 0 else RED_BORDER
            unr_line = f"""
<div style="margin-top:10px;display:inline-block;
            background:{unr_bg};border:1px solid {unr_border};
            border-radius:8px;padding:5px 10px;">
  <span style="font-family:{MONO};font-size:13px;font-weight:700;
               color:{unr_col};">{fmt_money(unr, sign=True)}</span>
  <span style="font-family:{FONT};font-size:10px;color:{INK_DIM};
               margin-left:4px;">unrealized</span>
</div>"""

        explainer = STRATEGY_EXPLAINERS.get(name, "")
        explainer_html = ""
        if explainer:
            icon = "💡" if not is_disabled else "🔎"
            explainer_html = f"""
<div style="margin-top:14px;padding-top:12px;border-top:1px solid {border};">
  <div style="font-family:{FONT};font-size:11px;color:{INK_DIM};
              line-height:1.55;font-weight:400;">
    {icon} {html_lib.escape(explainer)}
  </div>
</div>"""

        cards.append(
            f"""
<td style="padding:6px;width:50%;vertical-align:top;">
  <div style="background:{bg};border:1.5px solid {border};border-radius:16px;
              padding:20px 20px 16px;height:100%;box-sizing:border-box;">
    <div style="display:flex;justify-content:space-between;
                align-items:flex-start;margin-bottom:10px;">
      <div>
        <div style="font-family:{FONT};font-size:15px;font-weight:800;
                    color:{ink};letter-spacing:-0.01em;">
          {html_lib.escape(name)}
        </div>
        <div style="font-family:{FONT};font-size:11px;color:{INK_MUTE};
                    margin-top:3px;font-weight:500;">{positions_line}</div>
      </div>
      {status_html}
    </div>
    {unr_line}
    {explainer_html}
  </div>
</td>"""
        )

    rows_html = ""
    for i in range(0, len(cards), 2):
        pair = cards[i : i + 2]
        if len(pair) == 1:
            pair.append('<td style="padding:6px;width:50%;"></td>')
        rows_html += "<tr>" + "".join(pair) + "</tr>"

    return f"""
<div style="padding:28px 24px 0;">
  <div style="font-family:{DISPLAY};font-size:26px;font-weight:900;font-style:italic;
              letter-spacing:-0.025em;color:{INK};margin-bottom:6px;">
    Your Strategies
  </div>
  <div style="font-family:{FONT};font-size:13px;color:{INK_DIM};
              margin-bottom:16px;line-height:1.5;">
    Your portfolio is run by multiple specialized strategies, each with its own
    logic and edge. Here's their current status.
  </div>
  <table style="width:100%;border-collapse:separate;border-spacing:0;">
    {rows_html}
  </table>
</div>
"""


# ── Section: Today's Tape ─────────────────────────────────────────────────────
def build_today_trades(
    trades: list[dict],
    sig_map: dict[tuple[str, str], dict],
    rejections: list[dict] | None = None,
    zero_trade_streak: int = 0,
) -> str:
    if not trades:
        streak_html = ""
        if zero_trade_streak >= 3:
            streak_html = f"""
<div style="margin-top:14px;padding:12px 16px;background:{AMBER_BG};
            border:1px solid {AMBER_BORDER};border-radius:10px;
            font-family:{FONT};font-size:12px;color:{AMBER_DARK};line-height:1.5;">
  💤 <strong>{zero_trade_streak} consecutive days</strong> with no trades. This is normal —
  the system only trades when its conditions are met. Patience is part of the strategy.
</div>"""

        rej_html = ""
        if rejections:
            rej_label_map = {
                "portfolio_heat": "Portfolio too concentrated",
                "insufficient_cash": "Not enough cash reserved",
                "correlation": "Too similar to existing position",
                "sector_concentration": "Sector limit reached",
                "max_positions_reached": "Already at max position count",
                "benchmark_etf_guard": "Symbol is a benchmark ETF",
                "cross_strategy_dedup": "Already held by another strategy",
                "wash_trade_guard": "Wash-trade prevention",
                "ml_risk_off": "AI model in risk-off mode",
                "size_reduced_to_zero": "Size calculation returned 0",
            }
            rej_rows = "".join(
                f"""<tr>
  <td style="font-family:{FONT};font-size:12px;color:{INK_DIM};padding:6px 0;">
    {html_lib.escape(rej_label_map.get(r.get('reason_code',''), r.get('reason_code','')))}
  </td>
  <td style="font-family:{MONO};font-size:12px;color:{INK_MUTE};text-align:right;
             padding:6px 0;">{r.get('cnt','')}×</td>
</tr>"""
                for r in rejections
            )
            rej_html = f"""
<div style="margin-top:16px;">
  <div style="font-family:{FONT};font-size:10px;font-weight:800;letter-spacing:0.18em;
              color:{INK_MUTE};text-transform:uppercase;margin-bottom:8px;">
    Why no trades fired today
  </div>
  <table style="width:100%;border-collapse:collapse;">{rej_rows}</table>
  <div style="font-family:{FONT};font-size:11px;color:{INK_MUTE};margin-top:8px;
              line-height:1.5;">
    💡 These are risk filters doing their job — protecting capital by declining
    low-quality or over-concentrated signals.
  </div>
</div>"""

        return f"""
<div style="padding:0 24px 4px;">
  <div style="background:{CARD};border:1.5px dashed {BORDER};border-radius:16px;
              padding:24px 26px;">
    <div style="font-family:{FONT};font-size:15px;font-weight:700;color:{INK};">
      Quiet day — no trades executed
    </div>
    <div style="font-family:{FONT};font-size:13px;color:{INK_DIM};margin-top:4px;">
      The system reviewed the market but didn't find opportunities worth acting on.
      Existing positions continue to be held.
    </div>
    {streak_html}{rej_html}
  </div>
</div>
"""

    rows = ""
    for t in trades:
        action = t.get("action") or ""
        sym = t.get("symbol") or ""
        shares = t.get("shares") or 0
        price = t.get("exec_price") or 0
        pnl = t.get("pnl")
        strat = t.get("strat") or ""
        is_buy = action == "BUY"

        sig = sig_map.get((sym, action)) or {}
        raw_reason = sig.get("reasoning") or ""

        s_ink, s_bg, s_border = STRAT_BRAND.get(strat, (SLATE, SLATE_BG, SLATE_BORDER))

        if is_buy:
            reason = _infer_buy_reason(strat, raw_reason)
            pnl_html = f'<span style="font-family:{FONT};font-size:12px;color:{INK_MUTE};">Position opened</span>'
            action_bg, action_fg, action_border = GREEN_BG, GREEN_DARK, GREEN_BORDER
            action_label = "BUY"
        else:
            pnl_pct = None
            if pnl is not None and t.get("notional"):
                try:
                    pnl_pct = (pnl / float(t["notional"])) * 100
                except Exception:
                    pass
            reason = _infer_sell_reason(strat, raw_reason, pnl, pnl_pct, None)
            col = pnl_color(pnl)
            pnl_html = (
                f'<span style="font-family:{MONO};font-size:14px;font-weight:800;color:{col};">'
                f'{fmt_money(pnl, sign=True) if pnl is not None else "—"}</span>'
            )
            action_bg, action_fg, action_border = RED_BG, RED_DARK, RED_BORDER
            action_label = "SELL"

        rows += f"""
<div style="padding:16px 0;border-top:1px solid {BORDER};display:flex;
            align-items:flex-start;gap:14px;">

  <!-- Action badge -->
  <div style="flex-shrink:0;padding-top:2px;">
    <span style="display:inline-block;background:{action_bg};color:{action_fg};
                 border:1.5px solid {action_border};font-family:{FONT};
                 font-size:10px;font-weight:800;letter-spacing:0.14em;
                 padding:4px 10px;border-radius:8px;">{action_label}</span>
  </div>

  <!-- Main content -->
  <div style="flex:1;min-width:0;">
    <div style="display:flex;justify-content:space-between;align-items:flex-start;">
      <div>
        <span style="font-family:{FONT};font-size:17px;font-weight:800;
                     color:{INK};letter-spacing:-0.02em;">{html_lib.escape(sym)}</span>
        <span style="font-family:{FONT};font-size:12px;color:{INK_MUTE};
                     margin-left:8px;">{int(shares)} shares @ ${price:,.2f}</span>
      </div>
      <div style="text-align:right;flex-shrink:0;padding-left:12px;">
        {pnl_html}
      </div>
    </div>
    <!-- Reason line -->
    <div style="font-family:{FONT};font-size:13px;color:{INK_DIM};
                margin-top:5px;line-height:1.45;">{html_lib.escape(reason)}</div>
    <!-- Strategy tag -->
    <div style="margin-top:7px;">
      <span style="display:inline-block;background:{s_bg};color:{s_ink};
                   border:1px solid {s_border};font-family:{FONT};font-size:10px;
                   font-weight:700;padding:2px 9px;border-radius:999px;
                   letter-spacing:0.04em;">{html_lib.escape(_short_strategy(strat))}</span>
    </div>
  </div>
</div>
"""

    return f"""
<div style="padding:0 24px 4px;">
  <div style="background:{CARD};border:1.5px solid {BORDER};border-radius:16px;
              padding:20px 24px;">
    {rows}
  </div>
</div>
"""


# ── Section: Movers ───────────────────────────────────────────────────────────
def build_movers(positions: list[dict], top_n: int = 3) -> str:
    if not positions or len(positions) < 2:
        return ""

    def _pnl(p: dict) -> float:
        return float(p.get("unrealized_pnl") or 0)

    sorted_pos = sorted(positions, key=_pnl, reverse=True)
    winners = [p for p in sorted_pos if _pnl(p) > 0][:top_n]
    losers = list(reversed([p for p in sorted_pos if _pnl(p) < 0][-top_n:]))

    def _row(p: dict, side: str) -> str:
        sym = p.get("symbol") or ""
        unr = _pnl(p)
        entry = float(p.get("entry_price") or p.get("avg_price") or 0)
        curr = float(p.get("current_price") or entry)
        pct = ((curr - entry) / entry * 100) if entry else 0.0
        c = GREEN if side == "win" else RED
        return f"""
<tr>
  <td style="padding:8px 0;font-family:{FONT};font-size:14px;font-weight:700;
             color:{INK};">{html_lib.escape(sym)}</td>
  <td style="padding:8px 0;text-align:right;font-family:{MONO};font-size:13px;
             font-weight:700;color:{c};">{fmt_money(unr, sign=True)}</td>
  <td style="padding:8px 0 8px 12px;text-align:right;font-family:{FONT};
             font-size:11px;font-weight:600;color:{c};">{fmt_pct(pct)}</td>
</tr>"""

    def _col(title: str, items: list[dict], side: str, bg: str, bdr: str, fg: str) -> str:
        if not items:
            inner = (
                f'<div style="padding:16px 0;font-family:{FONT};font-size:13px;'
                f'color:{INK_MUTE};text-align:center;">'
                + ("No winners yet" if side == "win" else "No losing positions")
                + "</div>"
            )
        else:
            inner = (
                '<table style="width:100%;border-collapse:collapse;">'
                + "".join(_row(p, side) for p in items)
                + "</table>"
            )
        emoji = "📈" if side == "win" else "📉"
        return f"""
<td style="padding:6px;width:50%;vertical-align:top;">
  <div style="background:{bg};border:1.5px solid {bdr};border-radius:14px;padding:18px 20px;">
    <div style="font-family:{FONT};font-size:11px;font-weight:800;letter-spacing:0.16em;
                color:{fg};text-transform:uppercase;margin-bottom:12px;">
      {emoji} {title}
    </div>
    {inner}
  </div>
</td>"""

    return f"""
<div style="padding:0 24px 4px;">
  <table style="width:100%;border-collapse:separate;border-spacing:10px 0;">
    <tr>
      {_col("Top Winners", winners, "win", GREEN_BG, GREEN_BORDER, GREEN_DARK)}
      {_col("Watch List", losers, "loss", RED_BG, RED_BORDER, RED_DARK)}
    </tr>
  </table>
</div>
"""


# ── Section: Open Positions ───────────────────────────────────────────────────
def build_positions(positions: list[dict]) -> str:
    if not positions:
        return f"""
<div style="padding:0 24px 4px;font-family:{FONT};font-size:13px;color:{INK_DIM};">
  No open positions right now.
</div>
"""
    cards: list[str] = []
    for p in positions:
        sym = p.get("symbol") or ""
        shares = p.get("shares") or 0
        entry = p.get("entry_price") or p.get("avg_price") or 0
        curr = p.get("current_price") or entry
        unr = p.get("unrealized_pnl") or 0
        days = p.get("days_held")
        stop = p.get("stop_loss_price")
        strat = p.get("strat") or ""
        ret_pct = ((curr - entry) / entry * 100) if entry else 0
        is_up = unr >= 0
        col = pnl_color(unr)
        rail_col = GREEN if is_up else RED
        s_ink, s_bg, s_border = STRAT_BRAND.get(strat, (SLATE, SLATE_BG, SLATE_BORDER))

        chart_b64 = render_sparkline(sym, entry_price=float(entry) if entry else None)
        chart_html = (
            f'<img src="data:image/png;base64,{chart_b64}" '
            f'style="display:block;width:100%;height:auto;border-radius:8px;" />'
            if chart_b64
            else f'<div style="height:56px;background:{CARD_ALT};border-radius:8px;"></div>'
        )

        # Stop loss distance indicator
        stop_html = ""
        if stop and curr:
            stop_dist = (curr - float(stop)) / curr * 100
            stop_col = RED if stop_dist < 5 else (AMBER if stop_dist < 10 else INK_MUTE)
            stop_html = f"""
<div style="margin-top:8px;padding:7px 10px;background:{CARD_ALT};
            border-radius:8px;display:flex;justify-content:space-between;
            align-items:center;">
  <span style="font-family:{FONT};font-size:10px;color:{INK_MUTE};font-weight:600;
               letter-spacing:0.08em;">STOP LOSS</span>
  <span style="font-family:{MONO};font-size:12px;font-weight:700;color:{stop_col};">
    ${float(stop):,.2f}
    <span style="font-family:{FONT};font-size:10px;font-weight:500;color:{stop_col};
                 margin-left:4px;">({stop_dist:.1f}% away)</span>
  </span>
</div>"""

        days_html = (
            f'<span style="font-family:{FONT};font-size:10px;color:{INK_MUTE};"> · {days}d held</span>'
            if days is not None
            else ""
        )

        cards.append(
            f"""
<td style="padding:6px;width:50%;vertical-align:top;">
  <div style="background:{CARD};border:1.5px solid {BORDER};border-radius:16px;
              padding:16px 18px 14px;position:relative;overflow:hidden;">
    <div style="position:absolute;left:0;top:0;bottom:0;width:4px;background:{rail_col};
                border-radius:4px 0 0 4px;"></div>
    <div style="display:flex;justify-content:space-between;align-items:flex-start;
                margin-bottom:10px;">
      <div>
        <div style="font-family:{FONT};font-size:20px;font-weight:800;color:{INK};
                    letter-spacing:-0.025em;line-height:1;">{html_lib.escape(sym)}</div>
        <div style="margin-top:4px;">
          <span style="display:inline-block;background:{s_bg};color:{s_ink};
                       border:1px solid {s_border};font-size:9px;font-weight:700;
                       padding:2px 8px;border-radius:999px;letter-spacing:0.04em;">
            {html_lib.escape(_short_strategy(strat))}
          </span>
          <span style="font-family:{FONT};font-size:11px;color:{INK_MUTE};">
            &nbsp;{int(shares)} shares{days_html}
          </span>
        </div>
      </div>
      <div style="text-align:right;">
        <div style="font-family:{MONO};font-size:16px;font-weight:800;color:{col};
                    letter-spacing:-0.01em;">{fmt_money(unr, sign=True)}</div>
        <div style="font-family:{FONT};font-size:12px;color:{col};font-weight:600;
                    margin-top:2px;">{fmt_pct(ret_pct)}</div>
      </div>
    </div>
    <div style="margin-bottom:10px;">{chart_html}</div>
    <table style="width:100%;border-collapse:collapse;">
      <tr>
        <td style="font-family:{FONT};font-size:10px;color:{INK_MUTE};letter-spacing:0.10em;
                   font-weight:600;">BOUGHT AT</td>
        <td style="font-family:{MONO};font-size:12px;color:{INK_DIM};text-align:right;">
          ${entry:,.2f}</td>
        <td style="font-family:{FONT};font-size:10px;color:{INK_MUTE};letter-spacing:0.10em;
                   font-weight:600;text-align:right;padding-left:14px;">NOW</td>
        <td style="font-family:{MONO};font-size:12px;color:{INK};font-weight:700;
                   text-align:right;padding-left:6px;">${curr:,.2f}</td>
      </tr>
    </table>
    {stop_html}
  </div>
</td>"""
        )

    rows_html = ""
    for i in range(0, len(cards), 2):
        pair = cards[i : i + 2]
        if len(pair) == 1:
            pair.append('<td style="padding:6px;width:50%;"></td>')
        rows_html += "<tr>" + "".join(pair) + "</tr>"

    tip_html = f"""
<div style="margin-bottom:14px;padding:12px 16px;background:{BLUE_BG};
            border:1px solid {BLUE_BORDER};border-radius:10px;">
  <span style="font-family:{FONT};font-size:11px;color:{BLUE_DARK};line-height:1.5;">
    💡 <strong>How to read these cards:</strong> The colored bar on the left
    shows green (profitable) or red (losing). The "stop loss" price is the automatic
    exit price if the stock falls too far — it limits your downside.
  </span>
</div>"""

    return f"""
<div style="padding:0 24px 4px;">
  {tip_html}
  <table style="width:100%;border-collapse:separate;border-spacing:0;">
    {rows_html}
  </table>
</div>
"""


# ── Section: News Digest ──────────────────────────────────────────────────────
_NEWS_CACHE_PATH = Path("/tmp/imb_news_cache.json")


def _load_news_cache() -> dict[str, dict]:
    if not _NEWS_CACHE_PATH.exists():
        return {}
    try:
        import json as _json

        data = _json.loads(_NEWS_CACHE_PATH.read_text())
        if data.get("date") == datetime.now().strftime("%Y-%m-%d"):
            return {str(k): dict(v) for k, v in (data.get("symbols") or {}).items()}
    except Exception:
        pass
    return {}


def _save_news_cache(symbols: dict[str, dict]) -> None:
    try:
        import json as _json

        _NEWS_CACHE_PATH.write_text(
            _json.dumps(
                {"date": datetime.now().strftime("%Y-%m-%d"), "symbols": symbols},
                ensure_ascii=False,
            )
        )
    except Exception:
        pass


def _fetch_position_news(symbols: list[str]) -> dict[str, dict]:
    cache = _load_news_cache()
    missing = [s for s in symbols if s not in cache]
    if missing:
        try:
            from src.utils.news_sentiment import NewsSentimentProvider

            provider = NewsSentimentProvider(max_workers=8, per_symbol_timeout=5.0)
            fresh = provider.fetch_batch(missing)
            cache.update(fresh)
            _save_news_cache(cache)
        except Exception:
            pass
    return {s: cache.get(s, {"headlines": [], "score": 0.5}) for s in symbols}


def _tone_chip(score: float) -> str:
    if score >= 0.62:
        bg, fg, border, label = GREEN_BG, GREEN_DARK, GREEN_BORDER, "BULLISH"
    elif score <= 0.38:
        bg, fg, border, label = RED_BG, RED_DARK, RED_BORDER, "BEARISH"
    else:
        bg, fg, border, label = CARD_ALT, INK_DIM, BORDER, "NEUTRAL"
    return (
        f'<span style="display:inline-block;background:{bg};color:{fg};border:1px solid {border};'
        f'font-size:9px;font-weight:800;letter-spacing:0.16em;padding:2px 8px;border-radius:6px;">'
        f"{label}</span>"
    )


def _position_context(positions: list[dict], symbol: str) -> dict:
    for p in positions:
        if (p.get("symbol") or "").upper() == symbol:
            shares = float(p.get("shares") or 0)
            avg = float(p.get("avg_price") or 0)
            unr = float(p.get("unrealized_pnl") or 0)
            cost = shares * avg
            unr_pct = (unr / cost * 100) if cost > 0 else 0.0
            return {"qty": shares, "today_pnl": unr, "today_pct": unr_pct, "unrealized_pnl": unr}
    return {}


def build_news_digest(
    positions: list[dict], traded_today: list[str] | None = None, max_stories: int = 6
) -> str:
    if not positions:
        return ""
    traded_set = {s.upper() for s in (traded_today or [])}
    all_symbols = list(
        dict.fromkeys((p.get("symbol") or "").upper() for p in positions if p.get("symbol"))
    )
    if not all_symbols:
        return ""
    news_map = _fetch_position_news(all_symbols)

    def _rank_key(s: str) -> tuple[int, float, float]:
        ctx = news_map.get(s, {})
        articles = ctx.get("articles") or []
        best_q = max((a.get("quality", 0.0) for a in articles), default=0.0)
        sent_mag = abs(float(ctx.get("score", 0.5)) - 0.5)
        traded_bonus = 1 if s in traded_set else 0
        return (traded_bonus, best_q, sent_mag)

    ranked = sorted(
        [s for s in all_symbols if news_map.get(s, {}).get("articles")],
        key=_rank_key,
        reverse=True,
    )[:max_stories]

    if not ranked:
        return f"""
<div style="padding:0 24px 4px;">
  <div style="background:{CARD};border:1.5px dashed {BORDER};border-radius:16px;
              padding:20px 24px;text-align:center;">
    <div style="font-family:{FONT};font-size:13px;color:{INK_DIM};">
      No fresh headlines for today's holdings.
    </div>
  </div>
</div>
"""

    summarizer = None
    try:
        from src.utils.news_summarizer import NewsSummarizer

        summarizer = NewsSummarizer()
    except Exception:
        pass

    blocks = []
    for sym in ranked:
        ctx = news_map[sym]
        articles: list[dict] = ctx.get("articles") or []
        if not articles:
            continue
        lead = articles[0]
        score = float(ctx.get("score", 0.5))
        chip = _tone_chip(score)
        pos_ctx = _position_context(positions, sym)
        is_traded = sym in traded_set

        why = ""
        if summarizer is not None:
            try:
                why = summarizer.summarize_for_position(sym, articles, pos_ctx, score)
            except Exception:
                why = ""

        pos_strap = ""
        if pos_ctx.get("qty", 0) > 0:
            unr = float(pos_ctx.get("unrealized_pnl") or 0)
            unr_pct = float(pos_ctx.get("today_pct") or 0)
            unr_col = GREEN if unr >= 0 else RED
            pos_strap = (
                f'<div style="font-family:{FONT};font-size:11px;color:{INK_MUTE};'
                f'margin-top:6px;line-height:1.45;">'
                f'You hold {pos_ctx["qty"]:.0f} shares · '
                f'<span style="color:{unr_col};font-weight:700;">'
                f"{fmt_money(unr, sign=True)} ({unr_pct:+.2f}%) unrealized</span></div>"
            )

        traded_badge = (
            f'<span style="display:inline-block;background:{AMBER_BG};color:{AMBER_DARK};'
            f"border:1px solid {AMBER_BORDER};font-size:9px;font-weight:800;"
            f'letter-spacing:0.14em;padding:2px 8px;border-radius:6px;margin-left:6px;">'
            f"TRADED TODAY</span>"
            if is_traded
            else ""
        )

        headline_html = html_lib.escape(lead.get("title", ""))
        link = lead.get("link", "")
        if link:
            headline_html = (
                f'<a href="{html_lib.escape(link)}" target="_blank" '
                f'style="color:{INK};text-decoration:none;">{headline_html}</a>'
            )

        meta_bits = []
        if lead.get("source"):
            meta_bits.append(html_lib.escape(lead["source"]))
        if lead.get("age"):
            meta_bits.append(html_lib.escape(lead["age"]))
        meta_html = (
            f'<div style="font-family:{FONT};font-size:10px;color:{INK_MUTE};margin-top:8px;'
            f'letter-spacing:0.06em;font-weight:600;text-transform:uppercase;">'
            + " · ".join(meta_bits)
            + "</div>"
            if meta_bits
            else ""
        )

        why_html = (
            f'<div style="font-family:{DISPLAY};font-style:italic;font-size:13px;'
            f'color:{INK_DIM};margin-top:10px;line-height:1.5;">{html_lib.escape(why)}</div>'
            if why
            else ""
        )

        blocks.append(
            f"""
<div style="padding:20px 24px;border-bottom:1px solid {PURPLE_BG};">
  <div style="margin-bottom:10px;display:flex;flex-wrap:wrap;gap:6px;align-items:center;">
    <span style="display:inline-block;background:{PURPLE_BG};color:{PURPLE_DARK};
                 border:1px solid {PURPLE_BORDER};font-family:{FONT};font-size:11px;
                 font-weight:800;padding:3px 10px;border-radius:999px;letter-spacing:0.06em;">
      {html_lib.escape(sym)}
    </span>
    {chip}{traded_badge}
    {pos_strap}
  </div>
  <div style="font-family:{DISPLAY};font-size:18px;font-weight:700;color:{INK};
              line-height:1.35;letter-spacing:-0.01em;">
    <span style="color:{PURPLE};font-size:26px;line-height:0;vertical-align:-6px;
                 margin-right:3px;">"</span>{headline_html}
  </div>
  {why_html}{meta_html}
</div>"""
        )

    llm_label = (
        "AI-summarized via LLM · headlines via Google News"
        if summarizer is not None and summarizer.llm_enabled
        else "Headlines via Google News"
    )

    return f"""
<div style="padding:0 24px 4px;">
  <div style="background:{CARD};border:1.5px solid {PURPLE_BORDER};border-radius:18px;
              overflow:hidden;">
    {''.join(blocks)}
    <div style="padding:10px 20px;background:{PURPLE_BG};font-size:10px;color:{PURPLE};
                letter-spacing:0.08em;font-weight:700;text-transform:uppercase;">
      Market Intel · {llm_label}
    </div>
  </div>
</div>
"""


# ── Section: System Status ────────────────────────────────────────────────────
def build_system_status(recon_status: str, fill_summary: dict, db_path: str) -> str:
    recon_upper = (recon_status or "").upper()
    recon_ok = "SYNCED" in recon_upper or "PASS" in recon_upper
    recon_label = "Account balanced with broker" if recon_ok else f"Sync issue: {recon_status}"

    # Fill quality row
    fill_count = int(fill_summary.get("fill_count") or 0)
    avg_dev = fill_summary.get("avg_dev")
    fill_ok = fill_count == 0 or (avg_dev is not None and float(avg_dev) < 30)
    fill_label = (
        "No fills today — no quality data"
        if fill_count == 0
        else f"{fill_count} fills · avg {float(avg_dev or 0):.0f} bps slippage"
    )

    # Live readiness (keep existing check)
    readiness_html = ""
    try:
        from check_live_readiness import evaluate_readiness

        result = evaluate_readiness(db_path)
        ready = result.get("ready")
        passed = result.get("passed", 0)
        total = result.get("total", 0)
        r_ok = bool(ready)
        checks_html = ""
        for c in result.get("checks", []):
            ok = c.get("ok")
            dot = GREEN if ok else RED
            checks_html += f"""
<div style="display:flex;justify-content:space-between;padding:7px 0;
            border-top:1px solid {BORDER};">
  <span style="font-family:{FONT};font-size:12px;color:{INK_DIM};">
    <span style="display:inline-block;width:7px;height:7px;border-radius:50%;
                 background:{dot};margin-right:8px;vertical-align:middle;"></span>
    {html_lib.escape(c.get('label',''))}
  </span>
  <span style="font-family:{MONO};font-size:12px;color:{INK_DIM};font-weight:600;">
    {html_lib.escape(c.get('display','—'))}
    <span style="font-family:{FONT};font-size:10px;color:{INK_MUTE};margin-left:4px;">
      {html_lib.escape(c.get('target',''))}
    </span>
  </span>
</div>"""
        readiness_html = f"""
<div style="margin-top:14px;padding-top:14px;border-top:2px dashed {BORDER};">
  <div style="font-family:{FONT};font-size:10px;font-weight:800;letter-spacing:0.18em;
              color:{INK_MUTE};text-transform:uppercase;margin-bottom:8px;">
    Live Trading Readiness
  </div>
  <div style="font-family:{FONT};font-size:12px;color:{INK_DIM};margin-bottom:8px;">
    {'✅ Ready to trade with real money' if r_ok else f'⏳ Not yet — {total - passed} check(s) remaining'}
  </div>
  {checks_html}
</div>"""
    except Exception:
        pass

    def _status_row(label: str, detail: str, ok: bool) -> str:
        icon = "✅" if ok else "⚠️"
        return f"""
<div style="display:flex;justify-content:space-between;align-items:center;
            padding:10px 0;border-top:1px solid {BORDER};">
  <span style="font-family:{FONT};font-size:13px;color:{INK};">
    <span style="margin-right:8px;">{icon}</span>{label}
  </span>
  <span style="font-family:{FONT};font-size:12px;color:{INK_DIM};">{html_lib.escape(detail)}</span>
</div>"""

    ts = datetime.now().strftime("%Y-%m-%d %H:%M ET")
    return f"""
<div style="padding:0 24px 4px;">
  <div style="background:{CARD};border:1.5px solid {BORDER};border-radius:16px;padding:20px 24px;">
    <div style="font-family:{FONT};font-size:10px;font-weight:800;letter-spacing:0.18em;
                color:{INK_MUTE};text-transform:uppercase;margin-bottom:4px;">System Status</div>
    <div style="font-family:{FONT};font-size:11px;color:{INK_MUTE};margin-bottom:12px;">
      Generated {ts}
    </div>
    {_status_row("Broker reconciliation", recon_label, recon_ok)}
    {_status_row("Fill quality", fill_label, fill_ok)}
    {readiness_html}
  </div>
</div>
"""


# ── Section header helper ─────────────────────────────────────────────────────
def _section_title(text: str, sub: str = "", count: int | None = None, accent: str = BLUE) -> str:
    badge = (
        f'<span style="margin-left:10px;display:inline-block;font-family:{FONT};font-size:11px;'
        f"font-weight:800;color:{BLUE_DARK};background:{BLUE_BG};border:1px solid {BLUE_BORDER};"
        f'padding:2px 10px;border-radius:999px;">{count}</span>'
        if count is not None and count > 0
        else ""
    )
    sub_html = (
        f'<div style="font-family:{FONT};font-size:12px;color:{INK_MUTE};'
        f'margin-top:4px;font-weight:400;">{html_lib.escape(sub)}</div>'
        if sub
        else ""
    )
    return f"""
<div style="padding:28px 24px 12px;">
  <div style="font-family:{DISPLAY};font-size:24px;font-weight:900;font-style:italic;
              letter-spacing:-0.025em;color:{INK};line-height:1.05;">
    {html_lib.escape(text)}{badge}
  </div>
  {sub_html}
  <div style="margin-top:8px;width:40px;height:3px;background:{accent};border-radius:3px;"></div>
</div>
"""


# ── Footer ────────────────────────────────────────────────────────────────────
def build_footer() -> str:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"""
<div style="padding:28px 24px 36px;border-top:2px solid {BORDER};margin-top:24px;
            background:{PAGE_BG};">
  <div style="font-family:{FONT};font-size:11px;color:{INK_MUTE};
              line-height:1.6;max-width:520px;">
    <strong style="color:{INK_DIM};">Investor Mimic</strong> is a fully automated paper-trading
    system. All trades are simulated — no real money is at risk. Past paper performance
    does not guarantee live trading results.
  </div>
  <div style="font-family:{FONT};font-size:10px;color:{INK_MUTE};
              margin-top:10px;letter-spacing:0.06em;">
    Generated {ts} · Paper trading only
  </div>
</div>
"""


# ── Main entry ────────────────────────────────────────────────────────────────
def generate_email_body(db_path: str = "trading.db", include_visuals: bool = True) -> str:
    db = _conn(db_path)
    try:
        snap = get_latest_snapshot(db)
        equity = get_equity_curve(db, days=30)
        trades_today = get_today_trades(db)
        positions = get_open_positions(db)
        agg = get_aggregate_pnl(db)
        symbols: list[str] = list({str(s) for t in trades_today if (s := t.get("symbol"))})
        sig_map = get_signal_reasons(db, symbols)
        run_id = get_latest_run_id(db)
        rejections = get_rejection_summary(db, run_id) if not trades_today else []
        zero_streak = get_zero_trade_streak(db) if not trades_today else 0
        strategy_rows = get_strategy_statuses(db)
        fill_summary = get_fill_quality_summary(db)
    finally:
        db.close()

    pv = float(snap.get("portfolio_value") or 0)
    recon = snap.get("reconciliation_status") or "UNKNOWN"

    today_pnl = 0.0
    today_pct = 0.0
    if len(equity) >= 2:
        prev = equity[-2]["total"]
        curr_e = equity[-1]["total"]
        today_pnl = (curr_e or 0) - (prev or 0)
        today_pct = (today_pnl / prev * 100) if prev else 0.0

    today_real = float(agg.get("today_realized") or 0)
    total_pnl = float(agg.get("total_pnl") or 0)
    wins = int(agg.get("wins") or 0)
    closed = int(agg.get("closed") or 0)
    losses = closed - wins
    win_rate = (wins / closed) if closed else None

    date_str = datetime.now().strftime("%A, %B %-d")

    # Compute alerts using a transient conn (db is already closed)
    db2 = _conn(db_path)
    try:
        alerts = get_system_alerts(db2, recon, zero_streak)
    finally:
        db2.close()

    traded_today_syms = [t.get("symbol", "") for t in trades_today if t.get("symbol")]

    body = (
        build_hero(pv, today_pnl, today_pct, date_str, equity=equity)
        + build_alert_banner(alerts)
        + build_kpi_strip(today_real, total_pnl, win_rate, wins, losses, len(positions))
        + build_strategy_dashboard(strategy_rows)
        + _section_title(
            "Today's Tape",
            sub="What the system bought and sold — and why."
            if trades_today
            else "No trades executed today.",
            count=len(trades_today),
            accent=AMBER,
        )
        + build_today_trades(
            trades_today, sig_map, rejections=rejections, zero_trade_streak=zero_streak
        )
        + _section_title(
            "Movers & Shakers", sub="Best and worst positions right now.", accent=GREEN
        )
        + build_movers(positions)
        + _section_title(
            "What You Own",
            sub="Every open position with price history and stop losses.",
            count=len(positions),
            accent=BLUE,
        )
        + build_positions(positions)
        + _section_title(
            "Market Intel",
            sub="News on the stocks you hold — ranked by relevance to your positions.",
            accent=PURPLE,
        )
        + build_news_digest(positions, traded_today=traded_today_syms)
        + _section_title("System Status", sub="How the engine performed today.", accent=SLATE)
        + build_system_status(recon, fill_summary, db_path)
        + build_footer()
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Investor Mimic · Daily</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Fraunces:opsz,ital,wght@9..144,0,700;9..144,0,900;9..144,1,500;9..144,1,700;9..144,1,900&display=swap" rel="stylesheet">
  <style>
    body, table, td, div, p, span, a {{
      font-family: {FONT};
      -webkit-font-smoothing: antialiased;
      -moz-osx-font-smoothing: grayscale;
      text-rendering: optimizeLegibility;
      box-sizing: border-box;
    }}
    a {{ color: inherit; }}
    img {{ border: 0; display: block; }}
  </style>
</head>
<body style="margin:0;padding:0;background:{PAGE_BG};color:{INK};">
  <div style="max-width:700px;margin:0 auto;background:{PAGE_BG};">
    {body}
  </div>
</body>
</html>"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--include-visuals", action="store_true", help="Compatibility flag — visuals always on now."
    )
    parser.add_argument("--send", action="store_true")
    parser.add_argument("--db", default="trading.db")
    args = parser.parse_args()

    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    html = generate_email_body(db_path=args.db, include_visuals=True)
    out_path = "/tmp/daily_email.html"
    Path(out_path).write_text(html, encoding="utf-8")
    print(f"✅ Email HTML generated: {out_path}")

    if args.send:
        from src.utils.email_notifier import EmailNotifier

        notifier = EmailNotifier()
        if not notifier.enabled:
            print("❌ Email disabled — set SENDER_EMAIL, SENDER_PASSWORD, RECIPIENT_EMAIL")
            return 1
        date_str = datetime.now().strftime("%Y-%m-%d")
        try:
            notifier._send_email(f"Trading · {date_str}", html, is_html=True)
            print("✅ Email sent.")
        except Exception as exc:
            print(f"❌ Send failed: {exc}")
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
