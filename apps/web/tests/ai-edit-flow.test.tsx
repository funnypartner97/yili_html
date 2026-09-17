import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import AIAssistantPanel from "../components/editor/AIAssistantPanel";
import VersionHistory from "../components/editor/VersionHistory";
import { ApiClientError, type ApiClient } from "../lib/api/client";
import type { EditPreviewInfo } from "../lib/api/types";

function previewFixture(overrides: Partial<EditPreviewInfo> = {}): EditPreviewInfo {
  return {
    previewId: "01993f2f-2b79-7000-8000-0000000000aa",
    baseVersion: 1,
    commands: [{ kind: "replaceText", blockId: "b1", text: "新的执行摘要" }],
    summary: [{ kind: "replaceText", blockId: "b1", before: "旧的执行摘要", after: "新的执行摘要" }],
    affectedBlockIds: ["b1"],
    expiresAt: "2026-09-16T02:00:00Z",
    ...overrides,
  };
}

function fakeApi(overrides: Partial<ApiClient> = {}): ApiClient {
  return {
    previewEdit: vi.fn().mockResolvedValue(previewFixture()),
    applyEdit: vi.fn().mockResolvedValue({ versionNumber: 2, savedAt: "2026-09-16T01:00:00Z" }),
    restoreVersion: vi.fn().mockResolvedValue({ versionNumber: 3, savedAt: "2026-09-16T01:30:00Z" }),
    listVersions: vi.fn().mockResolvedValue({
      versions: [
        { versionNumber: 2, origin: "ai", createdAt: "2026-09-16T01:00:00Z" },
        { versionNumber: 1, origin: "generation", createdAt: "2026-09-16T00:00:00Z" },
      ],
    }),
    ...overrides,
  } as unknown as ApiClient;
}

async function openPreview(api: ApiClient, instruction = "改写执行摘要", selected?: string[]) {
  render(
    <AIAssistantPanel api={api} artifactId="artifact-1" baseVersion={1} selectedBlockIds={selected} />,
  );
  await userEvent.type(screen.getByLabelText("修改指令"), instruction);
  await userEvent.click(screen.getByRole("button", { name: "生成预览" }));
  await screen.findByText(/将做以下修改/);
}

describe("AIAssistantPanel", () => {
  it("keeps apply disabled until a preview exists", () => {
    render(<AIAssistantPanel api={fakeApi()} artifactId="artifact-1" baseVersion={1} />);
    expect(screen.getByRole("button", { name: "应用修改" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "生成预览" })).toBeDisabled();
  });

  it("shows the summary and affected blocks before enabling apply", async () => {
    const api = fakeApi();
    await openPreview(api);
    expect(screen.getByText(/影响 1 个内容块/)).toBeVisible();
    expect(screen.getByText("替换文本")).toBeVisible();
    await waitFor(() => expect(screen.getByRole("button", { name: "应用修改" })).toBeEnabled());
  });

  it("applies a previewed edit and offers undo", async () => {
    const api = fakeApi();
    const onApplied = vi.fn();
    render(
      <AIAssistantPanel api={api} artifactId="artifact-1" baseVersion={1} onApplied={onApplied} />,
    );
    await userEvent.type(screen.getByLabelText("修改指令"), "改写执行摘要");
    await userEvent.click(screen.getByRole("button", { name: "生成预览" }));
    await screen.findByText(/将做以下修改/);
    await userEvent.click(screen.getByRole("button", { name: "应用修改" }));
    await waitFor(() => expect(api.applyEdit).toHaveBeenCalledWith(
      "artifact-1", "01993f2f-2b79-7000-8000-0000000000aa"));
    expect(onApplied).toHaveBeenCalledWith(expect.objectContaining({ versionNumber: 2 }));
    const undo = await screen.findByRole("button", { name: "撤销本次修改" });
    await userEvent.click(undo);
    await waitFor(() => expect(api.restoreVersion).toHaveBeenCalledWith("artifact-1", 1));
  });

  it("passes selected block ids to the preview request", async () => {
    const api = fakeApi();
    await openPreview(api, "只改选中的块", ["block-9"]);
    expect(api.previewEdit).toHaveBeenCalledWith("artifact-1", "只改选中的块", ["block-9"]);
  });

  it("cancels a preview and disables apply again", async () => {
    const api = fakeApi();
    await openPreview(api);
    await userEvent.click(screen.getByRole("button", { name: "取消" }));
    await waitFor(() => expect(screen.queryByText(/将做以下修改/)).not.toBeInTheDocument());
    expect(screen.getByRole("button", { name: "应用修改" })).toBeDisabled();
  });

  it("surfaces a version conflict without applying", async () => {
    const api = fakeApi({
      applyEdit: vi.fn().mockRejectedValue(
        new ApiClientError("version_conflict", "文档已有新版本", 409, { latestVersion: 5 })),
    });
    render(<AIAssistantPanel api={api} artifactId="artifact-1" baseVersion={1} />);
    await userEvent.type(screen.getByLabelText("修改指令"), "并发的修改");
    await userEvent.click(screen.getByRole("button", { name: "生成预览" }));
    await screen.findByText(/将做以下修改/);
    await userEvent.click(screen.getByRole("button", { name: "应用修改" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("文档已有新版本");
  });
});

describe("VersionHistory", () => {
  it("lists immutable versions and restores a historical one", async () => {
    const api = fakeApi();
    const onRestored = vi.fn();
    render(
      <VersionHistory api={api} artifactId="artifact-1" currentVersion={2} onRestored={onRestored} />,
    );
    expect(await screen.findByText("版本 2")).toBeVisible();
    expect(screen.getByText("初始生成")).toBeVisible();
    expect(screen.getByText("AI 修改")).toBeVisible();
    // The current version cannot be restored onto itself.
    expect(screen.getByRole("button", { name: "恢复到版本 2" })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "恢复到版本 1" }));
    await waitFor(() => expect(api.restoreVersion).toHaveBeenCalledWith("artifact-1", 1));
    expect(onRestored).toHaveBeenCalledWith(expect.objectContaining({ versionNumber: 3 }));
  });
});
