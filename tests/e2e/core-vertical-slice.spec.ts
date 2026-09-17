import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test } from "@playwright/test";

/**
 * Full-stack core vertical slice: source → parsed → confirmed plan → generated →
 * edited → exported standalone HTML. Requires the local stack to be running:
 *
 *   docker compose up -d --wait
 *   uv run --project services/api python scripts/e2e-seed.py   (optional seed)
 *   uv run --project services/api uvicorn --app-dir services/api src.main:app --port 8000
 *   uv run --project services/api arq src.worker.settings.WorkerSettings   (worker)
 *   pnpm --filter web dev
 *
 * The web server proxies `/v1` to the API (see apps/web/next.config.ts). Set
 * E2E_BASE_URL to override the web origin.
 */

const here = path.dirname(fileURLToPath(import.meta.url));
const FIXTURE = path.resolve(here, "../fixtures/quarterly-report.pdf");
const SEED_FILE = path.resolve(here, ".seed.json");

function readSeed(): { artifactId: string; version: number } | null {
  if (!existsSync(SEED_FILE)) return null;
  try {
    return JSON.parse(readFileSync(SEED_FILE, "utf-8"));
  } catch {
    return null;
  }
}

test("source to confirmed plan to edited HTML export", async ({ page }) => {
  await page.goto("/create");
  await page.getByLabel("创作指令").fill("生成管理层季度经营汇报");
  await page.getByLabel("添加材料").setInputFiles(FIXTURE);
  await expect(page.getByText("解析完成")).toBeVisible();
  await page.getByLabel("文档").check();
  await page.getByLabel("演示").check();
  await page.getByRole("button", { name: "生成计划" }).click();

  await expect(page.getByRole("heading", { name: "确认生成计划" })).toBeVisible();
  await page.getByRole("button", { name: "确认并生成" }).click();

  await expect(page.getByRole("heading", { name: "生成完成" })).toBeVisible({ timeout: 30_000 });
  await page.getByRole("link", { name: "打开编辑器" }).click();

  // Edit the first editable rich-text block; the section title depends on the
  // generated document, so the assertion targets the save state, not a fixed name.
  const editor = page.getByRole("textbox").first();
  await expect(editor).toBeVisible();
  await editor.fill("更新后的执行摘要");
  await expect(page.getByText("已保存")).toBeVisible({ timeout: 15_000 });

  await page.getByRole("button", { name: "导出" }).click();
  await page.getByRole("menuitem", { name: "独立 HTML" }).click();
  await expect(page.getByText("导出完成")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("link", { name: "下载独立 HTML" })).toHaveAttribute("href", /.+/);
});

test("repeated exports of one version are byte-for-byte identical", async ({ request }) => {
  const seed = readSeed();
  test.skip(!seed, "Run scripts/e2e-seed.py to seed a deterministic artifact first.");
  const artifactId = seed!.artifactId;

  const first = await request.post(`/v1/artifacts/${artifactId}/exports/html`);
  const second = await request.post(`/v1/artifacts/${artifactId}/exports/html`);
  expect(first.ok()).toBeTruthy();
  expect(second.ok()).toBeTruthy();
  const firstBody = await first.json();
  const secondBody = await second.json();
  expect(firstBody.contentHash).toBe(secondBody.contentHash);
  expect(firstBody.passedLayers).toEqual(["schema", "semantic", "layout"]);
  expect(firstBody.diagnostics).toEqual([]);
});
