import { AxeBuilder } from "@axe-core/playwright";
import { expect, test, type Page, type Route } from "@playwright/test";

import type { ApplicationListItem, ApplicationListResponse } from "../src/api/contracts";
import { HASH, cvDocument, detail, documentCheck, settings } from "../src/test/records";

/* Axe scans of the screens whose own specs are Vitest-only: the board, the Resume
   resolver, the draft editor, the Ready screen, Settings, and Not Found. New Application, Job Detail, and the Facts integrity
   check carry their scans in their own specs.

   Every `/api/v1` request goes through one handler. A screen that starts reading an
   endpoint these stubs do not answer fails the test by name, rather than rendering the
   preview server's HTML fallback as a broken reply and scanning an error state. */

type Answer = (route: Route) => Promise<void>;

const jsonAnswer =
  (body: unknown, status = 200, headers: Record<string, string> = {}): Answer =>
  (route) =>
    route.fulfill({ status, contentType: "application/json", headers, json: body });

const stubApi = async (page: Page, answers: Record<string, Answer>): Promise<string[]> => {
  const unstubbed: string[] = [];
  const table: Record<string, Answer> = { "GET /api/v1/settings": jsonAnswer(settings()), ...answers };
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const key = `${request.method()} ${new URL(request.url()).pathname}`;
    const answer = table[key];
    if (answer === undefined) {
      unstubbed.push(key);
      await route.fulfill({ status: 404, contentType: "application/problem+json", json: { status: 404 } });
      return;
    }
    await answer(route);
  });
  return unstubbed;
};

const scan = async (page: Page, exclude: string[] = []) => {
  const builder = new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]);
  for (const selector of exclude) builder.exclude(selector);
  const results = await builder.analyze();
  expect(results.violations).toEqual([]);
};

/* The draft preview is the server-rendered CV in a `sandbox=""` frame. Axe cannot run
   scripts there and waits on the frame until the test times out; the document inside is
   the backend's render output, checked by its render validation, not this app's UI. The
   frame's title is asserted by the test itself. */
const DRAFT_PREVIEW = 'iframe[title="תצוגה מקדימה של הטיוטה"]';

const listItem = (overrides: Partial<ApplicationListItem>): ApplicationListItem => ({
  id: "app-1",
  company: "Acme",
  target_role: "Backend Engineer",
  current_status: "saved",
  notes: "",
  created_at: "2026-08-24T07:00:00Z",
  updated_at: "2026-08-24T07:00:00Z",
  recruitment_status: "saved",
  preparation_state: "needs_analysis",
  document_state: "none",
  content_check: "none",
  review_reasons: [],
  warnings: [],
  active_job_snapshot_id: "snap-1",
  available_actions: ["analyze"],
  blocked_actions: [],
  recommended_action: "analyze",
  is_closed: false,
  ...overrides,
});

const board = (): ApplicationListResponse => {
  const items = [
    listItem({}),
    listItem({
      id: "app-2",
      company: "Globex",
      target_role: "Account Executive",
      current_status: "interview",
      recruitment_status: "interview",
      preparation_state: "ready",
      document_state: "ready",
      content_check: "passed",
      active_job_snapshot_id: "snap-2",
      available_actions: ["download"],
      recommended_action: null,
      next_action: "Prepare for the panel",
      next_action_date: "2026-09-05",
    }),
  ];
  return {
    items,
    matched: items.length,
    total: items.length,
    limit: 24,
    offset: 0,
    preset_counts: { all: 2, active_interviews: 1, ready_to_send: 1, needs_attention: 0 },
    recruitment_status_counts: { saved: 1, interview: 1 },
    stage_counts: { needs_analysis: 1, ready: 1 },
  };
};

test.describe("accessibility", () => {
  let unstubbed: string[] = [];

  test.afterEach(() => {
    expect(unstubbed, "requests with no stub").toEqual([]);
  });

  test("the application board has no automatically detectable violations", async ({ page }) => {
    unstubbed = await stubApi(page, { "GET /api/v1/applications": jsonAnswer(board()) });

    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1, name: "לוח מועמדויות" })).toBeVisible();
    await expect(page.getByText("Globex").first()).toBeVisible();

    await scan(page);
  });

  /* The resolver renders a screen of its own only while it reads or when the read fails;
     a successful read redirects to a screen that carries its own scan. The failure is the
     state a reader can stay on. */
  test("the Resume view's failure state has no automatically detectable violations", async ({ page }) => {
    unstubbed = await stubApi(page, {
      "GET /api/v1/applications/app-1": jsonAnswer(
        { type: "about:blank", title: "Internal Server Error", status: 500 },
        500,
      ),
    });

    await page.goto("/applications/app-1/resume");
    await expect(page.getByText("לא ניתן לטעון את פרטי המועמדות")).toBeVisible();
    await expect(page.getByRole("button", { name: "ניסיון חוזר" })).toBeEnabled();

    await scan(page);
  });

  test("the draft editor and its approval dialog have no automatically detectable violations", async ({ page }) => {
    const draft = cvDocument({
      content_check: "none",
      content_report: null,
      outline: {
        headline: {
          claim_id: "c-headline",
          style: "headline",
          text: "Account Manager",
          claim_type: "headline",
          fact_ids: [],
          pending_reason: null,
        },
        contacts: [
          {
            claim_id: "c-mail",
            style: "contact",
            text: "candidate@example.com",
            claim_type: "canonical",
            fact_ids: ["f-mail"],
            pending_reason: null,
          },
        ],
        sections: [
          {
            name: "Core Skills",
            claims: [
              {
                claim_id: "c-1",
                style: "bullet",
                text: "Owned the CRM migration.",
                claim_type: "canonical",
                fact_ids: ["f-1"],
                pending_reason: null,
              },
            ],
          },
        ],
      },
      facts: [
        {
          fact_id: "f-1",
          text: "Owned the CRM migration end to end.",
          linked_claim_ids: ["c-1"],
          section: "Core Skills",
          outcome: "selected",
          reason: null,
        },
        {
          fact_id: "f-mail",
          text: "candidate@example.com",
          linked_claim_ids: ["c-mail"],
          section: null,
          outcome: null,
          reason: null,
        },
      ],
    });
    const documentPath = "/api/v1/applications/app-1/document";
    unstubbed = await stubApi(page, {
      "GET /api/v1/applications/app-1": jsonAnswer(
        detail({
          content_check: "none",
          available_actions: ["edit", "check", "approve"],
          recommended_action: "check",
        }),
      ),
      [`GET ${documentPath}`]: jsonAnswer(draft, 200, { ETag: `"${HASH}"` }),
      [`GET ${documentPath}/preview`]: (route) =>
        route.fulfill({
          contentType: "text/html",
          body: '<!doctype html><html lang="en"><head><title>Preview</title></head><body><main><h1>Account Manager</h1><p>Owned the CRM migration.</p></main></body></html>',
        }),
      [`POST ${documentPath}/check`]: jsonAnswer(documentCheck()),
      "GET /api/v1/applications/app-1/artifacts": jsonAnswer({ items: [] }),
      "GET /api/v1/facts": jsonAnswer({ items: [] }),
      "GET /api/v1/facts/history": jsonAnswer({ events: [] }),
    });

    await page.goto("/applications/app-1/draft");
    await expect(page.getByRole("button", { name: "עריכה ותצוגה" })).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByTitle("תצוגה מקדימה של הטיוטה")).toBeVisible();
    await expect(page.getByText("Owned the CRM migration.").first()).toBeVisible();

    await scan(page, [DRAFT_PREVIEW]);

    await page.getByRole("button", { name: "בדיקה והכנת PDF" }).click();
    const approval = page.getByRole("dialog", { name: "אישור והכנת PDF" });
    await expect(approval).toBeVisible();
    await expect(approval).toHaveCSS("opacity", "1");

    await scan(page, [DRAFT_PREVIEW]);
  });

  test("the Settings screen has no automatically detectable violations", async ({ page }) => {
    unstubbed = await stubApi(page, {});

    await page.goto("/settings");
    await expect(page.getByText("מדיניות הפעלה ותצוגה")).toBeVisible();

    await scan(page);
  });

  test("the Not Found screen has no automatically detectable violations", async ({ page }) => {
    unstubbed = await stubApi(page, {});

    await page.goto("/no-such-screen");
    await expect(page.getByRole("heading", { level: 1, name: "העמוד לא נמצא" })).toBeVisible();

    await scan(page);
  });

  test("the Ready screen and its submission dialog have no automatically detectable violations", async ({ page }) => {
    const approvedAt = "2026-08-25T08:00:00Z";
    const documentPath = "/api/v1/applications/app-1/document";
    unstubbed = await stubApi(page, {
      "GET /api/v1/applications/app-1": jsonAnswer(
        detail({
          preparation_state: "ready",
          document_state: "ready",
          approved_at: approvedAt,
          available_actions: ["edit", "submit", "download_pdf"],
          recommended_action: "submit",
        }),
      ),
      [`GET ${documentPath}`]: jsonAnswer(cvDocument({ document_state: "ready", approved_at: approvedAt }), 200, {
        ETag: `"${HASH}"`,
      }),
      [`GET ${documentPath}/decision-markdown`]: jsonAnswer({
        application_id: "app-1",
        document_id: "doc-1",
        markdown: "# Decision",
      }),
    });

    await page.goto("/applications/app-1/ready");
    await expect(page.getByRole("heading", { name: "מוכן למסירה" })).toBeVisible();
    await expect(page.getByRole("link", { name: "הורדת PDF" }).first()).toBeVisible();

    await scan(page);

    await page.getByRole("button", { name: "רישום ההגשה" }).click();
    const submission = page.getByRole("dialog", { name: "רישום הגשה קבועה" });
    await expect(submission).toBeVisible();
    await expect(submission).toHaveCSS("opacity", "1");

    await scan(page);
  });
});
