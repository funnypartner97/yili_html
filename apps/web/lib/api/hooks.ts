"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { ApiClient } from "./client";
import type { GenerationParametersValue, JobInfo, PlanInfo } from "./types";

const JOB_POLL_INTERVAL_MS = 2000;

export function useArtifact(api: ApiClient, artifactId: string | null) {
  return useQuery({
    queryKey: ["artifact", artifactId],
    queryFn: () => api.getArtifact(artifactId as string),
    enabled: artifactId !== null,
  });
}

export function useFiles(api: ApiClient, artifactId: string | null) {
  return useQuery({
    queryKey: ["files", artifactId],
    queryFn: () => api.listFiles(artifactId as string),
    enabled: artifactId !== null,
    refetchInterval: (query) =>
      query.state.data?.some((file) => file.parseStatus === "queued" || file.parseStatus === "parsing")
        ? JOB_POLL_INTERVAL_MS
        : false,
  });
}

export function usePlan(api: ApiClient, artifactId: string, planId: string) {
  const query = useQuery({
    queryKey: ["plan", artifactId, planId],
    queryFn: () => api.getPlan(artifactId, planId),
  });
  return { plan: query.data, error: query.error };
}

export function useJob(api: ApiClient, jobId: string | null): { job: JobInfo | undefined } {
  const query = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => api.getJob(jobId as string),
    enabled: jobId !== null,
    refetchInterval: (query) =>
      query.state.data?.status === "queued" || query.state.data?.status === "running"
        ? JOB_POLL_INTERVAL_MS
        : false,
  });
  return { job: query.data };
}

export function useCreatePlan(api: ApiClient, onCreated: (plan: PlanInfo) => void) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ artifactId, instruction, parameters }: {
      artifactId: string;
      instruction: string;
      parameters: GenerationParametersValue;
    }) => api.createPlan(artifactId, instruction, parameters),
    onSuccess: (plan) => {
      queryClient.setQueryData(["artifact", plan.artifactId], (artifact) => artifact);
      onCreated(plan);
    },
  });
}

export function useConfirmPlan(api: ApiClient, onConfirmed: (confirmation: { jobId: string }) => void) {
  return useMutation({
    mutationFn: ({ artifactId, planId }: { artifactId: string; planId: string }) =>
      api.confirmPlan(artifactId, planId),
    onSuccess: onConfirmed,
  });
}
