import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

/* The New Application screen renders fully without a backend. Duplicate choices and
   creation need real FastAPI and a real DraftFlow, so they belong to the central E2E
   that the F gate owns, not here. */
test.describe("the New Application screen", () => {
  test("has no automatically detectable accessibility violations", async ({ page }) => {
    await page.goto("/applications/new");

    const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();

    expect(results.violations).toEqual([]);
  });
});
