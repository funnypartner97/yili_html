export type QueuedFileStatus = "uploading" | "parsing" | "parsed" | "failed";

export interface QueuedFile {
  id: string;
  name: string;
  status: QueuedFileStatus;
  error?: string | null;
}

const STATUS_LABELS: Record<QueuedFileStatus, string> = {
  uploading: "上传中",
  parsing: "解析中",
  parsed: "已解析",
  failed: "解析失败",
};

export default function FileQueue({ files }: { files: QueuedFile[] }) {
  if (files.length === 0) return null;
  return (
    <ul aria-label="材料队列">
      {files.map((file) => (
        <li key={file.id} data-status={file.status}>
          <span>{file.name}</span>
          <span>{file.error ?? STATUS_LABELS[file.status]}</span>
        </li>
      ))}
    </ul>
  );
}
