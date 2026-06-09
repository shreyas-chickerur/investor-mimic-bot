/**
 * AwaitingSnapshot — shown when latest.json is unavailable (404 or network error).
 * This is the expected state between initial Vercel deploy and the first GHA run.
 * Must look intentional, not broken.
 */
import { tokens } from "@/lib/tokens";

export function AwaitingSnapshot() {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "40vh",
        gap: 16,
        textAlign: "center",
        padding: "48px 24px",
      }}
    >
      {/* Pulsing logo */}
      <div
        style={{
          width: 56,
          height: 56,
          borderRadius: "50%",
          background: `${tokens.color.lime}18`,
          border: `2px solid ${tokens.color.lime}44`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 24,
        }}
      >
        ◆
      </div>
      <div
        style={{
          fontFamily: tokens.font.display,
          fontWeight: 700,
          fontSize: 20,
          color: tokens.color.text,
        }}
      >
        Awaiting first snapshot
      </div>
      <div
        style={{
          fontSize: 14,
          color: tokens.color.sec,
          maxWidth: 420,
          lineHeight: 1.65,
        }}
      >
        The trading system runs daily via GitHub Actions. The dashboard will populate
        automatically after the first run exports a snapshot.
        <br />
        <br />
        If this persists after a run, check that the{" "}
        <code
          style={{
            fontFamily: tokens.font.mono,
            fontSize: 12,
            background: tokens.color.panel2,
            padding: "2px 6px",
            borderRadius: 4,
          }}
        >
          data
        </code>{" "}
        branch exists and{" "}
        <code
          style={{
            fontFamily: tokens.font.mono,
            fontSize: 12,
            background: tokens.color.panel2,
            padding: "2px 6px",
            borderRadius: 4,
          }}
        >
          NEXT_PUBLIC_SNAPSHOT_URL
        </code>{" "}
        points to it.
      </div>
    </div>
  );
}
