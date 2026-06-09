import React from "react";
import { tokens } from "@/lib/tokens";

interface ChipProps {
  children: React.ReactNode;
  color: string;
  style?: React.CSSProperties;
}

/** Coloured pill badge — uses the token colour for text + transparent background. */
export function Chip({ children, color, style }: ChipProps) {
  return (
    <span
      style={{
        fontFamily: tokens.font.mono,
        fontSize: 11,
        fontWeight: 700,
        color,
        background: `${color}1a`,
        border: `1px solid ${color}44`,
        padding: "3px 9px",
        borderRadius: tokens.radius.chip,
        whiteSpace: "nowrap",
        ...style,
      }}
    >
      {children}
    </span>
  );
}
