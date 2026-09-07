import { expect, test } from "@playwright/test";

import type { Settings } from "../src/api/contracts";

const settings = {
  edit_version: 0,
  auto_generate_when_review_not_required: false,
  ai_enabled: false,
  ai_enabled_override: null,
  default_ai_model: "gpt-5.6-terra",
  default_execution_mode: "deterministic",
  default_reasoning_effort: "medium",
  available_ai_models: [
    {
      id: "gpt-5.6-terra",
      label: "GPT-5.6 Terra",
      input_per_million_usd: "2.00",
      cached_input_per_million_usd: "0.20",
      output_per_million_usd: "12.00",
      recommended: true,
      pricing_version: "openai-2026-09-03",
      pricing_source: "https://developers.openai.com/api/docs/models/compare",
    },
  ],
  provider_configured: false,
  ui_density: "comfortable",
  ui_text_size: "normal",
  updated_at: null,
} satisfies Settings;

test.describe("the application shell", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/api/v1/settings", async (route) => {
      await route.fulfill({ contentType: "application/json", json: settings });
    });
  });

  test("moves focus to the page heading after a route change", async ({ page }) => {
    await page.goto("/applications/new");
    await page.getByRole("link", { name: "הגדרות" }).click();

    await expect(page.getByRole("heading", { level: 1 })).toBeFocused();
  });
});
