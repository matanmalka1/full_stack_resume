import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

/* The foundation check, and the one screen that exists without a backend. The flows the
   specification lists - New Application, Analysis Review, Draft Editor, Validation, Ready
   - are added as each screen lands, against real FastAPI and a real worker. */
test.describe("the application shell", () => {
  test("serves a Hebrew RTL document with the workflow landmark", async ({ page }) => {
    await page.goto("/");

    await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
    await expect(page.getByRole("navigation", { name: "שלבי הכנת קורות החיים" })).toBeVisible();
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  });

  test("moves focus to the page heading after a route change", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("link", { name: "הגדרות" }).click();

    await expect(page.getByRole("heading", { level: 1 })).toBeFocused();
  });

  test("has no automatically detectable accessibility violations", async ({ page }) => {
    await page.goto("/");

    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();

    expect(results.violations).toEqual([]);
  });
});
