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
    expect(screen.getByRole("switch", { name: "יצירת טיוטה עם AI כברירת מחדל" })).toBeDisabled();
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
    fireEvent.click(screen.getByRole("switch", { name: "תצוגה צפופה" }));
    fireEvent.click(screen.getByRole("switch", { name: "טקסט גדול" }));
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
      ui_theme: "system",
    });
    await waitFor(() => expect(autoGenerate).not.toBeChecked());
    expect(saveButton).toBeDisabled();
  });
});

const conflictResponse = () =>
  json(
    {
      type: "about:blank",
      title: "Conflict",
      status: 409,
      code: "STATE_CONFLICT",
      detail: "changed",
      retryable: false,
    },
    409,
  );

it("preserves edits through refresh failure and repeated conflict, and merges only explicitly selected fields", async () => {
  let reads = 0;
  let writes = 0;
  const fetch = vi.fn((_input: unknown, init?: RequestInit) => {
    if (init?.method === "PATCH") {
      writes++;
      if (writes < 3) return Promise.resolve(conflictResponse());
      return Promise.resolve(
        json(settings({ ...JSON.parse(String(init.body)), edit_version: 3 }), 200, { ETag: '"settings-3"' }),
      );
    }
    reads++;
    if (reads === 2) return Promise.reject(new TypeError("offline"));
    return Promise.resolve(
      json(
        settings(
          reads === 1 ? {} : { ui_density: "compact", default_reasoning_effort: "high", edit_version: reads - 2 },
        ),
        200,
        { ETag: `"settings-${Math.max(0, reads - 2)}"` },
      ),
    );
  });
  vi.stubGlobal("fetch", fetch);
  renderRoute("/settings", "/settings", <SettingsPage />);
  await screen.findByRole("switch", { name: "ערכת נושא לפי המערכת" });
  fireEvent.click(screen.getByRole("switch", { name: "ערכת נושא לפי המערכת" }));
  fireEvent.click(screen.getByRole("switch", { name: "ערכת נושא כהה" }));
  fireEvent.change(screen.getByLabelText("מאמץ חשיבה"), { target: { value: "low" } });
  fireEvent.click(screen.getByRole("button", { name: "שמירת הגדרות" }));
  await screen.findByText("ההגדרות השתנו מאז שפתחת את הטופס");
  expect(screen.getByRole("button", { name: "שמירת הגדרות" })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "טעינת הגרסה העדכנית להשוואה" }));
  await screen.findByRole("alert");
  expect(screen.getByRole("switch", { name: "ערכת נושא כהה" })).toBeChecked();
  fireEvent.click(screen.getByRole("button", { name: "טעינת הגרסה העדכנית להשוואה" }));
  fireEvent.click(await screen.findByRole("checkbox", { name: "החלת העריכה: ערכת נושא" }));
  fireEvent.click(screen.getByRole("button", { name: "החלת הבחירה על הגרסה העדכנית" }));
  expect(screen.getByLabelText("מאמץ חשיבה")).toHaveValue("high");
  expect(screen.getByRole("switch", { name: "תצוגה צפופה" })).toBeChecked();
  expect(writes).toBe(1);
  fireEvent.click(screen.getByRole("button", { name: "שמירת הגדרות" }));
  await screen.findByText("ההגדרות השתנו מאז שפתחת את הטופס");
  fireEvent.click(screen.getByRole("button", { name: "טעינת הגרסה העדכנית להשוואה" }));
  fireEvent.click(await screen.findByRole("checkbox", { name: "החלת העריכה: ערכת נושא" }));
  fireEvent.click(screen.getByRole("button", { name: "החלת הבחירה על הגרסה העדכנית" }));
  fireEvent.click(screen.getByRole("button", { name: "שמירת הגדרות" }));
  await screen.findByText("ההגדרות נשמרו");
  const patches = fetch.mock.calls.filter((call) => call[1]?.method === "PATCH");
  expect(patches.map((call) => (call[1]?.headers as Headers | undefined)?.get("If-Match"))).toEqual([
    '"settings-0"',
    '"settings-1"',
    '"settings-2"',
  ]);
  expect(JSON.parse(String(patches.at(-1)?.[1]?.body))).toMatchObject({
    ui_theme: "dark",
    ui_density: "compact",
    default_reasoning_effort: "high",
  });
});

it("discards local edits only by explicit choice and adopts the current server version", async () => {
  let reads = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn((_input: unknown, init?: RequestInit) => {
      if (init?.method === "PATCH") return Promise.resolve(conflictResponse());
      reads++;
      return Promise.resolve(
        json(settings({ ui_theme: reads === 1 ? "system" : "light" }), 200, { ETag: `"settings-${reads}"` }),
      );
    }),
  );
  renderRoute("/settings", "/settings", <SettingsPage />);
  fireEvent.click(await screen.findByRole("switch", { name: "ערכת נושא לפי המערכת" }));
  fireEvent.click(screen.getByRole("switch", { name: "ערכת נושא כהה" }));
  fireEvent.click(screen.getByRole("button", { name: "שמירת הגדרות" }));
  fireEvent.click(await screen.findByRole("button", { name: "טעינת הגרסה העדכנית להשוואה" }));
  fireEvent.click(await screen.findByRole("button", { name: "טעינת ערכי השרת והשלכת העריכות שלי" }));
  expect(screen.getByRole("switch", { name: "ערכת נושא כהה" })).not.toBeChecked();
  expect(screen.getByRole("button", { name: "שמירת הגדרות" })).toBeDisabled();
});

it("keeps a non-conflict 412 as a validation failure and retains unsaved edits", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn((_input: unknown, init?: RequestInit) =>
      Promise.resolve(
        init?.method === "PATCH"
          ? json(
              {
                type: "about:blank",
                title: "Unavailable",
                status: 412,
                code: "PRECONDITION_FAILED",
                detail: "AI unavailable",
              },
              412,
            )
          : json(settings(), 200, { ETag: '"settings-0"' }),
      ),
    ),
  );
  renderRoute("/settings", "/settings", <SettingsPage />);
  fireEvent.click(await screen.findByRole("switch", { name: "ערכת נושא לפי המערכת" }));
  fireEvent.click(screen.getByRole("switch", { name: "ערכת נושא כהה" }));
  fireEvent.click(screen.getByRole("button", { name: "שמירת הגדרות" }));
  await screen.findByText("לא ניתן לבצע את הפעולה כעת");
  expect(screen.queryByText("ההגדרות השתנו מאז שפתחת את הטופס")).not.toBeInTheDocument();
  expect(screen.getByRole("switch", { name: "ערכת נושא כהה" })).toBeChecked();
});
