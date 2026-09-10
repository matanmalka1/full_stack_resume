import type { ApplicationDetail, Operation } from "@/api/contracts";
import { isTerminalOperation } from "@/api/operations";

export type AnalysisViewState = "loading" | "processing" | "analysis_failed" | "content";

/* The preparation page is one product state at a time. The projection and the watched
   Operation can briefly describe different moments of the same run: an analyze Operation
   may already be live while the projection still says `needs_analysis`, or the Operation
   may have succeeded before the refreshed projection carries its analysis. Those are
   transport boundaries, not additional screens for the reader. */
export const analysisViewState = ({
  analysisWasQueuedOnCreate,
  detail,
  operation,
}: {
  analysisWasQueuedOnCreate: boolean;
  detail: ApplicationDetail | undefined;
  operation: Operation | undefined;
}): AnalysisViewState => {
  if (detail === undefined) {
    return analysisWasQueuedOnCreate ? "processing" : "loading";
  }

  if (operation?.operation_type !== "analyze_job") {
    return "content";
  }

  if (!isTerminalOperation(operation)) {
    return "processing";
  }

  if (operation.status !== "succeeded") {
    return "analysis_failed";
  }

  /* Success belongs to processing until the projection exposes the exact product. This
     also covers re-analysis: the presence of an older active analysis is not evidence
     that the projection has caught up with the Operation that just replaced it. */
  const activatedAnalysisId = operation.outputs.find(
    (output) => output.active && output.output_type === "job_analysis",
  )?.output_id;
  if (activatedAnalysisId !== undefined) {
    if (detail.active_analysis_id === activatedAnalysisId) {
      return "content";
    }

    /* Applying review decisions is synchronous and may derive another analysis after the
       watched analyze Operation. That newer active record is progress beyond the watched
       output, not a stale projection waiting to expose it. Timestamps distinguish it from
       the opposite re-analysis race, where the projection still carries the older record. */
    const activeAnalysis = detail.latest_analysis;
    const activeAnalysisTime =
      activeAnalysis?.id === detail.active_analysis_id ? Date.parse(activeAnalysis.created_at) : NaN;
    const operationFinishedTime = operation.finished_at == null ? NaN : Date.parse(operation.finished_at);
    if (
      Number.isFinite(activeAnalysisTime) &&
      Number.isFinite(operationFinishedTime) &&
      activeAnalysisTime >= operationFinishedTime
    ) {
      return "content";
    }

    return "processing";
  }

  return detail.active_analysis_id === null || detail.active_analysis_id === undefined ? "processing" : "content";
};
