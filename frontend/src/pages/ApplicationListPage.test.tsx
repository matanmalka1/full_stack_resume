import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ApplicationListItem } from "../api/contracts";
import { ApplicationListPage } from "./ApplicationListPage";
import { actionLabel } from "./applicationLabels";

const item = (overrides: Partial<ApplicationListItem> = {}): ApplicationListItem =>
  ({
    id: "app-1",
    company: "Acme",
    target_role: "Backend Engineer",
    current_status: "saved",
    notes: "",
    source: "manual",
    created_at: "2026-08-24T07:00:00Z",
    updated_at: "2026-08-24T07:00:00Z",
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
    ...overrides,
  }) as ApplicationListItem;

const jsonResponse = (body: unknown, status = 200): Response =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });

/* The list endpoint answers one page plus the two counts that place it. The stub fills
   `matched` from the rows it was handed, because a page whose count disagreed with its
   own rows would be testing against a server that cannot exist; `total` - the count
   before the query narrowed anything - is separate, and is what tells an empty database
   apart from a filter that matched nothing.

   The mock builds a `Response` per call rather than resolving to one: a body can only
   be read once, so a stub answering every call with the same object fails the second
   request as an unreadable reply - which is what the screen reports when a control
   re-asks the question. */
interface Counts {
  matched?: number;
  total?: number;
  stageCounts?: Partial<Record<string, number>>;
}

const listBody = (items: ApplicationListItem[], counts: Counts = {}) => {
  const matched = counts.matched ?? items.length;
  /* Counted over every Application rather than the page, the way the server answers it:
     the stage menu must not collapse to the one stage its own filter selected. */
  const stage_counts =
    counts.stageCounts ??
    items.reduce<Record<string, number>>(
      (totals, item) => ({
        ...totals,
        [item.preparation_state]: (totals[item.preparation_state] ?? 0) + 1,
      }),
      {},
    );

  return {
    items,
    matched,
    total: counts.total ?? matched,
    limit: 25,
    offset: 0,
    stage_counts,
  };
};

const stubList = (items: ApplicationListItem[], counts: Counts = {}) => {
  const body = { current: listBody(items, counts) };
  const fetchMock = vi.fn(async (_url: unknown, _options?: unknown) =>
    jsonResponse(body.current),
  );
  vi.stubGlobal("fetch", fetchMock);
  return {
    fetchMock,
    /* What the server answers next, for a test that changes the question mid-flight. */
    answer: (nextItems: ApplicationListItem[], nextCounts: Counts = {}) => {
      body.current = listBody(nextItems, nextCounts);
    },
  };
};

const renderPage = (entries: string[] = ["/"]) =>
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <MemoryRouter initialEntries={entries}>
        <Routes>
          <Route element={<ApplicationListPage />} path="/" />
          <Route element={<h1>משרה חדשה</h1>} path="/applications/new" />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("ApplicationListPage", () => {
  /* The reason this screen exists: an Application that was saved has to be reachable
     without its URL, and its row has to say where it stands. */
  it("lists every Application with both of its state axes", async () => {
    stubList([
      item(),
      item({ id: "app-2", company: "Binat", preparation_state: "ready" }),
    ]);

    renderPage();

    expect(await screen.findByRole("link", { name: "Acme" })).toHaveAttribute(
      "href",
      "/applications/app-1",
    );
    expect(screen.getByRole("link", { name: "Binat" })).toHaveAttribute(
      "href",
      "/applications/app-2",
    );
    /* Preparation and recruitment are independent axes and the board shows both: one says
       how far the CV has got, the other where the Application stands with the employer.
       Scoped to the table because the stage filter offers the same vocabulary as its
       options, and an option is a control rather than a row. */
    const board = within(screen.getByRole("table"));
    expect(board.getByText("ממתין לניתוח המשרה")).toBeInTheDocument();
    expect(board.getByText("קורות החיים מוכנים")).toBeInTheDocument();
    expect(board.getAllByText("נשמר")).toHaveLength(2);
  });

  /* The board answers "which of these is waiting on me", so the recommended action is a
     column rather than something found by opening each Application in turn. */
  it("shows the stored recruitment follow-up alongside the workflow recommendation", async () => {
    stubList([
      item({
        next_action: "Follow up with recruiter",
        next_action_date: "2026-09-05",
        recommended_action: "analyze",
      }),
    ]);

    renderPage();

    expect(await screen.findByText("Follow up with recruiter")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: actionLabel("analyze") })).toBeInTheDocument();
  });
});
