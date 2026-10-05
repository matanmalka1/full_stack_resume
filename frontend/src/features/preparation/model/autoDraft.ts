import type { ApplicationDetail, Operation, Settings } from "@/api/contracts";
import { aiRegenerationAvailable } from "@/api/settings";

/* What an automatic generate is addressed to: the document the first analysis created,
   at the exact hash the projection reports. `create_draft` activates only while the
   document still carries that hash, so naming it here is what keeps the continuation
   from drafting over anything the user has changed since. */
export interface AutoDraftSources {
  analysisId: string;
  applicationId: string;
  documentHash: string;
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
    !aiRegenerationAvailable(settings) ||
    detail === undefined ||
    operation.application_id !== detail.application.id ||
    detail.application.deleted_at != null ||
    detail.preparation_state !== "ready_to_draft" ||
    !detail.available_actions.includes("create_draft") ||
    detail.blocked_actions.some(({ action }) => action === "create_draft") ||
    detail.review_reasons.length !== 0 ||
    detail.active_operation != null ||
    detail.document_hash == null ||
    detail.document_analysis_id == null
  ) {
    return null;
  }
  /* A historical successful analyze cannot authorize drafting a document built on a
     different analysis: only the run that produced the document's own analysis continues
     into it. A cancelled or failed run has no outputs, so it confers no authority. */
  const activated = operation.outputs.some(
    (output) => output.output_type === "job_analysis" && output.output_id === detail.document_analysis_id,
  );
  if (!activated) {
    return null;
  }
  return {
    applicationId: detail.application.id,
    analysisId: detail.document_analysis_id,
    documentHash: detail.document_hash,
  };
};

/* The same opt-in guard, asked one step earlier: not "may the continuation be sent now"
   but "is one expected the moment this analysis lands". It is the announcement condition
   only - `autoDraftSources` above stays the sole authority on dispatch - so it reads the
   facts that are already true while the analysis runs and leaves the projection to decide
   the rest. A first analysis creates the document, so "no document yet" is the case the
   notice is for. */
export const autoDraftIsAnticipated = (
  settings: Settings | undefined,
  detail: ApplicationDetail | undefined,
): boolean =>
  settings?.auto_generate_when_review_not_required === true &&
  detail !== undefined &&
  detail.document_id == null &&
  detail.active_operation?.operation_type === "analyze_job";

/* The continuation announcement uses the same source guard as dispatch. In the narrow
   catch-up window before the projection names the document the analysis created, only a
   durable activated analysis output can anticipate it; a posting captured after that run
   ended is already a new context. */
export const autoDraftIsContinuing = (
  operation: Operation | undefined,
  settings: Settings | undefined,
  detail: ApplicationDetail | undefined,
): boolean => {
  if (autoDraftSources(operation, settings, detail) !== null) return true;
  if (
    settings?.auto_generate_when_review_not_required !== true ||
    !aiRegenerationAvailable(settings) ||
    operation?.operation_type !== "analyze_job" ||
    operation.status !== "succeeded" ||
    detail === undefined ||
    operation.application_id !== detail.application.id ||
    detail.application.deleted_at != null ||
    detail.document_id != null ||
    detail.review_reasons.length !== 0 ||
    (detail.active_operation != null && detail.active_operation.id !== operation.id) ||
    detail.blocked_actions.some(({ action }) => action === "create_draft")
  )
    return false;
  const capturedTime = Date.parse(detail.job_posting.job_text_updated_at);
  const finishedTime = operation.finished_at == null ? NaN : Date.parse(operation.finished_at);
  return !(capturedTime > finishedTime) && operation.outputs.some((output) => output.output_type === "job_analysis");
};
