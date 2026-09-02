import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ApplicationDetail, WorkingDraft, WorkingDraftFacts } from "../../api/contracts";
import { settingsQueryKey } from "../../api/settings";
import { DraftEditorPage } from "./DraftEditorPage";

const DETAIL_PATH = "/api/v1/applications/app-1";
const DRAFT_PATH = "/api/v1/working-drafts/wd-1";

const detail = (overrides: Partial<ApplicationDetail> = {}): ApplicationDetail =>
  ({
    recruitment_status: "saved",
    allowed_recruitment_transitions: ["withdrawn", "closed"],
    recruitment_timeline: [],
    preparation_state: "draft_in_progress",
    working_draft_state: "editing",
    review_reasons: [],
    stale_reasons: [],
    warnings: [],
    active_job_snapshot_id: "snap-1",
    active_analysis_id: "an-1",
    active_selection_plan_id: "sp-1",
    active_working_draft_id: "wd-1",
    newer_draft_in_progress: false,
    available_actions: ["update_working_draft"],
    blocked_actions: [],
    recommended_action: "validate",
    application: {
      id: "app-1",
      company: "Acme",
      target_role: "Account Manager",
      current_status: "saved",
      notes: "",
      source: "manual",
      created_at: "2026-08-24T07:00:00Z",
      updated_at: "2026-08-24T07:00:00Z",
    },
    ...overrides,
  }) as unknown as ApplicationDetail;

const draft = (overrides: Partial<WorkingDraft["outline"]> = {}): WorkingDraft =>
  ({
    id: "wd-1",
    application_id: "app-1",
    job_analysis_id: "an-1",
    selection_plan_id: "sp-1",
    source: {},
    outline: {
      headline: {
        claim_id: "c-headline",
        style: "headline",
        text: "Account Manager",
        claim_type: "headline",
        fact_ids: [],
        pending_reason: null,
      },
      contacts: [
        {
          claim_id: "c-mail",
          style: "contact",
          text: "matan@example.com",
          claim_type: "canonical",
          fact_ids: ["f-mail"],
          pending_reason: null,
        },
      ],
      sections: [
        {
          name: "Core Skills",
          claims: [
            {
              claim_id: "c-1",
              style: "bullet",
              text: "Owned the CRM migration.",
              claim_type: "canonical",
              fact_ids: ["f-1"],
              pending_reason: null,
            },
          ],
        },
      ],
      ...overrides,
    },
    edit_version: 4,
    content_hash: "hash-4",
    active: true,
    created_at: "2026-08-24T07:00:00Z",
    updated_at: "2026-08-24T07:10:00Z",
  }) as unknown as WorkingDraft;

const facts = (): WorkingDraftFacts => ({
  working_draft_id: "wd-1",
  application_id: "app-1",
  selection_plan_id: "sp-1",
  language: "en",
  facts: [
    {
      fact_id: "f-1",
      text: "Owned the CRM migration end to end.",
      linked_claim_ids: ["c-1"],
      section: "Core Skills",
      outcome: "selected",
      reason: null,
    },
    {
      fact_id: "f-mail",
      text: "matan@example.com",
      linked_claim_ids: ["c-mail"],
      section: null,
      outcome: null,
      reason: null,
    },
  ],
});

const jsonResponse = (body: unknown, status = 200): Response =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ETag: '"4-hash-4"' },
  });

const conflictResponse = (): Response =>
  new Response(
    JSON.stringify({
      type: "about:blank#state_conflict",
      title: "Conflict",
      status: 409,
      code: "STATE_CONFLICT",
      detail: "working draft wd-1 has content hash hash-9, not hash-4",
    }),
    { status: 409, headers: { "Content-Type": "application/problem+json" } },
  );

const updateResponse = (editVersion: number): Response =>
  new Response(
    JSON.stringify({
      application_id: "app-1",
      working_draft_id: "wd-1",
      edit_version: editVersion,
      content_hash: `hash-${editVersion}`,
      selection_plan_id: "sp-1",
      pending_claim_ids: [],
    }),
    {
      status: 200,
      headers: { "Content-Type": "application/json", ETag: `"${editVersion}-hash-${editVersion}"` },
    },
  );

/* One route per read, so a test states which answer it is giving rather than depending on
   the order the screen happens to request them in. */
const stubReads = (
  answers: Partial<Record<"detail" | "draft" | "facts" | "selectionChange" | "regenerate", () => Response>>,
): ReturnType<typeof vi.fn> => {
  const fetchMock = vi.fn((input: unknown) => {
    const url = String(input);

    if (url.includes("/regenerate-")) {
      return Promise.resolve(answers.regenerate?.() ?? jsonResponse({}, 500));
    }
    if (url.endsWith("/apply-selection-change")) {
      return Promise.resolve(
        answers.selectionChange?.() ??
          jsonResponse({
            application_id: "app-1",
            working_draft_id: "wd-1",
            edit_version: 5,
            content_hash: "hash-5",
            selection_plan_id: "sp-2",
            plan: {},
          }),
      );
    }
    if (url.startsWith(`${DRAFT_PATH}/facts`)) {
      return Promise.resolve(answers.facts?.() ?? jsonResponse(facts()));
    }
    if (url === "/api/v1/facts" || url === "/api/v1/facts/history") {
      return Promise.resolve(jsonResponse(url.endsWith("/history") ? { events: [] } : { items: [] }));
    }
    if (url.startsWith(DRAFT_PATH)) {
      return Promise.resolve(answers.draft?.() ?? jsonResponse(draft()));
    }
    return Promise.resolve(answers.detail?.() ?? jsonResponse(detail()));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
};

const renderPage = (aiEnabled = true) => {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false, refetchInterval: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });
  client.setQueryData(settingsQueryKey, {
    settings: {
      edit_version: 0,
      auto_generate_when_review_not_required: false,
      ai_enabled: aiEnabled,
      ai_enabled_override: aiEnabled,
      default_execution_mode: "deterministic",

      provider_configured: aiEnabled,
      ui_density: "comfortable",
      ui_text_size: "normal",
      updated_at: null,
    },
    etag: '"settings-0"',
  });

  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/applications/app-1/draft"]}>
        <Routes>
          <Route element={<DraftEditorPage />} path="/applications/:applicationId/draft" />
          <Route element={<h1>הכנת קורות החיים</h1>} path="/applications/:applicationId/preparation" />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("DraftEditorPage", () => {
  it("gates AI regeneration through effective Settings without offering a silent fallback", async () => {
    stubReads({});

    renderPage(false);

    expect(await screen.findByText("יצירה מחדש באמצעות AI אינה זמינה")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "מעבר להגדרות" })).toHaveAttribute("href", "/settings");
    expect(screen.getByRole("button", { name: "יצירה מחדש של הפרק" })).toBeDisabled();
  });

  it("renders the outline the projection named, with each claim's status in Hebrew", async () => {
    stubReads({});

    renderPage();

    expect(await screen.findByText("Owned the CRM migration.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 3, name: "Core Skills" })).toBeInTheDocument();
    expect(screen.getAllByText("מבוסס עובדה").length).toBeGreaterThan(0);
    expect(screen.getByText("Account Manager")).toBeInTheDocument();
  });

  it("names the facts behind a claim by their text, never by their identifier", async () => {
    stubReads({});

    renderPage();

    expect(await screen.findByText("Owned the CRM migration end to end.")).toBeInTheDocument();
    expect(screen.queryByText(/f-1/)).not.toBeInTheDocument();
  });

  it("marks free text nothing authorized as a blocker and keeps the text", async () => {
    stubReads({
      draft: () =>
        jsonResponse(
          draft({
            sections: [
              {
                name: "Core Skills",
                claims: [
                  {
                    claim_id: "c-1",
                    style: "bullet",
                    text: "Delivered 30% growth.",
                    claim_type: "pending",
                    fact_ids: [],
                    pending_reason: "no canonical fact authorizes this wording",
                  },
                ],
              },
            ],
          }),
        ),
    });

    renderPage();

    expect(await screen.findAllByText("Delivered 30% growth.")).toHaveLength(2);
    expect(screen.getByText("ללא ביסוס")).toBeInTheDocument();
    expect(screen.getByText("no canonical fact authorizes this wording")).toBeInTheDocument();
    expect(screen.getByText("הפיכת הטקסט לעובדה מאושרת")).toBeInTheDocument();
  });

  it("keeps fact creation and lifecycle management inside the draft context", async () => {
    stubReads({});

    renderPage();

    expect(await screen.findByRole("heading", { name: "מחזור חיי העובדות" })).toBeInTheDocument();
    expect(screen.getByText(/יצירה וקידום כאן משנים את מקור הידע הקבוע/)).toBeInTheDocument();
    expect(screen.getByText("יצירת עובדה ממתינה חדשה")).toBeInTheDocument();
  });

  it("refreshes the conflict comparison and reapplies against the current ETag", async () => {
    let draftReads = 0;
    let patchWrites = 0;
    const fetchMock = vi.fn((input: unknown, init?: RequestInit) => {
      const url = String(input);
      if (url.startsWith(`${DRAFT_PATH}/facts`)) {
        return Promise.resolve(jsonResponse(facts()));
      }
      if (url === "/api/v1/facts" || url === "/api/v1/facts/history") {
        return Promise.resolve(jsonResponse(url.endsWith("/history") ? { events: [] } : { items: [] }));
      }
      if (url === DRAFT_PATH && init?.method === "PATCH") {
        patchWrites += 1;
        return Promise.resolve(patchWrites === 1 ? conflictResponse() : updateResponse(10));
      }
      if (url === DRAFT_PATH) {
        draftReads += 1;
        const current =
          draftReads === 1
            ? draft()
            : draft({
                sections: [
                  {
                    name: "Core Skills",
                    claims: [
                      {
                        ...draft().outline.sections[0]!.claims[0]!,
                        text: "Saved in the other tab.",
                      },
                    ],
                  },
                ],
              });
        return Promise.resolve(
          new Response(JSON.stringify(current), {
            status: 200,
            headers: {
              "Content-Type": "application/json",
              ETag: draftReads === 1 ? '"4-hash-4"' : '"9-hash-9"',
            },
          }),
        );
      }
      return Promise.resolve(jsonResponse(detail()));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderPage();
    const editor = await screen.findByDisplayValue("Owned the CRM migration.");
    fireEvent.change(editor, { target: { value: "My local wording." } });
    fireEvent.blur(editor);

    const dialog = await screen.findByRole("dialog", {
      name: "הטיוטה השתנתה בזמן העריכה",
    });
    expect(within(dialog).getByText("My local wording.")).toBeInTheDocument();
    expect(within(dialog).getByText("Saved in the other tab.")).toBeInTheDocument();

    fireEvent.click(within(dialog).getByRole("button", { name: "החלת הטקסט שלי על הגרסה הנוכחית" }));
    await waitFor(() => expect(dialog).not.toHaveAttribute("open"));

    const patchCalls = fetchMock.mock.calls.filter(
      (call) => String(call[0]) === DRAFT_PATH && (call[1] as RequestInit)?.method === "PATCH",
    );
    expect(patchCalls).toHaveLength(2);
    expect(((patchCalls[1]![1] as RequestInit).headers as Headers).get("If-Match")).toBe('"9-hash-9"');
  });

  it("presents the projection's own review reason rather than inventing an approval rule", async () => {
    stubReads({
      detail: () =>
        jsonResponse(
          detail({
            review_reasons: [
              {
                code: "PENDING_FACT_REQUIRES_RESOLUTION",
                message: "A claim in the active draft depends on a pending fact.",
                entity_references: {},
                allowed_resolution_actions: ["confirm_and_use_fact", "update_working_draft"],
              },
            ],
          } as Partial<ApplicationDetail>),
        ),
    });

    renderPage();

    /* The projection's reason reaches the screen as its own code, titled from the code
       rather than by the backend's sentence: the message is written to be complete, and
       several of them stacked was what made this screen open with a wall of prose. What
       the test guards is unchanged - the blocker shown is the projection's, not a rule
       this screen invented. */
    expect(await screen.findByText("טענה בלי עובדה מאושרת")).toBeInTheDocument();
    expect(screen.queryByText("A claim in the active draft depends on a pending fact.")).toBeNull();
  });

  it("says plainly when there is no active draft instead of reading one that does not exist", async () => {
    const fetchMock = stubReads({
      detail: () => jsonResponse(detail({ active_working_draft_id: null, working_draft_state: "none" })),
    });

    renderPage();

    expect(await screen.findByText("אין כרגע טיוטה פעילה למועמדות הזו")).toBeInTheDocument();
    expect(fetchMock.mock.calls.every((call) => !String(call[0]).startsWith(DRAFT_PATH))).toBe(true);
  });

  it("keeps the approved revision render step after approval deactivates the draft", async () => {
    const fetchMock = vi.fn((input: unknown) => {
      const url = String(input);
      if (url.includes("/approved-revisions/revision-1")) {
        return Promise.resolve(
          jsonResponse({
            id: "revision-1",
            application_id: "app-1",
            ready_qualified: false,
          }),
        );
      }
      return Promise.resolve(
        jsonResponse(
          detail({
            active_working_draft_id: null,
            latest_approved_revision_id: "revision-1",
            preparation_state: "approved",
            working_draft_state: "none",
          }),
        ),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    renderPage();

    expect(await screen.findByRole("heading", { name: "הגרסה אושרה" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("button", { name: "יצירת HTML ו־PDF" })).toBeEnabled());
    expect(screen.queryByText("אין כרגע טיוטה פעילה למועמדות הזו")).not.toBeInTheDocument();
    expect(fetchMock.mock.calls.every((call) => !String(call[0]).startsWith(DRAFT_PATH))).toBe(true);
  });

  it("states why a structural line stays instead of offering a removal that would be refused", async () => {
    stubReads({});

    renderPage();

    expect(await screen.findByText("שורת הכותרת היא חלק ממבנה המסמך ואינה נמחקת.")).toBeInTheDocument();
  });
});

describe("DraftEditorPage selection changes", () => {
  const omittedFacts = (): WorkingDraftFacts => ({
    ...facts(),
    facts: [
      ...facts().facts,
      {
        fact_id: "f-pinned",
        text: "Built the reporting pipeline.",
        linked_claim_ids: ["c-9"],
        section: "Core Skills",
        outcome: "pinned",
        reason: null,
      },
      {
        fact_id: "f-out",
        text: "Ran the partner onboarding programme.",
        linked_claim_ids: [],
        section: "Core Skills",
        outcome: "omitted",
        reason: "below_section_budget",
      },
    ],
  });

  it("includes an omitted fact as a pin, carrying every decision already recorded", async () => {
    const fetchMock = stubReads({ facts: () => jsonResponse(omittedFacts()) });

    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "הכללת העובדה" }));

    await waitFor(() =>
      expect(fetchMock.mock.calls.some((call) => String(call[0]).endsWith("/apply-selection-change"))).toBe(true),
    );
    const call = fetchMock.mock.calls.find((entry) => String(entry[0]).endsWith("/apply-selection-change"));
    /* Absolute lists: the existing pin is resent alongside the new one, because the plan
       is built from the overlay alone. */
    expect(JSON.parse(String((call?.[1] as RequestInit).body))).toEqual({
      expected_edit_version: 4,
      pinned_fact_ids: ["f-pinned", "f-out"],
      excluded_fact_ids: [],
    });
  });

  it("removes a fact-backed line by excluding its facts, not by patching the claim", async () => {
    const fetchMock = stubReads({ facts: () => jsonResponse(omittedFacts()) });

    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "הסרת השורה" }));

    await waitFor(() =>
      expect(fetchMock.mock.calls.some((call) => String(call[0]).endsWith("/apply-selection-change"))).toBe(true),
    );
    const call = fetchMock.mock.calls.find((entry) => String(entry[0]).endsWith("/apply-selection-change"));
    expect(JSON.parse(String((call?.[1] as RequestInit).body)).excluded_fact_ids).toEqual(["f-1"]);
    expect(fetchMock.mock.calls.some((entry) => (entry[1] as RequestInit)?.method === "PATCH")).toBe(false);
  });

  it("presents the manual-wording refusal as the backend states it", async () => {
    stubReads({
      facts: () => jsonResponse(omittedFacts()),
      selectionChange: () =>
        jsonResponse(
          {
            type: "about:blank#precondition_failed",
            title: "Precondition Failed",
            status: 412,
            code: "PRECONDITION_FAILED",
            detail: "this draft carries manual wording that a deterministic rebuild would discard",
          },
          412,
        ),
    });

    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "הכללת העובדה" }));

    expect(
      await screen.findByText("this draft carries manual wording that a deterministic rebuild would discard"),
    ).toBeInTheDocument();
  });
});

describe("DraftEditorPage regeneration", () => {
  const accepted = (): Response =>
    new Response(
      JSON.stringify({
        id: "op-7",
        application_id: "app-1",
        operation_type: "regenerate_claim",
        status: "queued",
        is_terminal: false,
        phase: "queued",
        message: "",
        created_at: "2026-08-24T07:00:00Z",
        outputs: [],
        available_actions: ["cancel"],
      }),
      {
        status: 202,
        headers: { "Content-Type": "application/json", Location: "/api/v1/operations/op-7" },
      },
    );

  /* The regeneration is reported in place. It used to navigate to the Operation's own
     route, which took the draft off the screen at the moment the user was waiting to see
     what became of one of its lines - and the way back from there led to the Application
     screen rather than to the editor they had left. The panel that appears here is the
     same one the Application screen uses. */
  it("freezes the exact saved version and reports the queued Operation in place", async () => {
    const fetchMock = stubReads({ regenerate: () => accepted() });

    renderPage();
    fireEvent.click((await screen.findAllByRole("button", { name: "יצירה מחדש של השורה" }))[0]!);

    /* The panel, not the route: the editor's own heading is still on screen beside it. */
    expect(await screen.findByRole("heading", { name: "הרצת יצירה מחדש של טענה" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "עריכה, אימות ואישור" })).toBeInTheDocument();
    const call = fetchMock.mock.calls.find((entry) => String(entry[0]).endsWith("/regenerate-claim"));
    /* All three parts of the draft's identity: that is what makes a save landing mid
       flight fail as SOURCE_CHANGED instead of overwriting the user's edit. */
    expect(JSON.parse(String((call?.[1] as RequestInit).body))).toEqual({
      application_id: "app-1",
      expected_edit_version: 4,
      expected_content_hash: "hash-4",
      job_analysis_id: "an-1",
      selection_plan_id: "sp-1",
      claim_id: "c-headline",
    });
    expect(((call?.[1] as RequestInit).headers as Headers).get("Idempotency-Key")).toBe("wd-1:4:c-headline");
  });

  it("withholds regeneration while an edit is still unsaved, and says why", async () => {
    stubReads({});

    renderPage();
    const editors = await screen.findAllByLabelText("טקסט השורה");
    fireEvent.change(editors[0]!, { target: { value: "typed but not saved" } });

    expect(
      await screen.findByText("יצירה מחדש מוקפאת על הגרסה השמורה של הטיוטה, ולכן היא זמינה רק אחרי שהשמירה הסתיימה."),
    ).toBeInTheDocument();
    for (const button of screen.getAllByRole("button", { name: "יצירה מחדש של השורה" })) {
      expect(button).toBeDisabled();
    }
  });
});

describe("DraftEditorPage preview", () => {
  it("frames the server-rendered draft in an isolated sandbox, marked as a draft", async () => {
    stubReads({});

    renderPage();

    const frame = await screen.findByTitle("תצוגה מקדימה של הטיוטה");
    expect(frame).toHaveAttribute("src", "/api/v1/working-drafts/wd-1/preview?v=4");
    /* An empty sandbox is the point: no allow-same-origin and no allow-scripts, so the
       document renders in an opaque origin and cannot reach this page. */
    expect(frame).toHaveAttribute("sandbox", "");
    expect(screen.getByText("טיוטה")).toBeInTheDocument();
  });

  it("keeps both panes mounted so switching views does not discard unsaved text", async () => {
    stubReads({});

    renderPage();
    const editors = await screen.findAllByLabelText("טקסט השורה");
    fireEvent.change(editors[0]!, { target: { value: "typed then switched away" } });

    fireEvent.click(screen.getByRole("button", { name: "תצוגה ואישור" }));

    expect(screen.getAllByLabelText("טקסט השורה")[0]).toHaveValue("typed then switched away");
    expect(screen.getByTitle("תצוגה מקדימה של הטיוטה")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "עריכה בלבד" }));
    expect(screen.getAllByLabelText("טקסט השורה")[0]).toHaveValue("typed then switched away");
    expect(screen.getByRole("button", { name: "עריכה ותצוגה" })).toBeInTheDocument();
  });
});
