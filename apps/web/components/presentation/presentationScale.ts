/**
 * Fixed-stage presentation geometry.
 *
 * The presentation canvas is a logical 1920×1080 surface. It is never reflowed
 * per breakpoint and never uses CSS `zoom`; instead one uniform scale is derived
 * from the available viewport and applied at the stage root, so the deck keeps
 * exact authored proportions on 16:9, 16:10, and narrow screens alike.
 */

export const STAGE_WIDTH = 1920;
export const STAGE_HEIGHT = 1080;

/** Logical size label exposed on the stage root for tests and diagnostics. */
export const STAGE_LOGICAL_SIZE = `${STAGE_WIDTH}x${STAGE_HEIGHT}`;

export interface Viewport {
  width: number;
  height: number;
}

/**
 * The single uniform scale for the fixed stage: the largest factor that fits the
 * whole 1920×1080 canvas inside the viewport without cropping either axis.
 */
export function presentationScale(viewport: Viewport): number {
  const width = Number.isFinite(viewport.width) ? Math.max(0, viewport.width) : 0;
  const height = Number.isFinite(viewport.height) ? Math.max(0, viewport.height) : 0;
  return Math.min(width / STAGE_WIDTH, height / STAGE_HEIGHT);
}
