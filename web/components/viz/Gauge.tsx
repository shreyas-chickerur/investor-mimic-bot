"use client";

import React from "react";
import { tokens } from "@/lib/tokens";

const S = tokens.color;

/**
 * Animated circular gauge. The arc sweeps to `value/max` as `p` goes 0→1 and
 * the centre figure counts up in lock-step. Used for the strategy health ring.
 */
export function Gauge({
  value,
  max = 100,
  p,
  color,
  size = 104,
  stroke = 9,
  label,
  sub,
}: {
  value: number;
  max?: number;
  p: number;
  color: string;
  size?: number;
  stroke?: number;
  label?: string;
  sub?: string;
}) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const frac = Math.max(0, Math.min(1, value / max));
  const offset = c * (1 - frac * p);
  const shown = Math.round(value * p);

  return (
    <div style={{ position: "relative", width: size, height: size, flexShrink: 0 }}>
      <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={S.line} strokeWidth={stroke} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={offset}
          style={{ filter: `drop-shadow(0 0 6px ${color}88)` }}
        />
      </svg>
      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <span style={{ fontFamily: tokens.font.mono, fontSize: 22, fontWeight: 700, color, lineHeight: 1 }}>
          {shown}
        </span>
        {label && <span style={{ fontSize: 9.5, color: S.muted, marginTop: 3, letterSpacing: "0.06em" }}>{label}</span>}
        {sub && <span style={{ fontSize: 9, color: S.sec, marginTop: 1 }}>{sub}</span>}
      </div>
    </div>
  );
}
