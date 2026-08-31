import { queryOptions } from "@tanstack/react-query";

import { type ApiPath, apiRequest } from "./client";
import type {
  AttachFactRequest,
  CaptureClaimFactRequest,
  ConfirmAndUseFact,
  ConfirmAndUseFactRequest,
  CreateFactRequest,
  FactAttachment,
  FactDetail,
  FactHistory,
  FactList,
  FactMutation,
  FactStatus,
  FactTransitionRequest,
} from "./contracts";

const factsPath: ApiPath = "/api/v1/facts";
const factPath = (factId: string): ApiPath => `/api/v1/facts/${encodeURIComponent(factId)}`;

export const factsQueryKey = (status?: FactStatus) => ["facts", status ?? "all"] as const;
export const factDetailQueryKey = (factId: string) => ["fact", factId] as const;
export const factHistoryQueryKey = ["fact-history"] as const;

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
    queryFn: async ({ signal }) =>
      (await apiRequest<FactDetail>(factPath(factId), { signal })).data,
  });

export const factHistoryQueryOptions = queryOptions({
  queryKey: factHistoryQueryKey,
  queryFn: async ({ signal }) =>
    (await apiRequest<FactHistory>(`${factsPath}/history` as ApiPath, { signal })).data,
});

export const createPendingFact = async (body: CreateFactRequest): Promise<FactMutation> =>
  (await apiRequest<FactMutation>(factsPath, { method: "POST", body })).data;

export const captureClaimFact = async (
  body: CaptureClaimFactRequest,
): Promise<FactMutation> =>
  (await apiRequest<FactMutation>(`${factsPath}/from-claim` as ApiPath, { method: "POST", body }))
    .data;

export const transitionFact = async (
  factId: string,
  command: "confirm" | "promote",
  body: FactTransitionRequest,
): Promise<FactMutation> =>
  (
    await apiRequest<FactMutation>(`${factPath(factId)}/${command}` as ApiPath, {
      method: "POST",
      body,
    })
  ).data;

export const attachFact = async (
  factId: string,
  body: AttachFactRequest,
): Promise<FactAttachment> =>
  (
    await apiRequest<FactAttachment>(`${factPath(factId)}/attachments` as ApiPath, {
      method: "POST",
      body,
    })
  ).data;

export const confirmAndUseFact = async (
  factId: string,
  body: ConfirmAndUseFactRequest,
): Promise<ConfirmAndUseFact> =>
  (
    await apiRequest<ConfirmAndUseFact>(`${factPath(factId)}/confirm-and-use` as ApiPath, {
      method: "POST",
      body,
    })
  ).data;
