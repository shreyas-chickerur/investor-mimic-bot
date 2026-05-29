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

## 10. Follow-up investigation (2026-05-28 18:15)

Continued the audit after commit `9796c1d`. Several items closed,
several new bugs surfaced.

### 10.1 Issue #6 (workflow double-run) — RESOLVED ✅

`gh run list` showed both `schedule` and `workflow_dispatch` events
firing daily, but `git log .github/workflows/daily_trading.yml` reveals
commit `6a251c8` (2026-05-28 17:24 CDT, ~3 hours ago) already commented
out the `schedule:` block. The double-runs we observed in `broker_state`
were from `schedule` cron firings that fired BEFORE the commit landed.

**Action**: nothing. Tomorrow's `gh run list` should show only
`workflow_dispatch` events. If `schedule` still appears, the comment-out
didn't take effect.

### 10.2 Issue #7 (order intent failure rate 16%) — RESOLVED, BENIGN ✅

All 6 FAILED order intents in the last 14 days are from a single run:

| Time | Symbol | Alpaca error |
|---|---|---|
| 2026-05-20 22:51:45 UTC | TSLA | `opg orders must be submitted after 7:00pm and before 9:28am` |
| 2026-05-20 22:51:45 UTC | AAPL | (same) |
| 2026-05-20 22:51:46 UTC | NVDA | (same) |
| 2026-05-20 22:51:47 UTC | AVGO | (same) |
| 2026-05-20 22:51:47 UTC | UNH | (same) |
| 2026-05-20 22:51:47 UTC | AMD | (same) |

22:51 UTC = 18:51 ET, i.e. ~9 minutes before the OPG submission window
opens at 19:00 ET. A single mis-timed run rejected all six BUYs. **Not
a systemic 16% failure rate** — just a one-time scheduling collision.

**Action**: ensure all triggers fire at or after 19:00 ET. cron-job.org
fires at 00:30 UTC (19:30 ET in summer / 18:30 ET in winter). If we're
ever on winter time the cron will be ~30 min too early. Worth converting
the cron-job.org schedule to dynamic ET-aware time, or just shifting it
to 00:45 UTC year-round to leave headroom.

### 10.3 Issue #5 (equal capital allocation) — ROOT CAUSE FOUND 🚨

The dynamic allocator IS functioning. I reproduced it via
`@/Users/shreyaschickerur/CascadeProjects/investor-mimic-bot/scripts/adhoc/probe_allocator.py`
and confirmed it computes Sharpe-weighted allocations correctly:

| Strategy | Computed allocation | Currently in DB |
|---|---|---|
| Earnings Drift | $20,419 (25.0%) | $11,668 |
| RSI Mean Reversion | $20,088 (24.6%) | $11,668 |
| ML Momentum | $9,271 (11.4%) | $11,668 |
| Factor Momentum | $7,726 (9.5%) | $11,668 |
| News Sentiment | $7,726 (9.5%) | $11,668 |
| MA Crossover | $6,181 (7.6%) | $11,668 |
| Volatility Breakout | $6,181 (7.6%) | $11,668 |

**Root cause**: `@/Users/shreyaschickerur/CascadeProjects/investor-mimic-bot/src/core/execution_engine.py:591`
inside `initialize_strategies()` calls
`db.update_strategy_capital_allocation(strategy_id, capital_per_strategy)`
where `capital_per_strategy = deployed_capital / num_strategies` is the
EQUAL split. This hard-codes equal weights into the
`strategies.capital_allocation` DB column on every run, BEFORE the
dynamic allocator computes Sharpe-based weights.

The dynamic allocator runs later and writes the correct weights to
`strategy.capital` (the in-memory attribute that drives position
sizing via `calculate_position_size`). **So sizing IS
Sharpe-weighted** — but every external observer (DB queries, email
template, dashboards, this audit) sees the misleading equal split.

**Severity**: medium. Sizing is correct; observability is wrong.
But because the email and audit show flat weights, we keep being
fooled into thinking allocator is broken.

**Recommended fix**: in `_apply_allocations`, also write the dynamic
weights to the DB column so observability matches reality. ~3 line
change.

### 10.4 NEW BUG: stale ACKED orders never reconciled 🚨

7 order intents in `order_intents` table are stuck at `ACKED` status,
oldest from 2026-05-18:

| Created | Symbol | Side | Qty | Broker order id |
|---|---|---|---|---|
| 2026-05-22 07:02:35 | AMZN | BUY | 8 | 7b4aa148… |
| 2026-05-22 07:02:35 | AVGO | BUY | 4 | d06add83… |
| 2026-05-22 06:44:02 | AMZN | BUY | 8 | 5d0a9a18… |
| 2026-05-22 06:44:02 | AVGO | BUY | 4 | 4bc01e3e… |
| 2026-05-21 23:18:57 | AMZN | BUY | 8 | f464685e… |
| 2026-05-21 23:18:57 | AVGO | BUY | 4 | c1744193… |
| 2026-05-18 22:28:18 | XLV | BUY | 11 | 4c678c65… |

**Patterns to notice**:
- AMZN BUY 8 appears **3 times** across 3 different runs on 2026-05-21
  and 2026-05-22.
- AVGO BUY 4 appears **3 times** on the same days.
- These are real broker orders (have `broker_order_id`), submitted but
  never re-checked.

**Root cause**: `@/Users/shreyaschickerur/CascadeProjects/investor-mimic-bot/src/core/execution_engine.py:487-547`
`verify_order_statuses()` only iterates `self.executed_trades` from the
CURRENT run. Orders from previous runs that were `ACKED` but never
reached terminal state are never re-polled. They stay `ACKED` forever
even if Alpaca has long since filled, expired, or cancelled them.

**Consequence**: the strategy doesn't know these BUYs failed (or
succeeded), so it re-evaluates and re-submits. That's why AMZN BUY 8
and AVGO BUY 4 each appear 3 times.

**Recommended fix**: at the top of each run, sweep all `ACKED` intents,
poll Alpaca for each broker_order_id, and update status. Add a max-age
guard (e.g., expire ACKEDs older than 48h to `FAILED`).

**Verify daily**:
```sql
SELECT created_at, symbol, side, target_qty, broker_order_id
FROM order_intents
WHERE status='ACKED' AND created_at < datetime('now','-1 day');
```
Should return 0 rows once the fix is in.

### 10.5 NEW FINDING: cross-strategy position duplication ⚠️

On 2026-05-08, **three different strategies bought AMD** within the
same trading session:

| Time (UTC) | Strategy | Shares @ Price |
|---|---|---|
| 21:24:29.12 | Earnings Drift | 1 @ $455.42 |
| 21:24:29.28 | Factor Momentum | 1 @ $455.42 |
| 22:00:07.94 | Earnings Drift | 1 @ $455.42 |
| 22:00:08.04 | Factor Momentum | 1 @ $455.42 |
| 22:24:05.97 | ML Momentum | 2 @ $455.42 |

The 21:24, 22:00, and 22:24 are **three separate runs of the same day**
(this was during the double-trigger period — see §10.1).

The cross-strategy dedup at `@/Users/shreyaschickerur/CascadeProjects/investor-mimic-bot/src/core/execution_engine.py:1973-1976`
checks "already held by another strategy" but presumably only at the
moment each strategy processes its own signal queue. If multiple
strategies all evaluate AMD before any one writes its position, none
triggers the dedup. Or the dedup is only intra-run.

**Question for you**: is this intentional (strategies independent,
positions can overlap) or a bug (one strategy should own each symbol)?
Current behavior creates fragmented small positions (1-2 shares each)
and triples notional exposure to a single symbol.

If unintentional, the dedup needs to check `positions` table across
ALL strategies, not just within-run intent.

### 10.6 News Sentiment hits `max_signals_limit` 7× in 14d ⚠️

| Date | Hits |
|---|---|
| 2026-05-28 | 4 |
| 2026-05-27 | 3 |

The strategy generated more BUY signals than `top_n=5` (or the strategy's
configured cap) allowed, so 3-4 candidates per day were throttled.

**Could be**:
- Strategy is correctly noisy and the throttle is doing its job
  (most likely — it executed 11 of 23 raw signals).
- Or the throttle is too tight and we're losing alpha by capping.

**Not actionable without backtest validation**. Worth checking after
News Sentiment has 20+ closed trades to compare throttled vs unthrottled
hypothetical P&L. Until then, leave it.

### 10.7 Volatility Breakout XLY rejection — WAITING ON DATA

Both 2026-05-28 XLY breakout signals were rejected at the RISK stage
with the (pre-fix) bucketed code `cash_or_heat_limit`. With the
granular-reason fix from commit `9f1471a`, tomorrow's run will tell us
which specific check failed.

XLY is the Consumer Discretionary sector ETF. Hypothesis: the
`benchmark_etf_filter` at line ~1934 in execution_engine.py blocks ETFs
in non-BROKER_SYNC strategies. Will confirm when tomorrow's data lands.

---

## 11. Recommended next fixes

In priority order:

1. **Stale ACKED reconciliation** (10.4) — concrete bug, causes
   duplicate broker submissions. Estimated effort: ~30 lines.
2. **Capital allocation observability** (10.3) — write dynamic
   allocations to the DB column so observers see truth. ~3 lines.
3. **Cross-strategy AMD overlap** (10.5) — needs a design decision
   first. Investigate / propose, don't change behavior yet.
4. **cron-job.org timing buffer** (10.2) — shift to 00:45 UTC to
   survive ET timezone shifts. Single config change in cron-job.org UI,
   no code change.

---

## 12. Adhoc scripts created during this audit

- `@/Users/shreyaschickerur/CascadeProjects/investor-mimic-bot/scripts/adhoc/probe_allocator.py` — reproduces
  what `DynamicAllocator` sees during a live run. Useful any time
  observed vs expected allocations diverge.

---

## 13. Deep sweep findings (2026-05-28 18:30) — major new bugs

After the user asked "are there any other issues", I ran a broader DB
forensics + test-suite + cross-strategy scan. Several **significant**
new issues surfaced.

### 13.1 🚨 SELL trades bypass `order_intents` tracking entirely

Database state:

| | Count |
|---|---|
| `order_intents` rows where `side='BUY'` | 89 |
| `order_intents` rows where `side='SELL'` | **0** |
| `trades` rows where `action='SELL'` | 19 |

Every one of the 19 SELL trades has an `order_id` that **does not match
any row in `order_intents`** (verified by left-join). The SELL
codepaths in
`@/Users/shreyaschickerur/CascadeProjects/investor-mimic-bot/src/core/execution_engine.py:969`
and `:2484` both call `db.create_order_intent(..., "SELL", ...)`, yet
no SELL intent has ever been persisted.

**Implications**:
- `verify_order_statuses()` walks intents, so **SELLs are never
  broker-confirmed**. The local DB optimistically writes the SELL into
  `trades` (with computed P&L), but there's no audit trail to confirm
  the broker actually executed it.
- This is the proximate cause of the XLV phantom-trade pattern (§13.2).

**Investigation needed**: figure out why `create_order_intent` for
SELLs never produces a row. Options:
- Some upstream `continue` is firing before the call (no logs say so)
- `conn.commit()` failing silently
- Duplicate intent_id collision (deterministic ID — but BUY/SELL params
  are in the hash, so this shouldn't happen)
- A legacy DAY-order SELL path is taking precedence

**Verify daily**:
```sql
SELECT side, COUNT(*) FROM order_intents GROUP BY side;
```
SELL count should be > 0 once the bug is fixed.

### 13.2 🚨 XLV phantom-trade chain (consequence of §13.1)

Reconstructing the full XLV story:

| Date | Event | Source |
|---|---|---|
| 2026-05-18 22:28:18 | ML Momentum BUY 11 XLV @ $145.79 | `trades` |
| 2026-05-18 22:28:18 | order_intents: ACKED, broker_order_id `4c678c65…` | `order_intents` |
| 2026-05-21 23:18:57 | ML Momentum SELL 11 XLV @ $148.08, **+$24.30 P&L** | `trades` |
| 2026-05-21 23:18:57 | **NO order_intent row** | — |
| 2026-05-22 (next day SYNC) | Broker reports 11 XLV @ $145.44 in account | `broker_state` |
| 2026-05-22 → today | XLV imported as BROKER_SYNC strategy, 11 shares | `positions` |

**Read the timeline**:
1. Bot believed it bought 11 XLV at $145.79 (paper-OPG optimistic
   record), but the BUY intent stayed `ACKED` — broker never confirmed
   the fill.
2. Three days later, bot believed it sold 11 XLV at $148.08 with +$24
   P&L, but no SELL intent was ever written.
3. The next day's broker reconciliation found XLV still in the account
   at a **different cost basis** ($145.44, not $145.79) and imported it
   as a "new" BROKER_SYNC position.

**The +$24.30 P&L on the XLV trade is fictitious**. The broker never
sold those shares; we're still long 11 XLV. The local DB credits ML
Momentum with a "win" that didn't happen.

This is recorded in `trade_pnl_detail` and contributes to the win-rate
calculation used by the live-readiness gate.

### 13.3 🚨 Cash-impact divergence ($36k unaccounted)

| Source | 14-day cash impact |
|---|---|
| Sum over `trades`: SELL notional − BUY notional | **−$41,818** |
| Actual cash delta: $100k − $94,457 | **−$5,543** |
| **Discrepancy** | **$36,275** |

Per-strategy breakdown of the 14d trade-table cash impact:

| Strategy | BUY notional | SELL notional | Net |
|---|---|---|---|
| ML Momentum | $13,964 | $8,654 | −$5,310 |
| News Sentiment | $12,354 | $0 | −$12,354 |
| Earnings Drift | $11,575 | $0 | −$11,575 |
| Factor Momentum | $8,848 | $421 | −$8,427 |
| MA Crossover | $4,152 | $0 | −$4,152 |

If we trust the trades table, the bot deployed ~$42k of new capital in
14 days. Reality: only $5.5k of cash actually moved. The simplest
explanation consistent with §13.1 and §13.2:

**Many BUY trades that the local DB records as filled never actually
executed at the broker.** They were submitted as paper-OPG, the bot
optimistically wrote a `trades` row, the intent stayed `ACKED`, and the
broker never filled the order (or filled at the open and was never
reconciled back into the local intent state).

**Severity**: this means the entire P&L narrative is partially
fictitious. The 31.6% win rate, the +$204 net P&L, the live-readiness
gate output — all of it is computed from `trades` rows that may or may
not correspond to real broker executions.

**Verify**:
```sql
SELECT t.executed_at, t.symbol, t.action, t.shares, t.exec_price, oi.status AS intent_status
FROM trades t LEFT JOIN order_intents oi ON t.order_id = oi.broker_order_id
WHERE t.executed_at >= datetime('now','-14 days')
ORDER BY t.executed_at DESC;
```
Any row with `intent_status` ≠ 'FILLED' is a candidate phantom trade.

### 13.4 🚨 News Sentiment has the same naive time-exit as old ML Momentum

`@/Users/shreyaschickerur/CascadeProjects/investor-mimic-bot/src/strategies/strategy_news_sentiment.py:160-163`:

```python
elif days_held >= self.max_hold_days:
    exit_reason = f"Max hold reached ({days_held}d)"
elif days_held >= self.hold_days:
    exit_reason = f"Sentiment hold window expired ({days_held}d)"
```

No profit-or-bearish gate at `hold_days = 7`. Same anti-pattern that
caused the 2026-05-18 ML Momentum bulk dump.

**Imminent risk**: AMZN (4 sh @ $271.99) and ABBV (5 sh @ $215.51) were
opened by News Sentiment on 2026-05-27. They will be force-exited on
**2026-06-03** regardless of profitability or sentiment score.

**Recommended fix**: mirror the ML Momentum pattern — exit at
`hold_days` only if (a) profitable, OR (b) sentiment has crossed
`sell_threshold`. Hold to `max_hold_days = 14` otherwise.

### 13.5 ⚠️ 4 failing unit tests

```
FAILED tests/unit/test_critical_bugs_and_guards.py::TestOrderTimingOPG::test_execution_engine_uses_opg_not_day_for_buys
FAILED tests/unit/test_ten_improvements.py::TestImprovement10TaxAwareExit::test_rsi_extends_hold_at_day_250
FAILED tests/unit/test_ten_improvements.py::TestImprovement10TaxAwareExit::test_factor_extends_hold_at_day_252
FAILED tests/unit/test_workflow_fixes.py::TestFetchHistoricalDataTierDetection::test_fetcher_respects_premium_flag
```

- **`test_execution_engine_uses_opg_not_day_for_buys`**: BUY orders
  should use `TimeInForce.OPG`. Test failing suggests a regression to
  `DAY` somewhere — could explain unexpected fills outside the
  market-on-open path.
- **`test_rsi_extends_hold_at_day_250`** and
  **`test_factor_extends_hold_at_day_252`**: the tax-aware "extend hold
  to cross 1-year LTCG threshold" logic emits a SELL when it should
  defer. We have no positions near the 1-year mark today, but this is
  broken and will silently realize short-term capital gains when we do.
- **`test_fetcher_respects_premium_flag`**: `TypeError` from
  `str | None` syntax in `scripts/fetch_historical_data.py:79` —
  Python 3.9 vs 3.10+ compat. Test infra issue, not a runtime bug.

**Verify**:
```bash
python3 -m pytest tests/unit -q --tb=short
```

### 13.6 ⚠️ Email script bugs (extends earlier findings)

`@/Users/shreyaschickerur/CascadeProjects/investor-mimic-bot/scripts/generate_daily_email.py:156`,
`:263`, `:265` — all filter positions with `WHERE p.shares > 0`. Same
latent short-position bug fixed in `database.py` (commit `9f1471a`)
still present in the email script.

`@/Users/shreyaschickerur/CascadeProjects/investor-mimic-bot/scripts/generate_daily_email.py:999`,
`:1009` — read `capital_allocation` directly from the DB column, which
is the equal-weighted misleading value (Issue #10.3). The email
displays inaccurate per-strategy allocations.

### 13.7 ✅ What I confirmed is healthy

- All signals have `terminal_state` populated.
- No positions with `current_price = 0` or `NULL`.
- No stale (>3d) open positions.
- `trade_pnl_detail` row count matches SELL count (19/19).
- No absurd `gross_pnl_pct` values.
- Health scorer is running daily — strategy_performance snapshots are
  current for all strategies.
- No orphan signals (foreign-key integrity intact).
- No positions with `avg_price = 0`.
- Other strategies (RSI MR, MA Crossover, Vol Breakout, Earnings Drift,
  Factor Momentum) all have proper `max_hold_days` ceilings + profit
  gating in their time-exit logic. Only News Sentiment shares the old
  ML Momentum anti-pattern (§13.4).

---

## 14. Combined fix priority list

After both audit passes, here's the priority-ordered fix list:

| # | Fix | Severity | Effort |
|---|---|---|---|
| 1 | **§13.1 + §13.2 + §13.3 — SELL intent + phantom trade chain** | 🚨 critical (data integrity) | Multi-file, ~1-2h |
| 2 | **§10.4 — Stale ACKED orders never reconciled** | 🚨 high (causes resubmissions) | ~30 lines |
| 3 | **§13.4 — News Sentiment time-exit gating** | 🚨 high (imminent 06-03 dump) | ~15 lines |
| 4 | **§10.3 — Capital allocation DB observability** | medium | ~3 lines |
| 5 | **§13.5 — Tax-aware exit unit tests fail** | medium (silent STCG when 1y old positions exist) | needs investigation |
| 6 | **§13.6 — Email script filters/displays** | low (UI only) | ~5 lines |
| 7 | **§13.5 — `OrderTimingOPG` test fail** | medium | needs investigation |
| 8 | **§10.5 — Cross-strategy position duplication** | design decision | discuss first |
| 9 | **§10.2 — cron-job.org timing buffer** | low | UI change in cron-job.org |

---

## 15. Adhoc artifacts created during this audit

All under `@/Users/shreyaschickerur/CascadeProjects/investor-mimic-bot/scripts/adhoc/`:

- `probe_allocator.py` — reproduce DynamicAllocator output
- `issue_sweep.sql` + `.out` — broad DB integrity scan
- `xlv_forensics.sql` + `.out` — XLV phantom-trade reconstruction
- `trade_intent_audit.sql` + `.out` — trade↔intent linkage check
- `sell_intent_audit.sql` + `.out` — SELL intent existence check
- `commit_msg_*.txt` — commit message bodies for `git commit -F`

---

## 16. Broker-verified update (2026-05-28 19:00)

After user note that "Claude Code took care of XLV", I queried Alpaca
directly via
`@/Users/shreyaschickerur/CascadeProjects/investor-mimic-bot/scripts/adhoc/verify_against_alpaca.py`.
Several earlier severities revised; one new bug surfaces.

### 16.1 Alpaca account state (paper)

| Field | Value |
|---|---|
| cash | **$94,456.92** |
| portfolio_value | $96,091.85 |
| buying_power | $190,548.77 |
| equity | $96,091.85 |
| status | ACTIVE |

### 16.2 Broker positions vs local DB — **3 of 4 local positions are phantom**

| Symbol | Local strategy | Local shares | Broker shares | Notes |
|---|---|---|---|---|
| ABBV | News Sentiment | 5.00 | **0.00** | 🚨 phantom |
| AMD | Factor Momentum | 2.00 | **0.00** | 🚨 phantom |
| AMZN | News Sentiment | 4.00 | **0.00** | 🚨 phantom |
| XLV | BROKER_SYNC | 11.00 | 11.00 | ✓ matches |

**Broker actually holds only 11 XLV.** Everything else the bot thinks
it owns does not exist at Alpaca. The "reconciliation SYNCED" status in
`broker_state` is misleading — the recon snapshots broker positions but
doesn't actually compare local vs broker at the strategy level.

Root cause: when a BUY order intent gets `canceled` or `expired` at the
broker, the bot's optimistic `positions` row (created at signal
submission time) stays put. There's no cleanup pass that removes
phantom positions when their creating BUY order failed.

### 16.3 XLV — user is correct, Claude Code handled it ✅

Reconstructing with broker confirmation:

| Date | Event | Broker reality |
|---|---|---|
| 2026-05-18 | ML Momentum BUY 11 XLV recorded at $145.79 | **Actually filled at $145.44** (different price — optimistic local record was off) |
| 2026-05-21 | ML Momentum SELL 11 XLV recorded with **+$24.30 P&L** | **`canceled` at broker** — SELL never executed |
| 2026-05-22 | Broker SYNC saw XLV still in account, imported as BROKER_SYNC | ✓ real position |
| 2026-05-28 22:23:15 | **New SELL XLV 11 submitted today, status `accepted`** | ✓ will fill at next open |

So:
- The +$24.30 P&L in `trade_pnl_detail` for the 5/21 trade **is
  fictitious** — broker canceled that SELL. This historical row is
  wrong but the next fill will close the position cleanly.
- A small +$0.35 correction would be needed to the historical entry
  price ($145.79 → $145.44) but it's now moot since the position will
  close.
- **Action**: optionally clean up the bogus 5/21 row in `trade_pnl_detail`
  (it inflates win rate by 1 trade). Otherwise accept as historical
  noise.

### 16.4 Stale ACKED order intents — corrected breakdown

Of the 7 ACKED intents I flagged in §10.4, the broker-side truth:

| Local status | Broker status | Count | Implication |
|---|---|---|---|
| ACKED | `canceled` | 6 (AMZN/AVGO 5/21–5/22) | 🚨 caused resubmission |
| ACKED | `filled` | 1 (XLV 5/18) | False-negative; trade is real |

Plus 10 OLDER intents from before 5/18 are also stuck at ACKED locally
but are actually `filled` at broker (UNH 5/12, NVDA 5/11×2, AMD 5/11,
TSLA 5/11, ABT 5/8, MCD 5/8, AMD 5/8×2, TSLA 5/8, UNH 5/8). Those
trades are real; just the status field is stale.

**Fix scope expands**: the reconciliation sweep needs to handle both
directions:
- ACKED→`canceled`: cancel the local position record (it's phantom)
- ACKED→`filled`: update the intent status to FILLED (trade is real)

### 16.5 Local SELL trades vs broker — **17 of 19 real, 2 phantom**

Of the 19 SELL trades in `trades`:
- **17 actually filled** at the broker. Local exec_price has typical
  slippage of 0-170 bps vs broker fill price (acceptable).
- **2 phantom SELLs** never executed at broker:
  - 2026-05-21 XLV SELL 11 → broker `canceled` (covered in §16.3)
  - **2026-05-18 TSLA SELL 2** → broker `expired`

The TSLA case is a phantom we haven't addressed. If the broker still
holds those 2 TSLA shares we have a `BROKER_SYNC`-style discrepancy
that wasn't caught. Today's broker positions show 0 TSLA, so either:
- The TSLA had also failed to BUY originally (paired phantom), or
- It was later sold via another path

**Action**: verify whether those 2 TSLA shares were ever real (check
order history before 5/18) and if the local +pnl entry needs
correction.

### 16.6 Updated severity for earlier §13 findings

| § | Original claim | Revised after broker check |
|---|---|---|
| 13.1 | SELL trades bypass order_intents | **Still real bug** — 0 SELL intents in DB. Less catastrophic than I thought because 17/19 SELLs did fill, but the auditability gap remains. |
| 13.2 | XLV phantom +$24 P&L | **Confirmed phantom but already addressed** — Claude Code submitted fresh SELL today. Historical row in `trade_pnl_detail` is still wrong. |
| 13.3 | $36k cash-impact divergence | **Re-explained** — divergence is dominated by phantom positions (§16.2), not phantom BUYs across the board. Most BUYs did fill at broker. |
| 13.4 | News Sentiment time-exit | **Still real bug but moot for current positions** — AMZN/ABBV are phantom, so the 6/3 force-exit will fail at the broker with "insufficient shares". Code bug still needs fixing for the next time News Sentiment opens real positions. |

---

## 17. **Final consolidated bug list** (broker-verified)

In priority order:

### 🚨 1. Phantom position cleanup missing (NEW, root cause)

When a BUY intent → `canceled` or `expired` at broker, the local
`positions` row stays. **The bot is currently managing 3 positions
(ABBV, AMD, AMZN) that don't exist at Alpaca.** When it tries to SELL
them, the order will be rejected for insufficient shares.

**Fix**: in `verify_order_statuses()` or a new daily sweep, walk
`order_intents` with status='ACKED', poll Alpaca, and for any that
came back `canceled`/`expired`/`rejected`:
- Mark intent as FAILED in DB
- Reverse the optimistic position update (`positions.shares -=
  filled_qty_difference`)
- Mark the matching `trades` row as `is_phantom=1` or delete it

### 🚨 2. ACKED ↔ FILLED status drift (HIGH)

10+ intents are stuck at ACKED locally but actually FILLED at broker.
Same root cause as #1: `verify_order_statuses()` only walks current-run
trades.

**Fix**: same daily sweep as #1, in the `filled` branch, update intent
status to FILLED + broker_order_id.

### 🚨 3. SELL trades bypass `order_intents` entirely (MEDIUM-HIGH)

DB has 89 BUY intents, 0 SELL intents despite 19 SELL trades. Auditing
SELLs against the broker requires falling back to order_id lookup. The
code paths at `execution_engine.py:969` and `:2484` aren't producing
DB rows.

**Fix**: investigate why `create_order_intent(side='SELL')` isn't
persisting. Check if there's an early `continue` somewhere, a silently
failing commit, or a code path that bypasses these methods.

### 🚨 4. News Sentiment naive time-exit (HIGH, code bug — currently moot)

`@/Users/shreyaschickerur/CascadeProjects/investor-mimic-bot/src/strategies/strategy_news_sentiment.py:160-163`
fires SELL at `hold_days=7` with no profit/sentiment gate. Same anti-
pattern that caused 2026-05-18 ML Momentum bulk dump. Moot for AMZN/ABBV
(phantom) but will hit the next time News Sentiment opens real
positions.

**Fix**: mirror ML Momentum fix from `9f1471a` — gate
`days_held >= hold_days` exit on profit OR sentiment-score weakening.

### ⚠️ 5. Equal `capital_allocation` overwrites dynamic weights in DB (MEDIUM)

`@/Users/shreyaschickerur/CascadeProjects/investor-mimic-bot/src/core/execution_engine.py:591`
writes equal shares to `strategies.capital_allocation` on every run.
Sizing IS Sharpe-weighted (uses `strategy.capital` in-memory), but
observability (email, dashboards, queries) sees the wrong column.

**Fix**: in `_apply_allocations()`, also write the dynamic allocation
to the DB column.

### ⚠️ 6. Tax-aware exit unit tests failing (MEDIUM)

`test_rsi_extends_hold_at_day_250` and `test_factor_extends_hold_at_day_252`
fail: the "extend hold to cross 1-year LTCG threshold" logic emits a
SELL when it should defer. Currently no positions are near the 1-year
mark so the bug is dormant.

**Fix**: investigate the 250-365 day tax-aware extension code in
strategy_rsi_mean_reversion.py and strategy_factor_momentum.py.

### ⚠️ 7. `test_execution_engine_uses_opg_not_day_for_buys` failing (MEDIUM)

Possible OPG → DAY regression in BUY order placement. The recent
broker output shows orders being placed as expected OPG (multiple
`expired` lines on 5/27 morning indicate OPG orders waiting for open),
so this may be test-side only. Confirm.

### ⚠️ 8. Email script latent bugs (LOW)

`@/Users/shreyaschickerur/CascadeProjects/investor-mimic-bot/scripts/generate_daily_email.py:156`,
`:263`, `:265` filter `WHERE p.shares > 0` (same short-position bug
fixed in database.py at commit `9f1471a`). Line `:999`, `:1009` read
the misleading equal `capital_allocation` column.

**Fix**: change to `shares != 0` and consume the post-dynamic
allocation value once §5 is fixed.

### ⚠️ 9. Cross-strategy AMD purchasing on 2026-05-08 (DESIGN QUESTION)

Three strategies bought AMD on the same day during the double-trigger
period. With phantom-cleanup fix (#1) in place, this becomes less
severe. Still want explicit policy: should multiple strategies be
allowed to hold the same symbol independently?

### ✅ 10. cron-job.org timing buffer (TRIVIAL)

Shift cron-job.org daily fire from 00:30 UTC to 00:45 UTC to survive
ET timezone shifts and avoid OPG window collisions like 2026-05-20.
UI-only change.

### ✅ 11. Python 3.9/3.10 test compat (TRIVIAL)

`test_fetcher_respects_premium_flag` fails due to `str | None` in
`scripts/fetch_historical_data.py:79`. Add `from __future__ import
annotations` or upgrade test environment to Python 3.10+.

---

## 18. What I confirmed via broker is healthy

- **Account is healthy**: ACTIVE, $94k cash, $96k equity, $190k
  buying_power.
- **17 of 19 SELL trades** are real broker fills with normal slippage
  (0-170 bps).
- **Most BUY intents** actually filled at broker, just have stale local
  status.
- **The XLV issue is being closed today** by Claude Code's fresh SELL
  submission (5/28 22:23 UTC, status `accepted`).
- **No reconciliation pause/alert is firing** despite the phantom
  positions — meaning the recon logic itself needs strengthening
  (it should be detecting and flagging the ABBV/AMD/AMZN drift).

---

*Generated 2026-05-28 17:54, extended 18:15, 18:30, and 19:00
(post-commits `9f1471a`, `9796c1d`, `e7c06a4`, `9924c84`). Final
verification against Alpaca paper account 2026-05-28 18:50 CDT.*
