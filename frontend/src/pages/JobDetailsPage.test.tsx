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
  it("owns the job posting and recruitment controls before analysis exists", async () => {
    renderPage();

    expect(await screen.findByRole("heading", { level: 1, name: "Backend Engineer" })).toBeInTheDocument();
    expect(screen.getByText("Acme")).toBeInTheDocument();
    expect(screen.getByText("Backend Engineer")).toBeInTheDocument();
    expect(screen.getByText("Referral from a former colleague")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /פתיחת מודעת המקור.*example\.com/ })).toBeInTheDocument();
    expect(screen.getByText("Senior Backend Engineer")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "שמירת נוסח חדש" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "מעקב גיוס" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "שמירת השלב" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "שמירת הפעולה" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "ניתוח המשרה" })).not.toBeInTheDocument();
  });

  it("shows only a preparation summary and links to its separate workflow", async () => {
    renderPage();

    expect(await screen.findByText("ממתין לניתוח המשרה")).toBeInTheDocument();
    const navigation = screen.getByRole("navigation", { name: "תחומי המועמדות" });
    expect(within(navigation).getByRole("link", { name: "פרטי משרה" })).toHaveAttribute("aria-current", "page");
    expect(within(navigation).getByRole("link", { name: "הכנת קורות החיים" })).toHaveAttribute(
      "href",
      "/applications/app-1/preparation",
    );
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

    fireEvent.click(await screen.findByRole("button", { name: "שמירת נוסח חדש" }));
    fireEvent.change(screen.getByLabelText("טקסט המשרה"), {
      target: { value: "Senior Backend Engineer, now remote" },
    });
    fireEvent.click(screen.getByRole("button", { name: "שמירת נוסח המשרה" }));

    expect(await screen.findByText("נשמר תצלום משרה חדש")).toBeInTheDocument();
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
});
