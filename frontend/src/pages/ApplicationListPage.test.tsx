import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useNavigate } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { applicationDetailQueryOptions, applicationListQueryOptions } from "../api/applications";
import type { ApplicationDetail, ApplicationListItem, ApplicationListResponse, Reason } from "../api/contracts";
import { ApplicationListPage } from "./ApplicationListPage";

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

const reason = (code: string): Reason => ({
  code,
  message: `plain sentence for ${code}`,
  entity_references: {},
  allowed_resolution_actions: [],
});

const jsonResponse = (body: unknown, status = 200): Response =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });

/* The list endpoint answers one page plus the two counts that place it. The stub defaults
   `matched` to the rows it was handed for the common one-page case; pagination tests
   override it with the count across every matching page. `total` - the count before the
   query narrowed anything - is separate, and is what tells an empty database apart from
   a filter that matched nothing.

   The mock builds a `Response` per call rather than resolving to one: a body can only
   be read once, so a stub answering every call with the same object fails the second
   request as an unreadable reply - which is what the screen reports when a control
   re-asks the question. */
interface Counts {
  matched?: number;
  total?: number;
  stageCounts?: Record<string, number>;
}

const listBody = (items: ApplicationListItem[], counts: Counts = {}): ApplicationListResponse => {
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

const detailBody = (): ApplicationDetail => ({
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
});

const stubList = (items: ApplicationListItem[], counts: Counts = {}) => {
  const body = listBody(items, counts);
  const fetchMock = vi.fn(async (_url: unknown, options?: RequestInit) =>
    options?.method === "POST"
      ? jsonResponse({
          application_id: "app-1",
          current_status: "closed",
          event_id: "event-1",
          next_action: null,
          next_action_date: null,
          terminal_outcome: null,
        })
      : jsonResponse(body),
  );
  vi.stubGlobal("fetch", fetchMock);
  return {
    fetchMock,
  };
};

const HistoryBack = () => {
  const navigate = useNavigate();
  return <button onClick={() => navigate(-1)}>בדיקת חזרה</button>;
};

interface RenderPageOptions {
  entries?: string[];
  initialIndex?: number;
  queryClient?: QueryClient;
  withHistoryBack?: boolean;
}

const renderPage = ({
  entries = ["/"],
  initialIndex,
  queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } }),
  withHistoryBack = false,
}: RenderPageOptions = {}) => {
  const view = render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={entries} initialIndex={initialIndex}>
        {withHistoryBack ? <HistoryBack /> : null}
        <Routes>
          <Route element={<ApplicationListPage />} path="/" />
          <Route element={<h1>משרה חדשה</h1>} path="/applications/new" />
          <Route element={<h1>מסך המועמדות</h1>} path="/applications/:applicationId" />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );

  return { ...view, queryClient };
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("ApplicationListPage", () => {
  /* The reason this screen exists: an Application that was saved has to be reachable
     without its URL, and its row has to say where it stands. */
  it("lists every Application with both of its state axes", async () => {
    stubList([item(), item({ id: "app-2", company: "Binat", preparation_state: "ready" })]);

    renderPage();

    expect(await screen.findByRole("link", { name: "Acme" })).toHaveAttribute("href", "/applications/app-1");
    expect(screen.getByRole("link", { name: "Binat" })).toHaveAttribute("href", "/applications/app-2");
    /* Preparation and recruitment are independent axes and the board shows both: one says
       how far the CV has got, the other where the Application stands with the employer.
       Scoped to the table because the stage filter offers the same vocabulary as its
       options, and an option is a control rather than a row. */
    const board = within(screen.getByRole("table"));
    expect(board.getByText("ממתין לניתוח המשרה")).toBeInTheDocument();
    expect(board.getByText("קורות החיים מוכנים")).toBeInTheDocument();
    expect(board.getAllByText("נשמר")).toHaveLength(2);
    expect(board.getByRole("columnheader", { name: "צעד הבא ויעד" })).toBeInTheDocument();
    expect(board.getByRole("columnheader", { name: "פעולות מהירות" })).toBeInTheDocument();
    expect(board.getByRole("link", { name: "עדכון סטטוס ומשימות עבור Acme" })).toHaveAttribute(
      "href",
      "/applications/app-1/tracking",
    );
  });

  /* The column is read to decide which row to open next, so it names what is waiting
     rather than counting it, and the badge is the way into the Application that states
     each item beside the control that resolves it. */
  it("names a blocking reason and links it to preparation", async () => {
    stubList([item({ review_reasons: [reason("HARD_GAP_REQUIRES_DECISION")] })]);

    renderPage();

    const attention = await screen.findByRole("link", { name: "Acme: יש פער חוסם מול הדרישות" });
    expect(attention).toHaveAttribute("href", "/applications/app-1/preparation");
    expect(within(attention).getByText("יש פער חוסם מול הדרישות")).toBeInTheDocument();
  });
  /* The stage menu hides stages nothing is in. Hiding the one the URL selects left the
     select showing "הכול" while that filter was still narrowing the board. */
  it("keeps a selected stage in the menu when the board counts none of it", async () => {
    stubList([], { matched: 0, total: 4, stageCounts: { ready: 4 } });

    renderPage({ entries: ["/?stage=needs_analysis"] });

    await screen.findByText("אין מועמדות שמתאימה לסינון.");
    expect(screen.getByLabelText("מצב קורות החיים")).toHaveValue("needs_analysis");
  });

  /* Clearing what matched nothing must not also move the reader to another board. */
  it("keeps the activity and sort selections when the filter is cleared", async () => {
    const { fetchMock } = stubList([], { matched: 0, total: 4, stageCounts: { ready: 4 } });

    renderPage({ entries: ["/?activity=closed&sort=company&search=nothing"] });

    fireEvent.click(await screen.findByRole("button", { name: "ניקוי הסינון" }));

    expect(screen.getByLabelText("מועמדויות")).toHaveValue("closed");
    expect(screen.getByLabelText("סדר")).toHaveValue("company");
    expect(screen.getByLabelText("חיפוש")).toHaveValue("");
    await waitFor(() =>
      expect(fetchMock).toHaveBeenLastCalledWith(
        expect.stringContaining("activity=closed"),
        expect.objectContaining({ method: "GET" }),
      ),
    );
  });

  /* The row was painted on hover while only three of its cells were clickable. */
  it("opens the Application from a click anywhere the row carries no control of its own", async () => {
    stubList([item()]);

    renderPage();

    fireEvent.click(await screen.findByText("Backend Engineer"));

    expect(screen.getByRole("heading", { name: "מסך המועמדות" })).toBeInTheDocument();
  });

  it("switches between table, card, and recruitment pipeline views without changing the server query", async () => {
    const { fetchMock } = stubList([
      item({ next_action: "Follow up", next_action_date: "2020-01-01" }),
      item({ id: "app-2", company: "Binat", notes: "Referral from Dana", recruitment_status: "interview" }),
      item({ id: "app-3", company: "ClosedCo", recruitment_status: "rejected" }),
    ]);

    renderPage();

    expect(await screen.findByRole("table")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "תצוגת כרטיסים" }));
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "Acme" })).toHaveLength(1);
    expect(screen.getAllByRole("link", { name: "Binat" })).toHaveLength(1);
    expect(screen.getByText("Follow up")).toBeInTheDocument();
    expect(screen.getByText(/באיחור/)).toBeInTheDocument();
    expect(screen.getByText(/Referral from Dana/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "עדכון סטטוס ומשימות עבור Acme" })).toHaveAttribute(
      "href",
      "/applications/app-1/tracking",
    );

    fireEvent.click(screen.getByRole("button", { name: "תצוגת שלבי גיוס" }));
    const pipeline = screen.getByRole("list", { name: "מועמדויות לפי שלב גיוס" });
    expect(within(pipeline).getByRole("heading", { name: "נשמרו / בהכנה" })).toBeInTheDocument();
    expect(within(pipeline).getByRole("heading", { name: "ראיונות והצעות" })).toBeInTheDocument();
    expect(within(pipeline).getByRole("heading", { name: "תהליכים סגורים" })).toBeInTheDocument();
    expect(within(pipeline).getAllByText("אין מועמדויות בשלב זה")).toHaveLength(2);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("keeps the filters visible when a narrowed board matches none of the stored Applications", async () => {
    stubList([], { matched: 0, total: 4, stageCounts: { ready: 4 } });

    renderPage({ entries: ["/?activity=closed"] });

    expect(await screen.findByText("אין מועמדות שמתאימה לסינון.")).toBeInTheDocument();
    expect(screen.getByLabelText("חיפוש")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "ניקוי הסינון" })).toBeInTheDocument();
    expect(screen.queryByText("עוד לא נוצרה אף מועמדות.")).not.toBeInTheDocument();
  });

  it("uses the first-use empty state only when no Application exists before filtering", async () => {
    stubList([], { matched: 0, total: 0 });

    renderPage();

    expect(await screen.findByText("עוד לא נוצרה אף מועמדות.")).toBeInTheDocument();
    expect(screen.queryByLabelText("חיפוש")).not.toBeInTheDocument();
    expect(screen.queryByText("אין מועמדות שמתאימה לסינון.")).not.toBeInTheDocument();
  });

  it("moves through server pages and writes page-boundary offsets to the URL query", async () => {
    const firstPage = Array.from({ length: 25 }, (_, index) =>
      item({ id: `app-${index + 1}`, company: `Company ${index + 1}` }),
    );
    const firstPageBody = listBody(firstPage, { matched: 26, total: 26 });
    const lastPageBody = listBody([item({ id: "app-26", company: "Last Company" })], {
      matched: 26,
      total: 26,
    });
    const fetchMock = vi.fn(async (url: unknown) =>
      jsonResponse(String(url).includes("offset=25") ? lastPageBody : firstPageBody),
    );
    vi.stubGlobal("fetch", fetchMock);

    renderPage();

    expect(await screen.findByRole("navigation", { name: "ניווט בין דפי המועמדויות" })).toBeInTheDocument();
    expect(screen.getByText("1–25 מתוך 26")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "הבא" }));

    /* A page-boundary navigation starts a fresh server query. Under the full parallel
       suite, scheduling that query can exceed Testing Library's one-second default even
       though the mocked response is immediate. Keep the longer budget local to this
       multi-render transition rather than weakening every assertion. */
    expect(await screen.findByRole("link", { name: "Last Company" }, { timeout: 5_000 })).toBeInTheDocument();
    expect(screen.getByText("26–26 מתוך 26")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenLastCalledWith(
      expect.stringContaining("offset=25"),
      expect.objectContaining({ method: "GET" }),
    );
    expect(screen.getByRole("button", { name: "הבא" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "הקודם" })).toBeEnabled();
  });

  it("updates the field from browser history immediately and delays only the server read", async () => {
    const { fetchMock } = stubList([item()]);

    renderPage({
      entries: ["/?search=first", "/?search=second"],
      initialIndex: 1,
      withHistoryBack: true,
    });

    expect(await screen.findByDisplayValue("second")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: "בדיקת חזרה" }));

    expect(screen.getByDisplayValue("first")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(fetchMock).toHaveBeenLastCalledWith(
      expect.stringContaining("search=first"),
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("invalidates every cached list and detail after closing an Application", async () => {
    const { fetchMock } = stubList([item()]);
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const closedListKey = applicationListQueryOptions({ activity: "closed" }).queryKey;
    const detailKey = applicationDetailQueryOptions("app-1").queryKey;
    queryClient.setQueryData(closedListKey, listBody([], { total: 1 }));
    queryClient.setQueryData(detailKey, detailBody());

    renderPage({ queryClient });

    fireEvent.click(await screen.findByRole("button", { name: "סגירת המועמדות Acme" }));
    fireEvent.click(screen.getByRole("button", { name: "סגירת המועמדות" }));

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/v1/applications/app-1/close",
        expect.objectContaining({ method: "POST" }),
      ),
    );
    await waitFor(() => {
      expect(queryClient.getQueryState(closedListKey)?.isInvalidated).toBe(true);
      expect(queryClient.getQueryState(detailKey)?.isInvalidated).toBe(true);
    });
  });
});
