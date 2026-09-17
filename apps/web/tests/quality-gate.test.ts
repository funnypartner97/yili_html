import { describe, expect, it } from "vitest";

import {
  ALL_VIEWPORTS, AMBIGUOUS_OVERFLOW_PX, CANONICAL_VIEWPORT, MINIMUM_CONTRAST,
  contrastDiagnostic, contrastRatio, expectedMotionState, geometryDiagnostics, parseColor,
} from "../lib/quality/browser-validator";
import { presentationScale } from "../components/presentation/presentationScale";

describe("color and contrast", () => {
  it("parses hex, rgb, and rgba colors", () => {
    expect(parseColor("#fff")).toEqual({ r: 255, g: 255, b: 255 });
    expect(parseColor("#1d1d1f")).toEqual({ r: 29, g: 29, b: 31 });
    expect(parseColor("rgb(10, 20, 30)")).toEqual({ r: 10, g: 20, b: 30 });
    expect(parseColor("rgba(10, 20, 30, 0.5)")).toEqual({ r: 10, g: 20, b: 30 });
    expect(parseColor("not-a-color")).toBeNull();
  });

  it("computes the WCAG contrast ratio", () => {
    expect(contrastRatio("#000000", "#ffffff")).toBeCloseTo(21, 1);
    expect(contrastRatio("#777777", "#888888")!).toBeLessThan(MINIMUM_CONTRAST);
    expect(contrastRatio("bogus", "#ffffff")).toBeNull();
  });

  it("flags insufficient contrast as an accessibility error", () => {
    expect(contrastDiagnostic("node-1", "#000000", "#ffffff")).toBeNull();
    const diagnostic = contrastDiagnostic("node-1", "#777777", "#888888");
    expect(diagnostic?.code).toBe("insufficient_contrast");
    expect(diagnostic?.layer).toBe("accessibility");
    expect(diagnostic?.severity).toBe("error");
  });
});

describe("geometry classification", () => {
  it("turns real overflow into an error and marginal overflow into a review", () => {
    const hard = geometryDiagnostics({ nodeId: "n", overflowPx: AMBIGUOUS_OVERFLOW_PX + 10 });
    expect(hard[0].code).toBe("content_clipped");
    expect(hard[0].severity).toBe("error");

    const ambiguous = geometryDiagnostics({ nodeId: "n", overflowPx: 1 });
    expect(ambiguous[0].code).toBe("content_clipped_ambiguous");
    expect(ambiguous[0].severity).toBe("review");
  });

  it("reports overlap, safe-area intrusion, and small fonts with repairs", () => {
    const diagnostics = geometryDiagnostics({
      nodeId: "slide-1", overlapsNeighbour: true, intrudesSafeArea: true, fontSizePx: 12,
    });
    const codes = diagnostics.map((item) => item.code);
    expect(codes).toContain("bounding_box_overlap");
    expect(codes).toContain("safe_area_intrusion");
    expect(codes).toContain("font_below_minimum");
    expect(diagnostics.find((item) => item.code === "bounding_box_overlap")?.repair)
      .toEqual({ command: "splitSlide", layoutId: "title-media" });
  });

  it("produces no diagnostics for clean geometry", () => {
    expect(geometryDiagnostics({ nodeId: "n", overflowPx: 0, fontSizePx: 28 })).toEqual([]);
  });
});

describe("motion state", () => {
  it("animates only declared entries when motion is allowed", () => {
    expect(expectedMotionState({ targetId: "t", exportState: "animated" }, false)).toBe("animated");
    expect(expectedMotionState({ targetId: "t", exportState: "animated" }, true)).toBe("final");
    expect(expectedMotionState({ targetId: "t", exportState: "static" }, false)).toBe("final");
  });
});

describe("viewport coverage", () => {
  it("measures the canonical stage plus representative viewports at one uniform scale", () => {
    expect(ALL_VIEWPORTS.map((viewport) => viewport.name)).toEqual(["stage", "16:9", "16:10", "narrow"]);
    expect(presentationScale(CANONICAL_VIEWPORT)).toBe(1);
    for (const viewport of ALL_VIEWPORTS) {
      expect(presentationScale(viewport)).toBeGreaterThan(0);
    }
  });
});
