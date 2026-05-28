#!/usr/bin/env python3
"""
Daily Trading Digest — dark terminal aesthetic, premium evening read.

Usage:
    python3 scripts/generate_daily_email.py [--include-visuals] [--send]
"""
from __future__ import annotations

import argparse
import base64
import html as html_lib
import io
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ── Exact color tokens from reference ────────────────────────────────────────
PAGE_BG = "#0a0e14"
CARD = "#0f1623"
CARD_ALT = "#0a1119"  # inset panel bg
BORDER = "#1e2a3d"  # card border
BORDER_INSET = "#1a2436"  # inset panel border
BORDER_STRONG = "#2a3a52"

INK = "#ffffff"  # primary white
INK_DIM = "#cdd6e4"  # body text
INK_MID = "#9fb0c8"  # secondary text
INK_MUTE = "#7d8aa0"  # label text
INK_FAINT = "#5a6678"  # muted text

GREEN = "#4ade80"
GREEN_BG = "#0d2a1f"
GREEN_BORDER = "#1d5c42"

RED = "#f87171"
RED_BG = "#2a1414"
RED_BORDER = "#5c1d1d"

AMBER = "#fbbf24"
AMBER_BG = "#1f1a0a"
AMBER_BORDER = "#5c4a1d"

TEAL = "#5eead4"

# For legacy sections that still reference these names
BLUE = "#5eead4"
BLUE_BG = "#0a1119"
BLUE_BORDER = "#1a2436"
PURPLE = "#9fb0c8"
PURPLE_BG = "#0a1119"
PURPLE_BORDER = "#1a2436"
SLATE = "#7d8aa0"
SLATE_BG = "#0a1119"
SLATE_BORDER = "#1a2436"

# Fonts — Trebuchet for labels/body, Georgia for numbers, Courier for code
FONT = "'Trebuchet MS',Verdana,sans-serif"
SERIF = "Georgia,'Times New Roman',serif"
MONO = "'Courier New',monospace"
DISPLAY = SERIF  # legacy alias

# Strategy accent colours used by legacy sections (build_positions, etc.)
STRAT_BRAND: dict[str, tuple[str, str, str]] = {
    "RSI Mean Reversion": (TEAL, CARD_ALT, BORDER_INSET),
    "ML Momentum": ("#9fb0c8", CARD_ALT, BORDER_INSET),
    "Earnings Drift": (AMBER, AMBER_BG, AMBER_BORDER),
    "Factor Momentum": (INK_FAINT, CARD_ALT, BORDER_INSET),
}

STRATEGY_EXPLAINERS: dict[str, str] = {
    "RSI Mean Reversion": "Buys stocks that have fallen too far, too fast — expecting them to bounce back.",
    "ML Momentum": "An AI model trained on 12 signals predicts which stocks will rise over the next 5 days.",
    "News Sentiment": "Reads financial news to gauge sentiment — buys on positive momentum, exits on negative shifts.",
    "MA Crossover": "Buys when the short-term moving average crosses above the long-term — a classic trend-following signal.",
    "Volatility Breakout": "Trades breakouts when price moves sharply beyond its recent range on elevated volume.",
    "Earnings Drift": "Rides the post-earnings wave — stocks often keep climbing for weeks after strong results.",
    "Factor Momentum": "Ranks stocks by quality and momentum factors, buying the top-ranked names.",
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
        SELECT snapshot_date AS date, portfolio_value AS total
        FROM broker_state
        WHERE snapshot_type = 'END'
          AND snapshot_date >= date('now', ?)
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
                WHERE p.strategy_id = strategies.id AND p.shares > 0) AS unrealized_total,
               (SELECT COUNT(*) FROM signals sg
                WHERE sg.strategy_id = strategies.id) AS signal_count
        FROM strategies
        WHERE name != 'BROKER_SYNC'
        ORDER BY id
        """,
    )


def get_system_alerts(db, recon_status: str, zero_streak: int) -> list[dict]:
    alerts = []
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
    recon_upper = (recon_status or "").upper()
    if "FAIL" in recon_upper or "MISMATCH" in recon_upper or "ERROR" in recon_upper:
        alerts.append(
            {
                "level": "critical",
                "icon": "⚠️",
                "msg": f"Account sync issue — {recon_status}. System will retry automatically.",
            }
        )
    if zero_streak >= 5:
        alerts.append(
            {
                "level": "info",
                "icon": "💤",
                "msg": f"{zero_streak} days in a row with no trades. System is being selective.",
            }
        )
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
    fig, ax = plt.subplots(figsize=(4.0, 0.8), dpi=140)
    fig.patch.set_facecolor(CARD)
    ax.set_facecolor(CARD)
    ax.plot(range(len(closes)), closes, color=line_color, linewidth=1.6)
    ax.fill_between(range(len(closes)), closes, min(closes), color=line_color, alpha=0.15)
    if entry_price and min(closes) <= entry_price <= max(closes):
        ax.axhline(entry_price, color=INK_MUTE, linewidth=0.7, linestyle=(0, (3, 4)))
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.margins(x=0.01, y=0.18)
    plt.tight_layout(pad=0.05)
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
    bg = "#0d1f35"
    fig, ax = plt.subplots(figsize=(7.2, 1.4), dpi=140)
    fig.patch.set_facecolor(bg)
    ax.set_facecolor(bg)
    ax.plot(range(len(values)), values, color=line_color, linewidth=2.0)
    ax.fill_between(range(len(values)), values, min(values), color=line_color, alpha=0.18)
    ax.axhline(values[0], color="#4a7fa8", linewidth=0.7, linestyle=(0, (4, 5)))
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.margins(x=0.005, y=0.22)
    plt.tight_layout(pad=0.05)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor=bg, edgecolor="none")
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
    prefix = "-" if v < 0 else ("+" if sign else "")
    return f"{prefix}${abs(v):,.2f}"


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


# ── SPY benchmark ────────────────────────────────────────────────────────────
def _fetch_spy_return() -> float | None:
    """Return SPY's 1-day % change, or None on any failure."""
    try:
        import yfinance as yf

        hist = yf.Ticker("SPY").history(period="5d", interval="1d")
        if len(hist) < 2:
            return None
        closes = hist["Close"].dropna().tolist()
        if len(closes) < 2:
            return None
        return (closes[-1] - closes[-2]) / closes[-2] * 100  # type: ignore[no-any-return]
    except Exception:
        return None


# ── Section: Header bar ───────────────────────────────────────────────────────
def build_header_bar(date_str: str, run_number: str | None) -> str:
    run_part = f" &nbsp;&middot;&nbsp; Run #{html_lib.escape(run_number)}" if run_number else ""
    return f"""
<tr><td style="padding:0 0 12px 0;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
    <td style="font-family:{FONT};color:{TEAL};font-size:13px;font-weight:bold;
               letter-spacing:3px;text-transform:uppercase;">&#9650; Investor Mimic</td>
    <td align="right" style="font-family:{FONT};color:{INK_MUTE};font-size:12px;
               letter-spacing:1px;">
      {html_lib.escape(date_str)}{run_part}
    </td>
  </tr></table>
</td></tr>
"""


# ── Section: System Health Card ───────────────────────────────────────────────
def build_health_card(
    recon_status: str | None,
    auto_sync_ok: str | None,
    drift_resolved: str | None,
    drift_remaining: str | None,
    fill_summary: dict,
    db_path: str,
) -> str:
    import json as _json
    import time as _time

    recon_upper = (recon_status or "UNKNOWN").upper()
    recon_ok = recon_upper in ("PASS", "SYNCED") or "PASS" in recon_upper
    auto_sync_fired = auto_sync_ok is not None and auto_sync_ok != ""
    drift_clean = str(drift_resolved).lower() == "true"
    recon_final_ok = recon_ok or (auto_sync_fired and drift_clean)
    remaining_str = str(drift_remaining or "0")
    remaining = int(remaining_str) if remaining_str.lstrip("-").isdigit() else 0

    # 1. Broker reconciled
    if recon_final_ok:
        broker_detail, broker_ok = "Balanced with broker", True
    elif auto_sync_fired:
        broker_detail, broker_ok = f"{remaining} item(s) remaining", False
    else:
        broker_detail, broker_ok = f"Drift: {recon_upper}", False

    # 2. Data fresh — training_data.csv mtime
    csv_path = PROJECT_ROOT / "data" / "training_data.csv"
    DATA_MAX_AGE_HOURS = 144
    if csv_path.exists():
        age_hours = (_time.time() - csv_path.stat().st_mtime) / 3600
        data_ok = age_hours < DATA_MAX_AGE_HOURS
        data_detail = f"{int(age_hours)}h ago" + ("" if data_ok else " · stale")
    else:
        data_ok, data_detail = False, "File missing"

    # 3. Data quality — N/M symbols clean
    quality_ok, quality_detail = True, "—"
    try:
        if csv_path.exists():
            import pandas as pd

            df = pd.read_csv(csv_path, usecols=["symbol", "close"])
            total_syms = int(df["symbol"].nunique())
            clean_syms = int(df.groupby("symbol")["close"].apply(lambda x: x.notna().all()).sum())
            quality_detail = f"{clean_syms}/{total_syms} symbols clean"
            quality_ok = (clean_syms / total_syms >= 0.90) if total_syms > 0 else False
    except Exception:
        pass

    # 4. Circuit breaker clear — daily loss < 5% threshold
    cb_ok, cb_detail = True, "Within limit"
    try:
        db_tmp = _conn(db_path)
        slo_row = _q1(
            db_tmp, "SELECT metrics_json FROM run_slo_metrics ORDER BY created_at DESC LIMIT 1"
        )
        db_tmp.close()
        if slo_row and slo_row.get("metrics_json"):
            try:
                slo = _json.loads(slo_row["metrics_json"])
                dpct = float(slo.get("daily_pnl_pct") or slo.get("daily_pnl") or 0)
                if dpct < -5.0:
                    cb_ok, cb_detail = False, f"Tripped: {dpct:.1f}%"
                else:
                    cb_detail = f"Daily: {'+' if dpct >= 0 else ''}{dpct:.1f}%"
            except (_json.JSONDecodeError, ValueError, TypeError):
                cb_detail = "Metrics parse error"
    except Exception:
        pass

    # 5. Correlation filter — neutral marker, always counts healthy
    corr_ok, corr_detail = None, "Active"

    # 6. Regime from system_state table — neutral marker
    regime_display = "NORMAL"
    try:
        db_tmp2 = _conn(db_path)
        rrow = _q1(db_tmp2, "SELECT value FROM system_state WHERE key='regime' LIMIT 1")
        db_tmp2.close()
        if rrow and rrow.get("value"):
            rdata = _json.loads(rrow["value"])
            cls = (
                rdata.get("classification") or rdata.get("volatility_regime") or "NORMAL"
            ).upper()
            regime_display = (
                "LOW_VOL"
                if cls in ("LOW_VOL", "LOW")
                else ("HIGH_VOL" if cls in ("HIGH_VOL", "HIGH") else cls)
            )
    except Exception:
        pass
    regime_ok = None

    markers: list[tuple[str, bool | None]] = [
        ("Broker reconciled", broker_ok),
        (f"Data fresh ({data_detail})", data_ok),
        (quality_detail, quality_ok),
        ("Circuit breaker clear", cb_ok),
        ("Correlation filter OK", corr_ok),
        (f"Regime: {regime_display}", regime_ok),
    ]

    healthy = sum(1 for _, ok in markers if ok is True)
    neutral = sum(1 for _, ok in markers if ok is None)
    failed_count = sum(1 for _, ok in markers if ok is False)
    total = len(markers)
    healthy_total = healthy + neutral

    if failed_count == 0:
        header_color, header_text = GREEN, "All Systems Healthy"
    elif drift_clean and auto_sync_fired:
        header_color, header_text = AMBER, "Auto-Recovered"
    else:
        header_color, header_text = RED, "Needs Attention"

    ts = datetime.now().strftime("%H:%M ET")

    header_html = f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
  <td style="font-family:{FONT};">
    <span style="display:inline-block;width:10px;height:10px;background-color:{header_color};
                 border-radius:50%;vertical-align:middle;">&nbsp;</span>
    <span style="color:{INK};font-size:15px;font-weight:bold;vertical-align:middle;
                 padding-left:8px;">{header_text}</span>
    <span style="color:{header_color};font-size:15px;font-weight:bold;vertical-align:middle;
                 padding-left:8px;">{healthy_total}/{total}</span>
  </td>
  <td align="right" style="font-family:{FONT};color:{INK_MUTE};font-size:12px;">Generated {ts}</td>
</tr></table>"""

    def _pill(label: str, ok: bool | None) -> str:
        if ok is True:
            icon_html = f'<span style="color:{GREEN};">&#10003;</span>'
        elif ok is False:
            icon_html = f'<span style="color:{RED};">&#10007;</span>'
        else:
            icon_html = f'<span style="color:{AMBER};">&#9632;</span>'
        return (
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"'
            f' style="background-color:{CARD_ALT};border:1px solid {BORDER_INSET};border-radius:10px;">'
            f'<tr><td style="padding:11px 14px;font-family:{FONT};font-size:13px;color:{INK_MID};">'
            f"{icon_html}&nbsp; {html_lib.escape(label)}"
            f"</td></tr></table>"
        )

    pill_rows = []
    for i in range(0, len(markers), 2):
        left_label, left_ok = markers[i]
        right_td = ""
        if i + 1 < len(markers):
            right_label, right_ok = markers[i + 1]
            right_td = f'<td width="50%" style="padding:5px 0 5px 5px;">{_pill(right_label, right_ok)}</td>'
        pill_rows.append(
            f'<tr><td width="50%" style="padding:5px 5px 5px 0;">{_pill(left_label, left_ok)}</td>{right_td}</tr>'
        )

    pills_html = (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"'
        f' style="margin-top:16px;">{"".join(pill_rows)}</table>'
    )

    attention_html = ""
    if failed_count > 0 and not drift_clean:
        failed_labels = [label for label, ok in markers if ok is False]
        items_html = "".join(
            f'<div style="font-family:{FONT};font-size:12px;color:{RED};padding:4px 0;">'
            f"&#10007; {html_lib.escape(str(lbl))}</div>"
            for lbl in failed_labels
        )
        attention_html = (
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"'
            f' style="margin-top:16px;background-color:{RED_BG};border:1px solid {RED_BORDER};border-radius:10px;">'
            f'<tr><td style="padding:12px 16px;">'
            f'<div style="font-family:{FONT};font-size:11px;font-weight:bold;letter-spacing:1px;'
            f'text-transform:uppercase;color:{RED};padding-bottom:6px;">What Needs Attention</div>'
            f"{items_html}</td></tr></table>"
        )

    return f"""
<tr><td style="padding:0 0 12px 0;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
         style="background-color:{CARD};border:1px solid {BORDER};border-radius:18px;">
  <tr><td style="padding:22px 24px;">
    {header_html}
    {pills_html}
    {attention_html}
  </td></tr>
  </table>
</td></tr>
"""


# ── Section: Hero ─────────────────────────────────────────────────────────────
def build_hero(
    pv: float,
    today_pnl: float,
    today_pct: float,
    date_str: str,
    equity: list[dict] | None = None,
    spy_return: float | None = None,
    total_pnl: float = 0.0,
    cash: float = 0.0,
    open_count: int = 0,
) -> str:
    is_up = today_pnl >= 0
    arrow = "&#9650;" if is_up else "&#9660;"
    pnl_col = GREEN if is_up else RED
    pnl_bg_col = GREEN_BG if is_up else RED_BG
    pnl_border = GREEN_BORDER if is_up else RED_BORDER

    if today_pct >= 1.5:
        vibe = "Strong day. The system delivered."
    elif today_pct >= 0.3:
        vibe = "Quiet gains. Slow and steady wins."
    elif today_pct > -0.3:
        vibe = "Flat tape &mdash; markets were indecisive."
    elif today_pct > -1.5:
        vibe = "Tape leaned heavy. Holding the line."
    else:
        vibe = "Rough session. Losses are part of the game."

    # Portfolio value: split dollars and cents for the large/small contrast
    pv_dollars = f"${int(pv):,}"
    pv_cents = f"{pv % 1:.2f}"[1:]  # ".99"

    spy_html = ""
    if spy_return is not None:
        spy_col = GREEN if spy_return >= 0 else RED
        spy_arrow = "&#9650;" if spy_return >= 0 else "&#9660;"
        alpha = today_pct - spy_return
        alpha_col = GREEN if alpha >= 0 else RED
        alpha_sign = "+" if alpha >= 0 else ""
        spy_html = f"""
<div style="font-family:{FONT};color:{INK_MUTE};font-size:11px;padding-top:10px;">
  SPY&nbsp;<span style="color:{spy_col};">{spy_arrow}&nbsp;{spy_return:+.2f}%</span>
  &nbsp;&nbsp;alpha&nbsp;<span style="color:{alpha_col};">{alpha_sign}{alpha:.2f}%</span>
</div>"""

    chart_html = ""
    if equity and len(equity) >= 3:
        b64 = render_equity_sparkline(equity)
        if b64:
            window = len(equity)
            first = float(equity[0].get("total") or 0)
            last = float(equity[-1].get("total") or 0)
            window_pnl = last - first
            window_pct = (window_pnl / first * 100) if first else 0.0
            w_col = GREEN if window_pnl >= 0 else RED
            chart_html = f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
       style="margin-top:20px;">
  <tr><td>
    <img src="data:image/png;base64,{b64}"
         style="display:block;width:100%;height:auto;border-radius:6px;" />
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
           style="padding-top:6px;">
      <tr>
        <td style="font-family:{FONT};font-size:11px;color:{INK_FAINT};">
          {window}-day equity curve
        </td>
        <td align="right" style="font-family:{SERIF};font-size:12px;color:{w_col};font-weight:bold;">
          {'&#9650;' if window_pnl >= 0 else '&#9660;'} ${abs(window_pnl):,.0f} &nbsp; {window_pct:+.1f}%
        </td>
      </tr>
    </table>
  </td></tr>
</table>"""

    total_col = GREEN if total_pnl >= 0 else RED
    total_sign = "+" if total_pnl >= 0 else ""

    return f"""
<tr><td style="padding:0 0 12px 0;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
         style="background-color:{CARD};border:1px solid {BORDER};border-radius:18px;">
  <tr><td style="padding:34px 34px 28px 34px;">
    <div style="font-family:{FONT};color:{INK_MUTE};font-size:12px;
                letter-spacing:2px;text-transform:uppercase;padding-bottom:6px;">Portfolio Value</div>
    <div style="font-family:{SERIF};color:{INK};font-size:50px;font-weight:bold;
                line-height:1;letter-spacing:-1px;">
      {pv_dollars}<span style="font-size:28px;color:{INK_MUTE};">{pv_cents}</span>
    </div>
    <table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin-top:18px;"><tr>
      <td style="background-color:{pnl_bg_col};border:1px solid {pnl_border};
                 border-radius:999px;padding:7px 16px;font-family:{FONT};
                 color:{pnl_col};font-size:15px;font-weight:bold;white-space:nowrap;">
        {arrow} {fmt_money(today_pnl)} &nbsp; {today_pct:+.2f}%
      </td>
      <td style="padding-left:14px;font-family:{FONT};color:{INK_MID};
                 font-size:13px;font-style:italic;">{vibe}</td>
    </tr></table>
    {spy_html}
    {chart_html}
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
           style="margin-top:24px;border-top:1px solid {BORDER};"><tr>
      <td width="33%" style="padding:18px 0 0 0;font-family:{FONT};">
        <div style="color:{INK_MUTE};font-size:11px;letter-spacing:1px;text-transform:uppercase;">All-Time</div>
        <div style="font-family:{SERIF};color:{total_col};font-size:19px;font-weight:bold;padding-top:4px;">
          {total_sign}{fmt_money(total_pnl)}
        </div>
      </td>
      <td width="33%" style="padding:18px 0 0 0;border-left:1px solid {BORDER};font-family:{FONT};">
        <div style="color:{INK_MUTE};font-size:11px;letter-spacing:1px;text-transform:uppercase;padding-left:18px;">Cash</div>
        <div style="font-family:{SERIF};color:{INK_DIM};font-size:19px;font-weight:bold;padding-top:4px;padding-left:18px;">
          {fmt_money(cash)}
        </div>
      </td>
      <td width="33%" style="padding:18px 0 0 0;border-left:1px solid {BORDER};font-family:{FONT};">
        <div style="color:{INK_MUTE};font-size:11px;letter-spacing:1px;text-transform:uppercase;padding-left:18px;">Positions</div>
        <div style="color:{INK_DIM};font-size:19px;font-weight:bold;padding-top:4px;padding-left:18px;">
          {open_count} open
        </div>
      </td>
    </tr></table>
  </td></tr>
  </table>
</td></tr>
"""


# ── Section: Alert Banner ─────────────────────────────────────────────────────
def build_alert_banner(alerts: list[dict]) -> str:
    if not alerts:
        return ""
    has_critical = any(a.get("level") == "critical" for a in alerts)
    acc = RED if has_critical else AMBER
    acc_bg = RED_BG if has_critical else AMBER_BG
    acc_border = RED_BORDER if has_critical else AMBER_BORDER
    label = "CRITICAL ALERT" if has_critical else "HEADS UP"

    items = "".join(
        f"""<tr>
  <td style="padding:10px 0;border-top:1px solid {acc_border};
             font-family:{FONT};font-size:13px;color:{INK_DIM};line-height:1.5;">
    {html_lib.escape(a.get('icon',''))} {html_lib.escape(a.get('msg',''))}
  </td>
</tr>"""
        for a in alerts
    )
    return f"""
<tr><td style="padding:0 0 12px 0;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
         style="background-color:{acc_bg};border:1px solid {acc_border};border-radius:14px;">
  <tr><td style="padding:14px 20px;">
    <div style="font-family:{FONT};font-size:10px;font-weight:bold;letter-spacing:2px;
                color:{acc};text-transform:uppercase;padding-bottom:4px;">{label}</div>
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
      {items}
    </table>
  </td></tr>
  </table>
</td></tr>
"""


# ── Section: Stats Strip ──────────────────────────────────────────────────────
def build_kpi_strip(
    today_realized: float,
    total_pnl: float,
    win_rate: float | None,
    wins: int,
    losses: int,
    open_count: int,
) -> str:
    wr_str = f"{int(round(win_rate * 100))}%" if win_rate is not None else "—"
    wr_col = (
        GREEN
        if (win_rate and win_rate >= 0.5)
        else (RED if (win_rate and win_rate < 0.4) else AMBER)
    )

    def _stat(label: str, value: str, color: str, sub: str = "") -> str:
        sub_html = (
            f'<div style="font-family:{FONT};font-size:10px;color:{INK_MUTE};'
            f'margin-top:4px;">{sub}</div>'
            if sub
            else ""
        )
        return f"""
<td style="padding:22px 28px;text-align:center;border-right:1px solid {BORDER};
           vertical-align:top;">
  <div style="font-family:{MONO};font-size:32px;font-weight:700;
              color:{color};letter-spacing:-0.03em;line-height:1;">{value}</div>
  <div style="font-family:{FONT};font-size:10px;color:{INK_MUTE};
              margin-top:8px;letter-spacing:0.16em;text-transform:uppercase;
              font-weight:700;">{label}</div>
  {sub_html}
</td>"""

    wr_sub = f"{wins}W · {losses}L" if win_rate is not None else "no closed trades"
    return f"""
<div style="background:{CARD};border-bottom:1px solid {BORDER};">
  <table style="width:100%;border-collapse:collapse;">
    <tr>
      {_stat("Today's P&L", fmt_money(today_realized, sign=True), pnl_color(today_realized))}
      {_stat("All-Time P&L", fmt_money(total_pnl, sign=True), pnl_color(total_pnl))}
      {_stat("Win Rate", wr_str, wr_col, wr_sub)}
      {_stat("Open Positions", str(open_count), BLUE)}
    </tr>
  </table>
</div>
"""


# ── Section: Command Center (Strategies) ──────────────────────────────────────
def build_strategy_dashboard(
    strategy_rows: list[dict],
    health_by_name: dict[str, dict] | None = None,
    portfolio_value: float = 0.0,
) -> str:
    if not strategy_rows:
        return ""
    health_by_name = health_by_name or {}

    active_count = sum(
        1 for r in strategy_rows if (r.get("status") or "active").lower() in ("active", "")
    )

    # Normalize allocation bars to % of portfolio value
    _total_alloc = sum(float(r.get("capital_allocation") or 0) for r in strategy_rows)
    _alloc_base = (
        portfolio_value if portfolio_value > 0 else (_total_alloc if _total_alloc > 0 else 1)
    )

    cards_html = ""
    for row in strategy_rows:
        name = row.get("name") or ""
        open_count = int(row.get("open_count") or 0)
        unr = float(row.get("unrealized_total") or 0)
        capital_alloc = float(row.get("capital_allocation") or 0)
        signal_count = int(row.get("signal_count") or 0)
        db_status = (row.get("status") or "active").lower()
        health = health_by_name.get(name, {})
        health_score = health.get("health_score")

        is_active = db_status in ("active", "")
        # A strategy is "not implemented" if it has never produced a signal
        never_ran = signal_count == 0

        # Status badge
        if is_active:
            badge = (
                f'<span style="background-color:{GREEN_BG};color:{GREEN};'
                f"font-size:10px;font-weight:bold;letter-spacing:1px;"
                f'padding:3px 8px;border-radius:5px;margin-left:6px;">ACTIVE</span>'
            )
        else:
            badge = (
                f'<span style="background-color:{AMBER_BG};color:{AMBER};'
                f"font-size:10px;font-weight:bold;letter-spacing:1px;"
                f'padding:3px 8px;border-radius:5px;margin-left:6px;">'
                f"{db_status.upper()}</span>"
            )

        # Health score chip
        health_badge = ""
        if isinstance(health_score, (int, float)) and not never_ran:
            score_int = int(health_score)
            if score_int >= 80:
                hc, hbg = GREEN, GREEN_BG
            elif score_int >= 60:
                hc, hbg = AMBER, AMBER_BG
            else:
                hc, hbg = RED, RED_BG
            health_badge = (
                f'<span style="background-color:{hbg};color:{hc};'
                f"font-size:10px;font-weight:bold;"
                f'padding:3px 8px;border-radius:5px;margin-left:4px;">'
                f"{score_int}/100</span>"
            )

        # Right-side stat: unrealized P&L, dash, or nothing
        if open_count > 0:
            prices_look_stale = abs(unr) < 0.01
            if prices_look_stale:
                right_html = (
                    f'<td align="right" style="font-family:{FONT};color:{INK_MUTE};'
                    f"font-size:13px;vertical-align:top;padding-left:12px;"
                    f'white-space:nowrap;">'
                    f"{open_count} position{'s' if open_count != 1 else ''} &middot; prices loading</td>"
                )
            else:
                unr_col = GREEN if unr >= 0 else RED
                right_html = (
                    f'<td align="right" style="font-family:{SERIF};color:{unr_col};'
                    f"font-size:18px;font-weight:bold;vertical-align:top;"
                    f'white-space:nowrap;padding-left:12px;">'
                    f"{fmt_money(unr, sign=True)}</td>"
                )
        elif is_active:
            right_html = (
                f'<td align="right" style="font-family:{FONT};color:{INK_MUTE};'
                f'font-size:13px;vertical-align:top;padding-left:12px;">'
                f"scanning &middot; no positions</td>"
            )
        else:
            right_html = (
                f'<td align="right" style="font-family:{FONT};color:{INK_FAINT};'
                f'font-size:13px;vertical-align:top;padding-left:12px;">&mdash;</td>'
            )

        # Allocation bar: width = % of portfolio, teal if active+profit, red if loss, grey if undeployed
        alloc_pct = (
            max(1, min(95, int(capital_alloc / _alloc_base * 100))) if capital_alloc > 0 else 5
        )
        if open_count > 0 and unr < -0.01:
            bar_col = RED
        elif open_count == 0:
            bar_col = INK_FAINT  # grey = budget reserved but not deployed
        else:
            bar_col = TEAL
        alloc_bar = (
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"'
            f' style="margin-top:12px;background-color:{CARD_ALT};border-radius:6px;height:8px;"><tr>'
            f'<td width="{alloc_pct}%" style="background-color:{bar_col};border-radius:6px;'
            f'height:8px;font-size:1px;line-height:8px;">&nbsp;</td>'
            f'<td style="font-size:1px;line-height:8px;">&nbsp;</td>'
            f"</tr></table>"
        )

        # Footer line: allocation %, position count, or "not implemented" warning
        footer_parts = []
        if is_active and capital_alloc > 0:
            if open_count > 0:
                footer_parts.append(f"{alloc_pct}% capital deployed")
            else:
                footer_parts.append(f"{alloc_pct}% capital budgeted &middot; waiting for signals")
        elif open_count > 0:
            footer_parts.append(f"{open_count} position{'s' if open_count != 1 else ''}")
        footer_txt = " &middot; ".join(footer_parts) if footer_parts else ""

        issue_html = ""
        if never_ran:
            issue_html = (
                f'<div style="font-family:{FONT};color:{INK_FAINT};font-size:11px;padding-top:9px;">'
                f"&#9888; No signals generated yet &mdash; strategy module not yet implemented</div>"
            )
        elif health.get("issues"):
            issue_html = (
                f'<div style="font-family:{FONT};color:{AMBER};font-size:11px;padding-top:9px;">'
                f'&#9888; {html_lib.escape(health["issues"][0])}</div>'
            )
        elif footer_txt:
            issue_html = (
                f'<div style="font-family:{FONT};color:{INK_FAINT};font-size:11px;padding-top:9px;">'
                f"{footer_txt}</div>"
            )

        explainer = STRATEGY_EXPLAINERS.get(name, "")
        expl_col = INK_FAINT if never_ran else (INK_MID if is_active else INK_FAINT)
        expl_html = (
            f'<div style="font-family:{FONT};color:{expl_col};font-size:12px;'
            f'line-height:1.5;padding-top:8px;">{html_lib.escape(explainer)}</div>'
            if explainer
            else ""
        )

        bar_html = alloc_bar if (is_active and not never_ran) or open_count > 0 else ""

        cards_html += f"""
<tr><td style="padding:0 0 10px 0;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
         style="background-color:{CARD};border:1px solid {BORDER};border-radius:14px;">
  <tr><td style="padding:18px 22px;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
      <td style="font-family:{FONT};">
        <span style="color:{INK};font-size:16px;font-weight:bold;">{html_lib.escape(name)}</span>
        {badge}{health_badge}
      </td>
      {right_html}
    </tr></table>
    {expl_html}
    {bar_html}
    {issue_html}
  </td></tr>
  </table>
</td></tr>"""

    label_row = f"""
<tr><td style="padding:12px 4px 12px 4px;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
    <td style="font-family:{FONT};color:{INK_MUTE};font-size:12px;font-weight:bold;
               letter-spacing:2px;text-transform:uppercase;">Command Center</td>
    <td align="right" style="font-family:{FONT};color:{GREEN};font-size:12px;font-weight:bold;">
      {active_count} of {len(strategy_rows)} active
    </td>
  </tr></table>
</td></tr>"""

    return label_row + cards_html


# ── Section divider ───────────────────────────────────────────────────────────
def _section_title(text: str, sub: str = "", count: int | None = None, accent: str = TEAL) -> str:
    count_html = (
        f'<span style="font-family:{FONT};color:{GREEN};font-size:12px;font-weight:bold;">'
        f"{count}</span>"
        if count is not None and count > 0
        else ""
    )
    return f"""
<tr><td style="padding:14px 4px 10px 4px;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
    <td style="font-family:{FONT};color:{INK_MUTE};font-size:12px;font-weight:bold;
               letter-spacing:2px;text-transform:uppercase;">{html_lib.escape(text)}</td>
    <td align="right">{count_html}</td>
  </tr></table>
</td></tr>
"""


# ── Section: Today's Trades ───────────────────────────────────────────────────
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
            border:1px solid {AMBER_BORDER};border-radius:6px;
            font-family:{FONT};font-size:12px;color:{AMBER};line-height:1.5;">
  <strong>{zero_trade_streak} consecutive days</strong> with no trades.
  The system only buys when its conditions are met — patience is part of the edge.
</div>"""

        rej_html = ""
        if rejections:
            rej_label_map = {
                "portfolio_heat": "Portfolio at max concentration",
                "insufficient_cash": "Not enough cash reserved",
                "correlation": "Too similar to existing position",
                "sector_concentration": "Sector limit reached",
                "max_positions_reached": "Already at max positions",
                "benchmark_etf_guard": "Symbol is a benchmark ETF",
                "cross_strategy_dedup": "Already held by another strategy",
                "wash_trade_guard": "Wash-trade prevention",
                "ml_risk_off": "AI model in risk-off mode",
                "size_reduced_to_zero": "Position sizing returned zero",
            }
            rej_items = "".join(
                f"""<div style="display:flex;justify-content:space-between;
                               padding:8px 0;border-top:1px solid {BORDER};">
  <span style="font-family:{FONT};font-size:12px;color:{INK_DIM};">
    {html_lib.escape(rej_label_map.get(r.get('reason_code', ''), r.get('reason_code', '')))}
  </span>
  <span style="font-family:{MONO};font-size:12px;color:{INK_MUTE};">{r.get('cnt', '')}×</span>
</div>"""
                for r in rejections
            )
            rej_html = f"""
<div style="margin-top:16px;">
  <div style="font-family:{FONT};font-size:10px;font-weight:800;letter-spacing:0.18em;
              color:{INK_MUTE};text-transform:uppercase;margin-bottom:6px;">
    Why signals were filtered
  </div>
  {rej_items}
</div>"""

        return f"""
<div style="background:{CARD};padding:28px 32px;">
  <div style="font-family:{FONT};font-size:15px;font-weight:600;color:{INK_DIM};">
    No trades executed today
  </div>
  <div style="font-family:{FONT};font-size:12px;color:{INK_MUTE};margin-top:4px;">
    The system scanned the market but didn't find setups worth acting on.
  </div>
  {streak_html}{rej_html}
</div>
"""

    rows_html = ""
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
        s_ink, _, _ = STRAT_BRAND.get(strat, (SLATE, SLATE_BG, SLATE_BORDER))

        if is_buy:
            reason = _infer_buy_reason(strat, raw_reason)
            pnl_html = (
                f'<span style="font-family:{FONT};font-size:12px;'
                f'color:{INK_MUTE};">opened</span>'
            )
            action_col, action_bg_col, action_bdr = GREEN, GREEN_BG, GREEN_BORDER
            action_label = "BUY"
        else:
            pnl_pct = None
            if pnl is not None and t.get("notional"):
                try:
                    cost_basis = float(t["notional"]) - pnl
                    if abs(cost_basis) > 0.01:
                        pnl_pct = (pnl / cost_basis) * 100
                except Exception:
                    pass
            reason = _infer_sell_reason(strat, raw_reason, pnl, pnl_pct, None)
            col = GREEN if (pnl or 0) >= 0 else RED
            pnl_html = (
                f'<span style="font-family:{MONO};font-size:16px;font-weight:700;color:{col};">'
                f"{fmt_money(pnl, sign=True) if pnl is not None else '—'}</span>"
            )
            action_col, action_bg_col, action_bdr = RED, RED_BG, RED_BORDER
            action_label = "SELL"

        rows_html += f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
       style="border-top:1px solid {BORDER};">
<tr><td style="padding:26px 32px;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
  <tr>
    <td width="64" style="vertical-align:top;padding-right:20px;padding-top:4px;">
      <span style="display:inline-block;background:{action_bg_col};color:{action_col};
                   border:1px solid {action_bdr};font-family:{FONT};
                   font-size:10px;font-weight:800;letter-spacing:0.14em;
                   padding:6px 14px;border-radius:4px;">{action_label}</span>
    </td>
    <td style="vertical-align:top;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
      <tr>
        <td style="vertical-align:bottom;">
          <span style="font-family:{MONO};font-size:22px;font-weight:700;
                       color:{INK};letter-spacing:-0.02em;">{html_lib.escape(sym)}</span>
        </td>
        <td align="right" style="vertical-align:top;padding-top:3px;">{pnl_html}</td>
      </tr>
      </table>
      <div style="font-family:{FONT};font-size:13px;color:{INK_MUTE};margin-top:6px;">
        {int(shares)} shares &nbsp;&middot;&nbsp; ${price:,.2f} per share
      </div>
      <div style="font-family:{FONT};font-size:12px;color:{INK_DIM};
                  margin-top:10px;line-height:1.55;">{html_lib.escape(reason)}</div>
      <div style="margin-top:10px;">
        <span style="font-family:{FONT};font-size:10px;color:{s_ink};
                     font-weight:700;letter-spacing:0.05em;text-transform:uppercase;">
          {html_lib.escape(_short_strategy(strat))}
        </span>
      </div>
    </td>
  </tr>
  </table>
</td></tr>
</table>
"""
    return f'<div style="background:{CARD};">{rows_html}</div>'


# ── Section: Movers ───────────────────────────────────────────────────────────
def build_movers(positions: list[dict], top_n: int = 3) -> str:
    def _pnl(p: dict) -> float:
        return float(p.get("unrealized_pnl") or 0)

    def _pct(p: dict) -> float:
        entry = float(p.get("entry_price") or p.get("avg_price") or 0)
        curr = float(p.get("current_price") or entry)
        return ((curr - entry) / entry * 100) if entry else 0.0

    sorted_pos = sorted(positions, key=_pnl, reverse=True) if positions else []
    winners = [p for p in sorted_pos if _pnl(p) > 0][:top_n]
    losers = list(reversed([p for p in sorted_pos if _pnl(p) < 0][-top_n:]))

    def _mover_row(p: dict, col: str) -> str:
        sym = html_lib.escape(p.get("symbol") or "")
        pct = _pct(p)
        entry = float(p.get("entry_price") or p.get("avg_price") or 0)
        curr = float(p.get("current_price") or entry)
        is_stale = abs(curr - entry) < 0.001
        pct_str = "—" if is_stale else f"{'+' if pct >= 0 else ''}{pct:.1f}%"
        pnl_dollar = float(p.get("unrealized_pnl") or 0)
        dollar_str = "" if is_stale else fmt_money(pnl_dollar, sign=True)
        sub = (
            f'<span style="font-family:{FONT};font-size:10px;color:{INK_FAINT};">price pending</span>'
            if is_stale
            else f'<span style="font-family:{FONT};font-size:10px;color:{INK_MUTE};">{dollar_str} since entry</span>'
        )
        return f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
       style="padding:6px 0;">
<tr>
  <td style="font-family:{FONT};color:{INK};font-size:14px;font-weight:bold;
             vertical-align:middle;">{sym}</td>
  <td align="right" style="font-family:{SERIF};color:{col};font-size:14px;font-weight:bold;
             vertical-align:middle;">{pct_str}</td>
</tr>
<tr>
  <td colspan="2" style="padding-bottom:4px;">{sub}</td>
</tr>
</table>"""

    def _half_card(title: str, title_col: str, items: list[dict], col: str, arrow: str) -> str:
        if items:
            rows = "".join(_mover_row(p, col) for p in items)
        else:
            no_data_msg = (
                "No positions are up right now."
                if "Gainers" in title
                else "No positions are down right now."
            )
            rows = (
                f'<div style="font-family:{FONT};color:{INK_FAINT};font-size:13px;'
                f'font-style:italic;padding-top:4px;">{no_data_msg}</div>'
            )
        return f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
       style="background-color:{CARD};border:1px solid {BORDER};border-radius:14px;">
<tr><td style="padding:16px 20px;">
  <div style="font-family:{FONT};color:{title_col};font-size:12px;font-weight:bold;
              letter-spacing:1px;text-transform:uppercase;padding-bottom:10px;">
    {arrow} {html_lib.escape(title)}
  </div>
  {rows}
</td></tr>
</table>"""

    gainers_card = _half_card("Top Gainers", GREEN, winners, GREEN, "&#9650;")
    losers_card = _half_card("Laggards", RED, losers, RED, "&#9660;")

    return f"""
<tr><td style="padding:0 0 12px 0;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
    <td width="50%" valign="top" style="padding-right:6px;">{gainers_card}</td>
    <td width="50%" valign="top" style="padding-left:6px;">{losers_card}</td>
  </tr></table>
</td></tr>
"""


# ── Section: Open Positions ────────────────────────────────────────────────────
def build_positions(positions: list[dict]) -> str:
    MAX_ROWS = 6
    shown = positions[:MAX_ROWS]
    total = len(positions)

    title_suffix = (
        f'<span style="color:{INK_FAINT};font-weight:normal;"> (top {MAX_ROWS} of {total})</span>'
        if total > MAX_ROWS
        else ""
    )

    if not shown:
        inner_html = (
            f'<div style="padding:20px 0;font-family:{FONT};color:{INK_FAINT};'
            f'font-size:13px;font-style:italic;">No open positions right now.</div>'
        )
    else:
        rows_html = ""
        for i, p in enumerate(shown):
            sym = p.get("symbol") or ""
            shares = float(p.get("shares") or 0)
            avg = float(p.get("avg_price") or 0)
            curr = float(p.get("current_price") or avg)
            stored_unr = float(p.get("unrealized_pnl") or 0)
            days_held = int(p.get("days_held") or 0)
            value = shares * curr

            prices_stale = abs(curr - avg) < 0.001
            if prices_stale and stored_unr == 0.0:
                pnl_col = INK_FAINT
                pnl_main = "&mdash;"
                pnl_sub = ""
            else:
                unr = stored_unr if abs(stored_unr) > 0.001 else (shares * (curr - avg))
                ret_pct = ((curr - avg) / avg * 100) if avg else 0.0
                pnl_col = INK_MUTE if abs(unr) < 0.01 else (GREEN if unr > 0 else RED)
                sign = "&minus;" if unr < 0 else "+"
                pnl_main = f"{sign}${abs(unr):,.2f}"
                pnl_sub = f"{ret_pct:+.1f}%"

            is_last = i == len(shown) - 1
            border_style = "" if is_last else "border-bottom:1px solid #14202f;"
            days_txt = "today" if days_held == 0 else f"{days_held}d"

            rows_html += f"""
<tr><td style="padding:16px 0;{border_style}">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
  <tr>
    <td style="vertical-align:bottom;">
      <span style="font-family:{FONT};font-size:15px;font-weight:bold;color:{INK};">{html_lib.escape(sym)}</span>
      <span style="font-family:{FONT};font-size:11px;color:{INK_MUTE};margin-left:8px;">{int(shares)} shares</span>
    </td>
    <td align="right" style="vertical-align:bottom;">
      <span style="font-family:{SERIF};font-size:16px;font-weight:bold;color:{pnl_col};">{pnl_main}</span>
      {"&nbsp;<span style='font-family:" + FONT + ";font-size:12px;color:" + pnl_col + ";'>" + pnl_sub + "</span>" if pnl_sub else ""}
    </td>
  </tr>
  <tr>
    <td colspan="2" style="padding-top:5px;">
      <span style="font-family:{FONT};font-size:11px;color:{INK_MUTE};">
        ${value:,.0f} total
        &nbsp;&middot;&nbsp; avg ${avg:,.2f}
        {"&nbsp;&middot;&nbsp; now $" + f"{curr:,.2f}" if not prices_stale else ""}
        &nbsp;&middot;&nbsp; held {days_txt}
      </span>
    </td>
  </tr>
  </table>
</td></tr>"""

        inner_html = f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
  {rows_html}
</table>"""

    return f"""
<tr><td style="padding:12px 4px 12px 4px;font-family:{FONT};color:{INK_MUTE};
               font-size:12px;font-weight:bold;letter-spacing:2px;text-transform:uppercase;">
  Your Holdings{title_suffix}
</td></tr>
<tr><td style="padding:0 0 12px 0;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
         style="background-color:{CARD};border:1px solid {BORDER};border-radius:14px;">
  <tr><td style="padding:8px 22px 14px 22px;">
    {inner_html}
  </td></tr>
  </table>
</td></tr>
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


def _sentiment_plain(score: float) -> tuple[str, str, str]:
    """Return (plain-English label, color, bg) for a sentiment score."""
    if score >= 0.62:
        return "Good news", GREEN, GREEN_BG
    elif score <= 0.38:
        return "Concerning news", RED, RED_BG
    else:
        return "Mixed / neutral news", INK_MUTE, CARD_ALT


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
        return (1 if s in traded_set else 0, best_q, sent_mag)

    ranked = sorted(
        [s for s in all_symbols if news_map.get(s, {}).get("articles")],
        key=_rank_key,
        reverse=True,
    )[:max_stories]

    if not ranked:
        return f"""
<div style="background:{CARD};padding:28px 32px;">
  <div style="font-family:{FONT};font-size:13px;color:{INK_MUTE};">
    No headlines for today's holdings.
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
        is_traded = sym in traded_set
        pos_ctx = _position_context(positions, sym)

        tone_label, tone_col, tone_bg = _sentiment_plain(score)

        why = ""
        if summarizer is not None:
            try:
                why = summarizer.summarize_for_position(sym, articles, pos_ctx, score)
            except Exception:
                why = ""

        # Headline as clickable link
        headline_text = html_lib.escape(lead.get("title", ""))
        link = lead.get("link", "")
        if link:
            headline_html = (
                f'<a href="{html_lib.escape(link)}" target="_blank" '
                f'style="color:{INK_DIM};text-decoration:underline;font-size:12px;">{headline_text} &#8599;</a>'
            )
        else:
            headline_html = f'<span style="color:{INK_DIM};font-size:12px;">{headline_text}</span>'

        meta_bits = []
        if lead.get("source"):
            meta_bits.append(html_lib.escape(lead["source"]))
        if lead.get("age"):
            meta_bits.append(html_lib.escape(lead["age"]))
        meta_str = " &middot; ".join(meta_bits)

        # Position context for this symbol
        qty = float(pos_ctx.get("qty") or 0)
        unr = float(pos_ctx.get("unrealized_pnl") or 0)

        # "You own" line with P&L context
        if qty > 0:
            unr_col = GREEN if unr >= 0 else RED
            if abs(unr) < 0.01:
                pos_context_html = (
                    f'<span style="font-family:{FONT};font-size:12px;color:{INK_MUTE};">'
                    f"You own {int(qty)} shares of {html_lib.escape(sym)}.</span>"
                )
            else:
                pos_context_html = (
                    f'<span style="font-family:{FONT};font-size:12px;color:{INK_MUTE};">'
                    f"You own {int(qty)} shares &middot; "
                    f'<span style="color:{unr_col};font-weight:600;">{fmt_money(unr, sign=True)} unrealized</span></span>'
                )
        else:
            pos_context_html = ""

        traded_badge = (
            f'<span style="background:{AMBER_BG};color:{AMBER};'
            f"border:1px solid {AMBER_BORDER};font-size:9px;font-weight:800;"
            f"letter-spacing:0.12em;padding:2px 8px;border-radius:4px;"
            f'display:inline-block;margin-left:6px;">TRADED TODAY</span>'
            if is_traded
            else ""
        )

        # Plain-English "why it matters" — prefer AI summary, fall back to simple framing
        if why:
            explanation = html_lib.escape(why)
        elif score >= 0.62:
            explanation = (
                f"Positive news about {html_lib.escape(sym)} — this type of coverage "
                f"typically supports the stock price."
            )
        elif score <= 0.38:
            explanation = (
                f"Negative coverage around {html_lib.escape(sym)} — this may create "
                f"short-term selling pressure on the stock."
            )
        else:
            explanation = f"Mixed or neutral coverage. No strong signal either way for {html_lib.escape(sym)}."

        blocks.append(
            f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
       style="border-top:1px solid {BORDER};">
<tr><td style="padding:22px 32px;">
  <!-- Header: symbol + sentiment pill -->
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
         style="margin-bottom:12px;">
  <tr>
    <td style="vertical-align:middle;">
      <span style="font-family:{MONO};font-size:15px;font-weight:700;color:{INK};">{html_lib.escape(sym)}</span>
      {traded_badge}
    </td>
    <td align="right" style="vertical-align:middle;">
      <span style="display:inline-block;background:{tone_bg};color:{tone_col};
                   font-family:{FONT};font-size:10px;font-weight:700;
                   padding:3px 10px;border-radius:5px;">{html_lib.escape(tone_label)}</span>
    </td>
  </tr>
  </table>
  <!-- Position context -->
  {('<div style="margin-bottom:10px;">' + pos_context_html + '</div>') if pos_context_html else ''}
  <!-- Plain-English explanation -->
  <div style="font-family:{FONT};font-size:13px;color:{INK_DIM};
              line-height:1.6;margin-bottom:12px;">
    {explanation}
  </div>
  <!-- Source headline (secondary) -->
  <div style="font-family:{FONT};font-size:11px;color:{INK_FAINT};
              border-left:2px solid {BORDER_STRONG};padding-left:10px;
              margin-bottom:8px;line-height:1.5;">
    {headline_html}
  </div>
  <!-- Source + age -->
  {"<div style='font-family:" + FONT + ";font-size:10px;color:" + INK_FAINT + ";'>" + meta_str + "</div>" if meta_str else ""}
</td></tr>
</table>"""
        )

    return f"""
<div style="background:{CARD};">
  {''.join(blocks)}
  <div style="padding:10px 32px;border-top:1px solid {BORDER};background:{CARD_ALT};
              font-family:{FONT};font-size:10px;color:{INK_MUTE};
              letter-spacing:0.08em;font-weight:600;text-transform:uppercase;">
    News affecting your holdings &middot; Google News
  </div>
</div>
"""


# ── Section: System Status ────────────────────────────────────────────────────
def build_system_status(recon_status: str, fill_summary: dict, db_path: str) -> str:
    recon_upper = (recon_status or "").upper()
    recon_ok = "SYNCED" in recon_upper or "PASS" in recon_upper
    recon_label = "Balanced with broker" if recon_ok else f"Sync issue: {recon_status}"

    fill_count = int(fill_summary.get("fill_count") or 0)
    avg_dev = fill_summary.get("avg_dev")
    fill_ok = fill_count == 0 or (avg_dev is not None and float(avg_dev) < 30)
    fill_label = (
        "No fills today"
        if fill_count == 0
        else f"{fill_count} fills · avg {float(avg_dev or 0):.0f} bps slippage"
    )

    readiness_rows = ""
    try:
        from check_live_readiness import evaluate_readiness

        result = evaluate_readiness(db_path)
        for c in result.get("checks", []):
            ok = c.get("ok")
            dot = GREEN if ok else RED
            readiness_rows += f"""
<div style="display:flex;justify-content:space-between;align-items:center;
            padding:9px 0;border-top:1px solid {BORDER};">
  <span style="font-family:{FONT};font-size:12px;color:{INK_DIM};
               display:flex;align-items:center;gap:10px;">
    <span style="display:inline-block;width:6px;height:6px;border-radius:50%;
                 background:{dot};flex-shrink:0;"></span>
    {html_lib.escape(c.get('label', ''))}
  </span>
  <span style="font-family:{MONO};font-size:11px;color:{INK_MUTE};">
    {html_lib.escape(c.get('display', '—'))}
  </span>
</div>"""
    except Exception:
        pass

    def _row(label: str, detail: str, ok: bool) -> str:
        ic = GREEN if ok else AMBER
        sym = "✓" if ok else "!"
        return f"""
<div style="display:flex;justify-content:space-between;align-items:center;
            padding:11px 0;border-top:1px solid {BORDER};">
  <span style="font-family:{FONT};font-size:13px;color:{INK};
               display:flex;align-items:center;gap:10px;">
    <span style="font-family:{MONO};font-size:12px;font-weight:700;color:{ic};">{sym}</span>
    {html_lib.escape(label)}
  </span>
  <span style="font-family:{FONT};font-size:12px;color:{INK_MUTE};">
    {html_lib.escape(detail)}
  </span>
</div>"""

    ts = datetime.now().strftime("%Y-%m-%d %H:%M ET")
    return f"""
<div style="background:{CARD};padding:20px 32px 24px;">
  <div style="font-family:{FONT};font-size:11px;color:{INK_MUTE};margin-bottom:8px;">
    Generated {ts} · Paper trading only
  </div>
  {_row("Broker reconciliation", recon_label, recon_ok)}
  {_row("Fill quality", fill_label, fill_ok)}
  {readiness_rows}
</div>
"""


# ── Section: Live Readiness ───────────────────────────────────────────────────
def build_golive_section(db_path: str, recon_status: str, data_stale: bool) -> str:
    import math as _math
    import time as _time2
    from datetime import date as _date

    # Live readiness uses a stricter 26h freshness threshold (data should be from
    # yesterday at latest). The 144h threshold in the health card is the operational
    # fallback; here we want the tighter standard required before going live.
    _csv_path2 = PROJECT_ROOT / "data" / "training_data.csv"
    PIPELINE_MAX_HOURS = 26
    if _csv_path2.exists():
        _age_h = (_time2.time() - _csv_path2.stat().st_mtime) / 3600
        pipeline_stale = _age_h >= PIPELINE_MAX_HOURS
    else:
        pipeline_stale = True

    db = _conn(db_path)
    try:
        agg = _q1(
            db,
            """
            SELECT COUNT(*) AS closed,
                   SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) AS wins
            FROM trades WHERE pnl IS NOT NULL
        """,
        )
        closed = int(agg.get("closed") or 0)
        wins = int(agg.get("wins") or 0)

        run_dates = _q1(
            db,
            """
            SELECT MIN(DATE(created_at)) AS first_day,
                   MAX(DATE(created_at)) AS last_day
            FROM broker_state
            WHERE run_id NOT IN ('AUTO_SYNC', '') AND run_id IS NOT NULL
        """,
        )
        days_running = 0
        first_day = run_dates.get("first_day") or ""
        if first_day:
            try:
                days_running = (_date.today() - _date.fromisoformat(first_day)).days
            except Exception:
                pass

        max_dd = 0.0
        try:
            dd_row = _q1(
                db,
                """
                SELECT MAX(CAST(json_extract(metrics_json, '$.max_drawdown') AS REAL)) AS v
                FROM run_slo_metrics
            """,
            )
            max_dd = float(dd_row.get("v") or 0)
        except Exception:
            pass

        rp = _q1(
            db,
            """
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN reconciliation_status='PASS' THEN 1 ELSE 0 END) AS passes
            FROM broker_state
            WHERE snapshot_type IN ('RECONCILIATION','RECONCILIATION_RETRY','END')
              AND created_at >= date('now', '-30 days')
        """,
        )
        recon_total = int(rp.get("total") or 0)
        recon_passes = int(rp.get("passes") or 0)
        recon_rate = recon_passes / recon_total if recon_total > 0 else 0.0
    finally:
        db.close()

    recon_ok_env = (recon_status or "").upper() in ("PASS", "SYNCED") or "PASS" in (
        recon_status or ""
    ).upper()

    # 5 go-live criteria
    MIN_TRADES = 20
    MIN_DAYS = 30
    MAX_DD_THRESHOLD = 0.15
    MIN_RECON_RATE = 0.90

    # Pace estimate: use actual closed-trade rate instead of hardcoded "2/week"
    weeks_running = max(days_running / 7, 1)
    trades_per_week = closed / weeks_running
    needed = max(MIN_TRADES - closed, 0)
    if closed >= MIN_TRADES:
        pace_fix = None
    elif trades_per_week >= 0.1:
        weeks_needed = _math.ceil(needed / trades_per_week)
        pace_fix = (
            f"Need {needed} more closed trades "
            f"(~{weeks_needed} weeks at current pace of {trades_per_week:.1f}/week)"
        )
    else:
        pace_fix = (
            f"Need {needed} more closed trades — current pace is very low "
            f"({closed} in {days_running}d). Check strategy signal logs."
        )

    criteria = [
        {
            "label": f"≥ {MIN_TRADES} closed trades",
            "ok": closed >= MIN_TRADES,
            "actual": f"{closed} closed",
            "fix": pace_fix,
        },
        {
            "label": f"≥ {MIN_DAYS} days paper-trading",
            "ok": days_running >= MIN_DAYS,
            "actual": f"{days_running}d since {first_day[:10] if first_day else '?'}",
            "fix": f"Continue for {max(0, MIN_DAYS - days_running)} more days"
            if days_running < MIN_DAYS
            else None,
        },
        {
            "label": f"Data pipeline current (<{PIPELINE_MAX_HOURS}h)",
            "ok": not pipeline_stale,
            "actual": "Fresh" if not pipeline_stale else "Stale",
            "fix": "python3 scripts/update_daily_data.py  (or run the GHA workflow manually)"
            if pipeline_stale
            else None,
        },
        {
            "label": f"Max drawdown < {int(MAX_DD_THRESHOLD * 100)}%",
            "ok": max_dd < MAX_DD_THRESHOLD,
            "actual": f"{max_dd:.2%}",
            "fix": "Review strategy risk limits and position sizing"
            if max_dd >= MAX_DD_THRESHOLD
            else None,
        },
        {
            "label": f"Broker recon ≥ {int(MIN_RECON_RATE * 100)}% (30d)",
            "ok": recon_rate >= MIN_RECON_RATE or (recon_total == 0),
            "actual": f"{recon_passes}/{recon_total} runs pass" if recon_total > 0 else "No data",
            "fix": (
                "Open sync_database.yml and investigate reconciliation failures — "
                "do NOT go live until this is consistently green"
                if recon_rate < MIN_RECON_RATE and recon_total > 0
                else None
            ),
        },
    ]

    passed = sum(1 for c in criteria if c["ok"])
    total = len(criteria)
    is_ready = passed == total

    # Readiness check rows
    check_rows = ""
    for c in criteria:
        ok = c["ok"]
        icon = (
            f'<span style="color:{GREEN};">&#10003;</span>'
            if ok
            else f'<span style="color:{RED};">&#10007;</span>'
        )
        actual_col = INK_MID if ok else RED
        check_rows += (
            f"<tr>"
            f'<td style="padding:7px 0;font-family:{FONT};font-size:12px;color:{INK_DIM};">'
            f'{icon}&nbsp; {html_lib.escape(str(c["label"]))}</td>'
            f'<td align="right" style="padding:7px 0;font-family:{FONT};font-size:12px;color:{actual_col};">'
            f'{html_lib.escape(str(c["actual"]))}</td>'
            f"</tr>"
        )

    # Action plan (only failing items)
    fixes = [(c["label"], c["fix"]) for c in criteria if not c["ok"] and c["fix"]]
    action_html = ""
    if fixes:
        fix_items = "".join(
            f'<tr><td style="padding:5px 0;border-bottom:1px solid {BORDER_INSET};">'
            f'<div style="font-family:{FONT};font-size:11px;color:{INK_MID};">'
            f'<span style="color:{AMBER};">&#9654;</span>&nbsp;'
            f"<strong>{html_lib.escape(str(lbl))}</strong></div>"
            f'<div style="font-family:{FONT};font-size:11px;color:{INK_FAINT};padding:2px 0 4px 14px;">'
            f"{html_lib.escape(str(fix))}</div>"
            f"</td></tr>"
            for lbl, fix in fixes
        )
        action_html = f"""
<div style="margin-top:16px;padding-top:14px;border-top:1px solid {BORDER_INSET};">
  <div style="font-family:{FONT};color:{INK_MUTE};font-size:10px;font-weight:bold;
              letter-spacing:1px;text-transform:uppercase;padding-bottom:8px;">
    What to Fix
  </div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
    {fix_items}
  </table>
</div>"""

    verdict_col = GREEN if is_ready else (AMBER if passed >= 3 else RED)
    verdict_bg = GREEN_BG if is_ready else (AMBER_BG if passed >= 3 else RED_BG)
    verdict_border = GREEN_BORDER if is_ready else (AMBER_BORDER if passed >= 3 else RED_BORDER)
    verdict_text = (
        "&#10003; READY TO GO LIVE"
        if is_ready
        else f"NOT READY &mdash; {passed}/{total} criteria met"
    )

    return f"""
<tr><td style="padding:14px 4px 10px 4px;font-family:{FONT};color:{INK_MUTE};
               font-size:12px;font-weight:bold;letter-spacing:2px;text-transform:uppercase;">
  Live Readiness
</td></tr>
<tr><td style="padding:0 0 20px 0;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
         style="background-color:{CARD};border:1px solid {BORDER};border-radius:14px;">
  <tr><td style="padding:18px 22px;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
      {check_rows}
    </table>
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
           style="margin-top:12px;background-color:{verdict_bg};border:1px solid {verdict_border};border-radius:8px;">
    <tr><td style="padding:11px 16px;font-family:{FONT};font-size:13px;font-weight:bold;color:{verdict_col};">
      {verdict_text}
    </td></tr>
    </table>
    {action_html}
  </td></tr>
  </table>
</td></tr>
"""


# ── Footer ────────────────────────────────────────────────────────────────────
def build_footer() -> str:
    return f"""
<tr><td style="padding:20px 4px 8px 4px;text-align:center;
               font-family:{FONT};color:{INK_FAINT};font-size:11px;line-height:1.6;">
  <strong style="color:{INK_MUTE};">Investor Mimic</strong> &mdash;
  fully automated paper-trading. All trades are simulated. No real money is at risk.
</td></tr>
"""


# ── Main entry ────────────────────────────────────────────────────────────────
def generate_email_body(db_path: str = "trading.db", include_visuals: bool = True) -> str:
    # Workflow health context from env vars injected by daily_trading.yml
    recon_status_env = os.environ.get("RECON_STATUS")
    auto_sync_ok_env = os.environ.get("AUTO_SYNC_OK")
    drift_resolved_env = os.environ.get("DRIFT_RESOLVED")
    drift_remaining_env = os.environ.get("DRIFT_REMAINING")
    run_number_env = os.environ.get("RUN_NUMBER")

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
    cash = float(snap.get("cash") or 0)
    recon = recon_status_env or snap.get("reconciliation_status") or "UNKNOWN"

    today_pnl = 0.0
    today_pct = 0.0
    if len(equity) >= 2:
        prev = equity[-2]["total"]
        curr_e = equity[-1]["total"]
        today_pnl = (curr_e or 0) - (prev or 0)
        today_pct = (today_pnl / prev * 100) if prev else 0.0

    total_pnl = float(agg.get("total_pnl") or 0)
    closed = int(agg.get("closed") or 0)

    date_str = datetime.now().strftime("%A, %b %-d")

    db2 = _conn(db_path)
    try:
        alerts = get_system_alerts(db2, recon, zero_streak)
    finally:
        db2.close()

    # Strategy health scores from StrategyHealthScorer
    health_by_name: dict[str, dict] = {}
    try:
        from src.monitoring.strategy_health_scorer import StrategyHealthScorer

        class _DBWrap:
            def __init__(self, path: str) -> None:
                self.db_path = path

        scorer = StrategyHealthScorer(_DBWrap(db_path))
        for row in strategy_rows:
            sid = row.get("id")
            sname = row.get("name") or ""
            if sid is not None and sname:
                health_by_name[sname] = scorer.calculate_strategy_health(int(sid), sname)
    except Exception:
        pass

    spy_return = _fetch_spy_return()
    traded_today_syms = [t.get("symbol", "") for t in trades_today if t.get("symbol")]

    # needs_attention glow: swap inner gradient colour when there's unresolved drift
    recon_upper = (recon_status_env or recon or "").upper()
    recon_failed = "FAIL" in recon_upper
    drift_unresolved = str(drift_resolved_env or "").lower() != "true"
    needs_attention = recon_failed and drift_unresolved
    glow_inner = "#2b1313" if needs_attention else "#131b2b"

    # Compute data freshness once so both health card and golive section share it
    import time as _time

    _csv = PROJECT_ROOT / "data" / "training_data.csv"
    _data_stale = not _csv.exists() or ((_time.time() - _csv.stat().st_mtime) / 3600 >= 144)

    _trades_html = build_today_trades(
        trades_today, sig_map, rejections=rejections, zero_trade_streak=zero_streak
    )
    _news_html = build_news_digest(positions, traded_today=traded_today_syms)

    inner_rows = (
        build_header_bar(date_str, run_number_env)
        + build_hero(
            pv,
            today_pnl,
            today_pct,
            date_str,
            equity=equity,
            spy_return=spy_return,
            total_pnl=total_pnl,
            cash=cash,
            open_count=len(positions),
        )
        + build_alert_banner(alerts)
        + build_strategy_dashboard(strategy_rows, health_by_name=health_by_name, portfolio_value=pv)
        + _section_title("Today's Trades", count=len(trades_today) or None)
        + f'<tr><td style="padding:0 0 12px 0;">{_trades_html}</td></tr>'
        + _section_title("Movers & Shakers")
        + build_movers(positions)
        + build_positions(positions)
        + _section_title("What's Moving Your Stocks")
        + (f'<tr><td style="padding:0 0 12px 0;">{_news_html}</td></tr>' if _news_html else "")
        + _section_title("System Status")
        + build_health_card(
            recon_status=recon_status_env or recon,
            auto_sync_ok=auto_sync_ok_env,
            drift_resolved=drift_resolved_env,
            drift_remaining=drift_remaining_env,
            fill_summary=fill_summary,
            db_path=db_path,
        )
        + build_golive_section(
            db_path, recon_status=recon_status_env or recon, data_stale=_data_stale
        )
        + build_footer()
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Investor Mimic &middot; Daily</title>
</head>
<body style="margin:0;padding:0;background-color:{PAGE_BG};">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
       style="background-color:{PAGE_BG};background-image:radial-gradient(circle at 50% 0%,{glow_inner} 0%,{PAGE_BG} 60%);">
<tr><td align="center" style="padding:32px 16px;">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0"
       style="width:600px;max-width:600px;">
  {inner_rows}
</table>
</td></tr>
</table>
</body>
</html>"""


_MOCK_STATES: dict[str, dict[str, str]] = {
    "healthy": {
        "RECON_STATUS": "PASS",
        "AUTO_SYNC_OK": "",
        "DRIFT_RESOLVED": "",
        "DRIFT_REMAINING": "0",
        "RUN_NUMBER": "42",
    },
    "auto_recovered": {
        "RECON_STATUS": "FAIL",
        "AUTO_SYNC_OK": "true",
        "DRIFT_RESOLVED": "true",
        "DRIFT_REMAINING": "0",
        "RUN_NUMBER": "43",
    },
    "needs_action": {
        "RECON_STATUS": "FAIL",
        "AUTO_SYNC_OK": "false",
        "DRIFT_RESOLVED": "false",
        "DRIFT_REMAINING": "3",
        "RUN_NUMBER": "44",
    },
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--include-visuals", action="store_true", help="Compatibility flag — visuals always on."
    )
    parser.add_argument("--send", action="store_true")
    parser.add_argument("--db", default="trading.db")
    parser.add_argument(
        "--mock-state",
        choices=list(_MOCK_STATES),
        help="Inject mock workflow health env vars for preview testing.",
    )
    args = parser.parse_args()

    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    if args.mock_state:
        for k, v in _MOCK_STATES[args.mock_state].items():
            os.environ[k] = v
        print(f"🔧 Mock state: {args.mock_state}")

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
