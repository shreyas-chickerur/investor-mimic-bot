# Investor Mimic Bot

A production-grade, fully-automated systematic paper-trading platform: a suite of
strategies gated by out-of-sample evidence, executed once daily against the
Alpaca paper API through a self-healing GitHub Actions pipeline, with a SQLite
database persisted as the single source of truth between runs.

> **Status: decommissioned (July 2026).** It ran unattended in production every
> trading day from December 2025 to July 2026. The automation is intentionally
> switched off; this repository is preserved as an engineering case study. See
> [Outcome & honest retrospective](#outcome--honest-retrospective).

---

## Why this repo is worth reading

The interesting part isn't the trading — it's the **reliability and governance
engineering** around an autonomous system that mutates real state every day with
no human in the loop:

- **Self-healing execution.** Every run reconciles the local database against the
  broker, auto-syncs on drift, and retries before it will trade — and blocks
  trading outright if it still can't agree. A run reaches `SUCCESS` only through
  an allow-list health gate.
- **The database *is* the state.** Positions, trades, signals, run history, and
  stop-loss state all persist in a SQLite file passed between otherwise-stateless
  CI runs as an artifact. Every schema change ships with a migration tested
  against a populated, production-shaped fixture.
- **Evidence-based strategy governance.** Strategies are enabled or disabled by
  out-of-sample evidence, re-validated quarterly, with the decision provenance
  checked into the repo. **Three strategies are disabled** because they failed
  honest validation (near-random purged-OOS accuracy; no cointegrating pairs;
  unvalidatable look-ahead). The system is built to tell the truth about itself.
- **Defense in depth.** Direction-aware stop-losses, a drawdown kill-switch
  measured on the alpha sleeve, regime/correlation/risk funnels, idempotency
  guards against duplicate runs, and a dead-man's-switch heartbeat.
- **Operable under failure.** ~750 tests, CI tripwires that catch a class of
  outage that once took the system down, an incident runbook, and a
  `make diagnose` that reconstructs any run's state from its artifacts.

## Architecture

```text
cron-job.org ──dispatch──► GitHub Actions (daily_trading.yml, ~65 steps)
                                │
        download DB artifact ──►│  migrate schema  ──►  sync broker state
                                │  update market data
                                ▼
                   Execution engine (MultiStrategyRunner)
      stop-losses ─► wind-down ─► kill-switches ─► strategy signals
             ─► regime / correlation / risk funnel ─► DAY limit orders
                                │
        reconcile vs broker ──► auto-sync + retry ──► health gate
                                ▼
     run_health.json + run_history row   ·   email via notification outbox
                                ▼
        export snapshot ─► data branch ─► Next.js dashboard on Vercel
```

- **Trigger:** an external cron (`cron-job.org`) fires a `workflow_dispatch`
  pre-market; a native Actions cron backs it up.
- **Execution:** stop-losses run first (unconditional), then inactive-strategy
  wind-down, kill-switches, then enabled strategies generate signals that pass a
  regime → correlation → risk funnel before becoming `TimeInForce.DAY`
  marketable-limit orders. Idle cash is swept into SPY.
- **Reconciliation:** local DB vs Alpaca; drift triggers an auto-sync and a retry
  before the hard trading gate.
- **Observability:** `run_health.json` (per-run source of truth) + a
  `run_history` table (cross-run memory that escalates recurring failures);
  HTML email digests through a database-backed outbox; a public dashboard.

## Tech stack

| Layer | Choice |
|---|---|
| Language | Python 3.11 |
| State | SQLite, persisted as a CI artifact between runs |
| Broker | Alpaca (paper) |
| Orchestration | GitHub Actions (scheduled + externally dispatched) |
| Dashboard | Next.js on Vercel, fed from a committed `data` branch |
| Quality | pytest (~750 tests), black, ruff, mypy, bandit, detect-secrets, actionlint |
| Monitoring | healthchecks.io dead-man's-switch, structured run health |

## Strategies

Enablement is an evidence decision, not a preference. Each strategy is validated
out-of-sample; the ones that don't clear the bar are turned off and left in the
codebase with their evidence.

**Active (evidence-enabled):** Factor Momentum · RSI Mean Reversion · MA
Crossover · Dual Momentum · Earnings Drift · Sector Rotation · Volatility
Breakout

**Disabled by out-of-sample evidence:** ML Momentum (purged-OOS accuracy
near-random over 91 windows) · Pairs Trading (0/5 pairs pass cointegration) ·
News Sentiment (offline-unvalidatable look-ahead)

## Outcome & honest retrospective

The engineering succeeded; the **alpha did not** — and the platform was built to
surface that rather than hide it.

- Over the real-fill era, the active strategies were roughly break-even after
  costs. The portfolio's mild out-performance of SPY was explained by **lower
  effective beta** (idle cash plus a sub-100% SPY weight), not by demonstrated
  edge.
- That is the expected base rate: retail systematic alpha in liquid US equities
  with standard factors and daily bars is close to a coin flip after costs. The
  most valuable thing this platform produced was an **honest answer to its own
  question** — which is exactly what the evidence-governance layer existed to do.

What the project demonstrates: designing an autonomous system that stays correct
and observable while operating unattended, degrades safely, reconciles against an
external source of truth, and refuses to fool itself about whether it works.

## Repository tour

- `src/core/execution_engine.py` — the daily run: stop-losses, funnels, orders,
  reconciliation gate.
- `src/risk/` — broker reconciliation, drawdown/kill-switch management.
- `scripts/` — database setup/migrations, broker sync, diagnostics, analysis.
- `.github/workflows/daily_trading.yml` — the ~65-step production pipeline.
- `docs/research/` — the out-of-sample evidence and the decision runbook.
- `CLAUDE.md` — the operations manual / incident-triage guide.
- `web/` — the Next.js dashboard.

## Running it locally

```bash
make test        # fast unit suite
make diagnose    # reconstruct the latest run's state from CI artifacts
make help        # every available command
```

Live execution requires Alpaca paper credentials and is disabled by default.

## License

MIT
