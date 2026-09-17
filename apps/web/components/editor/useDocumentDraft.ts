"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import type { DocumentGraph } from "@html-office/contracts";

import { ApiClientError, type ApiClient } from "../../lib/api/client";

/** Autosave fires 800 ms after the last edit. */
export const AUTOSAVE_DELAY_MS = 800;

export type DraftStatus = "saved" | "dirty" | "saving" | "conflict" | "error";

export interface DocumentDraft {
  draft: DocumentGraph;
  status: DraftStatus;
  version: number;
  errorMessage: string | null;
  updateBlock: (sectionId: string, blockId: string, patch: Record<string, unknown>) => void;
  loadLatest: () => Promise<void>;
  saveAsCopy: () => Promise<void>;
}

export function useDocumentDraft(
  api: ApiClient,
  artifactId: string,
  initialGraph: DocumentGraph,
  initialVersion: number,
): DocumentDraft {
  const [draft, setDraft] = useState<DocumentGraph>(initialGraph);
  const [status, setStatus] = useState<DraftStatus>("saved");
  const [version, setVersion] = useState(initialVersion);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const draftRef = useRef(initialGraph);
  const versionRef = useRef(initialVersion);
  const autosavePausedRef = useRef(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    draftRef.current = draft;
  }, [draft]);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  const persist = useCallback(async () => {
    setStatus("saving");
    try {
      const result = await api.saveDocument(artifactId, draftRef.current, String(versionRef.current));
      versionRef.current = result.versionNumber;
      setVersion(result.versionNumber);
      setStatus("saved");
      setErrorMessage(null);
    } catch (error) {
      if (error instanceof ApiClientError && error.code === "version_conflict") {
        // Pause autosave and surface the conflict; never silently merge graphs.
        autosavePausedRef.current = true;
        setStatus("conflict");
      } else {
        setStatus("error");
        setErrorMessage(error instanceof Error ? error.message : "保存失败，请重试。");
      }
    }
  }, [api, artifactId]);

  const scheduleAutosave = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      timerRef.current = null;
      void persist();
    }, AUTOSAVE_DELAY_MS);
  }, [persist]);

  const updateBlock = useCallback(
    (sectionId: string, blockId: string, patch: Record<string, unknown>) => {
      setDraft((previous) => ({
        ...previous,
        // map() preserves length, so the non-empty sections tuple stays valid.
        sections: previous.sections.map((section) => {
          if (section.id !== sectionId) return section;
          return {
            ...section,
            blocks: section.blocks.map((block) =>
              block.id === blockId ? ({ ...block, ...patch } as typeof block) : block,
            ),
          };
        }) as typeof previous.sections,
      }));
      if (autosavePausedRef.current) return;
      setStatus((current) => (current === "conflict" ? current : "dirty"));
      scheduleAutosave();
    },
    [scheduleAutosave],
  );

  const loadLatest = useCallback(async () => {
    const [latestGraph, artifact] = await Promise.all([
      api.getDocument(artifactId),
      api.getArtifact(artifactId),
    ]);
    autosavePausedRef.current = false;
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    draftRef.current = latestGraph;
    versionRef.current = artifact.latestVersion;
    setDraft(latestGraph);
    setVersion(artifact.latestVersion);
    setStatus("saved");
    setErrorMessage(null);
  }, [api, artifactId]);

  const saveAsCopy = useCallback(async () => {
    // Keep the local edits as a brand-new version on top of whatever arrived
    // from the server: refresh the precondition, then save the local draft.
    const artifact = await api.getArtifact(artifactId);
    autosavePausedRef.current = false;
    versionRef.current = artifact.latestVersion;
    setVersion(artifact.latestVersion);
    await persist();
  }, [api, artifactId, persist]);

  return { draft, status, version, errorMessage, updateBlock, loadLatest, saveAsCopy };
}
