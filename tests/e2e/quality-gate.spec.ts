import { test, expect } from "@playwright/test";

import {
  contrastDiagnostic, geometryDiagnostics,
} from "../../apps/web/lib/quality/browser-validator";

/**
 * Self-contained quality-gate scenarios. These render static fixtures in the
 * pinned Chromium and assert that the shipped gate helpers produce the expected
 * stable diagnostics. They require no API, database, or object storage, so they
 * run anywhere Playwright browsers are installed.
 */

const BROKEN_FIXTURE = `<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><style>
  .slot { position: relative; width: 400px; height: 60px; overflow: hidden; }
  .overflow { height: 200px; }
  .low-contrast { color: #777777; background: #888888; }
</style></head><body>
  <div class="slot"><div class="overflow" data-block-id="block-overflow">溢出的内容</div></div>
  <p class="low-contrast" data-node-id="text-lowcontrast">低对比度文本</p>
</body></html>`;

const CLEAN_FIXTURE = `<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"></head><body>
  <div style="width:400px;height:200px"><p data-block-id="block-ok" style="height:20px">正常内容</p></div>
</body></html>`;

const SELF_CONTAINED_FIXTURE = `<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<style>body{font-family:system-ui,sans-serif}</style></head>
<body><article aria-label="季度经营分析"><h1>季度经营分析</h1>
<section aria-label="执行摘要"><h2>执行摘要</h2><p>收入稳步增长。</p>
<table aria-label="季度收入"><thead><tr><th scope="col">季度</th><th scope="col">收入</th></tr></thead>
<tbody><tr><td>Q1</td><td>120</td></tr></tbody></table></section></article></body></html>`;

async function measureOverflow(page: import("@playwright/test").Page, blockId: string): Promise<number> {
  return page.evaluate((id) => {
    const node = document.querySelector(`[data-block-id="${id}"]`) as HTMLElement | null;
    if (!node || !node.parentElement) return 0;
    const box = node.getBoundingClientRect();
    const parent = node.parentElement.getBoundingClientRect();
    return Math.max(0, box.bottom - parent.bottom);
  }, blockId);
}

test("flags content overflow as a render error", async ({ page }) => {
  await page.setContent(BROKEN_FIXTURE);
  const overflow = await measureOverflow(page, "block-overflow");
  const diagnostics = geometryDiagnostics({ nodeId: "block-overflow", overflowPx: overflow });
  expect(overflow).toBeGreaterThan(2);
  expect(diagnostics.some((item) => item.code === "content_clipped")).toBe(true);
});

test("flags insufficient contrast as an accessibility error", async ({ page }) => {
  await page.setContent(BROKEN_FIXTURE);
  const colors = await page.evaluate(() => {
    const node = document.querySelector('[data-node-id="text-lowcontrast"]') as HTMLElement;
    const style = window.getComputedStyle(node);
    return { fg: style.color, bg: style.backgroundColor };
  });
  const diagnostic = contrastDiagnostic("text-lowcontrast", colors.fg, colors.bg);
  expect(diagnostic?.code).toBe("insufficient_contrast");
  expect(diagnostic?.layer).toBe("accessibility");
});

test("a clean page yields no render diagnostics", async ({ page }) => {
  await page.setContent(CLEAN_FIXTURE);
  const overflow = await measureOverflow(page, "block-ok");
  expect(geometryDiagnostics({ nodeId: "block-ok", overflowPx: overflow })).toEqual([]);
});

test("self-contained content renders with all external network requests blocked", async ({ page, context }) => {
  const external: string[] = [];
  await context.route("**", (route) => {
    const url = route.request().url();
    const local = url.startsWith("data:") || url.startsWith("file:") || url.startsWith("about:")
      || url.includes("localhost") || url.includes("127.0.0.1");
    if (!local) external.push(url);
    return local ? route.continue() : route.abort();
  });
  await page.setContent(SELF_CONTAINED_FIXTURE);
  await expect(page.getByRole("heading", { name: "执行摘要" })).toBeVisible();
  await expect(page.getByRole("table", { name: "季度收入" })).toBeVisible();
  expect(external).toEqual([]);
});
