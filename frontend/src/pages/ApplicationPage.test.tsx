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
  /* The auto-draft dispatch record is session-scoped and survives a remount by design,
     which is the point of the guard - so it is cleared between tests rather than leaking
     an "already continued" answer into the next one. */
  sessionStorage.clear();
});

describe("ApplicationPage", () => {
  /* The Web automation opt-in, which moved here with the flow: queueing no longer
     navigates, so the Operation screen that used to run this chain is not on the path.
     Once per successful analyze, and not again after a remount - the session record is
     what makes a reload safe. */
  it("auto-generates the draft once per successful analyze when Settings ask for it", async () => {
    let projectionReads = 0;
    const analyzed = queued({ status: "succeeded", is_terminal: true, phase: "completed", available_actions: [] });
    const drafting = queued({ id: "op-draft", operation_type: "create_draft" });
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (init?.method === "POST") {
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
      /* The projection reports the analyze while it runs and lets go once it finishes -
         which is also what the continuation guard waits for, since it refuses to queue a
         draft while other work is live. The screen keeps watching the succeeded Operation
         by id, which is what the chain reads. */
      projectionReads += 1;
      return Promise.resolve(
        jsonResponse(
          analyzed_detail({
            active_operation: projectionReads === 1 ? queued({ status: "running" }) : null,
            active_selection_plan_id: "plan-1",
          }),
        ),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    const first = renderPage({ ...deterministicSettings, auto_generate_when_review_not_required: true });

    await waitFor(() =>
      expect(sessionStorage.getItem("stage-e:auto-draft:op-1")).toBe("accepted"),
    );
    const posts = fetchMock.mock.calls.filter((call) => call[1]?.method === "POST");
    expect(posts).toHaveLength(1);
    expect(JSON.parse(String(posts[0]?.[1]?.body))).toEqual({
      job_analysis_id: "analysis-1",
      selection_plan_id: "plan-1",
    });

    first.unmount();
    renderPage({ ...deterministicSettings, auto_generate_when_review_not_required: true });

    await waitFor(() =>
      expect(fetchMock.mock.calls.filter((call) => call[1]?.method === "POST")).toHaveLength(1),
    );
  });
  /* Queueing work no longer navigates: the projection carries the Operation and this
     screen reports it in place. */
  it("watches a running operation without leaving the screen", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          detail({
            active_operation: queued({ status: "running", phase: "executing" }),
          }),
        ),
      ),
    );

    renderPage();

    expect(await screen.findByRole("heading", { name: "ניתוח המשרה" })).toBeInTheDocument();
    expect(screen.getByText("מתבצעת")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "מעבר למצב הפעולה" })).not.toBeInTheDocument();
  });

  /* `active_operation` is only ever queued or running: it goes null the moment work
     finishes. Read straight, the panel would vanish exactly when the Operation had
     something to say, so a failed run would leave no trace on the screen that started it.
     The watch is held by id across that transition. */
  it("keeps reporting an operation after the projection lets go of it", async () => {
    const failed = queued({
      status: "failed",
      is_terminal: true,
      phase: "completed",
      failure_code: "PROVIDER_UNAVAILABLE",
      safe_failure_detail: "The provider did not answer.",
      available_actions: ["retry"],
    });

    /* The projection reports the Operation while it runs and then lets go of it -
       `active_operation` is only ever queued or running. The watch has to survive that
       transition, which is the whole point of holding the id. */
    let projectionReads = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/operations/")) {
          return Promise.resolve(jsonResponse(failed));
        }
        projectionReads += 1;
        return Promise.resolve(
          jsonResponse(
            detail({
              active_operation: projectionReads === 1 ? queued({ status: "running" }) : null,
            }),
          ),
        );
      }),
    );

    renderPage();

    expect(
      await screen.findByText("ספק הבינה המלאכותית אינו זמין"),
    ).toBeInTheDocument();
    expect(screen.getByText("The provider did not answer.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "ניסיון חוזר" })).toBeInTheDocument();
  });
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

  it("renders recruitment choices and correction history from the backend projection", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          detail({
            allowed_recruitment_transitions: ["withdrawn", "closed"],
            recruitment_timeline: [
              {
                id: "event-1",
                item_type: "status_transition",
                occurred_at: "2026-08-30T09:00:00Z",
                actor_type: "user",
                client: "web",
                from_status: "saved",
                to_status: "withdrawn",
                reason: "role changed",
                metadata: {},
              },
              {
                id: "event-2",
                item_type: "status_correction",
                occurred_at: "2026-08-30T10:00:00Z",
                actor_type: "user",
                client: "web",
                from_status: "withdrawn",
                to_status: "closed",
                corrects_event_id: "event-1",
                reason: "wrong application",
                metadata: {},
              },
            ],
          }),
        ),
      ),
    );

    renderPage();

    expect(await screen.findByRole("heading", { name: "מעקב גיוס" })).toBeInTheDocument();
    expect(screen.getAllByRole("option", { name: "בוטל" }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("option", { name: "סגור" }).length).toBeGreaterThan(0);
    expect(screen.getByText(/תוקן ל־סגור/)).toBeInTheDocument();
    expect(screen.getByText("wrong application")).toBeInTheDocument();
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
    expect(
      await screen.findByRole("heading", { name: "ניתוח המשרה", level: 2 }),
    ).toBeInTheDocument();

    const request = fetchMock.mock.calls.find((call) => call[0] === ANALYSES_PATH);
    expect(request?.[0]).toBe(ANALYSES_PATH);
    expect(request?.[1]).toEqual(expect.objectContaining({ method: "POST" }));
    /* The source is explicit: an analyze command that picked its own snapshot could
       classify something other than what the screen was showing. */
    expect(JSON.parse(String(request?.[1]?.body))).toEqual({ job_snapshot_id: "snap-1" });
    expect((request?.[1]?.headers as Headers).get("Idempotency-Key")).not.toBeNull();
  });

  it("uses the effective manual AI mode without changing the deterministic default", async () => {
    const aiSettings: Settings = {
      edit_version: 1,
      auto_generate_when_review_not_required: false,
      ai_enabled: true,
      ai_enabled_override: true,
      default_execution_mode: "ai",
      provider_configured: true,
      ui_density: "comfortable",
      ui_text_size: "normal",
      updated_at: null,
    };
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (init?.method === "POST") {
        return Promise.resolve(acceptedResponse(queued()));
      }
      if (url.includes("/operations/")) {
        return Promise.resolve(jsonResponse(queued()));
      }
      /* Settings is seeded into the cache by `renderPage`, but the screen also subscribes
         to it: answering that read with a projection body would let the effective AI mode
         resolve to the deterministic default and lose the `provider` under test. */
      if (url.includes("/settings")) {
        return Promise.resolve(jsonResponse(aiSettings));
      }
      return Promise.resolve(jsonResponse(detail()));
    });
    vi.stubGlobal("fetch", fetchMock);
    renderPage(aiSettings);

    await clickEnabledButton("ניתוח המשרה");

    const analyzeCall = fetchMock.mock.calls.find((call) => call[0] === ANALYSES_PATH);
    expect(JSON.parse(String(analyzeCall?.[1]?.body))).toEqual({
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
    /* A refused command queues nothing, so no Operation is reported. */
    expect(screen.queryByRole("region", { name: /ניתוח המשרה/ })).not.toBeInTheDocument();
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
    const drafting = queued({ id: "op-2", operation_type: "create_draft" });
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === "POST") {
        return Promise.resolve(acceptedResponse(drafting));
      }
      if (String(input).includes("/operations/")) {
        return Promise.resolve(jsonResponse(drafting));
      }
      return Promise.resolve(
        jsonResponse(
          detail({
            preparation_state: "ready_to_draft",
            active_analysis_id: "analysis-1",
            active_selection_plan_id: "plan-1",
            available_actions: ["analyze", "create_draft"],
            recommended_action: "create_draft",
          }),
        ),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    renderPage();
    await clickEnabledButton("יצירת טיוטה");

    expect(await screen.findByRole("heading", { name: "יצירת הטיוטה", level: 2 })).toBeInTheDocument();

    const request = fetchMock.mock.calls.find((call) => call[0] === GENERATE_PATH);
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
    /* The control that resolves it is the panel on this same screen, so the callout
       states the requirement and offers no link away from the form that settles it. */
    expect(screen.queryByRole("link", { name: "החלת החלטות הסקירה" })).not.toBeInTheDocument();
    expect(screen.queryByText(/מגיע בפרוסה הבאה/)).not.toBeInTheDocument();
    expect(screen.getByRole("region", { name: "ההחלטה שנדרשת" })).toBeInTheDocument();
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

  /* The Operation the projection reports as already running is watched in place, which
     "watches a running operation without leaving the screen" above covers. What remains
     worth asserting here is the way out for the record itself: the panel still links to
     the Operation's own route, which is where a bookmark or a reload lands. */
  it("still offers the Operation's own route from the panel", async () => {
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

    expect(await screen.findByRole("link", { name: "פרטי הפעולה המלאים" })).toHaveAttribute(
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
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(analyzed_detail())));

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
    /* The confidence reads as a Hebrew-side percentage, not an isolated LTR run. */
    expect(screen.getByText("רמת הביטחון בסיווג: 82%")).toBeInTheDocument();
  });

  /* The projection's review reason says a decision is needed; the panel says what about
     the analysis made it necessary, which is what a person needs in order to decide. */
  it("says what about the classification requires a decision", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(analyzed_detail())));

    renderPage();

    expect(await screen.findByText("מה מחייב החלטה")).toBeInTheDocument();
    expect(screen.getByText("רמת הביטחון בסיווג נמוכה מהסף.")).toBeInTheDocument();
  });

  /* A blocked action naming a review reason gets a sentence, not the raw code it used to
     print once per action. */
  it("explains a review-reason blocker in words", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          analyzed_detail({
            preparation_state: "needs_review",
            available_actions: ["apply_analysis_decisions"],
            recommended_action: "apply_analysis_decisions",
            blocked_actions: [
              { action: "draft", reasons: ["MATERIAL_CLASSIFICATION_AMBIGUITY"] },
            ],
          }),
        ),
      ),
    );

    renderPage();

    expect(
      await screen.findByText("סיווג המשרה ממתין להחלטה מפורשת."),
    ).toBeInTheDocument();
    expect(screen.queryByText("MATERIAL_CLASSIFICATION_AMBIGUITY")).not.toBeInTheDocument();
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
      vi.fn().mockResolvedValue(jsonResponse(analyzed_detail({ active_analysis_id: "analysis-9" }))),
    );

    renderPage();

    expect(
      await screen.findByText("הניתוח שעל המסך אינו הניתוח הפעיל"),
    ).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "ניתוח המשרה" })).not.toBeInTheDocument();
    expect(screen.queryByText("The posting is a backend role.")).not.toBeInTheDocument();
  });
});
