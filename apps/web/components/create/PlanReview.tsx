"use client";

import { useEffect, useState } from "react";

import type { ApiClient } from "../../lib/api/client";
import type { JobInfo, PlanInfo } from "../../lib/api/types";
import { parametersFromPlan } from "../../lib/api/types";
import GenerationParameters from "./GenerationParameters";
import GenerationProgress from "./GenerationProgress";

const POLL_INTERVAL_MS = 2000;

const MODE_LABELS: Record<string, string> = {
  document: "文档",
  presentation: "演示",
  data: "数据",
  dashboard: "看板",
};

const LENGTH_LABELS: Record<string, string> = { short: "精简", standard: "标准", long: "详尽" };
const DENSITY_LABELS: Record<string, string> = { sparse: "疏朗", balanced: "均衡", dense: "紧凑" };
const SPEC_LABELS: Record<string, string> = { responsive: "自适应", fixed: "固定" };

interface Props {
  api: ApiClient;
  plan: PlanInfo;
  onRestart?: () => void;
}

export default function PlanReview({ api, plan, onRestart }: Props) {
  const [current, setCurrent] = useState(plan);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(() => parametersFromPlan(plan.plan));
  const [jobId, setJobId] = useState<string | null>(null);
  const [job, setJob] = useState<JobInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!jobId) return;
    let cancelled = false;
    const tick = async () => {
      try {
        const next = await api.getJob(jobId);
        if (cancelled) return;
        setJob(next);
        if (next.status === "queued" || next.status === "running") {
          setTimeout(() => void tick(), POLL_INTERVAL_MS);
        }
      } catch {
        if (!cancelled) setError("无法获取生成进度，请刷新重试。");
      }
    };
    void tick();
    return () => { cancelled = true; };
  }, [api, jobId]);

  async function saveEdits() {
    setBusy(true);
    setError(null);
    try {
      const modes = draft.outputModes.length > 0
        ? draft.outputModes
        : [current.plan.outputModes[0]];
      const updated = await api.updatePlan(current.artifactId, current.id, {
        ...current.plan,
        outputModes: modes as PlanInfo["plan"]["outputModes"],
        audience: draft.audience.trim() || current.plan.audience,
        lengthPreset: draft.lengthPreset,
        density: draft.density,
        outputSpec: draft.outputSpec,
        emphasis: draft.emphasis,
      });
      setCurrent(updated);
      setEditing(false);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "保存修改失败，请重试。");
    } finally {
      setBusy(false);
    }
  }

  async function confirmAndGenerate() {
    setBusy(true);
    setError(null);
    try {
      const confirmation = await api.confirmPlan(current.artifactId, current.id);
      setJobId(confirmation.jobId);
    } catch (confirmError) {
      setError(confirmError instanceof Error ? confirmError.message : "确认失败，请重试。");
    } finally {
      setBusy(false);
    }
  }

  if (jobId && job) {
    if (job.status === "succeeded") {
      return (
        <section aria-label="生成完成">
          <h2>生成完成</h2>
          <GenerationProgress job={job} />
          <a className="primary" href={`/artifacts/${current.artifactId}/edit`}>打开编辑器</a>
        </section>
      );
    }
    if (job.status === "failed") {
      return (
        <section aria-label="生成失败">
          <h2>生成失败</h2>
          <p role="alert">{job.error?.message ?? "生成失败。"}</p>
          <GenerationProgress job={job} />
          <button type="button" className="primary" onClick={onRestart ?? (() => setJobId(null))}>
            重新创建计划
          </button>
        </section>
      );
    }
    return (
      <section aria-label="生成中">
        <h2>正在生成</h2>
        <GenerationProgress job={job} />
      </section>
    );
  }

  const summary = current.plan.sourceSummary;
  return (
    <main className="plan-review">
      <h1>确认生成计划</h1>

      <section aria-label="计划摘要">
        <h2>产物形式</h2>
        <p>{current.plan.outputModes.map((mode) => MODE_LABELS[mode] ?? mode).join(" + ")}</p>

        <h2>内容大纲</h2>
        <ol>
          {current.plan.outline.map((item) => <li key={item.id}>{item.title}</li>)}
        </ol>

        <h2>材料摘要</h2>
        <p>已解析材料 {summary.parsed} 份{summary.failed > 0 ? `，${summary.failed} 个材料解析失败` : ""}。</p>
        {summary.conflicts.length > 0 && (
          <ul>
            {summary.conflicts.map((conflict) => <li key={conflict}>{conflict}</li>)}
          </ul>
        )}

        <h2>推断设置</h2>
        <dl>
          <div><dt>受众</dt><dd>{current.plan.audience}</dd></div>
          <div><dt>篇幅</dt><dd>{LENGTH_LABELS[current.plan.lengthPreset]}</dd></div>
          <div><dt>信息密度</dt><dd>{DENSITY_LABELS[current.plan.density]}</dd></div>
          <div><dt>输出规格</dt><dd>{SPEC_LABELS[current.plan.outputSpec]}</dd></div>
          {current.plan.emphasis.length > 0 && (
            <div><dt>侧重点</dt><dd>{current.plan.emphasis.join("；")}</dd></div>
          )}
        </dl>
      </section>

      {editing ? (
        <section aria-label="编辑设置">
          <GenerationParameters value={draft} onChange={setDraft} />
          <button type="button" disabled={busy} onClick={() => void saveEdits()}>保存修改</button>
          <button type="button" disabled={busy} onClick={() => setEditing(false)}>取消</button>
        </section>
      ) : (
        <button type="button" onClick={() => setEditing(true)}>编辑设置</button>
      )}

      {error && <p role="alert">{error}</p>}

      <p className="confirmation-note">确认后将按此计划生成，生成过程中可随时查看进度。</p>
      <button
        type="button"
        className="primary"
        disabled={busy || current.status === "confirmed"}
        onClick={() => void confirmAndGenerate()}
      >
        确认并生成
      </button>
    </main>
  );
}
