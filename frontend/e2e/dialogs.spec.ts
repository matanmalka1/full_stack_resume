import type { Page } from "@playwright/test";

import type { Operation } from "../src/api/contracts";
import { HASH, cvDocument, detail as recordDetail, operation } from "../src/test/records";
import { expect, json, test } from "./fixtures";

/* Real keyboard navigation verifies Tab boundary wrapping, native modal focus
   restoration, and Escape reaching the element's cancel behavior. */

const detail = {
  recruitment_status: "recruiter_screen",
  allowed_recruitment_transitions: ["interview", "rejected", "withdrawn", "closed"],
  recruitment_timeline: [],
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
    current_status: "recruiter_screen",
    next_action: "Follow up",
    next_action_date: "2026-09-05",
    notes: "Referral from a former colleague",
    created_at: "2026-08-24T07:00:00Z",
    updated_at: "2026-08-25T08:00:00Z",
  },
  job_posting: {
    job_text: "Senior Backend Engineer",
    source_url: "https://example.com/jobs/1",
    job_text_hash: "c".repeat(64),
    job_text_updated_at: "2026-08-24T07:00:00Z",
    locked: false,
  },
};

test.describe("dialogs", () => {
  test.beforeEach(({ api }) => {
    api.stub("GET /api/v1/applications/app-1", json(detail));
    /* The search palette opens on the Applications needing attention. */
    api.stub(
      "GET /api/v1/applications?preset=needs_attention&limit=8",
      json({ items: [], total: 0, limit: 8, offset: 0 }),
    );
  });

  /* Whether focus is inside the open modal. Read from `document.activeElement` rather
     than a `:focus` locator, which misses a date field whose focus sits in the input's
     own shadow parts. */
  const focusInsideOpenDialog = (page: Page) =>
    page.evaluate(() => document.activeElement?.closest("dialog[open]") != null);

  /* The hub's status sheet: a modal form with a free-text field, so it carries both the
     focus trap and the rule that a stray backdrop click does not discard typing. */
  const openStatusDialog = async (page: Page) => {
    await page.goto("/applications/app-1");
    const invoker = page.getByRole("button", { name: "עדכון סטטוס" });
    await invoker.click();
    const dialog = page.getByRole("dialog", { name: "עדכון סטטוס ומשימות" });
    await expect(dialog).toBeVisible();
    return { dialog, invoker };
  };

  test("opens on its heading, keeps Tab inside, and hands focus back on Escape", async ({ page }) => {
    const { dialog, invoker } = await openStatusDialog(page);

    await expect(dialog.getByRole("heading", { name: "עדכון סטטוס ומשימות" })).toBeFocused();

    await expect(dialog.locator("div").first()).toHaveAttribute("dir", "rtl");

    /* More presses than the dialog has stops, so a trap that leaked would have reached the
       page behind it by now. The presses are a sequence by nature - each one moves the
       focus the next one starts from - so they are awaited one at a time. */
    // oxlint-disable-next-line no-await-in-loop
    for (let step = 0; step < 12; step += 1) {
      // oxlint-disable-next-line no-await-in-loop
      await page.keyboard.press("Tab");
      // oxlint-disable-next-line no-await-in-loop
      await expect.poll(() => focusInsideOpenDialog(page)).toBe(true);
    }
    for (let step = 0; step < 12; step += 1) {
      // oxlint-disable-next-line no-await-in-loop
      await page.keyboard.press("Shift+Tab");
      // oxlint-disable-next-line no-await-in-loop
      await expect.poll(() => focusInsideOpenDialog(page)).toBe(true);
    }

    await page.keyboard.press("Escape");

    await expect(dialog).toBeHidden();
    await expect(invoker).toBeFocused();
  });

  test("does not discard typing when the backdrop is clicked", async ({ page }) => {
    const { dialog, invoker } = await openStatusDialog(page);
    const notes = dialog.getByRole("textbox", { name: "הערות" });

    await notes.fill("שיחה טובה עם המגייסת");
    await page.mouse.click(5, 5);

    await expect(dialog).toBeVisible();
    await expect(notes).toHaveValue("שיחה טובה עם המגייסת");

    /* The deliberate route out still closes, and still returns focus. */
    await page.keyboard.press("Escape");
    await expect(dialog).toBeHidden();
    await expect(invoker).toBeFocused();
  });

  test("closes on the backdrop while nothing has been typed", async ({ page }) => {
    const { dialog, invoker } = await openStatusDialog(page);

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
    const trigger = page.getByRole("button", { name: "מעבר מהיר למועמדות" });
    const palette = page.getByRole("dialog", { name: "מעבר מהיר למועמדות" });

    await trigger.click();
    await expect(palette).toBeVisible();

    await page.keyboard.press("Escape");

    await expect(palette).toBeHidden();
    await expect(trigger).toBeFocused();
  });

  /* Work in flight on a step that stays on screen - the draft editor's regeneration - sits
     beside the page. Hiding it with Escape hands focus to the chip that reopens it - not to
     whatever held focus when the screen opened the overlay by itself - and the report the
     chip opens is a dialog that does close on Escape. (The analysis and the draft's
     creation are the step's whole screen while they run; see OperationOverlay.) */
  test("puts a live run's panel away only from its close button and opens the report from its chip", async ({
    api,
    page,
  }) => {
    const running: Operation = {
      ...operation(),
      operation_type: "regenerate_section",
      status: "running",
      phase: "executing",
      is_terminal: false,
    };
    const documentPath = "/api/v1/applications/app-1/document";
    api.stub(
      "GET /api/v1/applications/app-1",
      json(
        recordDetail({
          content_check: "none",
          available_actions: ["edit", "check", "approve"],
          recommended_action: "check",
          active_operation: running,
          latest_operation: running,
        }),
      ),
    );
    api.stub(`GET ${documentPath}`, json(cvDocument({ content_check: "none" }), { headers: { ETag: `"${HASH}"` } }));
    api.stub(
      `GET ${documentPath}/page-count`,
      json({
        application_id: "app-1",
        document_id: "doc-1",
        document_hash: HASH,
        template: null,
        pages: 1,
        maximum: 1,
      }),
    );
    api.stub(`GET ${documentPath}/preview?v=${HASH}`, (route) =>
      route.fulfill({ contentType: "text/html", body: "<!doctype html><title>Preview</title>" }),
    );
    api.stub(`GET /api/v1/operations/${running.id}`, json(running));
    api.stub("GET /api/v1/facts", json({ items: [] }));
    api.stub("GET /api/v1/facts/history", json({ events: [] }));

    await page.goto("/applications/app-1/draft");
    /* Live work is a panel beside the page, not a modal: Escape leaves it where it is,
       and only its own close button puts it away. */
    const panel = page.getByRole("region", { name: "הרצת יצירה מחדש של פרק" });
    await expect(panel).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(panel).toBeVisible();

    await panel.getByRole("button", { name: "סגירה" }).click();
    await expect(panel).toBeHidden();
    const chip = page.getByRole("button", { name: /פירוט ההרצה/ });
    await expect(chip).toBeFocused();

    const report = page.getByRole("dialog", { name: "הרצת יצירה מחדש של פרק" });
    await chip.click();
    await expect(report).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(report).toBeHidden();
    await expect(chip).toBeFocused();
  });
});
