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
});

describe("OperationPage", () => {
  it("names the status in Hebrew and reports the phase", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(operation())));

    renderPage(<OperationPage />);

    /* Matched by accessible name rather than by finding the heading and then reading it:
       the heading is on screen from the first render carrying its loading text, so a
       bare findByRole resolves before the Operation arrives. */
    expect(await screen.findByRole("heading", { level: 1, name: "מתבצעת" })).toBeInTheDocument();
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
          }),
        ),
      ),
    );

    renderPage(<OperationPage />);

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("חסימה");
    expect(alert).toHaveTextContent("The provider did not answer in time.");
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("נכשלה");
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

  /* The regression this file exists for: a transport error is not an ApiProblem, and the
     screen used to render nothing at all for it. */
  it("shows a safe fallback when the failure is not a Problem Details", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));

    renderPage(<OperationPage />);

    expect(await screen.findByRole("alert")).toHaveTextContent("לא ניתן לטעון את מצב הפעולה");
  });

  it("cancels only when the backend exposes the action and keeps the returned state", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(operation()))
      .mockResolvedValueOnce(
        jsonResponse(
          operation({
            status: "cancelled",
            is_terminal: true,
            phase: "completed",
            available_actions: ["retry"],
          }),
        ),
      );
    vi.stubGlobal("fetch", fetchMock);

    renderPage(<OperationPage />);
    fireEvent.click(await screen.findByRole("button", { name: "ביטול הפעולה" }));

    expect(await screen.findByRole("button", { name: "ניסיון חוזר" })).toBeInTheDocument();
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/v1/operations/op-1/cancel",
      expect.objectContaining({ method: "POST" }),
    );
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
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(terminal))
      .mockResolvedValueOnce(
        new Response(JSON.stringify(queued), {
          status: 202,
          headers: {
            "Content-Type": "application/json",
            Location: "/api/v1/operations/op-2",
          },
        }),
      )
      .mockResolvedValueOnce(jsonResponse(queued));
    vi.stubGlobal("fetch", fetchMock);

    renderPage(<OperationPage />);
    fireEvent.click(await screen.findByRole("button", { name: "ניסיון חוזר" }));

    expect(await screen.findByRole("button", { name: "ביטול הפעולה" })).toBeInTheDocument();
    await waitFor(() => expect(fetchMock.mock.calls.length).toBeGreaterThanOrEqual(2));
    const retryRequest = fetchMock.mock.calls[1];
    expect(retryRequest?.[0]).toBe("/api/v1/operations/op-1/retry");
    expect(retryRequest?.[1]).toEqual(
      expect.objectContaining({
        method: "POST",
        headers: expect.any(Headers),
      }),
    );
    expect((retryRequest?.[1]?.headers as Headers).get("Idempotency-Key")).not.toBeNull();
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
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse(
          operation({
            status: "failed",
            is_terminal: true,
            phase: "completed",
            available_actions: ["retry"],
          }),
        ),
      )
      .mockResolvedValueOnce(conflictResponse())
      .mockResolvedValueOnce(conflictResponse());
    vi.stubGlobal("fetch", fetchMock);

    renderPage(<OperationPage />);
    fireEvent.click(await screen.findByRole("button", { name: "ניסיון חוזר" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "לא ניתן ליצור ניסיון חוזר במצב הנוכחי.",
    );
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("נכשלה");

    const firstKey = (fetchMock.mock.calls[1]?.[1]?.headers as Headers).get("Idempotency-Key");
    fireEvent.click(screen.getByRole("button", { name: "ניסיון חוזר" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
    const secondKey = (fetchMock.mock.calls[2]?.[1]?.headers as Headers).get("Idempotency-Key");
    expect(secondKey).toBe(firstKey);
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

    expect(await screen.findByRole("heading", { level: 1, name: "מתבצעת" })).toBeInTheDocument();
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
  });
});
