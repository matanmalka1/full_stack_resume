import type { OperationPhase } from "@/api/contracts";

/* The two stretches a run passes through, as the reader can follow them. The backend's
   phases are finer - two kinds of waiting, read from what is running - and each belongs
   to exactly one of these, so the steps move forward and never back. Keyed by the
   generated union, so a new backend phase fails the build until it is placed. */
export const operationPhaseSteps = ["בתור", "ביצוע"] as const;

const stepByPhase: Record<OperationPhase, number> = {
  queued: 0,
  waiting_for_application: 0,
  waiting_for_render_slot: 0,
  executing: 1,
  completed: operationPhaseSteps.length,
};

/* The index of the current step; `operationPhaseSteps.length` once every step is done. */
export const operationPhaseStep = (phase: OperationPhase): number => stepByPhase[phase];
