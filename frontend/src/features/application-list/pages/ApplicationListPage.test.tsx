import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import type { ComponentProps } from "react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ApplicationListItem, ApplicationListResponse, Reason } from "@/api/contracts";
import { json } from "@/test/fixtures";
import { BOARD_LIMIT } from "../model/applicationListParams";
import { ApplicationListPage } from "./ApplicationListPage";

const item = (overrides: Partial<ApplicationListItem> = {}): ApplicationListItem =>
  ({
    id: "app-1",
    company: "Acme",
    target_role: "Backend Engineer",
    notes: "",
    created_at: "2026-08-24T07:00:00Z",
    updated_at: "2026-08-24T07:00:00Z",
    preparation_state: "needs_analysis",
    content_check: "none",
    review_reasons: [],
    warnings: [],
    job_text_hash: "c".repeat(64),
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

/* The list endpoint answers one page plus the counts that place it. `total` - the count
   before the query narrowed anything - is what tells an empty database apart from a
   slice that matched nothing. */
interface Counts {
  presetCounts?: Record<string, number>;
  total?: number;
}

const listBody = (items: ApplicationListItem[], counts: Counts = {}): ApplicationListResponse => ({
  items,
  matched: items.length,
  total: counts.total ?? items.length,
  limit: BOARD_LIMIT,
  offset: 0,
  preset_counts: counts.presetCounts ?? {
    all: items.length,
    ready_to_send: items.filter((entry) => entry.preparation_state === "ready").length,
    needs_attention: items.filter((entry) => entry.review_reasons.length > 0).length,
  },
  stage_counts: {},
});

/* Answers each read from `answer`, by its URL; a fresh Response per call, since a body can
   only be read once. */
const stubBoard = (answer: (url: URL) => ApplicationListResponse | Promise<never>) => {
  const fetchMock = vi.fn(async (url: unknown) => {
    const body = answer(new URL(String(url), "http://localhost"));
    return json(await body);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
};

const stubList = (items: ApplicationListItem[], counts: Counts = {}) => stubBoard(() => listBody(items, counts));

const requestedUrls = (fetchMock: ReturnType<typeof vi.fn>): URL[] =>
  fetchMock.mock.calls.map(([url]) => new URL(String(url), "http://localhost"));

const LocationProbe = () => {
  const location = useLocation();
  return <output data-testid="location">{location.pathname + location.search}</output>;
};

const renderPage = ({
  entries = ["/"],
  queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } }),
}: {
  entries?: ComponentProps<typeof MemoryRouter>["initialEntries"];
  queryClient?: QueryClient;
} = {}) => {
  const view = render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={entries}>
        <LocationProbe />
        <Routes>
          <Route element={<ApplicationListPage />} path="/" />
          <Route element={<h1>משרה חדשה</h1>} path="/applications/new" />
          <Route element={<h1>מסך המועמדות</h1>} path="/applications/:applicationId" />
          <Route element={<h1>עורך הטיוטה</h1>} path="/applications/:applicationId/draft" />
          <Route element={<h1>גרסה מוכנה</h1>} path="/applications/:applicationId/ready" />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );

  return { ...view, queryClient };
};

const cardsList = () => screen.findByRole("list", { name: "כרטיסי מועמדויות" });

afterEach(() => {
  vi.unstubAllGlobals();
  window.sessionStorage.clear();
});

describe("ApplicationListPage", () => {
  /* The board's slice is what every "back to the board" link returns to. Stored in the
     board's own canonical form rather than as the raw location, so an address arriving with
     a stale or invented parameter - the removed filter panel's among them - is not handed
     back later as a narrowing the reader chose. */
  it("remembers its slice and order for the screens that offer a way back to it", async () => {
    stubList([item()]);

    renderPage({ entries: ["/?preset=ready_to_send&sort=company&stage=approved&search=x&offset=24"] });

    expect(await screen.findByRole("heading", { level: 1, name: "לוח המועמדויות" })).toBeInTheDocument();
    expect(window.sessionStorage.getItem("cv:board-query")).toBe("preset=ready_to_send&sort=company");
  });

  it("asks for the whole board in one read", async () => {
    const fetchMock = stubList([item()]);

    renderPage();

    await cardsList();
    const board = requestedUrls(fetchMock).find((url) => !url.searchParams.has("preset"));
    expect(board?.searchParams.has("activity")).toBe(false);
    expect(board?.searchParams.get("limit")).toBe(String(BOARD_LIMIT));
    expect(board?.searchParams.has("offset")).toBe(false);
  });

  /* A board that failed to load is an error the reader can retry, not a blocker to
     resolve, and trying again is one press rather than a reload of the whole page. */
  it("offers to read the board again when it failed to load", async () => {
    let failing = true;
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => (failing ? json({ detail: "boom" }, 500) : json(listBody([item()])))),
    );

    renderPage();

    const failure = await screen.findByRole("alert", {}, { timeout: 4_000 });
    failing = false;
    expect(failure).toHaveTextContent("שגיאה");
    fireEvent.click(within(failure).getByRole("button", { name: "ניסיון חוזר" }));
    expect(await screen.findByRole("link", { name: /Backend Engineer/ })).toBeInTheDocument();
  });

  /* Coming back from the flow, the card worked on is marked for a moment where it already
     is - the board's order and slice stay exactly as they were left. */
  it("marks the card the reader came back to for a moment, without reordering the board", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      stubList([item(), item({ id: "app-2", company: "Binat", target_role: "Sales Engineer" })]);

      renderPage({ entries: [{ pathname: "/", state: { returnedFrom: "app-2" } }] });

      const list = await cardsList();
      const returned = within(list).getByRole("link", { name: /Sales Engineer/ });
      expect(returned).toHaveClass("cv-returned");
      expect(within(list).getByRole("link", { name: /Backend Engineer/ })).not.toHaveClass("cv-returned");
      expect(
        within(list)
          .getAllByRole("link")
          .map((card) => card.dataset.applicationId),
      ).toEqual(["app-1", "app-2"]);

      act(() => vi.advanceTimersByTime(2_400));
      expect(returned).not.toHaveClass("cv-returned");
    } finally {
      vi.useRealTimers();
    }
  });

  it("reserves the card grid with skeletons while the first request is pending", () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise<Response>(() => undefined)),
    );

    renderPage();

    expect(screen.getByRole("status", { name: "טוען את המועמדויות" })).toBeInTheDocument();
    expect(screen.queryByRole("list", { name: "כרטיסי מועמדויות" })).not.toBeInTheDocument();
  });

  /* The reason this screen exists: an Application that was saved has to be reachable
     without its URL, and its card has to say where its CV stands. The whole card
     is the way in, at the step the server recommends. */
  it("draws each Application as one link with its CV progress", async () => {
    stubList([
      item({ preparation_state: "draft_in_progress", recommended_action: "edit" }),
      item({
        id: "app-2",
        company: "Binat",
        preparation_state: "ready",
        recommended_action: null,
        target_role: "Sales Engineer",
      }),
    ]);

    renderPage();

    const list = await cardsList();
    const acme = within(list).getByRole("link", { name: /Backend Engineer/ });
    expect(acme).toHaveAttribute("href", "/applications/app-1/draft");
    expect(within(acme).getByText("Acme")).toBeInTheDocument();
    expect(within(acme).getByText("קו״ח")).toBeInTheDocument();
    expect(acme).toHaveTextContent("3/5");
    expect(acme).toHaveTextContent("הכנת קורות החיים: טיוטה בעבודה, שלב 3 מתוך 5");

    const binat = within(list).getByRole("link", { name: /Sales Engineer/ });
    expect(binat).toHaveAttribute("href", "/applications/app-2/ready");
    expect(within(binat).getByText("מוכן")).toBeInTheDocument();

    /* The board no longer stacks a next-step block or a menu on each card. */
    expect(screen.queryByRole("button", { name: /פעולות נוספות/ })).not.toBeInTheDocument();
    expect(screen.queryByText("פעולה מומלצת הבאה")).not.toBeInTheDocument();
  });

  it("says how many Applications there are, whichever slice is chosen", async () => {
    stubList([item()], { presetCounts: { all: 12, needs_attention: 3, ready_to_send: 1 } });

    renderPage({ entries: ["/?preset=ready_to_send"] });

    expect(await screen.findByText("12 מועמדויות")).toBeInTheDocument();
  });

  /* The slices are the board's only narrowing: a chip says how many it holds, a press
     narrows the server's read and writes the slice to the address bar, and "הכל" undoes
     it. */
  it("narrows by a slice from the server's counts and writes it to the URL", async () => {
    const fetchMock = stubList([item()], {
      presetCounts: { all: 12, needs_attention: 3, ready_to_send: 1 },
    });

    renderPage();

    const slices = await screen.findByRole("group", { name: "סינון מהיר לפי מצב" });
    expect(within(slices).getByRole("button", { name: "הכל 12" })).toHaveAttribute("aria-pressed", "true");
    expect(within(slices).getByRole("button", { name: "דורש טיפול 3" })).toHaveAttribute("aria-pressed", "false");

    fireEvent.click(within(slices).getByRole("button", { name: "מוכן לשליחה 1" }));

    expect(screen.getByTestId("location")).toHaveTextContent("/?preset=ready_to_send");
    await waitFor(() =>
      expect(requestedUrls(fetchMock).some((url) => url.searchParams.get("preset") === "ready_to_send")).toBe(true),
    );
    expect(within(slices).getByRole("button", { name: "מוכן לשליחה 1" })).toHaveAttribute("aria-pressed", "true");

    fireEvent.click(within(slices).getByRole("button", { name: "הכל 12" }));
    expect(screen.getByTestId("location")).toHaveTextContent(/^\/$/);
  });

  it("orders the board from the sort menu without dropping the slice", async () => {
    const fetchMock = stubList([item()]);

    renderPage({ entries: ["/?preset=needs_attention"] });

    await screen.findByRole("group", { name: "סינון מהיר לפי מצב" });
    const [sort] = screen.getAllByRole("combobox", { name: "מיון" });
    expect(sort).toHaveValue("updated");
    fireEvent.change(sort!, { target: { value: "company" } });

    expect(screen.getByTestId("location")).toHaveTextContent("/?preset=needs_attention&sort=company");
    await waitFor(() =>
      expect(requestedUrls(fetchMock).some((url) => url.searchParams.get("sort") === "company")).toBe(true),
    );
  });

  /* What blocks the reader comes from the whole board, one row per Application a review
     reason blocks, each the way to the step that resolves it. */
  it("lists blocked work in the action hub, each row a link", async () => {
    stubList([
      item({ id: "app-ready", company: "Ready Co", preparation_state: "ready", recommended_action: null }),
      item({ id: "app-attn", company: "Attn Co", review_reasons: [reason("PENDING_FACT_REQUIRES_RESOLUTION")] }),
      item({
        id: "app-warned",
        company: "Warned Co",
        warnings: [{ code: "DOCUMENT_ON_OLDER_ANALYSIS", message: "m", entity_references: {} }],
      }),
      item({ id: "app-fine", company: "Fine Co" }),
    ]);

    renderPage();

    const hub = await screen.findByRole("region", { name: "מוקד פעולות" });
    const rows = within(hub).getAllByRole("link");
    expect(rows.map((row) => row.getAttribute("href"))).toEqual(["/applications/app-attn/analysis"]);
    expect(rows[0]).toHaveTextContent("טענה בלי עובדה מאושרת");
    expect(rows[0]).toHaveTextContent("דורש טיפול");
    expect(within(hub).getByText("1 ממתינות")).toBeInTheDocument();
  });

  it("folds the hub past its first rows behind one control", async () => {
    stubList(
      ["a", "b", "c", "d"].map((id) =>
        item({ id, company: `Co ${id}`, review_reasons: [reason("PENDING_FACT_REQUIRES_RESOLUTION")] }),
      ),
    );

    renderPage();

    const hub = await screen.findByRole("region", { name: "מוקד פעולות" });
    const all = within(hub).getByRole("button", { name: "הכל (4)" });
    expect(all).toHaveAttribute("aria-expanded", "false");
    expect(within(hub).getAllByRole("listitem")[3]).toHaveClass("hidden");
    fireEvent.click(all);
    expect(all).toHaveAttribute("aria-expanded", "true");
    expect(within(hub).getAllByRole("listitem")[3]).not.toHaveClass("hidden");
  });

  it("draws no hub when nothing waits", async () => {
    stubList([item()]);

    renderPage();

    await cardsList();
    expect(screen.queryByRole("region", { name: "מוקד פעולות" })).not.toBeInTheDocument();
  });

  it("offers a first job and the fact pool when no Application exists", async () => {
    stubList([], { total: 0 });

    renderPage();

    expect(await screen.findByRole("heading", { name: "עוד אין מועמדויות" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "קליטת משרה ראשונה" })).toHaveAttribute("href", "/applications/new");
    expect(screen.getByRole("link", { name: "קודם למלא את מאגר העובדות" })).toHaveAttribute("href", "/facts");
    expect(screen.queryByRole("group", { name: "סינון מהיר לפי מצב" })).not.toBeInTheDocument();
  });

  /* A slice that holds nothing is a gap in the board, not an empty product: the slices
     stay, and the way out shows everything again. */
  it("offers to show every Application when the slice matches none", async () => {
    stubList([], { total: 4, presetCounts: { all: 4, ready_to_send: 0, needs_attention: 0 } });

    renderPage({ entries: ["/?preset=ready_to_send"] });

    expect(await screen.findByText("אין מועמדות שמתאימה לסינון.")).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "סינון מהיר לפי מצב" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "הצגת כל המועמדויות" }));
    expect(screen.getByTestId("location")).toHaveTextContent(/^\/$/);
  });

  it("dims the board while a changed slice replaces it, not while the same board is re-read", async () => {
    let boardReads = 0;
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    stubBoard(() => {
      boardReads += 1;
      return boardReads <= 2 ? listBody([item()]) : new Promise<never>(() => undefined);
    });

    renderPage({ queryClient });

    const list = await cardsList();
    expect(list.closest('[aria-busy="true"]')).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: /^דורש טיפול/ }));
    await waitFor(() => expect(boardReads).toBe(3));
    expect(screen.getByRole("list", { name: "כרטיסי מועמדויות" }).closest('[aria-busy="true"]')).not.toBeNull();
  });
});
