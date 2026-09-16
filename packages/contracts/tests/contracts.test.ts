import { describe, expect, it } from 'vitest';
import * as contracts from '../src';
import { fixtures, generationPlanFixture, presentationGraphFixture } from './fixtures';

describe('canonical shared contracts', () => {
  for (const [name, fixture] of Object.entries(fixtures)) {
    it(`round-trips ${name} without losing contract fields`, () => {
      const schema = (contracts as unknown as Record<string, { parse: (value: unknown) => unknown }>)[`${name}Schema`];
      expect(schema.parse(fixture)).toEqual(fixture);
    });
  }
  it('accepts multiple output modes', () => {
    expect(contracts.GenerationPlanSchema.parse(generationPlanFixture).outputModes).toEqual(['document', 'presentation']);
  });
  it.each([[], ['document', 'document'], ['data'], ['dashboard']])('rejects unavailable or duplicate plan modes %j', (...modes) => {
    expect(contracts.GenerationPlanSchema.safeParse({ ...generationPlanFixture, outputModes: modes }).success).toBe(false);
  });
  it('retains note binding after slide reorder', () => {
    const graph = structuredClone(presentationGraphFixture);
    const second = structuredClone(graph.presentation.slides[0]);
    second.id = '01993f2f-2b79-7000-8000-000000000020';
    second.speakerNotes.id = '01993f2f-2b79-7000-8000-000000000021';
    second.speakerNotes.slideId = second.id;
    second.slotAssignments.forEach((a, i) => a.id = `01993f2f-2b79-7000-8000-00000000002${i + 2}`);
    second.animationTimeline = [];
    graph.presentation.slides[0].order = 1;
    graph.presentation.slides.unshift(second);
    const parsed = contracts.DocumentGraphSchema.parse(graph);
    expect(parsed.presentation?.slides.map(s => s.speakerNotes?.slideId)).toEqual([second.id, '01993f2f-2b79-7000-8000-000000000006']);
  });
  const invalidGraphs: [string, (g: typeof presentationGraphFixture) => void][] = [
    ['unknown layout', g => { g.presentation.slides[0].layoutId = 'unknown'; }],
    ['unknown slot', g => { g.presentation.slides[0].slotAssignments[0].slotId = 'unknown'; }],
    ['over capacity', g => {
      const block = { ...g.sections[0].blocks[0], id: '01993f2f-2b79-7000-8000-000000000099', order: 1 };
      g.sections[0].blocks.push(block);
      g.presentation.slides[0].slotAssignments[0].blockIds = [g.sections[0].blocks[0].id, block.id];
    }],
    ['duplicate block identity', g => { g.sections[0].blocks.push(structuredClone(g.sections[0].blocks[0])); }],
    ['non UUIDv7 identity', g => { g.sections[0].blocks[0].id = 'page-1'; }],
    ['note mismatch', g => { g.presentation.slides[0].speakerNotes.slideId = g.artifactId; }],
    ['wrong stage', g => { g.presentation.stage.width = 1280; }],
    ['missing block reference', g => { g.presentation.slides[0].slotAssignments[0].blockIds[0] = g.artifactId; }],
    ['unknown animation target', g => { g.presentation.slides[0].animationTimeline[0].targetIds[0] = g.artifactId; }],
    ['duplicate order', g => { g.presentation.slides[0].slotAssignments[1].order = 0; }],
    ['script animation', g => { Object.assign(g.presentation.slides[0].animationTimeline[0], { script: 'alert(1)' }); }],
  ];
  it.each(invalidGraphs)('rejects %s', (_, mutate) => {
    const graph = structuredClone(presentationGraphFixture); mutate(graph);
    expect(contracts.DocumentGraphSchema.safeParse(graph).success).toBe(false);
  });
  it.each(['provenance', 'rights', 'alt'])('requires media %s', key => {
    const media = { ...presentationGraphFixture.assets[0].mediaIntent } as Record<string, unknown>;
    delete media[key]; expect(contracts.MediaIntentSchema.safeParse(media).success).toBe(false);
  });
  it.each(['alternatives', 'invariantResults'])('requires chart audit %s', key => {
    const plan = { ...fixtures.ChartPlan } as Record<string, unknown>; delete plan[key];
    expect(contracts.ChartPlanSchema.safeParse(plan).success).toBe(false);
  });
  it('requires a rejected alternative with reasons', () => {
    expect(contracts.ChartPlanSchema.safeParse({ ...fixtures.ChartPlan, alternatives: [] }).success).toBe(false);
    expect(contracts.ChartPlanSchema.safeParse({ ...fixtures.ChartPlan, alternatives: [{ id: 'pie', score: 0.2, rejected: true, reasons: [] }] }).success).toBe(false);
  });
  it.each(['dependencies', 'licenseMetadata'])('requires template %s', key => {
    const template = { ...fixtures.TemplatePackage } as Record<string, unknown>; delete template[key];
    expect(contracts.TemplatePackageSchema.safeParse(template).success).toBe(false);
  });
  it('rejects mutable dependency ranges', () => {
    expect(contracts.TemplatePackageSchema.safeParse({ ...fixtures.TemplatePackage, dependencies: [{ name: 'core', version: '^1.0.0' }] }).success).toBe(false);
  });
  it('requires source-backed plans', () => {
    expect(contracts.GenerationPlanSchema.safeParse({ ...generationPlanFixture, sourceSummary: { parsed: 0, failed: 1, conflicts: [] } }).success).toBe(false);
  });
  it('validates the shipped layout registry and presentation independently', () => {
    expect(contracts.LayoutRegistrySchema.parse(contracts.corePresentationLayouts).layouts[0].id).toBe('title-media');
    expect(contracts.PresentationDocumentSchema.parse(presentationGraphFixture.presentation).stage).toEqual({ width: 1920, height: 1080 });
  });
  it.each(['composition', 'proportionalBars', 'ohlc', 'hierarchy', 'network', 'map'])('requires %s invariant metadata', kind => {
    expect(contracts.ChartSpecSchema.safeParse({ ...fixtures.ChartSpec, invariants: { kind } }).success).toBe(false);
  });
  it('rejects animation references to another slide even when they exist in the graph', () => {
    const graph = structuredClone(presentationGraphFixture);
    graph.presentation.slides[0].animationTimeline[0].targetIds = [graph.sections[0].id];
    expect(contracts.DocumentGraphSchema.safeParse(graph).success).toBe(false);
  });
  it('requires document graph identity not to collide with contained entities', () => {
    const graph = structuredClone(presentationGraphFixture);
    graph.assets[0].id = graph.artifactId;
    graph.presentation.slides[0].slotAssignments[1].assetIds = [graph.artifactId];
    expect(contracts.DocumentGraphSchema.safeParse(graph).success).toBe(false);
  });
  it('keeps chart validation equally strict when charts are inserted using edit commands', () => {
    const block = { id: '01993f2f-2b79-7000-8000-000000000030', order: 1, kind: 'chart', chart: { ...fixtures.ChartSpec, encodings: [{ ...fixtures.EncodingSpec, scale: { ...fixtures.EncodingSpec.scale, baseline: 10 } }] }, frame: fixtures.ChartFrame, sourceRefs: presentationGraphFixture.sections[0].blocks[0].sourceRefs };
    expect(contracts.EditCommandSchema.safeParse({ kind: 'insertBlock', sectionId: presentationGraphFixture.sections[0].id, block }).success).toBe(false);
  });
  it.each(['composition', 'ohlc', 'hierarchy', 'network', 'map'])('rejects incompatible mark for %s', kind => {
    expect(contracts.ChartSpecSchema.safeParse({ ...fixtures.ChartSpec, invariants: { kind } }).success).toBe(false);
  });
});
