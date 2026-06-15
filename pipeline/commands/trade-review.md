---
description: Periodic settlement of the trade journal. Settles matured entries, computes realized P&L and edge vs SPY after costs, and writes the calibration that Stage 3 reads next cycle. Reads/writes only; places no trades.
argument-hint: "[optional: eval horizon override, e.g. 10d]"
---

# /trade-review — Periodic Journal Settlement (MODE=REVIEW)

Run this periodically (e.g. weekly) to close the learning loop. It settles past
suggestions, measures whether they actually beat an index after costs, and emits the
calibration the sizer consumes next cycle. **This command reads and writes files and
pulls quotes only — it never places, modifies, or cancels an order.**

## Absolute paths

- PROMPTS_DIR: `/Users/shreyaschickerur/prompts`
- STATE_DIR:   `/Users/shreyaschickerur/pipeline-state`
- Journal prompt: `/Users/shreyaschickerur/prompts/journal_prompt.md`
- Journal store:  `/Users/shreyaschickerur/pipeline-state/journal.jsonl`

## What to do

1. If `/Users/shreyaschickerur/pipeline-state/journal.jsonl` is missing or empty →
   STOP and report "No journal entries to review yet." Do not fabricate a record.
2. Follow `/Users/shreyaschickerur/prompts/journal_prompt.md` in **MODE=REVIEW**.
   If `$ARGUMENTS` supplies an eval-horizon override (e.g. `10d`), use it; otherwise
   use the prompt's default horizon.
3. For journal entries older than the eval horizon with `outcome: null`: pull the
   current/closing price, compute realized return (including rejected/skipped picks
   as counterfactuals), benchmark `edge = your_return − SPY_return`, compute hit rate
   by strategy_tag, calibrate predicted vs realized hit rate, and subtract cost drag.
4. Write outputs:
   - `/Users/shreyaschickerur/pipeline-state/journal_summary.md` — human track record.
   - `/Users/shreyaschickerur/pipeline-state/calibration_summary.md` — machine
     adjustments Stage 3 reads next `/trade-cycle` (per-strategy confidence discounts).
5. Capture any MCP tool/auth error VERBATIM; mark affected settlements unverifiable
   rather than guessing a price.

## Honesty requirement

If the data shows **no edge vs SPY after costs**, the report must say so plainly —
"this is not beating an index fund — reduce size or stop." Small samples lie: mark
every stat low-confidence until `n` is meaningful. Never backfill a prediction to
look smart.
