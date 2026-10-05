import { describe, expect, it } from "vitest";

import type { ApplicationDetail, Operation } from "@/api/contracts";
import { detail as baseDetail, settings } from "@/test/fixtures";

import { autoDraftIsAnticipated, continuationAwaitsProjection, continuedDraft } from "./autoDraft";

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
    available_actions: ["edit_matching_configuration", "create_draft"],
    recommended_action: "create_draft",
    ...overrides,
  });

const automatic = settings({ auto_generate_when_review_not_required: true, provider_configured: true });

const succeeded = () =>
  queued({
    status: "succeeded",
    is_terminal: true,
    outputs: [{ output_type: "job_analysis", output_id: "analysis-1" }],
  });

const drafting = queued({ id: "op-draft", operation_type: "create_draft" });

/* Before the first analysis lands there is no document. */
const undocumented = (overrides: Partial<ApplicationDetail> = {}): ApplicationDetail =>
  baseDetail({ document_id: null, document_hash: null, document_analysis_id: null, ...overrides });

describe("continuedDraft", () => {
  it("follows the draft the server queued for the document this analysis created", () => {
    expect(continuedDraft(succeeded(), analyzed({ active_operation: drafting }))).toEqual(drafting);
  });

  it.each(["other-analysis", "no-output", "cancelled", "other-application", "no-draft", "other-operation"])(
    "follows nothing with %s",
    (scenario) => {
      const operation = succeeded();
      const projection = analyzed({ active_operation: drafting });
      if (scenario === "other-analysis") projection.document_analysis_id = "analysis-2";
      if (scenario === "no-output") operation.outputs = [];
      if (scenario === "cancelled") operation.status = "cancelled";
      if (scenario === "other-application") operation.application_id = "app-2";
      if (scenario === "no-draft") projection.active_operation = null;
      if (scenario === "other-operation") projection.active_operation = queued({ id: "op-2" });
      expect(continuedDraft(operation, projection)).toBeNull();
    },
  );
});

describe("continuationAwaitsProjection", () => {
  it("holds between the analysis succeeding and the projection naming its document", () => {
    expect(continuationAwaitsProjection(succeeded(), automatic, undocumented())).toBe(true);
  });

  it("ends once the projection names the document, or when the opt-in is off", () => {
    expect(continuationAwaitsProjection(succeeded(), automatic, analyzed())).toBe(false);
    expect(continuationAwaitsProjection(succeeded(), settings({ provider_configured: true }), undocumented())).toBe(
      false,
    );
  });
});

describe("autoDraftIsAnticipated", () => {
  it("announces the draft while a first analysis runs with the opt-in on", () => {
    expect(autoDraftIsAnticipated(automatic, undocumented({ active_operation: queued({ status: "running" }) }))).toBe(
      true,
    );
    expect(autoDraftIsAnticipated(automatic, analyzed({ active_operation: queued({ status: "running" }) }))).toBe(
      false,
    );
  });
});
