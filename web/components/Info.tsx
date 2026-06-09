"use client";

/**
 * Info — portaled tooltip popover using @floating-ui/react.
 *
 * Why portaled: the reference's hand-rolled position:fixed tooltip hit repeated
 * stacking-context bugs when cards had transforms or overflow:hidden.  Floating UI
 * renders the popover directly into <body> (outside any card), so it can never be
 * clipped, regardless of where the ? badge sits — even near screen edges or inside
 * an overflow:hidden table cell.
 *
 * Behaviour:
 *   - Opens on hover AND focus (keyboard-accessible).
 *   - Closes on Escape, on blur, and on scroll (via FloatingUI's useDismiss).
 *   - Flips automatically when near the viewport edge (flip middleware).
 *   - Shifts to stay within the viewport on small screens (shift middleware).
 *   - aria-describedby wires the popover content to the trigger for screen readers.
 */

import React, { useId } from "react";
import {
  useFloating,
  useHover,
  useFocus,
  useDismiss,
  useRole,
  useInteractions,
  FloatingPortal,
  offset,
  flip,
  shift,
  arrow,
  autoUpdate,
} from "@floating-ui/react";
import { glossary } from "@/lib/glossary";
import { tokens } from "@/lib/tokens";

interface InfoProps {
  /** Key into the glossary (e.g. "sharpe", "regime") */
  termKey: string;
}

export function Info({ termKey }: InfoProps) {
  const [open, setOpen] = React.useState(false);
  const arrowRef = React.useRef<HTMLDivElement>(null);
  const descId = useId();
  const term = glossary[termKey];

  const { refs, floatingStyles, context, middlewareData, placement } = useFloating({
    open,
    onOpenChange: setOpen,
    placement: "bottom",
    whileElementsMounted: autoUpdate,
    middleware: [
      offset(8),
      flip({ fallbackAxisSideDirection: "start" }),
      shift({ padding: 10 }),
      arrow({ element: arrowRef }),
    ],
  });

  const hover = useHover(context, { move: false });
  const focus = useFocus(context);
  const dismiss = useDismiss(context);
  const role = useRole(context, { role: "tooltip" });

  const { getReferenceProps, getFloatingProps } = useInteractions([hover, focus, dismiss, role]);

  if (!term) return null;

  const arrowX = middlewareData.arrow?.x ?? 0;
  const arrowY = middlewareData.arrow?.y ?? 0;
  const isTop = placement.startsWith("top");
  const arrowSide = isTop ? "bottom" : "top";

  return (
    <>
      {/* ? badge */}
      <span
        ref={refs.setReference}
        {...getReferenceProps()}
        aria-describedby={open ? descId : undefined}
        tabIndex={0}
        role="button"
        aria-label={`Info: ${term.t}`}
        style={{
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          width: 15,
          height: 15,
          boxSizing: "border-box",
          borderRadius: "50%",
          border: `1px solid ${tokens.color.muted}`,
          color: tokens.color.muted,
          fontSize: 9,
          fontWeight: 700,
          cursor: "pointer",
          marginLeft: 5,
          flexShrink: 0,
          verticalAlign: "-0.18em",
          lineHeight: 1,
          fontFamily: tokens.font.body,
          userSelect: "none",
        }}
      >
        ?
      </span>

      {/* Portal popover — rendered directly in <body>, never clipped */}
      {open && (
        <FloatingPortal>
          <div
            ref={refs.setFloating}
            id={descId}
            role="tooltip"
            {...getFloatingProps()}
            style={{
              ...floatingStyles,
              zIndex: 9999,
              width: 256,
              maxWidth: "calc(100vw - 20px)",
              background: "#11141c",
              border: `1px solid ${tokens.color.line}`,
              borderRadius: 12,
              padding: "11px 13px",
              boxShadow: "0 14px 44px -8px #000",
              pointerEvents: "none",
              animation: "popover-in 0.12s ease both",
            }}
          >
            {/* Arrow */}
            <div
              ref={arrowRef}
              style={{
                position: "absolute",
                width: 8,
                height: 8,
                background: "#11141c",
                border: `1px solid ${tokens.color.line}`,
                borderTopRightRadius: 2,
                transform: "rotate(45deg)",
                left: arrowX,
                top: arrowY,
                [arrowSide === "bottom" ? "bottom" : "top"]: -4,
                borderBottomLeftRadius: 2,
                ...(arrowSide === "bottom"
                  ? { borderTop: "none", borderLeft: "none" }
                  : { borderBottom: "none", borderRight: "none" }),
              }}
            />
            <span
              style={{
                color: tokens.color.lime,
                fontSize: 12,
                fontWeight: 700,
                fontFamily: tokens.font.body,
                display: "block",
                marginBottom: 5,
              }}
            >
              {term.t}
            </span>
            <span
              style={{
                color: tokens.color.sec,
                fontSize: 12,
                lineHeight: 1.55,
                fontFamily: tokens.font.body,
              }}
            >
              {term.d}
            </span>
          </div>
        </FloatingPortal>
      )}
    </>
  );
}
