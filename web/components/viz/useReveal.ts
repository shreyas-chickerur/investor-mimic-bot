"use client";

import { useEffect, useRef, useState } from "react";

function prefersReducedMotion(): boolean {
  if (typeof window === "undefined" || !window.matchMedia) return false;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/**
 * Returns [ref, inView] — inView flips true (once) when the element scrolls
 * into the viewport. SSR/no-IO environments report inView immediately so the
 * content is never hidden.
 */
export function useInView<T extends HTMLElement = HTMLDivElement>(threshold = 0.2) {
  const ref = useRef<T>(null);
  const [inView, setInView] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (typeof IntersectionObserver === "undefined") {
      setInView(true);
      return;
    }
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setInView(true);
          io.disconnect();
        }
      },
      { threshold },
    );
    io.observe(el);
    // Safety net: some environments (headless capture, certain embeds) never
    // deliver an IO callback. Reveal anyway after a short grace period so a
    // card can never stay stuck at its empty (p=0) state.
    const fallback = window.setTimeout(() => setInView(true), 1200);
    return () => {
      io.disconnect();
      window.clearTimeout(fallback);
    };
  }, [threshold]);

  return [ref, inView] as const;
}

/**
 * Eased 0→1 progress that ramps once `run` is true. Drives every animated
 * sub-visual in a card from a single clock so the radar, gauges and counters
 * move in sync. Honours prefers-reduced-motion by snapping to 1.
 */
export function useProgress(run: boolean, duration = 1100, delay = 0): number {
  const [p, setP] = useState(0);

  useEffect(() => {
    if (!run) return;
    if (prefersReducedMotion()) {
      setP(1);
      return;
    }
    let raf = 0;
    let startTs = 0;
    const tick = (now: number) => {
      if (!startTs) startTs = now;
      const elapsed = now - startTs - delay;
      if (elapsed < 0) {
        raf = requestAnimationFrame(tick);
        return;
      }
      const t = Math.min(1, elapsed / duration);
      // easeOutCubic
      setP(1 - Math.pow(1 - t, 3));
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [run, duration, delay]);

  return p;
}
