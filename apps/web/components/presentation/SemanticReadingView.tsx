import type { Block, DocumentGraph, TableData } from "@html-office/contracts";

export interface SemanticReadingViewProps {
  graph: DocumentGraph;
  lang?: string;
}

function cellText(value: string | number | boolean | null): string {
  return value === null ? "" : String(value);
}

/** A semantic HTML table with column headers and an accessible name. */
function SemanticTable({ table, name }: { table: TableData; name?: string }) {
  return (
    <table className="reading-table" aria-label={name}>
      <thead>
        <tr>
          {table.columns.map((column) => (
            <th key={column} scope="col">{column}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {table.rows.map((row, rowIndex) => (
          // Rows carry no stable identity in the contract; positional keys are safe here.
          <tr key={rowIndex}>
            {row.map((cell, cellIndex) => (
              <td key={cellIndex}>{cellText(cell)}</td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function RichText({ text }: { text: string }) {
  const paragraphs = text.split("\n").map((line) => line.trim()).filter(Boolean);
  if (paragraphs.length === 0) return <p className="reading-empty">（空）</p>;
  return (
    <>
      {paragraphs.map((paragraph, index) => (
        <p key={index} className="reading-paragraph">{paragraph}</p>
      ))}
    </>
  );
}

function SemanticBlock({ block, sectionTitle }: { block: Block; sectionTitle: string }) {
  switch (block.kind) {
    case "richText":
      return <RichText text={block.text} />;
    case "table":
      return <SemanticTable table={block.table} name={`${sectionTitle} 数据表`} />;
    case "metric":
      return (
        <p className="reading-metric">
          <strong>{block.label}</strong>
          {`：${block.value}${block.unit ?? ""}`}
        </p>
      );
    case "chart":
      return (
        <figure className="reading-chart">
          <figcaption className="reading-chart-caption">{block.frame.title}</figcaption>
          <p className="reading-chart-summary">{block.chart.semanticExplanation}</p>
          {block.frame.claim && <p className="reading-chart-claim">{block.frame.claim}</p>}
          <SemanticTable table={block.frame.tableFallback} name={block.frame.title} />
          <p className="reading-chart-asof">数据截至 {block.frame.asOf}</p>
        </figure>
      );
    case "image":
      return (
        <figure className="reading-image">
          <div role="img" aria-label={block.assetId}>图片：{block.assetId}</div>
        </figure>
      );
    default:
      return null;
  }
}

/**
 * A separate, reflowed semantic reading surface. This is its own DOM tree — not a
 * visually hidden copy of the fixed stage — and it ignores presentation
 * coordinates entirely. Content is emitted in the document's semantic reading
 * order (section order, then block order) with real headings, lists, figures and
 * captions, semantic tables with headers, and chart summaries plus table
 * fallbacks. It supports browser zoom, keyboard traversal, accessible names, and
 * an explicit `lang`.
 */
export default function SemanticReadingView({ graph, lang = "zh-CN" }: SemanticReadingViewProps) {
  const sections = [...graph.sections].sort((a, b) => a.order - b.order);
  return (
    <article className="semantic-reading-view" aria-label={graph.title} lang={lang} tabIndex={-1}>
      <header className="reading-header">
        <h1>{graph.title}</h1>
      </header>
      {sections.map((section, sectionIndex) => {
        const blocks = [...section.blocks].sort((a, b) => a.order - b.order);
        const heading = section.title || `第 ${sectionIndex + 1} 节`;
        const headingId = `reading-heading-${section.id}`;
        return (
          <section key={section.id} className="reading-section" aria-labelledby={headingId}>
            <h2 id={headingId}>{heading}</h2>
            {blocks.map((block) => (
              <SemanticBlock key={block.id} block={block} sectionTitle={heading} />
            ))}
          </section>
        );
      })}
    </article>
  );
}
