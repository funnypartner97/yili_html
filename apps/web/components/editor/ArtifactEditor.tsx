"use client";

import { useState } from "react";

import type { DocumentGraph } from "@html-office/contracts";

import type { ApiClient } from "../../lib/api/client";
import DocumentRenderer from "./DocumentRenderer";
import SectionNavigator from "./SectionNavigator";
import PresentationStage from "../presentation/PresentationStage";
import SemanticReadingView from "../presentation/SemanticReadingView";
import { useMeasuredViewport } from "../presentation/useMeasuredViewport";
import { useDocumentDraft, type DraftStatus } from "./useDocumentDraft";

const STATUS_LABELS: Record<DraftStatus, string> = {
  saved: "已保存",
  dirty: "未保存更改",
  saving: "保存中…",
  conflict: "版本冲突",
  error: "保存失败",
};

type EditorMode = "document" | "presentation";
type PresentationSurface = "stage" | "reading";

export interface ArtifactEditorProps {
  api: ApiClient;
  artifactId: string;
  graph: DocumentGraph;
  version: number;
}

/** Top-level editor: mode switch, autosaved draft, conflict recovery. */
export default function ArtifactEditor({ api, artifactId, graph, version }: ArtifactEditorProps) {
  const hasPresentation = graph.outputModes.includes("presentation");
  const [activeMode, setActiveMode] = useState<EditorMode>(
    hasPresentation && !graph.outputModes.includes("document") ? "presentation" : "document",
  );
  const [surface, setSurface] = useState<PresentationSurface>("stage");
  const { draft, status, errorMessage, updateBlock, loadLatest, saveAsCopy } =
    useDocumentDraft(api, artifactId, graph, version);
  const { ref: stageViewportRef, viewport } = useMeasuredViewport<HTMLDivElement>();

  return (
    <div className="artifact-editor">
      <header className="editor-toolbar glass">
        <h1>{draft.title}</h1>
        <div className="mode-switch" role="group" aria-label="视图切换">
          <button
            type="button"
            aria-pressed={activeMode === "document"}
            disabled={!draft.outputModes.includes("document")}
            onClick={() => setActiveMode("document")}
          >
            文档视图
          </button>
          <button
            type="button"
            aria-pressed={activeMode === "presentation"}
            disabled={!hasPresentation}
            onClick={() => setActiveMode("presentation")}
          >
            演示视图
          </button>
        </div>
        {activeMode === "presentation" && (
          <div className="mode-switch" role="group" aria-label="演示呈现方式">
            <button
              type="button"
              aria-pressed={surface === "stage"}
              onClick={() => setSurface("stage")}
            >
              舞台视图
            </button>
            <button
              type="button"
              aria-pressed={surface === "reading"}
              onClick={() => setSurface("reading")}
            >
              阅读视图
            </button>
          </div>
        )}
        <span className="save-status" role="status" data-status={status}>
          {STATUS_LABELS[status]}
        </span>
      </header>

      {status === "conflict" && (
        <div className="conflict-banner glass" role="alert">
          <p>文档已产生新版本</p>
          <button type="button" onClick={() => void loadLatest()}>加载最新版本</button>
          <button type="button" className="primary" onClick={() => void saveAsCopy()}>保存为副本</button>
        </div>
      )}

      {status === "error" && errorMessage && (
        <div className="conflict-banner glass" role="alert">
          <p>{errorMessage}</p>
        </div>
      )}

      <div className="editor-body">
        <aside className="editor-sidebar glass">
          <SectionNavigator graph={draft} />
        </aside>
        <div className="editor-canvas glass">
          {activeMode === "document" && (
            <DocumentRenderer graph={draft} onBlockChange={updateBlock} />
          )}
          {activeMode === "presentation" && surface === "stage" && (
            <div className="stage-viewport-host" ref={stageViewportRef}>
              <PresentationStage graph={draft} viewport={viewport} onBlockChange={updateBlock} />
            </div>
          )}
          {activeMode === "presentation" && surface === "reading" && (
            <SemanticReadingView graph={draft} />
          )}
        </div>
      </div>
    </div>
  );
}
