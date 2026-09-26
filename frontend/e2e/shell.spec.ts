import { expect, test } from "@playwright/test";

import type { Settings } from "../src/api/contracts";

const settings = {
  edit_version: 0,
  auto_generate_when_review_not_required: false,
  ai_enabled: false,
  ai_enabled_override: null,
  default_ai_model: "gpt-5.6-terra",
  default_execution_mode: "deterministic",
  default_reasoning_effort: "medium",
  available_ai_models: [
    {
      id: "gpt-5.6-terra",
      label: "GPT-5.6 Terra",
      input_per_million_usd: "2.00",
      cached_input_per_million_usd: "0.20",
      output_per_million_usd: "12.00",
      recommended: true,
      pricing_version: "openai-2026-09-03",
      pricing_source: "https://developers.openai.com/api/docs/models/compare",
    },
  ],
  provider_configured: false,
  ui_density: "comfortable",
  ui_text_size: "normal",
  ui_theme: "system",
  updated_at: null,
} satisfies Settings;

test.describe("the application shell", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/api/v1/settings", async (route) => {
      await route.fulfill({ contentType: "application/json", json: settings });
    });
  });

  test("moves focus to the page heading after a route change", async ({ page }) => {
    await page.goto("/settings");
    await page.getByRole("link", { name: "לוח המועמדויות" }).click();

    await expect(page.getByRole("heading", { level: 1, name: "לוח מועמדויות" })).toBeFocused();
  });

  test("folds the desktop sidebar to a rail whose labels open across the page, and keeps it folded", async ({
    page,
  }) => {
    await page.goto("/settings");
    const sidebar = page.locator("#app-sidebar");
    const expandedWidth = (await sidebar.boundingBox())?.width ?? 0;

    await page.getByRole("button", { name: "כיווץ סרגל הניווט" }).click();

    const expand = page.getByRole("button", { name: "הרחבת סרגל הניווט" });
    await expect(expand).toHaveAttribute("aria-expanded", "false");
    const rail = await sidebar.boundingBox();
    expect(rail?.width ?? 0).toBeLessThan(expandedWidth / 2);

    // Every rail control sits inside the rail and on its centre line.
    const railCentre = (rail?.x ?? 0) + (rail?.width ?? 0) / 2;
    const controlBoxes = await Promise.all(
      [
        expand,
        page.getByRole("link", { name: "לוח המועמדויות" }),
        page.getByRole("link", { name: "מאגר העובדות" }),
        page.getByRole("link", { name: "הגדרות" }),
        page.getByRole("button", { name: "מעבר מהיר למועמדות" }),
        page.getByRole("link", { name: "קליטת משרה חדשה" }),
        page.getByRole("button", { name: /^ערכת נושא:/ }),
      ].map((control) => control.boundingBox()),
    );
    for (const box of controlBoxes) {
      expect(box?.x ?? 0).toBeGreaterThanOrEqual(rail?.x ?? 0);
      expect((box?.x ?? 0) + (box?.width ?? 0)).toBeLessThanOrEqual((rail?.x ?? 0) + (rail?.width ?? 0));
      expect(Math.abs((box?.x ?? 0) + (box?.width ?? 0) / 2 - railCentre)).toBeLessThanOrEqual(2);
    }

    // The rail sits on the RTL inline-start (right) edge, so a label must open leftwards
    // into the page; one opening the other way would push the document sideways.
    const link = page.getByRole("link", { name: "מאגר העובדות" });
    await link.hover();
    const tooltip = page.getByRole("tooltip").filter({ hasText: "מאגר העובדות" });
    await expect(tooltip).toBeVisible();
    const linkBox = await link.boundingBox();
    const tooltipBox = await tooltip.boundingBox();
    expect((tooltipBox?.x ?? 0) + (tooltipBox?.width ?? 0)).toBeLessThanOrEqual(linkBox?.x ?? 0);
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth),
    ).toBe(true);

    await page.reload();
    await expect(page.getByRole("button", { name: "הרחבת סרגל הניווט" })).toBeVisible();

    await page.setViewportSize({ width: 800, height: 720 });
    await expect(page.getByRole("button", { name: "הרחבת סרגל הניווט" })).toBeHidden();
    await expect(page.getByText("קורות חיים", { exact: true })).toBeVisible();
  });
});

test("shares the saved theme between the shell and Settings and follows system changes", async ({ page }) => {
  let saved: Settings = { ...settings, ui_theme: "system" };
  await page.route("**/api/v1/settings", async (route) => {
    if (route.request().method() === "PATCH")
      saved = { ...saved, ...route.request().postDataJSON(), edit_version: saved.edit_version + 1 };
    await route.fulfill({
      contentType: "application/json",
      headers: { ETag: `"settings-${saved.edit_version}"` },
      json: saved,
    });
  });
  await page.emulateMedia({ colorScheme: "dark" });
  await page.goto("/settings");
  await expect(page.getByRole("switch", { name: "ערכת נושא לפי המערכת", exact: true })).toBeChecked();
  await expect(page.locator("html")).not.toHaveAttribute("data-theme");
  const dark = await page.locator("html").evaluate((element) => getComputedStyle(element).backgroundColor);
  await page.emulateMedia({ colorScheme: "light" });
  await expect(page.locator("html")).not.toHaveAttribute("data-theme");
  const light = await page.locator("html").evaluate((element) => getComputedStyle(element).backgroundColor);
  expect(light).not.toBe(dark);
  await page.getByRole("switch", { name: "ערכת נושא לפי המערכת", exact: true }).click();
  await page.getByRole("switch", { name: "ערכת נושא כהה", exact: true }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.getByRole("button", { name: "שמירת הגדרות" }).click();
  await expect(page.getByText("ההגדרות נשמרו")).toBeVisible();
  await expect(page.getByRole("button", { name: "ערכת נושא: כהה", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "ערכת נושא: כהה", exact: true }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await expect(page.getByRole("switch", { name: "ערכת נושא כהה", exact: true })).not.toBeChecked();
  await expect(page.getByRole("dialog", { name: "ערכת נושא", exact: true })).toHaveCount(0);
  await page.reload();
  await expect(page.getByRole("switch", { name: "ערכת נושא כהה", exact: true })).not.toBeChecked();
});
