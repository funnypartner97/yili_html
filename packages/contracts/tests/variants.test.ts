import { describe, expect, it } from 'vitest';
import { ChartSpecSchema, DocumentGraphSchema, EditCommandSchema } from '../src';
import { fixtures } from './fixtures';
import negativeFixtures from './negative-fixtures.json';

describe('discriminated contract variants', () => {
  it('rejects a chart block whose identity is reused by its nested chart', () => {
    expect(() => EditCommandSchema.parse(negativeFixtures.insertBlockDuplicateChartId)).toThrow('Duplicate stable identity');
  });
  it.each(['audio', 'video'])('rejects an image block referencing %s in a document', kind => {
    const graph = structuredClone(fixtures.DocumentGraph);
    graph.assets[0].kind = kind;
    const block = { id: '01993f2f-2b79-7000-8000-000000000032', order: 1, kind: 'image', assetId: graph.assets[0].id, sourceRefs: graph.sections[0].blocks[0].sourceRefs };
    const { presentation: _presentation, ...document } = graph;
    expect(() => DocumentGraphSchema.parse({ ...document, outputModes: ['document'], sections: [{ ...graph.sections[0], blocks: [block] }] })).toThrow('image asset');
  });
  it.each(['audio', 'video'])('rejects an image block referencing %s in a slide', kind => {
    const graph = structuredClone(fixtures.DocumentGraph);
    graph.assets[0].kind = kind;
    const block = { id: '01993f2f-2b79-7000-8000-000000000032', order: 1, kind: 'image', assetId: graph.assets[0].id, sourceRefs: graph.sections[0].blocks[0].sourceRefs };
    graph.presentation.slides[0].slotAssignments[1].assetIds = [];
    graph.presentation.slides[0].slotAssignments[1].blockIds = [block.id];
    expect(() => DocumentGraphSchema.parse({ ...graph, sections: [{ ...graph.sections[0], blocks: [...graph.sections[0].blocks, block] }] })).toThrow('image asset');
  });
  const sourceRefs = fixtures.DocumentGraph.sections[0].blocks[0].sourceRefs;
  const base = { id: '01993f2f-2b79-7000-8000-000000000031', order: 1, sourceRefs };
  const blocks = [
    { ...base, kind: 'richText', text: 'text' },
    { ...base, kind: 'table', table: fixtures.ChartFrame.tableFallback },
    { ...base, kind: 'metric', label: 'Revenue', value: 42, unit: 'CNY' },
    { ...base, kind: 'image', assetId: fixtures.DocumentGraph.assets[0].id },
    { ...base, kind: 'chart', chart: fixtures.ChartSpec, frame: fixtures.ChartFrame },
  ];
  it.each(blocks)('preserves $kind block payload', block => {
    const graph = structuredClone(fixtures.DocumentGraph);
    const result = DocumentGraphSchema.parse({ ...graph, sections: [{ ...graph.sections[0], blocks: [graph.sections[0].blocks[0], block] }] });
    expect(result.sections[0].blocks[1]).toEqual(block);
  });
  const edits = [
    fixtures.EditCommand,
    { kind: 'insertBlock', sectionId: fixtures.DocumentGraph.sections[0].id, block: blocks[2] },
    { kind: 'removeBlock', blockId: base.id },
    { kind: 'moveBlock', blockId: base.id, sectionId: fixtures.DocumentGraph.sections[0].id, order: 2 },
    { kind: 'setTheme', theme: fixtures.DocumentGraph.theme },
  ];
  it.each(edits)('accepts $kind edit command', command => {
    expect(EditCommandSchema.parse(command)).toEqual(command);
  });
  const charts = [
    { mark: 'arc', invariants: { kind: 'composition', partToWhole: true, nonNegative: true, total: 100, maxParts: 6 } },
    { mark: 'ohlc', invariants: { kind: 'ohlc', orderedTime: true, lowAtMostOpenClose: true, highAtLeastOpenClose: true, maxCandles: 80 } },
    { mark: 'hierarchy', invariants: { kind: 'hierarchy', acyclic: true, singleParent: true, maxDepth: 4, maxNodes: 100 } },
    { mark: 'network', invariants: { kind: 'network', resolvedEndpoints: true, directed: false, maxNodes: 80, maxEdges: 200 } },
    { mark: 'map', invariants: { kind: 'map', coordinateSystem: 'WGS84', projection: 'equalEarth', validCoordinates: true, offlineGeometry: true, maxFeatures: 200 } },
  ];
  it.each(charts)('round-trips reserved $mark invariants and capacity', variant => {
    const chart = { ...fixtures.ChartSpec, ...variant };
    expect(ChartSpecSchema.parse(chart)).toEqual(chart);
    expect(ChartSpecSchema.safeParse({ ...chart, mark: 'bar' }).success).toBe(false);
  });
});
