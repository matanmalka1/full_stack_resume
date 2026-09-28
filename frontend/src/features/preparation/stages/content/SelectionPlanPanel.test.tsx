import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ApplicationDetail, Operation, SelectionPlanDetail, Settings } from "@/api/contracts";
import { operationQueryKey } from "@/api/operations";
import { settingsQueryKey } from "@/api/settings";
import { workflowActionPlan } from "../../model/workflowActionPlan";
import { SelectionPlanPanel } from "./SelectionPlanPanel";

const detail = (planId: string | null): ApplicationDetail => ({
  recruitment_status: "saved",
  preparation_state: planId === null ? "needs_review" : "ready_to_draft",
  working_draft_state: "none",
  review_reasons:
    planId === null
      ? [
          {
            code: "FACT_SELECTION_UNRESOLVED",
            message: "missing",
            entity_references: { job_analysis_id: "analysis-1" },
            allowed_resolution_actions: ["create_selection_plan"],
          },
        ]
      : [],
  stale_reasons: [],
  warnings: [],
  active_job_snapshot_id: "snapshot-1",
  active_analysis_id: "analysis-1",
  active_selection_plan_id: planId,
  newer_draft_in_progress: false,
  available_actions: ["analyze", "create_selection_plan", ...(planId === null ? [] : ["create_draft"])],
  blocked_actions: [],
  recommended_action: planId === null ? "create_selection_plan" : "create_draft",
  allowed_recruitment_transitions: [],
  recruitment_timeline: [],
  application: {
    id: "app-1",
    company: "Acme",
    target_role: "Engineer",
    current_status: "saved",
    notes: "",
    created_at: "2026-09-06T10:00:00Z",
    updated_at: "2026-09-06T10:00:00Z",
  },
  latest_snapshot: {
    id: "snapshot-1",
    application_id: "app-1",
    version_number: 1,
    job_text: "Engineer",
    captured_at: "2026-09-06T10:00:00Z",
    source_metadata: {},
    source_hash: "snapshot-hash",
  },
});

const plan: SelectionPlanDetail = {
  id: "plan-1",
  application_id: "app-1",
  job_analysis_id: "analysis-1",
  version_number: 1,
  plan: {},
  candidate_context_version: "candidate-v1",
  candidate_context_hash: "candidate-hash",
  profile_version: "profile-hash",
  selection_policy_version: "policy-hash",
  track_emphasis_dependencies: {},
  created_at: "2026-09-06T10:00:00Z",
  language: "he",
  facts_version: "facts-hash",
  pinned_fact_ids: [],
  excluded_fact_ids: [],
  proposed_by: null,
  proposal_rationale: null,
  candidates: [
    {
      fact_id: "fact.selected",
      text: "עובדה שנבחרה",
      section: "ניסיון",
      outcome: "selected",
      reason: null,
      user_selectable: true,
    },
    {
      fact_id: "fact.omitted",
      text: "עובדה שהושמטה",
      section: "מיומנויות",
      outcome: "omitted",
      reason: "below_section_budget",
      user_selectable: true,
    },
  ],
};

const settings = (ai: boolean): Settings =>
  ({
    edit_version: 0,
    auto_generate_when_review_not_required: false,
    ai_enabled: ai,
    ai_enabled_override: null,
    default_execution_mode: "deterministic",
    default_ai_model: "gpt-5.6-terra",
    default_reasoning_effort: "medium",
    available_ai_models: [],
    provider_configured: ai,
    ui_density: "comfortable",
    ui_text_size: "normal",
    ui_theme: "system",
    updated_at: null,
  }) as Settings;

const operation: Operation = {
  id: "operation-1",
  application_id: "app-1",
  operation_type: "propose_selection",
  status: "queued",
  is_terminal: false,
  phase: "queued",
  message: "",
  created_at: "2026-09-06T10:00:00Z",
  outputs: [],
  available_actions: ["cancel"],
};

const response = (body: unknown, status: number, location?: string): Response =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...(location === undefined ? {} : { Location: location }) },
  });

/* The panel is handed the offer rather than re-deriving it, so the test derives it the
   same way the preparation view does - from the projection - instead of inventing one the
   workflow never made. */
const panelFor = (client: QueryClient, value: ApplicationDetail, onQueued: (id: string) => void) => {
  const action = workflowActionPlan(value).createSelectionPlan;
  if (action === null) {
    throw new Error("create_selection_plan was not offered for this projection");
  }
  return (
    <QueryClientProvider client={client}>
      <SelectionPlanPanel
        action={action}
        detail={value}
        onQueued={onQueued}
        operationLive={false}
        requirements={[
          {
            requirementId: "requirement-1",
            text: "Priority ERP",
            importance: "mandatory",
            coverage: "matched",
            shortfallSeverity: null,
            shortfallReason: null,
            supportingFactIds: ["fact.omitted"],
            boundaryFactIds: [],
          },
        ]}
      />
    </QueryClientProvider>
  );
};

const renderPanel = (value: ApplicationDetail, ai: boolean, onQueued = vi.fn()) => {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, refetchInterval: false }, mutations: { retry: false } },
  });
  client.setQueryData(settingsQueryKey, { settings: settings(ai), etag: '"settings-1"' });
  const rendered = render(panelFor(client, value, onQueued));
  return {
    client,
    onQueued,
    rerender: (next: ApplicationDetail) => rendered.rerender(panelFor(client, next, onQueued)),
  };
};

afterEach(() => vi.unstubAllGlobals());

describe("SelectionPlanPanel", () => {
  it("recovers a missing plan through the deterministic command", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        response({ application_id: "app-1", job_analysis_id: "analysis-1", selection_plan_id: "plan-2", plan }, 201),
      );
    vi.stubGlobal("fetch", fetchMock);
    renderPanel(detail(null), false);

    fireEvent.click(screen.getByRole("button", { name: "יצירת בחירת ברירת המחדל" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))).toEqual(
      expect.objectContaining({
        application_id: "app-1",
        mode: "deterministic",
        pinned_fact_ids: [],
        excluded_fact_ids: [],
        expected_selection_plan_id: null,
      }),
    );
  });

  it("queues explicit AI selection even when deterministic is the default", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response(operation, 202, "/api/v1/operations/operation-1"));
    vi.stubGlobal("fetch", fetchMock);
    const { onQueued } = renderPanel(detail(null), true);

    fireEvent.click(screen.getByRole("button", { name: "הצעת בחירה באמצעות AI" }));

    await waitFor(() => expect(onQueued).toHaveBeenCalledWith("operation-1"));
    expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))).toEqual(
      expect.objectContaining({ mode: "ai", pinned_fact_ids: [], excluded_fact_ids: [] }),
    );
    expect((fetchMock.mock.calls[0]?.[1]?.headers as Headers | undefined)?.get("Idempotency-Key")).not.toBeNull();
  });

  it("shows an AI plan's own rationale and labels only the marks it still holds", async () => {
    const aiPlan: SelectionPlanDetail = {
      ...plan,
      pinned_fact_ids: ["fact.omitted"],
      excluded_fact_ids: ["fact.selected"],
      proposed_by: "ai",
      proposal_rationale: "Pinned the skills fact because the posting asks for it.",
    };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(aiPlan, 200)));
    renderPanel(detail("plan-1"), false);

    expect(await screen.findByText("Pinned the skills fact because the posting asks for it.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /^מיומנויות/ }));
    fireEvent.click(screen.getByRole("button", { name: /^ניסיון/ }));
    const pinnedRow = screen.getByText("עובדה שהושמטה").closest("li");
    const excludedRow = screen.getByText("עובדה שנבחרה").closest("li");
    if (pinnedRow === null || excludedRow === null) throw new Error("candidate rows were not rendered");
    expect(within(pinnedRow).getByText(/מהצעת AI/)).toBeInTheDocument();
    expect(within(excludedRow).getByText(/מהצעת AI/)).toBeInTheDocument();

    fireEvent.click(within(pinnedRow).getByRole("radio", { name: "אוטומטי" }));
    expect(within(pinnedRow).queryByText(/מהצעת AI/)).toBeNull();
  });

  it("claims no AI provenance for a plan that did not record one", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({ ...plan, pinned_fact_ids: ["fact.omitted"] }, 200)));
    renderPanel(detail("plan-1"), false);

    fireEvent.click(await screen.findByRole("button", { name: /^מיומנויות/ }));
    expect(screen.queryByText("נימוק הצעת ה־AI")).toBeNull();
    expect(screen.queryByText(/מהצעת AI/)).toBeNull();
  });

  it("submits absolute manual choices against the plan and versions shown", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) =>
      init?.method === "POST"
        ? Promise.resolve(
            response(
              { application_id: "app-1", job_analysis_id: "analysis-1", selection_plan_id: "plan-2", plan },
              201,
            ),
          )
        : Promise.resolve(response(plan, 200)),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderPanel(detail("plan-1"), false);

    const sectionToggle = await screen.findByRole("button", { name: /^מיומנויות/ });
    expect(sectionToggle).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(sectionToggle);
    expect(sectionToggle).toHaveAttribute("aria-expanded", "true");

    const row = screen.getByText("עובדה שהושמטה").closest("li");
    if (row === null) throw new Error("candidate row was not rendered");
    expect(within(row).getByRole("radio", { name: "אוטומטי" })).toBeChecked();
    fireEvent.click(within(row).getByRole("radio", { name: "הכללה" }));
    expect(within(row).getByText(/שינוי שטרם נשמר/)).toBeInTheDocument();
    const saveButton = screen.getByRole("button", { name: "שמירת בחירת העובדות" });
    expect(saveButton.closest(".sticky")).toBeNull();
    fireEvent.click(saveButton);

    await waitFor(() => expect(fetchMock.mock.calls.some((call) => call[1]?.method === "POST")).toBe(true));
    const post = fetchMock.mock.calls.find((call) => call[1]?.method === "POST");
    expect(JSON.parse(String(post?.[1]?.body))).toEqual(
      expect.objectContaining({
        pinned_fact_ids: ["fact.omitted"],
        excluded_fact_ids: [],
        expected_selection_plan_id: "plan-1",
        expected_candidate_context_hash: "candidate-hash",
        expected_facts_version: "facts-hash",
        expected_profile_version: "profile-hash",
        expected_selection_policy_version: "policy-hash",
      }),
    );
  });
  it("reports exactly which facts an AI proposal added and removed, and why", async () => {
    const proposed: SelectionPlanDetail = {
      ...plan,
      id: "plan-2",
      version_number: 2,
      pinned_fact_ids: ["fact.omitted"],
      excluded_fact_ids: ["fact.selected"],
      plan: {
        candidates: [
          { fact_id: "fact.omitted", requirement_rank: 2, profile_score: 2, emphasis_score: 1, keyword_hits: 1 },
        ],
      },
      candidates: [
        { ...plan.candidates[0]!, outcome: "omitted", reason: "excluded_by_user" },
        { ...plan.candidates[1]!, outcome: "pinned", reason: null },
      ],
    };
    const finished = {
      ...operation,
      status: "succeeded",
      is_terminal: true,
      available_actions: [],
      outputs: [{ output_type: "selection_plan", output_id: "plan-2", active: true }],
    } as Operation;
    let operationState: Operation = operation;
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (init?.method === "POST") {
        return Promise.resolve(response(operation, 202, "/api/v1/operations/operation-1"));
      }
      if (url.includes("/operations/")) {
        return Promise.resolve(response(operationState, 200));
      }
      return Promise.resolve(response(url.endsWith("plan-2") ? proposed : plan, 200));
    });
    vi.stubGlobal("fetch", fetchMock);
    const { client, onQueued, rerender } = renderPanel(detail("plan-1"), true);

    await screen.findByRole("button", { name: /^ניסיון/ });
    fireEvent.click(screen.getByRole("button", { name: "הצעת בחירה באמצעות AI" }));
    await waitFor(() => expect(onQueued).toHaveBeenCalledWith("operation-1"));
    expect(await screen.findByText("ה־AI בוחן את העובדות מול דרישות המשרה…")).toBeInTheDocument();

    operationState = finished;
    client.setQueryData(operationQueryKey("operation-1"), finished);
    rerender(detail("plan-2"));

    expect(await screen.findByText("ההצעה שינתה 2 עובדות בקורות החיים:")).toBeInTheDocument();
    const added = screen.getByRole("heading", { name: "נוספו לקורות החיים (1)" }).parentElement;
    if (added === null) throw new Error("the added list was not rendered");
    expect(within(added).getByText("עובדה שהושמטה")).toBeInTheDocument();
    expect(within(added).getByText(/ראיה לדרישת חובה/)).toBeInTheDocument();
    expect(within(added).getByText("Priority ERP")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "הוסרו מקורות החיים (1)" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /^מיומנויות/ }));
    expect(screen.getByText("נוספה בהצעת ה־AI")).toBeInTheDocument();
  });
});
