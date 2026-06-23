"use client";

import React from "react";
import type { Snapshot } from "@/lib/types";
import { tokens, plColor, healthChipColor, SERIES_COLORS } from "@/lib/tokens";
import { Panel } from "@/components/Panel";
import { Label } from "@/components/Label";
import { Chip } from "@/components/Chip";
import { fmtNum, fmtPct } from "@/lib/format";
import { StrategyShowcase } from "@/components/viz/StrategyShowcase";
import { StrategyFlow } from "@/components/viz/StrategyFlow";
import { STRATEGY_FLOWS } from "@/lib/strategyFlows";
import { Info } from "@/components/Info";

const S = tokens.color;

// Column header → glossary key (null = no tooltip). Hovering the ? explains it.
const HEADERS: { label: string; term: string | null }[] = [
  { label: "Strategy", term: null },
  { label: "Status", term: "status" },
  { label: "Alloc", term: "alloc" },
  { label: "Return", term: "return" },
  { label: "Sharpe", term: "sharpe" },
  { label: "Sortino", term: "sortino" },
  { label: "Win %", term: "winrate" },
  { label: "Max DD", term: "drawdown" },
  { label: "P.Factor", term: "pf" },
  { label: "Trades", term: "trades" },
  { label: "Health", term: "health" },
];

export function StrategiesPage({ snapshot }: { snapshot: Snapshot }) {
  const active = snapshot.strategies.filter((s) => s.status === "ACTIVE").length;
  const watching = snapshot.strategies.filter((s) => s.status === "WATCHING").length;
  const disabled = snapshot.strategies.filter((s) => s.status === "DISABLED").length;
  const traded = snapshot.strategies.filter((s) => s.tradesCount > 0).length;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <Label>Strategy Performance</Label>

      <PlatformExplainer active={active} watching={watching} disabled={disabled} traded={traded} />

      {/* Summary table */}
      <Panel pad={0} style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr style={{ color: S.muted, fontSize: 11, textTransform: "uppercase", letterSpacing: "0.06em" }}>
              {HEADERS.map(({ label, term }) => (
                <th key={label} style={{ textAlign: label === "Strategy" || label === "Status" ? "left" : "right", padding: "14px 16px", fontWeight: 600, whiteSpace: "nowrap" }}>
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 4, justifyContent: label === "Strategy" || label === "Status" ? "flex-start" : "flex-end" }}>
                    {label}
                    {term && <Info termKey={term} />}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {snapshot.strategies.map((s, i) => {
              const accent = SERIES_COLORS[i % SERIES_COLORS.length];
              return (
                <tr key={s.key} style={{ borderTop: `1px solid ${S.line}` }}>
                  <td style={{ padding: "14px 16px", fontWeight: 700, whiteSpace: "nowrap" }}>
                    <span style={{ width: 8, height: 8, borderRadius: "50%", background: accent, display: "inline-block", marginRight: 8, verticalAlign: "middle" }} />
                    {s.name}
                  </td>
                  <td style={{ padding: "14px 16px" }}>
                    <Chip color={s.status === "ACTIVE" ? S.green : s.status === "WATCHING" ? S.amber : S.muted}>{s.status}</Chip>
                  </td>
                  <td style={{ padding: "14px 16px", textAlign: "right", color: S.sec }}>{s.allocationPct}%</td>
                  <td style={{ padding: "14px 16px", textAlign: "right", color: s.returnPct != null ? plColor(s.returnPct) : S.muted, fontWeight: 600 }}>
                    {s.returnPct != null ? fmtPct(s.returnPct) : "—"}
                  </td>
                  <td style={{ padding: "14px 16px", textAlign: "right", color: s.sharpe != null ? (s.sharpe >= 1 ? S.green : s.sharpe >= 0.5 ? S.amber : S.red) : S.muted, fontWeight: 600 }}>
                    {fmtNum(s.sharpe)}
                  </td>
                  <td style={{ padding: "14px 16px", textAlign: "right", color: S.sec }}>{fmtNum(s.sortino)}</td>
                  <td style={{ padding: "14px 16px", textAlign: "right", color: S.text }}>
                    {s.winRatePct != null ? `${s.winRatePct.toFixed(0)}%` : "—"}
                  </td>
                  <td style={{ padding: "14px 16px", textAlign: "right", color: s.maxDrawdownPct != null && s.maxDrawdownPct > 15 ? S.amber : S.sec }}>
                    {s.maxDrawdownPct != null ? `${s.maxDrawdownPct.toFixed(1)}%` : "—"}
                  </td>
                  <td style={{ padding: "14px 16px", textAlign: "right", color: S.sec }}>
                    {s.profitFactor != null ? s.profitFactor.toFixed(2) : "—"}
                  </td>
                  <td style={{ padding: "14px 16px", textAlign: "right" }}>{s.tradesCount}</td>
                  <td
                    style={{ padding: "14px 16px", textAlign: "right", cursor: s.note ? "help" : "default" }}
                    title={s.note ? `Why ${s.healthScore}/100: ${s.note}` : `Health ${s.healthScore}/100`}
                  >
                    <div style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                      <div style={{ width: 40, height: 4, background: S.line, borderRadius: 99, overflow: "hidden" }}>
                        <div style={{ height: "100%", width: `${s.healthScore}%`, background: healthChipColor(s.healthScore), borderRadius: 99 }} />
                      </div>
                      <span style={{ fontSize: 11, color: healthChipColor(s.healthScore), fontWeight: 600 }}>{s.healthScore}</span>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </Panel>

      {/* Animated per-strategy showcase */}
      <div style={{ marginTop: 8 }}>
        <Label>
          Strategy Profiles{" "}
          <span style={{ fontSize: 10, letterSpacing: "0.05em" }}>— what each strategy bets on &amp; how it is doing</span>
        </Label>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(360px, 1fr))", gap: 16 }}>
        {snapshot.strategies.map((s, i) => (
          <StrategyShowcase
            key={s.key}
            strategy={s}
            accent={SERIES_COLORS[i % SERIES_COLORS.length]}
            index={i}
          />
        ))}
      </div>

      {/* How each strategy works — animated decision pipeline */}
      <div style={{ marginTop: 8 }}>
        <Label>
          How Each Strategy Works{" "}
          <span style={{ fontSize: 10, letterSpacing: "0.05em" }}>— press “Walk me through”, or click any step, to go deeper</span>
        </Label>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        {snapshot.strategies.map((s, i) => {
          const steps =
            STRATEGY_FLOWS[s.key] ??
            [
              { kind: "scan" as const, title: "Scan", detail: "Evaluate the universe each morning" },
              { kind: "signal" as const, title: "Signal", detail: s.edgeTechnical },
            ];
          // Inject the live state of THIS run into the diagram: today's
          // candidates (with their real computed reasons), current holdings,
          // and recent exits — matched by the strategy's display name.
          const candidates = snapshot.signals.explorer.filter((c) => c.strategy === s.name);
          const positions = snapshot.positions.filter((p) => p.strategy === s.name);
          const trades = snapshot.trades.filter((t) => t.strategy === s.name);
          return (
            <StrategyFlow
              key={s.key}
              strategy={s}
              accent={SERIES_COLORS[i % SERIES_COLORS.length]}
              steps={steps}
              candidates={candidates}
              positions={positions}
              trades={trades}
            />
          );
        })}
      </div>
    </div>
  );
}

// ── On-platform explainer: how the system works, answered inline ──────────────
function PlatformExplainer({
  active,
  watching,
  disabled,
  traded,
}: {
  active: number;
  watching: number;
  disabled: number;
  traded: number;
}) {
  const legendChip = (color: string, label: string) => (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
      <span style={{ width: 8, height: 8, borderRadius: 99, background: color, boxShadow: `0 0 6px ${color}` }} />
      <span style={{ color: S.sec }}>{label}</span>
    </span>
  );
  const block = (title: string, body: React.ReactNode) => (
    <div style={{ flex: "1 1 280px" }}>
      <div style={{ fontSize: 11, fontWeight: 700, color: S.text, marginBottom: 5, letterSpacing: "0.02em" }}>{title}</div>
      <div style={{ fontSize: 11.5, color: S.sec, lineHeight: 1.6 }}>{body}</div>
    </div>
  );

  return (
    <Panel pad={0} style={{ overflow: "hidden" }}>
      <details open>
        <summary
          style={{
            listStyle: "none",
            cursor: "pointer",
            padding: "13px 18px",
            display: "flex",
            alignItems: "center",
            gap: 8,
            fontWeight: 700,
            fontSize: 13.5,
            fontFamily: tokens.font.display,
            borderBottom: `1px solid ${S.line}`,
          }}
        >
          <span style={{ color: tokens.color.cyan }}>How this platform works</span>
          <span style={{ fontSize: 11, color: S.muted, fontWeight: 400 }}>
            — why so few are trading, and what “Health” means
          </span>
        </summary>
        <div style={{ padding: "16px 18px", display: "flex", flexWrap: "wrap", gap: 22 }}>
          {block(
            "The daily loop",
            <>
              Every morning all 11 strategies <strong style={{ color: S.text }}>scan the universe</strong> for setups.
              A strategy only trades when its own signal fires <em>and</em> the trade clears the shared funnel —
              market-regime gate → correlation filter → risk &amp; cash/heat caps → order at the next open.
            </>,
          )}
          {block(
            `Why only ${traded} are trading right now`,
            <>
              Of 11 strategies, <strong style={{ color: S.green }}>{active} are ACTIVE</strong>,{" "}
              <strong style={{ color: S.amber }}>{watching} WATCHING</strong>, and{" "}
              <strong style={{ color: S.muted }}>{disabled} DISABLED</strong>. WATCHING means enabled but{" "}
              <strong style={{ color: S.text }}>no setup met its rules recently</strong> — patience by design, not a fault.
              Disabled strategies were switched off by the quarterly evidence review for having no validated edge.
              <div style={{ marginTop: 8, display: "flex", flexWrap: "wrap", gap: 14, fontSize: 11 }}>
                {legendChip(S.green, "ACTIVE — will trade on signal")}
                {legendChip(S.amber, "WATCHING — scanning, no setup")}
                {legendChip(S.muted, "DISABLED — switched off")}
              </div>
            </>,
          )}
          {block(
            "What “Health” means",
            <>
              A 0–100 grade of whether a strategy is <strong style={{ color: S.text }}>behaving normally</strong> —
              enough recent trades, a sane win rate, no data problems. <strong style={{ color: S.text }}>Low ≠ losing money</strong>;
              it usually just means too few trades yet to judge it. Hover any strategy’s Health bar for its exact reason.
              <div style={{ marginTop: 8, display: "flex", flexWrap: "wrap", gap: 14, fontSize: 11 }}>
                {legendChip(S.green, "80–100 healthy")}
                {legendChip(S.amber, "60–79 watch")}
                {legendChip(S.red, "< 60 needs attention")}
              </div>
            </>,
          )}
        </div>
      </details>
    </Panel>
  );
}
