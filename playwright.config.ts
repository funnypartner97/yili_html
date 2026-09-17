import { defineConfig, devices } from "@playwright/test";

/**
 * Root end-to-end configuration for the core vertical slice.
 *
 * The full-stack scenario (`core-vertical-slice.spec.ts`) requires the local
 * services to be running: `docker compose up -d --wait`, `python scripts/e2e-seed.py`,
 * the API/worker, and the web dev server. The `quality-gate.spec.ts` scenario is
 * self-contained and renders static fixtures in the pinned Chromium, so it needs no
 * services. No global webServer is declared here so the self-contained gate can run
 * on its own; start the stack explicitly before running the full scenario.
 */
export default defineConfig({
  testDir: "./tests/e2e",
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
