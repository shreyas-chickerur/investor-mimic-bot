---
description: Human-approved trading pipeline (Stages 0-5). Research → analyze → size → APPROVAL GATE → execute (dry_run default) → journal. Places nothing without your explicit, specific approval.
argument-hint: "[optional: extra tickers or focus notes]"
---

# /trade-cycle — Interactive, Human-Approved Trading Pipeline

Run the full pipeline **in this one interactive session**, in order. Each stage
hands off to the next **only via its file artifact** — those files are the contract.
Treat `$ARGUMENTS` as extra tickers/notes to merge into the Stage 1 watchlist.

## Absolute paths (resolve from any session/dir)

- PROMPTS_DIR: `/Users/shreyaschickerur/prompts`
- STATE_DIR:   `/Users/shreyaschickerur/pipeline-state`
- Stage 1 command file: `/Users/shreyaschickerur/.claude/commands/generate-market-report.md`
- Stage 2 prompt: `/Users/shreyaschickerur/prompts/analysis_prompt.md`
- Stage 3 prompt: `/Users/shreyaschickerur/prompts/sizing_prompt.md`
- Stage 4 prompt: `/Users/shreyaschickerur/prompts/execution_prompt.md`
- Stage 5 prompt: `/Users/shreyaschickerur/prompts/journal_prompt.md`

## Run setup (do this first)

1. Compute `RUN_ID = <YYYYMMDD_HHMMSS>` (current local time). Create
   `/Users/shreyaschickerur/pipeline-state/runs/<RUN_ID>/`.
2. Open a timestamped log at `runs/<RUN_ID>/run.log`. Log every stage start/finish,
   each HEALTH flag, the approved order set, and **every tool/auth error VERBATIM**.
3. Write each stage's artifact into BOTH `STATE_DIR/<artifact>.md` (the live handoff
   path the next stage reads) and a copy under `runs/<RUN_ID>/` for the record.
4. If any stage artifact is missing/empty/malformed when the next stage needs it →
   STOP, name the stage + defect, never fabricate a downstream input. Log it, then
   jump to the Final summary.

---

## Stage 0 — Load feedback

- If `/Users/shreyaschickerur/pipeline-state/calibration_summary.md` exists, read it
  and carry its adjustments forward to Stage 3.
- If it does NOT exist, proceed and explicitly tell Stage 3 there is **no track
  record yet → size at the floor** (unproven edge = minimal risk).

## Stage 1 — Context (research only)

Read and execute the instructions in
`/Users/shreyaschickerur/.claude/commands/generate-market-report.md`, merging
`$ARGUMENTS` into the watchlist. Write the resulting Context Report to
`/Users/shreyaschickerur/pipeline-state/context_report.md`. (Research only — places
nothing.)

## Stage 2 — Analysis (HEALTH gate)

Follow `/Users/shreyaschickerur/prompts/analysis_prompt.md` against
`/Users/shreyaschickerur/pipeline-state/context_report.md` → write
`/Users/shreyaschickerur/pipeline-state/analyzed_context.md`. Then read its HEALTH flag:

- `INSUFFICIENT` → **ABORT** the cycle. Place nothing. Tell me exactly what is
  blocking. Still run Stage 5 (LOG the abort), then print the Final summary.
- `DEGRADED` → continue; surface it in the summary; instruct Stage 3 to size down.
- `COMPLETE` → continue normally.

## Stage 3 — Sizing (suggestions only)

Follow `/Users/shreyaschickerur/prompts/sizing_prompt.md` against
`/Users/shreyaschickerur/pipeline-state/analyzed_context.md` plus any Stage 0
calibration → write `/Users/shreyaschickerur/pipeline-state/sizing_recommendations.md`.
Objective is **risk-adjusted return within the caps (5% max per position)**, never
raw profit. "Do nothing" is a valid output. With an empty/short track record, size
at the floor.

## ===== HARD STOP — BINDING APPROVAL (never skip, no flag bypasses this) =====

Present the exact orders as a **numbered table**: `# | side | ticker | shares |
order type | limit price | est cost | % equity`, plus the **run total**
(total deploy $, order count, resulting cash %, any name near the 5% cap).

Then ask me to reply with **exactly one** of:

- `APPROVE ALL`
- `APPROVE <subset>` (e.g. `APPROVE 1,3`)
- `EDIT <#> <change>`
- `ABORT`

A vague "yes / ok / sounds good" is **NOT** approval — re-prompt for the exact form.
Place ONLY what I explicitly approve, exactly as shown. Do **not** re-decide
side/size/price after approval. If I `ABORT`, place nothing and go to Stage 5 (LOG)
then the Final summary.

## Stage 4 — Execution (dry_run by default)

Follow `/Users/shreyaschickerur/prompts/execution_prompt.md` to place **ONLY the
approved orders** → write `/Users/shreyaschickerur/pipeline-state/execution_report.md`.

- **START IN `dry_run` MODE** — simulate, place nothing. Going `live` is a
  deliberate config change inside `execution_prompt.md`, made by me on purpose.
- Enforce as **hard per-order preconditions** (a failure skips THAT order, not the
  whole gate): market open; per-order 5% cap; `max_deploy_per_run` cap; idempotency
  (never double-submit an existing/recent equivalent order); kill switch.
- Default order type = `limit`.
- Capture every tool response (order id / status / error) verbatim into the log.

## Stage 5 — Journal (always runs, even on abort)

Follow `/Users/shreyaschickerur/prompts/journal_prompt.md` in **MODE=LOG** to append
this run — every suggestion, its predicted `p`/`b`, my decision, and any fills — to
`/Users/shreyaschickerur/pipeline-state/journal.jsonl`. Log even if the run aborted
early at Stage 2 or I chose ABORT. Log predicted `p`/`b` BEFORE outcomes are known.

---

## Final — print the TRADE-CYCLE SUMMARY (always, on success OR failure)

```
== TRADE-CYCLE SUMMARY ==
stages:   [0 OK | 1 OK | 2 DEGRADED | 3 OK | 4 PARTIAL | 5 OK]
health:   context COMPLETE/DEGRADED/INSUFFICIENT
mode:     dry_run | live
approved: [verbatim]   placed: [order ids + status]   skipped/errors: [...]
artifacts + log: [paths under /Users/shreyaschickerur/pipeline-state/ and runs/<RUN_ID>/]
verdict:  one plain sentence — what happened, and whether anything touched the account
```

## Invariants (do not build around these)

- The Stage 3 → 4 approval gate is mandatory. There is no auto-approve / `--yes` /
  skip-gate path. Nothing reaches execution without my explicit, specific approval.
- Stage 4 defaults to `dry_run`. Live is an intentional config change.
- Objective is risk-adjusted return within my caps — never raw profit maximization.
- Empty/short journal → Stage 3 sizes at the floor.
- On any MCP tool/auth failure: capture the error verbatim, mark dependent data
  unverifiable, carry it into the summary — never silently guess.
