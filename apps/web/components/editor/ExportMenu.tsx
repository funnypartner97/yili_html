"use client";

import { useState } from "react";

import { ApiClientError, type ApiClient } from "../../lib/api/client";
import type { ExportResult, QualityDiagnostic } from "../../lib/api/types";

export interface ExportMenuProps {
  api: ApiClient;
  artifactId: string;
}

interface ExportError {
  code: string;
  message: string;
  diagnostics: QualityDiagnostic[];
}

function repairHint(diagnostic: QualityDiagnostic): string | null {
  const command = diagnostic.repair?.command;
  return typeof command === "string" ? command : null;
}

/**
 * Export menu. Only `独立 HTML` is enabled in this slice; PDF and image appear
 * disabled with `后续开放`. Export runs the full quality gate first: error
 * diagnostics block the download and show their repair actions, while review
 * diagnostics can be explicitly acknowledged.
 */
export default function ExportMenu({ api, artifactId }: ExportMenuProps) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<ExportResult | null>(null);
  const [error, setError] = useState<ExportError | null>(null);

  async function runExport(acknowledgeReview: boolean) {
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const exported = await api.exportHtml(artifactId, acknowledgeReview);
      setResult(exported);
    } catch (exportError) {
      if (exportError instanceof ApiClientError) {
        setError({
          code: exportError.code,
          message: exportError.message,
          diagnostics: (exportError.details?.diagnostics as QualityDiagnostic[] | undefined) ?? [],
        });
      } else {
        setError({ code: "export_failed", message: "导出失败，请稍后重试。", diagnostics: [] });
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="export-menu">
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        导出
      </button>
      {open && (
        <div className="export-dropdown glass" role="menu" aria-label="导出格式">
          <button
            type="button"
            role="menuitem"
            disabled={busy}
            onClick={() => { setOpen(false); void runExport(false); }}
          >
            {busy ? "导出中…" : "独立 HTML"}
          </button>
          <button type="button" role="menuitem" disabled aria-disabled="true">
            PDF<span className="export-locked">后续开放</span>
          </button>
          <button type="button" role="menuitem" disabled aria-disabled="true">
            图片<span className="export-locked">后续开放</span>
          </button>
        </div>
      )}

      {result && (
        <p className="export-done" role="status">
          导出完成（版本 {result.documentVersion}）·{" "}
          <a href={result.downloadUrl} download>下载独立 HTML</a>
        </p>
      )}

      {error && (
        <div className="export-error" role="alert">
          <p>{error.message}</p>
          {error.diagnostics.length > 0 && (
            <ul className="export-diagnostics">
              {error.diagnostics.map((diagnostic, index) => (
                <li key={`${diagnostic.code}-${diagnostic.nodeId}-${index}`}>
                  {diagnostic.message}
                  {repairHint(diagnostic) && <span className="export-repair">（修复：{repairHint(diagnostic)}）</span>}
                </li>
              ))}
            </ul>
          )}
          {error.code === "quality_review_required" && (
            <button type="button" onClick={() => void runExport(true)} disabled={busy}>
              仍然导出
            </button>
          )}
        </div>
      )}
    </div>
  );
}
