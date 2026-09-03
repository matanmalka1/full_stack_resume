import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import { invalidateApplicationViews, startDraftGeneration } from "../../api/applications";
import type { ApplicationDetail, Operation } from "../../api/contracts";
import { operationQueryKey } from "../../api/operations";
import { settingsQueryOptions } from "../../api/settings";
import { type AutoDraftSources, autoDraftSources } from "./autoDraft";

const autoDraftReceiptKey = (operationId: string): string => `stage-e:auto-draft:${operationId}`;

interface AutomaticDraftAttempt {
  sources: AutoDraftSources;
  triggerOperationId: string;
}

/* Owns the Web automation continuation from a successful analysis to its draft.

   Eligibility comes from two server-backed reads only: the watched analyze Operation and
   the Application projection. The mutation's variables prevent another dispatch of the
   same continuation while this hook is mounted; across reloads, the stable command key
   makes a repeated request the same command at the API boundary.

   The session entry is a success receipt retained for the existing screen contract. It is
   deliberately write-only here: it no longer participates in deciding whether work may
   start, so it cannot disagree with the projection or the watched Operation. */
export const useAutomaticDraft = ({
  applicationId,
  detail,
  operation,
  operationId,
  watch,
}: {
  applicationId: string;
  detail: ApplicationDetail | undefined;
  operation: Operation | undefined;
  operationId: string | null;
  watch: (operationId: string) => void;
}) => {
  const queryClient = useQueryClient();
  const settingsQuery = useQuery(settingsQueryOptions);
  const automaticDraft = useMutation({
    mutationFn: ({ sources, triggerOperationId }: AutomaticDraftAttempt) =>
      startDraftGeneration(
        sources.applicationId,
        sources.analysisId,
        sources.planId,
        `auto-draft:${triggerOperationId}:${sources.analysisId}:${sources.planId}`,
      ),
    onSuccess: ({ operation: queued }, attempt) => {
      sessionStorage.setItem(autoDraftReceiptKey(attempt.triggerOperationId), "accepted");
      queryClient.setQueryData(operationQueryKey(queued.id), queued);
      watch(queued.id);
      void invalidateApplicationViews(queryClient, applicationId);
    },
  });

  const attemptedOperationId = automaticDraft.variables?.triggerOperationId ?? null;
  useEffect(() => {
    if (operationId === null || attemptedOperationId === operationId) {
      return;
    }
    const sources = autoDraftSources(operation, settingsQuery.data?.settings, detail);
    if (sources !== null) {
      automaticDraft.mutate({ sources, triggerOperationId: operationId });
    }
  }, [attemptedOperationId, detail, operation, operationId, settingsQuery.data]);
};
