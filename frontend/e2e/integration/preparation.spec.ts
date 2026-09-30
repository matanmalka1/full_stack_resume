import { readFile } from "node:fs/promises";

import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

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

test("analysis, AI draft, approval, real PDF and submission compose through the browser", async ({ page, request }) => {
  test.setTimeout(120_000);
  const applications = "/api/v1/applications";
  await page.goto("/applications/new");
  await expect(page.getByText("יצירת המועמדות תשמור את תצלום המשרה ותתחיל את הניתוח.")).toBeVisible();
  await page.getByLabel("שם החברה", { exact: true }).fill("Browser Preparation Co");
  await page.getByLabel("תפקיד היעד", { exact: true }).fill("Account Manager");
  const jobText = "Experience owning the full sales cycle.\nFluent English.";
  await page.getByLabel("טקסט המשרה", { exact: true }).fill(jobText);

  const createdResponse = postResponse(page, applications);
  // Intake starts analysis itself; capture it before pressing Create.
  const analysisResponse = page.waitForResponse(
    (response) =>
      /\/applications\/[^/]+\/analyses$/.test(new URL(response.url()).pathname) &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "יצירת מועמדות", exact: true }).click();
  const created = await createdResponse;
  expect(created.status()).toBe(201);
  const { application_id: id, job_snapshot_id: snapshotId } = await created.json();
  const applicationPath = `${applications}/${id}`;
  const documentPath = `${applicationPath}/document`;
  const analyzed = await analysisResponse;
  expect(analyzed.status()).toBe(202);
  const firstAnalysisId = (await analyzed.json()).id;
  await expect
    .poll(async () => (await (await request.get(`/api/v1/operations/${firstAnalysisId}`)).json()).status)
    .toBe("failed");
  const retryResponse = postResponse(page, `/api/v1/operations/${firstAnalysisId}/retry`);
  await page.getByRole("button", { name: "ניסיון חוזר", exact: true }).click();
  const retried = await retryResponse;
  expect(retried.status()).toBe(202);
  const retriedOperation = await retried.json();
  expect(retriedOperation.retry_of_operation_id).toBe(firstAnalysisId);
  await operationSucceeded(request, retriedOperation.id);
  const analysisDetail = await request.get(applicationPath);
  expect(analysisDetail.status()).toBe(200);
  expect(await analysisDetail.json()).toMatchObject({
    preparation_state: "ready_to_draft",
    active_job_snapshot_id: snapshotId,
    latest_snapshot: { job_text: jobText },
  });

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
  await conflict.getByRole("button", { name: "שמירה על הגרסה הנוכחית" }).click();
  await expect(conflict).not.toBeVisible();
  await expect(row.getByText("הטקסט הזה חוסם אישור", { exact: true })).toBeVisible();
  const blockedCheck = postResponse(page, `${documentPath}/check`);
  await page.getByRole("button", { name: "בדיקה והכנת PDF", exact: true }).click();
  expect((await (await blockedCheck).json()).passed).toBe(false);
  await expect(page.getByRole("dialog", { name: "אישור והכנת PDF" })).not.toBeVisible();
  // Correct through the UI using the original canonical wording; it must unblock
  // the same document, without an AI key or a bypass of the approval boundary.
  const editing = row.getByRole("textbox", { name: "טקסט השורה" });
  if (!(await editing.isVisible())) await row.getByRole("button", { name: "עריכת השורה", exact: true }).click();
  const savedCorrection = page.waitForResponse(
    (response) => response.request().method() === "PATCH" && new URL(response.url()).pathname === documentPath,
  );
  await editing.fill(target.text);
  await editing.blur();
  expect((await savedCorrection).status()).toBe(200);
  await expect(row.getByText("הטקסט הזה חוסם אישור", { exact: true })).not.toBeVisible();
  const checkResponse = postResponse(page, `${documentPath}/check`);
  await page.getByRole("button", { name: "בדיקה והכנת PDF", exact: true }).click();
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
  await expect(page.getByRole("heading", { name: "מוכן למסירה" })).toBeVisible();
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

  await page.getByRole("button", { name: "רישום ההגשה", exact: true }).click();
  const submission = page.getByRole("dialog", { name: "רישום הגשה קבועה" });
  const submittedResponse = postResponse(page, `${applicationPath}/submissions`);
  await submission.getByRole("button", { name: "אישור ורישום ההגשה", exact: true }).click();
  const submitted = await submittedResponse;
  expect(submitted.status()).toBe(201);
  const record = await submitted.json();
  expect(record.document_hash).toBe(ready.document_hash);
  expect(record.current_status).toBe("applied");
  await expect(page.getByText("ההגשה נרשמה", { exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("link", { name: "סיום וחזרה ללוח", exact: true })).toBeVisible();
  const persistedResponse = await request.get(applicationPath);
  expect(persistedResponse.status()).toBe(200);
  const persisted = await persistedResponse.json();
  expect(persisted.recruitment_status).toBe("applied");
  expect(persisted.preparation_state).toBe("ready");
  expect(persisted.document_hash).toBe(ready.document_hash);
  expect(persisted.latest_snapshot).toMatchObject({ job_text: jobText });
  expect(persisted.recruitment_timeline).toEqual(
    expect.arrayContaining([
      expect.objectContaining({
        id: record.submission_id,
        item_type: "submission",
        submission_type: "internal",
        document_hash: ready.document_hash,
      }),
    ]),
  );
});
