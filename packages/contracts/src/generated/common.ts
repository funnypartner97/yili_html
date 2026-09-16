/* Generated from canonical JSON Schema. Run pnpm --filter @html-office/contracts generate. */

/**
 * This interface was referenced by `CommonContracts`'s JSON-Schema
 * via the `definition` "StableId".
 */
export type StableId = string;
/**
 * This interface was referenced by `CommonContracts`'s JSON-Schema
 * via the `definition` "OutputMode".
 */
export type OutputMode = "document" | "presentation" | "data" | "dashboard";
/**
 * @minItems 1
 *
 * This interface was referenced by `CommonContracts`'s JSON-Schema
 * via the `definition` "EnabledModes".
 */
export type EnabledModes = ["document" | "presentation", ...("document" | "presentation")[]];

export interface CommonContracts {
  [k: string]: unknown;
}
/**
 * This interface was referenced by `CommonContracts`'s JSON-Schema
 * via the `definition` "SourceRef".
 */
export interface SourceRef {
  sourceId: StableId;
  locator: string;
}
/**
 * This interface was referenced by `CommonContracts`'s JSON-Schema
 * via the `definition` "Tokens".
 */
export interface Tokens {
  [k: string]: string;
}
/**
 * This interface was referenced by `CommonContracts`'s JSON-Schema
 * via the `definition` "Insets".
 */
export interface Insets {
  top: number;
  right: number;
  bottom: number;
  left: number;
}
/**
 * This interface was referenced by `CommonContracts`'s JSON-Schema
 * via the `definition` "Theme".
 */
export interface Theme {
  id: string;
  tokens: Tokens;
}
/**
 * This interface was referenced by `CommonContracts`'s JSON-Schema
 * via the `definition` "TableData".
 */
export interface TableData {
  /**
   * @minItems 1
   */
  columns: [string, ...string[]];
  rows: (string | number | boolean | null)[][];
}
