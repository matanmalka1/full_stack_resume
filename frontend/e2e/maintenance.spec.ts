import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const settings = {
  edit_version: 0,
  auto_generate_when_review_not_required: false,
  ai_enabled: false,
  ai_enabled_override: null,
  default_execution_mode: "deterministic",
  provider_configured: false,
  ui_density: "comfortable",
  ui_text_size: "normal",
  updated_at: null,
};

const report = {
  passed: false,
  artifact_versions_checked: 2,
  problems: ["missing artifact: artifacts/outputs/revision-1/resume.pdf"],
  fact_lifecycle: {
    passed: false,
    fact_counts: { canonical: 2, pending: 1 },
    tracked_facts: 3,
    facts_version: "facts-version-1",
    lifecycle_version: "lifecycle-version-1",
    problems: ["fact audit mismatch"],
    journal_prepared: 0,
    journal_quarantined: 1,
  },
};

test.describe("the Settings reconciliation panel", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/api/v1/settings", async (route) => {
      await route.fulfill({ contentType: "application/json", json: settings });
    });
    await page.route("**/api/v1/maintenance/reconciliations", async (route) => {
      expect(route.request().method()).toBe("POST");
      await route.fulfill({ contentType: "application/json", json: report });
    });
  });

  test("runs the report and has no automatically detectable accessibility violations", async ({
    page,
  }) => {
    await page.goto("/settings");
    await page.getByRole("button", { name: "הפעלת בדיקת התאמה" }).click();

    await expect(page.getByText("קבצים חסרים: 1")).toBeVisible();
    await expect(page.getByText("מה צריך לעשות")).toBeVisible();
    await page.getByText("פרטים טכניים").click();
    await expect(
      page.getByText("missing artifact: artifacts/outputs/revision-1/resume.pdf"),
    ).toBeVisible();
    await expect(page.getByText("fact audit mismatch")).toBeVisible();

    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();

    expect(results.violations).toEqual([]);
  });
});
