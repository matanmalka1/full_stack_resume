import { describe, expect, it } from "vitest";

import type { ApplicationDetail, Operation } from "@/api/contracts";
import { analysisViewState } from "./analysisViewState";

const operation = (overrides: Partial<Operation> = {}): Operation =>
  ({
    id: "operation-1",
    application_id: "application-1",
    operation_type: "analyze_job",
    status: "running",
    phase: "executing",
    is_terminal: false,
    available_actions: ["cancel"],
    outputs: [],
    message: "",
    created_at: "2026-09-10T08:00:00Z",
    ...overrides,
  }) as Operation;

const detail = (overrides: Partial<ApplicationDetail> = {}): ApplicationDetail =>
  ({
    active_analysis_id: null,
    ...overrides,
  }) as ApplicationDetail;

describe("analysisViewState", () => {
  it("keeps creation and its live analysis in one processing state", () => {
    expect(analysisViewState({ analysisWasQueuedOnCreate: true, detail: undefined, operation: undefined })).toBe(
      "processing",
    );
    expect(analysisViewState({ analysisWasQueuedOnCreate: true, detail: detail(), operation: operation() })).toBe(
      "processing",
    );
  });

  it("does not expose the pre-analysis projection after the operation succeeds", () => {
    expect(
      analysisViewState({
        analysisWasQueuedOnCreate: true,
        detail: detail(),
        operation: operation({ status: "succeeded", is_terminal: true }),
      }),
    ).toBe("processing");
  });

  it("shows decisions only once the completed analysis is in the projection", () => {
    expect(
      analysisViewState({
        analysisWasQueuedOnCreate: true,
        detail: detail({ active_analysis_id: "analysis-1" }),
        operation: operation({ status: "succeeded", is_terminal: true }),
      }),
    ).toBe("content");
  });

  it("does not expose an older analysis while a re-analysis projection catches up", () => {
    const succeeded = operation({
      status: "succeeded",
      is_terminal: true,
      outputs: [{ output_type: "job_analysis", output_id: "analysis-2", active: true }],
    });

    expect(
      analysisViewState({
        analysisWasQueuedOnCreate: false,
        detail: detail({ active_analysis_id: "analysis-1" }),
        operation: succeeded,
      }),
    ).toBe("processing");
    expect(
      analysisViewState({
        analysisWasQueuedOnCreate: false,
        detail: detail({ active_analysis_id: "analysis-2" }),
        operation: succeeded,
      }),
    ).toBe("content");
  });

  it("preserves a real failed outcome", () => {
    expect(
      analysisViewState({
        analysisWasQueuedOnCreate: true,
        detail: detail(),
        operation: operation({ status: "failed", is_terminal: true }),
      }),
    ).toBe("analysis_failed");
  });
});
