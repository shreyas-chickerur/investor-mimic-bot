"use client";

import React, { Suspense } from "react";
import { tokens, meshGradient } from "@/lib/tokens";
import type { Snapshot } from "@/lib/types";
import { Nav } from "./Nav";

interface ShellProps {
  snapshot: Snapshot | null;
  children: React.ReactNode;
}

/**
 * Shell — the outer chrome: gradient-mesh atmosphere + Nav.
 * Client component so Nav can read useSearchParams for mode.
 * Pages are server components; the shell is the only client boundary at root.
 */
export function Shell({ snapshot, children }: ShellProps) {
  // Swap mesh to red tint when health needs attention
  const needsAttention =
    snapshot?.health.markers.some((m) => !m.ok && !m.neutral && !m.autoResolved) ?? false;

  return (
    <div
      style={{
        background: tokens.color.bg,
        minHeight: "100vh",
        fontFamily: tokens.font.body,
        color: tokens.color.text,
        position: "relative",
        overflowX: "hidden",
      }}
    >
      {/* Gradient-mesh atmosphere layer */}
      <div
        aria-hidden
        style={{
          position: "fixed",
          inset: 0,
          pointerEvents: "none",
          zIndex: 0,
          background: meshGradient(needsAttention),
        }}
      />

      {/* Content */}
      <div
        style={{
          position: "relative",
          zIndex: 1,
          maxWidth: 1240,
          margin: "0 auto",
          padding: "22px 22px 60px",
        }}
      >
        <Suspense fallback={null}>
          <Nav snapshot={snapshot} />
        </Suspense>
        {children}
      </div>
    </div>
  );
}
