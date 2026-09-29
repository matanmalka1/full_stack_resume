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

test("analysis, deterministic draft, approval, real PDF and submission compose through the browser", async ({
  page,
  request,
}) => {
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
  await operationSucceeded(request, (await analyzed.json()).id);
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
