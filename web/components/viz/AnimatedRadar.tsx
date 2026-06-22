"use client";

import React from "react";
import { tokens } from "@/lib/tokens";

const S = tokens.color;

type Factors = {
  momentum: number;
  quality: number;
  reversion: number;
  volume: number;
  volatility: number;
};

const AXES: { key: keyof Factors; label: string }[] = [
  { key: "momentum", label: "Momentum" },
  { key: "quality", label: "Quality" },
  { key: "reversion", label: "Reversion" },
  { key: "volume", label: "Volume" },
  { key: "volatility", label: "Vol" },
];

/**
 * Bespoke SVG factor radar with a continuously rotating "radar sweep", a
 * draw-in data polygon (driven by `p`: 0→1) and a soft glow. Custom SVG (not
 * recharts) so the reveal and sweep are fully controllable.
 */
export function AnimatedRadar({
  factors,
  color,
  p,
  size = 188,
  dim = false,
}: {
  factors: Factors;
  color: string;
  p: number;
  size?: number;
  dim?: boolean;
}) {
  const cx = size / 2;
  const cy = size / 2;
  const R = size / 2 - 26; // leave room for labels
  const n = AXES.length;
  const uid = React.useId().replace(/[:]/g, "");

  const angleFor = (i: number) => (-90 + (360 / n) * i) * (Math.PI / 180);
  const pointAt = (i: number, frac: number) => {
    const a = angleFor(i);
    return [cx + R * frac * Math.cos(a), cy + R * frac * Math.sin(a)] as const;
  };

  // Grid rings (concentric pentagons).
  const rings = [0.25, 0.5, 0.75, 1].map((frac) =>
    AXES.map((_, i) => pointAt(i, frac).join(",")).join(" "),
  );

  // Data polygon, grown from centre by p.
  const dataPts = AXES.map(({ key }, i) => {
    const v = Math.max(0, Math.min(100, factors[key])) / 100;
    return pointAt(i, v * p);
  });
  const dataPoly = dataPts.map((pt) => pt.join(",")).join(" ");

  return (
    <svg
      viewBox={`0 0 ${size} ${size}`}
      width="100%"
      height={size}
      style={{ display: "block", overflow: "visible", opacity: dim ? 0.55 : 1 }}
      role="img"
      aria-label="Factor profile radar"
    >
      <defs>
        <radialGradient id={`fill-${uid}`} cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor={color} stopOpacity={0.45} />
          <stop offset="100%" stopColor={color} stopOpacity={0.08} />
        </radialGradient>
        <linearGradient id={`sweep-${uid}`} x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor={color} stopOpacity={0} />
          <stop offset="100%" stopColor={color} stopOpacity={0.32} />
        </linearGradient>
        <filter id={`glow-${uid}`} x="-40%" y="-40%" width="180%" height="180%">
          <feGaussianBlur stdDeviation="3.2" result="b" />
          <feMerge>
            <feMergeNode in="b" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      {/* Grid rings */}
      {rings.map((pts, i) => (
        <polygon
          key={i}
          points={pts}
          fill="none"
          stroke={S.line}
          strokeWidth={1}
          opacity={i === rings.length - 1 ? 0.9 : 0.5}
        />
      ))}

      {/* Spokes */}
      {AXES.map((_, i) => {
        const [x, y] = pointAt(i, 1);
        return <line key={i} x1={cx} y1={cy} x2={x} y2={y} stroke={S.line} strokeWidth={1} opacity={0.5} />;
      })}

      {/* Rotating radar sweep wedge */}
      <g
        className="radar-sweep"
        style={{ transformOrigin: `${cx}px ${cy}px` }}
      >
        <path
          d={`M ${cx} ${cy} L ${cx + R} ${cy} A ${R} ${R} 0 0 0 ${
            cx + R * Math.cos(-0.7)
          } ${cy + R * Math.sin(-0.7)} Z`}
          fill={`url(#sweep-${uid})`}
        />
        <line x1={cx} y1={cy} x2={cx + R} y2={cy} stroke={color} strokeWidth={1.5} opacity={0.7} />
      </g>

      {/* Data polygon */}
      <polygon
        points={dataPoly}
        fill={`url(#fill-${uid})`}
        stroke={color}
        strokeWidth={2}
        strokeLinejoin="round"
        filter={`url(#glow-${uid})`}
      />

      {/* Vertices */}
      {dataPts.map(([x, y], i) => (
        <circle key={i} cx={x} cy={y} r={p > 0.85 ? 3 : 0} fill={color} style={{ transition: "r 0.3s ease" }} />
      ))}

      {/* Axis labels */}
      {AXES.map(({ label }, i) => {
        const [x, y] = pointAt(i, 1.2);
        const a = angleFor(i);
        const cos = Math.cos(a);
        const anchor = cos > 0.3 ? "start" : cos < -0.3 ? "end" : "middle";
        return (
          <text
            key={i}
            x={x}
            y={y + 3}
            textAnchor={anchor}
            style={{ fill: S.muted, fontSize: 10, fontWeight: 600 }}
          >
            {label}
          </text>
        );
      })}
    </svg>
  );
}
