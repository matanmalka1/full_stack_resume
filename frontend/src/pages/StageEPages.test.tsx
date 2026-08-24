import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { ApplicationDetail, ApprovedRevision, Operation, Settings, ValidationRun, WorkingDraft } from "../api/contracts";
import { ApprovalPage } from "./ApprovalPage";
import { ReadyPage } from "./ReadyPage";
import { RenderPage } from "./RenderPage";
import { SettingsPage } from "./SettingsPage";
import { ValidationPage } from "./ValidationPage";

const json = (value: unknown, status = 200, headers: Record<string, string> = {}) =>
  new Response(JSON.stringify(value), { status, headers: { "Content-Type": "application/json", ...headers } });

const detail = (overrides: Partial<ApplicationDetail> = {}): ApplicationDetail => ({
  recruitment_status: "saved",
  preparation_state: "ready_for_approval",
  working_draft_state: "validated",
  review_reasons: [], stale_reasons: [], warnings: [], blocked_actions: [],
  active_job_snapshot_id: "snapshot-1",
  active_analysis_id: "analysis-1",
  active_selection_plan_id: "plan-1",
  active_working_draft_id: "draft-1",
  latest_approved_revision_id: null,
  latest_ready_revision_id: null,
  newer_draft_in_progress: false,
  available_actions: ["approve"], recommended_action: "approve",
  application: { id: "app-1", company: "Acme", target_role: "Engineer", current_status: "saved", notes: "", source: "manual", created_at: "2026-08-24T00:00:00Z", updated_at: "2026-08-24T00:00:00Z" },
  latest_snapshot: { id: "snapshot-1", application_id: "app-1", version_number: 1, job_text: "Engineer", captured_at: "2026-08-24T00:00:00Z", source_metadata: {}, content_hash: "snapshot-hash" },
  ...overrides,
});

const draft = (overrides: Partial<WorkingDraft> = {}): WorkingDraft => ({
  id: "draft-1", application_id: "app-1", active: true, edit_version: 4, content_hash: "draft-hash",
  job_analysis_id: "analysis-1", selection_plan_id: "plan-1", latest_validation_run_id: "run-1", latest_validation_passed: true,
  source: {}, outline: { headline: { claim_id: "headline", text: "Engineer", claim_type: "headline", style: "headline", fact_ids: [] }, contacts: [], sections: [] },
  created_at: "2026-08-24T00:00:00Z", updated_at: "2026-08-24T00:00:00Z", ...overrides,
});

const validation = (overrides: Partial<ValidationRun> = {}): ValidationRun => ({
  validation_run_id: "run-1", application_id: "app-1", working_draft_id: "draft-1", edit_version: 4,
  content_hash: "draft-hash", passed: true,
  report: { passed: true, groups: { facts: true }, evidence: { checked: 3 }, issues: [] }, ...overrides,
});

const revision = (overrides: Partial<ApprovedRevision> = {}): ApprovedRevision => ({
  id: "revision-1", application_id: "app-1", version_number: 1, approved_at: "2026-08-24T00:00:00Z",
  working_draft_id: "draft-1", draft_edit_version: 4, draft_content_hash: "draft-hash",
  job_snapshot_id: "snapshot-1", job_analysis_id: "analysis-1", selection_plan_id: "plan-1", facts_version: "facts-1",
  validation_run_id: "run-1", decision_provenance: { client: "web" }, ready_qualified: true,
  html_artifact_version_id: "html-1", pdf_artifact_version_id: "pdf-1",
  ready_validation: { passed: true, groups: { artifacts: true }, evidence: {}, issues: [] }, ...overrides,
});

const operation = (): Operation => ({
  id: "op-render", application_id: "app-1", operation_type: "render_revision", status: "queued", phase: "queued",
  is_terminal: false, available_actions: ["cancel"], outputs: [], message: "", created_at: "2026-08-24T00:00:00Z",
});

const settings = (overrides: Partial<Settings> = {}): Settings => ({
  edit_version: 0, auto_generate_when_review_not_required: false, ai_enabled: false, ai_enabled_override: null,
  default_execution_mode: "deterministic", open_browser_on_launch: true, provider_configured: false,
  ui_density: "comfortable", ui_text_size: "normal", updated_at: null, ...overrides,
});

const renderRoute = (entry: string, path: string, element: ReactElement) => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, refetchInterval: false, gcTime: 0 }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[entry]}><Routes>
    <Route element={element} path={path} />
    <Route element={<h1>פעולה</h1>} path="/operations/:operationId" />
    <Route element={<h1>רינדור</h1>} path="/approved-revisions/:approvedRevisionId/render" />
    <Route element={<h1>אימות</h1>} path="/applications/:applicationId/validation" />
  </Routes></MemoryRouter></QueryClientProvider>);
};

beforeEach(() => {
  /* jsdom exposes HTMLDialogElement but does not implement its modal methods. Mirror
     the observable native state so the shared Dialog component can be exercised. */
  Object.defineProperty(HTMLDialogElement.prototype, "showModal", {
    configurable: true,
    value: vi.fn(function (this: HTMLDialogElement) {
      this.setAttribute("open", "");
    }),
  });
  Object.defineProperty(HTMLDialogElement.prototype, "close", {
    configurable: true,
    value: vi.fn(function (this: HTMLDialogElement) {
      this.removeAttribute("open");
      this.dispatchEvent(new Event("close"));
    }),
  });
});

afterEach(() => { vi.unstubAllGlobals(); sessionStorage.clear(); });

describe("ValidationPage", () => {
  it("renders hard issues as blockers and soft issues as warnings without dropping unknown values", async () => {
    const run = validation({ passed: false, report: { passed: false, groups: { unknown_group: false }, evidence: { opaque: true }, issues: [
      { group: "unknown_group", code: "UNKNOWN_HARD", hard: true, message: "Hard issue" },
      { group: "unknown_group", code: "UNKNOWN_SOFT", hard: false, message: "Soft issue" },
    ] } });
    vi.stubGlobal("fetch", vi.fn((input: string | URL | Request) => Promise.resolve(json(String(input).includes("validation-runs") ? run : String(input).includes("working-drafts") ? draft() : detail({ working_draft_state: "validation_failed" })))));
    renderRoute("/applications/app-1/validation", "/applications/:applicationId/validation", <ValidationPage />);
    expect(await screen.findByText("Hard issue")).toBeInTheDocument();
    expect(screen.getByText("Soft issue")).toBeInTheDocument();
    expect(screen.getByText(/UNKNOWN_HARD/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "אימות מחדש" })).toBeInTheDocument();
  });

  it("posts the exact edit version and exposes approval only after a passing response", async () => {
    const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
      const url = String(input);
      if (init?.method === "POST") return Promise.resolve(json(validation()));
      return Promise.resolve(json(url.includes("working-drafts") ? draft({ latest_validation_run_id: null }) : detail({ working_draft_state: "editing" })));
    });
    vi.stubGlobal("fetch", fetchMock);
    renderRoute("/applications/app-1/validation", "/applications/:applicationId/validation", <ValidationPage />);
    const validate = await screen.findByRole("button", { name: "אימות הטיוטה" });
    await waitFor(() => expect(validate).toBeEnabled());
    fireEvent.click(validate);
    expect(await screen.findByRole("link", { name: "מעבר לאישור" })).toBeInTheDocument();
    const request = fetchMock.mock.calls.find((call) => call[1]?.method === "POST");
    expect(JSON.parse(String(request?.[1]?.body))).toEqual({ expected_edit_version: 4 });
  });
});

describe("ApprovalPage", () => {
  it("requires the local warning checkbox and never sends an acknowledgement field", async () => {
    const warned = validation({ report: { passed: true, groups: {}, evidence: {}, issues: [{ group: "copy", code: "SOFT", hard: false, message: "Review wording" }] } });
    const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
      const url = String(input);
      if (init?.method === "POST") return Promise.resolve(json({ revision_id: "revision-1", application_id: "app-1", version: 1, decision_record_id: "decision-1", markdown_artifact_version_id: "md-1", manifest_artifact_version_id: "manifest-1" }, 201));
      return Promise.resolve(json(url.includes("validation-runs") ? warned : url.includes("working-drafts") ? draft() : detail()));
    });
    vi.stubGlobal("fetch", fetchMock);
    renderRoute("/applications/app-1/approval?validation_run_id=run-1", "/applications/:applicationId/approval", <ApprovalPage />);
    const openApproval = await screen.findByRole("button", { name: "פתיחת אישור" });
    await waitFor(() => expect(openApproval).toBeEnabled());
    fireEvent.click(openApproval);
    const approve = await screen.findByRole("button", { name: "אישור הגרסה" });
    expect(approve).toBeDisabled();
    fireEvent.click(screen.getByRole("checkbox")); fireEvent.click(approve);
    await screen.findByRole("heading", { name: "רינדור" });
    const request = fetchMock.mock.calls.find((call) => call[1]?.method === "POST");
    expect(JSON.parse(String(request?.[1]?.body))).toEqual({ expected_edit_version: 4, validation_run_id: "run-1" });
  });

  it("returns VALIDATION_STALE to validation without retrying automatically", async () => {
    const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => init?.method === "POST"
      ? Promise.resolve(json({ type: "about:blank", title: "Stale", status: 412, code: "VALIDATION_STALE", detail: "stale" }, 412))
      : Promise.resolve(json(String(input).includes("validation-runs") ? validation() : String(input).includes("working-drafts") ? draft() : detail())));
    vi.stubGlobal("fetch", fetchMock);
    renderRoute("/applications/app-1/approval", "/applications/:applicationId/approval", <ApprovalPage />);
    const openApproval = await screen.findByRole("button", { name: "פתיחת אישור" });
    await waitFor(() => expect(openApproval).toBeEnabled());
    fireEvent.click(openApproval);
    fireEvent.click(await screen.findByRole("button", { name: "אישור הגרסה" }));
    expect(await screen.findByRole("heading", { name: "אימות" })).toBeInTheDocument();
    expect(fetchMock.mock.calls.filter((call) => call[1]?.method === "POST")).toHaveLength(1);
  });
});

describe("RenderPage and ReadyPage", () => {
  it("renders with the explicit application ID and follows the accepted Operation", async () => {
    const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => init?.method === "POST"
      ? Promise.resolve(json(operation(), 202, { Location: "/api/v1/operations/op-render" }))
      : Promise.resolve(json(revision({ ready_qualified: false, html_artifact_version_id: null, pdf_artifact_version_id: null }))));
    vi.stubGlobal("fetch", fetchMock);
    renderRoute("/approved-revisions/revision-1/render", "/approved-revisions/:approvedRevisionId/render", <RenderPage />);
    const renderButton = await screen.findByRole("button", { name: "יצירת HTML ו־PDF" });
    await waitFor(() => expect(renderButton).toBeEnabled());
    fireEvent.click(renderButton);
    expect(await screen.findByRole("heading", { name: "פעולה" })).toBeInTheDocument();
    const request = fetchMock.mock.calls.find((call) => call[1]?.method === "POST");
    expect(JSON.parse(String(request?.[1]?.body))).toEqual({ application_id: "app-1" });
  });

  it("frames and downloads the exact Ready artifacts", async () => {
    vi.stubGlobal("fetch", vi.fn((input: string | URL | Request) => Promise.resolve(json(String(input).includes("applications") ? detail({ preparation_state: "ready", latest_ready_revision_id: "revision-1" }) : revision()))));
    renderRoute("/approved-revisions/revision-1/ready", "/approved-revisions/:approvedRevisionId/ready", <ReadyPage />);
    const frame = await screen.findByTitle("תצוגה מאושרת של קורות החיים");
    expect(frame).toHaveAttribute("sandbox", "");
    expect(frame).toHaveAttribute("src", "/api/v1/approved-revisions/revision-1/preview?html_artifact_version_id=html-1");
    expect(screen.getByRole("link", { name: "הורדת PDF" })).toHaveAttribute("href", "/api/v1/approved-revisions/revision-1/recruiter-pdf?pdf_artifact_version_id=pdf-1");
  });

  it("creates a child draft from explicit active sources without a provider", async () => {
    const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => init?.method === "POST"
      ? Promise.resolve(json({ ...operation(), id: "op-draft", operation_type: "create_draft" }, 202, { Location: "/api/v1/operations/op-draft" }))
      : Promise.resolve(json(String(input).includes("applications") ? detail({ preparation_state: "ready", working_draft_state: "none" }) : revision())));
    vi.stubGlobal("fetch", fetchMock);
    renderRoute("/approved-revisions/revision-1/ready", "/approved-revisions/:approvedRevisionId/ready", <ReadyPage />);
    fireEvent.click(await screen.findByRole("button", { name: "יצירת טיוטה חדשה" }));
    await waitFor(() =>
      expect(fetchMock.mock.calls.some((call) => call[1]?.method === "POST")).toBe(true),
    );
    const request = fetchMock.mock.calls.find((call) => call[1]?.method === "POST");
    expect(JSON.parse(String(request?.[1]?.body))).toEqual({ job_analysis_id: "analysis-1", selection_plan_id: "plan-1", parent_revision_id: "revision-1" });
  });
});

describe("SettingsPage", () => {
  it("shows provider availability and keeps AI mode unavailable without one", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json(settings(), 200, { ETag: '"settings-0"' })));
    renderRoute("/settings", "/settings", <SettingsPage />);
    expect(await screen.findByText("לא הוגדר ספק AI בסביבת הריצה.")).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "AI" })).toBeDisabled();
  });

  it("saves all product settings under the read ETag", async () => {
    const fetchMock = vi.fn((_input: string | URL | Request, _init?: RequestInit) =>
      Promise.resolve(json(settings({ edit_version: 1 }), 200, { ETag: '"settings-1"' })),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderRoute("/settings", "/settings", <SettingsPage />);
    fireEvent.click(await screen.findByRole("button", { name: "שמירת הגדרות" }));
    await screen.findByRole("status");
    const request = fetchMock.mock.calls.find((call) => call[1]?.method === "PATCH");
    expect((request?.[1]?.headers as Headers).get("If-Match")).toBe('"settings-1"');
    expect(Object.keys(JSON.parse(String(request?.[1]?.body))).sort()).toEqual(["ai_enabled_override", "auto_generate_when_review_not_required", "default_execution_mode", "open_browser_on_launch", "ui_density", "ui_text_size"].sort());
  });
});
