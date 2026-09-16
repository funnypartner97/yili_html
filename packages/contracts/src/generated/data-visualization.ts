/* Generated from canonical JSON Schema. Run pnpm --filter @html-office/contracts generate. */

export type DataVisualizationContract =
  DatasetProfile | AnalyticIntent | ChartPlan | ChartSpec | EncodingSpec | ChartFrame;
export type ChartInvariants =
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

export interface DatasetProfile {
  id: string;
  sourceId: string;
  rowCount: number;
  /**
   * @minItems 1
   */
  fields: [
    {
      name: string;
      type: "quantitative" | "nominal" | "ordinal" | "temporal" | "boolean" | "geo";
      cardinality: number;
      nullCount: number;
      invalidCount: number;
      timezone: string | null;
      unit: string | null;
      sensitivity: "public" | "internal" | "confidential" | "restricted";
    },
    ...{
      name: string;
      type: "quantitative" | "nominal" | "ordinal" | "temporal" | "boolean" | "geo";
      cardinality: number;
      nullCount: number;
      invalidCount: number;
      timezone: string | null;
      unit: string | null;
      sensitivity: "public" | "internal" | "confidential" | "restricted";
    }[]
  ];
  aggregationProvenance: {
    operation: "none" | "sum" | "mean" | "count" | "min" | "max" | "median";
    /**
     * @minItems 1
     */
    fields: [string, ...string[]];
    sourceRowCount: number;
  }[];
  sampling: {
    method: "none" | "random" | "stratified" | "systematic";
    sampleSize: number;
    populationSize: number;
    seed?: number;
  };
}
export interface AnalyticIntent {
  question: string;
  audience: string;
  readingSpeed: "quick" | "standard" | "deep";
  surface: "document" | "presentation" | "data" | "dashboard";
  /**
   * @minItems 1
   */
  interaction: [
    "none" | "filter" | "highlight" | "zoom" | "drilldown",
    ...("none" | "filter" | "highlight" | "zoom" | "drilldown")[]
  ];
  accessibility: {
    tableRequired: true;
    colorIndependent: true;
  };
  offline: boolean;
}
export interface ChartPlan {
  id: string;
  selectedCandidate: Candidate;
  /**
   * @minItems 1
   */
  alternatives: [
    {
      id: string;
      score: number;
      /**
       * @minItems 1
       */
      reasons: [string, ...string[]];
      rejected: true;
    },
    ...{
      id: string;
      score: number;
      /**
       * @minItems 1
       */
      reasons: [string, ...string[]];
      rejected: true;
    }[]
  ];
  expectedMarks: number;
  fallback: "accessibleTable";
  /**
   * @minItems 1
   */
  invariantResults: [
    {
      rule: string;
      passed: boolean;
      reason: string;
    },
    ...{
      rule: string;
      passed: boolean;
      reason: string;
    }[]
  ];
}
export interface Candidate {
  id: string;
  score: number;
  /**
   * @minItems 1
   */
  reasons: [string, ...string[]];
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
  invariants: ChartInvariants;
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
export interface SourceRef {
  sourceId: string;
  locator: string;
}
export interface TableData {
  /**
   * @minItems 1
   */
  columns: [string, ...string[]];
  rows: (string | number | boolean | null)[][];
}
