# CLAUDE.md — operations guide for this repo

Paper-trading bot: 7 OOS-validated strategies (3 disabled by evidence — see
`docs/research/EVIDENCE_2026-06.md`), Alpaca paper API, one trading run per day.
This file is the triage manual. **If something is broken, start at
"First commands" below — do not start by reading code.**

## Architecture in 10 lines

1. **Trigger**: cron-job.org fires `workflow_dispatch` on `daily_trading.yml` at 05:45 UTC (≈00:45 ET, pre-market).
   GitHub's native cron is intentionally disabled (unreliable + caused duplicate runs).
2. `daily_trading.yml` (~65 steps): downloads the SQLite DB from the `trading-database` artifact → migrates schema
   (`scripts/setup_database.py`) → syncs broker state → updates market data → runs `scripts/run_trading.sh`.
3. `run_trading.sh` writes a status file (`STARTED → MARKET_CLOSED | PREFLIGHT_FAILED | EXECUTING → SUCCESS |
   EXECUTION_FAILED`), runs pre-flight checks, then `src/core/execution_engine.py` (`MultiStrategyRunner`).
4. The engine: stop-losses first (unconditional, direction-aware) → inactive-strategy wind-down → kill switches →
   enabled strategies (config `strategies.<name>.disabled`) generate signals → regime/correlation/risk funnel → OPG
   limit orders at next open → cash sweep parks idle cash in SPY. Strategy enable/capital decisions come from OOS
   evidence (`docs/research/EVIDENCE_RUNBOOK.md`, quarterly). Longs = positive shares; shorts = negative shares
   (pairs trading, currently disabled).
5. Reconciliation compares DB positions vs Alpaca; drift triggers auto-sync + retry.
6. `build_run_health.py` consolidates everything into `artifacts/run_health.json` + a `run_history` DB row; the final
   health gate passes only GREEN/YELLOW.
7. Dashboard: `export_snapshot.py` → `web/public/data/latest.json` → committed to the `data` branch → Vercel (Next.js
   app in `web/`).
8. Email: workflow-level dawidd6 actions for infra failures (work even when Python is broken); ALL Python alerts go
   through the `notification_outbox` table.
9. The DB is the state: positions, trades, signals, run_state, run_history, stop_loss_state, system_state — all
   persisted via the artifact between runs.
10. Dead-man's switch: healthchecks.io ping at end of run (`HEALTHCHECKS_URL` secret); cron-job.org failure
    notifications cover rejected dispatches.

## First commands for any incident

```bash
make diagnose                 # fetches latest run's DB + health artifacts, prints triage
gh run list --workflow daily_trading.yml --limit 10
gh run download <run-id> -n run-health
sqlite3 tmp/diagnose/trading.db "SELECT run_date, overall, status, failed_checks_json FROM run_history ORDER BY id DESC LIMIT 14;"
```

`artifacts/run_health.json` (artifact name `run-health`) is the single source
of truth per run: GREEN/YELLOW/RED + every check with severity and detail.
`run_history` is the cross-run memory — if the same check fails 3 consecutive
runs, email subjects get a `[RECURRING: <check>]` prefix.

## Runbook — known failure modes

### 1. Workflow file unparseable (caused the June 2026 outage)

- **Signature**: `gh run list` shows 0-second `failure` runs named after the *file path*
  (`.github/workflows/daily_trading.yml`) instead of "Daily Trading Execution". No scheduled/dispatched runs fire at all
  — and no failure email, because no run exists.
- **Diagnose**: `make diagnose` flags this explicitly. `actionlint .github/workflows/daily_trading.yml` shows the schema
  error; `git log -p .github/workflows/daily_trading.yml` finds the commit.
- **Known cause class**: step-level keys that are only valid at job/workflow level (e.g. `permissions:`). Guarded by
  `tests/unit/test_workflow_tripwires.py` and actionlint in CI.

### 2. No run fired, workflow file is fine

- **Signature**: healthchecks.io "check is down" email; no run in `gh run list` at 05:45 UTC.
- **Diagnose**: cron-job.org dashboard → execution history (it logs the HTTP response of the dispatch call; 422 = GitHub
  rejected it, 401 = PAT expired).

### 3. Kill switch fired / 0 trades

- **Signature**: log line `🛑 KILL SWITCH: ...`; `run_health.json` check `expect:Kill switch did not fire` failed.
- **Diagnose**: `sqlite3 trading.db "SELECT key, value FROM system_state WHERE key IN
  ('max_drawdown','peak_portfolio_value','cumulative_pnl');"`
- **History**: drawdown is computed live from `peak_portfolio_value` vs portfolio value as a FRACTION (0.05 = 5%). The
  stored `max_drawdown` system_state value is in PERCENT units and must never feed the kill switch directly (a unit
  mismatch halted trading for a week in June 2026 — "drawdown 186.7%").

### 4. Artifact DB migration failure

- **Signature**: run dies in the "Initialize database" step.
- **Diagnose**: download the `trading-database` artifact, run `python3 scripts/setup_database.py --db <downloaded.db>`
  locally.
- **Prevention**: every schema change must extend `tests/unit/test_db_migration_populated.py` (populated legacy fixture
  from real 2026-05 production schema). New constraints must handle pre-existing violating rows (see the
  trade_pnl_detail dedup-before-unique-index pattern in `database.py`).

### 5. Reconciliation drift

- **Signature**: `run_health.json` reconciliation check failed; "Manual sync needed" email.
- **Diagnose**: `sqlite3 trading.db "SELECT snapshot_type, reconciliation_status, discrepancies_json FROM broker_state
  ORDER BY created_at DESC LIMIT 6;"`
- **Fix**: `python3 scripts/sync_broker_state.py` (or the Sync Database workflow). Shorts are negative qty on BOTH
  sides; a local-short-vs-broker-long sign flip always fails loudly.

### 6. Stale data / Monday-after-holiday

- **Single knob**: workflow-level `DATA_MAX_AGE_HOURS` (80h). Holiday gaps pass via the last-completed-NYSE-session
  check in `src/validation/data_freshness.py` — widen the knob only if the calendar logic is wrong, never to paper over
  a missed fetch.

## Conventions (do not regress these)

- **run_status protocol**: `STARTED → MARKET_CLOSED | PREFLIGHT_FAILED | EXECUTING → SUCCESS | EXECUTION_FAILED`. The
  final health gate is an ALLOW-list: only `SUCCESS` and `MARKET_CLOSED` pass. `UNKNOWN` means run_trading.sh never ran
  and must fail.
- **continue-on-error policy**: allowed only for steps whose failure must not block the DB upload/email (downloads,
  reports, charts) — but every diagnostic/publishing step's `outcome` is checked in the final health gate, so nothing
  fails silently. New steps follow the same pattern: `id:` + outcome check in the gate.
- **Email policy**: workflow-level `dawidd6/action-send-mail` only for infra failures; all Python-originated mail via
  `db.enqueue_notification` (outbox). All email is HTML. Alert emails only for critical/high severity.
- **Shorts**: negative shares in `positions`; `direction` columns in `trade_pnl_detail` and `stop_loss_state`; short
  stops sit ABOVE entry and exit via BUY_TO_COVER; short P&L = (entry − exit) × shares. Pairs trading is the only short
  user; its pair map is rebuilt from positions each run (never trust in-memory state across runs).
- **Signals**: every emitted signal dict must include `asof_date` (AST-enforced by
  `tests/unit/test_signal_contract.py`).
- **Orders**: new entries use `TimeInForce.OPG` (signals are generated pre-open); only defensive exits (stop-loss SELL /
  BUY-to-cover) may use `DAY`.
- **Tests**: `make test` = fast suite; integration/functional are auto-marked `slow` — CI runs them with `-o
  addopts=""`. The DRY_RUN smoke test (`tests/functional/test_dry_run_smoke.py`) is the engine-level canary; it runs on
  every CI push and a weekly Sunday schedule.
- **Pre-commit stack**: black, ruff, mypy, bandit, yamllint, detect-secrets (use `# pragma: allowlist secret` for fake
  test creds). Hooks reformat files and ABORT the commit — re-add and commit again.
- **Never push during 05:30–06:30 UTC** (the daily run window).
- **Paper mode seams**: `ALPACA_PAPER=true` everywhere; OPG fills are marked FILLED optimistically in paper mode and
  trued-up by the pre-execution broker sync next run. Going live requires auditing every `self.paper_mode` branch.
