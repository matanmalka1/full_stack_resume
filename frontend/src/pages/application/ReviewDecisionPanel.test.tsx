import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ApplicationDetail, Reason } from "../../api/contracts";
import { ApplicationPage } from "../ApplicationPage";

const APPLY_PATH = "/api/v1/analyses/analysis-1/apply-decisions";

const reason = (code: string, actions: string[] = ["apply_analysis_decisions"]): Reason => ({
  code,
  message: `plain sentence for ${code}`,
  entity_references: { job_analysis_id: "analysis-1" },
  allowed_resolution_actions: actions,
});

const detail = (overrides: Partial<ApplicationDetail> = {}): ApplicationDetail =>
  ({
    recruitment_status: "saved",
    allowed_recruitment_transitions: ["withdrawn", "closed"],
    recruitment_timeline: [],
    preparation_state: "needs_review",
    working_draft_state: "none",
    review_reasons: [reason("MATERIAL_CLASSIFICATION_AMBIGUITY")],
    stale_reasons: [],
    warnings: [],
    active_job_snapshot_id: "snap-1",
    active_analysis_id: "analysis-1",
    newer_draft_in_progress: false,
    available_actions: ["apply_analysis_decisions"],
    blocked_actions: [],
    recommended_action: "apply_analysis_decisions",
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
        track: "sales",
        profile: "account-manager",
        emphasis: "account-growth",
        language: "he",
        fit: "low",
        gaps: [{ requirement: "5 years of Kubernetes", severity: "hard", reason: "missing" }],
        user_override: {},
      },
      provider: "deterministic",
      model: "rules-v1",
      created_at: "2026-08-24T07:00:00Z",
    },
    ...overrides,
  }) as ApplicationDetail;

const jsonResponse = (body: unknown, status = 200): Response =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });

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
    defaultOptions: {
      queries: { retry: false, refetchInterval: false, gcTime: 0 },
      mutations: { retry: false },
    },
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
});

describe("the review decision, on the Application screen", () => {
  it("shows the fit acceptance for a hard gap and no classification selects", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(detail({ review_reasons: [reason("HARD_GAP_REQUIRES_DECISION")] }))),
    );

    renderPage();

    expect(await screen.findByRole("checkbox")).toBeInTheDocument();
    expect(screen.queryByLabelText("מסלול")).not.toBeInTheDocument();
  });

  it("commits every decision in one request without leaving the screen", async () => {
    /* Routed by URL rather than by call order: the screen reads Settings as well as the
       projection, so a queue of `mockResolvedValueOnce` answers would hand the wrong body
       to whichever request happened to arrive second. */
    let applied = false;
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === APPLY_PATH) {
        applied = true;
        return Promise.resolve(
          jsonResponse(
            {
              application_id: "app-1",
              job_analysis_id: "analysis-2",
              selection_plan_id: "plan-2",
              created_analysis: true,
              analysis: {},
              plan: {},
            },
            201,
          ),
        );
      }
      void init;
      /* The decision closed the reason, which the refreshed projection is what reports. */
      return Promise.resolve(
        jsonResponse(applied ? detail({ review_reasons: [], preparation_state: "ready_to_draft" }) : detail()),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    renderPage();

    fireEvent.change(await screen.findByLabelText("מסלול"), { target: { value: "tech-sales" } });
    fireEvent.change(screen.getByLabelText("דגש"), { target: { value: "leadership" } });
    fireEvent.click(screen.getByRole("button", { name: "החלת כל ההחלטות" }));

    /* The refreshed projection reports the state that follows - here, that the reason
       closed - on the screen the user never left. */
    expect(await screen.findByText("מוכן ליצירת טיוטה")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "ההחלטה שנדרשת" })).not.toBeInTheDocument();

    const applyCall = fetchMock.mock.calls.find((call) => call[0] === APPLY_PATH);
    expect(applyCall).toBeDefined();
    /* One commit, not one per control. */
    expect(fetchMock.mock.calls.filter((call) => call[0] === APPLY_PATH)).toHaveLength(1);
    expect(JSON.parse((applyCall as [string, RequestInit])[1].body as string)).toEqual({
      application_id: "app-1",
      accept_low_fit: false,
      track_override: "tech-sales",
      emphasis_override: "leadership",
    });
  });

  it("preserves the form and shows the safe refusal when the server refuses", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(detail()))
      .mockResolvedValueOnce(problemResponse("PRECONDITION_FAILED", "the submitted decisions change nothing"));
    vi.stubGlobal("fetch", fetchMock);

    renderPage();

    fireEvent.change(await screen.findByLabelText("מסלול"), { target: { value: "tech-sales" } });
    fireEvent.click(screen.getByRole("button", { name: "החלת כל ההחלטות" }));

    expect(await screen.findByText("the submitted decisions change nothing")).toBeInTheDocument();
    /* Still on the screen, with the decision still selected: nothing safe was lost. */
    expect(screen.getByRole("heading", { level: 1, name: "הכנת קורות החיים" })).toBeInTheDocument();
    expect(screen.getByLabelText("מסלול")).toHaveValue("tech-sales");
  });

  it("does not show a superseded analysis as the one under decision", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(detail({ active_analysis_id: "analysis-9" }))));

    renderPage();

    /* The analysis on record belongs to an older snapshot, so it is named as superseded
       rather than shown as the classification in force. */
    expect(await screen.findByText("הניתוח שעל המסך אינו הניתוח הפעיל")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "ניתוח המשרה" })).not.toBeInTheDocument();
    /* The decision is still offered - it goes to the active analysis either way. */
    expect(screen.getByLabelText("מסלול")).toBeInTheDocument();
  });
});
