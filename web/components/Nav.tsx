"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import React from "react";
import { tokens } from "@/lib/tokens";
import { relativeTime } from "@/lib/format";
import type { Snapshot } from "@/lib/types";

const PAGES = [
  { label: "Overview",   href: "/" },
  { label: "Strategies", href: "/strategies" },
  { label: "Positions",  href: "/positions" },
  { label: "Trades",     href: "/trades" },
  { label: "Signals",    href: "/signals" },
  { label: "Analytics",  href: "/analytics" },
  { label: "System",     href: "/system" },
] as const;

interface NavProps {
  snapshot: Snapshot | null;
  /** Advanced mode comes from URL ?mode=advanced, managed here */
}

export function Nav({ snapshot }: NavProps) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const isAdv = searchParams.get("mode") === "advanced";

  // Build URL with mode toggled
  function modeHref() {
    const params = new URLSearchParams(searchParams.toString());
    if (isAdv) params.delete("mode");
    else params.set("mode", "advanced");
    const q = params.toString();
    return `${pathname}${q ? `?${q}` : ""}`;
  }

  // Build page href preserving mode
  function pageHref(href: string) {
    const q = searchParams.toString();
    return `${href}${q ? `?${q}` : ""}`;
  }

  // Health summary dot (x/y healthy)
  const markers = snapshot?.health.markers ?? [];
  const healthy = markers.filter((m) => m.ok || m.neutral).length;
  const total = markers.length;
  const allOk = healthy === total;

  return (
    <nav
      style={{ marginBottom: 24 }}
      aria-label="Main navigation"
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexWrap: "wrap",
          gap: 12,
          rowGap: 12,
        }}
      >
        {/* Logo + page tabs */}
        <div style={{ display: "flex", alignItems: "center", gap: 18, flex: "1 1 auto", minWidth: 0 }}>
          <div
            style={{
              fontFamily: tokens.font.display,
              fontWeight: 800,
              fontSize: 18,
              letterSpacing: -0.5,
              whiteSpace: "nowrap",
              flex: "0 0 auto",
            }}
          >
            <span style={{ color: tokens.color.lime }}>◆</span>{" "}
            Investor<span style={{ color: tokens.color.muted }}>Mimic</span>
          </div>

          {/* Scrollable tab strip */}
          <div
            className="tscroll"
            style={{ display: "flex", gap: 2, minWidth: 0, flex: "1 1 auto" }}
          >
            {PAGES.map(({ label, href }) => {
              const active = pathname === href;
              return (
                <Link
                  key={href}
                  href={pageHref(href)}
                  className={active ? "nav-active" : ""}
                  style={{
                    padding: "7px 13px",
                    borderRadius: 10,
                    fontSize: 13,
                    fontWeight: 600,
                    whiteSpace: "nowrap",
                    color: active ? tokens.color.bg : tokens.color.sec,
                    textDecoration: "none",
                    transition: "all .15s",
                  }}
                  aria-current={active ? "page" : undefined}
                >
                  {label}
                </Link>
              );
            })}
          </div>
        </div>

        {/* Right side: mode toggle + health dot */}
        <div style={{ display: "flex", alignItems: "center", gap: 12, flex: "0 0 auto", flexWrap: "wrap" }}>
          {/* Simple/Advanced toggle — persisted in URL */}
          <Link
            href={modeHref()}
            replace
            aria-label={isAdv ? "Switch to Simple mode" : "Switch to Advanced mode"}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              cursor: "pointer",
              background: tokens.color.glass2,
              border: `1px solid ${tokens.color.line}`,
              borderRadius: tokens.radius.pill,
              padding: "5px 8px 5px 13px",
              textDecoration: "none",
            }}
          >
            <span style={{ fontSize: 12, color: tokens.color.sec, fontWeight: 600 }}>
              {isAdv ? "Advanced" : "Simple"}
            </span>
            {/* Toggle track */}
            <div
              style={{
                width: 38,
                height: 20,
                borderRadius: 999,
                background: isAdv ? tokens.color.lime : "#2a2f3a",
                position: "relative",
                transition: "background .2s",
                flexShrink: 0,
              }}
            >
              <div
                style={{
                  position: "absolute",
                  top: 2,
                  left: isAdv ? 20 : 2,
                  width: 16,
                  height: 16,
                  borderRadius: "50%",
                  background: isAdv ? tokens.color.bg : "#8a94a3",
                  transition: "left .2s",
                }}
              />
            </div>
          </Link>

          {/* Health dot */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 7,
              background: tokens.color.glass2,
              border: `1px solid ${tokens.color.line}`,
              borderRadius: tokens.radius.pill,
              padding: "6px 12px",
            }}
          >
            <span
              style={{
                width: 8,
                height: 8,
                borderRadius: "50%",
                background: allOk ? tokens.color.green : tokens.color.amber,
                boxShadow: `0 0 8px ${allOk ? tokens.color.green : tokens.color.amber}`,
                flexShrink: 0,
              }}
            />
            <span
              style={{ fontSize: 12, color: tokens.color.sec, fontFamily: tokens.font.mono }}
            >
              {total > 0 ? `${healthy}/${total}` : "—"}
            </span>
          </div>
        </div>
      </div>

      {/* Simple-mode banner */}
      {!isAdv && (
        <div
          style={{
            marginTop: 12,
            fontSize: 12.5,
            color: tokens.color.sec,
            background: tokens.color.glass2,
            border: `1px solid ${tokens.color.line}`,
            borderRadius: 12,
            padding: "12px 16px",
            display: "flex",
            alignItems: "flex-start",
            gap: 10,
          }}
        >
          <span style={{ color: tokens.color.lime, flexShrink: 0, marginTop: 1 }}>ⓘ</span>
          <span style={{ lineHeight: 1.6 }}>
            Simple mode hides the technical stats. See a{" "}
            <span
              aria-hidden
              style={{
                display: "inline-flex",
                width: 15,
                height: 15,
                boxSizing: "border-box",
                borderRadius: "50%",
                border: `1px solid ${tokens.color.muted}`,
                color: tokens.color.muted,
                fontSize: 9,
                fontWeight: 700,
                alignItems: "center",
                justifyContent: "center",
                verticalAlign: "middle",
                lineHeight: 1,
              }}
            >
              ?
            </span>{" "}
            next to anything? Hover or tap for a plain-English explanation. Flip to{" "}
            <strong style={{ color: tokens.color.text }}>Advanced</strong> (top right) for the full quant view.
          </span>
        </div>
      )}

      {/* Freshness canary — ties meta.generatedAt to a visible timestamp */}
      {snapshot && (
        <div
          style={{
            marginTop: 8,
            fontSize: 11,
            color: tokens.color.muted,
            textAlign: "right",
            fontFamily: tokens.font.mono,
          }}
        >
          PAPER TRADING · NO REAL CAPITAL · Snapshot from{" "}
          {snapshot.meta.tradingDate} · updated {relativeTime(snapshot.meta.generatedAt)}
        </div>
      )}
    </nav>
  );
}
