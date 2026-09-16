/* Generated from canonical JSON Schema. Run pnpm --filter @html-office/contracts generate. */

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
export interface Tokens {
  [k: string]: string;
}
export interface SourceRef {
  sourceId: string;
  locator: string;
}
