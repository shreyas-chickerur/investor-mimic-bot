# P2 strategy re-validation — post-execution-fix (2026-07-10)

Kickoff report, not a conclusive re-validation. Triggered automatically once
order-level fill-rate recovery held for 3 consecutive post-fix trading days.
**Headline finding: the clean, broker-confirmed sample is still too thin to
re-validate or disable anything.** This report documents what execution
recovery looks like so far, why the prior evidence is unreliable, and what
has to happen before a real re-validation can be written.

## Background

PR #60 (`c488ae8`, 2026-07-02) switched every order placement from
`TimeInForce.OPG` to `TimeInForce.DAY`. OPG (opening-auction) orders expired
unfilled ~87% of the time (126 FAILED vs 19 FILLED buys, 2026-05-20 →
2026-07-02 — confirmed again below), so paper mode's optimistic fills
recorded trades and P&L that mostly never happened at the broker. Per
`CLAUDE.md`, all per-strategy evidence from before 2026-07-03 — including
`docs/research/EVIDENCE_2026-06.md` and the "live +$714" justification cited
in `config/trading_config.yaml` for re-enabling Factor Momentum — must be
treated as contaminated.

## Methodology

Source: `trading.db` restored from the `data` branch SQL backup
(`db/trading.sql`, current as of the 2026-07-10 05:45 UTC run — the GitHub
Actions artifact download was blocked by this environment's egress policy,
so the branch backup was used instead; contents are identical, the workflow
uploads both from the same run).

"Broker-confirmed" means the order's row in `order_intents` has
`status='FILLED'` — i.e., the broker actually filled it, independent of what
`trades`/`trade_pnl_detail` optimistically recorded in paper mode. Every
number below is joined against `order_intents` on `broker_order_id`; nothing
is taken from `trades`/`trade_pnl_detail` at face value.

## a) Order-level fill-rate recovery

Settled BUY orders (`status IN ('FILLED','FAILED')`), post-fix
(2026-07-03 → 2026-07-09, excluding today's not-yet-trued fills):

| Date | Filled | Failed | Fill rate |
|---|---|---|---|
| 2026-07-07 | 4 | 0 | 100% |
| 2026-07-08 | 1 | 0 | 100% |
| 2026-07-09 | 1 | 0 | 100% |

Overall post-fix settled fill rate: **100% (6/6)**. Three consecutive days
≥60% — the threshold that triggered this report.

**Caveat — the sample is thin two ways, not one:**
- **Volume**: 6 settled BUYs total across 3 days (contrast: pre-fix window
  2026-05-20→2026-07-02 had 155 settled BUYs, 21 filled / 132 failed = 13.5%
  fill rate — consistent with the ~87%-unfilled figure in `CLAUDE.md`).
- **Coverage**: those 6 fills came from only **3 of the 7 enabled
  strategies** — RSI Mean Reversion (2), Earnings Drift (2), MA Crossover
  (2) — plus 1 Cash Sweep. **Factor Momentum, Volatility Breakout, Dual
  Momentum, and Sector Rotation have placed zero BUY orders since the fix**
  (no signals fired yet, not a fill problem, but it means zero fill-rate
  evidence exists for them post-fix).

`run_health.json`/`run_history` still shows the `expect:Order fill rate
healthy` check YELLOW on every post-fix run (07-06 through 07-10) — this is
expected and correct: that check almost certainly uses a rolling window
(e.g. 14d) that still mixes in the pre-fix contaminated days, and will clear
on its own as the window rolls past 2026-07-02.

## b) Realized P&L: broker-confirmed closes, pre-fix vs post-fix

This is the headline number. Every row in `trade_pnl_detail` was joined back
to `order_intents` (via `trades.order_id = order_intents.broker_order_id`)
to check whether **both** the entry and the exit leg were actually filled by
the broker.

**Result: of 36 rows in `trade_pnl_detail` across the entire history
(2026-04-30 → 2026-07-10), only 3 have both legs broker-confirmed FILLED —
and all 3 are tail-end closes of positions originally opened on 2026-05-29
(pre-fix), that sat unable to exit for weeks and only closed after the
07-02 fix:**

| Strategy | Symbol | Entry order filled | Exit order filled | Gross P&L | Return |
|---|---|---|---|---|---|
| Factor Momentum | UNH | 2026-05-29 | 2026-07-10 | +$48.57 | +12.7% |
| News Sentiment (disabled, wind-down) | VZ | 2026-05-29 | 2026-07-06 | +$7.93 | +1.5% |
| News Sentiment (disabled, wind-down) | VZ | 2026-05-29 | 2026-07-07 | +$1.56 | +0.3% |

**There is currently zero complete round-trip trade where both entry AND
exit happened after the fix.** The fix has demonstrably unstuck old
positions (proof the DAY-order mechanism works — these exits had failed
repeatedly as OPG before finally filling), but no strategy has completed a
full post-fix trade cycle yet.

The other 33 `trade_pnl_detail` rows (Factor Momentum ×4 total incl. the one
above, ML Momentum ×17, News Sentiment ×11 total) rest on at least one leg
still showing `SUBMITTED`/`ACKED`/`FAILED` at the broker — i.e., phantom
paper fills. Notably, the AMD trade (+$752.02, Factor Momentum, 2026-04-30)
that anchors the "live +$714" comment re-enabling Factor Momentum in
`config/trading_config.yaml:195` has a buy leg that shows `SUBMITTED`, never
`FILLED` — **that justification does not hold up under this join.**

Aggregate pnl/win-rate by strategy from the full (unconfirmed)
`trade_pnl_detail` table, shown only for context on what the prior evidence
was built from — **do not use these to make decisions**:

| Strategy | Trades | Win rate | Total gross P&L | Avg hold (d) |
|---|---|---|---|---|
| Factor Momentum | 4 | 75.0% | +$812.18 | 8.8 |
| ML Momentum (disabled) | 17 | 29.4% | −$489.28 | 5.3 |
| News Sentiment (disabled) | 11 | 18.2% | −$517.04 | 8.5 |

(Pairs Trading, disabled, has no trade_pnl_detail rows at all — it never
opened a position; consistent with its 2026-06 evidence.)

## c) Enabled strategies — pulling their weight?

**Cannot be answered yet.** With one broker-confirmed closed trade
(Factor Momentum/UNH, +$48.57) across all 7 enabled strategies, there is no
statistical basis to say any enabled strategy is or isn't earning its
allocation on real fills. Deployed capital also confirms very little is
actually at risk yet: as of 2026-07-10, non-sweep, strategy-attributed
position market value is ~$4,534 (MSFT $1,153 under Earnings Drift, MU+UNH
$1,855 under Factor Momentum, HD+WFC+WM $1,526 under MA Crossover) against a
$96,129 total portfolio — under 5%. RSI Mean Reversion, Volatility
Breakout, Dual Momentum, and Sector Rotation currently show **zero
strategy-attributed open positions** (their positions have either not been
opened yet or — see caveat below — were reattributed to the broker-sync
bucket).

**Data-quality caveat worth flagging**: `positions` currently carries an
11-position, $5,757 bucket under a synthetic `strategy_id=5` named
`BROKER_SYNC`, including a short VZ position (−26 shares) and several
symbols (CMG, CSCO, GIS, PSX, QCOM, SPGI, UBER, XLV) that were bought under
real strategy IDs in `trades`/`order_intents` (e.g. CMG and WM were bought
under MA Crossover's strategy_id in `order_intents`) but show up under
`BROKER_SYNC` in current `positions`. This looks like the reconciliation
auto-sync (`sync_broker_state.py`) re-attributing positions it couldn't
match cleanly to their originating strategy — not a P2 scope, but it means
strategy-level position attribution cannot be fully trusted right now, and
should be looked at before final per-strategy capital decisions are made off
live data.

## d) The three disabled strategies — worth a fresh OOS eval?

Their 2026-06 disable evidence was itself untouched by the OPG/paper-fill
bug (it came from the production-parity **backtester**, not live paper
trades — see `EVIDENCE_2026-06.md`), so the execution fix does not, by
itself, invalidate those verdicts. Recommendation per strategy:

- **ML Momentum** — disable evidence (purged-OOS accuracy near-random on
  91/91 walk-forward windows) is a model-quality finding, orthogonal to
  order execution. **No re-eval warranted from this fix alone.** The
  existing `EXP-2026-06-22-ml-orthogonal-features` experiment
  (`config/strategy_experiments.yaml`, review_date 2026-07-06, now
  **overdue by 4 days**) is the right vehicle for any revival attempt —
  chase that up separately.
- **News Sentiment** — disable evidence was "structurally unvalidatable
  offline" (live RSS lookahead), not an execution problem. Its wind-down
  position (VZ) is exactly the one that got stuck failing-to-exit for weeks
  under OPG and just closed under the DAY fix — that's a good sign the
  wind-down mechanism itself now works, but says nothing about the
  strategy's edge. **No re-eval warranted from this fix alone**; its
  separate `EXP-2026-06-22-news-pit-recording` experiment (review_date
  2026-09-22) continues on its own timeline.
- **Pairs Trading** — disabled for cointegration/half-life economics (0/5
  pairs passed), unrelated to fills; it never even opened a position, so
  there's nothing execution-related to re-check. Its
  `EXP-2026-06-22-pairs-universe-screen` experiment (review_date
  2026-07-22) is the active vehicle.

None of the three disabled strategies' original disable rationale rested on
live fill data, so this execution fix does not on its own justify
re-enabling any of them. Treat their existing experiment tracks
(`STRATEGY_CHANGELOG.md`) as the path back, independent of this report.

## e) Cash-sweep allocation

Cash sweep (SPY, strategy_id 12) currently holds $71,412 market value out of
$81,778 total invested (positions) value — **87.3%**, matching the ~88%
figure in `CLAUDE.md`, and 74.3% of the full $96,129 portfolio. This
ballooned because strategies couldn't fill entries (OPG), so idle cash kept
parking in the sweep. Now that entries are filling (§a), the sweep
proportion should mechanically shrink as strategies deploy capital — but
that hasn't happened yet (still only ~5% deployed in strategy-attributed
positions as of today, §c). **Recommendation**: don't change the sweep
target yet. Re-check the sweep percentage in 2-3 weeks once strategies have
had a real chance to deploy under DAY orders; if it's still >70% at that
point with strategies generating signals that pass the funnel, that would
indicate a different problem (e.g. the risk/correlation funnel or capital
allocator, not execution) worth its own investigation.

## f) Prioritized recommendations

1. **Do not change any strategy's `disabled`/allocation config off this
   report.** The clean sample (1 fully post-fix-confirmed close, 3 total
   confirmed closes counting pre-fix-opened positions) is far too small.
2. **Re-run this re-validation in 2-3 weeks** (roughly 2026-07-24 to
   2026-07-31), once more strategies have had signals fire and complete full
   post-fix entry→exit cycles. Target: at least 30 broker-confirmed closed
   trades per strategy before evaluating edge (same bar as the OOS
   backtester gate in `EVIDENCE_RUNBOOK.md`), or at minimum enough trades
   per strategy for a directional read.
3. **Fix `config/trading_config.yaml:195`'s comment** — "Re-enabled: live
   P&L +$714" cites a phantom fill (§b); either remove the live-P&L
   justification or replace it once real post-fix evidence exists.
4. **Investigate the `BROKER_SYNC` position-attribution issue (§c)**
   before the next capital-allocation decision — it currently obscures which
   strategy actually owns ~$5,757 of open positions including a short VZ
   line that shouldn't exist under any currently-enabled strategy.
5. **Chase the overdue `EXP-2026-06-22-ml-orthogonal-features` review**
   (due 2026-07-06, 4 days overdue as of this report) — unrelated to
   execution, but stale.
6. Leave the cash-sweep target alone for now (§e); revisit alongside the
   2-3 week re-validation.

## Confidence scoping

Every number in §a is based on 6-7 settled orders across 3 trading days —
directionally strong (100% vs the ~13.5% pre-fix baseline) but not a large
sample. Every number in §b is based on n=1 (or n=3 if counting the
pre-fix-opened, post-fix-closed trades) — **not enough to draw any
per-strategy performance conclusion, full stop.** This report exists to
establish a clean baseline and a re-check date, not to make a keep/disable
call.
