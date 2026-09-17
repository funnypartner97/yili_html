"use client";

import { useState } from "react";

import type { ApiClient, DocumentSaveResult } from "../../lib/api/client";
import type { EditPreviewInfo } from "../../lib/api/types";
import EditPreview from "./EditPreview";

export interface AIAssistantPanelProps {
  api: ApiClient;
  artifactId: string;
  baseVersion: number;
  selectedBlockIds?: string[];
  onApplied?: (result: DocumentSaveResult) => void;
  onUndone?: (result: DocumentSaveResult) => void;
}

type Busy = "preview" | "apply" | "undo" | null;

/**
 * Right-side AI assistant. The user describes an edit, always sees the proposed
 * summary and affected blocks first, and only then applies it. Applying creates a
 * new immutable version; the prior version can be restored with one undo.
 */
export default function AIAssistantPanel({
  api, artifactId, baseVersion, selectedBlockIds = [], onApplied, onUndone,
}: AIAssistantPanelProps) {
  const [instruction, setInstruction] = useState("");
  const [preview, setPreview] = useState<EditPreviewInfo | null>(null);
  const [applied, setApplied] = useState<DocumentSaveResult | null>(null);
  const [busy, setBusy] = useState<Busy>(null);
  const [error, setError] = useState<string | null>(null);

  async function handlePreview() {
    setBusy("preview");
    setError(null);
    setApplied(null);
    try {
      const result = await api.previewEdit(artifactId, instruction.trim(), selectedBlockIds);
      setPreview(result);
    } catch (previewError) {
      setPreview(null);
      setError(previewError instanceof Error ? previewError.message : "生成预览失败，请重试。");
    } finally {
      setBusy(null);
    }
  }

  async function handleApply() {
    if (!preview) return;
    setBusy("apply");
    setError(null);
    try {
      const result = await api.applyEdit(artifactId, preview.previewId);
      setApplied(result);
      setPreview(null);
      setInstruction("");
      onApplied?.(result);
    } catch (applyError) {
      setError(applyError instanceof Error ? applyError.message : "应用修改失败，请重试。");
    } finally {
      setBusy(null);
    }
  }

  async function handleUndo() {
    setBusy("undo");
    setError(null);
    try {
      // Undo restores the version the AI edit was based on.
      const result = await api.restoreVersion(artifactId, baseVersion);
      setApplied(null);
      onUndone?.(result);
    } catch (undoError) {
      setError(undoError instanceof Error ? undoError.message : "撤销失败，请重试。");
    } finally {
      setBusy(null);
    }
  }

  function handleCancel() {
    setPreview(null);
    setError(null);
  }

  return (
    <aside className="ai-assistant-panel glass" aria-label="AI 修改助手">
      <h2>AI 修改</h2>
      <label className="ai-instruction-label" htmlFor="ai-instruction">修改指令</label>
      <textarea
        id="ai-instruction"
        aria-label="修改指令"
        value={instruction}
        rows={3}
        placeholder="例如：把执行摘要改写得更简洁"
        onChange={(event) => setInstruction(event.target.value)}
      />
      {selectedBlockIds.length > 0 && (
        <p className="ai-selection">已选择 {selectedBlockIds.length} 个内容块</p>
      )}

      <div className="ai-actions">
        <button
          type="button"
          onClick={() => void handlePreview()}
          disabled={busy !== null || !instruction.trim()}
        >
          {busy === "preview" ? "生成中…" : "生成预览"}
        </button>
        {preview && (
          <button type="button" onClick={handleCancel} disabled={busy !== null}>取消</button>
        )}
      </div>

      {error && <p role="alert" className="ai-error">{error}</p>}

      {preview && <EditPreview preview={preview} />}

      {!applied && (
        <button
          type="button"
          className="primary ai-apply"
          onClick={() => void handleApply()}
          disabled={busy !== null || !preview}
        >
          {busy === "apply" ? "应用中…" : "应用修改"}
        </button>
      )}

      {applied && (
        <div className="ai-applied">
          <p role="status">修改已应用，当前版本 {applied.versionNumber}。</p>
          <button type="button" onClick={() => void handleUndo()} disabled={busy !== null}>
            {busy === "undo" ? "撤销中…" : "撤销本次修改"}
          </button>
        </div>
      )}
    </aside>
  );
}
