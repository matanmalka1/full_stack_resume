import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Operation } from "../api/contracts";
import { OperationPage } from "./OperationPage";

const operation = (overrides: Partial<Operation> = {}): Operation => ({
  id: "op-1",
  application_id: "app-1",
  operation_type: "analyze_job",
  status: "running",
  is_terminal: false,
  phase: "executing",
  message: "",
  created_at: "2026-08-24T07:00:00Z",
  outputs: [],
  available_actions: ["cancel"],
  ...overrides,
});

const jsonResponse = (body: unknown, status = 200): Response =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });

/* The screen reads the Application projection for every Operation, not only a succeeded
   analyze: that read is what lets a running Operation publish its workflow stage. It is
   a background read that answers no assertion here, so these tests route by URL rather
   than by call position - a positional queue hands the projection whichever response the
   next assertion was waiting for. */
const projectionUrl = "/api/v1/applications/app-1";
const projection = {
  application: { id: "app-1" },
  review_reasons: [],
  working_draft_state: "none",
  active_operation: null,
  active_analysis_id: null,
  active_selection_plan_id: null,
};

const postCalls = (fetchMock: { mock: { calls: unknown[][] } }) =>
  fetchMock.mock.calls.filter((call) => (call[1] as RequestInit | undefined)?.method === "POST");

/* Retries and refetching are off inside the test client: the poll interval is covered by
   its own unit tests, and a live timer here would make every assertion racy. */
const renderPage = (children: ReactNode) => {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false, refetchInterval: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });

  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/operations/op-1"]}>
        <Routes>
          <Route element={children} path="/operations/:operationId" />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
};

afterEach(() => {
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

describe("OperationPage", () => {
  /* The automatic draft continuation is not asserted here any more: it moved to the
     Application screen with the flow, and its test moved with it. This route is no longer
     on the workflow path - queueing reports in place - so running the chain here too
     would let one analyze Operation queue two drafts. */
  it("names the operation in the heading and reports status and phase separately", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(operation())));

    renderPage(<OperationPage />);

    /* Matched by accessible name rather than by finding the heading and then reading it:
       the heading is on screen from the first render carrying its loading text, so a
       bare findByRole resolves before the Operation arrives. */
    expect(
      await screen.findByRole("heading", { level: 1, name: "ניתוח המשרה" }),
    ).toBeInTheDocument();
    expect(screen.getByText("מתבצעת")).toBeInTheDocument();
    expect(screen.getByText("בביצוע")).toBeInTheDocument();
  });


  it("lets a backend message pick its own direction inside the RTL shell", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(operation({ message: "Analyzing job text" }))),
    );

    renderPage(<OperationPage />);

    expect(await screen.findByText("Analyzing job text")).toHaveAttribute("dir", "auto");
  });

  it("presents a safe failure detail as a blocker rather than a crash", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          operation({
            status: "failed",
            is_terminal: true,
            phase: "executing",
            failure_code: "PROVIDER_TIMEOUT",
            safe_failure_detail: "The provider did not answer in time.",
            available_actions: ["retry"],
          }),
        ),
      ),
    );

    renderPage(<OperationPage />);

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("חסימה");
    expect(alert).toHaveTextContent("The provider did not answer in time.");
    expect(alert).toHaveTextContent("לא בוצע מעבר אוטומטי למצב דטרמיניסטי");
    expect(
      screen.queryByRole("button", { name: "המשך במצב דטרמיניסטי" }),
    ).not.toBeInTheDocument();
    expect(screen.getByText("נכשלה")).toBeInTheDocument();
  });

  it("sends SOURCE_CHANGED back to the current application context without hiding retry", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          operation({
            status: "failed",
            is_terminal: true,
            phase: "completed",
            failure_code: "SOURCE_CHANGED",
            safe_failure_detail: "Operation sources changed.",
            available_actions: ["retry"],
          }),
        ),
      ),
    );

    renderPage(<OperationPage />);

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("המקור השתנה בזמן הפעולה");
    expect(alert).toHaveTextContent("התוצאה לא הופעלה והמצב הקיים נשמר");
    expect(screen.getByRole("link", { name: "חזרה למועמדות" })).toHaveClass("bg-cv-accent");
    expect(screen.getByRole("button", { name: "ניסיון חוזר" })).toBeInTheDocument();
  });

  it("explains best-effort cancellation while the Operation is still running", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          operation({
            cancellation_requested_at: "2026-08-24T07:01:00Z",
            available_actions: [],
          }),
        ),
      ),
    );

    renderPage(<OperationPage />);

    expect(
      await screen.findByText("בקשת הביטול התקבלה", { selector: "span" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("בקשת הביטול התקבלה");
    expect(screen.getByText(/התוצאה שלה לא תופעל/)).toBeInTheDocument();
  });

  it("states that a completed cancellation activated no new result", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          operation({
            status: "cancelled",
            is_terminal: true,
            phase: "completed",
            available_actions: ["retry"],
          }),
        ),
      ),
    );

    renderPage(<OperationPage />);

    expect(await screen.findByText("בוטלה")).toBeInTheDocument();
    expect(screen.getByText(/לא הופעלה תוצאה חדשה/)).toBeInTheDocument();
  });

  it("explains a Problem Details failure with its safe detail", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          {
            type: "about:blank#unknown-record",
            title: "Operation not found",
            status: 404,
            code: "UNKNOWN_RECORD",
            detail: "אין פעולה במזהה הזה.",
          },
          404,
        ),
      ),
    );

    renderPage(<OperationPage />);

    expect(await screen.findByRole("alert")).toHaveTextContent("אין פעולה במזהה הזה.");
  });

  /* The regression this file exists for: a transport error used to render nothing at all.
     What it renders is no longer the screen's generic fallback - the client now turns an
     unreachable server into an ApiProblem of its own, so the alert names the transport
     failure specifically. The assertion follows that: what is guarded is that a failure
     with no Problem Details from the server still reaches the user as a safe, readable
     alert rather than as silence. */
  it("shows a safe alert when the request never reached the server", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));

    renderPage(<OperationPage />);

    expect(await screen.findByRole("alert")).toHaveTextContent("לא ניתן להגיע לשרת");
  });

  it("cancels only when the backend exposes the action and keeps the returned state", async () => {
    const cancelled = operation({
      status: "cancelled",
      is_terminal: true,
      phase: "completed",
      available_actions: ["retry"],
    });
    let cancelRequested = false;
    const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
      const url = String(input);
      if (init?.method === "POST") {
        cancelRequested = true;
        return Promise.resolve(jsonResponse(cancelled));
      }
      if (url === projectionUrl) {
        return Promise.resolve(jsonResponse(projection));
      }
      return Promise.resolve(jsonResponse(cancelRequested ? cancelled : operation()));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderPage(<OperationPage />);
    fireEvent.click(await screen.findByRole("button", { name: "ביטול הפעולה" }));

    expect(await screen.findByRole("button", { name: "ניסיון חוזר" })).toBeInTheDocument();
    expect(postCalls(fetchMock)).toHaveLength(1);
    expect(postCalls(fetchMock)[0]?.[0]).toBe("/api/v1/operations/op-1/cancel");
  });

  it("follows a retry to the new Operation named by the accepted response", async () => {
    const terminal = operation({
      status: "failed",
      is_terminal: true,
      phase: "completed",
      available_actions: ["retry"],
    });
    const queued = operation({
      id: "op-2",
      status: "queued",
      phase: "queued",
      retry_of_operation_id: "op-1",
      available_actions: ["cancel"],
    });
    const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
      const url = String(input);
      if (init?.method === "POST") {
        return Promise.resolve(
          new Response(JSON.stringify(queued), {
            status: 202,
            headers: {
              "Content-Type": "application/json",
              Location: "/api/v1/operations/op-2",
            },
          }),
        );
      }
      if (url === projectionUrl) {
        return Promise.resolve(jsonResponse(projection));
      }
      return Promise.resolve(jsonResponse(url.endsWith("op-2") ? queued : terminal));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderPage(<OperationPage />);
    fireEvent.click(await screen.findByRole("button", { name: "ניסיון חוזר" }));

    expect(await screen.findByRole("button", { name: "ביטול הפעולה" })).toBeInTheDocument();
    await waitFor(() => expect(postCalls(fetchMock)).toHaveLength(1));
    const retryRequest = postCalls(fetchMock)[0];
    expect(retryRequest?.[0]).toBe("/api/v1/operations/op-1/retry");
    expect(retryRequest?.[1]).toEqual(
      expect.objectContaining({
        method: "POST",
        headers: expect.any(Headers),
      }),
    );
    expect(((retryRequest?.[1] as RequestInit).headers as Headers).get("Idempotency-Key")).not.toBeNull();
  });

  it("keeps the safe Operation visible when retry is refused with a conflict", async () => {
    const conflictResponse = () =>
      jsonResponse(
        {
          type: "about:blank#state-conflict",
          title: "State conflict",
          status: 409,
          code: "STATE_CONFLICT",
          detail: "לא ניתן ליצור ניסיון חוזר במצב הנוכחי.",
        },
        409,
      );
    const failed = operation({
      status: "failed",
      is_terminal: true,
      phase: "completed",
      available_actions: ["retry"],
    });
    const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
      const url = String(input);
      if (init?.method === "POST") {
        return Promise.resolve(conflictResponse());
      }
      if (url === projectionUrl) {
        return Promise.resolve(jsonResponse(projection));
      }
      return Promise.resolve(jsonResponse(failed));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderPage(<OperationPage />);
    fireEvent.click(await screen.findByRole("button", { name: "ניסיון חוזר" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "לא ניתן ליצור ניסיון חוזר במצב הנוכחי.",
    );
    expect(screen.getByText("נכשלה")).toBeInTheDocument();

    const keyOf = (call: unknown[] | undefined) =>
      ((call?.[1] as RequestInit | undefined)?.headers as Headers | undefined)?.get(
        "Idempotency-Key",
      );
    const firstKey = keyOf(postCalls(fetchMock)[0]);
    expect(firstKey).not.toBeNull();

    /* A refused retry is the same command retried, so it must carry the key it carried
       the first time: a fresh one would let the backend queue two attempts. */
    fireEvent.click(screen.getByRole("button", { name: "ניסיון חוזר" }));
    await waitFor(() => expect(postCalls(fetchMock)).toHaveLength(2));
    expect(keyOf(postCalls(fetchMock)[1])).toBe(firstKey);
  });

  it("does not invent an action when the backend exposes none", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          operation({
            status: "running",
            cancellation_requested_at: "2026-08-24T07:01:00Z",
            available_actions: [],
          }),
        ),
      ),
    );

    renderPage(<OperationPage />);

    expect(await screen.findByText("מתבצעת")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "ביטול הפעולה" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "ניסיון חוזר" })).not.toBeInTheDocument();
    /* The way back belongs to a finished Operation. While one is still running, leaving
       is the browser's job, not an action this screen offers. */
    expect(screen.queryByRole("link", { name: "חזרה למועמדות" })).not.toBeInTheDocument();
  });

  /* A finished Operation used to be a dead end. What follows it depends on the
     application projection (A.1), so the screen hands the user back to the screen that
     owns it instead of routing by operation_type. */
  it("hands a finished Operation back to the application that owns it", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          operation({
            status: "succeeded",
            is_terminal: true,
            phase: "completed",
            available_actions: ["retry"],
          }),
        ),
      ),
    );

    renderPage(<OperationPage />);

    expect(await screen.findByRole("link", { name: "חזרה למועמדות" })).toHaveAttribute(
      "href",
      "/applications/app-1",
    );
    /* `succeeded` and `completed` are both "הושלמה"; this is the one fixture that holds
       both at once. The screen printed that word four times over — heading, badge, phase,
       and both halves of the announcement — saying it repeatedly and never saying which
       operation had finished. */
    expect(screen.getAllByText("הושלמה")).toHaveLength(1);
    /* Retry is offered on a succeeded Operation because the backend offers it, but it is
       not the recommendation: emphasizing it puts the loudest control on the screen on
       re-running work that just worked. */
    expect(screen.getByRole("link", { name: "חזרה למועמדות" })).toHaveClass("bg-cv-accent");
    expect(screen.getByRole("button", { name: "ניסיון חוזר" })).not.toHaveClass("bg-cv-accent");
  });

  it("names what a succeeded Operation produced, and only its active outputs", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          operation({
            status: "succeeded",
            is_terminal: true,
            phase: "completed",
            outputs: [
              { output_type: "job_analysis", output_id: "analysis-1", active: true },
              { output_type: "selection_plan", output_id: "plan-1", active: true },
              /* §11: an inactive output is evidence, not a result. Naming it would claim
                 the operation produced something it never activated. */
              { output_type: "working_draft", output_id: "draft-1", active: false },
              /* Registered, but it is the provider's own text and this screen shows
                 none. */
              { output_type: "provider_response", output_id: "resp-1", active: true },
            ],
          }),
        ),
      ),
    );

    renderPage(<OperationPage />);

    expect(
      await screen.findByText(
        "הפעולה הושלמה ויצרה ניתוח המשרה ותוכנית בחירת העובדות. חזרה למועמדות מציגה מה הפעולה הבאה.",
      ),
    ).toBeInTheDocument();
  });

  it("names what the workflow is waiting on next, from the projection", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((input: RequestInfo | URL) => {
        const url = String(input);
        if (url === projectionUrl) {
          return Promise.resolve(
            jsonResponse({ ...projection, preparation_state: "draft_in_progress" }),
          );
        }
        return Promise.resolve(
          jsonResponse(
            operation({
              operation_type: "create_draft",
              status: "succeeded",
              is_terminal: true,
              phase: "completed",
              outputs: [
                { output_type: "working_draft", output_id: "draft-1", active: true },
              ],
            }),
          ),
        );
      }),
    );

    renderPage(<OperationPage />);

    /* The stage sentence is the Application screen's own copy, read from the same
       projection: this screen reports the workflow position rather than deciding one. */
    expect(
      await screen.findByText(
        "הפעולה הושלמה ויצרה טיוטה. יש טיוטה פעילה לעבוד עליה. כשהיא מוכנה, אימות בודק אותה מול העובדות הקנוניות.",
      ),
    ).toBeInTheDocument();
  });
});
