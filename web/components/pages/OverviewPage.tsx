"use client";

import React from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import type { Snapshot } from "@/lib/types";
import { tokens, plColor, healthChipColor, SERIES_COLORS } from "@/lib/tokens";
import { Panel } from "@/components/Panel";
import { Chip } from "@/components/Chip";
import { Label } from "@/components/Label";
import { Sparkline } from "@/components/Sparkline";
import { TOOLTIP_STYLE } from "@/components/ChartTooltip";
import { fmt, fmtPct, fmtNum, fmtDate } from "@/lib/format";

const S = tokens.color;
const R = tokens.radius;

function Stat({
  label,
  value,
  sub,
  color,
}: {
  label: string;
  value: React.ReactNode;
  sub?: string;
  color?: string;
}) {
  return (
    <div>
      <div style={{ fontSize: 11, color: S.muted, fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase", marginBottom: 3 }}>
        {label}
      </div>
      <div style={{ fontSize: 22, fontWeight: 800, color: color ?? S.text, letterSpacing: -0.5, lineHeight: 1.1 }}>
        {value}
      </div>
      {sub && <div style={{ fontSize: 11.5, color: S.muted, marginTop: 2 }}>{sub}</div>}
    </div>
  );
}

function EqChart({ snap }: { snap: Snapshot }) {
  const data = snap.equityCurve.map((pt) => ({
    date: pt.date,
    Portfolio: pt.value,
    SPY: pt.spy,
    label: fmtDate(pt.date),
  }));

  return (
    <ResponsiveContainer width="100%" height={160}>
      <AreaChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
        <defs>
          <linearGradient id="eqGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor={S.lime} stopOpacity={0.18} />
            <stop offset="95%" stopColor={S.lime} stopOpacity={0} />
          </linearGradient>
          <linearGradient id="spyGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor={S.muted} stopOpacity={0.1} />
            <stop offset="95%" stopColor={S.muted} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke={S.line} strokeDasharray="3 4" vertical={false} />
        <XAxis dataKey="label" tick={{ fill: S.muted, fontSize: 10 }} tickLine={false} axisLine={false} interval="preserveStartEnd" />
        <YAxis domain={["auto", "auto"]} tick={{ fill: S.muted, fontSize: 10 }} tickLine={false} axisLine={false} tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} width={46} />
        <Tooltip contentStyle={TOOLTIP_STYLE} />
        {data[0]?.SPY != null && (
          <Area type="monotone" dataKey="SPY" stroke={S.muted} strokeWidth={1.5} fill="url(#spyGrad)" dot={false} strokeDasharray="4 3" />
        )}
        <Area type="monotone" dataKey="Portfolio" stroke={S.lime} strokeWidth={2} fill="url(#eqGrad)" dot={false} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

function StratCard({ s, idx }: { s: Snapshot["strategies"][0]; idx: number }) {
  const accent = SERIES_COLORS[idx % SERIES_COLORS.length];
  return (
    <Panel glow={accent} pad={18} style={{ display: "flex", flexDirection: "column", gap: 12, minWidth: 0 }}>
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 8 }}>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: 13, fontWeight: 700, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{s.name}</div>
          <div style={{ fontSize: 11, color: S.muted, marginTop: 2 }}>{s.allocationPct}% capital</div>
        </div>
        <Chip color={s.status === "ACTIVE" ? S.green : s.status === "WATCHING" ? S.amber : S.muted}>
          {s.status}
        </Chip>
      </div>

      <div style={{ display: "flex", gap: 14 }}>
        {[
          { l: "Return", v: s.returnPct != null ? fmtPct(s.returnPct) : "—", c: s.returnPct != null ? plColor(s.returnPct) : S.muted },
          { l: "Sharpe", v: fmtNum(s.sharpe), c: s.sharpe != null ? (s.sharpe >= 1 ? S.green : s.sharpe >= 0.5 ? S.amber : S.red) : S.muted },
          { l: "Win%", v: s.winRatePct != null ? `${s.winRatePct.toFixed(0)}%` : "—", c: S.text },
          { l: "Trades", v: String(s.tradesCount), c: S.text },
        ].map(({ l, v, c }) => (
          <div key={l}>
            <div style={{ fontSize: 10, color: S.muted, textTransform: "uppercase", letterSpacing: "0.05em" }}>{l}</div>
            <div style={{ fontSize: 14, fontWeight: 700, color: c }}>{v}</div>
          </div>
        ))}
      </div>

      <div style={{ fontSize: 11.5, color: S.sec, lineHeight: 1.55 }}>{s.edgePlain}</div>

      <div>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
          <span style={{ fontSize: 10, color: S.muted }}>Health</span>
          <span style={{ fontSize: 10, color: healthChipColor(s.healthScore), fontWeight: 600 }}>{s.healthScore}/100</span>
        </div>
        <div style={{ height: 3, background: S.line, borderRadius: 99, overflow: "hidden" }}>
          <div style={{ height: "100%", width: `${s.healthScore}%`, background: healthChipColor(s.healthScore), borderRadius: 99 }} />
        </div>
      </div>
    </Panel>
  );
}

function HealthBar({ snap }: { snap: Snapshot }) {
  return (
    <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
      {snap.health.markers.map((m) => {
        const ok = m.ok || m.neutral || m.autoResolved;
        const c = ok ? S.green : S.amber;
        return (
          <div
            key={m.key}
            title={m.detail}
            style={{ display: "flex", alignItems: "center", gap: 6, background: S.glass2, border: `1px solid ${c}40`, borderRadius: R.chip, padding: "4px 10px", fontSize: 11.5, color: ok ? S.sec : S.amber }}
          >
            <span style={{ width: 6, height: 6, borderRadius: "50%", background: c, flexShrink: 0 }} />
            {m.label}
          </div>
        );
      })}
    </div>
  );
}

function HoldingsTable({ snap }: { snap: Snapshot }) {
  const { positions } = snap;
  if (!positions.length) return <div style={{ color: S.muted, fontSize: 13, textAlign: "center", padding: "32px 0" }}>No open positions</div>;
  return (
    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
      <thead>
        <tr style={{ color: S.muted, fontSize: 11, textTransform: "uppercase", letterSpacing: "0.06em" }}>
          {["Symbol", "Strategy", "Shares", "Value", "P&L"].map((h, i) => (
            <th key={h} style={{ textAlign: i > 1 ? "right" : "left", paddingBottom: 10, fontWeight: 600 }}>{h}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {positions.map((p) => {
          const pl = p.unrealizedPlUsd ?? 0;
          return (
            <tr key={p.symbol} style={{ borderTop: `1px solid ${S.line}` }}>
              <td style={{ padding: "10px 0", fontWeight: 700 }}>{p.symbol}</td>
              <td style={{ padding: "10px 0", color: S.sec, fontSize: 12 }}>{p.strategy}</td>
              <td style={{ padding: "10px 0", textAlign: "right", color: S.sec }}>{p.shares}</td>
              <td style={{ padding: "10px 0", textAlign: "right" }}>{fmt(p.value)}</td>
              <td style={{ padding: "10px 0", textAlign: "right", color: plColor(pl), fontWeight: 600 }}>
                {pl >= 0 ? "+" : ""}{fmt(pl)}
                {p.unrealizedPlPct != null && (
                  <span style={{ fontSize: 11, marginLeft: 4, opacity: 0.7 }}>({fmtPct(p.unrealizedPlPct)})</span>
                )}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

export function OverviewPage({ snapshot }: { snapshot: Snapshot }) {
  const p = snapshot.portfolio;
  const change = p.todayChangeUsd;
  const allTime = p.allTimePnlUsd;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {/* Hero */}
      <Panel glow={change >= 0 ? S.lime : S.red} pad={24}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 24, marginBottom: 20 }}>
          <Stat label="Portfolio Value" value={fmt(p.totalValue)} sub={`Cash ${fmt(p.cash)}`} />
          <Stat label="Today" value={fmtPct(p.todayChangePct)} color={plColor(change)} sub={`${change >= 0 ? "+" : ""}${fmt(change)}`} />
          <Stat label="All-Time P&L" value={`${allTime >= 0 ? "+" : ""}${fmt(allTime)}`} color={plColor(allTime)} />
          <Stat label="Positions" value={p.positionsCount} sub={`${p.exposurePct.toFixed(1)}% deployed`} />
          {p.sharpe != null && (
            <Stat label="Sharpe" value={fmtNum(p.sharpe, 2)} color={p.sharpe >= 1 ? S.green : p.sharpe >= 0.5 ? S.amber : S.red} />
          )}
          {p.maxDrawdownPct != null && (
            <Stat label="Max DD" value={`${p.maxDrawdownPct.toFixed(2)}%`} color={p.maxDrawdownPct < 8 ? S.green : p.maxDrawdownPct < 15 ? S.amber : S.red} />
          )}
        </div>
        <EqChart snap={snapshot} />
      </Panel>

      {/* Health */}
      <div>
        <div style={{ marginBottom: 10 }}><Label>System Health</Label></div>
        <HealthBar snap={snapshot} />
      </div>

      {/* Strategies */}
      <div>
        <div style={{ marginBottom: 10 }}><Label>Strategies</Label></div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: 14 }}>
          {snapshot.strategies.map((s, i) => <StratCard key={s.key} s={s} idx={i} />)}
        </div>
      </div>

      {/* Holdings */}
      <Panel pad={22}>
        <div style={{ marginBottom: 14 }}><Label>Holdings</Label></div>
        <HoldingsTable snap={snapshot} />
      </Panel>
    </div>
  );
}
