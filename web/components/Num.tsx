import React from "react";
import { tokens } from "@/lib/tokens";

interface NumProps {
  children: React.ReactNode;
  size?: number;
  color?: string;
}

/** Large mono number display — all data numbers use this. */
export function Num({ children, size = 26, color = tokens.color.text }: NumProps) {
  return (
    <div
      style={{
        fontFamily: tokens.font.mono,
        fontSize: size,
        fontWeight: 700,
        color,
        letterSpacing: -0.5,
        lineHeight: 1.1,
      }}
    >
      {children}
    </div>
  );
}
