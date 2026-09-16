/* Generated from canonical JSON Schema. Run pnpm --filter @html-office/contracts generate. */

export interface TemplatePackage {
  id: string;
  version: string;
  /**
   * @minItems 1
   */
  modes: [
    "document" | "presentation" | "data" | "dashboard",
    ...("document" | "presentation" | "data" | "dashboard")[]
  ];
  formality: "casual" | "neutral" | "formal";
  density: "sparse" | "balanced" | "dense";
  readingSpeed: "quick" | "standard" | "deep";
  /**
   * @minItems 1
   */
  languageCoverage: [string, ...string[]];
  layoutCapabilities: string[];
  chartCapabilities: string[];
  tokens: Tokens;
  /**
   * @minItems 1
   */
  validators: [string, ...string[]];
  /**
   * @minItems 1
   */
  exportSupport: ["html" | "pdf" | "pptx", ...("html" | "pdf" | "pptx")[]];
  dependencies: {
    name: string;
    version: string;
  }[];
  licenseMetadata: {
    id: string;
    kind: "asset" | "font";
    license: string;
    source: string;
    attribution: string;
  }[];
}
export interface Tokens {
  [k: string]: string;
}
