import type { Settings } from "../src/api/contracts";
import { settings } from "../src/test/records";
import { type Answer, expect, json, test } from "./fixtures";

test.describe("the application shell", () => {
  test("moves focus to the page heading after a route change", async ({ api, page }) => {
    /* Landing on the board reads its list and, separately, its attention summary. */
    const emptyList = {
      items: [],
      matched: 0,
      total: 0,
      limit: 24,
      offset: 0,
      preset_counts: {},
      recruitment_status_counts: {},
      stage_counts: {},
    };
    api.stub("GET /api/v1/applications?activity=open&limit=24&sort=updated", json(emptyList));
    api.stub("GET /api/v1/applications?preset=needs_attention&limit=3", json({ ...emptyList, limit: 3 }));
    await page.goto("/settings");
    await page.getByRole("link", { name: "לוח המועמדויות" }).click();

    await expect(page.getByRole("heading", { level: 1, name: "לוח מועמדויות" })).toBeFocused();
  });
});

test("applies the saved theme from Settings and follows system changes", async ({ api, page }) => {
  let saved: Settings = settings({ ui_theme: "system" });
  const answer: Answer = async (route) => {
    if (route.request().method() === "PATCH")
      saved = { ...saved, ...route.request().postDataJSON(), edit_version: saved.edit_version + 1 };
    await route.fulfill({
      contentType: "application/json",
      headers: { ETag: `"settings-${saved.edit_version}"` },
      json: saved,
    });
  };
  api.stub("GET /api/v1/settings", answer);
  api.stub("PATCH /api/v1/settings", answer);
  await page.emulateMedia({ colorScheme: "dark" });
  await page.goto("/settings");
  await expect(page.getByRole("radio", { name: "לפי המכשיר", exact: true })).toBeChecked();
  await expect(page.locator("html")).not.toHaveAttribute("data-theme");
  const dark = await page.locator("html").evaluate((element) => getComputedStyle(element).backgroundColor);
  await page.emulateMedia({ colorScheme: "light" });
  await expect(page.locator("html")).not.toHaveAttribute("data-theme");
  const light = await page.locator("html").evaluate((element) => getComputedStyle(element).backgroundColor);
  expect(light).not.toBe(dark);
  await page.getByText("כהה", { exact: true }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.getByRole("button", { name: "שמירת הגדרות" }).click();
  await expect(page.getByText("ההגדרות נשמרו")).toBeVisible();
  await expect(page.getByRole("button", { name: /^ערכת צבעים:/ })).toHaveCount(0);
  await page.reload();
  await expect(page.getByRole("radio", { name: "כהה", exact: true })).toBeChecked();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
});

test.describe("signing in", () => {
  test("a signed-out reader lands on sign-in and returns to the screen they asked for", async ({ api, page }) => {
    const me = { id: "user-1", email: "candidate@example.com", created_at: "2026-10-11T12:00:00+00:00" };
    const signedOut: Answer = (route) =>
      route.fulfill({
        status: 401,
        contentType: "application/problem+json",
        json: { type: "about:blank", title: "Unauthorized", status: 401, code: "AUTHENTICATION_REQUIRED", detail: "" },
      });
    api.stub("GET /api/v1/auth/me", signedOut);
    api.stub("POST /api/v1/auth/login", async (route) => {
      expect(route.request().postDataJSON()).toEqual({ email: "candidate@example.com", password: "a long password" });
      api.stub("GET /api/v1/auth/me", json(me));
      await json(me)(route);
    });

    await page.goto("/settings");

    await expect(page).toHaveURL(/\/login\?next=%2Fsettings$/);
    await expect(page.getByRole("heading", { level: 1, name: "כניסה לחשבון" })).toBeVisible();
    await page.getByLabel("אימייל").fill("candidate@example.com");
    await page.getByLabel("סיסמה").fill("a long password");
    await page.getByRole("button", { name: "כניסה" }).click();

    await expect(page).toHaveURL(/\/settings$/);
    await expect(page.getByRole("heading", { level: 1, name: "הגדרות" })).toBeVisible();
  });
});
