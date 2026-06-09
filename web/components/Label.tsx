import React from "react";
import { tokens } from "@/lib/tokens";
import { Info } from "./Info";

interface LabelProps {
  children: React.ReactNode;
  termKey?: string;  // glossary key → renders a ? Info badge
  tall?: boolean;
}

/** Section label — uppercase, letter-spaced, muted. Optional ? tooltip. */
export function Label({ children, termKey, tall }: LabelProps) {
  return (
    <div
      style={{
        color: tokens.color.muted,
        fontSize: 11,
        letterSpacing: 2,
        textTransform: "uppercase",
        fontWeight: 700,
        lineHeight: 1.35,
        minHeight: tall ? 32 : undefined,
        marginBottom: tall ? 4 : 0,
        display: "flex",
        alignItems: "center",
        gap: 0,
      }}
    >
      {children}
      {termKey && <Info termKey={termKey} />}
    </div>
  );
}
