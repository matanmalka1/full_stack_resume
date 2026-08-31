import { expect, test } from "@playwright/test";

/* The foundation check: direction, the workflow landmark, and route focus, which belong
   to the shell rather than to whichever screen it happens to be hosting. The per-screen
   assertions and the axe scan for the New Application form live in its own spec, so a
   later change to the root route cannot quietly move what this file is proving. */
test.describe("the application shell", () => {
  test("serves a Hebrew RTL document with the workflow landmark", async ({ page }) => {
    await page.goto("/applications/new");

    await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
    await expect(
      page.getByRole("img", { name: /^שלבי הכנת קורות החיים:/ }),
    ).toBeVisible();
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  });

  test("moves focus to the page heading after a route change", async ({ page }) => {
    await page.goto("/applications/new");
    await page.getByRole("link", { name: "הגדרות" }).click();

    await expect(page.getByRole("heading", { level: 1 })).toBeFocused();
  });

  /* A screen publishes its stage, and the landmark holds it until the next screen speaks:
     it is no longer reset on unmount, because resetting flashed `intake` between two
     mid-workflow screens. That makes a screen outside the workflow say so explicitly, and
     this is the assertion that fails if one forgets - the landmark would otherwise carry
     the previous screen's stage into Settings and keep claiming it. */
  test("drops the workflow landmark on a screen outside the workflow", async ({ page }) => {
    await page.goto("/applications/new");
    const workflow = page.getByRole("img", { name: /^שלבי הכנת קורות החיים:/ });
    await expect(workflow).toBeVisible();

    await page.getByRole("link", { name: "הגדרות" }).click();

    await expect(workflow).toHaveCount(0);
  });
});
