import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

/* The landmark stopped being a picture of progress and became the way back through it.
   What that added is a link per stage the projection has already reached, so this spec
   proves the two things the unit tests cannot: that clicking one lands on the screen it
   names, and that the navigation landmark it turns into is still clean under axe. */

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

/* Mid-workflow on purpose: a draft exists, so טיוטה and אימות have a screen, and the
   reader is on neither of them. */
const detail = {
  recruitment_status: "saved",
  allowed_recruitment_transitions: ["withdrawn", "closed"],
  recruitment_timeline: [],
  preparation_state: "ready_for_approval",
  working_draft_state: "validated",
  review_reasons: [],
  stale_reasons: [],
  warnings: [],
  active_job_snapshot_id: "snap-1",
  active_analysis_id: "analysis-1",
  active_working_draft_id: "draft-1",
  newer_draft_in_progress: false,
  available_actions: ["approve_draft"],
  blocked_actions: [],
  recommended_action: "approve_draft",
  application: {
    id: "app-1",
    company: "Acme",
    target_role: "Backend Engineer",
    current_status: "saved",
    notes: "",
    source: "manual",
    created_at: "2026-08-24T07:00:00Z",
    updated_at: "2026-08-25T08:00:00Z",
  },
  latest_snapshot: {
    id: "snap-1",
    application_id: "app-1",
    version_number: 1,
    job_text: "Senior Backend Engineer",
    source_url: "https://example.com/jobs/1",
    captured_at: "2026-08-24T07:00:00Z",
    source_metadata: {},
    content_hash: "hash-1",
  },
};

test.describe("the workflow landmark", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/api/v1/settings", async (route) => {
      await route.fulfill({ contentType: "application/json", json: settings });
    });
    await page.route("**/api/v1/applications/app-1", async (route) => {
      await route.fulfill({ contentType: "application/json", json: detail });
    });
    await page.route("**/api/v1/applications/app-1/artifacts", async (route) => {
      await route.fulfill({ contentType: "application/json", json: { items: [] } });
    });
  });

  test("counts only the CV stages and leaves the job record to the page's own way back", async ({ page }) => {
    await page.goto("/applications/app-1/preparation");

    const workflow = page.getByRole("navigation", { name: /^שלבי הכנת קורות החיים:/ });
    await expect(workflow).toBeVisible();
    /* The stage whose screen is open offers no link to itself. */
    await expect(workflow.getByRole("link", { name: "חזרה לשלב ניתוח" })).toHaveCount(0);
    /* Nothing ahead of the current stage opens, because the projection has not produced
       the record such a screen would show. */
    await expect(workflow.getByRole("link", { name: /לשלב מוכן$/ })).toHaveCount(0);
    /* The job record is not a stage: it is the entrance the work is started from, and the
       bar neither counts it nor leads to it. */
    await expect(workflow.getByRole("link", { name: /משרה חדשה/ })).toHaveCount(0);
    await expect(workflow.getByRole("link", { name: "חזרה לשלב טיוטה" })).toBeVisible();

    await page.getByRole("navigation", { name: "חזרה לפרטי המשרה" }).getByRole("link").click();

    await expect(page.getByRole("heading", { level: 1, name: "Backend Engineer" })).toBeVisible();
    await expect(page).toHaveURL(/\/applications\/app-1$/);
  });

  test("marks the stage in progress and has no accessibility violations as a navigation landmark", async ({ page }) => {
    await page.goto("/applications/app-1/preparation");

    const workflow = page.getByRole("navigation", { name: /^שלבי הכנת קורות החיים:/ });
    /* אימות is the current stage and its screen is the editor, which is not this screen -
       so it is a link, and it says which stage the work is on rather than pretending to
       be a way back. */
    await expect(workflow.getByRole("link", { name: "מעבר לשלב אימות" })).toHaveAttribute("aria-current", "step");

    const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();

    expect(results.violations).toEqual([]);
  });
});
