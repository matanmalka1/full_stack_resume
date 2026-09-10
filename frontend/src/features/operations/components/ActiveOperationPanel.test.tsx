import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { Operation } from "@/api/contracts";
import { ActiveOperationPanel } from "./ActiveOperationPanel";

const operation = (overrides: Partial<Operation> = {}): Operation => ({
  id: "operation-1",
  application_id: "application-1",
  operation_type: "analyze_job",
  status: "running",
  phase: "executing",
  is_terminal: false,
  available_actions: [],
  outputs: [],
  message: "",
  created_at: "2026-09-09T08:00:00Z",
  ...overrides,
});

const renderPanel = (value: Operation) => {
  const client = new QueryClient({
    defaultOptions: { mutations: { retry: false }, queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <ActiveOperationPanel onQueued={vi.fn()} operation={value} />
    </QueryClientProvider>,
  );
};

describe("ActiveOperationPanel progress", () => {
  it("presents a queued operation as one status", () => {
    renderPanel(operation({ status: "queued", phase: "queued" }));

    expect(screen.getByRole("status")).toHaveTextContent("ממתינה בתור");
    expect(screen.getAllByText("ממתינה בתור")).toHaveLength(2);
  });

  it("collapses the generic executing phase into the running status", () => {
    renderPanel(operation());

    expect(screen.getByRole("status")).toHaveTextContent("מתבצעת");
    expect(screen.queryByText("בביצוע")).not.toBeInTheDocument();
  });

  it("prefers a specific waiting phase over a generic running status", () => {
    renderPanel(operation({ phase: "waiting_for_ai_slot" }));

    expect(screen.getByRole("status")).toHaveTextContent("ממתינה לתור המודל");
    expect(screen.queryByText("מתבצעת")).not.toBeInTheDocument();
  });

  it("lets terminal status override the operation's last phase", () => {
    renderPanel(operation({ status: "succeeded", phase: "activating", is_terminal: true }));

    expect(screen.getByRole("status")).toHaveTextContent("הושלמה");
    expect(screen.queryByText("מפעילה את התוצר")).not.toBeInTheDocument();
  });

  it("does not expose safe English detail for a known failure code", () => {
    renderPanel(
      operation({
        status: "failed",
        phase: "completed",
        is_terminal: true,
        failure_code: "VALIDATION_EXECUTION_FAILED",
        safe_failure_detail: "Operation execution failed.",
      }),
    );

    expect(screen.getByRole("alert")).toHaveTextContent("לא ניתן להשלים את בדיקות הפעולה");
    expect(screen.queryByText("Operation execution failed.")).not.toBeInTheDocument();
  });
});
