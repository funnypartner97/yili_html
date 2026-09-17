import type { DocumentGraph } from "@html-office/contracts";

/** Anchor navigation across the document's sections. */
export default function SectionNavigator({ graph }: { graph: DocumentGraph }) {
  const sections = [...graph.sections].sort((a, b) => a.order - b.order);
  return (
    <nav className="section-navigator" aria-label="章节导航">
      <ol>
        {sections.map((section, index) => (
          <li key={section.id}>
            <a href={`#section-${section.id}`}>{section.title || `第 ${index + 1} 节`}</a>
          </li>
        ))}
      </ol>
    </nav>
  );
}
