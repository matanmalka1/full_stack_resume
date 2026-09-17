import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

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

const renderPanel = (value: Operation, onQueued = vi.fn()) => {
  const client = new QueryClient({
    defaultOptions: { mutations: { retry: false }, queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <ActiveOperationPanel onQueued={onQueued} operation={value} />
    </QueryClientProvider>,
  );
};

describe("ActiveOperationPanel progress", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("presents a queued operation as one status", () => {
    renderPanel(operation({ status: "queued", phase: "queued" }));

    expect(screen.getByRole("status")).toHaveTextContent("ממתינה בתור");
    expect(screen.getAllByText("ממתינה בתור")).toHaveLength(2);
  });

  it("collapses the generic executing phase into the running status", () => {
    renderPanel(operation());

    expect(screen.getByRole("status")).toHaveTextContent("מתבצעת");
    expect(screen.getByRole("progressbar", { name: "התקדמות: מתבצעת" })).toBeInTheDocument();
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
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
    expect(screen.queryByText("מפעילה את התוצר")).not.toBeInTheDocument();
  });

  it("keeps optional AI execution metadata behind an interactive disclosure", () => {
    renderPanel(operation({ cost_usd: "0.012", model: "gpt-test", provider: "openai", reasoning_effort: "high" }));

    const details = screen.getByText("פרטי ביצוע").closest("details");
    expect(details).not.toHaveAttribute("open");
    fireEvent.click(screen.getByText("פרטי ביצוע"));
    expect(details).toHaveAttribute("open");
    expect(screen.getByText("gpt-test")).toBeVisible();
    expect(screen.getByText("גבוה")).toBeVisible();
  });

  it("keeps timing and reported usage accessible after success", () => {
    renderPanel(
      operation({
        status: "succeeded",
        is_terminal: true,
        phase: "completed",
        started_at: "2026-09-09T08:00:05Z",
        finished_at: "2026-09-09T08:01:10Z",
        input_tokens: 1200,
        cached_input_tokens: 0,
        output_tokens: 100,
      }),
    );

    const details = screen.getByText("פרטי ביצוע").closest("details");
    expect(details).not.toHaveAttribute("open");
    fireEvent.click(screen.getByText("פרטי ביצוע"));
    expect(screen.getByText("5 שניות")).toBeVisible();
    expect(screen.getByText("1 דקות ו־5 שניות")).toBeVisible();
    expect(screen.getByText("0")).toBeVisible();
    expect(screen.queryByText("סך הטוקנים")).not.toBeInTheDocument();
    expect(screen.queryByText("עלות")).not.toBeInTheDocument();
  });

  it("does not invent a duration for terminal work without a finish timestamp", () => {
    renderPanel(operation({ status: "failed", is_terminal: true, started_at: "2026-09-09T08:00:05Z" }));
    fireEvent.click(screen.getByText("פרטי ביצוע"));
    expect(screen.queryByText("משך הריצה")).not.toBeInTheDocument();
    expect(screen.queryByText("זמן שחלף")).not.toBeInTheDocument();
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

  it("reveals cancellation only when live work is taking unusually long", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-09-10T08:00:00Z"));
    renderPanel(
      operation({
        available_actions: ["cancel"],
        created_at: "2026-09-10T08:00:00Z",
      }),
    );

    expect(screen.queryByRole("button", { name: "ביטול הפעולה" })).not.toBeInTheDocument();
    act(() => vi.advanceTimersByTime(4_000));
    expect(screen.getByRole("button", { name: "ביטול הפעולה" })).toBeInTheDocument();
  });

  it("distinguishes an accepted cancellation request from completed cancellation", () => {
    renderPanel(operation({ available_actions: [], cancellation_requested_at: "2026-09-10T08:00:04Z" }));

    expect(screen.getByText("בקשת הביטול התקבלה")).toBeInTheDocument();
    expect(screen.queryByText("בוטלה")).not.toBeInTheDocument();
  });

  it("prevents duplicate cancellation requests while the first request is pending", async () => {
    vi.useFakeTimers();
    let resolveCancel!: (response: Response) => void;
    const fetchMock = vi.fn(
      () =>
        new Promise<Response>((resolve) => {
          resolveCancel = resolve;
        }),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderPanel(operation({ available_actions: ["cancel"] }));
    act(() => vi.advanceTimersByTime(4_000));
    vi.useRealTimers();

    const cancel = screen.getByRole("button", { name: "ביטול הפעולה" });
    fireEvent.click(cancel);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    fireEvent.click(cancel);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(cancel).toBeDisabled();

    resolveCancel(new Response(JSON.stringify(operation()), { headers: { "Content-Type": "application/json" } }));
    await act(async () => Promise.resolve());
  });

  it("tracks the new Operation returned by retry", async () => {
    const onQueued = vi.fn();
    const queued = operation({ id: "operation-2", status: "queued", phase: "queued" });
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify(queued), {
          headers: { "Content-Type": "application/json", Location: "/api/v1/operations/operation-2" },
          status: 202,
        }),
      ),
    );
    renderPanel(
      operation({ available_actions: ["retry"], is_terminal: true, phase: "completed", status: "failed" }),
      onQueued,
    );

    fireEvent.click(screen.getByRole("button", { name: "ניסיון חוזר" }));
    await waitFor(() => expect(onQueued).toHaveBeenCalledWith("operation-2"));
  });

  it("explains a blocked retry without offering an action the server omitted", () => {
    renderPanel(
      operation({
        available_actions: [],
        failure_code: "MISSING_FACT_RENDERING",
        safe_failure_detail: "Fact development.phdigital.nextjs has no 'he' rendering.",
        is_terminal: true,
        phase: "completed",
        status: "failed",
      }),
    );

    expect(screen.getByRole("alert")).toHaveTextContent("יש להשלים ניסוח לעובדה בשפת היעד");
    expect(screen.getByRole("alert")).toHaveTextContent("לעובדה development.phdigital.nextjs חסר ניסוח בשפה he.");
    expect(screen.queryByText("Fact development.phdigital.nextjs has no 'he' rendering.")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "ניסיון חוזר" })).not.toBeInTheDocument();
  });

  it("directs a source-changed failure to a fresh action without offering retry", () => {
    renderPanel(
      operation({
        available_actions: [],
        failure_code: "SOURCE_CHANGED",
        is_terminal: true,
        phase: "completed",
        status: "failed",
      }),
    );

    expect(screen.getByRole("alert")).toHaveTextContent("יש ליצור פעולה חדשה");
    expect(screen.queryByRole("button", { name: "ניסיון חוזר" })).not.toBeInTheDocument();
  });
});
