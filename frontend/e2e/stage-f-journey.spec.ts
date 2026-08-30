import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";
import { readFile, rename } from "node:fs/promises";
import path from "node:path";

const ACCOUNT_MANAGER_JOB =
  "Account Manager responsible for retention, portfolio growth, negotiation, and customer relationships.";
const PERFORMANCE_CLAIM =
  /^(?:Delivered approximately 30% improvement in team performance and sales revenue over the management period\.|שיפור של כ-30% בביצועי הצוות ובהכנסות ממכירות לאורך תקופת הניהול\.)$/;
const REVIEW_REQUIRED_JOB =
  "דרוש מנהל לקוחות עם ניסיון בפיתוח עסקי ובניהול תיק לקוחות מול ארגונים גדולים. " +
  "התפקיד כולל אחריות על שימור, גיוס לקוחות חדשים והובלת תהליכי מכירה מורכבים. " +
  "דרישות: account manager, business development, Salesforce, must have direct saas sales.";
const PROJECT_MARKER = path.join(process.cwd(), "test-results", "stage-f-project-root.txt");

/* The Ready and Draft screens embed the server-rendered CV in a `sandbox=""` iframe, which
   forbids script execution by design. axe still walks every frame and waits on an
   `axe-core` injection that frame can never run, which leaves the browser context unusable
   and fails the following `finishRun`. The preview is a separate document that owns its own
   direction and markup, so it is not this shell's accessibility surface to assert on. */
const expectAxeClean = async (page: Page) => {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .exclude("iframe[sandbox]")
    .analyze();
  expect(results.violations).toEqual([]);
};

const createApplication = async (
  page: Page,
  input: { company: string; jobText: string },
) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1, name: "משרה חדשה", exact: true })).toBeVisible();
  await page.getByLabel("שם החברה").fill(input.company);
  await page.getByLabel("תפקיד היעד").fill("Account Manager");
  await page.getByLabel("טקסט המשרה").fill(input.jobText);
  await page.getByRole("button", { name: "יצירת מועמדות", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1, name: "מצב המועמדות", exact: true })).toBeVisible();
};

const waitForOperation = async (page: Page, outcome: "succeeded" | "failed" = "succeeded") => {
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(
    page.getByText(outcome === "succeeded" ? "הושלמה" : "נכשלה", { exact: true }).first(),
  ).toBeVisible({ timeout: 120_000 });
};

const returnToApplication = async (page: Page) => {
  await page.getByRole("link", { name: "חזרה למועמדות", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1, name: "מצב המועמדות", exact: true })).toBeVisible();
};

const analyze = async (page: Page) => {
  await page.getByRole("button", { name: "ניתוח המשרה", exact: true }).click();
  await waitForOperation(page);
  await returnToApplication(page);
};

const resolveReview = async (page: Page) => {
  await page.getByRole("link", { name: "החלטות הסקירה", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1, name: "סקירת הניתוח", exact: true })).toBeVisible();
  await expectAxeClean(page);
  await page.getByLabel("פרופיל").selectOption("account-manager");
  /* This fixture's analysis raises both a low-fit and a hard-requirement blocker, and one
     acceptance resolves both. `isVisible()` does not wait, so guarding on it skipped the
     checkbox whenever the decision form had not rendered yet; the profile override alone
     then satisfied the apply button and the decisions applied without resolving anything. */
  /* The accessible name is the label followed by the control's hint text, so this
     deliberately matches on the label alone; it collides with no other control. */
  const fitAcceptance = page.getByRole("checkbox", {
    name: "אני מאשר את ההתאמה ואת הפערים ומבקש להמשיך",
  });
  await expect(fitAcceptance).toBeVisible();
  await fitAcceptance.check();
  await expect(fitAcceptance).toBeChecked();
  await page.getByRole("button", { name: "החלת כל ההחלטות", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1, name: "מצב המועמדות", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "יצירת טיוטה", exact: true })).toBeVisible();
};

const createDraft = async (page: Page) => {
  await page.getByRole("button", { name: "יצירת טיוטה", exact: true }).click();
  await waitForOperation(page);
  await returnToApplication(page);
  /* Deterministic generation returns an already validated draft, so the projection's
     single draft-screen action is named for its furthest available step. It still opens
     the editor, where this journey performs the required manual edit before approval. */
  await page.getByRole("link", { name: "אישור הגרסה", exact: true }).click();
  await expect(
    page.getByRole("heading", { level: 1, name: "עריכה, אימות ואישור", exact: true }),
  ).toBeVisible();
};

const editValidateAndApprove = async (page: Page) => {
  const approvalButton = page.getByRole("button", { name: "אישור הגרסה", exact: true });
  /* Deterministic generation records a passing validation before this screen opens. The
     editor then reads that exact run and publishes approval eligibility asynchronously;
     wait for the user-visible result so axe does not inspect the opacity transition. */
  await expect(approvalButton).toBeEnabled();
  await expectAxeClean(page);
  /* This pinned line is one canonical fact, so saving its displayed wording exercises a
     real manual edit without turning a generated headline into an unsupported claim. */
  const supportingFact = page.getByText(PERFORMANCE_CLAIM);
  const factBackedClaim = page
    .getByRole("listitem")
    .filter({ has: supportingFact })
    .first()
    .getByLabel("טקסט השורה");
  await expect(factBackedClaim).toBeVisible();
  await factBackedClaim.press("End");
  await factBackedClaim.type(" ");
  await factBackedClaim.press("Backspace");
  await factBackedClaim.blur();
  /* Save state is deliberately duplicated into a screen-reader live region. Observe the
     visible badge here; a global text locator would be ambiguous by design. */
  await expect(page.locator("span", { hasText: /^נשמר$/ })).toBeVisible();

  await page.getByRole("button", { name: "אימות הטיוטה", exact: true }).click();
  await expect(page.getByRole("heading", { name: "הטיוטה עברה אימות", exact: true })).toBeVisible();
  /* The validation result renders before the editor's effect publishes that its exact
     passing run may be approved. Axe must inspect one settled UI state rather than read
     the button's disabled opacity while React is enabling that same button. */
  await expect(approvalButton).toBeEnabled();
  await expectAxeClean(page);

  await approvalButton.click();
  const dialog = page.getByRole("dialog", { name: "אישור גרסה קבועה", exact: true });
  await expect(dialog).toBeVisible();
  const warningAcknowledgement = dialog.getByRole("checkbox", {
    name: "קראתי את האזהרות ואני רוצה להמשיך באישור",
  });
  if (await warningAcknowledgement.isVisible()) await warningAcknowledgement.check();
  await dialog.getByRole("button", { name: "אישור הגרסה", exact: true }).click();
  await expect(page.getByRole("heading", { name: "הגרסה אושרה", exact: true })).toBeVisible();
};

const renderAndOpenReady = async (page: Page) => {
  await page.getByRole("button", { name: "יצירת HTML ו־PDF", exact: true }).click();
  await waitForOperation(page);
  await returnToApplication(page);
  await page.getByRole("link", { name: "צפייה בגרסה המוכנה", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1, name: "קורות החיים מוכנים", exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "הורדת PDF", exact: true })).toBeVisible();
  await expectAxeClean(page);
};

test.describe.serial("Stage F real built-Web journey", () => {
  test("the no-review path survives render failure/retry and keeps old Ready beside a newer draft", async ({
    page,
  }) => {
    await createApplication(page, { company: "Stage F No Review", jobText: ACCOUNT_MANAGER_JOB });
    await analyze(page);
    await expect(page.getByRole("button", { name: "יצירת טיוטה", exact: true })).toBeVisible();
    await createDraft(page);
    await editValidateAndApprove(page);

    const projectRoot = (await readFile(PROJECT_MARKER, "utf8")).trim();
    const template = path.join(projectRoot, "rendering", "templates", "sales_ltr.html.j2");
    const unavailable = `${template}.stage-f-unavailable`;
    await rename(template, unavailable);
    try {
      await page.getByRole("button", { name: "יצירת HTML ו־PDF", exact: true }).click();
      await waitForOperation(page, "failed");
      await expect(
        page.getByText("יצירת קובץ קורות החיים נכשלה", { exact: true }),
      ).toBeVisible();
      await expect(page.getByText("הגרסה שאושרה נשמרה", { exact: false })).toBeVisible();
    } finally {
      await rename(unavailable, template);
    }

    await page.getByRole("button", { name: "ניסיון חוזר", exact: true }).click();
    await waitForOperation(page);
    await returnToApplication(page);
    await page.getByRole("link", { name: "צפייה בגרסה המוכנה", exact: true }).click();
    await expect(page.getByRole("heading", { level: 1, name: "קורות החיים מוכנים", exact: true })).toBeVisible();
    await expectAxeClean(page);

    await page.getByRole("button", { name: "יצירת טיוטה חדשה", exact: true }).click();
    await waitForOperation(page);
    await returnToApplication(page);
    await expect(page.getByText("קיימת טיוטה חדשה יותר מהגרסה שאושרה")).toBeVisible();
    await page.getByRole("link", { name: "צפייה בגרסה המוכנה", exact: true }).click();
    await expect(page.getByText("קיימת טיוטה חדשה יותר")).toBeVisible();
    await expect(page.locator("details[open]")).toHaveCount(0);
  });

  test("the review-required path resolves its decisions and reaches Ready", async ({ page }) => {
    await createApplication(page, { company: "Stage F Review", jobText: REVIEW_REQUIRED_JOB });
    await analyze(page);
    await expect(page.getByText("נדרשת החלטה לפני המשך", { exact: true }).first()).toBeVisible();
    await resolveReview(page);
    await createDraft(page);
    await editValidateAndApprove(page);
    await renderAndOpenReady(page);
    await expect(page.locator("details[open]")).toHaveCount(0);
  });
});
