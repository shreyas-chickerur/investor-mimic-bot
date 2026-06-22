"use client";

import React from "react";
import type { Snapshot } from "@/lib/types";
import { tokens, healthChipColor } from "@/lib/tokens";
import { Panel } from "@/components/Panel";
import { Chip } from "@/components/Chip";
import { AnimatedRadar } from "./AnimatedRadar";
import { Gauge } from "./Gauge";
import { useInView, useProgress } from "./useReveal";

const S = tokens.color;
type Strategy = Snapshot["strategies"][number];

function statusColor(status: Strategy["status"]): string {
  return status === "ACTIVE" ? S.green : status === "WATCHING" ? S.amber : S.muted;
}

/** A single labelled metric with an animated fill bar. */
function StatBar({
  label,
  display,
  frac,
  color,
  p,
}: {
  label: string;
  display: string;
  frac: number; // 0..1 bar fill (normalised)
  color: string;
  p: number;
}) {
  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 5 }}>
        <span style={{ fontSize: 10.5, color: S.muted, letterSpacing: "0.04em", textTransform: "uppercase" }}>
          {label}
        </span>
        <span style={{ fontFamily: tokens.font.mono, fontSize: 13, fontWeight: 700, color: S.text }}>{display}</span>
      </div>
      <div style={{ height: 4, background: S.line, borderRadius: 99, overflow: "hidden" }}>
        <div
          style={{
            height: "100%",
            width: `${Math.max(0, Math.min(1, frac)) * p * 100}%`,
            background: color,
            borderRadius: 99,
            boxShadow: `0 0 8px -1px ${color}`,
          }}
        />
      </div>
    </div>
  );
}

export function StrategyShowcase({
  strategy: s,
  accent,
  index,
}: {
  strategy: Strategy;
  accent: string;
  index: number;
}) {
  const [ref, inView] = useInView<HTMLDivElement>(0.18);
  const p = useProgress(inView, 1100, Math.min(index * 90, 600));
  const dim = s.status === "DISABLED";
  const sColor = statusColor(s.status);

  // Count-up helpers driven by the shared clock.
  const upPct = (v: number | null, d = 1) => (v == null ? "—" : `${(v * p).toFixed(d)}%`);
  const upNum = (v: number | null, d = 2) => (v == null ? "—" : (v * p).toFixed(d));

  const sharpeColor = s.sharpe == null ? S.muted : s.sharpe >= 1 ? S.green : s.sharpe >= 0.5 ? S.amber : S.red;

  return (
    <div ref={ref}>
      <Panel glow={dim ? undefined : accent} pad={0} style={{ overflow: "hidden", opacity: dim ? 0.78 : 1 }}>
        {/* Header */}
        <div style={{ position: "relative", padding: "16px 18px 12px", borderBottom: `1px solid ${S.line}` }}>
          {/* accent sheen */}
          {!dim && (
            <div
              aria-hidden
              style={{
                position: "absolute",
                top: 0,
                left: 0,
                right: 0,
                height: 2,
                background: `linear-gradient(90deg, transparent, ${accent}, transparent)`,
                opacity: 0.7,
              }}
            />
          )}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 10 }}>
            <div style={{ minWidth: 0 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ width: 9, height: 9, borderRadius: "50%", background: accent, boxShadow: `0 0 8px ${accent}` }} />
                <span style={{ fontWeight: 700, fontSize: 15, fontFamily: tokens.font.display }}>{s.name}</span>
              </div>
              <div style={{ fontSize: 11.5, color: S.sec, marginTop: 5, lineHeight: 1.5 }}>{s.edgePlain}</div>
            </div>
            <Chip color={sColor}>{s.status}</Chip>
          </div>
        </div>

        {/* Body: radar + health ring */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1.15fr 0.85fr",
            gap: 8,
            padding: "10px 12px 4px",
            alignItems: "center",
          }}
        >
          <AnimatedRadar factors={s.factorProfile} color={accent} p={p} dim={dim} />
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 10 }}>
            <Gauge value={s.healthScore} p={p} color={healthChipColor(s.healthScore)} label="HEALTH" />
            <div style={{ textAlign: "center" }}>
              <div style={{ fontSize: 9.5, color: S.muted, letterSpacing: "0.06em" }}>BACKTEST SHARPE</div>
              <div style={{ fontFamily: tokens.font.mono, fontSize: 16, fontWeight: 700, color: S.cyan }}>
                {upNum(s.backtestSharpe)}
              </div>
            </div>
          </div>
        </div>

        {/* Stat bars */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: "12px 18px",
            padding: "12px 18px 16px",
          }}
        >
          <StatBar label="Allocation" display={upPct(s.allocationPct, 0)} frac={s.allocationPct / 30} color={accent} p={p} />
          <StatBar
            label="Win rate"
            display={s.winRatePct == null ? "—" : `${Math.round(s.winRatePct * p)}%`}
            frac={(s.winRatePct ?? 0) / 100}
            color={s.winRatePct != null && s.winRatePct >= 50 ? S.green : S.amber}
            p={p}
          />
          <StatBar
            label="Sharpe (live)"
            display={upNum(s.sharpe)}
            frac={(s.sharpe ?? 0) / 2}
            color={sharpeColor}
            p={p}
          />
          <StatBar
            label="Profit factor"
            display={upNum(s.profitFactor)}
            frac={(s.profitFactor ?? 0) / 3}
            color={s.profitFactor != null && s.profitFactor >= 1.1 ? S.green : S.amber}
            p={p}
          />
          <StatBar
            label="Trades (30d)"
            display={String(Math.round(s.tradesCount * p))}
            frac={s.tradesCount / 20}
            color={S.violet}
            p={p}
          />
          <StatBar
            label="Max drawdown"
            display={s.maxDrawdownPct == null ? "—" : `${(s.maxDrawdownPct * p).toFixed(1)}%`}
            frac={(s.maxDrawdownPct ?? 0) / 25}
            color={s.maxDrawdownPct != null && s.maxDrawdownPct > 15 ? S.red : S.sec}
            p={p}
          />
        </div>

        {/* Footer: technical edge + note */}
        <div style={{ padding: "0 18px 16px" }}>
          <div style={{ fontSize: 10.5, color: S.muted, lineHeight: 1.55 }}>{s.edgeTechnical}</div>
          {s.note && (
            <div
              style={{
                fontSize: 10.5,
                color: S.sec,
                marginTop: 8,
                padding: "6px 10px",
                background: S.glass2,
                borderRadius: 8,
                border: `1px solid ${S.line}`,
              }}
            >
              {s.note}
            </div>
          )}
        </div>
      </Panel>
    </div>
  );
}
