import React, { useState, useRef, useEffect } from "react";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, RadarChart, PolarGrid, PolarAngleAxis, Radar, BarChart, Bar,
  LineChart, Line,
} from "recharts";

// ============================================================
// INVESTOR MIMIC — full interactive dashboard (mock data)
// 7 pages, simple/advanced toggle, time-range controls,
// mobile responsive, and an info-tooltip glossary on every term.
// ============================================================

const C = {
  bg: "#08090d", lime: "#d4ff3f", cyan: "#4dd0ff", mag: "#ff5da2",
  violet: "#b794ff", amber: "#ffb84d", green: "#5fe39a", red: "#ff6b7d",
  text: "#f0f2f5", sec: "#aab3c0", muted: "#6b7585", line: "rgba(255,255,255,0.08)",
  glass: "rgba(255,255,255,0.035)", glass2: "rgba(255,255,255,0.02)",
};
const MONO = "'JetBrains Mono','SF Mono',ui-monospace,monospace";
const DISP = "'Bricolage Grotesque','Manrope',system-ui,sans-serif";
const BODY = "'Manrope',system-ui,sans-serif";

// ---------- GLOSSARY: every confusing term, in plain language ----------
const G = {
  regime: { t: "Market Regime", d: "The market's current 'mood', judged by how volatile it is (a VIX proxy). LOW_VOL = calm, NORMAL = average, HIGH_VOL = turbulent. The bot trades more cautiously when markets are turbulent." },
  cap: { t: "Heat Cap (max exposure)", d: "The most of your portfolio the bot will put into the market at once — a guardrail against over-betting. It tightens with risk: 50% in calm markets, 40% normal, 30% turbulent. '31% of 40%' means it's using 31 of its allowed 40 points." },
  cashfree: { t: "Cash Free", d: "Money not currently invested in any stock — it's sitting ready to deploy into new trades." },
  sharpe: { t: "Sharpe Ratio", d: "Return earned per unit of total risk (bumpiness). Higher is better: above 1 is good, above 2 is excellent. It answers 'am I being paid enough for the ups and downs?'" },
  sortino: { t: "Sortino Ratio", d: "Like Sharpe, but it only penalizes DOWNWARD bumpiness — it doesn't count upside swings as 'risk'. Often a fairer measure, since nobody minds volatility when it's making money." },
  drawdown: { t: "Drawdown", d: "How far the portfolio has fallen from its highest point. Max drawdown is the worst such drop ever recorded. It measures the most pain you'd have felt holding on." },
  volatility: { t: "Volatility", d: "How much the portfolio value bounces around, shown as a yearly %. Higher = a bumpier ride. It's the 'risk' in risk-adjusted return." },
  pf: { t: "Profit Factor", d: "Total dollars made on winning trades ÷ total dollars lost on losing trades. Above 1 means profitable overall. 1.5 = you earn $1.50 for every $1 you lose." },
  winrate: { t: "Win Rate", d: "The percentage of closed trades that ended in a profit. (On its own it's misleading — a few big losses can sink a high win rate, which is why profit factor matters too.)" },
  factor: { t: "Factor Profile", d: "A fingerprint of what a strategy 'bets on', scored across 5 dimensions: momentum (riding trends), quality, reversion (betting on bounce-backs), volume, and volatility. Built from how heavily the strategy's rules weight each one. It's how you see, at a glance, that two strategies are actually different." },
  sharpecompare: { t: "Why compare Sharpe?", d: "Comparing total return only tells you who made the most money. Comparing Sharpe tells you who made the most money FOR THE RISK THEY TOOK. A strategy with lower return but far lower risk can be the better engine." },
  sentiment: { t: "News Sentiment Score", d: "A 0-to-1 score from running each stock's recent news headlines (Google News) through VADER, a sentiment analyzer. Above 0.62 = bullish (boosts the trade), below 0.38 = bearish (shrinks it), below 0.20 = cancels the buy entirely. It's context, not a guarantee." },
  mult: { t: "Sentiment Multiplier", d: "How much the news score scales a strategy's confidence before trading. ×1.15 = bullish news made the bot 15% more confident; ×0.80 = bearish news trimmed confidence by 20%." },
  atr: { t: "ATR Stop", d: "An automatic sell price (stop-loss) set using ATR — Average True Range, the stock's typical daily price swing. The stop sits 2.5× ATR below your entry, so jumpy stocks get more room and calm ones get tighter stops, instead of a flat one-size %." },
  beta: { t: "Beta", d: "How much a stock moves relative to the whole market. Beta 1 = moves with the market; above 1 = swingier than the market; below 1 = calmer than the market." },
  basis: { t: "Cost Basis", d: "What you originally paid for a position. Today's value minus cost basis = your unrealized profit or loss." },
  funnel: { t: "Signal Funnel", d: "The gauntlet every potential trade runs before it's placed. It starts with every candidate and filters at each stage, so you can see exactly why most ideas never become trades." },
  scanned: { t: "Candidates Scanned", d: "Every symbol-and-strategy combination the bot looked at today (36 stocks × 4 strategies = lots of candidates)." },
  passed: { t: "Passed Strategy Logic", d: "Candidates that actually met their strategy's entry rules (e.g. RSI turning up, or a top-5 factor rank)." },
  corr: { t: "Correlation Filter", d: "Rejects a new trade if it moves too similarly (over 0.8 correlation) to something you already hold — stops you from accidentally making the same bet five times." },
  newsgate: { t: "News Gate", d: "Drops or shrinks trades when the news sentiment is bad enough (below 0.38). This is where bearish headlines stop a buy." },
  heatstage: { t: "Within Heat Cap", d: "Trades that still had room under the exposure cap. Once the cap is hit, remaining good signals are deferred to the next session rather than over-extending." },
  conf: { t: "Confidence", d: "The strategy's own estimate of how likely the trade is to work — e.g. the ML model's predicted probability of a 5-day gain." },
  correlation: { t: "Correlation", d: "How similarly two stocks move: 0 = independent, 1 = identical twins. Holding lots of highly-correlated stocks means concentrated, hidden risk." },
  underwater: { t: "Underwater Curve", d: "A drawdown chart that's always at or below zero. It shows how deep, and for how long, the portfolio has been stuck below its previous high." },
  backtest: { t: "Backtest vs Live", d: "Backtest = how the strategy would have done on historical data. Live = real (paper) results. Live is almost always worse — the size of that gap tells you how much to trust the backtest." },
  spy: { t: "vs S&P 500 (SPY)", d: "Your return compared to simply buying the whole market via an S&P 500 index fund. Beating it is the bar that justifies all this complexity over just buying the index." },
  health: { t: "Strategy Health Score", d: "A 0-100 internal grade for whether a strategy is behaving normally — enough recent trades, sane win rate, no data problems. Low scores flag a strategy that needs attention, not necessarily one losing money." },
};

const SERIES = [C.lime, C.cyan, C.mag, C.amber, C.violet];

// 252 trading days for time-range slicing
const fullEq = Array.from({ length: 252 }, (_, i) => ({
  d: i,
  v: Math.round(82000 + i * 105 + Math.sin(i / 11) * 2200 + (i > 160 ? (i - 160) * 70 : 0)),
  spy: Math.round(82000 + i * 82 + Math.sin(i / 13) * 1600),
}));
const RANGES = { "1W": 5, "1M": 21, "3M": 63, YTD: 145, ALL: 252 };

const drawdown = Array.from({ length: 80 }, (_, i) => ({ d: i, dd: -Math.abs(Math.sin(i / 7) * 4 + (i % 13 === 0 ? 2.5 : 0)).toFixed(2) }));
const rollSharpe = Array.from({ length: 40 }, (_, i) => ({ d: i, s: +(1.1 + Math.sin(i / 6) * 0.5 + i * 0.004).toFixed(2) }));
const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const heat = months.map((m, i) => ({ m, r: +(Math.sin(i / 2) * 4 + (i % 3 === 0 ? 1.5 : -0.5)).toFixed(1) }));
const hist = [-6, -4, -2, 0, 2, 4, 6, 8].map((b, i) => ({ b: `${b}%`, n: [2, 5, 11, 18, 22, 14, 7, 3][i] }));

const strategies = [
  { name: "ML Momentum", alloc: 34, ret: 12.4, sharpe: 1.42, sortino: 1.9, pf: 1.8, trades: 47, win: 61, hold: "5d", maxdd: -5.1, color: C.lime, btSharpe: 1.71,
    edge: "LightGBM on 12 OHLCV+indicator features; calibrated top-k entries on P(5-day gain).",
    plain: "An AI model picks the stocks most likely to rise over the next week.",
    radar: [{ k: "Momentum", v: 95 }, { k: "Quality", v: 60 }, { k: "Reversion", v: 20 }, { k: "Volume", v: 70 }, { k: "Volatility", v: 50 }], health: 82 },
  { name: "Factor Momentum", alloc: 28, ret: 8.1, sharpe: 1.09, sortino: 1.4, pf: 1.5, trades: 38, win: 58, hold: "20d", maxdd: -6.4, color: C.cyan, btSharpe: 1.3,
    edge: "Cross-sectional rank: 12m momentum (40%), quality (20%), reversion (20%), volume (20%); top 5.",
    plain: "Ranks all stocks and buys the 5 strongest all-around performers.",
    radar: [{ k: "Momentum", v: 80 }, { k: "Quality", v: 75 }, { k: "Reversion", v: 45 }, { k: "Volume", v: 65 }, { k: "Volatility", v: 40 }], health: 74 },
  { name: "RSI Mean Reversion", alloc: 22, ret: -2.3, sharpe: 0.61, sortino: 0.8, pf: 0.9, trades: 29, win: 48, hold: "≤20d", maxdd: -8.2, color: C.violet, btSharpe: 0.95,
    edge: "RSI(14) < 40 with slope > 0; exits RSI > 55 or 20-day hold. 2.5× ATR stop.",
    plain: "Buys stocks that dropped too fast, betting they bounce back.",
    radar: [{ k: "Momentum", v: 15 }, { k: "Quality", v: 40 }, { k: "Reversion", v: 95 }, { k: "Volume", v: 50 }, { k: "Volatility", v: 80 }], health: 55 },
  { name: "Earnings Drift", alloc: 16, ret: 5.6, sharpe: 0.88, sortino: 1.1, pf: 1.4, trades: 14, win: 64, hold: "≤40d", maxdd: -4.0, color: C.amber, btSharpe: 1.12,
    edge: "Abnormal return > 3% + volume > 1.5× avg (PEAD proxy). 20% target / 10% stop.",
    plain: "Rides the wave after a company posts strong earnings.",
    radar: [{ k: "Momentum", v: 70 }, { k: "Quality", v: 55 }, { k: "Reversion", v: 25 }, { k: "Volume", v: 90 }, { k: "Volatility", v: 60 }], health: 70 },
];

const funnel = [
  { stage: "Candidates scanned", n: 144, color: C.muted, k: "scanned", why: "All 36 symbols × 4 strategies evaluated" },
  { stage: "Passed strategy logic", n: 38, color: C.cyan, k: "passed", why: "106 didn't meet entry conditions" },
  { stage: "Survived correlation filter", n: 22, color: C.violet, k: "corr", why: "16 rejected: >0.8 correlation with held positions" },
  { stage: "Survived news gate", n: 16, color: C.amber, k: "newsgate", why: "6 suppressed/dropped on sentiment < 0.38" },
  { stage: "Within heat cap → executed", n: 9, color: C.lime, k: "heatstage", why: "7 deferred: 40% NORMAL-regime cap reached" },
];

const signalRows = [
  { sym: "NVDA", strat: "ML Momentum", conf: 0.88, sent: 0.71, mult: "×1.15", status: "EXECUTED", reason: "High confidence, sentiment boost applied" },
  { sym: "AVGO", strat: "Factor Mom.", conf: 0.79, sent: 0.64, mult: "×1.15", status: "EXECUTED", reason: "Top-5 rank, bullish news" },
  { sym: "TSLA", strat: "ML Momentum", conf: 0.72, sent: 0.34, mult: "×0.80", status: "FILTERED", reason: "News gate: sentiment 0.34 suppressed below floor" },
  { sym: "JPM", strat: "Factor Mom.", conf: 0.68, sent: 0.55, mult: "×1.00", status: "FILTERED", reason: "Correlation 0.83 with held BAC position" },
  { sym: "KO", strat: "RSI Bounce", conf: 0.61, sent: 0.41, mult: "×1.00", status: "EXECUTED", reason: "RSI turning up, neutral news" },
  { sym: "META", strat: "ML Momentum", conf: 0.83, sent: 0.69, mult: "×1.15", status: "DEFERRED", reason: "Heat cap reached — queued for next session" },
];

const positions = [
  { sym: "NVDA", strat: "ML Momentum", sh: 12, val: 10490, basis: 9878, pl: 6.2, sent: 0.71, lbl: "BULLISH", beta: 1.7, stop: 812.4 },
  { sym: "AVGO", strat: "Factor Mom.", sh: 9, val: 8205, basis: 7865, pl: 4.3, sent: 0.64, lbl: "BULLISH", beta: 1.3, stop: 372.1 },
  { sym: "AMD", strat: "Factor Mom.", sh: 21, val: 6840, basis: 6634, pl: 3.1, sent: 0.58, lbl: "NEUTRAL", beta: 1.9, stop: 142.8 },
  { sym: "UNH", strat: "ML Momentum", sh: 11, val: 5510, basis: 5461, pl: 0.9, sent: 0.49, lbl: "NEUTRAL", beta: 0.6, stop: 466.2 },
  { sym: "BRK.B", strat: "RSI Bounce", sh: 15, val: 7248, basis: 7299, pl: -0.9, sent: 0.33, lbl: "BEARISH", beta: 0.8, stop: 451.0 },
  { sym: "KO", strat: "Earnings Drift", sh: 29, val: 2442, basis: 2461, pl: -0.8, sent: 0.41, lbl: "NEUTRAL", beta: 0.5, stop: 72.4 },
];

// per-symbol drill-down detail (price spark, why-held, news, lots)
const detail = {
  NVDA: { spark: [9.6, 9.7, 9.5, 9.9, 10.1, 10.0, 10.3, 10.49], conf: 0.88, mult: "×1.15",
    why: "ML Momentum scored P(5-day gain) = 0.88, top-3 of today's calibrated set. Bullish news boosted confidence ×1.15.",
    lots: [{ d: "May 16", sh: 12, px: 823.2 }], news: [{ h: "Nvidia data-center sales top forecasts on AI demand", s: "Reuters", sc: 0.74 }, { h: "Analysts lift targets ahead of GTC keynote", s: "Bloomberg", sc: 0.68 }] },
  AVGO: { spark: [7.8, 7.9, 7.85, 8.0, 8.1, 8.05, 8.15, 8.2], conf: 0.79, mult: "×1.15",
    why: "Factor Momentum top-5 composite rank (momentum + quality). Bullish news boost applied.",
    lots: [{ d: "May 12", sh: 9, px: 873.9 }], news: [{ h: "Broadcom raises full-year AI revenue outlook", s: "CNBC", sc: 0.66 }] },
  AMD: { spark: [6.6, 6.7, 6.65, 6.8, 6.75, 6.82, 6.8, 6.84], conf: 0.71, mult: "×1.00",
    why: "Factor Momentum rank #4. Neutral news — no sentiment adjustment.",
    lots: [{ d: "May 9", sh: 21, px: 315.9 }], news: [{ h: "Chip sector mixed as data-center demand normalizes", s: "WSJ", sc: 0.55 }] },
  UNH: { spark: [5.4, 5.45, 5.5, 5.48, 5.52, 5.5, 5.51, 5.51], conf: 0.69, mult: "×1.00",
    why: "ML Momentum entry on modest upward probability. Neutral news.",
    lots: [{ d: "May 14", sh: 11, px: 496.5 }], news: [{ h: "UnitedHealth holds guidance after Q1 beat", s: "Quiver", sc: 0.49 }] },
  "BRK.B": { spark: [7.4, 7.35, 7.3, 7.32, 7.28, 7.3, 7.25, 7.25], conf: 0.61, mult: "×1.00",
    why: "RSI Mean Reversion: RSI(14) dipped below 40 and turned up. Bearish-leaning news stayed above the 0.20 drop-floor, so the signal held.",
    lots: [{ d: "Jan 27", sh: 15, px: 486.6 }], news: [{ h: "Berkshire cash pile draws scrutiny amid slow buybacks", s: "Reuters", sc: 0.33 }] },
  KO: { spark: [2.46, 2.45, 2.44, 2.45, 2.43, 2.44, 2.44, 2.44], conf: 0.58, mult: "×0.80",
    why: "Earnings Drift (PEAD) post-report drift. Soft news trimmed confidence ×0.80 but stayed above the floor.",
    lots: [{ d: "May 2", sh: 29, px: 84.9 }], news: [{ h: "Coca-Cola faces volume pressure in key markets", s: "WSJ", sc: 0.41 }] },
};

const trades = [
  { date: "May 21", sym: "MSFT", strat: "Factor Mom.", side: "SELL", sh: 18, entry: 415.6, exit: 441.3, pl: 6.2, reason: "12% target" },
  { date: "May 18", sym: "GOOGL", strat: "ML Momentum", side: "SELL", sh: 20, entry: 168.2, exit: 175.9, pl: 4.6, reason: "5-day hold" },
  { date: "May 15", sym: "XOM", strat: "RSI Bounce", side: "SELL", sh: 40, entry: 118.4, exit: 113.1, pl: -4.5, reason: "ATR stop hit" },
  { date: "May 12", sym: "LLY", strat: "Earnings Drift", side: "SELL", sh: 6, entry: 740.0, exit: 888.0, pl: 20.0, reason: "20% target" },
  { date: "May 9", sym: "AAPL", strat: "ML Momentum", side: "SELL", sh: 14, entry: 188.5, exit: 191.2, pl: 1.4, reason: "5-day hold" },
];

const fmt = (n) => "$" + n.toLocaleString("en-US");
const sentColor = (s) => (s >= 0.62 ? C.green : s <= 0.38 ? C.red : C.amber);
const plColor = (n) => (n >= 0 ? C.green : C.red);

// ---------- info tooltip ----------
// Measures the icon and renders the popover with position:fixed, clamped to the
// viewport on all sides — so it can never be cut off or trapped behind a card,
// regardless of where the icon sits. (align kept for API compat; unused.)
function Info({ k }) {
  const [o, setO] = useState(false);
  const [pos, setPos] = useState({ top: 0, left: 0, flip: false });
  const ref = useRef(null);
  const g = G[k];

  const place = () => {
    const el = ref.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const W = 248, PAD = 10;
    const vw = window.innerWidth, vh = window.innerHeight;
    let left = r.left + r.width / 2 - W / 2;          // center under the icon
    left = Math.max(PAD, Math.min(left, vw - W - PAD)); // clamp horizontally
    const below = r.bottom + 8;
    const flip = below > vh - 130;                     // open upward if near bottom
    setPos({ top: flip ? r.top - 8 : below, left, flip });
    setO(true);
  };

  useEffect(() => {
    if (!o) return;
    const close = () => setO(false);
    window.addEventListener("scroll", close, true);
    window.addEventListener("resize", close);
    return () => { window.removeEventListener("scroll", close, true); window.removeEventListener("resize", close); };
  }, [o]);

  if (!g) return null;
  return (
    <span style={{ display: "inline-flex", alignItems: "center", verticalAlign: "-0.18em", lineHeight: 0 }}>
      <span ref={ref}
        onMouseEnter={place} onMouseLeave={() => setO(false)}
        onClick={(e) => { e.stopPropagation(); o ? setO(false) : place(); }}
        style={{
          cursor: "pointer", width: 14, height: 14, boxSizing: "border-box", borderRadius: "50%",
          border: `1px solid ${C.muted}`, color: C.muted, fontSize: 9, fontWeight: 700,
          display: "inline-flex", alignItems: "center", justifyContent: "center", marginLeft: 5,
          lineHeight: 1, fontFamily: BODY, flex: "0 0 auto",
        }}>?</span>
      {o && (
        <span style={{
          position: "fixed", top: pos.top, left: pos.left,
          transform: pos.flip ? "translateY(-100%)" : "none",
          width: 248, maxWidth: "calc(100vw - 20px)", zIndex: 9999, padding: "11px 13px",
          background: "#11141c", border: `1px solid ${C.line}`, borderRadius: 12, boxShadow: "0 14px 44px -8px #000",
          textTransform: "none", letterSpacing: 0, fontWeight: 400, lineHeight: 1.55, pointerEvents: "none",
        }}>
          <span style={{ color: C.lime, fontSize: 12, fontWeight: 700, fontFamily: BODY, display: "block", marginBottom: 5 }}>{g.t}</span>
          <span style={{ color: C.sec, fontSize: 12, lineHeight: 1.55, fontFamily: BODY }}>{g.d}</span>
        </span>
      )}
    </span>
  );
}
function Label({ children, k, align, tall }) {
  return (
    <div style={{
      color: C.muted, fontSize: 11, letterSpacing: 2, textTransform: "uppercase", fontWeight: 700,
      lineHeight: 1.35, minHeight: tall ? 32 : undefined, marginBottom: tall ? 4 : 0,
    }}>
      {children}{k && <Info k={k} />}
    </div>
  );
}
function Panel({ children, style, glow, pad = 22, delay = 0, cls }) {
  return (
    <div className={cls} style={{
      background: "#0e1118", border: `1px solid ${C.line}`, borderRadius: 20, padding: pad,
      boxShadow: glow ? `0 0 40px -12px ${glow}55` : "none",
      ...style,
    }}>{children}</div>
  );
}
function Num({ children, size = 26, color = C.text }) {
  return <div style={{ fontFamily: MONO, fontSize: size, fontWeight: 700, color, letterSpacing: -0.5 }}>{children}</div>;
}
function Chip({ children, color }) {
  return <span style={{ fontFamily: MONO, fontSize: 11, fontWeight: 700, color, background: `${color}1a`, border: `1px solid ${color}44`, padding: "3px 9px", borderRadius: 7 }}>{children}</span>;
}
function Spark({ data, color, w = 150, h = 40 }) {
  const min = Math.min(...data), max = Math.max(...data), rng = max - min || 1;
  const pts = data.map((v, i) => `${(i / (data.length - 1)) * w},${h - ((v - min) / rng) * h}`).join(" ");
  return (
    <svg width={w} height={h} style={{ display: "block" }}>
      <polyline points={pts} fill="none" stroke={color} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}
function RangePicker({ range, setRange }) {  return (
    <div style={{ display: "flex", gap: 4 }}>
      {Object.keys(RANGES).map((r) => (
        <span key={r} onClick={() => setRange(r)} style={{
          cursor: "pointer", fontFamily: MONO, fontSize: 11, fontWeight: 700, padding: "4px 9px", borderRadius: 7,
          color: range === r ? C.bg : C.muted, background: range === r ? C.lime : "transparent",
          border: `1px solid ${range === r ? C.lime : C.line}`,
        }}>{r}</span>
      ))}
    </div>
  );
}

export default function MimicDashboard() {
  const [page, setPage] = useState("Overview");
  const [adv, setAdv] = useState(false);
  const [sel, setSel] = useState(strategies[0]);
  const [range, setRange] = useState("3M");

  const NAV = ["Overview", "Strategies", "Positions", "Trades", "Signals", "Analytics", "System"];
  const tip = { background: "#0d1018", border: `1px solid ${C.line}`, borderRadius: 10, color: C.text, fontFamily: MONO, fontSize: 12 };

  return (
    <div style={{ background: C.bg, minHeight: "100vh", fontFamily: BODY, color: C.text, position: "relative", overflow: "hidden" }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500;12..96,700;12..96,800&family=JetBrains+Mono:wght@400;700&family=Manrope:wght@400;500;700&display=swap');
        @keyframes rise { from { opacity:0 } to { opacity:1 } }
        @keyframes grow { from { transform: scaleX(0);} to {transform:scaleX(1);} }
        *::-webkit-scrollbar{height:8px;width:8px} *::-webkit-scrollbar-thumb{background:#ffffff18;border-radius:8px}
        .navitem:hover{ color:#fff !important; } .row:hover{ background: rgba(255,255,255,0.03); }
        .gh{display:grid;gap:16px;grid-template-columns:1.7fr 1fr}
        .gs{display:grid;gap:16px;grid-template-columns:1.4fr 1fr}
        .gf{display:grid;gap:16px;grid-template-columns:1fr 1.3fr}
        .g2{display:grid;gap:16px;grid-template-columns:1fr 1fr}
        .g3{display:grid;gap:16px;grid-template-columns:1fr 1fr 1fr}
        .g4{display:grid;gap:12px;grid-template-columns:repeat(4,1fr)}
        .span2{grid-column:span 2}
        .tscroll{overflow-x:auto}
        @media(max-width:860px){
          .gh,.gs,.gf,.g2,.g3,.g4{grid-template-columns:1fr !important}
          .span2{grid-column:auto}
          .wrap{flex-wrap:wrap;gap:10px}
        }
      `}</style>

      <div style={{ position: "absolute", inset: 0, pointerEvents: "none",
        background: `radial-gradient(700px 400px at 12% -5%, ${C.lime}14, transparent 60%), radial-gradient(600px 500px at 95% 0%, ${C.cyan}12, transparent 55%), radial-gradient(800px 600px at 60% 110%, ${C.mag}0e, transparent 60%)` }} />

      <div style={{ position: "relative", maxWidth: 1240, margin: "0 auto", padding: "22px 22px 60px" }}>
        {/* NAV */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 24, flexWrap: "wrap", gap: 12, rowGap: 12 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 18, flex: "1 1 auto", minWidth: 0 }}>
            <div style={{ fontFamily: DISP, fontWeight: 800, fontSize: 18, letterSpacing: -0.5, whiteSpace: "nowrap", flex: "0 0 auto" }}>
              <span style={{ color: C.lime }}>◆</span> Investor<span style={{ color: C.muted }}>Mimic</span>
            </div>
            <div className="tscroll" style={{ display: "flex", gap: 2, minWidth: 0, flex: "1 1 auto" }}>
              {NAV.map((t) => (
                <div key={t} className="navitem" onClick={() => setPage(t)} style={{
                  padding: "7px 13px", borderRadius: 10, fontSize: 13, cursor: "pointer", fontWeight: 600, whiteSpace: "nowrap",
                  color: page === t ? C.bg : C.sec, background: page === t ? C.lime : "transparent",
                  boxShadow: page === t ? `0 0 24px -6px ${C.lime}` : "none", transition: "all .2s",
                }}>{t}</div>
              ))}
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 12, flex: "0 0 auto", flexWrap: "wrap" }}>
            <div onClick={() => setAdv(!adv)} style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer", background: C.glass, border: `1px solid ${C.line}`, borderRadius: 999, padding: "5px 8px 5px 13px", flex: "0 0 auto" }}>
              <span style={{ fontSize: 12, color: C.sec, fontWeight: 600 }}>{adv ? "Advanced" : "Simple"}</span>
              <div style={{ width: 38, height: 20, borderRadius: 999, background: adv ? C.lime : "#2a2f3a", position: "relative", transition: "all .2s", flex: "0 0 auto" }}>
                <div style={{ position: "absolute", top: 2, left: adv ? 20 : 2, width: 16, height: 16, borderRadius: "50%", background: adv ? C.bg : "#8a94a3", transition: "all .2s" }} />
              </div>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 7, background: C.glass, border: `1px solid ${C.line}`, borderRadius: 999, padding: "6px 12px", flex: "0 0 auto" }}>
              <span style={{ width: 8, height: 8, borderRadius: "50%", background: C.green, boxShadow: `0 0 8px ${C.green}` }} />
              <span style={{ fontSize: 12, color: C.sec }}>6/6</span>
            </div>
          </div>
        </div>

        {!adv && (
          <div style={{ marginBottom: 16, fontSize: 12.5, color: C.sec, background: C.glass, border: `1px solid ${C.line}`, borderRadius: 12, padding: "12px 16px", display: "flex", alignItems: "flex-start", gap: 10 }}>
            <span style={{ color: C.lime, flex: "0 0 auto", marginTop: 1 }}>ⓘ</span>
            <span style={{ lineHeight: 1.6 }}>
              Simple mode hides the technical stats. See a{" "}
              <span style={{ display: "inline-flex", width: 15, height: 15, boxSizing: "border-box", borderRadius: "50%", border: `1px solid ${C.muted}`, color: C.muted, fontSize: 9, fontWeight: 700, alignItems: "center", justifyContent: "center", verticalAlign: "middle", lineHeight: 1 }}>?</span>{" "}
              next to anything? Hover or tap it for a plain-English explanation. Flip to <b style={{ color: C.text }}>Advanced</b> (top right) for the full quant view.
            </span>
          </div>
        )}

        {page === "Overview" && <Overview adv={adv} tip={tip} range={range} setRange={setRange} />}
        {page === "Strategies" && <Strategies adv={adv} sel={sel} setSel={setSel} tip={tip} />}
        {page === "Positions" && <Positions adv={adv} />}
        {page === "Trades" && <Trades adv={adv} />}
        {page === "Signals" && <Signals adv={adv} />}
        {page === "Analytics" && <Analytics adv={adv} tip={tip} />}
        {page === "System" && <System />}

        <div style={{ textAlign: "center", marginTop: 34, fontSize: 11, color: C.muted, fontFamily: MONO }}>
          PAPER TRADING · NO REAL CAPITAL · SNAPSHOT UPDATED 2026-05-22 00:40 ET VIA GITHUB ACTIONS
        </div>
      </div>
    </div>
  );
}

// ============== OVERVIEW ==============
function Overview({ adv, tip, range, setRange }) {
  const data = fullEq.slice(-RANGES[range]);
  return (
    <>
      <div className="gh" style={{ marginBottom: 16 }}>
        <Panel glow={C.lime} delay={0}>
          <div className="wrap" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
            <div>
              <Label>Portfolio Value</Label>
              <div style={{ fontFamily: MONO, fontSize: 44, fontWeight: 700, letterSpacing: -1.5, marginTop: 8 }}>$108,432<span style={{ color: C.muted, fontSize: 24 }}>.17</span></div>
            </div>
            <div style={{ textAlign: "right" }}>
              <Chip color={C.green}>▲ +8.43% ALL-TIME</Chip>
              <div style={{ marginTop: 8, display: "flex", justifyContent: "flex-end", alignItems: "center" }}><Chip color={C.lime}>▲ +2.1% vs SPY</Chip><Info k="spy" align="right" /></div>
            </div>
          </div>
          <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 10 }}><RangePicker range={range} setRange={setRange} /></div>
          <div style={{ height: 190, marginTop: 8 }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={data}>
                <defs><linearGradient id="eg" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={C.lime} stopOpacity={0.4} /><stop offset="100%" stopColor={C.lime} stopOpacity={0} /></linearGradient></defs>
                <CartesianGrid stroke={C.line} vertical={false} /><XAxis dataKey="d" hide /><YAxis hide domain={["dataMin - 1500", "dataMax + 1500"]} />
                <Tooltip contentStyle={tip} formatter={(v) => fmt(v)} labelStyle={{ color: C.muted }} />
                <Area type="monotone" dataKey="spy" stroke={C.muted} strokeWidth={1.5} strokeDasharray="4 4" fill="none" />
                <Area type="monotone" dataKey="v" stroke={C.lime} strokeWidth={2.5} fill="url(#eg)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
          <div style={{ display: "flex", gap: 16, fontSize: 12, color: C.muted, fontFamily: MONO }}><span style={{ color: C.lime }}>━ Portfolio</span><span>┅ S&P 500</span><span style={{ marginLeft: "auto" }}>{range}</span></div>
        </Panel>

        <Panel delay={0.06}>
          <Label>{adv ? "Risk-Adjusted Performance" : "How You're Doing"}</Label>
          {!adv ? (
            <div style={{ marginTop: 16 }}>
              <Num size={34} color={C.green}>+$8,432</Num>
              <div style={{ color: C.sec, fontSize: 13, marginTop: 4 }}>total profit since you started</div>
              <div className="g2" style={{ gap: 14, marginTop: 22, alignItems: "start" }}>
                <div><Label tall>Today</Label><Num size={20} color={C.green}>+$1,961</Num></div>
                <div><Label k="cashfree" align="right" tall>Cash Free</Label><Num size={20}>$22,108</Num></div>
                <div><Label tall>Holdings</Label><Num size={20}>14</Num></div>
                <div><Label k="spy" align="right" tall>Beating index?</Label><Num size={20} color={C.lime}>Yes ✓</Num></div>
              </div>
            </div>
          ) : (
            <div className="g2" style={{ gap: 16, marginTop: 16, alignItems: "start" }}>
              <div><Label k="sharpe" tall>Sharpe</Label><Num size={24} color={C.lime}>1.31</Num></div>
              <div><Label k="sortino" align="right" tall>Sortino</Label><Num size={24} color={C.green}>1.88</Num></div>
              <div><Label k="drawdown" tall>Max Drawdown</Label><Num size={24} color={C.amber}>−6.4%</Num></div>
              <div><Label k="volatility" align="right" tall>Volatility</Label><Num size={24}>11.2%</Num></div>
              <div><Label k="winrate" tall>Win Rate</Label><Num size={24}>57%</Num></div>
              <div><Label k="pf" align="right" tall>Profit Factor</Label><Num size={24}>1.54</Num></div>
            </div>
          )}
          <div style={{ marginTop: 18, paddingTop: 14, borderTop: `1px solid ${C.line}`, display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 13 }}>
            <Label k="regime">Regime</Label><span style={{ color: C.amber, fontWeight: 700, fontFamily: MONO, display: "flex", alignItems: "center" }}>● NORMAL · 40% cap<Info k="cap" align="right" /></span>
          </div>
        </Panel>
      </div>

      <div className="g3">
        <Panel delay={0.12} cls="span2">
          <Label>Strategy Allocation</Label>
          <div className="wrap" style={{ display: "flex", alignItems: "center", gap: 20, marginTop: 8 }}>
            <div style={{ width: 150, height: 150 }}>
              <ResponsiveContainer><PieChart>
                <Pie data={strategies} dataKey="alloc" innerRadius={45} outerRadius={70} paddingAngle={3} stroke="none">{strategies.map((s, i) => <Cell key={i} fill={s.color} />)}</Pie>
                <Tooltip contentStyle={tip} formatter={(v, n, p) => [`${v}%`, p.payload.name]} />
              </PieChart></ResponsiveContainer>
            </div>
            <div style={{ flex: 1, minWidth: 220 }}>
              {strategies.map((s) => (
                <div key={s.name} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "7px 0", borderBottom: `1px solid ${C.line}` }}>
                  <span style={{ fontSize: 13 }}><span style={{ color: s.color }}>●</span> {s.name}</span>
                  <span style={{ display: "flex", gap: 14, fontFamily: MONO, fontSize: 13 }}><span style={{ color: C.muted }}>{s.alloc}%</span><span style={{ color: plColor(s.ret), width: 56, textAlign: "right" }}>{s.ret >= 0 ? "+" : ""}{s.ret}%</span></span>
                </div>
              ))}
            </div>
          </div>
        </Panel>
        <Panel delay={0.18}>
          <Label>Today's Activity</Label>
          {[["BUY", "12 NVDA", C.green], ["BUY", "40 KO", C.green], ["SELL", "18 MSFT", C.red]].map(([a, t, c], i) => (
            <div key={i} style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 0", borderBottom: i < 2 ? `1px solid ${C.line}` : "none" }}><Chip color={c}>{a}</Chip><span style={{ fontFamily: MONO, fontSize: 13 }}>{t}</span></div>
          ))}
          <div style={{ fontSize: 12, color: C.muted, marginTop: 10 }}>9 signals executed · 7 deferred by heat cap</div>
        </Panel>
      </div>
    </>
  );
}

// ============== STRATEGIES ==============
function Strategies({ adv, sel, setSel, tip }) {
  return (
    <>
      <div className="g4" style={{ marginBottom: 16 }}>
        {strategies.map((s, i) => {
          const on = sel.name === s.name;
          return (
            <Panel key={s.name} delay={i * 0.05} glow={on ? s.color : null} style={{ cursor: "pointer", borderColor: on ? `${s.color}66` : C.line }} pad={18}>
              <div onClick={() => setSel(s)}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span style={{ color: s.color, fontSize: 16 }}>●</span>
                  <span style={{ display: "flex", alignItems: "center" }}><Chip color={s.health >= 75 ? C.green : s.health >= 60 ? C.amber : C.red}>{s.health}/100</Chip><Info k="health" align="right" /></span>
                </div>
                <div style={{ fontFamily: DISP, fontWeight: 700, fontSize: 15, marginTop: 10 }}>{s.name}</div>
                <Num size={22} color={plColor(s.ret)}>{s.ret >= 0 ? "+" : ""}{s.ret}%</Num>
                <div style={{ height: 5, background: C.glass2, borderRadius: 4, marginTop: 10, overflow: "hidden" }}><div style={{ width: `${s.alloc}%`, height: "100%", background: s.color, transformOrigin: "left", animation: "grow .6s ease backwards" }} /></div>
                <div style={{ fontSize: 11, color: C.muted, marginTop: 8, fontFamily: MONO }}>{s.alloc}% alloc · {s.trades} trades</div>
              </div>
            </Panel>
          );
        })}
      </div>

      <div className="gs">
        <Panel glow={sel.color} delay={0.1}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div style={{ fontFamily: DISP, fontWeight: 800, fontSize: 22 }}><span style={{ color: sel.color }}>●</span> {sel.name}</div>
            <Chip color={sel.color}>{sel.hold} hold</Chip>
          </div>
          <div style={{ color: C.sec, fontSize: 14, marginTop: 12, lineHeight: 1.6 }}>{adv ? sel.edge : sel.plain}</div>
          <div className="g3" style={{ gridTemplateColumns: adv ? "1fr 1fr 1fr" : "1fr 1fr", gap: 16, marginTop: 22, alignItems: "start" }}>
            <div><Label tall>Return</Label><Num size={22} color={plColor(sel.ret)}>{sel.ret >= 0 ? "+" : ""}{sel.ret}%</Num></div>
            <div><Label k="winrate" tall>Win Rate</Label><Num size={22}>{sel.win}%</Num></div>
            {adv && <div><Label k="sharpe" align="right" tall>Sharpe</Label><Num size={22} color={sel.color}>{sel.sharpe}</Num></div>}
            {adv && <div><Label k="sortino" tall>Sortino</Label><Num size={22}>{sel.sortino}</Num></div>}
            {adv && <div><Label k="pf" tall>Profit Factor</Label><Num size={22}>{sel.pf}</Num></div>}
            {adv && <div><Label k="drawdown" align="right" tall>Max DD</Label><Num size={22} color={C.amber}>{sel.maxdd}%</Num></div>}
            {!adv && <div><Label tall>Allocation</Label><Num size={22}>{sel.alloc}%</Num></div>}
          </div>
        </Panel>

        <Panel delay={0.16}>
          <Label k="factor">{adv ? "Factor Profile" : "What It Bets On"}</Label>
          <div style={{ height: 240, marginTop: 8 }}>
            <ResponsiveContainer><RadarChart data={sel.radar} outerRadius={85}><PolarGrid stroke={C.line} /><PolarAngleAxis dataKey="k" tick={{ fill: C.sec, fontSize: 11 }} /><Radar dataKey="v" stroke={sel.color} fill={sel.color} fillOpacity={0.3} strokeWidth={2} /></RadarChart></ResponsiveContainer>
          </div>
        </Panel>
      </div>

      <Panel delay={0.22} style={{ marginTop: 16 }}>
        <Label k={adv ? "sharpecompare" : undefined}>Strategy Comparison{!adv && <Info k="sharpecompare" />}</Label>
        <div style={{ height: 200, marginTop: 12 }}>
          <ResponsiveContainer><BarChart data={strategies}><CartesianGrid stroke={C.line} vertical={false} /><XAxis dataKey="name" tick={{ fill: C.muted, fontSize: 11 }} axisLine={false} tickLine={false} /><YAxis tick={{ fill: C.muted, fontSize: 11, fontFamily: MONO }} axisLine={false} tickLine={false} /><Tooltip contentStyle={tip} cursor={{ fill: "#ffffff08" }} /><Bar dataKey={adv ? "sharpe" : "ret"} radius={[6, 6, 0, 0]}>{strategies.map((s, i) => <Cell key={i} fill={s.color} />)}</Bar></BarChart></ResponsiveContainer>
        </div>
        <div style={{ fontSize: 12, color: C.muted }}>Comparing {adv ? "Sharpe ratio — return earned per unit of risk, so this shows the best engine, not just the biggest winner" : "total return %"} across strategies</div>
      </Panel>
    </>
  );
}

// ============== POSITIONS ==============
function Positions({ adv }) {
  const [open, setOpen] = useState(null);
  const colSpan = adv ? 8 : 5;
  return (
    <Panel delay={0}>
      <div className="wrap" style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
        <Label>Positions & News Sentiment</Label>
        <span style={{ fontSize: 12, color: C.muted, fontFamily: MONO }}>14 open · {adv ? "advanced" : "simple"} view</span>
      </div>
      <div style={{ fontSize: 12, color: C.muted, marginBottom: 14 }}>Click any row to expand its full analysis ▾</div>
      <div className="tscroll">
        <table style={{ width: "100%", borderCollapse: "collapse", minWidth: adv ? 760 : 460 }}>
          <thead><tr style={{ color: C.muted, fontSize: 10.5, letterSpacing: 1, textTransform: "uppercase", textAlign: "left" }}>
            <th style={{ padding: "0 0 12px", fontWeight: 700 }}>Symbol</th><th style={{ fontWeight: 700 }}>Strategy</th>
            {adv && <th style={{ fontWeight: 700, textAlign: "right" }}>Shares</th>}
            <th style={{ fontWeight: 700, textAlign: "right" }}>Value</th>
            {adv && <th style={{ fontWeight: 700, textAlign: "right" }}><span style={{ display: "inline-flex", alignItems: "center" }}>Cost Basis<Info k="basis" /></span></th>}
            <th style={{ fontWeight: 700, textAlign: "right" }}>P&L</th>
            {adv && <th style={{ fontWeight: 700, textAlign: "right" }}><span style={{ display: "inline-flex", alignItems: "center" }}>Beta<Info k="beta" /></span></th>}
            {adv && <th style={{ fontWeight: 700, textAlign: "right" }}><span style={{ display: "inline-flex", alignItems: "center" }}>ATR Stop<Info k="atr" /></span></th>}
            <th style={{ fontWeight: 700, textAlign: "right" }}><span style={{ display: "inline-flex", alignItems: "center" }}>Sentiment<Info k="sentiment" /></span></th>
          </tr></thead>
          <tbody>
            {positions.map((p) => {
              const isOpen = open === p.sym;
              const d = detail[p.sym];
              return (
                <React.Fragment key={p.sym}>
                  <tr className="row" onClick={() => setOpen(isOpen ? null : p.sym)}
                    style={{ borderTop: `1px solid ${C.line}`, cursor: "pointer", background: isOpen ? "rgba(212,255,63,0.04)" : "transparent" }}>
                    <td style={{ padding: "13px 0", fontWeight: 700, fontFamily: MONO }}>
                      <span style={{ display: "inline-block", width: 12, color: isOpen ? C.lime : C.muted, transition: "transform .2s", transform: isOpen ? "rotate(90deg)" : "none" }}>▸</span> {p.sym}
                    </td>
                    <td style={{ color: C.sec, fontSize: 13 }}>{p.strat}</td>
                    {adv && <td style={{ textAlign: "right", fontFamily: MONO, fontSize: 13, color: C.sec }}>{p.sh}</td>}
                    <td style={{ textAlign: "right", fontFamily: MONO, fontSize: 13 }}>{fmt(p.val)}</td>
                    {adv && <td style={{ textAlign: "right", fontFamily: MONO, fontSize: 13, color: C.muted }}>{fmt(p.basis)}</td>}
                    <td style={{ textAlign: "right", fontFamily: MONO, fontWeight: 700, color: plColor(p.pl) }}>{p.pl >= 0 ? "+" : ""}{p.pl}%</td>
                    {adv && <td style={{ textAlign: "right", fontFamily: MONO, fontSize: 13, color: C.sec }}>{p.beta}</td>}
                    {adv && <td style={{ textAlign: "right", fontFamily: MONO, fontSize: 13, color: C.muted }}>${p.stop}</td>}
                    <td style={{ textAlign: "right" }}><div style={{ display: "inline-flex", alignItems: "center", gap: 8 }}><div style={{ width: 54, height: 6, background: C.glass2, borderRadius: 4, overflow: "hidden" }}><div style={{ width: `${p.sent * 100}%`, height: "100%", background: sentColor(p.sent) }} /></div><Chip color={sentColor(p.sent)}>{p.sent.toFixed(2)}</Chip></div></td>
                  </tr>
                  {isOpen && d && (
                    <tr>
                      <td colSpan={colSpan} style={{ padding: 0 }}>
                        <div style={{ background: C.glass2, border: `1px solid ${C.line}`, borderRadius: 14, margin: "4px 0 12px", padding: 18 }}>
                          <div className="g3" style={{ gap: 16, alignItems: "start" }}>
                            {/* price + why */}
                            <div className="span2">
                              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                                <span style={{ fontFamily: DISP, fontWeight: 700, fontSize: 16 }}>{p.sym} <span style={{ color: C.muted, fontSize: 13, fontWeight: 400 }}>· {p.strat}</span></span>
                                <Spark data={d.spark} color={plColor(p.pl)} w={140} h={36} />
                              </div>
                              <Label>Why the bot holds this</Label>
                              <div style={{ color: C.sec, fontSize: 13, lineHeight: 1.6, marginTop: 6 }}>{d.why}</div>
                              {adv && (
                                <div style={{ display: "flex", gap: 18, marginTop: 12, fontFamily: MONO, fontSize: 12, color: C.sec, flexWrap: "wrap" }}>
                                  <span>conf <b style={{ color: C.text }}>{d.conf}</b></span>
                                  <span>sentiment mult <b style={{ color: C.text }}>{d.mult}</b></span>
                                  <span>ATR stop <b style={{ color: C.text }}>${p.stop}</b></span>
                                  <span>beta <b style={{ color: C.text }}>{p.beta}</b></span>
                                </div>
                              )}
                              {/* lots / how acquired */}
                              <div style={{ marginTop: 14 }}>
                                <Label>How you got here</Label>
                                <div style={{ marginTop: 6 }}>
                                  {d.lots.map((l, i) => (
                                    <div key={i} style={{ display: "flex", gap: 10, alignItems: "center", fontSize: 13, padding: "5px 0" }}>
                                      <Chip color={C.green}>BUY</Chip>
                                      <span style={{ fontFamily: MONO, color: C.body }}>{l.sh} sh @ ${l.px}</span>
                                      <span style={{ color: C.muted, fontSize: 12 }}>· {l.d}</span>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            </div>
                            {/* news column */}
                            <div>
                              <Label>News driving sentiment</Label>
                              <div style={{ marginTop: 8 }}>
                                {d.news.map((n, i) => (
                                  <div key={i} style={{ borderLeft: `2px solid ${sentColor(n.sc)}`, paddingLeft: 10, marginBottom: 12 }}>
                                    <div style={{ fontSize: 12.5, color: C.body, lineHeight: 1.45 }}>{n.h}</div>
                                    <div style={{ fontSize: 11, color: C.muted, marginTop: 4, fontFamily: MONO }}>{n.s} · score {n.sc.toFixed(2)}</div>
                                  </div>
                                ))}
                                <div style={{ fontSize: 10.5, color: C.muted, fontStyle: "italic", marginTop: 4 }}>Context only — not a guaranteed cause.</div>
                              </div>
                            </div>
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

// ============== TRADES (closed-trade ledger) ==============
function Trades({ adv }) {
  const realized = trades.reduce((a, t) => a + t.pl, 0);
  return (
    <>
      <div className="g4" style={{ marginBottom: 16 }}>
        <Panel delay={0}><Label>Closed Trades</Label><Num size={26}>{trades.length}</Num></Panel>
        <Panel delay={0.04}><Label k="winrate">Win Rate</Label><Num size={26}>{Math.round(trades.filter(t => t.pl > 0).length / trades.length * 100)}%</Num></Panel>
        <Panel delay={0.08}><Label>Avg Return / Trade</Label><Num size={26} color={plColor(realized / trades.length)}>{(realized / trades.length).toFixed(1)}%</Num></Panel>
        {adv ? <Panel delay={0.12}><Label k="pf">Profit Factor</Label><Num size={26}>1.54</Num></Panel> : <Panel delay={0.12}><Label>Best Trade</Label><Num size={26} color={C.green}>+20%</Num></Panel>}
      </div>
      <Panel delay={0.16}>
        <Label>Trade History</Label>
        <div className="tscroll" style={{ marginTop: 12 }}>
          <table style={{ width: "100%", borderCollapse: "collapse", minWidth: adv ? 700 : 420 }}>
            <thead><tr style={{ color: C.muted, fontSize: 10.5, letterSpacing: 1, textTransform: "uppercase", textAlign: "left" }}>
              <th style={{ padding: "0 0 12px", fontWeight: 700 }}>Date</th><th style={{ fontWeight: 700 }}>Symbol</th><th style={{ fontWeight: 700 }}>Strategy</th>
              {adv && <th style={{ fontWeight: 700, textAlign: "right" }}>Entry → Exit</th>}
              <th style={{ fontWeight: 700, textAlign: "right" }}>Realized P&L</th><th style={{ fontWeight: 700, textAlign: "right" }}>Exit Reason</th>
            </tr></thead>
            <tbody>
              {trades.map((t, i) => (
                <tr key={i} className="row" style={{ borderTop: `1px solid ${C.line}` }}>
                  <td style={{ padding: "13px 0", fontFamily: MONO, fontSize: 13, color: C.sec }}>{t.date}</td>
                  <td style={{ fontWeight: 700, fontFamily: MONO }}>{t.sym}</td>
                  <td style={{ color: C.sec, fontSize: 13 }}>{t.strat}</td>
                  {adv && <td style={{ textAlign: "right", fontFamily: MONO, fontSize: 13, color: C.muted }}>${t.entry} → ${t.exit}</td>}
                  <td style={{ textAlign: "right", fontFamily: MONO, fontWeight: 700, color: plColor(t.pl) }}>{t.pl >= 0 ? "+" : ""}{t.pl}%</td>
                  <td style={{ textAlign: "right", fontSize: 12, color: C.sec }}>{t.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </>
  );
}

// ============== SIGNALS ==============
function Signals({ adv }) {
  const maxF = funnel[0].n;
  const sc = { EXECUTED: C.green, FILTERED: C.red, DEFERRED: C.amber };
  return (
    <div className="gf">
      <Panel delay={0}>
        <Label k="funnel">Signal Funnel · Today</Label>
        <div style={{ marginTop: 14 }}>
          {funnel.map((f) => (
            <div key={f.stage} style={{ marginBottom: 16 }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12.5, marginBottom: 6 }}>
                <span style={{ color: C.sec, display: "inline-flex", alignItems: "center" }}>{f.stage}<Info k={f.k} /></span>
                <span style={{ fontFamily: MONO, fontWeight: 700, color: f.color }}>{f.n}</span>
              </div>
              <div style={{ height: 12, background: C.glass2, borderRadius: 6, overflow: "hidden" }}><div style={{ width: `${(f.n / maxF) * 100}%`, height: "100%", background: f.color, borderRadius: 6, transformOrigin: "left", animation: "grow .6s ease backwards" }} /></div>
              {adv && <div style={{ fontSize: 11, color: C.muted, marginTop: 5, fontFamily: MONO }}>{f.why}</div>}
            </div>
          ))}
          <div style={{ fontSize: 11.5, color: C.muted, fontStyle: "italic", marginTop: 4 }}>144 scanned → 9 executed. Each stage shows why ideas were filtered out.</div>
        </div>
      </Panel>

      <Panel delay={0.08}>
        <Label>Signal Explorer · Why Each Fired or Didn't</Label>
        <div style={{ marginTop: 12 }}>
          {signalRows.map((r) => (
            <div key={r.sym} className="row" style={{ padding: "12px 10px", borderRadius: 12, borderBottom: `1px solid ${C.line}` }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}><span style={{ fontFamily: MONO, fontWeight: 700 }}>{r.sym}</span><span style={{ fontSize: 12, color: C.muted }}>{r.strat}</span></div>
                <Chip color={sc[r.status]}>{r.status}</Chip>
              </div>
              {adv && (
                <div style={{ display: "flex", gap: 16, marginTop: 8, fontFamily: MONO, fontSize: 11.5, color: C.sec, flexWrap: "wrap" }}>
                  <span style={{ display: "inline-flex", alignItems: "center" }}>conf <b style={{ color: C.text, marginLeft: 4 }}>{r.conf}</b><Info k="conf" /></span>
                  <span style={{ display: "inline-flex", alignItems: "center" }}>sent <b style={{ color: sentColor(r.sent), marginLeft: 4 }}>{r.sent}</b><Info k="sentiment" /></span>
                  <span style={{ display: "inline-flex", alignItems: "center" }}>mult <b style={{ color: C.text, marginLeft: 4 }}>{r.mult}</b><Info k="mult" /></span>
                </div>
              )}
              <div style={{ fontSize: 12, color: C.muted, marginTop: 7, lineHeight: 1.5 }}>{r.reason}</div>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}

// ============== ANALYTICS ==============
function Analytics({ adv, tip }) {
  const heatColor = (r) => r >= 0 ? `rgba(95,227,154,${Math.min(Math.abs(r) / 5, 1) * 0.8 + 0.15})` : `rgba(255,107,125,${Math.min(Math.abs(r) / 5, 1) * 0.8 + 0.15})`;
  const corr = strategies.map((a) => strategies.map((b) => a.name === b.name ? 1 : +(Math.random() * 0.5 + 0.1).toFixed(2)));
  return (
    <>
      <div className="g2" style={{ marginBottom: 16 }}>
        <Panel delay={0}>
          <Label k="underwater">Drawdown · Underwater Curve</Label>
          <div style={{ height: 180, marginTop: 12 }}>
            <ResponsiveContainer><AreaChart data={drawdown}><defs><linearGradient id="dd" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={C.red} stopOpacity={0.05} /><stop offset="100%" stopColor={C.red} stopOpacity={0.4} /></linearGradient></defs><CartesianGrid stroke={C.line} vertical={false} /><XAxis dataKey="d" hide /><YAxis tick={{ fill: C.muted, fontSize: 11, fontFamily: MONO }} axisLine={false} tickLine={false} /><Tooltip contentStyle={tip} formatter={(v) => `${v}%`} /><Area type="monotone" dataKey="dd" stroke={C.red} strokeWidth={2} fill="url(#dd)" /></AreaChart></ResponsiveContainer>
          </div>
          <div style={{ fontSize: 12, color: C.muted }}>Worst: −6.4% · how far below the prior peak you've been</div>
        </Panel>
        {adv ? (
          <Panel delay={0.06}>
            <Label k="sharpe">Rolling 30-Day Sharpe</Label>
            <div style={{ height: 180, marginTop: 12 }}><ResponsiveContainer><LineChart data={rollSharpe}><CartesianGrid stroke={C.line} vertical={false} /><XAxis dataKey="d" hide /><YAxis tick={{ fill: C.muted, fontSize: 11, fontFamily: MONO }} axisLine={false} tickLine={false} /><Tooltip contentStyle={tip} /><Line type="monotone" dataKey="s" stroke={C.lime} strokeWidth={2.5} dot={false} /></LineChart></ResponsiveContainer></div>
            <div style={{ fontSize: 12, color: C.muted }}>Risk-adjusted return, trended over time</div>
          </Panel>
        ) : (
          <Panel delay={0.06}>
            <Label>Best & Worst Months</Label>
            <div className="g2" style={{ gap: 16, marginTop: 18 }}><div><Label>Best</Label><Num size={28} color={C.green}>+5.8%</Num><div style={{ color: C.muted, fontSize: 12 }}>March</div></div><div><Label>Worst</Label><Num size={28} color={C.red}>−3.1%</Num><div style={{ color: C.muted, fontSize: 12 }}>August</div></div></div>
            <div style={{ marginTop: 18, paddingTop: 14, borderTop: `1px solid ${C.line}`, fontSize: 13, color: C.sec }}>8 of 12 months positive · steady upward trend</div>
          </Panel>
        )}
      </div>

      <Panel delay={0.1} style={{ marginBottom: 16 }}>
        <Label k="backtest">Backtest vs Live · Reality Check</Label>
        <div style={{ marginTop: 14 }}>
          {strategies.map((s) => (
            <div key={s.name} style={{ display: "flex", alignItems: "center", gap: 12, padding: "9px 0", borderBottom: `1px solid ${C.line}` }}>
              <span style={{ width: 150, fontSize: 13 }}><span style={{ color: s.color }}>●</span> {s.name}</span>
              <div style={{ flex: 1, display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ fontFamily: MONO, fontSize: 12, color: C.muted, width: 84 }}>backtest {s.btSharpe}</span>
                <div style={{ flex: 1, height: 8, background: C.glass2, borderRadius: 5, position: "relative" }}>
                  <div style={{ width: `${(s.btSharpe / 2) * 100}%`, height: "100%", background: `${s.color}55`, borderRadius: 5 }} />
                  <div style={{ position: "absolute", top: 0, width: `${(s.sharpe / 2) * 100}%`, height: "100%", background: s.color, borderRadius: 5 }} />
                </div>
                <span style={{ fontFamily: MONO, fontSize: 12, color: C.text, width: 64 }}>live {s.sharpe}</span>
              </div>
            </div>
          ))}
          <div style={{ fontSize: 12, color: C.muted, marginTop: 10 }}>Live (solid) runs below backtest (faded) — normal, and honest. A small gap means the backtest was realistic.</div>
        </div>
      </Panel>

      <Panel delay={0.14} style={{ marginBottom: 16 }}>
        <Label>Monthly Returns</Label>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(12,1fr)", gap: 6, marginTop: 14 }}>
          {heat.map((h) => (<div key={h.m} style={{ textAlign: "center" }}><div style={{ height: 54, borderRadius: 8, background: heatColor(h.r), display: "flex", alignItems: "center", justifyContent: "center", fontFamily: MONO, fontSize: 12, fontWeight: 700, color: "#08090d" }}>{h.r > 0 ? "+" : ""}{h.r}</div><div style={{ fontSize: 10, color: C.muted, marginTop: 5 }}>{h.m}</div></div>))}
        </div>
      </Panel>

      {adv && (
        <div className="g2">
          <Panel delay={0.18}>
            <Label>Return Distribution</Label>
            <div style={{ height: 170, marginTop: 12 }}><ResponsiveContainer><BarChart data={hist}><CartesianGrid stroke={C.line} vertical={false} /><XAxis dataKey="b" tick={{ fill: C.muted, fontSize: 10, fontFamily: MONO }} axisLine={false} tickLine={false} /><YAxis hide /><Tooltip contentStyle={tip} cursor={{ fill: "#ffffff08" }} /><Bar dataKey="n" radius={[5, 5, 0, 0]}>{hist.map((h, i) => <Cell key={i} fill={h.b.startsWith("-") ? C.red : C.lime} />)}</Bar></BarChart></ResponsiveContainer></div>
          </Panel>
          <Panel delay={0.22}>
            <Label k="correlation">Strategy Correlation Matrix</Label>
            <div style={{ marginTop: 14 }}>
              {corr.map((row, i) => (<div key={i} style={{ display: "flex", gap: 5, marginBottom: 5, alignItems: "center" }}><span style={{ width: 30, fontSize: 10, color: C.muted, fontFamily: MONO }}>{strategies[i].name.split(" ")[0].slice(0, 4)}</span>{row.map((v, j) => (<div key={j} style={{ flex: 1, height: 32, borderRadius: 6, background: `rgba(212,255,63,${v * 0.7 + 0.05})`, display: "flex", alignItems: "center", justifyContent: "center", fontFamily: MONO, fontSize: 11, fontWeight: 700, color: v > 0.5 ? "#08090d" : C.sec }}>{v}</div>))}</div>))}
              <div style={{ fontSize: 11, color: C.muted, marginTop: 8 }}>Lower = better diversification across strategies</div>
            </div>
          </Panel>
        </div>
      )}
    </>
  );
}

// ============== SYSTEM DESIGN ==============
function System() {
  const pipeline = [
    { t: "1 · Data Ingest", c: C.cyan, d: "Alpha Vantage pulls 15 years of split-adjusted OHLCV. A data-quality gate blocks any symbol with >10% missing values, staleness >72h, or price outliers." },
    { t: "2 · Strategy Signals", c: C.lime, d: "4 independent strategies (RSI, ML Momentum, Earnings Drift, Factor Momentum) each scan all 36 symbols and emit candidate buy/sell signals." },
    { t: "3 · News Sentiment", c: C.amber, d: "Google News headlines per symbol → VADER sentiment. Boosts, suppresses, or cancels each signal's confidence before sizing." },
    { t: "4 · Risk Filters", c: C.violet, d: "Correlation filter (reject >0.8 vs holdings), regime-dependent heat cap, 2.5× ATR stops, and a −5% daily loss circuit breaker." },
    { t: "5 · Allocation", c: C.mag, d: "Capital is split across strategies by Sharpe ratio, rebalanced weekly, bounded 10–40% each." },
    { t: "6 · Reconcile + Execute", c: C.green, d: "Local positions are reconciled against the Alpaca broker before any order. A >1% mismatch blocks trading until resolved." },
    { t: "7 · Snapshot + Notify", c: C.cyan, d: "Results export to a JSON snapshot (this site reads that — never the live broker) and a daily email digest is sent. All via GitHub Actions." },
  ];
  const glossOrder = ["regime", "cap", "sharpe", "sortino", "drawdown", "volatility", "pf", "winrate", "factor", "sentiment", "mult", "atr", "beta", "basis", "funnel", "correlation", "underwater", "backtest"];
  return (
    <>
      <Panel delay={0} glow={C.lime} style={{ marginBottom: 16 }}>
        <div style={{ fontFamily: DISP, fontWeight: 800, fontSize: 24 }}>How Investor Mimic Works</div>
        <div style={{ color: C.sec, fontSize: 14, marginTop: 10, lineHeight: 1.6, maxWidth: 760 }}>
          A fully automated, regime-aware quantitative trading system. It runs once each trading day through a GitHub Actions pipeline — no servers, no manual steps. Every stage below is a real safety or decision layer, executed in order.
        </div>
      </Panel>

      <div style={{ marginBottom: 16 }}>
        {pipeline.map((p, i) => (
          <div key={i} style={{ display: "flex", gap: 16, alignItems: "stretch", animation: `rise .5s ease ${i * 0.05}s backwards` }}>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
              <div style={{ width: 14, height: 14, borderRadius: "50%", background: p.c, boxShadow: `0 0 12px ${p.c}`, marginTop: 22 }} />
              {i < pipeline.length - 1 && <div style={{ width: 2, flex: 1, background: C.line }} />}
            </div>
            <Panel delay={0} style={{ flex: 1, marginBottom: 10 }} pad={16}>
              <div style={{ fontFamily: DISP, fontWeight: 700, fontSize: 15, color: p.c }}>{p.t}</div>
              <div style={{ color: C.sec, fontSize: 13, marginTop: 6, lineHeight: 1.55 }}>{p.d}</div>
            </Panel>
          </div>
        ))}
      </div>

      <div className="g3" style={{ marginBottom: 16 }}>
        <Panel delay={0.1}><Label>Stack</Label><div style={{ fontSize: 13, color: C.sec, marginTop: 10, lineHeight: 1.9, fontFamily: MONO }}>Python · LightGBM<br />SQLite · Alpaca API<br />GitHub Actions CI<br />Next.js + Recharts</div></Panel>
        <Panel delay={0.14}><Label>Safety Layers</Label><div style={{ fontSize: 13, color: C.sec, marginTop: 10, lineHeight: 1.9 }}>Broker reconciliation<br />−5% circuit breaker<br />Correlation filter<br />Data-quality gate</div></Panel>
        <Panel delay={0.18}><Label>Why a Snapshot?</Label><div style={{ fontSize: 12.5, color: C.sec, marginTop: 10, lineHeight: 1.55 }}>This public site reads a daily JSON export, never the live broker connection — so real data is shown without exposing any API keys or account access.</div></Panel>
      </div>

      <Panel delay={0.22}>
        <Label>Full Glossary</Label>
        <div className="g2" style={{ gap: 14, marginTop: 14 }}>
          {glossOrder.map((k) => (
            <div key={k} style={{ paddingBottom: 12, borderBottom: `1px solid ${C.line}` }}>
              <div style={{ color: C.lime, fontSize: 13, fontWeight: 700 }}>{G[k].t}</div>
              <div style={{ color: C.sec, fontSize: 12.5, marginTop: 4, lineHeight: 1.5 }}>{G[k].d}</div>
            </div>
          ))}
        </div>
      </Panel>
    </>
  );
}
