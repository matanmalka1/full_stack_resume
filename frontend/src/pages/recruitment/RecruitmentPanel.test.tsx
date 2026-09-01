import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ApplicationDetail, RecruitmentTimelineItem } from "../../api/contracts";
import { RecruitmentPanel } from "./RecruitmentPanel";

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
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });

  const panel = (next: ApplicationDetail) => (
    <QueryClientProvider client={client}>
      <RecruitmentPanel detail={next} />
    </QueryClientProvider>
  );
  const rendered = render(panel(value));

  return {
    ...rendered,
    rerenderPanel: (next: ApplicationDetail) => rendered.rerender(panel(next)),
  };
};

const requestFor = (fetchMock: ReturnType<typeof vi.fn>, suffix: string) =>
  fetchMock.mock.calls.find(([input]) => String(input).endsWith(suffix));

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("RecruitmentPanel", () => {
  it("sends the exact forward transition and next-action choices, including a clear", async () => {
    const fetchMock = vi.fn(emptyJsonFetch);
    vi.stubGlobal("fetch", fetchMock);
    renderPanel(detail({ recruitment_timeline: [statusEvent({ reason: "application created" })] }));

    expect(screen.getByText("המועמדות נוצרה")).toBeInTheDocument();
    expect(screen.queryByText("application created")).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("השלב הבא"), { target: { value: "closed" } });
    fireEvent.change(screen.getByLabelText("סיבה (רשות)"), {
      target: { value: "Position filled" },
    });
    fireEvent.click(screen.getByRole("button", { name: "שמירת השלב" }));

    await waitFor(() => expect(requestFor(fetchMock, "/status")).toBeDefined());
    const transitionRequest = requestFor(fetchMock, "/status");
    expect(transitionRequest?.[1]).toEqual(expect.objectContaining({ method: "POST" }));
    expect(JSON.parse(String(transitionRequest?.[1]?.body))).toEqual({
      target_status: "closed",
      reason: "Position filled",
    });

    fireEvent.change(screen.getByLabelText("מה לעשות"), {
      target: { value: " Send portfolio " },
    });
    fireEvent.change(screen.getByLabelText("תאריך"), { target: { value: "2026-09-10" } });
    fireEvent.click(screen.getByRole("button", { name: "שמירת הפעולה" }));

    await waitFor(() =>
      expect(fetchMock.mock.calls.filter(([input]) => String(input).endsWith("/next-action"))).toHaveLength(1),
    );
    const setRequest = requestFor(fetchMock, "/next-action");
    expect(setRequest?.[1]).toEqual(expect.objectContaining({ method: "PATCH" }));
    expect(JSON.parse(String(setRequest?.[1]?.body))).toEqual({
      next_action: "Send portfolio",
      next_action_date: "2026-09-10",
    });

    await waitFor(() => expect(screen.getByRole("button", { name: "סימון כהושלמה" })).toBeEnabled());
    fireEvent.click(screen.getByRole("button", { name: "סימון כהושלמה" }));

    await waitFor(() =>
      expect(fetchMock.mock.calls.filter(([input]) => String(input).endsWith("/next-action"))).toHaveLength(2),
    );
    const clearRequest = fetchMock.mock.calls.filter(([input]) => String(input).endsWith("/next-action"))[1];
    expect(JSON.parse(String(clearRequest?.[1]?.body))).toEqual({
      next_action: null,
      next_action_date: null,
    });
  });

  it("appends the correction and external submission exactly as entered", async () => {
    const fetchMock = vi.fn(emptyJsonFetch);
    vi.stubGlobal("fetch", fetchMock);
    renderPanel();

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
    fireEvent.change(screen.getByLabelText("מועד ההגשה"), {
      target: { value: "2026-09-01T12:30" },
    });
    fireEvent.change(screen.getByLabelText("הערה (רשות)"), {
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

  it("surfaces a safe server refusal instead of swallowing it", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
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
    );
    renderPanel();

    fireEvent.click(screen.getByRole("button", { name: "שמירת הפעולה" }));

    expect(await screen.findByText("Invalid next action")).toBeInTheDocument();
    expect(screen.getByText("הפעולה השתנתה בשרת. יש לרענן ולנסות שוב.")).toBeInTheDocument();
  });

  it("syncs untouched next-action fields from a refreshed projection", async () => {
    vi.stubGlobal("fetch", vi.fn(emptyJsonFetch));
    const { rerenderPanel } = renderPanel();

    rerenderPanel(
      detail({
        application: {
          ...detail().application,
          next_action: "Schedule interview",
          next_action_date: "2026-09-12",
        },
      }),
    );

    await waitFor(() => expect(screen.getByLabelText("מה לעשות")).toHaveValue("Schedule interview"));
    expect(screen.getByLabelText("תאריך")).toHaveValue("2026-09-12");
    expect(screen.queryByText("הפעולה הבאה השתנתה בשרת")).not.toBeInTheDocument();
  });

  it("keeps each dirty next-action field and warns when the server changes underneath it", async () => {
    vi.stubGlobal("fetch", vi.fn(emptyJsonFetch));
    const { rerenderPanel } = renderPanel();

    fireEvent.change(screen.getByLabelText("מה לעשות"), {
      target: { value: "My unsaved follow-up" },
    });
    rerenderPanel(
      detail({
        application: {
          ...detail().application,
          next_action: "Server follow-up",
          next_action_date: "2026-09-12",
        },
      }),
    );

    expect(screen.getByLabelText("מה לעשות")).toHaveValue("My unsaved follow-up");
    await waitFor(() => expect(screen.getByLabelText("תאריך")).toHaveValue("2026-09-12"));
    expect(await screen.findByText("הפעולה הבאה השתנתה בשרת")).toBeInTheDocument();
  });

  it("preserves dirty transition and correction choices across projection refreshes", async () => {
    vi.stubGlobal("fetch", vi.fn(emptyJsonFetch));
    const olderEvent = statusEvent({ id: "status-older", to_status: "applied" });
    const currentEvent = statusEvent({ id: "status-current", to_status: "recruiter_screen" });
    const { rerenderPanel } = renderPanel(detail({ recruitment_timeline: [olderEvent, currentEvent] }));

    fireEvent.change(screen.getByLabelText("השלב הבא"), { target: { value: "closed" } });
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

    expect(screen.getByLabelText("השלב הבא")).toHaveValue("closed");
    expect(screen.getByLabelText("האירוע השגוי")).toHaveValue("status-older");
    expect(await screen.findByText("אפשרויות המעבר השתנו בשרת")).toBeInTheDocument();
    expect(screen.getByText("ציר הזמן השתנה בשרת")).toBeInTheDocument();
  });
});
