# Platform Audit — 2026-05-28

**Purpose**: forensic snapshot of the trading bot's state at the end of
2026-05-28, with every issue flagged, every relevant data point captured,
and copy-pastable SQL so we can re-verify each item tomorrow without
re-deriving anything.

**Tone**: this is a working document for "future Cascade + Shreyas". It
errs on the side of more detail; skim the headings, dive into the
specific section that matters when investigating a regression.

---

## 0. TL;DR

| Theme | State |
|---|---|
| **Reconciliation** | ✅ PASS every day for last 7 days |
| **Live-readiness gate** | ❌ 3/5 — blocked by win rate (31.6%) and trade count (19/30) |
| **Reconciliation drift warnings** | ✅ none in last 7 days |
| **Email rendering** | ⚠️ shows $0.00 P&L for newly-opened positions until tomorrow's run (fix landed commit `9f1471a`, takes effect next run) |
| **Strategy participation** | ⚠️ effectively 2 strategies trading (ML Momentum + Factor Momentum); the other 5 contribute almost nothing to P&L |
| **Win rate dragger** | 🚨 ML Momentum -$507 net over 17 closed trades (5W/12L); single AMD trade was -$279 |
| **Profitability concentration** | 🚨 +$711 from one Factor Momentum AMD trade is 348% of all-time net P&L — fragile |
| **Scheduling** | ⚠️ workflow ran 2× on both 2026-05-27 and 2026-05-28 — investigate whether GHA schedule was actually disabled (commit `9f1471a` is too recent to have run yet) |

---

## 1. Account & portfolio snapshot

Run timestamp: `2026-05-28T07:08:11` (latest full run)

| Metric | Value |
|---|---|
| Cash | $94,456.92 |
| Portfolio value | $96,091.85 |
| Buying power | $187,371.23 |
| Heat (deployed / PV) | **~5.0%** (well under 30% ceiling) |
| Reconciliation status | **PASS** |
| Regime | NORMAL · VIX 16.3 · TRENDING_BULL · trend=weak_trend |
| Peak portfolio value | $97,855.08 (set 2026-04-30) |

**Drawdown from peak**: ($97,855.08 - $96,091.85) / $97,855.08 = **1.80%**.
Comfortably inside the 8% live-readiness target.

### Open positions (4 total)

| Strategy | Symbol | Shares | Avg | Current | Unrealized | Entry |
|---|---|---|---|---|---|---|
| BROKER_SYNC | XLV | 11 | $145.44 | $148.79 | **+$36.83** | 2026-05-22 |
| Factor Momentum | AMD | 2 | $495.79 | $495.79 | $0.00 ⚠️ | 2026-05-27 |
| News Sentiment | AMZN | 4 | $271.99 | $271.99 | $0.00 ⚠️ | 2026-05-27 |
| News Sentiment | ABBV | 5 | $215.51 | $215.51 | $0.00 ⚠️ | 2026-05-27 |

The three $0.00 unrealized rows are the stale-price bug (Issue #4 below).
They were opened during the 2026-05-27 run, never marked-to-market on the
run that opened them, and the 2026-05-28 run re-opened them
intraday — these are TODAY's entries, not yesterday's, but the cycle is
the same.

**Verify**:
```sql
SELECT s.name, p.symbol, p.shares, ROUND(p.avg_price,2), ROUND(p.current_price,2),
       ROUND(p.unrealized_pnl,2), p.entry_date, p.last_updated
FROM positions p JOIN strategies s ON p.strategy_id=s.id
WHERE p.shares != 0 ORDER BY p.unrealized_pnl DESC;
```

---

## 2. Live-readiness gate (the path to flipping off paper trading)

```
NOT READY — 3/5 checks pass.
  ✗ Closed trades            19           (target >= 30)
  ✗ Win rate                 31.6%        (target >= 45%)
  ✓ Max drawdown             1.82%        (target <= 8.0%)
  ✓ Profit factor            1.27         (target >= 1.2)
  ✓ Clean reconciliation     20 days      (target >= 14 days)
```

**Re-run**: `python3 scripts/check_live_readiness.py`

**Biggest blocker**: win rate. See Issue #1.

---

## 3. Strategy activity, last 14 days

### Signal funnel

| Strategy | Runs | Raw | After Risk | Executed | Status |
|---|---|---|---|---|---|
| ML Momentum | 12 | 24 | 22 | **14** | ✅ active, dominant |
| News Sentiment | 6 | 23 | 16 | 11 | ✅ active |
| Factor Momentum | 5 | 14 | 14 | 7 | ✅ active |
| MA Crossover | 6 | 4 | 4 | 3 | ✅ active (low volume) |
| Earnings Drift | 12 | 7 | 7 | 2 | ⚠️ low conversion |
| Volatility Breakout | 6 | 2 | 2 | **0** | 🚨 all filtered downstream of risk |
| RSI Mean Reversion | 12 | **0** | 0 | 0 | 🚨 **dormant** |

**Note**: `News Sentiment` and `Volatility Breakout` show fewer runs
because they didn't exist in earlier scheduler cycles or were toggled off
mid-window.

**Verify**:
```sql
SELECT s.name, COUNT(DISTINCT f.run_id) AS runs,
       SUM(f.raw_signals_count) AS raw,
       SUM(f.after_regime_count) AS af_reg,
       SUM(f.after_correlation_count) AS af_corr,
       SUM(f.after_risk_count) AS af_risk,
       SUM(f.executed_count) AS exec
FROM signal_funnel f JOIN strategies s ON f.strategy_id=s.id
WHERE f.created_at >= datetime('now','-14 days')
GROUP BY s.id ORDER BY exec DESC;
```

### Signal rejection breakdown (14d)

| Strategy | Reason | Count |
|---|---|---|
| ML Momentum | cash_or_heat_limit | 8 |
| Factor Momentum | cash_or_heat_limit | 7 |
| News Sentiment | max_signals_limit | 7 |
| Earnings Drift | cash_or_heat_limit | 5 |
| News Sentiment | cash_or_heat_limit | 5 |
| ML Momentum | max_signals_limit | 2 |
| Volatility Breakout | cash_or_heat_limit | 2 |
| MA Crossover | cash_or_heat_limit | 1 |

⚠️ **All `cash_or_heat_limit` entries above use the pre-fix combined
bucket**. Starting with the next run after commit `9f1471a`, this column
will populate with granular reasons (`insufficient_cash`,
`portfolio_heat`, `cross_strategy_dedup`, `wash_trade_guard`,
`earnings_protection`, `ml_risk_off`, `size_zero`, `sector_filter`).
If tomorrow's report still shows `cash_or_heat_limit` for new runs, the
fix didn't take effect — investigate.

**Verify**:
```sql
SELECT s.name, sr.stage, sr.reason_code, COUNT(*) AS n
FROM signal_rejections sr JOIN strategies s ON sr.strategy_id=s.id
WHERE sr.created_at >= datetime('now','-14 days')
GROUP BY s.id, sr.stage, sr.reason_code ORDER BY n DESC;
```

---

## 4. Closed-trade P&L forensics

### By strategy (all-time)

| Strategy | Closed | Total P&L | Avg | Wins | Losses | Worst | Best |
|---|---|---|---|---|---|---|---|
| **Factor Momentum** | 2 | **+$711.46** | +$355.73 | 1 | 1 | -$38.45 | **+$749.91** |
| **ML Momentum** | 17 | **-$506.94** | -$29.82 | 5 | 12 | -$279.14 | +$108.49 |
| Total | 19 | **+$204.52** | +$10.76 | 6 | 13 | -$279.14 | +$749.91 |

**Concentration risk**: a single Factor Momentum AMD trade on 2026-05-06
returned +$749.91 — that one trade is **+367% of all-time net P&L**.
Without it, the system has lost $545 net.

### Full closed-trade ledger (oldest → newest)

| Date | Strategy | Symbol | Shares | Px | P&L |
|---|---|---|---|---|---|
| 2026-05-04 | ML Momentum | AVGO | 3 | $416.29 | -$4.67 |
| 2026-05-05 | ML Momentum | ABT | 16 | $87.13 | -$60.04 |
| 2026-05-05 | ML Momentum | GOOGL | 5 | $388.24 | +$15.25 |
| 2026-05-05 | ML Momentum | UNH | 12 | $363.57 | -$72.70 |
| 2026-05-05 | ML Momentum | VZ | 36 | $47.33 | -$26.87 |
| 2026-05-06 | ML Momentum | DHR | 9 | $174.71 | -$5.51 |
| 2026-05-06 | ML Momentum | NFLX | 18 | $88.23 | -$70.64 |
| 2026-05-06 | Factor Momentum | AMD | 10 | $421.18 | **+$749.91** |
| 2026-05-11 | ML Momentum | GOOGL | 5 | $388.45 | -$49.94 |
| 2026-05-11 | ML Momentum | ABT | 22 | $82.51 | -$41.24 |
| 2026-05-12 | ML Momentum | AAPL | 16 | $294.65 | +$108.49 |
| 2026-05-12 | ML Momentum | NFLX | 24 | $87.62 | -$17.80 |
| 2026-05-12 | ML Momentum | XLK | 13 | $175.12 | +$63.91 |
| 2026-05-18 | ML Momentum | AMD | 8 | $420.78 | **-$279.14** |
| 2026-05-18 | ML Momentum | NVDA | 4 | $222.21 | +$10.19 |
| 2026-05-18 | ML Momentum | TSLA | 2 | $409.79 | -$71.28 |
| 2026-05-18 | ML Momentum | UNH | 5 | $390.88 | -$29.25 |
| 2026-05-18 | Factor Momentum | AMD | 1 | $420.78 | -$38.45 |
| 2026-05-21 | ML Momentum | XLV | 11 | $148.08 | +$24.30 |

**Pattern flags**:
- 2026-05-05 / 2026-05-06 / 2026-05-18: synchronized bulk exits of 4–5
  positions. Strong evidence of mechanical time-exits firing at the same
  point in market cycles (Issue #1).
- AMD held by both ML Momentum AND Factor Momentum simultaneously,
  liquidated on the same day at the same price → suggests
  cross-strategy dedup may not be catching it; or both strategies are
  hitting time-exits in lockstep.

**Verify**:
```sql
SELECT t.executed_at, s.name AS strat, t.symbol, t.shares,
       ROUND(t.exec_price,2) AS px, ROUND(t.pnl,2) AS pnl
FROM trades t JOIN strategies s ON t.strategy_id=s.id
WHERE t.action='SELL' AND t.pnl IS NOT NULL
ORDER BY t.executed_at;
```

---

## 5. Order intent lifecycle (14d)

| Status | Count |
|---|---|
| FILLED | 24 |
| ACKED (pending) | 7 |
| FAILED | 6 |

**Worth investigating**: 6 FAILED intents in 14 days = ~30% non-fill rate
when combined with ACKED. Drill into FAILED to see whether they're
rejections, cancels, or expirations:

```sql
SELECT created_at, symbol, side, qty, status, error_message
FROM order_intents
WHERE status='FAILED' AND created_at >= datetime('now','-14 days')
ORDER BY created_at DESC;
```

---

## 6. Reconciliation history (last week)

Every day reads `START → SYNC (SYNCED) → RECONCILIATION (PASS) → END (PASS)`.
Auto-sync is running and corrective; no drift warning emails have been
emitted since the auto-sync gate landed.

**Two-run-per-day pattern** observed on 2026-05-27 and 2026-05-28
(two START/SYNC/RECONCILIATION/END cycles each day). Causes:
- cron-job.org primary trigger + GHA `workflow_dispatch` manual runs,
  OR
- the GHA schedule trigger may not actually be disabled despite the
  commented-out cron in `.github/workflows/daily_trading.yml`.

🚨 **TODO tomorrow**: confirm only one run per day after commit `9f1471a`.
Two runs is wasteful and can produce duplicate emails.

**Verify**:
```sql
SELECT snapshot_date, snapshot_type, reconciliation_status,
       substr(discrepancies_json,1,200) AS discr
FROM broker_state
ORDER BY snapshot_date DESC, ROWID DESC LIMIT 30;
```

---

## 7. Flagged issues

### Issue #1 — ML Momentum's mechanical time-exit is the dominant P&L drag 🚨

**Evidence**: ML Momentum -$507 net over 17 closed trades. The single
2026-05-18 exit cluster (AMD -$279, TSLA -$71, UNH -$29, NVDA +$10) is
~$370 of that loss, all triggered by `days_held >= 5` exits on the same
day regardless of P&L.

**Status**: **partially mitigated** in commit `9f1471a`. New rule only
forces exit at `hold_days` if (a) profitable or (b) model has weakened
to `prob < 0.50`. Otherwise holds to `max_hold_days = 15`.

**Verify the fix is live tomorrow**: any SELL signal from ML Momentum
should have a reasoning string of either `Held Nd in profit`,
`Held Nd, model weakened (X%)`, `Held Nd (max ceiling)`, or
`ML bearish (X%)`. The old plain `Held Nd` reason should no longer
appear.

```sql
SELECT generated_at, symbol, signal_type, reasoning
FROM signals
WHERE strategy_id = (SELECT id FROM strategies WHERE name='ML Momentum')
  AND signal_type='SELL'
  AND generated_at >= datetime('now','-3 days')
ORDER BY generated_at DESC;
```

**If still problematic after a week of new data**: consider lowering
`min_confidence` floor (currently 0.65 in config), or adding an
entry-side rule that requires `prob_positive > 0.70` for new BUYs.

---

### Issue #2 — RSI Mean Reversion is dormant 🚨

**Evidence**: 0 raw signals in 14 days. Lifetime total = 2 signals.

**Root cause**: entry requires `RSI < 35 AND slope > 0 AND price > SMA-100 AND not capitulation`.
In a TRENDING_BULL / VIX 16.3 regime, large-caps rarely dip to RSI < 35.

**Status**: **not a bug, by design**. Strategy is correctly idle in the
current regime.

**Action only if**: regime shifts to HIGH_VOL or sideways and RSI MR is
*still* silent — then loosen `rsi_threshold` from 35 to 40 in
`config/trading_config.yaml` (add a `strategies.rsi_mean_reversion`
block; it doesn't exist yet, the legacy class attribute is the source of
truth).

**Verify regime daily**:
```sql
SELECT value FROM system_state WHERE key='regime';
```

---

### Issue #3 — Volatility Breakout produces signals but they're all filtered ⚠️

**Evidence**: 2 raw signals in 14 days, 2 survived risk filters, 0 executed.

**Likely cause**: `_execute_strategy_trades` rejected both at the
cash/sector/heat layer. With the new granular rejection codes (commit
`9f1471a`), tomorrow's data will tell us which one.

**Verify tomorrow**:
```sql
SELECT sr.created_at, sr.symbol, sr.reason_code, sr.details_json
FROM signal_rejections sr
JOIN strategies s ON sr.strategy_id = s.id
WHERE s.name='Volatility Breakout'
  AND sr.created_at >= datetime('now','-14 days')
ORDER BY sr.created_at DESC;
```

---

### Issue #4 — Stale `current_price` on newly-opened positions ⚠️ (fixed, awaiting verification)

**Evidence**: AMD / ABBV / AMZN all opened 2026-05-27, all show
`current_price == avg_price` and `unrealized_pnl = 0.00`. XLV (opened
2026-05-22) shows the real intraday close.

**Status**: **fix landed in commit `9f1471a`**. Added a second
`refresh_position_prices(current_prices)` call after strategies execute,
plus changed `WHERE shares > 0` to `WHERE shares != 0` in two queries.

**Verify after next run**:
```sql
SELECT symbol, avg_price, current_price, unrealized_pnl, last_updated
FROM positions WHERE shares != 0 AND entry_date = (SELECT MAX(entry_date) FROM positions);
```
If a position was opened in the run and `current_price != avg_price`,
the fix is working.

---

### Issue #5 — Capital allocation is exactly equal across all 7 strategies ⚠️

**Evidence**: every active strategy has `capital_allocation = $11,668.30`
(7-way equal split of ~$81.7k).

**Likely cause**: `DynamicAllocator` falls back to equal weight when
strategies have too few closed trades to score a trailing Sharpe
reliably. We have 19 closed trades spread across 2 strategies — far
below the threshold for individual scoring.

**Status**: **not actionable today**, will self-correct as trade history
accumulates per strategy. Recheck once each strategy has ≥20 closed
trades.

**Verify**:
```sql
SELECT id, name, ROUND(capital_allocation,0) AS alloc,
       ROUND(initial_capital,0) AS init
FROM strategies WHERE status='active' ORDER BY name;
```

---

### Issue #6 — Workflow ran twice on both 2026-05-27 and 2026-05-28 ⚠️

**Evidence**: two complete START/SYNC/RECONCILIATION/END cycles per day
in `broker_state`.

**Possible causes**:
1. cron-job.org triggers `workflow_dispatch` AND the GHA `schedule`
   trigger is also firing (we believed we disabled it).
2. cron-job.org triggers twice (misconfigured).
3. Manual `workflow_dispatch` invocations.

🚨 **TODO**: check `.github/workflows/daily_trading.yml` to confirm
the `schedule:` block is actually removed/commented out:
```bash
grep -A 3 "^on:" .github/workflows/daily_trading.yml
```

And check the last 7 days of GHA runs:
```bash
gh run list --workflow daily_trading.yml --limit 30 --json createdAt,event,conclusion \
  | jq -r '.[] | "\(.createdAt) \(.event) \(.conclusion)"'
```

If you see two runs per day, look at the `event` column —
`schedule` means GHA cron is still firing; `workflow_dispatch` x2
means cron-job.org is double-firing.

---

### Issue #7 — Order intent failure rate ⚠️

**Evidence**: 6 FAILED of 37 intents in 14 days = 16% failure rate.

**Status**: not investigated. Could be expected (e.g., orders cancelled
when market closed before fill) or could mask real broker errors.

**Verify**:
```sql
SELECT created_at, symbol, side, qty, status, error_message
FROM order_intents
WHERE status='FAILED' AND created_at >= datetime('now','-14 days')
ORDER BY created_at DESC;
```

---

### Issue #8 — Profitability is concentrated in one outlier trade 🚨

**Evidence**: one Factor Momentum AMD trade returned +$749.91. The other
18 trades net to **-$545.39**. The system is one trade away from being
deeply negative.

**Status**: not a bug — it's the inherent statistical reality with only
19 closed trades. Will look less alarming with more sample size.

**Action**: do **not** flip off paper trading until the win rate gate
(45%) is met with a meaningful sample (target 30+ trades). The
live-readiness gate already enforces this.

---

## 8. Where to start tomorrow

In priority order:

1. **Confirm the four `9f1471a` fixes took effect**. Tomorrow's email
   should:
   - show real intraday P&L (not $0.00) on any positions opened today
   - show `Held Nd in profit` or `Held Nd, model weakened` reasoning
     when ML Momentum exits, not bare `Held Nd`
   - populate `signal_rejections.reason_code` with granular codes
     (`insufficient_cash`, `portfolio_heat`, etc.) instead of
     `cash_or_heat_limit`
2. **Investigate Issue #6 (double runs)** — check GHA workflow trigger
   config and `gh run list`. Fix whichever side is double-firing.
3. **Drill into Issue #7 (order intent failures)** — pull the 6 FAILED
   intents from the last 14 days, check `error_message`, decide whether
   it's benign or hiding a broker integration bug.
4. **Re-run live-readiness gate** — see whether the ML Momentum fix has
   pushed win rate above 45% after a few more closed trades.

## 9. Useful command quick-reference

```bash
# Refresh local DB from latest GHA artifact
./scripts/refresh_local_db.sh

# Live-readiness gate
python3 scripts/check_live_readiness.py

# Daily email preview
python3 scripts/generate_daily_email.py
open /tmp/daily_email.html

# Check recent GHA runs
gh run list --workflow daily_trading.yml --limit 10

# Tail latest run logs
gh run view --log $(gh run list --workflow daily_trading.yml --limit 1 --json databaseId -q '.[0].databaseId')

# Sync broker state manually
python3 scripts/sync_broker_state.py
```

---

*Generated 2026-05-28 17:54 (post-commit `9f1471a`).*
