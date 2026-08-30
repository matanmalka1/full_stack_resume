import { defineConfig, devices } from "@playwright/test";

const PORT = 4173;

/* The spec requires E2E against a built application, so the server under test is the
   production build served by `vite preview`, never the dev server.
   The flows that need real FastAPI, a real worker, and a real DraftFlow arrive with the
   screens that drive them; this configuration is the foundation they plug into. */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    locale: "he-IL",
    trace: "on-first-retry",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: `npm run build && npm run preview -- --host 127.0.0.1 --port ${PORT} --strictPort`,
    url: `http://127.0.0.1:${PORT}`,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
