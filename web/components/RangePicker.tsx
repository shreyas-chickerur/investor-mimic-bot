"use client";
import { tokens } from "@/lib/tokens";

export const RANGES = { "1W": 5, "1M": 21, "3M": 63, YTD: 145, ALL: 252 } as const;
export type RangeKey = keyof typeof RANGES;

interface RangePickerProps {
  range: RangeKey;
  onChange: (r: RangeKey) => void;
}

export function RangePicker({ range, onChange }: RangePickerProps) {
  return (
    <div style={{ display: "flex", gap: 4 }}>
      {(Object.keys(RANGES) as RangeKey[]).map((r) => {
        const active = range === r;
        return (
          <button
            key={r}
            onClick={() => onChange(r)}
            style={{
              cursor: "pointer",
              fontFamily: tokens.font.mono,
              fontSize: 11,
              fontWeight: 700,
              padding: "4px 9px",
              borderRadius: tokens.radius.chip,
              color: active ? tokens.color.bg : tokens.color.muted,
              background: active ? tokens.color.lime : "transparent",
              border: `1px solid ${active ? tokens.color.lime : tokens.color.line}`,
              transition: "all .15s",
            }}
          >
            {r}
          </button>
        );
      })}
    </div>
  );
}
