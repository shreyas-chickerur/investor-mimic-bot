// Shared Recharts tooltip contentStyle — matches the dark reference exactly.
import { tokens } from "@/lib/tokens";

export const TOOLTIP_STYLE = {
  background: "#0d1018",
  border: `1px solid ${tokens.color.line}`,
  borderRadius: 10,
  color: tokens.color.text,
  fontFamily: tokens.font.mono,
  fontSize: 12,
} as const;
