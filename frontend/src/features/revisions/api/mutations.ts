import { useMutation, useQueryClient } from "@tanstack/react-query";

import { startDraftGeneration } from "@/api/applications";
import type { ApplicationDetail, ApprovedRevision } from "@/api/contracts";
import { operationQueryKey } from "@/api/operations";
import { isOperationLive, useWatchedOperation } from "@/features/operations";

const childDraftKey = (revision: ApprovedRevision, detail: ApplicationDetail) =>
  `revision-draft:${revision.id}:${detail.active_analysis_id ?? "none"}:${detail.active_selection_plan_id ?? "none"}`;

export const useRevisionDraftGeneration = (
  revision: ApprovedRevision | undefined,
  detail: ApplicationDetail | undefined,
) => {
  const queryClient = useQueryClient();
  const { awaitingRecord, operation, settled, watch } = useWatchedOperation(revision?.application_id ?? "", detail);
  /* Starting a new draft while this Application's work is under way would queue over
     it; the overlay can be hidden, so the offer itself waits. */
  const operationLive = isOperationLive({
    awaitingRecord,
    operation,
    pending: false,
    settled,
  });
  const canCreate =
    !operationLive &&
    detail?.active_analysis_id != null &&
    detail.active_selection_plan_id != null &&
    detail.available_actions.includes("create_draft");

  const createDraft = useMutation({
    mutationFn: async () => {
      if (
        revision === undefined ||
        detail === undefined ||
        detail.active_analysis_id == null ||
        detail.active_selection_plan_id == null
      ) {
        throw new Error("No active compatible analysis and selection plan");
      }
      return startDraftGeneration(
        revision.application_id,
        detail.active_analysis_id,
        detail.active_selection_plan_id,
        childDraftKey(revision, detail),
        { parentRevisionId: revision.id },
      );
    },
    onSuccess: ({ operation: queuedOperation }) => {
      queryClient.setQueryData(operationQueryKey(queuedOperation.id), queuedOperation);
      watch(queuedOperation.id);
    },
  });

  return { awaitingRecord, canCreate, createDraft, operation, settled, watch };
};
