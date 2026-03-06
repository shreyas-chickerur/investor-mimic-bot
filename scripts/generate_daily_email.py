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
    return q(db, "SELECT date, SUM(portfolio_value) AS total "
                 "FROM strategy_performance WHERE date >= date('now','-30 days') "
                 "GROUP BY date ORDER BY date")

def get_strategy_perf(db):
    return q(db, """
        SELECT s.name,
          COUNT(CASE WHEN t.executed_at >= date('now','-7 days') THEN 1 END) t7,
          SUM(CASE WHEN t.executed_at>=date('now','-7 days') AND t.pnl>0 THEN 1 ELSE 0 END) w7,
          SUM(CASE WHEN t.executed_at>=date('now','-7 days') THEN COALESCE(t.pnl,0) ELSE 0 END) p7,
          COUNT(CASE WHEN t.executed_at >= date('now','-30 days') THEN 1 END) t30,
          SUM(CASE WHEN t.executed_at>=date('now','-30 days') AND t.pnl>0 THEN 1 ELSE 0 END) w30,
          SUM(CASE WHEN t.executed_at>=date('now','-30 days') THEN COALESCE(t.pnl,0) ELSE 0 END) p30
        FROM trades t JOIN strategies s ON t.strategy_id=s.id
        WHERE t.pnl IS NOT NULL GROUP BY s.name ORDER BY p30 DESC""")

def get_positions(db):
    return q(db, """
        SELECT p.symbol, s.name strat, p.shares, p.avg_price, p.current_price,
               p.unrealized_pnl, p.entry_date, p.entry_price, p.stop_loss_price,
               CAST(julianday('now') - julianday(COALESCE(p.entry_date, date('now'))) AS INTEGER) days
        FROM positions p JOIN strategies s ON p.strategy_id=s.id
        WHERE p.shares > 0 ORDER BY p.unrealized_pnl DESC""")

def get_today_trades(db):
    return q(db, """
        SELECT t.symbol, t.action, t.shares, t.exec_price,
               t.notional, t.pnl, s.name strat, t.executed_at
        FROM trades t JOIN strategies s ON t.strategy_id=s.id
        WHERE DATE(t.executed_at)=DATE('now') ORDER BY t.executed_at""")

def get_signal_reasoning(db):
    return q(db, """
        SELECT sg.symbol, sg.signal_type, sg.confidence, sg.reasoning,
               sg.terminal_state, sg.terminal_reason, sg.asof_date, s.name strat
        FROM signals sg JOIN strategies s ON sg.strategy_id=s.id
        WHERE sg.asof_date >= date('now','-7 days')
          AND sg.reasoning IS NOT NULL AND sg.reasoning != ''
        ORDER BY sg.generated_at DESC LIMIT 20""")

def get_funnel(db):
    return q(db, """
        SELECT strategy_name, raw_signals_count, after_regime_count,
               after_correlation_count, after_risk_count, executed_count
        FROM signal_funnel WHERE DATE(created_at)=DATE('now')
        ORDER BY executed_count DESC""")

def get_rejections(db):
    return q(db, """
        SELECT stage, reason_code, COUNT(*) cnt
        FROM signal_rejections WHERE DATE(created_at)=DATE('now')
        GROUP BY stage, reason_code ORDER BY cnt DESC LIMIT 8""")

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

# ── Trades ─────────────────────────────────────────────────────────────────────
def build_trades(trades):
    if not trades:
        return "<p style='color:" + MUTED + ";font-size:13px;font-style:italic;margin:0;'>No trades executed today.</p>"
    sells = [t for t in trades if t.get('action') == 'SELL']
    total_r = sum(t.get('pnl', 0) or 0 for t in sells)
    rows = ''
    for i, t in enumerate(trades):
        bg = WHITE if i % 2 == 0 else ROW_ALT
        a  = t.get('action', '')
        ac = POS if a == 'BUY' else NEG
        pnl = t.get('pnl')
        pnl_s = fmt_pnl(pnl) if pnl is not None else '<span style="color:#9ca3af">open</span>'
        rows += ("<tr style='background:" + bg + ";'>"
                 + td_s("<span style='font-weight:700;color:" + ac + ";'>" + a + "</span>")
                 + td_s("<strong>" + (t.get('symbol') or '') + "</strong>")
                 + td_s("{:.0f}".format(t.get('shares') or 0), align='right', mono=True)
                 + td_s("${:.2f}".format(t.get('exec_price') or 0), align='right', mono=True)
                 + td_s("${:,.0f}".format(t.get('notional') or 0), align='right', small=True, color=TEXT2)
                 + td_s("<span style='color:" + pnl_col(pnl) + ";font-weight:700;font-family:" + MONO + ";'>" + pnl_s + "</span>", align='right')
                 + td_s(t.get('strat') or '', small=True, color=TEXT2)
                 + td_s((t.get('executed_at') or '')[:16], small=True, color=MUTED)
                 + "</tr>")
    buys_n = len([t for t in trades if t.get('action') == 'BUY'])
    note = str(buys_n) + " buys &middot; " + str(len(sells)) + " sells"
    if sells:
        note += (" &middot; realized today: <strong style='color:" + pnl_col(total_r) + ";'>"
                 + fmt_pnl(total_r) + "</strong>")
    return ("<div style='font-size:11px;color:" + TEXT2 + ";margin-bottom:8px;'>" + note + "</div>"
            + tbl(['Action','Symbol','Shares','Price','Notional','P&L','Strategy','Time'],
                  rows, ['left','left','right','right','right','right','left','left']))

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

# ── Signal reasoning flowchart ─────────────────────────────────────────────────
def build_reasoning(signal_rows):
    if not signal_rows:
        return ("<p style='color:" + MUTED + ";font-size:13px;font-style:italic;margin:0;'>"
                "No signals with reasoning in last 7 days.</p>")
    cards = ''
    for sig in signal_rows[:16]:
        sym   = html_lib.escape(sig.get('symbol') or '?')
        strat = html_lib.escape(sig.get('strat') or '?')
        stype = (sig.get('signal_type') or 'BUY').upper()
        conf  = sig.get('confidence') or 0
        raw_r = sig.get('reasoning') or ''
        term  = (sig.get('terminal_state') or '').upper()
        t_rsn = sig.get('terminal_reason') or ''
        asof  = sig.get('asof_date') or ''

        # Split reasoning into discrete steps
        steps = [s.strip() for s in raw_r.replace(';', ',').split(',') if s.strip()]
        if not steps:
            steps = [raw_r.strip()]

        executed  = 'EXECUTED' in term
        ac        = POS if stype == 'BUY' else NEG
        term_col  = POS if executed else NEG
        term_label = 'EXECUTED' if executed else (
            term.replace('REJECTED_', '').replace('_', '\u00a0') if term else 'FILTERED')

        # Build inline step chain
        nodes = ''
        for idx, step in enumerate(steps):
            nodes += ("<span style='display:inline-block;background:" + TH_BG + ";"
                      "border:1px solid " + BORDER + ";padding:3px 8px;border-radius:2px;"
                      "font-size:11px;color:" + TEXT + ";font-family:" + MONO + ";'>"
                      + html_lib.escape(step) + "</span>")
            if idx < len(steps) - 1:
                nodes += "<span style='color:" + MUTED + ";margin:0 4px;'>&rarr;</span>"

        nodes += ("<span style='color:" + MUTED + ";margin:0 4px;'>&rarr;</span>"
                  "<span style='display:inline-block;background:" + term_col + ";color:#fff;"
                  "padding:3px 8px;border-radius:2px;font-size:11px;font-weight:700;'>"
                  + term_label + "</span>")
        if t_rsn:
            nodes += ("<span style='color:" + MUTED + ";font-size:10px;margin-left:6px;'>"
                      "(" + html_lib.escape(t_rsn[:60]) + ")</span>")

        cards += ("<div style='border:1px solid " + BORDER + ";border-left:3px solid " + ac + ";"
                  "padding:12px 14px;margin-bottom:8px;background:" + WHITE + ";'>"
                  "<div style='margin-bottom:8px;'>"
                  "<span style='font-weight:700;font-size:12px;color:" + TEXT + ";'>" + sym + "</span>"
                  "<span style='color:" + MUTED + ";font-size:11px;margin:0 8px;'>&middot;</span>"
                  "<span style='color:" + TEXT2 + ";font-size:11px;'>" + strat + "</span>"
                  "<span style='color:" + MUTED + ";font-size:11px;margin:0 8px;'>&middot;</span>"
                  "<span style='font-weight:700;font-size:11px;color:" + ac + ";'>" + stype + "</span>"
                  "<span style='color:" + MUTED + ";font-size:11px;margin:0 8px;'>&middot;</span>"
                  "<span style='font-size:11px;color:" + MUTED + ";'>conf {:.3f}</span>".format(conf)
                  + "<span style='float:right;font-size:10px;color:" + MUTED + ";'>" + asof + "</span>"
                  "</div>"
                  "<div style='line-height:2;'>" + nodes + "</div>"
                  "</div>")
    return cards

# ── Strategy performance ───────────────────────────────────────────────────────
def build_strat_perf(rows):
    if not rows:
        return "<p style='color:" + MUTED + ";font-size:13px;font-style:italic;margin:0;'>No trade history.</p>"
    trows = ''
    for i, r in enumerate(rows):
        bg  = WHITE if i % 2 == 0 else ROW_ALT
        t7  = r.get('t7')  or 0; w7  = r.get('w7')  or 0; p7  = r.get('p7')  or 0
        t30 = r.get('t30') or 0; w30 = r.get('w30') or 0; p30 = r.get('p30') or 0
        wr7  = "{:.0f}%".format(w7  / t7  * 100) if t7  > 0 else '\u2014'
        wr30 = "{:.0f}%".format(w30 / t30 * 100) if t30 > 0 else '\u2014'
        trows += ("<tr style='background:" + bg + ";'>"
                  + td_s("<strong>" + (r.get('name') or '') + "</strong>")
                  + td_s(str(t7),  align='center', color=TEXT2)
                  + td_s(wr7,      align='center', color=MUTED)
                  + td_s("<span style='color:" + pnl_col(p7) + ";font-weight:700;font-family:" + MONO + ";'>" + fmt_pnl(p7) + "</span>", align='right')
                  + td_s(str(t30), align='center', color=TEXT2)
                  + td_s(wr30,     align='center', color=MUTED)
                  + td_s("<span style='color:" + pnl_col(p30) + ";font-weight:700;font-family:" + MONO + ";'>" + fmt_pnl(p30) + "</span>", align='right')
                  + "</tr>")
    return tbl(['Strategy','Trades (7d)','Win% (7d)','P&L (7d)',
                'Trades (30d)','Win% (30d)','P&L (30d)'], trows,
               ['left','center','center','right','center','center','right'])

# ── Signal funnel ──────────────────────────────────────────────────────────────
def build_funnel(funnel_rows):
    if not funnel_rows:
        return "<p style='color:" + MUTED + ";font-size:13px;font-style:italic;margin:0;'>No funnel data for today.</p>"
    rows = ''
    for i, r in enumerate(funnel_rows):
        bg  = WHITE if i % 2 == 0 else ROW_ALT
        raw = r.get('raw_signals_count') or 0
        reg = r.get('after_regime_count') or raw
        cor = r.get('after_correlation_count') or reg
        rsk = r.get('after_risk_count') or cor
        exc = r.get('executed_count') or 0
        conv = "{:.0f}%".format(exc / raw * 100) if raw > 0 else '\u2014'
        def _node(v, total):
            pct = int(v / total * 100) if total > 0 else 0
            c   = POS if pct >= 80 else ('#d97706' if pct >= 40 else NEG)
            return str(v) + " <span style='font-size:10px;color:" + c + ";'>(" + str(pct) + "%)</span>"
        rows += ("<tr style='background:" + bg + ";'>"
                 + td_s("<strong>" + (r.get('strategy_name') or '?') + "</strong>")
                 + td_s("<strong style='font-family:" + MONO + ";'>" + str(raw) + "</strong>", align='center')
                 + td_s(_node(reg, raw), align='center', small=True)
                 + td_s(_node(cor, raw), align='center', small=True)
                 + td_s(_node(rsk, raw), align='center', small=True)
                 + td_s("<strong style='color:" + POS + ";font-family:" + MONO + ";'>" + str(exc) + "</strong>", align='center')
                 + td_s(conv, align='center', small=True, color=TEXT2)
                 + "</tr>")
    return tbl(['Strategy','Raw','After Regime','After Correlation','After Risk','Executed','Conv%'],
               rows, ['left','center','center','center','center','center','center'])

# ── Rejections ─────────────────────────────────────────────────────────────────
def build_rejections(rows):
    if not rows:
        return "<p style='color:" + MUTED + ";font-size:13px;font-style:italic;margin:0;'>No rejections today.</p>"
    trows = ''
    for i, r in enumerate(rows):
        bg = WHITE if i % 2 == 0 else ROW_ALT
        trows += ("<tr style='background:" + bg + ";'>"
                  + td_s(r.get('stage') or '', color=TEXT2)
                  + td_s("<span style='font-family:" + MONO + ";'>" + (r.get('reason_code') or '') + "</span>")
                  + td_s("<strong style='color:" + NEG + ";'>" + str(r.get('cnt') or 0) + "</strong>", align='right')
                  + "</tr>")
    return tbl(['Stage','Reason','Count'], trows, ['left','left','right'])

# ── Strategy health ────────────────────────────────────────────────────────────
def build_health(health_data):
    if not health_data: return ''
    strategies = health_data.get('strategies', [])
    if not strategies: return ''
    portfolio_score = health_data.get('portfolio_health_score', 0)
    ps_col = POS if portfolio_score >= 70 else ('#d97706' if portfolio_score >= 40 else NEG)
    trows = ''
    for i, s in enumerate(strategies):
        bg     = WHITE if i % 2 == 0 else ROW_ALT
        sc     = s.get('health_score', 0)
        status = s.get('health_status', 'UNKNOWN')
        issues = ', '.join(s.get('issues', [])[:2]) or 'None'
        sc_col = POS if status == 'HEALTHY' else ('#d97706' if status == 'WARNING' else NEG)
        trows += ("<tr style='background:" + bg + ";'>"
                  + td_s("<strong>" + html_lib.escape(s.get('strategy_name') or '?') + "</strong>")
                  + td_s("<span style='font-weight:700;color:" + sc_col + ";font-family:" + MONO + ";'>"
                         + str(sc) + "/100</span>", align='center')
                  + td_s(chip(status, sc_col))
                  + td_s(html_lib.escape(issues), small=True, color=TEXT2)
                  + "</tr>")
    summary = ("<div style='margin-top:10px;font-size:11px;color:" + TEXT2 + ";'>"
               "Portfolio health: <strong style='color:" + ps_col + ";font-size:14px;'>"
               + str(portfolio_score) + "/100</strong></div>")
    return section('Strategy Health',
                   tbl(['Strategy','Score','Status','Issues'], trows,
                       ['left','center','left','left']) + summary)

# ── Main ───────────────────────────────────────────────────────────────────────
def generate_email_body(artifact_path=None, db_path='trading.db', include_visuals=False):
    db = _conn(db_path)
    snap, dd, regime   = get_snapshot(db)
    rows_30d            = get_30d(db)
    strat_perf          = get_strategy_perf(db)
    positions           = get_positions(db)
    today_trades        = get_today_trades(db)
    signal_rows         = get_signal_reasoning(db)
    funnel              = get_funnel(db)
    rejections          = get_rejections(db)
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

    header  = build_header(pv, cash, daily_pnl, daily_pct, dd, regime, recon, len(today_trades))
    summary = build_summary(pv, cash, pnl_30d, rows_30d)
    health  = build_health(get_health())

    body_sections = (
        "    <div style='margin-bottom:20px;'>" + summary + "</div>\n"
        + section("Today's Trades",         build_trades(today_trades),    str(len(today_trades)) + " total")
        + section("Open Positions",          build_positions(positions),    str(len(positions)) + " active")
        + section("Signal Reasoning Chains", build_reasoning(signal_rows),  "last 7 days")
        + section("Strategy Performance",    build_strat_perf(strat_perf),  "7-day and 30-day")
        + health
        + section("Signal Funnel",           build_funnel(funnel),          "today")
        + section("Top Rejection Reasons",   build_rejections(rejections),  "today")
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
