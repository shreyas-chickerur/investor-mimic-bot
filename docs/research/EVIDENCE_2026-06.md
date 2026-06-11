# Strategy evidence — 2026-06 (decision run)

Out-of-sample walk-forward evidence behind the 2026-06 strategy dispositions.
Procedure: `docs/research/EVIDENCE_RUNBOOK.md`. Harness: production-parity
backtester (gates/stops from trading_config.yaml, ratchet stop replicated),
ML leakage fixes, Phase-4 exit policy — commits `75b81db..` (cited commit
includes the dual-momentum addition and the 400-day lookback window).

## Runs

```bash
# primary: 36 symbols × 15yr (2011–2026), ~19 OOS windows
run_backtest.py --per-strategy --exclude MLMomentumStrategy \
  --data data/extended_historical_data.csv --years 12 --train-days 504 --test-days 126 --step-days 126
# recent regime: 43 symbols × 2yr (has SPY + sector ETFs), 3 OOS windows
run_backtest.py --per-strategy --exclude MLMomentumStrategy \
  --years 2 --train-days 252 --test-days 63 --step-days 63
# pairs: scripts/research/validate_pairs.py (both datasets)
# dual momentum: same two runs, all other strategies excluded
```

**Caveats**: the 15yr file has NO SPY or sector ETFs → every SPY>SMA50 uptrend
gate was permissive (strategies traded through 2018/2020/2022 bears — harsh,
not flattering), and Sector Rotation is untestable on it. Single-strategy runs
use relaxed heat (0.80) to measure signal quality; CAGR is therefore not the
headline number — Sharpe/PF/DD are.

## Gates

OOS Sharpe ≥ 0.5 · max DD ≤ 25% · ≥ 30 closed trades · PF ≥ 1.1 ·
≥ 50% OOS windows positive. Pairs additionally: EG cointegration at 5% AND
half-life < 20d AND sim PF ≥ 1.1 over ≥ 10 round-trips.

## Results

| Strategy | 15y Sharpe | 15y DD | 15y trades | 15y PF | 15y win+ | 2y Sharpe | 2y PF | Verdict |
|---|---|---|---|---|---|---|---|---|
| Dual Momentum (new) | **1.20** | −7.3% | 590 | **2.06** | 78.9% | 1.45 | 2.84 | **PASS — enable** |
| MA Crossover | 1.19 | −5.6% | 843 | 1.78 | 84.2% | 0.33 ✗ | 1.15 | PASS primary / FAIL recent → keep on probation (10%) |
| Volatility Breakout | 1.17 | −4.2% | 1314 | 1.57 | 94.7% | 1.57 | 1.44 | **PASS** (probation cap — weak prior) |
| Factor Momentum | 1.16 | −4.7% | 529 | 1.67 | 84.2% | 1.76 | 2.45 | **PASS — top cap** (also live +$714) |
| RSI Mean Reversion | 0.64 | −6.2% | 494 | 1.43 | 63.2% | 0.84 | 1.58 | **PASS** |
| Earnings Drift | 0.59 | −23.7% | 782 | 1.40 | 73.7% | 1.37 | 1.69 | **PASS** (DD near limit — monitor) |
| Sector Rotation | n/a (no ETFs) | — | 0 | — | — | 2.38 | 2.73 | 25 trades < 30 gate → probation (10%), UNVALIDATED |
| News Sentiment | (invalid) | — | 781 | — | — | (invalid) | — | **DISABLE** |
| Pairs Trading | — | — | — | — | — | — | — | **DISABLE** (0/5 pairs pass) |
| ML Momentum | — | — | — | — | — | — | — | **DISABLE** (purged-OOS < 52% × 91 windows) |

### Why News Sentiment's numbers are struck

The strategy fetches **live** Google News RSS inside `generate_signals` — in a
backtest that applies *today's* sentiment scores to 15 years of historical
prices. Its 781 "trades" are lookahead artifacts, not evidence. The strategy
is structurally unvalidatable offline; with a weak prior and a tiny live
sample, it is disabled.

### Pairs detail (validate_pairs.py)

| Pair | EG tstat (15y) | half-life | sim PF | verdict |
|---|---|---|---|---|
| JPM/BAC | no overlapping history (BAC absent until 2026-06) | — | — | FAIL |
| AAPL/MSFT | −3.10 | 141.6d | 0.99 | FAIL |
| XOM/CVX | no overlapping history | — | — | FAIL |
| V/MA | −3.36 (cointegrated) | 100.1d | 1.19 | FAIL (half-life 5× the 20d max hold) |
| ABBV/MRK | −2.45 | 194.3d | 0.57 | FAIL |

Even the one cointegrated pair mean-reverts over ~100 days while the strategy
force-exits at 20 — the economics are structurally broken at this horizon.

### ML Momentum detail

After removing the `future_return_5d` label path and adding purge+embargo to
the walk-forward split, the model reported "near-random on OOS data"
(purged-OOS < 52%) on **91 consecutive** training windows across 15 years
(log: 2026-06-11, preserved during the run). Gate was purged-OOS ≥ 54% AND
parity Sharpe ≥ 0.5; the first condition fails conclusively.

## Dispositions applied (config/trading_config.yaml)

- `disabled: true` → news_sentiment, pairs_trading, ml_momentum (open
  positions wind down automatically via the engine's inactive-strategy sweep).
- `backtest_sharpe_priors` ← measured 15y parity Sharpes (dual_momentum 1.20,
  ma_crossover 1.19, volatility_breakout 1.17, factor_momentum 1.16,
  rsi_mean_reversion 0.64, earnings_drift 0.59; sector_rotation 0.50
  judgment value — 2y-only, under-sampled).
- `allocation_overrides` re-tiered: factor_momentum 0.30 · earnings_drift
  0.25 · rsi_mean_reversion 0.25 · dual_momentum 0.15 · volatility_breakout
  0.15 · ma_crossover 0.10 (2y regime fail) · sector_rotation 0.10.
- `validation_status`: OOS_VALIDATED for the six gate-passers; UNVALIDATED
  for sector_rotation (sample) and the three disabled strategies (ML downgraded
  from its previously incorrect OOS_VALIDATED).

## Parameter plateaus

Deferred deliberately: this run already changes exits (Phase 4) and the
strategy mix. Tune one variable at a time — re-run the plateau grids
(RUNBOOK §commands) at the next quarterly validation against live paper
results from this configuration.
