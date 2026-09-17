/**
 * Browser geometry and accessibility gate helpers.
 *
 * The pure functions here (color/contrast math, geometry classification, motion
 * state) are unit-tested without a browser. The `measure*` runners drive a pinned
 * Chromium through Playwright at the canonical 1920×1080 stage plus representative
 * 16:9, 16:10, and narrow viewports, and turn ambiguous geometry into `review`
 * diagnostics instead of silently passing.
 *
 * Playwright is imported as a type only, so importing this module never loads the
 * browser runtime; the runners receive an already-created page.
 */
import type { Page } from "@playwright/test";

import { STAGE_HEIGHT, STAGE_WIDTH, presentationScale } from "../../components/presentation/presentationScale";

export type Severity = "error" | "warning" | "review";

export interface GateDiagnostic {
  code: string;
  severity: Severity;
  layer: "render" | "accessibility";
  nodeId: string;
  message: string;
  measurements: Record<string, unknown>;
  constraint: string;
  repair: Record<string, unknown> | null;
}

export const CANONICAL_VIEWPORT = { name: "stage", width: STAGE_WIDTH, height: STAGE_HEIGHT };
export const REPRESENTATIVE_VIEWPORTS = [
  { name: "16:9", width: 1280, height: 720 },
  { name: "16:10", width: 1440, height: 900 },
  { name: "narrow", width: 390, height: 844 },
];
export const ALL_VIEWPORTS = [CANONICAL_VIEWPORT, ...REPRESENTATIVE_VIEWPORTS];

/** Registry safe area for the core layouts (top/right/bottom/left, logical px). */
export const SAFE_AREA = { top: 48, right: 48, bottom: 72, left: 48 };
export const MINIMUM_FONT_SIZE_PX = 24;
export const MINIMUM_CONTRAST = 4.5;
/** Below this many logical px of overflow we treat geometry as ambiguous (review). */
export const AMBIGUOUS_OVERFLOW_PX = 2;

export interface RGB { r: number; g: number; b: number }

export function parseColor(input: string): RGB | null {
  const value = input.trim().toLowerCase();
  const hex = /^#([0-9a-f]{3}|[0-9a-f]{6})$/.exec(value);
  if (hex) {
    let body = hex[1];
    if (body.length === 3) body = body.split("").map((c) => c + c).join("");
    return {
      r: parseInt(body.slice(0, 2), 16),
      g: parseInt(body.slice(2, 4), 16),
      b: parseInt(body.slice(4, 6), 16),
    };
  }
  const rgb = /rgba?\(([^)]+)\)/.exec(value);
  if (rgb) {
    const parts = rgb[1].split(/[\s,/]+/).filter(Boolean).map(Number);
    if (parts.length >= 3 && parts.slice(0, 3).every((n) => Number.isFinite(n))) {
      return { r: parts[0], g: parts[1], b: parts[2] };
    }
  }
  return null;
}

function channel(value: number): number {
  const s = value / 255;
  return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
}

export function relativeLuminance({ r, g, b }: RGB): number {
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}

export function contrastRatio(foreground: string, background: string): number | null {
  const fg = parseColor(foreground);
  const bg = parseColor(background);
  if (!fg || !bg) return null;
  const l1 = relativeLuminance(fg);
  const l2 = relativeLuminance(bg);
  const lighter = Math.max(l1, l2);
  const darker = Math.min(l1, l2);
  return (lighter + 0.05) / (darker + 0.05);
}

export function contrastDiagnostic(
  nodeId: string, foreground: string, background: string, minimum = MINIMUM_CONTRAST,
): GateDiagnostic | null {
  const ratio = contrastRatio(foreground, background);
  if (ratio === null || ratio >= minimum) return null;
  return {
    code: "insufficient_contrast", severity: "error", layer: "accessibility", nodeId,
    message: `对比度 ${ratio.toFixed(2)} 低于最低要求 ${minimum}。`,
    measurements: { ratio: Number(ratio.toFixed(3)), minimum },
    constraint: "core-presentation-layouts.json#accessibility.minimumContrast",
    repair: { command: "replaceLayout", nodeId },
  };
}

export interface GeometryInput {
  nodeId: string;
  /** Logical px of content overflowing its slot box (0 when it fits). */
  overflowPx?: number;
  overlapsNeighbour?: boolean;
  intrudesSafeArea?: boolean;
  fontSizePx?: number;
  imageCropped?: boolean;
}

/**
 * Classifies measured geometry into stable diagnostics. Marginal overflow within
 * `AMBIGUOUS_OVERFLOW_PX` becomes a `review` diagnostic rather than a hard error,
 * so an ambiguous measurement is never silently passed.
 */
export function geometryDiagnostics(input: GeometryInput): GateDiagnostic[] {
  const diagnostics: GateDiagnostic[] = [];
  const overflow = input.overflowPx ?? 0;
  if (overflow > AMBIGUOUS_OVERFLOW_PX) {
    diagnostics.push({
      code: "content_clipped", severity: "error", layer: "render", nodeId: input.nodeId,
      message: `内容溢出槽位 ${Math.round(overflow)} 逻辑像素。`,
      measurements: { overflowPx: overflow, allowed: 0 },
      constraint: "slot box", repair: { command: "truncateToCapacity", nodeId: input.nodeId },
    });
  } else if (overflow > 0) {
    diagnostics.push({
      code: "content_clipped_ambiguous", severity: "review", layer: "render", nodeId: input.nodeId,
      message: `内容可能轻微溢出（${overflow.toFixed(1)} 逻辑像素），需人工确认。`,
      measurements: { overflowPx: overflow, tolerance: AMBIGUOUS_OVERFLOW_PX },
      constraint: "slot box", repair: { command: "truncateToCapacity", nodeId: input.nodeId },
    });
  }
  if (input.overlapsNeighbour) {
    diagnostics.push({
      code: "bounding_box_overlap", severity: "error", layer: "render", nodeId: input.nodeId,
      message: "相邻内容包围盒发生重叠。", measurements: { overlaps: true },
      constraint: "slot separation", repair: { command: "splitSlide", layoutId: "title-media" },
    });
  }
  if (input.intrudesSafeArea) {
    diagnostics.push({
      code: "safe_area_intrusion", severity: "error", layer: "render", nodeId: input.nodeId,
      message: "内容侵入版式安全区。", measurements: { safeArea: SAFE_AREA },
      constraint: "core-presentation-layouts.json#safeArea",
      repair: { command: "replaceLayout", layoutId: "title-body" },
    });
  }
  if (input.fontSizePx !== undefined && input.fontSizePx < MINIMUM_FONT_SIZE_PX) {
    diagnostics.push({
      code: "font_below_minimum", severity: "error", layer: "accessibility", nodeId: input.nodeId,
      message: `字号 ${input.fontSizePx}px 低于最小值 ${MINIMUM_FONT_SIZE_PX}px。`,
      measurements: { fontSizePx: input.fontSizePx, minimum: MINIMUM_FONT_SIZE_PX },
      constraint: "core-presentation-layouts.json#minimumFontSize",
      repair: { command: "truncateToCapacity", nodeId: input.nodeId },
    });
  }
  if (input.imageCropped) {
    diagnostics.push({
      code: "image_crop_out_of_bounds", severity: "review", layer: "render", nodeId: input.nodeId,
      message: "图片裁剪可能超出主体安全区，需人工确认。", measurements: { cropped: true },
      constraint: "presentation.schema.json#MediaIntent.subjectSafeArea",
      repair: { command: "replaceLayout", nodeId: input.nodeId },
    });
  }
  return diagnostics;
}

export interface AnimationEntryView {
  targetId: string;
  exportState: "animated" | "static" | "omitted";
}

/**
 * The expected final state for each declared animation target. Under reduced
 * motion (or a non-animated export state) every target must already be at its
 * stable final state, which the browser check asserts.
 */
export function expectedMotionState(
  entry: AnimationEntryView, reducedMotion: boolean,
): "animated" | "final" {
  return entry.exportState === "animated" && !reducedMotion ? "animated" : "final";
}

/**
 * Drives a page through every viewport, measuring the fixed stage and the reading
 * view. Returns render/accessibility diagnostics. Requires a running export or
 * editor page; not exercised in unit tests.
 */
export async function measurePresentation(
  page: Page, url: string, nodeSelector: string,
): Promise<GateDiagnostic[]> {
  const diagnostics: GateDiagnostic[] = [];
  for (const viewport of ALL_VIEWPORTS) {
    await page.setViewportSize({ width: viewport.width, height: viewport.height });
    await page.goto(url);
    const scale = presentationScale({ width: viewport.width, height: viewport.height });
    const measured = await page.evaluate((selector) => {
      const nodes = Array.from(document.querySelectorAll<HTMLElement>(selector));
      return nodes.map((node) => {
        const box = node.getBoundingClientRect();
        const parent = node.parentElement?.getBoundingClientRect();
        const style = window.getComputedStyle(node);
        return {
          id: node.dataset.blockId ?? node.id ?? selector,
          overflowPx: parent ? Math.max(0, box.bottom - parent.bottom) : 0,
          fontSizePx: parseFloat(style.fontSize) || 0,
        };
      });
    }, nodeSelector);
    for (const node of measured) {
      // Overflow is measured on the scaled stage; convert back to logical pixels.
      diagnostics.push(...geometryDiagnostics({
        nodeId: node.id,
        overflowPx: scale > 0 ? node.overflowPx / scale : node.overflowPx,
        fontSizePx: scale > 0 ? node.fontSizePx / scale : node.fontSizePx,
      }));
    }
  }
  return diagnostics;
}
