/* Generated from canonical JSON Schema. Run pnpm --filter @html-office/contracts generate. */

/**
 * @minItems 1
 */
export type EnabledModes = ["document" | "presentation", ...("document" | "presentation")[]];
/**
 * This interface was referenced by `DocumentGraph`'s JSON-Schema
 * via the `definition` "Block".
 */
export type Block =
  | {
      id: string;
      order: number;
      kind: "richText";
      text: string;
      sourceRefs: SourceRefs;
    }
  | {
      id: string;
      order: number;
      kind: "table";
      table: TableData;
      sourceRefs: SourceRefs;
    }
  | {
      id: string;
      order: number;
      kind: "metric";
      label: string;
      value: number;
      unit: string;
      sourceRefs: SourceRefs;
    }
  | {
      id: string;
      order: number;
      kind: "chart";
      chart: ChartSpec;
      frame: ChartFrame;
      sourceRefs: SourceRefs;
    }
  | {
      id: string;
      order: number;
      kind: "image";
      assetId: string;
      sourceRefs: SourceRefs;
    };
/**
 * @minItems 1
 *
 * This interface was referenced by `DocumentGraph`'s JSON-Schema
 * via the `definition` "SourceRefs".
 */
export type SourceRefs = [SourceRef, ...SourceRef[]];

export interface DocumentGraph {
  schemaVersion: "1.0.0";
  artifactId: string;
  title: string;
  outputModes: EnabledModes;
  theme: Theme;
  assets: Asset[];
  /**
   * @minItems 1
   */
  sections: [Section, ...Section[]];
  presentation?: PresentationDocument;
}
export interface Theme {
  id: string;
  tokens: Tokens;
}
export interface Tokens {
  [k: string]: string;
}
/**
 * This interface was referenced by `DocumentGraph`'s JSON-Schema
 * via the `definition` "Asset".
 */
export interface Asset {
  id: string;
  kind: "image" | "video" | "audio";
  uri: string;
  mediaIntent: MediaIntent;
}
/**
 * This interface was referenced by `PresentationDocument`'s JSON-Schema
 * via the `definition` "MediaIntent".
 */
export interface MediaIntent {
  role: "evidence" | "illustration" | "decoration";
  fidelity: "source" | "illustrative" | "photographic";
  slotId: string;
  targetAspectRatio: "16:9" | "4:3" | "1:1" | "3:4" | "9:16";
  cropPolicy: "contain" | "cover" | "none";
  subjectSafeArea: Insets;
  language: string;
  brandTokens: Tokens;
  provenance: SourceRef;
  rights: {
    status: "user-provided" | "licensed" | "public-domain";
    license: string;
  };
  alt: string;
  caption?: string;
}
export interface Insets {
  top: number;
  right: number;
  bottom: number;
  left: number;
}
export interface SourceRef {
  sourceId: string;
  locator: string;
}
/**
 * This interface was referenced by `DocumentGraph`'s JSON-Schema
 * via the `definition` "Section".
 */
export interface Section {
  id: string;
  order: number;
  title: string;
  blocks: Block[];
}
export interface TableData {
  /**
   * @minItems 1
   */
  columns: [string, ...string[]];
  rows: (string | number | boolean | null)[][];
}
export interface ChartSpec {
  id: string;
  datasetId: string;
  mark: "bar" | "line" | "point" | "area" | "arc" | "ohlc" | "hierarchy" | "network" | "map";
  /**
   * @minItems 1
   */
  encodings: [EncodingSpec, ...EncodingSpec[]];
  filters: {
    field: string;
    operator: "eq" | "neq" | "in" | "gt" | "gte" | "lt" | "lte";
    /**
     * @minItems 1
     */
    values: [string | number | boolean | null, ...(string | number | boolean | null)[]];
  }[];
  calculations: {
    as: string;
    operation: "add" | "subtract" | "multiply" | "divide" | "percent" | "datePart";
    /**
     * @minItems 1
     */
    fields: [string, ...string[]];
  }[];
  semanticExplanation: string;
  invariants:
    | {
        kind: "general";
        maxMarks: number;
      }
    | {
        kind: "composition";
        partToWhole: true;
        nonNegative: true;
        total: number;
        maxParts: number;
      }
    | {
        kind: "proportionalBars";
        zeroBaseline: true;
        nonNegative: true;
        maxBars: number;
      }
    | {
        kind: "ohlc";
        orderedTime: true;
        lowAtMostOpenClose: true;
        highAtLeastOpenClose: true;
        maxCandles: number;
      }
    | {
        kind: "hierarchy";
        acyclic: true;
        singleParent: true;
        maxDepth: number;
        maxNodes: number;
      }
    | {
        kind: "network";
        resolvedEndpoints: true;
        directed: boolean;
        maxNodes: number;
        maxEdges: number;
      }
    | {
        kind: "map";
        coordinateSystem: "WGS84";
        projection: "mercator" | "equalEarth" | "equirectangular";
        validCoordinates: true;
        offlineGeometry: true;
        maxFeatures: number;
      };
}
export interface EncodingSpec {
  channel:
    | "x"
    | "y"
    | "color"
    | "size"
    | "shape"
    | "label"
    | "theta"
    | "radius"
    | "longitude"
    | "latitude"
    | "open"
    | "high"
    | "low"
    | "close"
    | "source"
    | "target"
    | "parent";
  field: string;
  type: "quantitative" | "nominal" | "ordinal" | "temporal" | "geo";
  aggregation: "none" | "sum" | "mean" | "count" | "min" | "max" | "median";
  sort: "none" | "ascending" | "descending";
  scale: {
    type: "linear" | "log" | "time" | "ordinal" | "identity";
    /**
     * @minItems 2
     */
    domain: [string | number, string | number, ...(string | number)[]];
    baseline: number | null;
  };
}
export interface ChartFrame {
  title: string;
  description: string;
  /**
   * @minItems 1
   */
  source: [SourceRef, ...SourceRef[]];
  asOf: string;
  methodology?: string;
  caveats: string[];
  claim: string;
  tableFallback: TableData;
}
export interface PresentationDocument {
  stage: {
    width: 1920;
    height: 1080;
  };
  /**
   * @minItems 1
   */
  slides: [Slide, ...Slide[]];
}
/**
 * This interface was referenced by `PresentationDocument`'s JSON-Schema
 * via the `definition` "Slide".
 */
export interface Slide {
  id: string;
  order: number;
  sectionId: string;
  kind: "title" | "content" | "section" | "closing";
  layoutId: string;
  slotAssignments: SlotAssignment[];
  speakerNotes?: SpeakerNotes;
  timing: Timing;
  animationTimeline: AnimationEntry[];
}
/**
 * This interface was referenced by `PresentationDocument`'s JSON-Schema
 * via the `definition` "SlotAssignment".
 */
export interface SlotAssignment {
  id: string;
  order: number;
  slotId: string;
  blockIds: string[];
  assetIds: string[];
}
/**
 * This interface was referenced by `PresentationDocument`'s JSON-Schema
 * via the `definition` "SpeakerNotes".
 */
export interface SpeakerNotes {
  id: string;
  slideId: string;
  talk: string;
  transition: string;
  interaction: string;
  stageDirections: string;
}
/**
 * This interface was referenced by `PresentationDocument`'s JSON-Schema
 * via the `definition` "Timing".
 */
export interface Timing {
  plannedSeconds: number;
  autoAdvanceSeconds?: number;
  rehearsalEvents: {
    id: string;
    elapsedSeconds: number;
  }[];
}
/**
 * This interface was referenced by `PresentationDocument`'s JSON-Schema
 * via the `definition` "AnimationEntry".
 */
export interface AnimationEntry {
  id: string;
  order: number;
  intent: "reveal" | "emphasize" | "transition";
  /**
   * @minItems 1
   */
  targetIds: [string, ...string[]];
  duration: "instant" | "short" | "medium" | "long";
  easing: "linear" | "ease-in" | "ease-out" | "ease-in-out";
  exportState: "animated" | "static" | "omitted";
}
