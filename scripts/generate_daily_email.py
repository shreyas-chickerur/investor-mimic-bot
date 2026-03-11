#!/usr/bin/env python3
"""
Generate Daily Email Digest v3 — professional, minimal, data-dense.
No gradients. No emoji headers. Signal reasoning flowchart from DB.
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
BG      = '#f4f5f7'
WHITE   = '#ffffff'
HDR     = '#0d1117'
HDR_SUB = '#161b22'
ACCENT  = '#2563eb'
POS     = '#15803d'
NEG     = '#dc2626'
MUTED   = '#6b7280'
BORDER  = '#e2e8f0'
ROW_ALT = '#fafafa'
TH_BG   = '#f1f3f5'
TEXT    = '#0f172a'
TEXT2   = '#475569'
MONO    = '"SFMono-Regular",Consolas,monospace'

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

def get_all_time_perf(db):
    return q(db, """
        SELECT s.name,
          COUNT(t.id)                                          total_trades,
          SUM(CASE WHEN t.pnl > 0 THEN 1 ELSE 0 END)         wins,
          SUM(CASE WHEN t.pnl <= 0 THEN 1 ELSE 0 END)        losses,
          SUM(COALESCE(t.pnl, 0))                             total_pnl,
          MAX(t.pnl)                                          best_trade,
          MIN(t.pnl)                                          worst_trade,
          AVG(CASE WHEN t.pnl > 0 THEN t.pnl END)            avg_win,
          AVG(CASE WHEN t.pnl <= 0 THEN t.pnl END)           avg_loss,
          MIN(DATE(t.executed_at))                            first_trade
        FROM trades t JOIN strategies s ON t.strategy_id=s.id
        WHERE t.pnl IS NOT NULL AND s.name != 'BROKER_SYNC'
        GROUP BY s.name ORDER BY total_pnl DESC""")

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
    """Fetch top 2 news headlines per symbol via yfinance. Returns {symbol: [headline, ...]}"""
    news_map = {}
    if not symbols:
        return news_map
    try:
        import yfinance as yf
    except Exception:
        return news_map
    for sym in symbols:
        try:
            ticker = yf.Ticker(sym)
            items = ticker.news or []
            headlines = []
            for item in items[:3]:
                title = (item.get('content', {}).get('title') or
                         item.get('title') or '')
                if title:
                    headlines.append(title[:90])
                if len(headlines) >= 2:
                    break
            if headlines:
                news_map[sym] = headlines
        except Exception:
            pass
    return news_map

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
            "font-size:10px;font-weight:700;letter-spacing:0.5px;"
            "padding:2px 7px;border-radius:2px;text-transform:uppercase;'>"
            + label + "</span>")

# ── Layout helpers ────────────────────────────────────────────────────────────
def section(title, body, note=''):
    note_html = ''
    if note:
        note_html = ("<span style='font-size:11px;color:" + MUTED + ";font-weight:400;"
                     "margin-left:10px;'>" + note + "</span>")
    return ("  <div style='margin-bottom:28px;'>\n"
            "    <div style='font-size:10px;font-weight:700;letter-spacing:1.5px;"
            "text-transform:uppercase;color:" + TEXT2 + ";"
            "border-bottom:1px solid " + BORDER + ";padding-bottom:7px;"
            "margin-bottom:14px;'>" + title + note_html + "</div>\n"
            "    " + body + "\n"
            "  </div>\n")

def th(label, align='left'):
    return ("<th style='padding:8px 12px;text-align:" + align + ";font-size:10px;"
            "font-weight:700;letter-spacing:0.8px;text-transform:uppercase;"
            "color:" + TEXT2 + ";background:" + TH_BG + ";"
            "border-bottom:2px solid " + BORDER + ";'>" + label + "</th>")

def tbl(headers, rows_html, aligns=None):
    ths = ''.join(th(h, (aligns[i] if aligns else 'left')) for i, h in enumerate(headers))
    return ("<table style='width:100%;border-collapse:collapse;font-size:12.5px;'>"
            "<thead><tr>" + ths + "</tr></thead>"
            "<tbody>" + rows_html + "</tbody></table>")

def td_s(val, align='left', bold=False, color=None, mono=False, small=False):
    s = "padding:8px 12px;text-align:" + align + ";border-bottom:1px solid " + BORDER + ";vertical-align:middle;"
    if bold:  s += "font-weight:700;"
    if color: s += "color:" + color + ";"
    if mono:  s += "font-family:" + MONO + ";"
    if small: s += "font-size:11px;"
    return "<td style='" + s + "'>" + str(val) + "</td>"

# ── Header ────────────────────────────────────────────────────────────────────
def build_header(pv, cash, daily_pnl, daily_pct, dd, regime, recon, n_trades):
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
    recon_chip = chip('SYNCED' if recon_ok else 'DRIFT', POS if recon_ok else NEG)

    regime_col = {
        'NORMAL': POS, 'HIGH_VOL': '#d97706', 'CRISIS': NEG
    }.get(regime_str, MUTED)
    dd_col = {'NORMAL': POS, 'RAMPUP': '#d97706', 'HALT': NEG, 'PANIC': '#7c3aed'}.get(dd_str, MUTED)

    return (
        "<table style='width:100%;border-collapse:collapse;background:" + HDR + ";'><tr>"
        "<td style='padding:22px 28px 18px;'>"
        "<div style='font-size:10px;font-weight:700;letter-spacing:2px;color:#6b7280;"
        "margin-bottom:10px;text-transform:uppercase;'>Investor Mimic Bot &mdash; Daily Report</div>"
        "<table style='width:100%;border-collapse:collapse;'><tr>"
        "<td style='vertical-align:bottom;'>"
        "<span style='font-size:30px;font-weight:700;color:#f9fafb;font-family:" + MONO + ";'>"
        "${:,.2f}".format(pv) + "</span>"
        "<span style='font-size:14px;font-weight:600;margin-left:14px;color:" + pc + ";'>"
        + pnl_sign + "${:,.2f}".format(daily_pnl) + "&nbsp;&nbsp;"
        + pnl_sign + "{:.2f}%".format(daily_pct) + "</span>"
        "</td>"
        "<td style='vertical-align:bottom;text-align:right;color:#9ca3af;font-size:12px;'>"
        + today + "</td>"
        "</tr></table>"
        "</td></tr><tr>"
        "<td style='padding:9px 28px;background:" + HDR_SUB + ";border-top:1px solid #1f2937;"
        "font-size:11px;color:#9ca3af;'>"
        "<table style='border-collapse:collapse;'><tr>"
        "<td style='padding:0 16px 0 0;'><span style='color:#6b7280;'>Reconciliation&nbsp;</span>" + recon_chip + "</td>"
        "<td style='padding:0 16px;'><span style='color:#6b7280;'>Regime&nbsp;</span>" + chip(regime_str, regime_col) + "</td>"
        "<td style='padding:0 16px;'><span style='color:#6b7280;'>VIX proxy&nbsp;</span>"
        "<span style='color:#d1d5db;'>" + str(vix) + "</span></td>"
        "<td style='padding:0 16px;'><span style='color:#6b7280;'>Drawdown&nbsp;</span>"
        + chip(dd_str, dd_col)
        + "<span style='color:#6b7280;'>&nbsp;{:.1f}%</span></td>".format(dd_pct)
        + "<td style='padding:0 16px;'><span style='color:#6b7280;'>Heat&nbsp;</span>"
        "<span style='color:#d1d5db;'>{:.1f}%</span></td>".format(heat)
        + "<td style='padding:0;'><span style='color:#6b7280;'>Trades today&nbsp;</span>"
        "<span style='color:#d1d5db;'>" + str(n_trades) + "</span></td>"
        "</tr></table>"
        "</td></tr></table>"
    )

# ── Summary bar ───────────────────────────────────────────────────────────────
def build_summary(pv, cash, pnl_30d, rows_30d):
    invested = pv - cash
    inv_pct = invested / pv * 100 if pv > 0 else 0

    def metric(label, val, col):
        return ("<td style='padding:16px 20px;border-right:1px solid " + BORDER + ";'>"
                "<div style='font-size:10px;font-weight:700;letter-spacing:1px;"
                "text-transform:uppercase;color:" + MUTED + ";margin-bottom:6px;'>" + label + "</div>"
                "<div style='font-size:20px;font-weight:700;color:" + col + ";font-family:" + MONO + ";'>"
                + val + "</div></td>")

    cells = (metric('Portfolio Value', '${:,.2f}'.format(pv), TEXT)
           + metric('Cash Available',  '${:,.0f}'.format(cash), TEXT)
           + metric('Invested',        '${:,.0f} ({:.1f}%)'.format(invested, inv_pct), TEXT2)
           + metric('30-Day P&L',      fmt_pnl(pnl_30d), pnl_col(pnl_30d)))

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
            "border:1px solid " + BORDER + ";background:" + WHITE + ";'>"
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
    return tbl(['Symbol','Strategy','Shares','Entry','Current','Unrealized P&L','Stop Price','Held'],
               rows, ['left','left','right','right','right','right','right','center'])

# ── Today's Actions (trade table + news-driven reasoning flowchart) ────────────
def _arrow():
    return "<span style='color:" + MUTED + ";margin:0 5px;font-size:13px;'>&#x2192;</span>"

def _node_pill(text, bg=None, color=None, bold=False):
    bg    = bg    or TH_BG
    color = color or TEXT
    fw    = 'font-weight:700;' if bold else ''
    return ("<span style='display:inline-block;background:" + bg + ";"
            "border:1px solid " + BORDER + ";padding:3px 9px;border-radius:2px;"
            "font-size:11px;color:" + color + ";font-family:" + MONO + ";" + fw + "'>"
            + html_lib.escape(str(text)) + "</span>")

def build_today_actions(today_trades, signal_map, news_map):
    if not today_trades:
        return ("<p style='color:" + MUTED + ";font-size:13px;font-style:italic;margin:0;'>"
                "No trades executed today.</p>")

    sells   = [t for t in today_trades if t.get('action') == 'SELL']
    total_r = sum(t.get('pnl', 0) or 0 for t in sells)
    buys_n  = len([t for t in today_trades if t.get('action') == 'BUY'])
    note    = (str(buys_n) + " buys &middot; " + str(len(sells)) + " sells")
    if sells:
        note += (" &middot; realized today: <strong style='color:" + pnl_col(total_r) + ";'>"
                 + fmt_pnl(total_r) + "</strong>")

    cards = "<div style='font-size:11px;color:" + TEXT2 + ";margin-bottom:12px;'>" + note + "</div>"

    for t in today_trades:
        sym    = t.get('symbol') or ''
        action = t.get('action') or ''
        strat  = t.get('strat')  or ''
        price  = t.get('exec_price') or 0
        shares = t.get('shares') or 0
        pnl    = t.get('pnl')
        ac     = POS if action == 'BUY' else NEG

        sig        = signal_map.get((sym, strat)) or {}
        conf       = sig.get('confidence') or 0
        raw_r      = sig.get('reasoning') or ''
        tech_steps = [s.strip() for s in raw_r.replace(';', ',').split(',') if s.strip()]

        headlines = news_map.get(sym) or []

        pnl_s = ("<span style='color:" + pnl_col(pnl) + ";font-weight:700;'>"
                 + fmt_pnl(pnl) + "</span>") if pnl is not None else (
                 "<span style='color:" + MUTED + ";'>open</span>")

        # ── card header ──
        card = ("<div style='border:1px solid " + BORDER + ";border-left:3px solid " + ac + ";"
                "padding:14px 16px;margin-bottom:10px;background:" + WHITE + ";'>"
                # trade headline row
                "<table style='width:100%;border-collapse:collapse;margin-bottom:10px;'><tr>"
                "<td><span style='font-size:14px;font-weight:700;color:" + TEXT + ";'>"
                + html_lib.escape(sym) + "</span>"
                "<span style='margin-left:10px;font-size:12px;font-weight:700;color:" + ac + ";'>"
                + action + "</span>"
                "<span style='margin-left:10px;font-size:12px;color:" + TEXT2 + ";'>"
                + "{:.0f} sh @ ${:.2f}".format(shares, price) + "</span>"
                "<span style='margin-left:10px;font-size:11px;color:" + MUTED + ";'>"
                + html_lib.escape(strat) + "</span></td>"
                "<td style='text-align:right;'>" + pnl_s + "</td>"
                "</tr></table>")

        # ── news context row ──
        if headlines:
            card += ("<div style='background:#f0f4ff;border-left:2px solid " + ACCENT + ";"
                     "padding:7px 10px;margin-bottom:10px;border-radius:0 2px 2px 0;'>"
                     "<span style='font-size:10px;font-weight:700;letter-spacing:0.8px;"
                     "text-transform:uppercase;color:" + ACCENT + ";'>Market Context</span><br>")
            for h in headlines:
                card += ("<span style='font-size:11px;color:" + TEXT2 + ";'>"
                         + html_lib.escape(h) + "</span><br>")
            card += "</div>"

        # ── flowchart row ──
        card += "<div style='line-height:2.2;flex-wrap:wrap;'>"
        if tech_steps:
            for idx, step in enumerate(tech_steps):
                card += _node_pill(step)
                card += _arrow()
        elif raw_r:
            card += _node_pill(raw_r[:70])
            card += _arrow()
        else:
            card += _node_pill("Signal generated")
            card += _arrow()

        if conf:
            card += _node_pill("conf {:.2f}".format(conf), bg='#f0fdf4', color=POS)
            card += _arrow()

        card += _node_pill("EXECUTED " + action, bg=ac, color='#fff', bold=True)
        card += "</div></div>"
        cards += card

    return cards

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
        return ("<div style='text-align:center;padding:10px 16px;'>"
                "<div style='font-size:18px;font-weight:700;font-family:" + MONO + ";color:"
                + color + ";'>" + val + "</div>"
                "<div style='font-size:10px;color:" + TEXT2 + ";margin-top:3px;"
                "text-transform:uppercase;letter-spacing:0.6px;'>" + label + "</div></div>")

    note = ''
    if days < 10:
        note = ("<div style='font-size:11px;color:" + MUTED + ";font-style:italic;"
                "margin-bottom:8px;'>Building track record — "
                + str(n_trades) + " trades across " + str(days) + " trading days since "
                + since + ".</div>")

    return (
        note
        + "<div style='display:flex;flex-wrap:wrap;background:" + TH_BG + ";border:1px solid "
        + BORDER + ";border-radius:4px;margin-bottom:16px;'>"
        + _kpi('Total Return', _pct(total_ret), ret_col)
        + _kpi('CAGR (ann.)', _pct((cagr or 0) * 100, 1), cagr_col)
        + _kpi('Sharpe', _f(sharpe), POS if sharpe and sharpe > 0.8 else MUTED)
        + _kpi('Win Rate', _pct((win_rate or 0) * 100, 0), wr_col)
        + _kpi('Max DD', _pct(max_dd), dd_col)
        + _kpi('Profit Factor', _f(pf), POS if pf and pf > 1.0 else NEG)
        + _kpi('Trades', str(n_trades), MUTED)
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
        ['Strategy', 'Trades', 'Win %', 'Total P&L', 'Profit Factor',
         'Best Trade', 'Worst Trade', 'Since'],
        trows,
        ['left', 'center', 'center', 'right', 'center', 'right', 'right', 'center'])

# ── Strategy-by-strategy concerns ─────────────────────────────────────────────
def build_strategy_concerns(health_data, rejection_rows, recent_rows):
    # Index rejections and recent perf by strategy name
    rej_by_strat = {}
    for r in (rejection_rows or []):
        rej_by_strat.setdefault(r['strat'], []).append(r)
    recent_by_strat = {r['strat']: r for r in (recent_rows or [])}

    strategies = []
    if health_data:
        strategies = health_data.get('strategies', [])

    # If no health data, build minimal cards from DB data alone
    if not strategies and not rej_by_strat and not recent_by_strat:
        return ("<p style='color:" + MUTED + ";font-size:13px;font-style:italic;margin:0;'>"
                "No concern data available.</p>")

    strat_names = list({s.get('strategy_name') for s in strategies} |
                       set(rej_by_strat.keys()) | set(recent_by_strat.keys()))

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
            concern_items.append("30d P&L negative ({})".format(fmt_pnl(r_pnl)))
        if r_trades > 0 and r_wins / r_trades < 0.4:
            concern_items.append("Win rate below 40% (30d: {})".format(r_wr))
        for rej in top_rej:
            concern_items.append("Rejected by {} — {} ({} times)".format(
                rej.get('stage', ''), rej.get('reason_code', ''), rej.get('cnt', 0)))

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
                 "30d: <span style='color:" + wr_col + ";font-weight:700;'>" + r_wr + "</span>"
                 " win rate &middot; "
                 "<span style='color:" + pnl_col(r_pnl) + ";font-weight:700;font-family:"
                 + MONO + ";'>" + fmt_pnl(r_pnl) + "</span>"
                 "</td></tr></table>")

        if concern_items:
            card += "<ul style='margin:0;padding-left:18px;'>"
            for item in concern_items:
                card += ("<li style='font-size:11px;color:" + TEXT2 + ";margin-bottom:3px;'>"
                         + html_lib.escape(str(item)) + "</li>")
            card += "</ul>"
        else:
            card += ("<p style='font-size:11px;color:" + POS + ";margin:0;font-style:italic;'>"
                     "No active concerns.</p>")

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

    pv    = snap.get('portfolio_value') or 100_000
    cash  = snap.get('cash') or 0
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

    header      = build_header(pv, cash, daily_pnl, daily_pct, dd, regime, recon, len(today_trades))
    summary     = build_summary(pv, cash, pnl_30d, rows_30d)
    health_data = get_health()

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
        + section("Open Positions",
                  build_positions(positions),
                  str(len(positions)) + " active")
        + section("Today's Actions",
                  build_today_actions(today_trades, signal_map, news_map),
                  str(len(today_trades)) + " executed")
        + section("Strategy Performance",
                  build_portfolio_metrics(db_path) + build_all_time_perf(all_time_perf),
                  "all-time")
        + section("Strategy Concerns",
                  build_strategy_concerns(health_data, rej_rows, recent_rows),
                  "30-day window")
        + "    <div style='padding-top:20px;border-top:1px solid " + BORDER + ";"
          "font-size:11px;color:" + MUTED + ";text-align:center;'>"
          "Investor Mimic Bot &middot; Generated "
          + datetime.now().strftime('%Y-%m-%d %H:%M') + "</div>\n"
    )

    return ("<!DOCTYPE html>\n<html>\n"
            "<head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'></head>\n"
            "<body style='font-family:-apple-system,BlinkMacSystemFont,\"Segoe UI\",Roboto,"
            "\"Helvetica Neue\",Arial,sans-serif;background:" + BG + ";margin:0;padding:0;'>\n"
            "<div style='max-width:900px;margin:0 auto;'>\n"
            + header + "\n"
            "<div style='padding:24px 28px;background:" + BG + ";'>\n"
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
