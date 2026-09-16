import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ApplicationDetail } from "@/api/contracts";
import { ApplicationPage } from "./ApplicationPage";

const APPLY_PATH = "/api/v1/analyses/analysis-1/apply-decisions";

const detail = (overrides: Partial<ApplicationDetail> = {}): ApplicationDetail =>
  ({
    recruitment_status: "saved",
    allowed_recruitment_transitions: ["withdrawn", "closed"],
    recruitment_timeline: [],
    preparation_state: "ready_to_draft",
    working_draft_state: "none",
    review_reasons: [],
    stale_reasons: [],
    warnings: [],
    active_job_snapshot_id: "snap-1",
    active_analysis_id: "analysis-1",
    active_selection_plan_id: "plan-1",
    newer_draft_in_progress: false,
    available_actions: ["create_draft", "edit_matching_configuration"],
    blocked_actions: [],
    recommended_action: "create_draft",
    application: {
      id: "app-1",
      company: "Acme",
      target_role: "Backend Engineer",
      current_status: "saved",
      notes: "",
      source: "manual",
      created_at: "2026-08-24T07:00:00Z",
      updated_at: "2026-08-24T07:00:00Z",
    },
    latest_snapshot: {
      id: "snap-1",
      application_id: "app-1",
      version_number: 1,
      job_text: "Senior Backend Engineer",
      captured_at: "2026-08-24T07:00:00Z",
      source_metadata: {},
      content_hash: "hash-1",
    },
    latest_analysis: {
      id: "analysis-1",
      application_id: "app-1",
      job_snapshot_id: "snap-1",
      version_number: 1,
      analysis: {
        analysis_version: "3.0",
        track: "sales",
        profile: "account-manager",
        emphasis: "account-growth",
        language: "he",
        summary: "A sales role",
        keywords: [],
        requirements: [],
        issues: [],
        source_coverage: null,
        user_override: {},
      },
      provider: "openai",
      model: "gpt-5.6-terra",
      created_at: "2026-08-24T07:00:00Z",
    },
    ...overrides,
  }) as ApplicationDetail;

const jsonResponse = (body: unknown, status = 200): Response =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

const problemResponse = (code: string, detailText: string, status = 412): Response =>
  new Response(
    JSON.stringify({
      type: `about:blank#${code.toLowerCase()}`,
      title: "Precondition Failed",
      status,
      code,
      detail: detailText,
    }),
    { status, headers: { "Content-Type": "application/problem+json" } },
  );

const renderPage = () => {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, refetchInterval: false, gcTime: 0 }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/applications/app-1"]}>
        <Routes>
          <Route element={<ApplicationPage />} path="/applications/:applicationId" />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
};

afterEach(() => {
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

describe("voluntary matching configuration", () => {
  it("shows current values and sends both active-context CAS identities", async () => {
    let applied = false;
    const before = detail();
    const after = detail({ active_selection_plan_id: "plan-2" });
    after.application = { ...before.application, emphasis: "new-business" };
    const fetchMock = vi.fn((input: RequestInfo | URL, _init?: RequestInit) => {
      if (String(input) === APPLY_PATH) {
        applied = true;
        return Promise.resolve(
          jsonResponse(
            {
              application_id: "app-1",
              job_analysis_id: "analysis-1",
              selection_plan_id: "plan-2",
              created_analysis: false,
              analysis: after.latest_analysis!.analysis,
              plan: {},
              state: after,
            },
            201,
          ),
        );
      }
      return Promise.resolve(jsonResponse(applied ? after : before));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderPage();
    await screen.findByText("מסלול, פרופיל ודגשים");
    expect(screen.getByLabelText("מסלול")).toHaveValue("sales");
    expect(screen.getByLabelText("פרופיל")).toHaveValue("account-manager");
    expect(screen.getByLabelText("דגש")).toHaveValue("account-growth");
    const save = screen.getByRole("button", { name: "שמירת הגדרות ההתאמה" });
    expect(save).toBeDisabled();

    fireEvent.change(screen.getByLabelText("דגש"), { target: { value: "new-business" } });
    expect(save).toBeEnabled();
    fireEvent.click(save);

    expect(await screen.findByText("הגדרות ההתאמה נשמרו")).toBeInTheDocument();
    const applyCall = fetchMock.mock.calls.find((call) => call[0] === APPLY_PATH);
    expect(JSON.parse((applyCall as [string, RequestInit])[1].body as string)).toEqual({
      application_id: "app-1",
      expected_analysis_id: "analysis-1",
      expected_selection_plan_id: "plan-1",
      emphasis_override: "new-business",
    });
  });

  it.each([
    [
      "draft_in_progress" as const,
      { active_working_draft_id: "draft-1", working_draft_state: "editing" as const },
      /הטיוטה הפעילה לא תימחק, אך תהיה לא מעודכנת/,
    ],
    [
      "ready" as const,
      { latest_approved_revision_id: "revision-1", latest_ready_revision_id: "revision-1" },
      /הגרסאות שאושרו והקבצים המוכנים לא ישתנו/,
    ],
  ])("explains the consequence from server state %s", async (preparation_state, extra, message) => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(jsonResponse(detail({ preparation_state, ...extra })))),
    );
    renderPage();
    await screen.findByText("מסלול, פרופיל ודגשים");
    expect(screen.getByText(message)).toBeInTheDocument();
  });

  it("keeps local choices visible when the server reports a context conflict", async () => {
    const before = detail();
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) =>
        String(input) === APPLY_PATH
          ? Promise.resolve(problemResponse("STATE_CONFLICT", "the active JobAnalysis moved", 409))
          : Promise.resolve(jsonResponse(before)),
      ),
    );

    renderPage();
    await screen.findByText("מסלול, פרופיל ודגשים");
    fireEvent.change(screen.getByLabelText("דגש"), { target: { value: "new-business" } });
    fireEvent.click(screen.getByRole("button", { name: "שמירת הגדרות ההתאמה" }));

    expect(await screen.findByText("הפעולה מתנגשת במצב העדכני. יש לרענן ולנסות שוב.")).toBeInTheDocument();
    expect(screen.getByLabelText("דגש")).toHaveValue("new-business");
  });
});
