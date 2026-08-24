import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ApplicationDetail, Reason } from "../api/contracts";
import { ReviewPage } from "./ReviewPage";

const DETAIL_PATH = "/api/v1/applications/app-1";
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
      <MemoryRouter initialEntries={["/applications/app-1/review"]}>
        <Routes>
          <Route element={<ReviewPage />} path="/applications/:applicationId/review" />
          <Route element={<h1>מועמדות</h1>} path="/applications/:applicationId" />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("ReviewPage", () => {
  it("shows the current classification and the hard gap being decided about", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(detail())));

    renderPage();

    /* Awaited on the region, not on the h1: the heading is static and would resolve
       before the projection had arrived. Scoped to the summary too, because the same
       Hebrew names are also select options and an unscoped query would pass on those. */
    const current = within(await screen.findByRole("region", { name: "הסיווג הנוכחי" }));
    expect(current.getByText("מנהל לקוחות")).toBeInTheDocument();
    expect(current.getByText("צמיחת לקוחות קיימים")).toBeInTheDocument();
    expect(current.getByText("התאמה נמוכה")).toBeInTheDocument();
    expect(current.getByText(/5 years of Kubernetes/)).toBeInTheDocument();
  });

  it("offers a control only for the reasons it resolves and names the others as elsewhere", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          detail({
            review_reasons: [
              reason("MATERIAL_CLASSIFICATION_AMBIGUITY"),
              reason("PENDING_FACT_REQUIRES_RESOLUTION", ["confirm_and_use_fact"]),
            ],
          }),
        ),
      ),
    );

    renderPage();

    expect(await screen.findByLabelText("מסלול")).toBeInTheDocument();
    /* Not dropped, and not given a control that would not resolve it. */
    expect(screen.getByText("החלטה שנפתרת במסך אחר")).toBeInTheDocument();
    expect(screen.getByText(/אישור עובדה ושימוש בה/)).toBeInTheDocument();
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  });

  it("shows the fit acceptance for a hard gap and no classification selects", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          jsonResponse(detail({ review_reasons: [reason("HARD_GAP_REQUIRES_DECISION")] })),
        ),
    );

    renderPage();

    expect(await screen.findByRole("checkbox")).toBeInTheDocument();
    expect(screen.queryByLabelText("מסלול")).not.toBeInTheDocument();
  });

  it("does not offer a submission until a decision has been made", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(detail())));

    renderPage();

    const submit = await screen.findByRole("button", { name: "החלת כל ההחלטות" });
    expect(submit).toBeDisabled();

    fireEvent.change(screen.getByLabelText("פרופיל"), { target: { value: "sdr-bdr" } });
    expect(submit).toBeEnabled();
  });

  it("commits every decision in one request and returns to the application", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(detail()))
      .mockResolvedValueOnce(
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
      )
      .mockResolvedValue(jsonResponse(detail({ review_reasons: [], preparation_state: "ready_to_draft" })));
    vi.stubGlobal("fetch", fetchMock);

    renderPage();

    fireEvent.change(await screen.findByLabelText("מסלול"), { target: { value: "tech-sales" } });
    fireEvent.change(screen.getByLabelText("דגש"), { target: { value: "leadership" } });
    fireEvent.click(screen.getByRole("button", { name: "החלת כל ההחלטות" }));

    expect(await screen.findByRole("heading", { name: "מועמדות" })).toBeInTheDocument();

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
      .mockResolvedValueOnce(
        problemResponse("PRECONDITION_FAILED", "the submitted decisions change nothing"),
      );
    vi.stubGlobal("fetch", fetchMock);

    renderPage();

    fireEvent.change(await screen.findByLabelText("מסלול"), { target: { value: "tech-sales" } });
    fireEvent.click(screen.getByRole("button", { name: "החלת כל ההחלטות" }));

    expect(await screen.findByText("the submitted decisions change nothing")).toBeInTheDocument();
    /* Still on the screen, with the decision still selected: nothing safe was lost. */
    expect(screen.getByRole("heading", { level: 1, name: "סקירת הניתוח" })).toBeInTheDocument();
    expect(screen.getByLabelText("מסלול")).toHaveValue("tech-sales");
  });

  it("does not show a superseded analysis as the one under decision", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(detail({ active_analysis_id: "analysis-9" }))),
    );

    renderPage();

    expect(await screen.findByText("הסיווג הנוכחי אינו מוצג")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "הסיווג הנוכחי" })).not.toBeInTheDocument();
    /* The decision is still offered - it goes to the active analysis either way. */
    expect(screen.getByLabelText("מסלול")).toBeInTheDocument();
  });
});
