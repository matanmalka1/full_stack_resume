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

const detail = {
  recruitment_status: "recruiter_screen",
  allowed_recruitment_transitions: ["interview", "rejected", "withdrawn", "closed"],
  recruitment_timeline: [],
  preparation_state: "needs_analysis",
  working_draft_state: "none",
  review_reasons: [],
  stale_reasons: [],
  warnings: [],
  active_job_snapshot_id: "snap-1",
  newer_draft_in_progress: false,
  available_actions: ["analyze"],
  blocked_actions: [],
  recommended_action: "analyze",
  application: {
    id: "app-1",
    company: "Acme",
    target_role: "Backend Engineer",
    current_status: "recruiter_screen",
    next_action: "Follow up",
    next_action_date: "2026-09-05",
    notes: "Referral from a former colleague",
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

test.describe("the Job Detail screen", () => {
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

  test("owns job and recruitment facts and has no automatically detectable accessibility violations", async ({
    page,
  }) => {
    await page.goto("/applications/app-1");

    await expect(page.getByRole("heading", { level: 1, name: "Backend Engineer" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "מודעת המשרה" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "מעקב גיוס" })).toBeVisible();
    await expect(page.getByRole("link", { name: "עדכון מעקב הגיוס" })).toHaveAttribute("href", "#recruitment-heading");
    await expect(page.getByRole("link", { name: "מעבר להכנת קורות החיים" })).toHaveAttribute(
      "href",
      "/applications/app-1/preparation",
    );
    /* The job record is the entrance to an Application, not a stage of the CV workflow,
       so no landmark is drawn here: this screen is still opened months after the document
       is done, and it takes no part in the four stages the bar counts. */
    await expect(page.getByRole("navigation", { name: /^שלבי הכנת קורות החיים:/ })).toHaveCount(0);
    await expect(page.getByRole("img", { name: /^שלבי הכנת קורות החיים:/ })).toHaveCount(0);
    await expect(page.getByRole("navigation", { name: "חזרה ללוח המועמדויות" })).toBeVisible();

    /* The door first, then what the job is: preparation is the work started from here,
       not another fact about the posting. */
    await expect(page.getByRole("heading", { level: 2 })).toHaveText([
      "הכנת קורות החיים",
      "פרטי המועמדות",
      "מעקב גיוס",
      "מודעת המשרה",
    ]);

    const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();

    expect(results.violations).toEqual([]);

    await page.getByRole("button", { name: "עדכון נוסח המשרה" }).click();
    await expect(page.getByRole("dialog", { name: "יצירת תצלום משרה חדש" })).toBeVisible();
    const dialogResults = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();
    expect(dialogResults.violations).toEqual([]);
  });
});
