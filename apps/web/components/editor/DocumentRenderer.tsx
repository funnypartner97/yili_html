import type { Block, DocumentGraph } from "@html-office/contracts";

import BlockView from "./blocks/BlockView";

export interface DocumentRendererProps {
  graph: DocumentGraph;
  editable?: boolean;
  onBlockChange?: (sectionId: string, blockId: string, patch: Record<string, unknown>) => void;
}

function blockLabel(sectionTitle: string, block: Block, blocks: Block[]): string {
  const sameKind = blocks.filter((item) => item.kind === block.kind);
  const index = sameKind.indexOf(block);
  return sameKind.length > 1 ? `${sectionTitle} 第${index + 1}段` : sectionTitle;
}

/** Normal-flow document rendering with direct block editing. */
export default function DocumentRenderer({ graph, editable = true, onBlockChange }: DocumentRendererProps) {
  const orderedSections = [...graph.sections].sort((a, b) => a.order - b.order);
  return (
    <article className="document-view">
      {orderedSections.map((section) => {
        const blocks = [...section.blocks].sort((a, b) => a.order - b.order);
        return (
          <section
            key={section.id}
            id={`section-${section.id}`}
            className="document-section"
            aria-labelledby={`heading-${section.id}`}
          >
            <h2 id={`heading-${section.id}`}>{section.title}</h2>
            <div className="document-blocks">
              {blocks.map((block) => (
                <BlockView
                  key={block.id}
                  graph={graph}
                  block={block}
                  label={blockLabel(section.title || `第 ${section.order + 1} 节`, block, blocks)}
                  editable={editable}
                  onBlockChange={onBlockChange}
                  sectionId={section.id}
                />
              ))}
            </div>
          </section>
        );
      })}
    </article>
  );
}
