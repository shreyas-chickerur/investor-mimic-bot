// snapshot.ts — ISR fetch + runtime validation of latest.json.
// Returns null when the data branch hasn't been published yet (404)
// or when the snapshot fails basic schema checks.
// The app renders a clean "Awaiting first snapshot" state on null.

import type { Snapshot } from "./types";

// The snapshot is published to the data branch by the GHA export step.
// Never hardcode secrets here — this is a public raw GitHub URL.
const SNAPSHOT_URL =
  process.env.NEXT_PUBLIC_SNAPSHOT_URL ??
  `https://raw.githubusercontent.com/${
    process.env.NEXT_PUBLIC_GH_REPO ?? "shreyas-chickerur/investor-mimic-bot"
  }/data/web/public/data/latest.json`;

// ISR: revalidate every 3600s (1 hour).
// real freshness = ~1h 5min (raw.githubusercontent.com CDN caches ~5min).
export const REVALIDATE_SECONDS = 3600;

export async function getSnapshot(): Promise<Snapshot | null> {
  let res: Response;
  try {
    res = await fetch(SNAPSHOT_URL, {
      next: { revalidate: REVALIDATE_SECONDS },
      // cache: 'no-store'  ← do NOT use this; it breaks ISR
    });
  } catch {
    // Network failure — return null so the app shows the "no data" state
    console.error("[snapshot] fetch error — network unavailable");
    return null;
  }

  if (!res.ok) {
    if (res.status === 404) {
      // Expected during initial deploy before the first GHA run.
      console.info("[snapshot] 404 — data branch not yet published");
    } else {
      console.error(`[snapshot] unexpected HTTP ${res.status}`);
    }
    return null;
  }

  let raw: unknown;
  try {
    raw = await res.json();
  } catch {
    console.error("[snapshot] JSON parse error");
    return null;
  }

  // Minimal runtime validation (full schema is enforced server-side by validate_snapshot.py)
  if (!isValidSnapshot(raw)) {
    console.error("[snapshot] schema check failed");
    return null;
  }

  return raw as Snapshot;
}

function isValidSnapshot(v: unknown): v is Snapshot {
  if (!v || typeof v !== "object") return false;
  const s = v as Record<string, unknown>;
  return (
    typeof s.meta === "object" &&
    s.meta !== null &&
    (s.meta as Record<string, unknown>).schemaVersion === 1 &&
    typeof s.portfolio === "object" &&
    Array.isArray(s.equityCurve) &&
    Array.isArray(s.strategies) &&
    Array.isArray(s.positions) &&
    Array.isArray(s.trades) &&
    typeof s.signals === "object" &&
    typeof s.analytics === "object" &&
    typeof s.health === "object"
  );
}

// ─── Local dev helper ────────────────────────────────────────────────────────
// When running `make web-mock` + `npm run dev`, serve mock data from the local
// file instead of fetching GitHub. Set NEXT_PUBLIC_SNAPSHOT_URL=local to enable.
// The mock file lives at web/public/data/mock/latest.json (isolated from real history).
