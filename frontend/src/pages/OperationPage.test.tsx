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
});
