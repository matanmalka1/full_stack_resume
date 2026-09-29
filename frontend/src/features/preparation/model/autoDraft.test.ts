import { describe, expect, it } from "vitest";

import type { ApplicationDetail, Operation } from "@/api/contracts";
import { HASH, detail as baseDetail, settings } from "@/test/fixtures";

import { autoDraftSources } from "./autoDraft";

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

/* The first analysis created the document with its deterministic selection and no
   content: the one moment an automatic generate may continue into. */
const analyzed = (overrides: Partial<ApplicationDetail> = {}): ApplicationDetail =>
  baseDetail({
    preparation_state: "ready_to_draft",
    content_check: "none",
    available_actions: ["update_selection", "create_draft"],
    recommended_action: "create_draft",
    ...overrides,
  });

const automatic = settings({ auto_generate_when_review_not_required: true });

const succeeded = () =>
  queued({
    status: "succeeded",
    is_terminal: true,
    outputs: [{ output_type: "job_analysis", output_id: "analysis-1", active: true }],
  });

describe("autoDraftSources", () => {
  it("addresses the continuation to the document the analysis created, at its current hash", () => {
    expect(autoDraftSources(succeeded(), automatic, analyzed())).toEqual({
      applicationId: "app-1",
      analysisId: "analysis-1",
      documentHash: HASH,
    });
  });

  it.each(["blocked", "other-analysis", "inactive-output", "cancelled", "deleted", "has-content", "opted-out"])(
    "does not authorize a restored automatic draft with %s",
    (scenario) => {
      const operation = succeeded();
      const projection = analyzed();
      let current = automatic;
      if (scenario === "blocked")
        projection.blocked_actions = [{ action: "create_draft", reasons: ["KNOWLEDGE_QUARANTINED"] }];
      if (scenario === "other-analysis") projection.document_analysis_id = "analysis-2";
      if (scenario === "inactive-output")
        operation.outputs.forEach((output) => {
          output.active = false;
        });
      if (scenario === "cancelled") operation.status = "cancelled";
      if (scenario === "deleted") projection.application.deleted_at = "2026-09-14T07:00:00Z";
      if (scenario === "has-content") projection.preparation_state = "draft_in_progress";
      if (scenario === "opted-out") current = settings();
      expect(autoDraftSources(operation, current, projection)).toBeNull();
    },
  );
});
