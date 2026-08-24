import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ApplicationDetail, WorkingDraft, WorkingDraftFacts } from "../api/contracts";
import { DraftEditorPage } from "./DraftEditorPage";

const DETAIL_PATH = "/api/v1/applications/app-1";
const DRAFT_PATH = "/api/v1/working-drafts/wd-1";

const detail = (overrides: Partial<ApplicationDetail> = {}): ApplicationDetail =>
  ({
    recruitment_status: "saved",
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

/* One route per read, so a test states which answer it is giving rather than depending on
   the order the screen happens to request them in. */
const stubReads = (
  answers: Partial<Record<"detail" | "draft" | "facts", () => Response>>,
): ReturnType<typeof vi.fn> => {
  const fetchMock = vi.fn((input: unknown) => {
    const url = String(input);

    if (url.startsWith(`${DRAFT_PATH}/facts`)) {
      return Promise.resolve(answers.facts?.() ?? jsonResponse(facts()));
    }
    if (url.startsWith(DRAFT_PATH)) {
      return Promise.resolve(answers.draft?.() ?? jsonResponse(draft()));
    }
    return Promise.resolve(answers.detail?.() ?? jsonResponse(detail()));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
};

const renderPage = () => {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false, refetchInterval: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });

  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/applications/app-1/draft"]}>
        <Routes>
          <Route element={<DraftEditorPage />} path="/applications/:applicationId/draft" />
          <Route element={<h1>מועמדות</h1>} path="/applications/:applicationId" />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("DraftEditorPage", () => {
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

    expect(await screen.findByText("Delivered 30% growth.")).toBeInTheDocument();
    expect(screen.getByText("ללא ביסוס")).toBeInTheDocument();
    expect(
      screen.getByText("no canonical fact authorizes this wording"),
    ).toBeInTheDocument();
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

    expect(
      await screen.findByText("A claim in the active draft depends on a pending fact."),
    ).toBeInTheDocument();
    expect(screen.getByText("נדרשת החלטה לפני אישור הגרסה")).toBeInTheDocument();
  });

  it("says plainly when there is no active draft instead of reading one that does not exist", async () => {
    const fetchMock = stubReads({
      detail: () =>
        jsonResponse(detail({ active_working_draft_id: null, working_draft_state: "none" })),
    });

    renderPage();

    expect(await screen.findByText("אין כרגע טיוטה פעילה למועמדות הזו")).toBeInTheDocument();
    expect(fetchMock.mock.calls.every((call) => !String(call[0]).startsWith(DRAFT_PATH))).toBe(true);
  });

  it("states why a structural line stays instead of offering a removal that would be refused", async () => {
    stubReads({});

    renderPage();

    expect(
      await screen.findByText("שורת הכותרת היא חלק ממבנה המסמך ואינה נמחקת."),
    ).toBeInTheDocument();
  });
});
