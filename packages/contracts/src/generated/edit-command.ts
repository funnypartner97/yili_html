/* Generated from canonical JSON Schema. Run pnpm --filter @html-office/contracts generate. */

export type EditCommand =
  | {
      kind: "replaceText";
      blockId: string;
      text: string;
    }
  | {
      kind: "insertBlock";
      sectionId: string;
      block:
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
    }
  | {
      kind: "removeBlock";
      blockId: string;
    }
  | {
      kind: "moveBlock";
      blockId: string;
      sectionId: string;
      order: number;
    }
  | {
      kind: "setTheme";
      theme: Theme;
    };
/**
 * @minItems 1
 */
export type SourceRefs = [SourceRef, ...SourceRef[]];

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
export interface Theme {
  id: string;
  tokens: Tokens;
}
export interface Tokens {
  [k: string]: string;
}
