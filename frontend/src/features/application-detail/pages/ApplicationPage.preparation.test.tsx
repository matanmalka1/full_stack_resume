import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useNavigate } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ApplicationDetail, Operation, Settings } from "@/api/contracts";
import { applicationDetailQueryKey } from "@/api/applications";
import { operationQueryKey, operationQueryOptions } from "@/api/operations";
import { settingsQueryKey } from "@/api/settings";
import { ApplicationPage } from "./ApplicationPage";

const ANALYSES_PATH = "/api/v1/applications/app-1/analyses";
const HASH = "a".repeat(64);

const detail = (overrides: Partial<ApplicationDetail> = {}): ApplicationDetail => ({
  recruitment_status: "saved",
  allowed_recruitment_transitions: ["withdrawn", "closed"],
  recruitment_timeline: [],
  preparation_state: "needs_analysis",
  content_check: "none",
  review_reasons: [],
  warnings: [],
  job_text_hash: "c".repeat(64),
  available_actions: ["analyze"],
  blocked_actions: [],
  recommended_action: "analyze",
  application: {
    id: "app-1",
    company: "Acme",
    target_role: "Backend Engineer",
    current_status: "saved",
    notes: "",
    created_at: "2026-08-24T07:00:00Z",
    updated_at: "2026-08-24T07:00:00Z",
  },
  job_posting: {
    job_text: "Senior Backend Engineer",
    job_text_hash: "c".repeat(64),
    job_text_updated_at: "2026-08-24T07:00:00Z",
    locked: false,
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

/* An Application whose first analysis is on record and created its document: a selection
   and no content. The base fixture leaves all of it absent, which is the pre-analysis
   state, so only the tests that opt in here render the analysis panel. */
const analyzed_detail = (overrides: Partial<ApplicationDetail> = {}): ApplicationDetail =>
  detail({
    preparation_state: "ready_to_draft",
    available_actions: ["create_draft"],
    recommended_action: "create_draft",
    latest_analysis_id: "analysis-1",
    document_id: "doc-1",
    document_hash: HASH,
    document_analysis_id: "analysis-1",
    latest_analysis: {
      id: "analysis-1",
      application_id: "app-1",
      job_text_hash: "c".repeat(64),
      version_number: 1,
      analysis: {
        analysis_version: "3.0",
        track: "development",
        profile: "development",
        emphasis: "development-backend",
        language: "en",
        summary: "The posting is a backend role.",
        keywords: ["FastAPI", "PostgreSQL"],
        requirements: [],
        issues: [],
        source_coverage: 1,
        user_override: {},
      },
      fit_level: "high",
      fit_score: 1,
      gaps: [],
      provider: "openai",
      model: "gpt-5.6-terra",
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

/* No AI provider configured: the state in which neither analysis nor drafting can run. */
const noProviderSettings: Settings = {
  edit_version: 0,
  auto_generate_when_review_not_required: false,
  default_ai_model: "gpt-5.6-terra",
  default_reasoning_effort: "medium",
  available_ai_models: [],

  provider_configured: false,
  ui_density: "comfortable",
  ui_text_size: "normal",
  ui_theme: "system",
  updated_at: null,
};

/* The only state analysis and drafting can be commanded from. Both are AI-only, so their
   buttons read `provider_configured` and are inert without it. */
const aiSettings: Settings = { ...noProviderSettings, provider_configured: true };

/* Retries are off. Query-specific polling options override the client's default,
   so tests that require a completion tick explicitly refresh the watched Operation. */
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

const renderPage = (settings: Settings = aiSettings, routeState?: unknown) => {
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
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
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

    renderPage(noProviderSettings, {
      createdApplication: { analysisProblem: null, operationId: "op-1" },
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

  /* §9 automatic generation is the server's: the analysis that creates the document
     queues `create_draft` in the same commit. The screen follows that run and sends no
     command of its own. */
  it("follows the draft the server queued after the analysis, sending nothing itself", async () => {
    const analyzed = queued({
      status: "succeeded",
      is_terminal: true,
      phase: "completed",
      available_actions: [],
      outputs: [{ output_type: "job_analysis", output_id: "analysis-1" }],
    });
    const drafting = queued({ id: "op-draft", operation_type: "create_draft" });
    let projectionReads = 0;
    const fetchMock = vi.fn((input: RequestInfo | URL, _init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/operations/op-draft")) return Promise.resolve(jsonResponse(drafting));
      if (url.includes("/settings")) {
        return Promise.resolve(jsonResponse({ ...aiSettings, auto_generate_when_review_not_required: true }));
      }
      if (url.includes("/operations/")) return Promise.resolve(jsonResponse(analyzed));
      projectionReads += 1;
      return Promise.resolve(
        jsonResponse(
          projectionReads === 1
            ? detail({ active_operation: queued({ status: "running" }) })
            : analyzed_detail({ active_operation: drafting, latest_operation: analyzed }),
        ),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    renderPage({ ...aiSettings, auto_generate_when_review_not_required: true });

    await waitFor(() =>
      expect(fetchMock.mock.calls.some(([input]) => String(input).endsWith("/operations/op-draft"))).toBe(true),
    );
    expect(fetchMock.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(0);
  });

  it("moves to the editor after the automatically generated draft succeeds", async () => {
    let projectionReads = 0;
    const analyzed = queued({
      status: "succeeded",
      is_terminal: true,
      phase: "completed",
      available_actions: [],
      outputs: [{ output_type: "job_analysis", output_id: "analysis-1" }],
    });
    const drafting = queued({ id: "op-draft", operation_type: "create_draft" });
    const drafted = queued({
      id: "op-draft",
      operation_type: "create_draft",
      status: "succeeded",
      is_terminal: true,
      phase: "completed",
      available_actions: [],
    });
    let draftActivated = false;
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/operations/op-draft")) {
          draftActivated = true;
          return Promise.resolve(jsonResponse(drafted));
        }
        if (url.includes("/settings")) {
          return Promise.resolve(jsonResponse({ ...aiSettings, auto_generate_when_review_not_required: true }));
        }
        if (url.includes("/operations/")) return Promise.resolve(jsonResponse(analyzed));
        projectionReads += 1;
        return Promise.resolve(
          jsonResponse(
            analyzed_detail({
              active_operation:
                projectionReads === 1 ? queued({ status: "running" }) : draftActivated ? null : drafting,
              /* The newest run the server reports: the analysis, then its draft. */
              latest_operation: projectionReads === 1 ? null : draftActivated ? drafted : analyzed,
              ...(draftActivated
                ? {
                    content_check: "outdated",
                    preparation_state: "draft_in_progress",
                  }
                : {}),
            }),
          ),
        );
      }),
    );

    const { client } = renderPage({ ...aiSettings, auto_generate_when_review_not_required: true });

    /* The draft is followed from the projection that names it. Drive its next read
       explicitly rather than spending the test budget on a poll timer. */
    await waitFor(() => expect(client.getQueryData<Operation>(operationQueryKey("op-draft"))).toBeDefined());
    await act(async () => {
      await client.fetchQuery(operationQueryOptions("op-draft"));
    });

    expect(await screen.findByText("Draft editor route")).toBeInTheDocument();
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
    });
    let draftActivated = false;
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (init?.method === "POST") return Promise.resolve(acceptedResponse(drafting));
      if (url.includes("/settings")) return Promise.resolve(jsonResponse(aiSettings));
      if (url.endsWith("/operations/op-draft")) {
        draftActivated = true;
        return Promise.resolve(jsonResponse(drafted));
      }
      return Promise.resolve(
        jsonResponse(
          analyzed_detail({
            available_actions: ["create_draft"],
            recommended_action: "create_draft",
            ...(draftActivated
              ? {
                  content_check: "outdated",
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
  /* Drafting is AI-only: every generate names the provider, and the bar says what the
     press costs. */
  it("runs the draft through the provider", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === "POST") {
        return Promise.resolve(acceptedResponse(queued({ id: "op-draft", operation_type: "create_draft" })));
      }
      return Promise.resolve(
        jsonResponse(
          String(input).includes("/settings")
            ? aiSettings
            : analyzed_detail({
                available_actions: ["create_draft"],
                recommended_action: "create_draft",
              }),
        ),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    renderPage(aiSettings);

    expect(
      await screen.findByText("היצירה כוללת קריאת AI בתשלום, והעבודה מתבצעת ברקע.", { exact: false }),
    ).toBeInTheDocument();
    await clickEnabledButton("יצירת טיוטה");

    await waitFor(() => expect(fetchMock.mock.calls.filter((call) => call[1]?.method === "POST")).toHaveLength(1));
    const post = fetchMock.mock.calls.find((call) => call[1]?.method === "POST");
    expect(String(post?.[0])).toContain("/applications/app-1/document/draft");
    expect(JSON.parse(String(post?.[1]?.body))).toEqual({ expected_document_hash: HASH, provider: "openai" });
  });

  it("refuses to command a draft with no AI provider configured", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, _init?: RequestInit) =>
      Promise.resolve(
        jsonResponse(
          String(input).includes("/settings")
            ? noProviderSettings
            : analyzed_detail({
                available_actions: ["create_draft"],
                recommended_action: "create_draft",
              }),
        ),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    renderPage(noProviderSettings);

    expect(await screen.findByText("יצירת הטיוטה דורשת ספק AI, ועדיין לא הוגדר כזה.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "יצירת טיוטה" })).toBeDisabled();
    expect(screen.getByRole("link", { name: "פתיחת ההגדרות" })).toBeInTheDocument();
    expect(fetchMock.mock.calls.filter((call) => call[1]?.method === "POST")).toHaveLength(0);
  });

  it("analyzes the exact job text the projection names and reports the queued Operation", async () => {
    /* Routed by URL rather than by call order: once the command is accepted the screen
       watches the Operation it queued, so a fixed queue of answers would leave that read
       unanswered and the overlay would never settle. */
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === "POST") {
        return Promise.resolve(acceptedResponse(queued()));
      }
      if (String(input).includes("/operations/")) {
        return Promise.resolve(jsonResponse(queued()));
      }
      if (String(input).includes("/settings")) {
        return Promise.resolve(jsonResponse(aiSettings));
      }
      return Promise.resolve(jsonResponse(detail()));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderPage(aiSettings);
    await clickEnabledButton("ניתוח המשרה");

    /* The accepted `202` is seeded as the overlay's first state, so the queued Operation is
       reported on this screen rather than on one the user was sent to. */
    expect(await screen.findByRole("heading", { name: "הרצת ניתוח המשרה", level: 2 })).toBeInTheDocument();
    expect(screen.queryByText("המשרה טרם נותחה")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "ניתוח המשרה" })).not.toBeInTheDocument();
    expect(screen.queryByText("חומר עזר")).not.toBeInTheDocument();

    const request = fetchMock.mock.calls.find((call) => call[0] === ANALYSES_PATH);
    expect(request?.[0]).toBe(ANALYSES_PATH);
    expect(request?.[1]).toEqual(expect.objectContaining({ method: "POST" }));
    /* The source is explicit: an analyze command that picked up whatever text is current could
       classify something other than what the screen was showing. The provider is explicit
       for the same reason - analysis runs one AI lane and names it. */
    expect(JSON.parse(String(request?.[1]?.body))).toEqual({ job_text_hash: "c".repeat(64), provider: "openai" });
    expect((request?.[1]?.headers as Headers | undefined)?.get("Idempotency-Key")).not.toBeNull();
  });

  /* The D5 gate, from the screen's side: analysis is an AI-only lane, so with no provider
     configured there is no way to command it at all. The button stays on screen rather
     than vanishing - the projection still names the action - and the sentence above it
     says what is missing, because an inert control with no reason reads as a broken one. */
  it("refuses to command an analysis with no AI provider configured", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) =>
        Promise.resolve(
          String(input).includes("/settings") ? jsonResponse(noProviderSettings) : jsonResponse(detail()),
        ),
      ),
    );

    renderPage(noProviderSettings);

    expect(await screen.findByRole("button", { name: "ניתוח המשרה" })).toBeDisabled();
    /* The reason sits in the bar beside the inert button, and the bar leads with the way
       to fix it. The "not analyzed yet" banner does not repeat either. */
    expect(screen.getByText("הניתוח דורש ספק AI, ועדיין לא הוגדר כזה.")).toBeInTheDocument();
    expect(screen.queryByText(/כדי לנתח את המשרה יש להגדיר ולהפעיל ספק AI בהגדרות/)).not.toBeInTheDocument();
    const settingsLinks = screen.getAllByRole("link", { name: "פתיחת ההגדרות" });
    expect(settingsLinks).toHaveLength(1);
    for (const link of settingsLinks) expect(link).toHaveAttribute("href", "/settings");
  });

  it("shows the frozen AI execution and its calculated cost", async () => {
    const aiOperation = queued({
      provider: "openai",
      model: "gpt-5.6-luna",
      reasoning_effort: "high",
      input_tokens: 11,
      cached_input_tokens: 3,
      cache_write_tokens: 5,
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
    /* Two significant digits below a cent, not the raw decimal string. */
    expect(screen.getByText("$0.000028")).toBeInTheDocument();
    expect(screen.getByText("מאמץ חשיבה")).toBeInTheDocument();
    expect(screen.getByText("גבוה")).toBeInTheDocument();
    /* Cache writes are billed at their own rate, so they are shown beside cache reads. */
    expect(screen.getByText("כתיבה למטמון")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
  });

  it("does not present a superseded analysis as the one in force", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(analyzed_detail({ latest_analysis_id: "analysis-9" }))),
    );

    renderPage();

    expect(await screen.findByText("הניתוח שעל המסך אינו הניתוח הפעיל")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "ניתוח המשרה" })).not.toBeInTheDocument();
    expect(screen.queryByText("The posting is a backend role.")).not.toBeInTheDocument();
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
              job_text_hash: "c".repeat(64),
              version_number: 1,
              analysis: {
                analysis_version: "3.0",
                track: "development",
                profile: "development",
                emphasis: "development-backend",
                language: "en",
                summary: "The posting is a backend role.",
                keywords: ["FastAPI"],
                requirements: [
                  {
                    requirement_id: "req-1",
                    text: "5 years of Python",
                    importance: "mandatory",
                    coverage: "matched",
                    supporting_fact_ids: ["fact-1"],
                    boundary_fact_ids: [],
                    source: null,
                  },
                  {
                    requirement_id: "req-2",
                    text: "Production Kubernetes experience",
                    importance: "mandatory",
                    coverage: "partial",
                    supporting_fact_ids: [],
                    boundary_fact_ids: ["fact-boundary"],
                    source: null,
                  },
                  {
                    requirement_id: "req-3",
                    text: "Terraform",
                    importance: "preferred",
                    coverage: "unsupported",
                    supporting_fact_ids: [],
                    boundary_fact_ids: [],
                    source: null,
                  },
                  {
                    requirement_id: "",
                    text: "Malformed requirement",
                    importance: "mandatory",
                    coverage: "matched",
                    supporting_fact_ids: [],
                    boundary_fact_ids: [],
                    source: null,
                  },
                ],
                issues: [],
                source_coverage: 1,
                user_override: {},
              },
              fit_level: "high",
              fit_score: 1,
              gaps: [],
              provider: "openai",
              model: "gpt-5.6-terra",
              created_at: "2026-08-24T07:00:00Z",
            },
          }),
        ),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    renderPage();

    /* The list opens on what needs attention; a covered requirement is one press away. */
    expect(await screen.findByText("Production Kubernetes experience")).toBeInTheDocument();
    expect(screen.getByText("Terraform")).toBeInTheDocument();
    expect(screen.queryByText("5 years of Python")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "הכל (3)" }));
    expect(
      within(screen.getByRole("list", { name: "דרישות חובה" })).getByText("5 years of Python"),
    ).toBeInTheDocument();
    expect(within(screen.getByRole("list", { name: "דרישות מועדפות" })).getByText("Terraform")).toBeInTheDocument();

    /* Coverage is split by how much the employer insists, and the malformed record is
       reported rather than silently dropped. */
    expect(screen.getByText("1/2 מכוסות")).toBeInTheDocument();
    expect(screen.getByText("0/1 מכוסות")).toBeInTheDocument();
    expect(screen.getByText("הערות על אמינות הניתוח (1)")).toBeInTheDocument();
    expect(screen.getByText("דרישה אחת לא הייתה תקינה ואינה מוצגת.")).toBeInTheDocument();
    expect(screen.queryByText("Malformed requirement")).not.toBeInTheDocument();

    /* Evidence is resolved by id to the fact's current wording. */
    expect(screen.getByText("עובדה אחת מעידה על הדרישה")).toBeInTheDocument();
    expect(await screen.findByText("5 years building backend systems in Python")).toBeInTheDocument();
    expect(screen.getByText("מה מגביל את הכיסוי")).toBeInTheDocument();
    expect(screen.getByText("Used Kubernetes in a personal lab")).toBeInTheDocument();
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
            content_check: "failed",
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
    expect(screen.getByText("הבדיקה נכשלה. צריך לתקן ולבדוק מחדש.")).toBeInTheDocument();
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
    /* A run that had already failed when the screen read it is history: it does not pop
       over the page, and its report - retry included - is a press on its chip away. */
    fireEvent.click(await screen.findByRole("button", { name: /פירוט ההרצה/ }));
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

  /* QA report finding 2: `available_actions`/`recommended_action` still name a plain
     "analyze" after a terminal failure - the projection never withdrew it - but the
     screen used to show only the Operation overlay's own "retry", which can only ever
     resend the failed run's own frozen execution. The fix renders this step's own action
     panel beside the failure, so its analyze button - wired to current Settings via
     `useAnalyzeCommand` - is reachable without leaving the screen or predicting the
     projection in a new way: a fresh analyze is offered beside retry, and it queues a new
     Operation rather than resending the failed one. */
  it("offers a fresh analysis beside retry after a terminal analysis failure", async () => {
    const failed = queued({
      status: "failed",
      is_terminal: true,
      failure_code: "INVALID_OUTPUT",
      available_actions: ["retry"],
    });
    const fresh = queued({ id: "op-fresh" });
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === ANALYSES_PATH && init?.method === "POST") return Promise.resolve(acceptedResponse(fresh));
      if (url.endsWith("/operations/op-1")) return Promise.resolve(jsonResponse(failed));
      if (url.includes("/settings")) return Promise.resolve(jsonResponse(aiSettings));
      return Promise.resolve(jsonResponse(detail({ latest_operation: failed, active_operation: null })));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderPage(aiSettings);

    /* Both ways forward are on screen at once. Neither is offered instead of the other;
       the projection permits both and the reader chooses. */
    fireEvent.click(await screen.findByRole("button", { name: /פירוט ההרצה/ }));
    expect(await screen.findByRole("button", { name: "ניסיון חוזר" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "סגירה" }));
    await clickEnabledButton("ניתוח המשרה");

    const request = fetchMock.mock.calls.find(([, init]) => init?.method === "POST");
    /* A fresh analyze command against the job text, not a resend of the failed run: it
       posts to the analyses collection rather than to that Operation's retry route. */
    expect(request?.[0]).toBe(ANALYSES_PATH);
    expect(JSON.parse(String(request?.[1]?.body))).toEqual({ job_text_hash: "c".repeat(64), provider: "openai" });
  });

  /* A run with no provider is fixed in Settings, not in the posting, so the posting
     stays folded away like on any other visit instead of opening with its edit action. */
  it("keeps the posting folded when analysis failed for want of a provider", async () => {
    const failed = queued({
      status: "failed",
      is_terminal: true,
      failure_code: "PROVIDER_NOT_CONFIGURED",
      available_actions: ["retry"],
    });
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) =>
        Promise.resolve(
          String(input).includes("/settings")
            ? jsonResponse(noProviderSettings)
            : jsonResponse(detail({ latest_operation: failed, active_operation: null })),
        ),
      ),
    );

    renderPage(noProviderSettings);

    expect(await screen.findByText("צפייה בנוסח המשרה שנשמר")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "עדכון נוסח המשרה" })).not.toBeVisible();
  });

  it("keeps the stored posting and its update action reachable after analysis fails", async () => {
    const failed = queued({
      status: "failed",
      is_terminal: true,
      failure_code: "MISSING_FACT_RENDERING",
      safe_failure_detail: "Fact development.phdigital.nextjs has no 'he' rendering.",
      failure_reason: { code: "missing_fact_rendering", fact_id: "development.phdigital.nextjs", language: "he" },
      available_actions: [],
    });
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) =>
        Promise.resolve(
          String(input).includes("/settings")
            ? jsonResponse(aiSettings)
            : jsonResponse(detail({ latest_operation: failed, active_operation: null })),
        ),
      ),
    );

    renderPage(aiSettings);

    expect(await screen.findByText("לעובדה development.phdigital.nextjs חסר ניסוח בשפה he.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "עדכון נוסח המשרה" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "עדכון נוסח המשרה" }));
    expect(screen.getByRole("dialog", { name: "עריכת נוסח המשרה" })).toBeInTheDocument();
    expect(screen.getByLabelText("טקסט המשרה")).toHaveValue("Senior Backend Engineer");
  });

  it("offers analysis after creation scheduling failed and does not retain creation news over later server work", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) =>
        Promise.resolve(String(input).includes("/settings") ? jsonResponse(aiSettings) : jsonResponse(detail())),
      ),
    );
    const { client } = renderPage(aiSettings, { createdApplication: { operationId: null } });
    expect(await screen.findByText("המועמדות נוצרה, אך הניתוח לא הופעל")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "ניתוח המשרה" })).toBeEnabled();
    act(() => client.setQueryData(applicationDetailQueryKey("app-1"), analyzed_detail()));
    await waitFor(() => expect(screen.queryByText("המועמדות נוצרה, אך הניתוח לא הופעל")).not.toBeInTheDocument());
    expect(await screen.findByRole("button", { name: "יצירת טיוטה" })).toBeInTheDocument();
  });

  it("restores a completed analysis from the server and sends no draft command of its own", async () => {
    const analyzed = queued({
      status: "succeeded",
      is_terminal: true,
      available_actions: [],
      outputs: [{ output_type: "job_analysis", output_id: "analysis-1" }],
    });
    const fetchMock = vi.fn((input: RequestInfo | URL, _init?: RequestInit) => {
      if (String(input).includes("/settings"))
        return Promise.resolve(jsonResponse({ ...aiSettings, auto_generate_when_review_not_required: true }));
      if (String(input).includes("/operations/")) return Promise.resolve(jsonResponse(analyzed));
      return Promise.resolve(jsonResponse(analyzed_detail({ latest_operation: analyzed })));
    });
    vi.stubGlobal("fetch", fetchMock);
    renderPage({ ...aiSettings, auto_generate_when_review_not_required: true });
    /* The projection names no queued draft, so there is nothing to follow: the run settles. */
    expect(await screen.findByRole("button", { name: "יצירת טיוטה" })).toBeInTheDocument();
    expect(screen.queryByText("הניתוח הושלם. יצירת הטיוטה מתחילה מיד.")).not.toBeInTheDocument();
    expect(fetchMock.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(0);
  });

  it("isolates late watched analysis results across URL changes and Back / Forward", async () => {
    let resolveOld: (response: Response) => void = () => {};
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/operations/"))
        return new Promise<Response>((resolve) => {
          resolveOld = resolve;
        });
      if (url.includes("/settings")) return Promise.resolve(jsonResponse(aiSettings));
      return Promise.resolve(
        jsonResponse(
          url.endsWith("/app-2")
            ? detail({ application: { ...detail().application, id: "app-2", company: "Other" } })
            : detail({ active_operation: queued() }),
        ),
      );
    });
    vi.stubGlobal("fetch", fetchMock);
    renderPage(aiSettings);
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

  it("waits for the document's content on refresh and does not repeat completed navigation on Back", async () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    const generated = queued({
      id: "op-draft",
      operation_type: "create_draft",
      status: "succeeded",
      is_terminal: true,
    });
    const projection = analyzed_detail({ latest_operation: generated });
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) =>
        Promise.resolve(jsonResponse(String(input).includes("/operations/") ? generated : projection)),
      ),
    );
    const { client } = renderPage(noProviderSettings, {
      preparationContinuation: { applicationId: "app-1", draftOperationId: "op-draft" },
    });
    expect(await screen.findByText("Acme — Backend Engineer")).toBeInTheDocument();
    expect(screen.queryByText("Draft editor route")).not.toBeInTheDocument();
    await waitFor(() => expect(client.isFetching()).toBe(0));
    act(() =>
      client.setQueryData(applicationDetailQueryKey("app-1"), {
        ...projection,
        content_check: "outdated",
        preparation_state: "draft_in_progress",
      }),
    );
    expect(await screen.findByText("Draft editor route")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Analysis" }));
    expect(await screen.findByText("Acme — Backend Engineer")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(await screen.findByText("Draft editor route")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Forward" }));
    expect(await screen.findByText("Acme — Backend Engineer")).toBeInTheDocument();
    expect(screen.queryByText("Draft editor route")).not.toBeInTheDocument();
    expect(screen.queryByText("הטיוטה נוצרה. מעבר לעורך הטיוטה…")).not.toBeInTheDocument();
  });
  it.each(["review-blocked", "no-content", "other-operation"])(
    "does not consume a restored navigation receipt for %s work",
    async (scenario) => {
      const generated = queued({
        id: "op-draft",
        operation_type: "create_draft",
        status: "succeeded",
        is_terminal: true,
      });
      const projection = analyzed_detail({
        latest_operation: generated,
        ...(scenario === "no-content" ? {} : { preparation_state: "draft_in_progress" as const }),
        ...(scenario === "review-blocked"
          ? {
              review_reasons: [
                {
                  code: "PENDING_FACT_REQUIRES_RESOLUTION",
                  message: "a claim has no confirmed fact",
                  entity_references: {},
                  allowed_resolution_actions: ["confirm_and_use_fact"],
                },
              ],
            }
          : {}),
      });
      vi.stubGlobal(
        "fetch",
        vi.fn((input: RequestInfo | URL) =>
          Promise.resolve(jsonResponse(String(input).includes("/operations/") ? generated : projection)),
        ),
      );
      renderPage(noProviderSettings, {
        preparationContinuation: {
          applicationId: "app-1",
          draftOperationId: scenario === "other-operation" ? "op-other" : "op-draft",
        },
      });
      expect(await screen.findByText("Acme — Backend Engineer")).toBeInTheDocument();
      expect(screen.queryByText("Draft editor route")).not.toBeInTheDocument();
    },
  );
});

/* §14 `build_from_analysis`: a newer analysis never changes the document by itself. The
   projection warns, and re-pinning is an explicit press - confirmed first when it would
   discard written content. */
describe("a document built on an older analysis", () => {
  const olderDocument = (overrides: Partial<ApplicationDetail> = {}) =>
    analyzed_detail({
      preparation_state: "draft_in_progress",
      latest_analysis_id: "analysis-1",
      document_analysis_id: "analysis-0",
      available_actions: ["build_from_analysis", "edit"],
      recommended_action: null,
      warnings: [
        {
          code: "DOCUMENT_ON_OLDER_ANALYSIS",
          message: "the document is pinned to an older analysis",
          entity_references: {},
        },
      ],
      ...overrides,
    });

  it("warns, and rebuilds only after confirming that the draft's content is discarded", async () => {
    const fetchMock = vi.fn((_input: RequestInfo | URL, init?: RequestInit) =>
      Promise.resolve(
        init?.method === "POST"
          ? jsonResponse({
              application_id: "app-1",
              document_id: "doc-1",
              document_hash: "b".repeat(64),
              preparation_state: "draft_in_progress",
              content_check: "none",
              pending_claim_ids: [],
            })
          : jsonResponse(olderDocument()),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    renderPage();

    expect(await screen.findByText("המסמך בנוי על ניתוח ישן יותר")).toBeInTheDocument();
    await clickEnabledButton("בנייה מחדש מהניתוח החדש");
    const dialog = await screen.findByRole("dialog", { name: "בניית המסמך מחדש מהניתוח החדש" });
    expect(fetchMock.mock.calls.filter((call) => call[1]?.method === "POST")).toHaveLength(0);

    fireEvent.click(within(dialog).getByRole("button", { name: "בנייה מחדש מהניתוח החדש" }));

    await waitFor(() => expect(fetchMock.mock.calls.filter((call) => call[1]?.method === "POST")).toHaveLength(1));
    const post = fetchMock.mock.calls.find((call) => call[1]?.method === "POST");
    expect(String(post?.[0])).toBe("/api/v1/applications/app-1/document/build-from-analysis");
    expect(JSON.parse(String(post?.[1]?.body))).toEqual({ expected_document_hash: HASH, analysis_id: "analysis-1" });
  });

  it("rebuilds without asking while the document has no content to lose", async () => {
    const fetchMock = vi.fn((_input: RequestInfo | URL, init?: RequestInit) =>
      Promise.resolve(
        init?.method === "POST"
          ? jsonResponse({
              application_id: "app-1",
              document_id: "doc-1",
              document_hash: "b".repeat(64),
              preparation_state: "ready_to_draft",
              content_check: "none",
              pending_claim_ids: [],
            })
          : jsonResponse(olderDocument({ preparation_state: "ready_to_draft" })),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    renderPage();

    await clickEnabledButton("בנייה מחדש מהניתוח החדש");
    await waitFor(() => expect(fetchMock.mock.calls.filter((call) => call[1]?.method === "POST")).toHaveLength(1));
    expect(screen.queryByRole("dialog", { name: "בניית המסמך מחדש מהניתוח החדש" })).not.toBeInTheDocument();
  });

  it("is not offered unless the projection offers it", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(olderDocument({ available_actions: ["edit"] }))));

    renderPage();

    expect(await screen.findByText("המסמך בנוי על ניתוח ישן יותר")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "בנייה מחדש מהניתוח החדש" })).not.toBeInTheDocument();
  });
});
