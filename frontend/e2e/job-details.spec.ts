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

    await expect(page.getByRole("heading", { level: 1, name: "פרטי משרה" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "מודעת המשרה" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "מעקב גיוס" })).toBeVisible();
    await expect(page.getByRole("link", { name: "הכנת קורות החיים" })).toHaveAttribute(
      "href",
      "/applications/app-1/preparation",
    );
    /* Job Detail is where the landmark's intake step leads, so the landmark is present
       here rather than dropped: a screen that is a destination of the bar cannot be a
       screen the bar disappears on. It is a navigation landmark because a stage behind
       the reader can be opened; the step for this very screen carries no link. */
    const workflow = page.getByRole("navigation", { name: /^שלבי הכנת קורות החיים:/ });
    await expect(workflow).toBeVisible();
    await expect(workflow.getByRole("link", { name: "חזרה לשלב משרה חדשה" })).toHaveCount(0);

    const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();

    expect(results.violations).toEqual([]);
  });
});
