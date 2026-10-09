import { defineConfig } from "@playwright/test";

import { chromiumProject } from "./playwright.chromium";

const baseURL = process.env.CV_TEST_BASE_URL;
if (!baseURL) {
  throw new Error("Run tests/e2e/test_browser_api_journey.py: pytest owns the isolated database and API server.");
}

export default defineConfig({
  testDir: "./e2e/integration",
  fullyParallel: false,
  workers: 1,
  forbidOnly: true,
  retries: 0,
  timeout: 60_000,
  reporter: [["list"]],
  use: {
    baseURL,
    locale: "he-IL",
    serviceWorkers: "block",
    trace: "retain-on-failure",
  },
  projects: [chromiumProject],
});
