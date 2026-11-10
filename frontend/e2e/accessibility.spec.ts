import { AxeBuilder } from "@axe-core/playwright";
import type { Page } from "@playwright/test";

import type { ApplicationListItem, ApplicationListResponse } from "../src/api/contracts";
import { HASH, cvDocument, detail, documentCheck } from "../src/test/records";
import { expect, json, test } from "./fixtures";

/* Axe scans of the screens whose own specs are Vitest-only: the board, the Resume
   resolver, the draft editor, the Ready screen, Settings, and Not Found. New Application,
   the Application hub, and the Facts integrity check carry their scans in their own specs. Every
   API read is stubbed through the shared fixture, which fails a test on any other. */

const scan = async (page: Page, exclude: string[] = []) => {
  const builder = new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]);
  for (const selector of exclude) builder.exclude(selector);
  const results = await builder.analyze();
  expect(results.violations).toEqual([]);
};

/* A CV preview is the server-rendered document in a `sandbox=""` frame. Axe cannot run
   scripts there and waits on the frame until the test times out; the document inside is
   the backend's render output, checked by its render validation, not this app's UI. The
   frame's title is asserted by the test itself. */
const DRAFT_PREVIEW = 'iframe[title="תצוגה מקדימה של הטיוטה"]';
const READY_PREVIEW = 'iframe[title="קורות החיים המוכנים"]';

const previewHtml =
  '<!doctype html><html lang="en"><head><title>Preview</title></head><body><main><h1>Account Manager</h1><p>Owned the CRM migration.</p></main></body></html>';

const listItem = (overrides: Partial<ApplicationListItem>): ApplicationListItem => ({
  id: "app-1",
  company: "Acme",
  target_role: "Backend Engineer",
  notes: "",
  created_at: "2026-08-24T07:00:00Z",
  updated_at: "2026-08-24T07:00:00Z",
  preparation_state: "needs_analysis",
  content_check: "none",
  review_reasons: [],
  warnings: [],
  job_text_hash: "c".repeat(64),
  available_actions: ["analyze"],
  blocked_actions: [],
  recommended_action: "analyze",
  ...overrides,
});

const board = (): ApplicationListResponse => {
  const items = [
    listItem({}),
    listItem({
      id: "app-2",
      company: "Globex",
      target_role: "Account Executive",
      preparation_state: "ready",
      content_check: "passed",
      job_text_hash: "d".repeat(64),
      available_actions: ["download"],
      recommended_action: null,
    }),
  ];
  return {
    items,
    matched: items.length,
    total: items.length,
    limit: 200,
    offset: 0,
    preset_counts: { all: 2, ready_to_send: 1, needs_attention: 0 },
    stage_counts: { needs_analysis: 1, ready: 1 },
  };
};

test.describe("accessibility", () => {
  test("the application board has no automatically detectable violations", async ({ api, page }) => {
    /* The board reads its list once; the action hub is drawn from the same answer. */
    api.stub("GET /api/v1/applications?limit=200&sort=updated", json(board()));

    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1, name: "לוח המועמדויות" })).toBeVisible();
    await expect(page.getByText("Globex").first()).toBeVisible();

    await scan(page);
  });

  /* The resolver renders a screen of its own only while it reads or when the read fails;
     a successful read redirects to a screen that carries its own scan. The failure is the
     state a reader can stay on. */
  test("the Resume view's failure state has no automatically detectable violations", async ({ api, page }) => {
    api.stub(
      "GET /api/v1/applications/app-1",
      json({ type: "about:blank", title: "Internal Server Error", status: 500 }, { status: 500 }),
    );

    await page.goto("/applications/app-1/resume");
    await expect(page.getByText("לא ניתן לטעון את פרטי המועמדות")).toBeVisible();
    await expect(page.getByRole("button", { name: "ניסיון חוזר" })).toBeEnabled();

    await scan(page);
  });

  test("the draft editor and its approval dialog have no automatically detectable violations", async ({
    api,
    page,
  }) => {
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
        },
        {
          fact_id: "f-mail",
          text: "candidate@example.com",
          linked_claim_ids: ["c-mail"],
          section: null,
        },
      ],
    });
    const documentPath = "/api/v1/applications/app-1/document";
    api.stub(
      "GET /api/v1/applications/app-1",
      json(
        detail({ content_check: "none", available_actions: ["edit", "check", "approve"], recommended_action: "check" }),
      ),
    );
    api.stub(`GET ${documentPath}`, json(draft, { headers: { ETag: `"${HASH}"` } }));
    /* The preview frame's source carries the document hash as its cache key. */
    api.stub(`GET ${documentPath}/preview?v=${HASH}`, (route) =>
      route.fulfill({ contentType: "text/html", body: previewHtml }),
    );
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
    api.stub(`POST ${documentPath}/check`, json(documentCheck()));
    api.stub("GET /api/v1/facts", json({ items: [] }));
    api.stub("GET /api/v1/facts/history", json({ events: [] }));

    await page.goto("/applications/app-1/draft");
    await expect(page.getByText("Owned the CRM migration.").first()).toBeVisible();

    await scan(page);

    /* The rendered document is behind the heading's preview toggle. */
    const preview = page.getByRole("button", { name: "תצוגה מקדימה" });
    await preview.click();
    await expect(preview).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByTitle("תצוגה מקדימה של הטיוטה")).toBeVisible();

    await scan(page, [DRAFT_PREVIEW]);

    await page.getByRole("button", { name: "אישור הטיוטה ויצירת הקובץ" }).click();
    const approval = page.getByRole("dialog", { name: "אישור והכנת PDF" });
    await expect(approval).toBeVisible();
    await expect(approval).toHaveCSS("opacity", "1");

    await scan(page, [DRAFT_PREVIEW]);
  });

  test("the Settings screen and its template dialog have no automatically detectable violations", async ({
    api,
    page,
  }) => {
    await page.goto("/settings");
    await expect(page.getByRole("radio", { name: "לפי המכשיר" })).toBeChecked();

    await scan(page);

    /* The dialog frames the sample CV in every template; the frames are presentation
       only, so a blank page answers them. */
    for (const template of ["track", "latex", "deedy"]) {
      api.stub(`GET /api/v1/templates/${template}/sample?language=he`, (route) =>
        route.fulfill({ contentType: "text/html", body: "<!doctype html><title>sample</title>" }),
      );
    }
    await page.getByRole("button", { name: /^תבנית עיצוב/ }).click();
    const dialog = page.getByRole("dialog", { name: "בחירת תבנית" });
    await expect(dialog).toHaveCSS("opacity", "1");

    await scan(page, ['iframe[title^="תצוגה מקדימה:"]']);
  });

  test("the Not Found screen has no automatically detectable violations", async ({ page }) => {
    await page.goto("/no-such-screen");
    await expect(page.getByRole("heading", { level: 1, name: "העמוד לא נמצא" })).toBeVisible();

    await scan(page);
  });

  test("the Ready screen has no automatically detectable violations", async ({ api, page }) => {
    const approvedAt = "2026-08-25T08:00:00Z";
    const documentPath = "/api/v1/applications/app-1/document";
    api.stub(
      "GET /api/v1/applications/app-1",
      json(
        detail({
          preparation_state: "ready",
          approved_at: approvedAt,
          available_actions: ["edit", "download_pdf"],
          recommended_action: "download_pdf",
        }),
      ),
    );
    api.stub(
      `GET ${documentPath}`,
      json(cvDocument({ preparation_state: "ready", approved_at: approvedAt }), { headers: { ETag: `"${HASH}"` } }),
    );
    api.stub(
      `GET ${documentPath}/decision-markdown`,
      json({ application_id: "app-1", document_id: "doc-1", markdown: "# Decision" }),
    );

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

    /* The Ready document itself, framed like the draft's preview. */
    api.stub(`GET ${documentPath}/preview?v=${HASH}`, (route) =>
      route.fulfill({ contentType: "text/html", body: previewHtml }),
    );

    await page.goto("/applications/app-1/ready");
    await expect(page.getByRole("heading", { level: 1, name: "קורות החיים מוכנים" })).toBeVisible();
    await expect(page.getByRole("link", { name: "הורדת PDF" }).first()).toBeVisible();
    await expect(page.locator(READY_PREVIEW)).toBeVisible();

    await scan(page, [READY_PREVIEW]);
  });
});
