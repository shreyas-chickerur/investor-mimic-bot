#!/usr/bin/env python3
"""
Daily Email Digest — minimal, Apple-Watch-Activity / Nike inspired.

Design philosophy:
    * Pure black background, volt-green accent, big condensed numerals.
    * No jargon, no walls of text, no unverifiable narratives.
    * Shows ONLY what matters: today's P&L, total P&L, win rate, open
      positions, today's trades with concrete reasons, and a small price
      chart per stock we touched.

Removed from previous version:
    * "News → noticed → decided" 3-box flowchart — we cannot prove
      causality between headlines and price moves, so we don't claim it.
    * Generic "we held this position for the planned duration" string —
      every exit reason is now computed from real trade math.
    * Strategy concerns wall, regime chrome, redundant metrics.

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

# ── Palette (Apple Activity light / Nike volt) ───────────────────────────────
# Light theme: every email client renders this consistently. Dark email
# templates get inverted or stripped by Gmail/Outlook, leading to invisible text.
BG = "#f5f5f0"  # soft warm off-white (page background)
CARD = "#ffffff"  # cards on top of BG
CARD_ALT = "#f0f0eb"  # subtle alt fill
BORDER = "#e6e6e0"  # soft hairline
TEXT = "#111111"  # primary copy
TEXT_DIM = "#5e5e5e"  # secondary copy
TEXT_MUTE = "#9a9a9a"  # tertiary / labels
VOLT = "#76b900"  # Nike-volt deep — readable on white
VOLT_SOFT = "#e8ffd4"  # volt tint for badge backgrounds
LOSS = "#d63031"  # warm red for losses
LOSS_SOFT = "#ffe1e1"

FONT = (
    'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, '
    '"Helvetica Neue", Arial, sans-serif'
)
MONO = '"SF Mono", "JetBrains Mono", "Roboto Mono", Menlo, Consolas, monospace'

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


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
    snap = _q1(
        db,
        """
        SELECT portfolio_value, cash, reconciliation_status, snapshot_date
        FROM broker_state
        WHERE snapshot_type IN ('RECONCILIATION', 'RECONCILIATION_RETRY',
                                'END', 'SYNC', 'START')
        ORDER BY created_at DESC, id DESC LIMIT 1
    """,
    )
    return snap or {}


def get_equity_curve(db, days: int = 30) -> list[dict]:
    return _q(
        db,
        """
        SELECT snapshot_date AS date, MAX(portfolio_value) AS total
        FROM broker_state
        WHERE snapshot_type IN ('START', 'END')
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
    """Most-recent executed signal per (symbol, signal_type), today only."""
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


def get_aggregate_pnl(db) -> dict:
    row = _q1(
        db,
        """
        SELECT COUNT(*)                                     AS closed,
               SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END)     AS wins,
               SUM(COALESCE(pnl, 0))                        AS total_pnl,
               SUM(CASE WHEN DATE(executed_at)=DATE('now')
                        THEN COALESCE(pnl,0) ELSE 0 END)    AS today_realized
        FROM trades
        WHERE pnl IS NOT NULL
    """,
    )
    return row or {}


# ── Per-symbol price chart (matplotlib → base64 PNG) ─────────────────────────
_CHART_CACHE: dict[str, str] = {}


def _load_price_history() -> dict[str, list[tuple[str, float]]] | None:
    """Load close-price history per symbol from data/training_data.csv."""
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
    """Return a base64 PNG sparkline for the given symbol. Empty string if unavailable."""
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
    line_color = VOLT if is_up else LOSS

    fig, ax = plt.subplots(figsize=(3.4, 0.9), dpi=140)
    fig.patch.set_facecolor(CARD)
    ax.set_facecolor(CARD)
    ax.plot(range(len(closes)), closes, color=line_color, linewidth=1.6)
    ax.fill_between(range(len(closes)), closes, min(closes), color=line_color, alpha=0.12)
    if entry_price and min(closes) <= entry_price <= max(closes):
        ax.axhline(entry_price, color=TEXT_DIM, linewidth=0.6, linestyle=(0, (2, 3)))
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.margins(x=0.01, y=0.15)
    plt.tight_layout(pad=0.1)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor=CARD, edgecolor="none")
    plt.close(fig)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    _CHART_CACHE[cache_key] = b64
    return b64


def render_equity_sparkline(equity: list[dict]) -> str:
    """
    Render a wide sparkline of portfolio value over the equity curve window.

    Used inside the hero card. Returns a base64 PNG, or empty string on any
    failure (chart rendering is non-critical and must never block the email).
    """
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
    line_color = VOLT if is_up else LOSS

    fig, ax = plt.subplots(figsize=(7.2, 1.4), dpi=140)
    fig.patch.set_facecolor(CARD)
    ax.set_facecolor(CARD)
    ax.plot(range(len(values)), values, color=line_color, linewidth=2.0)
    ax.fill_between(range(len(values)), values, min(values), color=line_color, alpha=0.14)
    # baseline of starting value to anchor the eye
    ax.axhline(values[0], color=TEXT_DIM, linewidth=0.6, linestyle=(0, (2, 3)))
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.margins(x=0.005, y=0.18)
    plt.tight_layout(pad=0.05)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor=CARD, edgecolor="none")
    plt.close(fig)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    _CHART_CACHE[cache_key] = b64
    return b64


# ── Reason inference (computed, not guessed) ─────────────────────────────────
def _short_strategy(name: str) -> str:
    return {
        "RSI Mean Reversion": "Bounce",
        "ML Momentum": "AI Model",
        "Earnings Drift": "Earnings",
        "Factor Momentum": "Top Rank",
    }.get(name or "", name or "")


def _infer_buy_reason(strategy: str, signal_reasoning: str) -> str:
    """Concrete, signal-driven entry rationale. No generic fallbacks where avoidable."""
    r = (signal_reasoning or "").lower()
    import re

    m = re.search(r"rsi[^a-z0-9]?(\d{1,2}(?:\.\d+)?)", r)
    if "rsi" in r and m:
        return f"RSI at {m.group(1)} — oversold, turning up"
    if "rsi" in r:
        return "RSI signaled oversold reversal"

    m = re.search(r"p\(up\)\s*[=:]?\s*([\d.]+)", r)
    if m:
        return f"AI: {int(float(m.group(1)) * 100)}% probability up next 5d"
    m = re.search(r"confidence[^0-9]*([\d.]+)", r)
    if m and float(m.group(1)) <= 1.0:
        return f"AI confidence {int(float(m.group(1)) * 100)}%"

    m = re.search(r"volume[_\s]*ratio[=:\s]*([\d.]+)", r)
    if m:
        return f"Volume {float(m.group(1)):.1f}× normal — earnings move"

    m = re.search(r"top\s*(\d+)\s*/\s*(\d+)", r)
    if m:
        return f"Ranked #{m.group(1)} of {m.group(2)} on momentum+quality"
    if "factor" in r or "composite" in r:
        return "Top-tier composite score across momentum+quality"

    return f"{_short_strategy(strategy)} entry triggered"


def _infer_sell_reason(
    strategy: str,
    signal_reasoning: str,
    pnl: float | None,
    pnl_pct: float | None,
    days_held: int | None,
) -> str:
    """Always specific — pulls from numbers if signal reasoning is generic."""
    r = (signal_reasoning or "").lower()
    pct_str = f"{pnl_pct:+.1f}%" if pnl_pct is not None else None
    d = days_held if days_held is not None else None

    if "stop" in r and "loss" in r:
        return f"Stop-loss hit ({pct_str} in {d}d)" if pct_str else "Stop-loss hit"
    if "profit target" in r or ("profit" in r and "target" in r):
        return f"Profit target hit ({pct_str} in {d}d)" if pct_str else "Profit target hit"
    if "rsi" in r and (">" in r or "recovery" in r or "reversion" in r or "complete" in r):
        return (
            f"RSI recovered — reversion complete ({pct_str})"
            if pct_str
            else "RSI recovered — reversion complete"
        )
    if "negative" in r and ("surprise" in r or "sentiment" in r):
        return (
            f"Negative signal — exited early ({pct_str})"
            if pct_str
            else "Negative signal — exited early"
        )

    # Time-based / planned exits — show numbers, not generic platitudes
    if any(w in r for w in ("rebalance", "held", "expired", "window", "drift")):
        if pct_str and d is not None:
            return f"Planned {d}-day exit closed {pct_str}"
        if pct_str:
            return f"Planned exit closed {pct_str}"

    # Fall back to pure trade math
    if pct_str and d is not None:
        return f"Closed {pct_str} after {d}d"
    if pct_str:
        return f"Closed {pct_str}"
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
        return TEXT_DIM
    return VOLT if v > 0 else LOSS


# ── Section builders ──────────────────────────────────────────────────────────
def build_header(
    pv: float,
    today_pnl: float,
    today_pct: float,
    date_str: str,
    equity: list[dict] | None = None,
) -> str:
    """Hero card: date pill, portfolio value, today's change pill, equity sparkline."""
    is_up = today_pnl >= 0
    col = VOLT if is_up else LOSS
    chip_bg = VOLT_SOFT if is_up else LOSS_SOFT
    chip_fg = "#1a3300" if is_up else "#7a1a1a"
    arrow = "▲" if is_up else "▼"

    chart_html = ""
    if equity:
        b64 = render_equity_sparkline(equity)
        if b64:
            window = len(equity)
            first = float(equity[0].get("total") or 0)
            last = float(equity[-1].get("total") or 0)
            window_pnl = last - first
            window_pct = (window_pnl / first * 100) if first else 0.0
            window_col = VOLT if window_pnl >= 0 else LOSS
            chart_html = f"""
    <div style="margin-top:22px;">
      <img src="data:image/png;base64,{b64}"
           style="display:block;width:100%;height:auto;border-radius:8px;" />
      <div style="display:flex;justify-content:space-between;
                  margin-top:8px;font-family:{FONT};font-size:11px;
                  color:{TEXT_MUTE};letter-spacing:0.04em;font-weight:600;">
        <span>{window}-session window</span>
        <span style="color:{window_col};font-weight:700;">
          {'+' if window_pnl >= 0 else '−'}${abs(window_pnl):,.2f} ·
          {window_pct:+.2f}%
        </span>
      </div>
    </div>
"""

    return f"""
<div style="padding:24px 22px 4px;">
  <div style="background:{CARD};border:1px solid {BORDER};border-radius:18px;
              padding:30px 32px;position:relative;overflow:hidden;">
    <!-- accent rail -->
    <div style="position:absolute;left:0;top:0;bottom:0;width:4px;background:{col};"></div>
    <div style="font-family:{FONT};font-size:11px;font-weight:700;
                letter-spacing:0.22em;color:{TEXT_MUTE};
                text-transform:uppercase;margin-bottom:18px;">
      {html_lib.escape(date_str)} · Portfolio
    </div>
    <div style="font-family:{FONT};font-size:54px;font-weight:800;
                letter-spacing:-0.03em;color:{TEXT};line-height:1;">
      ${pv:,.2f}
    </div>
    <div style="margin-top:14px;">
      <span style="display:inline-block;background:{chip_bg};color:{chip_fg};
                   border:1px solid {col};
                   font-family:{FONT};font-size:13px;font-weight:700;
                   padding:6px 12px;border-radius:999px;letter-spacing:-0.01em;">
        {arrow} ${abs(today_pnl):,.2f}
        <span style="opacity:0.7;font-weight:600;margin-left:4px;">
          {today_pct:+.2f}%
        </span>
      </span>
      <span style="font-family:{FONT};font-size:12px;color:{TEXT_DIM};
                   margin-left:10px;letter-spacing:0.04em;">today</span>
    </div>
    {chart_html}
  </div>
</div>
"""


def _kpi_card(label: str, value: str, value_color: str, sub: str = "", accent: bool = False) -> str:
    sub_html = (
        f'<div style="font-family:{FONT};font-size:11px;color:{TEXT_MUTE};'
        f'margin-top:6px;letter-spacing:0.04em;font-weight:500;">{sub}</div>'
        if sub
        else ""
    )
    bg = VOLT_SOFT if accent else CARD
    border_col = VOLT if accent else BORDER
    return f"""
<td style="padding:20px 18px;background:{bg};border:1px solid {border_col};
           border-radius:14px;vertical-align:top;width:25%;">
  <div style="font-family:{FONT};font-size:10px;font-weight:700;
              letter-spacing:0.2em;color:{TEXT_MUTE};
              text-transform:uppercase;margin-bottom:10px;">{label}</div>
  <div style="font-family:{FONT};font-size:26px;font-weight:800;
              letter-spacing:-0.025em;color:{value_color};line-height:1;">{value}</div>
  {sub_html}
</td>
"""


def build_kpi_strip(
    today_realized: float,
    total_pnl: float,
    win_rate: float | None,
    wins: int,
    losses: int,
    open_positions: int,
) -> str:
    wr_str = f"{int(round(win_rate * 100))}%" if win_rate is not None else "—"
    wr_col = (
        VOLT if win_rate and win_rate >= 0.5 else (LOSS if win_rate and win_rate < 0.4 else TEXT)
    )
    wr_sub = f"{wins}W · {losses}L" if win_rate is not None else "no closed trades"
    total_accent = total_pnl > 0
    return f"""
<div style="padding:14px 22px 4px;">
  <table style="width:100%;border-collapse:separate;border-spacing:10px 0;">
    <tr>
      {_kpi_card("Today", fmt_money(today_realized, sign=True),
                pnl_color(today_realized), "realized")}
      {_kpi_card("Total P&amp;L", fmt_money(total_pnl, sign=True),
                pnl_color(total_pnl), "all-time", accent=total_accent)}
      {_kpi_card("Win rate", wr_str, wr_col, wr_sub)}
      {_kpi_card("Open", str(open_positions), TEXT, "positions")}
    </tr>
  </table>
</div>
"""


def _section_title(text: str, count: int | None = None) -> str:
    """Bold black section heading with optional volt counter pill."""
    badge = ""
    if count is not None and count > 0:
        badge = (
            f'<span style="margin-left:10px;display:inline-block;'
            f"font-family:{FONT};font-size:12px;font-weight:700;"
            f"color:#1a3300;background:{VOLT_SOFT};border:1px solid {VOLT};"
            f"padding:2px 10px;border-radius:999px;letter-spacing:0;"
            f'vertical-align:middle;">{count}</span>'
        )
    return f"""
<div style="padding:34px 32px 12px;">
  <div style="font-family:{FONT};font-size:20px;font-weight:800;
              letter-spacing:-0.02em;color:{TEXT};">
    {html_lib.escape(text)}{badge}
  </div>
</div>
"""


def build_today_trades(trades: list[dict], sig_map: dict[tuple[str, str], dict]) -> str:
    if not trades:
        return f"""
<div style="padding:0 22px 4px;">
  <div style="background:{CARD};border:1px dashed {BORDER};border-radius:14px;
              padding:22px 24px;text-align:center;">
    <div style="font-family:{FONT};font-size:14px;font-weight:700;color:{TEXT};
                letter-spacing:-0.01em;">Quiet day — no trades</div>
    <div style="font-family:{FONT};font-size:12px;color:{TEXT_DIM};
                margin-top:4px;">Holding existing positions.</div>
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
        tag_bg = VOLT_SOFT if is_buy else LOSS_SOFT
        tag_fg = "#1a3300" if is_buy else "#7a1a1a"
        tag_border = VOLT if is_buy else LOSS
        tag = "BUY" if is_buy else "SELL"

        sig = sig_map.get((sym, action)) or {}
        raw_reason = sig.get("reasoning") or ""

        if is_buy:
            reason = _infer_buy_reason(strat, raw_reason)
            pnl_cell = (
                f'<span style="color:{TEXT_DIM};font-family:{FONT};'
                f'font-size:12px;">opened</span>'
            )
        else:
            pnl_pct = None
            if t.get("exec_price") and t.get("notional") and shares:
                # Best-effort %: prefer pnl/notional, fall back to nothing
                if pnl is not None and t.get("notional"):
                    try:
                        pnl_pct = (pnl / float(t["notional"])) * 100
                    except Exception:
                        pnl_pct = None
            reason = _infer_sell_reason(strat, raw_reason, pnl, pnl_pct, None)
            pnl_cell = (
                f'<span style="font-family:{MONO};font-size:14px;'
                f'font-weight:700;color:{pnl_color(pnl)};">'
                f'{fmt_money(pnl, sign=True) if pnl is not None else "—"}</span>'
            )

        rows += f"""
<tr>
  <td style="padding:14px 16px;border-top:1px solid {BORDER};vertical-align:middle;">
    <span style="display:inline-block;background:{tag_bg};color:{tag_fg};
                 border:1px solid {tag_border};
                 font-family:{FONT};font-size:10px;font-weight:800;
                 letter-spacing:0.12em;padding:4px 8px;border-radius:6px;">
      {tag}
    </span>
  </td>
  <td style="padding:14px 4px;border-top:1px solid {BORDER};vertical-align:middle;
             font-family:{FONT};font-size:15px;font-weight:700;color:{TEXT};
             letter-spacing:-0.01em;">
    {html_lib.escape(sym)}
    <div style="font-size:11px;font-weight:500;color:{TEXT_MUTE};
                letter-spacing:0.04em;margin-top:2px;">
      {html_lib.escape(_short_strategy(strat))}
    </div>
  </td>
  <td style="padding:14px 16px;border-top:1px solid {BORDER};vertical-align:middle;
             text-align:right;font-family:{MONO};font-size:13px;color:{TEXT_DIM};">
    {int(shares)} @ ${price:,.2f}
  </td>
  <td style="padding:14px 16px;border-top:1px solid {BORDER};vertical-align:middle;
             font-family:{FONT};font-size:12px;color:{TEXT_DIM};max-width:280px;">
    {html_lib.escape(reason)}
  </td>
  <td style="padding:14px 16px;border-top:1px solid {BORDER};vertical-align:middle;
             text-align:right;">
    {pnl_cell}
  </td>
</tr>
"""
    return f"""
<div style="padding:0 22px 4px;">
  <table style="width:100%;border-collapse:collapse;background:{CARD};
                border:1px solid {BORDER};border-radius:14px;overflow:hidden;">
    {rows}
  </table>
</div>
"""


def build_movers(positions: list[dict], top_n: int = 3) -> str:
    """
    Two-column split: top winners and top losers by unrealized P&L.

    Lives between Open Positions header and the position grid, so the most
    interesting holdings are visible without scrolling through 14+ cards.
    Returns "" if there are fewer than 2 positions (split is meaningless).
    """
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
        c = VOLT if side == "win" else LOSS
        return f"""
<tr>
  <td style="padding:9px 0;font-family:{FONT};font-size:14px;font-weight:700;
             color:{TEXT};letter-spacing:-0.01em;">{html_lib.escape(sym)}</td>
  <td style="padding:9px 0;text-align:right;font-family:{MONO};font-size:13px;
             font-weight:700;color:{c};letter-spacing:-0.01em;">
    {fmt_money(unr, sign=True)}
  </td>
  <td style="padding:9px 0 9px 10px;text-align:right;font-family:{FONT};
             font-size:11px;font-weight:600;color:{c};white-space:nowrap;">
    {fmt_pct(pct)}
  </td>
</tr>
"""

    def _column(title: str, items: list[dict], side: str, accent: str, bg: str) -> str:
        if not items:
            empty = "No winners yet" if side == "win" else "No losers — clean sheet"
            inner = (
                f'<div style="padding:18px 0;font-family:{FONT};font-size:12px;'
                f'color:{TEXT_MUTE};text-align:center;">{empty}</div>'
            )
        else:
            inner = (
                '<table style="width:100%;border-collapse:collapse;">'
                + "".join(_row(p, side) for p in items)
                + "</table>"
            )
        chip = (
            f'<span style="display:inline-block;background:{bg};color:{accent};'
            f"border:1px solid {accent};font-size:9px;font-weight:800;"
            f"letter-spacing:0.16em;padding:2px 7px;border-radius:4px;"
            f'vertical-align:middle;margin-left:8px;">{len(items)}</span>'
        )
        return f"""
<td style="padding:6px;width:50%;vertical-align:top;">
  <div style="background:{CARD};border:1px solid {BORDER};border-radius:14px;
              padding:18px 20px 6px;">
    <div style="font-family:{FONT};font-size:11px;font-weight:700;
                letter-spacing:0.18em;color:{TEXT_MUTE};
                text-transform:uppercase;margin-bottom:10px;">
      {title}{chip}
    </div>
    {inner}
  </div>
</td>
"""

    return f"""
<div style="padding:0 22px 4px;">
  <table style="width:100%;border-collapse:separate;border-spacing:0;">
    <tr>
      {_column("Top winners", winners, "win", "#1a3300", VOLT_SOFT)}
      {_column("Top losers", losers, "loss", "#7a1a1a", LOSS_SOFT)}
    </tr>
  </table>
</div>
"""


def build_positions(positions: list[dict]) -> str:
    if not positions:
        return f"""
<div style="padding:0 32px 4px;font-family:{FONT};font-size:13px;color:{TEXT_DIM};">
  No open positions.
</div>
"""
    cards_list: list[str] = []
    rows_html = ""
    for p in positions:
        sym = p.get("symbol") or ""
        shares = p.get("shares") or 0
        entry = p.get("entry_price") or p.get("avg_price") or 0
        curr = p.get("current_price") or entry
        unr = p.get("unrealized_pnl") or 0
        days = p.get("days_held")
        ret_pct = ((curr - entry) / entry * 100) if entry else 0
        col = pnl_color(unr)
        chart_b64 = render_sparkline(sym, entry_price=float(entry) if entry else None)
        chart_html = (
            f'<img src="data:image/png;base64,{chart_b64}" '
            f'style="display:block;width:100%;height:auto;border-radius:8px;" />'
            if chart_b64
            else f'<div style="height:60px;background:{CARD_ALT};border-radius:8px;"></div>'
        )
        # Color-coded left rail makes up/down instantly scannable
        rail_col = VOLT if unr > 0 else (LOSS if unr < 0 else BORDER)
        cards_list.append(
            f"""
<td style="padding:6px;width:50%;vertical-align:top;">
  <div style="background:{CARD};border:1px solid {BORDER};border-radius:14px;
              padding:16px 16px 14px 18px;position:relative;overflow:hidden;">
    <div style="position:absolute;left:0;top:0;bottom:0;width:3px;background:{rail_col};"></div>
    <table style="width:100%;border-collapse:collapse;">
      <tr>
        <td style="vertical-align:top;">
          <div style="font-family:{FONT};font-size:19px;font-weight:800;color:{TEXT};
                      letter-spacing:-0.025em;line-height:1;">{html_lib.escape(sym)}</div>
          <div style="font-family:{FONT};font-size:11px;color:{TEXT_MUTE};
                      letter-spacing:0.02em;margin-top:5px;font-weight:500;">
            {int(shares)} sh · {html_lib.escape(_short_strategy(p.get('strat') or ''))}{f" · {days}d" if days is not None else ""}
          </div>
        </td>
        <td style="text-align:right;vertical-align:top;">
          <div style="font-family:{MONO};font-size:15px;font-weight:700;color:{col};
                      letter-spacing:-0.01em;line-height:1;">{fmt_money(unr, sign=True)}</div>
          <div style="font-family:{FONT};font-size:11px;color:{col};margin-top:4px;
                      font-weight:600;">
            {fmt_pct(ret_pct)}
          </div>
        </td>
      </tr>
    </table>
    <div style="margin-top:12px;">{chart_html}</div>
    <table style="width:100%;border-collapse:collapse;margin-top:8px;">
      <tr>
        <td style="font-family:{FONT};font-size:10px;color:{TEXT_MUTE};
                   letter-spacing:0.12em;font-weight:600;">ENTRY</td>
        <td style="font-family:{MONO};font-size:12px;color:{TEXT_DIM};
                   text-align:right;">${entry:,.2f}</td>
        <td style="font-family:{FONT};font-size:10px;color:{TEXT_MUTE};
                   letter-spacing:0.12em;font-weight:600;text-align:right;
                   padding-left:14px;">NOW</td>
        <td style="font-family:{MONO};font-size:12px;color:{TEXT};
                   text-align:right;font-weight:700;padding-left:6px;">${curr:,.2f}</td>
      </tr>
    </table>
  </div>
</td>
"""
        )
    for i in range(0, len(cards_list), 2):
        pair = cards_list[i : i + 2]
        if len(pair) == 1:
            pair.append('<td style="padding:6px;width:50%;"></td>')
        rows_html += "<tr>" + "".join(pair) + "</tr>"

    return f"""
<div style="padding:0 22px 4px;">
  <table style="width:100%;border-collapse:separate;border-spacing:0;">
    {rows_html}
  </table>
</div>
"""


# ── Morning Brew–style news digest ────────────────────────────────────────────
_NEWS_CACHE_PATH = Path("/tmp/imb_news_cache.json")


def _load_news_cache() -> dict[str, dict]:
    if not _NEWS_CACHE_PATH.exists():
        return {}
    try:
        import json as _json

        data = _json.loads(_NEWS_CACHE_PATH.read_text())
        if data.get("date") == datetime.now().strftime("%Y-%m-%d"):
            symbols = data.get("symbols") or {}
            return {str(k): dict(v) for k, v in symbols.items()}
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
    """Return {symbol: {headlines: [...], score: float}} with one-day disk cache."""
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
            # News is best-effort; never let it break the email
            pass
    return {s: cache.get(s, {"headlines": [], "score": 0.5}) for s in symbols}


def _tone_chip(score: float) -> str:
    """Return a small inline chip describing the headline tone."""
    if score >= 0.62:
        bg, fg, border, label = VOLT_SOFT, "#1a3300", VOLT, "BULLISH"
    elif score <= 0.38:
        bg, fg, border, label = LOSS_SOFT, "#7a1a1a", LOSS, "BEARISH"
    else:
        bg, fg, border, label = CARD_ALT, TEXT_DIM, BORDER, "NEUTRAL"
    return (
        f'<span style="display:inline-block;background:{bg};color:{fg};'
        f"border:1px solid {border};font-size:9px;font-weight:800;"
        f"letter-spacing:0.16em;padding:2px 7px;border-radius:4px;"
        f'vertical-align:middle;">{label}</span>'
    )


def build_news_digest(positions: list[dict], max_stories: int = 6) -> str:
    """
    Morning Brew–style digest of why our holdings are in the news today.

    For each held symbol with at least one headline, render a single story
    block: bold lead with ticker, then the top headline as the story body,
    then a tone chip + secondary headline if present. Caps total stories
    at max_stories so the email stays scannable.
    """
    if not positions:
        return ""
    symbols = list(
        dict.fromkeys((p.get("symbol") or "").upper() for p in positions if p.get("symbol"))
    )
    if not symbols:
        return ""
    news_map = _fetch_position_news(symbols)

    # Rank: prefer symbols with strong sentiment magnitude (interesting news)
    ranked = sorted(
        [s for s in symbols if news_map.get(s, {}).get("headlines")],
        key=lambda s: abs(news_map[s].get("score", 0.5) - 0.5),
        reverse=True,
    )[:max_stories]

    if not ranked:
        return f"""
<div style="padding:0 22px 4px;">
  <div style="background:{CARD};border:1px dashed {BORDER};border-radius:14px;
              padding:18px 22px;text-align:center;font-size:12px;color:{TEXT_DIM};">
    No fresh headlines for today's holdings.
  </div>
</div>
"""

    blocks = []
    for sym in ranked:
        ctx = news_map[sym]
        headlines: list[str] = ctx.get("headlines") or []
        if not headlines:
            continue
        lead = headlines[0]
        secondary = headlines[1] if len(headlines) > 1 else None
        chip = _tone_chip(float(ctx.get("score", 0.5)))

        secondary_html = (
            f'<div style="font-size:12px;color:{TEXT_DIM};line-height:1.5;'
            f'margin-top:6px;font-weight:500;">+ {html_lib.escape(secondary)}</div>'
            if secondary
            else ""
        )

        blocks.append(
            f"""
<div style="padding:18px 22px;border-bottom:1px solid {BORDER};">
  <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
    <span style="font-family:{FONT};font-size:13px;font-weight:800;color:{TEXT};
                 letter-spacing:0.02em;">{html_lib.escape(sym)}</span>
    <span style="margin-left:8px;">{chip}</span>
  </div>
  <div style="font-family:{FONT};font-size:15px;font-weight:600;color:{TEXT};
              line-height:1.45;letter-spacing:-0.01em;">
    {html_lib.escape(lead)}
  </div>
  {secondary_html}
</div>
"""
        )

    return f"""
<div style="padding:0 22px 4px;">
  <div style="background:{CARD};border:1px solid {BORDER};border-radius:14px;
              overflow:hidden;">
    {''.join(blocks)}
    <div style="padding:12px 22px;background:{CARD_ALT};font-size:11px;
                color:{TEXT_MUTE};letter-spacing:0.04em;">
      Headlines via Google News · ranked by sentiment intensity
    </div>
  </div>
</div>
"""


def build_readiness(db_path: str) -> str:
    """Render the live-trading readiness gate as a single black card."""
    try:
        from check_live_readiness import evaluate_readiness
    except Exception:
        return ""
    try:
        result = evaluate_readiness(db_path)
    except Exception:
        return ""

    ready = result.get("ready")
    passed = result.get("passed", 0)
    total = result.get("total", 0)
    headline = "READY TO GO LIVE" if ready else f"NOT READY · {passed}/{total}"
    head_bg = VOLT_SOFT if ready else CARD_ALT
    head_fg = "#1a3300" if ready else TEXT
    head_border = VOLT if ready else BORDER

    rows = ""
    for c in result.get("checks", []):
        ok = c.get("ok")
        dot = VOLT if ok else LOSS
        val_col = TEXT if ok else TEXT_DIM
        rows += f"""
<tr>
  <td style="padding:9px 0;border-top:1px solid {BORDER};">
    <span style="display:inline-block;width:6px;height:6px;border-radius:50%;
                 background:{dot};margin-right:10px;vertical-align:middle;"></span>
    <span style="font-family:{FONT};font-size:13px;color:{TEXT};">
      {html_lib.escape(c.get('label', ''))}
    </span>
  </td>
  <td style="padding:9px 0;border-top:1px solid {BORDER};text-align:right;
             font-family:{MONO};font-size:13px;color:{val_col};font-weight:600;">
    {html_lib.escape(c.get('display', '—'))}
  </td>
  <td style="padding:9px 0 9px 14px;border-top:1px solid {BORDER};
             font-family:{FONT};font-size:11px;color:{TEXT_MUTE};
             text-align:right;letter-spacing:0.04em;">
    {html_lib.escape(c.get('target', ''))}
  </td>
</tr>
"""
    return f"""
<div style="padding:0 22px 4px;">
  <div style="background:{CARD};border:1px solid {BORDER};border-radius:14px;
              padding:20px 22px;">
    <div style="display:inline-block;background:{head_bg};color:{head_fg};
                border:1px solid {head_border};
                font-family:{FONT};font-size:11px;font-weight:800;
                letter-spacing:0.18em;padding:5px 10px;border-radius:6px;">
      {headline}
    </div>
    <table style="width:100%;border-collapse:collapse;margin-top:14px;">
      {rows}
    </table>
  </div>
</div>
"""


def build_footer(recon_status: str) -> str:
    ok = "SYNCED" in recon_status.upper() or "PASS" in recon_status.upper()
    dot_col = VOLT if ok else LOSS
    label = "Account synced" if ok else f"Sync: {recon_status}"
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"""
<div style="padding:24px 32px 32px;border-top:1px solid {BORDER};margin-top:18px;">
  <table style="width:100%;border-collapse:collapse;">
    <tr>
      <td style="font-family:{FONT};font-size:11px;color:{TEXT_MUTE};
                 letter-spacing:0.08em;">
        <span style="display:inline-block;width:7px;height:7px;border-radius:50%;
                     background:{dot_col};margin-right:6px;vertical-align:middle;"></span>
        {html_lib.escape(label)}
      </td>
      <td style="font-family:{FONT};font-size:11px;color:{TEXT_MUTE};
                 text-align:right;letter-spacing:0.06em;">
        Investor Mimic · {ts}
      </td>
    </tr>
  </table>
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
    finally:
        db.close()

    pv = float(snap.get("portfolio_value") or 0)
    recon = snap.get("reconciliation_status") or "UNKNOWN"
    today_pnl = 0.0
    today_pct = 0.0
    if len(equity) >= 2:
        prev, curr = equity[-2]["total"], equity[-1]["total"]
        today_pnl = (curr or 0) - (prev or 0)
        today_pct = (today_pnl / prev * 100) if prev else 0.0

    today_real = float(agg.get("today_realized") or 0)
    total_pnl = float(agg.get("total_pnl") or 0)
    wins = int(agg.get("wins") or 0)
    closed = int(agg.get("closed") or 0)
    losses = closed - wins
    win_rate = (wins / closed) if closed else None

    date_str = datetime.now().strftime("%A, %b %-d")

    body = (
        build_header(pv, today_pnl, today_pct, date_str, equity=equity)
        + build_kpi_strip(today_real, total_pnl, win_rate, wins, losses, len(positions))
        + _section_title("Today's Trades", count=len(trades_today))
        + build_today_trades(trades_today, sig_map)
        + _section_title("Movers")
        + build_movers(positions)
        + _section_title("Open Positions", count=len(positions))
        + build_positions(positions)
        + _section_title("In the news")
        + build_news_digest(positions)
        + _section_title("Live-Trading Readiness")
        + build_readiness(db_path)
        + build_footer(recon)
    )

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Daily</title>
<!-- Inter for clients that allow web fonts; safe fallback otherwise -->
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
  body, table, td, div, p, span {{
    font-family: {FONT};
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
    text-rendering: optimizeLegibility;
  }}
</style>
</head>
<body style="margin:0;padding:0;background:{BG};font-family:{FONT};color:{TEXT};">
  <div style="max-width:720px;margin:0 auto;background:{BG};font-family:{FONT};">
    {body}
  </div>
</body></html>"""


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
