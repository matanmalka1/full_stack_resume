import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import type {
  ApplicationDetail,
  ApprovedRevision,
  Operation,
  ReconciliationReport,
  Settings,
  ValidationRun,
  WorkingDraft,
} from "@/api/contracts";

/* Record builders for the §9 projection shapes, and the one route harness the screens
   that read them are rendered through.

   They live here rather than in one feature's test file because the same Application,
   draft, and revision are what the draft editor, the revision screen, and settings each
   see; three copies of the same record drift apart, and a projection field added to the
   contracts then has three places to be remembered. Each builder takes overrides, so a
   test still states only the fields it is about. */

export const json = (value: unknown, status = 200, headers: Record<string, string> = {}) =>
  new Response(JSON.stringify(value), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });

export const detail = (overrides: Partial<ApplicationDetail> = {}): ApplicationDetail => ({
  recruitment_status: "saved",
  allowed_recruitment_transitions: ["withdrawn", "closed"],
  recruitment_timeline: [],
  preparation_state: "ready_for_approval",
  working_draft_state: "validated",
  review_reasons: [],
  stale_reasons: [],
  warnings: [],
  blocked_actions: [],
  active_job_snapshot_id: "snapshot-1",
  active_analysis_id: "analysis-1",
  active_selection_plan_id: "plan-1",
  active_working_draft_id: "draft-1",
  latest_approved_revision_id: null,
  latest_ready_revision_id: null,
  newer_draft_in_progress: false,
  available_actions: ["approve"],
  recommended_action: "approve",
  application: {
    id: "app-1",
    company: "Acme",
    target_role: "Engineer",
    current_status: "saved",
    notes: "",
    source: "manual",
    created_at: "2026-08-24T00:00:00Z",
    updated_at: "2026-08-24T00:00:00Z",
  },
  latest_snapshot: {
    id: "snapshot-1",
    application_id: "app-1",
    version_number: 1,
    job_text: "Engineer",
    captured_at: "2026-08-24T00:00:00Z",
    source_metadata: {},
    content_hash: "snapshot-hash",
  },
  ...overrides,
});

export const draft = (overrides: Partial<WorkingDraft> = {}): WorkingDraft => ({
  id: "draft-1",
  application_id: "app-1",
  active: true,
  edit_version: 4,
  content_hash: "draft-hash",
  job_analysis_id: "analysis-1",
  selection_plan_id: "plan-1",
  latest_validation_run_id: "run-1",
  latest_validation_passed: true,
  source: {},
  outline: {
    headline: {
      claim_id: "headline",
      text: "Engineer",
      claim_type: "headline",
      style: "headline",
      fact_ids: [],
    },
    contacts: [],
    sections: [],
  },
  created_at: "2026-08-24T00:00:00Z",
  updated_at: "2026-08-24T00:00:00Z",
  ...overrides,
});

export const validation = (overrides: Partial<ValidationRun> = {}): ValidationRun => ({
  validation_run_id: "run-1",
  application_id: "app-1",
  working_draft_id: "draft-1",
  edit_version: 4,
  content_hash: "draft-hash",
  passed: true,
  report: { passed: true, groups: { facts: true }, evidence: { checked: 3 }, issues: [] },
  ...overrides,
});

export const revision = (overrides: Partial<ApprovedRevision> = {}): ApprovedRevision => ({
  id: "revision-1",
  application_id: "app-1",
  version_number: 1,
  approved_at: "2026-08-24T00:00:00Z",
  working_draft_id: "draft-1",
  draft_edit_version: 4,
  draft_content_hash: "draft-hash",
  job_snapshot_id: "snapshot-1",
  job_analysis_id: "analysis-1",
  selection_plan_id: "plan-1",
  facts_version: "facts-1",
  validation_run_id: "run-1",
  decision_provenance: { client: "web" },
  ready_qualified: true,
  html_artifact_version_id: "html-1",
  pdf_artifact_version_id: "pdf-1",
  ready_validation: { passed: true, groups: { artifacts: true }, evidence: {}, issues: [] },
  ...overrides,
});

export const operation = (): Operation => ({
  id: "op-render",
  application_id: "app-1",
  operation_type: "render_revision",
  status: "queued",
  phase: "queued",
  is_terminal: false,
  available_actions: ["cancel"],
  outputs: [],
  message: "",
  created_at: "2026-08-24T00:00:00Z",
});

export const settings = (overrides: Partial<Settings> = {}): Settings => ({
  edit_version: 0,
  auto_generate_when_review_not_required: false,
  ai_enabled: false,
  ai_enabled_override: null,
  default_execution_mode: "deterministic",
  default_ai_model: "gpt-5.6-terra",
  default_reasoning_effort: "medium",
  available_ai_models: [
    {
      id: "gpt-5.6-luna",
      label: "GPT-5.6 Luna",
      input_per_million_usd: "0.20",
      cached_input_per_million_usd: "0.02",
      output_per_million_usd: "1.20",
      recommended: false,
      pricing_version: "openai-2026-09-03",
      pricing_source: "https://developers.openai.com/api/docs/models/compare",
    },
    {
      id: "gpt-5.6-terra",
      label: "GPT-5.6 Terra",
      input_per_million_usd: "2.00",
      cached_input_per_million_usd: "0.20",
      output_per_million_usd: "12.00",
      recommended: true,
      pricing_version: "openai-2026-09-03",
      pricing_source: "https://developers.openai.com/api/docs/models/compare",
    },
  ],
  provider_configured: false,
  ui_density: "comfortable",
  ui_text_size: "normal",
  updated_at: null,
  ...overrides,
});

export const reconciliationReport = (overrides: Partial<ReconciliationReport> = {}): ReconciliationReport => ({
  passed: true,
  artifact_versions_checked: 4,
  problems: [],
  fact_lifecycle: {
    passed: true,
    fact_counts: { canonical: 3, pending: 1 },
    tracked_facts: 4,
    facts_version: "facts-version-1",
    lifecycle_version: "lifecycle-version-1",
    problems: [],
    journal_prepared: 0,
    journal_quarantined: 0,
  },
  ...overrides,
});

export const renderRoute = (entry: string, path: string, element: ReactElement) => {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false, refetchInterval: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[entry]}>
        <Routes>
          <Route element={element} path={path} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
};
