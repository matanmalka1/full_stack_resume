import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { json, renderRoute, settings } from "@/test/fixtures";
import { ThemeToggle } from "./ThemeToggle";
afterEach(() => {
  localStorage.clear();
  vi.unstubAllGlobals();
});
it("uses the saved server preference, offers all modes, and imports legacy preference only explicitly", async () => {
  localStorage.setItem("cv-theme", "dark");
  const fetch = vi.fn((_input: unknown, init?: RequestInit) =>
    Promise.resolve(
      json(settings({ ui_theme: init?.method === "PATCH" ? "dark" : "system" }), 200, { ETag: '"settings-1"' }),
    ),
  );
  vi.stubGlobal("fetch", fetch);
  renderRoute("/", "/", <ThemeToggle />);
  const toggle = await screen.findByRole("button", { name: "ערכת נושא: לפי המערכת" });
  await waitFor(() => expect(toggle).toBeEnabled());
  fireEvent.click(toggle);
  expect(screen.getByRole("combobox", { name: "ערכת נושא" })).toHaveValue("system");
  fireEvent.click(screen.getByRole("button", { name: "שימוש בהעדפה המקומית הישנה" }));
  expect(screen.getByRole("combobox", { name: "ערכת נושא" })).toHaveValue("dark");
  expect(fetch.mock.calls.filter((call) => call[1]?.method === "PATCH")).toHaveLength(0);
  fireEvent.click(screen.getByRole("button", { name: "שמירת הגדרות" }));
  await screen.findByText("ההגדרות נשמרו");
  expect(screen.getByRole("button", { name: "ערכת נושא: כהה" })).toBeInTheDocument();
});
