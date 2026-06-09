"use client";

import React from "react";
import type { Snapshot } from "@/lib/types";
import { tokens, sentimentColor, SERIES_COLORS } from "@/lib/tokens";
import { Panel } from "@/components/Panel";
import { Label } from "@/components/Label";
import { Chip } from "@/components/Chip";
import { fmtNum } from "@/lib/format";

const S = tokens.color;

export function SignalsPage({ snapshot }: { snapshot: Snapshot }) {
  const { funnel, explorer } = snapshot.signals;
  const executed = explorer.filter((s) => s.status === "EXECUTED");
  const filtered = explorer.filter((s) => s.status === "FILTERED");
  const deferred = explorer.filter((s) => s.status === "DEFERRED");
  const maxCount = funnel[0]?.count ?? 1;

  const statusColor = (status: string) =>
    status === "EXECUTED" ? S.green : status === "DEFERRED" ? S.amber : S.muted;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div style={{ display: "grid", gridTemplateColumns: "340px 1fr", gap: 14, alignItems: "start" }}>
        {/* Funnel */}
        <Panel pad={20}>
          <div style={{ marginBottom: 16 }}><Label termKey="funnel">Signal Funnel</Label></div>
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {funnel.map((stage, i) => {
              const pct = maxCount > 0 ? (stage.count / maxCount) * 100 : 0;
              return (
                <div key={stage.stage}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                    <span style={{ fontSize: 12, color: S.sec }}>{stage.stage}</span>
                    <span style={{ fontSize: 12, fontWeight: 700 }}>{stage.count}</span>
                  </div>
                  <div style={{ height: 6, background: S.line, borderRadius: 99, overflow: "hidden" }}>
                    <div style={{ height: "100%", width: `${pct}%`, background: SERIES_COLORS[i % SERIES_COLORS.length], borderRadius: 99, transition: "width .5s" }} />
                  </div>
                  {stage.note && <div style={{ fontSize: 11, color: S.muted, marginTop: 2 }}>{stage.note}</div>}
                </div>
              );
            })}
          </div>
        </Panel>

        {/* Split counts */}
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {[
            { label: "Executed", count: executed.length, color: S.green },
            { label: "Filtered", count: filtered.length, color: S.muted },
            { label: "Deferred", count: deferred.length, color: S.amber },
          ].map(({ label, count, color }) => (
            <Panel key={label} pad={16}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: 13, color: S.sec }}>{label}</span>
                <span style={{ fontSize: 22, fontWeight: 800, color }}>{count}</span>
              </div>
            </Panel>
          ))}
        </div>
      </div>

      {explorer.length > 0 ? (
        <Panel pad={0} style={{ overflowX: "auto" }}>
          <div style={{ padding: "16px 20px 12px", borderBottom: `1px solid ${S.line}` }}>
            <Label>Signal Explorer</Label>
          </div>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ color: S.muted, fontSize: 11, textTransform: "uppercase", letterSpacing: "0.06em" }}>
                {["Symbol", "Strategy", "Status", "Confidence", "Sentiment", "Multiplier", "Reason"].map((h) => (
                  <th key={h} style={{ textAlign: ["Confidence", "Sentiment"].includes(h) ? "right" : "left", padding: "12px 16px", fontWeight: 600, whiteSpace: "nowrap" }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {explorer.map((sig, i) => (
                <tr key={i} style={{ borderTop: `1px solid ${S.line}` }}>
                  <td style={{ padding: "11px 16px", fontWeight: 700 }}>{sig.symbol}</td>
                  <td style={{ padding: "11px 16px", color: S.sec, fontSize: 12 }}>{sig.strategy}</td>
                  <td style={{ padding: "11px 16px" }}>
                    <Chip color={statusColor(sig.status)}>{sig.status}</Chip>
                  </td>
                  <td style={{ padding: "11px 16px", textAlign: "right", color: sig.confidence != null ? (sig.confidence >= 0.7 ? S.green : S.amber) : S.muted, fontWeight: 600 }}>
                    {sig.confidence != null ? `${(sig.confidence * 100).toFixed(0)}%` : "—"}
                  </td>
                  <td style={{ padding: "11px 16px", textAlign: "right", color: sentimentColor(sig.sentimentScore) }}>
                    {fmtNum(sig.sentimentScore)}
                  </td>
                  <td style={{ padding: "11px 16px", color: S.cyan, fontSize: 12 }}>{sig.multiplier}</td>
                  <td style={{ padding: "11px 16px", color: S.muted, fontSize: 12 }}>{sig.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      ) : (
        <Panel pad={40} style={{ textAlign: "center" }}>
          <div style={{ fontSize: 14, color: S.muted }}>No signals generated this run</div>
        </Panel>
      )}
    </div>
  );
}
