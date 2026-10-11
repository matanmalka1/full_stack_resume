import { test as base, expect } from "@playwright/test";

/* The integration specs' `test`. Every route but sign-in requires a session, so each test
   starts by signing in through the real screen with the user pytest created
   (tests/fixtures/api.py), and `request` carries the browser's session instead of being
   a second, signed-out client. */
const credentials = () => {
  const email = process.env.CV_TEST_EMAIL;
  const password = process.env.CV_TEST_PASSWORD;
  if (!email || !password) throw new Error("CV_TEST_EMAIL and CV_TEST_PASSWORD come from the pytest harness.");
  return { email, password };
};

export const test = base.extend({
  page: async ({ page }, use) => {
    const { email, password } = credentials();
    await page.goto("/login");
    await page.getByLabel("אימייל").fill(email);
    await page.getByLabel("סיסמה").fill(password);
    await page.getByRole("button", { name: "התחברות" }).click();
    await expect(page).not.toHaveURL(/\/login/);
    await use(page);
  },
  /* The session cookie is `Secure`. Chromium sends it to http://127.0.0.1 as to any
     secure context, but Playwright's Node-side request client does not, so the browser's
     cookie is handed to it explicitly. */
  request: async ({ baseURL, page, playwright }, use) => {
    const cookies = await page.context().cookies();
    const context = await playwright.request.newContext({
      baseURL,
      extraHTTPHeaders: { Cookie: cookies.map((cookie) => `${cookie.name}=${cookie.value}`).join("; ") },
    });
    await use(context);
    await context.dispose();
  },
});

export { expect };
