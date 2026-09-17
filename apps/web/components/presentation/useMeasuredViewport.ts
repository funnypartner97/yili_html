"use client";

import { useEffect, useRef, useState } from "react";

import type { Viewport } from "./presentationScale";

const FALLBACK: Viewport = { width: 1280, height: 720 };

/**
 * Measures an element and reports the viewport available to the fixed stage.
 * Falls back to a 16:9 default before the first layout pass (and in jsdom, which
 * reports zero sizes) so the uniform scale is always well defined.
 */
export function useMeasuredViewport<T extends HTMLElement>(): {
  ref: React.RefObject<T | null>;
  viewport: Viewport;
} {
  const ref = useRef<T | null>(null);
  const [viewport, setViewport] = useState<Viewport>(FALLBACK);

  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    const measure = () => {
      const rect = element.getBoundingClientRect();
      if (rect.width > 0 && rect.height > 0) {
        setViewport({ width: rect.width, height: rect.height });
      }
    };
    measure();
    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  return { ref, viewport };
}
