import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { DocumentGraph } from "@html-office/contracts";

import ArtifactEditor from "../components/editor/ArtifactEditor";
import DocumentRenderer from "../components/editor/DocumentRenderer";
import SectionNavigator from "../components/editor/SectionNavigator";
import PresentationStage from "../components/presentation/PresentationStage";
import SemanticReadingView from "../components/presentation/SemanticReadingView";
import { presentationScale } from "../components/presentation/presentationScale";
import { ApiClientError, type ApiClient } from "../lib/api/client";

const SOURCE_REF = { sourceId: "01993f2f-2b79-7000-8000-000000000001", locator: "page 1" };
const SECTION_ID = "01993f2f-2b79-7000-8000-000000000010";
const TEXT_BLOCK_ID = "01993f2f-2b79-7000-8000-000000000011";
const SLIDE_ID = "01993f2f-2b79-7000-8000-000000000020";

function graphFixture(overrides: Partial<DocumentGraph> = {}): DocumentGraph {
  return {
    schemaVersion: "1.0.0",
    artifactId: "01993f2f-2b79-7000-8000-000000000100",
    title: "季度经营分析",
    outputModes: ["document", "presentation"],
    theme: { id: "core", tokens: {} },
    assets: [],
    sections: [{
      id: SECTION_ID,
      order: 0,
      title: "执行摘要",
      blocks: [{
        id: TEXT_BLOCK_ID,
        order: 0,
        kind: "richText",
        text: "本季度收入稳步增长。",
        sourceRefs: [SOURCE_REF],
      }],
    }],
    presentation: {
      stage: { width: 1920, height: 1080 },
      slides: [{
        id: SLIDE_ID,
        order: 0,
        sectionId: SECTION_ID,
        kind: "content",
        layoutId: "title-body",
        slotAssignments: [{
          id: "01993f2f-2b79-7000-8000-000000000021",
          order: 0,
          slotId: "title",
          blockIds: [TEXT_BLOCK_ID],
          assetIds: [],
        }],
        timing: { plannedSeconds: 60, rehearsalEvents: [] },
        animationTimeline: [],
      }],
    },
    ...overrides,
  } as DocumentGraph;
}

/** A deck with a chart section, used for the semantic reading view assertions. */
function readingGraphFixture(): DocumentGraph {
  return {
    ...graphFixture(),
    sections: [
      ...graphFixture().sections,
      {
        id: "01993f2f-2b79-7000-8000-000000000030",
        order: 1,
        title: "收入趋势",
        blocks: [{
          id: "01993f2f-2b79-7000-8000-000000000031",
          order: 0,
          kind: "chart",
          chart: {
            id: "01993f2f-2b79-7000-8000-000000000032",
            datasetId: "quarterly-revenue",
            mark: "bar",
            encodings: [
              { channel: "x", field: "quarter", type: "ordinal", aggregation: "none", sort: "none", scale: { type: "ordinal", domain: ["Q1", "Q2"], baseline: null } },
              { channel: "y", field: "revenue", type: "quantitative", aggregation: "sum", sort: "none", scale: { type: "linear", domain: [0, 200], baseline: 0 } },
            ],
            filters: [],
            calculations: [],
            semanticExplanation: "按季度汇总的营业收入。",
            invariants: { kind: "proportionalBars", zeroBaseline: true, nonNegative: true, maxBars: 12 },
          },
          frame: {
            title: "季度收入",
            description: "两个季度的营业收入对比。",
            source: [SOURCE_REF],
            asOf: "2026-06-30",
            caveats: [],
            claim: "收入环比增长。",
            tableFallback: { columns: ["季度", "收入"], rows: [["Q1", 120], ["Q2", 160]] },
          },
          sourceRefs: [SOURCE_REF],
        }],
      },
    ],
  } as unknown as DocumentGraph;
}

/** The base deck plus a second slide, for stable-id navigation. */
function twoSlideGraph(): DocumentGraph {
  const base = graphFixture();
  const secondSlide = {
    ...base.presentation!.slides[0],
    id: "01993f2f-2b79-7000-8000-000000000040",
    order: 1,
    slotAssignments: [{
      id: "01993f2f-2b79-7000-8000-000000000041",
      order: 0,
      slotId: "title",
      blockIds: [TEXT_BLOCK_ID],
      assetIds: [],
    }],
  };
  return {
    ...base,
    presentation: { stage: { width: 1920, height: 1080 }, slides: [base.presentation!.slides[0], secondSlide] },
  } as unknown as DocumentGraph;
}

/** The base deck with a reveal animation targeting the title block. */
function animatedGraph(): DocumentGraph {
  const base = graphFixture();
  const slide = {
    ...base.presentation!.slides[0],
    animationTimeline: [{
      id: "01993f2f-2b79-7000-8000-000000000050",
      order: 0,
      intent: "reveal",
      targetIds: [TEXT_BLOCK_ID],
      duration: "medium",
      easing: "ease-out",
      exportState: "animated",
    }],
  };
  return {
    ...base,
    presentation: { stage: { width: 1920, height: 1080 }, slides: [slide] },
  } as unknown as DocumentGraph;
}

function artifactFixture(latestVersion: number) {
  return {
    id: "01993f2f-2b79-7000-8000-000000000100",
    title: "季度经营分析",
    status: "editable" as const,
    sourceCount: 1,
    latestVersion,
    createdAt: "2026-09-16T00:00:00Z",
    updatedAt: "2026-09-16T00:00:00Z",
  };
}

function fakeApi(overrides: Partial<ApiClient> = {}): ApiClient {
  return {
    getDocument: vi.fn().mockResolvedValue(graphFixture()),
    getArtifact: vi.fn().mockResolvedValue(artifactFixture(1)),
    saveDocument: vi.fn().mockResolvedValue({ versionNumber: 2, savedAt: "2026-09-16T01:00:00Z" }),
    listVersions: vi.fn().mockResolvedValue({ versions: [] }),
    previewEdit: vi.fn(),
    applyEdit: vi.fn(),
    restoreVersion: vi.fn(),
    ...overrides,
  } as unknown as ApiClient;
}

function mockMatchMedia(matches: boolean) {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    configurable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
}

const VIEWPORT = { width: 1280, height: 720 };

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("presentationScale", () => {
  it("returns one uniform scale that fits the canvas at representative viewports", () => {
    expect(presentationScale({ width: 1920, height: 1080 })).toBe(1);
    // 16:9 — both axes agree.
    expect(presentationScale({ width: 1280, height: 720 })).toBeCloseTo(2 / 3, 6);
    // 16:10 — width is the binding axis.
    expect(presentationScale({ width: 1440, height: 900 })).toBe(0.75);
    // Narrow mobile — width is the binding axis.
    expect(presentationScale({ width: 390, height: 844 })).toBeCloseTo(390 / 1920, 6);
  });
});

describe("renderers", () => {
  it("renders the same graph as a document and a fixed presentation stage", () => {
    const graph = graphFixture();
    const { unmount } = render(<DocumentRenderer graph={graph} />);
    expect(screen.getByRole("heading", { name: "执行摘要" })).toBeVisible();
    unmount();
    render(<PresentationStage graph={graph} viewport={VIEWPORT} />);
    expect(screen.getByLabelText("幻灯片 1")).toBeVisible();
    expect(screen.getByTestId("presentation-stage")).toHaveAttribute("data-logical-size", "1920x1080");
  });

  it("applies exactly one uniform scale at the stage root", () => {
    render(<PresentationStage graph={graphFixture()} viewport={{ width: 1440, height: 900 }} />);
    const stage = screen.getByTestId("presentation-stage");
    expect(stage).toHaveAttribute("data-scale", "0.75");
    expect(stage.style.transform).toBe("scale(0.75)");
  });

  it("synthesizes one slide per section when no deck exists", () => {
    render(<PresentationStage graph={graphFixture({ presentation: undefined })} viewport={VIEWPORT} />);
    expect(screen.getByLabelText("幻灯片 1")).toBeVisible();
  });

  it("navigates by stable slide ids", async () => {
    render(<PresentationStage graph={twoSlideGraph()} viewport={VIEWPORT} />);
    expect(screen.getByLabelText("幻灯片 1")).toHaveAttribute("data-slide-id", SLIDE_ID);
    await userEvent.click(screen.getByRole("button", { name: "下一张" }));
    expect(screen.getByLabelText("幻灯片 2")).toHaveAttribute(
      "data-slide-id",
      "01993f2f-2b79-7000-8000-000000000040",
    );
  });

  it("navigates sections through anchors", () => {
    render(<SectionNavigator graph={graphFixture()} />);
    expect(screen.getByRole("link", { name: "执行摘要" })).toHaveAttribute("href", `#section-${SECTION_ID}`);
  });
});

describe("SemanticReadingView", () => {
  it("offers a reflowed reading surface independent of fixed-stage geometry", () => {
    const graph = readingGraphFixture();
    render(<SemanticReadingView graph={graph} />);
    expect(screen.getByRole("article", { name: graph.title })).toBeVisible();
    expect(screen.getByRole("heading", { name: "执行摘要" })).toBeVisible();
    expect(screen.getByRole("table", { name: "季度收入" })).toBeVisible();
    expect(screen.getByRole("article")).toHaveAttribute("lang", "zh-CN");
  });
});

describe("reduced motion", () => {
  it("animates a declared target when motion is allowed", () => {
    mockMatchMedia(false);
    const { container } = render(<PresentationStage graph={animatedGraph()} viewport={VIEWPORT} />);
    const target = container.querySelector(`[data-block-id="${TEXT_BLOCK_ID}"]`);
    expect(target).toHaveAttribute("data-motion-state", "animated");
  });

  it("shows the stable final state when reduced motion is preferred", () => {
    mockMatchMedia(true);
    const { container } = render(<PresentationStage graph={animatedGraph()} viewport={VIEWPORT} />);
    const target = container.querySelector(`[data-block-id="${TEXT_BLOCK_ID}"]`);
    expect(target).toHaveAttribute("data-motion-state", "final");
  });
});

describe("ArtifactEditor", () => {
  it("switches between document, presentation, and reading surfaces", async () => {
    render(<ArtifactEditor api={fakeApi()} artifactId="artifact-1" graph={graphFixture()} version={1} />);
    expect(screen.getByRole("heading", { name: "执行摘要" })).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "演示视图" }));
    expect(screen.getByLabelText("幻灯片 1")).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "阅读视图" }));
    expect(screen.getByRole("article", { name: "季度经营分析" })).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "文档视图" }));
    expect(screen.getByRole("heading", { name: "执行摘要" })).toBeVisible();
  });

  it("disables presentation switching for document-only artifacts", () => {
    render(
      <ArtifactEditor
        api={fakeApi()}
        artifactId="artifact-1"
        graph={graphFixture({ outputModes: ["document"], presentation: undefined })}
        version={1}
      />,
    );
    expect(screen.getByRole("button", { name: "演示视图" })).toBeDisabled();
  });

  it("autosaves the edited graph 800ms after the last edit", async () => {
    const api = fakeApi();
    render(<ArtifactEditor api={api} artifactId="artifact-1" graph={graphFixture()} version={1} />);
    const textbox = screen.getByRole("textbox", { name: "执行摘要" });
    await userEvent.click(textbox);
    // A small inter-key delay lets ProseMirror settle each DOM mutation before the
    // next keystroke, keeping the captured text deterministic under load.
    await userEvent.type(textbox, "，利润创新高。", { delay: 8 });
    expect(screen.getByRole("status")).toHaveTextContent("未保存更改");
    await waitFor(() => expect(api.saveDocument).toHaveBeenCalledTimes(1), { timeout: 3000 });
    expect(api.saveDocument).toHaveBeenCalledWith(
      "artifact-1",
      expect.objectContaining({
        sections: [expect.objectContaining({
          blocks: [expect.objectContaining({ text: "本季度收入稳步增长。，利润创新高。" })],
        })],
      }),
      "1",
    );
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("已保存"));
  });

  it("pauses autosave on version conflict and recovers by loading the latest version", async () => {
    const api = fakeApi({
      saveDocument: vi.fn().mockRejectedValue(new ApiClientError(
        "version_conflict", "文档已有新版本", 409, { latestVersion: 3 })),
      getDocument: vi.fn().mockResolvedValue(graphFixture({
        sections: [{
          id: SECTION_ID,
          order: 0,
          title: "执行摘要",
          blocks: [{
            id: TEXT_BLOCK_ID,
            order: 0,
            kind: "richText",
            text: "服务器上的最新执行摘要。",
            sourceRefs: [SOURCE_REF],
          }],
        }],
      })),
      getArtifact: vi.fn().mockResolvedValue(artifactFixture(3)),
    });
    render(<ArtifactEditor api={api} artifactId="artifact-1" graph={graphFixture()} version={1} />);

    const textbox = screen.getByRole("textbox", { name: "执行摘要" });
    await userEvent.click(textbox);
    await userEvent.type(textbox, "追加内容");
    await waitFor(() => expect(screen.getByText("文档已产生新版本")).toBeVisible(), { timeout: 3000 });

    // Autosave is paused: further typing must not trigger another save.
    await userEvent.type(textbox, "继续输入");
    await new Promise((resolve) => setTimeout(resolve, 1200));
    expect(api.saveDocument).toHaveBeenCalledTimes(1);

    // Loading the latest version replaces the draft and clears the banner.
    await userEvent.click(screen.getByRole("button", { name: "加载最新版本" }));
    await waitFor(() => expect(screen.queryByText("文档已产生新版本")).not.toBeInTheDocument());
    expect(await screen.findByText("服务器上的最新执行摘要。")).toBeVisible();
    expect(screen.getByRole("status")).toHaveTextContent("已保存");
  });

  it("saves the local draft as a new version after a conflict", async () => {
    const api = fakeApi({
      saveDocument: vi.fn()
        .mockRejectedValueOnce(new ApiClientError("version_conflict", "文档已有新版本", 409, { latestVersion: 2 }))
        .mockResolvedValue({ versionNumber: 3, savedAt: "2026-09-16T02:00:00Z" }),
      getArtifact: vi.fn().mockResolvedValue(artifactFixture(2)),
    });
    render(<ArtifactEditor api={api} artifactId="artifact-1" graph={graphFixture()} version={1} />);

    const textbox = screen.getByRole("textbox", { name: "执行摘要" });
    await userEvent.click(textbox);
    await userEvent.type(textbox, "本地修改");
    await waitFor(() => expect(screen.getByText("文档已产生新版本")).toBeVisible(), { timeout: 3000 });

    await userEvent.click(screen.getByRole("button", { name: "保存为副本" }));
    await waitFor(() => expect(screen.queryByText("文档已产生新版本")).not.toBeInTheDocument());
    // The retry must carry the fresh precondition, not the stale one.
    expect(api.saveDocument).toHaveBeenLastCalledWith("artifact-1", expect.objectContaining({}), "2");
    expect(screen.getByRole("status")).toHaveTextContent("已保存");
  });
});
