import { readFile } from "node:fs/promises";

import type { APIRequestContext, Page } from "@playwright/test";

import { expect, test } from "./fixtures";

const postResponse = (page: Page, path: string) =>
  page.waitForResponse(
    (response) => new URL(response.url()).pathname === path && response.request().method() === "POST",
  );

async function operationSucceeded(request: APIRequestContext, id: string) {
  await expect
    .poll(
      async () => {
        const response = await request.get(`/api/v1/operations/${id}`);
        expect(response.status()).toBe(200);
        const operation = await response.json();
        if (operation.is_terminal) expect(operation.status, JSON.stringify(operation)).toBe("succeeded");
        return operation.status;
      },
      { timeout: 60_000 },
    )
    .toBe("succeeded");
}

test("analysis, AI draft, approval and real PDF compose through the browser", async ({ page, request }) => {
  test.setTimeout(120_000);
  const applications = "/api/v1/applications";
  await page.goto("/applications/new");
  await page.getByLabel("חברה", { exact: true }).fill("Browser Preparation Co");
  await page.getByLabel("תפקיד", { exact: true }).fill("Account Manager");
  const jobText = "Experience owning the full sales cycle.\nFluent English.";
  await page.getByLabel("טקסט המודעה", { exact: true }).fill(jobText);

  const createdResponse = postResponse(page, applications);
  // Intake starts analysis itself; capture it before pressing Create.
  const analysisResponse = page.waitForResponse(
    (response) =>
      /\/applications\/[^/]+\/analyses$/.test(new URL(response.url()).pathname) &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "שמירה וניתוח המשרה", exact: true }).click();
  const created = await createdResponse;
  expect(created.status()).toBe(201);
  const { application_id: id, job_text_hash: jobTextHash } = await created.json();
  const applicationPath = `${applications}/${id}`;
  const documentPath = `${applicationPath}/document`;
  const analyzed = await analysisResponse;
  expect(analyzed.status()).toBe(202);
  const firstAnalysisId = (await analyzed.json()).id;
  await expect
    .poll(async () => (await (await request.get(`/api/v1/operations/${firstAnalysisId}`)).json()).status)
    .toBe("failed");
  const retryResponse = postResponse(page, `/api/v1/operations/${firstAnalysisId}/retry`);
  // The failed run is the analysis step's whole screen, with the run again as its command.
  await page.getByRole("button", { name: "הרצה מחדש", exact: true }).click();
  const retried = await retryResponse;
  expect(retried.status()).toBe(202);
  const retriedOperation = await retried.json();
  expect(retriedOperation.retry_of_operation_id).toBe(firstAnalysisId);
  await operationSucceeded(request, retriedOperation.id);
  const analysisDetail = await request.get(applicationPath);
  expect(analysisDetail.status()).toBe(200);
  expect(await analysisDetail.json()).toMatchObject({
    preparation_state: "ready_to_draft",
    job_text_hash: jobTextHash,
    job_posting: { job_text: jobText, job_text_hash: jobTextHash },
  });

  // The draft is created on the verification step the analysis leads on to.
  await page.getByRole("link", { name: "המשך לטיוטה" }).click();
  await expect(page).toHaveURL(new RegExp(`/applications/${id}/verification$`));
  const draftedResponse = postResponse(page, `${documentPath}/draft`);
  await page.getByRole("button", { name: "יצירת טיוטה", exact: true }).click();
  const drafted = await draftedResponse;
  expect(drafted.status()).toBe(202);
  await operationSucceeded(request, (await drafted.json()).id);
  await expect(page).toHaveURL(new RegExp(`/applications/${id}/draft$`));
  // Reload proves the editor is reading persisted content, not navigation state.
  await page.reload();
  // A real concurrent writer makes the editor's ETag stale. No route interception:
  // the second write goes through the same HTTP boundary as another browser tab.
  const before = await request.get(documentPath);
  const beforeDocument = await before.json();
  const target = beforeDocument.outline.sections
    .flatMap(
      (section: { claims: { claim_id: string; text: string; fact_ids: string[]; claim_type: string }[] }) =>
        section.claims,
    )
    .find(
      (claim: { claim_type: string; fact_ids: string[] }) =>
        claim.claim_type === "canonical" && claim.fact_ids.length === 1,
    );
  expect(target).toBeDefined();
  // The editor shows one part of the CV at a time; open the one holding the target line.
  const targetSection = beforeDocument.outline.sections.find((section: { claims: { claim_id: string }[] }) =>
    section.claims.some((claim) => claim.claim_id === target.claim_id),
  );
  await page
    .getByRole("navigation", { name: "חלקי קורות החיים" })
    .getByRole("button", { name: targetSection.name, exact: true })
    .click();
  const row = page.locator(`[id="draft-claim-${target.claim_id}"]`);
  await row.getByRole("button", { name: "עריכת השורה", exact: true }).click();
  const concurrentText = "Managed a fictional division of 9999 people.";
  const localText = "My conflicting unsupported claim about 8888 people.";
  const concurrent = await request.patch(documentPath, {
    headers: { Origin: new URL(page.url()).origin, "If-Match": before.headers().etag! },
    data: {
      claim_edits: [{ claim_id: target.claim_id, fact_ids: target.fact_ids, text: concurrentText }],
      claim_removals: [],
      claim_additions: [],
    },
  });
  expect(concurrent.status()).toBe(200);
  const conflicted = page.waitForResponse(
    (response) => response.request().method() === "PATCH" && new URL(response.url()).pathname === documentPath,
  );
  await row.getByRole("textbox", { name: "טקסט השורה" }).fill(localText);
  await row.getByRole("textbox", { name: "טקסט השורה" }).blur();
  expect((await conflicted).status()).toBe(409);
  const conflict = page.getByRole("dialog", { name: "הטיוטה השתנתה בזמן העריכה" });
  await expect(conflict.getByText(localText, { exact: true })).toBeVisible();
  await expect(conflict.getByText(concurrentText, { exact: true })).toBeVisible();
  await conflict.getByRole("button", { name: "השארת הגרסה הנוכחית" }).click();
  await expect(conflict).not.toBeVisible();
  // A line waiting on the reader says why it holds approval back.
  const blocking = row.getByText(/אין עובדה שמאשרת את השורה הזו|הבדיקה מצאה טענה שאינה נתמכת בעובדות/);
  await expect(blocking).toBeVisible();
  const blockedCheck = postResponse(page, `${documentPath}/check`);
  await page.getByRole("button", { name: "אישור הטיוטה ויצירת הקובץ", exact: true }).click();
  expect((await (await blockedCheck).json()).passed).toBe(false);
  await expect(page.getByRole("dialog", { name: "אישור והכנת PDF" })).not.toBeVisible();
  // Correct through the UI using the original canonical wording; it must unblock
  // the same document, without an AI key or a bypass of the approval boundary.
  const editing = row.getByRole("textbox", { name: "טקסט השורה" });
  // A line waiting on the reader is edited through its "עריכה" pill.
  if (!(await editing.isVisible())) await row.getByRole("button", { name: "עריכה", exact: true }).click();
  const savedCorrection = page.waitForResponse(
    (response) => response.request().method() === "PATCH" && new URL(response.url()).pathname === documentPath,
  );
  await editing.fill(target.text);
  await editing.blur();
  expect((await savedCorrection).status()).toBe(200);
  await expect(blocking).not.toBeVisible();
  const checkResponse = postResponse(page, `${documentPath}/check`);
  await page.getByRole("button", { name: "אישור הטיוטה ויצירת הקובץ", exact: true }).click();
  const checked = await checkResponse;
  expect(checked.status()).toBe(200);
  expect((await checked.json()).passed).toBe(true);

  const approval = page.getByRole("dialog", { name: "אישור והכנת PDF" });
  await expect(approval).toBeVisible();
  const warnings = approval.getByRole("checkbox", { name: "קראתי את האזהרות ואני רוצה להמשיך באישור" });
  if (await warnings.isVisible()) await warnings.check();
  const approvedResponse = postResponse(page, `${documentPath}/approve`);
  const renderedResponse = postResponse(page, `${documentPath}/render`);
  await approval.getByRole("button", { name: "אישור והכנת PDF", exact: true }).click();
  const approved = await approvedResponse;
  expect(approved.status()).toBe(200);
  expect((await approved.json()).passed).toBe(true);
  const rendered = await renderedResponse;
  expect(rendered.status()).toBe(202);
  await operationSucceeded(request, (await rendered.json()).id);
  await expect(page).toHaveURL(new RegExp(`/applications/${id}/ready$`), { timeout: 30_000 });
  await page.reload();
  await expect(page.getByRole("heading", { level: 1, name: "קורות החיים מוכנים" })).toBeVisible();
  const readyResponse = await request.get(documentPath);
  expect(readyResponse.status()).toBe(200);
  const ready = await readyResponse.json();
  expect(ready.preparation_state).toBe("ready");
  expect(ready.approved_at).not.toBeNull();

  const downloadEvent = page.waitForEvent("download");
  await page.getByRole("link", { name: "הורדת PDF", exact: true }).first().click();
  const download = await downloadEvent;
  expect(await download.failure()).toBeNull();
  const pdfPath = await download.path();
  expect(pdfPath).not.toBeNull();
  const pdf = await readFile(pdfPath!);
  expect(pdf.subarray(0, 5).toString()).toBe("%PDF-");

  await expect(page.getByRole("link", { name: "סיום וחזרה ללוח", exact: true }).first()).toBeVisible();
});
