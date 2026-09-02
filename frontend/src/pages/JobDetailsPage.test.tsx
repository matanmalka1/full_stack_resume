import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ApplicationDetail, ArtifactVersion } from "../api/contracts";
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

const artifact = (id: string, artifactType: string): ArtifactVersion => ({
  artifact_id: `artifact-${id}`,
  artifact_type: artifactType,
  content_hash: `hash-${id}`,
  created_at: "2026-08-25T08:00:00Z",
  id,
  lifecycle_status: "rendered",
  logical_name: `${id}.html`,
  metadata: {},
  revision_id: "revision-1",
  version_number: 1,
});

const renderPage = (
  fetchImplementation?: (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>,
  navigationState?: { createdApplication: { analysisQueued: boolean } },
) => {
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
      <MemoryRouter initialEntries={[{ pathname: "/applications/app-1", state: navigationState }]}>
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
  it("confirms creation and reports that automatic analysis is running", async () => {
    renderPage(undefined, { createdApplication: { analysisQueued: true } });

    expect(await screen.findByText("המועמדות נוצרה, הניתוח רץ")).toBeInTheDocument();
  });

  it("keeps a failed automatic analysis start actionable on the created job", async () => {
    renderPage(undefined, { createdApplication: { analysisQueued: false } });

    expect(await screen.findByText("המועמדות נוצרה, אך הניתוח לא הופעל")).toBeInTheDocument();
    /* The notice carries no control of its own: the door below is the one way from the
       job to preparation, and it is on the screen whether the analysis started or not. */
    expect(screen.getByRole("link", { name: "מעבר להכנת קורות החיים" })).toHaveAttribute(
      "href",
      "/applications/app-1/preparation",
    );
  });

  it("owns the job posting and recruitment controls before analysis exists", async () => {
    renderPage();

    expect(await screen.findByRole("heading", { level: 1, name: "Backend Engineer" })).toBeInTheDocument();
    expect(screen.getByText("Acme")).toBeInTheDocument();
    expect(screen.getByText("Backend Engineer")).toBeInTheDocument();
    expect(screen.getByText("Referral from a former colleague")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /פתיחת מודעת המקור.*example\.com/ })).toBeInTheDocument();
    expect(screen.getByText("Senior Backend Engineer")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "עדכון נוסח המשרה" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "מעקב גיוס" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "שמירת השלב" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "שמירת הפעולה" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "ניתוח המשרה" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "עדכון מעקב הגיוס" })).toHaveAttribute("href", "#recruitment-heading");
  });

  it("orders the sections by daily use before the static posting", async () => {
    renderPage();

    await screen.findByRole("heading", { level: 1, name: "Backend Engineer" });
    expect(screen.getAllByRole("heading", { level: 2 }).map((heading) => heading.textContent)).toEqual([
      "הכנת קורות החיים",
      "פרטי המועמדות",
      "מעקב גיוס",
      "מודעת המשרה",
    ]);
  });

  /* The job record is the entrance to an Application, not a stage of the CV workflow: it
     shows where preparation stands and the door into it, and reports no stage of its own
     so the landmark stays off this screen. */
  it("is the entrance to preparation rather than a stage of it", async () => {
    renderPage();

    expect(await screen.findByText("ממתין לניתוח המשרה")).toBeInTheDocument();
    const gate = screen.getByRole("region", { name: "הכנת קורות החיים" });
    expect(within(gate).getByRole("link", { name: "מעבר להכנת קורות החיים" })).toHaveAttribute(
      "href",
      "/applications/app-1/preparation",
    );
    expect(screen.queryByRole("navigation", { name: "תחומי המועמדות" })).toBeNull();
    expect(screen.getByRole("navigation", { name: "חזרה ללוח המועמדויות" })).toBeInTheDocument();
  });

  it("suppresses milestone-implied draft absence and an unchanged update timestamp", async () => {
    const readyDetail: ApplicationDetail = {
      ...detail(),
      preparation_state: "ready",
      working_draft_state: "none",
      latest_ready_revision_id: "revision-1",
      application: {
        ...detail().application,
        updated_at: detail().application.created_at,
      },
    };
    renderPage((input) =>
      Promise.resolve(String(input).endsWith("/artifacts") ? jsonResponse({ items: [] }) : jsonResponse(readyDetail)),
    );

    expect(await screen.findByText("קורות החיים מוכנים")).toBeInTheDocument();
    expect(screen.queryByText("אין טיוטה פעילה")).not.toBeInTheDocument();
    expect(screen.queryByText("עודכנה לאחרונה")).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "פתיחת הגרסה המוכנה" })).not.toBeInTheDocument();
  });

  it("groups deliverable files by immutable revision and offers one revision link", async () => {
    renderPage((input) =>
      Promise.resolve(
        String(input).includes("/artifacts")
          ? jsonResponse({ items: [artifact("pdf-1", "resume_pdf"), artifact("html-1", "resume_html")] })
          : jsonResponse(detail()),
      ),
    );

    expect(await screen.findByText(/2 קבצים/)).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "מעבר לגרסה" })).toHaveLength(1);
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
    expect(screen.queryByText("נשמר תצלום משרה חדש")).not.toBeInTheDocument();
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
