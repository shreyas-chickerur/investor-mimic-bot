import React from "react";
import { tokens } from "@/lib/tokens";

interface PanelProps {
  children: React.ReactNode;
  glow?: string;        // accent colour hex for the box-shadow glow
  pad?: number;
  style?: React.CSSProperties;
  className?: string;
}

/** Card panel — panel bg, 1px border, radius 20, optional accent glow. */
export function Panel({ children, glow, pad = 22, style, className }: PanelProps) {
  return (
    <div
      className={className}
      style={{
        background: tokens.color.panel,
        border: `1px solid ${glow ? `${glow}66` : tokens.color.line}`,
        borderRadius: tokens.radius.card,
        padding: pad,
        boxShadow: glow ? `0 0 40px -12px ${glow}55` : "none",
        ...style,
      }}
    >
      {children}
    </div>
  );
}
