# Strategy evidence runbook

How to (re)generate the out-of-sample evidence that decides which strategies
get capital. The acceptance gates and the keep/fix/disable decision rules live
in `docs/research/EVIDENCE_<date>.md`; this file is the *procedure*.

## When to re-run

- **Quarterly** (first week of each quarter), and
- **Event-triggered**: when the 128-symbol universe accumulates ≥1 year of
  history for most names (backfill onboards 25/day from 2026-06; expect
  ~Q3-2026), re-run with `--data data/training_data.csv` to use the wider
  universe, and
- after any change to entry/exit logic or the backtester itself.

## Commands

```bash
# 1. Long-horizon evidence (36 symbols x 15yr; NO SPY/ETFs in this file —
#    uptrend gates are permissive and Sector Rotation cannot trade; judge
#    Sector Rotation on the 2yr run instead)
python3 scripts/run_backtest.py --per-strategy --exclude MLMomentumStrategy \
    --data data/extended_historical_data.csv --years 12 \
    --train-days 504 --test-days 126 --step-days 126

# 2. Recent-regime check (43+ symbols x 2yr; has SPY + sector ETFs)
python3 scripts/run_backtest.py --per-strategy --exclude MLMomentumStrategy \
    --years 2 --train-days 252 --test-days 63 --step-days 63

# 3. Pairs (backtester has no short support)
python3 scripts/research/validate_pairs.py            # 15yr
python3 scripts/research/validate_pairs.py --data data/training_data.csv

# 4. ML Momentum: gate on the purged walk-forward OOS accuracy logged during
#    training ("ML purged walk-forward OOS accuracy: X%"). Its daily retrain
#    makes full equity-curve backtests impractical (~4h); if the purged OOS
#    accuracy clears 54% consistently, run it through the backtester overnight
#    before granting capital.

# Parameter plateaus (gate-passers only; accept only if the WHOLE
# neighborhood passes, never a single best point):
python3 scripts/run_backtest.py --per-strategy --parity \
    --set strategies.rsi_mean_reversion.rsi_entry_threshold=30 ...
```

Artifacts land in `artifacts/backtest/` (untracked). After a decision run,
write `docs/research/EVIDENCE_<date>.md` with: the gates table, per-window
returns, pair stats, the exact commands, and the harness git SHA — then update
`config/trading_config.yaml` (`disabled`, `backtest_sharpe_priors`,
`allocation_overrides`, `validation_status`) citing that document.

## Acceptance gates (config `backtesting.*`)

OOS Sharpe ≥ 0.5 · max drawdown ≤ 25% · ≥ 30 closed trades ·
profit factor ≥ 1.1 · ≥ 50% of OOS windows positive.
Pairs additionally: Engle-Granger 5% cointegration AND half-life < 20 days.

## The evidence dataset

`data/extended_historical_data.csv` (36 symbols × 15yr, ~66MB) is gitignored —
it is NOT in a fresh clone. Recovery options, in order:

1. **Backup**: `research/extended_historical_data.csv.xz` on the `data`
   branch (one-time upload 2026-06-12). Restore:
   `git show origin/data:research/extended_historical_data.csv.xz | xz -d > data/extended_historical_data.csv`
2. **Regenerate** (premium Alpha Vantage key, ~10 min at 75 req/min):
   `python3 scripts/fetch_historical_data.py` with the symbol list from the
   backup's header. When regenerating, ALSO include SPY + the 13 sector ETFs
   and the full 128-symbol universe — that removes the two standing caveats
   (permissive uptrend gates, Sector Rotation untestable on 15y) and gives
   the next quarterly run a strictly better evidence base.

## Interpretation rules

- Strong-prior strategies (PEAD, cross-sectional momentum) that fail get ONE
  identified defect fixed and ONE re-run; weak-prior strategies that fail are
  disabled with no second chance.
- Disabling a strategy is safe: the engine winds down its open positions
  automatically (OPG exits, `strategy wind-down` reasoning) and the DRY_RUN
  smoke test derives its expected strategy count from config.
- News Sentiment fetches live RSS — ~0 backtest trades is expected and is
  itself the finding (the strategy is structurally unvalidatable offline).
