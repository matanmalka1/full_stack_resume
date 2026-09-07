import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { json, reconciliationReport, renderRoute, settings } from "@/test/fixtures";
import { SettingsPage } from "./SettingsPage";

afterEach(() => {
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

describe("SettingsPage", () => {
  it("shows provider availability and keeps AI mode unavailable without one", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: string | URL | Request) =>
        Promise.resolve(
          String(input) === "/api/v1/facts" ? json({ items: [] }) : json(settings(), 200, { ETag: '"settings-0"' }),
        ),
      ),
    );
    renderRoute("/settings", "/settings", <SettingsPage />);
    expect(screen.getByRole("link", { name: "מועמדויות" })).toHaveAttribute("href", "/");
    expect(screen.getByText("הגדרות")).toHaveAttribute("aria-current", "page");
    expect(await screen.findByText("לא הוגדר ספק AI בסביבת הריצה.")).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "AI" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "הפעלת בדיקת התאמה" })).toBeInTheDocument();
  });

  it("saves all product settings under the read ETag", async () => {
    const fetchMock = vi.fn((input: string | URL | Request, _init?: RequestInit) =>
      Promise.resolve(
        String(input) === "/api/v1/facts"
          ? json({ items: [] })
          : json(settings({ edit_version: 1 }), 200, { ETag: '"settings-1"' }),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderRoute("/settings", "/settings", <SettingsPage />);
    const autoGenerate = await screen.findByRole("switch", {
      name: "יצירת טיוטה אוטומטית כשלא נדרשת סקירה",
    });
    fireEvent.click(autoGenerate);
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
    fireEvent.click(await screen.findByRole("button", { name: "שמירת הגדרות" }));
    await screen.findByRole("status");
    const request = fetchMock.mock.calls.find((call) => call[1]?.method === "PATCH");
    expect((request?.[1]?.headers as Headers).get("If-Match")).toBe('"settings-1"');
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
  });

  it("shows canonical facts read-only and reports a missing audit status", async () => {
    const fetchMock = vi.fn((input: string | URL | Request) =>
      Promise.resolve(
        String(input) === "/api/v1/facts"
          ? json({
              items: [
                {
                  fact: {
                    fact_id: "fact-1",
                    meaning: "Built backend services",
                    provenance: "Confirmed by candidate",
                    renderings: { en: "Built backend services" },
                    resume_style: "bullet",
                    source: "development.md",
                    status: "canonical",
                    tags: ["backend"],
                  },
                  recorded_status: null,
                },
              ],
            })
          : json(settings(), 200, { ETag: '"settings-0"' }),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    renderRoute("/settings", "/settings", <SettingsPage />);

    expect(await screen.findByText("Built backend services")).toBeInTheDocument();
    expect(screen.getByText("מקור אמת")).toBeInTheDocument();
    expect(screen.getByText(/מצב העובדה אינו תואם למצב האחרון ביומן/)).toBeInTheDocument();
    expect(fetchMock.mock.calls.filter((call) => String(call[0]) === "/api/v1/facts")).toHaveLength(1);
  });
});

describe("Settings reconciliation", () => {
  it("runs reconciliation in place and presents the complete report", async () => {
    const report = reconciliationReport({
      passed: false,
      problems: ["missing artifact: artifacts/outputs/revision-1/resume.pdf"],
      fact_lifecycle: {
        ...reconciliationReport().fact_lifecycle,
        passed: false,
        problems: ["fact audit mismatch"],
        journal_quarantined: 1,
      },
    });
    const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
      if (String(input).includes("/maintenance/reconciliations") && init?.method === "POST") {
        return Promise.resolve(json(report));
      }
      return Promise.resolve(
        String(input) === "/api/v1/facts" ? json({ items: [] }) : json(settings(), 200, { ETag: '"settings-0"' }),
      );
    });
    vi.stubGlobal("fetch", fetchMock);
    renderRoute("/settings", "/settings", <SettingsPage />);

    fireEvent.click(await screen.findByRole("button", { name: "הפעלת בדיקת התאמה" }));

    expect(await screen.findByText("נמצאה בעיית תקינות", { selector: "span" })).toBeInTheDocument();
    expect(screen.getByText("קבצים חסרים: 1")).toBeInTheDocument();
    expect(screen.getByText("מה צריך לעשות")).toBeInTheDocument();
    fireEvent.click(screen.getByText("פרטים טכניים"));
    expect(screen.getByText("missing artifact: artifacts/outputs/revision-1/resume.pdf")).toBeInTheDocument();
    expect(screen.getByText("fact audit mismatch")).toBeInTheDocument();
    expect(screen.getByText("תוצרים — 4 גרסאות נבדקו")).toBeInTheDocument();
    expect(screen.getByText("facts-version-1")).toBeInTheDocument();
    const request = fetchMock.mock.calls.find((call) => String(call[0]).includes("/maintenance/reconciliations"));
    expect(request?.[0]).toBe("/api/v1/maintenance/reconciliations");
    expect(request?.[1]?.method).toBe("POST");
  });
});
