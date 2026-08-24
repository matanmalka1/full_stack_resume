import { expect, test } from "@playwright/test";

/* The foundation check: direction, the workflow landmark, and route focus, which belong
   to the shell rather than to whichever screen it happens to be hosting. The per-screen
   assertions and the axe scan for the New Application form live in its own spec, so a
   later change to the root route cannot quietly move what this file is proving. */
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
});
