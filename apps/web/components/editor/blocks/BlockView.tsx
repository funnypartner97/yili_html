import type { Block, DocumentGraph } from "@html-office/contracts";

import ChartBlock from "./ChartBlock";
import ImageBlock from "./ImageBlock";
import MetricBlock from "./MetricBlock";
import RichTextBlock from "./RichTextBlock";
import TableBlock from "./TableBlock";

export interface BlockViewProps {
  graph: DocumentGraph;
  block: Block;
  label: string;
  editable?: boolean;
  onBlockChange?: (sectionId: string, blockId: string, patch: Record<string, unknown>) => void;
  sectionId?: string;
}

/** Dispatches a contract block to its editor component. */
export default function BlockView({
  graph, block, label, editable = true, onBlockChange, sectionId,
}: BlockViewProps) {
  switch (block.kind) {
    case "richText":
      return (
        <RichTextBlock
          key={block.id}
          text={block.text}
          label={label}
          editable={editable}
          onChangeText={
            onBlockChange && sectionId
              ? (text) => onBlockChange(sectionId, block.id, { text })
              : undefined
          }
        />
      );
    case "table":
      return <TableBlock key={block.id} block={block} />;
    case "metric":
      return <MetricBlock key={block.id} block={block} />;
    case "chart":
      return <ChartBlock key={block.id} block={block} />;
    case "image":
      return <ImageBlock key={block.id} block={block} graph={graph} />;
  }
}
