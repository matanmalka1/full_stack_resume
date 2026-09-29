import { AxeBuilder } from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

/* Accessibility runs independently; creation and duplicate choices against real
   FastAPI live in integration/intake.spec.ts, launched by pytest. */
test.describe("the New Application screen", () => {
  test("has no automatically detectable accessibility violations", async ({ page }) => {
    await page.goto("/applications/new");

    const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();

    expect(results.violations).toEqual([]);
  });
});
