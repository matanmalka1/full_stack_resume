import type { ApplicationDetail, Operation, Settings } from "@/api/contracts";

/* §9 automatic generation is the server's: when the opt-in was on at submission, the
   analysis that creates the document queues `create_draft` in the same commit. Nothing
   here decides or sends anything. These readings only let the screen follow that run and
   say what is happening while it does. */

/* Said while the analysis is still running: the opt-in is on and there is no document yet,
   so the run will create one and continue into its draft. Settings are read live, so a
   change made mid-run can make the notice wrong until the run ends; the server acts on
   what was frozen when the analysis was submitted. */
export const autoDraftIsAnticipated = (
  settings: Settings | undefined,
  detail: ApplicationDetail | undefined,
): boolean =>
  settings?.auto_generate_when_review_not_required === true &&
  detail !== undefined &&
  detail.document_id == null &&
  detail.active_operation?.operation_type === "analyze_job";

/* The draft the server queued for the document this succeeded analysis created. The
   analysis's own `job_analysis` output must be the one the document is pinned to: a
   later analysis never touches an existing document, so only the run that created it
   is followed into its draft. */
export const continuedDraft = (
  operation: Operation | undefined,
  detail: ApplicationDetail | undefined,
): Operation | null => {
  if (
    operation?.operation_type !== "analyze_job" ||
    operation.status !== "succeeded" ||
    detail === undefined ||
    detail.application.id !== operation.application_id ||
    detail.active_operation?.operation_type !== "create_draft" ||
    !operation.outputs.some(
      (output) => output.output_type === "job_analysis" && output.output_id === detail.document_analysis_id,
    )
  ) {
    return null;
  }
  return detail.active_operation;
};

/* The moment between the watched analysis succeeding and the projection being read
   again: the analysis ran with the opt-in on and the projection still shows no document.
   It ends at that next read, which either names the queued draft or does not. */
export const continuationAwaitsProjection = (
  operation: Operation | undefined,
  settings: Settings | undefined,
  detail: ApplicationDetail | undefined,
): boolean =>
  settings?.auto_generate_when_review_not_required === true &&
  operation?.operation_type === "analyze_job" &&
  operation.status === "succeeded" &&
  detail !== undefined &&
  detail.application.id === operation.application_id &&
  detail.document_id == null;
