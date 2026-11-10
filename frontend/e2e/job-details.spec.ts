import { AxeBuilder } from "@axe-core/playwright";
import { expect, json, test } from "./fixtures";

const detail = {
  preparation_state: "needs_analysis",
  content_check: "none",
  review_reasons: [],
  warnings: [],
  job_text_hash: "c".repeat(64),
  available_actions: ["analyze"],
  blocked_actions: [],
  recommended_action: "analyze",
  application: {
    id: "app-1",
    company: "Acme",
    target_role: "Backend Engineer",
    notes: "Referral from a former colleague",
    created_at: "2026-08-24T07:00:00Z",
    updated_at: "2026-08-25T08:00:00Z",
  },
  job_posting: {
    job_text: "Senior Backend Engineer",
    source_url: "https://example.com/jobs/1",
    job_text_hash: "c".repeat(64),
    job_text_updated_at: "2026-08-24T07:00:00Z",
  },
};

test.describe("the Application hub", () => {
  test.beforeEach(({ api }) => {
    api.stub("GET /api/v1/applications/app-1", json(detail));
  });

  test("has no automatically detectable accessibility violations", async ({ page }) => {
    await page.goto("/applications/app-1");

    const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();

    expect(results.violations).toEqual([]);
  });

  test("edits the posting from the record's menu in an accessible dialog", async ({ page }) => {
    await page.goto("/applications/app-1");

    await page.locator('button[aria-label="פעולות נוספות"]:visible').click();
    await page.getByRole("menuitem", { name: "עריכת נוסח המשרה" }).click();
    const dialog = page.getByRole("dialog", { name: "עריכת נוסח המשרה" });
    await expect(dialog).toBeVisible();
    await expect(dialog).toHaveCSS("opacity", "1");
    await expect(dialog.getByRole("textbox", { name: "טקסט המשרה" })).toHaveValue("Senior Backend Engineer");

    const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
    expect(results.violations).toEqual([]);
  });
});
