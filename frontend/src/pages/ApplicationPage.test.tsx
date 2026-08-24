import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ApplicationDetail, Operation } from "../api/contracts";
import { ApplicationPage } from "./ApplicationPage";

const DETAIL_PATH = "/api/v1/applications/app-1";
const ANALYSES_PATH = "/api/v1/applications/app-1/analyses";

const detail = (overrides: Partial<ApplicationDetail> = {}): ApplicationDetail => ({
  recruitment_status: "saved",
  preparation_state: "needs_analysis",
  working_draft_state: "none",
  review_reasons: [],
  stale_reasons: [],
  warnings: [],
  active_job_snapshot_id: "snap-1",
  newer_draft_in_progress: false,
  available_actions: ["analyze"],
  blocked_actions: [],
  recommended_action: "analyze",
  application: {
    id: "app-1",
    company: "Acme",
    target_role: "Backend Engineer",
    current_status: "saved",
    notes: "",
    source: "manual",
    created_at: "2026-08-24T07:00:00Z",
    updated_at: "2026-08-24T07:00:00Z",
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

const queued = (overrides: Partial<Operation> = {}): Operation => ({
  id: "op-1",
  application_id: "app-1",
  operation_type: "analyze_job",
  status: "queued",
  is_terminal: false,
  phase: "queued",
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

const acceptedResponse = (operation: Operation): Response =>
  new Response(JSON.stringify(operation), {
    status: 202,
    headers: {
      "Content-Type": "application/json",
      Location: `/api/v1/operations/${operation.id}`,
    },
  });

/* Retries and the projection poll are off inside the test client: the interval is
   covered by its own unit test, and a live timer here would make every assertion racy. */
const renderPage = () => {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false, refetchInterval: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });

  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/applications/app-1"]}>
        <Routes>
          <Route element={<ApplicationPage />} path="/applications/:applicationId" />
          <Route element={<h1>מצב הפעולה</h1>} path="/operations/:operationId" />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("ApplicationPage", () => {
  it("names the application and reports both projected states in Hebrew", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(detail())));

    renderPage();

    expect(await screen.findByRole("heading", { level: 1, name: "Acme" })).toBeInTheDocument();
    expect(screen.getByText("תפקיד היעד: Backend Engineer")).toBeInTheDocument();
    expect(screen.getByText("ממתין לניתוח המשרה")).toBeInTheDocument();
    expect(screen.getByText("אין טיוטה פעילה")).toBeInTheDocument();
  });

  it("analyzes the exact snapshot the projection names and follows the accepted Operation", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(detail()))
      .mockResolvedValueOnce(acceptedResponse(queued()));
    vi.stubGlobal("fetch", fetchMock);

    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "ניתוח המשרה" }));

    expect(await screen.findByRole("heading", { name: "מצב הפעולה" })).toBeInTheDocument();

    const request = fetchMock.mock.calls[1];
    expect(request?.[0]).toBe(ANALYSES_PATH);
    expect(request?.[1]).toEqual(expect.objectContaining({ method: "POST" }));
    /* The source is explicit: an analyze command that picked its own snapshot could
       classify something other than what the screen was showing. */
    expect(JSON.parse(String(request?.[1]?.body))).toEqual({ job_snapshot_id: "snap-1" });
    expect((request?.[1]?.headers as Headers).get("Idempotency-Key")).not.toBeNull();
  });

  it("refuses to follow an accepted response that does not name its queued Operation", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(jsonResponse(detail()))
        .mockResolvedValueOnce(jsonResponse(queued(), 202)),
    );

    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "ניתוח המשרה" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("הפעולה לא בוצעה");
    expect(screen.queryByRole("heading", { name: "מצב הפעולה" })).not.toBeInTheDocument();
  });

  /* A.1: the projection decides what comes next. A recommended action whose screen this
     slice does not build is named and reported as missing, never routed to something
     invented for it. */
  it("names a recommended action it cannot perform instead of inventing a screen", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          detail({
            preparation_state: "ready_to_draft",
            available_actions: ["analyze", "create_draft"],
            recommended_action: "create_draft",
          }),
        ),
      ),
    );

    renderPage();

    expect(await screen.findByText("הפעולה המומלצת כעת היא יצירת טיוטה")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "יצירת טיוטה" })).not.toBeInTheDocument();
    /* Analysis is still available, but it is no longer the emphasized action and it says
       what a second analysis does. */
    expect(screen.getByRole("button", { name: "ניתוח מחדש של המשרה" })).toBeInTheDocument();
    expect(
      screen.getByText(/ניתוח מחדש יוצר ניתוח חדש ונפרד/, { exact: false }),
    ).toBeInTheDocument();
  });

  it("presents a review reason as a blocker with the action that resolves it", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          detail({
            preparation_state: "needs_review",
            recommended_action: "apply_analysis_decisions",
            review_reasons: [
              {
                code: "LOW_FIT_REQUIRES_ACCEPTANCE",
                message: "Low fit requires explicit acceptance before drafting.",
                entity_references: { job_analysis_id: "analysis-1" },
                allowed_resolution_actions: ["apply_analysis_decisions"],
              },
            ],
          }),
        ),
      ),
    );

    renderPage();

    expect(await screen.findByText("נדרשת החלטה לפני המשך")).toBeInTheDocument();
    expect(
      screen.getByText("Low fit requires explicit acceptance before drafting."),
    ).toHaveAttribute("dir", "auto");
    expect(
      screen.getByText(/הפעולה שפותרת אותה: החלת החלטות הסקירה/),
    ).toBeInTheDocument();
    expect(screen.getByText("LOW_FIT_REQUIRES_ACCEPTANCE")).toBeInTheDocument();
  });

  it("links to the Operation the projection reports as already running", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(detail({ active_operation: queued({ status: "running", phase: "executing" }) })),
      ),
    );

    renderPage();

    expect(await screen.findByText("פעולה רצה על המועמדות הזו")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "מעבר למצב הפעולה" })).toHaveAttribute(
      "href",
      "/operations/op-1",
    );
  });

  it("shows a load failure safely and offers no action it cannot back", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          {
            type: "about:blank#unknown-record",
            title: "Application not found",
            status: 404,
            code: "UNKNOWN_RECORD",
            detail: "אין מועמדות במזהה הזה.",
          },
          404,
        ),
      ),
    );

    renderPage();

    expect(await screen.findByRole("alert")).toHaveTextContent("אין מועמדות במזהה הזה.");
    expect(screen.queryByRole("button", { name: "ניתוח המשרה" })).not.toBeInTheDocument();
  });
});
