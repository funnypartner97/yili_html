import type { GenerationPlan } from "@html-office/contracts";

export type ArtifactStatus = "draft" | "planning" | "plan_ready" | "generating" | "editable" | "failed";
export type ParseStatus = "queued" | "parsing" | "parsed" | "failed";
export type JobStatus = "queued" | "running" | "succeeded" | "failed";

export interface ArtifactInfo {
  id: string;
  title: string;
  status: ArtifactStatus;
  sourceCount: number;
  latestVersion: number;
  createdAt: string;
  updatedAt: string;
}

export interface SourceFileInfo {
  sourceId: string;
  filename: string;
  contentType: string;
  sizeBytes: number;
  sha256: string;
  parseStatus: ParseStatus;
  error: { code: string; message: string } | null;
  createdAt: string;
  updatedAt: string;
}

export interface PlanInfo {
  id: string;
  artifactId: string;
  revision: number;
  status: "ready" | "confirmed";
  plan: GenerationPlan;
  createdAt: string;
  confirmedAt: string | null;
}

export interface ConfirmationInfo {
  jobId: string;
  planId: string;
  status: JobStatus;
}

export interface JobInfo {
  id: string;
  artifactId: string;
  status: JobStatus;
  progress: number;
  stage: string | null;
  error: { code: string; message: string; stage: string | null } | null;
  createdAt: string;
  updatedAt: string;
}

export interface GenerationParametersValue {
  outputModes: ("document" | "presentation")[];
  audience: string;
  lengthPreset: "short" | "standard" | "long";
  density: "sparse" | "balanced" | "dense";
  outputSpec: "responsive" | "fixed";
  emphasis: string[];
}

export const DEFAULT_GENERATION_PARAMETERS: GenerationParametersValue = {
  outputModes: ["document"],
  audience: "",
  lengthPreset: "standard",
  density: "balanced",
  outputSpec: "responsive",
  emphasis: [],
};

export function parametersFromPlan(plan: GenerationPlan): GenerationParametersValue {
  const modes: ("document" | "presentation")[] = [];
  for (const mode of plan.outputModes) {
    if (mode === "document" || mode === "presentation") modes.push(mode);
  }
  return {
    outputModes: modes,
    audience: plan.audience,
    lengthPreset: plan.lengthPreset,
    density: plan.density,
    outputSpec: plan.outputSpec,
    emphasis: plan.emphasis,
  };
}

export function toRequestParameters(value: GenerationParametersValue): Record<string, unknown> {
  const parameters: Record<string, unknown> = {
    outputModes: value.outputModes,
    lengthPreset: value.lengthPreset,
    density: value.density,
    outputSpec: value.outputSpec,
    emphasis: value.emphasis,
  };
  if (value.audience.trim()) parameters.audience = value.audience.trim();
  return parameters;
}
