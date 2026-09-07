import { useMutation, useQueryClient } from "@tanstack/react-query";

import { invalidateApplicationViews, startDraftGeneration } from "@/api/applications";
import type { ApplicationDetail, ApprovedRevision } from "@/api/contracts";
import { operationQueryKey } from "@/api/operations";
import { useWatchedOperation } from "@/hooks/useWatchedOperation";

const childDraftKey = (revision: ApprovedRevision, detail: ApplicationDetail) =>
  `revision-draft:${revision.id}:${detail.active_analysis_id ?? "none"}:${detail.active_selection_plan_id ?? "none"}`;

export const useRevisionDraftGeneration = (
  revision: ApprovedRevision | undefined,
  detail: ApplicationDetail | undefined,
) => {
  const queryClient = useQueryClient();
  const { operation, watch } = useWatchedOperation(revision?.application_id ?? "", detail);
  const canCreate = detail?.active_analysis_id != null && detail.active_selection_plan_id != null;

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

  return { canCreate, createDraft, operation, watch };
};
