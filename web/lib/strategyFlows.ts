// strategyFlows.ts — the decision pipeline for each strategy, authored from the
// live strategy code in src/strategies/*.py and config/trading_config.yaml.
// Rendered as an animated left-to-right flow by components/viz/StrategyFlow.tsx
// so a strategy reads as a sequence of explained steps, not a black box.

export type FlowKind =
  | "scan"
  | "gate"
  | "signal"
  | "filter"
  | "rank"
  | "entry"
  | "hold"
  | "exit";

export interface FlowRule {
  when: string; // the condition (the "before")
  then: string; // what the bot does (the "after")
}

export interface FlowStep {
  kind: FlowKind;
  title: string;
  detail?: string;
  rules?: FlowRule[]; // used by entry/exit nodes to show condition → action
}

// What each KIND of stage does, in general — shown in the click-through detail
// panel so the pipeline reads as cause → effect, not just labels.
export const KIND_INFO: Record<FlowKind, string> = {
  scan: "Every run starts here: pull fresh prices and indicators for every symbol in the universe.",
  gate: "A gate is a yes/no precondition. If it fails, the strategy does nothing for that name today — no signal is even generated.",
  signal: "The core trigger. When this condition fires, the strategy PROPOSES a trade — but the proposal still has to clear the filters, the risk funnel and the cash/heat caps before it becomes an order.",
  filter: "A filter trims weak or risky proposals so only high-quality signals proceed.",
  rank: "Instead of fixed thresholds, the strategy scores and ranks every candidate, then acts on only the best few.",
  entry: "When a proposal clears every check, the engine places the order at the next market open and sets the stop-loss.",
  hold: "While a position is open it is re-evaluated against the exit rules on every single run.",
  exit: "The position is closed the moment ANY one exit rule fires — whichever comes first.",
};

// Plain-English definitions for the jargon a step mentions. The detail panel
// auto-surfaces any whose key appears in the step's text, so a click explains
// exactly what e.g. "RSI" or "golden cross" means.
export const TERMS: Record<string, { t: string; d: string }> = {
  "RSI": { t: "RSI (Relative Strength Index)", d: "A 0–100 momentum gauge. Below ~30 means the stock has fallen hard recently (‘oversold’ — often due a bounce); above ~70 means it has run up hard (‘overbought’)." },
  "SMA": { t: "SMA (Simple Moving Average)", d: "The average closing price over the last N days. The 100-day SMA is a slow trend line: price above it = broad uptrend." },
  "VWAP": { t: "VWAP", d: "Volume-weighted average price — the average price paid recently, weighting heavier-volume days more. ‘Near VWAP’ means you’re buying close to what everyone else paid, not chasing." },
  "Bollinger": { t: "Bollinger Bands", d: "A band drawn 2 standard deviations above/below a 20-day average. A close above the UPPER band is an unusually strong move — a breakout." },
  "ATR": { t: "ATR (Average True Range)", d: "A measure of how much a stock typically moves in a day. Stops are set as a multiple of ATR so a calm stock gets a tight stop and a wild one gets room to breathe." },
  "ADX": { t: "ADX", d: "Trend-strength meter (0–100). Above ~20 means a real trend is in place rather than choppy sideways noise." },
  "golden cross": { t: "Golden Cross", d: "When the fast 20-day average crosses ABOVE the slow 50-day average — a classic ‘an uptrend just started’ signal." },
  "death cross": { t: "Death Cross", d: "The opposite of a golden cross: the 20-day average drops below the 50-day — a ‘trend is rolling over’ exit signal." },
  "z-score": { t: "Z-score", d: "How many standard deviations a value is from its average. A pair spread at z = −1.5 is unusually stretched and statistically due to snap back." },
  "cointegrated": { t: "Cointegration", d: "Two stocks whose prices move together over the long run, so the gap between them reliably mean-reverts. The basis for pairs trading." },
  "12-1 momentum": { t: "12-1 Momentum", d: "Return from 12 months ago up to 1 month ago. Skipping the most recent month avoids the short-term ‘what went up last month tends to dip’ reversal effect." },
  "VIX": { t: "VIX", d: "The market’s ‘fear gauge’ of expected volatility. When it’s high the cash sweep parks less in stock to keep risk down." },
  "Bollinger Band": { t: "Bollinger Bands", d: "A band 2 standard deviations around a 20-day average; a close above the upper band flags an unusually strong breakout." },
  "earnings": { t: "Post-Earnings Drift", d: "After a positive earnings surprise, a stock tends to keep drifting up for weeks — the market underreacts at first. This strategy rides that drift." },
  "VADER": { t: "VADER sentiment", d: "A rule-based analyzer that scores news headlines from negative to positive (0–1). Used as a context tilt, not a standalone signal." },
};

// Keyed by the strategy `key` in the snapshot. Every key the dashboard can show
// has a flow; StrategyFlow falls back to the edge text if one is ever missing.
export const STRATEGY_FLOWS: Record<string, FlowStep[]> = {
  rsi_mean_reversion: [
    { kind: "scan", title: "Scan universe", detail: "Watch every symbol each morning" },
    { kind: "gate", title: "Uptrend gate", detail: "Only names above their 100-day average (SMA-100)" },
    { kind: "signal", title: "Oversold signal", detail: "RSI(14) drops below 35, then starts turning back up" },
    { kind: "filter", title: "Confirm", detail: "Require a volume spike and price near its 20-day VWAP" },
    { kind: "entry", title: "Buy", rules: [{ when: "all of the above true", then: "BUY · stop 2.5× ATR below entry" }] },
    { kind: "hold", title: "Hold", detail: "Up to 20 trading days for the bounce" },
    {
      kind: "exit",
      title: "Exit (first to hit)",
      rules: [
        { when: "RSI(14) > 55", then: "SELL · bounce captured" },
        { when: "20 days elapse", then: "SELL · time exit" },
        { when: "price hits ATR stop", then: "SELL · risk control" },
      ],
    },
  ],

  ma_crossover: [
    { kind: "scan", title: "Scan universe", detail: "Watch every symbol each morning" },
    { kind: "gate", title: "Market & trend gate", detail: "SPY above its 50-day SMA, and ADX > 20 (trending, not choppy)" },
    { kind: "signal", title: "Golden cross", detail: "20-day SMA crosses above the 50-day SMA (within last 5 days)" },
    { kind: "filter", title: "Participation", detail: "Volume ratio > 0.8 confirms the move" },
    { kind: "entry", title: "Buy", rules: [{ when: "golden cross confirmed", then: "BUY · trailing ATR ratchet stop" }] },
    { kind: "hold", title: "Hold", detail: "Ride the trend up to 30 trading days" },
    {
      kind: "exit",
      title: "Exit (first to hit)",
      rules: [
        { when: "death cross (20 SMA < 50 SMA)", then: "SELL · trend over" },
        { when: "30 days elapse", then: "SELL · time exit" },
        { when: "trailing stop hit", then: "SELL · risk control" },
      ],
    },
  ],

  volatility_breakout: [
    { kind: "scan", title: "Scan universe", detail: "Watch every symbol each morning" },
    { kind: "signal", title: "Breakout", detail: "Price closes above the upper Bollinger Band" },
    { kind: "filter", title: "Volume confirm", detail: "Breakout must come on elevated volume (real momentum, not noise)" },
    { kind: "entry", title: "Buy", rules: [{ when: "breakout confirmed", then: "BUY · ATR stop" }] },
    { kind: "hold", title: "Hold", detail: "Up to 15 trading days" },
    {
      kind: "exit",
      title: "Exit (first to hit)",
      rules: [
        { when: "price falls back to the middle band", then: "SELL · momentum faded" },
        { when: "profit target hit", then: "SELL · take profit" },
        { when: "15 days elapse", then: "SELL · time exit" },
      ],
    },
  ],

  factor_momentum: [
    { kind: "scan", title: "Scan universe", detail: "Watch every symbol each morning" },
    {
      kind: "rank",
      title: "Score 8 factors",
      detail: "60-day momentum, low-vol quality, RSI reversion, volume, excess return vs SPY, sector strength, fundamental quality (ROE/debt) & value (1/PE)",
    },
    { kind: "rank", title: "Rank & select", detail: "Buy the top-ranked names (top quintile, ~3 stocks)" },
    { kind: "entry", title: "Buy", rules: [{ when: "stock is top-ranked", then: "BUY · sized by conviction" }] },
    { kind: "hold", title: "Hold & re-rank", detail: "Hold ~20 trading days, then re-score" },
    {
      kind: "exit",
      title: "Exit",
      rules: [
        { when: "drops out of the top rank", then: "SELL · rotate to a stronger name" },
        { when: "trailing stop hit", then: "SELL · risk control" },
      ],
    },
  ],

  earnings_drift: [
    { kind: "scan", title: "Scan earnings", detail: "From the earnings calendar (price-proxy fallback if stale)" },
    { kind: "signal", title: "Positive surprise", detail: "Stock beat earnings inside the post-report window (or: volume spike + abnormal up-move)" },
    { kind: "entry", title: "Buy", rules: [{ when: "beat inside entry window", then: "BUY · ride the drift" }] },
    { kind: "hold", title: "Hold the drift", detail: "Beats keep drifting up for weeks (~40-day target)" },
    {
      kind: "exit",
      title: "Exit (first to hit)",
      rules: [
        { when: "+20% profit target", then: "SELL · take profit" },
        { when: "-10% stop-loss", then: "SELL · cut loss" },
        { when: "drift window expires", then: "SELL · time exit" },
        { when: "negative re-surprise", then: "SELL · thesis broken" },
      ],
    },
  ],

  dual_momentum: [
    { kind: "scan", title: "Scan universe", detail: "Watch every symbol each morning" },
    { kind: "signal", title: "12-1 momentum", detail: "Return from 12 months ago to 1 month ago (skip last month to avoid reversal)" },
    { kind: "gate", title: "Absolute filter", detail: "Stock's own 12-1 return > 0 AND SPY's > 0 (stay out of bear markets)" },
    { kind: "rank", title: "Rank & select", detail: "Buy the top 5 by momentum (confidence scaled by rank)" },
    { kind: "entry", title: "Buy", rules: [{ when: "top-ranked & filters pass", then: "BUY" }] },
    { kind: "hold", title: "Hold w/ hysteresis", detail: "Min 5 / soft 35 / max 70 days; keep while still in the top band" },
    {
      kind: "exit",
      title: "Exit (first to hit)",
      rules: [
        { when: "falls out of the top-2N band", then: "SELL · rotate" },
        { when: "70-day ceiling", then: "SELL · time exit" },
        { when: "trailing stop hit", then: "SELL · risk control" },
      ],
    },
  ],

  sector_rotation: [
    { kind: "rank", title: "Rank sectors", detail: "Rank the 7 sector ETFs by 20-day return" },
    { kind: "signal", title: "Pick leaders", detail: "Select the top 2 outperforming sectors" },
    { kind: "filter", title: "Best stock", detail: "Strongest stock per sector by 20-day return (not already held)" },
    { kind: "entry", title: "Buy", rules: [{ when: "sector leader chosen", then: "BUY" }] },
    { kind: "hold", title: "Hold", detail: "~20 trading days, then rotate" },
    {
      kind: "exit",
      title: "Exit",
      rules: [
        { when: "+12% profit target", then: "SELL · take profit" },
        { when: "time limit / re-rank", then: "SELL · rotate to new leaders" },
      ],
    },
  ],

  ml_momentum: [
    { kind: "scan", title: "Scan universe", detail: "Watch every symbol each morning" },
    { kind: "filter", title: "Build 12 features", detail: "RSI, returns, volatility, volume, trend, ATR, ADX… per stock" },
    { kind: "signal", title: "Model prediction", detail: "Gradient-boosting model predicts P(stock beats SPY over next 5 days)" },
    { kind: "filter", title: "Threshold", detail: "Confidence ≥ threshold and in the top quantile (max 2 new positions/day)" },
    { kind: "entry", title: "Buy", rules: [{ when: "model is confident", then: "BUY" }] },
    { kind: "hold", title: "Hold ≥ 5 days", detail: "Don't dump a loser early if the model still likes it" },
    {
      kind: "exit",
      title: "Exit (first to hit)",
      rules: [
        { when: "day 5 and profitable", then: "SELL · take it" },
        { when: "model turns bearish (<0.5)", then: "SELL" },
        { when: "15-day ceiling", then: "SELL · time exit" },
      ],
    },
  ],

  news_sentiment: [
    { kind: "scan", title: "Fetch news", detail: "Pull recent headlines per symbol (Google News RSS)" },
    { kind: "signal", title: "Score sentiment", detail: "VADER sentiment of the headlines → a 0–1 score" },
    { kind: "filter", title: "Threshold", detail: "Score ≥ buy threshold (~0.60)" },
    { kind: "entry", title: "Buy", rules: [{ when: "sentiment is bullish", then: "BUY" }] },
    { kind: "hold", title: "Hold ~7 days" },
    {
      kind: "exit",
      title: "Exit (first to hit)",
      rules: [
        { when: "sentiment drops ≤ sell threshold", then: "SELL" },
        { when: "14-day max hold", then: "SELL · time exit" },
      ],
    },
  ],

  pairs_trading: [
    { kind: "scan", title: "Scan pairs", detail: "Cointegrated same-sector pairs (data-driven screen)" },
    { kind: "signal", title: "Spread z-score", detail: "Z-score of the price ratio over 60 days" },
    {
      kind: "entry",
      title: "Enter pair (market-neutral)",
      rules: [{ when: "z < −1.5 (spread stretched)", then: "BUY the laggard + SHORT the leader" }],
    },
    { kind: "hold", title: "Hold for reversion" },
    {
      kind: "exit",
      title: "Close (first to hit)",
      rules: [
        { when: "z reverts to ±0.3", then: "CLOSE both legs · reverted" },
        { when: "max hold reached", then: "CLOSE · force exit" },
      ],
    },
  ],

  cash_sweep: [
    { kind: "scan", title: "After strategies trade", detail: "Whatever cash the strategies didn't deploy" },
    { kind: "gate", title: "VIX throttle", detail: "Park less when volatility is high (manage beta risk)" },
    {
      kind: "entry",
      title: "Park in SPY",
      rules: [{ when: "idle cash above threshold", then: "BUY SPY · earn market return on idle cash" }],
    },
    { kind: "hold", title: "Hold SPY", detail: "Until the cash is needed" },
    {
      kind: "exit",
      title: "Release",
      rules: [
        { when: "a strategy needs capital", then: "SELL SPY · free the cash" },
        { when: "daily rebalance", then: "trim / top-up the sweep" },
      ],
    },
  ],
};
