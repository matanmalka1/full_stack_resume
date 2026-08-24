import { describe, expect, it } from "vitest";

import type { PreparationState } from "../api/contracts";
import type { WorkflowStep } from "../ui/WorkflowSteps";
import { workflowStepsFor } from "./WorkflowLandmark";

const current = (steps: WorkflowStep[]): string | undefined =>
  steps.find((step) => step.state === "current")?.label;

const completed = (steps: WorkflowStep[]): string[] =>
  steps.filter((step) => step.state === "complete").map((step) => step.label);

describe("workflowStepsFor", () => {
  it("places each PreparationState on the stage it belongs to", () => {
    const stages: [PreparationState, string][] = [
      ["needs_analysis", "ניתוח"],
      ["needs_review", "ניתוח"],
      ["ready_to_draft", "טיוטה"],
      ["draft_in_progress", "טיוטה"],
      ["ready_for_approval", "אימות"],
      ["approved", "מוכן"],
    ];

    for (const [state, label] of stages) {
      const steps = workflowStepsFor(state);

      expect(current(steps)).toBe(label);
      expect(completed(steps)).toEqual(
        ["משרה חדשה", "ניתוח", "טיוטה", "אימות", "מוכן"].slice(
          0,
          steps.findIndex((step) => step.state === "current"),
        ),
      );
    }
  });

  it("starts at the intake stage, which is the one that exists before an Application does", () => {
    const steps = workflowStepsFor("intake");

    expect(current(steps)).toBe("משרה חדשה");
    expect(completed(steps)).toEqual([]);
  });

  /* The projection has not arrived yet. The intake is certainly behind an Application
     that exists, but which stage it is on is not the landmark's to guess. */
  it("claims no current stage while the projection is still loading", () => {
    const steps = workflowStepsFor("unknown");

    expect(current(steps)).toBeUndefined();
    expect(completed(steps)).toEqual(["משרה חדשה"]);
  });

  it("completes the last stage rather than leaving it in progress once the CV is ready", () => {
    const steps = workflowStepsFor("ready");

    expect(current(steps)).toBeUndefined();
    expect(completed(steps)).toEqual(["משרה חדשה", "ניתוח", "טיוטה", "אימות", "מוכן"]);
  });
});
