import { AxeBuilder } from "@axe-core/playwright";
import { expect, test } from "./fixtures";

/* Accessibility runs independently; creation and duplicate choices against real
   FastAPI live in integration/intake.spec.ts, launched by pytest. The empty form reads
   only Settings, which the fixture answers by default. */
test.describe("the New Application screen", () => {
  test("has no automatically detectable accessibility violations", async ({ page }) => {
    await page.goto("/applications/new");

    const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();

    expect(results.violations).toEqual([]);
  });
});
