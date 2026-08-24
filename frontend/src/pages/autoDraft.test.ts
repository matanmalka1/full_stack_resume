import { describe, expect, it } from "vitest";

import type { ApplicationDetail, Operation, Settings } from "../api/contracts";
import { autoDraftSources } from "./autoDraft";

const operation = (overrides: Partial<Operation> = {}): Operation => ({
  id: "op-1", application_id: "app-1", operation_type: "analyze_job", status: "succeeded",
  phase: "completed", is_terminal: true, available_actions: [], outputs: [], message: "", created_at: "now", ...overrides,
});
const settings = (enabled = true) => ({ auto_generate_when_review_not_required: enabled }) as Settings;
const detail = (overrides: Partial<ApplicationDetail> = {}) => ({
  application: { id: "app-1" }, review_reasons: [], working_draft_state: "none", active_operation: null,
  active_analysis_id: "analysis-1", active_selection_plan_id: "plan-1", ...overrides,
}) as ApplicationDetail;

describe("autoDraftSources", () => {
  it("returns the exact active source pair after a successful Analyze", () => {
    expect(autoDraftSources(operation(), settings(), detail(), false, false)).toEqual({
      applicationId: "app-1", analysisId: "analysis-1", planId: "plan-1",
    });
  });

  it("does nothing when the setting is off or the Operation is not a successful Analyze", () => {
    expect(autoDraftSources(operation(), settings(false), detail(), false, false)).toBeNull();
    expect(autoDraftSources(operation({ status: "failed" }), settings(), detail(), false, false)).toBeNull();
    expect(autoDraftSources(operation({ operation_type: "render_revision" }), settings(), detail(), false, false)).toBeNull();
  });

  it("does nothing when review or another Operation remains", () => {
    expect(autoDraftSources(operation(), settings(), detail({ review_reasons: [{}] as never }), false, false)).toBeNull();
    expect(autoDraftSources(operation(), settings(), detail({ active_operation: operation() }), false, false)).toBeNull();
  });

  it("never replaces an existing draft and requires both explicit source IDs", () => {
    expect(autoDraftSources(operation(), settings(), detail({ working_draft_state: "editing" }), false, false)).toBeNull();
    expect(autoDraftSources(operation(), settings(), detail({ active_analysis_id: null }), false, false)).toBeNull();
    expect(autoDraftSources(operation(), settings(), detail({ active_selection_plan_id: null }), false, false)).toBeNull();
  });

  it("suppresses both a previously accepted dispatch and a dispatch already in flight", () => {
    expect(autoDraftSources(operation(), settings(), detail(), true, false)).toBeNull();
    expect(autoDraftSources(operation(), settings(), detail(), false, true)).toBeNull();
  });
});
