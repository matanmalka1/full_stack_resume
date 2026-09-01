import { queryOptions } from "@tanstack/react-query";

import { type ApiPath, apiRequest } from "./client";
import type { ApprovedRevision, DecisionMarkdown, Operation, RenderRevisionRequest } from "./contracts";
import { type QueuedOperation, queuedOperation } from "./operations";

const revisionPath = (approvedRevisionId: string): ApiPath =>
  `/api/v1/approved-revisions/${encodeURIComponent(approvedRevisionId)}`;

const approvedRevisionQueryKey = (approvedRevisionId: string) => ["approved-revision", approvedRevisionId] as const;

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

export interface DecisionMarkdownDownload extends DecisionMarkdown {
  filename: string;
}

const safeFilename = (contentDisposition: string | null): string => {
  const encoded = contentDisposition?.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
  const quoted = contentDisposition?.match(/filename="([^"]+)"/i)?.[1];
  let candidate = quoted;
  if (encoded !== undefined) {
    try {
      candidate = decodeURIComponent(encoded);
    } catch {
      candidate = quoted;
    }
  }
  return (candidate ?? "decision.md").split(/[\\/]/).at(-1) || "decision.md";
};

const decisionMarkdownQueryKey = (approvedRevisionId: string, applicationId: string) =>
  ["decision-markdown", approvedRevisionId, applicationId] as const;

export const decisionMarkdownQueryOptions = (approvedRevisionId: string, applicationId: string) =>
  queryOptions({
    queryKey: decisionMarkdownQueryKey(approvedRevisionId, applicationId),
    queryFn: async ({ signal }): Promise<DecisionMarkdownDownload> => {
      const response = await apiRequest<DecisionMarkdown>(
        `${revisionPath(approvedRevisionId)}/decision-markdown?application_id=${encodeURIComponent(applicationId)}` as ApiPath,
        { signal },
      );
      return {
        ...response.data,
        filename: safeFilename(response.contentDisposition),
      };
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

export const approvedPreviewSrc = (approvedRevisionId: string, htmlArtifactVersionId: string): string =>
  `${revisionPath(approvedRevisionId)}/preview?html_artifact_version_id=${encodeURIComponent(htmlArtifactVersionId)}`;

export const recruiterPdfHref = (approvedRevisionId: string, pdfArtifactVersionId: string): string =>
  `${revisionPath(approvedRevisionId)}/recruiter-pdf?pdf_artifact_version_id=${encodeURIComponent(pdfArtifactVersionId)}`;
