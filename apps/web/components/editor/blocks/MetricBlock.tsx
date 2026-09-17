import type { Block } from "@html-office/contracts";

export default function MetricBlock({ block }: { block: Extract<Block, { kind: "metric" }> }) {
  return (
    <div className="metric-block" aria-label={block.label}>
      <span className="metric-value">
        {block.value}
        {block.unit && <span className="metric-unit">{block.unit}</span>}
      </span>
      <span className="metric-label">{block.label}</span>
    </div>
  );
}
