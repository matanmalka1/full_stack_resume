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
          {/* Both addresses resolve to this one screen, exactly as `router.tsx` maps them:
              selecting the preparation tab moves the URL to `/preparation` rather than
              leaving a `?tab=` on the other form, so a stub behind that path would test a
              route the application does not have. */}
          <Route element={<ApplicationPage />} path="/applications/:applicationId" />
          <Route element={<ApplicationPage />} path="/applications/:applicationId/preparation" />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("ApplicationPage", () => {
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

  it("links a Ready application to the exact immutable revision, from the preparation tab", async () => {
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

    fireEvent.click(await screen.findByRole("tab", { name: /הכנת קורות חיים/ }));
    expect(await screen.findByRole("link", { name: "צפייה בגרסה המוכנה" })).toHaveAttribute(
      "href",
      "/revisions/revision-7",
    );
  });

  it("reports preparation and recruitment as two separate axes", async () => {
    renderPage();

    /* Two headings, two states, and neither is a step of the other: the CV can be Ready
       while the recruitment status is still a first call, so a single merged "status"
       would be claiming a sequence that does not exist. */
    const preparation = await screen.findByRole("heading", { name: "הכנת קורות חיים" });
    const recruitment = screen.getByRole("heading", { name: "גיוס" });
    expect(preparation.compareDocumentPosition(recruitment) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.getByText("ממתין לניתוח המשרה")).toBeInTheDocument();
    expect(screen.getByText("שיחת מגייס")).toBeInTheDocument();

    /* Reading the recruitment state is not the same as changing it: the transitions and
       the timeline stay in the manager dialog. */
    expect(screen.queryByRole("heading", { name: "מעקב גיוס" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "עדכון סטטוס ומשימות" }));
    expect(await screen.findByRole("dialog", { name: "ניהול מועמדות: Acme" })).toBeInTheDocument();
  });

  it("offers the recommended action as one destination beside the record", async () => {
    renderPage();

    /* The projection recommends `analyze`; the masthead offers it as the way into the
       screen that runs it, never as a second copy of the command itself. */
    expect(await screen.findByRole("link", { name: /ניתוח המשרה/ })).toHaveAttribute(
      "href",
      "/applications/app-1/preparation",
    );
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
        String(input).endsWith("/artifacts") ? jsonResponse({ items: artifacts }) : jsonResponse(detail()),
      ),
    );

    fireEvent.click(await screen.findByRole("tab", { name: /תוצרים/ }));
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
