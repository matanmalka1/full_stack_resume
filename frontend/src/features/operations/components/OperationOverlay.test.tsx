import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Operation } from "@/api/contracts";
import { settingsQueryKey } from "@/api/settings";
import { settings as settingsFixture } from "@/test/fixtures";
import { isOperationLive } from "../model/operationLive";
import { OperationOverlay, type PendingWork } from "./OperationOverlay";
import { OperationReport } from "./OperationReport";

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

const succeeded = (overrides: Partial<Operation> = {}) =>
  operation({ status: "succeeded", phase: "completed", is_terminal: true, ...overrides });
const failed = (overrides: Partial<Operation> = {}) =>
  operation({ status: "failed", phase: "completed", is_terminal: true, ...overrides });

const client = () =>
  new QueryClient({
    defaultOptions: { mutations: { retry: false }, queries: { retry: false } },
  });

/* The report's content, read without the overlay's session around it. */
const renderPanel = (value: Operation, onQueued = vi.fn(), failureAction?: ReactElement) => {
  render(
    <QueryClientProvider client={client()}>
      <OperationReport failureAction={failureAction} onQueued={onQueued} operation={value} />
    </QueryClientProvider>,
  );
};

interface OverlayProps {
  awaitingRecord?: boolean;
  continuation?: string;
  operation?: Operation;
  pending?: PendingWork;
  settled?: boolean;
}

/* One host screen across several reads: each `update` is the next render of the same
   overlay, the way a watch hands it a new record. */
const renderOverlay = (initial: OverlayProps, settings?: ReturnType<typeof settingsFixture>) => {
  const queryClient = client();
  if (settings !== undefined) queryClient.setQueryData(settingsQueryKey, { settings, etag: null });
  const view = (props: OverlayProps): ReactElement => (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <OperationOverlay
          awaitingRecord={props.awaitingRecord ?? false}
          continuation={props.continuation}
          onQueued={vi.fn()}
          operation={props.operation}
          pending={props.pending}
          settled={props.settled ?? false}
        />
      </MemoryRouter>
    </QueryClientProvider>
  );
  const result = render(view(initial));
  return { update: (props: OverlayProps) => result.rerender(view(props)) };
};

const overlay = (): HTMLDialogElement => {
  const dialog = document.querySelector("dialog");
  if (dialog === null) throw new Error("no overlay on screen");
  return dialog;
};
const chip = () => screen.getByRole("button", { name: /· .*פירוט ההרצה/ });
const panel = () => screen.getByRole("region");

describe("OperationReport", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("presents a queued operation as one status", () => {
    renderOverlay({ operation: operation({ status: "queued", phase: "queued" }) });

    expect(screen.getByRole("status")).toHaveTextContent("ממתינה בתור");
    /* The chip, the report's badge, and the live region: one sentence, three places. */
    expect(screen.getAllByText(/ממתינה בתור/)).toHaveLength(3);
  });

  it("collapses the generic executing phase into the running status", () => {
    renderPanel(operation());

    expect(screen.getByText("מתבצעת")).toBeInTheDocument();
    expect(screen.getByRole("progressbar", { name: "התקדמות: מתבצעת" })).toBeInTheDocument();
    expect(screen.queryByText("בביצוע")).not.toBeInTheDocument();
  });

  it("makes the writer and reviewer stage visible during draft generation", () => {
    renderOverlay({ operation: operation({ operation_type: "create_draft" }) });

    expect(screen.getByRole("status")).toHaveTextContent("מנסחת ובודקת את הטענות");
  });

  it("prefers a specific waiting phase over a generic running status", () => {
    renderOverlay({ operation: operation({ phase: "waiting_for_ai_slot" }) });

    expect(screen.getByRole("status")).toHaveTextContent("ממתינה לתור המודל");
    expect(screen.queryByText(/מתבצעת/)).not.toBeInTheDocument();
  });

  it("lets terminal status override the operation's last phase", () => {
    renderPanel(operation({ status: "succeeded", phase: "activating", is_terminal: true }));

    expect(screen.getByText("הושלמה")).toBeInTheDocument();
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
    expect(screen.queryByText("מפעילה את התוצר")).not.toBeInTheDocument();
  });

  it("offers a re-run of finished work as a secondary action", () => {
    renderPanel(succeeded({ available_actions: ["retry"] }));

    expect(screen.getByRole("button", { name: "הרצה מחדש" })).toBeInTheDocument();
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

  it("explains a render validation failure and shows the host recovery action", () => {
    renderPanel(
      failed({
        failure_code: "RENDER_FAILED",
        operation_type: "render_revision",
        safe_failure_detail: "Rendered PDF has 2 pages; maximum 1.",
        failure_reason: { code: "pdf_page_limit", pages: 2, maximum: 1 },
      }),
      vi.fn(),
      <button type="button">חזרה לעריכת הטיוטה</button>,
    );

    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("קובץ ה־PDF כולל 2 עמודים");
    expect(alert).toHaveTextContent("הפרופיל מאפשר לכל היותר 1");
    expect(screen.getByRole("button", { name: "חזרה לעריכת הטיוטה" })).toBeInTheDocument();
    expect(screen.queryByText("Rendered PDF has 2 pages; maximum 1.")).not.toBeInTheDocument();
  });

  /* The backend files "no provider configured" under PROVIDER_REFUSED. With Settings
     saying no provider exists, the report names that cause, says the request went
     nowhere, and offers Settings rather than a retry that would fail the same way. */
  it.each([
    [false, "לא הוגדר ספק AI"],
    [true, "ה־AI כבוי בהגדרות"],
  ] as const)("routes a refusal with no usable provider (configured: %s) to Settings", (configured, title) => {
    const queryClient = client();
    const settings = settingsFixture({ provider_configured: configured, ai_enabled: false });
    queryClient.setQueryData(settingsQueryKey, { settings, etag: null });
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <OperationReport
            onQueued={vi.fn()}
            operation={failed({ failure_code: "PROVIDER_REFUSED", available_actions: ["retry"] })}
          />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    expect(screen.getByRole("alert")).toHaveTextContent(title);
    expect(screen.queryByText("ספק הבינה המלאכותית סירב לבקשה")).not.toBeInTheDocument();
    /* The reason is the report's line on a failure; no vaguer one above it. */
    expect(screen.queryByText("הפעולה נכשלה ולא יצרה תוצאה.")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "פתיחת ההגדרות" })).toHaveAttribute("href", "/settings");
    expect(screen.queryByRole("button", { name: "ניסיון חוזר" })).not.toBeInTheDocument();
  });

  /* A failure recorded before the structured reason existed carries only the English
     sentence. It is not parsed: the code's own guidance stands, and the sentence stays out. */
  it("does not parse the English detail of a failure recorded without a reason", () => {
    renderPanel(
      failed({
        failure_code: "RENDER_FAILED",
        operation_type: "render_revision",
        safe_failure_detail: "Rendered PDF has 2 pages; maximum 1.",
      }),
    );

    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("יצירת קובץ קורות החיים נכשלה");
    expect(alert).not.toHaveTextContent("קובץ ה־PDF כולל");
    expect(screen.queryByText("Rendered PDF has 2 pages; maximum 1.")).not.toBeInTheDocument();
  });

  /* PROVIDER_NOT_CONFIGURED is the server's own word for a run that had no provider. While
     that is still true it goes to Settings; once a provider is usable, it can run again. */
  it("sends a not-configured run to Settings, and offers it again once a provider is usable", () => {
    const run = failed({ failure_code: "PROVIDER_NOT_CONFIGURED", available_actions: ["retry"] });
    const renderWith = (configured: boolean) => {
      const queryClient = client();
      queryClient.setQueryData(settingsQueryKey, {
        settings: settingsFixture({ provider_configured: configured, ai_enabled: configured }),
        etag: null,
      });
      return render(
        <QueryClientProvider client={queryClient}>
          <MemoryRouter>
            <OperationReport onQueued={vi.fn()} operation={run} />
          </MemoryRouter>
        </QueryClientProvider>,
      );
    };

    const first = renderWith(false);
    expect(screen.getByRole("alert")).toHaveTextContent("לא הוגדר ספק AI");
    expect(screen.getByRole("link", { name: "פתיחת ההגדרות" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "ניסיון חוזר" })).not.toBeInTheDocument();
    first.unmount();

    renderWith(true);
    expect(screen.getByRole("alert")).toHaveTextContent("לא היה ספק AI בזמן ההרצה");
    expect(screen.getByRole("button", { name: "ניסיון חוזר" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "פתיחת ההגדרות" })).not.toBeInTheDocument();
  });

  it.each([
    ["CLAIM_REVIEW_UNCERTAIN", "הבדיקה לא הצליחה לקבוע שהניסוח נתמך"],
    ["CLAIM_REVIEW_UNSUPPORTED", "הבדיקה מצאה טענה שאינה נתמכת בעובדות"],
  ] as const)("presents %s as a distinct review outcome", (failureCode, title) => {
    renderPanel(
      operation({
        status: "failed",
        phase: "completed",
        is_terminal: true,
        failure_code: failureCode,
      }),
    );

    expect(screen.getByRole("alert")).toHaveTextContent(title);
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
        failure_reason: { code: "missing_fact_rendering", fact_id: "development.phdigital.nextjs", language: "he" },
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

describe("OperationOverlay", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  /* Once a provider is available, a refused run no longer blocks anything: the row says
     it can be tried again and stops wearing the blocker tone. */
  it("stops presenting a refused run as an open blocker once a provider is available", () => {
    const refused = failed({ failure_code: "PROVIDER_REFUSED", available_actions: ["retry"] });
    renderOverlay(
      { operation: refused, settled: true },
      settingsFixture({ provider_configured: true, ai_enabled: true }),
    );

    expect(chip()).toHaveTextContent("נכשלה · אפשר לנסות שוב");
  });

  it("keeps a refused run a plain failure while no provider is available", () => {
    const refused = failed({ failure_code: "PROVIDER_REFUSED", available_actions: ["retry"] });
    renderOverlay({ operation: refused, settled: true }, settingsFixture());

    expect(chip()).toHaveTextContent("נכשלה");
    expect(chip()).not.toHaveTextContent("אפשר לנסות שוב");
  });

  it("shows live work in a panel beside the page, not over it", () => {
    renderOverlay({ operation: operation() });

    expect(panel()).toHaveTextContent("הרצת ניתוח המשרה");
    expect(panel()).toHaveTextContent("מתבצעת");
    expect(within(panel()).getByRole("list", { name: "שלבי ההרצה" })).toBeInTheDocument();
    expect(overlay().open).toBe(false);

    /* The full report is still a press away while the run lasts. */
    fireEvent.click(within(panel()).getByRole("button", { name: "פירוט ההרצה" }));
    expect(overlay().open).toBe(true);
  });

  it("shows nothing for a success that was already finished when the screen read it", () => {
    /* Not settled yet either: waiting for the refresh extends a session, never starts one. */
    renderOverlay({ operation: succeeded(), settled: false });

    expect(screen.queryByRole("region")).not.toBeInTheDocument();
    expect(overlay().open).toBe(false);
    expect(screen.queryByRole("button", { name: /פירוט ההרצה/ })).not.toBeInTheDocument();
  });

  it("shows a success briefly once its refresh has landed, then leaves nothing behind", () => {
    vi.useFakeTimers();
    const { update } = renderOverlay({ operation: operation() });

    update({ operation: succeeded({ available_actions: ["retry"] }), settled: false });
    expect(panel()).toHaveTextContent("הושלמה");

    update({ operation: succeeded({ available_actions: ["retry"] }), settled: true });
    expect(panel()).toHaveTextContent("הושלמה");
    expect(overlay().open).toBe(false);

    act(() => vi.advanceTimersByTime(3_000));
    expect(screen.queryByRole("region")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /פירוט ההרצה/ })).not.toBeInTheDocument();
  });

  it("opens the report on a failure, and leaves a status row that reopens it", () => {
    const { update } = renderOverlay({ operation: operation() });

    /* Put away while it runs, the panel is replaced by the status row. */
    fireEvent.click(within(panel()).getByRole("button", { name: "סגירה" }));
    expect(screen.queryByRole("region")).not.toBeInTheDocument();
    expect(chip()).toHaveTextContent("מתבצעת");
    expect(chip()).toHaveFocus();

    update({ operation: failed({ failure_code: "VALIDATION_EXECUTION_FAILED" }), settled: true });
    expect(overlay().open).toBe(true);
    expect(screen.getByRole("alert")).toHaveTextContent("לא ניתן להשלים את בדיקות הפעולה");

    fireEvent.click(within(overlay()).getByRole("button", { name: "סגירה" }));
    expect(overlay().open).toBe(false);
    expect(chip()).toHaveTextContent("נכשלה");
    fireEvent.click(chip());
    expect(overlay().open).toBe(true);
  });

  it("keeps one session from pending work to the record that replaces it", () => {
    const pending = { heading: <>הרצת ניתוח המשרה</>, note: "יוצרים את המועמדות ומנתחים את המשרה…" };
    const { update } = renderOverlay({ pending });
    const first = panel();
    expect(first).toHaveTextContent("נשלחה לביצוע");
    expect(first).toHaveTextContent("יוצרים את המועמדות ומנתחים את המשרה…");

    update({ operation: operation() });
    expect(panel()).toBe(first);
    expect(first).toHaveTextContent("מתבצעת");
  });

  it("stays in one panel across a continuation and never opens the report", () => {
    const analyze = operation();
    const draft = operation({ id: "operation-2", operation_type: "create_draft" });
    const continuation = "הניתוח הושלם. יצירת הטיוטה מתחילה מיד.";
    const { update } = renderOverlay({ operation: analyze });
    const first = panel();

    update({ continuation, operation: succeeded(), settled: true });
    expect(panel()).toBe(first);
    expect(first).toHaveTextContent(continuation);

    update({ operation: draft });
    expect(panel()).toBe(first);
    expect(first).toHaveTextContent("הרצת יצירת הטיוטה");

    update({ operation: { ...draft, status: "succeeded", phase: "completed", is_terminal: true }, settled: true });
    expect(first).toHaveTextContent("הושלמה");
    expect(overlay().open).toBe(false);
  });

  it("moves a retry's new run back to the panel, without the previous failure", () => {
    const previous = failed({ available_actions: ["retry"] });
    const { update } = renderOverlay({ operation: operation() });
    update({ operation: previous, settled: true });
    expect(overlay().open).toBe(true);

    update({ awaitingRecord: true, operation: previous, settled: true });
    expect(overlay().open).toBe(false);
    expect(panel()).toHaveTextContent("נשלחה לביצוע");
    /* The previous run's failure is not this run's outcome. */
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();

    update({ operation: operation({ id: "operation-2" }) });
    expect(panel()).toHaveTextContent("מתבצעת");
  });

  it("does not hold an old failure open when the new command never queued", () => {
    const { update } = renderOverlay({ operation: failed(), settled: true });
    expect(overlay().open).toBe(false);
    expect(chip()).toHaveTextContent("נכשלה");

    update({ operation: failed(), pending: { heading: "הרצה", note: "נשלחה" }, settled: true });
    expect(panel()).toHaveTextContent("נשלחה");

    update({ operation: failed(), settled: true });
    expect(overlay().open).toBe(false);
    expect(screen.queryByRole("region")).not.toBeInTheDocument();
    expect(chip()).toHaveTextContent("נכשלה");
  });

  it("keeps the cancel delay running while the report is closed", () => {
    vi.useFakeTimers();
    renderOverlay({ operation: operation({ available_actions: ["cancel"] }) });

    act(() => vi.advanceTimersByTime(2_000));
    fireEvent.click(within(panel()).getByRole("button", { name: "סגירה" }));
    act(() => vi.advanceTimersByTime(2_000));
    fireEvent.click(chip());

    expect(screen.getByRole("button", { name: "ביטול הפעולה" })).toBeInTheDocument();
  });
});

describe("isOperationLive", () => {
  const base = { awaitingRecord: false, operation: undefined, pending: false, settled: false };

  it("holds conflicting actions through a success until its refresh has landed", () => {
    expect(isOperationLive({ ...base, operation: operation() })).toBe(true);
    expect(isOperationLive({ ...base, operation: succeeded(), settled: false })).toBe(true);
    expect(isOperationLive({ ...base, operation: succeeded(), settled: true })).toBe(false);
    expect(isOperationLive({ ...base, operation: failed() })).toBe(false);
  });

  it("covers work asked for before a record exists", () => {
    expect(isOperationLive({ ...base, pending: true })).toBe(true);
    expect(isOperationLive({ ...base, awaitingRecord: true, operation: failed() })).toBe(true);
    expect(isOperationLive({ ...base, continuation: "ממשיכה", operation: succeeded(), settled: true })).toBe(true);
  });
});
