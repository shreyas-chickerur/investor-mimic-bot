// ============================================================
// glossary.ts — plain-English definitions for every term.
// Used by the <Info> tooltip and the System page glossary.
// Ported verbatim from the approved demo (MimicDashboard.jsx).
// Keys map to the term; { t: title, d: definition }.
// ============================================================

type Term = { t: string; d: string };
export const glossary: Record<string, Term> = {
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
