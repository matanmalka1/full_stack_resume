import { useQuery } from "@tanstack/react-query";

import { watchedApplicationDetailQueryOptions } from "@/api/applications";
import type { ApplicationDetail, CVDocument, Operation } from "@/api/contracts";
import { documentQueryOptions } from "@/api/documents";
import { useWatchedOperation } from "@/features/operations";
import { type EditableDocument, isEditable } from "../model/drafts.types";

export interface DraftDocument {
  applicationError: unknown;
  /* See `useWatchedOperation`. */
  awaitingRecord: boolean;
  detail: ApplicationDetail | undefined;
  /* The document as read, with or without content. */
  document: CVDocument | undefined;
  /* The same document narrowed to one with content - the only shape the editor draws. */
  draft: EditableDocument | undefined;
  draftError: unknown;
  /* The token that authorizes writing, taken from the same read as the content above it.
     Autosave sends it and never one captured elsewhere. */
  etag: string | null;
  /* The projection names a document; before the first analysis there is none to read. */
  hasDocument: boolean;
  /* Live work on this Application, reported over the document it is rewriting. */
  operation: Operation | undefined;
  settled: boolean;
  watch: (operationId: string) => void;
}

/* Everything this screen reads, and nothing it writes.

   It reads the §9 projection for where the document stands and what is blocking, and the
   document itself - content, outline, selection and fact accounting in one read - for the
   structure the editor draws. It derives no second workflow state machine (A.1): approval
   and readiness are the projection's `preparation_state`, never computed here. */
export const useDraftDocument = (applicationId: string): DraftDocument => {
  const applicationQuery = useQuery(watchedApplicationDetailQueryOptions(applicationId));
  const detail = applicationQuery.data;

  /* The same watch the Application screen keeps, on the other screen that queues durable
     work against one Application. */
  const { awaitingRecord, operation, settled, watch } = useWatchedOperation(applicationId, detail);

  const hasDocument = detail?.document_id != null;
  const documentQuery = useQuery({
    ...documentQueryOptions(applicationId),
    enabled: hasDocument,
  });
  const document = documentQuery.data?.document;

  return {
    applicationError: applicationQuery.error,
    awaitingRecord,
    detail,
    document,
    draft: document !== undefined && isEditable(document) ? document : undefined,
    draftError: documentQuery.error,
    etag: documentQuery.data?.etag ?? null,
    hasDocument,
    operation,
    settled,
    watch,
  };
};
