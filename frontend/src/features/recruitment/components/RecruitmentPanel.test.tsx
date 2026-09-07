import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { applicationDetailQueryKey } from "@/api/applications";
import type { ApplicationDetail, RecruitmentTimelineItem } from "@/api/contracts";
import { formatDate } from "@/utils/formatDateTime";
import { RecruitmentManagerButton } from "./RecruitmentManagerButton";

const statusEvent = (overrides: Partial<RecruitmentTimelineItem> = {}): RecruitmentTimelineItem => ({
  id: "status-1",
  item_type: "status_transition",
  occurred_at: "2026-08-24T07:00:00Z",
  actor_type: "user",
  client: "web",
  from_status: "saved",
  to_status: "recruiter_screen",
  reason: "Recruiter replied",
  metadata: {},
  ...overrides,
});

const detail = (overrides: Partial<ApplicationDetail> = {}): ApplicationDetail => ({
  recruitment_status: "saved",
  allowed_recruitment_transitions: ["withdrawn", "closed"],
  recruitment_timeline: [statusEvent()],
  preparation_state: "ready",
  working_draft_state: "none",
  review_reasons: [],
  stale_reasons: [],
  warnings: [],
  active_job_snapshot_id: "snap-1",
  newer_draft_in_progress: false,
  available_actions: [],
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
    next_action: "Follow up",
    next_action_date: "2026-09-05",
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
  ...overrides,
});

const jsonResponse = (body: unknown, status = 200, contentType = "application/json"): Response =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": contentType },
  });

/* A fresh Response is required for every request because a response body can only be
   consumed once. Keeping the fetch parameters in the signature also preserves Vitest's
   call-tuple types for the request assertions below. */
const emptyJsonFetch = (_input: RequestInfo | URL, _init?: RequestInit): Promise<Response> =>
  Promise.resolve(jsonResponse({}));

const renderPanel = (value: ApplicationDetail = detail()) => {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0, staleTime: Infinity },
      mutations: { retry: false },
    },
  });
  client.setQueryData(applicationDetailQueryKey(value.application.id), value);

  const manager = (next: ApplicationDetail) => (
    <QueryClientProvider client={client}>
      <RecruitmentManagerButton application={next.application} />
    </QueryClientProvider>
  );
  const rendered = render(manager(value));

  return {
    ...rendered,
    rerenderPanel: (next: ApplicationDetail) => {
      client.setQueryData(applicationDetailQueryKey(next.application.id), next);
      rendered.rerender(manager(next));
    },
  };
};

const requestFor = (fetchMock: ReturnType<typeof vi.fn>, suffix: string) =>
  fetchMock.mock.calls.find(([input]) => String(input).endsWith(suffix));

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("RecruitmentManagerButton", () => {
  it("names the first event an opening rather than a transition from a status never held", async () => {
    const value = detail({
      recruitment_timeline: [statusEvent({ from_status: null, to_status: "saved", reason: "application created" })],
    });
    vi.stubGlobal("fetch", vi.fn(emptyJsonFetch));
    renderPanel(value);

    fireEvent.click(screen.getByRole("button", { name: "עדכון סטטוס ומשימות" }));
    expect(screen.getByText("המועמדות נפתחה במצב נשמר")).toBeInTheDocument();
    expect(screen.queryByText(/עבר מ־נשמר ל־נשמר/)).not.toBeInTheDocument();
  });

  it("sends the exact forward transition and next-action choices from one dialog", async () => {
    const value = detail({ recruitment_timeline: [statusEvent({ reason: "application created" })] });
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) =>
      init?.method === undefined && String(input).endsWith("/applications/app-1")
        ? Promise.resolve(jsonResponse(value))
        : emptyJsonFetch(input, init),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderPanel(value);

    expect(screen.queryByLabelText("עדכון שלב")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "עדכון סטטוס ומשימות" }));
    expect(await screen.findByRole("dialog", { name: "ניהול מועמדות: Acme" })).toBeInTheDocument();
    expect(screen.getByText("המועמדות נוצרה")).toBeInTheDocument();
    expect(screen.queryByText("application created")).not.toBeInTheDocument();
    expect(screen.queryByText("לא נקבע צעד הבא")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "שמירת שינויים" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "עדכון" })).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(screen.getByRole("button", { name: "היסטוריה" }));
    expect(screen.getByRole("button", { name: "היסטוריה" })).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(screen.getByRole("button", { name: "עדכון" }));

    fireEvent.change(screen.getByLabelText("עדכון שלב"), { target: { value: "closed" } });
    fireEvent.change(screen.getByLabelText("סיבת השינוי"), {
      target: { value: "Position filled" },
    });
    fireEvent.change(screen.getByLabelText("הפעולה הבאה"), {
      target: { value: " Send portfolio " },
    });
    fireEvent.change(screen.getByLabelText(/תאריך יעד/), { target: { value: "2026-09-10" } });
    fireEvent.click(screen.getByRole("button", { name: "שמירת שינויים" }));

    await waitFor(() => expect(requestFor(fetchMock, "/status")).toBeDefined());
    await waitFor(() =>
      expect(fetchMock.mock.calls.filter(([input]) => String(input).endsWith("/next-action"))).toHaveLength(1),
    );
    const transitionRequest = requestFor(fetchMock, "/status");
    expect(transitionRequest?.[1]).toEqual(expect.objectContaining({ method: "POST" }));
    expect(JSON.parse(String(transitionRequest?.[1]?.body))).toEqual({
      target_status: "closed",
      reason: "Position filled",
    });
    const setRequest = requestFor(fetchMock, "/next-action");
    expect(setRequest?.[1]).toEqual(expect.objectContaining({ method: "PATCH" }));
    expect(JSON.parse(String(setRequest?.[1]?.body))).toEqual({
      next_action: "Send portfolio",
      next_action_date: "2026-09-10",
    });
  });

  it("clears the next action by saving empty fields instead of showing another panel button", async () => {
    const value = detail();
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) =>
      init?.method === undefined && String(input).endsWith("/applications/app-1")
        ? Promise.resolve(jsonResponse(value))
        : emptyJsonFetch(input, init),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderPanel(value);

    expect(screen.queryByRole("button", { name: "הסרת התזכורת" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "עדכון סטטוס ומשימות" }));
    fireEvent.change(await screen.findByLabelText("הפעולה הבאה"), { target: { value: "" } });
    fireEvent.change(screen.getByLabelText(/תאריך יעד/), { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: "שמירת שינויים" }));

    await waitFor(() => expect(requestFor(fetchMock, "/next-action")).toBeDefined());
    const clearRequest = requestFor(fetchMock, "/next-action");
    expect(JSON.parse(String(clearRequest?.[1]?.body))).toEqual({
      next_action: null,
      next_action_date: null,
    });
  });

  it("appends the correction and external submission exactly as entered", async () => {
    const value = detail();
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) =>
      (init?.method ?? "GET") === "GET" && String(input).endsWith("/applications/app-1")
        ? Promise.resolve(jsonResponse(value))
        : emptyJsonFetch(input, init),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderPanel();

    fireEvent.click(screen.getByRole("button", { name: "עדכון סטטוס ומשימות" }));
    const additionalActions = screen.getByText("תיקון היסטוריה").closest("details");
    expect(additionalActions).not.toHaveAttribute("open");
    expect(screen.getByRole("button", { name: "רישום הגשה חיצונית" })).toBeInTheDocument();
    fireEvent.click(screen.getByText("תיקון היסטוריה"));
    expect(additionalActions).toHaveAttribute("open");

    fireEvent.click(screen.getByRole("button", { name: "תיקון אירוע שנרשם" }));
    fireEvent.change(screen.getByLabelText("המצב הנכון"), {
      target: { value: "applied" },
    });
    fireEvent.change(screen.getByLabelText("למה נדרש תיקון"), {
      target: { value: "Wrong status recorded" },
    });
    fireEvent.click(screen.getByRole("button", { name: "הוספת אירוע תיקון" }));

    await waitFor(() => expect(requestFor(fetchMock, "/status-corrections")).toBeDefined());
    const correctionRequest = requestFor(fetchMock, "/status-corrections");
    expect(JSON.parse(String(correctionRequest?.[1]?.body))).toEqual({
      target_status: "applied",
      corrects_event_id: "status-1",
      reason: "Wrong status recorded",
    });

    await waitFor(() => expect(screen.queryByRole("dialog", { name: "תיקון אירוע שנרשם" })).not.toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "רישום הגשה חיצונית" }));
    const submissionDialog = screen.getByRole("dialog", { name: "רישום הגשה שבוצעה מחוץ למערכת" });
    fireEvent.change(within(submissionDialog).getByLabelText("מועד ההגשה"), {
      target: { value: "2026-09-01T12:30" },
    });
    fireEvent.change(within(submissionDialog).getByLabelText(/הערה/), {
      target: { value: " Submitted by email " },
    });
    fireEvent.click(screen.getByRole("button", { name: "רישום ההגשה החיצונית" }));

    await waitFor(() => expect(requestFor(fetchMock, "/external-submissions")).toBeDefined());
    const submissionRequest = requestFor(fetchMock, "/external-submissions");
    expect(JSON.parse(String(submissionRequest?.[1]?.body))).toEqual({
      submitted_at: new Date("2026-09-01T12:30").toISOString(),
      artifact_version_id: null,
      metadata: { note: "Submitted by email" },
    });
  });

  it("formats a next-action calendar date instead of exposing the raw ISO value", () => {
    vi.stubGlobal("fetch", vi.fn(emptyJsonFetch));
    renderPanel(
      detail({
        recruitment_timeline: [
          statusEvent({
            id: "next-1",
            item_type: "next_action",
            next_action: "Send portfolio",
            next_action_date: "2026-09-10",
          }),
        ],
      }),
    );

    fireEvent.click(screen.getByRole("button", { name: "עדכון סטטוס ומשימות" }));
    expect(screen.getByText(new RegExp(formatDate("2026-09-10")))).toBeInTheDocument();
    expect(screen.queryByText(/2026-09-10/)).not.toBeInTheDocument();
  });

  it("uses the recruitment status presentation and initially keeps a long history compact", () => {
    const timeline = Array.from({ length: 6 }, (_, index) =>
      statusEvent({
        id: `next-${index}`,
        item_type: "next_action",
        next_action: `Action ${index}`,
        occurred_at: `2026-08-${String(18 + index).padStart(2, "0")}T07:00:00Z`,
      }),
    );
    vi.stubGlobal("fetch", vi.fn(emptyJsonFetch));
    renderPanel(detail({ recruitment_status: "offer", recruitment_timeline: timeline }));

    fireEvent.click(screen.getByRole("button", { name: "עדכון סטטוס ומשימות" }));
    const summary = screen.getByRole("region", { name: "מצב הגיוס" });
    expect(within(summary).getByText("הצעה").closest("span")).toHaveClass("text-cv-success");
    /* The timeline states what the event was, not the bare value it carried, so the
       newest entry is matched inside its sentence. */
    expect(screen.getByText(/הפעולה הבאה נקבעה: Action 5/)).toBeInTheDocument();
    expect(screen.queryByText(/Action 0/)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "הצגת כל ההיסטוריה (6)" }));
    expect(screen.getByText(/הפעולה הבאה נקבעה: Action 0/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "הצגת פחות אירועים" })).toBeInTheDocument();
  });

  it("surfaces a safe server refusal instead of swallowing it", async () => {
    const value = detail();
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL, init?: RequestInit) =>
        (init?.method ?? "GET") === "GET" && String(input).endsWith("/applications/app-1")
          ? Promise.resolve(jsonResponse(value))
          : Promise.resolve(
              jsonResponse(
                {
                  type: "about:blank#invalid-next-action",
                  title: "Invalid next action",
                  status: 409,
                  code: "INVALID_NEXT_ACTION",
                  detail: "הפעולה השתנתה בשרת. יש לרענן ולנסות שוב.",
                },
                409,
                "application/problem+json",
              ),
            ),
      ),
    );
    renderPanel(value);

    fireEvent.click(screen.getByRole("button", { name: "עדכון סטטוס ומשימות" }));
    fireEvent.change(await screen.findByLabelText("הפעולה הבאה"), { target: { value: "Try again tomorrow" } });
    fireEvent.click(screen.getByRole("button", { name: "שמירת שינויים" }));

    expect(await screen.findByText("Invalid next action")).toBeInTheDocument();
    expect(screen.getByText("הפעולה השתנתה בשרת. יש לרענן ולנסות שוב.")).toBeInTheDocument();
  });

  it("syncs untouched next-action fields from a refreshed projection", async () => {
    vi.stubGlobal("fetch", vi.fn(emptyJsonFetch));
    const { rerenderPanel } = renderPanel();

    fireEvent.click(screen.getByRole("button", { name: "עדכון סטטוס ומשימות" }));
    expect(await screen.findByLabelText("הפעולה הבאה")).toHaveValue("Follow up");

    rerenderPanel(
      detail({
        application: {
          ...detail().application,
          next_action: "Schedule interview",
          next_action_date: "2026-09-12",
        },
      }),
    );

    await waitFor(() => expect(screen.getByLabelText("הפעולה הבאה")).toHaveValue("Schedule interview"));
    expect(screen.getByLabelText(/תאריך יעד/)).toHaveValue("2026-09-12");
    expect(screen.queryByText("פרטי המועמדות השתנו בשרת")).not.toBeInTheDocument();
  });

  it("keeps each dirty next-action field and warns when the server changes underneath it", async () => {
    vi.stubGlobal("fetch", vi.fn(emptyJsonFetch));
    const { rerenderPanel } = renderPanel();

    fireEvent.click(screen.getByRole("button", { name: "עדכון סטטוס ומשימות" }));
    fireEvent.change(await screen.findByLabelText("הפעולה הבאה"), {
      target: { value: "My unsaved follow-up" },
    });
    fireEvent.change(screen.getByLabelText("עדכון שלב"), { target: { value: "closed" } });
    rerenderPanel(
      detail({
        allowed_recruitment_transitions: ["withdrawn"],
        application: {
          ...detail().application,
          next_action: "Server follow-up",
          next_action_date: "2026-09-12",
        },
      }),
    );

    expect(screen.getByLabelText("הפעולה הבאה")).toHaveValue("My unsaved follow-up");
    expect(screen.getByLabelText("עדכון שלב")).toHaveValue("closed");
    await waitFor(() => expect(screen.getByLabelText(/תאריך יעד/)).toHaveValue("2026-09-12"));
    expect(await screen.findByText("פרטי המועמדות השתנו בשרת")).toBeInTheDocument();
  });

  it("preserves a dirty correction choice across projection refreshes", async () => {
    vi.stubGlobal("fetch", vi.fn(emptyJsonFetch));
    const olderEvent = statusEvent({ id: "status-older", to_status: "applied" });
    const currentEvent = statusEvent({ id: "status-current", to_status: "recruiter_screen" });
    const { rerenderPanel } = renderPanel(detail({ recruitment_timeline: [olderEvent, currentEvent] }));

    fireEvent.click(screen.getByRole("button", { name: "עדכון סטטוס ומשימות" }));
    fireEvent.click(screen.getByText("תיקון היסטוריה"));
    fireEvent.click(screen.getByRole("button", { name: "תיקון אירוע שנרשם" }));
    fireEvent.change(screen.getByLabelText("האירוע השגוי"), {
      target: { value: "status-older" },
    });

    const newestEvent = statusEvent({ id: "status-newest", to_status: "interview" });
    rerenderPanel(
      detail({
        allowed_recruitment_transitions: ["withdrawn"],
        recruitment_timeline: [olderEvent, currentEvent, newestEvent],
      }),
    );

    expect(screen.getByLabelText("האירוע השגוי")).toHaveValue("status-older");
    expect(screen.getByText("ציר הזמן השתנה בשרת")).toBeInTheDocument();
  });

  /* Notes are recruitment's, not the Application screen's. This covered a standalone
     notes dialog that no longer exists; the field is one section of the manager now, and
     the precondition it sends is what actually needs guarding - a save that names the
     value the reader was shown, so an edit made elsewhere is refused rather than
     overwritten. */
  it("edits notes with the exact server value as an optimistic precondition", async () => {
    const value = detail({
      application: { ...detail().application, notes: "Referral from a former colleague" },
    });
    const fetchMock = vi.fn((input: RequestInfo | URL, _init?: RequestInit) =>
      Promise.resolve(
        String(input).endsWith("/notes")
          ? jsonResponse({ application_id: "app-1", notes: "Follow up after the holiday", updated_at: "now" })
          : jsonResponse({}),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderPanel(value);

    fireEvent.click(screen.getByRole("button", { name: "עדכון סטטוס ומשימות" }));
    fireEvent.change(screen.getByLabelText("תוכן ההערה"), { target: { value: "Follow up after the holiday" } });
    fireEvent.click(screen.getByRole("button", { name: "שמירת שינויים" }));

    await waitFor(() => expect(requestFor(fetchMock, "/notes")).toBeDefined());
    const request = requestFor(fetchMock, "/notes");
    expect(request?.[1]?.method).toBe("PATCH");
    expect(JSON.parse(String(request?.[1]?.body))).toEqual({
      notes: "Follow up after the holiday",
      expected_notes: "Referral from a former colleague",
    });
  });
});
