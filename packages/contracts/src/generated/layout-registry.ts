/* Generated from canonical JSON Schema. Run pnpm --filter @html-office/contracts generate. */

export interface LayoutRegistry {
  version: "1.0.0";
  /**
   * @minItems 1
   */
  layouts: [Layout, ...Layout[]];
}
/**
 * This interface was referenced by `LayoutRegistry`'s JSON-Schema
 * via the `definition` "Layout".
 */
export interface Layout {
  id: string;
  /**
   * @minItems 1
   */
  slideKinds: ["title" | "content" | "section" | "closing", ...("title" | "content" | "section" | "closing")[]];
  /**
   * @minItems 1
   */
  languages?: [string, ...string[]];
  /**
   * @minItems 1
   */
  slots: [LayoutSlot, ...LayoutSlot[]];
  readingOrder?: string[];
  safeArea: Insets;
  minimumFontSize?: number;
  accessibility?: {
    altRequired: true;
    minimumContrast: number;
  };
  /**
   * @minItems 1
   */
  exportSupport: ["html" | "pdf" | "pptx", ...("html" | "pdf" | "pptx")[]];
}
/**
 * This interface was referenced by `LayoutRegistry`'s JSON-Schema
 * via the `definition` "LayoutSlot".
 */
export interface LayoutSlot {
  id: string;
  kind: "text" | "media" | "table" | "metric" | "chart";
  order?: number;
  required: boolean;
  minItems?: number;
  maxItems: number;
  maxChars?: number;
  maxLines?: number;
  /**
   * @minItems 1
   */
  aspectRatios?: ["16:9" | "4:3" | "1:1" | "3:4" | "9:16", ...("16:9" | "4:3" | "1:1" | "3:4" | "9:16")[]];
}
export interface Insets {
  top: number;
  right: number;
  bottom: number;
  left: number;
}
