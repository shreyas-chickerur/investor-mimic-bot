"use client";

import React from "react";
import {
  AreaChart,
  Area,
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Cell,
  ReferenceLine,
} from "recharts";
import type { Snapshot } from "@/lib/types";
import { tokens, SERIES_COLORS } from "@/lib/tokens";
import { Panel } from "@/components/Panel";
import { Label } from "@/components/Label";
import { TOOLTIP_STYLE } from "@/components/ChartTooltip";
import { fmtNum, fmtDate, fmtMonth } from "@/lib/format";

const S = tokens.color;

export function AnalyticsPage({ snapshot }: { snapshot: Snapshot }) {
  const a = snapshot.analytics;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {/* Drawdown */}
      <Panel pad={20}>
        <div style={{ marginBottom: 14 }}><Label termKey="underwater">Drawdown</Label></div>
        <ResponsiveContainer width="100%" height={140}>
          <AreaChart data={a.drawdown} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id="ddG" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={S.red} stopOpacity={0.3} />
                <stop offset="95%" stopColor={S.red} stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke={S.line} strokeDasharray="3 4" vertical={false} />
            <XAxis dataKey="date" tickFormatter={fmtDate} tick={{ fill: S.muted, fontSize: 10 }} tickLine={false} axisLine={false} interval="preserveStartEnd" />
            <YAxis tick={{ fill: S.muted, fontSize: 10 }} tickLine={false} axisLine={false} tickFormatter={(v) => `${v.toFixed(1)}%`} width={46} />
            <Tooltip contentStyle={TOOLTIP_STYLE} />
            <Area type="monotone" dataKey="ddPct" stroke={S.red} strokeWidth={2} fill="url(#ddG)" dot={false} name="Drawdown %" />
          </AreaChart>
        </ResponsiveContainer>
      </Panel>

      {/* Rolling Sharpe */}
      {a.rollingSharpe.length > 0 && (
        <Panel pad={20}>
          <div style={{ marginBottom: 14 }}><Label termKey="sharpe">Rolling Sharpe (30d)</Label></div>
          <ResponsiveContainer width="100%" height={120}>
            <LineChart data={a.rollingSharpe} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
              <CartesianGrid stroke={S.line} strokeDasharray="3 4" vertical={false} />
              <XAxis dataKey="date" tickFormatter={fmtDate} tick={{ fill: S.muted, fontSize: 10 }} tickLine={false} axisLine={false} interval="preserveStartEnd" />
              <YAxis tick={{ fill: S.muted, fontSize: 10 }} tickLine={false} axisLine={false} tickFormatter={(v) => v.toFixed(1)} width={36} />
              <ReferenceLine y={1} stroke={S.green} strokeDasharray="4 3" strokeWidth={1} label={{ value: "1.0", fill: S.green, fontSize: 10, position: "right" }} />
              <ReferenceLine y={0} stroke={S.muted} strokeWidth={1} />
              <Tooltip contentStyle={TOOLTIP_STYLE} />
              <Line type="monotone" dataKey="sharpe" stroke={S.cyan} strokeWidth={2} dot={false} name="Sharpe" />
            </LineChart>
          </ResponsiveContainer>
        </Panel>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 14 }}>
        {/* Monthly returns */}
        {a.monthlyReturns.length > 0 && (
          <Panel pad={20}>
            <div style={{ marginBottom: 14 }}><Label>Monthly Returns</Label></div>
            <ResponsiveContainer width="100%" height={150}>
              <BarChart data={a.monthlyReturns} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
                <CartesianGrid stroke={S.line} strokeDasharray="3 4" vertical={false} />
                <XAxis dataKey="month" tickFormatter={(v) => fmtMonth(v).split(" ")[0]} tick={{ fill: S.muted, fontSize: 10 }} tickLine={false} axisLine={false} />
                <YAxis tick={{ fill: S.muted, fontSize: 10 }} tickLine={false} axisLine={false} tickFormatter={(v) => `${v.toFixed(1)}%`} width={42} />
                <ReferenceLine y={0} stroke={S.muted} />
                <Tooltip contentStyle={TOOLTIP_STYLE} />
                <Bar dataKey="returnPct" name="Return %" radius={3}>
                  {a.monthlyReturns.map((e, i) => <Cell key={i} fill={(e.returnPct ?? 0) >= 0 ? S.green : S.red} fillOpacity={0.8} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
            <div style={{ display: "flex", gap: 16, marginTop: 10 }}>
              {a.bestMonth && (
                <div>
                  <div style={{ fontSize: 10, color: S.muted }}>Best</div>
                  <div style={{ fontSize: 12, color: S.green, fontWeight: 600 }}>{fmtMonth(a.bestMonth.month)} +{a.bestMonth.returnPct.toFixed(2)}%</div>
                </div>
              )}
              {a.worstMonth && (
                <div>
                  <div style={{ fontSize: 10, color: S.muted }}>Worst</div>
                  <div style={{ fontSize: 12, color: S.red, fontWeight: 600 }}>{fmtMonth(a.worstMonth.month)} {a.worstMonth.returnPct.toFixed(2)}%</div>
                </div>
              )}
            </div>
          </Panel>
        )}

        {/* Return distribution */}
        {a.returnDistribution.length > 0 && (
          <Panel pad={20}>
            <div style={{ marginBottom: 14 }}><Label>Return Distribution</Label></div>
            <ResponsiveContainer width="100%" height={150}>
              <BarChart data={a.returnDistribution} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
                <CartesianGrid stroke={S.line} strokeDasharray="3 4" vertical={false} />
                <XAxis dataKey="bucket" tick={{ fill: S.muted, fontSize: 9 }} tickLine={false} axisLine={false} />
                <YAxis tick={{ fill: S.muted, fontSize: 10 }} tickLine={false} axisLine={false} width={28} />
                <Tooltip contentStyle={TOOLTIP_STYLE} />
                <Bar dataKey="count" name="Trades" radius={3}>
                  {a.returnDistribution.map((e, i) => (
                    <Cell key={i} fill={e.bucket.startsWith("-") ? S.red : S.green} fillOpacity={0.75} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </Panel>
        )}
      </div>

      {/* Backtest vs Live */}
      {a.backtestVsLive.length > 0 && (
        <Panel pad={20}>
          <div style={{ marginBottom: 14 }}><Label termKey="backtest">Backtest Sharpe vs Live Sharpe</Label></div>
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {a.backtestVsLive.map((row) => {
              const bt = row.backtestSharpe ?? 0;
              const lv = row.liveSharpe ?? 0;
              const maxVal = Math.max(bt, lv, 1.5);
              return (
                <div key={row.strategy}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                    <span style={{ fontSize: 12, color: S.sec }}>{row.strategy}</span>
                    <div style={{ display: "flex", gap: 12, fontSize: 11 }}>
                      <span style={{ color: S.muted }}>BT: <strong style={{ color: S.cyan }}>{row.backtestSharpe != null ? row.backtestSharpe.toFixed(2) : "—"}</strong></span>
                      <span style={{ color: S.muted }}>Live: <strong style={{ color: row.liveSharpe != null ? (row.liveSharpe >= 0.5 ? S.green : S.amber) : S.muted }}>{row.liveSharpe != null ? row.liveSharpe.toFixed(2) : "—"}</strong></span>
                    </div>
                  </div>
                  <div style={{ display: "flex", gap: 4 }}>
                    <div style={{ flex: 1, height: 4, background: S.line, borderRadius: 99, overflow: "hidden" }}>
                      <div style={{ height: "100%", width: `${(bt / maxVal) * 100}%`, background: S.cyan, borderRadius: 99 }} />
                    </div>
                    <div style={{ flex: 1, height: 4, background: S.line, borderRadius: 99, overflow: "hidden" }}>
                      <div style={{ height: "100%", width: `${(lv / maxVal) * 100}%`, background: lv >= 0.5 ? S.green : S.amber, borderRadius: 99 }} />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
          <div style={{ display: "flex", gap: 12, marginTop: 10, fontSize: 11 }}>
            <span style={{ color: S.cyan }}>■</span><span style={{ color: S.muted }}>Backtest</span>
            <span style={{ color: S.green, marginLeft: 6 }}>■</span><span style={{ color: S.muted }}>Live</span>
          </div>
        </Panel>
      )}

      {/* Correlation matrix */}
      {a.strategyCorrelation.labels.length > 0 && (
        <Panel pad={20}>
          <div style={{ marginBottom: 14 }}><Label termKey="correlation">Strategy Correlation</Label></div>
          <div style={{ overflowX: "auto" }}>
            <table style={{ borderCollapse: "collapse", fontSize: 11 }}>
              <thead>
                <tr>
                  <th style={{ padding: "6px 8px", color: S.muted }} />
                  {a.strategyCorrelation.labels.map((l) => (
                    <th key={l} style={{ padding: "6px 8px", color: S.muted, fontWeight: 600, whiteSpace: "nowrap" }}>
                      {l.split(" ")[0]}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {a.strategyCorrelation.matrix.map((row, ri) => (
                  <tr key={ri}>
                    <td style={{ padding: "6px 8px", color: S.muted, fontWeight: 600, whiteSpace: "nowrap" }}>
                      {a.strategyCorrelation.labels[ri]?.split(" ")[0]}
                    </td>
                    {row.map((v, ci) => {
                      const val = v ?? 0;
                      const isdiag = ri === ci;
                      const bg = isdiag ? `${S.lime}22` : val > 0.6 ? `${S.red}${Math.round(val * 99).toString(16).padStart(2, "0")}` : "transparent";
                      return (
                        <td key={ci} style={{ padding: "6px 8px", textAlign: "center", background: bg, color: isdiag ? S.lime : Math.abs(val) > 0.5 ? S.text : S.muted, fontWeight: isdiag ? 700 : 400, borderRadius: 4 }}>
                          {v != null ? v.toFixed(2) : "—"}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div style={{ fontSize: 11, color: S.muted, marginTop: 8 }}>
            Red cells = high positive correlation (concentrated risk). Values above 0.6 indicate the strategies may be making the same bet.
          </div>
        </Panel>
      )}
    </div>
  );
}
