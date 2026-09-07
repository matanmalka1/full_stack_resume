import { useMutation, useQueryClient } from "@tanstack/react-query";

import { invalidateApplicationViews, startAnalysis } from "@/api/applications";
import type { ApplicationDetail } from "@/api/contracts";
import { operationQueryKey } from "@/api/operations";
import { executionProvider } from "@/api/settings";
import { useSettings } from "@/api/useSettings";

/* The analyze command on its own, because two surfaces send it and only one of them
   needs anything else.

   The first analysis of an Application is offered among the workflow's next steps; a
   re-analysis is offered beside the analysis it would replace, in the diagnostics tab.
   Both send this exact command. `ReanalyzeCard` used to reach it through the full
   command hook, which mounted the stale-draft version read and the in-flight Operation
   query a second time for a button that needs neither. */
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
