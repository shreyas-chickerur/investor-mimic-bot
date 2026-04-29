#!/usr/bin/env python3
"""
Daily Email Digest — plain-English summary of today's trading decisions.
For every trade: shows the news headline, what the system noticed, and why
it bought or sold. No jargon. Readable by anyone.
"""
import sys
import json
import sqlite3
import glob
import html as html_lib
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# ── Palette ──────────────────────────────────────────────────────────────────
BG      = '#f6f0e6'
WHITE   = '#fffdf8'
HDR     = '#17384f'
HDR_SUB = '#eef7fb'
ACCENT  = '#0f766e'
POS     = '#2f855a'
NEG     = '#c2410c'
MUTED   = '#6b7280'
BORDER  = '#e6d8c3'
ROW_ALT = '#fff8ec'
TH_BG   = '#fdf3e2'
TEXT    = '#1f2937'
TEXT2   = '#4b5563'
MONO    = '"Menlo",Consolas,monospace'
FONT_UI = '"Avenir Next","Segoe UI","Helvetica Neue",Arial,sans-serif'

# ── DB helpers ────────────────────────────────────────────────────────────────
def _conn(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def q(db, sql, *args):
    try:
        return [dict(r) for r in db.execute(sql, args).fetchall()]
    except Exception:
        return []

def q1(db, sql, *args):
    rows = q(db, sql, *args)
    return rows[0] if rows else {}

# ── Queries ───────────────────────────────────────────────────────────────────
def get_snapshot(db):
    snap = q1(db, """
        SELECT portfolio_value, cash, reconciliation_status
        FROM broker_state
        WHERE reconciliation_status IS NOT NULL
          AND reconciliation_status != 'SKIPPED'
          AND snapshot_type IN ('RECONCILIATION', 'RECONCILIATION_RETRY', 'END', 'SYNC')
        ORDER BY created_at DESC, id DESC
        LIMIT 1
    """)
    if not snap:
        snap = q1(db, "SELECT portfolio_value, cash, reconciliation_status "
                       "FROM broker_state ORDER BY created_at DESC LIMIT 1")
    dd_row = q1(db, "SELECT value FROM system_state WHERE key='drawdown_stop_state'")
    dd = {}
    if dd_row.get('value'):
        try: dd = json.loads(dd_row['value'])
        except Exception: pass
    rg_row = q1(db, "SELECT value FROM system_state WHERE key='regime'")
    rg = {}
    if rg_row.get('value'):
        try: rg = json.loads(rg_row['value'])
        except Exception: rg = {'classification': rg_row['value']}
    return snap, dd, rg

def get_30d(db):
    """30-day daily portfolio value from broker_state START snapshots."""
    return q(db, """
        SELECT snapshot_date AS date, portfolio_value AS total
        FROM broker_state
        WHERE snapshot_type = 'START'
          AND snapshot_date >= date('now', '-30 days')
        GROUP BY snapshot_date
        ORDER BY snapshot_date""")

_CANONICAL_STRATEGIES = [
    'RSI Mean Reversion',
    'ML Momentum',
    'Earnings Drift',
    'Factor Momentum',
]

def get_all_time_perf(db):
    rows = q(db, """
        SELECT s.name,
          COUNT(t.id)                                          total_trades,
          SUM(CASE WHEN t.pnl > 0 THEN 1 ELSE 0 END)         wins,
          SUM(CASE WHEN t.pnl IS NOT NULL AND t.pnl <= 0 THEN 1 ELSE 0 END) losses,
          SUM(COALESCE(t.pnl, 0))                             total_pnl,
          MAX(t.pnl)                                          best_trade,
          MIN(t.pnl)                                          worst_trade,
          AVG(CASE WHEN t.pnl > 0 THEN t.pnl END)            avg_win,
          AVG(CASE WHEN t.pnl IS NOT NULL AND t.pnl <= 0 THEN t.pnl END) avg_loss,
          MIN(DATE(t.executed_at))                            first_trade
        FROM strategies s LEFT JOIN trades t
          ON t.strategy_id = s.id AND t.pnl IS NOT NULL
        WHERE s.name IN ('RSI Mean Reversion','ML Momentum','Earnings Drift','Factor Momentum')
        GROUP BY s.name ORDER BY total_pnl DESC""")
    # Ensure all 4 canonical strategies appear even if missing from DB
    found = {r['name'] for r in rows}
    for name in _CANONICAL_STRATEGIES:
        if name not in found:
            rows.append({'name': name, 'total_trades': 0, 'wins': 0, 'losses': 0,
                         'total_pnl': 0, 'best_trade': None, 'worst_trade': None,
                         'avg_win': None, 'avg_loss': None, 'first_trade': None})
    rows.sort(key=lambda r: r.get('total_pnl') or 0, reverse=True)
    return rows

def get_today_signals_for_trades(db):
    """Return signal reasoning keyed by (symbol, strategy_id) for today's executed signals."""
    rows = q(db, """
        SELECT sg.symbol, sg.strategy_id, sg.signal_type, sg.confidence,
               sg.reasoning, sg.terminal_state, s.name strat
        FROM signals sg JOIN strategies s ON sg.strategy_id = s.id
        WHERE sg.asof_date = DATE('now')
          AND (sg.terminal_state = 'EXECUTED'
               OR sg.generated_at >= datetime('now', '-1 day'))
        ORDER BY sg.generated_at DESC""")
    out = {}
    for r in rows:
        key = (r['symbol'], r['strat'])
        if key not in out:          # keep first (most recent) per symbol+strategy
            out[key] = r
    return out

def get_strategy_concerns_data(db):
    """Return per-strategy rejection counts and recent win rates for the concerns panel."""
    rejections = q(db, """
        SELECT s.name strat, sr.stage, sr.reason_code, COUNT(*) cnt
        FROM signal_rejections sr JOIN strategies s ON sr.strategy_id = s.id
        WHERE sr.created_at >= datetime('now', '-7 days') AND s.name != 'BROKER_SYNC'
        GROUP BY s.name, sr.stage, sr.reason_code ORDER BY cnt DESC""")
    recent = q(db, """
        SELECT s.name strat,
          COUNT(t.id) trades,
          SUM(CASE WHEN t.pnl > 0 THEN 1 ELSE 0 END) wins,
          SUM(COALESCE(t.pnl, 0)) pnl
        FROM trades t JOIN strategies s ON t.strategy_id = s.id
        WHERE t.executed_at >= datetime('now', '-30 days') AND t.pnl IS NOT NULL
          AND s.name != 'BROKER_SYNC'
        GROUP BY s.name""")
    return rejections, recent

def fetch_symbol_news(symbols):
    """Fetch headlines via Google News RSS (no API key needed). Returns {symbol: [headline, ...]}"""
    if not symbols:
        return {}
    try:
        sys.path.insert(0, str(project_root))
        from src.utils.news_sentiment import fetch_symbol_news as _fetch
        result = {}
        for sym in symbols:
            ctx = _fetch(sym, max_articles=5)
            if ctx.get('headlines'):
                result[sym] = ctx['headlines'][:3]
        return result
    except Exception:
        return {}


# ── Plain-English translation helpers ────────────────────────────────────────

_STRATEGY_LABELS = {
    'RSI Mean Reversion': 'Bounce-Back Strategy',
    'ML Momentum':        'AI Prediction Strategy',
    'Earnings Drift':     'Earnings Momentum Strategy',
    'Factor Momentum':    'Best-in-Class Strategy',
}

def _strategy_label(name):
    return _STRATEGY_LABELS.get(name, name)


def _translate_buy_reason(raw, strategy):
    """Convert a technical signal reasoning string into one plain-English sentence."""
    import re
    r = (raw or '').lower()

    if 'rsi' in r and ('oversold' in r or 'slope' in r or '< 40' in r or '<40' in r):
        return ("The stock had fallen sharply and our system detected it was "
                "starting to bounce back — a classic entry point.")

    if 'ml' in r or 'probability' in r or 'p(up)' in r:
        m_pct = re.search(r'positive\s*5d\s*return[:=\s]*([\d.]+)%', r)
        if m_pct:
            pct = int(float(m_pct.group(1)))
            return (f"Our AI model estimated about a {pct}% chance this stock "
                    f"would rise over the next 5 trading days.")
        m = re.search(r'p\(up\)[=:\s]*([\d.]+)', r)
        if m:
            pct = int(float(m.group(1)) * 100)
            return (f"Our AI model calculated a {pct}% probability the stock "
                    f"would rise over the next 5 trading days.")
        return "Our AI model predicted the stock was more likely than not to rise over the next 5 days."

    if any(w in r for w in ['earnings', 'drift', 'pead', 'volume spike', 'abnormal']):
        m = re.search(r'volume[_\s]*ratio[=:\s]*([\d.]+)', r)
        vol = f"{float(m.group(1)):.1f}×" if m else "unusually high"
        return (f"The stock made a large move on {vol} its normal trading volume — "
                f"often a signal of a significant earnings or news event.")

    if any(w in r for w in ['factor', 'rank', 'composite', 'top 3', 'top 4', 'top 5']):
        m = re.search(r'top\s*(\d+)/(\d+)', r)
        if m:
            rank, total = m.group(1), m.group(2)
            return (f"This stock ranked #{rank} out of {total} companies we track "
                    f"across strength, momentum, and quality — one of the best.")
        return ("This stock ranked in the top 5 of all 36 companies we track "
                "for overall strength and momentum.")

    return "Multiple signals aligned to suggest a good buying opportunity."


def _translate_sell_reason(raw, strategy):
    """Convert a technical exit reasoning string into one plain-English sentence."""
    import re
    r = (raw or '').lower()

    m_gain = re.search(r'([\d.]+)%\s*gain', r)
    m_loss = re.search(r'([\d.]+)%\s*loss', r)

    if 'profit target' in r or ('profit' in r and 'target' in r):
        pct = m_gain.group(1) if m_gain else None
        suffix = f" — locked in a +{pct}% gain" if pct else ""
        return f"The stock hit our profit target{suffix}. We sold to lock in the gains."

    if 'stop-loss' in r or 'stop loss' in r:
        pct = m_loss.group(1) if m_loss else None
        suffix = f" (down {pct}%)" if pct else ""
        return (f"The stock dropped to our stop-loss level{suffix}. "
                f"We sold to prevent further losses.")

    if 'rsi' in r and ('>' in r or 'recovery' in r or 'reversion' in r or 'complete' in r):
        return ("The stock fully recovered from its oversold level — "
                "the bounce-back trade played out as planned.")

    if any(w in r for w in ['rebalance', 'held', 'expired', 'window', 'drift window']):
        m_d = re.search(r'(\d+)\s*d', r)
        days = m_d.group(1) if m_d else None
        suffix = f" after {days} days as planned" if days else " as scheduled"
        return f"We held this position for the planned duration and exited{suffix}."

    if 'negative surprise' in r or ('negative' in r and 'sentiment' in r):
        return ("Our system detected a negative signal — we exited early "
                "to protect any remaining gains.")

    return "The planned exit conditions were met — we sold as scheduled."


def _translate_rejection(stage, reason_code):
    """Translate a technical rejection code to a plain-English explanation."""
    code = (reason_code or '').upper()
    stage = (stage or '').upper()
    m = {
        'MAX_HEAT_EXCEEDED':        'The portfolio was already too invested (over our safe limit)',
        'CORRELATION_FILTER':       'Too similar to a stock we already hold — avoids concentration risk',
        'DAILY_LOSS_LIMIT':         'The portfolio hit today\'s loss limit — paused to protect capital',
        'DATA_QUALITY_FAIL':        'The price data for this stock looked suspicious — skipped for safety',
        'DRAWDOWN_STOP':            'The portfolio drew down too far — all buying paused until recovery',
        'REGIME_FILTER':            'Market conditions were too volatile — held back this trade',
        'KILL_SWITCH':              'The system\'s kill switch was active — no trading today',
        'RECONCILIATION_FAILED':    'Account positions didn\'t match our records — trading paused',
        'NO_BUYING_POWER':          'Not enough cash available for this trade',
        'POSITION_ALREADY_OPEN':    'We already hold this stock — avoided doubling up',
        'CONFIDENCE_TOO_LOW':       'The signal wasn\'t strong enough to act on',
    }
    return m.get(code, f"Blocked at the {stage.lower()} stage ({reason_code})")

def get_positions(db):
    return q(db, """
        SELECT p.symbol, s.name strat, p.shares, p.avg_price, p.current_price,
               p.unrealized_pnl, p.entry_date, p.entry_price, p.stop_loss_price,
               CAST(julianday('now') - julianday(COALESCE(p.entry_date, date('now'))) AS INTEGER) days
        FROM positions p JOIN strategies s ON p.strategy_id=s.id
        WHERE p.shares > 0 AND s.name != 'BROKER_SYNC'
        ORDER BY p.unrealized_pnl DESC""")

def get_today_trades(db):
    return q(db, """
        SELECT t.symbol, t.action, t.shares, t.exec_price,
               t.notional, t.pnl, s.name strat, t.executed_at
        FROM trades t JOIN strategies s ON t.strategy_id=s.id
        WHERE DATE(t.executed_at)=DATE('now') AND s.name != 'BROKER_SYNC'
        ORDER BY t.executed_at""")


def get_health():
    files = glob.glob('artifacts/health/strategy_health_summary_*.json')
    if not files: return None
    try:
        path = max(files, key=lambda x: Path(x).stat().st_mtime)
        with open(path) as f:
            return json.load(f)
    except Exception: return None


def get_guardrail_report():
    """Load latest post-run guardrail report when available."""
    path = Path('artifacts/diagnostics/post_run_guardrails.json')
    if not path.exists():
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None

# ── Utilities ─────────────────────────────────────────────────────────────────
def sparkline(values, width=28):
    blocks = ' \u2581\u2582\u2583\u2584\u2585\u2586\u2587\u2588'
    if len(values) < 2: return '\u2014'
    mn, mx = min(values), max(values)
    rng = mx - mn or 1
    step = max(1, len(values) // width)
    return ''.join(blocks[int((values[i] - mn) / rng * 8)] for i in range(0, len(values), step))

def fmt_pnl(v):
    if v is None: return '\u2014'
    sign = '+' if v >= 0 else ''
    return sign + '${:,.2f}'.format(v)

def pnl_col(v):
    if v is None or v == 0: return MUTED
    return POS if v > 0 else NEG

def chip(label, color):
    return ("<span style='display:inline-block;background:" + color + ";color:#fff;"
            "font-size:10px;font-weight:700;letter-spacing:0.4px;"
            "padding:3px 9px;border-radius:999px;text-transform:uppercase;'>"
            + label + "</span>")

# ── Layout helpers ────────────────────────────────────────────────────────────
def section(title, body, note=''):
    note_html = ''
    if note:
        note_html = ("<span style='font-size:12px;color:" + MUTED + ";font-weight:500;"
                     "margin-left:10px;'>" + note + "</span>")
    return ("  <div style='margin-bottom:26px;'>\n"
            "    <div style='font-size:20px;font-weight:700;color:" + TEXT + ";"
            "padding-bottom:10px;margin-bottom:14px;line-height:1.35;"
            "border-bottom:2px solid " + BORDER + ";'>" + title + note_html + "</div>\n"
            "    " + body + "\n"
            "  </div>\n")

def th(label, align='left'):
    return ("<th style='padding:11px 13px;text-align:" + align + ";font-size:11px;"
            "font-weight:700;letter-spacing:0.4px;text-transform:uppercase;"
            "color:" + TEXT2 + ";background:" + TH_BG + ";"
            "border-bottom:2px solid " + BORDER + ";'>" + label + "</th>")

def tbl(headers, rows_html, aligns=None):
    ths = ''.join(th(h, (aligns[i] if aligns else 'left')) for i, h in enumerate(headers))
    return ("<table style='width:100%;border-collapse:collapse;font-size:13px;"
            "border:1px solid " + BORDER + ";border-radius:10px;overflow:hidden;'>"
            "<thead><tr>" + ths + "</tr></thead>"
            "<tbody>" + rows_html + "</tbody></table>")

def td_s(val, align='left', bold=False, color=None, mono=False, small=False):
    s = "padding:11px 13px;text-align:" + align + ";border-bottom:1px solid " + BORDER + ";vertical-align:middle;"
    if bold:  s += "font-weight:700;"
    if color: s += "color:" + color + ";"
    if mono:  s += "font-family:" + MONO + ";"
    if small: s += "font-size:12px;"
    return "<td style='" + s + "'>" + str(val) + "</td>"

# ── Header ────────────────────────────────────────────────────────────────────
def build_header(pv, cash, daily_pnl, daily_pct, dd, regime, recon, n_trades, data_missing=False):
    today = datetime.now().strftime('%a %b %-d, %Y')
    invested = pv - cash
    heat = invested / pv * 100 if pv > 0 else 0
    dd_pct = dd.get('drawdown', 0) * 100
    dd_str = (dd.get('state') or 'NORMAL').upper()
    regime_str = (regime.get('classification') or 'UNKNOWN').upper()
    vix = regime.get('vix', '\u2014')

    pnl_sign = '+' if daily_pnl >= 0 else ''
    pc = POS if daily_pnl >= 0 else NEG

    recon_ok = 'SYNCED' in recon.upper() or 'PASS' in recon.upper()
    if data_missing:
        recon_chip = chip('Data Missing', '#b45309')
    else:
        recon_chip = chip('Account Synced' if recon_ok else 'Out of Sync', POS if recon_ok else NEG)

    regime_labels = {'NORMAL': 'Normal market', 'HIGH_VOL': 'Volatile market', 'CRISIS': 'Crisis mode', 'LOW_VOL': 'Calm market'}
    if data_missing:
        regime_display = 'Unknown'
        regime_col = MUTED
    else:
        regime_display = regime_labels.get(regime_str, regime_str.replace('_', ' ').title())
        regime_col = {'NORMAL': POS, 'LOW_VOL': POS, 'HIGH_VOL': '#d97706', 'CRISIS': NEG}.get(regime_str, MUTED)
    dd_col = {'NORMAL': POS, 'RAMPUP': '#d97706', 'HALT': NEG, 'PANIC': '#7c3aed'}.get(dd_str, MUTED)

    return (
        "<table style='width:100%;border-collapse:collapse;background:" + HDR + ";'><tr>"
        "<td style='padding:28px 30px 18px;'>"
        "<div style='font-size:12px;font-weight:700;letter-spacing:1.1px;color:#b7d4e6;"
        "margin-bottom:10px;text-transform:uppercase;'>Investor Mimic Bot</div>"
        "<div style='font-size:21px;font-weight:700;color:#f6fbff;margin-bottom:8px;'>Your Daily Portfolio Snapshot</div>"
        "<table style='width:100%;border-collapse:collapse;'><tr>"
        "<td style='vertical-align:bottom;'>"
        "<span style='font-size:36px;font-weight:700;color:#ffffff;font-family:" + MONO + ";'>"
        "${:,.2f}".format(pv) + "</span>"
        "<span style='font-size:16px;font-weight:600;margin-left:14px;color:" + pc + ";'>"
        + pnl_sign + "${:,.2f}".format(daily_pnl) + " (" + pnl_sign + "{:.2f}%".format(daily_pct) + ")</span>"
        "</td>"
        "<td style='vertical-align:bottom;text-align:right;color:#d7e8f2;font-size:13px;'>"
        + today + "</td>"
        "</tr></table>"
        "</td></tr><tr>"
        "<td style='padding:12px 30px;background:" + HDR_SUB + ";"
        "font-size:12px;color:" + TEXT2 + ";'>"
        "<table style='border-collapse:collapse;'><tr>"
        "<td style='padding:0 16px 0 0;'><span style='color:" + MUTED + ";'>Account:&nbsp;</span>" + recon_chip + "</td>"
        "<td style='padding:0 16px;'><span style='color:" + MUTED + ";'>Market:&nbsp;</span>" + chip(regime_display, regime_col) + "</td>"
        "<td style='padding:0 16px;'><span style='color:" + MUTED + ";'>Invested:&nbsp;</span>"
        "<span style='color:" + TEXT2 + ";'>{:.1f}%</span></td>".format(heat)
        + "<td style='padding:0 16px;'><span style='color:" + MUTED + ";'>Peak drop:&nbsp;</span>"
        "<span style='color:" + TEXT2 + ";'>{:.1f}%</span></td>".format(dd_pct)
        + "<td style='padding:0;'><span style='color:" + MUTED + ";'>Trades today:&nbsp;</span>"
        "<span style='color:" + TEXT2 + ";'>" + str(n_trades) + "</span></td>"
        "</tr></table>"
        "</td></tr></table>"
    )

# ── Summary bar ───────────────────────────────────────────────────────────────
def build_summary(pv, cash, pnl_30d, rows_30d):
    invested = pv - cash
    inv_pct = invested / pv * 100 if pv > 0 else 0

    def metric(label, val, col):
        return ("<td style='padding:18px 18px;border-right:1px solid " + BORDER + ";'>"
                "<div style='font-size:12px;font-weight:600;color:" + MUTED + ";margin-bottom:6px;'>" + label + "</div>"
                "<div style='font-size:22px;font-weight:700;color:" + col + ";font-family:" + MONO + ";'>"
                + val + "</div></td>")

    cells = (metric('Portfolio value', '${:,.2f}'.format(pv), TEXT)
           + metric('Cash available', '${:,.0f}'.format(cash), TEXT)
           + metric('Amount currently invested', '${:,.0f} ({:.1f}%)'.format(invested, inv_pct), TEXT2)
           + metric('30-day change', fmt_pnl(pnl_30d), pnl_col(pnl_30d)))

    spark_cell = ''
    if rows_30d and len(rows_30d) >= 2:
        vals = [r['total'] for r in rows_30d]
        s = sparkline(vals)
        d0 = rows_30d[0]['date']
        d1 = rows_30d[-1]['date']
        spark_cell = ("<td style='padding:16px 20px;'>"
                      "<div style='font-size:10px;font-weight:700;letter-spacing:1px;"
                      "text-transform:uppercase;color:" + MUTED + ";margin-bottom:6px;'>30-Day Trend</div>"
                      "<div style='font-family:" + MONO + ";font-size:16px;letter-spacing:1px;"
                      "color:" + ACCENT + ";'>" + s + "</div>"
                      "<div style='font-size:10px;color:" + MUTED + ";margin-top:3px;'>"
                      + d0 + " &rarr; " + d1 + "</div></td>")

    return ("<table style='width:100%;border-collapse:collapse;"
            "border:1px solid " + BORDER + ";background:" + WHITE + ";border-radius:12px;overflow:hidden;'>"
            "<tr>" + cells + spark_cell + "</tr></table>")

# ── Positions ──────────────────────────────────────────────────────────────────
def build_positions(positions):
    if not positions:
        return "<p style='color:" + MUTED + ";font-size:13px;font-style:italic;margin:0;'>No open positions.</p>"
    total_unr = sum(p.get('unrealized_pnl') or 0 for p in positions)
    rows = ''
    for i, p in enumerate(positions):
        bg    = WHITE if i % 2 == 0 else ROW_ALT
        entry = p.get('entry_price') or p.get('avg_price') or 0
        curr  = p.get('current_price') or entry
        unr   = p.get('unrealized_pnl') or 0
        upct  = (curr - entry) / entry * 100 if entry > 0 else 0
        stop  = p.get('stop_loss_price')
        dist  = (curr - stop) / curr * 100 if stop and curr > 0 else None
        stop_s = ('${:.2f}'.format(stop)
                  + ('<br><span style="font-size:10px;color:' + MUTED + ';">{:.1f}% away</span>'.format(dist) if dist else '')
                  ) if stop else '\u2014'
        upct_sign = '+' if upct >= 0 else ''
        rows += ("<tr style='background:" + bg + ";'>"
                 + td_s("<strong>" + (p.get('symbol') or '') + "</strong>")
                 + td_s(p.get('strat') or '', small=True, color=TEXT2)
                 + td_s("{:.0f}".format(p.get('shares') or 0), align='right', mono=True)
                 + td_s("${:.2f}".format(entry), align='right', mono=True)
                 + td_s("${:.2f}".format(curr), align='right', mono=True)
                 + td_s("<span style='color:" + pnl_col(unr) + ";font-weight:700;"
                        "font-family:" + MONO + ";'>" + fmt_pnl(unr)
                        + "<br><span style='font-size:10px;'>" + upct_sign + "{:.1f}%".format(upct) + "</span></span>",
                        align='right')
                 + td_s(stop_s, align='right', small=True)
                 + td_s(str(p.get('days') or '?') + "d", align='center', small=True, color=TEXT2)
                 + "</tr>")
    tc = pnl_col(total_unr)
    rows += ("<tr style='background:" + TH_BG + ";border-top:2px solid " + BORDER + ";'>"
             + td_s('<strong>Total unrealized</strong>', bold=True) + td_s('') + td_s('') + td_s('') + td_s('')
             + td_s("<strong style='color:" + tc + ";font-family:" + MONO + ";font-size:14px;'>"
                    + fmt_pnl(total_unr) + "</strong>", align='right')
             + td_s('') + td_s('') + "</tr>")
    return tbl(['Company','Strategy','Shares','We Paid','Price Now','Unrealized Gain / Loss','Safety Stop','Days Held'],
               rows, ['left','left','right','right','right','right','right','center'])

# ── Flowchart helpers ─────────────────────────────────────────────────────────

def _flow_box(label, icon, body_lines, bg, border_color, label_color):
    """Render one box in the news→signal→decision flowchart."""
    lines_html = ''.join(
        "<div style='font-size:12px;color:" + TEXT + ";line-height:1.5;margin-top:4px;'>"
        + html_lib.escape(str(ln)) + "</div>"
        for ln in body_lines if ln
    )
    return (
        "<td style='vertical-align:top;width:32%;background:" + bg + ";"
        "border:1px solid " + border_color + ";border-top:4px solid " + border_color + ";"
        "padding:13px 14px;border-radius:8px;'>"
        "<div style='font-size:10px;font-weight:700;letter-spacing:0.8px;"
        "text-transform:uppercase;color:" + label_color + ";margin-bottom:6px;'>"
        + icon + "&nbsp;" + label + "</div>"
        + lines_html
        + "</td>"
    )

def _flow_arrow():
    return ("<td style='vertical-align:middle;text-align:center;padding:0 6px;"
            "font-size:22px;color:#b08968;width:4%;'>&rarr;</td>")


def build_today_actions(today_trades, signal_map, news_map):
    """
    For every trade today, render a 3-box flowchart:
      [What the news said] → [What our system noticed] → [What we decided]
    All plain English — no jargon.
    """
    if not today_trades:
        return ("<p style='color:" + MUTED + ";font-size:13px;font-style:italic;margin:0;'>"
                "No trades today.</p>")

    sells   = [t for t in today_trades if t.get('action') == 'SELL']
    buys    = [t for t in today_trades if t.get('action') == 'BUY']
    total_r = sum(t.get('pnl', 0) or 0 for t in sells)

    summary_parts = []
    if buys:
        summary_parts.append("<strong>" + str(len(buys)) + "</strong> stock"
                             + ("s" if len(buys) != 1 else "") + " purchased")
    if sells:
        summary_parts.append("<strong>" + str(len(sells)) + "</strong> position"
                             + ("s" if len(sells) != 1 else "") + " closed")
    if sells and total_r != 0:
        col = POS if total_r >= 0 else NEG
        summary_parts.append("realized today: <strong style='color:" + col + ";'>"
                              + fmt_pnl(total_r) + "</strong>")

    cards = ("<div style='font-size:13px;color:" + TEXT2 + ";margin-bottom:16px;'>"
             + " &nbsp;&middot;&nbsp; ".join(summary_parts) + "</div>")

    for t in today_trades:
        sym    = t.get('symbol') or ''
        action = t.get('action') or ''
        strat  = t.get('strat')  or ''
        price  = t.get('exec_price') or 0
        shares = t.get('shares') or 0
        pnl    = t.get('pnl')
        ac     = POS if action == 'BUY' else NEG
        action_word = 'Bought' if action == 'BUY' else 'Sold'

        sig    = signal_map.get((sym, strat)) or {}
        raw_r  = sig.get('reasoning') or ''

        headlines  = news_map.get(sym) or []
        strat_lbl  = _strategy_label(strat)

        # P&L display
        if pnl is not None:
            pnl_disp = fmt_pnl(pnl)
            pnl_col_ = pnl_col(pnl)
        else:
            pnl_disp, pnl_col_ = 'Position still open', MUTED

        # Trade headline bar
        card = (
            "<div style='border:1px solid " + BORDER + ";border-left:4px solid " + ac + ";"
            "padding:15px 16px;margin-bottom:16px;background:" + WHITE + ";border-radius:10px;'>"
            "<table style='width:100%;border-collapse:collapse;margin-bottom:14px;'><tr>"
            "<td>"
            "<span style='font-size:16px;font-weight:700;color:" + TEXT + ";'>"
            + html_lib.escape(sym) + "</span>"
            "<span style='margin-left:10px;font-size:13px;font-weight:700;color:" + ac + ";'>"
            + action_word + " " + "{:.0f}".format(shares)
            + " share" + ("s" if shares != 1 else "")
            + " at ${:.2f}".format(price) + "</span>"
            "<br><span style='font-size:11px;color:" + MUTED + ";margin-top:3px;display:inline-block;'>"
            + html_lib.escape(strat_lbl) + "</span>"
            "</td>"
            "<td style='text-align:right;vertical-align:top;'>"
            "<span style='font-size:13px;font-weight:700;color:" + pnl_col_ + ";'>"
            + pnl_disp + "</span>"
            "</td>"
            "</tr></table>"
        )

        # ── 3-box flowchart ──────────────────────────────────────────────────
        card += "<table style='width:100%;border-collapse:separate;border-spacing:0;'><tr>"

        # Box 1 — NEWS
        if headlines:
            news_lines = headlines[:2]
            card += _flow_box(
                "What the news said", "&#128240;",
                news_lines,
                "#f0f4ff", ACCENT, ACCENT
            )
        else:
            card += _flow_box(
                "News today", "&#128240;",
                ["No major headlines found for this stock today."],
                TH_BG, BORDER, MUTED
            )

        card += _flow_arrow()

        # Box 2 — WHAT WE NOTICED
        if action == 'BUY':
            observed = _translate_buy_reason(raw_r, strat)
        else:
            observed = _translate_sell_reason(raw_r, strat)

        card += _flow_box(
            "What our system noticed", "&#128269;",
            [observed],
            "#fffbeb", "#d97706", "#92400e"
        )

        card += _flow_arrow()

        # Box 3 — DECISION
        if action == 'BUY':
            decision_lines = [
                action_word + " " + "{:.0f}".format(shares)
                + " share" + ("s" if shares != 1 else "") + " at ${:.2f}".format(price) + ".",
                "This position is now open and being monitored.",
            ]
            dec_bg, dec_border = "#f0fdf4", POS
            dec_label_col = POS
        else:
            result_line = ("Gained " + fmt_pnl(pnl) if pnl and pnl > 0
                           else "Lost " + fmt_pnl(abs(pnl)) if pnl and pnl < 0
                           else "Trade closed.")
            decision_lines = [
                action_word + " " + "{:.0f}".format(shares)
                + " share" + ("s" if shares != 1 else "") + " at ${:.2f}".format(price) + ".",
                result_line,
            ]
            dec_bg, dec_border = "#fff1f2", NEG
            dec_label_col = NEG

        card += _flow_box(
            "What we decided", "&#9989;" if action == 'BUY' else "&#128683;",
            decision_lines,
            dec_bg, dec_border, dec_label_col
        )

        card += "</tr></table></div>"
        cards += card

    return cards


def build_system_checks(guardrail_report):
    """Render latest operational guardrail status for the email."""
    if not guardrail_report:
        return ("<p style='color:" + MUTED + ";font-size:13px;font-style:italic;margin:0;'>"
                "Guardrail report not available for this run.</p>")

    critical = guardrail_report.get('critical_failures') or []
    warnings = guardrail_report.get('warnings') or []
    run_id = guardrail_report.get('latest_run_id') or 'unknown'
    status = 'PASS' if not critical else 'FAIL'
    status_col = POS if status == 'PASS' else NEG

    out = (
        "<div style='border:1px solid " + BORDER + ";border-left:4px solid " + status_col + ";"
        "padding:12px 14px;border-radius:8px;background:" + WHITE + ";'>"
        "<div style='font-size:13px;color:" + TEXT + ";font-weight:700;margin-bottom:8px;'>"
        "Run safety checks: <span style='color:" + status_col + ";'>" + status + "</span>"
        "</div>"
        "<div style='font-size:12px;color:" + TEXT2 + ";margin-bottom:8px;'>"
        "Run ID: " + html_lib.escape(str(run_id)) + " &middot; Canonical strategy set enforced (4 strategies)"
        "</div>"
    )

    if critical:
        out += "<ul style='margin:0;padding-left:18px;'>"
        for item in critical[:6]:
            out += ("<li style='font-size:12px;color:" + NEG + ";margin-bottom:4px;'>"
                    + html_lib.escape(str(item)) + "</li>")
        out += "</ul>"
    elif warnings:
        out += "<ul style='margin:0;padding-left:18px;'>"
        for item in warnings[:6]:
            out += ("<li style='font-size:12px;color:#b45309;margin-bottom:4px;'>"
                    + html_lib.escape(str(item)) + "</li>")
        out += "</ul>"
    else:
        out += ("<p style='font-size:12px;color:" + POS + ";margin:0;font-style:italic;'>"
                "No critical guardrail issues detected in the latest run.</p>")

    out += "</div>"
    return out

# ── Portfolio-level holistic metrics ─────────────────────────────────────────
def build_portfolio_metrics(db_path):
    """Render a top-line metrics bar: CAGR, Sharpe, win rate, max drawdown."""
    try:
        import sys as _sys
        from pathlib import Path as _Path
        _sys.path.insert(0, str(_Path(__file__).parent))
        from performance_tracker import compute_portfolio_metrics
        m = compute_portfolio_metrics(db_path)
    except Exception:
        return ''

    def _pct(v, d=1):
        return ("{:.{}f}%".format(v, d)) if v is not None else '—'

    def _f(v, d=2):
        return ("{:.{}f}".format(v, d)) if v is not None else '—'

    total_ret  = m.get('total_return_pct')
    cagr       = m.get('cagr')
    sharpe     = m.get('sharpe')
    win_rate   = m.get('win_rate')
    max_dd     = m.get('max_drawdown')
    pf         = m.get('profit_factor')
    n_trades   = m.get('total_trades') or 0
    since      = m.get('data_since') or ''
    days       = m.get('trading_days') or 0

    cagr_col  = POS if cagr and cagr > 0 else (NEG if cagr and cagr < 0 else MUTED)
    wr_col    = POS if win_rate and win_rate >= 0.5 else (NEG if win_rate and win_rate < 0.4 else MUTED)
    dd_col    = NEG if max_dd and max_dd > 5 else MUTED
    ret_col   = POS if total_ret and total_ret > 0 else (NEG if total_ret and total_ret < 0 else MUTED)

    def _kpi(label, val, color):
        return ("<div style='text-align:center;padding:12px 16px;'>"
                "<div style='font-size:19px;font-weight:700;font-family:" + MONO + ";color:"
                + color + ";'>" + val + "</div>"
                "<div style='font-size:11px;color:" + TEXT2 + ";margin-top:3px;'>" + label + "</div></div>")

    note = ''
    if days < 10:
        note = ("<div style='font-size:11px;color:" + MUTED + ";font-style:italic;"
                "margin-bottom:8px;'>Building track record — "
                + str(n_trades) + " trades across " + str(days) + " trading days since "
                + since + ".</div>")

    return (
        note
        + "<div style='display:flex;flex-wrap:wrap;background:" + TH_BG + ";border:1px solid "
        + BORDER + ";border-radius:12px;margin-bottom:16px;'>"
        + _kpi('Total growth', _pct(total_ret), ret_col)
        + _kpi('Estimated yearly pace', _pct((cagr or 0) * 100, 1), cagr_col)
        + _kpi('Consistency score', _f(sharpe), POS if sharpe and sharpe > 0.8 else MUTED)
        + _kpi('Trades that won', _pct((win_rate or 0) * 100, 0), wr_col)
        + _kpi('Largest pullback', _pct(max_dd), dd_col)
        + _kpi('Wins/losses balance', _f(pf), POS if pf and pf > 1.0 else NEG)
        + _kpi('Closed trades', str(n_trades), MUTED)
        + "</div>"
    )


# ── Overall strategy performance (all-time) ────────────────────────────────────
def build_all_time_perf(rows):
    if not rows:
        return ("<p style='color:" + MUTED + ";font-size:13px;font-style:italic;margin:0;'>"
                "No trade history yet.</p>")
    trows = ''
    for i, r in enumerate(rows):
        bg    = WHITE if i % 2 == 0 else ROW_ALT
        tot   = r.get('total_trades') or 0
        wins  = r.get('wins') or 0
        pnl   = r.get('total_pnl') or 0
        best  = r.get('best_trade')
        worst = r.get('worst_trade')
        aw    = r.get('avg_win')
        al    = r.get('avg_loss')
        since = (r.get('first_trade') or '')[:10] or '\u2014'
        wr    = "{:.0f}%".format(wins / tot * 100) if tot > 0 else '\u2014'
        pf    = (abs(aw * wins) / abs(al * (tot - wins))
                 if al and al != 0 and (tot - wins) > 0 and aw else None)
        pf_s  = "{:.2f}".format(pf) if pf else '\u2014'
        trows += ("<tr style='background:" + bg + ";'>"
                  + td_s("<strong>" + html_lib.escape(r.get('name') or '') + "</strong>")
                  + td_s(str(tot), align='center', color=TEXT2)
                  + td_s(wr, align='center',
                         color=(POS if wins / tot >= 0.5 else NEG) if tot > 0 else MUTED)
                  + td_s("<span style='color:" + pnl_col(pnl) + ";font-weight:700;font-family:"
                         + MONO + ";'>" + fmt_pnl(pnl) + "</span>", align='right')
                  + td_s(pf_s, align='center', color=TEXT2)
                  + td_s(fmt_pnl(best) if best is not None else '\u2014',
                         align='right', color=POS, small=True)
                  + td_s(fmt_pnl(worst) if worst is not None else '\u2014',
                         align='right', color=NEG, small=True)
                  + td_s(since, align='center', small=True, color=MUTED)
                  + "</tr>")
    return tbl(
        ['Strategy', 'Closed Trades', 'Win Rate', 'Net Profit / Loss', 'Wins vs Losses',
         'Best Trade', 'Worst Trade', 'Started'],
        trows,
        ['left', 'center', 'center', 'right', 'center', 'right', 'right', 'center'])

# ── Strategy-by-strategy concerns ─────────────────────────────────────────────
def build_strategy_concerns(health_data, rejection_rows, recent_rows):
    min_trade_sample = 10
    # Index rejections and recent perf by strategy name
    rej_by_strat = {}
    for r in (rejection_rows or []):
        rej_by_strat.setdefault(r['strat'], []).append(r)
    recent_by_strat = {r['strat']: r for r in (recent_rows or [])}

    strategies = []
    if health_data:
        strategies = health_data.get('strategies', [])

    # Always include all 4 canonical strategies so the section is never blank
    strat_names = list(
        {s.get('strategy_name') for s in strategies}
        | set(rej_by_strat.keys())
        | set(recent_by_strat.keys())
        | set(_CANONICAL_STRATEGIES)
    )
    strat_names = [n for n in strat_names if n in _CANONICAL_STRATEGIES]

    cards = ''
    for name in sorted(strat_names):
        # Health scorer data
        hs = next((s for s in strategies if s.get('strategy_name') == name), {})
        score    = hs.get('health_score', None)
        status   = hs.get('health_status', 'UNKNOWN')
        issues   = hs.get('issues', [])
        sc_col   = POS if status == 'HEALTHY' else ('#d97706' if status == 'WARNING' else NEG)

        # Recent 30-day performance
        rec = recent_by_strat.get(name, {})
        r_trades = rec.get('trades') or 0
        r_wins   = rec.get('wins') or 0
        r_pnl    = rec.get('pnl') or 0
        r_wr     = "{:.0f}%".format(r_wins / r_trades * 100) if r_trades > 0 else 'n/a'
        wr_col   = (POS if r_trades > 0 and r_wins / r_trades >= 0.5 else
                    NEG if r_trades > 0 else MUTED)

        # Top rejections for this strategy
        top_rej = sorted(rej_by_strat.get(name, []),
                         key=lambda x: x.get('cnt', 0), reverse=True)[:3]

        concern_items = list(issues[:4])
        if r_pnl < 0:
            concern_items.append("Lost money over the last 30 days ({})".format(fmt_pnl(r_pnl)))
        if 0 < r_trades < min_trade_sample:
            concern_items.append(
                "Only {} closed trade{} in the last 30 days — performance sample is too small for a strong conclusion".format(
                    r_trades,
                    's' if r_trades != 1 else '',
                )
            )
        elif r_trades >= min_trade_sample and r_wins / r_trades < 0.4 and r_pnl <= 0:
            concern_items.append("Only {} of recent trades were profitable — this strategy is underperforming".format(r_wr))
        for rej in top_rej:
            cnt = rej.get('cnt', 0)
            reason = _translate_rejection(rej.get('stage', ''), rej.get('reason_code', ''))
            concern_items.append("{} — blocked {} time{}".format(reason, cnt, 's' if cnt != 1 else ''))

        border_col = sc_col if score is not None else MUTED
        card = ("<div style='border:1px solid " + BORDER + ";border-left:3px solid "
                + border_col + ";padding:14px 16px;margin-bottom:10px;background:" + WHITE + ";'>"
                "<table style='width:100%;border-collapse:collapse;margin-bottom:8px;'><tr>"
                "<td><span style='font-size:13px;font-weight:700;color:" + TEXT + ";'>"
                + html_lib.escape(name) + "</span>")
        if score is not None:
            card += ("<span style='margin-left:12px;font-size:11px;font-weight:700;color:"
                     + sc_col + ";'>" + str(score) + "/100</span>"
                     + "<span style='margin-left:8px;'>" + chip(status, sc_col) + "</span>")
        card += ("</td>"
                 "<td style='text-align:right;font-size:11px;color:" + TEXT2 + ";'>"
                 "Last 30 days: <span style='color:" + wr_col + ";font-weight:700;'>" + r_wr + "</span>"
                 " win rate &nbsp;&middot;&nbsp; "
                 "<span style='color:" + pnl_col(r_pnl) + ";font-weight:700;font-family:"
                 + MONO + ";'>" + fmt_pnl(r_pnl) + "</span>"
                 "</td></tr></table>")

        if concern_items:
            translated = [_translate_rejection('', i) if i.startswith('Rejected by') else i
                          for i in concern_items]
            card += "<ul style='margin:0;padding-left:18px;'>"
            for item in translated:
                card += ("<li style='font-size:12px;color:" + TEXT2 + ";margin-bottom:4px;'>"
                         + html_lib.escape(str(item)) + "</li>")
            card += "</ul>"
        else:
            card += ("<p style='font-size:12px;color:" + POS + ";margin:0;font-style:italic;'>"
                     "Everything looks healthy &mdash; no concerns right now.</p>")

        card += "</div>"
        cards += card

    return cards

# ── Main ───────────────────────────────────────────────────────────────────────
def generate_email_body(artifact_path=None, db_path='trading.db', include_visuals=False):
    db = _conn(db_path)
    snap, dd, regime        = get_snapshot(db)
    rows_30d                = get_30d(db)
    all_time_perf           = get_all_time_perf(db)
    positions               = get_positions(db)
    today_trades            = get_today_trades(db)
    signal_map              = get_today_signals_for_trades(db)
    rej_rows, recent_rows   = get_strategy_concerns_data(db)
    db.close()

    data_missing = not snap or 'portfolio_value' not in snap
    pv    = snap.get('portfolio_value') if not data_missing else 0
    cash  = snap.get('cash') if not data_missing else 0
    recon = snap.get('reconciliation_status') or 'UNKNOWN'

    daily_pnl = daily_pct = pnl_30d = 0.0
    if len(rows_30d) >= 2:
        prev, curr = rows_30d[-2]['total'], rows_30d[-1]['total']
        daily_pnl = curr - prev
        daily_pct = (curr / prev - 1) * 100 if prev > 0 else 0
        pnl_30d   = rows_30d[-1]['total'] - rows_30d[0]['total']

    # Fetch news for every symbol traded today (best-effort, never blocks)
    traded_symbols = list({t.get('symbol') for t in today_trades if t.get('symbol')})
    news_map = fetch_symbol_news(traded_symbols)

    header      = build_header(pv, cash, daily_pnl, daily_pct, dd, regime, recon, len(today_trades), data_missing=data_missing)
    summary     = build_summary(pv, cash, pnl_30d, rows_30d)
    if data_missing:
        summary = (
            "<div style='margin:12px 0;padding:12px 14px;border:1px solid #b45309;"
            "background:#fffbeb;color:#92400e;border-radius:10px;font-size:12px;'>"
            "⚠️ Missing broker_state snapshot data for this run. The daily workflow did not "
            "populate trading.db, so portfolio metrics are placeholders. Please check the "
            "Daily Trading Execution logs for database initialization errors or missing artifacts." 
            "</div>"
        ) + summary
    health_data = get_health()
    guardrails  = get_guardrail_report()

    # Build optional inline chart block (Mon/Wed/Fri via --include-visuals)
    chart_section = ""
    if include_visuals:
        try:
            import sys as _sys
            from pathlib import Path as _Path
            _sys.path.insert(0, str(_Path(__file__).parent))
            from generate_email_chart import generate_performance_chart
            b64 = generate_performance_chart(db_path=db_path, days=30)
            if b64:
                chart_section = (
                    "<div style='margin:16px 0;'>"
                    "<div style='font-size:10px;font-weight:700;letter-spacing:0.8px;"
                    "text-transform:uppercase;color:" + MUTED + ";margin-bottom:6px;'>"
                    "30-Day P&amp;L Curve</div>"
                    "<img src='data:image/png;base64," + b64 + "' "
                    "style='width:100%;max-width:860px;border:1px solid " + BORDER + ";'>"
                    "</div>\n"
                )
        except Exception:
            pass  # chart unavailable — email still sends without it

    body_sections = (
        "    <div style='margin-bottom:20px;'>" + summary + chart_section + "</div>\n"
        + section("Your Current Investments",
                  build_positions(positions),
                  str(len(positions)) + " open position" + ("s" if len(positions) != 1 else ""))
        + section("Today's Activity",
                  build_today_actions(today_trades, signal_map, news_map),
                  str(len(today_trades)) + " trade" + ("s" if len(today_trades) != 1 else "") + " today")
        + section("How Your Portfolio Has Performed",
                  build_portfolio_metrics(db_path) + build_all_time_perf(all_time_perf),
                  "results so far")
        + section("System Health Checks",
                  build_system_checks(guardrails),
                  "latest run")
        + section("What Needs Attention",
                  build_strategy_concerns(health_data, rej_rows, recent_rows),
                  "last 30 days")
        + "    <div style='padding-top:20px;border-top:1px solid " + BORDER + ";"
          "font-size:11px;color:" + MUTED + ";text-align:center;'>"
          "Investor Mimic Bot &middot; Generated "
          + datetime.now().strftime('%Y-%m-%d %H:%M') + "</div>\n"
    )

    return ("<!DOCTYPE html>\n<html>\n"
            "<head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'></head>\n"
            "<body style='font-family:" + FONT_UI + ";background:" + BG + ";margin:0;padding:22px 12px;line-height:1.6;'>\n"
            "<div style='max-width:920px;margin:0 auto;background:" + WHITE + ";border:1px solid " + BORDER + ";border-radius:14px;overflow:hidden;box-shadow:0 8px 26px rgba(88,72,48,0.08);'>\n"
            + header + "\n"
            "<div style='padding:28px 30px;background:" + WHITE + ";'>\n"
            + body_sections
            + "</div>\n</div>\n</body>\n</html>")

# ── CLI ────────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    import argparse
    from dotenv import load_dotenv
    load_dotenv()

    p = argparse.ArgumentParser()
    p.add_argument('--include-visuals', action='store_true')
    p.add_argument('--send', action='store_true')
    args = p.parse_args()

    date_str = datetime.now().strftime('%Y-%m-%d')
    html = generate_email_body(db_path='trading.db', include_visuals=args.include_visuals)

    out = '/tmp/daily_email.html'
    with open(out, 'w') as f:
        f.write(html)
    print("✅ Email HTML generated: " + out)

    if args.send:
        from src.utils.email_notifier import EmailNotifier
        notifier = EmailNotifier()
        if not notifier.enabled:
            print("❌ Email disabled — set SENDER_EMAIL, SENDER_PASSWORD, RECIPIENT_EMAIL in .env")
        else:
            try:
                notifier._send_email("📊 Trading Digest \u2014 " + date_str, html, is_html=True)
                print("✅ Email sent!")
            except Exception as e:
                print("❌ Send failed: " + str(e))
    import sys; sys.exit(0)
