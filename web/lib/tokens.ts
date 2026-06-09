// tokens.ts — exact values from design-tokens.ts reference. Do not modify.
export const tokens = {
  color: {
    bg: "#08090d",
    panel: "#0e1118",
    panel2: "#0a1119",
    glass2: "rgba(255,255,255,0.02)",
    line: "rgba(255,255,255,0.08)",
    line2: "rgba(255,255,255,0.05)",
    text: "#f0f2f5",
    sec: "#aab3c0",
    muted: "#6b7585",
    lime: "#d4ff3f",
    cyan: "#4dd0ff",
    mag: "#ff5da2",
    amber: "#ffb84d",
    violet: "#b794ff",
    green: "#5fe39a",
    red: "#ff6b7d",
  },
  font: {
    display: "'Bricolage Grotesque','Manrope',system-ui,sans-serif",
    body: "'Manrope',system-ui,sans-serif",
    mono: "'JetBrains Mono','SF Mono',ui-monospace,monospace",
  },
  radius: { card: 20, panel: 16, chip: 7, pill: 999 },
} as const;

export type TokenColor = keyof typeof tokens.color;

// Categorical series colors in order (use for strategies/chart series)
export const SERIES_COLORS = [
  tokens.color.lime,
  tokens.color.cyan,
  tokens.color.mag,
  tokens.color.amber,
  tokens.color.violet,
  tokens.color.green,
  tokens.color.red,
];

// Semantic helpers
export function sentimentColor(score: number): string {
  if (score >= 0.62) return tokens.color.green;
  if (score <= 0.38) return tokens.color.red;
  return tokens.color.amber;
}

export function plColor(n: number): string {
  return n >= 0 ? tokens.color.green : tokens.color.red;
}

export function healthChipColor(score: number): string {
  if (score >= 80) return tokens.color.green;
  if (score >= 60) return tokens.color.amber;
  return tokens.color.red;
}

// Gradient mesh atmosphere (matches reference exactly)
// In needs-attention state swap the first inner stop to a red tint.
export function meshGradient(needsAttention = false): string {
  const inner = needsAttention ? "#2b1313" : "#131b2b";
  return [
    `radial-gradient(700px 400px at 12% -5%, ${tokens.color.lime}14, transparent 60%)`,
    `radial-gradient(600px 500px at 95% 0%, ${tokens.color.cyan}12, transparent 55%)`,
    `radial-gradient(800px 600px at 60% 110%, ${tokens.color.mag}0e, transparent 60%)`,
  ].join(", ");
}
