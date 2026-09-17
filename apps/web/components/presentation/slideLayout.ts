import type { Block, DocumentGraph, LayoutRegistry, PresentationDocument } from "@html-office/contracts";
import { corePresentationLayouts } from "@html-office/contracts";

import { STAGE_HEIGHT, STAGE_WIDTH } from "./presentationScale";

export type Layout = LayoutRegistry["layouts"][number];
export type LayoutSlot = Layout["slots"][number];
export type Slide = PresentationDocument["slides"][number];
export type SlotAssignment = Slide["slotAssignments"][number];
export type SpeakerNotes = NonNullable<Slide["speakerNotes"]>;

/** Gap between stacked slots inside the safe area, in logical pixels. */
const SLOT_GAP = 48;
/** Share of the usable height reserved for the first (title) reading slot. */
const LEADING_SLOT_SHARE = 0.22;

export interface Rect {
  x: number;
  y: number;
  width: number;
  height: number;
}

export type DiagnosticSeverity = "error" | "warning";

export interface SlideDiagnostic {
  code:
    | "unknown_layout"
    | "incompatible_layout_kind"
    | "unknown_slot"
    | "missing_required_slot"
    | "slot_capacity"
    | "text_capacity"
    | "unknown_block";
  severity: DiagnosticSeverity;
  slideId: string;
  slotId?: string;
  message: string;
}

export interface ResolvedSlot {
  slotId: string;
  rect: Rect;
  assignment: SlotAssignment | undefined;
  blocks: Block[];
  assetIds: string[];
}

export interface ResolvedSlide {
  slideId: string;
  order: number;
  sectionId: string;
  kind: string;
  layout: Layout | undefined;
  layoutId: string;
  slots: ResolvedSlot[];
  diagnostics: SlideDiagnostic[];
  notes?: SpeakerNotes;
}

export function findLayout(layoutId: string): Layout | undefined {
  return corePresentationLayouts.layouts.find((layout) => layout.id === layoutId);
}

/**
 * The deck to render: the authored presentation when present, otherwise one
 * synthesized `title-body` slide per section so a document-only graph still has
 * a stable, navigable presentation surface. Synthesized slides reuse the section
 * id-derived stable ids so navigation and deep links stay deterministic.
 */
export function deckSlides(graph: DocumentGraph): Slide[] {
  if (graph.presentation) {
    return [...graph.presentation.slides].sort((a, b) => a.order - b.order);
  }
  return [...graph.sections]
    .sort((a, b) => a.order - b.order)
    .map((section, index): Slide => {
      const blocks = [...section.blocks].sort((a, b) => a.order - b.order);
      const titleBlock = blocks.find((block) => block.kind === "richText");
      const bodyBlocks = blocks.filter((block) => block.id !== titleBlock?.id);
      const slotAssignments: SlotAssignment[] = [];
      if (titleBlock) {
        slotAssignments.push({
          id: `${section.id}-title-slot`, order: 0, slotId: "title",
          blockIds: [titleBlock.id], assetIds: [],
        });
      }
      if (bodyBlocks.length > 0) {
        slotAssignments.push({
          id: `${section.id}-body-slot`, order: 1, slotId: "body",
          blockIds: bodyBlocks.map((block) => block.id), assetIds: [],
        });
      }
      return {
        id: `${section.id}-slide`,
        order: index,
        sectionId: section.id,
        kind: "content",
        layoutId: "title-body",
        slotAssignments,
        timing: { plannedSeconds: 60, rehearsalEvents: [] },
        animationTimeline: [],
      };
    });
}

/**
 * Deterministic vertical slot geometry inside the layout safe area. The registry
 * declares reading order, capacity, and safe area but not absolute coordinates,
 * so the stage derives a stable stacked layout: the leading reading slot takes a
 * fixed share and the remaining slots split the rest equally.
 */
export function slotRects(layout: Layout): Record<string, Rect> {
  const safe = layout.safeArea;
  const left = safe.left;
  const top = safe.top;
  const width = STAGE_WIDTH - safe.left - safe.right;
  const totalHeight = STAGE_HEIGHT - safe.top - safe.bottom;

  const orderedIds = layout.readingOrder && layout.readingOrder.length === layout.slots.length
    ? layout.readingOrder
    : [...layout.slots].sort((a, b) => (a.order ?? 0) - (b.order ?? 0)).map((slot) => slot.id);

  const count = orderedIds.length;
  const gaps = SLOT_GAP * Math.max(0, count - 1);
  const usable = Math.max(0, totalHeight - gaps);
  const leadingHeight = count > 1 ? Math.round(usable * LEADING_SLOT_SHARE) : usable;
  const restHeight = count > 1 ? Math.round((usable - leadingHeight) / (count - 1)) : 0;

  const rects: Record<string, Rect> = {};
  let cursorY = top;
  orderedIds.forEach((slotId, index) => {
    const height = index === 0 ? leadingHeight : restHeight;
    rects[slotId] = { x: left, y: cursorY, width, height };
    cursorY += height + SLOT_GAP;
  });
  return rects;
}

function textMeasure(block: Block): { chars: number; lines: number } {
  if (block.kind !== "richText") return { chars: 0, lines: 0 };
  return { chars: [...block.text].length, lines: block.text.split("\n").length };
}

/**
 * Resolve one slide against the registry: bind slot assignments to their blocks
 * and assets, compute geometry, and surface layout/slot/capacity problems as
 * diagnostics instead of silently shrinking text or dropping content.
 */
export function resolveSlide(
  graph: DocumentGraph,
  slide: Slide,
): ResolvedSlide {
  const diagnostics: SlideDiagnostic[] = [];
  const layout = findLayout(slide.layoutId);
  const blocksById = new Map(
    graph.sections.flatMap((section) => section.blocks).map((block) => [block.id, block]),
  );

  if (!layout) {
    diagnostics.push({
      code: "unknown_layout",
      severity: "error",
      slideId: slide.id,
      message: `未登记的版式 "${slide.layoutId}"，无法在固定舞台上渲染。`,
    });
    return {
      slideId: slide.id, order: slide.order, sectionId: slide.sectionId, kind: slide.kind,
      layout, layoutId: slide.layoutId, slots: [], diagnostics, notes: slide.speakerNotes,
    };
  }
  if (!layout.slideKinds.includes(slide.kind)) {
    diagnostics.push({
      code: "incompatible_layout_kind",
      severity: "error",
      slideId: slide.id,
      message: `版式 "${layout.id}" 不支持幻灯片类型 "${slide.kind}"。`,
    });
  }

  const rects = slotRects(layout);
  const assignmentsBySlot = new Map(slide.slotAssignments.map((a) => [a.slotId, a]));

  const slots: ResolvedSlot[] = layout.slots.map((slot) => {
    const assignment = assignmentsBySlot.get(slot.id);
    const blocks: Block[] = [];
    const assetIds: string[] = [];
    if (assignment) {
      let chars = 0;
      let lines = 0;
      for (const blockId of assignment.blockIds) {
        const block = blocksById.get(blockId);
        if (!block) {
          diagnostics.push({
            code: "unknown_block", severity: "error", slideId: slide.id, slotId: slot.id,
            message: `槽位 "${slot.id}" 引用了不存在的块 ${blockId}。`,
          });
          continue;
        }
        blocks.push(block);
        const measure = textMeasure(block);
        chars += measure.chars;
        lines += measure.lines;
      }
      assetIds.push(...assignment.assetIds);

      const count = assignment.blockIds.length + assignment.assetIds.length;
      const minItems = slot.minItems ?? (slot.required ? 1 : 0);
      if (count > slot.maxItems || count < minItems) {
        diagnostics.push({
          code: "slot_capacity", severity: "error", slideId: slide.id, slotId: slot.id,
          message: `槽位 "${slot.id}" 内容数 ${count} 超出允许范围 ${minItems}–${slot.maxItems}。`,
        });
      }
      if (slot.maxChars !== undefined && chars > slot.maxChars) {
        diagnostics.push({
          code: "text_capacity", severity: "warning", slideId: slide.id, slotId: slot.id,
          message: `槽位 "${slot.id}" 文本 ${chars} 字，超过上限 ${slot.maxChars} 字。`,
        });
      }
      if (slot.maxLines !== undefined && lines > slot.maxLines) {
        diagnostics.push({
          code: "text_capacity", severity: "warning", slideId: slide.id, slotId: slot.id,
          message: `槽位 "${slot.id}" 文本 ${lines} 行，超过上限 ${slot.maxLines} 行。`,
        });
      }
    } else if (slot.required) {
      diagnostics.push({
        code: "missing_required_slot", severity: "error", slideId: slide.id, slotId: slot.id,
        message: `缺少必填槽位 "${slot.id}"。`,
      });
    }
    return { slotId: slot.id, rect: rects[slot.id], assignment, blocks, assetIds };
  });

  for (const assignment of slide.slotAssignments) {
    if (!layout.slots.some((slot) => slot.id === assignment.slotId)) {
      diagnostics.push({
        code: "unknown_slot", severity: "error", slideId: slide.id, slotId: assignment.slotId,
        message: `版式 "${layout.id}" 未定义槽位 "${assignment.slotId}"。`,
      });
    }
  }

  return {
    slideId: slide.id, order: slide.order, sectionId: slide.sectionId, kind: slide.kind,
    layout, layoutId: slide.layoutId, slots, diagnostics, notes: slide.speakerNotes,
  };
}
