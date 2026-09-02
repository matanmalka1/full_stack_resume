import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { applicationDetailQueryOptions, invalidateApplicationViews, startDraftGeneration } from "../../api/applications";
import { operationQueryKey } from "../../api/operations";
import { approvedRevisionQueryOptions, decisionMarkdownQueryOptions } from "../../api/revisions";
import { recordInternalSubmission } from "../../api/tracking";
import { useWorkflowStage, workflowDestinations } from "../../app/WorkflowLandmark";
import { useWatchedOperation } from "../../hooks/useWatchedOperation";
import { isoFromLocalDateTimeInput } from "../../ui/isoFromLocalDateTimeInput";
import { localDateTimeInputValue } from "../../ui/localDateTimeInputValue";

/* One approved revision: its data, its commands, and the state that guards them. Apart
   from how it is drawn (see `RevisionPage.tsx`). */
export const useRevisionPageState = (approvedRevisionId: string) => {
  const queryClient = useQueryClient();
  const [submissionOpen, setSubmissionOpen] = useState(false);
  const [submittedAt, setSubmittedAt] = useState(() => localDateTimeInputValue(new Date()));
  const revisionQuery = useQuery(approvedRevisionQueryOptions(approvedRevisionId));
  const revision = revisionQuery.data;
  const decisionQuery = useQuery({
    ...decisionMarkdownQueryOptions(approvedRevisionId, revision?.application_id ?? ""),
    enabled: revision !== undefined,
  });
  const applicationQuery = useQuery({
    ...applicationDetailQueryOptions(revision?.application_id ?? ""),
    enabled: revision !== undefined,
  });
  const detail = applicationQuery.data;
  /* The Application this revision belongs to is named by the revision, so until it
     arrives there is no Application to link any stage back to. */
  useWorkflowStage(
    detail === undefined ? "unknown" : detail.preparation_state,
    revision === undefined ? undefined : workflowDestinations(revision.application_id, detail),
  );
  /* The same watch the Application screen and the editor keep. This screen queues one
     command - a new draft from the approved revision - and reports it beside the files
     rather than sending the reader to a screen that holds neither. */
  const { operation, watch } = useWatchedOperation(revision?.application_id ?? "", detail);
  const newDraftKey = useMemo(
    () =>
      `revision-draft:${approvedRevisionId}:${detail?.active_analysis_id ?? "none"}:${detail?.active_selection_plan_id ?? "none"}`,
    [approvedRevisionId, detail?.active_analysis_id, detail?.active_selection_plan_id],
  );
  const newDraft = useMutation({
    mutationFn: async () => {
      if (revision === undefined || detail?.active_analysis_id == null || detail.active_selection_plan_id == null) {
        throw new Error("No active compatible analysis and selection plan");
      }
      return startDraftGeneration(
        revision.application_id,
        detail.active_analysis_id,
        detail.active_selection_plan_id,
        newDraftKey,
        { parentRevisionId: revision.id },
      );
    },
    /* Reported in place rather than followed. Generating a new draft from a Ready
       revision used to navigate to the Operation's own screen, which handed the user a
       progress line and then a link back to the Application - so the approved files they
       were looking at went off screen, and the draft the work produced was reached by a
       third step. The watch below reports the run here and the projection names the draft
       when it exists. */
    onSuccess: ({ operation }) => {
      queryClient.setQueryData(operationQueryKey(operation.id), operation);
      watch(operation.id);
    },
  });
  const submission = useMutation({
    mutationFn: async () => {
      if (revision === undefined || revision.pdf_artifact_version_id == null) {
        throw new Error("Submission requires the exact Ready revision and PDF");
      }
      const submittedAtIso = isoFromLocalDateTimeInput(submittedAt);
      if (submittedAtIso === null) {
        throw new Error("Submission requires a valid date and time");
      }
      return recordInternalSubmission(revision.application_id, {
        approved_revision_id: revision.id,
        pdf_artifact_version_id: revision.pdf_artifact_version_id,
        submitted_at: submittedAtIso,
        metadata: {},
      });
    },
    onSuccess: () => {
      setSubmissionOpen(false);
      void invalidateApplicationViews(queryClient, revision?.application_id);
    },
  });
  const hasSources = detail?.active_analysis_id != null && detail.active_selection_plan_id != null;
  const displayedRevisionWarningCode =
    revision === undefined || detail === undefined
      ? null
      : revision.job_snapshot_id !== detail.active_job_snapshot_id
        ? "READY_REVISION_FOR_OLDER_SNAPSHOT"
        : revision.job_analysis_id !== detail.active_analysis_id
          ? "READY_REVISION_FOR_OLDER_ANALYSIS"
          : null;
  /* The server warning describes its latest Ready revision, while this route can show
     any immutable revision. Suppress only the warning this displayed revision already
     explains; a different latest-Ready warning still carries distinct information. */
  const otherWarnings = detail?.warnings.filter((warning) => warning.code !== displayedRevisionWarningCode);
  const submittedAtValid = isoFromLocalDateTimeInput(submittedAt) !== null;
  const downloadDecision = () => {
    if (decisionQuery.data === undefined) return;
    const href = URL.createObjectURL(new Blob([decisionQuery.data.content], { type: "text/markdown;charset=utf-8" }));
    const anchor = document.createElement("a");
    anchor.href = href;
    anchor.download = decisionQuery.data.filename;
    anchor.click();
    URL.revokeObjectURL(href);
  };

  return {
    applicationQuery,
    decisionQuery,
    detail,
    downloadDecision,
    hasSources,
    displayedRevisionWarningCode,
    newDraft,
    operation,
    otherWarnings,
    revision,
    revisionQuery,
    setSubmissionOpen,
    setSubmittedAt,
    submission,
    submissionOpen,
    submittedAt,
    submittedAtValid,
    watch,
  };
};
