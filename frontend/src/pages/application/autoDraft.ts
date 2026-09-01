import type { ApplicationDetail, Operation, Settings } from "../../api/contracts";

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
    detail.review_reasons.length !== 0 ||
    detail.working_draft_state !== "none" ||
    detail.active_operation != null ||
    detail.active_analysis_id == null ||
    detail.active_selection_plan_id == null
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
