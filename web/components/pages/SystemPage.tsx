"use client";

import React from "react";
import type { Snapshot } from "@/lib/types";
import { tokens } from "@/lib/tokens";
import { Panel } from "@/components/Panel";
import { Label } from "@/components/Label";
import { Chip } from "@/components/Chip";
import { GLOSS_ORDER, glossary } from "@/lib/glossary";

const S = tokens.color;

const MARKER_DESCRIPTIONS: Record<string, string> = {
  broker: "Alpaca broker state matches the local database. When this fails, open the sync workflow to resolve drift.",
  data: "Market data CSV is under 72 hours old. If stale, the data update step failed in the last GHA run.",
  quality: "≥90% of tracked symbols have clean, non-null data.",
  breaker: "The portfolio-level circuit breaker is inactive. It trips at 10% drawdown from peak.",
  correlation: "Strategy correlation filter is operational.",
  regime: "Market regime detector is running and classifying VIX-based conditions.",
};

function HealthCard({ marker }: { marker: Snapshot["health"]["markers"][0] }) {
  const resolved = marker.autoResolved;
  const ok = marker.ok || marker.neutral || resolved;
  const c = ok ? S.green : S.amber;
  const desc = MARKER_DESCRIPTIONS[marker.key] ?? marker.detail;

  return (
    <Panel glow={ok ? S.green : S.amber} pad={18}>
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
            <span style={{ width: 10, height: 10, borderRadius: "50%", background: c, boxShadow: `0 0 8px ${c}88`, flexShrink: 0 }} />
            <span style={{ fontWeight: 700, fontSize: 14 }}>{marker.label}</span>
          </div>
          <div style={{ fontSize: 12.5, color: S.sec, lineHeight: 1.5 }}>{marker.detail}</div>
          {desc !== marker.detail && (
            <div style={{ fontSize: 11, color: S.muted, marginTop: 4 }}>{desc}</div>
          )}
        </div>
        <div style={{ flexShrink: 0 }}>
          {resolved ? (
            <Chip color={S.cyan}>Auto-resolved</Chip>
          ) : marker.autoAttempted ? (
            <Chip color={S.amber}>Sync attempted</Chip>
          ) : (
            <Chip color={c}>{ok ? "OK" : marker.neutral ? "Info" : "Attention"}</Chip>
          )}
        </div>
      </div>
      {marker.remaining != null && marker.remaining > 0 && (
        <div style={{ marginTop: 8, fontSize: 11.5, color: S.amber }}>
          {marker.remaining} discrepanc{marker.remaining !== 1 ? "ies" : "y"} remaining
        </div>
      )}
    </Panel>
  );
}

export function SystemPage({ snapshot }: { snapshot: Snapshot }) {
  const markers = snapshot.health.markers;
  const okCount = markers.filter((m) => m.ok || m.neutral || m.autoResolved).length;
  const allOk = okCount === markers.length;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {/* Status banner */}
      <Panel glow={allOk ? S.green : S.amber} pad={20}>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <span style={{ width: 16, height: 16, borderRadius: "50%", background: allOk ? S.green : S.amber, boxShadow: `0 0 16px ${allOk ? S.green : S.amber}`, flexShrink: 0 }} />
          <div>
            <div style={{ fontSize: 18, fontWeight: 800, letterSpacing: -0.3 }}>
              {allOk ? "All Systems Operational" : `${okCount}/${markers.length} Checks Passing`}
            </div>
            <div style={{ fontSize: 12, color: S.sec, marginTop: 2 }}>Paper trading · No real capital at risk</div>
          </div>
        </div>
      </Panel>

      {/* Health cards */}
      <Label>Health Checks</Label>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: 14 }}>
        {markers.map((m) => <HealthCard key={m.key} marker={m} />)}
      </div>

      {/* Actions */}
      {snapshot.health.syncWorkflowUrl && (
        <Panel pad={18}>
          <div style={{ marginBottom: 12 }}><Label>Manual Actions</Label></div>
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 0", borderBottom: `1px solid ${S.line}`, marginBottom: 12 }}>
              <div>
                <div style={{ fontSize: 13, fontWeight: 600 }}>Sync Database</div>
                <div style={{ fontSize: 12, color: S.muted, marginTop: 2 }}>Force-sync local DB with Alpaca to fix reconciliation drift</div>
              </div>
              <a href={snapshot.health.syncWorkflowUrl} target="_blank" rel="noopener noreferrer"
                style={{ padding: "7px 16px", background: S.lime, color: S.bg, borderRadius: 8, fontSize: 12, fontWeight: 700, textDecoration: "none", flexShrink: 0, marginLeft: 12 }}>
                Run Workflow →
              </a>
            </div>
            {[
              { cmd: "python3 scripts/sync_broker_state.py", desc: "Sync broker positions to DB" },
              { cmd: "python3 scripts/pre_flight_check.py", desc: "Run all pre-flight checks" },
              { cmd: "python3 scripts/update_daily_data.py", desc: "Refresh market data" },
            ].map(({ cmd, desc }) => (
              <div key={cmd} style={{ marginBottom: 10 }}>
                <div style={{ fontFamily: tokens.font.mono, fontSize: 12, color: S.lime, background: S.glass2, padding: "6px 10px", borderRadius: 6, border: `1px solid ${S.line}`, marginBottom: 2 }}>
                  {cmd}
                </div>
                <div style={{ fontSize: 11, color: S.muted }}>{desc}</div>
              </div>
            ))}
          </div>
        </Panel>
      )}

      {/* Snapshot meta */}
      <Panel pad={18}>
        <div style={{ marginBottom: 12 }}><Label>Snapshot Info</Label></div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 12 }}>
          {[
            { k: "Trading Date", v: snapshot.meta.tradingDate },
            { k: "Run ID", v: snapshot.meta.runId, mono: true },
            { k: "Run #", v: snapshot.meta.runNumber?.toString() ?? "—" },
            { k: "Mode", v: "Paper Trading" },
            { k: "Schema", v: `v${snapshot.meta.schemaVersion}` },
          ].map(({ k, v, mono }) => (
            <div key={k}>
              <div style={{ fontSize: 10, color: S.muted, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 3 }}>{k}</div>
              <div style={{ fontSize: 13, color: S.sec, fontFamily: mono ? tokens.font.mono : undefined }}>{v}</div>
            </div>
          ))}
        </div>
      </Panel>

      {/* Glossary */}
      <Panel pad={18}>
        <div style={{ marginBottom: 14 }}><Label>Glossary</Label></div>
        <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
          {GLOSS_ORDER.filter((k) => glossary[k]).map((key, i) => {
            const term = glossary[key];
            return (
              <div key={key} style={{ padding: "10px 0", borderTop: i > 0 ? `1px solid ${S.line}` : undefined }}>
                <div style={{ fontSize: 12.5, fontWeight: 700, color: S.lime, marginBottom: 3 }}>{term.t}</div>
                <div style={{ fontSize: 12, color: S.sec, lineHeight: 1.6 }}>{term.d}</div>
              </div>
            );
          })}
        </div>
      </Panel>
    </div>
  );
}
