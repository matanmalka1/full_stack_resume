import { queryOptions } from "@tanstack/react-query";

import { type ApiPath, apiRequest } from "./client";
import type { ApprovedRevision, Operation, RenderRevisionRequest } from "./contracts";
import { type QueuedOperation, queuedOperation } from "./operations";

const revisionPath = (approvedRevisionId: string): ApiPath =>
  `/api/v1/approved-revisions/${encodeURIComponent(approvedRevisionId)}`;

export const approvedRevisionQueryKey = (approvedRevisionId: string) =>
  ["approved-revision", approvedRevisionId] as const;

export const approvedRevisionQueryOptions = (approvedRevisionId: string) =>
  queryOptions({
    queryKey: approvedRevisionQueryKey(approvedRevisionId),
    queryFn: async ({ signal }) => {
      const response = await apiRequest<ApprovedRevision>(revisionPath(approvedRevisionId), {
        signal,
      });
      return response.data;
    },
  });

export const renderApprovedRevision = async (
  approvedRevisionId: string,
  applicationId: string,
  idempotencyKey: string,
): Promise<QueuedOperation> => {
  const body: RenderRevisionRequest = { application_id: applicationId };
  return queuedOperation(
    await apiRequest<Operation>(`${revisionPath(approvedRevisionId)}/render` as ApiPath, {
      method: "POST",
      body,
      idempotencyKey,
    }),
  );
};

export const approvedPreviewSrc = (
  approvedRevisionId: string,
  htmlArtifactVersionId: string,
): string =>
  `${revisionPath(approvedRevisionId)}/preview?html_artifact_version_id=${encodeURIComponent(htmlArtifactVersionId)}`;

export const recruiterPdfHref = (
  approvedRevisionId: string,
  pdfArtifactVersionId: string,
): string =>
  `${revisionPath(approvedRevisionId)}/recruiter-pdf?pdf_artifact_version_id=${encodeURIComponent(pdfArtifactVersionId)}`;
