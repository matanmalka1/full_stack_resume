import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

/* The New Application screen is the one M4 screen that renders fully without a backend:
   the form, the local `.txt` read, and its accessibility are all client-side. Duplicate
   choices and creation need real FastAPI and a real DraftFlow, so they belong to the
   central E2E that the F gate owns, not here. */
test.describe("the New Application screen", () => {
  test("is the Hebrew intake form and never presents the URL as an import", async ({ page }) => {
    await page.goto("/applications/new");

    await expect(page.getByRole("heading", { level: 1, name: "משרה חדשה" })).toBeVisible();
    await expect(page.getByLabel("שם החברה")).toBeVisible();
    await expect(page.getByLabel("תפקיד היעד")).toBeVisible();
    await expect(page.getByLabel("כתובת המשרה — אופציונלי")).toHaveAttribute("dir", "ltr");
    await expect(page.getByRole("button", { name: "יצירת מועמדות" })).toBeVisible();
    await expect(page.getByText("המערכת אינה פותחת את הכתובת או מייבאת ממנה טקסט", { exact: false })).toBeVisible();
  });

  test("reads a local .txt file into the job text area without uploading it", async ({ page }) => {
    const unexpectedApiRequests: string[] = [];
    page.on("request", (request) => {
      const url = new URL(request.url());
      /* Stage E makes one shell-owned Settings read. The file-input contract is that
         choosing a local file starts no command and sends no file contents; permit only
         that read-only shell request and report every other API request. */
      if (url.pathname.startsWith("/api/") && !(request.method() === "GET" && url.pathname === "/api/v1/settings")) {
        unexpectedApiRequests.push(`${request.method()} ${url.pathname}`);
      }
    });

    await page.goto("/applications/new");
    await page.getByRole("button", { name: "העלאת קובץ" }).click();
    await page.getByLabel("בחירת קובץ טקסט").setInputFiles({
      name: "job.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("Senior Backend Engineer\nTel Aviv", "utf8"),
    });

    await expect(page.getByLabel("טקסט המשרה")).toHaveValue("Senior Backend Engineer\nTel Aviv");
    await expect(page.getByRole("status")).toContainText("job.txt");
    expect(unexpectedApiRequests).toEqual([]);
  });

  test("has no automatically detectable accessibility violations", async ({ page }) => {
    await page.goto("/applications/new");

    const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();

    expect(results.violations).toEqual([]);
  });
});
