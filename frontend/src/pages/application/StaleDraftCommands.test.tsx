import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ApplicationDetail, Operation, Reason, Settings, WorkingDraft } from "../../api/contracts";
import { settingsQueryKey } from "../../api/settings";
import { ApplicationPage } from "../ApplicationPage";

/* §14: the two ways out of a stale draft, end to end through the screen.

   `applicationActionPlan.test.ts` covers what the pair is offered on. What is left here is
   what pressing them sends, and that is worth a DOM: both commands are addressed to an
   exact version of a record the engine may not regenerate, and the version reaches them
   from a read the plan does not perform. A payload assembled from the wrong read, or a
   Keep decision carried over from a cancelled dialog, is a lost historical copy - and
   neither is visible from the plan alone. */

const REPLACE_PATH = "/api/v1/applications/app-1/working-draft/replace";
const ARCHIVE_PATH = "/api/v1/working-drafts/draft-1/archive";
const DRAFT_PATH = "/api/v1/working-drafts/draft-1";

const staleReason: Reason = {
  code: "DRAFT_SOURCES_MOVED",
  message: "the analysis in force is newer than the draft",
  entity_references: {},
  allowed_resolution_actions: ["replace_working_draft", "archive_working_draft"],
};

const detail = (overrides: Partial<ApplicationDetail> = {}): ApplicationDetail =>
  ({
    recruitment_status: "saved",
    allowed_recruitment_transitions: [],
    recruitment_timeline: [],
    preparation_state: "ready_to_draft",
    working_draft_state: "editing",
    review_reasons: [],
    stale_reasons: [staleReason],
    warnings: [],
    active_job_snapshot_id: "snap-1",
    active_analysis_id: "analysis-1",
    active_selection_plan_id: "plan-1",
    active_working_draft_id: "draft-1",
    newer_draft_in_progress: false,
    available_actions: ["replace_working_draft", "archive_working_draft"],
    blocked_actions: [],
    recommended_action: null,
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
    ...overrides,
  }) as ApplicationDetail;

const draftRead = (editVersion = 7): WorkingDraft =>
  ({
    id: "draft-1",
    application_id: "app-1",
    edit_version: editVersion,
    job_analysis_id: "analysis-1",
    selection_plan_id: "plan-1",
    active: true,
    content_hash: "hash-1",
    created_at: "2026-08-24T07:00:00Z",
    updated_at: "2026-08-24T07:00:00Z",
    latest_validation_passed: null,
    latest_validation_run_id: null,
    outline: { sections: [] },
    parent_revision_id: null,
    source: {},
  }) as unknown as WorkingDraft;

/* Replacement queues `create_draft`, not an Operation type of its own: the work it runs is
   generating a draft over the active record, and `OperationType` has no
   `replace_working_draft` member. The fixture says so rather than inventing a type the
   engine never emits - which is what the panel reading it back proves below. */
const operation = (): Operation => ({
  id: "op-1",
  application_id: "app-1",
  operation_type: "create_draft",
  status: "queued",
  is_terminal: false,
  phase: "queued",
  message: "",
  created_at: "2026-08-24T07:00:00Z",
  outputs: [],
  available_actions: ["cancel"],
});

const json = (body: unknown, status = 200): Response =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

const accepted = (): Response =>
  new Response(JSON.stringify(operation()), {
    status: 202,
    headers: { "Content-Type": "application/json", Location: "/api/v1/operations/op-1" },
  });

const conflict = (): Response =>
  new Response(
    JSON.stringify({
      type: "about:blank#working_draft_version_conflict",
      title: "Precondition Failed",
      status: 412,
      code: "WORKING_DRAFT_VERSION_CONFLICT",
      detail: "הטיוטה עודכנה מאז שנקראה. יש לרענן ולנסות שוב.",
    }),
    { status: 412, headers: { "Content-Type": "application/problem+json" } },
  );

const settings: Settings = {
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

/* Routed by URL rather than by call order: the screen reads the projection and the draft
   independently, and a fixed queue of answers would tie the assertions to which of the two
   resolved first. */
const routedFetch = (answers: { archive?: Response; draft?: () => Response; replace?: Response }) =>
  vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);

    if (url.includes(REPLACE_PATH) && init?.method === "POST") {
      return Promise.resolve(answers.replace ?? accepted());
    }
    if (url.includes(ARCHIVE_PATH) && init?.method === "POST") {
      return Promise.resolve(answers.archive ?? json({ working_draft_id: "draft-1" }));
    }
    if (url.includes(DRAFT_PATH)) {
      return Promise.resolve(answers.draft === undefined ? json(draftRead()) : answers.draft());
    }
    return Promise.resolve(json(detail()));
  });

const renderPage = () => {
  const client = new QueryClient({
    defaultOptions: {
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
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
};

const enabledButton = async (name: string) => {
  const button = await screen.findByRole("button", { name });
  await waitFor(() => expect(button).toBeEnabled());
  return button;
};

const bodyOf = (fetchMock: ReturnType<typeof routedFetch>, path: string): unknown => {
  const call = fetchMock.mock.calls.find(([input, init]) => String(input).includes(path) && init?.method === "POST");
  return JSON.parse(String(call?.[1]?.body));
};

afterEach(() => {
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

describe("the stale-draft commands (§14)", () => {
  /* Neither command may be sent before the version read answers, because neither can be
     addressed without it. A button that is pressable a moment early would send a
     replacement guarded by nothing. */
  it("holds both commands until the draft version has arrived", async () => {
    let releaseDraft: (value: Response) => void = () => {};
    const pendingDraft = new Promise<Response>((resolve) => {
      releaseDraft = resolve;
    });
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) =>
        String(input).includes(DRAFT_PATH) ? pendingDraft : Promise.resolve(json(detail())),
      ),
    );

    renderPage();

    expect(await screen.findByRole("button", { name: "החלפת הטיוטה" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "העברת הטיוטה לארכיון" })).toBeDisabled();

    releaseDraft(json(draftRead()));

    await waitFor(() => expect(screen.getByRole("button", { name: "העברת הטיוטה לארכיון" })).toBeEnabled());
  });

  /* The Keep decision defaults to keeping. A replacement is the one command here that can
     destroy manual wording nothing regenerates, so the safe answer is the one already
     selected when the dialog opens. */
  it("replaces with the exact payload and keeps a historical copy by default", async () => {
    const fetchMock = routedFetch({});
    vi.stubGlobal("fetch", fetchMock);

    renderPage();

    fireEvent.click(await enabledButton("החלפת הטיוטה"));
    fireEvent.click(await screen.findByRole("checkbox", { name: /שמירת עותק היסטורי/ }));
    fireEvent.click(await screen.findByRole("checkbox", { name: /שמירת עותק היסטורי/ }));
    fireEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "החלפת הטיוטה" }));

    await waitFor(() => expect(bodyOf(fetchMock, REPLACE_PATH)).not.toBeUndefined());
    expect(bodyOf(fetchMock, REPLACE_PATH)).toEqual({
      expected_edit_version: 7,
      job_analysis_id: "analysis-1",
      keep_previous: true,
      selection_plan_id: "plan-1",
      working_draft_id: "draft-1",
    });
  });

  /* Opting out is honoured as given - the checkbox is a real decision, not a reassurance. */
  it("sends keep_previous false when the reader clears the box", async () => {
    const fetchMock = routedFetch({});
    vi.stubGlobal("fetch", fetchMock);

    renderPage();

    fireEvent.click(await enabledButton("החלפת הטיוטה"));
    fireEvent.click(await screen.findByRole("checkbox", { name: /שמירת עותק היסטורי/ }));
    fireEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "החלפת הטיוטה" }));

    await waitFor(() => expect(bodyOf(fetchMock, REPLACE_PATH)).not.toBeUndefined());
    expect((bodyOf(fetchMock, REPLACE_PATH) as { keep_previous: boolean }).keep_previous).toBe(false);
  });

  /* A cleared box on a cancelled dialog must not become the next replacement's answer.
     Carrying it over would discard a historical copy the reader never chose to discard on
     the replacement they did go through with. */
  it("restores the default keep decision after a cancelled dialog", async () => {
    vi.stubGlobal("fetch", routedFetch({}));

    renderPage();

    fireEvent.click(await enabledButton("החלפת הטיוטה"));
    fireEvent.click(await screen.findByRole("checkbox", { name: /שמירת עותק היסטורי/ }));
    expect(screen.getByRole("checkbox", { name: /שמירת עותק היסטורי/ })).not.toBeChecked();

    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "ביטול" }));
    fireEvent.click(await enabledButton("החלפת הטיוטה"));

    expect(await screen.findByRole("checkbox", { name: /שמירת עותק היסטורי/ })).toBeChecked();
  });

  /* Archiving is synchronous and carries one argument: the version it is setting aside. */
  it("archives the exact version it read", async () => {
    const fetchMock = routedFetch({});
    vi.stubGlobal("fetch", fetchMock);

    renderPage();

    fireEvent.click(await enabledButton("העברת הטיוטה לארכיון"));

    await waitFor(() => expect(bodyOf(fetchMock, ARCHIVE_PATH)).not.toBeUndefined());
    expect(bodyOf(fetchMock, ARCHIVE_PATH)).toEqual({ expected_edit_version: 7 });
  });

  /* Replacement queues durable work and answers 202, so it is followed in place like
     `generate`: the panel reports the Operation the press produced rather than appearing a
     poll later. */
  it("reports the Operation the replacement queued", async () => {
    vi.stubGlobal("fetch", routedFetch({}));

    renderPage();

    fireEvent.click(await enabledButton("החלפת הטיוטה"));
    fireEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "החלפת הטיוטה" }));

    /* The panel names the work the Operation reports, which for a replacement is the draft
       generation it queued. */
    expect(await screen.findByRole("heading", { name: "הרצת יצירת הטיוטה" })).toBeInTheDocument();
  });

  /* The guard doing its job is a thing the reader must see. A draft edited elsewhere since
     this screen read it is refused, and the refusal is reported rather than swallowed into
     a button that simply did nothing. */
  it("shows the version conflict instead of swallowing it", async () => {
    vi.stubGlobal("fetch", routedFetch({ archive: conflict() }));

    renderPage();

    fireEvent.click(await enabledButton("העברת הטיוטה לארכיון"));

    expect(await screen.findByText(/הטיוטה עודכנה מאז שנקראה/)).toBeInTheDocument();
  });

  /* And the read that fails before either command can be addressed. Without this the two
     buttons sit disabled beside an alert about the draft with nothing saying why. */
  it("explains a failed version read rather than leaving the commands silently disabled", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) =>
        String(input).includes(DRAFT_PATH)
          ? Promise.resolve(
              new Response(
                JSON.stringify({
                  type: "about:blank#working_draft_read_failed",
                  title: "Server Error",
                  status: 500,
                  code: "WORKING_DRAFT_READ_FAILED",
                  detail: "לא ניתן לקרוא את גרסת הטיוטה.",
                }),
                { status: 500, headers: { "Content-Type": "application/problem+json" } },
              ),
            )
          : Promise.resolve(json(detail())),
      ),
    );

    renderPage();

    expect(await screen.findByText(/לא ניתן לקרוא את גרסת הטיוטה/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "החלפת הטיוטה" })).toBeDisabled();
  });
});
