import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ApplicationDetail } from "@/api/contracts";
import { HASH, detail, json } from "@/test/fixtures";
import { Toaster } from "@/ui/Toaster";
import { formatDate, formatDateTime } from "@/utils/formatDateTime";
import { ApplicationPage } from "./ApplicationPage";

const hubDetail = (overrides: Partial<ApplicationDetail> = {}): ApplicationDetail =>
  detail({
    recruitment_status: "applied",
    recruitment_timeline: [
      {
        id: "submission-1",
        item_type: "submission",
        submission_type: "external",
        occurred_at: "2026-08-26T09:00:00Z",
        from_status: "saved",
        to_status: "applied",
        reason: "submission recorded",
        metadata: {},
      },
    ],
    ...overrides,
    application: {
      ...detail().application,
      target_role: "Backend Engineer",
      fit_level: "medium",
      next_action: "Approve the draft",
      next_action_date: "2026-08-20",
      ...overrides.application,
    },
  });

const renderHub = (
  value: ApplicationDetail,
  {
    fetchImplementation,
    state,
  }: {
    fetchImplementation?: (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;
    state?: unknown;
  } = {},
) => {
  const fetchMock = vi.fn(fetchImplementation ?? (() => Promise.resolve(json(value))));
  vi.stubGlobal("fetch", fetchMock);
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, refetchInterval: false, gcTime: 0 }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[{ pathname: "/applications/app-1", state }]}>
        <Routes>
          <Route element={<ApplicationPage />} path="/applications/:applicationId" />
          <Route element={<p>Analysis step</p>} path="/applications/:applicationId/analysis" />
          <Route element={<p>The board</p>} path="/" />
        </Routes>
      </MemoryRouter>
      <Toaster />
    </QueryClientProvider>,
  );
  return fetchMock;
};

afterEach(() => {
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

describe("ApplicationPage", () => {
  it("names the record and says where it stands on both axes", async () => {
    renderHub(hubDetail());

    expect(await screen.findByRole("heading", { level: 1, name: "Backend Engineer" })).toBeInTheDocument();
    expect(screen.getByText(/Acme · נקלטה ב־/)).toBeInTheDocument();

    const stage = screen.getByRole("region", { name: "שלב הגיוס" });
    expect(within(stage).getByText("· שלב 2 מתוך 5")).toBeInTheDocument();
    expect(within(stage).getByRole("listitem", { current: "step" })).toHaveTextContent("הוגשה מועמדות");

    const preparation = screen.getByRole("region", { name: "הכנת קורות החיים" });
    expect(within(preparation).getByRole("link", { name: /ניתוח המשרה/ })).toHaveAttribute(
      "href",
      "/applications/app-1/analysis",
    );
    expect(within(preparation).getByRole("link", { name: /טיוטה בעבודה, השלב הנוכחי/ })).toHaveAttribute(
      "href",
      "/applications/app-1/draft",
    );
    /* A step ahead has nothing to open yet. */
    expect(within(preparation).queryByRole("link", { name: /קורות החיים מוכנים/ })).not.toBeInTheDocument();
  });

  it("states a late reminder and the record's facts", async () => {
    renderHub(hubDetail());

    const [reminder] = await screen.findAllByText("Approve the draft");
    expect(reminder?.closest("section")).toHaveTextContent("הפעולה הבאה · באיחור");

    const facts = screen.getByRole("complementary", { name: "פרטי המועמדות" });
    expect(within(facts).getByText("התאמה בינונית")).toBeInTheDocument();
    expect(within(facts).getByText("פתוחה")).toBeInTheDocument();
    expect(within(facts).getByText(formatDateTime("2026-08-26T09:00:00Z", "date"))).toBeInTheDocument();
  });

  it("continues to the screen the work is waiting on", async () => {
    renderHub(hubDetail());

    const commands = await screen.findAllByRole("link", { name: /המשך לעריכת הטיוטה/ });
    for (const command of commands) expect(command).toHaveAttribute("href", "/applications/app-1/draft");
    /* No PDF before the CV is ready: the control is there, disabled, and says why. */
    for (const download of screen.getAllByRole("button", { name: "הורדת קורות החיים, זמינה כשקורות החיים מוכנים" })) {
      expect(download).toBeDisabled();
    }
  });

  it("sends a record waiting on its analysis to the analysis step", async () => {
    renderHub(hubDetail({ preparation_state: "needs_analysis", recommended_action: "analyze", document_id: null }));

    const [command] = await screen.findAllByRole("link", { name: /המשך לניתוח המשרה/ });
    expect(command).toHaveAttribute("href", "/applications/app-1/analysis");
  });

  it("offers the Ready document's PDF", async () => {
    renderHub(hubDetail({ preparation_state: "ready", recommended_action: "submit" }));

    const [download] = await screen.findAllByRole("link", { name: "הורדת קורות החיים כקובץ PDF" });
    expect(download).toHaveAttribute("href", `/api/v1/applications/app-1/document/pdf?v=${HASH}`);
    expect(screen.getAllByRole("link", { name: "פתיחת קורות החיים המוכנים" })[0]).toHaveAttribute(
      "href",
      "/applications/app-1/ready",
    );
  });

  it("hands a just-created application on to the analysis step", async () => {
    renderHub(hubDetail(), { state: { createdApplication: { operationId: "op-1" } } });

    expect(await screen.findByText("Analysis step")).toBeInTheDocument();
  });

  it("closes the record from its menu after confirming", async () => {
    const value = hubDetail();
    const fetchMock = renderHub(value, {
      fetchImplementation: (input, init) =>
        Promise.resolve(
          init?.method === "POST"
            ? json({ application_id: "app-1", current_status: "closed", event_id: "event-1" })
            : json(value),
        ),
    });

    const [menu] = await screen.findAllByRole("button", { name: "פעולות נוספות" });
    fireEvent.click(menu);
    fireEvent.click(screen.getByRole("menuitem", { name: "סגירת המועמדות" }));
    const dialog = screen.getByRole("dialog", { name: "לסגור את המועמדות?" });
    expect(dialog).toHaveTextContent("Acme · Backend Engineer תסומן כסגורה");
    fireEvent.click(within(dialog).getByRole("button", { name: "סגירת המועמדות" }));

    await waitFor(() =>
      expect(fetchMock.mock.calls.some(([input]) => String(input).endsWith("/applications/app-1/close"))).toBe(true),
    );
    expect(await screen.findByText("המועמדות נסגרה")).toBeInTheDocument();
  });

  it("returns to the board once the record is deleted", async () => {
    const value = hubDetail();
    renderHub(value, {
      fetchImplementation: (_input, init) =>
        Promise.resolve(init?.method === "POST" ? json({ application_id: "app-1" }) : json(value)),
    });

    const [menu] = await screen.findAllByRole("button", { name: "פעולות נוספות" });
    fireEvent.click(menu);
    fireEvent.click(screen.getByRole("menuitem", { name: "מחיקת המועמדות" }));
    fireEvent.click(
      within(screen.getByRole("dialog", { name: "למחוק את המועמדות?" })).getByRole("button", {
        name: "מחיקת המועמדות",
      }),
    );

    expect(await screen.findByText("The board")).toBeInTheDocument();
  });

  it("opens the record's details from its menu", async () => {
    renderHub(hubDetail({ application: { ...hubDetail().application, notes: "Referral" } }));

    const [menu] = await screen.findAllByRole("button", { name: "פעולות נוספות" });
    fireEvent.click(menu);
    fireEvent.click(screen.getByRole("menuitem", { name: "פרטי משרה" }));

    const sheet = screen.getByRole("dialog", { name: /פרטי משרה/ });
    expect(within(sheet).getByText("Referral")).toBeInTheDocument();
    expect(within(sheet).getByText(`Approve the draft · ${formatDate("2026-08-20")}`)).toBeInTheDocument();
    expect(within(sheet).getByRole("link", { name: /המשך בהכנה/ })).toHaveAttribute(
      "href",
      "/applications/app-1/draft",
    );
  });

  it("says in its details that nothing is scheduled when nothing is", async () => {
    renderHub(
      hubDetail({
        recommended_action: null,
        application: { ...hubDetail().application, next_action: null, next_action_date: null },
      }),
    );

    const [menu] = await screen.findAllByRole("button", { name: "פעולות נוספות" });
    fireEvent.click(menu);
    fireEvent.click(screen.getByRole("menuitem", { name: "פרטי משרה" }));

    expect(
      within(screen.getByRole("dialog", { name: /פרטי משרה/ })).getByText("אין פעולה מתוזמנת כעת"),
    ).toBeInTheDocument();
  });

  /* A closed process is on no rung of the bar, so the card says it closed in words. */
  it("states a closed recruitment status in words beside its exact name", async () => {
    renderHub(hubDetail({ recruitment_status: "rejected" }));

    expect((await screen.findAllByText("לא התקבל")).length).toBeGreaterThan(0);
    expect(screen.getByText("· תהליך הגיוס נסגר")).toBeInTheDocument();
    expect(screen.queryByText(/הבא:/)).not.toBeInTheDocument();
  });

  it("edits the posting from the record's menu, naming the text it replaces", async () => {
    const value = hubDetail();
    const fetchMock = renderHub(value, {
      fetchImplementation: (input, init) =>
        Promise.resolve(
          String(input).endsWith("/job-text") && init?.method === "PATCH"
            ? json({ application_id: "app-1", job_text_hash: "d".repeat(64) })
            : json(value),
        ),
    });

    const [menu] = await screen.findAllByRole("button", { name: "פעולות נוספות" });
    fireEvent.click(menu);
    fireEvent.click(screen.getByRole("menuitem", { name: "עריכת נוסח המשרה" }));

    const dialog = screen.getByRole("dialog", { name: "עריכת נוסח המשרה" });
    const text = within(dialog).getByRole("textbox", { name: "טקסט המשרה" });
    expect(text).toHaveValue("Engineer");
    /* An unchanged posting is refused before any request. */
    fireEvent.click(within(dialog).getByRole("button", { name: "שמירת הנוסח" }));
    expect(await within(dialog).findByText(/זהים לנוסח השמור/)).toBeInTheDocument();

    fireEvent.change(text, { target: { value: "Senior Engineer" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "שמירת הנוסח" }));

    expect(await screen.findByText("נוסח המשרה עודכן")).toBeInTheDocument();
    const patch = fetchMock.mock.calls.find(
      ([input, init]) => String(input).endsWith("/job-text") && init?.method === "PATCH",
    );
    expect(JSON.parse(String(patch?.[1]?.body))).toEqual({
      job_text: "Senior Engineer",
      source_url: null,
      expected_job_text_hash: value.job_posting.job_text_hash,
    });
  });

  it("offers no posting edit once a Submission locked the text", async () => {
    renderHub(hubDetail({ job_posting: { ...hubDetail().job_posting, locked: true } }));

    const [menu] = await screen.findAllByRole("button", { name: "פעולות נוספות" });
    fireEvent.click(menu);
    expect(screen.getByRole("menuitem", { name: "פרטי משרה" })).toBeInTheDocument();
    expect(screen.queryByRole("menuitem", { name: "עריכת נוסח המשרה" })).not.toBeInTheDocument();
  });

  it("offers nothing against a deleted record", async () => {
    renderHub(hubDetail({ application: { ...hubDetail().application, deleted_at: "2026-08-30T00:00:00Z" } }));

    expect(await screen.findByRole("alert")).toHaveTextContent("המועמדות הזו נמחקה");
    expect(screen.queryByRole("button", { name: "פעולות נוספות" })).not.toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "הכנת קורות החיים" })).not.toBeInTheDocument();
  });
});
