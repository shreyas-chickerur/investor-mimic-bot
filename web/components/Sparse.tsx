/**
 * Sparse — intentional empty/awaiting states for charts and null metrics.
 * These look honest and designed, not broken.
 */
import { tokens } from "@/lib/tokens";
import { Info } from "./Info";

/** For a null metric (Sharpe, win rate) — shows "—" with a tooltip explaining why */
interface NullMetricProps {
  /** Glossary key for the ? tooltip */
  termKey?: string;
  /** e.g. "Available after 20 closed trades — 19 so far" */
  note?: string;
}

export function NullMetric({ termKey, note }: NullMetricProps) {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        fontFamily: tokens.font.mono,
        fontSize: 24,
        fontWeight: 700,
        color: tokens.color.muted,
      }}
      title={note}
      aria-label={note ?? "Not yet available"}
    >
      —{termKey && <Info termKey={termKey} />}
    </span>
  );
}

/** For a chart that doesn't have enough data yet */
interface SparseChartProps {
  message?: string;
  height?: number;
}

export function SparseChart({
  message = "Not enough history yet — updates daily",
  height = 180,
}: SparseChartProps) {
  return (
    <div
      style={{
        height,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 8,
        border: `1px dashed ${tokens.color.line}`,
        borderRadius: 10,
        color: tokens.color.muted,
        fontSize: 13,
        textAlign: "center",
        padding: "0 24px",
      }}
      aria-label={message}
    >
      <span style={{ fontSize: 20, opacity: 0.5 }}>∿</span>
      <span style={{ lineHeight: 1.5 }}>{message}</span>
    </div>
  );
}

/** Empty list / table state */
export function EmptyState({ message }: { message: string }) {
  return (
    <div
      style={{
        padding: "32px 24px",
        textAlign: "center",
        color: tokens.color.muted,
        fontSize: 13,
        fontStyle: "italic",
      }}
    >
      {message}
    </div>
  );
}
