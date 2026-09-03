import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ApplicationDetail } from "../api/contracts";
import { JobDetailsPage } from "./JobDetailsPage";

const detail = (): ApplicationDetail =>
  ({
    recruitment_status: "recruiter_screen",
    allowed_recruitment_transitions: ["interview", "rejected", "withdrawn", "closed"],
    recruitment_timeline: [],
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
      current_status: "recruiter_screen",
      next_action: "Follow up",
      next_action_date: "2026-09-05",
      notes: "Referral from a former colleague",
      source: "manual",
      created_at: "2026-08-24T07:00:00Z",
      updated_at: "2026-08-25T08:00:00Z",
    },
    latest_snapshot: {
      id: "snap-1",
      application_id: "app-1",
      version_number: 1,
      job_text: "Senior Backend Engineer",
      source_url: "https://example.com/jobs/1",
      captured_at: "2026-08-24T07:00:00Z",
      source_metadata: {},
      content_hash: "hash-1",
    },
  }) as ApplicationDetail;

const jsonResponse = (body: unknown): Response =>
  new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });

const renderPage = (fetchImplementation?: (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>) => {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false, refetchInterval: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });

  vi.stubGlobal(
    "fetch",
    vi.fn(
      fetchImplementation ??
        ((input: RequestInfo | URL) =>
          Promise.resolve(String(input).endsWith("/artifacts") ? jsonResponse({ items: [] }) : jsonResponse(detail()))),
    ),
  );

  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/applications/app-1"]}>
        <Routes>
          <Route element={<JobDetailsPage />} path="/applications/:applicationId" />
          <Route element={<h1>הכנת קורות החיים</h1>} path="/applications/:applicationId/preparation" />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("JobDetailsPage", () => {
  it("links a Ready application to the exact immutable revision", async () => {
    renderPage((input) =>
      Promise.resolve(
        String(input).endsWith("/artifacts")
          ? jsonResponse({ items: [] })
          : jsonResponse({
              ...detail(),
              preparation_state: "ready",
              latest_ready_revision_id: "revision-7",
            }),
      ),
    );

    expect(await screen.findByRole("link", { name: "צפייה בגרסה המוכנה" })).toHaveAttribute(
      "href",
      "/revisions/revision-7",
    );
  });

  it("presents recruitment status separately from the CV preparation state", async () => {
    renderPage();

    expect(await screen.findByText("שיחת מגייס")).toBeInTheDocument();
    expect(screen.getByText("ממתין לניתוח המשרה")).toBeInTheDocument();
  });

  it("captures an amended posting as a new immutable snapshot from Job Detail", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      if (String(input).endsWith("/job-snapshots") && init?.method === "POST") {
        return Promise.resolve(jsonResponse({ application_id: "app-1", job_snapshot_id: "snap-2" }));
      }
      return Promise.resolve(
        String(input).endsWith("/artifacts") ? jsonResponse({ items: [] }) : jsonResponse(detail()),
      );
    });
    renderPage(fetchMock);

    fireEvent.click(await screen.findByRole("button", { name: "עדכון נוסח המשרה" }));
    expect(screen.getByRole("dialog", { name: "יצירת תצלום משרה חדש" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("טקסט המשרה"), {
      target: { value: "Senior Backend Engineer, now remote" },
    });
    fireEvent.click(screen.getByRole("button", { name: "יצירת התצלום החדש" }));

    expect(await screen.findByText("נשמר תצלום משרה חדש")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "סגירת ההודעה" }));
    /* The mutation's reset notification is batched, so the callout it controls does not
       drop out of the DOM in the same tick as the click. */
    await waitFor(() => expect(screen.queryByText("נשמר תצלום משרה חדש")).not.toBeInTheDocument());
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([input, init]) => String(input).endsWith("/job-snapshots") && init?.method === "POST",
        ),
      ).toBe(true),
    );
    const request = fetchMock.mock.calls.find(
      ([input, init]) => String(input).endsWith("/job-snapshots") && init?.method === "POST",
    );
    expect(JSON.parse(String(request?.[1]?.body))).toEqual({
      job_text: "Senior Backend Engineer, now remote",
      source_url: "https://example.com/jobs/1",
    });
  });

  it("edits notes with the exact server value as an optimistic precondition", async () => {
    let currentNotes = detail().application.notes;
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      if (String(input).endsWith("/notes") && init?.method === "PATCH") {
        const body = JSON.parse(String(init.body)) as { notes: string };
        currentNotes = body.notes;
        return Promise.resolve(jsonResponse({ application_id: "app-1", notes: currentNotes, updated_at: "now" }));
      }
      if (String(input).endsWith("/artifacts")) return Promise.resolve(jsonResponse({ items: [] }));
      return Promise.resolve(
        jsonResponse({ ...detail(), application: { ...detail().application, notes: currentNotes } }),
      );
    });
    renderPage(fetchMock);

    fireEvent.click(await screen.findByRole("button", { name: "עריכת הערות" }));
    fireEvent.change(screen.getByLabelText("הערות"), { target: { value: "Follow up after the holiday" } });
    fireEvent.click(screen.getByRole("button", { name: "שמירת ההערות" }));

    await waitFor(() => expect(screen.queryByRole("dialog", { name: "עריכת הערות למועמדות" })).not.toBeInTheDocument());
    expect(screen.getByText("Follow up after the holiday")).toBeInTheDocument();
    const request = fetchMock.mock.calls.find(
      ([input, init]) => String(input).endsWith("/notes") && init?.method === "PATCH",
    );
    expect(JSON.parse(String(request?.[1]?.body))).toEqual({
      notes: "Follow up after the holiday",
      expected_notes: "Referral from a former colleague",
    });
  });
});
