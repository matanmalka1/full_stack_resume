import { AxeBuilder } from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

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

test.describe("the facts integrity check", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/api/v1/facts", async (route) => {
      await route.fulfill({ contentType: "application/json", json: { items: [] } });
    });
    await page.route("**/api/v1/maintenance/reconciliations", async (route) => {
      expect(route.request().method()).toBe("POST");
      await route.fulfill({ contentType: "application/json", json: report });
    });
  });

  test("runs the report and has no automatically detectable accessibility violations", async ({ page }) => {
    await page.goto("/facts");
    await page.getByRole("button", { name: "הפעלה" }).click();

    await expect(
      page.getByText("1 אי־התאמות בעובדות, 1 בעיות בתוצרים — הבדיקה מדווחת בלבד ואינה מתקנת נתונים."),
    ).toBeVisible();
    await page.getByText("הבעיות שנמצאו (2)").click();
    await expect(page.getByText("missing artifact: artifacts/outputs/revision-1/resume.pdf")).toBeVisible();
    await expect(page.getByText("fact audit mismatch")).toBeVisible();

    const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();

    expect(results.violations).toEqual([]);
  });
});
