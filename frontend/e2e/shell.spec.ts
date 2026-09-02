import { expect, test } from "@playwright/test";

/* The foundation check: direction, the workflow landmark, and route focus, which belong
   to the shell rather than to whichever screen it happens to be hosting. The per-screen
   assertions and the axe scan for the New Application form live in its own spec, so a
   later change to the root route cannot quietly move what this file is proving. */
/* The shell's own stubs: the landmark belongs to the CV workflow, so proving it is drawn
   and dropped needs a screen inside that workflow, and that screen reads one Application
   from the API. */
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
  recruitment_status: "saved",
  allowed_recruitment_transitions: ["withdrawn", "closed"],
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

test.describe("the application shell", () => {
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

  test("serves a Hebrew RTL document with the workflow landmark", async ({ page }) => {
    await page.goto("/applications/app-1/preparation");

    await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
    await expect(page.getByRole("img", { name: /^שלבי הכנת קורות החיים:/ })).toBeVisible();
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  });

  /* Intake creates the job the workflow later acts on, and is not one of its stages. */
  test("draws no workflow landmark on the intake screen", async ({ page }) => {
    await page.goto("/applications/new");

    await expect(page.getByRole("heading", { level: 1, name: "משרה חדשה" })).toBeVisible();
    await expect(page.getByRole("img", { name: /^שלבי הכנת קורות החיים:/ })).toHaveCount(0);
  });

  test("moves focus to the page heading after a route change", async ({ page }) => {
    await page.goto("/applications/new");
    await page.getByRole("link", { name: "הגדרות" }).click();

    await expect(page.getByRole("heading", { level: 1 })).toBeFocused();
  });

  /* A screen publishes its stage, and the landmark holds it until the next screen speaks:
     it is no longer reset on unmount, because resetting flashed the first stage between two
     mid-workflow screens. That makes a screen outside the workflow say so explicitly, and
     this is the assertion that fails if one forgets - the landmark would otherwise carry
     the previous screen's stage into Settings and keep claiming it. */
  test("drops the workflow landmark on a screen outside the workflow", async ({ page }) => {
    await page.goto("/applications/app-1/preparation");
    const workflow = page.getByRole("img", { name: /^שלבי הכנת קורות החיים:/ });
    await expect(workflow).toBeVisible();

    await page.getByRole("link", { name: "הגדרות" }).click();

    await expect(workflow).toHaveCount(0);
  });
});
