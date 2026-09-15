import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { json, renderRoute, settings } from "@/test/fixtures";
import { ThemeToggle } from "./ThemeToggle";
afterEach(() => {
  localStorage.clear();
  vi.unstubAllGlobals();
});
it("toggles and saves directly without a dialog while preserving current server preferences", async () => {
  let reads = 0;
  const fetch = vi.fn((_input: unknown, init?: RequestInit) => {
    if (init?.method === "PATCH")
      return Promise.resolve(json(settings(JSON.parse(String(init.body))), 200, { ETag: '"settings-2"' }));
    reads++;
    return Promise.resolve(
      json(settings({ ui_density: reads > 1 ? "compact" : "comfortable" }), 200, { ETag: '"settings-1"' }),
    );
  });
  vi.stubGlobal("fetch", fetch);
  renderRoute("/", "/", <ThemeToggle />);
  const toggle = await screen.findByRole("button", { name: "ערכת נושא: לפי המערכת" });
  await waitFor(() => expect(toggle).toBeEnabled());
  fireEvent.click(toggle);
  await screen.findByRole("button", { name: "ערכת נושא: כהה" });
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  const request = fetch.mock.calls.find((call) => call[1]?.method === "PATCH");
  expect(JSON.parse(String(request?.[1]?.body))).toMatchObject({ ui_theme: "dark", ui_density: "compact" });
  expect((request?.[1]?.headers as Headers | undefined)?.get("If-Match")).toBe('"settings-1"');
});
it("retains the saved theme and offers Settings on write conflict without automatic retry", async () => {
  const fetch = vi.fn((_input: unknown, init?: RequestInit) =>
    Promise.resolve(
      init?.method === "PATCH"
        ? json({ type: "about:blank", title: "Conflict", status: 409, code: "STATE_CONFLICT", detail: "changed" }, 409)
        : json(settings({ ui_theme: "dark" }), 200, { ETag: '"settings-1"' }),
    ),
  );
  vi.stubGlobal("fetch", fetch);
  renderRoute("/", "/", <ThemeToggle />);
  fireEvent.click(await screen.findByRole("button", { name: "ערכת נושא: כהה" }));
  await screen.findByRole("alert");
  expect(screen.getByRole("button", { name: "ערכת נושא: כהה" })).toBeEnabled();
  expect(screen.getByRole("link", { name: "פתיחת ההגדרות לפתרון" })).toHaveAttribute("href", "/settings");
  expect(fetch.mock.calls.filter((call) => call[1]?.method === "PATCH")).toHaveLength(1);
});
