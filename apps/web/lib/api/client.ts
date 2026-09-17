import type { DocumentGraph, GenerationPlan } from "@html-office/contracts";

import type {
  ArtifactInfo, ConfirmationInfo, EditPreviewInfo, GenerationParametersValue, JobInfo, PlanInfo,
  SourceFileInfo, VersionInfo,
} from "./types";
import { toRequestParameters } from "./types";

export class ApiClientError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly status: number,
    public readonly details?: Record<string, unknown>,
  ) {
    super(message);
    this.name = "ApiClientError";
  }
}

export interface DocumentSaveResult {
  versionNumber: number;
  savedAt: string;
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
  getDocument(artifactId: string): Promise<DocumentGraph>;
  saveDocument(artifactId: string, graph: DocumentGraph, ifMatch: string): Promise<DocumentSaveResult>;
  previewEdit(artifactId: string, instruction: string, blockIds: string[]): Promise<EditPreviewInfo>;
  applyEdit(artifactId: string, previewId: string): Promise<DocumentSaveResult>;
  listVersions(artifactId: string): Promise<{ versions: VersionInfo[] }>;
  restoreVersion(artifactId: string, version: number): Promise<DocumentSaveResult>;
}

type FetchLike = (input: string, init?: RequestInit) => Promise<Response>;

export function createApi(baseUrl = "", fetchImpl: FetchLike = ((input, init) => fetch(input, init)) as FetchLike): ApiClient {
  async function request<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetchImpl(baseUrl + path, init);
    if (!response.ok) {
      let code = "http_error";
      let message = "请求失败，请稍后重试。";
      let details: Record<string, unknown> | undefined;
      try {
        const body = (await response.json()) as { code?: string; message?: string; details?: Record<string, unknown> };
        if (body.code) code = body.code;
        if (body.message) message = body.message;
        if (body.details) details = body.details;
      } catch {
        // Non-JSON error bodies keep the generic message.
      }
      throw new ApiClientError(code, message, response.status, details);
    }
    return (await response.json()) as T;
  }

  function json<T>(path: string, method: string, body: unknown, headers?: Record<string, string>): Promise<T> {
    return request<T>(path, {
      method,
      headers: { "Content-Type": "application/json", ...headers },
      body: JSON.stringify(body),
    });
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
    getDocument: (artifactId) => request(`/v1/artifacts/${artifactId}/document`),
    saveDocument: (artifactId, graph, ifMatch) =>
      json(`/v1/artifacts/${artifactId}/document`, "PUT", graph, { "If-Match": ifMatch }),
    previewEdit: (artifactId, instruction, blockIds) =>
      json(`/v1/artifacts/${artifactId}/edits/preview`, "POST", { instruction, blockIds }),
    applyEdit: (artifactId, previewId) =>
      request(`/v1/artifacts/${artifactId}/edits/${previewId}/apply`, { method: "POST" }),
    listVersions: (artifactId) => request(`/v1/artifacts/${artifactId}/versions`),
    restoreVersion: (artifactId, version) =>
      request(`/v1/artifacts/${artifactId}/versions/${version}/restore`, { method: "POST" }),
  };
}
