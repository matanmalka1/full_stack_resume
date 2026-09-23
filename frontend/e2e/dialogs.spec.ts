import { expect, test, type Page } from "@playwright/test";

/* Real keyboard navigation verifies Tab boundary wrapping, native modal focus
   restoration, and Escape reaching the element's cancel behavior. */

const settings = {
  edit_version: 0,
  auto_generate_when_review_not_required: false,
  ai_enabled: false,
  ai_enabled_override: null,
  default_execution_mode: "deterministic",
  provider_configured: false,
  ui_density: "comfortable",
  ui_text_size: "normal",
  ui_theme: "system",
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

test.describe("dialogs", () => {
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
    /* Matched on the path itself: a glob wide enough to catch the list's query string
       also catches the detail request routed above it. */
    await page.route(
      (url) => url.pathname === "/api/v1/applications",
      async (route) => {
        await route.fulfill({ contentType: "application/json", json: { items: [], total: 0, limit: 8, offset: 0 } });
      },
    );
  });

  const openJobPostingDialog = async (page: Page) => {
    await page.goto("/applications/app-1");
    await page.getByText("צפייה בנוסח המשרה שנשמר", { exact: true }).click();
    const invoker = page.getByRole("button", { name: "עדכון נוסח המשרה" });
    await invoker.click();
    const dialog = page.getByRole("dialog", { name: "יצירת תצלום משרה חדש" });
    await expect(dialog).toBeVisible();
    return { dialog, invoker };
  };

  test("opens on its heading, keeps Tab inside, and hands focus back on Escape", async ({ page }) => {
    const { dialog, invoker } = await openJobPostingDialog(page);

    await expect(dialog.getByRole("heading", { name: "יצירת תצלום משרה חדש" })).toBeFocused();

    await expect(dialog.locator("div").first()).toHaveAttribute("dir", "rtl");

    /* More presses than the dialog has stops, so a trap that leaked would have reached the
       page behind it by now. The presses are a sequence by nature - each one moves the
       focus the next one starts from - so they are awaited one at a time. */
    // oxlint-disable-next-line no-await-in-loop
    for (let step = 0; step < 12; step += 1) {
      // oxlint-disable-next-line no-await-in-loop
      await page.keyboard.press("Tab");
      // oxlint-disable-next-line no-await-in-loop
      await expect(dialog.locator(":focus")).toHaveCount(1);
    }
    for (let step = 0; step < 12; step += 1) {
      // oxlint-disable-next-line no-await-in-loop
      await page.keyboard.press("Shift+Tab");
      // oxlint-disable-next-line no-await-in-loop
      await expect(dialog.locator(":focus")).toHaveCount(1);
    }

    await page.keyboard.press("Escape");

    await expect(dialog).toBeHidden();
    await expect(invoker).toBeFocused();
  });

  test("does not discard typing when the backdrop is clicked", async ({ page }) => {
    const { dialog, invoker } = await openJobPostingDialog(page);
    const jobText = dialog.getByRole("textbox", { name: "טקסט המשרה" });

    await jobText.fill("נוסח משרה מעודכן");
    await page.mouse.click(5, 5);

    await expect(dialog).toBeVisible();
    await expect(jobText).toHaveValue("נוסח משרה מעודכן");

    /* The deliberate route out still closes, and still returns focus. */
    await page.keyboard.press("Escape");
    await expect(dialog).toBeHidden();
    await expect(invoker).toBeFocused();
  });

  test("closes on the backdrop while nothing has been typed", async ({ page }) => {
    const { dialog, invoker } = await openJobPostingDialog(page);

    await page.mouse.click(5, 5);

    await expect(dialog).toBeHidden();
    await expect(invoker).toBeFocused();
  });

  test("opens the search palette on the shortcut with focus in its field", async ({ page }) => {
    await page.goto("/applications/app-1");
    const palette = page.getByRole("dialog", { name: "מעבר מהיר למועמדות" });
    await expect(palette).toBeHidden();

    await page.keyboard.press("ControlOrMeta+k");

    await expect(palette).toBeVisible();
    await expect(palette.getByRole("combobox")).toBeFocused();

    await page.keyboard.press("Shift+Tab");
    await expect(palette.locator(":focus")).toHaveCount(1);
    await page.keyboard.press("Tab");
    await expect(palette.getByRole("combobox")).toBeFocused();

    await page.keyboard.press("Escape");
    await expect(palette).toBeHidden();
  });

  /* Where focus lands on close is wherever it came from, which is the trigger only when
     the trigger is what opened the palette. Opening on the shortcut from an unfocused page
     restores focus to the body, and that is correct rather than a lost trigger. */
  test("returns focus to the palette trigger that opened it", async ({ page }) => {
    await page.goto("/applications/app-1");
    const trigger = page.getByRole("button", { name: "מעבר מהיר למועמדות (Cmd+K)" });
    const palette = page.getByRole("dialog", { name: "מעבר מהיר למועמדות" });

    await trigger.click();
    await expect(palette).toBeVisible();

    await page.keyboard.press("Escape");

    await expect(palette).toBeHidden();
    await expect(trigger).toBeFocused();
  });

  /* Work in flight sits over the page. Hiding it with Escape hands focus to the chip that
     reopens it - not to whatever held focus when the screen opened the overlay by itself -
     and does not make the page safe to change: the commands that conflict with the run
     stay locked while it is live. */
  test("hides a live run on Escape, keeps conflicting actions locked, and reopens from its chip", async ({
    page,
  }) => {
    const running = {
      id: "op-1",
      application_id: "app-1",
      operation_type: "create_draft",
      status: "running",
      phase: "executing",
      is_terminal: false,
      available_actions: [],
      outputs: [],
      message: "",
      created_at: "2026-08-24T07:00:00Z",
    };
    await page.route("**/api/v1/applications/app-1", async (route) => {
      await route.fulfill({
        contentType: "application/json",
        json: { ...detail, active_operation: running, latest_operation: running },
      });
    });
    await page.route("**/api/v1/operations/op-1", async (route) => {
      await route.fulfill({ contentType: "application/json", json: running });
    });

    await page.goto("/applications/app-1");
    const overlay = page.getByRole("dialog", { name: "הרצת יצירת הטיוטה" });
    await expect(overlay).toBeVisible();

    await page.keyboard.press("Escape");
    await expect(overlay).toBeHidden();
    const chip = page.getByRole("button", { name: /פירוט ההרצה/ });
    await expect(chip).toBeFocused();
    await expect(chip).toContainText("מתבצעת");

    await page.getByText("צפייה בנוסח המשרה שנשמר", { exact: true }).click();
    await expect(page.getByRole("button", { name: "עדכון נוסח המשרה" })).toBeDisabled();

    await chip.click();
    await expect(overlay).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(overlay).toBeHidden();
    await expect(chip).toBeFocused();
  });
});
