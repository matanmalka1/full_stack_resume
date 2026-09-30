import { useMutation, useQueryClient, type UseMutationResult } from "@tanstack/react-query";

import type {
  AttachFactRequest,
  CaptureClaimFactRequest,
  CreateFactRequest,
  FactAttachment,
  FactMutation,
} from "@/api/contracts";
import {
  attachFact,
  captureClaimFact,
  createPendingFact,
  deleteFact,
  confirmFact,
  invalidateFactViews,
} from "@/api/facts";

/* Every write below moves the permanent knowledge store (`invalidateFactViews`). */
const useFactCacheRefresh = () => {
  const queryClient = useQueryClient();

  return (factId?: string) => invalidateFactViews(queryClient, factId);
};

export const useCreatePendingFact = (
  onCreated?: (factId: string) => void,
): UseMutationResult<FactMutation, Error, CreateFactRequest> => {
  const refresh = useFactCacheRefresh();

  return useMutation({
    mutationFn: createPendingFact,
    onSuccess: (result) => {
      refresh(result.fact.fact_id);
      onCreated?.(result.fact.fact_id);
    },
  });
};

export const useCaptureClaimFact = (): UseMutationResult<FactMutation, Error, CaptureClaimFactRequest> => {
  const refresh = useFactCacheRefresh();

  return useMutation({
    mutationFn: captureClaimFact,
    onSuccess: (result) => refresh(result.fact.fact_id),
  });
};

export const useConfirmFact = (
  factId: string,
  onSettled?: () => void,
): UseMutationResult<FactMutation, Error, void> => {
  const refresh = useFactCacheRefresh();

  return useMutation({
    mutationFn: () => confirmFact(factId, { confirm: true, reason: "explicit Web confirmation" }),
    onSuccess: () => {
      refresh(factId);
      onSettled?.();
    },
  });
};

/* One-way: nothing settles it back. Kept as its own hook rather than folded into
   `useConfirmFact` because deletion is terminal and needs its own confirmation
   step in the UI, not another value on the same toggle. */
export const useDeleteFact = (factId: string, onSettled?: () => void): UseMutationResult<FactMutation, Error, void> => {
  const refresh = useFactCacheRefresh();

  return useMutation({
    mutationFn: () => deleteFact(factId, { confirm: true, reason: "explicit Web deletion" }),
    onSuccess: () => {
      refresh(factId);
      onSettled?.();
    },
  });
};

export const useAttachFact = (factId: string): UseMutationResult<FactAttachment, Error, AttachFactRequest> => {
  const refresh = useFactCacheRefresh();

  return useMutation({
    mutationFn: (body: AttachFactRequest) => attachFact(factId, body),
    onSuccess: () => refresh(factId),
  });
};
