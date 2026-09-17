import type { EditPreviewInfo, EditSummaryEntry } from "../../lib/api/types";

const KIND_LABELS: Record<string, string> = {
  replaceText: "替换文本",
  insertBlock: "新增内容块",
  removeBlock: "删除内容块",
  moveBlock: "移动内容块",
  setTheme: "更换主题",
};

function describe(entry: EditSummaryEntry): string {
  const label = KIND_LABELS[entry.kind] ?? entry.kind;
  if (entry.kind === "replaceText") {
    const before = entry.before ?? "";
    const after = entry.after ?? "";
    return `${label}：“${before.slice(0, 24)}${before.length > 24 ? "…" : ""}” → “${after.slice(0, 24)}${after.length > 24 ? "…" : ""}”`;
  }
  if (entry.kind === "setTheme") return `${label}：${entry.after ?? ""}`;
  return label;
}

export interface EditPreviewProps {
  preview: EditPreviewInfo;
}

/**
 * Read-only view of a proposed AI edit: the summary of every command and the
 * affected blocks. Shown before `应用修改` is enabled so nothing is applied
 * without the user seeing exactly what will change.
 */
export default function EditPreview({ preview }: EditPreviewProps) {
  return (
    <div className="edit-preview glass" aria-label="修改预览">
      <p className="edit-preview-heading">将做以下修改（基于版本 {preview.baseVersion}）：</p>
      <ul className="edit-preview-list">
        {preview.summary.map((entry, index) => (
          <li key={`${entry.kind}-${entry.blockId ?? index}`}>
            <span className="edit-kind">{KIND_LABELS[entry.kind] ?? entry.kind}</span>
            <span className="edit-detail">{describe(entry)}</span>
          </li>
        ))}
      </ul>
      <p className="edit-preview-affected">
        影响 {preview.affectedBlockIds.length} 个内容块
      </p>
    </div>
  );
}
