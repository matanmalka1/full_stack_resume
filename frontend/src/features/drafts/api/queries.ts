import { useQuery } from "@tanstack/react-query";

import { applicationDetailQueryOptions } from "@/api/applications";
import type { ApplicationDetail, Operation, WorkingDraft, WorkingDraftFacts } from "@/api/contracts";
import { workingDraftFactsQueryOptions, workingDraftQueryOptions } from "@/api/drafts";
import { useWatchedOperation } from "@/features/operations";

export interface DraftDocument {
  applicationError: unknown;
  detail: ApplicationDetail | undefined;
  draft: WorkingDraft | undefined;
  draftError: unknown;
  /* The token that authorizes writing, taken from the same read as the content above it.
     Autosave sends it and never one captured elsewhere. */
  etag: string | null;
  facts: WorkingDraftFacts | undefined;
  /* Live work on this Application, reported beside the draft it is rewriting. */
  operation: Operation | undefined;
  watch: (operationId: string) => void;
  workingDraftId: string | null;
}

/* Everything this screen reads, and nothing it writes.

   It reads the §9 projection for which draft is active and what is blocking, and the
   draft and its fact accounting for the structure the editor draws. Publishing the
   workflow landmark stays with the page, where every other routed screen does it.

   It derives no second workflow state machine (A.1): blockers are the projection's own
   review reasons, and approval is refused by the backend, not by a rule invented here. */
export const useDraftDocument = (applicationId: string): DraftDocument => {
  const applicationQuery = useQuery(applicationDetailQueryOptions(applicationId));
  const detail = applicationQuery.data;

  /* The same watch the Application screen keeps, on the other screen that queues durable
     work against one Application. */
  const { operation, watch } = useWatchedOperation(applicationId, detail);

  const workingDraftId = detail?.active_working_draft_id ?? null;
  const draftQuery = useQuery({
    ...workingDraftQueryOptions(workingDraftId ?? ""),
    enabled: workingDraftId !== null,
  });
  const factsQuery = useQuery({
    ...workingDraftFactsQueryOptions(workingDraftId ?? ""),
    enabled: workingDraftId !== null,
  });

  return {
    applicationError: applicationQuery.error,
    detail,
    draft: draftQuery.data?.draft,
    draftError: draftQuery.error,
    etag: draftQuery.data?.etag ?? null,
    facts: factsQuery.data,
    operation,
    watch,
    workingDraftId,
  };
};
