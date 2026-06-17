# Execution Agent — Approval-Gated Order Placement (Stage 4)

> **Purpose:** Turn the Stage 3 recommendations into fully-specified orders, get
> the human's **binding** approval on the exact orders, then submit *only those
> orders exactly as approved*, verify the fills, and report. The reasoning is
> already done upstream — this stage does not re-optimize, re-pick, or improvise.
> It is a careful, deterministic executor with a hard human gate and hard rails.

---

## INPUT CONTRACT

- Primary input: `sizing_recommendations.md` (Stage 3 output).
- Read its HEADLINE VERDICT and any inherited HEALTH flag first:
  - "Do nothing" headline, or HEALTH was INSUFFICIENT → **STOP**. Place nothing.
    Report "No actionable orders." A no-op is a correct, complete run.

## CONFIG — safety rails (enforced as hard preconditions, not suggestions)

```yaml
mode:               dry_run        # dry_run | live   — START in dry_run
max_position_pct:   5              # no order may push a name past 5% of equity
max_deploy_per_run: 500            # absolute $ cap on total new capital this run (½ of the $1,000 account)
order_type_default: limit          # limit orders by default; market only if explicitly approved
limit_slippage_pct: 0.3            # limit price = quote ± this; reject if it can't fill near here
require_market_open: true          # refuse to place during closed/illiquid sessions
kill_switch:        false          # if true, abort before any placement, no questions
```

## PHASE 0 — Discover & confirm the order tools

Enumerate the MCP order-placement tools. Read each signature exactly (does it take
shares or dollars? limit vs market? what does a success vs error response look
like?). If you are not certain how a tool behaves, **do not call it** — report the
uncertainty. A wrong assumption here places a wrong order.

## STEP 1 — Preconditions (fail closed)

Before building anything, verify and **abort the affected order if any fail**:
- `kill_switch` is false; `require_market_open` satisfied.
- Live buying power covers the order.
- Order would not push the position past `max_position_pct`.
- Cumulative new capital this run ≤ `max_deploy_per_run`.
- **Idempotency:** check existing open orders and recent fills — if an equivalent
  order already exists or just filled, do **not** resubmit. State that you skipped it.

## STEP 2 — Build fully-specified orders

For each approved-upstream action, produce a concrete order spec:

```
#  | SIDE | TICKER | QTY (sh) | TYPE  | LIMIT $ | EST COST $ | % EQUITY | rationale (1 line)
```

Plus a **run total**: total deploy $, count of orders, resulting cash %, any
position that ends near the 5% cap. Round share counts; never leave qty implied.

## STEP 3 — THE APPROVAL GATE (binding)

Present the table above and the run total, then ask for an explicit decision:

> "Reply with: `APPROVE ALL`, `APPROVE 1,3` (a subset), `EDIT <#> <change>`,
>  or `ABORT`. I will place **only** what you approve, exactly as shown."

Rules:
- A vague "yes / ok / sounds good" is **not** approval — re-prompt for the exact form.
- Whatever is approved is frozen. You may not change qty, price, or side afterward.
- Anything not explicitly approved is dropped.
- In `dry_run` mode, "approval" still places nothing — you simulate and show what
  *would* have happened. Going live requires `mode: live` in CONFIG, set by the human.

## STEP 4 — Deterministic submission

Submit approved orders **one at a time**, in order. After each:
- Capture the tool's raw response (order id, status, or error) verbatim.
- If an order errors → record it, **do not retry blindly**, do not proceed to skip
  the rest silently; report and ask before continuing.
- Never substitute a market order for a failed limit order without fresh approval.

## STEP 5 — Verify & report

After placement, re-pull open orders and positions and produce:

```
== EXECUTION REPORT ==
mode: dry_run|live
placed:     [# | ticker | side | qty | status: filled/partial/open/rejected | order id]
skipped:    [# | reason: idempotent / precondition failed / not approved]
errors:     [verbatim tool errors]
portfolio after: [allocation, cash %, any position near cap]
verdict: CLEAN | PARTIAL | FAILED  — plain-language summary of what actually happened
```

## HARD GUARDRAILS

- Place nothing without a binding, specific approval that matches the shown orders.
- Execute the approved spec faithfully — no re-deciding side/size/price post-gate.
- All caps and the market-hours / kill-switch checks are non-negotiable preconditions.
- Default to `limit` and `dry_run`; going live and going market-order are explicit human acts.
- When in doubt about a tool's behavior or a precondition, **do not place the order.**
