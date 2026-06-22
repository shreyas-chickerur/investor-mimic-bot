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

const S = tokens.color;

export function StrategiesPage({ snapshot }: { snapshot: Snapshot }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <Label>Strategy Performance</Label>

      {/* Summary table */}
      <Panel pad={0} style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr style={{ color: S.muted, fontSize: 11, textTransform: "uppercase", letterSpacing: "0.06em" }}>
              {["Strategy", "Status", "Alloc", "Return", "Sharpe", "Sortino", "Win %", "Max DD", "P.Factor", "Trades", "Health"].map((h) => (
                <th key={h} style={{ textAlign: h === "Strategy" || h === "Status" ? "left" : "right", padding: "14px 16px", fontWeight: 600, whiteSpace: "nowrap" }}>
                  {h}
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
                  <td style={{ padding: "14px 16px", textAlign: "right" }}>
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
          <span style={{ fontSize: 10, letterSpacing: "0.05em" }}>— the step-by-step decision pipeline, entry to exit</span>
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
          return (
            <StrategyFlow
              key={s.key}
              strategy={s}
              accent={SERIES_COLORS[i % SERIES_COLORS.length]}
              steps={steps}
            />
          );
        })}
      </div>
    </div>
  );
}
