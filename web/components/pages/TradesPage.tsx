"use client";

import React from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Cell,
} from "recharts";
import type { Snapshot } from "@/lib/types";
import { tokens, plColor } from "@/lib/tokens";
import { Panel } from "@/components/Panel";
import { Label } from "@/components/Label";
import { Chip } from "@/components/Chip";
import { TOOLTIP_STYLE } from "@/components/ChartTooltip";
import { fmt, fmtPct, fmtDate } from "@/lib/format";

const S = tokens.color;

export function TradesPage({ snapshot }: { snapshot: Snapshot }) {
  const trades = [...snapshot.trades].sort(
    (a, b) => new Date(b.date).getTime() - new Date(a.date).getTime()
  );

  if (!trades.length) {
    return <Panel pad={40} style={{ textAlign: "center" }}><div style={{ fontSize: 14, color: S.muted }}>No closed trades yet</div></Panel>;
  }

  const totalPnl = trades.reduce((s, t) => s + t.realizedPlUsd, 0);
  const wins = trades.filter((t) => t.realizedPlUsd > 0);
  const losses = trades.filter((t) => t.realizedPlUsd <= 0);
  const winRate = (wins.length / trades.length) * 100;
  const avgWin = wins.length ? wins.reduce((s, t) => s + t.realizedPlUsd, 0) / wins.length : 0;
  const avgLoss = losses.length ? Math.abs(losses.reduce((s, t) => s + t.realizedPlUsd, 0) / losses.length) : 0;
  const pf = avgLoss > 0 ? (avgWin * wins.length) / (avgLoss * losses.length) : null;

  // P&L per trade bar chart data (last 20)
  const barData = [...trades].reverse().slice(-20).map((t, i) => ({
    i: i + 1,
    pl: t.realizedPlUsd,
    symbol: t.symbol,
  }));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {/* Stats row */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))", gap: 14 }}>
        {[
          { l: "Total P&L", v: `${totalPnl >= 0 ? "+" : ""}${fmt(totalPnl)}`, c: plColor(totalPnl) },
          { l: "Closed Trades", v: String(trades.length), c: S.text },
          { l: "Win Rate", v: `${winRate.toFixed(0)}%`, c: winRate >= 50 ? S.green : S.amber },
          { l: "Avg Win", v: fmt(avgWin), c: S.green },
          { l: "Avg Loss", v: fmt(avgLoss), c: S.red },
          { l: "Profit Factor", v: pf != null ? pf.toFixed(2) : "—", c: pf != null && pf >= 1.5 ? S.green : S.amber },
        ].map(({ l, v, c }) => (
          <Panel key={l} pad={16}>
            <div style={{ fontSize: 10, color: S.muted, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 4 }}>{l}</div>
            <div style={{ fontSize: 18, fontWeight: 800, color: c }}>{v}</div>
          </Panel>
        ))}
      </div>

      {/* P&L chart */}
      <Panel pad={20}>
        <div style={{ marginBottom: 12 }}><Label>P&L per Trade (last 20)</Label></div>
        <ResponsiveContainer width="100%" height={100}>
          <BarChart data={barData} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
            <XAxis dataKey="symbol" tick={{ fill: S.muted, fontSize: 9 }} tickLine={false} axisLine={false} />
            <YAxis tick={{ fill: S.muted, fontSize: 10 }} tickLine={false} axisLine={false} tickFormatter={(v) => `$${v.toFixed(0)}`} width={44} />
            <ReferenceLine y={0} stroke={S.muted} />
            <Tooltip contentStyle={TOOLTIP_STYLE} />
            <Bar dataKey="pl" name="P&L" radius={3}>
              {barData.map((d, i) => <Cell key={i} fill={d.pl >= 0 ? S.green : S.red} fillOpacity={0.85} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </Panel>

      {/* Trade history table */}
      <Panel pad={0} style={{ overflowX: "auto" }}>
        <div style={{ padding: "16px 20px 12px", borderBottom: `1px solid ${S.line}` }}>
          <Label>Trade History</Label>
        </div>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr style={{ color: S.muted, fontSize: 11, textTransform: "uppercase", letterSpacing: "0.06em" }}>
              {["Date", "Symbol", "Strategy", "Side", "Shares", "Entry", "Exit", "P&L", "Return", "Reason"].map((h) => (
                <th key={h} style={{ textAlign: ["Shares", "Entry", "Exit", "P&L", "Return"].includes(h) ? "right" : "left", padding: "12px 16px", fontWeight: 600, whiteSpace: "nowrap" }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {trades.map((t, i) => (
              <tr key={i} style={{ borderTop: `1px solid ${S.line}` }}>
                <td style={{ padding: "11px 16px", color: S.muted, whiteSpace: "nowrap" }}>{fmtDate(t.date)}</td>
                <td style={{ padding: "11px 16px", fontWeight: 700 }}>{t.symbol}</td>
                <td style={{ padding: "11px 16px", color: S.sec, fontSize: 12 }}>{t.strategy}</td>
                <td style={{ padding: "11px 16px" }}>
                  <Chip color={t.side === "BUY" ? S.green : S.red}>{t.side}</Chip>
                </td>
                <td style={{ padding: "11px 16px", textAlign: "right", color: S.sec }}>{t.shares}</td>
                <td style={{ padding: "11px 16px", textAlign: "right", color: S.sec }}>{fmt(t.entry)}</td>
                <td style={{ padding: "11px 16px", textAlign: "right", color: S.sec }}>{fmt(t.exit)}</td>
                <td style={{ padding: "11px 16px", textAlign: "right", color: plColor(t.realizedPlUsd), fontWeight: 700 }}>
                  {t.realizedPlUsd >= 0 ? "+" : ""}{fmt(t.realizedPlUsd)}
                </td>
                <td style={{ padding: "11px 16px", textAlign: "right", color: plColor(t.realizedPlPct) }}>
                  {fmtPct(t.realizedPlPct)}
                </td>
                <td style={{ padding: "11px 16px", color: S.muted, fontSize: 12 }}>
                  {t.exitReason.replace(/_/g, " ").toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase())}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>
    </div>
  );
}
