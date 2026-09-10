import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ApplicationDetail, ArtifactVersion } from "@/api/contracts";
import { ApplicationPage } from "./ApplicationPage";

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
          {/* One address for this screen, exactly as `router.tsx` maps it. The second entry
              here mirrored the second route the table used to carry. */}
          <Route element={<ApplicationPage />} path="/applications/:applicationId" />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("ApplicationPage", () => {
  /* One navigation landmark and one way out. The breadcrumb trail that used to draw
     board › Application above the spine is gone: it claimed a record hierarchy over a
     linear flow, and its only destination the spine did not already offer was the board. */
  it("names the step and offers the board as the only way out of the flow", async () => {
    renderPage();

    expect(screen.getByRole("heading", { name: "ניתוח והתאמה" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "חזרה ללוח המועמדויות" })).toHaveAttribute("href", "/");
    expect(screen.queryByRole("navigation", { name: "פירורי לחם" })).not.toBeInTheDocument();
    /* Awaited: the shell renders before the projection lands, so the record's identity
       arrives a tick after the heading that names its step. */
    expect(await screen.findByText("Acme — Backend Engineer")).toBeInTheDocument();
  });

  it("links a Ready application to the exact immutable revision from the workflow spine", async () => {
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

    expect(await screen.findByRole("link", { name: /מוכן למסירה/ })).toHaveAttribute(
      "href",
      "/revisions/revision-7",
    );
  });

  it("keeps recruitment state off the CV preparation step", async () => {
    renderPage();

    expect(await screen.findByRole("heading", { name: "ניתוח והתאמה" })).toBeInTheDocument();
    expect(screen.queryByText("שיחת מגייס")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "עדכון סטטוס ומשימות" })).not.toBeInTheDocument();
  });

  it("offers the recommended action once inside the active step", async () => {
    renderPage();

    expect(await screen.findByRole("button", { name: /ניתוח המשרה/ })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /ניתוח המשרה/ })).not.toBeInTheDocument();
  });

  it("keeps the saved posting as collapsed reference material", async () => {
    renderPage();

    const postingSummary = await screen.findByText("צפייה בנוסח המשרה שנשמר");
    expect(postingSummary.closest("details")).not.toHaveAttribute("open");
    fireEvent.click(postingSummary);
    expect(postingSummary.closest("details")).toHaveAttribute("open");
    expect(screen.getByRole("heading", { name: "מודעת המשרה" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "עדכון סטטוס ומשימות" })).not.toBeInTheDocument();
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
        id: "legacy-render-image",
        artifact_id: "legacy-render-image",
        artifact_type: "visual_evidence",
        created_at: "2026-09-05T08:00:00Z",
        logical_name: "retired.png",
        revision_id: "revision-1",
      }),
    ];
    renderPage((input) =>
      Promise.resolve(
        String(input).endsWith("/artifacts")
          ? jsonResponse({ items: artifacts })
          : jsonResponse({ ...detail(), preparation_state: "ready", latest_ready_revision_id: "revision-2" }),
      ),
    );

    const artifactsSummary = (await screen.findAllByText("גרסאות וקבצים"))[0];
    expect(artifactsSummary.closest("details")).not.toHaveAttribute("open");
    fireEvent.click(artifactsSummary);
    expect(await screen.findByText("הגרסה האחרונה")).toBeInTheDocument();
    expect(screen.queryByText("גרסה קודמת")).not.toBeInTheDocument();
    expect(screen.queryByText("קובץ PDF של קורות החיים")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "הצגת הקבצים (2)" }));
    expect(screen.getByText("קובץ PDF של קורות החיים")).toBeInTheDocument();
    expect(screen.getByText("קובץ HTML של קורות החיים")).toBeInTheDocument();
    expect(screen.queryByText("קורות החיים ב־Markdown")).not.toBeInTheDocument();
    expect(screen.queryByText("visual_evidence")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "הצגת גרסאות קודמות (1)" }));
    expect(screen.getByText("גרסה קודמת")).toBeInTheDocument();
    expect(screen.queryByText("קורות החיים ב־Markdown")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "הצגת הקבצים (1)" }));
    expect(screen.getByText("קורות החיים ב־Markdown")).toBeInTheDocument();
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
});
