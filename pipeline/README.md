# Trading pipeline — vetted prompts & commands (baseline)

Money-touching source for the human-approved `/trade-cycle` + `/trade-review` pipeline.

**Install location (runtime):** the two command files live at `~/.claude/commands/`
(`trade-cycle.md`, `trade-review.md`); stage prompts live at `~/prompts/`. This
`pipeline/` folder is the version-controlled copy of record, not the run path.

- `commands/` — trade-cycle.md, trade-review.md  (Stage 1 = global generate-market-report.md, not copied here)
- `prompts/`  — analysis, sizing, execution, journal stage prompts + phase2 guardrail tests
- State/artifacts live outside git at `~/pipeline-state/`.

Guardrails as committed: Stage 4 defaults to `dry_run`; the Stage 3→4 approval gate is
mandatory; max_deploy_per_run=500; 5% per-name cap. These are LLM-followed instructions,
not hard asserts — see prompts/phase2_guardrail_tests.md "Honest limit".
