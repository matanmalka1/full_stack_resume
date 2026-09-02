import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useNavigate } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { applicationDetailQueryOptions, applicationListQueryOptions } from "../api/applications";
import type { ApplicationDetail, ApplicationListItem, ApplicationListResponse, Reason } from "../api/contracts";
import { settingsQueryKey } from "../api/settings";
import { ApplicationListPage } from "./ApplicationListPage";

const item = (overrides: Partial<ApplicationListItem> = {}): ApplicationListItem => {
  const result = {
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
  } as ApplicationListItem;
  result.is_closed =
    overrides.is_closed ??
    (result.terminal_outcome != null || ["rejected", "withdrawn", "closed"].includes(result.recruitment_status));
  return result;
};

const reason = (code: string): Reason => ({
  code,
  message: `plain sentence for ${code}`,
  entity_references: {},
  allowed_resolution_actions: [],
});

const jsonResponse = (body: unknown, status = 200, extraHeaders: Record<string, string> = {}): Response =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...extraHeaders },
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
  presetCounts?: Record<string, number>;
  recruitmentStatusCounts?: Record<string, number>;
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
  const recruitment_status_counts =
    counts.recruitmentStatusCounts ??
    items.reduce<Record<string, number>>((totals, item) => {
      totals[item.recruitment_status] = (totals[item.recruitment_status] ?? 0) + 1;
      return totals;
    }, {});
  const preset_counts = counts.presetCounts ?? {
    all: matched,
    active_interviews: items.filter((entry) =>
      ["recruiter_screen", "interview", "assignment", "final_stage", "offer"].includes(entry.recruitment_status),
    ).length,
    ready_to_send: items.filter((entry) => entry.latest_ready_revision_id != null).length,
    needs_attention: items.filter(
      (entry) => entry.review_reasons.length > 0 || entry.stale_reasons.length > 0 || entry.warnings.length > 0,
    ).length,
  };

  return {
    items,
    matched,
    total: counts.total ?? matched,
    limit: 25,
    offset: 0,
    preset_counts,
    recruitment_status_counts,
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

    expect(await screen.findByRole("heading", { name: "לוח מועמדויות ומעקב גיוס" })).toBeInTheDocument();
    expect(screen.getByText("בדיקת עובדות לפני אישור")).toBeInTheDocument();
    expect(await screen.findByText("2 מועמדויות במערכת")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "קליטת משרה חדשה" })).toHaveAttribute("href", "/applications/new");
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
    expect(board.getByRole("button", { name: "עדכון סטטוס ומשימות עבור Acme" })).toBeInTheDocument();
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
    expect(within(screen.getByRole("region", { name: "מוקד פעולות" })).getByRole("link")).toHaveAttribute(
      "href",
      "/applications/app-1/preparation",
    );
  });

  it("links a projected ready revision from the action hub", async () => {
    stubList([item({ latest_ready_revision_id: "revision-1", preparation_state: "ready" })]);

    renderPage();

    const hub = await screen.findByRole("region", { name: "מוקד פעולות" });
    expect(within(hub).getByRole("link", { name: /פתיחת הגרסה המוכנה/ })).toHaveAttribute(
      "href",
      "/revisions/revision-1",
    );
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
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByRole("button", { name: "תצוגת כרטיסים" }));
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "Acme" })).toHaveLength(1);
    expect(screen.getAllByRole("link", { name: "Binat" })).toHaveLength(1);
    expect(screen.getAllByText("Follow up")).toHaveLength(2);
    expect(screen.getAllByText(/באיחור/)).toHaveLength(2);
    expect(screen.getByText(/Referral from Dana/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "עדכון סטטוס ומשימות עבור Acme" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "תצוגת שלבי גיוס" }));
    const pipeline = screen.getByRole("list", { name: "מועמדויות לפי שלב גיוס" });
    expect(within(pipeline).getByRole("heading", { name: "נשמר" })).toBeInTheDocument();
    expect(within(pipeline).getByRole("heading", { name: "ראיונות ומטלות" })).toBeInTheDocument();
    expect(within(pipeline).getByRole("heading", { name: "תהליכים סגורים" })).toBeInTheDocument();
    expect(within(pipeline).getAllByText("אין מועמדויות בשלב זה")).toHaveLength(3);
    expect(within(pipeline).getByRole("link", { name: "Acme" })).toHaveAttribute("href", "/applications/app-1");
    expect(within(pipeline).getAllByText("ממתין לניתוח המשרה")).toHaveLength(3);
    expect(within(pipeline).getByText("Follow up")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("summarizes due work from the visible server projection and clears only its reminder", async () => {
    const { fetchMock } = stubList([item({ next_action: "Follow up with recruiter", next_action_date: "2020-01-01" })]);

    renderPage();

    const hub = await screen.findByRole("region", { name: "מוקד פעולות" });
    expect(within(hub).getByText("Follow up with recruiter")).toBeInTheDocument();
    expect(within(hub).getByText(/מתוך המועמדויות המוצגות/)).toBeInTheDocument();
    fireEvent.click(within(hub).getByRole("button", { name: "הסרת תזכורת" }));

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/v1/applications/app-1/next-action",
        expect.objectContaining({
          body: JSON.stringify({ next_action: null, next_action_date: null }),
          method: "PATCH",
        }),
      ),
    );
  });

  it("loads preset metrics from authoritative server counts and applies a selected metric", async () => {
    const countsByPreset: Record<string, number> = {
      all: 9,
      active_interviews: 3,
      ready_to_send: 2,
      needs_attention: 4,
    };
    const countsByRecruitmentStatuses: Record<string, number> = {
      saved: 5,
      applied: 4,
      recruiter_screen: 3,
      assignment: 1,
      interview: 1,
      accepted: 0,
      final_stage: 1,
      offer: 0,
    };
    const fetchMock = vi.fn(async (url: unknown) => {
      const requestUrl = new URL(String(url), "http://localhost");
      const preset = requestUrl.searchParams.get("preset");
      const matched = preset == null ? 9 : (countsByPreset[preset] ?? 0);

      return jsonResponse(
        listBody([item()], {
          matched,
          presetCounts: countsByPreset,
          recruitmentStatusCounts: countsByRecruitmentStatuses,
          total: 9,
        }),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    renderPage();

    const interviews = await screen.findByRole("button", { name: /ראיונות פעילים/ });
    const ready = screen.getByRole("button", { name: /מסמכים מוכנים לשליחה/ });
    const attention = screen.getByRole("button", { name: /דורש טיפול/ });
    /* The buttons render before the single list query settles, so their counts start as
       placeholders. The resolved response carries all authoritative facets together. */
    expect(await within(interviews).findByText("3")).toBeInTheDocument();
    expect(await within(ready).findByText("2")).toBeInTheDocument();
    expect(await within(attention).findByText("4")).toBeInTheDocument();
    const interviewStage = screen.getByRole("button", { name: /ראיונות ומטלות/ });
    expect(within(interviewStage).getByText("2")).toBeInTheDocument();

    fireEvent.click(interviewStage);

    await waitFor(() => expect(interviewStage).toHaveAttribute("aria-pressed", "true"));
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([url]) => {
          const requestUrl = new URL(String(url), "http://localhost");
          return (
            requestUrl.searchParams.get("limit") === "25" &&
            requestUrl.searchParams.getAll("recruitment_status").sort().join(",") === "assignment,interview"
          );
        }),
      ).toBe(true),
    );

    fireEvent.click(ready);

    await waitFor(() => expect(ready).toHaveAttribute("aria-pressed", "true"));
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([url]) => {
          const value = String(url);
          return value.includes("limit=25") && value.includes("preset=ready_to_send");
        }),
      ).toBe(true),
    );
  });

  it("requires explicit acknowledgement before quick intake creates a duplicate", async () => {
    const fetchMock = vi.fn(async (url: unknown, options?: RequestInit) => {
      const path = String(url);

      if (path === "/api/v1/applications/duplicate-check") {
        return jsonResponse({
          matches: [
            {
              application_id: "app-existing",
              company: "Acme",
              target_role: "Backend Engineer",
              matched_on: ["company_title"],
            },
          ],
        });
      }
      if (path === "/api/v1/applications" && options?.method === "POST") {
        return jsonResponse({ application_id: "app-new", job_snapshot_id: "snapshot-new", duplicate_matches: [] }, 201);
      }
      if (path === "/api/v1/applications/app-new/analyses") {
        return jsonResponse(
          {
            id: "operation-new",
            application_id: "app-new",
            operation_type: "analyze_job",
            status: "queued",
            is_terminal: false,
            phase: "queued",
            message: "",
            created_at: "2026-09-02T07:00:00Z",
            outputs: [],
            available_actions: ["cancel"],
          },
          202,
          { Location: "/api/v1/operations/operation-new" },
        );
      }

      return jsonResponse(listBody([item()]));
    });
    vi.stubGlobal("fetch", fetchMock);
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    queryClient.setQueryData(settingsQueryKey, {
      settings: {
        default_execution_mode: "deterministic",
        provider_configured: false,
        ai_enabled: false,
      },
      etag: null,
    });

    renderPage({ queryClient });

    fireEvent.click(await screen.findByRole("button", { name: "קליטה מהירה" }));
    expect(screen.getByRole("dialog", { name: "קליטת משרה מהירה" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("שם החברה"), { target: { value: " Acme " } });
    fireEvent.change(screen.getByLabelText("תפקיד היעד"), { target: { value: "Backend Engineer" } });
    fireEvent.change(screen.getByLabelText("טקסט המשרה"), { target: { value: "Exact job text" } });
    fireEvent.click(screen.getByRole("button", { name: "קליטת משרה" }));

    expect(await screen.findByText("נמצאה מועמדות דומה")).toBeInTheDocument();
    expect(
      fetchMock.mock.calls.filter(
        ([url, options]) => String(url) === "/api/v1/applications" && options?.method === "POST",
      ),
    ).toHaveLength(0);

    fireEvent.click(screen.getByRole("button", { name: "יצירת מועמדות נוספת" }));

    expect(await screen.findByRole("heading", { name: "מסך המועמדות" })).toBeInTheDocument();
    const createCall = fetchMock.mock.calls.find(
      ([url, options]) => String(url) === "/api/v1/applications" && options?.method === "POST",
    );
    expect(JSON.parse(String(createCall?.[1]?.body))).toMatchObject({
      acknowledged_duplicates: true,
      company: "Acme",
      job_text: "Exact job text",
      target_role: "Backend Engineer",
    });
  });

  it("loads allowed transitions before quick status updates and sends each changed field to its owner", async () => {
    const calls: { body: unknown; method: string; path: string }[] = [];
    const fetchMock = vi.fn(async (url: unknown, options?: RequestInit) => {
      const path = String(url);
      const method = options?.method ?? "GET";
      calls.push({
        body: typeof options?.body === "string" ? JSON.parse(options.body) : undefined,
        method,
        path,
      });

      if (path === "/api/v1/applications/app-1") {
        return jsonResponse(detailBody());
      }
      if (path === "/api/v1/applications/app-1/status") {
        return jsonResponse({ application_id: "app-1", current_status: "closed", event_id: "event-status" });
      }
      if (path === "/api/v1/applications/app-1/next-action") {
        return jsonResponse({ application_id: "app-1", current_status: "closed", event_id: "event-action" });
      }
      if (path === "/api/v1/applications/app-1/notes") {
        return jsonResponse({ application_id: "app-1", notes: "Interview notes" });
      }
      return jsonResponse(listBody([item()]));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: "עדכון סטטוס ומשימות עבור Acme" }));
    expect(await screen.findByRole("dialog", { name: "עדכון סטטוס ומשימות: Acme" })).toBeInTheDocument();
    /* The dialog opens before its own detail fetch settles - it shows a loading line
       until then - so the form's fields exist only once that resolves. */
    const status = await screen.findByLabelText(/מעבר לשלב הבא/);
    expect(within(status).getByRole("option", { name: "סגור" })).toBeInTheDocument();
    expect(within(status).queryByRole("option", { name: "הוגש" })).not.toBeInTheDocument();

    fireEvent.change(status, { target: { value: "closed" } });
    fireEvent.change(screen.getByLabelText(/הצעד הבא/), { target: { value: "Send follow-up" } });
    fireEvent.change(screen.getByLabelText(/תאריך יעד/), { target: { value: "2026-09-10" } });
    fireEvent.change(screen.getByLabelText(/הערות/), { target: { value: "Interview notes" } });
    fireEvent.click(screen.getByRole("button", { name: "שמירת שינויים" }));

    await waitFor(() =>
      expect(screen.queryByRole("dialog", { name: "עדכון סטטוס ומשימות: Acme" })).not.toBeInTheDocument(),
    );
    expect(calls).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          body: { reason: "", target_status: "closed" },
          method: "POST",
          path: "/api/v1/applications/app-1/status",
        }),
        expect.objectContaining({
          body: { next_action: "Send follow-up", next_action_date: "2026-09-10" },
          method: "PATCH",
          path: "/api/v1/applications/app-1/next-action",
        }),
        expect.objectContaining({
          body: { expected_notes: "", notes: "Interview notes" },
          method: "PATCH",
          path: "/api/v1/applications/app-1/notes",
        }),
      ]),
    );
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

  /* The inner findByRole below already budgets 5s for the post-navigation query under
     load; the test's own timeout must exceed that budget, or the outer clock can end the
     test before the inner wait it deliberately allows gets the chance to. */
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
  }, 10_000);

  it("updates the field from browser history immediately and delays only the server read", async () => {
    const { fetchMock } = stubList([item()]);

    renderPage({
      entries: ["/?search=first", "/?search=second"],
      initialIndex: 1,
      withHistoryBack: true,
    });

    expect(await screen.findByDisplayValue("second")).toBeInTheDocument();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));

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
