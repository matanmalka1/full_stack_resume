import { QueryClient } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ApprovedRevision, Operation, Settings, ValidationRun } from "./contracts";
import {
  approvedPreviewSrc,
  approvedRevisionQueryOptions,
  recruiterPdfHref,
  renderApprovedRevision,
} from "./revisions";
import {
  aiRegenerationAvailable,
  executionProvider,
  settingsQueryOptions,
  updateSettings,
} from "./settings";
import {
  approveWorkingDraft,
  validateWorkingDraft,
  validationRunQueryOptions,
} from "./validation";

const json = (value: unknown, status = 200, headers: Record<string, string> = {}) =>
  new Response(JSON.stringify(value), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });

const run = {
  validation_run_id: "run-1",
  application_id: "app-1",
  working_draft_id: "draft-1",
  edit_version: 4,
  content_hash: "hash",
  passed: true,
  report: { passed: true, groups: { novel: true }, issues: [], evidence: { exact: true } },
} as ValidationRun;

const revision = {
  id: "revision-1",
  application_id: "app-1",
  ready_qualified: false,
} as ApprovedRevision;

const operation = {
  id: "op-1",
  application_id: "app-1",
  operation_type: "render_revision",
  status: "queued",
  phase: "queued",
  is_terminal: false,
  available_actions: ["cancel"],
  outputs: [],
  message: "",
  created_at: "2026-08-24T00:00:00Z",
} as Operation;

const settings = {
  edit_version: 2,
  auto_generate_when_review_not_required: false,
  ai_enabled: true,
  ai_enabled_override: null,
  default_execution_mode: "deterministic",
  open_browser_on_launch: true,
  provider_configured: true,
  ui_density: "comfortable",
  ui_text_size: "normal",
} as Settings;

afterEach(() => vi.unstubAllGlobals());

const queryClient = () => new QueryClient({ defaultOptions: { queries: { retry: false } } });

describe("validation and approval clients", () => {
  it("reads a historical ValidationRun by its exact ID without a staleness precheck", async () => {
    const fetchMock = vi.fn().mockResolvedValue(json(run));
    vi.stubGlobal("fetch", fetchMock);
    const result = await queryClient().fetchQuery(validationRunQueryOptions("run 1"));
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/v1/validation-runs/run%201");
    expect(result).toEqual(run);
  });

  it("validates the exact draft edit version", async () => {
    const fetchMock = vi.fn().mockResolvedValue(json(run));
    vi.stubGlobal("fetch", fetchMock);
    await validateWorkingDraft("draft 1", 4);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/v1/working-drafts/draft%201/validate");
    expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))).toEqual({ expected_edit_version: 4 });
  });

  it("approves with only the version and ValidationRun plus the stable key", async () => {
    const fetchMock = vi.fn().mockResolvedValue(json({ revision_id: "revision-1" }, 201));
    vi.stubGlobal("fetch", fetchMock);
    await approveWorkingDraft("draft-1", 4, "run-1", "draft-1:4:run-1");
    expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))).toEqual({ expected_edit_version: 4, validation_run_id: "run-1" });
    expect((fetchMock.mock.calls[0]?.[1]?.headers as Headers).get("Idempotency-Key")).toBe("draft-1:4:run-1");
  });
});

describe("approved revision clients", () => {
  it("reads the exact approved revision", async () => {
    const fetchMock = vi.fn().mockResolvedValue(json(revision));
    vi.stubGlobal("fetch", fetchMock);
    const result = await queryClient().fetchQuery(approvedRevisionQueryOptions("revision 1"));
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/v1/approved-revisions/revision%201");
    expect(result).toEqual(revision);
  });

  it("renders with the explicit application binding and accepted Operation contract", async () => {
    const fetchMock = vi.fn().mockResolvedValue(json(operation, 202, { Location: "/api/v1/operations/op-1" }));
    vi.stubGlobal("fetch", fetchMock);
    await renderApprovedRevision("revision-1", "app-1", "render:revision-1");
    expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))).toEqual({ application_id: "app-1" });
  });

  it("builds preview and download URLs from both explicit identifiers", () => {
    expect(approvedPreviewSrc("revision 1", "html/1")).toBe("/api/v1/approved-revisions/revision%201/preview?html_artifact_version_id=html%2F1");
    expect(recruiterPdfHref("revision 1", "pdf/1")).toBe("/api/v1/approved-revisions/revision%201/recruiter-pdf?pdf_artifact_version_id=pdf%2F1");
  });
});

describe("settings client", () => {
  it("keeps the ETag paired with the Settings read", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json(settings, 200, { ETag: '"settings-2"' })));
    const result = await queryClient().fetchQuery(settingsQueryOptions);
    expect(result).toEqual({ settings, etag: '"settings-2"' });
  });

  it("patches the complete form under If-Match", async () => {
    const fetchMock = vi.fn().mockResolvedValue(json(settings, 200, { ETag: '"settings-3"' }));
    vi.stubGlobal("fetch", fetchMock);
    await updateSettings({
      auto_generate_when_review_not_required: false,
      ai_enabled_override: null,
      default_execution_mode: "deterministic",
      open_browser_on_launch: true,
      ui_density: "comfortable",
      ui_text_size: "normal",
    }, '"settings-2"');
    expect((fetchMock.mock.calls[0]?.[1]?.headers as Headers).get("If-Match")).toBe('"settings-2"');
  });

  it("derives manual execution and regeneration availability from effective settings", () => {
    expect(executionProvider(settings)).toBeUndefined();
    expect(executionProvider({ ...settings, default_execution_mode: "ai" })).toBe("openai");
    expect(aiRegenerationAvailable(settings)).toBe(true);
    expect(aiRegenerationAvailable({ ...settings, ai_enabled: false })).toBe(false);
  });
});
