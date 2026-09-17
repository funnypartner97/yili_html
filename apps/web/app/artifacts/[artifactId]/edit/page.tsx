"use client";

import { useParams } from "next/navigation";

import ArtifactEditor from "../../../../components/editor/ArtifactEditor";
import { createApi } from "../../../../lib/api/client";
import { useEditorDocument } from "../../../../lib/api/hooks";

function EditPageContent({ artifactId }: { artifactId: string }) {
  const api = createApi();
  const { graph, version, error } = useEditorDocument(api, artifactId);
  if (error) return <p role="alert">无法加载文档，请刷新重试。</p>;
  if (!graph) return <p className="loading-note">正在加载文档……</p>;
  return <ArtifactEditor api={api} artifactId={artifactId} graph={graph} version={version} />;
}

export default function EditPage() {
  const params = useParams<{ artifactId: string }>();
  return <EditPageContent artifactId={params.artifactId} />;
}
