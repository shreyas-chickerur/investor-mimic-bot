"use client";

import React from "react";
import type { Snapshot } from "@/lib/types";
import type { FlowKind, FlowStep } from "@/lib/strategyFlows";
import { KIND_INFO, TERMS } from "@/lib/strategyFlows";
import { tokens } from "@/lib/tokens";
import { Panel } from "@/components/Panel";
import { Chip } from "@/components/Chip";

const S = tokens.color;
type Strategy = Snapshot["strategies"][number];
type Candidate = Snapshot["signals"]["explorer"][number];
type Position = Snapshot["positions"][number];
type Trade = Snapshot["trades"][number];

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

interface LiveData {
  candidates: Candidate[];
  positions: Position[];
  trades: Trade[];
}

// How many live items sit at a given stage right now — drives the badge + the
// "active" glow + what the detail panel shows.
function liveCount(kind: FlowKind, d: LiveData): number {
  switch (kind) {
    case "scan":
    case "signal":
    case "gate":
    case "filter":
    case "rank":
      return d.candidates.length;
    case "entry":
      return d.candidates.filter((c) => c.status === "EXECUTED").length || d.trades.filter((t) => t.side === "BUY").length;
    case "hold":
      return d.positions.length;
    case "exit":
      return d.trades.filter((t) => t.side === "SELL" || t.side === "COVER").length;
  }
}

function plColor(n: number | null | undefined): string {
  if (n == null) return S.sec;
  return n >= 0 ? S.green : S.red;
}

// The jargon definitions relevant to a step (its text mentions them).
function termsFor(step: FlowStep): { t: string; d: string }[] {
  const hay = `${step.title} ${step.detail ?? ""} ${(step.rules ?? []).map((r) => r.when + r.then).join(" ")}`.toLowerCase();
  const seen = new Set<string>();
  const out: { t: string; d: string }[] = [];
  for (const [key, val] of Object.entries(TERMS)) {
    if (hay.includes(key.toLowerCase()) && !seen.has(val.t)) {
      seen.add(val.t);
      out.push(val);
    }
  }
  return out;
}

function StatusPill({ status }: { status: Candidate["status"] }) {
  const c = status === "EXECUTED" ? S.green : status === "DEFERRED" ? S.amber : S.muted;
  return <Chip color={c}>{status}</Chip>;
}

/** The drill-down shown when a step is clicked: what it means + live data. */
function StepDetail({ step, accent, data }: { step: FlowStep; accent: string; data: LiveData }) {
  const terms = termsFor(step);
  const k = KIND[step.kind];

  // Real data relevant to this stage.
  let live: React.ReactNode = null;
  if (["scan", "signal", "gate", "filter", "rank"].includes(step.kind)) {
    live = data.candidates.length ? (
      <DataList title={`Today's candidates for this strategy (${data.candidates.length})`}>
        {data.candidates.map((c, i) => (
          <div key={i} style={rowStyle}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 2 }}>
              <span style={{ fontWeight: 700, fontFamily: tokens.font.mono, color: S.text }}>{c.symbol}</span>
              <StatusPill status={c.status} />
              {c.confidence != null && <span style={{ fontSize: 10.5, color: S.muted }}>conf {(c.confidence * 100).toFixed(0)}%</span>}
            </div>
            <div style={{ fontSize: 10.5, color: S.sec, lineHeight: 1.5 }}>{c.reason}</div>
          </div>
        ))}
      </DataList>
    ) : (
      <Empty>No live candidates from this strategy in the latest run.</Empty>
    );
  } else if (step.kind === "entry") {
    const ex = data.candidates.filter((c) => c.status === "EXECUTED");
    live = ex.length ? (
      <DataList title={`Executed this run (${ex.length})`}>
        {ex.map((c, i) => (
          <div key={i} style={rowStyle}>
            <span style={{ fontWeight: 700, fontFamily: tokens.font.mono }}>{c.symbol}</span>
            <span style={{ fontSize: 10.5, color: S.sec }}> — {c.reason}</span>
          </div>
        ))}
      </DataList>
    ) : (
      <Empty>No entries executed by this strategy in the latest run.</Empty>
    );
  } else if (step.kind === "hold") {
    live = data.positions.length ? (
      <DataList title={`Currently held (${data.positions.length})`}>
        {data.positions.map((p, i) => (
          <div key={i} style={{ ...rowStyle, display: "flex", justifyContent: "space-between" }}>
            <span>
              <span style={{ fontWeight: 700, fontFamily: tokens.font.mono }}>{p.symbol}</span>
              <span style={{ fontSize: 10.5, color: S.muted }}> · {p.shares} sh</span>
            </span>
            {p.unrealizedPlPct != null && (
              <span style={{ fontFamily: tokens.font.mono, fontSize: 11, color: plColor(p.unrealizedPlPct) }}>
                {p.unrealizedPlPct >= 0 ? "+" : ""}
                {p.unrealizedPlPct.toFixed(1)}%
              </span>
            )}
          </div>
        ))}
      </DataList>
    ) : (
      <Empty>This strategy holds no open positions right now.</Empty>
    );
  } else if (step.kind === "exit") {
    const ex = data.trades.filter((t) => t.side === "SELL" || t.side === "COVER").slice(0, 6);
    live = ex.length ? (
      <DataList title={`Recent exits (${ex.length})`}>
        {ex.map((t, i) => (
          <div key={i} style={rowStyle}>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ fontWeight: 700, fontFamily: tokens.font.mono }}>
                {t.symbol} <span style={{ color: S.muted, fontWeight: 400 }}>· {t.date}</span>
              </span>
              <span style={{ fontFamily: tokens.font.mono, fontSize: 11, color: plColor(t.realizedPlUsd) }}>
                {t.realizedPlUsd >= 0 ? "+" : ""}
                {t.realizedPlUsd.toFixed(0)} ({t.realizedPlPct >= 0 ? "+" : ""}
                {t.realizedPlPct.toFixed(1)}%)
              </span>
            </div>
            <div style={{ fontSize: 10.5, color: S.sec }}>{t.exitReason}</div>
          </div>
        ))}
      </DataList>
    ) : (
      <Empty>No recent exits recorded for this strategy.</Empty>
    );
  }

  return (
    <div style={{ borderTop: `1px solid ${k.color}44`, background: S.panel2, padding: "14px 18px" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
        <Chip color={k.color}>{k.label}</Chip>
        <span style={{ fontWeight: 700, fontSize: 13.5 }}>{step.title}</span>
      </div>
      {step.detail && <div style={{ fontSize: 12, color: S.text, lineHeight: 1.55, marginBottom: 6 }}>{step.detail}</div>}
      <div style={{ fontSize: 11.5, color: S.sec, lineHeight: 1.55, marginBottom: 8 }}>{KIND_INFO[step.kind]}</div>

      {step.rules && (
        <div style={{ display: "flex", flexDirection: "column", gap: 4, marginBottom: 10 }}>
          {step.rules.map((r, i) => (
            <div key={i} style={{ fontSize: 11.5 }}>
              <span style={{ color: S.sec }}>{r.when}</span>
              <span style={{ color: k.color, fontWeight: 700 }}> ▸ {r.then}</span>
            </div>
          ))}
        </div>
      )}

      {terms.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 6, marginBottom: live ? 12 : 0 }}>
          {terms.map((t, i) => (
            <div key={i} style={{ fontSize: 11, lineHeight: 1.5 }}>
              <span style={{ color: accent, fontWeight: 700 }}>{t.t}</span>
              <span style={{ color: S.sec }}> — {t.d}</span>
            </div>
          ))}
        </div>
      )}

      {live}
    </div>
  );
}

const rowStyle: React.CSSProperties = {
  padding: "7px 0",
  borderTop: `1px solid ${S.line2}`,
};

function DataList({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <div style={{ fontSize: 10, letterSpacing: "0.06em", textTransform: "uppercase", color: S.muted, marginBottom: 2 }}>
        {title}
      </div>
      {children}
    </div>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return <div style={{ fontSize: 11, color: S.muted, fontStyle: "italic" }}>{children}</div>;
}

function StepNode({
  step,
  n,
  count,
  active,
  selected,
  onClick,
  nodeRef,
}: {
  step: FlowStep;
  n: number;
  count: number;
  active: boolean;
  selected: boolean;
  onClick: () => void;
  nodeRef?: (el: HTMLButtonElement | null) => void;
}) {
  const k = KIND[step.kind];
  return (
    <button
      ref={nodeRef}
      onClick={onClick}
      className="animate-rise"
      style={{
        animationDelay: `${n * 60}ms`,
        flex: "0 0 auto",
        width: 178,
        alignSelf: "stretch",
        textAlign: "left",
        cursor: "pointer",
        background: selected ? `${k.color}14` : S.panel2,
        border: `1px solid ${active ? k.color : `${k.color}44`}`,
        outline: selected ? `1px solid ${k.color}` : "none",
        borderRadius: 14,
        padding: "11px 13px",
        color: "inherit",
        font: "inherit",
        boxShadow: active ? `0 0 16px -6px ${k.color}` : "none",
        transition: "background 0.15s ease, box-shadow 0.15s ease",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 7 }}>
        <Chip color={k.color}>{k.label}</Chip>
        <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
          {count > 0 && (
            <span
              style={{
                fontFamily: tokens.font.mono,
                fontSize: 10,
                fontWeight: 700,
                color: k.color,
                background: `${k.color}1f`,
                borderRadius: 99,
                padding: "1px 7px",
              }}
            >
              {count} live
            </span>
          )}
          <span style={{ fontFamily: tokens.font.mono, fontSize: 10, color: S.muted, width: 18, height: 18, display: "inline-flex", alignItems: "center", justifyContent: "center", border: `1px solid ${S.line}`, borderRadius: 99 }}>
            {n}
          </span>
        </span>
      </div>
      <div style={{ fontWeight: 700, fontSize: 12.5, color: S.text, marginBottom: step.detail ? 4 : 0 }}>{step.title}</div>
      {step.detail && <div style={{ fontSize: 10.5, color: S.sec, lineHeight: 1.45 }}>{step.detail}</div>}
      <div style={{ fontSize: 9.5, color: k.color, marginTop: 7, opacity: 0.85 }}>tap to expand ↓</div>
    </button>
  );
}

function Connector({ color, index }: { color: string; index: number }) {
  return (
    <div aria-hidden style={{ flex: "0 0 auto", width: 30, alignSelf: "center", position: "relative", height: 16, display: "flex", alignItems: "center" }}>
      <div style={{ height: 2, width: "100%", background: S.line, borderRadius: 2 }} />
      <div className="flow-dot" style={{ position: "absolute", top: "50%", marginTop: -2.5, width: 5, height: 5, borderRadius: "50%", background: color, boxShadow: `0 0 7px 1px ${color}`, animationDelay: `${index * 0.18}s` }} />
      <div style={{ position: "absolute", right: -1, top: "50%", transform: "translateY(-50%)", width: 0, height: 0, borderTop: "4px solid transparent", borderBottom: "4px solid transparent", borderLeft: `6px solid ${S.muted}` }} />
    </div>
  );
}

export function StrategyFlow({
  strategy: s,
  accent,
  steps,
  candidates,
  positions,
  trades,
}: {
  strategy: Strategy;
  accent: string;
  steps: FlowStep[];
  candidates: Candidate[];
  positions: Position[];
  trades: Trade[];
}) {
  const data: LiveData = { candidates, positions, trades };
  const dim = s.status === "DISABLED";
  // Default-open the first stage that actually has live data, so a strategy
  // that did something today shows real numbers immediately.
  const firstLive = steps.findIndex((st) => liveCount(st.kind, data) > 0);
  const [sel, setSel] = React.useState<number>(firstLive);
  const scrollRef = React.useRef<HTMLDivElement>(null);
  const nodeEls = React.useRef<(HTMLButtonElement | null)[]>([]);

  const goTo = React.useCallback((i: number) => {
    setSel(i);
    const el = nodeEls.current[i];
    if (el) el.scrollIntoView({ behavior: "smooth", inline: "center", block: "nearest" });
  }, []);

  const exits = trades.filter((t) => t.side === "SELL" || t.side === "COVER");
  const lastExit = exits[0];
  const liveSummary = [
    candidates.length ? `${candidates.length} signal${candidates.length > 1 ? "s" : ""} today` : null,
    positions.length ? `${positions.length} held` : null,
    lastExit ? `last exit ${lastExit.symbol} ${lastExit.realizedPlPct >= 0 ? "+" : ""}${lastExit.realizedPlPct.toFixed(1)}%` : null,
  ].filter(Boolean);

  return (
    <Panel glow={dim ? undefined : accent} pad={0} style={{ overflow: "hidden", opacity: dim ? 0.82 : 1 }}>
      {/* Header */}
      <div style={{ padding: "13px 18px", borderBottom: `1px solid ${S.line}`, display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 9, minWidth: 0 }}>
          <span style={{ width: 9, height: 9, borderRadius: "50%", background: accent, boxShadow: `0 0 8px ${accent}`, flexShrink: 0 }} />
          <span style={{ fontWeight: 700, fontSize: 14, fontFamily: tokens.font.display }}>{s.name}</span>
          <span style={{ fontSize: 11.5, color: S.sec, marginLeft: 4 }}>{s.edgePlain}</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          {liveSummary.length > 0 && (
            <span style={{ fontSize: 10.5, color: S.muted, fontFamily: tokens.font.mono }}>● {liveSummary.join(" · ")}</span>
          )}
          <Chip color={s.status === "ACTIVE" ? S.green : s.status === "WATCHING" ? S.amber : S.muted}>{s.status}</Chip>
        </div>
      </div>

      {/* Pipeline */}
      <div ref={scrollRef} style={{ overflowX: "auto", padding: "16px 18px 14px" }}>
        <div style={{ display: "flex", alignItems: "stretch", minWidth: "min-content" }}>
          {steps.map((step, i) => {
            const count = liveCount(step.kind, data);
            return (
              <React.Fragment key={i}>
                <StepNode
                  step={step}
                  n={i + 1}
                  count={count}
                  active={count > 0}
                  selected={sel === i}
                  onClick={() => (sel === i ? setSel(-1) : goTo(i))}
                  nodeRef={(el) => {
                    nodeEls.current[i] = el;
                  }}
                />
                {i < steps.length - 1 && <Connector color={accent} index={i} />}
              </React.Fragment>
            );
          })}
        </div>
      </div>

      {/* Walkthrough controls */}
      <WalkthroughBar
        accent={accent}
        sel={sel}
        total={steps.length}
        title={sel >= 0 ? steps[sel].title : null}
        onStart={() => goTo(0)}
        onPrev={() => goTo(Math.max(0, sel - 1))}
        onNext={() => goTo(Math.min(steps.length - 1, sel + 1))}
        onClose={() => setSel(-1)}
      />

      {/* Click-through detail */}
      {sel >= 0 && sel < steps.length && <StepDetail step={steps[sel]} accent={accent} data={data} />}
    </Panel>
  );
}

function WalkthroughBar({
  accent,
  sel,
  total,
  title,
  onStart,
  onPrev,
  onNext,
  onClose,
}: {
  accent: string;
  sel: number;
  total: number;
  title: string | null;
  onStart: () => void;
  onPrev: () => void;
  onNext: () => void;
  onClose: () => void;
}) {
  const btn = (label: string, onClick: () => void, disabled = false, primary = false): React.ReactNode => (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        cursor: disabled ? "default" : "pointer",
        fontFamily: tokens.font.body,
        fontSize: 11.5,
        fontWeight: 700,
        color: disabled ? S.muted : primary ? tokens.color.bg : accent,
        background: primary ? accent : "transparent",
        border: `1px solid ${disabled ? S.line : accent}`,
        borderRadius: 8,
        padding: "5px 12px",
        opacity: disabled ? 0.5 : 1,
      }}
    >
      {label}
    </button>
  );

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "0 18px 14px" }}>
      {sel < 0 ? (
        <>
          {btn("▸ Walk me through", onStart, false, true)}
          <span style={{ fontSize: 11, color: S.muted }}>— or click any step above</span>
        </>
      ) : (
        <>
          {btn("← Prev", onPrev, sel === 0)}
          <span style={{ fontSize: 11.5, color: S.sec, fontFamily: tokens.font.mono, minWidth: 150 }}>
            Step {sel + 1} of {total}
            <span style={{ color: accent }}> · {title}</span>
          </span>
          {btn(sel === total - 1 ? "Finish" : "Next →", sel === total - 1 ? onClose : onNext, false, true)}
          <button onClick={onClose} style={{ marginLeft: "auto", cursor: "pointer", background: "transparent", border: "none", color: S.muted, fontSize: 12 }}>
            ✕ close
          </button>
        </>
      )}
    </div>
  );
}
