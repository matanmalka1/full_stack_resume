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
