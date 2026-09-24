import { describe, expect, it } from "vitest";

import type { ApplicationDetail, Operation, Settings } from "@/api/contracts";

import { autoDraftSources } from "./autoDraft";

const detail = (overrides: Partial<ApplicationDetail> = {}): ApplicationDetail => ({
  recruitment_status: "saved",
  allowed_recruitment_transitions: ["withdrawn", "closed"],
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
    current_status: "saved",
    notes: "",
    created_at: "2026-08-24T07:00:00Z",
    updated_at: "2026-08-24T07:00:00Z",
  },
  latest_snapshot: {
    id: "snap-1",
    application_id: "app-1",
    version_number: 1,
    job_text: "Senior Backend Engineer",
    captured_at: "2026-08-24T07:00:00Z",
    source_metadata: {},
    source_hash: "hash-1",
  },
  ...overrides,
});

const queued = (overrides: Partial<Operation> = {}): Operation => ({
  id: "op-1",
  application_id: "app-1",
  operation_type: "analyze_job",
  status: "queued",
  is_terminal: false,
  phase: "queued",
  message: "",
  created_at: "2026-08-24T07:00:00Z",
  outputs: [],
  available_actions: ["cancel"],
  ...overrides,
});

/* An Application whose analysis is on record and active. The base fixture leaves both
   fields absent, which is the pre-analysis state, so only the tests that opt in here
   render the analysis panel. */
const analyzed_detail = (overrides: Partial<ApplicationDetail> = {}): ApplicationDetail =>
  detail({
    preparation_state: "ready_to_draft",
    available_actions: ["create_draft"],
    recommended_action: "create_draft",
    active_analysis_id: "analysis-1",
    latest_analysis: {
      id: "analysis-1",
      application_id: "app-1",
      job_snapshot_id: "snap-1",
      version_number: 1,
      analysis: {
        analysis_version: "3.0",
        track: "development",
        profile: "development",
        emphasis: "development-backend",
        language: "en",
        summary: "The posting is a backend role.",
        keywords: ["FastAPI", "PostgreSQL"],
        requirements: [],
        issues: [],
        source_coverage: 1,
        user_override: {},
      },
      fit_level: "high",
      fit_score: 1,
      gaps: [],
      provider: "openai",
      model: "gpt-5.6-terra",
      created_at: "2026-08-24T07:00:00Z",
    },
    ...overrides,
  });

/* No AI provider configured. Named for the draft lane, which still has a deterministic
   path; analysis does not - these settings are simply the state in which analysis cannot
   run at all. */
const deterministicSettings: Settings = {
  edit_version: 0,
  auto_generate_when_review_not_required: false,
  ai_enabled: false,
  ai_enabled_override: null,
  default_execution_mode: "deterministic",
  default_ai_model: "gpt-5.6-terra",
  default_reasoning_effort: "medium",
  available_ai_models: [],

  provider_configured: false,
  ui_density: "comfortable",
  ui_text_size: "normal",
  ui_theme: "system",
  updated_at: null,
};

describe("autoDraftSources", () => {
  it.each(["blocked", "new-analysis", "new-plan", "inactive-output", "cancelled", "deleted", "existing-draft"])(
    "does not authorize a restored automatic draft with %s",
    (scenario) => {
      const analyzed = queued({
        status: "succeeded",
        is_terminal: true,
        outputs: [
          { output_type: "job_analysis", output_id: "analysis-1", active: true },
          { output_type: "selection_plan", output_id: "plan-1", active: true },
        ],
      });
      const projection = analyzed_detail({ active_selection_plan_id: "plan-1" });
      if (scenario === "blocked")
        projection.blocked_actions = [{ action: "create_draft", reasons: ["KNOWLEDGE_QUARANTINED"] }];
      if (scenario === "new-analysis") projection.active_analysis_id = "analysis-2";
      if (scenario === "new-plan") projection.active_selection_plan_id = "plan-2";
      if (scenario === "inactive-output")
        analyzed.outputs.forEach((output) => {
          output.active = false;
        });
      if (scenario === "cancelled") analyzed.status = "cancelled";
      if (scenario === "deleted") projection.application.deleted_at = "2026-09-14T07:00:00Z";
      if (scenario === "existing-draft") projection.active_working_draft_id = "draft-1";
      expect(
        autoDraftSources(
          analyzed,
          { ...deterministicSettings, auto_generate_when_review_not_required: true },
          projection,
        ),
      ).toBeNull();
    },
  );
});
