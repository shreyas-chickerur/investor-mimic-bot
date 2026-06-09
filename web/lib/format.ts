// format.ts — display formatting helpers used across all pages.

/** Format a dollar amount: $1,234.56 */
export function fmt(n: number): string {
  return "$" + n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

/** Format a dollar amount without cents: $1,234 */
export function fmtK(n: number): string {
  return "$" + n.toLocaleString("en-US", { maximumFractionDigits: 0 });
}

/** Format a percentage: +6.2% or -3.1% */
export function fmtPct(n: number, decimals = 2): string {
  const sign = n >= 0 ? "+" : "";
  return `${sign}${n.toFixed(decimals)}%`;
}

/** Format a number with optional decimals, showing null as "—" */
export function fmtNum(n: number | null | undefined, decimals = 2): string {
  if (n == null) return "—";
  return n.toFixed(decimals);
}

/** Format a dollar P&L with sign: +$612 or -$234 */
export function fmtPnl(n: number): string {
  const sign = n >= 0 ? "+" : "-";
  return `${sign}${fmtK(Math.abs(n))}`;
}

/** ISO date string to relative time: "2h ago", "3d ago", etc. */
export function relativeTime(iso: string): string {
  const delta = Date.now() - new Date(iso).getTime();
  const secs = delta / 1000;
  if (secs < 60) return "just now";
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`;
  if (secs < 86400) return `${Math.floor(secs / 3600)}h ago`;
  return `${Math.floor(secs / 86400)}d ago`;
}

/** Format an ISO date "2026-05-28" to readable "May 28" */
export function fmtDate(iso: string): string {
  return new Date(iso + "T00:00:00Z").toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

/** Format "2026-05" → "May 2026" */
export function fmtMonth(ym: string): string {
  const [year, month] = ym.split("-").map(Number);
  return new Date(year, month - 1).toLocaleDateString("en-US", { month: "short", year: "numeric" });
}

/** Null display with optional tooltip note */
export function nullDisplay(note?: string): string {
  void note;
  return "—";
}
