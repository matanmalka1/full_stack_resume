import { expect, test, type Page } from "@playwright/test";

const company = "Browser Journey Co";
const role = "Account Manager";
const jobText = "Experience owning the full sales cycle.\n\nאנגלית שוטפת — Fluent English.";
const applicationsPath = "/api/v1/applications";

async function fillIntake(page: Page) {
  await page.goto("/applications/new");
  // Wait for the real settings read so intake does not try to queue AI analysis.
  await expect(page.getByText(/ניתוח המשרה דורש ספק AI/)).toBeVisible();
  await page.getByLabel("שם החברה", { exact: true }).fill(company);
  await page.getByLabel("תפקיד היעד", { exact: true }).fill(role);
  await page.getByLabel("טקסט המשרה", { exact: true }).fill(jobText);
}

test("intake persists through reload and duplicate creation requires acknowledgement", async ({ page, request }) => {
  await fillIntake(page);
  const createdResponse = page.waitForResponse(
    (response) => new URL(response.url()).pathname === applicationsPath && response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "יצירת מועמדות", exact: true }).click();
  const created = await createdResponse;
  expect(created.status()).toBe(201);
  const { application_id: applicationId } = await created.json();
  await expect(page).toHaveURL(new RegExp(`/applications/${applicationId}$`));
  await expect(page.getByRole("main")).toContainText(company);
  await expect(page.getByRole("main")).toContainText(role);

  // A fresh document load exercises the production SPA fallback and server reads.
  await page.reload();
  await expect(page.getByRole("main")).toContainText(company);
  await expect(page.getByRole("main")).toContainText(role);
  const saved = await request.get(`${applicationsPath}/${applicationId}`);
  expect(saved.status()).toBe(200);
  const original = await saved.json();
  expect(original.job_posting.job_text).toBe(jobText);
  expect(original.preparation_state).toBe("needs_analysis");
  expect(original.latest_analysis).toBeNull();
  expect(original.active_operation).toBeNull();

  await page.goto("/");
  await expect(page.getByRole("main")).toContainText(company);
  await expect(page.getByRole("main")).toContainText(role);
  await page.getByRole("link", { name: `פתיחת המועמדות של ${company}`, exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/applications/${applicationId}(?:/resume)?$`));
  await expect(page.getByRole("main")).toContainText(company);

  await fillIntake(page);
  await page.getByRole("button", { name: "יצירת מועמדות", exact: true }).click();
  await expect(
    page.getByRole("link", { name: `פתיחת המועמדות הקיימת: ${company} — ${role}`, exact: true }),
  ).toHaveAttribute("href", `/applications/${applicationId}/resume`);
  const beforeAcknowledgement = await request.get(applicationsPath);
  expect(beforeAcknowledgement.status()).toBe(200);
  expect((await beforeAcknowledgement.json()).total).toBe(1);

  const duplicateResponse = page.waitForResponse(
    (response) => new URL(response.url()).pathname === applicationsPath && response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "יצירת מועמדות נוספת", exact: true }).click();
  const duplicate = await duplicateResponse;
  expect(duplicate.status()).toBe(201);
  expect(duplicate.request().postDataJSON().acknowledged_duplicates).toBe(true);
  const { application_id: duplicateId } = await duplicate.json();
  expect(duplicateId).not.toBe(applicationId);
  await expect(page).toHaveURL(new RegExp(`/applications/${duplicateId}$`));
  await expect(page.getByRole("main")).toContainText(company);

  const afterAcknowledgement = await request.get(applicationsPath);
  expect(afterAcknowledgement.status()).toBe(200);
  expect((await afterAcknowledgement.json()).total).toBe(2);
  const reread = await request.get(`${applicationsPath}/${applicationId}`);
  expect(reread.status()).toBe(200);
  expect((await reread.json()).job_posting).toEqual(original.job_posting);
});
