import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ApplicationDetail, Reason } from "@/api/contracts";
import { ApplicationPage } from "./ApplicationPage";

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
    active_selection_plan_id: "plan-1",
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
        gaps: [
          { requirement: "5 years of Kubernetes", severity: "hard", reason: "missing", requirement_id: "req-k8s" },
        ],
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
  sessionStorage.clear();
});

describe("the review decision, on the Application screen", () => {
  it("opens on the decision and keeps the diagnosis behind its own disclosure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(jsonResponse(detail()))),
    );

    renderPage();

    /* The screen opens on what it needs from the reader. The analysis it is about is
       still one press away rather than a scroll below every decision card, and the
       diagnosis is not read as a second thing to act on. */
    expect(await screen.findByRole("heading", { name: "החלטות נדרשות כדי להמשיך" })).toBeInTheDocument();
    const diagnosis = screen.getByText("פרטי הניתוח והאבחון");
    const diagnosisDisclosure = diagnosis.closest("details");
    expect(diagnosisDisclosure).not.toBeNull();
    expect(diagnosisDisclosure).not.toHaveAttribute("open");

    fireEvent.click(diagnosis);
    expect(diagnosisDisclosure).toHaveAttribute("open");
    expect(screen.getByRole("heading", { name: "ניתוח המשרה" })).toBeInTheDocument();

    expect(screen.queryByRole("region", { name: "התראות" })).not.toBeInTheDocument();
  });

  /* The verdict the decisions are about is stated before them, not under them. */
  it("states the analysis verdict above the decisions it explains", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(jsonResponse(detail({ review_reasons: [reason("LOW_FIT_REQUIRES_ACCEPTANCE")] })))),
    );

    renderPage();

    /* The fit sentence is anchored on here because it is now said in exactly one place:
       it used to stand in the analysis masthead and in the decision panel's preamble as
       well, three copies of one explanation on one screen. */
    const banner = await screen.findByText(/התאמה נמוכה מחייבת אישור מפורש/);
    const decision = screen.getByRole("heading", { name: "החלטות נדרשות כדי להמשיך" });
    expect(banner.compareDocumentPosition(decision) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("presents an accepted low-fit decision as closed after the projection refreshes", async () => {
    let applied = false;
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      if (String(input) === APPLY_PATH) {
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
      const refreshed = detail({
        review_reasons: [],
        preparation_state: "ready_to_draft",
        available_actions: ["create_draft"],
        recommended_action: "create_draft",
      });
      refreshed.latest_analysis!.analysis.user_override = { fit: "accepted-low-fit" };
      return Promise.resolve(
        jsonResponse(applied ? refreshed : detail({ review_reasons: [reason("LOW_FIT_REQUIRES_ACCEPTANCE")] })),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    renderPage();

    fireEvent.click(await screen.findByRole("switch", { name: /ההתאמה הנמוכה/ }));
    fireEvent.click(screen.getByRole("button", { name: "שמירת ההחלטות" }));

    expect(await screen.findByText("המשך עם התאמה נמוכה אושר")).toBeInTheDocument();
    expect(screen.getByText(/נשמר כהחלטה על הניתוח הזה/)).toBeInTheDocument();
    expect(screen.getByText("הצלחה")).toBeInTheDocument();
    expect(screen.queryByText(/התאמה נמוכה מחייבת אישור מפורש/)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "יצירת טיוטה" })).toBeInTheDocument();
  });

  it("requires every displayed decision before enabling the single commit", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          jsonResponse(
            detail({
              review_reasons: [reason("MATERIAL_CLASSIFICATION_AMBIGUITY"), reason("ANALYSIS_INCOMPLETE")],
            }),
          ),
        ),
      ),
    );

    renderPage();

    expect(await screen.findByRole("heading", { name: "החלטות נדרשות כדי להמשיך" })).toBeInTheDocument();
    const save = screen.getByRole("button", { name: "שמירת ההחלטות" });
    fireEvent.change(screen.getByLabelText("מסלול"), { target: { value: "tech-sales" } });
    expect(save).toBeDisabled();
    fireEvent.click(screen.getByRole("switch", { name: /הדרישות לא נקראו/ }));
    expect(save).toBeEnabled();
  });

  /* The decision a hard gap takes is per requirement and is recorded on the SelectionPlan.
     The fit acceptance is recorded on the analysis and answers low fit alone, so offering
     it here left the reader with a control that could not close the blocker: it re-derived
     the analysis and the same gap came back. */
  it("offers a hard gap its own acceptance rather than the fit checkbox", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(jsonResponse(detail({ review_reasons: [reason("HARD_GAP_REQUIRES_DECISION")] })))),
    );

    renderPage();

    expect(await screen.findByRole("checkbox", { name: /5 years of Kubernetes/ })).toBeInTheDocument();
    expect(screen.queryByRole("switch", { name: /ההתאמה הנמוכה/ })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("מסלול")).not.toBeInTheDocument();
  });

  /* An acceptance names a Requirement, and an analysis written before requirement
     extraction has none to name. The server refuses such an id, so the screen says why
     instead of offering a control that could only fail. */
  it("names a hard gap from a legacy analysis as one it cannot decide", async () => {
    const legacy = detail({ review_reasons: [reason("HARD_GAP_REQUIRES_DECISION")] });
    legacy.latest_analysis!.analysis.gaps = [
      { requirement: "5 years of Kubernetes", severity: "hard", reason: "missing" },
    ];
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(jsonResponse(legacy))),
    );

    renderPage();

    expect(await screen.findByText(/ניתוח מחדש של המשרה יזהה את הדרישה/)).toBeInTheDocument();
    expect(screen.queryByRole("checkbox", { name: /5 years of Kubernetes/ })).not.toBeInTheDocument();
  });

  it("sends an accepted gap with the plan the decision was taken against", async () => {
    let applied = false;
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      void init;
      const url = String(input);
      if (url === APPLY_PATH) {
        applied = true;
        return Promise.resolve(
          jsonResponse(
            {
              application_id: "app-1",
              job_analysis_id: "analysis-1",
              selection_plan_id: "plan-2",
              created_analysis: false,
              analysis: {},
              plan: {},
            },
            201,
          ),
        );
      }
      return Promise.resolve(
        jsonResponse(
          applied
            ? detail({
                review_reasons: [],
                preparation_state: "ready_to_draft",
                available_actions: ["create_draft"],
                recommended_action: "create_draft",
              })
            : detail({ review_reasons: [reason("HARD_GAP_REQUIRES_DECISION")] }),
        ),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    renderPage();

    fireEvent.click(await screen.findByRole("checkbox", { name: /5 years of Kubernetes/ }));
    fireEvent.change(screen.getByLabelText(/סיבת הקבלה/), { target: { value: "נסגר בראיון" } });
    fireEvent.click(screen.getByRole("button", { name: "שמירת ההחלטות" }));

    expect(await screen.findByRole("button", { name: "יצירת טיוטה" })).toBeInTheDocument();

    const applyCall = fetchMock.mock.calls.find((call) => call[0] === APPLY_PATH);
    expect(applyCall).toBeDefined();
    /* The plan id rides with the acceptance: without it the server would apply the
       decision to whatever plan is active now rather than the one on screen. */
    expect(JSON.parse((applyCall as [string, RequestInit])[1].body as string)).toEqual({
      application_id: "app-1",
      accept_low_fit: false,
      accept_incomplete_analysis: false,
      accepted_requirement_ids: ["req-k8s"],
      acceptance_reason: "נסגר בראיון",
      expected_selection_plan_id: "plan-1",
    });
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
        jsonResponse(
          applied
            ? detail({
                review_reasons: [],
                preparation_state: "ready_to_draft",
                available_actions: ["create_draft"],
                recommended_action: "create_draft",
              })
            : detail(),
        ),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    renderPage();

    fireEvent.change(await screen.findByLabelText("מסלול"), { target: { value: "tech-sales" } });
    fireEvent.change(screen.getByLabelText("דגש"), { target: { value: "leadership" } });
    fireEvent.click(screen.getByRole("button", { name: "שמירת ההחלטות" }));

    /* The refreshed projection reports the state that follows - here, that the reason
       closed - on the screen the user never left. */
    expect(await screen.findByRole("button", { name: "יצירת טיוטה" })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: /החלט.*כדי להמשיך/ })).not.toBeInTheDocument();

    const applyCall = fetchMock.mock.calls.find((call) => call[0] === APPLY_PATH);
    expect(applyCall).toBeDefined();
    /* One commit, not one per control. */
    expect(fetchMock.mock.calls.filter((call) => call[0] === APPLY_PATH)).toHaveLength(1);
    expect(JSON.parse((applyCall as [string, RequestInit])[1].body as string)).toEqual({
      application_id: "app-1",
      accept_low_fit: false,
      accept_incomplete_analysis: false,
      track_override: "tech-sales",
      profile_override: "account-manager",
      emphasis_override: "leadership",
      /* No gap was marked, so the acceptance is empty and carries no plan id with it. */
      accepted_requirement_ids: [],
    });
  });

  it("preserves the form and shows the safe refusal when the server refuses", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === APPLY_PATH) {
        /* A code this client's table does not translate, so the fallback path is what is
           under test: the server's own `detail` sentence, verbatim. */
        return Promise.resolve(problemResponse("UNRECOGNIZED_REFUSAL", "the submitted decisions change nothing"));
      }
      return Promise.resolve(jsonResponse(detail()));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderPage();

    fireEvent.change(await screen.findByLabelText("מסלול"), { target: { value: "tech-sales" } });
    fireEvent.click(screen.getByRole("button", { name: "שמירת ההחלטות" }));

    expect(await screen.findByText("the submitted decisions change nothing")).toBeInTheDocument();
    /* Still on the analysis step, with the decision surface and selection intact: nothing
       safe was lost. */
    expect(screen.getByRole("heading", { level: 1, name: "ניתוח והתאמה" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "החלטות נדרשות כדי להמשיך" })).toBeInTheDocument();
    expect(screen.getByLabelText("מסלול")).toHaveValue("tech-sales");
  });

  it("does not show a superseded analysis as the one under decision", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(jsonResponse(detail({ active_analysis_id: "analysis-9" })))),
    );

    renderPage();

    /* The analysis on record belongs to an older snapshot, so it is named as superseded
       rather than shown as the classification in force. */
    expect(await screen.findByText("הניתוח שעל המסך אינו הניתוח הפעיל")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "ניתוח המשרה" })).not.toBeInTheDocument();
    /* The decision is still offered - it goes to the active analysis either way. */
    expect(screen.getByLabelText("מסלול")).toBeInTheDocument();
  });
});
