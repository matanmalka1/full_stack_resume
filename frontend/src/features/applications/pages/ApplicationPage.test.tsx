import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
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
    content_check: "none",
    review_reasons: [],
    warnings: [],
    active_job_snapshot_id: "snap-1",
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
      source_hash: "hash-1",
    },
  }) as ApplicationDetail;

const artifact = (overrides: Partial<ArtifactVersion>): ArtifactVersion => ({
  artifact_id: "artifact-1",
  artifact_type: "provider_response",
  content_hash: "hash",
  created_at: "2026-09-06T08:00:00Z",
  emphasis: null,
  facts_version: null,
  id: "artifact-version-1",
  job_snapshot_id: "snap-1",
  lifecycle_status: "rendered",
  logical_name: "provider-response.json",
  metadata: {},
  profile: null,
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
  it("shows the route not-found frame without presenting a missing Application as a workflow step", async () => {
    renderPage(() =>
      Promise.resolve(
        new Response(
          JSON.stringify({
            type: "about:blank#not-found",
            title: "Not found",
            status: 404,
            code: "APPLICATION_NOT_FOUND",
            detail: "unknown application: app-1",
          }),
          { status: 404, headers: { "Content-Type": "application/problem+json" } },
        ),
      ),
    );

    expect(await screen.findByRole("heading", { name: "העמוד לא נמצא" })).toBeInTheDocument();
    expect(screen.queryByText("שלבי הכנת קורות החיים")).not.toBeInTheDocument();
  });

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

  it("links a Ready application to its ready step and to the draft from the workflow spine", async () => {
    renderPage((input) =>
      Promise.resolve(
        String(input).endsWith("/artifacts")
          ? jsonResponse({ items: [] })
          : jsonResponse({
              ...detail(),
              preparation_state: "ready",
              document_id: "doc-1",
            }),
      ),
    );

    expect(await screen.findByRole("link", { name: /מוכן למסירה/ })).toHaveAttribute(
      "href",
      "/applications/app-1/ready",
    );
    expect(screen.getByRole("link", { name: /טיוטה ואימות/ })).toHaveAttribute("href", "/applications/app-1/draft");
  });

  it("keeps recruitment state off the CV preparation step", async () => {
    renderPage();

    expect(await screen.findByRole("heading", { name: "ניתוח והתאמה" })).toBeInTheDocument();
    expect(screen.queryByText("סינון טלפוני / HR")).not.toBeInTheDocument();
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

  it("keeps the engine's provider evidence collapsed until requested", async () => {
    const artifacts = [
      artifact({
        id: "newest",
        artifact_id: "newest",
        created_at: "2026-09-06T08:00:00Z",
        metadata: { task: "propose_analysis", provider: "openai", model: "gpt-5.6-terra" },
      }),
      artifact({ id: "second", artifact_id: "second", created_at: "2026-09-05T08:00:00Z" }),
      artifact({ id: "third", artifact_id: "third", created_at: "2026-09-04T08:00:00Z" }),
      artifact({ id: "oldest", artifact_id: "oldest", created_at: "2026-09-03T08:00:00Z" }),
    ];
    renderPage((input) =>
      Promise.resolve(
        String(input).endsWith("/artifacts")
          ? jsonResponse({ items: artifacts })
          : jsonResponse({
              ...detail(),
              latest_analysis: {
                id: "analysis-1",
                application_id: "app-1",
                job_snapshot_id: "snap-1",
                version_number: 1,
                analysis: {},
                fit_level: "high",
                gaps: [],
                provider: "openai",
                model: "gpt-5.6-terra",
                created_at: "2026-08-24T07:00:00Z",
              },
            }),
      ),
    );

    const artifactsSummary = (await screen.findAllByText("תוצרי המנוע"))[0];
    expect(artifactsSummary.closest("details")).not.toHaveAttribute("open");
    fireEvent.click(artifactsSummary);
    /* A row is named by the task that produced it, with its model; a record without a
       known task keeps the artifact type's name. */
    const artifactsList = await screen.findByRole("region", { name: "תוצרי המנוע" });
    expect(within(artifactsList).getByText("ניתוח המשרה")).toBeInTheDocument();
    expect(within(artifactsList).getByText("gpt-5.6-terra")).toBeInTheDocument();
    expect(within(artifactsList).getAllByText("תשובת ספק ה־AI")).toHaveLength(2);

    fireEvent.click(screen.getByRole("button", { name: "הצגת רשומות קודמות (1)" }));
    expect(within(artifactsList).getAllByText("תשובת ספק ה־AI")).toHaveLength(3);
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

  it("blocks a job posting update that changes nothing, without a request", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) =>
      Promise.resolve(String(input).endsWith("/artifacts") ? jsonResponse({ items: [] }) : jsonResponse(detail())),
    );
    renderPage(fetchMock);

    fireEvent.click(await screen.findByRole("button", { name: "עדכון נוסח המשרה" }));
    fireEvent.click(screen.getByRole("button", { name: "יצירת התצלום החדש" }));

    expect(
      await screen.findByText("הנוסח והכתובת זהים לתצלום הקיים. יש לערוך את אחד השדות לפני השמירה."),
    ).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([input]) => String(input).endsWith("/job-snapshots"))).toBe(false);
  });

  it("blocks a job posting update with a malformed URL, without a request", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) =>
      Promise.resolve(String(input).endsWith("/artifacts") ? jsonResponse({ items: [] }) : jsonResponse(detail())),
    );
    renderPage(fetchMock);

    fireEvent.click(await screen.findByRole("button", { name: "עדכון נוסח המשרה" }));
    fireEvent.change(screen.getByLabelText("טקסט המשרה"), {
      target: { value: "Senior Backend Engineer, now remote" },
    });
    fireEvent.change(screen.getByLabelText("כתובת המשרה"), { target: { value: "not-a-url" } });
    fireEvent.click(screen.getByRole("button", { name: "יצירת התצלום החדש" }));

    expect(await screen.findByText("הכתובת חייבת להתחיל ב-http:// או https:// וללא רווחים.")).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([input]) => String(input).endsWith("/job-snapshots"))).toBe(false);
  });
});
