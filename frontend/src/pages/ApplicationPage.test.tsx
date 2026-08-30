import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ApplicationDetail, Operation, Settings } from "../api/contracts";
import { settingsQueryKey } from "../api/settings";
import { ApplicationPage } from "./ApplicationPage";

const DETAIL_PATH = "/api/v1/applications/app-1";
const ANALYSES_PATH = "/api/v1/applications/app-1/analyses";
const GENERATE_PATH = "/api/v1/applications/app-1/working-draft/generate";

const detail = (overrides: Partial<ApplicationDetail> = {}): ApplicationDetail => ({
  recruitment_status: "saved",
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
const analyzed = (overrides: Partial<ApplicationDetail> = {}): ApplicationDetail =>
  detail({
    preparation_state: "ready_to_draft",
    available_actions: ["draft"],
    recommended_action: "draft",
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
 
  provider_configured: false,
  ui_density: "comfortable",
  ui_text_size: "normal",
  updated_at: null,
};

/* Retries and the projection poll are off inside the test client: the interval is
   covered by its own unit test, and a live timer here would make every assertion racy. */
const renderPage = (settings: Settings = deterministicSettings) => {
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

  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/applications/app-1"]}>
        <Routes>
          <Route element={<ApplicationPage />} path="/applications/:applicationId" />
          <Route element={<h1>מצב הפעולה</h1>} path="/operations/:operationId" />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
};

const clickEnabledButton = async (name: string) => {
  const button = await screen.findByRole("button", { name });
  await waitFor(() => expect(button).toBeEnabled());
  fireEvent.click(button);
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("ApplicationPage", () => {
  it("names the page without repeating shell context and reports both projected states", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(detail())));

    renderPage();

    expect(
      screen.getByRole("heading", { level: 1, name: "מצב המועמדות" }),
    ).toBeInTheDocument();
    /* The heading is static and appears during loading, so the projected state—not the
       h1—is the synchronization point for assertions about the loaded application. */
    expect(await screen.findByText("ממתין לניתוח המשרה")).toBeInTheDocument();
    expect(screen.queryByText("Acme")).not.toBeInTheDocument();
    expect(screen.queryByText("Backend Engineer")).not.toBeInTheDocument();
    /* The draft axis is suppressed while the stage already implies it: at
       `needs_analysis` a draft cannot exist, so "there is no active draft" beside
       "waiting for the job analysis" is a restatement, not a second state. */
    expect(screen.queryByText("אין טיוטה פעילה")).not.toBeInTheDocument();
  });

  it("reports the draft axis when the stage does not settle it", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          /* `ready_to_draft` is reached both with no draft and with a draft whose
             sources went stale, so the stage alone implies nothing. This is the stale
             path: the draft exists, and its state is the one thing on the screen that
             says so. */
          detail({
            preparation_state: "ready_to_draft",
            working_draft_state: "stale",
            active_analysis_id: "analysis-1",
            active_selection_plan_id: "plan-1",
            active_working_draft_id: "draft-1",
            available_actions: ["create_draft"],
            recommended_action: "create_draft",
          }),
        ),
      ),
    );

    renderPage();

    expect(await screen.findByText("מוכן ליצירת טיוטה")).toBeInTheDocument();
    expect(screen.getByText("הטיוטה אינה מעודכנת מול המקורות")).toBeInTheDocument();
  });

  it("stays silent about the draft axis when the stage already settles it", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          detail({
            preparation_state: "ready_to_draft",
            working_draft_state: "none",
            active_analysis_id: "analysis-1",
            active_selection_plan_id: "plan-1",
            available_actions: ["create_draft"],
            recommended_action: "create_draft",
          }),
        ),
      ),
    );

    renderPage();

    expect(await screen.findByText("מוכן ליצירת טיוטה")).toBeInTheDocument();
    expect(screen.queryByText("אין טיוטה פעילה")).not.toBeInTheDocument();
  });

  it("analyzes the exact snapshot the projection names and follows the accepted Operation", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(detail()))
      .mockResolvedValueOnce(acceptedResponse(queued()));
    vi.stubGlobal("fetch", fetchMock);

    renderPage();
    await clickEnabledButton("ניתוח המשרה");

    expect(await screen.findByRole("heading", { name: "מצב הפעולה" })).toBeInTheDocument();

    const request = fetchMock.mock.calls[1];
    expect(request?.[0]).toBe(ANALYSES_PATH);
    expect(request?.[1]).toEqual(expect.objectContaining({ method: "POST" }));
    /* The source is explicit: an analyze command that picked its own snapshot could
       classify something other than what the screen was showing. */
    expect(JSON.parse(String(request?.[1]?.body))).toEqual({ job_snapshot_id: "snap-1" });
    expect((request?.[1]?.headers as Headers).get("Idempotency-Key")).not.toBeNull();
  });

  it("uses the effective manual AI mode without changing the deterministic default", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(jsonResponse(detail())).mockResolvedValueOnce(acceptedResponse(queued()));
    vi.stubGlobal("fetch", fetchMock);
    renderPage({
      edit_version: 1,
      auto_generate_when_review_not_required: false,
      ai_enabled: true,
      ai_enabled_override: true,
      default_execution_mode: "ai",
     
      provider_configured: true,
      ui_density: "comfortable",
      ui_text_size: "normal",
      updated_at: null,
    });

    await clickEnabledButton("ניתוח המשרה");

    expect(JSON.parse(String(fetchMock.mock.calls[1]?.[1]?.body))).toEqual({
      job_snapshot_id: "snap-1",
      provider: "openai",
    });
  });

  it("refuses to follow an accepted response that does not name its queued Operation", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(jsonResponse(detail()))
        .mockResolvedValueOnce(jsonResponse(queued(), 202)),
    );

    renderPage();
    await clickEnabledButton("ניתוח המשרה");

    expect(await screen.findByRole("alert")).toHaveTextContent("הפעולה לא בוצעה");
    expect(screen.queryByRole("heading", { name: "מצב הפעולה" })).not.toBeInTheDocument();
  });

  /* A.1: the projection decides what comes next. A recommended action whose screen this
     slice does not build is named and reported as missing, never routed to something
     invented for it. */
  it("names a recommended action it cannot perform instead of inventing a screen", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          detail({
            preparation_state: "draft_in_progress",
            working_draft_state: "editing",
            active_analysis_id: "analysis-1",
            active_selection_plan_id: "plan-1",
            active_working_draft_id: "draft-1",
            available_actions: ["analyze", "create_draft", "archive_working_draft"],
            recommended_action: "archive_working_draft",
          }),
        ),
      ),
    );

    renderPage();

    expect(await screen.findByText("הפעולה המומלצת כעת היא העברת הטיוטה לארכיון")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "העברת הטיוטה לארכיון" })).not.toBeInTheDocument();
    /* Analysis is still available, but it is no longer the emphasized action and it says
       what a second analysis does. */
    expect(screen.getByRole("button", { name: "ניתוח מחדש של המשרה" })).toBeInTheDocument();
    expect(
      screen.getByText(/ניתוח מחדש יוצר ניתוח חדש ונפרד/, { exact: false }),
    ).toBeInTheDocument();
  });

  it("collapses validation and approval into the one screen they both reach", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(detail({
      preparation_state: "ready_for_approval",
      working_draft_state: "validated",
      active_working_draft_id: "draft-1",
      available_actions: ["validate", "approve"],
      recommended_action: "approve",
    }))));

    renderPage();

    /* Validation is a panel on the draft editor and approval is a dialog opened from it,
       so both actions are one destination. Offering them side by side would ask the
       reader to choose between two links that go to the same URL. */
    expect(await screen.findByRole("link", { name: "אישור הגרסה" })).toHaveAttribute("href", "/applications/app-1/draft");
    expect(screen.queryByRole("link", { name: "אימות הטיוטה" })).not.toBeInTheDocument();
  });

  it("names the draft screen for validation when approval is not yet offered", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(detail({
      preparation_state: "draft_in_progress",
      working_draft_state: "editing",
      active_working_draft_id: "draft-1",
      available_actions: ["validate"],
      recommended_action: "validate",
    }))));

    renderPage();

    /* The furthest-along offered action is the honest label: it is what the workflow is
       waiting on. */
    expect(await screen.findByRole("link", { name: "אימות הטיוטה" })).toHaveAttribute("href", "/applications/app-1/draft");
    expect(screen.queryByRole("link", { name: "אישור הגרסה" })).not.toBeInTheDocument();
  });

  /* Rendering happens in the draft editor, on the revision the approval there
     returned, so this screen has no destination for it. It names the recommended action
     rather than inventing a link - the same honest default it applies to any action whose
     screen it does not own. */
  it("names a recommended render without inventing a destination for it", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(detail({
      preparation_state: "approved",
      latest_approved_revision_id: "revision 1",
      available_actions: ["render"],
      recommended_action: "render",
    }))));

    renderPage();

    expect(await screen.findByText(/הפעולה המומלצת כעת היא/)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "יצירת קובץ קורות החיים" })).not.toBeInTheDocument();
  });

  it("keeps an older Ready revision reachable from its explicit projection ID", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(detail({
      preparation_state: "draft_in_progress",
      latest_ready_revision_id: "ready-1",
      newer_draft_in_progress: true,
      available_actions: ["update_working_draft"],
    }))));

    renderPage();

    expect(await screen.findByRole("link", { name: "צפייה בגרסה המוכנה" })).toHaveAttribute("href", "/approved-revisions/ready-1/ready");
    expect(screen.getByText("קיימת טיוטה חדשה יותר מהגרסה שאושרה")).toBeInTheDocument();
  });

  /* §21: the no-review continuation. Analyze commits the JobAnalysis and its initial
     SelectionPlan together, and both IDs are sent explicitly so the draft cannot be built
     from a plan the user never saw. */
  it("generates the draft from the exact analysis and plan the projection names", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse(
          detail({
            preparation_state: "ready_to_draft",
            active_analysis_id: "analysis-1",
            active_selection_plan_id: "plan-1",
            available_actions: ["analyze", "create_draft"],
            recommended_action: "create_draft",
          }),
        ),
      )
      .mockResolvedValueOnce(
        acceptedResponse(queued({ id: "op-2", operation_type: "create_draft" })),
      );
    vi.stubGlobal("fetch", fetchMock);

    renderPage();
    await clickEnabledButton("יצירת טיוטה");

    expect(await screen.findByRole("heading", { name: "מצב הפעולה" })).toBeInTheDocument();

    const request = fetchMock.mock.calls[1];
    expect(request?.[0]).toBe(GENERATE_PATH);
    expect(request?.[1]).toEqual(expect.objectContaining({ method: "POST" }));
    expect(JSON.parse(String(request?.[1]?.body))).toEqual({
      job_analysis_id: "analysis-1",
      selection_plan_id: "plan-1",
    });
    expect((request?.[1]?.headers as Headers).get("Idempotency-Key")).not.toBeNull();
  });

  /* §14: generate writes over the one active WorkingDraft. Discarding a working copy is a
     choice, and the command that carries it is `replace_working_draft`; this screen offers
     no button that would make that choice silently. */
  it("does not offer a generation that would overwrite an active working draft", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          detail({
            preparation_state: "ready_to_draft",
            working_draft_state: "stale",
            active_analysis_id: "analysis-1",
            active_selection_plan_id: "plan-1",
            active_working_draft_id: "draft-1",
            available_actions: [
              "analyze",
              "create_draft",
              "archive_working_draft",
              "replace_working_draft",
            ],
            recommended_action: "create_draft",
          }),
        ),
      ),
    );

    renderPage();

    expect(await screen.findByText("הפעולה המומלצת כעת היא יצירת טיוטה")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "יצירת טיוטה" })).not.toBeInTheDocument();
    expect(screen.getByText(/כותבת על הטיוטה הפעילה/, { exact: false })).toBeInTheDocument();
  });

  it("presents a review reason as a blocker with the action that resolves it", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          detail({
            preparation_state: "needs_review",
            recommended_action: "apply_analysis_decisions",
            /* The projection derives availability from the reasons themselves, so a
               review reason always makes its resolution action available. */
            available_actions: ["analyze", "apply_analysis_decisions"],
            review_reasons: [
              {
                code: "LOW_FIT_REQUIRES_ACCEPTANCE",
                message: "Low fit requires explicit acceptance before drafting.",
                entity_references: { job_analysis_id: "analysis-1" },
                allowed_resolution_actions: ["apply_analysis_decisions"],
              },
            ],
          }),
        ),
      ),
    );

    renderPage();

    expect(await screen.findByText("נדרשת החלטה לפני המשך")).toBeInTheDocument();
    expect(
      screen.getByText("Low fit requires explicit acceptance before drafting."),
    ).toHaveAttribute("dir", "auto");
    /* The resolving action has a screen now, so the reason offers it instead of
       promising one is coming. */
    expect(screen.getByRole("link", { name: "החלת החלטות הסקירה" })).toHaveAttribute(
      "href",
      "/applications/app-1/review",
    );
    expect(screen.queryByText(/מגיע בפרוסה הבאה/)).not.toBeInTheDocument();
    expect(screen.getByText("LOW_FIT_REQUIRES_ACCEPTANCE")).toBeInTheDocument();
  });

  it("still names a resolution action that has no screen instead of linking to one", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          detail({
            preparation_state: "needs_review",
            review_reasons: [
              {
                code: "FACT_SELECTION_UNRESOLVED",
                message: "The active analysis has no active SelectionPlan.",
                entity_references: { job_analysis_id: "an-1" },
                allowed_resolution_actions: ["create_selection_plan"],
              },
            ],
          }),
        ),
      ),
    );

    renderPage();

    expect(await screen.findByText(/הפעולה שפותרת אותה: בחירת העובדות/)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "בחירת העובדות" })).not.toBeInTheDocument();
  });

  it("links to the Operation the projection reports as already running", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          jsonResponse(
            detail({ active_operation: queued({ status: "running", phase: "executing" }) }),
          ),
        ),
    );

    renderPage();

    expect(await screen.findByText("פעולה רצה על המועמדות הזו")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "מעבר למצב הפעולה" })).toHaveAttribute(
      "href",
      "/operations/op-1",
    );
  });

  it("shows a load failure safely and offers no action it cannot back", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          {
            type: "about:blank#unknown-record",
            title: "Application not found",
            status: 404,
            code: "UNKNOWN_RECORD",
            detail: "אין מועמדות במזהה הזה.",
          },
          404,
        ),
      ),
    );

    renderPage();

    expect(await screen.findByRole("alert")).toHaveTextContent("אין מועמדות במזהה הזה.");
    expect(screen.queryByRole("button", { name: "ניתוח המשרה" })).not.toBeInTheDocument();
  });

  /* The analysis is the reasoning behind the stage this screen reports, so it is read
     here rather than on a route of its own. */
  it("shows what the analysis concluded once one is active", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(analyzed())));

    renderPage();

    expect(await screen.findByRole("heading", { name: "ניתוח המשרה" })).toBeInTheDocument();
    expect(screen.getByText("התאמה בינונית")).toBeInTheDocument();
    expect(screen.getByText("פיתוח צד שרת")).toBeInTheDocument();
    expect(screen.getByText("The posting is a backend role.")).toBeInTheDocument();
    expect(screen.getByText("FastAPI")).toBeInTheDocument();
    expect(screen.getByText("5 years of Python")).toBeInTheDocument();
    /* A gap is reported with its severity and the backend's own reason. */
    expect(screen.getByText("no matching fact")).toBeInTheDocument();
    expect(screen.getByText("פער לתשומת לב")).toBeInTheDocument();
  });

  it("says nothing about an analysis before one exists", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(detail())));

    renderPage();

    expect(await screen.findByText("ממתין לניתוח המשרה")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "ניתוח המשרה" })).not.toBeInTheDocument();
  });

  /* `latest_analysis` is the newest analysis of any snapshot and `active_analysis_id` the
     newest for the active one. When they diverge the stored analysis describes a posting
     that is no longer the one in force, so it is named as superseded instead of shown. */
  it("does not present a superseded analysis as the one in force", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(analyzed({ active_analysis_id: "analysis-9" }))),
    );

    renderPage();

    expect(
      await screen.findByText("הניתוח שעל המסך אינו הניתוח הפעיל"),
    ).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "ניתוח המשרה" })).not.toBeInTheDocument();
    expect(screen.queryByText("The posting is a backend role.")).not.toBeInTheDocument();
  });
});
