import type { GenerationPlan } from "@html-office/contracts";

import type {
  ArtifactInfo, ConfirmationInfo, GenerationParametersValue, JobInfo, PlanInfo, SourceFileInfo,
} from "./types";
import { toRequestParameters } from "./types";

export class ApiClientError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiClientError";
  }
}

export interface ApiClient {
  createArtifact(title: string): Promise<ArtifactInfo>;
  uploadFile(artifactId: string, file: File): Promise<{ sourceId: string; parseStatus: "queued" }>;
  listFiles(artifactId: string): Promise<SourceFileInfo[]>;
  createPlan(artifactId: string, instruction: string, parameters: GenerationParametersValue): Promise<PlanInfo>;
  getPlan(artifactId: string, planId: string): Promise<PlanInfo>;
  updatePlan(artifactId: string, planId: string, plan: GenerationPlan): Promise<PlanInfo>;
  confirmPlan(artifactId: string, planId: string): Promise<ConfirmationInfo>;
  getJob(jobId: string): Promise<JobInfo>;
  getArtifact(artifactId: string): Promise<ArtifactInfo>;
}

type FetchLike = (input: string, init?: RequestInit) => Promise<Response>;

export function createApi(baseUrl = "", fetchImpl: FetchLike = ((input, init) => fetch(input, init)) as FetchLike): ApiClient {
  async function request<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetchImpl(baseUrl + path, init);
    if (!response.ok) {
      let code = "http_error";
      let message = "请求失败，请稍后重试。";
      try {
        const body = (await response.json()) as { code?: string; message?: string };
        if (body.code) code = body.code;
        if (body.message) message = body.message;
      } catch {
        // Non-JSON error bodies keep the generic message.
      }
      throw new ApiClientError(code, message, response.status);
    }
    return (await response.json()) as T;
  }

  function json(path: string, method: string, body: unknown): Promise<never> {
    return request(path, {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }) as Promise<never>;
  }

  return {
    createArtifact: (title) => json("/v1/artifacts", "POST", { title }),
    uploadFile: async (artifactId, file) => {
      const form = new FormData();
      form.append("file", file);
      return request(`/v1/artifacts/${artifactId}/files`, { method: "POST", body: form });
    },
    listFiles: (artifactId) => request(`/v1/artifacts/${artifactId}/files`),
    createPlan: (artifactId, instruction, parameters) =>
      json(`/v1/artifacts/${artifactId}/plans`, "POST", {
        instruction,
        parameters: toRequestParameters(parameters),
      }),
    getPlan: (artifactId, planId) => request(`/v1/artifacts/${artifactId}/plans/${planId}`),
    updatePlan: (artifactId, planId, plan) =>
      json(`/v1/artifacts/${artifactId}/plans/${planId}`, "PUT", { plan }),
    confirmPlan: (artifactId, planId) =>
      request(`/v1/artifacts/${artifactId}/plans/${planId}/confirm`, { method: "POST" }),
    getJob: (jobId) => request(`/v1/jobs/${jobId}`),
    getArtifact: (artifactId) => request(`/v1/artifacts/${artifactId}`),
  };
}
