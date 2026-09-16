/* Generated from canonical JSON Schema. Run pnpm --filter @html-office/contracts generate. */

/**
 * @minItems 1
 */
export type EnabledModes = ["document" | "presentation", ...("document" | "presentation")[]];

export interface GenerationPlan {
  artifactId: string;
  outputModes: EnabledModes;
  audience: string;
  lengthPreset: "short" | "standard" | "long";
  density: "sparse" | "balanced" | "dense";
  outputSpec: "responsive" | "fixed";
  emphasis: string[];
  /**
   * @minItems 1
   */
  outline: [
    {
      id: string;
      title: string;
    },
    ...{
      id: string;
      title: string;
    }[]
  ];
  sourceSummary: {
    parsed: number;
    failed: number;
    conflicts: string[];
  };
}
