# Investor Mimic — production build package

Hand this whole folder to Claude Code from inside the repo.

## What to feed it

1. **CLAUDE_CODE_PROD_PROMPT.md** — the build instructions (start here).
2. **reference/snapshot.types.ts** — the data contract (export script ⇄ frontend). Binding.
3. **reference/design-tokens.ts** — exact colors/fonts/visual rules. Binding.
4. **reference/glossary.ts** — plain-English term definitions for the tooltips.
5. **reference/MimicDashboard.reference.jsx** — the approved VISUAL reference (the demo).
   The production app must match its look, its 7 pages, the Simple/Advanced toggle,
   the expandable Positions rows, and the tooltip behavior.

## How to start the session

Open the repo in Claude Code and paste:

> Read CLAUDE_CODE_PROD_PROMPT.md and the three reference files plus
> MimicDashboard.reference.jsx. Do PHASE 0 first: read the listed source files,
> produce the field-by-field mapping from snapshot.types.ts to real code, list any
> fields you can't source, and STOP for my approval before writing code.

## The one-line pitch (for interviews)

A public, employer-facing dashboard that surfaces a quant trading system's *reasoning* —
strategy differentiation, the signal funnel, per-position drill-downs, risk analytics —
fed by a daily JSON snapshot exported from the trading DB, so real data is shown with
zero exposure of broker keys or live account access. Built in Next.js/TS, deployed on
Vercel, with a Simple/Advanced toggle so it serves both a beginner and a quant.

## Non-negotiables (also in the prompt)

- No secrets in the frontend; reads a read-only snapshot only.
- No trade controls / no auth / no real-time.
- TypeScript strict. Match the visual reference. Portal-based tooltips.
- Don't touch the trading system itself — only add the export step + the web app.
