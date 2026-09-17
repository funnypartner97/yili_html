import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import ExportMenu from "../components/editor/ExportMenu";
import { ApiClientError, type ApiClient } from "../lib/api/client";
import type { ExportResult } from "../lib/api/types";

function exportResult(): ExportResult {
  return {
    downloadUrl: "/v1/exports/memory/exports/a/1/hash.zip?expires_in=900",
    expiresAt: "2026-09-16T03:00:00Z",
    contentHash: "deadbeef",
    documentVersion: 1,
    passedLayers: ["schema", "semantic", "layout"],
    diagnostics: [],
  };
}

function fakeApi(overrides: Partial<ApiClient> = {}): ApiClient {
  return {
    exportHtml: vi.fn().mockResolvedValue(exportResult()),
    ...overrides,
  } as unknown as ApiClient;
}

async function openMenu() {
  await userEvent.click(screen.getByRole("button", { name: "导出" }));
}

describe("ExportMenu", () => {
  it("enables only standalone HTML in this slice", async () => {
    render(<ExportMenu api={fakeApi()} artifactId="artifact-1" />);
    await openMenu();
    expect(screen.getByRole("menuitem", { name: "独立 HTML" })).toBeEnabled();
    expect(screen.getByRole("menuitem", { name: /PDF/ })).toBeDisabled();
    expect(screen.getByRole("menuitem", { name: /图片/ })).toBeDisabled();
    expect(screen.getAllByText("后续开放")).toHaveLength(2);
  });

  it("exports and offers a download link", async () => {
    const api = fakeApi();
    render(<ExportMenu api={api} artifactId="artifact-1" />);
    await openMenu();
    await userEvent.click(screen.getByRole("menuitem", { name: "独立 HTML" }));
    await waitFor(() => expect(api.exportHtml).toHaveBeenCalledWith("artifact-1", false));
    expect(await screen.findByText(/导出完成/)).toBeVisible();
    expect(screen.getByRole("link", { name: "下载独立 HTML" })).toHaveAttribute(
      "href", exportResult().downloadUrl);
  });

  it("blocks export on a quality-gate failure and surfaces the repair", async () => {
    const api = fakeApi({
      exportHtml: vi.fn().mockRejectedValue(new ApiClientError(
        "quality_gate_failed", "文档未通过质量校验，无法导出。", 422, {
          diagnostics: [{
            code: "slot_capacity_exceeded", severity: "error", layer: "layout",
            nodeId: "slide-1", message: "槽位内容超出上限。", measurements: {},
            constraint: "maxItems", repair: { command: "splitSlide", layoutId: "title-media" },
          }],
        })),
    });
    render(<ExportMenu api={api} artifactId="artifact-1" />);
    await openMenu();
    await userEvent.click(screen.getByRole("menuitem", { name: "独立 HTML" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("文档未通过质量校验");
    expect(alert).toHaveTextContent("splitSlide");
    expect(screen.queryByText(/导出完成/)).not.toBeInTheDocument();
  });

  it("lets the user acknowledge review diagnostics and retry", async () => {
    const api = fakeApi({
      exportHtml: vi.fn()
        .mockRejectedValueOnce(new ApiClientError(
          "quality_review_required", "存在需要确认的质量问题。", 409, {
            diagnostics: [{
              code: "content_clipped_ambiguous", severity: "review", layer: "render",
              nodeId: "n", message: "内容可能轻微溢出。", measurements: {}, constraint: "slot box",
              repair: null,
            }],
          }))
        .mockResolvedValue(exportResult()),
    });
    render(<ExportMenu api={api} artifactId="artifact-1" />);
    await openMenu();
    await userEvent.click(screen.getByRole("menuitem", { name: "独立 HTML" }));
    await screen.findByRole("alert");
    await userEvent.click(screen.getByRole("button", { name: "仍然导出" }));
    await waitFor(() => expect(api.exportHtml).toHaveBeenLastCalledWith("artifact-1", true));
    expect(await screen.findByText(/导出完成/)).toBeVisible();
  });
});
