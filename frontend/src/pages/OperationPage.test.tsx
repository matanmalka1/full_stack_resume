import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
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
    defaultOptions: { queries: { retry: false, refetchInterval: false, gcTime: 0 } },
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
});
