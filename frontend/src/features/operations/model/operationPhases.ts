import type { OperationPhase } from "@/api/contracts";

/* The stretches a run passes through, as the reader can follow them: sent, waiting its
   turn, running, done. The backend's phases are finer - two kinds of waiting, read from
   what is running - and each belongs to exactly one of these, so the steps move forward
   and never back. "Sent" is the stretch before any record exists, which the overlay
   reports as pending work; once a record is on hand that step is behind it. Keyed by the
   generated union, so a new backend phase fails the build until it is placed. */
export const operationPhaseSteps = ["נשלחה לביצוע", "בתור", "ביצוע", "הסתיימה"] as const;

/* The step a run is on before its record exists. */
export const PENDING_STEP = 0;

const stepByPhase: Record<OperationPhase, number> = {
  queued: 1,
  waiting_for_application: 1,
  waiting_for_render_slot: 1,
  executing: 2,
  completed: operationPhaseSteps.length,
};

/* The index of the current step; `operationPhaseSteps.length` once every step is done. */
export const operationPhaseStep = (phase: OperationPhase): number => stepByPhase[phase];

/* Where a run that ended without a result stopped: in the queue if it never started,
   otherwise while running. */
export const failedPhaseStep = (startedAt: string | null | undefined): number => (startedAt == null ? 1 : 2);
