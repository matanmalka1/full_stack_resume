import { AxeBuilder } from "@axe-core/playwright";
import { expect, json, test } from "./fixtures";

const report = {
  passed: false,
  payloads_checked: 2,
  ai_calls_checked: 1,
  problems: ["AI call response hash mismatch: ai-call-1"],
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
  test.beforeEach(({ api }) => {
    api.stub("GET /api/v1/facts", json({ items: [] }));
    api.stub("POST /api/v1/maintenance/reconciliations", json(report));
  });

  test("runs the report and has no automatically detectable accessibility violations", async ({ page }) => {
    await page.goto("/facts");
    await page.getByRole("button", { name: "הפעלה" }).click();

    await expect(
      page.getByText("1 אי־התאמות בעובדות, 1 בעיות בקבצים או בקריאות AI — הבדיקה מדווחת בלבד ואינה מתקנת נתונים."),
    ).toBeVisible();
    await page.getByText("הבעיות שנמצאו (2)").click();
    await expect(page.getByText("AI call response hash mismatch: ai-call-1")).toBeVisible();
    await expect(page.getByText("fact audit mismatch")).toBeVisible();

    const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();

    expect(results.violations).toEqual([]);
  });
});
