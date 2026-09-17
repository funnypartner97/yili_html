import type { Block, DocumentGraph } from "@html-office/contracts";

export default function ImageBlock(
  { block, graph }: { block: Extract<Block, { kind: "image" }>; graph: DocumentGraph },
) {
  const asset = graph.assets.find((item) => item.id === block.assetId);
  const alt = asset?.mediaIntent.alt ?? "图片素材";
  const caption = asset?.mediaIntent.caption;
  return (
    <figure className="image-block" aria-label={alt}>
      <div role="img" aria-label={alt} className="image-placeholder">{alt}</div>
      <span className="image-alt">{alt}</span>
      {caption && <figcaption>{caption}</figcaption>}
    </figure>
  );
}
