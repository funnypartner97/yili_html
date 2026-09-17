import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import CreateComposer from "../components/create/CreateComposer";
import FileQueue from "../components/create/FileQueue";
import GenerationParameters, {
  DEFAULT_GENERATION_PARAMETERS,
} from "../components/create/GenerationParameters";
import GenerationProgress from "../components/create/GenerationProgress";
import PlanReview from "../components/create/PlanReview";
import type { ApiClient } from "../lib/api/client";
import type { GenerationParametersValue, PlanInfo } from "../lib/api/types";

function parsedFile(name = "report.csv") {
  return {
    sourceId: "src-1",
    filename: name,
    contentType: "text/csv",
    sizeBytes: 10,
    sha256: "a".repeat(64),
    parseStatus: "parsed" as const,
    error: null,
    createdAt: "2026-09-16T00:00:00Z",
    updatedAt: "2026-09-16T00:00:00Z",
  };
}

function planFixture(overrides: Partial<PlanInfo["plan"]> = {}): PlanInfo {
  return {
    id: "plan-1",
    artifactId: "artifact-1",
    revision: 1,
    status: "ready",
    createdAt: "2026-09-16T00:00:00Z",
    confirmedAt: null,
    plan: {
      artifactId: "artifact-1",
      outputModes: ["document"],
      audience: "管理层",
      lengthPreset: "standard",
      density: "balanced",
      outputSpec: "responsive",
      emphasis: [],
      outline: [{ id: "s1", title: "季度收入" }, { id: "s2", title: "成本结构" }],
      sourceSummary: { parsed: 1, failed: 0, conflicts: [] },
      ...overrides,
    },
  };
}

function fakeApi(overrides: Partial<ApiClient> = {}): ApiClient {
  return {
    createArtifact: vi.fn().mockResolvedValue({
      id: "artifact-1", title: "Report", status: "draft", sourceCount: 0,
      latestVersion: 0, createdAt: "2026-09-16T00:00:00Z", updatedAt: "2026-09-16T00:00:00Z",
    }),
    uploadFile: vi.fn().mockResolvedValue({ sourceId: "src-1", parseStatus: "queued" }),
    listFiles: vi.fn().mockResolvedValue([parsedFile()]),
    createPlan: vi.fn().mockResolvedValue(planFixture()),
    getPlan: vi.fn().mockResolvedValue(planFixture()),
    updatePlan: vi.fn().mockResolvedValue(planFixture({ audience: "董事会", outline: [{ id: "s1", title: "关键结论" }] })),
    confirmPlan: vi.fn().mockResolvedValue({ jobId: "job-1", planId: "plan-1", status: "queued" }),
    getJob: vi.fn().mockResolvedValue({
      id: "job-1", artifactId: "artifact-1", status: "succeeded", progress: 100,
      stage: "completed", error: null, createdAt: "2026-09-16T00:00:00Z", updatedAt: "2026-09-16T00:00:00Z",
    }),
    getArtifact: vi.fn().mockResolvedValue({
      id: "artifact-1", title: "Report", status: "editable", sourceCount: 1,
      latestVersion: 1, createdAt: "2026-09-16T00:00:00Z", updatedAt: "2026-09-16T00:00:00Z",
    }),
    ...overrides,
  } as ApiClient;
}

describe("CreateComposer", () => {
  it("keeps generation disabled until instruction and a parsed source exist", async () => {
    const api = fakeApi({ listFiles: vi.fn().mockResolvedValue([]) });
    render(<CreateComposer api={api} />);
    await userEvent.type(screen.getByRole("textbox", { name: /创作指令/ }), "生成季度汇报");
    expect(screen.getByRole("button", { name: "生成计划" })).toBeDisabled();
  });

  it("uploads files, polls parsing, and enables generation once parsed", async () => {
    const api = fakeApi();
    render(<CreateComposer api={api} />);
    await userEvent.type(screen.getByRole("textbox", { name: /创作指令/ }), "生成季度汇报");
    const input = screen.getByLabelText("添加材料") as HTMLInputElement;
    await userEvent.upload(input, new File(["col\nval"], "report.csv", { type: "text/csv" }));
    await waitFor(() => expect(screen.getByText("report.csv")).toBeVisible());
    await waitFor(() => expect(screen.getByText("已解析")).toBeVisible());
    expect(screen.getByRole("button", { name: "生成计划" })).toBeEnabled();
    await userEvent.click(screen.getByRole("button", { name: "生成计划" }));
    await waitFor(() => expect(api.createPlan).toHaveBeenCalledWith(
      "artifact-1", "生成季度汇报", expect.objectContaining({ outputModes: ["document"] })));
  });

  it("shows the failed state and keeps generation disabled when parsing fails", async () => {
    const api = fakeApi({
      listFiles: vi.fn().mockResolvedValue([{ ...parsedFile(), parseStatus: "failed" as const }]),
    });
    render(<CreateComposer api={api} />);
    await userEvent.type(screen.getByRole("textbox", { name: /创作指令/ }), "生成季度汇报");
    const input = screen.getByLabelText("添加材料") as HTMLInputElement;
    await userEvent.upload(input, new File(["col"], "broken.csv", { type: "text/csv" }));
    await waitFor(() => expect(screen.getByText("解析失败")).toBeVisible());
    expect(screen.getByRole("button", { name: "生成计划" })).toBeDisabled();
  });

  it("surfaces upload errors without crashing the composer", async () => {
    const api = fakeApi({ uploadFile: vi.fn().mockRejectedValue(new Error("上传失败")) });
    render(<CreateComposer api={api} />);
    await userEvent.type(screen.getByRole("textbox", { name: /创作指令/ }), "生成季度汇报");
    const input = screen.getByLabelText("添加材料") as HTMLInputElement;
    await userEvent.upload(input, new File(["col"], "report.csv", { type: "text/csv" }));
    await waitFor(() => expect(screen.getByText("上传失败")).toBeVisible());
    expect(screen.getByRole("button", { name: "生成计划" })).toBeDisabled();
  });
});

describe("GenerationParameters", () => {
  it("allows document and presentation to be selected together", async () => {
    const onChange = vi.fn();
    render(<GenerationParameters value={DEFAULT_GENERATION_PARAMETERS} onChange={onChange} />);
    await userEvent.click(screen.getByLabelText("文档"));
    await userEvent.click(screen.getByLabelText("演示"));
    expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({
      outputModes: ["document", "presentation"],
    }));
  });

  it("disables data and dashboard modes as coming later", () => {
    render(<GenerationParameters value={DEFAULT_GENERATION_PARAMETERS} onChange={vi.fn()} />);
    expect(screen.getByLabelText("数据")).toBeDisabled();
    expect(screen.getByLabelText("看板")).toBeDisabled();
    expect(screen.getAllByText("后续开放")).toHaveLength(2);
  });

  it("edits audience, length, density, and output specification", async () => {
    const onChange = vi.fn();
    const values: GenerationParametersValue[] = [];
    function Controlled() {
      const [value, setValue] = useState(DEFAULT_GENERATION_PARAMETERS);
      return (
        <GenerationParameters
          value={value}
          onChange={(next) => { setValue(next); values.push(next); }}
        />
      );
    }
    render(<Controlled />);
    await userEvent.type(screen.getByLabelText("受众"), "董事会");
    await userEvent.click(screen.getByLabelText("精简"));
    await userEvent.click(screen.getByLabelText("紧凑"));
    await userEvent.click(screen.getByLabelText("固定"));
    expect(values.at(-1)).toMatchObject({
      audience: "董事会", lengthPreset: "short", density: "dense", outputSpec: "fixed",
    });
  });
});

describe("PlanReview", () => {
  it("renders the plan summary and requires confirmation", () => {
    render(<PlanReview api={fakeApi()} plan={planFixture()} />);
    expect(screen.getByText("季度收入")).toBeVisible();
    expect(screen.getByText("成本结构")).toBeVisible();
    expect(screen.getByText(/已解析材料/)).toBeVisible();
    expect(screen.getByRole("button", { name: "确认并生成" })).toBeEnabled();
    expect(screen.queryByRole("button", { name: /跳过/ })).not.toBeInTheDocument();
  });

  it("shows conflicts from the source summary", () => {
    render(<PlanReview api={fakeApi()} plan={planFixture({
      sourceSummary: { parsed: 2, failed: 1, conflicts: ["两个材料收入口径不一致"] },
    })} />);
    expect(screen.getByText("两个材料收入口径不一致")).toBeVisible();
    expect(screen.getByText(/1 个材料解析失败/)).toBeVisible();
  });

  it("edits parameters into a new revision before confirming", async () => {
    const api = fakeApi();
    render(<PlanReview api={api} plan={planFixture()} />);
    await userEvent.click(screen.getByRole("button", { name: "编辑设置" }));
    await userEvent.clear(screen.getByLabelText("受众"));
    await userEvent.type(screen.getByLabelText("受众"), "董事会");
    await userEvent.click(screen.getByRole("button", { name: "保存修改" }));
    await waitFor(() => expect(api.updatePlan).toHaveBeenCalled());
    expect(api.updatePlan).toHaveBeenCalledWith("artifact-1", "plan-1",
      expect.objectContaining({ audience: "董事会" }));
  });

  it("confirms, tracks progress, and links to the editor on completion", async () => {
    const api = fakeApi();
    render(<PlanReview api={api} plan={planFixture()} />);
    await userEvent.click(screen.getByRole("button", { name: "确认并生成" }));
    await waitFor(() => expect(api.confirmPlan).toHaveBeenCalledWith("artifact-1", "plan-1"));
    await waitFor(() => expect(screen.getByRole("link", { name: "打开编辑器" })).toHaveAttribute(
      "href", "/artifacts/artifact-1/edit"));
  });

  it("exposes recovery after a failed generation", async () => {
    const api = fakeApi({
      getJob: vi.fn().mockResolvedValue({
        id: "job-1", artifactId: "artifact-1", status: "failed", progress: 85,
        stage: "validating_document",
        error: { code: "citation_source_missing", message: "引用未匹配", stage: "validating_document" },
        createdAt: "2026-09-16T00:00:00Z", updatedAt: "2026-09-16T00:00:00Z",
      }),
    });
    render(<PlanReview api={api} plan={planFixture()} />);
    await userEvent.click(screen.getByRole("button", { name: "确认并生成" }));
    await waitFor(() => expect(screen.getByText("引用未匹配")).toBeVisible());
    expect(screen.getByRole("button", { name: "重新创建计划" })).toBeEnabled();
  });
});

describe("GenerationProgress", () => {
  it("highlights the current stage while running", () => {
    render(<GenerationProgress job={{
      id: "job-1", artifactId: "artifact-1", status: "running", progress: 60,
      stage: "generating_content", error: null,
      createdAt: "2026-09-16T00:00:00Z", updatedAt: "2026-09-16T00:00:00Z",
    }} />);
    expect(screen.getByText("生成内容")).toHaveClass("stage-current");
    expect(screen.getByText("加载材料")).toHaveClass("stage-done");
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "60");
  });
});

describe("FileQueue", () => {
  it("renders every upload state", () => {
    render(<FileQueue files={[
      { id: "f1", name: "a.csv", status: "uploading" },
      { id: "f2", name: "b.csv", status: "parsing" },
      { id: "f3", name: "c.csv", status: "parsed" },
      { id: "f4", name: "d.csv", status: "failed" },
    ]} />);
    expect(screen.getByText("a.csv")).toBeVisible();
    expect(screen.getByText("上传中")).toBeVisible();
    expect(screen.getByText("解析中")).toBeVisible();
    expect(screen.getByText("已解析")).toBeVisible();
    expect(screen.getByText("解析失败")).toBeVisible();
  });
});
