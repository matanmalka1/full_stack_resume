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
  factDetailQueryKey,
  factHistoryQueryKey,
  factsQueryPrefix,
  transitionFact,
} from "@/api/facts";

export type FactTransitionCommand = "confirm" | "promote";

/* Every write below moves the permanent knowledge store, so all of them invalidate the
   same three reads: the pool, the lifecycle log, and - where the write named one fact -
   that fact's detail. Kept in one place because a write that forgets one of them leaves
   a stale status on screen next to the button that just changed it. */
const useFactCacheRefresh = () => {
  const queryClient = useQueryClient();

  return (factId?: string) => {
    void queryClient.invalidateQueries({ queryKey: factsQueryPrefix });
    void queryClient.invalidateQueries({ queryKey: factHistoryQueryKey });
    if (factId !== undefined) {
      void queryClient.invalidateQueries({ queryKey: factDetailQueryKey(factId) });
    }
  };
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

export const useTransitionFact = (
  factId: string,
  onSettled?: () => void,
): UseMutationResult<FactMutation, Error, FactTransitionCommand> => {
  const refresh = useFactCacheRefresh();

  return useMutation({
    mutationFn: (command: FactTransitionCommand) =>
      transitionFact(factId, command, {
        confirm: true,
        reason: command === "confirm" ? "explicit Web confirmation" : "explicit Web promotion",
      }),
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
