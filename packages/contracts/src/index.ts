import Ajv from 'ajv';
import { z } from 'zod';
import common from '../schemas/common.schema.json';
import graph from '../schemas/document-graph.schema.json';
import plan from '../schemas/generation-plan.schema.json';
import edits from '../schemas/edit-command.schema.json';
import presentation from '../schemas/presentation.schema.json';
import layouts from '../schemas/layout-registry.schema.json';
import template from '../schemas/template-package.schema.json';
import data from '../schemas/data-visualization.schema.json';
import registry from '../registries/core-presentation-layouts.json';
import type { DocumentGraph, Block } from './generated/document-graph';
import type { GenerationPlan } from './generated/generation-plan';
import type { EditCommand } from './generated/edit-command';
import type { PresentationDocument, MediaIntent } from './generated/presentation';
import type { LayoutRegistry } from './generated/layout-registry';
import type { TemplatePackage } from './generated/template-package';
import type { DatasetProfile, AnalyticIntent, ChartPlan, ChartSpec, EncodingSpec, ChartFrame } from './generated/data-visualization';
export type { OutputMode, StableId, Theme, SourceRef, TableData } from './generated/common';
export type { DocumentGraph, Block, GenerationPlan, EditCommand, PresentationDocument, MediaIntent, LayoutRegistry, TemplatePackage, DatasetProfile, AnalyticIntent, ChartPlan, ChartSpec, EncodingSpec, ChartFrame };
export const ENABLED_OUTPUT_MODES = ['document', 'presentation'] as const;
export const corePresentationLayouts = registry as LayoutRegistry;

const ajv = new Ajv({ allErrors: true, strict: false });
for (const schema of [common, graph, plan, edits, presentation, layouts, template, data]) ajv.addSchema(schema);

function unique(values: unknown[], label: string): void {
  if (new Set(values).size !== values.length) throw new Error('Duplicate ' + label);
}

// Stable entity identity is global; references such as blockIds and slideId are not identities.
function identityAndOrder(value: unknown): void {
  const ids: string[] = [];
  function visit(item: unknown): void {
    if (Array.isArray(item)) {
      const ordered = item.filter((x): x is { order: number } => typeof x === 'object' && x !== null && 'order' in x);
      unique(ordered.map(x => x.order), 'order');
      item.forEach(visit);
    } else if (item !== null && typeof item === 'object') {
      const obj = item as Record<string, unknown>;
      if (typeof obj.artifactId === 'string') ids.push(obj.artifactId);
      if (typeof obj.id === 'string' && /^[0-9a-f]{8}-/.test(obj.id)) ids.push(obj.id);
      Object.values(obj).forEach(visit);
    }
  }
  visit(value);
  unique(ids, 'stable identity');
}

function validatePresentation(p: PresentationDocument, doc?: DocumentGraph): void {
  identityAndOrder(p);
  const sections = new Set(doc?.sections.map(s => s.id));
  const blocks = new Map(doc?.sections.flatMap(s => s.blocks).map(b => [b.id, b]));
  const assets = new Map(doc?.assets.map(a => [a.id, a]));
  for (const slide of p.slides) {
    const layout = corePresentationLayouts.layouts.find(l => l.id === slide.layoutId);
    if (!layout || !layout.slideKinds.includes(slide.kind)) throw new Error('Unknown or incompatible layout');
    if (doc && !sections.has(slide.sectionId)) throw new Error('Unknown section');
    if (slide.speakerNotes && slide.speakerNotes.slideId !== slide.id) throw new Error('Note/slide mismatch');
    unique(slide.slotAssignments.map(s => s.slotId), 'slot assignment');
    const targets = new Set([slide.id, ...slide.slotAssignments.flatMap(a => [a.id, ...a.blockIds, ...a.assetIds])]);
    for (const animation of slide.animationTimeline) {
      if (animation.targetIds.some(id => !targets.has(id))) throw new Error('Unknown animation target');
    }
    for (const assignment of slide.slotAssignments) {
      const slot = layout.slots.find(s => s.id === assignment.slotId);
      if (!slot) throw new Error('Unknown slot');
      const count = assignment.blockIds.length + assignment.assetIds.length;
      if (count > slot.maxItems || count < (slot.minItems ?? (slot.required ? 1 : 0))) throw new Error('Slot capacity exceeded');
      if (doc) {
        let chars = 0; let lines = 0;
        for (const id of assignment.blockIds) {
          const block = blocks.get(id);
          if (!block) throw new Error('Unknown block reference');
          const expected = slot.kind === 'text' ? 'richText' : slot.kind === 'media' ? 'image' : slot.kind;
          if (block.kind !== expected) throw new Error('Incompatible block slot');
          if (block.kind === 'richText') { chars += [...block.text].length; lines += block.text.split('\n').length; }
          if (block.kind === 'image') checkMedia(block.assetId, true);
        }
        if (slot.maxChars && chars > slot.maxChars) throw new Error('Text capacity exceeded');
        if (slot.maxLines && lines > slot.maxLines) throw new Error('Line capacity exceeded');
        for (const id of assignment.assetIds) checkMedia(id);
        function checkMedia(id: string, requireImage = false): void {
          const asset = assets.get(id);
          if (!asset || slot!.kind !== 'media') throw new Error('Unknown or incompatible media');
          if (requireImage && asset.kind !== 'image') throw new Error('Incompatible image asset');
          if (asset.mediaIntent.slotId !== slot!.id || (slot!.aspectRatios && !slot!.aspectRatios.includes(asset.mediaIntent.targetAspectRatio))) throw new Error('Media slot/aspect mismatch');
        }
      } else if (assignment.assetIds.length && slot.kind !== 'media') throw new Error('Incompatible media slot');
    }
    for (const slot of layout.slots) {
      if (slot.required && !slide.slotAssignments.some(a => a.slotId === slot.id)) throw new Error('Missing required slot');
    }
  }
}

function validateGraph(doc: DocumentGraph): void {
  identityAndOrder(doc);
  if (doc.presentation && !doc.outputModes.includes('presentation')) throw new Error('Presentation mode required');
  const assets = new Map(doc.assets.map(a => [a.id, a]));
  for (const section of doc.sections) for (const block of section.blocks) {
    if (block.kind === 'image' && assets.get(block.assetId)?.kind !== 'image') throw new Error('Unknown or incompatible image asset');
    if (block.kind === 'table') validateTable(block.table);
    if (block.kind === 'chart') { validateChart(block.chart); validateTable(block.frame.tableFallback); }
  }
  if (doc.presentation) validatePresentation(doc.presentation, doc);
}

function validateTable(table: { columns: string[]; rows: unknown[][] }): void {
  if (table.rows.some(row => row.length !== table.columns.length)) throw new Error('Table row width mismatch');
}

function validateRegistry(value: LayoutRegistry): void {
  unique(value.layouts.map(l => l.id), 'layout');
  for (const layout of value.layouts) {
    unique(layout.slots.map(s => s.id), 'slot');
    unique(layout.slots.flatMap(s => s.order === undefined ? [] : [s.order]), 'slot order');
    for (const slot of layout.slots) if ((slot.minItems ?? 0) > slot.maxItems) throw new Error('Invalid slot capacity');
    if (layout.readingOrder && (layout.readingOrder.length !== layout.slots.length || layout.readingOrder.some(id => !layout.slots.some(s => s.id === id)))) throw new Error('Invalid reading order');
  }
}

function validateChart(value: ChartSpec): void {
  unique(value.encodings.map(e => e.channel), 'encoding channel');
  const requiredKind: Record<string, string> = { bar: 'proportionalBars', arc: 'composition', ohlc: 'ohlc', hierarchy: 'hierarchy', network: 'network', map: 'map' };
  if ((requiredKind[value.mark] ?? 'general') !== value.invariants.kind) throw new Error('Incompatible chart invariants');
  if (value.mark === 'bar' && value.encodings.some(e => e.type === 'quantitative' && (e.scale.baseline !== 0 || e.scale.type === 'log'))) throw new Error('Bars require a zero baseline');
}

function schema<T>(ref: string, refine?: (value: T) => void) {
  const validate = ajv.compile({ $ref: ref });
  return z.unknown().superRefine((value, context) => {
    if (!validate(value)) {
      for (const error of validate.errors ?? []) context.addIssue({ code: 'custom', message: error.instancePath + ' ' + error.message });
      return;
    }
    try { refine?.(value as T); } catch (error) { context.addIssue({ code: 'custom', message: (error as Error).message }); }
  }).transform(value => value as T);
}

export const DocumentGraphSchema = schema<DocumentGraph>('document-graph.schema.json', validateGraph);
export const GenerationPlanSchema = schema<GenerationPlan>('generation-plan.schema.json', value => {
  unique(value.outputModes, 'output mode'); unique(value.outline.map(s => s.id), 'outline id');
});
export const EditCommandSchema = schema<EditCommand>('edit-command.schema.json', value => {
  if (value.kind === 'insertBlock') {
    identityAndOrder(value.block);
    if (value.block.kind === 'table') validateTable(value.block.table);
    if (value.block.kind === 'chart') { validateChart(value.block.chart); validateTable(value.block.frame.tableFallback); }
  }
});
export const PresentationDocumentSchema = schema<PresentationDocument>('presentation.schema.json', validatePresentation);
export const LayoutRegistrySchema = schema<LayoutRegistry>('layout-registry.schema.json', validateRegistry);
export const MediaIntentSchema = schema<MediaIntent>('presentation.schema.json#/definitions/MediaIntent');
export const TemplatePackageSchema = schema<TemplatePackage>('template-package.schema.json', value => {
  unique(value.dependencies.map(d => d.name), 'dependency'); unique(value.licenseMetadata.map(l => l.id), 'license entry');
});
export const DatasetProfileSchema = schema<DatasetProfile>('data-visualization.schema.json#/definitions/DatasetProfile', value => {
  unique(value.fields.map(f => f.name), 'field');
  if (value.sampling.sampleSize > value.sampling.populationSize || value.fields.some(f => f.cardinality > value.rowCount || f.nullCount + f.invalidCount > value.rowCount)) throw new Error('Invalid dataset counts');
});
export const AnalyticIntentSchema = schema<AnalyticIntent>('data-visualization.schema.json#/definitions/AnalyticIntent');
export const ChartPlanSchema = schema<ChartPlan>('data-visualization.schema.json#/definitions/ChartPlan', value => unique([value.selectedCandidate.id, ...value.alternatives.map(a => a.id)], 'candidate'));
export const ChartSpecSchema = schema<ChartSpec>('data-visualization.schema.json#/definitions/ChartSpec', validateChart);
export const EncodingSpecSchema = schema<EncodingSpec>('data-visualization.schema.json#/definitions/EncodingSpec');
export const ChartFrameSchema = schema<ChartFrame>('data-visualization.schema.json#/definitions/ChartFrame', value => validateTable(value.tableFallback));
