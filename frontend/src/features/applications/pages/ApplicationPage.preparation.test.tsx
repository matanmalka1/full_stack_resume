import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useNavigate } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ApplicationDetail, Operation, Settings } from "@/api/contracts";
import { applicationDetailQueryKey } from "@/api/applications";
import { autoDraftSources } from "@/features/preparation/model/autoDraft";
import { settingsQueryKey } from "@/api/settings";
import { ApplicationPage } from "./ApplicationPage";

const ANALYSES_PATH = "/api/v1/applications/app-1/analyses";

const detail = (overrides: Partial<ApplicationDetail> = {}): ApplicationDetail => ({
  recruitment_status: "saved",
  allowed_recruitment_transitions: ["withdrawn", "closed"],
  recruitment_timeline: [],
  preparation_state: "needs_analysis",
  working_draft_state: "none",
  review_reasons: [],
  stale_reasons: [],
  warnings: [],
  active_job_snapshot_id: "snap-1",
  newer_draft_in_progress: false,
  available_actions: ["analyze"],
  blocked_actions: [],
  recommended_action: "analyze",
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
  ...overrides,
});

const queued = (overrides: Partial<Operation> = {}): Operation => ({
  id: "op-1",
  application_id: "app-1",
  operation_type: "analyze_job",
  status: "queued",
  is_terminal: false,
  phase: "queued",
  message: "",
  created_at: "2026-08-24T07:00:00Z",
  outputs: [],
  available_actions: ["cancel"],
  ...overrides,
});

/* An Application whose analysis is on record and active. The base fixture leaves both
   fields absent, which is the pre-analysis state, so only the tests that opt in here
   render the analysis panel. */
const analyzed_detail = (overrides: Partial<ApplicationDetail> = {}): ApplicationDetail =>
  detail({
    preparation_state: "ready_to_draft",
    available_actions: ["create_draft"],
    recommended_action: "create_draft",
    active_analysis_id: "analysis-1",
    latest_analysis: {
      id: "analysis-1",
      application_id: "app-1",
      job_snapshot_id: "snap-1",
      version_number: 1,
      analysis: {
        track: "development",
        profile: "development",
        emphasis: "development-backend",
        language: "en",
        fit: "medium",
        confidence: 0.82,
        rationale: "The posting is a backend role.",
        keywords: ["FastAPI", "PostgreSQL"],
        mandatory_requirements: ["5 years of Python"],
        preferred_requirements: ["Kubernetes"],
        gaps: [{ requirement: "Kubernetes", severity: "warning", reason: "no matching fact" }],
        approval_reasons: ["low-confidence"],
        user_override: {},
      },
      provider: "deterministic",
      model: "rules-v1",
      created_at: "2026-08-24T07:00:00Z",
    },
    ...overrides,
  });

const jsonResponse = (body: unknown, status = 200): Response =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });

const acceptedResponse = (operation: Operation): Response =>
  new Response(JSON.stringify(operation), {
    status: 202,
    headers: {
      "Content-Type": "application/json",
      Location: `/api/v1/operations/${operation.id}`,
    },
  });

const deterministicSettings: Settings = {
  edit_version: 0,
  auto_generate_when_review_not_required: false,
  ai_enabled: false,
  ai_enabled_override: null,
  default_execution_mode: "deterministic",
  default_ai_model: "gpt-5.6-terra",
  default_reasoning_effort: "medium",
  available_ai_models: [],

  provider_configured: false,
  ui_density: "comfortable",
  ui_text_size: "normal",
  ui_theme: "system",
  updated_at: null,
};

/* Retries and the projection poll are off inside the test client: the interval is
   covered by its own unit test, and a live timer here would make every assertion racy. */
const HistoryControls = () => {
  const navigate = useNavigate();
  return (
    <>
      <button onClick={() => navigate("/applications/app-2")}>Another application</button>
      <button onClick={() => navigate("/applications/app-1")}>Analysis</button>
      <button onClick={() => navigate(-1)}>Back</button>
      <button onClick={() => navigate(1)}>Forward</button>
    </>
  );
};

const renderPage = (settings: Settings = deterministicSettings, routeState?: unknown) => {
  const client = new QueryClient({
    defaultOptions: {
      /* Settings is shell-owned in production and deliberately seeded here. Keep that
         cache entry alive until the isolated page subscribes to it; gcTime zero can
         collect it in the gap between setQueryData and the child render. */
      queries: { retry: false, refetchInterval: false, gcTime: Infinity },
      mutations: { retry: false },
    },
  });
  client.setQueryData(settingsQueryKey, { settings, etag: '"settings-1"' });

  const rendered = render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[{ pathname: "/applications/app-1", state: routeState }]}>
        <HistoryControls />
        <Routes>
          <Route element={<ApplicationPage />} path="/applications/:applicationId" />
          <Route element={<p>Draft editor route</p>} path="/applications/:applicationId/draft" />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return { ...rendered, client };
};

const clickEnabledButton = async (name: string) => {
  const button = await screen.findByRole("button", { name });
  await waitFor(() => expect(button).toBeEnabled());
  fireEvent.click(button);
};

afterEach(() => {
  vi.unstubAllGlobals();
  /* The auto-draft dispatch record is session-scoped and survives a remount by design,
     which is the point of the guard - so it is cleared between tests rather than leaking
     an "already continued" answer into the next one. */
  sessionStorage.clear();
});

describe("ApplicationPage at the preparation route", () => {
  it("uses the Operation as the only status after creation queued the analysis", async () => {
    const succeeded = queued({
      status: "succeeded",
      is_terminal: true,
      phase: "completed",
      available_actions: ["retry"],
    });
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) =>
        Promise.resolve(
          String(input).includes("/operations/")
            ? jsonResponse(succeeded)
            : jsonResponse(detail({ active_operation: queued({ status: "running", phase: "executing" }) })),
        ),
      ),
    );

    renderPage(deterministicSettings, {
      createdApplication: { analysisProblem: null, analysisQueued: true },
    });

    expect((await screen.findAllByText("הושלמה")).length).toBeGreaterThan(0);
    expect(screen.queryByText("המועמדות נוצרה, הניתוח רץ")).not.toBeInTheDocument();
    expect(screen.queryByText("המשרה טרם נותחה")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "ניתוח המשרה" })).not.toBeInTheDocument();
    expect(screen.queryByText("חומר עזר")).not.toBeInTheDocument();
  });

  it("names the application without restoring the old record hierarchy", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(jsonResponse(detail()))),
    );

    renderPage();

    expect(await screen.findByText("Acme — Backend Engineer")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Acme — Backend Engineer" })).toBeNull();
    expect(screen.queryByRole("navigation", { name: "פירורי לחם" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "חזרה ללוח המועמדויות" })).toHaveAttribute("href", "/");
  });

  /* The Web automation opt-in, which moved here with the flow: queueing no longer
     navigates, so the Operation screen that used to run this chain is not on the path.
     This test proves one dispatch from the exact activated analysis and plan. Reload
     idempotency and server-backed recovery are covered separately below. */
  it("auto-generates the draft once per successful analyze when Settings ask for it", async () => {
    let draftQueued = false;
    const analyzed = queued({
      status: "succeeded",
      is_terminal: true,
      phase: "completed",
      available_actions: [],
      outputs: [
        { output_type: "job_analysis", output_id: "analysis-1", active: true },
        { output_type: "selection_plan", output_id: "plan-1", active: true },
      ],
    });
    const drafting = queued({ id: "op-draft", operation_type: "create_draft" });
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (init?.method === "POST") {
        draftQueued = true;
        return Promise.resolve(acceptedResponse(drafting));
      }
      if (url.endsWith("/operations/op-draft")) {
        return Promise.resolve(jsonResponse(drafting));
      }
      /* The opt-in is read from the live Settings query, not only from the seeded cache,
         so this read has to answer with the setting under test. */
      if (url.includes("/settings")) {
        return Promise.resolve(
          jsonResponse({ ...deterministicSettings, auto_generate_when_review_not_required: true }),
        );
      }
      if (url.includes("/operations/")) {
        return Promise.resolve(jsonResponse(analyzed));
      }
      return Promise.resolve(
        jsonResponse(
          analyzed_detail({
            active_operation: draftQueued ? drafting : null,
            latest_operation: analyzed,
            active_selection_plan_id: "plan-1",
          }),
        ),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    renderPage({
      ...deterministicSettings,
      auto_generate_when_review_not_required: true,
    });

    await waitFor(() => expect(sessionStorage.getItem("stage-e:auto-draft:op-1")).toBe("accepted"));
    const posts = fetchMock.mock.calls.filter((call) => call[1]?.method === "POST");
    expect(posts).toHaveLength(1);
    expect(JSON.parse(String(posts[0]?.[1]?.body))).toEqual({
      job_analysis_id: "analysis-1",
      selection_plan_id: "plan-1",
    });
  });

  it("moves to the editor after the automatically generated draft succeeds", async () => {
    let projectionReads = 0;
    const analyzed = queued({
      status: "succeeded",
      is_terminal: true,
      phase: "completed",
      available_actions: [],
      outputs: [
        { output_type: "job_analysis", output_id: "analysis-1", active: true },
        { output_type: "selection_plan", output_id: "plan-1", active: true },
      ],
    });
    const drafting = queued({ id: "op-draft", operation_type: "create_draft" });
    const drafted = queued({
      id: "op-draft",
      operation_type: "create_draft",
      status: "succeeded",
      is_terminal: true,
      phase: "completed",
      available_actions: [],
      outputs: [{ output_type: "working_draft", output_id: "draft-1", active: true }],
    });
    let draftActivated = false;
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (init?.method === "POST") return Promise.resolve(acceptedResponse(drafting));
        if (url.endsWith("/operations/op-draft")) {
          draftActivated = true;
          return Promise.resolve(jsonResponse(drafted));
        }
        if (url.includes("/settings")) {
          return Promise.resolve(
            jsonResponse({ ...deterministicSettings, auto_generate_when_review_not_required: true }),
          );
        }
        if (url.includes("/operations/")) return Promise.resolve(jsonResponse(analyzed));
        projectionReads += 1;
        return Promise.resolve(
          jsonResponse(
            analyzed_detail({
              active_operation: projectionReads === 1 ? queued({ status: "running" }) : null,
              active_selection_plan_id: "plan-1",
              ...(draftActivated
                ? {
                    active_working_draft_id: "draft-1",
                    working_draft_state: "editing",
                    preparation_state: "draft_in_progress",
                  }
                : {}),
            }),
          ),
        );
      }),
    );

    renderPage({ ...deterministicSettings, auto_generate_when_review_not_required: true });

    expect(await screen.findByText("Draft editor route")).toBeInTheDocument();
    expect(sessionStorage.getItem("stage-e:draft-navigation:op-draft")).toBe("completed");
  });

  /* The same move, for the generate a reader pressed. It used to belong to the automation
     alone: a pressed generate finished and left the reader on the analysis screen, with
     the draft it had just written reachable only through a link below - so the two ways of
     starting the identical command ended in different places. */
  it("moves to the editor after a pressed draft generation succeeds", async () => {
    const drafting = queued({ id: "op-draft", operation_type: "create_draft" });
    const drafted = queued({
      id: "op-draft",
      operation_type: "create_draft",
      status: "succeeded",
      is_terminal: true,
      phase: "completed",
      available_actions: [],
      outputs: [{ output_type: "working_draft", output_id: "draft-1", active: true }],
    });
    let draftActivated = false;
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (init?.method === "POST") return Promise.resolve(acceptedResponse(drafting));
      if (url.endsWith("/operations/op-draft")) {
        draftActivated = true;
        return Promise.resolve(jsonResponse(drafted));
      }
      return Promise.resolve(
        jsonResponse(
          analyzed_detail({
            available_actions: ["create_draft"],
            recommended_action: "create_draft",
            active_selection_plan_id: "plan-1",
            ...(draftActivated
              ? {
                  active_working_draft_id: "draft-1",
                  working_draft_state: "editing",
                  preparation_state: "draft_in_progress",
                }
              : {}),
          }),
        ),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    renderPage();
    await clickEnabledButton("יצירת טיוטה");

    expect(await screen.findByText("Draft editor route")).toBeInTheDocument();
    /* One command, from the press alone: the automation opt-in is off in these settings,
       so nothing else may queue a second generate behind it. */
    expect(fetchMock.mock.calls.filter((call) => call[1]?.method === "POST")).toHaveLength(1);
  });
  it("analyzes the exact snapshot the projection names and reports the queued Operation", async () => {
    /* Routed by URL rather than by call order: once the command is accepted the screen
       watches the Operation it queued, so a fixed queue of answers would leave that read
       unanswered and the panel would never settle. */
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === "POST") {
        return Promise.resolve(acceptedResponse(queued()));
      }
      if (String(input).includes("/operations/")) {
        return Promise.resolve(jsonResponse(queued()));
      }
      return Promise.resolve(jsonResponse(detail()));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderPage();
    await clickEnabledButton("ניתוח המשרה");

    /* The accepted `202` is seeded as the panel's first state, so the queued Operation is
       reported on this screen rather than on one the user was sent to. */
    expect(await screen.findByRole("heading", { name: "הרצת ניתוח המשרה", level: 2 })).toBeInTheDocument();
    expect(screen.queryByText("המשרה טרם נותחה")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "ניתוח המשרה" })).not.toBeInTheDocument();
    expect(screen.queryByText("חומר עזר")).not.toBeInTheDocument();

    const request = fetchMock.mock.calls.find((call) => call[0] === ANALYSES_PATH);
    expect(request?.[0]).toBe(ANALYSES_PATH);
    expect(request?.[1]).toEqual(expect.objectContaining({ method: "POST" }));
    /* The source is explicit: an analyze command that picked its own snapshot could
       classify something other than what the screen was showing. */
    expect(JSON.parse(String(request?.[1]?.body))).toEqual({ job_snapshot_id: "snap-1" });
    expect((request?.[1]?.headers as Headers | undefined)?.get("Idempotency-Key")).not.toBeNull();
  });

  it("shows the frozen AI execution and its calculated cost", async () => {
    const aiOperation = queued({
      provider: "openai",
      model: "gpt-5.6-luna",
      reasoning_effort: "high",
      input_tokens: 11,
      cached_input_tokens: 3,
      output_tokens: 22,
      total_tokens: 33,
      cost_usd: "0.00002806",
    });
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) =>
        Promise.resolve(
          String(input).includes("/operations/")
            ? jsonResponse(aiOperation)
            : jsonResponse(detail({ active_operation: aiOperation })),
        ),
      ),
    );

    renderPage();

    expect(await screen.findByText("gpt-5.6-luna")).toBeInTheDocument();
    expect(screen.getByText("$0.00002806")).toBeInTheDocument();
    expect(screen.getByText(/מאמץ גבוה/)).toBeInTheDocument();
  });

  it("does not present a superseded analysis as the one in force", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(analyzed_detail({ active_analysis_id: "analysis-9" }))),
    );

    renderPage();

    expect(await screen.findByText("הניתוח שעל המסך אינו הניתוח הפעיל")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "ניתוח המשרה" })).not.toBeInTheDocument();
    expect(screen.queryByText("The posting is a backend role.")).not.toBeInTheDocument();
  });

  it("presents an accepted incomplete analysis as recorded history, not an open instruction", async () => {
    const accepted = analyzed_detail();
    const latest = accepted.latest_analysis!;
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse({
          ...accepted,
          preparation_state: "ready",
          working_draft_state: "none",
          active_working_draft_id: null,
          latest_ready_revision_id: "revision-1",
          review_reasons: [],
          latest_analysis: {
            ...latest,
            analysis: {
              ...(latest.analysis as Record<string, unknown>),
              fit: "unknown",
              confidence: 0,
              approval_reasons: ["extraction-failed"],
              user_override: { accept_incomplete_analysis: true },
            },
          },
        }),
      ),
    );

    renderPage();

    expect(await screen.findByText("המשך ללא ניתוח דרישות אושר")).toBeInTheDocument();
    expect(screen.getByText(/ההמשך ללא דירוג התאמה אושר ונשמר כהחלטה/)).toBeInTheDocument();
    expect(screen.queryByText(/נדרשת הכרעה מפורשת לפני יצירת טיוטה/)).not.toBeInTheDocument();
  });

  it("shows requirement coverage, resolving supporting facts by id, once the analysis carries requirements", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      if (String(input).includes("/facts")) {
        return Promise.resolve(
          jsonResponse({
            items: [
              { fact: { fact_id: "fact-1", meaning: "5 years building backend systems in Python" } },
              { fact: { fact_id: "fact-boundary", meaning: "Used Kubernetes in a personal lab" } },
            ],
          }),
        );
      }
      return Promise.resolve(
        jsonResponse(
          analyzed_detail({
            latest_analysis: {
              id: "analysis-1",
              application_id: "app-1",
              job_snapshot_id: "snap-1",
              version_number: 1,
              analysis: {
                track: "development",
                profile: "development",
                emphasis: "development-backend",
                language: "en",
                fit: "medium",
                confidence: 0.82,
                rationale: "The posting is a backend role.",
                keywords: ["FastAPI"],
                mandatory_requirements: ["5 years of Python"],
                preferred_requirements: [],
                gaps: [],
                requirements: [
                  {
                    requirement_id: "req-1",
                    text: "5 years of Python",
                    kind: "threshold",
                    mandatory: true,
                    coverage: "matched",
                    supporting_fact_ids: ["fact-1"],
                    boundary_fact_ids: [],
                    missing_components: [],
                  },
                  {
                    requirement_id: "req-2",
                    text: "Production Kubernetes experience",
                    kind: "experience",
                    mandatory: true,
                    coverage: "partial",
                    supporting_fact_ids: [],
                    boundary_fact_ids: ["fact-boundary"],
                    missing_components: [
                      { component_id: "production", label: "ניסיון בסביבת production", demanded: "3 years" },
                    ],
                  },
                  {
                    requirement_id: "req-3",
                    text: "Terraform",
                    kind: "skill",
                    mandatory: false,
                    coverage: "unsupported",
                    supporting_fact_ids: [],
                    boundary_fact_ids: [],
                    missing_components: [],
                  },
                  { requirement_id: "", text: "Malformed requirement", mandatory: true, coverage: "matched" },
                ],
                approval_reasons: [],
                user_override: {},
              },
              provider: "deterministic",
              model: "rules-v1",
              created_at: "2026-08-24T07:00:00Z",
            },
          }),
        ),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    renderPage();

    expect(await screen.findByText("5 years of Python")).toBeInTheDocument();
    expect(screen.getByText("מכוסה")).toBeInTheDocument();
    expect(screen.getByText("מכוסות: 1")).toBeInTheDocument();
    expect(screen.getByText("חלקיות: 1")).toBeInTheDocument();
    expect(screen.getByText("לא מכוסות: 1")).toBeInTheDocument();
    expect(screen.getByText("לא ניתנות להצגה: 1")).toBeInTheDocument();
    expect(screen.getByText("דרישת חובה אחת עדיין אינה מכוסה במלואה.")).toBeInTheDocument();
    expect(screen.getByText("דרישה אחת אינה ניתנת להצגה")).toBeInTheDocument();
    expect(await screen.findByText(/5 years building backend systems in Python/)).toBeInTheDocument();
    expect(screen.getByText(/למה הכיסוי מוגבל: Used Kubernetes in a personal lab/)).toBeInTheDocument();
    expect(screen.getByText(/ניסיון בסביבת production \(נדרש: 3 years\)/)).toBeInTheDocument();
    /* Coverage supersedes the plain mandatory/preferred term lists once an analysis
       carries `requirements` - they would otherwise show the same requirement twice,
       once with its coverage and once as a bare string. */
    expect(screen.queryByText("דרישות חובה שזוהו")).not.toBeInTheDocument();
  });

  it("keeps the projected warning explanation available behind its alert disclosure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          detail({
            warnings: [
              {
                code: "NEXT_ACTION_OVERDUE",
                message: "The next recruitment action is past its target date.",
                entity_references: {},
              },
            ],
          }),
        ),
      ),
    );

    renderPage();

    expect(await screen.findByText("הפעולה הבאה באיחור")).toBeInTheDocument();
    const explanation = screen.getByText("The next recruitment action is past its target date.");
    expect(explanation).not.toBeVisible();
    fireEvent.click(screen.getByText("פרטי האזהרה"));
    expect(explanation).toBeVisible();
  });

  it("shows translated exceptional blockers without exposing routine or unknown reason codes", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          detail({
            preparation_state: "draft_in_progress",
            working_draft_state: "validation_failed",
            blocked_actions: [
              {
                action: "approve",
                reasons: ["VALIDATION_FAILED", "WORKING_DRAFT_REQUIRED"],
              },
            ],
          }),
        ),
      ),
    );

    renderPage();

    expect(await screen.findByText("הפעולה אישור הגרסה חסומה כרגע")).toBeInTheDocument();
    expect(screen.getByText("האימות נכשל. צריך לתקן ולאמת מחדש.")).toBeInTheDocument();
    expect(screen.queryByText("WORKING_DRAFT_REQUIRED")).not.toBeInTheDocument();
  });
  it("recovers a terminal analysis failure without route state and retries only the server-offered Operation", async () => {
    const failed = queued({
      status: "failed",
      is_terminal: true,
      failure_code: "PROVIDER_TIMEOUT",
      available_actions: ["retry"],
    });
    const retrying = queued({ id: "op-retry", retry_of_operation_id: failed.id });
    let resolveRetry: (response: Response) => void = () => {};
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (init?.method === "POST")
        return new Promise<Response>((resolve) => {
          resolveRetry = resolve;
        });
      if (url.endsWith("/operations/op-retry")) return Promise.resolve(jsonResponse(retrying));
      if (url.includes("/operations/")) return Promise.resolve(jsonResponse(failed));
      return Promise.resolve(jsonResponse(detail({ latest_operation: failed, active_operation: null })));
    });
    vi.stubGlobal("fetch", fetchMock);
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "ניסיון חוזר" }));
    const pending = await screen.findByRole("button", { name: "יוצר ניסיון חדש…" });
    expect(pending).toBeDisabled();
    fireEvent.click(pending);
    await act(async () => resolveRetry(acceptedResponse(retrying)));
    await waitFor(() => expect(screen.queryByRole("button", { name: "ניסיון חוזר" })).not.toBeInTheDocument());
    expect(screen.getByRole("heading", { name: "הרצת ניתוח המשרה" })).toBeInTheDocument();
    const posts = fetchMock.mock.calls.filter(([, init]) => init?.method === "POST");
    expect(posts).toHaveLength(1);
    const retryRequest = posts[0];
    expect(retryRequest).toBeDefined();
    expect(retryRequest?.[0]).toBe("/api/v1/operations/op-1/retry");
    expect(retryRequest?.[1]?.headers).toBeInstanceOf(Headers);
    expect((retryRequest?.[1]?.headers as Headers | undefined)?.get("Idempotency-Key")).toBe("retry:op-1");
  });

  it("offers analysis after creation scheduling failed and does not retain creation news over later server work", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(jsonResponse(detail()))),
    );
    const { client } = renderPage(deterministicSettings, { createdApplication: { analysisQueued: false } });
    expect(await screen.findByText("המועמדות נוצרה, אך הניתוח לא הופעל")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "ניתוח המשרה" })).toBeEnabled();
    act(() =>
      client.setQueryData(applicationDetailQueryKey("app-1"), analyzed_detail({ active_selection_plan_id: "plan-1" })),
    );
    await waitFor(() => expect(screen.queryByText("המועמדות נוצרה, אך הניתוח לא הופעל")).not.toBeInTheDocument());
    expect(await screen.findByRole("button", { name: "יצירת טיוטה" })).toBeInTheDocument();
  });

  it("restores a completed analysis from the server and resends an uncertain continuation with the same idempotency key", async () => {
    const analyzed = queued({
      status: "succeeded",
      is_terminal: true,
      available_actions: [],
      outputs: [
        { output_type: "job_analysis", output_id: "analysis-1", active: true },
        { output_type: "selection_plan", output_id: "plan-1", active: true },
      ],
    });
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === "POST") return Promise.reject(new TypeError("response lost"));
      if (String(input).includes("/settings"))
        return Promise.resolve(
          jsonResponse({ ...deterministicSettings, auto_generate_when_review_not_required: true }),
        );
      if (String(input).includes("/operations/")) return Promise.resolve(jsonResponse(analyzed));
      return Promise.resolve(
        jsonResponse(analyzed_detail({ latest_operation: analyzed, active_selection_plan_id: "plan-1" })),
      );
    });
    vi.stubGlobal("fetch", fetchMock);
    const settings = { ...deterministicSettings, auto_generate_when_review_not_required: true };
    const first = renderPage(settings);
    await waitFor(() => expect(fetchMock.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(1));
    await waitFor(() => expect(screen.queryByText("הניתוח הושלם. יצירת הטיוטה מתחילה מיד.")).not.toBeInTheDocument());
    first.unmount();
    renderPage(settings);
    await waitFor(() => expect(fetchMock.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(2));
    const keys = fetchMock.mock.calls
      .filter(([, init]) => init?.method === "POST")
      .map(([, init]) => (init?.headers as Headers | undefined)?.get("Idempotency-Key"));
    expect(keys).toEqual(["auto-draft:analysis-1:plan-1", "auto-draft:analysis-1:plan-1"]);
  });

  it.each([
    "review",
    "blocked",
    "new-analysis",
    "new-plan",
    "inactive-output",
    "cancelled",
    "deleted",
    "existing-draft",
  ])("does not authorize a restored automatic draft with %s", (scenario) => {
    const analyzed = queued({
      status: "succeeded",
      is_terminal: true,
      outputs: [
        { output_type: "job_analysis", output_id: "analysis-1", active: true },
        { output_type: "selection_plan", output_id: "plan-1", active: true },
      ],
    });
    const projection = analyzed_detail({ active_selection_plan_id: "plan-1" });
    if (scenario === "review")
      projection.review_reasons = [
        {
          code: "HARD_GAP_REQUIRES_DECISION",
          message: "Decision required",
          entity_references: {},
          allowed_resolution_actions: ["apply_analysis_decisions"],
        },
      ];
    if (scenario === "blocked")
      projection.blocked_actions = [{ action: "create_draft", reasons: ["KNOWLEDGE_QUARANTINED"] }];
    if (scenario === "new-analysis") projection.active_analysis_id = "analysis-2";
    if (scenario === "new-plan") projection.active_selection_plan_id = "plan-2";
    if (scenario === "inactive-output")
      analyzed.outputs.forEach((output) => {
        output.active = false;
      });
    if (scenario === "cancelled") analyzed.status = "cancelled";
    if (scenario === "deleted") projection.application.deleted_at = "2026-09-14T07:00:00Z";
    if (scenario === "existing-draft") projection.active_working_draft_id = "draft-1";
    expect(
      autoDraftSources(
        analyzed,
        { ...deterministicSettings, auto_generate_when_review_not_required: true },
        projection,
      ),
    ).toBeNull();
  });

  it("isolates late watched analysis results across URL changes and Back / Forward", async () => {
    let resolveOld: (response: Response) => void = () => {};
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/operations/"))
        return new Promise<Response>((resolve) => {
          resolveOld = resolve;
        });
      return Promise.resolve(
        jsonResponse(
          url.endsWith("/app-2")
            ? detail({ application: { ...detail().application, id: "app-2", company: "Other" } })
            : detail({ active_operation: queued() }),
        ),
      );
    });
    vi.stubGlobal("fetch", fetchMock);
    renderPage();
    await waitFor(() =>
      expect(fetchMock.mock.calls.some(([input]) => String(input).includes("/operations/"))).toBe(true),
    );
    fireEvent.click(screen.getByRole("button", { name: "Another application" }));
    expect(await screen.findByText("Other — Backend Engineer")).toBeInTheDocument();
    await act(async () =>
      resolveOld(jsonResponse(queued({ status: "failed", is_terminal: true, available_actions: ["retry"] }))),
    );
    expect(screen.queryByRole("heading", { name: "הרצת ניתוח המשרה" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "ניתוח המשרה" })).toBeEnabled();
    fireEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(await screen.findByText("Acme — Backend Engineer")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Forward" }));
    expect(await screen.findByText("Other — Backend Engineer")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "הרצת ניתוח המשרה" })).not.toBeInTheDocument();
  });

  it("does not watch or navigate an old application's late automatic acceptance", async () => {
    let resolveOld: (response: Response) => void = () => {};
    const analyzed = queued({
      status: "succeeded",
      is_terminal: true,
      outputs: [
        { output_type: "job_analysis", output_id: "analysis-1", active: true },
        { output_type: "selection_plan", output_id: "plan-1", active: true },
      ],
    });
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (init?.method === "POST")
        return new Promise<Response>((resolve) => {
          resolveOld = resolve;
        });
      if (url.includes("/settings"))
        return Promise.resolve(
          jsonResponse({ ...deterministicSettings, auto_generate_when_review_not_required: true }),
        );
      if (url.includes("/operations/")) return Promise.resolve(jsonResponse(analyzed));
      return Promise.resolve(
        jsonResponse(
          url.endsWith("/app-2")
            ? detail({ application: { ...detail().application, id: "app-2", company: "Other" } })
            : analyzed_detail({ latest_operation: analyzed, active_selection_plan_id: "plan-1" }),
        ),
      );
    });
    vi.stubGlobal("fetch", fetchMock);
    renderPage({ ...deterministicSettings, auto_generate_when_review_not_required: true });
    await waitFor(() => expect(fetchMock.mock.calls.some(([, init]) => init?.method === "POST")).toBe(true));
    fireEvent.click(screen.getByRole("button", { name: "Another application" }));
    expect(await screen.findByText("Other — Backend Engineer")).toBeInTheDocument();
    await act(async () => resolveOld(acceptedResponse(queued({ id: "op-draft", operation_type: "create_draft" }))));
    expect(screen.queryByText("Draft editor route")).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "הרצת יצירת טיוטה" })).not.toBeInTheDocument();
    expect(sessionStorage.getItem("stage-e:draft-navigation:op-draft")).toBeNull();
  });

  it("waits for the exact activated draft on refresh and does not repeat completed navigation on Back", async () => {
    const generated = queued({
      id: "op-draft",
      operation_type: "create_draft",
      status: "succeeded",
      is_terminal: true,
      outputs: [{ output_type: "working_draft", output_id: "draft-1", active: true }],
    });
    const projection = analyzed_detail({ active_selection_plan_id: "plan-1", latest_operation: generated });
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) =>
        Promise.resolve(jsonResponse(String(input).includes("/operations/") ? generated : projection)),
      ),
    );
    sessionStorage.setItem("stage-e:draft-navigation:op-draft", "pending");
    const { client } = renderPage();
    expect(await screen.findByText("Acme — Backend Engineer")).toBeInTheDocument();
    expect(screen.queryByText("Draft editor route")).not.toBeInTheDocument();
    await waitFor(() => expect(client.isFetching()).toBe(0));
    act(() =>
      client.setQueryData(applicationDetailQueryKey("app-1"), {
        ...projection,
        active_working_draft_id: "draft-1",
        working_draft_state: "editing",
        preparation_state: "draft_in_progress",
      }),
    );
    expect(await screen.findByText("Draft editor route")).toBeInTheDocument();
    expect(sessionStorage.getItem("stage-e:draft-navigation:op-draft")).toBe("completed");
    fireEvent.click(screen.getByRole("button", { name: "Analysis" }));
    expect(await screen.findByText("Acme — Backend Engineer")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(await screen.findByText("Draft editor route")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Forward" }));
    expect(await screen.findByText("Acme — Backend Engineer")).toBeInTheDocument();
    expect(screen.queryByText("Draft editor route")).not.toBeInTheDocument();
    expect(screen.queryByText("הטיוטה נוצרה. מעבר לעורך הטיוטה…")).not.toBeInTheDocument();
  });
  it.each(["inactive", "stale", "newer-draft", "review"])(
    "does not consume a restored navigation receipt for %s work",
    async (scenario) => {
      const generated = queued({
        id: "op-draft",
        operation_type: "create_draft",
        status: "succeeded",
        is_terminal: true,
        outputs: [{ output_type: "working_draft", output_id: "draft-1", active: scenario !== "inactive" }],
      });
      const projection = analyzed_detail({
        active_selection_plan_id: "plan-1",
        latest_operation: generated,
        active_working_draft_id: scenario === "newer-draft" ? "draft-2" : "draft-1",
        working_draft_state: scenario === "stale" ? "stale" : "editing",
      });
      if (scenario === "review")
        projection.review_reasons = [
          {
            code: "HARD_GAP_REQUIRES_DECISION",
            message: "Decision required",
            entity_references: {},
            allowed_resolution_actions: [],
          },
        ];
      vi.stubGlobal(
        "fetch",
        vi.fn((input: RequestInfo | URL) =>
          Promise.resolve(jsonResponse(String(input).includes("/operations/") ? generated : projection)),
        ),
      );
      sessionStorage.setItem("stage-e:draft-navigation:op-draft", "pending");
      renderPage();
      expect(await screen.findByText("Acme — Backend Engineer")).toBeInTheDocument();
      expect(screen.queryByText("Draft editor route")).not.toBeInTheDocument();
      expect(sessionStorage.getItem("stage-e:draft-navigation:op-draft")).toBe("pending");
    },
  );
});
