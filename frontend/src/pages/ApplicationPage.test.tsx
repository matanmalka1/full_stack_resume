import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ApplicationDetail, Operation, Settings } from "../api/contracts";
import { settingsQueryKey } from "../api/settings";
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
  default_ai_model: "gpt-5.6-terra",
  default_reasoning_effort: "medium",
  available_ai_models: [],

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
      <MemoryRouter initialEntries={["/applications/app-1/preparation"]}>
        <Routes>
          <Route element={<ApplicationPage />} path="/applications/:applicationId/preparation" />
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
  it("shows the complete hierarchy above CV preparation", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(jsonResponse(detail()))));

    renderPage();

    expect(await screen.findByRole("link", { name: "Acme – Backend Engineer" })).toHaveAttribute(
      "href",
      "/applications/app-1",
    );
    expect(screen.getByText("הכנת קורות החיים", { selector: "[aria-current='page']" })).toBeInTheDocument();
  });

  /* The Web automation opt-in, which moved here with the flow: queueing no longer
     navigates, so the Operation screen that used to run this chain is not on the path.
     Once per successful analyze, and not again after a remount - the session record is
     what makes a reload safe. */
  it("auto-generates the draft once per successful analyze when Settings ask for it", async () => {
    let projectionReads = 0;
    const analyzed = queued({
      status: "succeeded",
      is_terminal: true,
      phase: "completed",
      available_actions: [],
    });
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

    const first = renderPage({
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

    first.unmount();
    renderPage({ ...deterministicSettings, auto_generate_when_review_not_required: true });

    await waitFor(() => expect(fetchMock.mock.calls.filter((call) => call[1]?.method === "POST")).toHaveLength(1));
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

    const request = fetchMock.mock.calls.find((call) => call[0] === ANALYSES_PATH);
    expect(request?.[0]).toBe(ANALYSES_PATH);
    expect(request?.[1]).toEqual(expect.objectContaining({ method: "POST" }));
    /* The source is explicit: an analyze command that picked its own snapshot could
       classify something other than what the screen was showing. */
    expect(JSON.parse(String(request?.[1]?.body))).toEqual({ job_snapshot_id: "snap-1" });
    expect((request?.[1]?.headers as Headers).get("Idempotency-Key")).not.toBeNull();
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
});
