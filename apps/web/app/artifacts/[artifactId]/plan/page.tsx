"use client";

import { useParams, useSearchParams } from "next/navigation";
import { Suspense } from "react";

import PlanReview from "../../../../components/create/PlanReview";
import { createApi } from "../../../../lib/api/client";
import { usePlan } from "../../../../lib/api/hooks";

function PlanPageContent({ artifactId, planId }: { artifactId: string; planId: string }) {
  const { plan, error } = usePlan(createApi(), artifactId, planId);
  if (error) return <p role="alert">无法加载计划，请返回重新创建。</p>;
  if (!plan) return <p>正在加载计划……</p>;
  return <PlanReview api={createApi()} plan={plan} />;
}

function RoutedPlanPage() {
  const params = useParams<{ artifactId: string }>();
  const planId = useSearchParams().get("planId");
  if (!planId) return <p role="alert">缺少计划参数，请返回重新创建。</p>;
  return <PlanPageContent artifactId={params.artifactId} planId={planId} />;
}

export default function PlanPage() {
  return (
    <Suspense fallback={<p>正在加载计划……</p>}>
      <RoutedPlanPage />
    </Suspense>
  );
}
