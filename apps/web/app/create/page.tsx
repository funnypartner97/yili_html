"use client";

import { useRouter } from "next/navigation";

import CreateComposer from "../../components/create/CreateComposer";
import { createApi } from "../../lib/api/client";

export default function CreatePage() {
  const router = useRouter();
  return (
    <CreateComposer
      api={createApi()}
      onPlanCreated={(plan) => router.push(`/artifacts/${plan.artifactId}/plan?planId=${plan.id}`)}
    />
  );
}
