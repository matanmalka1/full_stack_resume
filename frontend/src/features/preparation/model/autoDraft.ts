import type { ApplicationDetail, Operation, Settings } from "@/api/contracts";

export interface AutoDraftSources {
  analysisId: string;
  applicationId: string;
  planId: string;
}

/* This is only the Web automation opt-in guard. It does not decide which lifecycle
   action is available: every workflow fact below is consumed from the server's
   Application projection, including the absence of review reasons and live work. */
export const autoDraftSources = (
  operation: Operation | undefined,
  settings: Settings | undefined,
  detail: ApplicationDetail | undefined,
): AutoDraftSources | null => {
  if (
    operation?.operation_type !== "analyze_job" ||
    operation.status !== "succeeded" ||
    settings?.auto_generate_when_review_not_required !== true ||
    detail === undefined ||
    operation.application_id !== detail.application.id ||
    detail.application.deleted_at != null ||
    detail.preparation_state !== "ready_to_draft" ||
    !detail.available_actions.includes("create_draft") ||
    detail.blocked_actions.some(({ action }) => action === "create_draft") ||
    detail.active_working_draft_id != null ||
    detail.review_reasons.length !== 0 ||
    detail.working_draft_state !== "none" ||
    detail.active_operation != null ||
    detail.active_analysis_id == null ||
    detail.active_selection_plan_id == null
  ) {
    return null;
  }
  /* A historical successful analyze cannot authorize drafting a different active pair.
     Inactive outputs (including those produced after cancellation) confer no authority. */
  const activated = (type: string, id: string): boolean =>
    operation.outputs.some((output) => output.active && output.output_type === type && output.output_id === id);
  if (
    !activated("job_analysis", detail.active_analysis_id) ||
    !activated("selection_plan", detail.active_selection_plan_id)
  ) {
    return null;
  }
  return {
    applicationId: detail.application.id,
    analysisId: detail.active_analysis_id,
    planId: detail.active_selection_plan_id,
  };
};

/* The same opt-in guard, asked one step earlier: not "may the continuation be sent now"
   but "is one expected the moment this analysis lands". It is the announcement condition
   only - `autoDraftSources` above stays the sole authority on dispatch - so it reads the
   two facts that are already true while the analysis runs and leaves the projection to
   decide the rest. A draft appearing without a press is otherwise the reader's first news
   that the setting is on, and the setting lives on another screen. */
export const autoDraftIsAnticipated = (
  settings: Settings | undefined,
  detail: ApplicationDetail | undefined,
): boolean =>
  settings?.auto_generate_when_review_not_required === true &&
  detail !== undefined &&
  detail.working_draft_state === "none" &&
  detail.active_operation?.operation_type === "analyze_job";

/* The continuation announcement uses the same source guard as dispatch. In the narrow
   catch-up window with no active analysis yet, only a durable activated analysis output
   can anticipate it; a posting captured after that run ended is already a new context. */
export const autoDraftIsContinuing = (
  operation: Operation | undefined,
  settings: Settings | undefined,
  detail: ApplicationDetail | undefined,
): boolean => {
  if (autoDraftSources(operation, settings, detail) !== null) return true;
  if (
    settings?.auto_generate_when_review_not_required !== true ||
    operation?.operation_type !== "analyze_job" ||
    operation.status !== "succeeded" ||
    detail === undefined ||
    operation.application_id !== detail.application.id ||
    detail.application.deleted_at != null ||
    detail.working_draft_state !== "none" ||
    detail.active_working_draft_id != null ||
    detail.active_analysis_id != null ||
    detail.review_reasons.length !== 0 ||
    (detail.active_operation != null && detail.active_operation.id !== operation.id) ||
    detail.blocked_actions.some(({ action }) => action === "create_draft")
  )
    return false;
  const capturedTime = Date.parse(detail.latest_snapshot.captured_at);
  const finishedTime = operation.finished_at == null ? NaN : Date.parse(operation.finished_at);
  return (
    !(capturedTime > finishedTime) &&
    operation.outputs.some((output) => output.active && output.output_type === "job_analysis")
  );
};
