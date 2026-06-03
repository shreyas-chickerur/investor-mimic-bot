// ============================================================
// design-tokens.ts — the visual system (matches MimicDashboard.jsx)
// Use these EXACT values. Expose as CSS variables in globals.css AND
// as a TS object for inline/Recharts usage. Do not invent new colors.
// ============================================================

export const tokens = {
  color: {
    bg: "#08090d",            // page background (OLED near-black)
    panel: "#0e1118",         // card background (opaque — see note)
    panel2: "#0a1119",        // inset/nested panel
    glass2: "rgba(255,255,255,0.02)",
    line: "rgba(255,255,255,0.08)",   // borders / dividers
    line2: "rgba(255,255,255,0.05)",
    text: "#f0f2f5",          // primary
    sec: "#aab3c0",           // secondary
    muted: "#6b7585",         // labels / muted
    // accent + categorical series (use in this order for strategies/series)
    lime: "#d4ff3f",          // primary accent / hero
    cyan: "#4dd0ff",
    mag: "#ff5da2",
    amber: "#ffb84d",
    violet: "#b794ff",
    // semantic
    green: "#5fe39a",         // positive P&L, bullish
    red: "#ff6b7d",           // negative P&L, bearish
  },
  font: {
    display: "'Bricolage Grotesque','Manrope',system-ui,sans-serif", // headings, big titles
    body: "'Manrope',system-ui,sans-serif",                          // UI text
    mono: "'JetBrains Mono','SF Mono',ui-monospace,monospace",       // ALL numbers/data
  },
  radius: { card: 20, panel: 16, chip: 7, pill: 999 },
  // self-host these via next/font (Google) — do NOT @import at runtime
  fonts_to_selfhost: ["Bricolage Grotesque", "Manrope", "JetBrains Mono"],
} as const;

// Semantic helpers (port from the artifact):
//   sentimentColor(s): s>=0.62 -> green, s<=0.38 -> red, else amber
//   plColor(n): n>=0 -> green else red
//   healthChip(score): >=80 green, 60–79 amber, <60 red
//
// Aesthetic rules (from the artifact, keep them):
// - Page has a gradient-mesh atmosphere:
//   radial-gradient(700px 400px at 12% -5%, lime14, transparent 60%),
//   radial-gradient(600px 500px at 95% 0%, cyan12, transparent 55%),
//   radial-gradient(800px 600px at 60% 110%, mag0e, transparent 60%)
//   (in the needs-attention health state, swap the inner of the first to a red tint)
// - Cards: panel bg, 1px line border, radius 20, with GAPS between them (never flush).
// - Glow on hero/selected cards: boxShadow 0 0 40px -12px <accent>55
// - Numbers ALWAYS mono; labels uppercase letterSpacing 2; pills rounded.
// - Active nav tab: lime background, dark text, lime glow.
// - Subtle entrance: fade/slide is fine HERE because production tooltips use a
//   portal (see prompt) and won't be trapped by animation stacking contexts.
