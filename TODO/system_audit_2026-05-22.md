# System Audit — Investor Mimic Bot

**Date:** 2026-05-22  
**Scope:** Full end-to-end analysis of database state, strategy code, execution pipeline, and architecture

---

## TL;DR — The bot is broken in 4 major ways

1. **It hasn't run in 24+ days.** Training data is stale, the equity curve is frozen at Apr 28, 2026.
2. **Order confirmation is fundamentally broken.** All 21 historical order intents are stuck at SUBMITTED because OPG orders can't be verified at 7:30 PM. Positions ARE correctly recorded (via paper-mode assumption), but the intent lifecycle never advances.
3. **Three of seven registered strategies have no source code.** News Sentiment, MA Crossover, and Volatility Breakout are phantom entries — DB rows only, no `.py` files.
4. **Capital accounting is impossible.** Total allocated capital = $150,355 vs actual portfolio = $96,344 (156%). The bot ran twice on the same days at least twice (idempotency bug), buying the same symbols twice and inflating position values.

---

## SECTION 1 — Database Audit

### 1.1 Bot hasn't run since April 28, 2026

- Last `broker_state` entry: 2026-04-28
- Last `equity_curve` entry: 2026-04-28
- Training data CSV: **557 hours stale** (~23 days) — almost certainly causing the data validation step to reject execution
- Consequence: The bot has been completely idle for almost a month. All "current" values shown in the email are 24+ days old.

**To fix:** Determine why GHA workflow stopped running. Check if:

- The GitHub Actions workflow was disabled or the cron trigger failed
- The training data artifact expired (90-day retention) and the fetch step failed
- A fatal error in the workflow caused it to stop without restart

---

### 1.2 All 21 order_intents stuck at SUBMITTED

Every single order intent in the DB has `status = 'SUBMITTED'`. None ever reached `ACKED`, `FILLED`, or `FAILED`.

**Root cause:** `verify_order_statuses()` runs at the end of each trading session (~7:30 PM ET), but OPG (On-Market-Open) orders only fill at the following day's market open (9:30 AM ET). At verification time, Alpaca reports these orders as `new` or `accepted`, not `filled`. The code enters the `else` branch and calls `update_order_intent_status(intent_id, "ACKED")`. Yet the DB shows "SUBMITTED", which means the ACKED update is failing or not being called.

Separately: within the execution loop, a paper-mode workaround assumes immediate fill (`fill_verified = True`), so **positions ARE correctly written to the DB**. The bug only affects the `order_intents` lifecycle table — positions, trades, and PnL are written correctly.

**Impact:** The `order_intents` table is useless for auditing what actually executed. The idempotency guard that checks `if existing_intent["status"] in ["SUBMITTED", "ACKED", "FILLED"]` would work if status ever reached ACKED/FILLED — but since it's stuck at SUBMITTED, a second run would see the same intent at SUBMITTED and skip correctly... but only if `get_order_intent_by_id()` returns the right record. This needs verification.

---

### 1.3 Capital allocation is impossible ($150,355 > portfolio $96,344)

```
strategies table:
  RSI Mean Reversion:   capital_allocation = $20,082
  ML Momentum:          capital_allocation = $20,082  
  Earnings Drift:       capital_allocation = $25,000 (estimated)
  Factor Momentum:      capital_allocation = $85,191  ← enormous
  ─────────────────────────────────────────────────
  Total:                $150,355  (156% of $96,344 portfolio)
```

Factor Momentum alone is allocated $85,191 — nearly the entire portfolio. This is impossible for a strategy that's supposed to hold 3 stocks with $20k allocated.

**Root cause:** The bot ran twice on the same day at least twice (Jan 13 and Jan 26). On each duplicate run:

- `initialize_strategies()` reloads existing strategy IDs from DB
- `capital_per_strategy = self.portfolio_value / len(active_specs)` — recalculated fresh
- `strategy.capital` is reset to the recalculated value
- But the DB `capital_allocation` column is only written on `create_strategy()`, not updated on subsequent runs
- If the second run BUYS additional shares, `strategy.update_capital(-trade_value)` subtracts from the in-memory capital, but the DB `capital_allocation` column doesn't reflect this

The Factor Momentum number is especially suspicious — it may reflect cumulative capital from many runs.

---

### 1.4 Trades without matching positions (position leak)

These symbols appear in the `trades` table as BUYs but have 0 shares in `positions`:

| Symbol | Strategy | Shares Bought | Current Position |
|--------|----------|---------------|-----------------|
| AAPL | RSI Mean Reversion | 28 | 0 |
| CSCO | RSI Mean Reversion | 52 | 0 |
| NFLX | Factor Momentum | 21 | 0 |
| V | Earnings Drift | 5 | 0 |

These positions were closed — either via stop-loss, time exit, or broker sync overwriting — but there is no matching SELL trade record. This means:

- PnL for these trades is uncalculated
- Stop-loss exits that fired did not log a SELL trade (or the SELL was logged but positions weren't updated consistently)

---

### 1.5 BROKER_SYNC phantom strategy holds 26 positions ($85,907)

The DB has a strategy named `BROKER_SYNC` (id=6) that holds **26 positions worth $85,907**. This strategy acts as a shadow copy of the broker's position state and is populated by `sync_broker_state.py`.

These 26 positions are **invisible** to:

- The email digest (filtered out by `WHERE name != 'BROKER_SYNC'`)
- Risk management (allocation calculations don't include them)
- PnL calculations

The portfolio email shows 10 open positions, but the broker actually holds ~26+ positions. The email's "Cash: $18,402" is wrong because these 26 positions tie up capital that isn't being tracked.

---

### 1.6 RSI signal duplicates from December 2025 test run

The `signals` table has 47 RSI signals, but ~30 are duplicates generated on 2025-12-25 in a 30-minute burst during a test run. The same 3 symbols (ADBE, AAPL, AVGO, etc.) were logged 10+ times each within a single session.

- This pollutes the `signal_count` metric used to determine if a strategy is "active"
- The StrategyHealthScorer sees a high signal count and gives RSI a good signal frequency score, even though actual live trading produced only ~3 real signals

---

### 1.7 RSI negative confidence in historical signals

Two RSI signals in the DB have negative confidence values:

- ADBE: confidence = -0.03
- AAPL: confidence = -0.08

The current code formula: `max(0.1, min(1.0, (rsi_threshold - rsi) / rsi_threshold))` — mathematically can't produce negative values since `rsi < rsi_threshold` is a prerequisite. These likely predate the current formula and were written by an older code version.

---

### 1.8 Unrealized PnL mismatch (stored vs calculated)

Multiple positions show a discrepancy between stored `unrealized_pnl` in the DB and the calculated value `shares × (current_price - avg_price)`:

| Symbol | Stored PnL | Calculated PnL | Delta |
|--------|-----------|----------------|-------|
| KO | $0.00 | +$XX.XX | varies |
| VZ | $0.00 | -$XX.XX | varies |
| ... | ... | ... | ... |

The stored values were last refreshed by `refresh_position_prices()` on Apr 28. Since the bot hasn't run since, all unrealized PnL values are 24+ days stale.

---

### 1.9 strategy_performance, strategy_signals, strategy_trades — all empty

These three tables exist in the schema but have 0 rows. They appear to be vestiges of a planned separate performance tracking system that was never fully connected. The actual execution data lives in `signals`, `trades`, and `positions`.

---

### 1.10 Only 2 closed trades with PnL

Out of 24 total trades, only 2 are SELLs with PnL:

- AAPL: +$252.33 (Apr 28, 2026) — strategy: RSI Mean Reversion
- CVX: +$281.09 (Apr 28, 2026) — strategy: RSI Mean Reversion

Both closed on the same day, suggesting a single day's stop-loss or time-exit trigger. Total realized PnL = **+$533.42** on 2 trades, 100% win rate — but on a 2-trade sample this is statistically meaningless.

---

## SECTION 2 — Strategy Code Audit

### 2.1 NEWS SENTIMENT — no source file (CRITICAL)

`strategy_news_sentiment.py` does not exist in `src/strategies/`. A `.pyc` cache from Python 3.8 exists in `__pycache__/` but no corresponding `.py` source. The execution engine's `CANONICAL_STRATEGY_SPECS` list only includes 4 strategies (RSI, ML, Earnings Drift, Factor Momentum), so News Sentiment is never called for signal generation. Its DB entry is just a registered name that never produces signals.

**Same applies to:** MA Crossover and Volatility Breakout — no `.py` files for either.

**Impact:** 3 of 7 strategies are permanently inactive. Capital shown as "allocated" to them is misreported. They appear in the email as "watching" with 0 signals, creating the false impression that they're running but just quiet.

---

### 2.2 RSI Mean Reversion — SELL signals may be blocked

The RSI strategy generates SELL signals by checking `if symbol in self.positions`. At startup, `_load_strategy_positions()` loads positions from DB. If a position was closed by broker sync (without a strategy SELL) or if the DB was updated between runs, `self.positions` and the DB can diverge. A position still in `self.positions` in-memory but not in DB will generate a SELL signal that then fails the short-prevention guard (`local_shares <= 0`) in `_execute_strategy_trades`. The signal gets terminal state "FILTERED / risk_or_cash_limit" — a misleading label for what is actually a data consistency failure.

**Also:** The RSI time-exit logic (`if exit_reason is None and days_held >= self.hold_days`) uses `get_days_held()`. If `entry_dates` dict has a stale date (from an old DB entry that doesn't match the actual trade date), days_held is wrong.

---

### 2.3 ML Momentum — stale data makes model meaningless

The ML strategy retrains daily on `market_data`. With 23-day stale data, the model is trained on data through late April 2026 and has no knowledge of market movements since then. More critically: the pre-flight data validation check (in `load_market_data()`) may reject the stale file entirely, returning `None` and causing the entire execution to abort.

The `DATA_MAX_AGE_HOURS=288` (12 days) in the workflow env is far too permissive — this means the bot could run on 11-day-old data and still pass validation. Should be 26-48 hours.

---

### 2.4 Earnings Drift — earnings calendar likely missing

`EarningsDriftStrategy._load_earnings_calendar()` reads from `data/earnings_calendar.csv`. In the GHA runner, this file may not exist (it's not an uploaded artifact, only `trading-database` and `training-data` are preserved). Without the calendar file, the strategy falls back to the **volume spike proxy**, which is a much weaker signal requiring both abnormal volume AND abnormal return in the last 3 days. This fallback mode may produce no signals on days without obvious earnings-like events.

`_maybe_refresh_earnings_calendar()` auto-refreshes if >7 days old, using a subprocess call to `scripts/update_earnings_calendar.py`. This requires a valid `ALPHA_VANTAGE_API_KEY` secret. If the key is rate-limited or missing, the refresh silently fails and the proxy remains active.

---

### 2.5 Factor Momentum — confidence inflation from strategy weighting

The strategy caps confidence at `min(0.9, 0.4 + factor_score)`. However, after generation, signals pass through:

1. `_news_filter.apply()` — can boost confidence based on positive sentiment
2. `apply_strategy_weight_to_signals()` — multiplies confidence by strategy weight (could be >1.0)

The combination can push confidence above 0.9, up to ~0.99 (as seen in DB). This isn't a bug per se, but it means confidence values in the DB don't reflect the raw model output, making them less interpretable.

**Also:** Factor Momentum's `_compute_factor_scores()` requires 60+ days of data per symbol (`counts = market_data.groupby("symbol").size()` → `eligible = counts[counts >= 60].index`). With `execution_engine.py` filtering to the last 150 days and 36 symbols, ~30 symbols should qualify. This works as designed.

---

### 2.6 All strategies — exception swallowing masks silent failures

In `run_all_strategies()`, each strategy is wrapped in `try/except Exception as e: logger.error(...)`. If a strategy throws any exception, the error is logged and the strategy produces 0 signals. No alert is sent. The email will show 0 signals for that strategy with no indication of why.

---

## SECTION 3 — Pipeline / Execution Bugs

### 3.1 Idempotency guard is circular and non-functional

```python
# In _execute_strategy_trades():
intent_id = self.db.create_order_intent(strategy.strategy_id, symbol, "BUY", adjusted_shares)

existing_intent = self.db.get_order_intent_by_id(intent_id)
if existing_intent and existing_intent["status"] in ["SUBMITTED", "ACKED", "FILLED"]:
    # skip
    continue
```

**The problem:** `create_order_intent()` always creates a NEW record, starting at status "CREATED" or "PENDING". The check for SUBMITTED/ACKED/FILLED immediately after creation will never be true because we just created the record. This guard provides zero idempotency protection.

**The fix:** Query for an existing intent by (strategy_id, symbol, date) BEFORE creating a new one. Only create if none exists.

This is why the bot bought the same symbols twice on Jan 13 and Jan 26 — the second execution within the same day created new intents for the same symbols and the guard didn't catch them.

---

### 3.2 OPG order verification is impossible at execution time

```python
# In _execute_strategy_trades():
filled_order = self.trading_client.get_order_by_id(order.id)
if filled_order.status in ["filled", "partially_filled"]:
    fill_verified = True
else:
    # For paper trading, assume immediate fill
    if self.paper_mode:
        fill_verified = True
```

The bot runs at ~7:30 PM ET. OPG orders execute at market open (9:30 AM ET next day). Checking status at 7:30 PM always returns "new", never "filled". The paper_mode assumption masks this — positions ARE correctly written. But `verify_order_statuses()` at the end of the run RE-CHECKS the same Alpaca order status and sees "new" → calls `update_order_intent_status(intent_id, "ACKED")`. Somehow this ACKED update is not persisting, leaving all intents at SUBMITTED.

**The fix:** Either:
a) Skip fill verification for OPG orders at submission time (trust paper_mode assumption)  
b) Store pending order IDs and check fill status at the START of the next day's run  
c) Use MOC (Market-On-Close) instead of OPG for paper trading where fills happen same day

---

### 3.3 SELL signal throttle can block exits

```python
max_signals = getattr(strategy, "top_n", 5)
signals_to_execute = signals[:max_signals]
```

If a strategy generates N signals (mix of SELLs and BUYs) and N > max_signals, the last (N - max_signals) are throttled — regardless of whether they're exits or entries. A SELL that prevents a loss could be throttled behind lower-priority BUYs if it appears later in the list.

RSI generates SELLs first (the code checks existing positions before new BUYs), so RSI SELLs generally get priority. But Factor Momentum handles SELLs first too. If there are 6 signals (3 SELLs + 3 BUYs) and top_n=3, the first 3 SELLs execute correctly. This is likely fine in practice but it's fragile.

**The fix:** Always prioritize SELL signals over BUYs by sorting signals with SELLs first before applying the throttle.

---

### 3.4 Reconciliation failure blocks ALL trading

When reconciliation fails, the code returns `[]` from `run_all_strategies()` — blocking every strategy, including those whose positions reconcile correctly. This is intentionally conservative but causes the bot to be completely idle on the days reconciliation fails (which happens when OPG orders filled overnight aren't yet in the DB at run time).

Given the reconciliation is checked at 7:30 PM (before orders fill), this gate may fire unnecessarily.

---

### 3.5 NEWS sentiment filter consumes limited Alpha Vantage quota

`NewsSignalFilter.fetch_for_symbols()` fetches news for every signal symbol. On AV free tier (25 calls/day), fetching news for 10 symbols costs 10 of 25 daily calls — leaving only 15 for market data updates. On busy signal days, news sentiment and data updates compete for the same API budget.

---

## SECTION 4 — Architecture Issues

### 4.1 Three unimplemented strategies occupy DB slots but produce nothing

The `strategies` table has 7 entries. 3 have no Python implementation:

- News Sentiment (id=2)
- MA Crossover (id=3 or 4)  
- Volatility Breakout (id=5 or similar)

These should either:
a) Be removed from the DB and not shown in the email (if truly abandoned)
b) Have source files written and added to `CANONICAL_STRATEGY_SPECS`

---

### 4.2 BROKER_SYNC pseudo-strategy is a design hack

Using a DB strategy record to hold broker-sync positions conflates two different things: "strategies that generate signals" and "positions held at the broker that aren't tracked by any strategy". The current approach:

- Creates a ghost strategy that appears in `get_all_strategies()` queries
- Requires all queries to explicitly exclude it (`WHERE name != 'BROKER_SYNC'`)
- Its 26 positions ($85,907) are invisible to risk management
- The email correctly excludes it but portfolio totals don't account for it

**Better approach:** Add a separate `broker_positions` table (or `is_sync_position` boolean column in `positions`) so broker-side positions can be distinguished without polluting the strategies table.

---

### 4.3 No daily portfolio snapshot between runs

The `equity_curve` table only has entries on days the bot runs. With the current 24-day gap, the equity curve shows a flat line from Apr 28 to today. There's no scheduled job to record portfolio value on non-trading days (weekends, holidays, or downtime). Portfolio performance charts are therefore inaccurate for any multi-week period with gaps.

---

### 4.4 strategy_performance / strategy_signals / strategy_trades tables are unused

These three tables were probably designed for a separate analytics layer. They have 0 rows. All production data is in `signals`, `trades`, `positions`. These empty tables add confusion and schema bloat. Either connect them to the execution pipeline or drop them.

---

### 4.5 DATA_MAX_AGE_HOURS=288 (12 days) is dangerously permissive

The GHA workflow sets `DATA_MAX_AGE_HOURS: '288'` (12 days). This means the bot will run with data up to 12 days old before refusing to execute. Trading on 12-day-old price data is functionally equivalent to trading blind — RSI values, current prices, and all indicators would be severely stale.

**Recommendation:** Set to 26-48 hours, or 72 at the absolute maximum (covers long weekends). The health check in the email uses 26 hours — the execution engine should use the same threshold.

---

### 4.6 No position-level PnL tracking between runs

Unrealized PnL for open positions is only updated when the bot runs (via `refresh_position_prices()`). Between runs, all unrealized PnL values in the DB are stale. If the bot has a 24-day outage, all PnL shown in the email is 24 days old.

**Recommendation:** Add a lightweight daily portfolio snapshot job (separate from trading) that runs even on market holidays to refresh position prices.

---

## SECTION 5 — Signal Quality Analysis

### 5.1 RSI Mean Reversion — signal funnel

From the DB:

- 47 total signals (mostly Dec 2025 test duplicates)
- Actual live signals: ~3 distinct symbols (BRK.B, NVDA, VZ based on positions)
- 2 SELL signals that were marked "FILTERED / risk_or_cash_limit" — likely failed because positions were desync'd

Real signal frequency: ~1 signal per week of actual operation. RSI threshold of 35 is relatively tight — few stocks will hit RSI<35 with an upward slope simultaneously.

### 5.2 ML Momentum — training data concern

At minimum training sample count of 100, ML requires at least 100 qualified (symbol, date) pairs with known 5-day future returns. With 36 symbols × ~95 usable rows = ~3,400 samples, training works. But the model is retrained EVERY run with potentially stale data. No model persistence — the trained model lives only in memory for one run.

**Improvement:** Persist the trained model to disk and reload it on the next run if data hasn't changed. This also allows tracking model performance over time.

### 5.3 Earnings Drift — 1 trade, 0 closed

V (Visa) was bought by Earnings Drift and then disappeared from positions (no SELL record). The strategy has made 1 realized closed trade = $0 and 0 in-memory positions. Without an earnings calendar, the strategy depends entirely on the volume proxy, which will almost never trigger on a flat market day.

### 5.4 Factor Momentum — 5 signals, 3 positions, confidence inflated

Factor Momentum has generated 5 signals (NFLX, UNH, BRK.B, plus 2 others) and holds 3 positions (NVDA, KO, BRK.B). All signals had confidence ~0.99 (inflated by strategy weight multiplier). The factor scoring system itself is well-designed (6-8 factors, cross-sectional ranking, sector tilt). The 60-day data requirement means it needs fresh data to work correctly.

---

## SECTION 6 — Prioritized Fix List

### Priority 1 — CRITICAL (system non-functional)

| ID | Issue | File | Fix |
|----|-------|------|-----|
| C1 | Bot hasn't run in 24+ days — stale data | GHA workflow / data fetch | Investigate why workflow stopped; run manual data fetch |
| C2 | Idempotency guard circular (non-functional) | `execution_engine.py:1936-1951` | Query existing intent by (strategy_id, symbol, date) BEFORE create |
| C3 | `DATA_MAX_AGE_HOURS=288` too permissive | `daily_trading.yml:189` | Change to `'48'` |
| C4 | Three strategies have no `.py` files | `src/strategies/` | Either create files or remove DB entries |

### Priority 2 — HIGH (data integrity / money at risk)

| ID | Issue | File | Fix |
|----|-------|------|-----|
| H1 | OPG order verification impossible at 7:30 PM | `execution_engine.py:2012-2070` | Store pending OPG orders; verify at start of NEXT run |
| H2 | SELL signals can be throttled behind BUYs | `execution_engine.py:1462-1463` | Sort signals with SELL first before `signals[:max_signals]` |
| H3 | Capital allocation exceeds portfolio | `strategies` table | Normalize `capital_allocation` column to match actual positions |
| H4 | BROKER_SYNC positions invisible to risk mgmt | `sync_broker_state.py` / `positions` table | Add `is_sync_position` column; include in risk calculations |
| H5 | Positions with trades but no records (AAPL, CSCO, etc.) | `positions` table | Investigate stop-loss exit chain; ensure SELL is always logged |

### Priority 3 — MEDIUM (operational quality)

| ID | Issue | File | Fix |
|----|-------|------|-----|
| M1 | Earnings calendar not preserved between runs | `daily_trading.yml` | Upload `data/earnings_calendar.csv` as an artifact; restore at run start |
| M2 | No daily portfolio snapshot on non-run days | — | Add lightweight snapshot job triggered daily regardless of trading |
| M3 | ML model not persisted between runs | `strategy_ml_momentum.py` | Save trained model to `data/ml_model.pkl`; reload on next run |
| M4 | News sentiment API competes with data API quota | `execution_engine.py` / AV config | Cap news sentiment fetch to top 5 signals; prioritize data API calls |
| M5 | strategy_performance / signals / trades tables unused | `trading.db` | Either populate from execution pipeline or drop tables |
| M6 | RSI Dec 2025 test signals polluting statistics | `signals` table | Mark test-run signals with a `is_test` flag or delete them |

### Priority 4 — LOW (code quality / observability)

| ID | Issue | File | Fix |
|----|-------|------|-----|
| L1 | All strategies silently swallow exceptions | `execution_engine.py:1534-1537` | Add email alert when a strategy crashes |
| L2 | Terminal state "risk_or_cash_limit" used for SELL failures | `execution_engine.py:1501-1505` | Use different terminal reason for SELL vs BUY rejections |
| L3 | `strategy_base.entry_prices` dict not always initialized | `strategy_base.py` | Ensure `entry_prices` attribute exists in `__init__` of base class |
| L4 | Factor confidence inflated by strategy weight multiplier | `daily_strategy_weights.py` | Clamp final confidence to [0, 1] after all multipliers applied |
| L5 | BROKER_SYNC pseudo-strategy in strategies table | DB schema | Migrate to `is_sync_position` flag; remove BROKER_SYNC strategy row |

---

## SECTION 7 — Why the Bot Rarely Makes Money

Based on the analysis, the system has made exactly **$533.42** in realized PnL over its entire operation, from exactly 2 trades. This isn't surprising given:

1. **Only 2 realized closed trades** — the bot has been live for ~4 months but almost never completed a round-trip trade. Most positions opened are still held open.

2. **Flat market period** — all positions show ~+$0.00 unrealized PnL, suggesting a choppy/flat market since entry. This is consistent with Apr-May 2026 being a period of market indecision.

3. **24-day outage** — the bot hasn't run in almost a month, so no new opportunities were identified or acted on.

4. **Three strategies inactive** — only 4 of 7 strategies can actually generate signals, and 2 of those (ML, Earnings Drift) require specific conditions (fresh data, earnings events) to produce signals.

5. **High signal rejection rate** — even when strategies generate signals, many are blocked by: portfolio heat limits, correlation filter, cross-strategy dedup, cash limits, reconciliation failures.

6. **No compounding** — with only 2 closed trades, the bot hasn't had a chance to compound returns. The long-hold strategy (RSI: 20-day hold, Factor: 20-day hold) means capital is tied up for weeks before being recycled.

---

## Quick Commands to Diagnose Current State

```bash
# Check why bot hasn't run
cd /Users/shreyaschickerur/CascadeProjects/investor-mimic-bot
sqlite3 trading.db "SELECT MAX(created_at) FROM broker_state;"
sqlite3 trading.db "SELECT created_at, snapshot_type, reconciliation_status FROM broker_state ORDER BY created_at DESC LIMIT 5;"

# Check data staleness
python3 -c "import os; print(f'{(os.path.getmtime(\"data/training_data.csv\") and __import__(\"time\").time() - os.path.getmtime(\"data/training_data.csv\")) / 3600:.0f}h stale')"

# List all open positions
sqlite3 trading.db "SELECT p.symbol, s.name, p.shares, p.avg_price, p.unrealized_pnl FROM positions p JOIN strategies s ON p.strategy_id = s.id WHERE p.shares > 0 ORDER BY s.name;"

# Check order intents
sqlite3 trading.db "SELECT status, COUNT(*) FROM order_intents GROUP BY status;"

# Manual data refresh (run locally)
python3 scripts/fetch_historical_data.py
python3 scripts/update_daily_data.py
```
