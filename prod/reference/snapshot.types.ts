// ============================================================
// snapshot.types.ts — THE CONTRACT
// ------------------------------------------------------------
// This is the single source of truth for the JSON the Python export
// script writes (scripts/export_snapshot.py) AND the shape the Next.js
// app reads. If a field isn't here, the frontend doesn't render it.
// The export script must produce EXACTLY this shape. Where a value
// can't be computed yet, emit null (frontend must handle null), never
// omit the key.
//
// All money in USD numbers (not strings). All percentages as numbers
// where 6.2 means +6.2% (NOT 0.062). Dates ISO-8601 strings.
// ============================================================

export type Regime = "LOW_VOL" | "NORMAL" | "HIGH_VOL";
export type SentimentLabel = "BULLISH" | "NEUTRAL" | "BEARISH";
export type SignalStatus = "EXECUTED" | "FILTERED" | "DEFERRED";
export type TradeSide = "BUY" | "SELL";

export interface Snapshot {
  meta: {
    generatedAt: string;      // ISO timestamp of the export run
    tradingDate: string;      // ISO date the data represents
    runId: string;            // broker_state run_id
    runNumber: number | null; // GitHub Actions run number if available
    paper: true;              // always true; surfaced as a PAPER badge
    schemaVersion: 1;
  };

  portfolio: {
    totalValue: number;
    cash: number;
    positionsCount: number;
    todayChangeUsd: number;
    todayChangePct: number;
    allTimePnlUsd: number;
    allTimePnlPct: number;
    // benchmark
    spyTodayPct: number | null;     // SPY daily % (fetch if not already stored — see prompt)
    vsSpyPct: number | null;        // portfolio today − SPY today
    // risk-adjusted (null until enough history)
    sharpe: number | null;
    sortino: number | null;
    maxDrawdownPct: number | null;
    volatilityPct: number | null;
    winRatePct: number | null;      // null if closedTrades < 20 (small-sample guard)
    profitFactor: number | null;    // null if closedTrades < 20
    closedTradesCount: number;
    // regime + exposure
    regime: Regime;
    heatCapPct: number;             // 50/40/30 by regime
    exposurePct: number;            // current deployed %
  };

  // 252-point (max) daily equity curve for time-range slicing (1W/1M/3M/YTD/ALL)
  equityCurve: Array<{ date: string; value: number; spy: number | null }>;

  strategies: Array<{
    key: string;                    // stable id
    name: string;                   // "ML Momentum"
    allocationPct: number;          // Sharpe-weighted, 10–40 bounded
    returnPct: number;              // strategy P&L %
    sharpe: number | null;
    sortino: number | null;
    profitFactor: number | null;
    maxDrawdownPct: number | null;
    tradesCount: number;
    winRatePct: number | null;
    holdPeriod: string;             // "5d", "≤20d"
    healthScore: number;            // 0–100 from StrategyHealthScorer
    edgeTechnical: string;          // advanced-mode description
    edgePlain: string;              // simple-mode plain-English
    // radar 0–100 per factor for the "factor profile" chart
    factorProfile: { momentum: number; quality: number; reversion: number; volume: number; volatility: number };
    // backtest comparison
    backtestSharpe: number | null;
    status: "ACTIVE" | "WATCHING" | "DISABLED";
    note: string | null;            // e.g. "Low trade count: 3 in 30d (need 5)"
  }>;

  positions: Array<{
    symbol: string;
    strategy: string;
    shares: number;
    value: number;
    costBasis: number;
    unrealizedPlPct: number;
    unrealizedPlUsd: number;
    beta: number | null;
    atrStop: number | null;
    sentimentScore: number;         // 0–1
    sentimentLabel: SentimentLabel;
    // drill-down detail (expandable row)
    detail: {
      priceSpark: number[];         // recent closes, ~8–30 points
      confidence: number | null;    // strategy's own P estimate
      sentimentMultiplier: string;  // "×1.15" | "×0.80" | "×1.00"
      whyHeld: string;              // the reasoning sentence(s)
      lots: Array<{ date: string; shares: number; price: number }>;
      news: Array<{ headline: string; source: string; score: number }>;
    };
  }>;

  trades: Array<{                   // closed-trade ledger
    date: string;
    symbol: string;
    strategy: string;
    side: TradeSide;
    shares: number;
    entry: number;
    exit: number;
    realizedPlPct: number;
    realizedPlUsd: number;
    exitReason: string;             // "12% target", "ATR stop hit", "5-day hold"
  }>;

  signals: {
    funnel: Array<{ stage: string; count: number; note: string }>; // ordered, scanned → executed
    explorer: Array<{
      symbol: string;
      strategy: string;
      confidence: number;
      sentimentScore: number;
      multiplier: string;
      status: SignalStatus;
      reason: string;               // why it fired / was filtered / deferred
    }>;
  };

  analytics: {
    drawdown: Array<{ date: string; ddPct: number }>;          // ≤ 0 underwater curve
    rollingSharpe: Array<{ date: string; sharpe: number }>;
    monthlyReturns: Array<{ month: string; returnPct: number }>;
    returnDistribution: Array<{ bucket: string; count: number }>;
    strategyCorrelation: { labels: string[]; matrix: number[][] }; // NxN, 0–1
    backtestVsLive: Array<{ strategy: string; backtestSharpe: number; liveSharpe: number }>;
    bestMonth: { month: string; returnPct: number } | null;
    worstMonth: { month: string; returnPct: number } | null;
  };

  health: {
    // x/y system-health markers (NOT performance stats)
    markers: Array<{
      key: "broker" | "data" | "quality" | "breaker" | "correlation" | "regime";
      label: string;
      ok: boolean;
      neutral?: boolean;            // regime marker: always counts healthy
      detail: string;               // plain-language status
      // remediation state mirrored from the workflow:
      autoAttempted?: boolean;
      autoResolved?: boolean;
      remaining?: number;
    }>;
    // derived by frontend: healthy = markers where ok||neutral; needsAction = any !ok && !neutral && !autoResolved
    syncWorkflowUrl: string;        // deep link for the one-click manual fix
  };
}
