import { type QueryClient, queryOptions } from "@tanstack/react-query";

import { type ApiPath, apiRequest } from "./client";
import type {
  AttachFactRequest,
  CaptureClaimFactRequest,
  ConfirmAndUseFact,
  ConfirmAndUseFactRequest,
  CreateFactRequest,
  FactAttachment,
  FactAttachmentTargets,
  FactDetail,
  FactHistory,
  FactList,
  FactMutation,
  FactStatus,
  FactTransitionRequest,
} from "./contracts";

const factsPath: ApiPath = "/api/v1/facts";
const factPath = (factId: string): ApiPath => `/api/v1/facts/${encodeURIComponent(factId)}`;

export const factsQueryPrefix = ["facts"] as const;
export const factsQueryKey = (status?: FactStatus) => [...factsQueryPrefix, status ?? "all"] as const;
const factDetailQueryKey = (factId: string) => ["fact", factId] as const;
const factHistoryQueryKey = ["fact-history"] as const;

/* Every write to the knowledge store moves the same three reads: the pool, the lifecycle
   log, and - where the write named one fact - that fact's detail. Kept here, beside the
   keys, because a write that forgets one of them leaves a stale status on screen next to
   the button that just changed it, and fact writes are sent from more than one feature. */
export const invalidateFactViews = (queryClient: QueryClient, factId?: string | null): void => {
  void queryClient.invalidateQueries({ queryKey: factsQueryPrefix });
  void queryClient.invalidateQueries({ queryKey: factHistoryQueryKey });
  if (factId != null) {
    void queryClient.invalidateQueries({ queryKey: factDetailQueryKey(factId) });
  }
};
const factAttachmentTargetsQueryKey = (factId?: string) =>
  [...factsQueryPrefix, "attachment-targets", factId ?? "all"] as const;

export const factsQueryOptions = (status?: FactStatus) =>
  queryOptions({
    queryKey: factsQueryKey(status),
    queryFn: async ({ signal }) => {
      const path = status === undefined ? factsPath : (`${factsPath}?status=${status}` as ApiPath);
      return (await apiRequest<FactList>(path, { signal })).data;
    },
  });

export const factDetailQueryOptions = (factId: string) =>
  queryOptions({
    queryKey: factDetailQueryKey(factId),
    queryFn: async ({ signal }) => (await apiRequest<FactDetail>(factPath(factId), { signal })).data,
  });

export const factHistoryQueryOptions = queryOptions({
  queryKey: factHistoryQueryKey,
  queryFn: async ({ signal }) => (await apiRequest<FactHistory>(`${factsPath}/history` as ApiPath, { signal })).data,
});

export const factAttachmentTargetsQueryOptions = (factId?: string) =>
  queryOptions({
    queryKey: factAttachmentTargetsQueryKey(factId),
    queryFn: async ({ signal }) => {
      const path =
        factId === undefined
          ? (`${factsPath}/attachment-targets` as ApiPath)
          : (`${factsPath}/attachment-targets?fact_id=${encodeURIComponent(factId)}` as ApiPath);
      return (await apiRequest<FactAttachmentTargets>(path, { signal })).data;
    },
  });

export const createPendingFact = async (body: CreateFactRequest): Promise<FactMutation> =>
  (await apiRequest<FactMutation>(factsPath, { method: "POST", body })).data;

export const captureClaimFact = async (body: CaptureClaimFactRequest): Promise<FactMutation> =>
  (await apiRequest<FactMutation>(`${factsPath}/from-claim` as ApiPath, { method: "POST", body })).data;

/* The one lifecycle step: pending -> canonical. `confirm: false` is refused rather than
   interpreted. */
export const confirmFact = async (factId: string, body: FactTransitionRequest): Promise<FactMutation> =>
  (
    await apiRequest<FactMutation>(`${factPath(factId)}/confirm` as ApiPath, {
      method: "POST",
      body,
    })
  ).data;

/* One-way: pending/canonical -> deleted. `confirm: false` is refused rather
   than interpreted, the same as `confirmFact`. */
export const deleteFact = async (factId: string, body: FactTransitionRequest): Promise<FactMutation> =>
  (
    await apiRequest<FactMutation>(`${factPath(factId)}/delete` as ApiPath, {
      method: "POST",
      body,
    })
  ).data;

export const attachFact = async (factId: string, body: AttachFactRequest): Promise<FactAttachment> =>
  (
    await apiRequest<FactAttachment>(`${factPath(factId)}/attachments` as ApiPath, {
      method: "POST",
      body,
    })
  ).data;

export const confirmAndUseFact = async (factId: string, body: ConfirmAndUseFactRequest): Promise<ConfirmAndUseFact> =>
  (
    await apiRequest<ConfirmAndUseFact>(`${factPath(factId)}/confirm-and-use` as ApiPath, {
      method: "POST",
      body,
    })
  ).data;
