# Trade Journal & Attribution Agent (Stage 5)

> **Purpose:** Give the pipeline a memory and an honest scorecard. Without this,
> the system reasons fresh every run and never learns whether its calls actually
> made money. Two modes: **LOG** (append every cycle) and **REVIEW** (settle
> outcomes, measure edge, and feed calibration back into sizing).
>
> The whole point is to answer one question honestly: *does this system have an
> edge over just buying an index — after costs — or not?* It must be willing to
> answer "no."

---

## STORE

- `journal.jsonl` — append-only machine record, one object per suggestion per run.
- `journal_summary.md` — human-readable track record.
- `calibration_summary.md` — machine-readable adjustments Stage 3 reads next run.

---

## MODE A — LOG  (runs at the end of every `/trade-cycle`)

Append a record for **every** suggestion this run — including the ones skipped or
rejected (omitting those hides bad judgment behind survivorship bias). Per record:

```json
{
  "run_id": "...", "ts": "...", "context_health": "COMPLETE|DEGRADED",
  "ticker": "...", "side": "...", "strategy_tag": "momentum|mean_revert|earnings|...",
  "predicted": { "p": 0.0, "b": 0.0, "expected_value": 0.0 },  // log BEFORE the outcome is known
  "suggested_size": 0, "pct_equity": 0.0,
  "decision": "approved|edited|rejected|skipped", "decision_reason": "...",
  "fill": { "status": "...", "price": 0.0, "qty": 0, "order_id": "...", "dry_run": true },
  "entry_ref_price": 0.0,        // price at suggestion time, for later attribution
  "outcome": null                // filled in later by REVIEW; never backfill predicted{}
}
```

Hard rule: **log the predicted `p`/`b` before you know how it turned out.** Never
edit a prediction after the fact to look smart — that destroys the only thing this
stage is for.

## MODE B — REVIEW / SETTLE  (separate command, run periodically)

For entries older than `eval_horizon` (e.g. 5–20 trading days) with `outcome: null`:

1. Pull the current/closing price; compute realized return for each suggestion —
   **including rejected/skipped ones** (the counterfactual: did the trades you
   *didn't* take outperform the ones you did?).
2. **Benchmark:** same-window SPY return. `edge = your_return − SPY_return`.
   Beating your own picks isn't the bar; beating the index after costs is.
3. **Hit rate** by `strategy_tag`.
4. **Calibration:** bucket suggestions by predicted `p`, compare predicted vs.
   realized hit rate. Flag overconfidence (e.g. "70%-confidence calls hit 48%").
5. **Cost drag:** estimate spread + fees + turnover; subtract it from edge.

Write `journal_summary.md`:

```
== TRACK RECORD (n = ...) ==
hit rate overall / by strategy | avg edge vs SPY (after costs) | total realized P&L
calibration table: predicted p  →  realized hit rate  (overconfidence flagged)
best / worst strategy tags | counterfactual: skipped picks vs taken picks
== VERDICT ==
plain sentence. If no edge vs SPY after costs: say so. The honest conclusion may be
"this is not beating an index fund — reduce size or stop."
```

Write `calibration_summary.md` (machine-readable): per `strategy_tag`, a confidence
discount the sizer applies next run (e.g. `momentum: shrink p by 0.15`).

## FEEDBACK LOOP (wire into Stage 3)

Stage 3 reads `calibration_summary.md` and shrinks Kelly inputs for strategies that
haven't earned their confidence. **No track record yet → treat every edge as
unproven and size at the floor (or paper only).** Confidence is earned by realized
results, not asserted upstream.

## HONESTY GUARDRAILS

- Predicted edge is logged before outcomes; never backfilled.
- Skipped and rejected suggestions are tracked too.
- Small samples lie — mark every stat low-confidence until `n` is meaningful, and
  resist drawing conclusions from a handful of trades.
- If the data says there's no edge, the report says there's no edge.
