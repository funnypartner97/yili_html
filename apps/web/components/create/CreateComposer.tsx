"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import type { ApiClient } from "../../lib/api/client";
import type { ArtifactInfo, GenerationParametersValue, PlanInfo } from "../../lib/api/types";
import { DEFAULT_GENERATION_PARAMETERS } from "../../lib/api/types";
import FileQueue, { type QueuedFile, type QueuedFileStatus } from "./FileQueue";
import GenerationParameters from "./GenerationParameters";

const POLL_INTERVAL_MS = 2000;

interface Props {
  api: ApiClient;
  onPlanCreated?: (plan: PlanInfo) => void;
}

export default function CreateComposer({ api, onPlanCreated }: Props) {
  const [instruction, setInstruction] = useState("");
  const [parameters, setParameters] = useState<GenerationParametersValue>(DEFAULT_GENERATION_PARAMETERS);
  const [artifact, setArtifact] = useState<ArtifactInfo | null>(null);
  const [files, setFiles] = useState<QueuedFile[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const artifactRef = useRef<ArtifactInfo | null>(null);

  const mergeSources = useCallback((sources: Awaited<ReturnType<ApiClient["listFiles"]>>) => {
    setFiles((previous) => previous.map((file) => {
      const source = sources.find((item) => item.sourceId === file.id);
      if (!source) return file;
      const status: QueuedFileStatus = source.parseStatus === "queued" || source.parseStatus === "parsing"
        ? "parsing"
        : source.parseStatus;
      return { ...file, status, error: source.error?.message ?? null };
    }));
  }, []);

  const refreshSources = useCallback(async (artifactId: string) => {
    mergeSources(await api.listFiles(artifactId));
  }, [api, mergeSources]);

  useEffect(() => {
    const artifactId = artifact?.id;
    if (!artifactId || !files.some((file) => file.status === "parsing")) return;
    const timer = setInterval(() => {
      void refreshSources(artifactId).catch(() => undefined);
    }, POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [artifact?.id, files, refreshSources]);

  async function addFiles(fileList: FileList | null) {
    if (!fileList || fileList.length === 0) return;
    setError(null);
    try {
      let current = artifactRef.current;
      if (!current) {
        const title = instruction.trim().slice(0, 50) || "新创作";
        current = await api.createArtifact(title);
        artifactRef.current = current;
        setArtifact(current);
      }
      for (const file of Array.from(fileList)) {
        const localId = `${file.name}-${file.size}-${Date.now()}-${Math.random().toString(36).slice(2)}`;
        setFiles((previous) => [...previous, { id: localId, name: file.name, status: "uploading" }]);
        try {
          const { sourceId } = await api.uploadFile(current.id, file);
          setFiles((previous) => previous.map((item) =>
            item.id === localId ? { ...item, id: sourceId, status: "parsing" as QueuedFileStatus } : item));
        } catch {
          setFiles((previous) => previous.map((item) =>
            item.id === localId ? { ...item, status: "failed" as QueuedFileStatus, error: "上传失败" } : item));
        }
      }
      await refreshSources(current.id);
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : "上传失败，请重试。");
    }
  }

  async function generatePlan() {
    if (!artifact) return;
    setSubmitting(true);
    setError(null);
    try {
      const plan = await api.createPlan(artifact.id, instruction.trim(), parameters);
      onPlanCreated?.(plan);
    } catch (planError) {
      setError(planError instanceof Error ? planError.message : "生成计划失败，请重试。");
    } finally {
      setSubmitting(false);
    }
  }

  const canGenerate = instruction.trim().length > 0 && files.some((file) => file.status === "parsed");

  return (
    <main className="create-composer">
      <h1>把材料变成可编辑成果</h1>
      <label className="instruction-label" htmlFor="instruction">创作指令</label>
      <textarea
        id="instruction"
        rows={4}
        placeholder="例如：基于这份季报，为管理层生成一份汇报文档"
        value={instruction}
        onChange={(event) => setInstruction(event.target.value)}
      />

      <div className="composer-actions">
        <label className="add-materials">
          <input type="file" multiple onChange={(event) => void addFiles(event.target.files)} />
          添加材料
        </label>
        <button type="button" disabled title="模板功能即将开放">
          选择模板
        </button>
      </div>

      <FileQueue files={files} />

      <GenerationParameters value={parameters} onChange={setParameters} />

      {error && <p role="alert">{error}</p>}

      <button
        type="button"
        className="primary"
        disabled={!canGenerate || submitting}
        onClick={() => void generatePlan()}
      >
        生成计划
      </button>
    </main>
  );
}
