"use client";

import React from "react";
import {
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  ResponsiveContainer,
} from "recharts";
import type { Snapshot } from "@/lib/types";
import { tokens, plColor, healthChipColor, SERIES_COLORS } from "@/lib/tokens";
import { Panel } from "@/components/Panel";
import { Label } from "@/components/Label";
import { Chip } from "@/components/Chip";
import { fmtNum, fmtPct } from "@/lib/format";

const S = tokens.color;

function FactorRadar({ factors, color }: { factors: Snapshot["strategies"][0]["factorProfile"]; color: string }) {
  const data = [
    { axis: "Momentum", value: factors.momentum },
    { axis: "Quality", value: factors.quality },
    { axis: "Reversion", value: factors.reversion },
    { axis: "Volume", value: factors.volume },
    { axis: "Volatility", value: factors.volatility },
  ];
  return (
    <ResponsiveContainer width="100%" height={130}>
      <RadarChart data={data} cx="50%" cy="50%">
        <PolarGrid stroke={S.line} />
        <PolarAngleAxis dataKey="axis" tick={{ fill: S.muted, fontSize: 10 }} />
        <Radar dataKey="value" stroke={color} fill={color} fillOpacity={0.18} strokeWidth={1.5} />
      </RadarChart>
    </ResponsiveContainer>
  );
}

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

      {/* Factor radar cards */}
      <div style={{ marginTop: 8 }}><Label>Factor Profiles <span style={{ fontSize: 10, letterSpacing: "0.05em" }}>— what each strategy bets on</span></Label></div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: 14 }}>
        {snapshot.strategies.map((s, i) => {
          const accent = SERIES_COLORS[i % SERIES_COLORS.length];
          return (
            <Panel key={s.key} glow={accent} pad={18}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 4 }}>
                <div>
                  <div style={{ fontWeight: 700, fontSize: 14 }}>{s.name}</div>
                  <div style={{ fontSize: 11.5, color: S.sec, marginTop: 3, lineHeight: 1.5 }}>{s.edgeTechnical}</div>
                </div>
                {s.backtestSharpe != null && (
                  <div style={{ textAlign: "right", flexShrink: 0, marginLeft: 12 }}>
                    <div style={{ fontSize: 10, color: S.muted }}>Backtest SR</div>
                    <div style={{ fontSize: 14, fontWeight: 700, color: S.cyan }}>{fmtNum(s.backtestSharpe)}</div>
                  </div>
                )}
              </div>
              <FactorRadar factors={s.factorProfile} color={accent} />
              {s.note && (
                <div style={{ fontSize: 11, color: S.muted, marginTop: 4, padding: "6px 10px", background: S.glass2, borderRadius: 8, border: `1px solid ${S.line}` }}>
                  {s.note}
                </div>
              )}
            </Panel>
          );
        })}
      </div>
    </div>
  );
}
