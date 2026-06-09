// types.ts — mirrors snapshot.types.ts exactly.
// The web app reads this; the export script writes to it.

export type Regime = "LOW_VOL" | "NORMAL" | "HIGH_VOL";
export type SentimentLabel = "BULLISH" | "NEUTRAL" | "BEARISH";
export type SignalStatus = "EXECUTED" | "FILTERED" | "DEFERRED";
export type TradeSide = "BUY" | "SELL";

export interface Snapshot {
  meta: {
    generatedAt: string;
    tradingDate: string;
    runId: string;
    runNumber: number | null;
    paper: true;
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
    spyTodayPct: number | null;
    vsSpyPct: number | null;
    sharpe: number | null;
    sortino: number | null;
    maxDrawdownPct: number | null;
    volatilityPct: number | null;
    winRatePct: number | null;
    profitFactor: number | null;
    closedTradesCount: number;
    regime: Regime;
    heatCapPct: number;
    exposurePct: number;
  };

  equityCurve: Array<{ date: string; value: number; spy: number | null }>;

  strategies: Array<{
    key: string;
    name: string;
    allocationPct: number;
    returnPct: number | null;
    sharpe: number | null;
    sortino: number | null;
    profitFactor: number | null;
    maxDrawdownPct: number | null;
    tradesCount: number;
    winRatePct: number | null;
    holdPeriod: string;
    healthScore: number;
    edgeTechnical: string;
    edgePlain: string;
    factorProfile: {
      momentum: number;
      quality: number;
      reversion: number;
      volume: number;
      volatility: number;
    };
    backtestSharpe: number | null;
    status: "ACTIVE" | "WATCHING" | "DISABLED";
    note: string | null;
  }>;

  positions: Array<{
    symbol: string;
    strategy: string;
    shares: number;
    value: number;
    costBasis: number;
    unrealizedPlPct: number | null;
    unrealizedPlUsd: number | null;
    beta: number | null;
    atrStop: number | null;
    sentimentScore: number;
    sentimentLabel: SentimentLabel;
    detail: {
      priceSpark: number[];
      confidence: number | null;
      sentimentMultiplier: string;
      whyHeld: string;
      lots: Array<{ date: string; shares: number; price: number }>;
      news: Array<{ headline: string; source: string; score: number }>;
    };
  }>;

  trades: Array<{
    date: string;
    symbol: string;
    strategy: string;
    side: TradeSide;
    shares: number;
    entry: number;
    exit: number;
    realizedPlPct: number;
    realizedPlUsd: number;
    exitReason: string;
  }>;

  signals: {
    funnel: Array<{ stage: string; count: number; note: string }>;
    explorer: Array<{
      symbol: string;
      strategy: string;
      confidence: number | null;
      sentimentScore: number;
      multiplier: string;
      status: SignalStatus;
      reason: string;
    }>;
  };

  analytics: {
    drawdown: Array<{ date: string; ddPct: number | null }>;
    rollingSharpe: Array<{ date: string; sharpe: number }>;
    monthlyReturns: Array<{ month: string; returnPct: number | null }>;
    returnDistribution: Array<{ bucket: string; count: number }>;
    strategyCorrelation: {
      labels: string[];
      matrix: Array<Array<number | null>>;
    };
    backtestVsLive: Array<{
      strategy: string;
      backtestSharpe: number | null;
      liveSharpe: number | null;
    }>;
    bestMonth: { month: string; returnPct: number } | null;
    worstMonth: { month: string; returnPct: number } | null;
  };

  health: {
    markers: Array<{
      key: "broker" | "data" | "quality" | "breaker" | "correlation" | "regime";
      label: string;
      ok: boolean;
      neutral?: boolean;
      detail: string;
      autoAttempted?: boolean;
      autoResolved?: boolean;
      remaining?: number;
    }>;
    syncWorkflowUrl: string;
  };
}
