import { defineConfig, devices } from "@playwright/test";

/**
 * Bridge to the repository-root end-to-end suite. Playwright is installed in this
 * workspace, so `pnpm --filter web e2e` runs the canonical root `tests/e2e` specs.
 * Keep this in sync with the root `playwright.config.ts`.
 */
export default defineConfig({
  testDir: "../../tests/e2e",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  timeout: 60_000,
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
});
