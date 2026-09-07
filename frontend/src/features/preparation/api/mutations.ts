import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import { invalidateApplicationViews, startAnalysis, startDraftGeneration } from "@/api/applications";
import type { ApplicationDetail, Operation } from "@/api/contracts";
import { operationQueryKey } from "@/api/operations";
import { executionProvider, settingsQueryOptions } from "@/api/settings";
import { useSettings } from "@/api/useSettings";
import { type AutoDraftSources, autoDraftSources } from "../model/autoDraft";

/* The commands this feature sends that own no screen state of their own.

   `useWorkflowCommands` is the exception and stays in hooks/: it carries the replace
   dialog's own decision, which is local state the server never sees until the command
   carrying it is sent. */

/* The analyze command on its own, because two surfaces send it and only one of them
   needs anything else. The first analysis of an Application is offered among the
   workflow's next steps; a re-analysis is offered beside the analysis it would replace,
   in the diagnostics tab. Both send this exact command, and reaching it through the full
   command hook mounted the stale-draft version read and the in-flight Operation query a
   second time for a button that needs neither. */
export const useAnalyzeCommand = (detail: ApplicationDetail, onQueued: (operationId: string) => void) => {
  const queryClient = useQueryClient();
  const { settings } = useSettings();
  const provider = executionProvider(settings);
  const snapshotId = detail.active_job_snapshot_id;
  /* One key per snapshot: an answer that never arrived can be sent again without
     queueing a second analysis of the same posting. Derived rather than cached, since a
     discarded useMemo would mint a new key on the same snapshot and break that
     guarantee. */
  const analyzeKey = `analyze:${detail.application.id}:${snapshotId}`;

  const analyze = useMutation({
    mutationFn: () => startAnalysis(detail.application.id, snapshotId, analyzeKey, provider),
    /* Queueing does not navigate. The projection carries `active_operation` in full and
       starts polling the moment it appears, so the screen reports the work in place;
       what the accepted `202` buys is the first state, a poll earlier than the
       projection would report it. */
    onSuccess: ({ operation }) => {
      queryClient.setQueryData(operationQueryKey(operation.id), operation);
      onQueued(operation.id);
      void invalidateApplicationViews(queryClient, detail.application.id);
    },
  });

  return { analyze, provider, settings };
};

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
