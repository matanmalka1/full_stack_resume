import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ApplicationListItem, Operation } from "../api/contracts";
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

const requestedQuery = (fetchMock: ReturnType<typeof vi.fn>): URLSearchParams => {
  const calls = fetchMock.mock.calls;
  const url = String(calls[calls.length - 1]?.[0] ?? "");
  return new URL(url, "http://localhost").searchParams;
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
  it("names the next action from the projection", async () => {
    stubList([
            item(),
            item({ id: "app-2", company: "Binat", recommended_action: null }),
            item({
              id: "app-3",
              company: "Cegal",
              preparation_state: "draft_in_progress",
              recommended_action: "update_working_draft",
            }),
          ]);

    renderPage();

    /* An action with no screen of its own leads to the Application, which is where it is
       taken. */
    expect(await screen.findByRole("link", { name: "ניתוח המשרה" })).toHaveAttribute(
      "href",
      "/applications/app-1",
    );
    /* Scoped to the row it is about, and to the cell within it. The em dash is the
       "nothing here" mark in more than one column, so an unscoped query would match every
       empty cell on the board and assert nothing about the row with no recommended
       action. The last cell is the one that carries it. */
    const withoutAction = screen.getByRole("link", { name: "Binat" }).closest("tr");
    const actionCell = within(withoutAction as HTMLElement).getAllByRole("cell").at(-1);
    expect(within(actionCell as HTMLElement).getByText("—")).toBeInTheDocument();
    /* One with a screen leads straight to it. The button names the action, so stopping at
       the context screen first asked the reader to find it a second time. */
    expect(screen.getByRole("link", { name: actionLabel("update_working_draft") })).toHaveAttribute(
      "href",
      "/applications/app-3/draft",
    );
  });

  /* The database starts empty, so this is the first screen a new installation shows. */
  it("offers the one action that fills an empty list", async () => {
    stubList([]);

    renderPage();

    expect(await screen.findByText("עוד לא נוצרה אף מועמדות.")).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: /משרה חדשה/ })[0]).toHaveAttribute(
      "href",
      "/applications/new",
    );
  });

  /* The projection carries every reason and warning; the row has one line. It says how
     much is waiting, so a badge reading "pending a decision" is not the whole answer. */
  it("counts what each Application is waiting on", async () => {
    stubList([
          item({
            preparation_state: "needs_review",
            review_reasons: [
              {
                code: "LOW_FIT_REQUIRES_ACCEPTANCE",
                message: "",
                entity_references: {},
                allowed_resolution_actions: [],
              },
            ],
            warnings: [{ code: "SOMETHING", message: "", entity_references: {} }],
          }),
        ]);

    renderPage();

    /* The counts name the same three reason lists the column header does, so a decision
       waiting on the user reads differently from a warning raised beside it. */
    expect(await screen.findByText("1 להכרעה · 1 אזהרות")).toBeInTheDocument();
  });

  /* While an Operation is running the answer to "what next" is to wait for it, so the
     row reports the work instead of an action that cannot be taken yet. */
  it("reports live work in place of the next action", async () => {
    stubList([
            item({
              active_operation: {
                id: "op-1",
                operation_type: "analyze_job",
                status: "running",
                is_terminal: false,
              } as Operation,
            }),
          ]);

    renderPage();

    /* The badge composes its label from two runs, so the assertion reads the element's
       whole text rather than one text node. */
    expect(
      await screen.findAllByText(
        (_, element) => element?.textContent === "ניתוח המשרה · מתבצעת",
      ),
    ).not.toHaveLength(0);
    expect(screen.queryByRole("link", { name: actionLabel("analyze") })).not.toBeInTheDocument();
  });

  /* The two are different questions and the board asks both: the tracked action is the
     user's own plan for this Application, the recommended one is what the preparation
     workflow says to do next. Collapsed into one cell, a scheduled call used to hide the
     fact that a draft was waiting. */
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

  /* The chips are the board's named questions. Each one sets the `preset` parameter and
     nothing else, so the server answers which rows match rather than this screen deciding
     it - the predicates are the §9 projection's. */
  it("asks the server for a preset when a chip is chosen, and narrows alongside it", async () => {
    const { fetchMock } = stubList([item()]);

    renderPage();
    await screen.findByRole("link", { name: "Acme" });

    fireEvent.click(screen.getByRole("radio", { name: "דורש טיפול" }));

    await waitFor(() => expect(requestedQuery(fetchMock).get("preset")).toBe("needs_attention"));

    /* A preset and a stage filter are one question with two clauses, not two questions:
       choosing a recruitment stage must not drop the chip that is already applied. */
    fireEvent.change(screen.getByLabelText("שלב גיוס"), { target: { value: "interview" } });

    await waitFor(() => {
      const query = requestedQuery(fetchMock);
      expect(query.get("preset")).toBe("needs_attention");
      expect(query.getAll("recruitment_status")).toEqual(["interview"]);
    });
  });

  /* "הכל" is the absence of a preset rather than a fourth one, so it clears the
     parameter instead of sending a value the server would have to know about. */
  it("clears the preset when the board returns to הכל", async () => {
    const { fetchMock } = stubList([item()], {});

    renderPage(["/?preset=ready_to_send"]);
    await screen.findByRole("link", { name: "Acme" });

    fireEvent.click(screen.getByRole("radio", { name: "הכל" }));

    await waitFor(() => expect(requestedQuery(fetchMock).has("preset")).toBe(false));
  });

  /* Overdue is a comparison against the reader's own today, so it is derived on the
     client rather than carried by the projection: a board left open past midnight must
     not go on reporting yesterday's answer.

     Dated relative to the real clock rather than under fake timers. Freezing time would
     also freeze the clock React Query and `findBy*` wait on, which is a deadlock rather
     than a test - and the thing under test is a date comparison, which a fixed offset
     from today exercises just as exactly. */
  it("marks a tracked action whose date has passed, and leaves a future one unmarked", async () => {
    const day = 24 * 60 * 60 * 1000;
    const isoDate = (offsetDays: number) =>
      new Date(Date.now() + offsetDays * day).toISOString().slice(0, 10);

    stubList([
      item({ id: "late", company: "Late", next_action: "Call", next_action_date: isoDate(-5) }),
      item({ id: "soon", company: "Soon", next_action: "Call", next_action_date: isoDate(5) }),
    ]);

    renderPage();

    /* One badge, on the row whose date has passed - not on both and not on neither. */
    await screen.findByRole("link", { name: "Late" });
    expect(screen.getAllByText("באיחור")).toHaveLength(1);
  });

  /* A Ready Application has produced the thing this whole workflow exists for. Its row
     used to be the one that said the least: an em dash where the file should be. */
  it("links a Ready Application straight to its finished revision", async () => {
    stubList([
            item({
              preparation_state: "ready",
              recommended_action: null,
              latest_ready_revision_id: "rev-9",
            }),
          ]);

    renderPage();

    expect(await screen.findByRole("link", { name: "הגרסה המוכנה" })).toHaveAttribute(
      "href",
      "/approved-revisions/rev-9/ready",
    );
  });

  /* Two rows for the same opening are identical everywhere else on this screen. */
  it("dates only the rows a reader cannot otherwise tell apart", async () => {
    stubList([
            item({ id: "app-1", created_at: "2026-08-20T07:00:00Z" }),
            item({ id: "app-2", created_at: "2026-08-24T07:00:00Z" }),
            item({ id: "app-3", company: "Binat" }),
          ]);

    renderPage();

    /* Scoped to the table, and asserted on the creation lines rather than the "updated"
       column that every row carries. The sort menu names an ordering by creation too, so
       an unscoped match would count a control as a row. */
    await screen.findByRole("table");
    const board = within(screen.getByRole("table"));
    expect(board.getByText("נוצר 20.8.2026")).toBeInTheDocument();
    expect(board.getByText("נוצר 24.8.2026")).toBeInTheDocument();
    /* Three rows, two of them a pair: the unique one carries no creation date. */
    expect(board.getAllByText(/^נוצר /)).toHaveLength(2);
  });

  /* Narrowing is the server's answer, so what the controls have to be tested on is the
     question they send. A screen that filtered the rows it already held would be deriving
     `preparation_state` a second time - it is computed by the projection, not stored. */
  it("asks the server for what the controls say, and opens on live work", async () => {
    /* The stage menu offers the states the Applications are actually in, counted by the
       server over all of them - so the stub has to report a stage for the filter to be
       able to name it. */
    const { fetchMock } = stubList([item()], { stageCounts: { needs_analysis: 1, ready: 4 } });

    renderPage();

    await screen.findByRole("link", { name: "Acme" });
    /* The board opens on the live Applications rather than everything ever stored. */
    expect(requestedQuery(fetchMock).get("activity")).toBe("open");

    fireEvent.change(screen.getByLabelText("מועמדויות"), { target: { value: "closed" } });
    await waitFor(() => expect(requestedQuery(fetchMock).get("activity")).toBe("closed"));

    fireEvent.change(screen.getByLabelText("מצב קורות החיים"), { target: { value: "ready" } });
    await waitFor(() => expect(requestedQuery(fetchMock).getAll("stage")).toEqual(["ready"]));

    fireEvent.change(screen.getByLabelText("סדר"), { target: { value: "company" } });
    await waitFor(() => expect(requestedQuery(fetchMock).get("sort")).toBe("company"));
  });

  /* The stage filter cannot be offered from the page it narrows: once it is applied, the
     only stage that page holds is the one it selected. The counts are the server's, over
     every Application. */
  it("offers only the stages that exist, with their counts", async () => {
    stubList([item()], { stageCounts: { needs_analysis: 3, ready: 1 } });

    renderPage();

    const stages = within(await screen.findByLabelText("מצב קורות החיים"));
    expect(stages.getByRole("option", { name: "ממתין לניתוח המשרה (3)" })).toBeInTheDocument();
    expect(stages.getByRole("option", { name: "קורות החיים מוכנים (1)" })).toBeInTheDocument();
    /* A state no Application has reached is not a filter worth offering. */
    expect(stages.queryByRole("option", { name: /מוכן לאישור/ })).not.toBeInTheDocument();
  });

  /* Every keystroke was a request, and their answers raced each other. The field stays
     responsive; what waits is the question. */
  it("waits for the search to settle before asking", async () => {
    const { fetchMock } = stubList([item()]);
    renderPage();

    const field = await screen.findByLabelText("חיפוש");
    expect(fetchMock).toHaveBeenCalledTimes(1);

    /* Fake timers only from here: the initial read has to complete on real ones, or the
       board never renders the field this test types into. */
    vi.useFakeTimers();
    try {
      for (const value of ["b", "bi", "bin", "bina", "binat"]) {
        fireEvent.change(field, { target: { value } });
      }

      /* The field shows what was typed immediately - the delay is not felt in it. */
      expect(field).toHaveValue("binat");
      expect(fetchMock).toHaveBeenCalledTimes(1);

      await vi.advanceTimersByTimeAsync(400);
    } finally {
      vi.useRealTimers();
    }

    await waitFor(() => expect(requestedQuery(fetchMock).get("search")).toBe("binat"));
    /* Five keystrokes, one question. */
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  /* A narrowed board is something a user links to, reloads, and goes back from, none of
     which survives state that only exists while the component is mounted. */
  it("carries the query in the address bar, in both directions", async () => {
    const { fetchMock } = stubList([item()], { stageCounts: { ready: 2 } });

    renderPage(["/?activity=all&stage=ready&sort=company"]);

    /* Read from the URL: the first request is the question the link asked. */
    await screen.findByRole("link", { name: "Acme" });
    expect(requestedQuery(fetchMock).get("activity")).toBe("all");
    expect(requestedQuery(fetchMock).getAll("stage")).toEqual(["ready"]);
    /* And the controls show it, rather than showing defaults beside a filtered board. */
    expect(screen.getByLabelText("מועמדויות")).toHaveValue("all");
    expect(screen.getByLabelText("סדר")).toHaveValue("company");

    /* Written back: a control moves the query the router holds, so the next request
       carries it. The router is a MemoryRouter here, so its location is what is
       asserted rather than the browser's own address bar. */
    fireEvent.change(screen.getByLabelText("סדר"), { target: { value: "created" } });
    await waitFor(() => expect(requestedQuery(fetchMock).get("sort")).toBe("created"));
    /* Cleared back to the default, the parameter is dropped rather than spelled out. */
    fireEvent.change(screen.getByLabelText("סדר"), { target: { value: "updated" } });
    await waitFor(() => expect(requestedQuery(fetchMock).get("sort")).toBe("updated"));
  });

  /* Closing is a status transition that keeps every record. It moves the Application off
     the live board, so it is confirmed rather than taken on one click. */
  it("closes an Application only after it is confirmed", async () => {
    const { fetchMock } = stubList([item({ company: "Acme" })]);

    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: "סגירת המועמדות Acme" }));

    /* Opening the dialog sends nothing. */
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("heading", { name: "לסגור את המועמדות?" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "ביטול" }));
    expect(fetchMock).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: "סגירת המועמדות Acme" }));
    fireEvent.click(screen.getByRole("button", { name: "סגירת המועמדות" }));

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([url, options]) =>
            String(url).endsWith("/applications/app-1/close") &&
            (options as RequestInit | undefined)?.method === "POST",
        ),
      ).toBe(true),
    );
  });

  /* A row that is already closed has nothing left to close. */
  it("does not offer closing an Application that is already closed", async () => {
    stubList([item({ recruitment_status: "closed", terminal_outcome: "closed" })]);

    renderPage();

    await screen.findByRole("link", { name: "Acme" });
    expect(screen.queryByRole("button", { name: /סגירת המועמדות/ })).not.toBeInTheDocument();
    expect(screen.getByText("התהליך נסגר")).toBeInTheDocument();
  });

  /* A board narrowed to nothing must not read like a board that is broken or empty.
     `total` is what tells the two apart: there are Applications, and the query is what is
     hiding them. */
  it("says a filter is what is hiding the rows, and offers the way back", async () => {
    const { answer, fetchMock } = stubList([], {
      matched: 0,
      total: 2,
      stageCounts: { needs_analysis: 2 },
    });

    /* Arrived at through a narrowing link, so clearing is a real change of question
       rather than re-asking the one already in the address bar. */
    renderPage(["/?search=nothing+matches+this"]);

    expect(await screen.findByText("אין מועמדות שמתאימה לסינון.")).toBeInTheDocument();
    expect(screen.queryByText("עוד לא נוצרה אף מועמדות.")).not.toBeInTheDocument();
    expect(screen.getByText("0 מתוך 2 מועמדויות")).toBeInTheDocument();

    answer([item(), item({ id: "app-2" })]);
    fireEvent.click(screen.getByRole("button", { name: "ניקוי הסינון" }));

    /* Clearing asks the default question again - live work, most recently updated - not
       a client-side reset of rows the screen kept. */
    await waitFor(() => expect(requestedQuery(fetchMock).get("stage")).toBeNull());
    expect(requestedQuery(fetchMock).get("search")).toBeNull();
    expect(requestedQuery(fetchMock).get("activity")).toBe("open");
    expect(await screen.findAllByRole("link", { name: "Acme" })).toHaveLength(2);
  });

  /* Paging is a window on the server's ordering. The screen asks for the next window; it
     does not slice a list it already holds. */
  it("pages through the matched rows and returns to the first page when the query changes", async () => {
    /* One row on the page, sixty matched: the pager exists because the answer says
       there is more of it, not because this page is full. */
    const { fetchMock } = stubList([item()], { matched: 60, stageCounts: { needs_analysis: 60 } });

    renderPage();

    /* The pager only appears once there is a second page to reach. */
    fireEvent.click(await screen.findByRole("button", { name: /הבא/ }));
    await waitFor(() => expect(requestedQuery(fetchMock).get("offset")).toBe("25"));

    /* Changing the question returns to the first page: an offset names a position in an
       ordering, and keeping it across a change to that ordering lands the reader in the
       middle of an answer they just replaced. */
    fireEvent.change(screen.getByLabelText("סדר"), { target: { value: "company" } });
    await waitFor(() => expect(requestedQuery(fetchMock).get("offset")).toBeNull());
  });

  it("reports a failed read rather than an empty list", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          {
            type: "about:blank#internal",
            title: "Internal error",
            status: 500,
            code: "INTERNAL",
            detail: "לא ניתן לקרוא את המועמדויות.",
          },
          500,
        ),
      ),
    );

    renderPage();

    expect(await screen.findByRole("alert")).toHaveTextContent("לא ניתן לקרוא את המועמדויות.");
    expect(screen.queryByText("עוד לא נוצרה אף מועמדות.")).not.toBeInTheDocument();
  });
});
