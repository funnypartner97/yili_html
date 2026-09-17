"use client";

import { useCallback, useEffect, useState } from "react";

import type { ApiClient, DocumentSaveResult } from "../../lib/api/client";
import type { VersionInfo, VersionOrigin } from "../../lib/api/types";

const ORIGIN_LABELS: Record<VersionOrigin, string> = {
  generation: "初始生成",
  manual: "手动编辑",
  ai: "AI 修改",
  restore: "版本恢复",
};

export interface VersionHistoryProps {
  api: ApiClient;
  artifactId: string;
  /** Bump to force a reload after a save, apply, or restore elsewhere. */
  refreshKey?: number;
  currentVersion?: number;
  onRestored?: (result: DocumentSaveResult) => void;
}

/** Immutable version ledger with one-click restore to any historical graph. */
export default function VersionHistory({
  api, artifactId, refreshKey = 0, currentVersion, onRestored,
}: VersionHistoryProps) {
  const [versions, setVersions] = useState<VersionInfo[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busyVersion, setBusyVersion] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const result = await api.listVersions(artifactId);
        if (!cancelled) {
          setVersions(result.versions);
          setError(null);
        }
      } catch (loadError) {
        if (!cancelled) setError(loadError instanceof Error ? loadError.message : "加载版本失败");
      }
    };
    void load();
    return () => { cancelled = true; };
  }, [api, artifactId, refreshKey]);

  const restore = useCallback(async (version: number) => {
    setBusyVersion(version);
    setError(null);
    try {
      const result = await api.restoreVersion(artifactId, version);
      const refreshed = await api.listVersions(artifactId);
      setVersions(refreshed.versions);
      onRestored?.(result);
    } catch (restoreError) {
      setError(restoreError instanceof Error ? restoreError.message : "恢复失败，请重试。");
    } finally {
      setBusyVersion(null);
    }
  }, [api, artifactId, onRestored]);

  return (
    <div className="version-history glass" role="region" aria-label="版本历史">
      <h2>版本历史</h2>
      {error && <p role="alert">{error}</p>}
      <ol className="version-list">
        {versions.map((version) => (
          <li key={version.versionNumber} data-origin={version.origin}>
            <span className="version-number">版本 {version.versionNumber}</span>
            <span className="version-origin">{ORIGIN_LABELS[version.origin]}</span>
            {version.versionNumber === currentVersion && <span className="version-current">当前</span>}
            <button
              type="button"
              aria-label={`恢复到版本 ${version.versionNumber}`}
              onClick={() => void restore(version.versionNumber)}
              disabled={busyVersion !== null || version.versionNumber === currentVersion}
            >
              恢复
            </button>
          </li>
        ))}
      </ol>
    </div>
  );
}
