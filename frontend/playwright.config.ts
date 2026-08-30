import { defineConfig, devices } from "@playwright/test";

const PORT = 4173;

/* Stage F is specifically the deployed-shape gate: `cv web` serves the production build
   and supervises FastAPI and the Operation worker over the same PostgreSQL/object-store
   composition. `e2e/serve-real-app.py` adds the guard rails the gate needs around that
   production entry point; it is not a substitute server. */
export default defineConfig({
  testDir: "./e2e",
  /* One `cv web` host over one PostgreSQL database backs every spec, so workers would
     contend for the same single-candidate project rather than isolate. `fullyParallel`
     alone still parallelizes across files; the gate owns its isolation explicitly. */
  fullyParallel: false,
  workers: 1,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  reporter: [["list"]],
  timeout: 180_000,
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    locale: "he-IL",
    trace: "on-first-retry",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: `npm run build && ../.venv/bin/python e2e/serve-real-app.py --port ${PORT}`,
    url: `http://127.0.0.1:${PORT}`,
    reuseExistingServer: false,
    timeout: 180_000,
  },
});
