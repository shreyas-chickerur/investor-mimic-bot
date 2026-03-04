# Strategy Reference Guide

*Last updated: 2026-03-03*

## Active Strategies (4 canonical)

All 4 strategies run every trading day at 4:15 PM ET via `src/core/execution_engine.py`.
Each is independent — separate capital, separate positions, separate P&L tracking.

---

## 1. RSI Mean Reversion (`strategy_rsi_mean_reversion.py`)

**Edge:** Buy oversold stocks that are turning up; hold until recovery.

| Parameter | Value |
|-----------|-------|
| Entry RSI threshold | < 40 |
| Entry slope | > 0 (RSI turning up) |
| Exit: mean reversion | RSI > 55 |
| Exit: time limit | 20 trading days |
| Stop loss | 2.5× ATR (via StopLossManager) |
| Max position | 10% of strategy capital |

**Key columns required:** `rsi`, `atr_20`, `close`

> **Bug history:** The `vwap` column in `training_data.csv` is a trailing 20-day
> VWAP (always ~70% of current close). A previous `price >= vwap` exit fired on
> every position causing zero holding periods. **This exit was removed.** Never
> add a `price >= vwap` exit back unless vwap is a same-day intraday VWAP.

---

## 2. ML Momentum (`strategy_ml_momentum.py`)

**Edge:** Logistic Regression predicts P(5-day positive return) using 12 features.

| Parameter | Value |
|-----------|-------|
| Model | LogisticRegression, C=0.1, `class_weight='balanced'` |
| Min confidence | 0.52 (config: `strategies.ml_momentum.min_confidence`) |
| Features | RSI, RSI slope, returns (5/20/60d), volatility, volume_ratio, price_to_sma20/50, ATR%, ADX |
| Training target | `future_return_5d > 0.005` (class 1) |
| Hold period | 5 days |
| Retrain | Daily (controlled by `_train_date`) |

**Key columns required:** `rsi`, `returns_5d`, `returns_20d`, `returns_60d`, `volatility_20d`,
`volume_ratio`, `price_to_sma20`, `price_to_sma50`, `atr_20`, `adx`, `future_return_5d`

> **Bug history:** `min_confidence=0.55` blocked all signals (logistic regression
> on financial data rarely exceeds 0.55). Fixed to 0.52. `class_weight='balanced'`
> added to prevent majority-class bias.

---

## 3. Earnings Drift / PEAD (`strategy_earnings_drift.py`)

**Edge:** Post-earnings announcement drift — buy after positive earnings surprise, hold.

| Parameter | Value |
|-----------|-------|
| Volume spike | > 2× 20-day average |
| Return magnitude | > 2× 20-day volatility AND > 2% absolute |
| Direction | Positive return only (buys PEAD) |
| Hold period | 40 days |
| Stop loss | 2.5× ATR |

**Key columns required:** `close`, `volume`, `atr_20`

---

## 4. Factor Momentum (`strategy_factor_momentum.py`)

**Edge:** Cross-sectional ranking — buy the top 5 stocks by composite factor score.

| Factor | Weight | Description |
|--------|--------|-------------|
| Momentum | 40% | 55-day return (skips last 5d for reversal) |
| Quality | 25% | Low volatility + positive momentum |
| Mean-reversion | 20% | RSI in 25–45 range |
| Volume confirmation | 15% | Rising volume on up-moves |
| **Hold period** | | 20 days |

Scores are computed via **cross-sectional percentile ranking** (`DataFrame.rank(pct=True)`)
across the full universe. Each factor is ranked relative to all other stocks — not
normalized in isolation.

> **Bug history:** `_rank_normalize(sigmoid(value))` applied independently to each
> symbol compressed all scores to 0.50–0.65. "Top 5" selection was nearly random.
> Fixed to percentile ranking — correct approach for cross-sectional strategies.

---

## News Sentiment Layer (`src/utils/news_sentiment.py`)

All 4 strategies' signals pass through a news sentiment filter **after** the
correlation filter and **before** execution:

| Sentiment score | Action |
|----------------|--------|
| > 0.62 | Confidence × 1.15 (boost) |
| 0.38–0.62 | No change (neutral) |
| < 0.38 | Confidence × 0.80 (suppress) |
| < 0.25 + BUY | Signal dropped entirely |
| Any score + SELL | Signal always passes through |

**Implementation:** `yfinance` for headlines (free, no API key), `VADER` for
sentiment scoring. Results cached per calendar day. Fetched in parallel
(ThreadPoolExecutor).

---

## Signal Flow (in order)

```
Raw signals (each strategy)
  ↓ Regime filter (high-VIX reduces heat cap)
  ↓ Correlation filter (60-day rolling, reject >0.80)
  ↓ News sentiment filter (yfinance + VADER)
  ↓ Log to DB, assign signal_id
  ↓ Take top N (strategy.top_n, default 5)
  ↓ Portfolio risk check (heat cap, cash)
  ↓ Order submission (Alpaca paper)
  ↓ Fill verification
  ↓ Stop loss set (2.5× ATR)
```

---

## Debugging Zero Signals

```bash
# Preview today's signals without trading
make signals-check

# Check news sentiment for a few symbols
make news-test

# View last 50 log lines
make logs
```

Common causes of zero signals:
1. **Stale data** — run `make update-data` to refresh `training_data.csv`
2. **All RSI values neutral** — RSI < 40 AND slope > 0 is a strict conjunction
3. **Correlation filter blocking all pairs** — check log for `CORRELATION` rejections
4. **News dropping BUY signals** — check log for `NewsFilter: dropping BUY`
5. **Portfolio heat at cap** — check `total_exposure` in logs
