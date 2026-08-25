import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  /* Component tests run in jsdom; Playwright owns the browser. `globals: false` keeps
     `describe`/`it`/`expect` explicit imports, so a test file reads like the rest of the
     source rather than relying on ambient names. */
  test: {
    environment: "jsdom",
    globals: false,
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    /* Each UI file creates its own jsdom and QueryClient. Running all of those
       environments at once can starve Testing Library's one-second async queries on
       a development laptop, producing cascades of timeouts after otherwise-correct
       renders. File isolation remains on; only file scheduling is serial. */
    fileParallelism: false,
    restoreMocks: true,
  },
  server: {
    host: "localhost",
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8765",
        changeOrigin: false,
      },
    },
  },
});
