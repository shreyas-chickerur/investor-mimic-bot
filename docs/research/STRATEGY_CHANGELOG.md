# Strategy changelog

The narrative companion to `config/strategy_experiments.yaml` (the
machine-readable registry the reviewer reads). Every change aimed at making a
strategy effective is logged here with its **hypothesis**, the **evidence
basis** (including web research), **measurable success criteria**, and the
**verdict** once reviewed. Nothing is enabled or abandoned without a verdict
that traces back to evidence for or against it.

## How this works

1. A change is implemented and registered as an experiment in
   `config/strategy_experiments.yaml` with falsifiable success criteria and a
   `review_date`.
2. `scripts/research/review_experiments.py` (run weekly by
   `.github/workflows/strategy_review.yml`, or `make strategy-review`) evaluates
   every **due** experiment against its criteria using the recorded result
   artifacts, assigns **validated / rejected / inconclusive**, emails the
   verdict, and writes it back into the registry.
3. A strategy is only re-enabled in `config/trading_config.yaml` after an
   experiment **validates** it. A `rejected` verdict records *why*, with the
   condition under which it's worth revisiting.

Verdict legend: ✅ validated (evidence FOR) · ❌ rejected (evidence AGAINST) ·
⏳ inconclusive (insufficient data yet).

---

## 2026-06-22 — initial experiment batch (the three disabled strategies)

Context: `docs/research/EVIDENCE_2026-06.md` disabled ML Momentum, News
Sentiment, and Pairs Trading. Rather than leave them off, each gets a concrete,
research-backed attempt with a tracked verdict.

### ⏳ EXP-2026-06-22-pairs-universe-screen — Pairs Trading

**Hypothesis.** The 5 hand-picked pairs failed because they weren't cointegrated
and/or mean-reverted far slower than the 20-day force-exit. Screening the whole
universe (same-sector, 1% Engle-Granger) for cointegration *and* aligning each
pair's max-hold to a multiple of its half-life will surface tradeable pairs.

**Evidence basis (research).**

- Half-life of mean reversion sets the correct lookback/hold horizon — "if the
  half-life is 20 days, a 5-day window won't capture the reversion." A 20-day
  force-exit on a 100-day half-life is the structural break that sank V/MA.
  (flare9xblog on half-life; Hudson & Thames *Introduction to Cointegration*.)
- Pairs alpha requires genuine long-run cointegration (Gatev, Goetzmann &
  Rouwenhorst 2006).
- Multiple comparisons: testing all C(n,2) pairs at 5% yields ~1-in-20 spurious
  pairs → restrict to **same-sector** candidates and select at the **1%**
  critical value.

**Change.** `scripts/research/screen_pairs.py` (writes `data/pairs_universe.json`);
the strategy now loads screened pairs with per-pair, half-life-aligned max-hold;
`validate_pairs.simulate_pair` parametrised by hold/lookback/thresholds.

**Result so far (2026-06-22 run on 36-symbol × 15y data).** Of 92 same-sector
candidate pairs, only **6 cointegrate at 5%** (≈ the chance false-positive rate)
and **1 at 1%** (COST/KO). Every cointegrated pair's half-life is **47–112 days**
(median 94) — far too slow for a weeks-horizon strategy. **0 pairs** pass the
gates. Success criterion (`pairs.passing_count ≥ 2`) currently **fails**.

**Disposition / revisit condition.** Stay **disabled**. The strategy is now
data-driven, so it auto-activates if a future, broader universe (more
within-sector peers, or sector/industry ETF pairs which tend to revert faster)
yields ≥ 2 qualifying pairs. Re-run `screen_pairs.py` after any universe
expansion. Review date **2026-07-22**.

### ⏳ EXP-2026-06-22-ml-orthogonal-features — ML Momentum

**Hypothesis.** The 12 production features are mostly collinear single-name
technicals. Adding orthogonal signal — cross-sectional return ranks, distance
from the 252-day high, momentum acceleration — lifts purged out-of-sample
accuracy above the 54% economic-edge gate.

**Evidence basis (research).**

- López de Prado, *Advances in Financial Machine Learning*: purged K-fold +
  embargo is the correct OOS estimator (already used here); cross-sectional and
  structural features carry signal single-name technicals don't.
- *Ten Reasons Most ML Funds Fail* (López de Prado / GARP): collinear features
  and leakage produce illusory accuracy; honest purged-OOS is near coin-flip
  for naive technical sets — matching our 12-feature result.

**Change.** `scripts/research/eval_ml_features.py` — a purged + embargoed
walk-forward measuring mean OOS accuracy for baseline vs enriched feature sets
(sklearn GBM, the strategy's own non-LightGBM fallback, for reproducibility).

**Result so far.** 2-year data (44 symbols, 11 folds): baseline mean OOS acc
**0.5005**, enriched **0.505** (Δ **+0.45%**). The orthogonal features help, but
the enriched set is still far below the **0.54** gate and the lift is below the
**+1%** improvement threshold. (A 15-year run over the 36-symbol extended set
can be produced with `make eval-ml-features` pointed at
`data/extended_historical_data.csv`; it is slow — ~160 walk-forward folds — and
not required for the verdict, since the 2-year purged-OOS result already misses
the gate.)

**Disposition / revisit condition.** Stay **disabled**. The features move the
needle the right direction but not enough to clear the gate — consistent with
the research that naive technical ML has no daily-horizon edge. Next escalation
if revisited: meta-labeling (a secondary model deciding *whether to act* on a
primary momentum signal) and genuinely exogenous features (fundamentals,
analyst revisions). Review date **2026-07-06**.

### ⏳ EXP-2026-06-22-news-pit-recording — News Sentiment

**Hypothesis.** News Sentiment is unvalidatable offline because it scores LIVE
RSS inside `generate_signals` (look-ahead). Recording point-in-time sentiment
daily builds a leak-free history that can be backtested with a t+1 execution lag
once enough has accumulated.

**Evidence basis (research).**

- Look-ahead bias in sentiment return prediction is well documented; the
  mitigation is **point-in-time capture + a reporting/execution lag**
  (arXiv:2309.17322; QuantConnect research guide).
- Backtest sentiment with a **t+1 execution lag** and point-in-time data to
  avoid look-ahead and survivorship bias (fortraders; QuantConnect).

**Change.** New `sentiment_history` table (`src/core/database.py`) +
`scripts/record_sentiment.py`, wired into the daily workflow so per-symbol VADER
sentiment is captured with its as-of date every run.

**Result so far.** Accumulating. Success criterion: ≥ **60** distinct as-of
dates of recorded sentiment (~3 trading months) before an offline backtest is
attempted. Review date **2026-09-22**.

**Disposition.** Stay **disabled** until the history matures; this is the only
one of the three with a realistic path to validation, but it is gated on data
that can only be collected forward in time.
