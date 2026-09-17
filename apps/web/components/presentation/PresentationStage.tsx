"use client";

import { useMemo, useState } from "react";

import type { Block, DocumentGraph } from "@html-office/contracts";

import BlockView from "../editor/blocks/BlockView";
import {
  STAGE_HEIGHT, STAGE_LOGICAL_SIZE, STAGE_WIDTH, presentationScale, type Viewport,
} from "./presentationScale";
import { deckSlides, resolveSlide, type Slide } from "./slideLayout";
import { useReducedMotion } from "./useReducedMotion";

export interface PresentationStageProps {
  graph: DocumentGraph;
  viewport: Viewport;
  activeSlideId?: string;
  onActiveSlideChange?: (slideId: string) => void;
  editable?: boolean;
  onBlockChange?: (sectionId: string, blockId: string, patch: Record<string, unknown>) => void;
}

interface MotionInfo {
  state: "animated" | "final";
  intent?: string;
  duration?: string;
  easing?: string;
}

/**
 * Fixed-stage presentation renderer.
 *
 * The deck is authored on a logical 1920×1080 canvas and shown through exactly
 * one uniform scale (`presentationScale`) applied at the stage root — there is no
 * per-block responsive reflow and no CSS `zoom`. Slides are addressed by stable
 * ids for navigation, deep links, notes, and animation targets; page numbers are
 * display-only. Unknown layouts/slots and capacity failures surface as
 * diagnostics rather than shrinking text below the registry minimum.
 */
export default function PresentationStage({
  graph, viewport, activeSlideId, onActiveSlideChange, editable = true, onBlockChange,
}: PresentationStageProps) {
  const reducedMotion = useReducedMotion();
  const slides = useMemo(() => deckSlides(graph), [graph]);
  const [internalActiveId, setInternalActiveId] = useState<string | null>(null);

  const controlledId = activeSlideId ?? internalActiveId;
  const activeIndex = Math.max(
    0,
    slides.findIndex((slide) => slide.id === controlledId),
  );
  const activeSlide = slides[activeIndex];

  const scale = presentationScale(viewport);
  const frameWidth = Math.round(STAGE_WIDTH * scale);
  const frameHeight = Math.round(STAGE_HEIGHT * scale);

  const resolved = useMemo(
    () => (activeSlide ? resolveSlide(graph, activeSlide) : null),
    [graph, activeSlide],
  );

  function select(id: string) {
    if (onActiveSlideChange) onActiveSlideChange(id);
    else setInternalActiveId(id);
  }

  function step(delta: number) {
    const next = Math.min(slides.length - 1, Math.max(0, activeIndex + delta));
    select(slides[next].id);
  }

  // Map animation targets to their declared motion for the active slide.
  const motionByTarget = useMemo(() => {
    const map = new Map<string, MotionInfo>();
    if (!activeSlide) return map;
    for (const entry of [...activeSlide.animationTimeline].sort((a, b) => a.order - b.order)) {
      const animate = entry.exportState === "animated" && !reducedMotion;
      for (const target of entry.targetIds) {
        map.set(target, animate
          ? { state: "animated", intent: entry.intent, duration: entry.duration, easing: entry.easing }
          : { state: "final" });
      }
    }
    return map;
  }, [activeSlide, reducedMotion]);

  function motionProps(id: string): Record<string, string> {
    const info = motionByTarget.get(id);
    if (!info) return { "data-motion-state": "final" };
    if (info.state === "final") return { "data-motion-state": "final" };
    return {
      "data-motion-state": "animated",
      "data-motion-intent": info.intent ?? "",
      "data-motion-duration": info.duration ?? "",
      "data-motion-easing": info.easing ?? "",
    };
  }

  function renderBlocks(sectionId: string, blocks: Block[], slotId: string) {
    return blocks.map((block) => (
      <div key={block.id} className="stage-block" data-block-id={block.id} data-slot-id={slotId} {...motionProps(block.id)}>
        <BlockView
          graph={graph}
          block={block}
          label={`幻灯片 ${activeIndex + 1} ${slotId}`}
          editable={editable}
          onBlockChange={onBlockChange}
          sectionId={sectionId}
        />
      </div>
    ));
  }

  return (
    <div className="presentation-stage-root" data-reduced-motion={reducedMotion ? "true" : "false"}>
      <nav className="stage-navigator" aria-label="幻灯片导航">
        <button type="button" onClick={() => step(-1)} disabled={activeIndex <= 0}>上一张</button>
        <ol className="stage-slide-list">
          {slides.map((slide, index) => (
            <li key={slide.id}>
              <button
                type="button"
                data-slide-id={slide.id}
                aria-current={index === activeIndex ? "true" : undefined}
                onClick={() => select(slide.id)}
              >
                {index + 1}
              </button>
            </li>
          ))}
        </ol>
        <button type="button" onClick={() => step(1)} disabled={activeIndex >= slides.length - 1}>下一张</button>
      </nav>

      <div className="presentation-stage-viewport" style={{ minHeight: frameHeight }}>
        <div className="presentation-stage-frame" style={{ width: frameWidth, height: frameHeight }}>
          <div
            className="presentation-stage"
            data-testid="presentation-stage"
            data-logical-size={STAGE_LOGICAL_SIZE}
            data-scale={scale}
            data-slide-id={activeSlide?.id}
            role="group"
            aria-label={`幻灯片 ${activeIndex + 1}`}
            style={{
              width: STAGE_WIDTH,
              height: STAGE_HEIGHT,
              transform: `scale(${scale})`,
              transformOrigin: "top left",
            }}
          >
            {resolved && resolved.slots.map((slot) => (
              <div
                key={slot.slotId}
                className="stage-slot"
                data-slot-id={slot.slotId}
                style={{
                  position: "absolute",
                  left: slot.rect.x,
                  top: slot.rect.y,
                  width: slot.rect.width,
                  height: slot.rect.height,
                }}
              >
                {renderBlocks(activeSlide!.sectionId, slot.blocks, slot.slotId)}
              </div>
            ))}
            {resolved && resolved.diagnostics.length > 0 && (
              <ul className="stage-diagnostics" role="list" aria-label="舞台诊断">
                {resolved.diagnostics.map((diagnostic, index) => (
                  <li key={`${diagnostic.code}-${index}`} data-code={diagnostic.code} data-severity={diagnostic.severity}>
                    {diagnostic.message}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>

      {resolved?.notes && (
        <aside className="stage-notes" aria-label="演讲者备注">
          <p>{resolved.notes.talk}</p>
        </aside>
      )}
    </div>
  );
}
