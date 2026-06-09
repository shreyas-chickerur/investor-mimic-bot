"use client";

import React, { useState } from "react";
import type { Snapshot } from "@/lib/types";
import { tokens, plColor, sentimentColor, SERIES_COLORS } from "@/lib/tokens";
import { Panel } from "@/components/Panel";
import { Label } from "@/components/Label";
import { Chip } from "@/components/Chip";
import { Sparkline } from "@/components/Sparkline";
import { fmt, fmtPct, fmtDate } from "@/lib/format";

const S = tokens.color;

export function PositionsPage({ snapshot }: { snapshot: Snapshot }) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const { positions } = snapshot;

  if (!positions.length) {
    return <Panel pad={40} style={{ textAlign: "center" }}><div style={{ fontSize: 14, color: S.muted }}>No open positions</div></Panel>;
  }

  const totalExposure = positions.reduce((s, p) => s + p.value, 0);
  const totalPl = positions.reduce((s, p) => s + (p.unrealizedPlUsd ?? 0), 0);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {/* Summary */}
      <div style={{ display: "flex", gap: 24, flexWrap: "wrap" }}>
        {[
          { l: "Open Positions", v: String(positions.length), c: S.text },
          { l: "Total Exposure", v: fmt(totalExposure), c: S.text },
          { l: "Unrealized P&L", v: fmt(totalPl), c: plColor(totalPl) },
        ].map(({ l, v, c }) => (
          <div key={l}>
            <div style={{ fontSize: 11, color: S.muted, textTransform: "uppercase", letterSpacing: "0.06em" }}>{l}</div>
            <div style={{ fontSize: 24, fontWeight: 800, color: c }}>{v}</div>
          </div>
        ))}
      </div>

      {positions.map((pos, i) => {
        const pl = pos.unrealizedPlUsd ?? 0;
        const isOpen = expanded === pos.symbol;
        const accent = SERIES_COLORS[i % SERIES_COLORS.length];

        return (
          <Panel key={pos.symbol} glow={isOpen ? accent : undefined} pad={20}>
            <div
              style={{ cursor: "pointer", userSelect: "none" }}
              onClick={() => setExpanded(isOpen ? null : pos.symbol)}
              role="button"
              aria-expanded={isOpen}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12 }}>
                <div style={{ display: "flex", gap: 12, alignItems: "center", minWidth: 0 }}>
                  <div>
                    <div style={{ fontSize: 20, fontWeight: 800, letterSpacing: -0.5 }}>{pos.symbol}</div>
                    <div style={{ fontSize: 11.5, color: S.muted, marginTop: 1 }}>{pos.strategy}</div>
                  </div>
                  <Chip color={sentimentColor(pos.sentimentScore)}>{pos.sentimentLabel}</Chip>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 20, flexShrink: 0 }}>
                  <div style={{ textAlign: "right" }}>
                    <div style={{ fontSize: 18, fontWeight: 700, color: plColor(pl) }}>
                      {pl >= 0 ? "+" : ""}{fmt(pl)}
                    </div>
                    <div style={{ fontSize: 12, color: plColor(pl), opacity: 0.8 }}>
                      {pos.unrealizedPlPct != null ? fmtPct(pos.unrealizedPlPct) : "—"}
                    </div>
                  </div>
                  <span style={{ color: S.muted, fontSize: 14, display: "inline-block", transform: isOpen ? "rotate(180deg)" : "none", transition: "transform .2s" }}>▼</span>
                </div>
              </div>

              <div style={{ display: "flex", gap: 24, marginTop: 14, flexWrap: "wrap" }}>
                {[
                  { l: "Shares", v: String(pos.shares) },
                  { l: "Value", v: fmt(pos.value) },
                  { l: "Cost Basis", v: fmt(pos.costBasis) },
                  ...(pos.atrStop != null ? [{ l: "Stop", v: fmt(pos.atrStop), c: S.amber }] : []),
                ].map(({ l, v, c }) => (
                  <div key={l}>
                    <div style={{ fontSize: 10, color: S.muted, textTransform: "uppercase" }}>{l}</div>
                    <div style={{ fontSize: 13, color: (c as string | undefined) ?? S.sec }}>{v}</div>
                  </div>
                ))}
                {pos.detail.priceSpark.length >= 2 && (
                  <div>
                    <div style={{ fontSize: 10, color: S.muted, textTransform: "uppercase", marginBottom: 2 }}>5d price</div>
                    <Sparkline data={pos.detail.priceSpark} color={plColor(pl)} width={80} height={28} />
                  </div>
                )}
              </div>
            </div>

            {/* Expanded detail */}
            {isOpen && (
              <div style={{ marginTop: 16, paddingTop: 16, borderTop: `1px solid ${S.line}` }}>
                {pos.detail.lots.length > 0 && (
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 10, marginBottom: 12 }}>
                    {pos.detail.lots.map((lot, li) => (
                      <div key={li} style={{ fontSize: 12, color: S.sec, background: S.glass2, padding: "5px 10px", borderRadius: 7, border: `1px solid ${S.line}` }}>
                        {lot.shares} sh @ {fmt(lot.price)} · {fmtDate(lot.date)}
                      </div>
                    ))}
                  </div>
                )}
                {pos.detail.whyHeld && (
                  <div style={{ fontSize: 12.5, color: S.sec, marginBottom: 12, padding: "8px 12px", background: S.glass2, borderRadius: 8, border: `1px solid ${S.line}`, lineHeight: 1.55 }}>
                    {pos.detail.whyHeld}
                  </div>
                )}
                {pos.detail.news.length > 0 && (
                  <div>
                    <div style={{ fontSize: 11, color: S.muted, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 6 }}>Recent News</div>
                    {pos.detail.news.map((n, ni) => (
                      <div key={ni} style={{ padding: "8px 0", borderTop: `1px solid ${S.line}` }}>
                        <div style={{ fontSize: 12.5, lineHeight: 1.45, marginBottom: 3 }}>{n.headline}</div>
                        <div style={{ display: "flex", gap: 8, fontSize: 11 }}>
                          <span style={{ color: S.muted }}>{n.source}</span>
                          <span style={{ color: sentimentColor(n.score), fontWeight: 600 }}>
                            {n.score >= 0.62 ? "▲ Positive" : n.score <= 0.38 ? "▼ Negative" : "— Neutral"}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </Panel>
        );
      })}
    </div>
  );
}
