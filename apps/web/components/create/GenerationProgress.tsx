import type { JobInfo } from "../../lib/api/types";

const STAGES = [
  { id: "loading_sources", label: "加载材料" },
  { id: "generating_structure", label: "构建结构" },
  { id: "generating_content", label: "生成内容" },
  { id: "validating_document", label: "校验文档" },
  { id: "saving_version", label: "保存版本" },
] as const;

export default function GenerationProgress({ job }: { job: JobInfo }) {
  const currentIndex = STAGES.findIndex((stage) => stage.id === job.stage);
  return (
    <section aria-label="生成进度">
      <progress
        role="progressbar"
        aria-valuenow={job.progress}
        aria-valuemin={0}
        aria-valuemax={100}
        value={job.progress}
        max={100}
      />
      <ol>
        {STAGES.map((stage, index) => {
          const state = job.status === "succeeded" || (currentIndex >= 0 && index < currentIndex)
            ? "stage-done"
            : index === currentIndex ? "stage-current" : "stage-pending";
          return <li key={stage.id} className={state}>{stage.label}</li>;
        })}
      </ol>
    </section>
  );
}
