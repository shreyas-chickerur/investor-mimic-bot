# Build: Investor Mimic — production web dashboard (Next.js), replacing Streamlit

You are working in the `investor-mimic-bot` repository. Build a polished, public,
employer-facing web dashboard that replaces the existing Streamlit `dashboard/`.
It must show far more than Alpaca does — strategy differentiation, signal funnel,
risk analytics, per-position drill-downs, news sentiment — with a Simple/Advanced
toggle and an info-tooltip glossary on every term.

**Three reference files are provided alongside this prompt — treat them as binding:**

- `reference/snapshot.types.ts` — the EXACT data contract (export script ⇄ frontend).
- `reference/design-tokens.ts` — the EXACT visual system (colors, fonts, rules).
- `reference/glossary.ts` — the plain-English term definitions.
- `MimicDashboard.jsx` — the approved single-file VISUAL REFERENCE. The production
  app must look and behave like this (same aesthetic, same 7 pages, same toggle,
  same expandable Positions rows, same tooltips). Reproduce its fidelity; do not
  redesign. It is a demo with mock data — your job is to make it real, routed,
  typed, responsive, and fed by a live snapshot.

---

## HARD CONSTRAINTS (never violate)

1. **No secrets in the frontend, ever.** The public site must NEVER hold Alpaca keys,
   Alpha Vantage keys, or connect to the live broker. It reads ONLY a published,
   read-only JSON snapshot. This is the core architecture and a key interview point.
2. **No trade execution / no mutations from the UI.** Read-only. The only outbound
   action anywhere is a deep link to the manual-sync GitHub Action (already exists).
3. **No auth, no accounts, no real-time/websockets.** Data changes once per trading
   day; a daily snapshot + ISR is correct. Streaming a batch system is wrong.
4. **TypeScript everywhere, strict mode.** No `any` in committed code.
5. **Keep the existing trading system untouched.** Do not modify strategies, risk
   logic, reconciliation, or the email pipeline. You ADD an export step and a web app.
6. **Paper-trading framing stays.** PAPER badge, "no real capital," "not financial
   advice," and "news is context not causation" must appear.

---

## STACK (decided — do not deviate)

- **Next.js (App Router) + TypeScript + Tailwind CSS**, deployed on **Vercel**.
- **Recharts** for charts (area, line, bar, pie, radar). Custom SVG for sparklines
  and the monthly-returns heatmap / correlation matrix (as in the reference).
- **Tooltips/popovers: `@floating-ui/react`** (or Radix Popover) rendered in a
  **portal**. This is REQUIRED — the demo's hand-rolled tooltips hit repeated
  stacking-context bugs; a portaled, auto-flipping, viewport-clamped popover
  eliminates that entire class of problem. Every `?` info badge and any hover card
  uses it. Do NOT hand-position absolute/fixed tooltips.
- **Fonts via `next/font`** (self-hosted): Bricolage Grotesque (display),
  JetBrains Mono (numbers/data), Manrope (body). Do NOT runtime-@import.
- State: React state + URL search params for page/mode (deep-linkable). No Redux.

---

## PHASE 0 — Discover before building (change nothing yet; report back)

Read and summarize each, then map EVERY field in `snapshot.types.ts` to a real
source. Where a field has no source, STOP and ask me — do not invent data.

1. `dashboard/` (Streamlit) — what data it already pulls and how; reuse that logic.
2. `src/monitoring/` — `PnLCalculator`, `StrategyHealthScorer`, `SignalFunnelTracker`:
   exact methods and return shapes for portfolio P&L, per-strategy returns/health,
   and the funnel counts.
3. `src/regime/` — `RegimeDetector`, `DynamicAllocator`: how regime and Sharpe-weighted
   allocation are exposed.
4. `src/risk/broker_reconciler.py` — reconciliation status shape (for health markers).
5. `src/utils/news_sentiment.py` — per-symbol score range, headline/source availability,
   and how the boost/suppress/drop multiplier is represented.
6. `src/strategies/` — for each strategy: hold period, targets/stops, and the factor
   weights (to build the 0–100 `factorProfile` radar — derive from the documented
   weights, e.g. Factor Momentum = momentum 40 / quality 20 / reversion 20 / volume 20,
   scaled to 0–100; confirm with me how you map each).
7. SQLite schema: `positions`, `signals`, `trades`, `broker_state` columns — needed
   for positions, the closed-trade ledger, lots, and the signal explorer.
8. Where is SPY/benchmark data? The snapshot needs `spyTodayPct` and a `spy` series in
   `equityCurve`. If not currently fetched, plan to add a lightweight SPY fetch to the
   export step (it does NOT need live broker access — Alpha Vantage daily is fine).
9. `.github/workflows/daily_trading.yml` — confirm the artifact name (`trading-database`)
   and where to insert the export step. Confirm `sync_database.yml` exists (the manual
   fix workflow from earlier work); the health `syncWorkflowUrl` deep-links to it.

**Deliverable for Phase 0:** a short field-by-field mapping table + a list of any
fields you cannot source, with your proposed resolution, for my approval.

---

## PHASE 1 — Data snapshot pipeline (the safe public read-model)

Create `scripts/export_snapshot.py`:

- Loads `trading.db` and uses the EXISTING monitoring/risk classes (not re-derived math)
  to compute every field in `snapshot.types.ts`.
- Writes `web/public/data/latest.json` (validated against the schema) AND
  `web/public/data/history/<tradingDate>.json` for an equity history.
- Applies the **small-sample guard**: `winRatePct`/`profitFactor` = null when
  `closedTradesCount < 20`.
- Computes `factorProfile` per strategy from documented weights (per Phase 0 mapping).
- Fetches SPY daily % (Alpha Vantage) for the benchmark fields. Read-only; no Alpaca.
- Emits `null` (never omits) when a value can't be computed.
- Has a `--mock` flag that writes a deterministic mock snapshot (for `make web-mock`,
  local dev, and the three health states: healthy / auto-recovered / needs-action).

Add an export step to `.github/workflows/daily_trading.yml` AFTER the run, BEFORE/with
the email step. It must:

- run `python scripts/export_snapshot.py`,
- publish `latest.json` so Vercel serves fresh data WITHOUT exposing secrets. Use this
  pattern (simplest + clean interview story): commit `web/public/data/latest.json` (and
  the dated history file) to a dedicated **`data` branch** via a bot commit, and have the
  Next.js app read it with **ISR** (`revalidate: 3600`) from the raw URL of that branch.
  (Do NOT commit churny data to `main`.) If you prefer committing to `main` to trigger a
  Vercel redeploy, ask me first.
- pass the workflow outputs into the health markers (reuse the earlier wiring:
  `check_reconciliation.status`, `auto_sync.sync_ok`, `verify_sync.resolved`,
  `verify_sync.remaining`).

Write a tiny schema check (e.g. `scripts/validate_snapshot.py` or a TS `zod` parse in
the app) so a malformed snapshot fails loudly instead of rendering blank.

---

## PHASE 2 — App scaffold + design system

Create the app under `web/` (Next.js App Router). Structure:

```
web/
  app/
    layout.tsx           # fonts (next/font), globals, gradient-mesh bg, <Nav/>
    page.tsx             # Overview (route "/")
    strategies/page.tsx
    positions/page.tsx
    trades/page.tsx
    signals/page.tsx
    analytics/page.tsx
    system/page.tsx
  components/
    Nav.tsx ModeToggle.tsx Panel.tsx Stat.tsx Chip.tsx Info.tsx
    Sparkline.tsx RangePicker.tsx HealthMarkers.tsx ... (mirror the reference)
  lib/
    snapshot.ts          # fetch + zod-validate latest.json (ISR)
    tokens.ts            # from reference/design-tokens.ts
    glossary.ts          # from reference/glossary.ts
    format.ts            # fmt(), plColor(), sentimentColor(), healthChip()
    types.ts             # from reference/snapshot.types.ts
  public/data/...        # snapshots (gitignored on main; on data branch)
```

- Port the exact tokens, fonts, gradient mesh, panel/glow styling, mono numerals.
- Each page is a routed component reading the typed snapshot from `lib/snapshot.ts`.
- Real deep-linkable routes; active nav tab styled per the reference (lime glow).

---

## PHASE 3 — Tooltips & glossary (do this right, once)

- Build `<Info termKey="sharpe" />`: a `?` badge that, on hover/focus/tap, opens a
  Floating-UI popover (portal, `flip`, `shift`, `offset`, `arrow`), keyboard-accessible
  (focusable, Esc to close, `aria-describedby`). Content from `lib/glossary.ts`.
- Because it's portaled, it can never be clipped or trapped behind a card — this is the
  fix for all the demo's tooltip bugs. Verify near every edge and on mobile.
- The System page renders the full glossary as a static reference section too.

---

## PHASE 4 — The seven pages (match MimicDashboard.jsx; specifics below)

**Overview** — hero portfolio value + equity area chart with SPY overlay and a
RangePicker (1W/1M/3M/YTD/ALL that slices `equityCurve`); a performance panel that
swaps Simple ("+$ total profit", today, cash, holdings, beating-index?) ↔ Advanced
(Sharpe/Sortino/maxDD/volatility/winRate/profitFactor); regime + exposure line;
allocation donut + per-strategy return list; today's activity.

**Strategies** — 4 selectable strategy cards (health chip, return, allocation bar,
trade count); a detail panel (plain edge in Simple, technical edge + Sharpe/Sortino/PF/
maxDD in Advanced); a **factor-profile radar**; a comparison bar (return in Simple,
Sharpe in Advanced, with the "why Sharpe" explanation).

**Positions** — the table with the **expandable drill-down rows** (this is required and
already designed in the reference): click a row → inline drawer with price sparkline,
"why the bot holds this," the buy lots ("how you got here"), and the news headlines
driving sentiment (color-coded borders, "context not cause" caveat). Advanced adds the
conf/multiplier/ATR/beta line and the cost-basis/beta/ATR columns. Allow multiple open.

**Trades** — closed-trade ledger: summary tiles (count, win rate, avg return, best/PF) +
a table (date, symbol, strategy, entry→exit [Advanced], realized P&L, exit reason).

**Signals** — the funnel (scanned → executed, each stage with its filter reason in
Advanced) + the signal explorer (per-candidate EXECUTED/FILTERED/DEFERRED with the why;
Advanced shows confidence / sentiment / multiplier).

**Analytics** — underwater drawdown area; Simple shows best/worst month, Advanced adds
rolling Sharpe; monthly-returns heatmap; backtest-vs-live bars; and in Advanced a return
-distribution histogram + strategy correlation matrix.

**System** — the 7-stage pipeline diagram (data ingest → signals → news → risk filters →
allocation → reconcile+execute → snapshot+notify), stack + safety-layer summary, the
"why a snapshot" explanation, and the full glossary. This page carries the engineering
story for employers — make it strong. Also render the **health markers** (x/y, three
states green/amber/red with the conditional "needs attention" + sync deep link) here,
wired to `snapshot.health`.

---

## PHASE 5 — Simple/Advanced toggle

- Global, in the nav, persisted to the URL (`?mode=advanced`) so links are shareable.
- Simple = plain language, hides quant stats, shows the "ⓘ hover the ? for explanations"
  banner. Advanced = full quant view. Match the reference's per-page behavior exactly.

---

## PHASE 6 — Responsive, accessible, fast, SEO

- **Mobile**: grids collapse to one column, nav + wide tables scroll, nothing clips.
  Test at 375px and 768px. Recruiters open on phones.
- **A11y**: semantic landmarks, focusable tooltips/toggle, visible focus rings, color
  contrast AA, `prefers-reduced-motion` disables entrance animations, charts have
  text/aria fallbacks or summaries.
- **Loading/empty/error states**: skeletons while the snapshot loads; a clear empty state
  if a section has no data (e.g. "No notable gainers today" — never the literal "None");
  a graceful error if the snapshot is missing/invalid.
- **Freshness**: a "Snapshot updated <relative time>" stamp (from `meta.generatedAt`).
- **Perf**: lighthouse ≥ 90 desktop. ISR; no client-side secret fetches. Lazy-load heavy
  charts below the fold.
- **SEO/meta**: title, description, OG image; it's a public portfolio piece.

---

## PHASE 7 — Deploy

- Vercel project from `web/`. Document env (none secret — the app only needs the public
  data URL). README section: architecture diagram + "how the snapshot stays safe."
- Decommission Streamlit or clearly mark it dev-only (ask me before deleting `dashboard/`).

---

## PHASE 8 — Prove it (don't claim done without this)

1. `make web-mock` (or documented command) generates `latest.json --mock` and runs the
   app locally so I can click all 7 pages with no API/secret access.
2. Provide mock snapshots for ALL THREE health states and screenshots of each.
3. Tooltips: verify a `?` near every screen edge and on a 375px viewport — none clip or
   render behind a card.
4. Positions: verify rows expand/collapse, multiple at once, in both modes.
5. Toggle: verify every page changes correctly and the URL reflects mode.
6. `tsc --noEmit` clean (strict), lint/format clean, lighthouse ≥ 90.
7. Show a diff summary of every file added/changed before finishing.

---

## What NOT to do (scope discipline)

- No live broker connection, no secrets client-side, no trade controls, no auth,
  no websockets/real-time, no UI-configurable strategy params.
- Don't redesign the look — match `MimicDashboard.jsx`.
- Don't hand-position tooltips — use the portal popover.
- Don't surface win rate / profit factor on < 20 closed trades.
- Don't conflate performance stats with system-health markers (health = is the machine
  working: broker/data/quality/breaker/correlation/regime — nothing else).

## Ask-me checkpoints

After Phase 0 (field mapping + gaps), and before: deleting `dashboard/`, committing data
to `main` instead of a `data` branch, or any factor-profile mapping you're unsure of.
