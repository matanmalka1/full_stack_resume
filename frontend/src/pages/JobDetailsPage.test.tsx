import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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

const artifact = (overrides: Partial<ArtifactVersion>): ArtifactVersion => ({
  approved_at: null,
  artifact_id: "artifact-1",
  artifact_type: "resume_pdf",
  content_hash: "hash",
  created_at: "2026-09-06T08:00:00Z",
  emphasis: null,
  facts_version: null,
  id: "artifact-version-1",
  job_snapshot_id: "snap-1",
  lifecycle_status: "rendered",
  logical_name: "resume.pdf",
  metadata: {},
  profile: null,
  revision_id: "revision-2",
  submitted_at: null,
  track: null,
  version_number: 1,
  ...overrides,
});

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
  it("places the job under the applications breadcrumb", async () => {
    renderPage();

    expect(await screen.findByRole("navigation", { name: "פירורי לחם" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "מועמדויות" })).toHaveAttribute("href", "/");
    /* Awaited, not read: the breadcrumb trail renders while the projection is still in
       flight - with "פרטי משרה" as the current crumb - so the navigation landmark is
       present one tick before the company is. Reading the company synchronously after it
       asserted the record's crumb against the loading state. */
    expect(await screen.findByText("Acme – Backend Engineer")).toHaveAttribute("aria-current", "page");
  });

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

    expect(await screen.findByText("ממתין לניתוח המשרה")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "מעקב גיוס" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "עדכון סטטוס ומשימות" }));
    expect(await screen.findByRole("dialog", { name: "ניהול מועמדות: Acme" })).toBeInTheDocument();
    expect(screen.getByText("שיחת מגייס")).toBeInTheDocument();
  });

  it("keeps recruitment details in the manager without duplicating application metadata", async () => {
    renderPage();

    const jobHeading = await screen.findByRole("heading", { name: "מודעת המשרה" });
    const updateButton = screen.getByRole("button", { name: "עדכון נוסח המשרה" });
    const textDisclosure = screen.getByText("הצגת נוסח המשרה השמור");
    expect(jobHeading.compareDocumentPosition(updateButton) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(updateButton.compareDocumentPosition(textDisclosure) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.queryByText("פרטים נוספים על המועמדות")).not.toBeInTheDocument();
    expect(screen.queryByText("מקור המועמדות")).not.toBeInTheDocument();

    expect(screen.queryByRole("heading", { name: "מעקב גיוס" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "עדכון סטטוס ומשימות" }));
    expect(await screen.findByLabelText("תוכן ההערה")).toHaveValue("Referral from a former colleague");
    expect(screen.queryByRole("heading", { name: "פרטי המועמדות" })).not.toBeInTheDocument();
  });

  it("keeps artifact files and previous CV revisions collapsed until requested", async () => {
    const artifacts = [
      artifact({ id: "latest-pdf", artifact_id: "latest-pdf", artifact_type: "resume_pdf" }),
      artifact({
        id: "latest-html",
        artifact_id: "latest-html",
        artifact_type: "resume_html",
        logical_name: "resume.html",
      }),
      artifact({
        id: "previous-markdown",
        artifact_id: "previous-markdown",
        artifact_type: "resume_markdown",
        created_at: "2026-09-05T08:00:00Z",
        logical_name: "resume.md",
        revision_id: "revision-1",
      }),
      artifact({
        id: "previous-visual",
        artifact_id: "previous-visual",
        artifact_type: "visual_evidence",
        created_at: "2026-09-05T08:00:00Z",
        logical_name: "resume.png",
        revision_id: "revision-1",
      }),
    ];
    renderPage((input) =>
      Promise.resolve(
        String(input).endsWith("/artifacts") ? jsonResponse({ items: artifacts }) : jsonResponse(detail()),
      ),
    );

    expect(await screen.findByText("הגרסה האחרונה")).toBeInTheDocument();
    expect(screen.queryByText("גרסה קודמת")).not.toBeInTheDocument();
    expect(screen.queryByText("קובץ PDF של קורות החיים")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "הצגת הקבצים (2)" }));
    expect(screen.getByText("קובץ PDF של קורות החיים")).toBeInTheDocument();
    expect(screen.getByText("קובץ HTML של קורות החיים")).toBeInTheDocument();
    expect(screen.queryByText("קורות החיים ב־Markdown")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "הצגת גרסאות קודמות (1)" }));
    expect(screen.getByText("גרסה קודמת")).toBeInTheDocument();
    expect(screen.queryByText("קורות החיים ב־Markdown")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "הצגת הקבצים (2)" }));
    expect(screen.getByText("קורות החיים ב־Markdown")).toBeInTheDocument();
    expect(screen.getByText("צילום מסך של התצוגה")).toBeInTheDocument();
  });

  it("copies the complete stored job text from inside its disclosure", async () => {
    const storedText = "Senior Backend Engineer\n\nResponsibilities:\nBuild reliable services.";
    const writeText = vi.fn(() => Promise.resolve());
    vi.stubGlobal("navigator", {
      clipboard: { writeText },
      userAgent: window.navigator.userAgent,
    });
    renderPage((input) =>
      Promise.resolve(
        String(input).endsWith("/artifacts")
          ? jsonResponse({ items: [] })
          : jsonResponse({
              ...detail(),
              latest_snapshot: { ...detail().latest_snapshot, job_text: storedText },
            }),
      ),
    );

    fireEvent.click(await screen.findByText("הצגת נוסח המשרה השמור"));
    const copyButton = screen.getByRole("button", { name: "העתקת נוסח המשרה" });
    expect(copyButton.querySelector(".lucide-copy")).not.toBeNull();
    fireEvent.click(copyButton);

    await waitFor(() => expect(writeText).toHaveBeenCalledWith(storedText));
    expect(screen.getByText("נוסח המשרה הועתק")).toBeInTheDocument();
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
