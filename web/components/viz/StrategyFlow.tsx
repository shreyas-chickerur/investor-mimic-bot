"use client";

import React from "react";
import type { Snapshot } from "@/lib/types";
import type { FlowKind, FlowStep } from "@/lib/strategyFlows";
import { tokens } from "@/lib/tokens";
import { Panel } from "@/components/Panel";
import { Chip } from "@/components/Chip";
import { useInView } from "./useReveal";

const S = tokens.color;
type Strategy = Snapshot["strategies"][number];

// Each step kind gets a label + colour so the pipeline reads at a glance.
const KIND: Record<FlowKind, { label: string; color: string }> = {
  scan: { label: "SCAN", color: S.muted },
  gate: { label: "GATE", color: S.amber },
  signal: { label: "SIGNAL", color: S.lime },
  filter: { label: "FILTER", color: S.violet },
  rank: { label: "RANK", color: S.cyan },
  entry: { label: "ENTRY", color: S.green },
  hold: { label: "HOLD", color: S.sec },
  exit: { label: "EXIT", color: S.mag },
};

function StepNode({ step, n, reveal, delay }: { step: FlowStep; n: number; reveal: boolean; delay: number }) {
  const k = KIND[step.kind];
  return (
    <div
      className={reveal ? "animate-rise" : undefined}
      style={{
        animationDelay: `${delay}ms`,
        opacity: reveal ? undefined : 0,
        flex: "0 0 auto",
        width: 176,
        alignSelf: "stretch",
        background: S.panel2,
        border: `1px solid ${k.color}55`,
        borderRadius: 14,
        padding: "11px 13px",
        position: "relative",
        boxShadow: `inset 0 0 0 1px ${S.line2}`,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 7 }}>
        <Chip color={k.color}>{k.label}</Chip>
        <span
          style={{
            fontFamily: tokens.font.mono,
            fontSize: 10,
            color: S.muted,
            border: `1px solid ${S.line}`,
            borderRadius: 99,
            width: 18,
            height: 18,
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          {n}
        </span>
      </div>
      <div style={{ fontWeight: 700, fontSize: 12.5, color: S.text, marginBottom: step.detail || step.rules ? 4 : 0 }}>
        {step.title}
      </div>
      {step.detail && <div style={{ fontSize: 10.5, color: S.sec, lineHeight: 1.5 }}>{step.detail}</div>}
      {step.rules && (
        <div style={{ display: "flex", flexDirection: "column", gap: 5, marginTop: 2 }}>
          {step.rules.map((r, i) => (
            <div key={i} style={{ fontSize: 10, lineHeight: 1.45 }}>
              <span style={{ color: S.sec }}>{r.when}</span>
              <span style={{ color: k.color, fontWeight: 700 }}> ▸ {r.then}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function Connector({ color, index }: { color: string; index: number }) {
  return (
    <div
      aria-hidden
      style={{
        flex: "0 0 auto",
        width: 30,
        alignSelf: "center",
        position: "relative",
        height: 16,
        display: "flex",
        alignItems: "center",
      }}
    >
      {/* track */}
      <div style={{ height: 2, width: "100%", background: S.line, borderRadius: 2 }} />
      {/* travelling pulse — staggered so it flows down the whole pipeline */}
      <div
        className="flow-dot"
        style={{
          position: "absolute",
          top: "50%",
          marginTop: -2.5,
          width: 5,
          height: 5,
          borderRadius: "50%",
          background: color,
          boxShadow: `0 0 7px 1px ${color}`,
          animationDelay: `${index * 0.18}s`,
        }}
      />
      {/* arrowhead */}
      <div
        style={{
          position: "absolute",
          right: -1,
          top: "50%",
          transform: "translateY(-50%)",
          width: 0,
          height: 0,
          borderTop: "4px solid transparent",
          borderBottom: "4px solid transparent",
          borderLeft: `6px solid ${S.muted}`,
        }}
      />
    </div>
  );
}

export function StrategyFlow({
  strategy: s,
  accent,
  steps,
}: {
  strategy: Strategy;
  accent: string;
  steps: FlowStep[];
}) {
  const [ref, inView] = useInView<HTMLDivElement>(0.12);
  const dim = s.status === "DISABLED";

  return (
    <div ref={ref}>
      <Panel glow={dim ? undefined : accent} pad={0} style={{ overflow: "hidden", opacity: dim ? 0.82 : 1 }}>
        {/* Header */}
        <div style={{ padding: "13px 18px", borderBottom: `1px solid ${S.line}`, display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 9, minWidth: 0 }}>
            <span style={{ width: 9, height: 9, borderRadius: "50%", background: accent, boxShadow: `0 0 8px ${accent}`, flexShrink: 0 }} />
            <span style={{ fontWeight: 700, fontSize: 14, fontFamily: tokens.font.display }}>{s.name}</span>
            <span style={{ fontSize: 11.5, color: S.sec, marginLeft: 4, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
              {s.edgePlain}
            </span>
          </div>
          <Chip color={s.status === "ACTIVE" ? S.green : s.status === "WATCHING" ? S.amber : S.muted}>{s.status}</Chip>
        </div>

        {/* Pipeline (horizontal, scrolls on narrow screens) */}
        <div style={{ overflowX: "auto", padding: "16px 18px 18px" }}>
          <div style={{ display: "flex", alignItems: "stretch", gap: 0, minWidth: "min-content" }}>
            {steps.map((step, i) => (
              <React.Fragment key={i}>
                <StepNode step={step} n={i + 1} reveal={inView} delay={i * 70} />
                {i < steps.length - 1 && <Connector color={accent} index={i} />}
              </React.Fragment>
            ))}
          </div>
        </div>
      </Panel>
    </div>
  );
}
