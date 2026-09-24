import type { OperationPhase } from "@/api/contracts";

/* The four stretches a run passes through, as the reader can follow them. The backend's
   phases are finer - three kinds of waiting, a retry pause - and each of them belongs to
   exactly one of these, so the steps move forward and never back. Keyed by the generated
   union, so a new backend phase fails the build until it is placed. */
export const operationPhaseSteps = ["בתור", "בדיקה", "ביצוע", "הפעלה"] as const;

const stepByPhase: Record<OperationPhase, number> = {
  queued: 0,
  waiting_for_application: 0,
  waiting_for_render_slot: 0,
  waiting_for_ai_slot: 0,
  pre_execution_check: 1,
  executing: 2,
  retry_wait: 2,
  pre_activation_check: 3,
  activating: 3,
  completed: operationPhaseSteps.length,
};

/* The index of the current step; `operationPhaseSteps.length` once every step is done. */
export const operationPhaseStep = (phase: OperationPhase): number => stepByPhase[phase];
