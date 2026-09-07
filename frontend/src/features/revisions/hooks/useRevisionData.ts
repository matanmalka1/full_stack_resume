import { useQuery } from "@tanstack/react-query";

import { applicationDetailQueryOptions } from "@/api/applications";
import { approvedRevisionQueryOptions, decisionMarkdownQueryOptions } from "@/api/revisions";

export const useRevisionData = (revisionId: string) => {
  const revisionQuery = useQuery(approvedRevisionQueryOptions(revisionId));
  const revision = revisionQuery.data;
  const applicationId = revision?.application_id;
  const applicationQuery = useQuery({
    ...applicationDetailQueryOptions(applicationId ?? ""),
    enabled: applicationId !== undefined,
  });
  const decisionQuery = useQuery({
    ...decisionMarkdownQueryOptions(revisionId, applicationId ?? ""),
    enabled: applicationId !== undefined,
  });

  const detail = applicationQuery.data;
  const displayedWarningCode =
    revision === undefined || detail === undefined
      ? null
      : revision.job_snapshot_id !== detail.active_job_snapshot_id
        ? "READY_REVISION_FOR_OLDER_SNAPSHOT"
        : revision.job_analysis_id !== detail.active_analysis_id
          ? "READY_REVISION_FOR_OLDER_ANALYSIS"
          : null;
  const otherWarnings = detail?.warnings.filter((warning) => warning.code !== displayedWarningCode) ?? [];
  const recordedSubmissions =
    revision === undefined
      ? []
      : (detail?.recruitment_timeline ?? []).filter(
          (item) => item.item_type === "submission" && item.approved_revision_id === revision.id,
        );
  const submittedAt = recordedSubmissions.at(-1)?.occurred_at ?? null;

  return {
    applicationQuery,
    decisionQuery,
    detail,
    displayedWarningCode,
    otherWarnings,
    revision,
    revisionQuery,
    submittedAt,
  };
};
