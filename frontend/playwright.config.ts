import { defineConfig } from "@playwright/test";

import { chromiumProject } from "./playwright.chromium";

const PORT = 4173;

/* The spec requires E2E against a built application, so the server under test is the
   production build served by `vite preview`, never the dev server.
   Real API coverage has a separate configuration owned by the pytest harness. */
export default defineConfig({
  testDir: "./e2e",
  testIgnore: "**/integration/**",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    locale: "he-IL",
    trace: "on-first-retry",
    /* Every API answer comes from the `api` fixture (e2e/fixtures.ts). The app registers
       no Service Worker, and none may answer in its place. */
    serviceWorkers: "block",
  },
  projects: [chromiumProject],
  webServer: {
    command: `npm run build && npm run preview -- --host 127.0.0.1 --port ${PORT} --strictPort`,
    url: `http://127.0.0.1:${PORT}`,
    /* Reusing a local preview can make the browser suite exercise an older dist build
       and report failures for styles that are no longer in the source tree. Always
       start from the production build created by the command above. */
    reuseExistingServer: false,
    /* The preview serves no API proxy in this suite (vite.config.ts). */
    env: { CV_E2E_MOCKED_API: "1" },
    timeout: 120_000,
  },
});
