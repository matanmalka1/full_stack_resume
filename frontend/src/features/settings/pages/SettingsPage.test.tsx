import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { json, renderRoute, settings } from "@/test/fixtures";
import { SettingsPage } from "./SettingsPage";

afterEach(() => {
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

describe("SettingsPage", () => {
  it("shows provider availability and keeps AI mode unavailable without one", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(json(settings(), 200, { ETag: '"settings-0"' }))),
    );
    renderRoute("/settings", "/settings", <SettingsPage />);
    expect(screen.getByRole("link", { name: "מועמדויות" })).toHaveAttribute("href", "/");
    expect(screen.getByText("הגדרות")).toHaveAttribute("aria-current", "page");
    expect(await screen.findByText("לא הוגדר ספק AI בסביבת הריצה.")).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "AI" })).toBeDisabled();
  });

  it("owns policy and display only: the fact store and its check live on the facts screen", async () => {
    const requestedUrls: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn((input: string | URL | Request) => {
        requestedUrls.push(String(input));
        return Promise.resolve(json(settings(), 200, { ETag: '"settings-0"' }));
      }),
    );

    renderRoute("/settings", "/settings", <SettingsPage />);
    await screen.findByRole("button", { name: "שמירת הגדרות" });

    expect(screen.queryByRole("button", { name: "הפעלת בדיקת תקינות" })).not.toBeInTheDocument();
    expect(screen.queryByText("מאגר העובדות")).not.toBeInTheDocument();
    expect(requestedUrls).not.toContain("/api/v1/facts");
  });

  it("saves all product settings under the read ETag", async () => {
    const fetchMock = vi.fn((_input: string | URL | Request, _init?: RequestInit) =>
      Promise.resolve(json(settings({ edit_version: 1 }), 200, { ETag: '"settings-1"' })),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderRoute("/settings", "/settings", <SettingsPage />);
    const autoGenerate = await screen.findByRole("switch", {
      name: "יצירת טיוטה אוטומטית כשלא נדרשת סקירה",
    });
    const saveButton = screen.getByRole("button", { name: "שמירת הגדרות" });
    expect(saveButton).toBeDisabled();
    fireEvent.click(autoGenerate);
    expect(saveButton).toBeEnabled();
    fireEvent.change(screen.getByLabelText("צפיפות תצוגה"), {
      target: { value: "compact" },
    });
    fireEvent.change(screen.getByLabelText("גודל טקסט"), {
      target: { value: "large" },
    });
    fireEvent.change(screen.getByLabelText("מודל AI"), {
      target: { value: "gpt-5.6-luna" },
    });
    fireEvent.change(screen.getByLabelText("מאמץ חשיבה"), {
      target: { value: "high" },
    });
    fireEvent.click(saveButton);
    await screen.findByRole("status");
    const request = fetchMock.mock.calls.find((call) => call[1]?.method === "PATCH");
    expect((request?.[1]?.headers as Headers | undefined)?.get("If-Match")).toBe('"settings-1"');
    expect(JSON.parse(String(request?.[1]?.body))).toEqual({
      ai_enabled_override: null,
      auto_generate_when_review_not_required: true,
      default_execution_mode: "deterministic",
      default_ai_model: "gpt-5.6-luna",
      default_reasoning_effort: "high",
      ui_density: "compact",
      ui_text_size: "large",
    });
    await waitFor(() => expect(autoGenerate).not.toBeChecked());
    expect(saveButton).toBeDisabled();
  });
});
