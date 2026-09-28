import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import type {
  ApplicationDetail,
  CVDocument,
  DocumentCheck,
  Operation,
  ReconciliationReport,
  Settings,
} from "@/api/contracts";

/* Record builders for the §9 projection shapes, and the one route harness the screens
   that read them are rendered through.

   They live here rather than in one feature's test file because the same Application and
   document are what the draft editor, the ready screen, and settings each see; three copies of the same record drift apart, and a projection field added to the
   contracts then has three places to be remembered. Each builder takes overrides, so a
   test still states only the fields it is about. */

/* A document hash has the shape the contract requires: 64 lowercase hex characters. */
export const HASH = "a".repeat(64);
export const OTHER_HASH = "b".repeat(64);

export const json = (value: unknown, status = 200, headers: Record<string, string> = {}) =>
  new Response(JSON.stringify(value), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });

export const detail = (overrides: Partial<ApplicationDetail> = {}): ApplicationDetail => ({
  recruitment_status: "saved",
  allowed_recruitment_transitions: ["withdrawn", "closed"],
  recruitment_timeline: [],
  preparation_state: "draft_in_progress",
  document_state: "draft",
  content_check: "passed",
  review_reasons: [],
  warnings: [],
  blocked_actions: [],
  active_job_snapshot_id: "snapshot-1",
  latest_analysis_id: "analysis-1",
  document_id: "doc-1",
  document_hash: HASH,
  document_analysis_id: "analysis-1",
  approved_at: null,
  last_render_error: null,
  available_actions: ["edit", "approve"],
  recommended_action: "approve",
  application: {
    id: "app-1",
    company: "Acme",
    target_role: "Engineer",
    current_status: "saved",
    notes: "",
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
    source_hash: "snapshot-hash",
  },
  ...overrides,
});

export const cvDocument = (overrides: Partial<CVDocument> = {}): CVDocument => ({
  id: "doc-1",
  application_id: "app-1",
  analysis_id: "analysis-1",
  document_hash: HASH,
  built_with: { profile_version: "profile-1", selection_policy_version: "policy-1" },
  language: "en",
  selection: {
    emphasis: "development-balanced",
    emphasis_override: null,
    selected_fact_ids: [],
    pinned_fact_ids: [],
    excluded_fact_ids: [],
    proposed_by: null,
    proposal_rationale: null,
    candidates: [],
  },
  content: {},
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
  facts: [],
  document_state: "draft",
  content_check: "passed",
  content_report: { passed: true, groups: { facts: true }, evidence: { checked: 3 }, issues: [] },
  approved_at: null,
  last_render_error: null,
  created_at: "2026-08-24T00:00:00Z",
  updated_at: "2026-08-24T00:00:00Z",
  ...overrides,
});

export const documentCheck = (overrides: Partial<DocumentCheck> = {}): DocumentCheck => ({
  application_id: "app-1",
  document_id: "doc-1",
  document_hash: HASH,
  document_state: "draft",
  content_check: "passed",
  pending_claim_ids: [],
  passed: true,
  report: { passed: true, groups: { facts: true }, evidence: { checked: 3 }, issues: [] },
  approved_at: null,
  ...overrides,
});

export const operation = (): Operation => ({
  id: "op-render",
  application_id: "app-1",
  operation_type: "render_document",
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
  ui_theme: "system",
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
